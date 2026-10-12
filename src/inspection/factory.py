"""Select the configured vision algorithm without changing the baseline's behaviour."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.week3 import BaselineVisionProcessor

from .geometry import GeometryParams
from .processor import StaticRplaProcessor
from .surface import SurfaceParams, SurfaceReference

PROJECT_ROOT = Path(__file__).resolve().parents[2]


BASELINE_ALGORITHM = "baseline_threshold"
STATIC_ALGORITHM = "static_rpla_geometry"
ALGORITHMS = (BASELINE_ALGORITHM, STATIC_ALGORITHM)


def static_params(config: Any) -> GeometryParams:
    """The configured ROI is the search ROI; everything else comes from the profile."""
    return GeometryParams.from_mapping({**config.static_options, "search_roi_px": tuple(config.roi_px)})


def surface_components(options: dict[str, Any]) -> tuple[SurfaceParams | None, SurfaceReference | None]:
    """Surface parameters and the loaded (immutable) reference; a relative path is under the project root."""
    if not options:
        return None, None
    params = SurfaceParams.from_mapping(options)
    if params.reference_path is None:
        return params, None
    path = Path(params.reference_path)
    return params, SurfaceReference.load(path if path.is_absolute() else PROJECT_ROOT / path)


def create_processor(config: Any, *, baseline_version: str, data_mode: str):
    if config.vision_algorithm == BASELINE_ALGORITHM:
        return BaselineVisionProcessor(
            threshold=config.threshold, min_area_px=config.min_area_px,
            algorithm_version=baseline_version, roi_px=config.roi_px,
            data_mode=data_mode, **config.vision_options,
        )
    if config.vision_algorithm == STATIC_ALGORITHM:
        surface, reference = surface_components(getattr(config, "surface_options", {}))
        return StaticRplaProcessor(static_params(config), data_mode=data_mode, surface=surface, reference=reference)
    raise ValueError(f"unknown vision algorithm: {config.vision_algorithm}")
