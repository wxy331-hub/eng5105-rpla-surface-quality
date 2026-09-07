import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import cv2
import pytest

from src.week7.protocol import ProtocolError
from src.week7.workflow import SampleWorkflow


def test_complete_sample_retake_and_restart(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    sample = workflow.create_sample("W7-001")
    session = sample["session_id"]
    with pytest.raises(ValueError):
        workflow.store.complete_sample(session)
    for angle in (0, 60, 120, 180, 240, 300):
        workflow.capture_angle(session, angle)
    with pytest.raises(ValueError, match="retake"):
        workflow.capture_angle(session, 0)
    result = workflow.capture_angle(session, 0, retake=True)
    assert result["completed_views"] == 12
    assert len(result["captures"]) == 14
    assert all(c["size_mm"] is None for c in result["captures"])
    assert any(not c["candidates"] for c in result["current_views"])
    workflow.store.complete_sample(session)
    reopened = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    assert reopened.store.get_sample(session)["status"] == "completed"
    assert reopened.health()["physical_outputs_allowed"] is False
    with pytest.raises(ValueError):
        reopened.capture_angle(session, 60, retake=True)


def test_lighting_fault_records_no_view_and_recovers(tmp_path, sample_capture_config):
    def dark_fault(message):
        if message["lighting_mode"] == "dark_field":
            return {**message, "reference_ok": False}
        return message

    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config, status_transform=dark_fault)
    sample = workflow.store.create_sample("PARTIAL")
    session = sample["session_id"]
    with pytest.raises(ProtocolError):
        workflow.capture_angle(session, 0)
    result = workflow.store.get_sample(session)
    assert result["completed_views"] == 1
    assert result["current_views"][0]["lighting_mode"] == "bright_field"
    assert workflow.health()["last_fault"]
    event_types = [event["event_type"] for event in result["events"]]
    assert "CAPTURE_FAILED" in event_types
    assert event_types[-1] == "SIMULATED_OFF_ACK"
    workflow.status_transform = lambda message: message
    result = workflow.capture_angle(session, 0, retake=True)
    assert result["completed_views"] == 2
    assert len(result["captures"]) == 3


def test_stale_frame_is_not_archived(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    source = workflow.source

    class StaleSource:
        def capture(self):
            packet, stamp = source.capture()
            return packet, stamp - 60

    workflow.source = StaleSource()
    sample = workflow.store.create_sample("STALE")
    with pytest.raises(ProtocolError):
        workflow.capture_angle(sample["session_id"], 0)
    assert workflow.store.get_sample(sample["session_id"])["completed_views"] == 0


@pytest.mark.parametrize("gate", ["ready", "material_present", "reference_ok"])
def test_unready_gate_prevents_frame_capture(tmp_path, gate, sample_capture_config):
    class CountedSource:
        calls = 0

        def capture(self):
            self.calls += 1
            raise AssertionError("An unready branch must never request a frame")

    source = CountedSource()
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config, source=source,
                              status_transform=lambda msg: {**msg, gate: False})
    session = workflow.store.create_sample("UNREADY")["session_id"]
    with pytest.raises(ProtocolError):
        workflow.capture_angle(session, 0)
    assert source.calls == 0


