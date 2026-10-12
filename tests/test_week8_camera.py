"""Injected-camera software checks; these do not establish hardware performance."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import socket
import sqlite3
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uvicorn
from websockets.sync.client import connect
from dataclasses import replace
from pathlib import Path
from queue import Queue
import threading
import time

import cv2
import numpy as np
import pytest

from src.camera_config import load_service_config
from src.live_service import CameraCaptureError, InspectionRuntime
from src.week3 import CameraState, FramePacket
from src.week3.models import utc_now_iso
from src.week7.store import ANGLES, LIGHTING_MODES, SampleStore
from src.week8.workflow import CameraSampleWorkflow
from src.week8_service import create_app


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Timed out waiting for test synchronization")


class InjectedCamera:
    def __init__(self):
        self.items = Queue()
        self.opens = 0
        self.closes = 0
        self.reported_properties = {"width_px": 64.0, "height_px": 48.0, "fps": 30.0}

    def connect(self):
        self.opens += 1

    def disconnect(self):
        self.closes += 1

    def frames(self, limit):
        packet = self.items.get(timeout=3)
        if isinstance(packet, Exception):
            raise packet
        yield packet


class Harness:
    def __init__(self, config):
        self.config = config
        self.source = InjectedCamera()
        self.runtime = InspectionRuntime(config, source_factory=lambda: self.source)
        self.frame_id = 0

    def deliver(self, *, wait_processed=True, shape=(48, 64, 3), state=CameraState.HEALTHY):
        stamp = utc_now_iso()
        packet = FramePacket(self.config.source_name, self.frame_id, stamp, stamp, state,
                             np.full(shape, 220 - self.frame_id % 100, np.uint8))
        self.frame_id += 1
        before = self.runtime.snapshot_payload()["summary"]["frames_received"]
        self.source.items.put(packet)
        if wait_processed:
            wait_until(lambda: self.runtime.snapshot_payload()["summary"]["frames_received"] > before)
        return packet

    def healthy(self):
        self.runtime.start()
        for _ in range(self.config.recovery_frames):
            self.deliver()
        assert self.runtime.camera_health()["capture_available"] is True

    def close(self):
        self.runtime._stop_event.set()
        self.source.items.put(ConnectionError("injected test teardown"))
        self.runtime.stop(timeout_s=2)


@pytest.fixture
def harness(monkeypatch, tmp_path):
    for name in ("RPLA_RESOLUTION", "RPLA_FRAMESIZE", "RPLA_CAMERA_DEVICE", "RPLA_CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    config = replace(load_service_config(), expected_width_px=64, expected_height_px=48,
                     roi_px=(0, 0, 64, 48), recovery_frames=2, stale_after_s=2.0,
                     disconnect_after_s=4.0, reconnect_delay_s=0.01,
                     database_path=tmp_path / "continuous.db")
    result = Harness(config)
    yield result
    result.close()


def capture_next(workflow, harness, session, angle=0, mode="bright_field", **kwargs):
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(workflow.capture_view, session, angle, mode, **kwargs)
        wait_until(lambda: bool(harness.runtime._raw_condition._waiters))
        expected = harness.deliver()
        return pending.result(timeout=3), expected


def test_preview_and_sample_share_source_and_capture_requires_a_new_raw_frame(harness, tmp_path):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("sample-001")["session_id"]
    before = harness.runtime.latest_jpeg()
    result, expected = capture_next(workflow, harness, session)
    assert harness.source.opens == 1
    assert len(result["current_views"]) == 1
    capture = result["current_views"][0]
    archived = cv2.imread(str(workflow.store.image_path(capture["capture_id"], "raw")))
    assert np.array_equal(archived, expected.image)
    assert harness.runtime.latest_jpeg()[0] > before[0]
    assert capture["evidence_label"] == "OFFLINE_FAULT_INJECTION_ONLY"
    assert all(event["evidence_label"] == "OFFLINE_FAULT_INJECTION_ONLY" for event in result["events"])
    lighting = capture["lighting_metadata"]
    assert lighting["captured_monotonic"] > lighting["requested_monotonic"]
    assert lighting["verification"] == "operator_declared"
    assert lighting["sensor_confirmed"] is lighting["simulated"] is False
    assert capture["size_mm"] is capture["position_mm"] is capture["calibration_id"] is None
    assert harness.runtime.camera_health()["hardware_stream_verified"] is False
    assert harness.runtime.camera_health()["reported_properties"]["fps"] == 30.0
    assert workflow.processor.params.search_roi_px == harness.config.roi_px
    assert workflow.capture_configuration["vision_algorithm"] == "static_rpla_geometry"


def test_complete_twelve_views_retake_csv_and_delete_preserve_contract(harness, tmp_path):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("all-views")["session_id"]
    for angle in ANGLES:
        for mode in LIGHTING_MODES:
            result, _ = capture_next(workflow, harness, session, angle, mode)
    assert result["completed_views"] == 12
    original = result["current_views"][0]["capture_id"]
    with pytest.raises(ValueError, match="explicit retake"):
        workflow.capture_view(session, 0, "bright_field")
    retaken, _ = capture_next(workflow, harness, session, retake=True)
    assert len(retaken["captures"]) == 13 and retaken["completed_views"] == 12
    assert workflow.store.image_path(original, "raw").is_file()
    completed = workflow.store.complete_sample(session)
    assert completed["status"] == "completed"
    assert "OFFLINE_FAULT_INJECTION_ONLY" in workflow.store.export_csv(session)
    assert "operator_declared" in workflow.store.export_csv(session)
    with pytest.raises(ValueError, match="in-progress"):
        workflow.capture_view(session, 0, "bright_field", retake=True)
    deleted = workflow.delete_sample(session)
    assert deleted["deleted_capture_count"] == 13
    assert deleted["cleanup_pending"] is False


def test_disconnected_recovering_stale_and_timeout_never_archive(harness, tmp_path):
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime, capture_timeout_s=0.08)
    session = workflow.create_sample("gates")["session_id"]
    with pytest.raises(CameraCaptureError, match="disconnected"):
        workflow.capture_view(session, 0, "bright_field")
    harness.runtime.start()
    harness.deliver()
    with pytest.raises(CameraCaptureError, match="recovering"):
        workflow.capture_view(session, 0, "bright_field")
    harness.deliver()
    with pytest.raises(CameraCaptureError, match="Timed out"):
        workflow.capture_view(session, 0, "bright_field")
    harness.runtime._raw_acquired_monotonic -= 3
    with pytest.raises(CameraCaptureError, match="stale"):
        workflow.capture_view(session, 0, "bright_field")
    assert workflow.store.get_sample(session)["captures"] == []


def test_capture_inspection_time_is_not_counted_as_frame_age(harness, tmp_path, monkeypatch):
    # 2026-10-12 bench: every in-focus 4K view failed as "stale" because the
    # capture's own inspection and PNG encoding pushed the frame past the
    # freshness limit before commit. Freshness is judged when the frame is
    # selected; here 3 s (> stale_after_s) pass between selection and commit.
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("slow-inspection")["session_id"]
    select = harness.runtime.capture_fresh_frame
    monkeypatch.setattr(harness.runtime, "capture_fresh_frame", lambda timeout_s: replace(
        lease := select(timeout_s), acquired_monotonic=lease.acquired_monotonic - 3,
        requested_monotonic=lease.requested_monotonic - 3))
    result, expected = capture_next(workflow, harness, session)
    assert len(result["current_views"]) == 1


def test_capture_is_refused_if_the_camera_stalled_and_recovered_meanwhile(harness, tmp_path, monkeypatch):
    # A USB source can stall and recover on the same handle, so the connection
    # generation does not change; the capture must still not archive the frame
    # selected before the interruption (Codex review 2026-10-12).
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("stall-recover")["session_id"]
    inspect = workflow.processor.inspect

    def stall_then_recover(*args, **kwargs):
        with harness.runtime._condition:
            harness.runtime._raw_acquired_monotonic -= 3  # no raw frame for longer than stale_after_s
        harness.deliver()
        assert harness.runtime._state is CameraState.HEALTHY
        return inspect(*args, **kwargs)

    monkeypatch.setattr(workflow.processor, "inspect", stall_then_recover)
    with pytest.raises(CameraCaptureError, match="remain healthy"):
        capture_next(workflow, harness, session)
    assert workflow.store.get_sample(session)["captures"] == []


def test_capture_archives_while_preview_processing_still_lags(harness, tmp_path, monkeypatch):
    # 2026-10-12 bench (white specimen, ~0.85 s preview frames): the capture's own
    # inspection slowed the preview past stale_after_s, the service read STALE at
    # commit, and every capture failed although raw frames kept arriving.
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("lagging-preview")["session_id"]
    inspect = workflow.processor.inspect

    def lagging_preview(*args, **kwargs):
        runtime = harness.runtime
        with runtime._condition:
            runtime._monitor.last_frame_at_s -= 3  # the processed frame aged past stale_after_s
        runtime._age_out()
        assert runtime._state is CameraState.STALE
        return inspect(*args, **kwargs)

    monkeypatch.setattr(workflow.processor, "inspect", lagging_preview)
    result, _ = capture_next(workflow, harness, session)
    assert len(result["current_views"]) == 1


def test_slow_preview_processing_does_not_void_a_capture(harness, tmp_path, monkeypatch):
    # Second review round: the service monitor is fed by preview processing, so
    # one slow preview frame marks the service stale although raw frames kept
    # arriving. Once healthy again, the capture must still archive.
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("slow-preview")["session_id"]
    inspect = workflow.processor.inspect

    def slow_preview_then_recover(*args, **kwargs):
        runtime = harness.runtime
        with runtime._condition:
            runtime._monitor.last_frame_at_s -= 3  # the processed frame aged past stale_after_s
        runtime._age_out()
        assert runtime._state is CameraState.STALE
        for _ in range(harness.config.recovery_frames):
            harness.deliver()
        assert runtime._state is CameraState.HEALTHY
        return inspect(*args, **kwargs)

    monkeypatch.setattr(workflow.processor, "inspect", slow_preview_then_recover)
    result, _ = capture_next(workflow, harness, session)
    assert len(result["current_views"]) == 1


def test_reconnect_invalidates_waiting_request_and_clears_preview(harness, tmp_path):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("reconnect")["session_id"]
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(workflow.capture_view, session, 0, "bright_field")
        wait_until(lambda: bool(harness.runtime._raw_condition._waiters))
        harness.runtime.request_reconnect()
        with pytest.raises(CameraCaptureError, match="connection changed"):
            pending.result(timeout=3)
    assert harness.runtime.latest_jpeg()[1] is None
    assert workflow.store.get_sample(session)["captures"] == []


def test_disconnect_while_writing_images_rolls_back_attempt(harness, tmp_path, monkeypatch):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("write-disconnect")["session_id"]
    original_write = workflow.store._write_image
    def disconnect_after_write(path, data):
        original_write(path, data)
        if path.name == "annotated.png":
            harness.runtime.request_reconnect()
    monkeypatch.setattr(workflow.store, "_write_image", disconnect_after_write)
    with pytest.raises(CameraCaptureError, match="connection changed"):
        capture_next(workflow, harness, session)
    sample = workflow.store.get_sample(session)
    assert sample["captures"] == []
    assert not any(event["event_type"] == "CAPTURE_ARCHIVED" for event in sample["events"])
    assert list((workflow.root / "images").rglob("*.png")) == []


def test_config_change_and_missing_configuration_are_rejected(harness, tmp_path):
    root = tmp_path / "sample"
    workflow = CameraSampleWorkflow(root, harness.runtime)
    session = workflow.create_sample("config-frozen")["session_id"]
    other = InspectionRuntime(replace(harness.config, threshold=99), source_factory=lambda: harness.source)
    changed = CameraSampleWorkflow(root, other)
    assert changed.describe_sample(changed.store.get_sample(session))["capture_compatible"] is False
    with pytest.raises(ValueError, match="different camera configuration"):
        changed.capture_view(session, 0, "bright_field")
    legacy = changed.store.create_sample("missing-config")
    with pytest.raises(ValueError, match="missing"):
        changed.capture_view(legacy["session_id"], 0, "bright_field")


def test_sample_stores_never_relabel_an_existing_database(tmp_path):
    legacy = SampleStore(tmp_path)
    session = legacy.create_sample("historical")
    with pytest.raises(ValueError, match="separate database"):
        SampleStore(tmp_path, evidence_label="LIVE_INTEGRATION_ONLY")
    assert legacy.get_sample(session["session_id"])["evidence_label"] == "OFFLINE_SYNTHETIC_ONLY"
    with pytest.raises(ValueError, match="filename"):
        SampleStore(tmp_path, database_name="../elsewhere.sqlite3")


@contextmanager
def local_server(app):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        wait_until(lambda: server.started)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()


def request(base, path, body=None):
    req = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                  headers={} if body is None else {"Content-Type": "application/json"})
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        data = response.read()
        if "application/json" in response.headers.get("Content-Type", ""):
            data = json.loads(data)
        return response.status, data


def test_api_uses_one_runtime_and_deferred_start_does_not_open_camera(harness, tmp_path):
    app = create_app(tmp_path / "api", runtime=harness.runtime, connect_on_start=False)
    with local_server(app) as base:
        health = request(base, "/api/week7/health")[1]
        assert health["mode"] == "plan_a_camera"
        assert health["camera"]["connection_deferred"] is True
        assert health["camera"]["capture_available"] is False
        assert health["image_size_px"] == [0, 0]
        assert harness.source.opens == 0
        assert request(base, "/api/frame.jpg")[0] == 503
        session = request(base, "/api/week7/samples", {"sample_id": "api"})[1]["session_id"]
        assert request(base, f"/api/week7/samples/{session}/capture",
                       {"angle_deg": 0, "lighting_mode": "bright_field"})[0] == 503
        assert request(base, "/api/control/reconnect", {})[0] == 200
        wait_until(lambda: harness.source.opens == 1)
        for _ in range(harness.config.recovery_frames):
            harness.deliver()
        assert request(base, "/api/week7/health")[1]["camera"]["capture_available"] is True
        assert request(base, "/api/snapshot")[1]["summary"]["frames_received"] == 2
        assert request(base, "/api/frame.jpg")[0] == 200
        with urlopen(base + "/api/stream.mjpg", timeout=3) as preview:
            assert preview.headers["Content-Type"].startswith("multipart/x-mixed-replace")
            assert b"Content-Type: image/jpeg" in preview.read(128)
        with connect(base.replace("http:", "ws:") + "/ws") as websocket:
            assert json.loads(websocket.recv(timeout=3))["summary"]["camera_state"] == "HEALTHY"
        with ThreadPoolExecutor(1) as pool:
            pending = pool.submit(request, base, f"/api/week7/samples/{session}/capture",
                                  {"angle_deg": 60, "lighting_mode": "dark_field"})
            wait_until(lambda: bool(harness.runtime._raw_condition._waiters))
            harness.deliver()
            status, saved = pending.result(timeout=3)
        assert status == 200 and saved["completed_views"] == 1
        capture_id = saved["captures"][0]["capture_id"]
        assert request(base, f"/api/week7/captures/{capture_id}/raw.png")[1].startswith(b"\x89PNG")
        assert b"OFFLINE_FAULT_INJECTION_ONLY" in request(base, f"/api/week7/samples/{session}/export.csv")[1]
        assert harness.source.opens == 1
        harness.close()


def test_processing_fault_requests_reconnect_instead_of_dropping_forever(harness):
    harness.healthy()
    generation = harness.runtime.camera_health()["generation"]
    harness.deliver(wait_processed=False, shape=(16, 16, 3))
    wait_until(lambda: harness.runtime._reconnect_event.is_set())
    harness.deliver(wait_processed=False)
    wait_until(lambda: harness.source.opens >= 2)
    assert harness.runtime.camera_health()["generation"] > generation
    for _ in range(harness.config.recovery_frames):
        harness.deliver()
    assert harness.runtime.camera_health()["capture_available"] is True


def test_duplicate_source_frame_is_rejected(harness):
    harness.healthy()
    packet = harness.runtime._raw_packet
    with pytest.raises(CameraCaptureError, match="Duplicate"):
        harness.runtime._publish_frame(packet)


@pytest.mark.parametrize("reject_table", ["captures", "sample_events"])
@pytest.mark.parametrize("reject_failure_event", [False, True])
def test_archive_sql_failure_rolls_back_and_keeps_original_error(
        harness, tmp_path, reject_table, reject_failure_event):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("sql-failure")["session_id"]
    before, _ = capture_next(workflow, harness, session)
    images = {path: path.read_bytes() for path in workflow.root.rglob("*.png")}
    condition = "WHEN NEW.event_type = 'CAPTURE_ARCHIVED' " if reject_table == "sample_events" else ""
    with workflow.store._connection() as connection:
        connection.execute(f"CREATE TRIGGER reject_archive BEFORE INSERT ON {reject_table} "
                           f"{condition}BEGIN SELECT RAISE(ABORT, 'primary archive failure'); END")
        if reject_failure_event:
            connection.execute("CREATE TRIGGER reject_failure_event BEFORE INSERT ON sample_events "
                               "WHEN NEW.event_type = 'CAPTURE_FAILED' "
                               "BEGIN SELECT RAISE(ABORT, 'secondary event failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match="primary archive failure") as caught:
        capture_next(workflow, harness, session, retake=True)
    after = workflow.store.get_sample(session)
    assert after["captures"] == before["captures"]
    assert {path: path.read_bytes() for path in workflow.root.rglob("*.png")} == images
    assert not list(workflow.root.rglob("*.pending"))
    assert workflow.health()["last_fault"] == "primary archive failure"
    failures = [event for event in after["events"] if event["event_type"] == "CAPTURE_FAILED"]
    if reject_failure_event:
        assert not failures
        assert any("secondary event failure" in note for note in caught.value.__notes__)
    else:
        assert failures[-1]["details"]["error"] == "primary archive failure"


def test_composed_api_uses_configured_cors_origins(harness, tmp_path):
    origin = "http://127.0.0.1:5199"
    runtime = InspectionRuntime(replace(harness.config, cors_allow_origins=(origin,)),
                                source_factory=lambda: harness.source)
    app = create_app(tmp_path / "cors", runtime=runtime, connect_on_start=False)
    with local_server(app) as base:
        for path in ("/api/week7/health", "/api/snapshot"):
            req = Request(base + path, method="OPTIONS", headers={
                "Origin": origin, "Access-Control-Request-Method": "GET",
            })
            with urlopen(req, timeout=3) as response:
                assert response.status == 200
                assert response.headers["Access-Control-Allow-Origin"] == origin
        req = Request(base + "/api/week7/health", method="OPTIONS", headers={
            "Origin": "http://127.0.0.1:5177", "Access-Control-Request-Method": "GET",
        })
        with pytest.raises(HTTPError) as denied:
            urlopen(req, timeout=3)
        assert denied.value.code == 400
        denied.value.close()
    assert harness.source.opens == 0


def test_static_branch_archives_a_rejected_view_with_its_reasons(harness, tmp_path):
    harness.healthy()
    workflow = CameraSampleWorkflow(tmp_path / "sample", harness.runtime)
    session = workflow.create_sample("static-001")["session_id"]
    result, _ = capture_next(workflow, harness, session)
    capture = result["current_views"][0]
    # A uniform injected frame has no specimen: archived, but not judged.
    assert capture["candidates"] == []
    assert capture["analysis_status"] == "rejected"
    assert "SAMPLE_NOT_LOCALIZED" in capture["analysis"]["reason_codes"]
    summary = result["inspection_summary"]
    assert summary["conclusion"] == "geometry_coverage_incomplete"
    assert summary["geometry_rejected"][0]["angle_deg"] == 0
    assert workflow.health()["algorithm_version"] == "static-rpla-geometry-surface-8"
    preview = harness.runtime.snapshot_payload()["summary"]
    assert preview["vision_algorithm"] == "static_rpla_geometry"
    assert preview["view_inspection"]["lighting"] == "operator_declared_bright_field"
    assert preview["view_inspection"]["surface"]["status"] == "rejected"
    assert preview["target_present"] is False
