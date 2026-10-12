"""Bright-field silhouette geometry for one clamped, static rPLA specimen.

The specimen is located against a smooth background by colour distance, its
two edges are refined to sub-pixel positions on the full-resolution image, and
sustained local changes of the projected width become candidates. Every value
is in pixels of the analysed image; none of it is a physical measurement.

A frame that cannot be measured is returned as ``rejected`` with reason codes,
so that "no candidates" is never reported for a sample that was not located or
whose focus could not be verified.

Focus is judged from the silhouette edge alone. A wide edge is read as "focus
not verifiable", not as "defocused": an in-focus specimen whose silhouette is
intrinsically soft (on 2026-10-12 a dark grey specimen: about 34 px against
11-19 px for three others in the same set-up) is indistinguishable from a
defocused one by this measure. Neither the steepest slope nor the sharpness of
small specks separated the two on real images (both let a known-defocused
2026-09-30 image through), so such views stay unjudged.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from dataclasses import asdict, dataclass, field
from contextlib import contextmanager
import math
from typing import Any, Iterator
import warnings

import cv2
import numpy as np


# Fixed rules of this algorithm version (not tuning knobs).
BACKGROUND_BAND_FRACTION = 0.10  # each side of the search ROI is assumed to be background
COARSE_LONG_SIDE_PX = 960  # coarse localisation only; edges are refined at full resolution
SIGMA_FLOOR_LAB = 0.5  # keeps a noise-free synthetic background from dividing by zero
SECOND_COMPONENT_RATIO = 0.25  # a second region this large means two objects in view
MAX_AXIS_TILT_DEG = 45.0
SKIP_ROTATION_BELOW_DEG = 0.25  # avoid interpolation blur for a specimen that is already aligned
MAX_LOCAL_TILT_DEG = 15.0  # phase 1 measures held, near-straight specimens; stronger bends are rejected
CLIP_LOW, CLIP_HIGH = 2, 253
EDGE_LEVEL, LOW_LEVEL, HIGH_LEVEL = 0.5, 0.1, 0.9

# Reasons that mean the specimen itself was not found, as opposed to found but
# not measurable. The live preview treats these as "waiting for material".
LOCALIZATION_REASONS = frozenset({
    "SAMPLE_NOT_LOCALIZED", "SEGMENTATION_AMBIGUOUS", "BACKGROUND_BAND_OBSTRUCTED",
    "AXIS_COVERAGE_LOW", "AXIS_ORIENTATION_UNEXPECTED", "SPECIMEN_TOO_NARROW",
})

STATUS_VALID = "valid"
STATUS_REJECTED = "rejected"
STATUS_NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True, slots=True)
class GeometryParams:
    """Configuration of the geometry branch; see docs/static_rpla_inspection.md."""

    search_roi_px: tuple[int, int, int, int] | None = None
    filament_axis: str = "vertical"
    min_feature_px: float = 12.0
    min_run_px: int = 40
    background_z_min: float = 5.0
    min_axis_coverage: float = 0.9
    max_edge_spread_px: float | None = None
    clip_fraction_max: float = 0.01
    good_width_range_px: tuple[float, float] | None = None
    width_local_limit_px: float | None = None

    def __post_init__(self) -> None:
        if self.filament_axis not in {"vertical", "horizontal", "auto"}:
            raise ValueError("filament_axis must be 'vertical', 'horizontal' or 'auto'")
        if self.search_roi_px is not None:
            if len(self.search_roi_px) != 4 or any(
                isinstance(value, bool) or int(value) != value for value in self.search_roi_px
            ):
                raise ValueError("search_roi_px must contain four integers")
            x, y, width, height = self.search_roi_px
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise ValueError("search_roi_px must have a non-negative origin and positive size")
        for name in ("min_feature_px", "background_z_min"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if isinstance(self.min_run_px, bool) or not isinstance(self.min_run_px, int) or self.min_run_px < 2:
            raise ValueError("min_run_px must be an integer of at least 2")
        for name in ("min_axis_coverage", "clip_fraction_max"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        for name in ("max_edge_spread_px", "width_local_limit_px"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be null or positive and finite")
        if self.good_width_range_px is not None:
            low, high = self.good_width_range_px
            if not (math.isfinite(low) and math.isfinite(high) and 0 < low < high):
                raise ValueError("good_width_range_px must satisfy 0 < low < high")

    @property
    def edge_spread_limit_px(self) -> float:
        return self.max_edge_spread_px if self.max_edge_spread_px is not None else self.min_feature_px / 2

    @property
    def width_limit_px(self) -> float:
        return self.width_local_limit_px if self.width_local_limit_px is not None else self.min_feature_px / 2

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "GeometryParams":
        known = {name for name in cls.__dataclass_fields__}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"unknown static inspection parameters: {sorted(unknown)}")
        data = dict(values)
        for name in ("search_roi_px", "good_width_range_px"):
            if data.get(name) is not None:
                data[name] = tuple(data[name])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for name in ("search_roi_px", "good_width_range_px"):
            if result[name] is not None:
                result[name] = list(result[name])
        result["effective_edge_spread_limit_px"] = self.edge_spread_limit_px
        result["effective_width_local_limit_px"] = self.width_limit_px
        return result


@dataclass(slots=True)
class GeometryOutcome:
    status: str
    reason_codes: list[str]
    metrics: dict[str, Any]
    candidates: list[dict[str, Any]] = field(default_factory=list)
    # Polylines in image coordinates for the overlay; not part of the record.
    left_edge_xy: np.ndarray | None = None
    right_edge_xy: np.ndarray | None = None
    roi_px: tuple[int, int, int, int] | None = None
    # Stretches whose edges could not be measured. They limit coverage; they
    # are image-quality findings, not defect candidates.
    unmeasured: list[dict[str, Any]] = field(default_factory=list)
    # In-process hand-over to the surface branch (valid views only); never serialised.
    context: "GeometryContext | None" = None


@dataclass(slots=True)
class GeometryContext:
    """What the surface branch needs from a valid geometry pass.

    ``rotated`` is the axis-vertical image *before* the light edge smoothing,
    so short surface features are not weakened before they are measured.
    """

    rotated: np.ndarray
    valid_pixels: np.ndarray
    rows: np.ndarray
    left_x: np.ndarray
    right_x: np.ndarray
    valid_rows: np.ndarray
    local_edge_spread: np.ndarray
    frame: "_Frame"


class _Frame:
    """Map points between the image and the axis-vertical analysis frame."""

    def __init__(self, roi_px: tuple[int, int, int, int], transposed: bool, matrix: np.ndarray | None):
        self.roi_px = roi_px
        self.transposed = transposed
        self.inverse = None if matrix is None else cv2.invertAffineTransform(matrix)

    def to_image(self, points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if self.inverse is not None:
            pts = pts @ self.inverse[:, :2].T + self.inverse[:, 2]
        if self.transposed:
            pts = pts[:, ::-1]
        return pts + np.array(self.roi_px[:2], dtype=np.float64)


def _validate_image(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a BGR array with three channels")
    if image.dtype != np.uint8:
        raise ValueError("image must be uint8")
    if min(image.shape[:2]) < 32:
        raise ValueError("image is too small for geometry analysis")


def _resolve_roi(shape: tuple[int, ...], roi: tuple[int, int, int, int] | None) -> tuple[int, int, int, int]:
    height, width = shape[:2]
    if roi is None:
        return 0, 0, width, height
    x, y, w, h = (int(value) for value in roi)
    if x + w > width or y + h > height:
        raise ValueError("search_roi_px lies outside the image")
    return x, y, w, h


def _rejected(reasons: list[str], metrics: dict[str, Any], roi: tuple[int, int, int, int],
              left: np.ndarray | None = None, right: np.ndarray | None = None) -> GeometryOutcome:
    return GeometryOutcome(STATUS_REJECTED, reasons, metrics, [], left, right, roi)


def _coarse_localise(work: np.ndarray, params: GeometryParams, metrics: dict[str, Any]):
    """Return per-row coarse edges at coarse scale, or a reason code."""
    height, width = work.shape[:2]
    scale = min(1.0, COARSE_LONG_SIDE_PX / max(height, width))
    small = cv2.resize(work, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else work
    lab = cv2.cvtColor(small.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)
    rows, cols = lab.shape[:2]
    band = max(2, round(cols * BACKGROUND_BAND_FRACTION))
    left, right = lab[:, :band], lab[:, cols - band:]
    left_median, right_median = np.median(left, axis=1), np.median(right, axis=1)
    # Interpolate the background across each row so a gentle illumination
    # gradient is not mistaken for the specimen.
    centre_left, centre_right = (band - 1) / 2, cols - band + (band - 1) / 2
    t = np.clip((np.arange(cols) - centre_left) / (centre_right - centre_left), 0, 1).astype(np.float32)
    background = left_median[:, None, :] * (1 - t)[None, :, None] + right_median[:, None, :] * t[None, :, None]
    residual = np.concatenate([left - left_median[:, None, :], right - right_median[:, None, :]], axis=1)
    sigma = np.maximum(1.4826 * np.median(np.abs(residual), axis=(0, 1)), SIGMA_FLOOR_LAB)
    z = np.sqrt((((lab - background) / sigma) ** 2).sum(axis=2))

    z_top = float(np.percentile(z, 99.5))
    metrics.update(coarse_scale=round(scale, 5), background_sigma_lab=[round(float(v), 3) for v in sigma],
                   z_p99_5=round(z_top, 2))
    if z_top <= params.background_z_min:
        return "SAMPLE_NOT_LOCALIZED"
    z_u8 = np.uint8(np.clip(z / z_top, 0, 1) * 255)
    otsu, _ = cv2.threshold(z_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    otsu_z = float(otsu) / 255 * z_top
    threshold = max(otsu_z, params.background_z_min)
    metrics.update(otsu_threshold_z=round(otsu_z, 2), segmentation_threshold_z=round(threshold, 2))
    mask = np.uint8(z > threshold)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return "SAMPLE_NOT_LOCALIZED"
    areas = stats[1:, cv2.CC_STAT_AREA]
    order = np.argsort(areas)[::-1]
    main = int(order[0]) + 1
    if len(order) > 1 and areas[order[1]] >= SECOND_COMPONENT_RATIO * areas[order[0]]:
        metrics["second_component_area_ratio"] = round(float(areas[order[1]] / areas[order[0]]), 3)
        return "SEGMENTATION_AMBIGUOUS"
    x0 = stats[main, cv2.CC_STAT_LEFT]
    x1 = x0 + stats[main, cv2.CC_STAT_WIDTH]
    if x0 < band or x1 > cols - band:
        return "BACKGROUND_BAND_OBSTRUCTED"
    component = labels == main
    present = component.any(axis=1)
    coverage = float(present.mean())
    metrics["component_axis_coverage"] = round(coverage, 4)
    if coverage < params.min_axis_coverage:
        return "AXIS_COVERAGE_LOW"
    row_idx = np.flatnonzero(present)
    first = component[row_idx].argmax(axis=1)
    last = cols - 1 - component[row_idx, ::-1].argmax(axis=1)
    return scale, row_idx, first.astype(np.float64), last.astype(np.float64)


@contextmanager
def _quiet_nan() -> Iterator[None]:
    """All-NaN slices are expected (invalid sections); their results stay NaN."""
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        yield


def _odd(window: int) -> int:
    return max(3, int(window) | 1)


def _nan_median_filter(values: np.ndarray, window: int) -> np.ndarray:
    # NaN padding truncates the window at the ends. Reflection would mirror an
    # anomaly that sits near an end and let it outvote the normal trend.
    window = _odd(window)
    padded = np.pad(values.astype(np.float64), window // 2, constant_values=np.nan)
    # Vectorised NaN-aware median: sorting puts NaN last, so each window's median
    # is read at its own count of finite values. (np.nanmedian falls back to a
    # per-row Python loop when NaN is present; that cost about 0.1 s per call at
    # 4K and pushed live processing towards the stale-frame limit.)
    ordered = np.sort(np.lib.stride_tricks.sliding_window_view(padded, window), axis=1)
    count = np.isfinite(ordered).sum(axis=1)
    rows = np.arange(len(ordered))
    low = ordered[rows, np.maximum(count - 1, 0) // 2]
    high = ordered[rows, count // 2 - (count == 0)]
    return np.where(count > 0, (low + high) / 2, np.nan)


def _local_line(values: np.ndarray, window: int,
                weights: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Weighted least-squares line over a centred window, truncated at the ends.

    Returns the fitted value and slope at every position (NaN where fewer than
    three weighted points exist). A local line stays unbiased for a locally
    straight trend even where the window is cut short at an end, unlike a
    running median or smoothing followed by differencing.
    """
    window = _odd(window)
    finite = np.isfinite(values)
    w = finite.astype(np.float64) if weights is None else np.where(finite, weights, 0.0)
    axis = np.arange(len(values), dtype=np.float64)
    centre = axis - axis.mean()
    y = np.where(finite, values, 0.0)
    kernel = np.ones(window)
    half = window // 2

    def total(series: np.ndarray) -> np.ndarray:
        # "full" then centre-crop keeps the input length even when the window
        # is longer than the series ("same" would return the window length).
        return np.convolve(series, kernel, mode="full")[half:half + len(series)]

    n, sx, sy = total(w), total(w * centre), total(w * y)
    sxx, sxy = total(w * centre * centre), total(w * centre * y)
    denominator = n * sxx - sx * sx
    with _quiet_nan():
        usable = (total(w > 0) >= 3) & (denominator > 1e-9 * np.maximum(n * sxx, 1.0))
        slope = np.where(usable, (n * sxy - sx * sy) / denominator, np.nan)
        fit = np.where(usable, (sy - slope * sx) / n + slope * centre, np.nan)
    return fit, slope


