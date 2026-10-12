"""Inspect one static-specimen view and render its candidate records."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any
from uuid import uuid4

import cv2
import numpy as np

from src.week3.models import DetectionRecord, FramePacket, QualityGrade

from .geometry import (
    STATUS_NOT_ASSESSED,
    STATUS_REJECTED,
    STATUS_VALID,
    GeometryOutcome,
    GeometryParams,
    analyse_geometry,
)
from .surface import SURFACE_ALGORITHM_VERSION, SurfaceParams, SurfaceReference, analyse_surface


ALGORITHM_VERSION = "static-rpla-geometry-6"
SURFACE_NOT_IN_SCOPE = "SURFACE_ANALYSIS_NOT_IN_PHASE_1"
DARK_FIELD_NOT_IN_SCOPE = "DARK_FIELD_GEOMETRY_NOT_IN_PHASE_1"

_VALID_COLOUR = (60, 200, 60)
_REJECTED_COLOUR = (0, 200, 255)
_CANDIDATE_COLOUR = (0, 165, 255)
_UNMEASURED_COLOUR = (170, 170, 170)
_SURFACE_COLOUR = (255, 120, 255)
_SURFACE_LABELS = {
    "surface_bright_spot_candidate": "bright spot?",
    "surface_dark_spot_candidate": "dark spot",
    "surface_scratch_candidate": "dark line?",
    "surface_texture_deviation_candidate": "texture vs ref",
    "surface_demo_roughness_candidate": "rough (demo)",
    "surface_contamination_candidate": "contamination?",
    "surface_texture_direction_candidate": "crack?",
}
_WHOLE_SURFACE_TYPES = {"surface_texture_deviation_candidate", "surface_demo_roughness_candidate"}
_DEMO_GRADES = {"demo_good": "GOOD", "demo_moderately_rough": "MODERATELY ROUGH",
                "demo_clearly_rough": "CLEARLY ROUGH"}


@dataclass(slots=True)
class ViewInspectionResult:
    """Everything one view produced, including why it was not judged.

    ``geometry_status`` and ``surface_status`` are separate because a view can
    have a measurable outline while its surface is still out of scope.
    """

    algorithm_version: str
    lighting_mode: str | None
    geometry_status: str
    surface_status: str
    reason_codes: list[str]
    metrics: dict[str, Any]
    candidates: list[dict[str, Any]]
    parameters: dict[str, Any]
    elapsed_ms: float
    unmeasured: list[dict[str, Any]] = field(default_factory=list)
    surface: dict[str, Any] | None = None
    records: list[DetectionRecord] = field(default_factory=list)
    annotated: np.ndarray | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe: non-finite numbers become null (archives use allow_nan=False)."""
        payload = {
            "schema_version": 1 if self.surface is None else 2,
            "algorithm_version": self.algorithm_version,
            "lighting_mode": self.lighting_mode,
            "geometry_status": self.geometry_status,
            "surface_status": self.surface_status,
            "reason_codes": list(self.reason_codes),
            "metrics": self.metrics,
            "candidates": self.candidates,
            "unmeasured_stretches": self.unmeasured,
            "parameters": self.parameters,
            "elapsed_ms": self.elapsed_ms,
            "units": "px",
            "physical_outputs_allowed": False,
        }
        if self.surface is not None:
            payload["surface"] = self.surface
        return _finite(payload)


def _surface_line(result: ViewInspectionResult) -> str:
    surface = result.surface
    if surface is None:
        return "surface not assessed"
    if surface["status"] != STATUS_VALID:
        return "SURFACE " + surface["status"].upper() + " " + " ".join(surface["reason_codes"])
    metrics, comparison = surface["metrics"], surface["comparison"]
    local = sum(1 for c in result.candidates if c["branch"] == "surface"
                and c["defect_type"] not in _WHOLE_SURFACE_TYPES)
    # Five decimals, as archived: the demo grade boundaries sit at 0.0025 and 0.0099.
    text = "SURFACE texture {:.5f} streak {:.5f}".format(metrics["texture_mad"], metrics["longitudinal_energy"])
    if comparison.get("quality_label") in _DEMO_GRADES:
        text += " | DEMO {} (uncalibrated)".format(_DEMO_GRADES[comparison["quality_label"]])
    elif comparison.get("status") == "compared" and comparison.get("ratio") is not None:
        text += " | x{:.2f} vs {} ({})".format(comparison["ratio"], comparison["reference_id"],
                                              comparison["quality_label"])
    elif comparison.get("quality_label") == "not_graded_bright_structure":
        text += " | bright structure (glare?), grade suspended"
    elif "DEMO_ANGLE_NOT_SUPPORTED" in surface["reason_codes"]:
        text += " | demo grade at 0 deg only"
    else:
        text += " | {}, not graded".format(comparison.get("status", "not_compared"))
    return text + " | {} local".format(local)


