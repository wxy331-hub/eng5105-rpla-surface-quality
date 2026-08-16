"""Week 3 source-independent inspection pipeline."""

from .models import CameraState, DetectionRecord, FramePacket, QualityGrade
from .repository import SQLiteInspectionRepository
from .sources import CameraSource, SyntheticCameraSource
from .vision import BaselineVisionProcessor

__all__ = [
    "BaselineVisionProcessor",
    "CameraSource",
    "CameraState",
    "DetectionRecord",
    "FramePacket",
    "QualityGrade",
    "SQLiteInspectionRepository",
    "SyntheticCameraSource",
]
