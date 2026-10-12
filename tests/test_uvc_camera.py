from __future__ import annotations

import cv2
import numpy as np
import pytest

from src.week3.models import CameraState
from src.week4.camera import ConnectionPolicy
from src.week4.uvc import UsbUvcSource


class FakeCapture:
    def __init__(self) -> None:
        self.opened = False
        self.open_result = True
        self.open_args = None
        self.properties = {}
        self.rejected_property = None
        self.image = np.zeros((24, 32, 3), dtype=np.uint8)
        self.read_result = True
        self.read_error = None
        self.release_error = None
        self.release_calls = 0

    def open(self, device, backend):
        self.open_args = (device, backend)
        self.opened = self.open_result
        return self.open_result

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.properties[prop] = value
        return prop != self.rejected_property

    def get(self, prop):
        return self.properties.get(prop, 0.0)

    def read(self):
        if self.read_error:
            raise self.read_error
        return self.read_result, self.image

    def release(self):
        self.release_calls += 1
        self.opened = False
        if self.release_error:
            raise self.release_error


def source_with(capture, **kwargs):
    return UsbUvcSource(0, width_px=32, height_px=24, capture_factory=lambda: capture, **kwargs)


@pytest.mark.parametrize("backend, expected", [
    ("auto", cv2.CAP_ANY), ("dshow", cv2.CAP_DSHOW),
    ("msmf", cv2.CAP_MSMF), ("v4l2", cv2.CAP_V4L2),
])
def test_opens_requested_backend_and_requests_mode_without_claiming_health(backend, expected):
    capture = FakeCapture()
    source = source_with(capture, backend=backend, fps=12.5)
    source.connect()
    assert capture.open_args == (0, expected)
    assert capture.properties == {
        cv2.CAP_PROP_FOURCC: cv2.VideoWriter_fourcc(*"MJPG"),
        cv2.CAP_PROP_FRAME_WIDTH: 32,
        cv2.CAP_PROP_FRAME_HEIGHT: 24,
        cv2.CAP_PROP_FPS: 12.5,
    }
    assert source.state is CameraState.CONNECTING
    assert not source.monitor.automatic_actions_allowed
    assert source.reported_properties["fps"] == 12.5
    source.disconnect()


@pytest.mark.parametrize("fps", [None, 30])
def test_dshow_retains_mjpg_when_mode_changes_reset_driver_format(fps):
    class FormatResettingCapture(FakeCapture):
        def set(self, prop, value):
            accepted = super().set(prop, value)
            # The real DirectShow device renegotiates YUY2 on mode changes.
            if prop in {cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS}:
                self.properties[cv2.CAP_PROP_FOURCC] = cv2.VideoWriter_fourcc(*"YUY2")
            return accepted

    capture = FormatResettingCapture()
    source = UsbUvcSource(1, width_px=3840, height_px=2160, backend="dshow", fps=fps,
                          capture_factory=lambda: capture)
    try:
        source.connect()
        assert source.reported_properties["fourcc"] == cv2.VideoWriter_fourcc(*"MJPG")
    finally:
        source.disconnect()


@pytest.mark.parametrize("device", [-1, True, 1.5, None, "", "-1", "http://camera/stream",
    "rtsp://camera/live", "C:\\video.avi", "clip.mp4", "/tmp/video0", "/dev/video0/other",
    "/dev/v4l/by-id/..", "/dev/v4l/by-id/../video0"])
def test_rejects_non_camera_inputs_before_capture_is_created(device):
    with pytest.raises(ValueError, match="UVC device"):
        UsbUvcSource(device, width_px=32, height_px=24, capture_factory=lambda: pytest.fail("opened I/O"))


@pytest.mark.parametrize("device, expected", [(2, 2), ("2", 2), ("/dev/video0", "/dev/video0"),
    ("/dev/v4l/by-id/usb-inspection-video-index0", "/dev/v4l/by-id/usb-inspection-video-index0")])
