"""Local USB/UVC acquisition through the source-independent frame contract."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from time import monotonic
from typing import Any

import cv2
import numpy as np

from src.week3.models import CameraState, FramePacket, utc_now_iso
from src.week3.sources import CameraSource

from .camera import CameraConnectionMonitor, ConnectionPolicy


_BACKENDS = {
    "auto": cv2.CAP_ANY,
    "dshow": cv2.CAP_DSHOW,
    "msmf": cv2.CAP_MSMF,
    "v4l2": cv2.CAP_V4L2,
}
_DEVICE_PATH = re.compile(r"/dev/(?:video[0-9]+|v4l/(?:by-id|by-path)/[^/\\]+)\Z")


def _local_device(device: int | str) -> int | str:
    if isinstance(device, int) and not isinstance(device, bool) and device >= 0:
        return device
    if isinstance(device, str):
        if re.fullmatch(r"[0-9]+", device):
            return int(device)
        if _DEVICE_PATH.fullmatch(device) and Path(device).name not in {".", ".."}:
            path = Path(device)
            # A configured device may not have arrived yet. Existing regular
            # files must never be opened through this camera-only adapter.
            if path.exists() and not path.is_char_device():
                raise ValueError("UVC device path must name a character device, not a file")
            return device
    raise ValueError("UVC device must be a non-negative index or a local /dev/video device path")


class UsbUvcSource(CameraSource):
    """UVC adapter with injected capture I/O and per-frame mode validation.

    Property setters request a camera mode; property getters are driver-reported
    metadata only. Neither establishes a measured frame rate or optical result.
    As with the interim adapter, both frame timestamps describe the host read,
    because this OpenCV interface does not provide a sensor exposure timestamp.
    """

    def __init__(
        self,
        device: int | str,
        *,
        width_px: int,
        height_px: int,
        pixel_format: str = "MJPG",
        fps: float | None = None,
        backend: str = "auto",
        source_name: str = "ALC_IMX258_USB",
        capture_factory: Callable[[], Any] | None = None,
        policy: ConnectionPolicy | None = None,
    ) -> None:
        self.device = _local_device(device)
        for name, value in (("width_px", width_px), ("height_px", height_px)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(backend, str) or backend.lower() not in _BACKENDS:
            raise ValueError("UVC backend must be auto, dshow, msmf, or v4l2")
        self.backend = backend.lower()
        if isinstance(self.device, str) and self.backend in {"dshow", "msmf"}:
            raise ValueError("Windows UVC backends require a numeric device index")
        if not isinstance(pixel_format, str) or not re.fullmatch(r"[A-Za-z0-9]{4}", pixel_format):
            raise ValueError("pixel_format must be a four-character ASCII FourCC code")
        if fps is not None and (
            isinstance(fps, bool) or not isinstance(fps, (int, float))
            or not math.isfinite(fps) or fps <= 0
        ):
            raise ValueError("fps must be a finite positive number or null")
        if not isinstance(source_name, str) or not source_name.strip():
            raise ValueError("source_name must not be empty")
        self.width_px = width_px
        self.height_px = height_px
        self.pixel_format = pixel_format.upper()
        self.fps = fps
        self.source_name = source_name
        self.capture_factory = capture_factory if capture_factory is not None else cv2.VideoCapture
        self.monitor = CameraConnectionMonitor(policy)
        self.reported_properties: dict[str, float | None] = {}
        self.last_release_error: str | None = None
        self._capture: Any | None = None
        self._frame_id = 0
        self._ever_connected = False

    @property
    def state(self) -> CameraState:
        return self.monitor.state

    def connect(self) -> None:
        self.disconnect()
        self.reported_properties = {}
        self.monitor.begin_connect(reconnect=self._ever_connected)
        try:
            self._capture = self.capture_factory()
            if not self._capture.open(self.device, _BACKENDS[self.backend]) or not self._capture.isOpened():
                raise ConnectionError(f"could not open UVC device {self.device!r} with backend {self.backend}")
            requested = [
                ("pixel_format", cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.pixel_format)),
                ("width_px", cv2.CAP_PROP_FRAME_WIDTH, self.width_px),
                ("height_px", cv2.CAP_PROP_FRAME_HEIGHT, self.height_px),
            ]
            if self.fps is not None:
                requested.append(("fps", cv2.CAP_PROP_FPS, self.fps))
            for name, prop, value in requested:
                if not self._capture.set(prop, value):
                    raise ConnectionError(f"UVC device rejected requested {name}={value!r}")
            for name, prop in (
                ("width_px", cv2.CAP_PROP_FRAME_WIDTH),
                ("height_px", cv2.CAP_PROP_FRAME_HEIGHT),
                ("fps", cv2.CAP_PROP_FPS),
                ("fourcc", cv2.CAP_PROP_FOURCC),
            ):
                try:
                    value = float(self._capture.get(prop))
                    self.reported_properties[name] = value if math.isfinite(value) and value > 0 else None
                except Exception:
                    self.reported_properties[name] = None
            self._ever_connected = True
        except Exception as exc:
            self.disconnect()
            if isinstance(exc, ConnectionError):
                raise
            raise ConnectionError(f"UVC device setup failed: {exc}") from exc

    def frames(self, limit: int) -> Iterator[FramePacket]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("frame limit must be a positive integer")
        if self._capture is None:
            raise ConnectionError("UVC source must be connected before reading frames")
        for _ in range(limit):
            try:
                if self._capture is None or not self._capture.isOpened():
                    raise ConnectionError("UVC source is no longer open")
                ok, image = self._capture.read()
                if not ok:
                    raise ConnectionError("UVC frame read failed")
                if (
                    not isinstance(image, np.ndarray) or image.dtype != np.uint8
                    or image.ndim != 3 or image.shape[2] != 3 or image.size == 0
                ):
                    raise ConnectionError("UVC frame is not a valid uint8 BGR image")
                height, width = image.shape[:2]
                if (width, height) != (self.width_px, self.height_px):
                    raise ConnectionError(
                        f"UVC frame size {width}x{height} does not match requested "
                        f"{self.width_px}x{self.height_px}"
                    )
                now_s = monotonic()
                # A long gap breaks consecutive-frame recovery even if read()
                # eventually returns a valid image.
                self.monitor.poll(now_s)
                state = self.monitor.frame_received(now_s)
                timestamp = utc_now_iso()
                packet = FramePacket(
                    source_name=self.source_name,
                    frame_id=self._frame_id,
                    captured_at_utc=timestamp,
                    received_at_utc=timestamp,
                    camera_state=state,
                    image=image,
                )
                # The service creates a new frames(1) generator for each read.
                self._frame_id += 1
            except Exception as exc:
                self.disconnect()
                if isinstance(exc, ConnectionError):
                    raise
                raise ConnectionError(f"UVC frame read failed: {exc}") from exc
            yield packet

    def disconnect(self) -> None:
        capture, self._capture = self._capture, None
        self.monitor.mark_read_failure()
        self.monitor.last_frame_at_s = None
        if capture is not None:
            self.last_release_error = None
            try:
                capture.release()
            except Exception as exc:
                # Cleanup must not hide the original I/O error or prevent the
                # resident service from attempting a later connection.
                self.last_release_error = str(exc)
