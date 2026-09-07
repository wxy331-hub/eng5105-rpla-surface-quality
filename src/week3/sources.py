"""Camera-source adapters for offline Week 3 development."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

from .models import CameraState, FramePacket, utc_now_iso


class CameraSource(ABC):
    """Common interface for synthetic, network MJPEG, and USB camera adapters."""

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
    """Repeatable local source used when no camera hardware is available.

    ``reference_size_px=(640, 360)`` scales the scene geometry onto a target
    canvas of the same aspect ratio. Noise is generated independently at the
    target pixel resolution; no source image is resized. Omitting the reference
    preserves the original small-fixture behaviour for existing tests/evidence.
    """

    width_px: int = 640
    height_px: int = 360
    source_name: str = "SYNTHETIC_OFFLINE"
    seed: int = 5105
    _state: CameraState = CameraState.DISCONNECTED
    reference_size_px: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        if self.reference_size_px is None:
            return
        dimensions = (self.width_px, self.height_px, *self.reference_size_px)
        if len(self.reference_size_px) != 2 or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in dimensions
        ):
            raise ValueError("image and reference dimensions must be positive integers")
        reference_width, reference_height = self.reference_size_px
        if self.width_px * reference_height != self.height_px * reference_width:
            raise ValueError("synthetic geometry requires the reference aspect ratio")

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
        if self.reference_size_px is not None:
            return self._make_scaled_frame(frame_id)
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

    def _make_scaled_frame(self, frame_id: int) -> np.ndarray:
        """Rasterise reference geometry and seeded noise on the target canvas."""
        assert self.reference_size_px is not None
        reference_width, reference_height = self.reference_size_px
        scale = self.width_px / reference_width

        def coordinate(value: int) -> int:
            return round(value * scale)

        def point(x: int, y: int) -> tuple[int, int]:
            return coordinate(x), coordinate(y)

        centre_y = reference_height // 2
        half_height = max(34, reference_height // 9)
        image = np.full((self.height_px, self.width_px, 3), 232, dtype=np.uint8)
        cv2.rectangle(
            image,
            point(24, centre_y - half_height),
            point(reference_width - 24, centre_y + half_height),
            (92, 92, 92), -1,
        )
        rng = np.random.default_rng(self.seed + frame_id)
        noise = rng.normal(0, 2.0, image.shape[:2]).astype(np.int16)
        for channel in range(3):
            image[:, :, channel] = np.clip(
                image[:, :, channel].astype(np.int16) + noise, 0, 255
            ).astype(np.uint8)

        pattern = frame_id % 4
        if pattern == 0:
            cv2.circle(
                image, point(reference_width // 3, centre_y),
                max(1, coordinate(13)), (215, 215, 215), -1,
            )
        elif pattern == 1:
            cv2.line(
                image,
                point(reference_width // 2 - 42, centre_y - 20),
                point(reference_width // 2 + 42, centre_y + 20),
                # OpenCV rasterises the legacy thickness 5 with radius 3.
                # Scale that radius so its caps and body keep their geometry.
                (225, 225, 225), max(1, 2 * coordinate(3)),
            )
        elif pattern == 2:
            points = np.array([
                point(3 * reference_width // 5 - 20, centre_y - 18),
                point(3 * reference_width // 5 + 28, centre_y - 12),
                point(3 * reference_width // 5 + 18, centre_y + 22),
                point(3 * reference_width // 5 - 25, centre_y + 15),
            ], dtype=np.int32)
            cv2.fillPoly(image, [points], (178, 178, 178))
        return image