def test_accepts_only_local_device_identifiers(device, expected):
    capture = FakeCapture()
    source = UsbUvcSource(device, width_px=32, height_px=24, capture_factory=lambda: capture)
    source.connect()
    assert capture.open_args[0] == expected
    source.disconnect()


@pytest.mark.parametrize("kwargs, message", [
    ({"backend": "ffmpeg"}, "backend"), ({"backend": None}, "backend"),
    ({"width_px": 0}, "width_px"), ({"height_px": -1}, "height_px"),
    ({"width_px": 32.0}, "width_px"), ({"width_px": True}, "width_px"),
    ({"pixel_format": "MJPEG"}, "pixel_format"), ({"pixel_format": "MJ P"}, "pixel_format"),
    ({"fps": 0}, "fps"), ({"fps": float("nan")}, "fps"),
    ({"fps": float("inf")}, "fps"), ({"fps": "30"}, "fps"),
    ({"source_name": " "}, "source_name"),
])
def test_rejects_invalid_mode_configuration(kwargs, message):
    config = {"width_px": 32, "height_px": 24, **kwargs}
    with pytest.raises(ValueError, match=message):
        UsbUvcSource(0, **config)


def test_windows_backend_rejects_linux_path():
    with pytest.raises(ValueError, match="numeric device index"):
        UsbUvcSource("/dev/video0", width_px=32, height_px=24, backend="dshow")


def test_valid_configuration_does_not_create_capture_until_connect():
    calls = []

    def factory():
        calls.append("created")
        return FakeCapture()

    source = UsbUvcSource("2", width_px=32, height_px=24, capture_factory=factory)
    assert source.device == 2
    assert calls == []
    source.connect()
    assert calls == ["created"]
    source.disconnect()


def test_device_shaped_path_cannot_open_an_existing_regular_file(monkeypatch):
    monkeypatch.setattr("src.week4.uvc.Path.exists", lambda _path: True)
    monkeypatch.setattr("src.week4.uvc.Path.is_char_device", lambda _path: False)
    with pytest.raises(ValueError, match="character device, not a file"):
        UsbUvcSource("/dev/video99", width_px=32, height_px=24)


@pytest.mark.parametrize("prop", [cv2.CAP_PROP_FOURCC, cv2.CAP_PROP_FRAME_WIDTH,
    cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS])
def test_unsupported_mode_fails_and_releases_capture(prop):
    capture = FakeCapture()
    capture.rejected_property = prop
    source = source_with(capture, fps=30)
    with pytest.raises(ConnectionError, match="rejected requested"):
        source.connect()
    assert source.state is CameraState.DISCONNECTED
    assert capture.release_calls == 1
    with pytest.raises(ConnectionError, match="must be connected"):
        next(source.frames(1))


def test_open_failure_releases_capture_and_factory_error_keeps_disconnected_state():
    capture = FakeCapture()
    capture.open_result = False
    source = source_with(capture)
    with pytest.raises(ConnectionError, match="could not open UVC"):
        source.connect()
    assert capture.release_calls == 1
    assert source.state is CameraState.DISCONNECTED

    def fail_factory():
        raise RuntimeError("driver unavailable")

    source.capture_factory = fail_factory
    with pytest.raises(ConnectionError, match="driver unavailable"):
        source.connect()
    assert source.state is CameraState.DISCONNECTED


@pytest.mark.parametrize("stage", ["open", "set"])
def test_unexpected_setup_exceptions_are_connection_errors_and_release_capture(stage):
    capture = FakeCapture()

    def driver_error(*_args):
        raise RuntimeError("backend failure")

    setattr(capture, stage, driver_error)
    source = source_with(capture)
    with pytest.raises(ConnectionError, match="UVC device setup failed: backend failure"):
        source.connect()
    assert source.state is CameraState.DISCONNECTED
    assert capture.release_calls == 1


def test_actual_frame_dimensions_override_misleading_driver_getters():
    capture = FakeCapture()
    source = source_with(capture)
    source.connect()
    assert source.reported_properties["width_px"] == 32
    capture.image = np.zeros((12, 16, 3), dtype=np.uint8)
    with pytest.raises(ConnectionError, match="16x12 does not match requested 32x24"):
        next(source.frames(1))
    assert source.state is CameraState.DISCONNECTED
    assert capture.release_calls == 1