def test_repeated_frame_identity_rejected(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    packet, _ = workflow.source.capture()

    class RepeatedSource:
        def capture(self):
            return packet, workflow.clock()

    workflow.source = RepeatedSource()
    sample = workflow.store.create_sample("REPEATED")
    with pytest.raises(ProtocolError, match="Duplicate"):
        workflow.capture_angle(sample["session_id"], 0)
    assert workflow.store.get_sample(sample["session_id"])["completed_views"] == 1


def test_wrong_source_is_rejected(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    workflow.source.source.source_name = "WRONG_CAMERA"
    session = workflow.store.create_sample("WRONG")["session_id"]
    with pytest.raises(ProtocolError, match="source"):
        workflow.capture_angle(session, 0)
    assert workflow.store.get_sample(session)["completed_views"] == 0


def test_whitespace_sample_and_invalid_angle_are_rejected(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    with pytest.raises(ValueError):
        workflow.store.create_sample("   ")
    session = workflow.store.create_sample("ANGLES")["session_id"]
    for angle in (True, 60.0, -60, 360, "60"):
        with pytest.raises(ValueError):
            workflow.capture_angle(session, angle)


def test_default_plan_a_captures_native_uhd_pair(tmp_path):
    workflow = SampleWorkflow(tmp_path)
    health = workflow.health()
    assert health["image_size_px"] == [3840, 2160]
    assert health["roi_px"] == [168, 864, 3504, 432]
    assert health["capture_granularity"] == "single_view"
    assert health["camera"] == {"status": "not_integrated", "connected": None, "capture_available": False}
    sample = workflow.create_sample("PLAN-A-UHD")
    assert sample["capture_configuration"]["image_size_px"] == [3840, 2160]
    result = workflow.capture_angle(sample["session_id"], 0)
    assert result["completed_views"] == 2
    assert {view["lighting_mode"] for view in result["current_views"]} == {"bright_field", "dark_field"}
    assert result["capture_compatible"]
    for capture in result["captures"]:
        assert capture["source_name"] == "PLAN_A_SYNTHETIC_TRIGGERED"
        assert (capture["image_width_px"], capture["image_height_px"]) == (3840, 2160)
        for kind in ("raw", "annotated"):
            image = cv2.imread(str(workflow.store.image_path(capture["capture_id"], kind)))
            assert image.shape == (2160, 3840, 3)
        assert capture["size_mm"] is None and capture["position_mm"] is None
        assert not capture["physical_outputs_allowed"]
        assert capture["calibration_status"] == "invalid"
        assert len(capture["candidates"]) == 1
        candidate = capture["candidates"][0]
        assert candidate["data_mode"] == "plan_a_synthetic_triggered"
        assert candidate["area_px"] > 10000
        assert candidate["bbox_px"][2] > 100


def test_legacy_small_archive_cannot_mix_with_new_default(tmp_path, sample_capture_config):
    old_config = json.loads(sample_capture_config.read_text(encoding="utf-8"))
    old_config["source_name"] = "WEEK7_SYNTHETIC_TRIGGERED"
    sample_capture_config.write_text(json.dumps(old_config), encoding="utf-8")
    old = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    sample = old.store.create_sample("LEGACY")
    packet, _ = old.source.capture()
    # Model an archive created before configuration events existed.
    old.store.save_capture(sample["session_id"], 0, "bright_field", packet,
                           packet.image, [], lighting_metadata={"simulated": True})
    before = old.store.get_sample(sample["session_id"])
    path = old.store.image_path(before["captures"][0]["capture_id"], "raw")
    original = path.read_bytes()
    upgraded = SampleWorkflow(tmp_path)
    description = upgraded.describe_sample(upgraded.store.get_sample(sample["session_id"]))
    assert not description["capture_compatible"]
    assert description["capture_configuration"]["image_size_px"] == [640, 360]
    with pytest.raises(ValueError, match="Create a new sample session"):
        upgraded.capture_angle(sample["session_id"], 60)
    assert upgraded.store.get_sample(sample["session_id"]) == before
    assert path.read_bytes() == original


def test_new_session_configuration_remains_frozen_across_restart(tmp_path, sample_capture_config):
    old = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    sample = old.create_sample("FROZEN-EMPTY")
    upgraded = SampleWorkflow(tmp_path)
    before = upgraded.store.get_sample(sample["session_id"])
    assert not upgraded.describe_sample(before)["capture_compatible"]
    with pytest.raises(ValueError, match="different capture configuration"):
        upgraded.capture_angle(sample["session_id"], 0)
    assert upgraded.store.get_sample(sample["session_id"]) == before


def test_single_view_capture_keeps_other_lighting_missing(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    session = workflow.create_sample("SEPARATE-LIGHTING")["session_id"]
    first = workflow.capture_view(session, 60, "dark_field")
    assert first["completed_views"] == 1
    assert len(first["captures"]) == 1
    assert first["current_views"][0]["lighting_mode"] == "dark_field"
    assert {"angle_deg": 60, "lighting_mode": "bright_field"} in first["missing_views"]
    requests = [event for event in first["events"] if event["event_type"] == "LIGHTING_REQUEST"]
    assert len(requests) == 1 and requests[0]["details"]["lighting_mode"] == "dark_field"
    assert first["events"][-1]["event_type"] == "SIMULATED_OFF_ACK"

    dark = first["current_views"][0]
    dark_path = workflow.store.image_path(dark["capture_id"], "raw")
    dark_bytes = dark_path.read_bytes()
    second = workflow.capture_view(session, 60, "bright_field")
    assert second["completed_views"] == 2
    assert len(second["captures"]) == 2
    assert next(view for view in second["current_views"] if view["lighting_mode"] == "dark_field") == dark
    assert dark_path.read_bytes() == dark_bytes


def test_single_view_retake_preserves_sibling_and_original_attempt(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    session = workflow.create_sample("SINGLE-RETAKE")["session_id"]
    workflow.capture_view(session, 120, "bright_field")
    before = workflow.capture_view(session, 120, "dark_field")
    original = next(view for view in before["current_views"] if view["lighting_mode"] == "bright_field")
    sibling = next(view for view in before["current_views"] if view["lighting_mode"] == "dark_field")
    original_path = workflow.store.image_path(original["capture_id"], "raw")
    original_bytes = original_path.read_bytes()
    with pytest.raises(ValueError, match="retake"):
        workflow.capture_view(session, 120, "bright_field")
    assert workflow.describe_sample(workflow.store.get_sample(session)) == before

    after = workflow.capture_view(session, 120, "bright_field", retake=True)
    assert after["completed_views"] == 2
    assert len(after["captures"]) == 3
    assert next(view for view in after["current_views"] if view["lighting_mode"] == "dark_field") == sibling
    replacement = next(view for view in after["current_views"] if view["lighting_mode"] == "bright_field")
    assert replacement["supersedes_capture_id"] == original["capture_id"]
    archived = next(view for view in after["captures"] if view["capture_id"] == original["capture_id"])
    assert archived["is_current"] is False
    assert archived["files_present"] is True
    assert original_path.read_bytes() == original_bytes
    requests = [event for event in after["events"] if event["event_type"] == "LIGHTING_REQUEST"]
    assert [event["details"]["lighting_mode"] for event in requests] == ["bright_field", "dark_field", "bright_field"]


def test_single_view_invalid_inputs_and_missing_retake_write_nothing(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    session = workflow.store.create_sample("INPUT-VALIDATION")["session_id"]
    before = workflow.store.get_sample(session)
    for angle, mode, retake in (
        (True, "bright_field", False), (60.0, "bright_field", False),
        (360, "bright_field", False), ("60", "dark_field", False),
        (0, None, False), (0, "both", False), (0, "BRIGHT_FIELD", False),
        (0, ["bright_field"], False), (0, "bright_field", "false"),
        (0, "bright_field", 1), (0, "bright_field", True),
    ):
        with pytest.raises(ValueError):
            workflow.capture_view(session, angle, mode, retake=retake)
        assert workflow.store.get_sample(session) == before
    assert not (tmp_path / "images").exists()


def test_single_view_old_configuration_is_rejected_before_writes(tmp_path, sample_capture_config):
    old = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    session = old.create_sample("OLD-SINGLE-VIEW")["session_id"]
    old.capture_view(session, 0, "bright_field")
    before = old.store.get_sample(session)
    upgraded = SampleWorkflow(tmp_path)
    with pytest.raises(ValueError, match="Create a new sample session"):
        upgraded.capture_view(session, 0, "dark_field")
    assert upgraded.store.get_sample(session) == before


def test_delete_waits_for_in_flight_single_view_capture(tmp_path, sample_capture_config):
    workflow = SampleWorkflow(tmp_path, config_path=sample_capture_config)
    session = workflow.create_sample("DELETE-ACTIVE-CAPTURE")["session_id"]
    source = workflow.source
    capture_started, release_capture, deletion_started = Event(), Event(), Event()

    class WaitingSource:
        def capture(self):
            capture_started.set()
            if not release_capture.wait(5):
                raise RuntimeError("Test capture was not released")
            return source.capture()

    workflow.source = WaitingSource()

    def delete():
        deletion_started.set()
        return workflow.delete_sample(session)

    with ThreadPoolExecutor(max_workers=2) as executor:
        capture = executor.submit(workflow.capture_view, session, 0, "bright_field")
        try:
            assert capture_started.wait(5)
            deletion = executor.submit(delete)
            assert deletion_started.wait(5)
            with pytest.raises(TimeoutError):
                deletion.result(timeout=0.1)
        finally:
            release_capture.set()
        assert capture.result(timeout=5)["completed_views"] == 1
        result = deletion.result(timeout=5)
    assert result["deleted_session_id"] == session
    assert result["deleted_capture_count"] == 1
    assert result["deleted_image_count"] == 2
    assert session not in workflow._controllers
    with pytest.raises(KeyError):
        workflow.store.get_sample(session)
