"""Archive one operator-selected view from the shared live camera connection."""

from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from src.inspection.factory import create_processor
from src.inspection.summary import summarize_sample
from src.live_service import CameraCaptureError, InspectionRuntime
from src.week7.store import ANGLES, LIGHTING_MODES, SampleStore

class CameraSampleWorkflow:
    """Manual six-angle/two-lighting archive with no device or MCU ownership.

    The operator sets the fixture and lighting before pressing Capture. The
    metadata records that declaration, without asserting sensor confirmation.
    """

    def __init__(self, root: Path, runtime: InspectionRuntime, *, capture_timeout_s: float = 5.0) -> None:
        if not 0 < capture_timeout_s <= 60:
            raise ValueError("capture_timeout_s must be between 0 and 60 seconds")
        self.runtime = runtime
        self.root = Path(root).resolve()
        self.evidence_label = runtime.camera_health()["source_evidence"]
        self.store = SampleStore(self.root, evidence_label=self.evidence_label, database_name="week8_samples.sqlite3")
        self.capture_timeout_s = capture_timeout_s
        self._lock = RLock()
        self._last_fault: str | None = None
        config = runtime.config
        self.processor = create_processor(
            config, baseline_version="week8-camera-baseline-1", data_mode="LIVE_TRIGGERED_CANDIDATE_ONLY",
        )
        # Freeze every acquisition/vision setting; exclude only transport policy
        # and output location. A changed configuration requires a fresh session.
        acquisition = asdict(config)
        for key in ("database_path", "cors_allow_origins", "event_retention", "jpeg_quality",
                    "reconnect_delay_s", "open_timeout_ms", "read_timeout_ms"):
            acquisition.pop(key)
        # Recorded only when on, so sessions frozen before this mode existed stay
        # compatible on the computer that made them.
        if not config.split_preview:
            acquisition.pop("split_preview")
        self.capture_configuration = json.loads(json.dumps({
            **acquisition,
            "schema_version": 1, "evidence_label": self.evidence_label,
            "source_evidence": runtime.camera_health()["source_evidence"],
            "image_size_px": [config.expected_width_px, config.expected_height_px],
            "angles_deg": list(ANGLES), "lighting_modes": list(LIGHTING_MODES),
            "lighting_control": "manual_declared", "angle_control": "manual_declared",
            "hardware_trigger_verified": False, "calibration_id": None,
            "physical_outputs_allowed": False, "physical_measurements_available": False,
            "algorithm_version": self.processor.algorithm_version, "data_mode": self.processor.data_mode,
            # Content fingerprint, not just a path: a reference replaced in place
            # must not be mixed into an existing session.
            "surface_reference": (None if getattr(self.processor, "reference", None) is None
                                  else self.processor.reference.identity()),
        }))

    @staticmethod
    def _frozen_configuration(sample: dict[str, Any]) -> dict[str, Any] | None:
        return next((event["details"] for event in sample["events"]
                     if event["event_type"] == "CAPTURE_CONFIGURATION"), None)

    def _configuration_conflict(self, sample: dict[str, Any]) -> str | None:
        frozen = self._frozen_configuration(sample)
        if frozen is None or frozen != self.capture_configuration:
            return "This session has missing or different camera configuration. Create a new sample session."
        for capture in sample["captures"]:
            if (capture["source_name"] != self.runtime.config.source_name
                    or [capture["image_width_px"], capture["image_height_px"]]
                    != self.capture_configuration["image_size_px"]
                    or capture["evidence_label"] != self.evidence_label):
                return "This session contains incompatible camera captures. Create a new sample session."
        return None

    def describe_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        conflict = self._configuration_conflict(sample)
        return {**sample, "capture_configuration": self._frozen_configuration(sample),
                "capture_compatible": conflict is None, "capture_block_reason": conflict,
                "inspection_summary": summarize_sample(sample["current_views"])}

    def create_sample(self, sample_id: str) -> dict[str, Any]:
        with self._lock:
            sample = self.store.create_sample(sample_id)
            self.store.append_event(sample["session_id"], "CAPTURE_CONFIGURATION", self.capture_configuration)
            return self.describe_sample(self.store.get_sample(sample["session_id"]))

    def delete_sample(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            return self.store.delete_sample(session_id)

    @staticmethod
    def calibration_check() -> dict[str, Any]:
        return {"valid": False, "status": "not_calibrated", "calibration_id": None,
                "reasons": ["A camera-specific calibration and independent validation are pending."],
                "physical_measurements_available": False, "physical_outputs_allowed": False}

    def health(self) -> dict[str, Any]:
        config = self.runtime.config
        camera = self.runtime.camera_health()
        return {
            "mode": "plan_a_camera", "evidence_label": self.evidence_label,
            "source_name": config.source_name, "source_type": config.source_type,
            "image_size_px": [camera["frame_width_px"], camera["frame_height_px"]],
            "roi_px": list(config.roi_px), "inspection_profile": config.inspection_profile,
            "parameter_status": config.parameter_status,
            "vision_algorithm": config.vision_algorithm, "algorithm_version": self.processor.algorithm_version,
            "physical_outputs_allowed": False, "physical_measurements_available": False,
            "calibration": self.calibration_check(), "last_fault": self._last_fault,
            "angles_deg": list(ANGLES), "lighting_modes": list(LIGHTING_MODES),
            "capture_granularity": "single_view", "lighting_control": "manual_declared",
            "angle_control": "manual_declared", "preview_url": "/api/stream.mjpg",
            "camera": camera, "capture_timeout_s": self.capture_timeout_s,
            "pending_deletions": self.store.list_pending_deletions(),
        }

    def capture_view(self, session_id: str, angle_deg: int, lighting_mode: str,
                     *, retake: bool = False) -> dict[str, Any]:
        if isinstance(angle_deg, bool) or not isinstance(angle_deg, int) or angle_deg not in ANGLES:
            raise ValueError("angle_deg must be one of 0, 60, 120, 180, 240, 300")
        if not isinstance(lighting_mode, str) or lighting_mode not in LIGHTING_MODES:
            raise ValueError("lighting_mode must be bright_field or dark_field")
        if not isinstance(retake, bool):
            raise ValueError("retake must be boolean")
        with self._lock:
            try:
                sample = self.store.get_sample(session_id)
            except sqlite3.Error as error:
                self._last_fault = str(error)
                raise
            if sample["status"] != "in_progress":
                raise ValueError("Only an in-progress sample can accept captures")
            conflict = self._configuration_conflict(sample)
            if conflict:
                raise ValueError(conflict)
            exists = any(view["angle_deg"] == angle_deg and view["lighting_mode"] == lighting_mode
                         for view in sample["current_views"])
            if exists and not retake:
                raise ValueError("This view already has a capture; use explicit retake")
            if retake and not exists:
                raise ValueError("Cannot retake a view that has no previous capture")
            request_id = uuid4().hex
            self._last_fault = None
            declaration = {
                "request_id": request_id, "mode": lighting_mode, "angle_deg": angle_deg,
                "control": "manual", "verification": "operator_declared",
                "sensor_confirmed": False, "angle_sensor_confirmed": False,
                "simulated": False, "hardware_trigger_verified": False,
            }
            try:
                self.store.append_event(session_id, "OPERATOR_CAPTURE_REQUEST", declaration)
                lease = self.runtime.capture_fresh_frame(self.capture_timeout_s)
                analysis = None
                if hasattr(self.processor, "inspect"):
                    # Archive the full result, including why a view was not judged,
                    # so a rejected view is never read back as "no candidates".
                    result = self.processor.inspect(lease.packet, session_id, lighting_mode=lighting_mode,
                                                    angle_deg=angle_deg)
                    annotated, records, analysis = result.annotated, result.records, result.to_dict()
                else:
                    annotated, records = self.processor.process(lease.packet, session_id)
                self.runtime.validate_capture_frame(lease)
                self.store.save_capture(
                    session_id, angle_deg, lighting_mode, lease.packet, annotated, records,
                    lighting_metadata={
                        **declaration, "connection_generation": lease.generation,
                        "source_frame_id": lease.source_frame_id, "service_sequence": lease.sequence,
                        "requested_monotonic": lease.requested_monotonic,
                        "captured_monotonic": lease.acquired_monotonic,
                        "freshness_basis": "host_read_completed_after_request",
                        "source_evidence": self.runtime.camera_health()["source_evidence"],
                    },
                    calibration=self.calibration_check(), retake=retake, request_id=request_id,
                    analysis=analysis, commit_guard=lambda: self.runtime.capture_commit_guard(lease),
                )
            except (CameraCaptureError, ValueError, OSError, sqlite3.Error) as error:
                self._last_fault = str(error)
                try:
                    self.store.append_event(session_id, "CAPTURE_FAILED", {
                        "request_id": request_id, "angle_deg": angle_deg,
                        "lighting_mode": lighting_mode, "error": str(error),
                    })
                except Exception as event_error:
                    # A secondary logging failure must not replace the capture error.
                    error.add_note(f"Could not record CAPTURE_FAILED: {event_error}")
                raise
            return self.describe_sample(self.store.get_sample(session_id))
