"""Exercise both camera paths through the existing resident pipeline without hardware."""

import json
import sqlite3
import threading
import time
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from src import live_service
from src.live_service import InspectionRuntime, load_service_config
from src.week3 import BaselineVisionProcessor, CameraState, FramePacket, SQLiteInspectionRepository, SyntheticCameraSource
from src.week4.camera import ConnectionPolicy, Esp32MjpegSource
from src.week4.uvc import UsbUvcSource


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/live_service.json"


@pytest.fixture(autouse=True)
def clear_camera_environment(monkeypatch):
    for name in ("RPLA_SOURCE_TYPE", "RPLA_CAMERA_IP", "RPLA_CAMERA_DEVICE", "RPLA_CAMERA_BACKEND",
                 "RPLA_RESOLUTION", "RPLA_FRAMESIZE", "RPLA_STREAM_URL", "RPLA_CONTROL_URL", "RPLA_CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)


def usb_config(monkeypatch, tmp_path):
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    return replace(load_service_config(CONFIG), expected_width_px=320, expected_height_px=180,
                   roi_px=(20, 40, 280, 100), presence_gate_enabled=False,
                   database_path=tmp_path / "usb.db", reconnect_delay_s=0.01)


def test_source_profiles_are_independent_and_usb_ignores_esp32_environment(monkeypatch):
    baseline = load_service_config(CONFIG)
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    monkeypatch.setenv("RPLA_FRAMESIZE", "not-an-esp32-size")
    monkeypatch.setenv("RPLA_CAMERA_IP", "unused.example")
    monkeypatch.setenv("RPLA_CONTROL_URL", "http://unused.example")
    selected = load_service_config(CONFIG)
    assert selected.camera_device == 0
    assert selected.camera_ip is None and selected.framesize_control_value is None
    assert selected.framesize_name == "UHD" and selected.expected_width_px == 3840
    assert selected.roi_px == (0, 0, 3840, 2160)
    assert selected.parameter_status == "UNVALIDATED_BASELINE"
    assert baseline.roi_px == (254, 47, 195, 527)
    assert baseline.framesize_name == "SVGA"
    with pytest.raises(ValueError, match="no network stream"):
        _ = selected.stream_url


def test_legacy_flat_configuration_retains_original_behavior():
    legacy = load_service_config(ROOT / "data/baselines/plan_b_before_uvc_20260906/config/live_service.json")
    current = load_service_config(CONFIG)
    assert legacy.roi_px == current.roi_px
    assert legacy.threshold == current.threshold
    assert legacy.min_area_px == current.min_area_px
    assert legacy.framesize_control_value == 11
    assert legacy.source_type == "esp32_mjpeg"


@pytest.mark.parametrize("change,match", [
    (lambda raw: raw.update(default_source_type="missing"), "source type"),
    (lambda raw: raw["sources"]["usb_uvc"].update(device="https://example.test/frame"), "device"),
    (lambda raw: raw["sources"]["usb_uvc"].update(backend="unknown"), "backend"),
    (lambda raw: raw["sources"]["usb_uvc"]["resolution_profiles"]["UHD"].update(fps=0), "fps"),
    (lambda raw: raw["inspection_profiles"]["plan_a"].update(roi_normalized=[0.9, 0, 0.3, 1]), "ROI"),
])
def test_invalid_source_configuration_fails_before_hardware(tmp_path, change, match):
    raw = json.loads(CONFIG.read_text())
    raw["default_source_type"] = "usb_uvc"
    change(raw)
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=match):
        load_service_config(path)


def test_usb_factory_constructs_without_camera_or_network(monkeypatch, tmp_path):
    config = usb_config(monkeypatch, tmp_path)
    monkeypatch.setattr(cv2, "VideoCapture", lambda *args: pytest.fail("constructor must not open camera"))
    monkeypatch.setattr(live_service, "configure_camera", lambda *args: pytest.fail("USB must not configure ESP32"))
    runtime = InspectionRuntime(config)
    assert isinstance(runtime._make_source(), UsbUvcSource)
    summary = runtime.snapshot_payload()["summary"]
    assert summary["source_type"] == "usb_uvc"
    assert summary["camera_path"] == "PLAN_A_ALC_IMX258_USB_UVC"
    assert "ALC_IMX258_USB" in summary["batch_id"]
    assert summary["frame_width_px"] == 0
    assert summary["requested_width_px"] == 320
    assert summary["hardware_stream_verified"] is False


def test_esp32_factory_defers_http_setup_until_connect(monkeypatch):
    calls = []
    monkeypatch.setattr(live_service, "configure_camera", lambda config: calls.append(config.source_type))
    runtime = InspectionRuntime(load_service_config(CONFIG))
    runtime._make_capture = lambda url: type("Capture", (), {"isOpened": lambda self: True})()
    source = runtime._make_source()
    assert isinstance(source, Esp32MjpegSource) and calls == []
    source.connect()
    assert calls == ["esp32_mjpeg"]