def _finite(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


class StaticRplaProcessor:
    """Phase-1 processor: bright-field silhouette geometry only.

    ``process`` keeps the ``BaselineVisionProcessor`` call shape so the live
    service can use either; ``inspect`` returns the full result with reasons.
    """

    def __init__(self, params: GeometryParams, *, data_mode: str, algorithm_version: str | None = None,
                 surface: SurfaceParams | None = None, reference: SurfaceReference | None = None) -> None:
        self.params = params
        self.data_mode = data_mode
        self.surface = surface
        self.reference = reference
        self.algorithm_version = algorithm_version or (
            ALGORITHM_VERSION if surface is None else SURFACE_ALGORITHM_VERSION)

    @property
    def preview_lighting(self) -> str | None:
        """Lighting the operator declared for the live preview (surface needs bright field)."""
        return None if self.surface is None else self.surface.preview_lighting

    @property
    def preview_angle_deg(self) -> int | None:
        """Angle the operator declared for the live preview; a reference is only used at its own angle."""
        return None if self.surface is None else self.surface.preview_angle_deg

    def inspect(self, packet: FramePacket, batch_id: str, *,
                lighting_mode: str | None = None, angle_deg: int | None = None) -> ViewInspectionResult:
        started = time.perf_counter()
        if lighting_mode == "dark_field":
            # Both specimen and background can be near black in dark field, so
            # its outline is not measured independently in this phase.
            outcome = GeometryOutcome(STATUS_NOT_ASSESSED, [DARK_FIELD_NOT_IN_SCOPE], {})
        else:
            outcome = analyse_geometry(packet.image, self.params)
        geometry_candidates = [{"branch": "geometry", **item} for item in outcome.candidates]
        if self.surface is None:
            surface_outcome = None
            reasons = [*outcome.reason_codes, SURFACE_NOT_IN_SCOPE]
            surface_status = STATUS_NOT_ASSESSED
        else:
            surface_outcome = analyse_surface(outcome.context, outcome.status, outcome.metrics,
                                              self.surface, self.reference, lighting_mode, angle_deg)
            reasons = [*outcome.reason_codes, *surface_outcome.reason_codes]
            surface_status = surface_outcome.status
        candidates = geometry_candidates + ([] if surface_outcome is None else surface_outcome.candidates)
        records = [self._record(packet, batch_id, item) for item in candidates]
        result = ViewInspectionResult(
            algorithm_version=self.algorithm_version,
            lighting_mode=lighting_mode,
            geometry_status=outcome.status,
            surface_status=surface_status,
            reason_codes=reasons,
            metrics=outcome.metrics,
            candidates=candidates,
            parameters=self.params.to_dict(),
            elapsed_ms=0.0,
            unmeasured=outcome.unmeasured,
            surface=None if surface_outcome is None else surface_outcome.to_dict(self.surface, self.reference),
            records=records,
        )
        result.annotated = self._annotate(packet.image, outcome, result)
        result.elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        return result

    def process(self, packet: FramePacket, batch_id: str) -> tuple[np.ndarray, list[DetectionRecord]]:
        result = self.inspect(packet, batch_id)
        return result.annotated, result.records

    def _record(self, packet: FramePacket, batch_id: str, candidate: dict[str, Any]) -> DetectionRecord:
        height, width = packet.image.shape[:2]
        x, y, w, h = candidate["bbox_px"]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        return DetectionRecord(
            detection_id=f"DET-{uuid4().hex[:10].upper()}",
            batch_id=batch_id,
            camera_source=packet.source_name,
            frame_id=packet.frame_id,
            received_at_utc=packet.received_at_utc,
            defect_type=candidate["defect_type"],
            bbox_px=(x0, y0, max(1, x1 - x0), max(1, y1 - y0)),
            area_px=candidate["support_area_px"],
            # Ranking score ratio/(1+ratio) of peak to limit; not a probability.
            confidence=candidate["score"],
            quality_grade=QualityGrade.WARNING,
            algorithm_version=self.algorithm_version,
            data_mode=self.data_mode,
        )

    def _annotate(self, image: np.ndarray, outcome: GeometryOutcome,
                  result: ViewInspectionResult) -> np.ndarray:
        annotated = image.copy()
        unit = max(1.0, image.shape[1] / 1280)
        thickness = max(1, round(2 * unit))
        edge_colour = _VALID_COLOUR if outcome.status == STATUS_VALID else _REJECTED_COLOUR
        for points in (outcome.left_edge_xy, outcome.right_edge_xy):
            if points is None:
                continue
            finite = np.isfinite(points).all(axis=1)
            # One polyline per measured stretch; NaN rows mark unmeasured gaps.
            breaks = np.flatnonzero(np.diff(np.concatenate([[0], finite.astype(int), [0]])))
            for start, stop in zip(breaks[::2], breaks[1::2]):
                if stop - start > 1:
                    cv2.polylines(annotated, [np.round(points[start:stop]).astype(np.int32).reshape(-1, 1, 2)],
                                  False, edge_colour, thickness, cv2.LINE_AA)
        for stretch in outcome.unmeasured:
            x, y, w, h = stretch["bbox_px"]
            cv2.rectangle(annotated, (x, y), (x + w, y + h), _UNMEASURED_COLOUR, thickness)
            cv2.putText(annotated, "unmeasured", (x, max(int(24 * unit), y - int(8 * unit))),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6 * unit, _UNMEASURED_COLOUR, thickness, cv2.LINE_AA)
        for candidate in result.candidates:
            x, y, w, h = candidate["bbox_px"]
            surface = candidate["branch"] == "surface"
            colour = _SURFACE_COLOUR if surface else _CANDIDATE_COLOUR
            label = (_SURFACE_LABELS.get(candidate["defect_type"], candidate["defect_type"]) if surface
                     else candidate["defect_type"].replace("_candidate", ""))
            cv2.rectangle(annotated, (x, y), (x + w, y + h), colour, thickness)
            cv2.putText(annotated, label,
                        (x, max(int(24 * unit), y - int(8 * unit))), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6 * unit, colour, thickness, cv2.LINE_AA)
        self._banner(annotated, result, unit, thickness)
        return annotated

    @staticmethod
    def _banner(image: np.ndarray, result: ViewInspectionResult, unit: float, thickness: int) -> None:
        status = result.geometry_status.upper()
        lines = [f"{result.algorithm_version}  GEOMETRY {status}"]
        geometry_count = sum(1 for c in result.candidates if c["branch"] == "geometry")
        surface_reasons = (result.surface or {}).get("reason_codes", [])
        if result.geometry_status == STATUS_VALID:
            unmeasured = f", {len(result.unmeasured)} unmeasured stretch(es)" if result.unmeasured else ""
            lines.append(f"{geometry_count} geometry candidate(s){unmeasured}")
        else:
            lines.append(" ".join(code for code in result.reason_codes
                                  if code != SURFACE_NOT_IN_SCOPE and code not in surface_reasons))
        lines.append(_surface_line(result))
        if "FOCUS_UNVERIFIABLE" in result.reason_codes:
            lines.append("MANUAL REVIEW RECOMMENDED")
        spread = result.metrics.get("edge_spread_px_median")
        if spread is not None:
            limit = result.parameters["effective_edge_spread_limit_px"]
            lines.append(f"edge spread {spread:.1f} px (limit {limit:.1f} px)")
        scale = 0.6 * unit
        line_height = int(30 * unit)
        width = max(cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0][0] for text in lines)
        pad = int(10 * unit)
        cv2.rectangle(image, (0, 0), (width + 2 * pad, line_height * len(lines) + pad), (20, 20, 20), -1)
        colour = _VALID_COLOUR if result.geometry_status == STATUS_VALID else _REJECTED_COLOUR
        for index, text in enumerate(lines):
            cv2.putText(image, text, (pad, line_height * (index + 1) - int(6 * unit)), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, colour if index == 0 else (235, 235, 235), thickness, cv2.LINE_AA)


__all__ = ["ALGORITHM_VERSION", "StaticRplaProcessor", "ViewInspectionResult",
           "STATUS_VALID", "STATUS_REJECTED", "STATUS_NOT_ASSESSED"]
