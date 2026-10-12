"""Synthetic checks of the static-specimen geometry branch.

These prove that the software measures and rejects as designed on rendered
images with known geometry. They do not show that real rPLA defects are
visible to the camera or detected by it.
"""

import json
import math

import cv2
import numpy as np
import pytest

from src.inspection.geometry import GeometryParams, analyse_geometry
from src.inspection.processor import ALGORITHM_VERSION, StaticRplaProcessor
from src.inspection.summary import summarize_sample
from src.week3.models import CameraState, FramePacket, QualityGrade

SHAPE = (1080, 1920)
ORANGE, GREEN = (80, 150, 225), (55, 95, 40)


def render(width=200.0, centre=0.0, angle_deg=0.0, *, shape=SHAPE, background=ORANGE, foreground=GREEN,
           blur=1.2, noise=3.0, seed=7, axial_limits=None, gradient=0.0, shading=0.0, shadow=0.0):
    """Anti-aliased specimen. ``width``/``centre`` are numbers or functions of the axial coordinate."""
    height, cols = shape
    yy, xx = np.mgrid[0:height, 0:cols].astype(np.float64)
    dx, dy = xx - (cols - 1) / 2, yy - (height - 1) / 2
    theta = math.radians(angle_deg)
    along = dx * math.sin(theta) + dy * math.cos(theta)
    across = dx * math.cos(theta) - dy * math.sin(theta)
    w = width(along) if callable(width) else width
    c = centre(along) if callable(centre) else centre
    coverage = np.clip(0.5 - (np.abs(across - c) - np.asarray(w) / 2), 0, 1)
    if axial_limits is not None:
        coverage *= (along >= axial_limits[0]) & (along <= axial_limits[1])
    bg = np.array(background, np.float64)[None, None, :] * (1 + gradient * (xx / cols - 0.5))[..., None]
    if shadow:
        # A soft shadow on the background beside the left edge, as in the 9/30 captures.
        distance = -(across - c) - np.asarray(w) / 2
        bg = bg * (1 - shadow * np.exp(-np.clip(distance, 0, None) / 150))[..., None]
    fg = np.array(foreground, np.float64)[None, None, :]
    if shading:
        # Cylinder shading: brighter towards the silhouette than at the centre.
        radial = np.clip(np.abs(across - c) / (np.asarray(w) / 2), 0, 1)
        fg = fg + shading * radial[..., None] ** 4
    image = bg * (1 - coverage[..., None]) + fg * coverage[..., None]
    if blur:
        image = cv2.GaussianBlur(image, (0, 0), blur)
    image += np.random.default_rng(seed).normal(0, noise, image.shape)
    return np.clip(np.round(image), 0, 255).astype(np.uint8)


def analyse(image, **overrides):
    return analyse_geometry(image, GeometryParams(**overrides))


def packet(image):
    return FramePacket("TEST_CAMERA", 3, "2026-10-07T00:00:00Z", "2026-10-07T00:00:00Z",
                       CameraState.HEALTHY, image)


@pytest.mark.parametrize("angle", [0.0, 15.0, 30.0, -20.0])
def test_straight_specimen_width_is_measured_normal_to_its_axis(angle):
    outcome = analyse(render(200.0, angle_deg=angle))
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["width_px_median"] == pytest.approx(200.0, abs=1.0)
    assert outcome.metrics["axis_tilt_deg"] == pytest.approx(angle, abs=0.5)
    assert outcome.metrics["edge_spread_px_median"] <= 6.0
    assert outcome.candidates == []


def test_cylinder_shading_and_background_shadow_do_not_widen_the_edge():
    image = render(450.0, foreground=(45, 70, 30), shading=25.0, shadow=0.2)
    outcome = analyse(image)
    assert outcome.status == "valid", (outcome.reason_codes, outcome.metrics)
    assert outcome.metrics["width_px_median"] == pytest.approx(450.0, abs=1.5)
    assert outcome.metrics["edge_spread_px_median"] <= 6.0
    assert outcome.candidates == []