class ControlledCapture:
    """Deliver frames only when the test requests them; no timing-based throughput claims."""

    def __init__(self, frames):
        self.frames = frames
        self.opened = False
        self.allow_read = threading.Semaphore(0)
        self.blocked = threading.Event()
        self.released = False
        self.read_count = 0

    def open(self, device, backend):
        self.opened = True
        return True

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        return True

    def get(self, prop):
        return 0

    def read(self):
        self.blocked.set()
        self.allow_read.acquire(timeout=3)
        self.blocked.clear()
        if self.frames:
            self.read_count += 1
            return True, self.frames.pop(0)
        return False, None

    def release(self):
        self.opened = False
        self.released = True


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("timed out waiting for pipeline state")


def test_usb_frames_reach_database_api_and_jpeg_without_esp32(monkeypatch, tmp_path):
    config = usb_config(monkeypatch, tmp_path)
    synthetic = SyntheticCameraSource(width_px=320, height_px=180)
    synthetic.connect()
    image = next(synthetic.frames(1)).image
    capture = ControlledCapture([image.copy() for _ in range(4)])
    source = UsbUvcSource(0, width_px=320, height_px=180, source_name=config.source_name,
                          capture_factory=lambda: capture)
    monkeypatch.setattr(live_service, "configure_camera", lambda *args: pytest.fail("unexpected ESP32 call"))
    runtime = InspectionRuntime(config, source_factory=lambda: source)
    monkeypatch.setattr(live_service, "_runtime", runtime)
    runtime.start()
    try:
        for number in range(1, 5):
            capture.allow_read.release()
            wait_until(lambda: runtime.snapshot_payload()["summary"]["frames_received"] >= number)
        summary = live_service.health()
        assert summary["camera_state"] == "HEALTHY"
        assert summary["frames_received"] == 4
        assert summary["recovery_frames_skipped"] == 2
        assert summary["camera_source"] == "ALC_IMX258_USB"
        assert summary["physical_measurements_available"] is False
        assert summary["rpla_defect_performance_verified"] is False
        records = live_service.events()["items"]
        assert records and all(row["camera_source"] == config.source_name for row in records)
        assert all(row["size_mm"] is None and row["position_mm"] is None for row in records)
        response = live_service.frame()
        assert response.media_type == "image/jpeg" and response.body[:2] == b"\xff\xd8"
        with sqlite3.connect(config.database_path) as connection:
            count, physical = connection.execute("SELECT COUNT(*), COUNT(size_mm_json) FROM detections").fetchone()
        assert count == len(records) and physical == 0
        assert live_service.reconnect() == {"status": "reconnect_requested"}
    finally:
        runtime._stop_event.set()
        capture.allow_read.release()
        runtime.stop(timeout_s=3)
    assert capture.released
    assert not runtime._thread.is_alive() and not runtime._process_thread.is_alive()


def test_wrong_frame_size_cannot_enter_database_or_healthy_state(monkeypatch, tmp_path):
    config = usb_config(monkeypatch, tmp_path)
    runtime = InspectionRuntime(config)
    packet = FramePacket(config.source_name, 0, "2026-09-06T00:00:00Z", "2026-09-06T00:00:00Z",
                         CameraState.HEALTHY, np.zeros((120, 160, 3), dtype=np.uint8))
    with SQLiteInspectionRepository(config.database_path) as repository:
        repository.start_batch(runtime.batch_id, config.source_name, "OFFLINE_SYNTHETIC_ONLY")
        with pytest.raises(ValueError, match="camera frame"):
            runtime._accept_packet(packet, repository)
        assert repository.list_detections(runtime.batch_id) == []
    summary = runtime.snapshot_payload()["summary"]
    assert summary["frames_received"] == 0 and summary["camera_state"] == "DISCONNECTED"
    assert runtime.latest_jpeg()[1] is None


def test_separate_heuristic_profiles_change_results_without_changing_default():
    source = SyntheticCameraSource()
    source.connect()
    packet = next(source.frames(1))
    original = BaselineVisionProcessor().process(packet, "B")[1]
    isolated = BaselineVisionProcessor(score_base=0.1, score_ceiling=0.2,
                                      contamination_min_area_px=10, reject_area_px=1).process(packet, "A")[1]
    repeated = BaselineVisionProcessor().process(packet, "B")[1]
    assert original and isolated
    assert isolated[0].defect_type == "contamination_candidate"
    assert isolated[0].confidence <= 0.2 < original[0].confidence
    assert original[0].confidence == repeated[0].confidence
    assert original[0].defect_type == repeated[0].defect_type


