"""Triggered, hardware-free sample workflow built on the shared frame contract.

A branch requests lighting, accepts a correlated READY, obtains a new frame,
acknowledges OFF, then commits the archive. Preview frames never enter here.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
import time
from typing import Any, Callable
from uuid import uuid4

from src.week3.models import CameraState, FramePacket
from src.week3.sources import SyntheticCameraSource
from src.week3.vision import BaselineVisionProcessor
from src.synthetic_profile import SYNTHETIC_REFERENCE_SIZE_PX, annotate_synthetic_candidates, synthetic_vision_profile
from .calibration import check_calibration
from .protocol import SimulatedLightingController, ProtocolError
from .store import SampleStore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config/week7_offline.json"
ANGLES = (0, 60, 120, 180, 240, 300)
LIGHTING_MODES = ("bright_field", "dark_field")
EVIDENCE = "OFFLINE_SYNTHETIC_ONLY"


class TriggeredSyntheticSource:
    """Generate a new deterministic fixture image after each simulated READY."""

    def __init__(self, config: dict[str, Any], clock: Callable[[], float]) -> None:
        self.clock = clock
        width, height = config["image_size_px"]
        self.source = SyntheticCameraSource(
            width_px=width, height_px=height, seed=config["seed"],
            source_name=config["source_name"],
            reference_size_px=tuple(config.get("synthetic_reference_size_px", SYNTHETIC_REFERENCE_SIZE_PX)),
        )
        self.source.connect()
        self.frames = self.source.frames(limit=1_000_000)

    def capture(self) -> tuple[FramePacket, float]:
        packet = next(self.frames)
        return packet, self.clock()


class SampleWorkflow:
    """One serialized offline acquisition controller and a persistent sample store.

    ``source`` and ``status_transform`` provide bounded fault injection for tests.
    This class does not open a physical camera, serial device or actuator.
    """

    def __init__(
        self, root: Path, *, config_path: Path = CONFIG_PATH,
        source: Any = None, clock: Callable[[], float] = time.monotonic,
        status_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.config = json.loads(config_path.read_text(encoding="utf-8"))
        if (self.config["evidence_label"] != EVIDENCE
                or tuple(self.config["angles_deg"]) != ANGLES
                or tuple(self.config["lighting_modes"]) != LIGHTING_MODES):
            raise ValueError("Offline sample capture requires the frozen 6 x 2 configuration")
        reference_size = tuple(self.config.get("synthetic_reference_size_px", SYNTHETIC_REFERENCE_SIZE_PX))
        if reference_size != SYNTHETIC_REFERENCE_SIZE_PX:
            raise ValueError("Synthetic capture requires the supported reference geometry")
        self.store = SampleStore(root)
        self.root = Path(root)
        self.clock = clock
        self.source = source or TriggeredSyntheticSource(self.config, clock)
        self.status_transform = status_transform or (lambda message: message)
        width, height = self.config["image_size_px"]
        reference_width, reference_height = reference_size
        reference_roi = tuple(round(value / scale) for value, scale in zip(
            self.config["roi_px"], (width / reference_width, height / reference_height) * 2,
        ))
        vision_profile = synthetic_vision_profile(width, height, reference_roi_px=reference_roi)
        vision_profile["roi_px"] = tuple(self.config["roi_px"])
        self.processor = BaselineVisionProcessor(
            **vision_profile,
            data_mode="plan_a_synthetic_triggered",
            algorithm_version="plan-a-synthetic-baseline-2",
        )
        self.capture_configuration = json.loads(json.dumps({
            **self.config, "vision_profile": vision_profile,
            "data_mode": self.processor.data_mode,
            "algorithm_version": self.processor.algorithm_version,
        }))
        self._lock = RLock()
        self._controllers: dict[str, SimulatedLightingController] = {}
        self._last_frame_id = -1
        self._last_fault: str | None = None

    def create_sample(self, sample_id: str) -> dict[str, Any]:
        """Create a session with its capture configuration recorded for restart safety."""
        with self._lock:
            sample = self.store.create_sample(sample_id)
            self.store.append_event(sample["session_id"], "CAPTURE_CONFIGURATION", self.capture_configuration)
            return self.describe_sample(self.store.get_sample(sample["session_id"]))

    def delete_sample(self, session_id: str) -> dict[str, Any]:
        """Serialize sample deletion with capture and release its simulator state."""
        with self._lock:
            result = self.store.delete_sample(session_id)
            self._controllers.pop(session_id, None)
            return result

    @staticmethod
    def _frozen_configuration(sample: dict[str, Any]) -> dict[str, Any] | None:
        return next((event["details"] for event in sample["events"]
                     if event["event_type"] == "CAPTURE_CONFIGURATION"), None)

    def _configuration_conflict(self, sample: dict[str, Any]) -> str | None:
        frozen = self._frozen_configuration(sample)
        if frozen is not None and frozen != self.capture_configuration:
            return "This session uses a different capture configuration. Create a new sample session to use the current configuration."
        for capture in sample["captures"]:
            if (capture["source_name"] != self.config["source_name"] or
                    [capture["image_width_px"], capture["image_height_px"]] != self.config["image_size_px"]):
                return "This session contains images from a different source or resolution. Create a new sample session to use the current configuration."
        return None

    def describe_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        """Expose compatibility without rewriting any existing archive or event."""
        configuration = self._frozen_configuration(sample)
        if configuration is None and sample["captures"]:
            first = sample["captures"][0]
            configuration = {
                "source_name": first["source_name"],
                "image_size_px": [first["image_width_px"], first["image_height_px"]],
            }
        conflict = self._configuration_conflict(sample)
        return {**sample, "capture_configuration": configuration,
                "capture_compatible": conflict is None, "capture_block_reason": conflict}

    def calibration_check(self) -> dict[str, Any]:
        context = {key: self.config[key] for key in (
            "source_name", "image_size_px", "roi_px", "lens",
            "working_distance_mm", "lighting_modes", "fixture", "axis",
        )}
        context["evidence_level"] = EVIDENCE
        profile = Path(self.config["calibration_profile"])
        if not profile.is_absolute():
            profile = PROJECT_ROOT / profile
        result = check_calibration(profile, context).to_dict()
        result["status"] = "valid_for_simulation" if result["valid"] else "invalid"
        return result

    def health(self) -> dict[str, Any]:
        return {
            "mode": "plan_a_offline", "evidence_label": EVIDENCE,
            "source_name": self.config["source_name"],
            "image_size_px": list(self.config["image_size_px"]),
            "roi_px": list(self.config["roi_px"]),
            "physical_outputs_allowed": False,
            "physical_measurements_available": False,
            "calibration": self.calibration_check(), "last_fault": self._last_fault,
            "angles_deg": list(ANGLES), "lighting_modes": list(LIGHTING_MODES),
            "capture_granularity": "single_view",
            "camera": {"status": "not_integrated", "connected": None, "capture_available": False},
            "pending_deletions": self.store.list_pending_deletions(),
        }

    def capture_angle(self, session_id: str, angle_deg: int, *, retake: bool = False) -> dict[str, Any]:
        """Compatibility helper for scripted demos that explicitly request a pair.

        Interactive/API capture must call ``capture_view`` with the selected
        lighting mode. A failure here still preserves the first successful view.
        """
        if isinstance(angle_deg, bool) or not isinstance(angle_deg, int) or angle_deg not in ANGLES:
            raise ValueError("angle_deg must be one of 0, 60, 120, 180, 240, 300")
        if not isinstance(retake, bool):
            raise ValueError("retake must be boolean")
        with self._lock:
            sample = self.store.get_sample(session_id)
            existing_modes = {view["lighting_mode"] for view in sample["current_views"]
                              if view["angle_deg"] == angle_deg}
            if not retake and existing_modes:
                raise ValueError("This angle already has a capture; use explicit retake")
            for mode in LIGHTING_MODES:
                sample = self.capture_view(session_id, angle_deg, mode,
                                           retake=retake and mode in existing_modes)
            return sample

    def capture_view(
        self, session_id: str, angle_deg: int, lighting_mode: str, *, retake: bool = False,
    ) -> dict[str, Any]:
        """Capture one selected view, acknowledge OFF, then commit its archive.

        The other lighting view remains unchanged. A repeat needs explicit
        ``retake=True`` and preserves the original image attempt and its record.
        Example: ``capture_view(session_id, 60, "dark_field")``.
        """
        if isinstance(angle_deg, bool) or not isinstance(angle_deg, int) or angle_deg not in ANGLES:
            raise ValueError("angle_deg must be one of 0, 60, 120, 180, 240, 300")
        if not isinstance(lighting_mode, str) or lighting_mode not in LIGHTING_MODES:
            raise ValueError("lighting_mode must be bright_field or dark_field")
        if not isinstance(retake, bool):
            raise ValueError("retake must be boolean")
        with self._lock:
            sample = self.store.get_sample(session_id)
            if sample["status"] != "in_progress":
                raise ValueError("Only an in-progress sample can accept captures")
            conflict = self._configuration_conflict(sample)
            if conflict:
                raise ValueError(conflict)
            existing_view = any(view["angle_deg"] == angle_deg and view["lighting_mode"] == lighting_mode
                                for view in sample["current_views"])
            if existing_view and not retake:
                raise ValueError("This view already has a capture; use explicit retake")
            if retake and not existing_view:
                raise ValueError("Cannot retake a view that has no previous capture")
            # Empty legacy sessions adopt the current configuration only when
            # acquisition starts. Existing image attempts are never rewritten.
            if self._frozen_configuration(sample) is None:
                self.store.append_event(session_id, "CAPTURE_CONFIGURATION", self.capture_configuration)
            controller = self._controllers.setdefault(
                session_id, SimulatedLightingController(session_id, clock=self.clock),
            )
            self._last_fault = None
            request_id = uuid4().hex
            off_acknowledged = False
            capture_error: Exception | None = None
            try:
                command = controller.begin(lighting_mode, request_id, angle_deg=angle_deg)
                self.store.append_event(session_id, "LIGHTING_REQUEST", command)
                ready = controller.receive(self.status_transform(controller.make_status()))
                self.store.append_event(session_id, "SIMULATED_READY", ready)
                if controller.state != "READY":
                    raise ProtocolError("Lighting, material and reference must be ready before capture")
                packet, captured_at = self.source.capture()
                if packet.camera_state != CameraState.HEALTHY:
                    raise ProtocolError("Camera is not healthy")
                if packet.source_name != self.config["source_name"]:
                    raise ProtocolError("Unexpected frame source")
                if list(packet.image.shape[:2][::-1]) != self.config["image_size_px"]:
                    raise ProtocolError("Frame dimensions differ from the capture configuration")
                if packet.frame_id <= self._last_frame_id:
                    raise ProtocolError("Duplicate or out-of-order frame")
                lighting = controller.authorize_frame({
                    "session_id": session_id, "request_id": request_id,
                    "lighting_mode": lighting_mode, "frame_id": packet.frame_id,
                    "captured_monotonic": captured_at,
                })
                self._last_frame_id = packet.frame_id
                _, records = self.processor.process(packet, session_id)
                annotated = annotate_synthetic_candidates(packet.image, records)
                # Complete and record OFF before committing a successful attempt.
                # No final event write can turn a committed capture into a failure.
                off = controller.finish()
                controller.receive(controller.make_status())
                off_acknowledged = True
                self.store.append_event(session_id, "SIMULATED_OFF_ACK", off)
                self.store.save_capture(
                    session_id, angle_deg, lighting_mode, packet, annotated,
                    [record.to_dict() for record in records],
                    lighting_metadata={**lighting, "request_id": request_id,
                                       "captured_monotonic": captured_at,
                                       "mode": lighting_mode, "simulated": True},
                    calibration=self.calibration_check(), retake=retake, request_id=request_id,
                )
            except Exception as exc:
                capture_error = exc
                self._last_fault = str(exc)
                try:
                    self.store.append_event(session_id, "CAPTURE_FAILED", {
                        "request_id": request_id, "angle_deg": angle_deg,
                        "lighting_mode": lighting_mode, "reason": str(exc),
                    })
                except Exception as event_error:
                    exc.add_note(f"Could not record CAPTURE_FAILED: {event_error}")
                raise
            finally:
                # The simulated peer always acknowledges OFF, even after a
                # malformed READY. A real transport must prove that separately.
                if not off_acknowledged:
                    try:
                        off = controller.finish()
                        controller.receive(controller.make_status())
                        self.store.append_event(session_id, "SIMULATED_OFF_ACK", off)
                    except Exception as off_error:
                        if capture_error is None:
                            raise
                        capture_error.add_note(f"Could not confirm or record SIMULATED_OFF_ACK: {off_error}")
            return self.describe_sample(self.store.get_sample(session_id))
