"""Combine the current views of one sample into a coverage-aware summary."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .geometry import STATUS_REJECTED, STATUS_VALID


ANGLES = (0, 60, 120, 180, 240, 300)


def _surface_view(angle: int, analysis: dict[str, Any]) -> dict[str, Any]:
    surface = analysis["surface"]
    comparison = surface.get("comparison", {})
    return {
        "angle_deg": angle, "status": surface["status"], "reason_codes": surface["reason_codes"],
        "quality_label": comparison.get("quality_label"), "ratio": comparison.get("ratio"),
        "reference_id": comparison.get("reference_id"),
        "candidate_count": sum(1 for c in analysis["candidates"] if c.get("branch") == "surface"),
    }


def summarize_sample(current_views: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarise phase-1 geometry coverage for the current (non-superseded) views.

    Each view is a capture mapping with ``angle_deg``, ``lighting_mode`` and an
    optional ``analysis`` produced by ``ViewInspectionResult.to_dict``. A sample
    is only reported as free of candidates when every required bright-field
    view was measured; a missing or rejected view leaves the coverage open.
    """
    bright = {view["angle_deg"]: view for view in current_views
              if view["lighting_mode"] == "bright_field"}
    valid, rejected, unassessed, candidate_views, partly_measured, surface_views = [], [], [], [], [], []
    versions = set()
    for angle in ANGLES:
        view = bright.get(angle)
        analysis = None if view is None else view.get("analysis")
        if analysis is None:
            if view is not None:
                unassessed.append(angle)
            continue
        versions.add(analysis["algorithm_version"])
        if analysis["geometry_status"] == STATUS_VALID:
            valid.append(angle)
            if analysis.get("unmeasured_stretches"):
                partly_measured.append(angle)
            # Surface candidates are summarised separately; older analyses have no branch.
            geometry = [c for c in analysis["candidates"] if c.get("branch", "geometry") == "geometry"]
            if geometry:
                candidate_views.append({"angle_deg": angle, "candidate_count": len(geometry)})
            if analysis.get("surface"):
                surface_views.append(_surface_view(angle, analysis))
        elif analysis["geometry_status"] == STATUS_REJECTED:
            rejected.append({"angle_deg": angle, "reason_codes": analysis["reason_codes"]})
    missing = [angle for angle in ANGLES if angle not in bright]
    # A valid view with unmeasured stretches still leaves material unassessed.
    complete = len(valid) == len(ANGLES) and not partly_measured
    if candidate_views:
        conclusion = "candidates_present"
    elif complete:
        conclusion = "no_geometry_candidates_in_assessed_scope"
    else:
        conclusion = "geometry_coverage_incomplete"
    return {
        "scope": "bright_field_geometry",
        "surface_status": "assessed" if any(v["status"] == "valid" for v in surface_views) else "not_assessed",
        "surface_views": surface_views,
        "required_bright_field_views": len(ANGLES),
        "geometry_valid_angles": valid,
        "geometry_rejected": rejected,
        "missing_bright_field_angles": missing,
        "unassessed_bright_field_angles": unassessed,
        "partly_measured_angles": partly_measured,
        "candidate_views": candidate_views,
        "candidate_count": sum(item["candidate_count"] for item in candidate_views),
        "coverage_complete": complete,
        "conclusion": conclusion,
        "algorithm_versions": sorted(versions),
    }
