import io
import json
from pathlib import Path

import numpy as np

from src.live_service import InspectionRuntime, configure_camera, load_service_config
from src.week3 import CameraState, FramePacket


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "live_service.json"


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_live_service_config_defaults_to_svga(monkeypatch) -> None:
    monkeypatch.delenv("RPLA_RESOLUTION", raising=False)
    monkeypatch.delenv("RPLA_FRAMESIZE", raising=False)
    config = load_service_config(CONFIG_PATH)
    assert config.framesize_control_value == 11
    assert config.framesize_name == "SVGA"
    assert (config.expected_width_px, config.expected_height_px) == (800, 600)
    assert config.roi_px == (254, 47, 195, 527)
    assert config.target_min_coverage == 0.80


def test_live_service_config_scales_roi_for_vga(monkeypatch) -> None:
    monkeypatch.setenv("RPLA_RESOLUTION", "VGA")
    monkeypatch.delenv("RPLA_FRAMESIZE", raising=False)
    config = load_service_config(CONFIG_PATH)
    assert config.framesize_control_value == 10
    assert (config.expected_width_px, config.expected_height_px) == (640, 480)
    assert config.roi_px == (203, 38, 156, 422)


def test_camera_configuration_sets_and_verifies_framesize(monkeypatch) -> None:
    monkeypatch.delenv("RPLA_RESOLUTION", raising=False)
    monkeypatch.delenv("RPLA_FRAMESIZE", raising=False)
    config = load_service_config(CONFIG_PATH)
    requested: list[str] = []

    def opener(url: str, timeout: int) -> FakeResponse:
        requested.append(url)
        if url.endswith("/status"):
            return FakeResponse(json.dumps({"framesize": 11}).encode())
        return FakeResponse(b"")

    status = configure_camera(config, opener)
    assert status["framesize"] == 11
    assert "var=framesize&val=11" in requested[0]


def _healthy_packet(config, frame_id: int = 0) -> FramePacket:
    image = np.zeros((config.expected_height_px, config.expected_width_px, 3), dtype=np.uint8)
    return FramePacket(
        source_name=config.source_name,
        frame_id=frame_id,
        captured_at_utc="2026-08-10T00:00:00.000+00:00",
        received_at_utc="2026-08-10T00:00:00.000+00:00",
        camera_state=CameraState.HEALTHY,
        image=image,
    )


def test_runtime_processes_and_exposes_latest_frame() -> None:
    config = load_service_config(CONFIG_PATH)
    runtime = InspectionRuntime(config)
    packet = _healthy_packet(config)
    for _ in range(config.recovery_frames):
        runtime._accept_packet(packet)

    payload = runtime.snapshot_payload()
    version, jpeg = runtime.latest_jpeg()

    assert payload["summary"]["frames_received"] == config.recovery_frames
    # Only the frame that completed the recovery run counts as healthy work.
    assert payload["summary"]["frames_processed_when_healthy"] == 1
    assert payload["summary"]["camera_state"] == "HEALTHY"
    assert payload["summary"]["frame_width_px"] == 800
    assert payload["summary"]["candidate_records"] == 0
    assert payload["summary"]["frame_received_at_utc"] == packet.received_at_utc
    assert payload["summary"]["frame_processed_at_utc"] is not None
    assert payload["summary"]["processing_latency_ms"] >= 0
    assert payload["summary"]["snapshot_published_at_utc"] is not None
    assert payload["summary"]["frame_age_ms"] is not None
    assert version > 0
    assert jpeg is not None and io.BytesIO(jpeg).read(2) == b"\xff\xd8"


def test_single_frame_does_not_re_enable_inspection() -> None:
    """A healthy-looking read must not clear the recovery gate on its own."""
    config = load_service_config(CONFIG_PATH)
    runtime = InspectionRuntime(config)

    runtime._accept_packet(_healthy_packet(config))
    summary = runtime.snapshot_payload()["summary"]
    assert summary["camera_state"] == "RECONNECTING"
    assert summary["automatic_actions_allowed"] is False
    assert summary["recovery_frames_skipped"] == 1


def test_service_downgrades_health_when_frames_stop_arriving() -> None:
    """Frame age, not 'the last read succeeded', decides service health."""
    config = load_service_config(CONFIG_PATH)
    runtime = InspectionRuntime(config)
    for _ in range(config.recovery_frames):
        runtime._accept_packet(_healthy_packet(config))
    assert runtime.snapshot_payload()["summary"]["camera_state"] == "HEALTHY"

    runtime._monitor.last_frame_at_s -= config.stale_after_s + 0.01
    runtime._age_out()
    assert runtime.snapshot_payload()["summary"]["camera_state"] == "STALE"

    runtime._monitor.last_frame_at_s -= config.disconnect_after_s
    runtime._age_out()
    assert runtime.snapshot_payload()["summary"]["camera_state"] == "DISCONNECTED"


def test_backlogged_frames_are_dropped_and_counted() -> None:
    """The one-slot buffer keeps the newest frame and reports what it discarded."""
    config = load_service_config(CONFIG_PATH)
    runtime = InspectionRuntime(config)

    assert runtime.snapshot_payload()["summary"]["dropped_frames"] == 0
    runtime._publish_frame(_healthy_packet(config, frame_id=0))
    runtime._publish_frame(_healthy_packet(config, frame_id=1))

    assert runtime.snapshot_payload()["summary"]["dropped_frames"] == 1
    taken = runtime._take_frame(0.01)
    assert taken is not None and taken.frame_id == 1
    assert runtime._take_frame(0.01) is None


def test_material_presence_gate_rejects_empty_scene_and_accepts_vertical_target() -> None:
    config = load_service_config(CONFIG_PATH)
    runtime = InspectionRuntime(config)
    empty = np.full((config.expected_height_px, config.expected_width_px, 3), 230, dtype=np.uint8)
    target = empty.copy()
    roi_x, _, roi_width, _ = config.roi_px
    stripe_width = max(2, round(roi_width * 0.20))
    stripe_centre = roi_x + roi_width // 2
    target[:, stripe_centre - stripe_width // 2 : stripe_centre + stripe_width // 2] = 50

    assert runtime._material_present(empty) is False
    assert runtime._material_present(target) is True

    dark_background = np.full((config.expected_height_px, config.expected_width_px, 3), 40, dtype=np.uint8)
    assert runtime._material_present(dark_background) is False
