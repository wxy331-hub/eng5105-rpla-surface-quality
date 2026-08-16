from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from src.week3 import CameraState, FramePacket
from src.week3.models import utc_now_iso
from src.week4 import CameraConnectionMonitor, ConnectionPolicy, Esp32MjpegSource, LatestFrameBuffer
from src.week4_offline_demo import run_week4_offline_demo


def make_packet(frame_id: int) -> FramePacket:
    timestamp = utc_now_iso()
    return FramePacket(
        source_name="TEST",
        frame_id=frame_id,
        captured_at_utc=timestamp,
        received_at_utc=timestamp,
        camera_state=CameraState.HEALTHY,
        image=np.zeros((12, 16, 3), dtype=np.uint8),
    )


def test_connection_monitor_blocks_actions_until_stable_recovery() -> None:
    monitor = CameraConnectionMonitor(ConnectionPolicy(1.0, 2.0, 3))
    assert monitor.begin_connect() is CameraState.CONNECTING
    assert monitor.frame_received(0.0) is CameraState.CONNECTING
    assert monitor.frame_received(0.1) is CameraState.CONNECTING
    assert monitor.frame_received(0.2) is CameraState.HEALTHY
    assert monitor.automatic_actions_allowed
    assert monitor.poll(1.3) is CameraState.STALE
    assert not monitor.automatic_actions_allowed
    assert monitor.poll(2.3) is CameraState.DISCONNECTED
    monitor.begin_connect(reconnect=True)
    assert monitor.frame_received(2.4) is CameraState.RECONNECTING
    assert monitor.frame_received(2.5) is CameraState.RECONNECTING
    assert monitor.frame_received(2.6) is CameraState.HEALTHY


def test_latest_frame_buffer_discards_backlog() -> None:
    buffer = LatestFrameBuffer()
    buffer.put(make_packet(1))
    buffer.put(make_packet(2))
    packet = buffer.take()
    assert packet is not None and packet.frame_id == 2
    assert buffer.dropped_frames == 1
    assert buffer.take() is None


class FakeCapture:
    def __init__(self, _url: str) -> None:
        self.opened = True
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        return True, np.zeros((24, 32, 3), dtype=np.uint8)

    def release(self) -> None:
        self.released = True
        self.opened = False


def test_mjpeg_adapter_contract_with_fake_capture() -> None:
    source = Esp32MjpegSource("http://192.0.2.1:81/stream", capture_factory=FakeCapture)
    source.connect()
    packets = list(source.frames(3))
    assert [packet.frame_id for packet in packets] == [0, 1, 2]
    assert packets[-1].camera_state is CameraState.HEALTHY
    source.disconnect()
    assert source.state is CameraState.DISCONNECTED


def test_mjpeg_adapter_counts_frames_across_single_frame_generators() -> None:
    """The resident service pulls one frame per generator, so the counter must
    advance before the yield rather than after it."""
    source = Esp32MjpegSource("http://192.0.2.1:81/stream", capture_factory=FakeCapture)
    source.connect()
    assert [next(source.frames(1)).frame_id for _ in range(3)] == [0, 1, 2]
    source.disconnect()


def test_mjpeg_adapter_marks_read_failure_as_disconnected() -> None:
    class FailingCapture(FakeCapture):
        def read(self):
            return False, None

    source = Esp32MjpegSource("http://192.0.2.1:81/stream", capture_factory=FailingCapture)
    source.connect()
    with pytest.raises(ConnectionError, match="frame read failed"):
        next(source.frames(1))
    assert source.state is CameraState.DISCONNECTED


def test_mjpeg_adapter_rejects_unresolved_placeholder() -> None:
    source = Esp32MjpegSource("http://<ESP32_IP>:81/stream", capture_factory=FakeCapture)
    with pytest.raises(ValueError, match="actual device address"):
        source.connect()


def test_week4_demo_produces_honest_offline_evidence(tmp_path) -> None:
    config = {
        "batch_id": "TEST-W4",
        "width_px": 320,
        "height_px": 180,
        "seed": 5105,
        "roi_px": [28, 70, 264, 40],
        "threshold": 145,
        "min_area_px": 30,
        "stale_after_s": 1.0,
        "disconnect_after_s": 2.0,
        "recovery_frames": 3,
    }
    summary = run_week4_offline_demo(config, tmp_path)
    assert summary["status"] == "PASS"
    assert summary["evidence_level"] == "OFFLINE_FAULT_INJECTION_ONLY"
    assert summary["hardware_performance_verified"] is False
    assert summary["physical_measurements_available"] is False
    assert {"HEALTHY", "STALE", "DISCONNECTED", "RECONNECTING"} <= set(
        summary["states_exercised"]
    )
    assert summary["frames_blocked_during_connection_recovery"] > 0
    with sqlite3.connect(tmp_path / "week4_offline.db") as connection:
        physical_values = connection.execute(
            "SELECT COUNT(position_mm), COUNT(size_mm_json) FROM detections"
        ).fetchone()
        event_count = connection.execute("SELECT COUNT(*) FROM system_events").fetchone()[0]
    assert physical_values == (0, 0)
    assert event_count > 0
