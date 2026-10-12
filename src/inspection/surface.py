"""Bright-field surface texture and local surface candidates on a measured specimen.

Phase 2a (docs/static_rpla_inspection.md): the analysis runs inside the outline
that the geometry branch measured, removes slow shading with a masked Gaussian,
reports two image-contrast metrics, finds bright/dark spots and dark lines, and
compares the metrics with a good-sample reference taken on the same bench.
Nothing here is a physical roughness, a probability or a length in millimetres.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .geometry import STATUS_NOT_ASSESSED, STATUS_REJECTED, STATUS_VALID, GeometryContext, _channel_max


SURFACE_ALGORITHM_VERSION = "static-rpla-geometry-surface-8"
REFERENCE_SCHEMA_VERSION = 1

# Fixed rules of this version (see the design table in the documentation).
# Rows whose local edge spread exceeds s/2 are not analysed (the geometry focus
# limit). Codex proposed s/3; on the 2026-10-08 bench the spread was 15-20 px
# against s = 60 and s/3 rejected most rows. Comparability between a frame and
# its reference is enforced separately by the focus check in _compare.
FOCUS_FRACTION = 1 / 2
MIN_AXIAL_COVERAGE = 0.9
MIN_AREA_COVERAGE = 0.8
BRIGHTNESS_FLOOR = 16 / 255
MASK_WEIGHT_FLOOR = 0.05
CONTRAST_FLOOR = 0.03
METRIC_FLOOR = 0.005
DEVIATES_RATIO, STRONGLY_DEVIATES_RATIO = 1.5, 2.0
SPOT_MAX_DIAMETER = 4.0  # times s
LINE_MIN_LENGTH = 3.0  # times s
ELONGATED_ASPECT = 3.0
AXIAL_LINE_DEG = 15.0
TEXTURE_LINE_FRACTION = 0.5  # an axial line longer than this share of the analysed length is texture
WIDTH_TOLERANCE, BRIGHTNESS_TOLERANCE = 0.05, 0.15
# The live preview writes every frame's candidates to the record database; a
# coarse texture without a reference (fixed 0.03 floor) can yield dozens per
# frame. Keep the highest-scoring ones and report how many were left out.
MAX_LOCAL_CANDIDATES = 12
# A local candidate must exceed this multiple of the local mean |residual| (2s
# neighbourhood), so a repeated texture raises its own threshold while an
# isolated spot or line barely raises it (Codex review 2026-10-08).
LOCAL_TEXTURE_FACTOR = 3.0
BRIGHT_STRUCTURE_LENGTH = 4.0  # times s: a long bright band is lighting-ambiguous
# Demo rules (2026-10-12, uncalibrated; no real contaminated, cracked or nodular
# specimen has been imaged). A compact region clearly darker than its local
# background is contamination; PLA texture runs along the filament, so a dark
# line running across it suggests a crack. (A structure-tensor detector for
# whole regions of oblique texture was tried and removed after three Codex
# review rounds: a wide unsaturated bright band, as glare makes, leaves faint
# opposite lobes in the background-subtracted residual that local statistics
# could not tell from an alternating texture without also missing real ones.)
CONTAMINATION_DARKENING = 0.25  # relative darkening R <= -0.25
CONTAMINATION_MAX_DIAMETER = 6.0  # times s
DIRECTION_OFF_AXIS_DEG = 30.0
TRANSVERSE_LINE_DEG = 60.0


@dataclass(frozen=True, slots=True)
class SurfaceParams:
    min_feature_px: float = 60.0
    preview_lighting: str | None = None
    preview_angle_deg: int | None = None
    reference_path: str | None = None
    # Demo only (2026-10-12): streak (longitudinal_energy) bounds [moderately, clearly rough],
    # set from four bench specimens of different colours. Uncalibrated; null disables.
    demo_longitudinal_thresholds: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if self.demo_longitudinal_thresholds is not None:
            bounds = self.demo_longitudinal_thresholds
            if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                           for v in bounds)
                    or not 0 < bounds[0] < bounds[1]):
                raise ValueError("demo_longitudinal_thresholds must be null or two finite numbers 0 < low < high")
            object.__setattr__(self, "demo_longitudinal_thresholds", (float(bounds[0]), float(bounds[1])))
        if not math.isfinite(self.min_feature_px) or self.min_feature_px < 6:
            raise ValueError("surface min_feature_px must be finite and at least 6")
        if self.preview_lighting not in (None, "bright_field"):
            raise ValueError("preview_lighting must be null or 'bright_field'")
        if self.preview_angle_deg not in (None, 0, 60, 120, 180, 240, 300):
            raise ValueError("preview_angle_deg must be null or one of the six capture angles")

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "SurfaceParams":
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown static surface parameters: {sorted(unknown)}")
        return cls(**values)


@dataclass(frozen=True, slots=True)
class SurfaceReference:
    """A good-sample reference recorded on one bench set-up. Immutable once loaded."""

    reference_id: str
    min_feature_px: float
    texture_mad: float
    longitudinal_energy: float
    brightness_median: float
    edge_spread_px: float
    width_px: float
    fingerprint: str
    source: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "SurfaceReference":
        raw = Path(path).read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if data.get("schema_version") != REFERENCE_SCHEMA_VERSION:
            raise ValueError(f"unsupported surface reference schema: {data.get('schema_version')}")
        if data.get("algorithm_version") != SURFACE_ALGORITHM_VERSION:
            raise ValueError("surface reference was made by a different algorithm version")
        values = validate_reference_metrics(data["metrics"])
        scale = float(data["min_feature_px"])
        if not math.isfinite(scale) or scale < 6:
            raise ValueError("surface reference min_feature_px must be finite and at least 6")
        reference_id = data.get("reference_id")
        if not isinstance(reference_id, str) or not reference_id.strip():
            raise ValueError("surface reference_id must be a non-empty string")
        source = dict(data.get("source", {}))
        # A reference without an angle would be "compatible" with every view.
        if source.get("angle_deg") not in REFERENCE_ANGLES:
            raise ValueError("surface reference source.angle_deg must be one of the six capture angles")
        return cls(reference_id=reference_id, min_feature_px=scale,
                   fingerprint=hashlib.sha256(raw).hexdigest(), source=source, **values)

    def identity(self) -> dict[str, Any]:
        return {"reference_id": self.reference_id, "fingerprint": self.fingerprint,
                "min_feature_px": self.min_feature_px, "source": self.source}


REFERENCE_ANGLES = (0, 60, 120, 180, 240, 300)
REFERENCE_METRICS = ("texture_mad", "longitudinal_energy", "brightness_median", "edge_spread_px", "width_px")


def validate_reference_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    """The rule both the reference creator and the loader apply."""
    values = {}
    for name in REFERENCE_METRICS:
        value = metrics.get(name)
        value = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else float("nan")
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"surface reference metric {name} must be positive and finite, got {metrics.get(name)!r}")
        values[name] = value
    return values


@dataclass(slots=True)
class SurfaceOutcome:
    status: str
    reason_codes: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self, params: SurfaceParams, reference: SurfaceReference | None) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "metrics": self.metrics,
            "metric_units": {"texture_mad": "relative_contrast", "longitudinal_energy": "relative_contrast",
                             "spot_density_per_mpx": "count_per_million_px", "brightness_median": "fraction_of_full_scale"},
            "coverage": self.coverage,
            "comparison": self.comparison,
            "parameters": {**asdict(params), "focus_limit_px": params.min_feature_px * FOCUS_FRACTION},
            "reference": None if reference is None else reference.identity(),
            "evidence_scope": "BENCH_DEMO_STARTING_POINT",
        }


def _not_judged(status: str, reasons: list[str], **extra: Any) -> SurfaceOutcome:
    return SurfaceOutcome(status, reasons, comparison={"status": "not_compared", "quality_label": "not_judged"}, **extra)


def _masked_gaussian(values: np.ndarray, mask: np.ndarray, sigma_x: float, sigma_y: float,
                     downsample: int = 1) -> np.ndarray:
    """Gaussian mean over the masked pixels only, so background never leaks in."""
    weights = mask.astype(np.float32)
    data = np.where(mask, values, 0).astype(np.float32)
    if downsample > 1:
        size = (max(1, values.shape[1] // downsample), max(1, values.shape[0] // downsample))
        data = cv2.resize(data, size, interpolation=cv2.INTER_AREA)
        weights = cv2.resize(weights, size, interpolation=cv2.INTER_AREA)
        sigma_x, sigma_y = sigma_x / downsample, sigma_y / downsample
    blurred = cv2.GaussianBlur(data, (0, 0), sigmaX=max(sigma_x, 0.5), sigmaY=max(sigma_y, 0.5))
    norm = cv2.GaussianBlur(weights, (0, 0), sigmaX=max(sigma_x, 0.5), sigmaY=max(sigma_y, 0.5))
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(norm > MASK_WEIGHT_FLOOR, blurred / norm, np.nan).astype(np.float32)
    if downsample > 1:
        result = cv2.resize(np.nan_to_num(result, nan=0.0), (values.shape[1], values.shape[0]),
                            interpolation=cv2.INTER_LINEAR)
        support = cv2.resize((norm > MASK_WEIGHT_FLOOR).astype(np.float32), (values.shape[1], values.shape[0]),
                             interpolation=cv2.INTER_NEAREST) > 0
        result = np.where(support, result, np.nan)
    return result


def _region(ctx: GeometryContext, s: float) -> tuple[np.ndarray, dict[str, Any], str | None]:
    """Analysis mask in the rotated frame, its coverage, and a rejection reason if any."""
    height, width = ctx.valid_pixels.shape
    n = len(ctx.rows)
    end = int(math.ceil(s))
    in_span = np.zeros(n, bool)
    in_span[end:max(end, n - end)] = True
    nominal = in_span & ctx.valid_rows
    spread = np.nan_to_num(ctx.local_edge_spread, nan=np.inf)
    in_focus = spread <= s * FOCUS_FRACTION
    use = nominal & in_focus
    inset = np.maximum(s, 2 * np.where(np.isfinite(spread), spread, 0))
    lo = np.ceil(ctx.left_x + inset)
    hi = np.floor(ctx.right_x - inset)
    columns = np.arange(width)[None, :]
    mask = np.zeros((height, width), bool)
    rows = ctx.rows[use]
    mask[rows] = (columns >= lo[use][:, None]) & (columns <= hi[use][:, None]) & ctx.valid_pixels[rows]
    nominal_width = np.clip(np.floor(ctx.right_x - s) - np.ceil(ctx.left_x + s) + 1, 0, None)
    nominal_area = float(nominal_width[nominal].sum())
    coverage = {
        "rows_nominal": int(nominal.sum()),
        "rows_excluded_focus": int((nominal & ~in_focus).sum()),
        "analysed_area_px": int(mask.sum()),
        "nominal_area_px": int(nominal_area),
    }
    if nominal.sum() == 0:
        return mask, coverage, "SURFACE_ROI_TOO_SMALL"

    def too_small(rows: np.ndarray) -> bool:
        interior = (hi - lo + 1)[rows]
        return len(interior) < 8 * s or float(np.median(interior)) < 4 * s

    if too_small(use):
        interior = (hi - lo + 1)[use]
        coverage["median_interior_width_px"] = float(np.median(interior)) if len(interior) else 0.0
        # Large enough before the focus filter: what is missing is focus evidence,
        # not specimen area.
        return mask, coverage, "SURFACE_ROI_TOO_SMALL" if too_small(nominal) else "SURFACE_FOCUS_UNVERIFIABLE"
    return mask, coverage, None


def _components(binary: np.ndarray, support: np.ndarray, s: float):
    radius = max(1, int(round(s / 12)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    closed = cv2.morphologyEx(binary.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool) & support
    count, labels, stats, _ = cv2.connectedComponentsWithStats(closed.astype(np.uint8), connectivity=8)
    # Nothing smaller than the smallest reportable shape (a line 3s long and
    # 2 px wide) can become a candidate; skip such specks before measuring them.
    min_area = LINE_MIN_LENGTH * s * 2
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] < min_area:
            continue
        x, y, w, h = stats[label, :4]
        component = labels[y:y + h, x:x + w] == label
        yield (x, y, w, h), component, binary[y:y + h, x:x + w] & component


def analyse_surface(ctx: GeometryContext | None, geometry_status: str, geometry_metrics: dict[str, Any],
                    params: SurfaceParams, reference: SurfaceReference | None,
                    lighting_mode: str | None, angle_deg: int | None = None) -> SurfaceOutcome:
    if lighting_mode == "dark_field":
        return _not_judged(STATUS_NOT_ASSESSED, ["DARK_FIELD_SURFACE_NOT_IN_SCOPE"])
    if lighting_mode != "bright_field":
        # The live preview has no lighting declaration unless the profile sets one.
        return _not_judged(STATUS_NOT_ASSESSED, ["SURFACE_LIGHTING_NOT_DECLARED"])
    if geometry_status != STATUS_VALID or ctx is None:
        return _not_judged(STATUS_REJECTED, ["GEOMETRY_UNUSABLE"])
    s = float(params.min_feature_px)
    mask, coverage, reason = _region(ctx, s)
    if reason:
        return _not_judged(STATUS_REJECTED, [reason], coverage=coverage)

    # Work on the bounding box of the region plus room for the slow background.
    ys, xs = np.nonzero(mask)
    margin = int(math.ceil(3 * s))
    y0, y1 = max(0, ys.min() - margin), min(mask.shape[0], ys.max() + margin + 1)
    x0, x1 = max(0, xs.min() - margin), min(mask.shape[1], xs.max() + margin + 1)
    crop = ctx.rotated[y0:y1, x0:x1]
    region = mask[y0:y1, x0:x1]
    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    # Saturated pixels (and a thin ring around them) cannot be analysed; a real
    # white particle can saturate too, so this is "unanalysed", not "glare
    # removed". The smoothing below is masked, so clipped values never spread
    # into their neighbours; the ring only covers JPEG ringing next to a clipped
    # pixel. (A ring of s/2 excluded 23 % of the specimen around scattered
    # glare specks on the 2026-10-12 bench while only 2 % was saturated.)
    saturated = (grey <= 2 / 255) | (_channel_max(np.ascontiguousarray(crop)) >= 253)
    if saturated.any():
        ring = max(1, int(math.ceil(s / 12)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring + 1, 2 * ring + 1))
        saturated = cv2.dilate(saturated.astype(np.uint8), kernel).astype(bool)
    support = region & ~saturated
    coverage["excluded_saturation_px"] = int((region & saturated).sum())
    rows_used = np.unique(np.nonzero(support)[0])
    axial = len(rows_used) / max(1, coverage["rows_nominal"])
    area = support.sum() / max(1.0, coverage["nominal_area_px"])
    coverage.update(axial_fraction=round(float(axial), 4), area_fraction=round(float(area), 4),
                    analysed_area_px=int(support.sum()))
    if axial < MIN_AXIAL_COVERAGE or area < MIN_AREA_COVERAGE:
        dominant = ("SURFACE_FOCUS_UNVERIFIABLE" if coverage["rows_excluded_focus"] > 0.5 * (1 - axial) *
                    coverage["rows_nominal"] else "EXPOSURE_CLIPPED" if coverage["excluded_saturation_px"]
                    else "SURFACE_COVERAGE_LOW")
        return _not_judged(STATUS_REJECTED, [dominant], coverage=coverage)

    downsample = max(1, int(s // 8))
    # Filters whose sigma is at least s/6 lose nothing at a reduced resolution;
    # at 4K this keeps the surface pass within the live service frame budget.
    fine = _masked_gaussian(grey, support, s / 6, s / 6, max(1, int(s // 24)))

    def residual_for(background: np.ndarray) -> np.ndarray:
        base = np.maximum(np.nan_to_num(background, nan=1.0), BRIGHTNESS_FLOOR)
        return np.where(support, (fine - background) / base, np.nan)

    # Two passes: a strong spot lifts a plain Gaussian background around it and
    # leaves a ring of the opposite sign (a false dark ring round a bright spot).
    # The second pass estimates the background without the clear outliers.
    background = _masked_gaussian(grey, support, 2 * s, 2 * s, downsample)
    first = residual_for(background)
    spread_first = 1.4826 * np.nanmedian(np.abs(first - np.nanmedian(first)))
    inliers = support & (np.abs(np.nan_to_num(first)) <= max(CONTRAST_FLOOR, 2.5 * float(spread_first)))
    if inliers.sum() > 0.5 * support.sum():
        background = _masked_gaussian(grey, inliers, 2 * s, 2 * s, downsample)
        # Deep inside a large outlier (a dark mark several s across) the 2 s window
        # holds too few inliers and the background is undefined; there it is
        # estimated on 4 s, so the mark is analysed whole rather than as a rim.
        missing = support & ~np.isfinite(background)
        if missing.any():
            background = np.where(missing, _masked_gaussian(grey, inliers, 4 * s, 4 * s, downsample), background)
    base = np.maximum(np.nan_to_num(background, nan=1.0), BRIGHTNESS_FLOOR)
    residual = residual_for(background)
    normalised = grey / base
    coarse = max(1, int(s // 12))
    streaks = (_masked_gaussian(normalised, support, s / 6, s, coarse)
               - _masked_gaussian(normalised, support, s, s, coarse))
    usable = support & np.isfinite(residual) & np.isfinite(streaks)
    spread_rows = ctx.local_edge_spread[np.isin(ctx.rows, rows_used + y0)]
    edge_spread = float(np.nanmedian(spread_rows)) if np.isfinite(spread_rows).any() else float("nan")

    # The local threshold adapts to the texture around each point. A floor of
    # 5x the reference texture (the original design) suppressed a clear new
    # spot on a strongly textured specimen and still reported "close to the
    # reference" (Codex review 2026-10-08), so the reference only grades.
    tau = CONTRAST_FLOOR
    # Within one imaging blur width of a clipped pixel the true intensity is
    # unknown: the highlight spills optically into it. The width is this view's
    # measured edge spread, not a tuning value.
    halo = np.zeros_like(saturated)
    if saturated.any():
        r = max(2, int(math.ceil(np.nan_to_num(edge_spread, nan=2.0))))
        disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        halo = cv2.dilate(saturated.astype(np.uint8), disc).astype(bool)
    # Pixels clipped to black have no residual but are certainly dark: they
    # (with their exclusion ring) count as contamination evidence.
    black = region & (grey <= 2 / 255)
    if black.any():
        ring = max(1, int(math.ceil(s / 12)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ring + 1, 2 * ring + 1))
        black = cv2.dilate(black.astype(np.uint8), kernel).astype(bool) & region
    contamination, claimed = _contamination_candidates(residual, usable, black, s, (x0, y0), ctx, reference)
    candidates, bright_structures, halos, reported = _local_candidates(
        residual, usable, tau, s, (x0, y0), ctx, reference, halo, claimed)
    candidates = contamination + candidates

    # The texture metrics describe the surface between the local defects, which
    # are reported on their own: one 100 px marker dot on the smooth white
    # specimen lifted the RMS streak metric from 0.001 to 0.030 and turned
    # "good" into "clearly rough" (2026-10-12 bench). The reported regions, grown
    # by the background scale (2 s: a soft-edged mark darkens well beyond its
    # reported core; s/3 left enough of a synthetic soft dot to lift the grade),
    # leave the metric pixels and the streak filter.
    measured = usable
    defects = claimed | reported
    if defects.any():
        reach = int(math.ceil(2 * s))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * reach + 1, 2 * reach + 1))
        defects = cv2.dilate(defects.astype(np.uint8), kernel).astype(bool)
        clean = support & ~defects
        clean_streaks = (_masked_gaussian(normalised, clean, s / 6, s, coarse)
                         - _masked_gaussian(normalised, clean, s, s, coarse))
        clean_measured = usable & ~defects & np.isfinite(clean_streaks)
        # Mostly defects: the surface between them is too small to stand for it,
        # so nothing is excluded. Both the pixels and the streak map switch
        # together; the clean map is undefined inside the excluded regions
        # (Codex review 2026-10-12: NaN streaks graded a striped specimen "good").
        if clean_measured.sum() >= 0.5 * usable.sum():
            streaks, measured = clean_streaks, clean_measured
    coverage["excluded_local_defect_px"] = int((usable & ~measured).sum())
    values = residual[measured]
    texture = float(1.4826 * np.median(np.abs(values - np.median(values))))
    energy = float(np.sqrt(np.mean(streaks[measured] ** 2)))
    brightness = float(np.median(grey[measured]))
    metrics: dict[str, Any] = {
        "texture_mad": round(texture, 5), "longitudinal_energy": round(energy, 5),
        "brightness_median": round(brightness, 4), "edge_spread_px": round(edge_spread, 2),
        "width_px": geometry_metrics.get("width_px_median"),
    }
    comparison = _compare(metrics, s, reference, angle_deg)
    comparison["local_threshold_rule"] = f"max({CONTRAST_FLOOR}, {LOCAL_TEXTURE_FACTOR} x local mean |R|)"
    counts = {kind: sum(1 for c in candidates if c["defect_type"] == kind) for kind in
              ("surface_bright_spot_candidate", "surface_dark_spot_candidate", "surface_scratch_candidate",
               "surface_contamination_candidate", "surface_texture_direction_candidate")}
    spots = (counts["surface_bright_spot_candidate"] + counts["surface_dark_spot_candidate"]
             + counts["surface_contamination_candidate"])
    metrics.update(candidate_counts=counts,
                   spot_density_per_mpx=round(1e6 * spots / max(1, usable.sum()), 2),
                   local_candidates_not_recorded=max(0, len(candidates) - MAX_LOCAL_CANDIDATES),
                   bright_structures=bright_structures, bright_next_to_saturation=halos)
    candidates = sorted(candidates, key=lambda item: item["score"], reverse=True)[:MAX_LOCAL_CANDIDATES]
    reasons: list[str] = []
    ratio = comparison.get("ratio")
    if comparison["status"] == "compared" and ratio is not None:
        if bright_structures:
            # A long bright band may be lighting rather than surface; it lifts
            # the streak metric, so the overall grade is suspended.
            reasons.append("GLARE_OR_BRIGHT_STRUCTURE_AMBIGUOUS")
            comparison["quality_label"] = "not_graded_bright_structure"
        elif ratio >= DEVIATES_RATIO:
            # A missing ratio (reference metric too low) cannot hide a high one.
            comparison["quality_label"] = "strongly_deviates" if ratio >= STRONGLY_DEVIATES_RATIO else "deviates"
            if ratio >= STRONGLY_DEVIATES_RATIO:
                candidates.append(_texture_candidate(usable, (x0, y0), ctx, ratio, reference))
        elif not comparison["complete"]:
            # ...but only both ratios together can show the surface is close.
            comparison["quality_label"] = "reference_metric_too_low"
        else:
            comparison["quality_label"] = ("near_reference_with_local_candidates" if candidates
                                           else "near_reference")
    elif params.demo_longitudinal_thresholds is not None and comparison["status"] in {"no_reference",
                                                                                      "reference_mismatch"}:
        # Demo grade without a comparable reference. The bounds were set on 0 deg
        # bright-field views of this bench only, so other angles are not graded.
        if angle_deg != 0:
            reasons.append("DEMO_ANGLE_NOT_SUPPORTED")
        elif bright_structures:
            reasons.append("GLARE_OR_BRIGHT_STRUCTURE_AMBIGUOUS")
            comparison["quality_label"] = "not_graded_bright_structure"
        else:
            low, high = params.demo_longitudinal_thresholds
            streaks = metrics["longitudinal_energy"]  # the archived (rounded) value, so display and grade agree
            reasons.append("UNCALIBRATED_DEMO_THRESHOLD")
            comparison["quality_label"] = ("demo_clearly_rough" if streaks >= high
                                           else "demo_moderately_rough" if streaks >= low else "demo_good")
            if streaks >= low:
                candidates.append(_demo_roughness_candidate(usable, (x0, y0), ctx, streaks, low))
    return SurfaceOutcome(STATUS_VALID, reasons, metrics, coverage, comparison, candidates)


def _compare(metrics: dict[str, Any], s: float, reference: SurfaceReference | None,
             angle_deg: int | None) -> dict[str, Any]:
    if reference is None:
        return {"status": "no_reference", "quality_label": "not_graded"}
    mismatches = []
    if angle_deg != reference.source.get("angle_deg"):
        # A 0-degree reference says nothing about another face of the specimen.
        mismatches.append("ANGLE_NOT_DECLARED" if angle_deg is None else "ANGLE_DIFFERS")
    if abs(reference.min_feature_px - s) > 1e-6:
        mismatches.append("SCALE_DIFFERS")
    width = metrics.get("width_px")
    if width is None or abs(width - reference.width_px) > WIDTH_TOLERANCE * reference.width_px:
        mismatches.append("WIDTH_DIFFERS")
    spread = metrics["edge_spread_px"]
    if not math.isfinite(spread) or abs(spread - reference.edge_spread_px) > max(2.0, 0.2 * reference.edge_spread_px):
        mismatches.append("FOCUS_DIFFERS")
    if abs(metrics["brightness_median"] - reference.brightness_median) > BRIGHTNESS_TOLERANCE * reference.brightness_median:
        mismatches.append("BRIGHTNESS_DIFFERS")
    if mismatches:
        return {"status": "reference_mismatch", "quality_label": "not_graded", "mismatches": mismatches,
                "reference_id": reference.reference_id}
    ratios = {}
    for name, ref_value in (("texture_mad", reference.texture_mad),
                            ("longitudinal_energy", reference.longitudinal_energy)):
        # A near-zero reference metric would turn noise into a huge ratio.
        ratios[name] = None if ref_value < METRIC_FLOOR else round(metrics[name] / ref_value, 3)
    available = {k: v for k, v in ratios.items() if v is not None}
    if not available:
        return {"status": "compared", "quality_label": "reference_metric_too_low", "metric_ratios": ratios,
                "reference_id": reference.reference_id, "ratio": None, "complete": False}
    dominant = max(available, key=available.get)
    return {"status": "compared", "reference_id": reference.reference_id, "metric_ratios": ratios,
            "dominant_metric": dominant, "ratio": available[dominant], "complete": len(available) == len(ratios)}


def _to_image_bbox(ctx: GeometryContext, offset: tuple[int, int], x: float, y: float, w: float, h: float) -> list[int]:
    ox, oy = offset
    corners = ctx.frame.to_image(np.array([[x + ox, y + oy], [x + ox + w, y + oy],
                                           [x + ox, y + oy + h], [x + ox + w, y + oy + h]], float))
    bx0, by0 = np.floor(corners.min(axis=0)).astype(int)
    bx1, by1 = np.ceil(corners.max(axis=0)).astype(int)
    return [int(bx0), int(by0), int(bx1 - bx0), int(by1 - by0)]


def _contamination_candidates(residual: np.ndarray, usable: np.ndarray, black: np.ndarray, s: float,
                              offset: tuple[int, int], ctx: GeometryContext, reference: SurfaceReference | None):
    """Compact regions clearly darker than the local background (demo rule: a dark mark is contamination).

    A fixed darkening, not the adaptive local threshold: a large dark mark raises
    the adaptive threshold around itself until only its rim is left. Returns the
    candidates and the mask they claim (no second report as a dark spot or line).
    """
    dark = (usable & (np.nan_to_num(residual) <= -CONTAMINATION_DARKENING)) | black
    darkening = np.where(black, -1.0, np.nan_to_num(residual))
    found, claimed = [], np.zeros_like(usable)
    for (x, y, w, h), component, original in _components(dark, usable | black, s):
        pts = cv2.findNonZero(component.astype(np.uint8))
        _, (rw, rh), _ = cv2.minAreaRect(pts)
        aspect = max(rw, rh) / max(min(rw, rh), 1.0)
        diameter = math.sqrt(4 * component.sum() / math.pi)
        if aspect >= ELONGATED_ASPECT or not 0.75 * s <= diameter <= CONTAMINATION_MAX_DIAMETER * s:
            continue
        claimed[y:y + h, x:x + w] |= component
        contrast = float(darkening[y:y + h, x:x + w][original].mean())
        q = abs(contrast) / CONTAMINATION_DARKENING
        found.append({
            "branch": "surface", "defect_type": "surface_contamination_candidate",
            "bbox_px": _to_image_bbox(ctx, offset, x, y, w, h),
            "support_area_px": int(original.sum()), "support_kind": "pixels_beyond_threshold",
            "contrast": round(contrast, 4), "threshold": -CONTAMINATION_DARKENING, "feature_scale_px": s,
            "score": round(q / (1 + q), 3), "reason_codes": ["UNCALIBRATED_DEMO_RULE"],
            "reference_id": None if reference is None else reference.reference_id,
        })
    return found, claimed


def _local_candidates(residual: np.ndarray, usable: np.ndarray, tau: float, s: float, offset: tuple[int, int],
                      ctx: GeometryContext, reference: SurfaceReference | None, halo: np.ndarray,
                      claimed: np.ndarray):
    """Local surface candidates, long bright structures, glare rims (the last two are not candidates)
    and the mask of the reported components.

    A bright component touching a saturated highlight's spill zone is its rim only
    if nothing of spot size remains outside that zone; otherwise it stays a
    candidate, flagged NEXT_TO_SATURATION. A dark component lying mostly (at least
    half) inside ``claimed`` is the contamination already reported there and is
    skipped; one merely touching it is independent. A dark line running across
    the filament is a texture direction anomaly."""
    found, bright_structures = [], []
    halos = 0
    reported = np.zeros_like(usable)
    analysed_length = float(np.ptp(np.nonzero(usable)[0])) + 1
    values = np.nan_to_num(residual)
    level = _masked_gaussian(np.abs(values), usable, 2 * s, 2 * s, max(1, int(s // 8)))
    local_tau = np.maximum(tau, LOCAL_TEXTURE_FACTOR * np.nan_to_num(level, nan=tau))
    for polarity, binary in (("bright", usable & (values > local_tau)), ("dark", usable & (values < -local_tau))):
        for (x, y, w, h), component, original in _components(binary, usable, s):
            pts = cv2.findNonZero(component.astype(np.uint8))
            if pts is None or len(pts) < 3:
                continue
            _, (rw, rh), _ = cv2.minAreaRect(pts)
            long_axis, short_axis = max(rw, rh), max(min(rw, rh), 1.0)
            aspect = long_axis / short_axis
            diameter = math.sqrt(4 * component.sum() / math.pi)
            contrast = float(values[y:y + h, x:x + w][original].mean()) if original.any() else 0.0
            # Principal direction from the pixel covariance; 0 deg = along the
            # specimen axis, which is vertical in the rotated frame.
            coords = pts.reshape(-1, 2).astype(np.float64)
            _, vectors = np.linalg.eigh(np.cov(coords.T))
            vx, vy = vectors[:, -1]
            off_axis = math.degrees(math.atan2(abs(vx), abs(vy)))
            # Touching a highlight does not make the whole component its rim: a
            # real spot next to a tiny clipped point was dropped entirely (Codex
            # review 2026-10-12). Only the spill zone itself is unanalysable.
            if polarity == "dark" and (component & claimed[y:y + h, x:x + w]).sum() >= 0.5 * component.sum():
                continue
            next_to_saturation = polarity == "bright" and bool((component & halo[y:y + h, x:x + w]).any())
            if next_to_saturation:
                rest = component & ~halo[y:y + h, x:x + w]
                if math.sqrt(4 * rest.sum() / math.pi) < 0.75 * s:
                    halos += 1
                    continue
            kind = None
            threshold = float(local_tau[y:y + h, x:x + w][component].mean())
            if polarity == "bright" and aspect >= ELONGATED_ASPECT and long_axis >= BRIGHT_STRUCTURE_LENGTH * s:
                bright_structures.append({"bbox_px": _to_image_bbox(ctx, offset, x, y, w, h),
                                          "length_px": round(float(long_axis), 1), "contrast": round(contrast, 4)})
                continue
            if polarity == "dark" and aspect >= ELONGATED_ASPECT and long_axis >= LINE_MIN_LENGTH * s:
                if off_axis <= AXIAL_LINE_DEG and long_axis >= TEXTURE_LINE_FRACTION * analysed_length:
                    continue  # a streak running most of the specimen is texture, not a local scratch
                threshold *= 2
                if abs(contrast) < threshold:
                    continue
                kind = ("surface_texture_direction_candidate" if off_axis >= DIRECTION_OFF_AXIS_DEG
                        else "surface_scratch_candidate")
            elif aspect < ELONGATED_ASPECT and 0.75 * s <= diameter <= SPOT_MAX_DIAMETER * s:
                # 0.75 s, not s: thresholding a blurred spot of size s keeps a slightly smaller core.
                kind = f"surface_{polarity}_spot_candidate"
            if kind is None:
                continue
            q = abs(contrast) / threshold
            found.append({
                "branch": "surface", "defect_type": kind,
                "bbox_px": _to_image_bbox(ctx, offset, x, y, w, h),
                "support_area_px": int(original.sum()), "support_kind": "pixels_beyond_threshold",
                "contrast": round(contrast, 4), "threshold": round(threshold, 4),
                "feature_scale_px": s, "score": round(q / (1 + q), 3),
                "reason_codes": ["NEXT_TO_SATURATION"] if next_to_saturation else [],
                "reference_id": None if reference is None else reference.reference_id,
            })
            reported[y:y + h, x:x + w] |= component
            if kind == "surface_texture_direction_candidate":
                found[-1].update(off_axis_deg=round(off_axis, 1), reason_codes=[
                    "TRANSVERSE_DARK_LINE" if off_axis >= TRANSVERSE_LINE_DEG else "OFF_AXIS_DARK_LINE",
                    "UNCALIBRATED_DEMO_RULE"])
    return found, bright_structures, halos, reported


def _demo_roughness_candidate(usable: np.ndarray, offset: tuple[int, int], ctx: GeometryContext,
                              streaks: float, low: float) -> dict[str, Any]:
    ys, xs = np.nonzero(usable)
    return {
        "branch": "surface", "defect_type": "surface_demo_roughness_candidate",
        "bbox_px": _to_image_bbox(ctx, offset, xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1),
        "support_area_px": int(usable.sum()), "support_kind": "analysed_area",
        "contrast": streaks, "threshold": low, "feature_scale_px": None,
        # q / (1 + q) with q = streaks / low, written so that a tiny low bound cannot overflow.
        "score": round(1 / (1 + low / streaks), 3), "reason_codes": ["UNCALIBRATED_DEMO_THRESHOLD"],
        "reference_id": None,
    }


def _texture_candidate(usable: np.ndarray, offset: tuple[int, int], ctx: GeometryContext, ratio: float,
                       reference: SurfaceReference) -> dict[str, Any]:
    ys, xs = np.nonzero(usable)
    q = ratio / STRONGLY_DEVIATES_RATIO
    return {
        "branch": "surface", "defect_type": "surface_texture_deviation_candidate",
        "bbox_px": _to_image_bbox(ctx, offset, xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1),
        # The area that supports the comparison, not a defect area.
        "support_area_px": int(usable.sum()), "support_kind": "analysed_area",
        "contrast": round(ratio, 3), "threshold": STRONGLY_DEVIATES_RATIO, "feature_scale_px": None,
        "score": round(q / (1 + q), 3), "reason_codes": [], "reference_id": reference.reference_id,
    }