def test_one_sided_bulge_is_a_candidate_on_that_side():
    bump = lambda v: np.where(np.abs(v) < 60, 20.0, 0.0)
    outcome = analyse(render(lambda v: 200 + bump(v), centre=lambda v: bump(v) / 2))
    assert outcome.status == "valid"
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"]
    found = outcome.candidates[0]
    assert found["side"] == "right"
    assert found["peak_px"] == pytest.approx(20, abs=2)
    assert 100 <= found["run_length_px"] <= 130
    x, y, w, h = found["bbox_px"]
    assert x < 960 + 110 < x + w and y < 540 < y + h


def test_symmetric_neck_is_a_candidate_on_both_sides():
    outcome = analyse(render(lambda v: np.where(np.abs(v) < 50, 180.0, 200.0)))
    assert [c["defect_type"] for c in outcome.candidates] == ["width_neck_candidate"]
    assert outcome.candidates[0]["side"] == "both"


def test_slow_taper_is_kept_as_a_trend_not_a_local_candidate():
    outcome = analyse(render(lambda v: 200 - v * (60 / 1080)))
    assert outcome.status == "valid"
    assert outcome.candidates == []
    assert outcome.metrics["width_taper_px_per_1000px"] == pytest.approx(-55.6, abs=3)


def test_bend_with_constant_width_is_not_reported_as_roughness():
    outcome = analyse(render(200.0, centre=lambda v: 15 * np.sin(2 * np.pi * v / 700)))
    assert outcome.status == "valid"
    assert outcome.candidates == []


def _arc(radius, thickness=200.0):
    y, x = np.mgrid[:SHAPE[0], :SHAPE[1]]
    distance = np.hypot(x - (959.5 - radius), y - 539.5)
    alpha = np.clip(0.5 - (np.abs(distance - radius) - thickness / 2), 0, 1)[..., None]
    image = np.rint(np.array(ORANGE) * (1 - alpha) + np.array(GREEN) * alpha).astype(np.uint8)
    return cv2.GaussianBlur(image, (0, 0), 1.2)


@pytest.mark.parametrize("radius", [950, 1000])
def test_strongly_bent_specimen_is_out_of_scope_not_a_bulge(radius):
    # Codex review 2026-10-07: a 200 px thick arc reaching ~33 deg local tilt
    # read as bulges, then (after a first fix) as locally out of focus.
    outcome = analyse(_arc(radius))
    assert outcome.reason_codes == ["CURVATURE_OUT_OF_SCOPE"]
    assert outcome.candidates == []


def test_gently_bent_specimen_is_measured_normal_to_its_axis():
    outcome = analyse(_arc(3000))
    assert outcome.status == "valid", outcome.reason_codes
    assert 5 < outcome.metrics["local_tilt_deg_max"] <= 15
    assert outcome.candidates == []
    assert outcome.metrics["width_px_p95"] == pytest.approx(200.0, abs=2.0)


@pytest.mark.parametrize("height, length", [(70, 80), (60, 44)])
def test_tall_one_sided_bulge_is_neither_missed_nor_flanked_by_false_necks(height, length):
    # Codex review 2026-10-07 (second round): centreline-based tilt shrank the
    # flanks of a one-sided bulge into false necks, or hid the bulge entirely.
    bump = lambda v: height * (np.abs(v) < length / 2)
    outcome = analyse(render(lambda v: 450 + bump(v), centre=lambda v: bump(v) / 2, noise=0))
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"]
    assert outcome.candidates[0]["peak_px"] == pytest.approx(height, abs=3)
    assert outcome.candidates[0]["side"] == "right"


def test_two_close_bulges_are_both_reported():
    # Codex review 2026-10-07 (third round): together they filled most of a
    # sliding trend window and became the "trend".
    bump = lambda v: 12 * (((v >= -140) & (v < -20)) | ((v >= 20) & (v < 140)))
    outcome = analyse(render(lambda v: 200 + bump(v), noise=3))
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"] * 2
    assert all(c["run_length_px"] >= 110 for c in outcome.candidates)


