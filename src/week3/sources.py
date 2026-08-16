"""Camera-source adapters for offline Week 3 development."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from .models import CameraState, FramePacket, utc_now_iso


class CameraSource(ABC):
    """Interface to be implemented by synthetic, MJPEG, and Picamera2 adapters."""

    @property
    @abstractmethod
    def state(self) -> CameraState:
        raise NotImplementedError

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def frames(self, limit: int) -> Iterator[FramePacket]:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class SyntheticCameraSource(CameraSource):
    """Repeatable local source used when no camera hardware is available."""

    width_px: int = 640
    height_px: int = 360
    source_name: str = "SYNTHETIC_OFFLINE"
    seed: int = 5105
    _state: CameraState = CameraState.DISCONNECTED

    @property
    def state(self) -> CameraState:
        return self._state

    def connect(self) -> None:
        self._state = CameraState.CONNECTING
        self._state = CameraState.HEALTHY

    def disconnect(self) -> None:
        self._state = CameraState.DISCONNECTED

    def frames(self, limit: int) -> Iterator[FramePacket]:
        if self._state is not CameraState.HEALTHY:
            raise ConnectionError("synthetic camera must be connected before reading frames")
        if limit <= 0:
            raise ValueError("frame limit must be positive")

        for frame_id in range(limit):
            timestamp = utc_now_iso()
            yield FramePacket(
                source_name=self.source_name,
                frame_id=frame_id,
                captured_at_utc=timestamp,
                received_at_utc=timestamp,
                camera_state=self._state,
                image=self._make_frame(frame_id),
            )

    def _make_frame(self, frame_id: int) -> np.ndarray:
        rng = np.random.default_rng(self.seed + frame_id)
        image = np.full((self.height_px, self.width_px, 3), 232, dtype=np.uint8)
        centre_y = self.height_px // 2
        half_height = max(34, self.height_px // 9)
        cv2.rectangle(
            image,
            (24, centre_y - half_height),
            (self.width_px - 24, centre_y + half_height),
            (92, 92, 92),
            -1,
        )

        noise = rng.normal(0, 2.0, image.shape[:2]).astype(np.int16)
        for channel in range(3):
            image[:, :, channel] = np.clip(
                image[:, :, channel].astype(np.int16) + noise, 0, 255
            ).astype(np.uint8)

        pattern = frame_id % 4
        if pattern == 0:
            cv2.circle(image, (self.width_px // 3, centre_y), 13, (215, 215, 215), -1)
        elif pattern == 1:
            cv2.line(
                image,
                (self.width_px // 2 - 42, centre_y - 20),
                (self.width_px // 2 + 42, centre_y + 20),
                (225, 225, 225),
                5,
            )
        elif pattern == 2:
            points = np.array(
                [
                    [3 * self.width_px // 5 - 20, centre_y - 18],
                    [3 * self.width_px // 5 + 28, centre_y - 12],
                    [3 * self.width_px // 5 + 18, centre_y + 22],
                    [3 * self.width_px // 5 - 25, centre_y + 15],
                ],
                dtype=np.int32,
            )
            cv2.fillPoly(image, [points], (178, 178, 178))
        return image