def _bisquare(values: np.ndarray, fit: np.ndarray, cutoff_px: float) -> np.ndarray:
    """Bisquare weights; residuals beyond cutoff_px (or 4.685 robust sigmas) weigh zero."""
    residual = values - fit
    with _quiet_nan():
        sigma = 1.4826 * np.nanmedian(np.abs(residual))
    scale = max(4.685 * float(sigma) if np.isfinite(sigma) else 0.0, cutoff_px)
    u = np.clip(np.abs(np.nan_to_num(residual, nan=np.inf)) / scale, 0, 1)
    return (1 - u ** 2) ** 2


def _robust_edge_trend(values: np.ndarray, window: int, cutoff_px: float,
                       iterations: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Local-line trend and slope of one edge, reweighted so a one-sided bump does not tilt it.

    Used for the local axis tilt, side attribution and roughness metrics only;
    width candidates are judged against ``_robust_width_reference``.
    """
    fit = _nan_median_filter(values, window)
    slope = np.zeros_like(fit)
    for _ in range(iterations):
        fit, slope = _local_line(values, window, _bisquare(values, fit, cutoff_px))
    return fit, slope


def _robust_width_reference(widths: np.ndarray, cutoff_px: float, iterations: int = 6) -> np.ndarray:
    """The specimen's own width model: a bisquare-weighted quadratic over the whole length.

    A held filament's width across the field can taper or flare slowly but has
    no other legitimate structure, so the whole measured length is the
    reference. A sliding window cannot be used: anomalies that together fill
    most of a window (two close bulges, or one bulge at a truncated end) then
    become the "trend" and vanish. Anomalies longer than roughly a quarter of
    the length are absorbed as the specimen's shape; ``good_width_range_px``
    bounds the absolute width for those.
    """
    finite = np.isfinite(widths)
    axis = np.linspace(-1.0, 1.0, len(widths))
    fit = _lmeds_quadratic_start(axis, widths, finite)
    for _ in range(iterations):
        weights = _bisquare(widths, fit, cutoff_px)
        use = finite & (weights > 0)
        if use.sum() < 3:
            break
        fit = np.polyval(np.polyfit(axis[use], widths[use], 2, w=np.sqrt(weights[use])), axis)
    return fit


def _lmeds_quadratic_start(axis: np.ndarray, values: np.ndarray, finite: np.ndarray,
                           segments: int = 16) -> np.ndarray:
    """Starting quadratic with a 50 % breakdown point.

    An ordinary least-squares start is pulled towards a long anomaly, and a
    quadratic can then bend to absorb part of it (a central hump, false necks
    on its flanks). Instead, take the median width of each axial segment and
    keep the exact quadratic through three segment medians that minimises the
    median absolute residual over all segments (least median of squares).
    """
    bounds = np.linspace(0, len(values), segments + 1).astype(int)
    xs, ys = [], []
    for start, stop in zip(bounds[:-1], bounds[1:]):
        keep = finite[start:stop]
        if keep.sum() >= max(3, (stop - start) // 2):
            xs.append(float(axis[start:stop][keep].mean()))
            ys.append(float(np.median(values[start:stop][keep])))
    xs, ys = np.array(xs), np.array(ys)
    if len(xs) < 3:
        return np.polyval(np.polyfit(axis[finite], values[finite], min(2, int(finite.sum()) - 1)), axis)
    best, best_score = None, np.inf
    for triple in combinations(range(len(xs)), 3):
        index = list(triple)
        coefficients = np.polyfit(xs[index], ys[index], 2)
        score = float(np.median(np.abs(ys - np.polyval(coefficients, xs))))
        if score < best_score:
            best, best_score = coefficients, score
    return np.polyval(best, axis)


def _channel_max(image: np.ndarray) -> np.ndarray:
    """Per-pixel maximum over the three channels (much faster than ndarray.max(axis=2))."""
    blue, green, red = cv2.split(image)
    return cv2.max(cv2.max(blue, green), red)


def _crossings(q: np.ndarray, level: float) -> np.ndarray:
    """Sub-pixel positions where each row of ``q`` crosses ``level``; NaN elsewhere."""
    a, b = q[:, :-1], q[:, 1:]
    hit = ((a < level) != (b < level)) & (a != b)
    with _quiet_nan():
        fraction = (level - a) / (b - a)
    positions = np.arange(q.shape[1] - 1)[None, :] + fraction
    return np.where(hit, positions, np.nan)


def _edge_side(rotated: np.ndarray, valid_px: np.ndarray, rows: np.ndarray, coarse_x: np.ndarray,
               inward: int, window: int, plateau: int, d: float) -> dict[str, np.ndarray]:
    """Refine one edge on every row. ``inward`` is +1 for the left edge, -1 for the right.

    Both reference levels are local plateaus just beyond the search window on
    each side of the edge. A cylinder in bright field is shaded (its centre is
    darker or brighter than its silhouette), so the specimen centre is not a
    valid "inside" level for an edge.
    """
    width = rotated.shape[1]
    centres = np.round(coarse_x).astype(np.int64)
    columns = centres[:, None] + (np.arange(-window, window + 1) * inward)[None, :]
    steps = (window + 1 + np.arange(plateau))[None, :]
    in_bounds = np.ones(len(rows), bool)
    sampled = []
    for cols in (columns, centres[:, None] - inward * steps, centres[:, None] + inward * steps):
        in_bounds &= (cols.min(axis=1) >= 0) & (cols.max(axis=1) < width)
        safe = np.clip(cols, 0, width - 1)
        in_bounds &= valid_px[rows[:, None], safe].all(axis=1)
        sampled.append(rotated[rows[:, None], safe].astype(np.float32))
    profile, outside, inside = sampled  # profile runs outside -> inside
    background = np.median(outside, axis=1)
    contrast_vec = np.median(inside, axis=1) - background
    contrast = np.linalg.norm(contrast_vec, axis=1)
    with _quiet_nan():
        unit = contrast_vec / contrast[:, None]
        q = ((profile - background[:, None, :]) * contrast_vec[:, None, :]).sum(axis=2) / (contrast ** 2)[:, None]
        noise_proj = ((outside - background[:, None, :]) * unit[:, None, :]).sum(axis=2)
    noise = 1.4826 * np.nanmedian(np.abs(noise_proj))
    noise = max(float(noise), 0.5)
    contrast_ratio = contrast / noise

    mid = _crossings(q, EDGE_LEVEL)
    count = np.isfinite(mid).sum(axis=1)
    with _quiet_nan():
        span = np.nanmax(mid, axis=1) - np.nanmin(mid, axis=1)
        x50 = np.nanmean(mid, axis=1)
        low = _crossings(q, LOW_LEVEL)
        high = _crossings(q, HIGH_LEVEL)
        x10 = np.nanmax(np.where(low < x50[:, None], low, np.nan), axis=1)
        x90 = np.nanmin(np.where(high > x50[:, None], high, np.nan), axis=1)
        transition = x90 - x10
        # Edge width as (normalised contrast) / (slope at the half-level
        # crossing), between the two local plateaus. For a Gaussian-blurred step
        # it is within a few percent of the 10-90 width, and a slow shading ramp
        # changes it less than the 10-90 distance. It is not the steepest slope:
        # a ramp that reaches the plateau also lowers the slope at the crossing,
        # so the value depends on the silhouette's shape as well as on focus.
        # The 10/90 crossings still have to exist so that the transition is
        # known to complete inside the window.
        slope = (_sample(q, x50 + 1) - _sample(q, x50 - 1)) / 2
        spread = np.where(slope > 0, 1 / slope, np.inf)

    reason = np.full(len(rows), "", dtype=object)
    reason[~in_bounds] = "WINDOW_OUT_OF_FRAME"
    reason[(reason == "") & (contrast_ratio < 1.0)] = "LOW_CONTRAST"
    reason[(reason == "") & (count == 0)] = "EDGE_NOT_FOUND"
    reason[(reason == "") & (span > d / 2)] = "MULTIPLE_EDGES"
    reason[(reason == "") & ~np.isfinite(transition)] = "EDGE_TRANSITION_UNRESOLVED"
    reason[(reason == "") & ~np.isfinite(spread)] = "EDGE_NOT_FOUND"
    position = centres - inward * window + inward * x50
    return {"x": position, "spread": spread, "transition": transition, "valid": reason == "",
            "reason": reason, "contrast_ratio": contrast_ratio, "noise": noise}


def _sample(q: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Linearly interpolate each row of ``q`` at one fractional position (NaN-safe)."""
    last = q.shape[1] - 1
    finite = np.isfinite(positions)
    pos = np.clip(np.where(finite, positions, 0), 0, last)
    index = np.minimum(np.floor(pos).astype(np.int64), last - 1)
    fraction = pos - index
    rows = np.arange(q.shape[0])
    values = q[rows, index] * (1 - fraction) + q[rows, index + 1] * fraction
    return np.where(finite, values, np.nan)


def _bridge(flags: np.ndarray, valid: np.ndarray, max_gap: float) -> np.ndarray:
    """Join flagged stretches across short unmeasured gaps.

    One unmeasurable section (a reflection or a ragged step) inside a defect
    would otherwise split it into runs that are each shorter than min_run_px.
    """
    bridged = flags.copy()
    for start, stop in _runs(~valid):
        if stop - start <= max_gap and start > 0 and stop < len(flags) and flags[start - 1] and flags[stop]:
            bridged[start:stop] = True
    return bridged


def _prefer(first: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Per row, take ``first`` where it measured an edge, else ``fallback``.

    A check that the short window's outer plateau is still the background was
    tried twice (Codex review 2026-10-12) and removed: it caught only an outer
    structure whose shade sits at about half-way between background and body,
    while a slightly lighter one is missed by every path anyway (coarse
    localisation and both windows treat it as background), and in both forms
    it refused sharp, valid edges under glare plus a mild background shadow.
    """
    use = first["valid"]
    merged = {key: np.where(use, first[key], fallback[key])
              for key in ("x", "spread", "transition", "valid", "reason", "contrast_ratio")}
    merged["noise"] = first["noise"]
    return merged


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    padded = np.concatenate([[False], flags, [False]])
    change = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(change[::2], change[1::2]))


def analyse_geometry(image: np.ndarray, params: GeometryParams) -> GeometryOutcome:
    """Measure the projected-width profile of one specimen in a bright-field view."""
    _validate_image(image)
    roi = _resolve_roi(image.shape, params.search_roi_px)
    x, y, w, h = roi
    # "auto" tries both orientations: with the wrong one the specimen crosses
    # the background bands and localisation fails. If both localise (a
    # specimen near 45 degrees), the orientation with the smaller tilt wins.
    axes = ("vertical", "horizontal") if params.filament_axis == "auto" else (params.filament_axis,)
    attempts = []
    for axis in axes:
        attempt_work = image[y:y + h, x:x + w]
        if axis == "horizontal":
            attempt_work = np.ascontiguousarray(attempt_work.transpose(1, 0, 2))
        attempt_metrics: dict[str, Any] = {"search_roi_px": list(roi), "filament_axis": axis}
        attempt = _coarse_localise(attempt_work, params, attempt_metrics)
        tilt = math.inf
        if not isinstance(attempt, str):
            _, attempt_rows, attempt_left, attempt_right = attempt
            slope = float(np.polyfit(attempt_rows, (attempt_left + attempt_right) / 2, 1)[0])
            tilt = math.degrees(math.atan(slope))
        attempts.append((abs(tilt), axis, attempt_work, attempt, attempt_metrics, tilt))
    _, axis, work, coarse, metrics, tilt_deg = min(attempts, key=lambda item: item[0])
    transposed = axis == "horizontal"
    if isinstance(coarse, str):
        reasons = list(dict.fromkeys(item[3] for item in attempts))
        return _rejected(reasons, metrics, roi)
    scale, coarse_rows, coarse_left, coarse_right = coarse

    # Rotate so the specimen runs vertically in the analysis frame.
    metrics["axis_tilt_deg"] = round(tilt_deg, 3)
    if abs(tilt_deg) > MAX_AXIS_TILT_DEG:
        return _rejected(["AXIS_ORIENTATION_UNEXPECTED"], metrics, roi)
    height, width = work.shape[:2]
    if abs(tilt_deg) >= SKIP_ROTATION_BELOW_DEG:
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), -tilt_deg, 1.0)
        rotated = cv2.warpAffine(work, matrix, (width, height), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        valid_px = cv2.warpAffine(np.ones((height, width), np.uint8), matrix, (width, height),
                                  flags=cv2.INTER_NEAREST, borderValue=0).astype(bool)
    else:
        matrix, rotated, valid_px = None, work, np.ones((height, width), bool)
    frame = _Frame(roi, transposed, matrix)

    def to_rotated(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        pts = np.column_stack([(xs + 0.5) / scale - 0.5, (ys + 0.5) / scale - 0.5])
        if matrix is not None:
            pts = pts @ matrix[:, :2].T + matrix[:, 2]
        return pts

    left_pts = to_rotated(coarse_left, coarse_rows)
    right_pts = to_rotated(coarse_right, coarse_rows)
    lo = int(math.ceil(max(left_pts[:, 1].min(), right_pts[:, 1].min())))
    hi = int(math.floor(min(left_pts[:, 1].max(), right_pts[:, 1].max())))
    rows = np.arange(max(lo, 0), min(hi, height - 1) + 1)
    if len(rows) < params.min_run_px * 2:
        return _rejected(["AXIS_COVERAGE_LOW"], metrics, roi)
    order_l, order_r = np.argsort(left_pts[:, 1]), np.argsort(right_pts[:, 1])
    left_x = np.interp(rows, left_pts[order_l, 1], left_pts[order_l, 0])
    right_x = np.interp(rows, right_pts[order_r, 1], right_pts[order_r, 0])

    d = params.min_feature_px
    # The search window has to hold an acceptable edge (10-90 width up to the
    # d/2 focus limit, so about d from 0 to 100 %) plus the coarse localisation
    # error. It must not grow faster than that with d: a large d at high
    # magnification would otherwise reject a wide specimen as too narrow.
    window = int(math.ceil(max(1.5 * d, 4 / scale)))
    plateau = int(math.ceil(max(d / 2, 8)))
    coarse_width = float(np.median(right_x - left_x))
    # Each edge needs its search window plus an inside plateau within the specimen.
    if coarse_width < 2 * (window + plateau) + 2:
        metrics["coarse_width_px"] = round(coarse_width, 2)
        return _rejected(["SPECIMEN_TOO_NARROW"], metrics, roi)

    # Smooth lightly: one pixel across the edge, at most d/6 along the axis.
    smoothed = cv2.GaussianBlur(rotated, (0, 0), sigmaX=1.0, sigmaY=max(1.0, d / 6))

    def measure(search: int, plate: int):
        left = _edge_side(smoothed, valid_px, rows, left_x, +1, search, plate, d)
        right = _edge_side(smoothed, valid_px, rows, right_x, -1, search, plate, d)
        valid = left["valid"] & right["valid"]
        reasons = Counter(r for r in np.concatenate([left["reason"], right["reason"]]) if r)
        return left, right, valid, reasons

    left, right, valid, reasons = measure(window, plateau)
    spread_now = (float(np.median(np.concatenate([left["spread"][valid], right["spread"][valid]])))
                  if valid.any() else math.inf)
    # A sharp edge needs only a short window. Sized from d, the inside reference
    # plateau can land on surface structure: on the 2026-10-12 bench a specular
    # streak 60-200 px inside a 5 px edge became the "edge" (MULTIPLE_EDGES on
    # 40 % of rows). Re-measure with a window sized from the spread just
    # measured. Per row and side the short window's result is preferred (its
    # plateaus sit next to the edge); the first result is kept only where the
    # short window, tight against the coarse-localisation error, failed.
    if math.isfinite(spread_now):
        narrow = int(math.ceil(max(3 * spread_now, 4 / scale, 8)))
        narrow_plateau = int(math.ceil(max(2 * spread_now, 8)))
        if narrow < window:
            short_left, short_right, _, _ = measure(narrow, narrow_plateau)
            left, right = _prefer(short_left, left), _prefer(short_right, right)
            valid = left["valid"] & right["valid"]
            reasons = Counter(r for r in np.concatenate([left["reason"], right["reason"]]) if r)
            metrics["edge_search_narrowed"] = {"window_px": narrow, "plateau_px": narrow_plateau}
    # A defocused edge is wider than the normal search window. Measure it once
    # with a wider window so the focus gate can report the actual spread instead
    # of a bare "not resolved"; the wider window never relaxes the gate itself.
    # Only when the edges are not known to be sharp: widening a window around a
    # sharp edge just reaches further into surface structure.
    widened = 3 * window
    if (valid.mean() < params.min_axis_coverage
            and reasons.most_common(1)[0][0] in {"EDGE_TRANSITION_UNRESOLVED", "EDGE_NOT_FOUND"}
            and spread_now > window / 3
            and coarse_width >= 2 * (widened + plateau) + 2):
        window = widened
        left, right, valid, reasons = measure(window, plateau)
        metrics["edge_search_widened"] = True
    measured = valid
    with _quiet_nan():
        contrast_median = float(np.nanmedian(np.concatenate([left["contrast_ratio"], right["contrast_ratio"]])))
    metrics.update(
        sections_total=int(len(rows)), sections_measured=int(measured.sum()),
        edge_search_window_px=window,
        contrast_ratio_median=round(contrast_median, 2),
        edge_spread_limit_px=params.edge_spread_limit_px,
    )
    step = max(1, len(rows) // 400)
    overlay_rows = rows[::step]

    def overlay(mask: np.ndarray):
        # Unmeasured sections become NaN rows, so the drawing breaks there
        # instead of bridging a gap with a straight line.
        keep = mask[::step]
        left_xy = frame.to_image(np.column_stack([left["x"][::step], overlay_rows]))
        right_xy = frame.to_image(np.column_stack([right["x"][::step], overlay_rows]))
        left_xy[~keep] = np.nan
        right_xy[~keep] = np.nan
        return left_xy, right_xy

    def finish_metrics(final_valid: np.ndarray) -> None:
        metrics.update(sections_valid=int(final_valid.sum()), valid_fraction=round(float(final_valid.mean()), 4),
                       invalid_section_reasons=dict(reasons))

    if measured.any():
        spreads = np.concatenate([left["spread"][measured], right["spread"][measured]])
        metrics["edge_spread_px_median"] = round(float(np.median(spreads)), 2)
        metrics["edge_spread_px_p90"] = round(float(np.percentile(spreads, 90)), 2)
        # Diagnostic only: includes any shading ramp within the search window.
        metrics["edge_transition_10_90_px_median"] = round(float(np.median(
            np.concatenate([left["transition"][measured], right["transition"][measured]]))), 2)
    if measured.mean() < params.min_axis_coverage:
        finish_metrics(measured)
        dominant = reasons.most_common(1)[0][0] if reasons else "EDGE_NOT_FOUND"
        return _rejected(["EDGES_NOT_RESOLVED", dominant], metrics, roi, *overlay(measured))
    if metrics["edge_spread_px_median"] > params.edge_spread_limit_px:
        finish_metrics(measured)
        metrics["focus_gate"] = "global_spread"
        return _rejected(["FOCUS_UNVERIFIABLE"], metrics, roi, *overlay(measured))

    # Local axis tilt, for the normal width: the mean slope of the two edges'
    # robust trends. A one-sided bump is down-weighted in its own edge's trend,
    # so it does not read as tilt; a symmetric taper cancels in the mean; and on
    # a thick bend the inner and outer edges differ, their mean being the
    # centreline. The width correction is second order in any tilt error.
    trend_window = 10 * params.min_run_px
    limit = params.width_limit_px
    left_trend, left_slope = _robust_edge_trend(np.where(measured, left["x"], np.nan), trend_window, limit)
    right_trend, right_slope = _robust_edge_trend(np.where(measured, right["x"], np.nan), trend_window, limit)
    tilt = np.nan_to_num((left_slope + right_slope) / 2)
    tilt_deg_max = float(np.degrees(np.arctan(np.abs(tilt[measured]).max())))
    metrics["local_tilt_deg_max"] = round(tilt_deg_max, 2)
    if tilt_deg_max > MAX_LOCAL_TILT_DEG:
        finish_metrics(measured)
        return _rejected(["CURVATURE_OUT_OF_SCOPE"], metrics, roi, *overlay(measured))

    # Focus is also judged locally: a blurred stretch must not hide a defect
    # behind a sharp majority. Smoothing over min_run_px keeps one noisy row
    # from deciding; such sections are then treated as unmeasured.
    local_spread = np.fmax(
        _nan_median_filter(np.where(measured, left["spread"], np.nan), params.min_run_px),
        _nan_median_filter(np.where(measured, right["spread"], np.nan), params.min_run_px),
    )
    with _quiet_nan():
        out_of_focus = measured & (local_spread > params.edge_spread_limit_px)
    if out_of_focus.any():
        reasons["LOCAL_FOCUS_UNVERIFIABLE"] = int(out_of_focus.sum())
    valid = measured & ~out_of_focus

    def reasons_by_row() -> np.ndarray:
        by_row = np.where(left["reason"] != "", left["reason"], right["reason"])
        return np.where(out_of_focus, "LOCAL_FOCUS_UNVERIFIABLE", by_row)

    finish_metrics(valid)
    left_xy, right_xy = overlay(valid)
    if valid.mean() < params.min_axis_coverage:
        metrics["focus_gate"] = "local_coverage"
        return _rejected(["FOCUS_UNVERIFIABLE"], metrics, roi, left_xy, right_xy)

    # Clipping is judged on the specimen only; a saturated backlight is legitimate.
    # Only the columns the specimen occupies; a full-width channel maximum at 4K
    # cost about 0.1 s.
    c0 = int(max(0, np.floor(np.nanmin(left["x"][valid]))))
    c1 = int(min(width, np.ceil(np.nanmax(right["x"][valid])) + 1))
    body = np.ascontiguousarray(rotated[rows[valid], c0:c1])
    columns = np.arange(c0, c1)[None, :]
    inside = (columns >= left["x"][valid][:, None]) & (columns <= right["x"][valid][:, None])
    inside &= valid_px[rows[valid], c0:c1]
    grey = cv2.cvtColor(body, cv2.COLOR_BGR2GRAY)
    clipped = ((grey <= CLIP_LOW) | (_channel_max(body) >= CLIP_HIGH)) & inside
    clip_fraction = float(clipped.sum() / max(1, inside.sum()))
    # The width depends only on the edge transitions, so the gate looks at
    # clipping within one search window inside each edge. Saturated glare in
    # the interior (1.3 % of the specimen on the 2026-10-12 bench) does not move
    # an edge; the surface branch excludes it and checks its own coverage.
    lefts, rights = left["x"][valid][:, None], right["x"][valid][:, None]
    edge_band = inside & ((columns <= lefts + window) | (columns >= rights - window))
    edge_clip_fraction = float((clipped & edge_band).sum() / max(1, edge_band.sum()))
    metrics.update(clip_fraction=round(clip_fraction, 5), edge_clip_fraction=round(edge_clip_fraction, 5))

    # Width normal to the local axis: the global rotation only aligns the mean
    # axis, and row-wise width grows by 1/cos(tilt) where the specimen bends.
    widths = (right["x"] - left["x"]) / np.sqrt(1 + tilt ** 2)

    valid_widths = widths[valid]
    metrics.update(
        width_px_median=round(float(np.median(valid_widths)), 2),
        width_px_p5=round(float(np.percentile(valid_widths, 5)), 2),
        width_px_p95=round(float(np.percentile(valid_widths, 95)), 2),
    )
    if edge_clip_fraction > params.clip_fraction_max:
        return _rejected(["EXPOSURE_CLIPPED"], metrics, roi, left_xy, right_xy)

    residual = np.where(valid, widths - _robust_width_reference(np.where(valid, widths, np.nan), limit), np.nan)
    # Outward-positive residual of each edge, for side attribution and roughness.
    left_out = np.where(valid, -(left["x"] - left_trend), np.nan)
    right_out = np.where(valid, right["x"] - right_trend, np.nan)
    metrics.update(
        width_taper_px_per_1000px=round(float(np.polyfit(rows[valid], valid_widths, 1)[0] * 1000), 3),
        width_residual_rms_px=round(float(1.4826 * np.nanmedian(np.abs(residual))), 3),
        edge_residual_rms_px={
            "left": round(float(1.4826 * np.nanmedian(np.abs(left_out[valid]))), 3),
            "right": round(float(1.4826 * np.nanmedian(np.abs(right_out[valid]))), 3),
        },
    )

    candidates: list[dict[str, Any]] = []
    with _quiet_nan():
        local_tests = (("width_bulge_candidate", residual > limit, residual, limit),
                       ("width_neck_candidate", residual < -limit, -residual, limit))
    for kind, flags, magnitude, threshold in local_tests:
        flags = _bridge(flags & valid, valid, params.min_feature_px)
        candidates.extend(_collect(kind, flags, magnitude, threshold, rows, left, right,
                                   left_out, right_out, frame, params))
    if params.good_width_range_px is not None:
        low, high = params.good_width_range_px
        outside = _bridge(valid & ((widths < low) | (widths > high)), valid, params.min_feature_px)
        excess = np.where(widths > high, widths - high, low - widths)
        candidates.extend(_collect("width_out_of_range_candidate", outside, excess, limit, rows, left, right,
                                   left_out, right_out, frame, params))
    # A stretch whose edges could not be measured is reported rather than
    # skipped: irregular or locally blurred edges often sit exactly at a defect,
    # and the coverage threshold alone would let it pass as "no candidates".
    # It is kept apart from the candidates: it marks unassessed material, and on
    # the live preview a slightly unsteady focus produced one in a new place on
    # many frames, which read as defects in the candidate records.
    # Only sections cut off by the frame or rotation border are exempt.
    unresolved = ~valid & (left["reason"] != "WINDOW_OUT_OF_FRAME") & (right["reason"] != "WINDOW_OUT_OF_FRAME")
    unmeasured = _collect_unresolved(unresolved, rows, left_x, right_x, left, right, reasons_by_row(),
                                     float(np.median(valid_widths)), window, frame, params)
    metrics["unmeasured_stretches"] = len(unmeasured)
    context = GeometryContext(rotated, valid_px, rows, left["x"], right["x"], valid, local_spread, frame)
    return GeometryOutcome(STATUS_VALID, [], metrics, candidates, left_xy, right_xy, roi, unmeasured, context)


def _collect(kind: str, flags: np.ndarray, magnitude: np.ndarray, threshold: float, rows: np.ndarray,
             left: dict[str, np.ndarray], right: dict[str, np.ndarray], left_out: np.ndarray,
             right_out: np.ndarray, frame: _Frame, params: GeometryParams) -> list[dict[str, Any]]:
    found = []
    pad = params.min_feature_px
    for start, stop in _runs(flags):
        if stop - start < params.min_run_px:
            continue
        span = slice(start, stop)
        peak = float(np.nanmax(magnitude[span]))
        ratio = peak / threshold
        x0 = float(np.nanmin(left["x"][span])) - pad
        x1 = float(np.nanmax(right["x"][span])) + pad
        bbox = _bbox(frame, x0, x1, rows[start], rows[stop - 1])
        left_share = float(np.nansum(np.abs(left_out[span])))
        right_share = float(np.nansum(np.abs(right_out[span])))
        side = "left" if left_share > 2 * right_share else "right" if right_share > 2 * left_share else "both"
        found.append({
            "defect_type": kind,
            "axial_range_px": [int(rows[start]), int(rows[stop - 1])],
            "run_length_px": int(stop - start),
            "peak_px": round(peak, 2),
            "limit_px": round(float(threshold), 2),
            # Pixel area between the measured edge and its slow trend over the run.
            "support_area_px": round(float(np.nansum(magnitude[span])), 1),
            "side": side,
            "score": round(ratio / (1 + ratio), 3),
            "bbox_px": bbox,
        })
    return found


def _bbox(frame: _Frame, x0: float, x1: float, r0: float, r1: float) -> list[int]:
    corners = frame.to_image(np.array([[x0, r0], [x1, r0], [x0, r1], [x1, r1]]))
    bx0, by0 = np.floor(corners.min(axis=0)).astype(int)
    bx1, by1 = np.ceil(corners.max(axis=0)).astype(int)
    return [int(bx0), int(by0), int(bx1 - bx0), int(by1 - by0)]


def _collect_unresolved(flags: np.ndarray, rows: np.ndarray, coarse_left: np.ndarray, coarse_right: np.ndarray,
                        left: dict[str, np.ndarray], right: dict[str, np.ndarray], reasons: np.ndarray,
                        typical_width: float, window: int, frame: _Frame,
                        params: GeometryParams) -> list[dict[str, Any]]:
    found = []
    for start, stop in _runs(flags):
        length = stop - start
        if length < params.min_run_px:
            continue
        span = slice(start, stop)
        left_bad = bool((~left["valid"][span]).any())
        right_bad = bool((~right["valid"][span]).any())
        ratio = length / params.min_run_px
        found.append({
            "kind": "unmeasured_stretch",
            "axial_range_px": [int(rows[start]), int(rows[stop - 1])],
            "run_length_px": int(length),
            "peak_px": None,
            "limit_px": float(params.min_run_px),
            # The unmeasured specimen area, not a defect area.
            "support_area_px": round(length * typical_width, 1),
            "side": "both" if left_bad == right_bad else "left" if left_bad else "right",
            "reason": Counter(reasons[span]).most_common(1)[0][0],
            "score": round(ratio / (1 + ratio), 3),
            "bbox_px": _bbox(frame, float(coarse_left[span].min()) - window,
                             float(coarse_right[span].max()) + window, rows[start], rows[stop - 1]),
        })
    return found