def test_bulge_starting_at_the_first_row_is_not_inverted_into_a_neck():
    # Codex review 2026-10-07 (third round).
    outcome = analyse(render(lambda v: 200 + 20 * (v + 539.5 < 120), noise=0))
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"]
    assert outcome.candidates[0]["peak_px"] == pytest.approx(20, abs=2)


@pytest.mark.parametrize("radius, thickness, height", [(2400.0, 900.0, 40.0), (2500.0, 700.0, 70.0)])
def test_one_sided_bulge_on_a_supported_bend(radius, thickness, height):
    # Codex review 2026-10-07 (third round): inner and outer edges of a thick
    # bend differ in slope, so a smaller-slope rule switched edges at the bump.
    inner = lambda v: np.sqrt((radius - thickness / 2) ** 2 - v * v)
    outer = lambda v: np.sqrt((radius + thickness / 2) ** 2 - v * v)
    bump = lambda v: height * (np.abs(v - 450) < 40)
    plain = analyse(render(lambda v: outer(v) - inner(v), centre=lambda v: (outer(v) + inner(v)) / 2 - radius,
                           noise=0))
    assert plain.status == "valid" and plain.candidates == []
    outcome = analyse(render(lambda v: outer(v) - inner(v) + bump(v),
                             centre=lambda v: (outer(v) + inner(v)) / 2 - radius + bump(v) / 2, noise=0))
    assert outcome.status == "valid", outcome.reason_codes
    assert [(c["defect_type"], c["side"]) for c in outcome.candidates] == [("width_bulge_candidate", "right")]


def test_a_short_unmeasured_gap_does_not_split_a_defect():
    # A single MULTIPLE_EDGES section split a 52-row neck into two runs < 40
    # (found by randomised stress testing, 2026-10-07).
    from src.inspection.geometry import _bridge
    flags = np.zeros(100, bool)
    flags[20:45] = flags[46:80] = True
    valid = np.ones(100, bool)
    valid[45] = False
    assert _bridge(flags, valid, 12)[20:80].all()
    valid[45:60] = False  # longer than max_gap: stays split
    flags[46:60] = False
    assert not _bridge(flags, valid, 12)[45:60].any()
    flags[:] = False
    flags[10:20] = True
    valid[:] = True
    valid[20:25] = False  # gap with a flagged stretch on one side only
    assert not _bridge(flags, valid, 12)[20:25].any()


def test_smooth_end_flare_stays_in_the_trend():
    # Codex review 2026-10-07 (second round): a NaN-truncated running median
    # lagged a smooth quadratic flare and reported both ends as bulges.
    outcome = analyse(render(lambda v: 450 + 30 * (v / 539.5) ** 2, noise=0))
    assert outcome.status == "valid"
    assert outcome.candidates == []


@pytest.mark.parametrize("rows", [79, 80, 81, 82])
def test_minimum_axial_length_never_raises(rows):
    # Codex review 2026-10-07 (second round): 80 sections broke a convolution.
    outcome = analyse(render(200.0, noise=0), search_roi_px=(0, 500, 1920, rows))
    assert outcome.status in {"valid", "rejected"}


@pytest.mark.parametrize("start", [10, 450, 970])
def test_bulge_is_found_near_either_end_of_the_specimen(start):
    # Codex review 2026-10-07: reflected padding absorbed bulges near the ends.
    outcome = analyse(render(lambda v: 200 + 20 * ((v + 539.5 >= start) & (v + 539.5 < start + 100)), noise=0))
    assert [c["defect_type"] for c in outcome.candidates] == ["width_bulge_candidate"]
    assert outcome.candidates[0]["peak_px"] == pytest.approx(20, abs=2)


def test_large_blurred_stretch_rejects_the_view_instead_of_hiding_a_bulge():
    # Codex review 2026-10-07: 26% of the axis blurred, sharp median, bulge hidden.
    sharp = render(lambda v: 200 + 12 * (np.abs(v) < 20), noise=0)
    mixed = sharp.copy()
    mixed[400:680] = cv2.GaussianBlur(sharp, (0, 0), 15)[400:680]
    assert analyse(sharp).candidates[0]["defect_type"] == "width_bulge_candidate"
    outcome = analyse(mixed)
    assert outcome.status == "rejected"
    assert outcome.reason_codes == ["FOCUS_UNVERIFIABLE"]


