"""Stable data contracts shared by camera, vision, storage, and GUI adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

import numpy as np


class CameraState(StrEnum):
    CONNECTING = "CONNECTING"
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"


class QualityGrade(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    REJECT = "reject"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True, slots=True)
class FramePacket:
    """One image plus source metadata, independent of camera implementation."""

    source_name: str
    frame_id: int
    captured_at_utc: str
    received_at_utc: str
    camera_state: CameraState
    image: np.ndarray

    def __post_init__(self) -> None:
        if self.frame_id < 0:
            raise ValueError("frame_id must be non-negative")
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")
        if self.image is None or self.image.size == 0:
            raise ValueError("image must not be empty")


@dataclass(frozen=True, slots=True)
class DetectionRecord:
    """A candidate finding. Physical units remain null until calibration exists.

    ``confidence`` is an uncalibrated ranking score derived from pixel area, not
    a probability that the region is a real defect. ``quality_grade`` is likewise
    provisional: it orders candidates for review and never authorises automatic
    rejection. Both stay meaningless as quality statements until labelled
    real-material validation replaces the baseline heuristics.
    """

    detection_id: str
    batch_id: str
    camera_source: str
    frame_id: int
    received_at_utc: str
    defect_type: str
    bbox_px: tuple[int, int, int, int]
    area_px: float
    confidence: float
    quality_grade: QualityGrade
    algorithm_version: str
    data_mode: str = "synthetic_baseline"
    position_mm: float | None = None
    size_mm: tuple[float, float] | None = None
    calibration_id: str | None = None
    image_path: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.area_px < 0:
            raise ValueError("area_px must be non-negative")
        if self.calibration_id is None and (
            self.position_mm is not None or self.size_mm is not None
        ):
            raise ValueError("physical measurements require a calibration_id")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["quality_grade"] = self.quality_grade.value
        result["bbox_px"] = list(self.bbox_px)
        if self.size_mm is not None:
            result["size_mm"] = list(self.size_mm)
        return result
