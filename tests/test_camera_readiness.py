import io
import json
from urllib.error import URLError

import pytest

from scripts.record_camera_readiness import (
    MAX_RESPONSE_BYTES,
    fetch_json,
    normalize_observation,
    record_readiness,
)


class Clock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


def snapshot(frames, state="HEALTHY", evidence="LIVE_INTEGRATION_ONLY", **extra):
    return {"summary": {
        "evidence_level": evidence, "source_type": "usb_uvc", "camera_source": "PLAN_A_ALC_IMX258_USB_UVC",
        "camera_state": state, "frames_received": frames, "measured_pipeline_fps": 9.0,
        "requested_width_px": 3840, "requested_height_px": 2160,
        "frame_width_px": 1920, "frame_height_px": 1080, **extra,
    }}


def run(tmp_path, responses, **kwargs):
    clock = Clock()
    sequence = iter(responses)
    calls = []

    def fetch(endpoint, timeout):
        calls.append((endpoint, timeout))
        item = next(sequence)
        if isinstance(item, Exception):
            raise item
        return item

    path, summary = record_readiness(
        "http://127.0.0.1:8765/api/week7/health", tmp_path,
        duration_s=len(responses), interval_s=1, fetch=fetch,
        monotonic=clock.monotonic, sleep=clock.sleep, **kwargs,
    )
    return path, summary, calls


def test_records_raw_payloads_actual_mode_and_counted_throughput(tmp_path):
    payloads = [snapshot(100), snapshot(110), snapshot(120)]
    path, result, calls = run(tmp_path, payloads)
    raw = [json.loads(line) for line in (path / "observations.jsonl").read_text().splitlines()]
    assert [record["payload"] for record in raw] == payloads
    assert result["requested_image_sizes_px"] == [[3840, 2160]]
    assert result["actual_image_sizes_px"] == [[1920, 1080]]
    assert result["observed_received_fps"] == 10
    assert result["service_reported_fps"]["median"] == 9
    assert result["evidence_label"] == "LIVE_INTEGRATION_ONLY"
    assert result["hardware_acceptance_passed"] is False
    assert result["r4_r5_r7_verified"] is False
    assert len(calls) == 3
    assert json.loads((path / "summary.json").read_text())["samples"] == 3


def test_disconnect_recovery_and_counter_reset_are_separate_observations(tmp_path):
    _, result, _ = run(tmp_path, [snapshot(100), snapshot(100, "DISCONNECTED"), snapshot(0, "RECONNECTING"), snapshot(10)])
    assert result["disconnect_transitions_observed"] == 1
    assert result["recovery_transitions_observed"] == 1
    assert result["counter_resets_observed"] == 1
    assert result["frames_received_delta_in_contiguous_samples"] == 10
    assert result["counted_interval_s"] == 2


def test_http_gap_is_saved_and_cannot_imply_continuity(tmp_path):
    path, result, _ = run(tmp_path, [snapshot(100), URLError("unavailable"), snapshot(900), snapshot(910)])
    assert result["http_error_samples"] == 1
    assert result["frames_received_delta_in_contiguous_samples"] == 10
    assert result["observed_received_fps"] == 10
    rows = [json.loads(line) for line in (path / "observations.jsonl").read_text().splitlines()]
    assert rows[1]["error"]["type"] == "URLError"


@pytest.mark.parametrize("payload", [snapshot(10, evidence="OFFLINE_SYNTHETIC_ONLY"), {}, {"mode": "plan_a_offline", "evidence_label": "OFFLINE_SYNTHETIC_ONLY"}])
def test_synthetic_or_unknown_is_never_promoted(tmp_path, payload):
    _, result, _ = run(tmp_path, [payload, payload])
    assert result["evidence_label"] != "LIVE_INTEGRATION_ONLY"
    assert result["hardware_acceptance_passed"] is False


def test_configured_live_camera_without_increasing_frames_is_pending(tmp_path):
    _, result, _ = run(tmp_path, [snapshot(100), snapshot(100)])
    assert result["evidence_label"] == "PENDING_REAL_MATERIAL"


