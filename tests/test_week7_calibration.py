from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from src.week7.calibration import (
    CalibrationContext,
    CalibrationError,
    CalibrationProfile,
    check_calibration,
)


NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


@pytest.fixture
def context():
    return {
        "source_name": "SYNTHETIC_OFFLINE",
        "image_size_px": [320, 180],
        "roi_px": [10, 10, 300, 160],
        "lens": "simulated-lens",
        "working_distance_mm": 100.0,
        "lighting_modes": ["bright_field", "dark_field"],
        "fixture": "simulated-indexed-fixture",
        "axis": "filament-longitudinal",
        "evidence_level": "OFFLINE_SYNTHETIC_ONLY",
    }


@pytest.fixture
def profile_data(context):
    # All numeric values and provenance here are explicit software-test inputs.
    return {
        "schema_version": 1,
        "calibration_id": "SYNTHETIC-LOGIC-TEST-ONLY",
        "status": "validated",
        **context,
        "version": "test-v1",
        "evidence_refs": ["synthetic-unit-test-fixture"],
        "validated_at_utc": "2026-09-01T00:00:00+00:00",
        "expires_at_utc": "2026-10-01T00:00:00+00:00",
        "revoked": False,
        "scale_mm_per_px": 0.01,
    }


def test_matching_simulated_profile_is_valid_for_logic_but_never_physical(profile_data, context):
    profile = CalibrationProfile.from_dict(profile_data)
    check = profile.validate(context, now=NOW)
    assert check.valid
    assert not check.physical_mm_allowed
    assert check.reason == "valid_for_offline_logic_only"
    assert check.to_dict()["calibration_id"] == "SYNTHETIC-LOGIC-TEST-ONLY"
    data = profile.to_dict()
    data["roi_px"][0] = 0
    assert profile.to_dict()["roi_px"][0] == 10


def test_context_dataclass_and_json_arrays_match(profile_data, context):
    profile = CalibrationProfile.from_dict(profile_data)
    assert profile.validate(CalibrationContext(**context), now=NOW).valid


def test_lighting_mode_order_does_not_invalidate_equivalent_setup(profile_data, context):
    context["lighting_modes"].reverse()
    assert CalibrationProfile.from_dict(profile_data).validate(context, now=NOW).valid


@pytest.mark.parametrize("field,value", [
    ("source_name", "USB-OTHER-CAMERA"),
    ("image_size_px", [640, 480]),
    ("roi_px", [0, 0, 300, 160]),
    ("lens", "replacement-lens"),
    ("working_distance_mm", 101.0),
    ("lighting_modes", ["bright_field"]),
    ("fixture", "fixture-remounted"),
    ("axis", "other-axis"),
    ("evidence_level", "LIVE_INTEGRATION_ONLY"),
])
def test_each_configuration_change_invalidates_profile(profile_data, context, field, value):
    profile = CalibrationProfile.from_dict(profile_data)
    context[field] = value
    check = profile.validate(context, now=NOW)
    assert not check.valid
    assert check.reason == f"context_mismatch:{field}"
    assert check.physical_mm_allowed is False


@pytest.mark.parametrize("field,value,reason", [
    ("status", "unvalidated", "unvalidated"),
    ("revoked", True, "revoked"),
    ("revoked", "false", "invalid_revocation_flag"),
    ("schema_version", True, "unsupported_schema_version"),
    ("calibration_id", "", "missing_calibration_id"),
    ("evidence_refs", [], "missing_validation_evidence"),
    ("expires_at_utc", "2026-09-07T00:00:00Z", "expired"),
    ("validated_at_utc", "2026-09-08T00:00:00Z", "not_yet_valid"),
    ("expires_at_utc", "2026-08-01T00:00:00Z", "invalid_validity_window"),
])
def test_stale_revoked_and_unvalidated_ids_never_grant_measurement(profile_data, context, field, value, reason):
    profile_data[field] = value
    check = CalibrationProfile.from_dict(profile_data).validate(context, now=NOW)
    assert not check.valid
    assert check.reason == reason
    assert not check.physical_mm_allowed


@pytest.mark.parametrize("field,value", [
    ("version", None),
    ("validated_at_utc", "2026-09-01T00:00:00"),
    ("expires_at_utc", "invalid-date"),
    ("image_size_px", [True, 180]),
    ("roi_px", [10, 10, 999, 160]),
    ("roi_px", [10, 10, 0, 160]),
    ("working_distance_mm", 0),
    ("working_distance_mm", 10 ** 1000),
    ("lighting_modes", ["bright_field", "bright_field"]),
    ("lighting_modes", ["unknown"]),
    ("scale_mm_per_px", -1),
    ("evidence_refs", [None]),
])
def test_malformed_validated_profile_fails_closed(profile_data, context, field, value):
    profile_data[field] = value
    check = CalibrationProfile.from_dict(profile_data).validate(context, now=NOW)
    assert not check.valid
    assert check.reason.startswith("malformed_profile_or_context:")
    assert not check.physical_mm_allowed


def test_unavailable_and_corrupt_profile_do_not_stop_pixel_workflow(tmp_path, context):
    assert check_calibration(None, context, now=NOW).reason == "missing_profile"
    assert not check_calibration(tmp_path / "absent.json", context, now=NOW).valid
    path = tmp_path / "corrupt.json"
    path.write_text("not-json", encoding="utf-8")
    assert not check_calibration(path, context, now=NOW).valid
    path.write_text('{"status":"validated","status":"unvalidated"}', encoding="utf-8")
    assert not check_calibration(path, context, now=NOW).valid
    path.write_text('{"scale_mm_per_px": NaN}', encoding="utf-8")
    assert not check_calibration(path, context, now=NOW).valid


def test_load_roundtrip_and_per_capture_expiration(tmp_path, profile_data, context):
    path = tmp_path / "test-profile.json"
    path.write_text(json.dumps(profile_data), encoding="utf-8")
    profile = CalibrationProfile.load(path)
    assert check_calibration(profile, context, now=NOW).valid
    later = datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert check_calibration(profile, context, now=later).reason == "expired"


def test_template_contains_no_measurement_values(context):
    path = Path(__file__).resolve().parents[1] / "config" / "week7_calibration.template.json"
    profile = CalibrationProfile.load(path)
    data = profile.to_dict()
    assert data["status"] == "unvalidated"
    assert data["image_size_px"] == [3840, 2160]
    assert data["roi_px"] == [168, 864, 3504, 432]
    assert data["source_name"] == "PLAN_A_SYNTHETIC_TRIGGERED"
    for field in ("calibration_id", "working_distance_mm", "scale_mm_per_px"):
        assert data[field] is None
    assert not profile.validate(context, now=NOW).valid


def test_missing_required_fields_and_naive_check_time_fail_closed(profile_data, context):
    profile = CalibrationProfile.from_dict(profile_data)
    assert not profile.validate(context, now=datetime(2026, 9, 7)).valid
    profile_data.pop("fixture")
    assert CalibrationProfile.from_dict(profile_data).validate(context, now=NOW).reason == "missing_profile_fields"


def test_nonfinite_scale_is_rejected_during_load(profile_data):
    profile_data["scale_mm_per_px"] = float("nan")
    with pytest.raises(CalibrationError):
        CalibrationProfile.from_dict(profile_data)
