"""Camera acquisition primitives that can be verified without camera hardware."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from time import monotonic
from typing import Any

import cv2

from src.week3.models import CameraState, FramePacket, utc_now_iso
from src.week3.sources import CameraSource


@dataclass(frozen=True, slots=True)
class ConnectionPolicy:
    stale_after_s: float = 1.0
    disconnect_after_s: float = 2.0
    recovery_frames: int = 3

    def __post_init__(self) -> None:
        if self.stale_after_s <= 0:
            raise ValueError("stale_after_s must be positive")
        if self.disconnect_after_s <= self.stale_after_s:
            raise ValueError("disconnect_after_s must be greater than stale_after_s")
        if self.recovery_frames <= 0:
            raise ValueError("recovery_frames must be positive")


class CameraConnectionMonitor:
    """Deterministic camera state machine with recovery-frame safety gating."""

    def __init__(self, policy: ConnectionPolicy | None = None) -> None:
        self.policy = policy or ConnectionPolicy()
        self.state = CameraState.DISCONNECTED
        self.last_frame_at_s: float | None = None
        self.recovery_count = 0

    @property
    def automatic_actions_allowed(self) -> bool:
        return self.state is CameraState.HEALTHY

    def begin_connect(self, *, reconnect: bool = False) -> CameraState:
        self.state = CameraState.RECONNECTING if reconnect else CameraState.CONNECTING
        self.recovery_count = 0
        return self.state

    def frame_received(self, now_s: float) -> CameraState:
        if self.last_frame_at_s is not None and now_s < self.last_frame_at_s:
            raise ValueError("frame time must be monotonic")
        self.last_frame_at_s = now_s
        if self.state is CameraState.HEALTHY:
            return self.state
        if self.state in {CameraState.STALE, CameraState.DISCONNECTED}:
            self.state = CameraState.RECONNECTING
            self.recovery_count = 0
        self.recovery_count += 1
        if self.recovery_count >= self.policy.recovery_frames:
            self.state = CameraState.HEALTHY
        return self.state

    def poll(self, now_s: float) -> CameraState:
        if self.last_frame_at_s is None:
            return self.state
        age_s = now_s - self.last_frame_at_s
        if age_s < 0:
            raise ValueError("poll time must not precede the last frame")
        if age_s >= self.policy.disconnect_after_s:
            self.state = CameraState.DISCONNECTED
            self.recovery_count = 0
        elif age_s >= self.policy.stale_after_s:
            self.state = CameraState.STALE
            self.recovery_count = 0
        return self.state

    def mark_read_failure(self) -> CameraState:
        """A failed read means the link is down now, whatever the frame age says."""
        self.state = CameraState.DISCONNECTED
        self.recovery_count = 0
        return self.state


class LatestFrameBuffer:
    """A one-frame buffer that deliberately discards backlogged images."""

    def __init__(self) -> None:
        self._packet: FramePacket | None = None
        self.dropped_frames = 0

    def put(self, packet: FramePacket) -> None:
        if self._packet is not None:
            self.dropped_frames += 1
        self._packet = packet

    def take(self) -> FramePacket | None:
        packet = self._packet
        self._packet = None
        return packet


class Esp32MjpegSource(CameraSource):
    """方案 B MJPEG adapter; testable with an injected VideoCapture factory."""

    def __init__(
        self,
        stream_url: str,
        *,
        source_name: str = "ESP32S3_OV3660",
        capture_factory: Callable[[str], Any] = cv2.VideoCapture,
    ) -> None:
        self.stream_url = stream_url
        self.source_name = source_name
        self.capture_factory = capture_factory
        self.monitor = CameraConnectionMonitor()
        self._capture: Any | None = None
        self._frame_id = 0

    @property
    def state(self) -> CameraState:
        return self.monitor.state

    def connect(self) -> None:
        if "<ESP32_IP>" in self.stream_url:
            raise ValueError("replace <ESP32_IP> with the actual device address")
        self.monitor.begin_connect(reconnect=self.state is not CameraState.DISCONNECTED)
        self._capture = self.capture_factory(self.stream_url)
        if not self._capture.isOpened():
            self.disconnect()
            raise ConnectionError(f"could not open MJPEG stream: {self.stream_url}")

    def frames(self, limit: int) -> Iterator[FramePacket]:
        if self._capture is None or not self._capture.isOpened():
            raise ConnectionError("MJPEG source must be connected before reading frames")
        if limit <= 0:
            raise ValueError("frame limit must be positive")
        for _ in range(limit):
            ok, image = self._capture.read()
            if not ok or image is None:
                self.monitor.mark_read_failure()
                raise ConnectionError("MJPEG frame read failed")
            now_s = monotonic()
            state = self.monitor.frame_received(now_s)
            timestamp = utc_now_iso()
            frame_id = self._frame_id
            # Advance before yielding: the resident service pulls a single frame
            # per generator, so anything after the yield never runs.
            self._frame_id += 1
            yield FramePacket(
                source_name=self.source_name,
                frame_id=frame_id,
                captured_at_utc=timestamp,
                received_at_utc=timestamp,
                camera_state=state,
                image=image,
            )

    def disconnect(self) -> None:
        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self.monitor.state = CameraState.DISCONNECTED
        self.monitor.recovery_count = 0