def test_all_http_errors_still_leave_reviewable_files(tmp_path):
    path, result, _ = run(tmp_path, [URLError("not running"), ValueError("bad JSON")])
    assert result["observation_status"] == "service_unavailable"
    assert result["evidence_label"] == "PENDING_REAL_MATERIAL"
    assert result["successful_samples"] == 0
    assert (path / "summary.json").exists()


def test_run_directories_never_overwrite_previous_observations(tmp_path):
    first, _, _ = run(tmp_path, [snapshot(10)])
    previous = (first / "summary.json").read_bytes()
    second, _, _ = run(tmp_path, [snapshot(20)])
    assert first != second
    assert (first / "summary.json").read_bytes() == previous


@pytest.mark.parametrize("field,value", [("duration_s", 301), ("duration_s", float("nan")), ("interval_s", 0), ("timeout_s", 11)])
def test_invalid_bounds_fail_before_creating_output(tmp_path, field, value):
    with pytest.raises(ValueError):
        record_readiness("http://localhost:8766/api/week7/health", tmp_path, **{field: value})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("endpoint", ["file:///camera", "http://a:secret@localhost/api/snapshot", "http://localhost/api/control/reconnect", "http://localhost/api/snapshot?token=secret"])
def test_only_get_observation_endpoints_are_accepted(tmp_path, endpoint):
    with pytest.raises(ValueError):
        record_readiness(endpoint, tmp_path)


def test_json_response_is_bounded_and_shape_checked():
    def opener(data):
        return lambda url, timeout: io.BytesIO(data)

    assert fetch_json("http://localhost/api/snapshot", 1, opener=opener(b'{"summary":{}}')) == {"summary": {}}
    with pytest.raises(ValueError, match="2 MiB"):
        fetch_json("http://localhost/api/snapshot", 1, opener=opener(b" " * (MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(ValueError, match="object"):
        fetch_json("http://localhost/api/snapshot", 1, opener=opener(b"[]"))
    with pytest.raises(ValueError, match="Non-finite"):
        fetch_json("http://localhost/api/snapshot", 1, opener=opener(b'{"frames_received": NaN}'))


def test_requested_dimensions_are_not_reused_as_actual_dimensions():
    row = normalize_observation({"source_name": "camera", "image_size_px": [3840, 2160], "camera": {"status": "disconnected"}})
    assert row["actual_image_size_px"] is None
    assert row["camera_state"] == "DISCONNECTED"


def test_camera_health_contract_keeps_driver_request_and_frames_distinct(tmp_path):
    def health(frames):
        return {"mode": "plan_a_camera", "evidence_label": "LIVE_INTEGRATION_ONLY", "camera": {
            "source_evidence": "OFFLINE_FAULT_INJECTION_ONLY", "source_type": "usb_uvc", "source_name": "camera",
            "hardware_stream_verified": False, "frames_received": frames, "status": "HEALTHY", "generation": 1,
            "requested_mode": {"width_px": 3840, "height_px": 2160, "fps": 30, "pixel_format": "MJPG"},
            "reported_properties": {"width_px": 1280, "height_px": 720, "fps": 30},
            "reported_properties_basis": "driver_reported_not_measured", "frame_width_px": 1920, "frame_height_px": 1080,
        }}

    _, result, _ = run(tmp_path, [health(10), health(20)])
    assert result["evidence_label"] == "OFFLINE_FAULT_INJECTION_ONLY"
    assert result["requested_image_sizes_px"] == [[3840, 2160]]
    assert result["actual_image_sizes_px"] == [[1920, 1080]]
    assert result["last_observation"]["driver_reported_properties"]["width_px"] == 1280
    assert result["last_observation"]["requested_fps"] == 30


def test_generation_change_does_not_imply_continuous_throughput(tmp_path):
    def health(frames, generation):
        return {"camera": {"frames_received": frames, "generation": generation, "source_type": "usb_uvc"}}

    _, result, _ = run(tmp_path, [health(100, 1), health(900, 2), health(910, 2)])
    assert result["frames_received_delta_in_contiguous_samples"] == 10
    assert result["observed_received_fps"] == 10
