"""Explainable offline baseline for candidate-region generation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import cv2
import numpy as np

from .models import DetectionRecord, FramePacket, QualityGrade


# Uncalibrated heuristics. They map pixel area onto a ranking score and a
# provisional grade so an operator can sort candidates; none of them is a
# probability, a validated decision threshold or a physical measurement. They
# must be re-derived from labelled rPLA specimens before any rejection rule
# depends on them, and no automatic rejection is authorised until then.
_SCORE_BASE = 0.55
_SCORE_AREA_DIVISOR_PX = 4000.0
_SCORE_CEILING = 0.95
_REJECT_AREA_PX = 1400.0
_SCRATCH_MIN_ASPECT = 2.0
_CONTAMINATION_MIN_AREA_PX = 900.0


@dataclass(slots=True)
class BaselineVisionProcessor:
    threshold: int = 145
    min_area_px: float = 80.0
    algorithm_version: str = "week3-baseline-1"
    roi_px: tuple[int, int, int, int] | None = None
    data_mode: str = "synthetic_baseline"

    def process(
        self, packet: FramePacket, batch_id: str
    ) -> tuple[np.ndarray, list[DetectionRecord]]:
        """Find bright candidate regions inside the synthetic filament ROI."""
        image = packet.image
        height, width = image.shape[:2]
        if self.roi_px is None:
            roi_x = 28
            roi_top = height // 2 - max(34, height // 9) + 4
            roi_width = width - 56
            roi_height = 2 * max(34, height // 9) - 8
        else:
            roi_x, roi_top, roi_width, roi_height = self.roi_px
            if roi_x < 0 or roi_top < 0 or roi_width <= 0 or roi_height <= 0:
                raise ValueError("ROI must have non-negative origin and positive size")
            if roi_x + roi_width > width or roi_top + roi_height > height:
                raise ValueError("ROI lies outside the image")
        roi = image[roi_top : roi_top + roi_height, roi_x : roi_x + roi_width]

        grey = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Keep the absolute intensity scale for this controlled synthetic source.
        # Histogram equalisation amplifies two-level sensor noise into false regions.
        blurred = cv2.GaussianBlur(grey, (5, 5), 0)
        _, mask = cv2.threshold(blurred, self.threshold, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        annotated = image.copy()
        records: list[DetectionRecord] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.min_area_px:
                continue
            x, y, box_width, box_height = cv2.boundingRect(contour)
            x += roi_x
            y += roi_top
            _, (rotated_width, rotated_height), _ = cv2.minAreaRect(contour)
            short_side = max(min(rotated_width, rotated_height), 1.0)
            aspect = max(rotated_width, rotated_height) / short_side
            defect_type = self._candidate_type(aspect, area)
            confidence = min(_SCORE_CEILING, _SCORE_BASE + area / _SCORE_AREA_DIVISOR_PX)
            grade = QualityGrade.WARNING if area < _REJECT_AREA_PX else QualityGrade.REJECT
            record = DetectionRecord(
                detection_id=f"DET-{uuid4().hex[:10].upper()}",
                batch_id=batch_id,
                camera_source=packet.source_name,
                frame_id=packet.frame_id,
                received_at_utc=packet.received_at_utc,
                defect_type=defect_type,
                bbox_px=(x, y, box_width, box_height),
                area_px=round(area, 2),
                confidence=round(confidence, 3),
                quality_grade=grade,
                algorithm_version=self.algorithm_version,
                data_mode=self.data_mode,
            )
            records.append(record)
            colour = (0, 165, 255) if grade is QualityGrade.WARNING else (0, 0, 255)
            cv2.rectangle(annotated, (x, y), (x + box_width, y + box_height), colour, 2)
            cv2.putText(
                annotated,
                defect_type,
                (x, max(18, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                colour,
                1,
                cv2.LINE_AA,
            )
        return annotated, records

    @staticmethod
    def _candidate_type(aspect: float, area: float) -> str:
        """Name a candidate by shape and size only; this is not a classifier."""
        if aspect >= _SCRATCH_MIN_ASPECT:
            return "scratch_candidate"
        if area >= _CONTAMINATION_MIN_AREA_PX:
            return "contamination_candidate"
        return "pit_candidate"