def test_short_unmeasurable_stretch_is_reported_not_skipped():
    sharp = render(200.0, noise=0)
    mixed = sharp.copy()
    mixed[500:560] = cv2.GaussianBlur(sharp, (0, 0), 15)[500:560]
    outcome = analyse(mixed)
    assert outcome.status == "valid"
    # 2026-10-08 bench: an unmeasured stretch marks unassessed material and is
    # kept out of the defect candidates (and so out of the candidate records).
    assert outcome.candidates == []
    [found] = outcome.unmeasured
    assert found["kind"] == "unmeasured_stretch"
    assert found["reason"] == "LOCAL_FOCUS_UNVERIFIABLE"
    x, y, w, h = found["bbox_px"]
    assert y <= 510 and y + h >= 550
    json.dumps(found, allow_nan=False)
    result = StaticRplaProcessor(GeometryParams(), data_mode="TEST").inspect(packet(mixed), "B")
    assert result.records == []
    assert len(result.to_dict()["unmeasured_stretches"]) == 1


def test_defocused_view_is_rejected_with_the_measured_spread():
    outcome = analyse(render(200.0, blur=15.0))
    assert outcome.status == "rejected"
    assert outcome.reason_codes == ["FOCUS_UNVERIFIABLE"]
    assert outcome.metrics["edge_spread_px_median"] > 6.0
    assert outcome.candidates == []


def test_empty_background_with_a_gradient_is_not_a_specimen():
    outcome = analyse(render(0.0, gradient=0.3))
    assert outcome.status == "rejected"
    assert outcome.reason_codes == ["SAMPLE_NOT_LOCALIZED"]


def test_bright_specimen_on_dark_background_is_located():
    outcome = analyse(render(200.0, background=(40, 40, 40), foreground=(200, 210, 215)))
    assert outcome.status == "valid"
    assert outcome.metrics["width_px_median"] == pytest.approx(200.0, abs=1.0)


def test_two_specimens_are_ambiguous():
    image = render(lambda v: 160.0, centre=-250)
    second = render(lambda v: 160.0, centre=250, seed=8)
    image = np.minimum(image, second)
    assert analyse(image).reason_codes == ["SEGMENTATION_AMBIGUOUS"]


def test_specimen_that_leaves_the_frame_is_not_measured():
    outcome = analyse(render(200.0, axial_limits=(-600, 0)))
    assert outcome.reason_codes == ["AXIS_COVERAGE_LOW"]


def test_horizontal_configuration_measures_a_horizontal_specimen():
    outcome = analyse(render(200.0, angle_deg=90.0), filament_axis="horizontal")
    assert outcome.status == "valid"
    assert outcome.metrics["width_px_median"] == pytest.approx(200.0, abs=1.0)


@pytest.mark.parametrize("angle", [0.0, 25.0, -25.0, 80.0, 90.0, -80.0])
def test_auto_axis_follows_how_the_specimen_was_placed(angle):
    # 2026-10-08 bench: the operator placed the specimen horizontally, then
    # near-vertically; a fixed axis setting rejected one of the two.
    outcome = analyse(render(200.0, angle_deg=angle), filament_axis="auto")
    assert outcome.status == "valid", outcome.reason_codes
    assert outcome.metrics["filament_axis"] == ("vertical" if abs(angle) < 45 else "horizontal")
    assert outcome.metrics["width_px_median"] == pytest.approx(200.0, abs=1.0)


def test_auto_axis_still_rejects_an_empty_view():
    assert analyse(render(0.0, gradient=0.3), filament_axis="auto").reason_codes == ["SAMPLE_NOT_LOCALIZED"]


def test_width_envelope_flags_a_specimen_outside_the_good_range():
    outcome = analyse(render(200.0), good_width_range_px=(170.0, 190.0))
    kinds = {c["defect_type"] for c in outcome.candidates}
    assert kinds == {"width_out_of_range_candidate"}


def test_saturated_specimen_is_rejected_as_clipped():
    outcome = analyse(render(200.0, background=(40, 40, 40), foreground=(255, 255, 255), noise=0.0))
    assert outcome.reason_codes == ["EXPOSURE_CLIPPED"]