@pytest.mark.parametrize("image", [None, np.array([]), np.zeros((24, 32), dtype=np.uint8),
    np.zeros((24, 32, 4), dtype=np.uint8), np.zeros((24, 32, 3), dtype=np.float32),
    np.zeros((0, 32, 3), dtype=np.uint8)])
def test_invalid_decoded_images_never_produce_frames(image):
    capture = FakeCapture()
    capture.image = image
    source = source_with(capture)
    source.connect()
    with pytest.raises(ConnectionError, match="valid uint8 BGR"):
        next(source.frames(1))
    assert source.state is CameraState.DISCONNECTED
    assert capture.release_calls == 1


@pytest.mark.parametrize("raises", [False, True])
def test_failed_reads_release_and_preserve_original_error_even_if_release_fails(raises):
    capture = FakeCapture()
    capture.read_result = False
    if raises:
        capture.read_error = RuntimeError("device removed")
    capture.release_error = RuntimeError("release unavailable")
    source = source_with(capture)
    source.connect()
    with pytest.raises(ConnectionError, match="frame read failed"):
        next(source.frames(1))
    assert source.state is CameraState.DISCONNECTED
    assert capture.release_calls == 1
    assert source.last_release_error == "release unavailable"
    source.disconnect()
    assert capture.release_calls == 1


def test_recovery_and_frame_ids_survive_single_frame_generators_and_reconnect():
    capture = FakeCapture()
    source = source_with(capture, policy=ConnectionPolicy(recovery_frames=3))
    source.connect()
    packets = [next(source.frames(1)) for _ in range(3)]
    assert [packet.frame_id for packet in packets] == [0, 1, 2]
    assert [packet.camera_state for packet in packets] == [
        CameraState.CONNECTING, CameraState.CONNECTING, CameraState.HEALTHY,
    ]
    assert all(packet.source_name == "ALC_IMX258_USB" for packet in packets)
    source.disconnect()
    source.connect()
    packets = [next(source.frames(1)) for _ in range(3)]
    assert [packet.frame_id for packet in packets] == [3, 4, 5]
    assert [packet.camera_state for packet in packets] == [
        CameraState.RECONNECTING, CameraState.RECONNECTING, CameraState.HEALTHY,
    ]
    source.disconnect()
    assert capture.release_calls == 2


def test_long_gap_restarts_consecutive_frame_recovery(monkeypatch):
    clock = iter([0.0, 0.1, 1.5, 1.6, 1.7])
    monkeypatch.setattr("src.week4.uvc.monotonic", lambda: next(clock))
    source = source_with(FakeCapture())
    source.connect()
    packets = list(source.frames(5))
    assert [packet.camera_state for packet in packets] == [
        CameraState.CONNECTING, CameraState.CONNECTING, CameraState.RECONNECTING,
        CameraState.RECONNECTING, CameraState.HEALTHY,
    ]
    source.disconnect()


def test_unavailable_reported_properties_do_not_block_valid_actual_frames():
    capture = FakeCapture()

    def unavailable_get(_prop):
        raise RuntimeError("get unavailable")

    capture.get = unavailable_get
    source = source_with(capture)
    source.connect()
    assert all(value is None for value in source.reported_properties.values())
    assert cv2.CAP_PROP_FPS not in capture.properties
    assert next(source.frames(1)).image.shape == (24, 32, 3)
    source.disconnect()


def test_connecting_again_releases_previous_handle():
    first, second = FakeCapture(), FakeCapture()
    captures = iter([first, second])
    source = UsbUvcSource(0, width_px=32, height_px=24, capture_factory=lambda: next(captures))
    source.connect()
    source.connect()
    assert first.release_calls == 1
    assert next(source.frames(1)).camera_state is CameraState.RECONNECTING
    source.disconnect()
    assert second.release_calls == 1