def test_disconnect_during_inspection_cannot_publish_or_persist_old_frame(monkeypatch, tmp_path):
    config = replace(usb_config(monkeypatch, tmp_path), recovery_frames=1)
    runtime = InspectionRuntime(config)
    source = SyntheticCameraSource(width_px=320, height_px=180, source_name=config.source_name)
    source.connect()
    packet = next(source.frames(1))
    entered = threading.Event()
    resume = threading.Event()
    original = runtime._processor

    class PausedProcessor:
        def process(self, packet, batch):
            entered.set()
            assert resume.wait(3)
            return original.process(packet, batch)

    runtime._processor = PausedProcessor()
    errors = []

    def process_frame():
        try:
            with SQLiteInspectionRepository(config.database_path) as repository:
                repository.start_batch(runtime.batch_id, config.source_name, "OFFLINE_SYNTHETIC_ONLY")
                runtime._accept_packet(packet, repository)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=process_frame)
    worker.start()
    try:
        assert entered.wait(3)
        runtime._monitor.mark_read_failure()
        runtime._set_state(CameraState.DISCONNECTED, "camera unplugged during processing")
    finally:
        resume.set()
        worker.join(3)
    assert not errors and not worker.is_alive()
    summary = runtime.snapshot_payload()["summary"]
    assert summary["camera_state"] == "DISCONNECTED"
    assert summary["last_error"] == "camera unplugged during processing"
    assert summary["detection_active"] is False
    assert summary["candidate_records"] == 0
    assert runtime.latest_jpeg()[1] is None
    with sqlite3.connect(config.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0


def test_reconnect_discards_buffered_frame_from_previous_connection(monkeypatch, tmp_path):
    config = usb_config(monkeypatch, tmp_path)
    runtime = InspectionRuntime(config)
    source = SyntheticCameraSource(width_px=320, height_px=180, source_name=config.source_name)
    source.connect()
    runtime._publish_frame(next(source.frames(1)))
    item = runtime._take_buffered_frame(0.01)
    runtime.request_reconnect()
    runtime._accept_packet(item[0], generation=item[1])
    assert runtime.snapshot_payload()["summary"]["frames_received"] == 0
    assert runtime.snapshot_payload()["summary"]["camera_state"] == "RECONNECTING"


def test_acquisition_fault_invalidates_frame_before_waiting_for_buffer_cleanup(monkeypatch, tmp_path):
    config = replace(usb_config(monkeypatch, tmp_path), recovery_frames=1)
    synthetic = SyntheticCameraSource(width_px=320, height_px=180, source_name=config.source_name)
    synthetic.connect()
    packet = next(synthetic.frames(1))
    fault = threading.Event()
    entered = threading.Event()
    resume = threading.Event()

    class ControlledFaultSource:
        sent = False

        def connect(self):
            pass

        def disconnect(self):
            pass

        def frames(self, count):
            if not self.sent:
                self.sent = True
                yield packet
            else:
                assert fault.wait(3)
                raise ConnectionError("camera unplugged before buffer cleanup")

    source = ControlledFaultSource()
    runtime = InspectionRuntime(config, source_factory=lambda: source)
    original = runtime._processor

    class PausedProcessor:
        def process(self, frame, batch):
            entered.set()
            assert resume.wait(3)
            return original.process(frame, batch)

    runtime._processor = PausedProcessor()
    errors = []

    def process_frame(item):
        try:
            with SQLiteInspectionRepository(config.database_path) as repository:
                repository.start_batch(runtime.batch_id, config.source_name, "OFFLINE_SYNTHETIC_ONLY")
                runtime._accept_packet(item[0], repository, generation=item[1])
        except Exception as exc:
            errors.append(exc)

    reader = threading.Thread(target=runtime._run)
    worker = None
    reader.start()
    try:
        item = runtime._take_buffered_frame(1)
        assert item is not None
        worker = threading.Thread(target=process_frame, args=(item,))
        worker.start()
        assert entered.wait(3)
        # Hold only the buffer lock. The acquisition thread can detect the
        # disconnect, but cannot finish buffer cleanup. An in-flight frame may
        # finish processing here and must already belong to an invalid generation.
        with runtime._buffer_condition:
            fault.set()
            wait_until(lambda: not runtime.snapshot_payload()["summary"]["camera_configured"])
            resume.set()
            worker.join(3)
            assert not worker.is_alive() and not errors
            summary = runtime.snapshot_payload()["summary"]
            assert summary["camera_state"] == "DISCONNECTED"
            assert summary["last_error"] == "camera unplugged before buffer cleanup"
            assert summary["detection_active"] is False
            assert summary["frames_received"] == 0
            assert summary["candidate_records"] == 0
            assert runtime.latest_jpeg()[1] is None
    finally:
        runtime._stop_event.set()
        fault.set()
        resume.set()
        reader.join(3)
        if worker is not None:
            worker.join(3)
    assert not reader.is_alive()
    with sqlite3.connect(config.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0
