"""Pixel-scale parameters for the reference synthetic scene.

These parameters preserve approximately the same fixture geometry and ranking
across canvas sizes. They are synthetic test settings, not calibrated material
thresholds or evidence that any camera supports the requested mode.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import cv2
import numpy as np

from src.week3.models import DetectionRecord, QualityGrade
from src.week3.vision import BaselineVisionProcessor


SYNTHETIC_REFERENCE_SIZE_PX = (640, 360)
SYNTHETIC_REFERENCE_ROI_PX = (28, 144, 584, 72)


def annotate_synthetic_candidates(
    image: np.ndarray, records: Iterable[DetectionRecord],
) -> np.ndarray:
    """Draw the supplied pixel-coordinate candidates on a separate BGR image.

    Line weight and text scale with the native canvas so UHD annotations remain
    legible when displayed as a preview. Records must come from this image;
    their boxes are drawn directly without scaling or recalculating findings.
    The source pixels and records remain unchanged.
    """
    if (image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3
            or image.shape[0] == 0 or image.shape[1] == 0):
        raise ValueError("synthetic annotation requires a non-empty uint8 BGR image")
    height, width = image.shape[:2]
    scale = width / SYNTHETIC_REFERENCE_SIZE_PX[0]
    display = image.copy()
    for record in records:
        x, y, box_width, box_height = record.bbox_px
        if (x < 0 or y < 0 or box_width <= 0 or box_height <= 0
                or x + box_width > width or y + box_height > height):
            raise ValueError("candidate box must lie inside the annotated image")
        colour = (60, 162, 223) if record.quality_grade == QualityGrade.WARNING else (60, 84, 194)
        cv2.rectangle(
            display, (x, y), (x + box_width, y + box_height), colour,
            max(1, round(2 * scale)),
        )
        cv2.putText(
            display, record.defect_type,
            (x, max(round(18 * scale), y - round(6 * scale))),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45 * scale, colour,
            max(1, round(scale)), cv2.LINE_AA,
        )
    return display


def synthetic_vision_profile(
    width_px: int,
    height_px: int,
    *,
    reference_roi_px: tuple[int, int, int, int] = SYNTHETIC_REFERENCE_ROI_PX,
) -> dict[str, Any]:
    """Return ``BaselineVisionProcessor`` kwargs for a native synthetic canvas.

    Lengths scale with the canvas; contour area and its ranking divisor scale
    with pixel area. Intensity thresholds and aspect ratios remain unchanged.
    Example: ``BaselineVisionProcessor(**synthetic_vision_profile(3840, 2160))``.
    """
    reference_width, reference_height = SYNTHETIC_REFERENCE_SIZE_PX
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (width_px, height_px)):
        raise ValueError("synthetic image dimensions must be positive integers")
    if width_px * reference_height != height_px * reference_width:
        raise ValueError("synthetic profile requires the reference aspect ratio")
    if len(reference_roi_px) != 4 or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in reference_roi_px
    ):
        raise ValueError("reference ROI must contain four integer coordinates")
    x, y, width, height = reference_roi_px
    if (x < 0 or y < 0 or width <= 0 or height <= 0
            or x + width > reference_width or y + height > reference_height):
        raise ValueError("reference ROI must lie inside the reference canvas")
    scale = width_px / reference_width
    area_scale = scale ** 2
    defaults = BaselineVisionProcessor()

    def kernel_size(size: int) -> int:
        # Scale the kernel's centre-to-edge distance and keep an exact centre.
        return 2 * max(0, round((size - 1) * scale / 2)) + 1

    roi = tuple(round(value * scale) for value in reference_roi_px)
    if roi[2] <= 0 or roi[3] <= 0:
        raise ValueError("target canvas is too small for the reference ROI")
    return {
        "roi_px": roi,
        "min_area_px": defaults.min_area_px * area_scale,
        "score_area_divisor_px": defaults.score_area_divisor_px * area_scale,
        "reject_area_px": defaults.reject_area_px * area_scale,
        "contamination_min_area_px": defaults.contamination_min_area_px * area_scale,
        "blur_kernel_size": kernel_size(defaults.blur_kernel_size),
        "morph_kernel_size": kernel_size(defaults.morph_kernel_size),
    }