def test_search_roi_limits_the_analysis_and_maps_back_to_the_image():
    bump = lambda v: np.where(np.abs(v) < 60, 20.0, 0.0)
    image = render(lambda v: 200 + bump(v), centre=lambda v: bump(v) / 2)
    outcome = analyse(image, search_roi_px=(500, 0, 920, 1080))
    assert outcome.status == "valid"
    x, y, w, h = outcome.candidates[0]["bbox_px"]
    assert 500 <= x and x + w <= 1420 and x < 1070 < x + w


@pytest.mark.parametrize("overrides", [
    {"filament_axis": "diagonal"}, {"min_feature_px": 0}, {"min_run_px": 1},
    {"min_axis_coverage": 1.5}, {"good_width_range_px": (200, 100)}, {"search_roi_px": (0, 0, -1, 10)},
])
def test_invalid_parameters_are_refused(overrides):
    with pytest.raises(ValueError):
        GeometryParams(**overrides)


def test_unknown_profile_keys_are_refused():
    with pytest.raises(ValueError, match="unknown"):
        GeometryParams.from_mapping({"threshold": 145})


def test_roi_outside_the_image_is_an_error_not_a_rejection():
    with pytest.raises(ValueError, match="outside"):
        analyse(render(200.0), search_roi_px=(1800, 0, 400, 1080))


def test_processor_records_are_uncalibrated_ranked_warnings():
    bump = lambda v: np.where(np.abs(v) < 60, 20.0, 0.0)
    image = render(lambda v: 200 + bump(v), centre=lambda v: bump(v) / 2)
    processor = StaticRplaProcessor(GeometryParams(), data_mode="TEST")
    result = processor.inspect(packet(image), "BATCH", lighting_mode="bright_field")
    assert result.geometry_status == "valid" and result.surface_status == "not_assessed"
    assert result.annotated.shape == image.shape and result.annotated is not image
    [record] = result.records
    assert record.algorithm_version == ALGORITHM_VERSION
    assert record.quality_grade is QualityGrade.WARNING
    assert 0.5 < record.confidence < 1.0
    assert record.size_mm is None and record.position_mm is None
    payload = result.to_dict()
    json.dumps(payload)
    assert payload["units"] == "px" and payload["physical_outputs_allowed"] is False
    annotated, records = processor.process(packet(image), "BATCH")
    assert annotated.shape == image.shape and len(records) == 1


def test_processor_does_not_judge_dark_field_geometry_in_phase_one():
    result = StaticRplaProcessor(GeometryParams(), data_mode="TEST").inspect(
        packet(render(200.0)), "BATCH", lighting_mode="dark_field")
    assert result.geometry_status == "not_assessed"
    assert "DARK_FIELD_GEOMETRY_NOT_IN_PHASE_1" in result.reason_codes
    assert result.records == []


def test_result_payload_never_contains_nan():
    from src.inspection.processor import _finite
    assert _finite({"a": float("nan"), "b": [np.float32(1.5), np.int64(2)], "c": (float("inf"),)}) ==         {"a": None, "b": [1.5, 2], "c": [None]}
    rejected = StaticRplaProcessor(GeometryParams(), data_mode="TEST").inspect(packet(render(200.0, blur=15.0)), "B")
    json.dumps(rejected.to_dict(), allow_nan=False)


def _view(angle, lighting="bright_field", status="valid", candidates=0):
    analysis = None if status is None else {
        "algorithm_version": ALGORITHM_VERSION, "geometry_status": status,
        "reason_codes": [] if status == "valid" else ["FOCUS_INADEQUATE"],
        "candidates": [{}] * candidates,
    }
    return {"angle_deg": angle, "lighting_mode": lighting, "analysis": analysis}


