"""Calibration-file validity checks for the offline Week 7 workflow.

A calibration identifier alone is never evidence of a measurement. This module
checks provenance, expiry and acquisition context, but its simulated workflow
always leaves physical measurement permission disabled.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CalibrationError(ValueError):
    """The profile or acquisition context is malformed."""


@dataclass(frozen=True)
class CalibrationContext:
    source_name: str
    image_size_px: tuple[int, int]
    roi_px: tuple[int, int, int, int]
    lens: str
    working_distance_mm: float
    lighting_modes: tuple[str, ...]
    fixture: str
    axis: str
    evidence_level: str = "OFFLINE_SYNTHETIC_ONLY"


@dataclass(frozen=True)
class CalibrationCheck:
    valid: bool
    reason: str
    calibration_id: str | None = None
    physical_mm_allowed: bool = False
    evidence_level: str = "OFFLINE_SYNTHETIC_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise CalibrationError(f"{field} must be an ISO UTC timestamp")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CalibrationError(f"{field} must be an ISO UTC timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CalibrationError(f"{field} must include timezone")
    return timestamp.astimezone(timezone.utc)


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalibrationError(f"{field} must be a nonempty string")
    return value


def _positive(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise CalibrationError(f"{field} must be a positive finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise CalibrationError(f"{field} exceeds finite numeric range") from exc
    if not finite or value <= 0:
        raise CalibrationError(f"{field} must be a positive finite number")
    return float(value)


def _context_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    result = {key: _text(value.get(key), key) for key in
              ("source_name", "lens", "fixture", "axis", "evidence_level")}
    for key, length in (("image_size_px", 2), ("roi_px", 4)):
        sequence = value.get(key)
        if (not isinstance(sequence, (list, tuple)) or len(sequence) != length or
                any(type(item) is not int or item < 0 for item in sequence)):
            raise CalibrationError(f"{key} must contain {length} nonnegative integers")
        result[key] = tuple(sequence)
    width, height = result["image_size_px"]
    x, y, roi_width, roi_height = result["roi_px"]
    if not width or not height or not roi_width or not roi_height:
        raise CalibrationError("image and ROI dimensions must be positive")
    if x + roi_width > width or y + roi_height > height:
        raise CalibrationError("roi_px is outside image_size_px")
    result["working_distance_mm"] = _positive(value.get("working_distance_mm"), "working_distance_mm")
    modes = value.get("lighting_modes")
    if (not isinstance(modes, (tuple, list)) or not modes or
            any(mode not in ("bright_field", "dark_field") for mode in modes) or
            len(set(modes)) != len(modes)):
        raise CalibrationError("lighting_modes must list unique supported modes")
    result["lighting_modes"] = tuple(sorted(modes))
    return result


@dataclass(frozen=True)
class CalibrationProfile:
    """A loaded JSON profile; validity is checked against each capture context."""

    data: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CalibrationProfile":
        if not isinstance(value, Mapping):
            raise CalibrationError("calibration profile must be an object")
        try:
            copied = json.loads(json.dumps(dict(value), allow_nan=False))
        except (TypeError, ValueError, RecursionError) as exc:
            raise CalibrationError("profile must contain finite JSON values") from exc
        return cls(copied)

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationProfile":
        def reject_constant(value: str) -> None:
            raise CalibrationError(f"nonfinite JSON constant: {value}")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise CalibrationError(f"duplicate profile key: {key}")
                result[key] = value
            return result

        try:
            profile_path = Path(path)
            if profile_path.stat().st_size > 65536:
                raise CalibrationError("calibration profile exceeds 64 KiB")
            text = profile_path.read_text(encoding="utf-8")
            value = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            raise CalibrationError(f"cannot load calibration profile: {exc}") from exc
        return cls.from_dict(value)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.data, allow_nan=False))

    def validate(
        self,
        context: Mapping[str, Any] | CalibrationContext,
        *,
        now: datetime | None = None,
    ) -> CalibrationCheck:
        data = self.data
        calibration_id = data.get("calibration_id")
        if not isinstance(calibration_id, str) or not calibration_id.strip():
            calibration_id = None

        def invalid(reason: str) -> CalibrationCheck:
            return CalibrationCheck(False, reason, calibration_id)

        required = {
            "schema_version", "calibration_id", "status", "source_name", "image_size_px",
            "roi_px", "lens", "working_distance_mm", "lighting_modes", "fixture", "axis",
            "version", "evidence_level", "evidence_refs", "validated_at_utc", "expires_at_utc",
            "revoked", "scale_mm_per_px",
        }
        if not required.issubset(data):
            return invalid("missing_profile_fields")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            return invalid("unsupported_schema_version")
        if type(data["revoked"]) is not bool:
            return invalid("invalid_revocation_flag")
        if data["revoked"]:
            return invalid("revoked")
        if data["status"] != "validated":
            return invalid("unvalidated")
        if calibration_id is None:
            return invalid("missing_calibration_id")
        try:
            _text(data["version"], "version")
            refs = data["evidence_refs"]
            if not isinstance(refs, list) or not refs:
                return invalid("missing_validation_evidence")
            for reference in refs:
                _text(reference, "evidence_refs entry")
            profile_context = _context_fields(data)
            actual_context = _context_fields(asdict(context) if isinstance(context, CalibrationContext) else context)
            validated_at = _timestamp(data["validated_at_utc"], "validated_at_utc")
            expires_at = _timestamp(data["expires_at_utc"], "expires_at_utc")
            current = datetime.now(timezone.utc) if now is None else now
            if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
                return invalid("validation_time_requires_timezone")
            if expires_at <= validated_at:
                return invalid("invalid_validity_window")
            if current < validated_at:
                return invalid("not_yet_valid")
            if current >= expires_at:
                return invalid("expired")
            scale = data["scale_mm_per_px"]
            if scale is not None:
                _positive(scale, "scale_mm_per_px")
        except (CalibrationError, TypeError, AttributeError) as exc:
            return invalid(f"malformed_profile_or_context: {exc}")
        for key, expected in profile_context.items():
            if actual_context[key] != expected:
                return invalid(f"context_mismatch:{key}")
        # A simulated profile can exercise the complete validity path. It cannot
        # turn synthetic pixel coordinates into a physical filament measurement.
        return CalibrationCheck(True, "valid_for_offline_logic_only", calibration_id)


def check_calibration(
    path_or_profile: str | Path | CalibrationProfile | None,
    context: Mapping[str, Any] | CalibrationContext,
    *,
    now: datetime | None = None,
) -> CalibrationCheck:
    """Fail closed for absent, unreadable or invalid profiles without stopping pixel analysis."""
    if path_or_profile is None:
        return CalibrationCheck(False, "missing_profile")
    try:
        profile = path_or_profile if isinstance(path_or_profile, CalibrationProfile) else CalibrationProfile.load(path_or_profile)
        return profile.validate(context, now=now)
    except (CalibrationError, OSError, TypeError) as exc:
        return CalibrationCheck(False, f"unavailable_profile: {exc}")
