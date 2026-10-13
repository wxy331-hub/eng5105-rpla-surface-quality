"""Synthetic checks of the surface branch (phase 2a).

They show that the operators respond as designed on rendered textures, spots
and lines. They do not show that real rPLA surface defects are recognised.
"""

import dataclasses
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

from src.inspection.geometry import GeometryParams, analyse_geometry
from src.inspection.processor import StaticRplaProcessor, _surface_line
from src.inspection.summary import summarize_sample
from src.inspection.surface import (
    SURFACE_ALGORITHM_VERSION,
    SurfaceParams,
    SurfaceReference,
    analyse_surface,
)
from src.week3.models import CameraState, FramePacket

H, W = 1080, 1920
S = 20.0
GEOMETRY = GeometryParams(min_feature_px=S, min_run_px=40)
SURFACE = SurfaceParams(min_feature_px=S)
ORANGE, GREEN = (80, 150, 225), (88, 152, 64)


def render_surface(*, streak_amp=0.0, streak_period=60.0, spots=(), lines=(), shading=0.0, brightness=1.0,
                   noise=2.0, blur=1.2, saturate=None, seed=1, width=320.0, pattern=None):
    """Vertical specimen; spots are (x, y, diameter, amplitude), lines (x0, y0, x1, y1, thickness, amplitude)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    across = xx - (W - 1) / 2
    cover = np.clip(0.5 - (np.abs(across) - width / 2), 0, 1)
    factor = np.ones((H, W))
    if shading:
        factor *= 1 + shading * np.clip(np.abs(across) / (width / 2), 0, 1) ** 4
    if streak_amp:
        factor *= 1 + streak_amp * np.sin(2 * np.pi * across / streak_period)
    if pattern is not None:
        factor *= 1 + pattern(across, yy)
    for x, y, diameter, amplitude in spots:
        factor *= 1 + amplitude * np.exp(-((across - x) ** 2 + (yy - y) ** 2) / (2 * (diameter / 2.5) ** 2))
    for x0, y0, x1, y1, thickness, amplitude in lines:
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((across - x0) * dx + (yy - y0) * dy) / (dx * dx + dy * dy), 0, 1)
        distance = np.hypot(across - (x0 + t * dx), yy - (y0 + t * dy))
        factor *= 1 + amplitude * np.exp(-distance ** 2 / (2 * (thickness / 2) ** 2))
    specimen = np.array(GREEN, float)[None, None, :] * factor[..., None] * brightness
    image = np.array(ORANGE, float)[None, None, :] * (1 - cover[..., None]) + specimen * cover[..., None]
    if saturate is not None:
        x, y, radius = saturate
        image[(across - x) ** 2 + (yy - y) ** 2 <= radius ** 2] = 255
    if blur:
        image = cv2.GaussianBlur(image, (0, 0), blur)
    image += np.random.default_rng(seed).normal(0, noise, image.shape)
    return np.clip(np.round(image), 0, 255).astype(np.uint8)


def surface_of(image, reference=None, lighting="bright_field", params=SURFACE, angle=0):
    geometry = analyse_geometry(image, GEOMETRY)
    return analyse_surface(geometry.context, geometry.status, geometry.metrics, params, reference, lighting, angle)


def reference_from(image, reference_id="REF-TEST"):
    outcome = surface_of(image)
    assert outcome.status == "valid", outcome.reason_codes
    geometry = analyse_geometry(image, GEOMETRY)
    m = outcome.metrics
    return SurfaceReference(reference_id=reference_id, min_feature_px=S, texture_mad=m["texture_mad"],
                            longitudinal_energy=m["longitudinal_energy"], brightness_median=m["brightness_median"],
                            edge_spread_px=m["edge_spread_px"], width_px=geometry.metrics["width_px_median"],
                            fingerprint="test", source={"angle_deg": 0})


def kinds(outcome):
    return [c["defect_type"] for c in outcome.candidates]


def packet(image):
    return FramePacket("TEST", 1, "2026-10-08T00:00:00Z", "2026-10-08T00:00:00Z", CameraState.HEALTHY, image)


def test_plain_shaded_specimen_has_low_texture_and_no_local_candidates():
    outcome = surface_of(render_surface(shading=0.25))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["texture_mad"] < 0.02
    assert kinds(outcome) == []
    assert outcome.comparison["status"] == "no_reference"
    assert outcome.coverage["area_fraction"] > 0.95


def test_metrics_rise_with_streak_amplitude_and_are_not_self_normalised():
    values = [surface_of(render_surface(streak_amp=a)).metrics for a in (0.02, 0.06, 0.12)]
    assert values[0]["texture_mad"] < values[1]["texture_mad"] < values[2]["texture_mad"]
    assert values[0]["longitudinal_energy"] < values[1]["longitudinal_energy"] < values[2]["longitudinal_energy"]
    assert values[2]["texture_mad"] > 3 * values[0]["texture_mad"]


def test_axial_streaks_are_texture_not_scratches():
    outcome = surface_of(render_surface(streak_amp=0.15))
    assert "surface_scratch_candidate" not in kinds(outcome)
    assert outcome.metrics["longitudinal_energy"] > 0.02


@pytest.mark.parametrize("amplitude, kind", [(0.5, "surface_bright_spot_candidate"),
                                             (-0.2, "surface_dark_spot_candidate"),
                                             (-0.5, "surface_contamination_candidate")])
def test_compact_spots_are_local_candidates_at_their_position(amplitude, kind):
    outcome = surface_of(render_surface(spots=[(40, 500, 2 * S, amplitude)]))
    assert kinds(outcome) == [kind]
    x, y, w, h = outcome.candidates[0]["bbox_px"]
    assert x <= 960 + 40 <= x + w and y <= 500 <= y + h
    assert 0.5 < outcome.candidates[0]["score"] < 1


def test_spots_smaller_than_the_feature_scale_are_not_claimed():
    outcome = surface_of(render_surface(spots=[(40, 500, 0.2 * S, 0.2)]))
    assert kinds(outcome) == []


def test_short_near_axial_dark_line_is_a_scratch_candidate():
    outcome = surface_of(render_surface(lines=[(-20, 400, 20, 600, 6, -0.5)]))
    assert kinds(outcome) == ["surface_scratch_candidate"]


@pytest.mark.parametrize("line, reason", [((-100, 400, 100, 600, 6, -0.5), "OFF_AXIS_DARK_LINE"),
                                          ((-120, 500, 120, 500, 6, -0.5), "TRANSVERSE_DARK_LINE")])
def test_dark_line_across_the_filament_is_a_texture_direction_anomaly(line, reason):
    # Demo rule (2026-10-12): PLA texture runs along the filament, so a dark line
    # across it suggests a crack.
    outcome = surface_of(render_surface(lines=[line]))
    assert kinds(outcome) == ["surface_texture_direction_candidate"]
    assert outcome.candidates[0]["reason_codes"][0] == reason


def test_local_candidates_are_capped_but_fully_counted():
    spots = [(-105 + 70 * (i % 4), 150 + 110 * (i // 4), 1.5 * S, 0.5) for i in range(20)]
    outcome = surface_of(render_surface(spots=spots))
    total = sum(outcome.metrics["candidate_counts"].values())
    assert total > 12
    assert len(outcome.candidates) == 12
    assert outcome.metrics["local_candidates_not_recorded"] == total - 12
    assert [c["score"] for c in outcome.candidates] == sorted((c["score"] for c in outcome.candidates), reverse=True)


def test_saturated_highlight_is_excluded_not_reported():
    outcome = surface_of(render_surface(saturate=(0, 500, 12)))
    assert outcome.status == "valid"
    assert outcome.coverage["excluded_saturation_px"] > 0
    assert "surface_bright_spot_candidate" not in kinds(outcome)


def test_reference_grades_texture_and_adds_one_deviation_candidate():
    reference = reference_from(render_surface(streak_amp=0.03, seed=2))
    same = surface_of(render_surface(streak_amp=0.03, seed=3), reference)
    assert same.comparison["quality_label"] == "near_reference"
    rough = surface_of(render_surface(streak_amp=0.15, seed=4), reference)
    assert rough.comparison["status"] == "compared"
    assert rough.comparison["ratio"] >= 2
    assert rough.comparison["quality_label"] == "strongly_deviates"
    assert kinds(rough).count("surface_texture_deviation_candidate") == 1
    assert "local mean" in rough.comparison["local_threshold_rule"]


def test_changed_lighting_is_a_reference_mismatch_not_a_grade():
    reference = reference_from(render_surface(streak_amp=0.03, seed=2))
    darker = surface_of(render_surface(streak_amp=0.15, brightness=0.6, seed=4), reference)
    assert darker.comparison["status"] == "reference_mismatch"
    assert "BRIGHTNESS_DIFFERS" in darker.comparison["mismatches"]
    assert darker.comparison["quality_label"] == "not_graded"
    assert "surface_texture_deviation_candidate" not in kinds(darker)


@pytest.mark.parametrize("lighting, reason", [(None, "SURFACE_LIGHTING_NOT_DECLARED"),
                                              ("dark_field", "DARK_FIELD_SURFACE_NOT_IN_SCOPE")])
def test_surface_needs_declared_bright_field(lighting, reason):
    outcome = surface_of(render_surface(), lighting=lighting)
    assert outcome.status == "not_assessed" and outcome.reason_codes == [reason]


def test_defocused_specimen_is_not_judged_on_its_surface():
    outcome = surface_of(render_surface(blur=12.0))
    assert outcome.status == "rejected"
    assert outcome.reason_codes == ["GEOMETRY_UNUSABLE"]


def test_reference_file_is_validated_and_fingerprinted(tmp_path):
    data = {"schema_version": 1, "reference_id": "REF-A", "algorithm_version": SURFACE_ALGORITHM_VERSION,
            "min_feature_px": S, "source": {"angle_deg": 0},
            "metrics": {"texture_mad": 0.03, "longitudinal_energy": 0.02,
                        "brightness_median": 0.4, "edge_spread_px": 4.5, "width_px": 320.0}}
    path = tmp_path / "ref.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    first = SurfaceReference.load(path)
    assert first.reference_id == "REF-A" and len(first.fingerprint) == 64
    data["metrics"]["texture_mad"] = 0.031
    path.write_text(json.dumps(data), encoding="utf-8")
    assert SurfaceReference.load(path).fingerprint != first.fingerprint
    # Codex review round 2: a reference without an angle was compatible with every view.
    for broken in ({"schema_version": 9}, {"algorithm_version": "other"},
                   {"metrics": {**data["metrics"], "texture_mad": 0}},
                   {"source": {}}, {"source": {"angle_deg": None}}, {"source": {"angle_deg": 45}}):
        path.write_text(json.dumps({**data, **broken}), encoding="utf-8")
        with pytest.raises(ValueError):
            SurfaceReference.load(path)


def test_processor_records_surface_candidates_in_a_schema_2_result():
    image = render_surface(spots=[(40, 500, 2 * S, 0.5)])
    processor = StaticRplaProcessor(GEOMETRY, data_mode="TEST", surface=SURFACE)
    assert processor.algorithm_version == SURFACE_ALGORITHM_VERSION
    result = processor.inspect(packet(image), "BATCH", lighting_mode="bright_field")
    assert result.surface_status == "valid"
    assert [r.defect_type for r in result.records] == ["surface_bright_spot_candidate"]
    payload = result.to_dict()
    json.dumps(payload, allow_nan=False)
    assert payload["schema_version"] == 2 and payload["surface"]["evidence_scope"] == "BENCH_DEMO_STARTING_POINT"
    assert payload["candidates"][0]["branch"] == "surface"
    assert result.annotated.shape == image.shape


def test_summary_keeps_geometry_conclusion_free_of_surface_candidates():
    views = []
    for angle in (0, 60, 120, 180, 240, 300):
        views.append({"angle_deg": angle, "lighting_mode": "bright_field", "analysis": {
            "algorithm_version": SURFACE_ALGORITHM_VERSION, "geometry_status": "valid", "reason_codes": [],
            "candidates": [{"branch": "surface", "defect_type": "surface_dark_spot_candidate"}],
            "surface": {"status": "valid", "reason_codes": [], "comparison": {"quality_label": "not_graded"}}}})
    summary = summarize_sample(views)
    assert summary["conclusion"] == "no_geometry_candidates_in_assessed_scope"
    assert summary["surface_status"] == "assessed"
    assert [v["candidate_count"] for v in summary["surface_views"]] == [1] * 6


def test_plan_a_profile_enables_the_surface_branch_on_the_preview(monkeypatch):
    from src.camera_config import load_service_config
    from src.inspection.factory import create_processor
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    for name in ("RPLA_RESOLUTION", "RPLA_CAMERA_DEVICE", "RPLA_CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)
    processor = create_processor(load_service_config(), baseline_version="x", data_mode="TEST")
    assert processor.surface is not None and processor.preview_lighting == "bright_field"
    assert processor.surface.demo_longitudinal_thresholds == (0.0025, 0.0099)


# --- Codex review of phase 2a (2026-10-08) -----------------------------------

def test_missing_streak_ratio_cannot_support_near_reference():
    # P1: the reference streak metric is below the floor, so its ratio is
    # dropped; the remaining texture ratio alone must not say "close".
    reference = dataclasses.replace(reference_from(render_surface(streak_amp=0.03, seed=2)),
                                    longitudinal_energy=0.001)
    outcome = surface_of(render_surface(streak_amp=0.03, seed=3), reference)
    assert outcome.comparison["status"] == "compared"
    assert outcome.comparison["complete"] is False
    assert outcome.comparison["quality_label"] == "reference_metric_too_low"


def test_reference_is_only_used_at_its_own_angle():
    # P1: a 0-degree reference was grading a 60-degree view.
    reference = dataclasses.replace(reference_from(render_surface(streak_amp=0.03, seed=2)),
                                    source={"angle_deg": 0})
    image = render_surface(streak_amp=0.03, seed=3)
    geometry = analyse_geometry(image, GEOMETRY)
    for angle, expected in ((0, "compared"), (60, "reference_mismatch"), (None, "reference_mismatch")):
        outcome = analyse_surface(geometry.context, geometry.status, geometry.metrics, SURFACE, reference,
                                  "bright_field", angle)
        assert outcome.comparison["status"] == expected, angle
    assert outcome.comparison["mismatches"] == ["ANGLE_NOT_DECLARED"]


def test_periodic_texture_raises_its_own_local_threshold():
    # P2: a regular pattern was split into dozens of spot candidates.
    outcome = surface_of(render_surface(
        pattern=lambda x, y: 0.1 * np.sin(2 * np.pi * x / 60) * np.sin(2 * np.pi * y / 60), noise=0))
    assert outcome.status == "valid"
    assert sum(outcome.metrics["candidate_counts"].values()) <= 2


def test_strong_texture_reference_does_not_hide_a_new_spot():
    # Codex review round 2: 5x the reference texture (0.40) hid a 50 % spot and
    # the result still read "close to the reference".
    # Codex's exact input: s = d = 60, 520 px specimen, 180 px texture period.
    geometry_params = GeometryParams(min_feature_px=60, min_run_px=60)
    params = SurfaceParams(min_feature_px=60)
    pattern = lambda x, y: 0.2 * np.sin(2 * np.pi * x / 180) * np.sin(2 * np.pi * y / 180)

    def analyse(image, reference=None):
        geometry = analyse_geometry(image, geometry_params)
        return geometry, analyse_surface(geometry.context, geometry.status, geometry.metrics, params, reference,
                                         "bright_field", 0)

    geometry, plain = analyse(render_surface(width=520, noise=0, pattern=pattern))
    m = plain.metrics
    reference = SurfaceReference("REF-STRONG", 60, m["texture_mad"], m["longitudinal_energy"], m["brightness_median"],
                                 m["edge_spread_px"], geometry.metrics["width_px_median"], "test", {"angle_deg": 0})
    _, outcome = analyse(render_surface(width=520, noise=0, pattern=pattern, spots=[(15, 500, 60, 0.5)]), reference)
    assert kinds(outcome) == ["surface_bright_spot_candidate"]
    assert outcome.comparison["quality_label"] == "near_reference_with_local_candidates"


def test_isolated_spot_on_streaks_is_still_found():
    # P2: the spot merged with streak pixels above a global threshold and vanished.
    outcome = surface_of(render_surface(streak_amp=0.06, noise=0, spots=[(15, 500, 2 * S, 0.5)]))
    assert "surface_bright_spot_candidate" in kinds(outcome)


def test_long_bright_band_suspends_the_grade():
    # P2: a non-saturated bright band lifted the streak metric to "strongly deviates".
    reference = reference_from(render_surface(streak_amp=0.03, noise=0))
    outcome = surface_of(render_surface(streak_amp=0.03, noise=0, lines=[(0, 200, 0, 850, 20, 0.35)]), reference)
    assert outcome.reason_codes == ["GLARE_OR_BRIGHT_STRUCTURE_AMBIGUOUS"]
    assert outcome.comparison["quality_label"] == "not_graded_bright_structure"
    assert "surface_texture_deviation_candidate" not in kinds(outcome)
    assert outcome.metrics["bright_structures"]


def test_non_finite_reference_scale_is_refused(tmp_path):
    # P2: "min_feature_px": "NaN" loaded and then passed the scale check.
    data = {"schema_version": 1, "reference_id": "REF-A", "algorithm_version": SURFACE_ALGORITHM_VERSION,
            "min_feature_px": "NaN", "metrics": {"texture_mad": 0.03, "longitudinal_energy": 0.02,
                                                "brightness_median": 0.4, "edge_spread_px": 4.5, "width_px": 320.0}}
    path = tmp_path / "ref.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        SurfaceReference.load(path)


def test_reference_creator_refuses_metrics_the_loader_would_refuse(tmp_path, monkeypatch):
    # P2: a texture-free image produced a reference the loader rejected, and
    # two such images divided by zero in the repeatability check.
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    import create_surface_reference as creator
    image = tmp_path / "flat.png"
    cv2.imwrite(str(image), cv2.resize(render_surface(noise=0, width=320), (3840, 2160)))
    monkeypatch.setattr(creator, "REFERENCE_DIR", tmp_path / "refs")
    for images in ([image], [image, image]):
        monkeypatch.setattr(sys, "argv", ["x", "--reference-id", "REF-FLAT", *map(str, images)])
        with pytest.raises(SystemExit, match="not usable as a reference"):
            creator.main()
    # Codex review round 2: the creator accepted an angle the loader refuses.
    monkeypatch.setattr(sys, "argv", ["x", "--reference-id", "REF-45", "--angle", "45", str(image)])
    with pytest.raises(SystemExit):
        creator.main()
    assert not (tmp_path / "refs").exists()


def test_published_result_is_withdrawn_when_processing_stops_keeping_up(monkeypatch, tmp_path):
    # P2: frames kept arriving but none finished in time, and the last
    # published analysis stayed current indefinitely.
    from dataclasses import replace
    from unittest.mock import patch
    import time
    from src.camera_config import load_service_config
    from src.live_service import InspectionRuntime
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    for name in ("RPLA_RESOLUTION", "RPLA_CAMERA_DEVICE", "RPLA_CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)
    config = replace(load_service_config(), expected_width_px=W, expected_height_px=H, roi_px=(0, 0, W, H),
                     recovery_frames=1, stale_after_s=1.0, disconnect_after_s=60.0,
                     database_path=tmp_path / "live.db",
                     static_options={"filament_axis": "vertical", "min_feature_px": S, "min_run_px": 40},
                     surface_options={"min_feature_px": S, "preview_lighting": "bright_field"})
    runtime = InspectionRuntime(config, source_factory=lambda: None)
    runtime._accept_packet(FramePacket(config.source_name, 1, "t", "t", CameraState.HEALTHY, render_surface()))
    assert runtime.snapshot_payload()["summary"]["view_inspection"]["surface"]["status"] == "valid"
    later = time.perf_counter() + 2.5
    with patch("src.live_service.time.perf_counter", return_value=later):
        # A newer frame has arrived (camera healthy) but its processing never published.
        runtime._monitor.frame_received(later)
        runtime._last_frame_monotonic = later
        summary = runtime.snapshot_payload()["summary"]
        jpeg = runtime.latest_jpeg()[1]
    assert summary["camera_state"] == "HEALTHY"
    assert summary["view_inspection"] is None
    assert jpeg is None


# --- 2026-10-12 bench: sharp specimen rejected on every frame ----------------

def test_glare_streak_inside_an_edge_does_not_break_the_edge(monkeypatch):
    # A whitish specular streak about 38 px inside the left edge on the lower
    # half: the inside reference plateau (placed by d) sat on it, and the edge
    # could not be resolved there, so every frame was rejected.
    image = render_surface(noise=0, blur=0).astype(float)
    yy, xx = np.mgrid[:H, :W]
    band = np.exp(-((xx - (W - 1) / 2 - (-160 + 38)) ** 2) / (2 * 4.8 ** 2)) * (yy > 540)
    image = image * (1 - band[..., None]) + np.array((210, 218, 222), float) * band[..., None]
    image = cv2.GaussianBlur(image, (0, 0), 1.2) + np.random.default_rng(2).normal(0, 2, image.shape)
    image = np.clip(np.round(image), 0, 255).astype(np.uint8)
    geometry = analyse_geometry(image, GEOMETRY)
    assert geometry.status == "valid", geometry.reason_codes
    assert geometry.metrics["width_px_median"] == pytest.approx(320, abs=2)
    assert geometry.metrics.get("edge_search_narrowed")
    # Without the short-window pass the same image is rejected.
    import src.inspection.geometry as geometry_module
    monkeypatch.setattr(geometry_module, "_prefer", lambda first, fallback: fallback)
    assert analyse_geometry(image, GEOMETRY).status == "rejected"


def test_saturated_interior_glare_does_not_reject_the_geometry():
    # 2.5 % of the specimen saturated in the interior, none at the edges: the
    # width is unaffected, and the surface excludes only the clipped pixels.
    image = render_surface(noise=2)
    yy, xx = np.mgrid[:H, :W]
    for y in (300, 500, 700):
        image[(xx - (W - 1) / 2) ** 2 + (yy - y) ** 2 <= 30 ** 2] = 255
    geometry = analyse_geometry(image, GEOMETRY)
    assert geometry.status == "valid", geometry.reason_codes
    assert geometry.metrics["clip_fraction"] > 0.01
    assert geometry.metrics["edge_clip_fraction"] < 0.01
    outcome = surface_of(image)
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.coverage["area_fraction"] > 0.9
    assert "surface_bright_spot_candidate" not in kinds(outcome)



def test_surface_reports_missing_focus_evidence_apart_from_a_small_region():
    # With the geometry gate relaxed for diagnosis, a specimen whose rows all fail
    # the surface focus filter was reported as SURFACE_ROI_TOO_SMALL although its
    # region was large enough (2026-10-12, dark grey specimen).
    relaxed = dataclasses.replace(GEOMETRY, max_edge_spread_px=200.0)
    geometry = analyse_geometry(render_surface(blur=12.0), relaxed)
    assert geometry.status == "valid", geometry.reason_codes
    outcome = analyse_surface(geometry.context, geometry.status, geometry.metrics, SURFACE, None, "bright_field", 0)
    assert outcome.reason_codes == ["SURFACE_FOCUS_UNVERIFIABLE"]
    # A sharp specimen too narrow for the analysis region keeps the area reason.
    assert surface_of(render_surface(width=100.0)).reason_codes == ["SURFACE_ROI_TOO_SMALL"]


def test_same_shade_bulge_is_found_with_the_short_window_active():
    # A bulge of the specimen's own material is part of the coarse mask, so the
    # short window is centred on its outer edge and the bulge is a candidate.
    image = np.full((1000, 1200, 3), 220, np.uint8)
    image[:, 350:850] = 60
    image[400:600, 290:350] = 60
    image = cv2.GaussianBlur(image, (0, 0), 1.2)
    outcome = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=60, filament_axis="auto"))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics.get("edge_search_narrowed")
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"]


def test_spot_touching_a_tiny_clipped_point_is_still_a_candidate():
    # Codex review 2026-10-12: the whole spot was dropped as a glare rim because
    # it touched a 2 px saturated point, and the view read "near reference".
    image = render_surface(noise=1, width=520, streak_amp=0.05, streak_period=180, spots=[(0, 500, 120, 0.5)])
    cv2.circle(image, (1030, 500), 2, (255, 255, 255), -1)
    geometry = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=40))
    outcome = analyse_surface(geometry.context, geometry.status, geometry.metrics, SurfaceParams(min_feature_px=60),
                              None, "bright_field", 0)
    found = [c for c in outcome.candidates if c["defect_type"] == "surface_bright_spot_candidate"]
    assert len(found) == 1 and found[0]["reason_codes"] == ["NEXT_TO_SATURATION"]


def test_background_shadow_does_not_undo_the_short_window_on_glare():
    # Second review round: the background check used the first pass's contrast,
    # which interior glare had shrunk, so a 10 % background shadow refused the
    # short window and the glare rejection came back.
    yy, xx = np.mgrid[:1000, :1200]
    image = np.full((1000, 1200, 3), 220.0)
    image[:, 350:850] = 60.0
    image *= 1 - (0.1 * np.exp(-((xx - 350) ** 2) / (2 * 60 ** 2)) * (xx < 350))[..., None]
    glare = np.exp(-((xx - 455) ** 2) / (2 * 14 ** 2)) * (yy > 500)
    image = image * (1 - glare[..., None]) + 220 * glare[..., None]
    image = cv2.GaussianBlur(np.round(image).astype(np.uint8), (0, 0), 1.2)
    outcome = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=40))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["width_px_median"] == pytest.approx(500, abs=1)
    # Third round: glare about 20 px inside the edge, where it also touches the
    # short window's inside plateau.
    image = np.full((1000, 1200, 3), 220.0)
    image[:, 350:850] = 60.0
    image *= 1 - (0.1 * np.exp(-((xx - 350) ** 2) / (2 * 60 ** 2)) * (xx < 350))[..., None]
    glare = np.exp(-((xx - 370) ** 2) / (2 * 6 ** 2)) * (yy > 500)
    image = image * (1 - glare[..., None]) + 190 * glare[..., None]
    image = cv2.GaussianBlur(np.round(image).astype(np.uint8), (0, 0), 1.2)
    outcome = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=40))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["width_px_median"] == pytest.approx(500, abs=2)


def test_short_window_still_rescues_rotated_corner_rows():
    # Second review round: where the long window left the rotated frame, the
    # short window was no longer used and a sharp 15 deg strip was rejected.
    yy, xx = np.mgrid[:600, :900]
    image = np.full((600, 900, 3), 20, np.uint8)
    image[np.abs(xx - (450 + np.tan(np.deg2rad(15)) * (yy - 300))) < 160] = 220
    image = cv2.GaussianBlur(image, (0, 0), 1.2)
    outcome = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=40))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["width_px_median"] == pytest.approx(320 * math.cos(math.radians(15)), abs=1)
    # Third round: 25 deg with the background darkening along the image.
    yy, xx = np.mgrid[:600, :900]
    image = np.broadcast_to(np.linspace(220, 110, 600)[:, None, None], (600, 900, 3)).copy()
    image[np.abs(xx - (450 + np.tan(np.deg2rad(25)) * (yy - 300))) < 160] = 60
    image = cv2.GaussianBlur(np.round(image).astype(np.uint8), (0, 0), 1.2)
    outcome = analyse_geometry(image, GeometryParams(min_feature_px=60, min_run_px=40))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["width_px_median"] == pytest.approx(320 * math.cos(math.radians(25)), abs=1)


# --- Demo roughness grade (2026-10-12, uncalibrated) ---------------------------

def demo_params(low, high):
    return SurfaceParams(min_feature_px=S, demo_longitudinal_thresholds=[low, high])


@pytest.mark.parametrize("bounds", [[0.01], [0.01, 0.02, 0.03], [True, 0.02], ["0.01", 0.02],
                                    [float("nan"), 0.02], [0, 0.02], [0.02, 0.02], [0.03, 0.02]])
def test_demo_thresholds_are_validated(bounds):
    with pytest.raises(ValueError):
        SurfaceParams(min_feature_px=S, demo_longitudinal_thresholds=bounds)


def test_demo_grade_has_three_exclusive_levels():
    image = render_surface(streak_amp=0.03, noise=0)
    assert surface_of(image).comparison["quality_label"] == "not_graded"  # off by default
    streaks = surface_of(image).metrics["longitudinal_energy"]
    for low, high, label, count in ((2 * streaks, 4 * streaks, "demo_good", 0),
                                    (streaks, 4 * streaks, "demo_moderately_rough", 1),  # equal -> higher level
                                    (streaks / 4, streaks, "demo_clearly_rough", 1)):
        outcome = surface_of(image, params=demo_params(low, high))
        assert outcome.comparison["quality_label"] == label
        assert outcome.reason_codes == ["UNCALIBRATED_DEMO_THRESHOLD"]
        assert kinds(outcome).count("surface_demo_roughness_candidate") == count


def test_demo_grade_only_without_a_comparable_reference_at_zero_degrees():
    image = render_surface(streak_amp=0.03, noise=0)
    low = surface_of(image).metrics["longitudinal_energy"] / 2
    params = demo_params(low, 1.0)
    # A comparable reference keeps the reference grade.
    graded = surface_of(image, reference_from(image), params=params)
    assert graded.comparison["status"] == "compared"
    assert "surface_demo_roughness_candidate" not in kinds(graded)
    # The bounds were set on 0 deg views only.
    other = surface_of(image, params=params, angle=60)
    assert other.reason_codes == ["DEMO_ANGLE_NOT_SUPPORTED"]
    assert other.comparison["quality_label"] == "not_graded" and not kinds(other)
    # A long bright band (possible glare) suspends it, as it does the reference grade.
    glare = surface_of(render_surface(streak_amp=0.03, noise=0, lines=[(0, 200, 0, 850, 20, 0.35)]), params=params)
    assert glare.reason_codes == ["GLARE_OR_BRIGHT_STRUCTURE_AMBIGUOUS"]
    assert "surface_demo_roughness_candidate" not in kinds(glare)


def test_demo_grade_applies_when_the_reference_is_not_comparable():
    image = render_surface(streak_amp=0.03, noise=0)
    low = surface_of(image).metrics["longitudinal_energy"] / 2
    darker = reference_from(render_surface(streak_amp=0.03, noise=0, brightness=0.6))
    outcome = surface_of(image, darker, params=demo_params(low, 1.0))
    assert outcome.comparison["status"] == "reference_mismatch"
    assert outcome.comparison["quality_label"] == "demo_moderately_rough"
    # A tiny but valid lower bound must not overflow the score.
    tiny = surface_of(image, params=demo_params(5e-324, 1.0))
    assert [c["score"] for c in tiny.candidates if c["defect_type"] == "surface_demo_roughness_candidate"] == [1.0]


def test_demo_roughness_is_one_record_and_shown_on_the_banner():
    image = render_surface(streak_amp=0.03, noise=0)
    low = surface_of(image).metrics["longitudinal_energy"] / 2
    processor = StaticRplaProcessor(GEOMETRY, data_mode="TEST", surface=demo_params(low, 1.0))
    result = processor.inspect(packet(image), "B", lighting_mode="bright_field", angle_deg=0)
    assert [r.defect_type for r in result.records] == ["surface_demo_roughness_candidate"]
    assert "DEMO MODERATELY ROUGH (uncalibrated) | 0 local" in _surface_line(result)
    # Why a frame is not graded is on the banner too.
    glare = render_surface(streak_amp=0.03, noise=0, lines=[(0, 200, 0, 850, 20, 0.35)])
    suspended = processor.inspect(packet(glare), "B", lighting_mode="bright_field", angle_deg=0)
    assert "grade suspended" in _surface_line(suspended)
    other_angle = processor.inspect(packet(image), "B", lighting_mode="bright_field", angle_deg=60)
    assert "demo grade at 0 deg only" in _surface_line(other_angle)


# --- Contamination and texture direction (2026-10-12, uncalibrated demo rules) ---

@pytest.mark.parametrize("amplitude", [-1.0, -0.7])
@pytest.mark.parametrize("diameter", [2 * S, 4 * S])
def test_dark_mark_is_one_contamination_candidate(amplitude, diameter):
    # -1.0 clips the centre to black, which the texture analysis excludes.
    outcome = surface_of(render_surface(spots=[(0, 500, diameter, amplitude)]))
    assert outcome.status == "valid", outcome.reason_codes
    assert kinds(outcome) == ["surface_contamination_candidate"]
    x, y, w, h = outcome.candidates[0]["bbox_px"]
    assert x <= 960 <= x + w and y <= 500 <= y + h


def oblique_patch(angle_deg, period=3 * S, amplitude=0.15, rows=(300, 700)):
    t = math.radians(angle_deg)

    def pattern(across, yy):
        inside = (yy >= rows[0]) & (yy <= rows[1])
        # Texture running at angle_deg from the axis (0 = along the filament).
        return inside * amplitude * np.sin(2 * np.pi * (across * math.cos(t) - yy * math.sin(t)) / period)
    return pattern


def test_axial_texture_and_single_spots_have_no_direction_anomaly():
    for image in (render_surface(pattern=oblique_patch(0), noise=1),
                  render_surface(streak_amp=0.1, noise=1),
                  render_surface(spots=[(0, 500, 3 * S, 0.5)]),
                  render_surface(spots=[(0, 500, 3 * S, -0.7)])):
        assert "surface_texture_direction_candidate" not in kinds(surface_of(image))


# --- Codex review of the contamination and direction rules (2026-10-12) ---------

def test_large_dark_mark_is_claimed_whole():
    # The 2 s background was undefined in the middle of a 5.5 s mark, so only its
    # rim (about 40 %) was claimed.
    image = render_surface(noise=0)
    cv2.circle(image, (960, 500), 55, (15, 15, 15), -1)
    outcome = surface_of(image)
    found = [c for c in outcome.candidates if c["defect_type"] == "surface_contamination_candidate"]
    assert len(found) == 1
    assert found[0]["support_area_px"] > 0.9 * math.pi * 55 ** 2


@pytest.mark.parametrize("line", [(-100, 400, 100, 600, 20, 0.6), (-120, 500, 120, 500, 20, 0.6),
                                  (-100, 400, 100, 600, 40, 0.2), (-100, 500, 100, 500, 80, 0.6),
                                  (-100, 400, 100, 600, 100, 0.6), (-120, 450, 120, 550, 160, 0.6)])
def test_single_bright_band_is_not_a_texture_direction_anomaly(line):
    # Glare-like bright bands, including the wide ones on which the removed
    # region detector kept reporting the faint dark side lobes as texture.
    assert "surface_texture_direction_candidate" not in kinds(surface_of(render_surface(lines=[line], noise=0)))


def test_a_local_defect_does_not_raise_the_roughness_grade():
    # 2026-10-12 bench: one marker dot on the smooth white specimen lifted the RMS
    # streak metric about 30 times and turned "good" into "clearly rough".
    params = demo_params(0.0025, 0.0099)  # the plan_a demo bounds
    assert surface_of(render_surface(noise=1), params=params).comparison["quality_label"] == "demo_good"
    # Soft-edged (Gaussian) marks darken well beyond the part reported as contamination.
    for amplitude, diameter in ((-0.9, 4 * S), (-0.9, 2 * S), (-0.5, 4 * S)):
        marked = surface_of(render_surface(noise=1, spots=[(0, 500, diameter, amplitude)]), params=params)
        assert "surface_contamination_candidate" in kinds(marked)
        assert marked.comparison["quality_label"] == "demo_good", (amplitude, diameter, marked.metrics)
        assert marked.coverage["excluded_local_defect_px"] > 0


def test_mostly_defects_keeps_the_unexcluded_streak_metric():
    # Codex review 2026-10-12: with two large marks less than half of the surface
    # was left, the fallback kept the excluded streak map, whose NaN graded a
    # clearly striped specimen "good".
    params = SurfaceParams(min_feature_px=60, demo_longitudinal_thresholds=(0.0025, 0.0099))
    geometry_params = GeometryParams(min_feature_px=60, min_run_px=40)
    image = render_surface(streak_amp=0.04, streak_period=180, noise=1, width=520,
                           spots=[(0, 350, 120, -0.9), (0, 750, 120, -0.9)])
    geometry = analyse_geometry(image, geometry_params)
    outcome = analyse_surface(geometry.context, geometry.status, geometry.metrics, params, None, "bright_field", 0)
    assert math.isfinite(outcome.metrics["longitudinal_energy"])
    assert outcome.comparison["quality_label"] == "demo_clearly_rough"



def test_local_dilation_equals_whole_mask_dilation():
    # The defect exclusion dilates by 2 s; done on the whole 4K strip it took
    # about 7 s on a Raspberry Pi 4B (2026-10-13). The local version must be
    # pixel-identical, including regions on the image edge and overlapping growth.
    from src.inspection.surface import _dilate

    rng = np.random.default_rng(20261013)
    for trial in range(30):
        height, width = int(rng.integers(20, 300)), int(rng.integers(20, 300))
        mask = np.zeros((height, width), bool)
        for _ in range(int(rng.integers(0, 6))):
            y, x = int(rng.integers(0, height)), int(rng.integers(0, width))
            h, w = int(rng.integers(1, 40)), int(rng.integers(1, 40))
            mask[y:y + h, x:x + w] = True
        mask |= rng.random((height, width)) < rng.choice([0.0, 0.001, 0.02])
        radius = int(rng.choice([1, 2, 5, 17, 60, 120]))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        expected = cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)
        assert np.array_equal(_dilate(mask, radius), expected), (trial, radius)
    # Large masks with a few small regions take the local path.
    for shape, boxes, radius in (((2160, 747), [(1751, 448, 70, 84)], 120),
                                 ((900, 600), [(0, 0, 30, 20), (850, 580, 50, 20), (400, 300, 5, 5)], 60)):
        mask = np.zeros(shape, bool)
        for y, x, h, w in boxes:
            mask[y:y + h, x:x + w] = True
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        assert np.array_equal(_dilate(mask, radius), cv2.dilate(mask.astype(np.uint8), kernel).astype(bool))