def test_summary_reports_absence_only_with_full_bright_field_coverage():
    views = [_view(angle) for angle in (0, 60, 120, 180, 240, 300)]
    assert summarize_sample(views)["conclusion"] == "no_geometry_candidates_in_assessed_scope"
    views[2] = _view(120, status="rejected")
    summary = summarize_sample(views)
    assert summary["conclusion"] == "geometry_coverage_incomplete"
    assert summary["geometry_rejected"] == [{"angle_deg": 120, "reason_codes": ["FOCUS_INADEQUATE"]}]
    assert summarize_sample(views[:5])["missing_bright_field_angles"] == [300]


def test_summary_does_not_claim_full_coverage_with_unmeasured_stretches():
    views = [_view(angle) for angle in (0, 60, 120, 180, 240, 300)]
    views[3]["analysis"]["unmeasured_stretches"] = [{"kind": "unmeasured_stretch"}]
    summary = summarize_sample(views)
    assert summary["conclusion"] == "geometry_coverage_incomplete"
    assert summary["partly_measured_angles"] == [180]


def test_summary_flags_candidates_and_keeps_legacy_views_unassessed():
    views = [_view(0, candidates=2), _view(60, status=None), _view(0, lighting="dark_field", status="not_assessed")]
    summary = summarize_sample(views)
    assert summary["conclusion"] == "candidates_present"
    assert summary["candidate_count"] == 2
    assert summary["unassessed_bright_field_angles"] == [60]
    assert summary["coverage_complete"] is False


def _preview_runtime(monkeypatch, tmp_path):
    from dataclasses import replace
    from src.camera_config import load_service_config
    from src.live_service import InspectionRuntime
    for name in ("RPLA_RESOLUTION", "RPLA_CAMERA_DEVICE", "RPLA_CONFIG_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RPLA_SOURCE_TYPE", "usb_uvc")
    # These tests cover service state, so they pin their own geometry
    # parameters instead of following the bench profile in the config file.
    config = replace(load_service_config(), expected_width_px=640, expected_height_px=480,
                     roi_px=(0, 0, 640, 480), recovery_frames=1, stale_after_s=60,
                     disconnect_after_s=120, database_path=tmp_path / "live.db",
                     static_options={"filament_axis": "vertical", "min_feature_px": 12, "min_run_px": 40})
    runtime = InspectionRuntime(config, source_factory=lambda: None)
    return config, runtime


def _preview(runtime, config, blur):
    image = render(200.0, shape=(480, 640), blur=blur)
    runtime._accept_packet(FramePacket(config.source_name, 0, "2026-10-07T00:00:00Z",
                                       "2026-10-07T00:00:00Z", CameraState.HEALTHY, image))
    return runtime.snapshot_payload()["summary"]


def test_preview_of_a_rejected_frame_is_located_but_not_processing(monkeypatch, tmp_path):
    # Codex review 2026-10-07: a defocused frame kept detection_active true.
    config, runtime = _preview_runtime(monkeypatch, tmp_path)
    summary = _preview(runtime, config, blur=8.0)
    assert summary["view_inspection"]["geometry_status"] == "rejected"
    assert "FOCUS_UNVERIFIABLE" in summary["view_inspection"]["reason_codes"]
    assert summary["target_present"] is True
    assert summary["detection_active"] is False and summary["automatic_actions_allowed"] is False
    summary = _preview(runtime, config, blur=1.2)
    assert summary["view_inspection"]["geometry_status"] == "valid"
    assert summary["detection_active"] is True


def test_preview_analysis_is_withdrawn_with_its_frame(monkeypatch, tmp_path):
    # Codex review 2026-10-07: reconnect and stale frames kept publishing "valid".
    from unittest.mock import patch
    import time
    config, runtime = _preview_runtime(monkeypatch, tmp_path)
    assert _preview(runtime, config, blur=1.2)["view_inspection"]["geometry_status"] == "valid"
    runtime.request_reconnect()
    assert runtime.snapshot_payload()["summary"]["view_inspection"] is None
    config, runtime = _preview_runtime(monkeypatch, tmp_path)
    _preview(runtime, config, blur=1.2)
    with patch("src.live_service.time.perf_counter", return_value=time.perf_counter() + 61):
        summary = runtime.snapshot_payload()["summary"]
    assert summary["camera_state"] != "HEALTHY"
    assert summary["view_inspection"] is None
