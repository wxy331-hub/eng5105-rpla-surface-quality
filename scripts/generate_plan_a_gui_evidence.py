#!/usr/bin/env python3
"""Build deterministic GUI evidence through the USB adapter with synthetic I/O.

Run from the repository root with:
    .venv/Scripts/python.exe scripts/generate_plan_a_gui_evidence.py

No camera is opened. Every capture object is an explicitly injected FakeCapture.
The scenario clock and timestamps are simulated; they are not throughput or
latency measurements. Only HEALTHY frames reach the candidate processor.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from src.week3.models import CameraState
from src.week3.sources import SyntheticCameraSource
from src.week3.vision import BaselineVisionProcessor
from src.synthetic_profile import annotate_synthetic_candidates, synthetic_vision_profile
from src.week4.camera import ConnectionPolicy, LatestFrameBuffer
from src.week4.uvc import UsbUvcSource


SEED = 5105
FRAME_COUNT = 7
SOURCE_NAME = "PLAN_A_USB_SIMULATION"
BATCH_ID = "PLAN-A-UHD-SIM-001"
SIMULATION_EPOCH = datetime(2026, 9, 7, tzinfo=timezone.utc)


class FakeCapture:
    """In-memory implementation of the OpenCV calls made by UsbUvcSource."""

    def __init__(self, frames: list[np.ndarray]) -> None:
        self.images = iter(frames)
        self.opened = False
        self.open_args: tuple[int, int] | None = None
        self.properties: dict[int, float] = {}
        self.read_count = 0
        self.release_count = 0

    def open(self, device: int, backend: int) -> bool:
        self.open_args = (device, backend)
        self.opened = True
        return True

    def isOpened(self) -> bool:
        return self.opened

    def set(self, prop: int, value: float) -> bool:
        self.properties[prop] = value
        return True

    def get(self, prop: int) -> float:
        return self.properties.get(prop, 0.0)

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.opened:
            return False, None
        try:
            image = next(self.images)
        except StopIteration:
            return False, None
        self.read_count += 1
        return True, image.copy()

    def release(self) -> None:
        self.opened = False
        self.release_count += 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    params = [cv2.IMWRITE_JPEG_QUALITY, 95] if path.suffix == ".jpg" else []
    if not cv2.imwrite(str(path), image, params):
        raise OSError(f"could not write generated image: {path}")


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)


def generate_evidence(gui_root: Path | None = None) -> dict:
    """Generate an isolated Plan A fixture; return its reproducibility manifest.

    ``gui_root`` overrides only the output directory for hardware-free tests.
    Raw synthetic frames, display frames, JS data and the manifest are generated
    together, leaving previously recorded camera evidence untouched.
    """
    gui_root = gui_root or ROOT / "gui-prototype"
    assets = gui_root / "public" / "assets" / "plan-a"
    module_path = gui_root / "src" / "data" / "planAOfflineEvidence.js"
    # Generate at the selected profile's native dimensions. This exercises the
    # configured pixel canvas without measuring a physical camera's performance.
    service_config = json.loads((ROOT / "config/live_service.json").read_text(encoding="utf-8"))
    usb_config = service_config["sources"]["usb_uvc"]
    requested_profile = usb_config["resolution_profiles"][usb_config["default_resolution"]]
    width_px, height_px = requested_profile["width_px"], requested_profile["height_px"]
    vision_profile = synthetic_vision_profile(width_px, height_px)
    roi_px = vision_profile["roi_px"]
    policy = ConnectionPolicy(stale_after_s=1.0, disconnect_after_s=2.0, recovery_frames=3)
    synthetic = SyntheticCameraSource(
        width_px=width_px, height_px=height_px, seed=SEED, reference_size_px=(640, 360),
    )
    synthetic.connect()
    try:
        input_images = [packet.image for packet in synthetic.frames(FRAME_COUNT)]
    finally:
        synthetic.disconnect()

    # These two objects represent the initial connection and the reconnect.
    captures = [FakeCapture(input_images[:3]), FakeCapture(input_images[3:])]
    factories = iter(captures)
    source = UsbUvcSource(
        0, width_px=width_px, height_px=height_px, pixel_format="MJPG", fps=None,
        source_name=SOURCE_NAME, capture_factory=lambda: next(factories), policy=policy,
    )
    processor = BaselineVisionProcessor(
        **vision_profile, algorithm_version="roi-candidate-synthetic-scaled-1",
        data_mode="plan_a_usb_simulation",
    )
    buffer = LatestFrameBuffer()
    timeline: list[dict] = []
    frames: list[dict] = []
    detections: list[dict] = []
    latest_frame_id: int | None = None
    clock_s = 0.0

    def timestamp() -> str:
        return (SIMULATION_EPOCH + timedelta(seconds=clock_s)).isoformat(timespec="milliseconds")

    def log(event: str) -> None:
        processing_allowed = source.monitor.automatic_actions_allowed
        timeline.append({
            "atS": clock_s, "event": event, "state": source.state.value,
            "frameId": latest_frame_id, "recoveryCount": source.monitor.recovery_count,
            "automaticActionsAllowed": processing_allowed,
            "candidateProcessingAllowed": processing_allowed,
            "physicalOutputsAllowed": False,
        })

    def read_frame(at_s: float) -> None:
        nonlocal clock_s, latest_frame_id
        clock_s = at_s
        acquired = next(source.frames(1))
        buffer.put(acquired)
        packet = buffer.take()
        assert packet is not None
        latest_frame_id = packet.frame_id
        log("VALID_FRAME")
        allowed = source.monitor.automatic_actions_allowed
        records = []
        if allowed:
            _, records = processor.process(packet, BATCH_ID)
        # Draw only candidate geometry in the GUI palette. Source, state and
        # frame identity belong in the translated matte rails outside the image.
        # The shared processor and historical camera evidence remain unchanged.
        display = annotate_synthetic_candidates(packet.image, records)
        display_file = f"frame_{packet.frame_id:04d}.jpg"
        raw_file = f"raw/frame_{packet.frame_id:04d}.png"
        _write_image(assets / raw_file, packet.image)
        _write_image(assets / display_file, display)
        frame_record_ids = []
        for index, record in enumerate(records, start=1):
            # The processor's UUID is replaced only in this deterministic
            # fixture export; production DetectionRecord IDs are unchanged.
            detection_id = f"DET-PA-UHD-{packet.frame_id:04d}-{index:03d}"
            frame_record_ids.append(detection_id)
            detections.append({
                "id": detection_id, "batchId": record.batch_id,
                "cameraSource": record.camera_source, "frameId": record.frame_id,
                "receivedAtUtc": record.received_at_utc,
                "type": record.defect_type, "bboxPx": list(record.bbox_px),
                "areaPx": record.area_px, "algorithmScore": record.confidence,
                "grade": record.quality_grade.value.capitalize(),
                "algorithmVersion": record.algorithm_version, "dataMode": record.data_mode,
                "imageFile": display_file, "imageIsFrameSpecific": True,
                "frameWidthPx": packet.image.shape[1], "frameHeightPx": packet.image.shape[0],
                "positionMm": None, "sizeMm": None, "calibrationId": None,
                "physicalOutputsAllowed": False,
            })
        frames.append({
            "frameId": packet.frame_id, "imageFile": display_file,
            "rawImageFile": raw_file, "imageIsFrameSpecific": True,
            "frameWidthPx": packet.image.shape[1], "frameHeightPx": packet.image.shape[0],
            "cameraSource": packet.source_name, "cameraState": packet.camera_state.value,
            "receivedAtUtc": packet.received_at_utc,
            "candidateProcessingAllowed": allowed, "processed": allowed,
            "detectionIds": frame_record_ids,
            "rawSha256": _sha256(assets / raw_file),
            "displaySha256": _sha256(assets / display_file),
        })

    # Patch only the adapter's clock in this synchronous generator; the adapter
    # itself performs mode validation, packet construction and recovery gating.
    with patch("src.week4.uvc.monotonic", lambda: clock_s), patch("src.week4.uvc.utc_now_iso", timestamp):
        try:
            source.connect()
            log("CONNECT_REQUESTED")
            for at_s in (0.0, 0.1, 0.2):
                read_frame(at_s)
            clock_s = 1.3
            source.monitor.poll(clock_s)
            log("FRAME_TIMEOUT_STALE")
            clock_s = 2.3
            source.monitor.poll(clock_s)
            log("FRAME_TIMEOUT_DISCONNECTED")
            clock_s = 2.4
            source.connect()
            log("RECONNECT_ATTEMPT")
            for at_s in (2.6, 2.7, 2.8, 2.9):
                read_frame(at_s)
            reported_properties = dict(source.reported_properties)
        finally:
            source.disconnect()

    processed_count = sum(frame["processed"] for frame in frames)
    if [frame["frameId"] for frame in frames if frame["processed"]] != [2, 5, 6]:
        raise RuntimeError("USB simulation recovery gate did not follow the three-frame policy")
    if [entry["state"] for entry in timeline[4:7]] != ["STALE", "DISCONNECTED", "RECONNECTING"]:
        raise RuntimeError("USB simulation timeout and reconnect transitions failed")
    summary = {
        "status": "PASS", "evidenceLevel": "OFFLINE FAULT INJECTION ONLY",
        "evidenceCode": "OFFLINE_FAULT_INJECTION_ONLY",
        "source": "PLAN A · USB/UVC SIMULATION", "cameraSource": SOURCE_NAME,
        "cameraPath": "PLAN_A_ALC_IMX258_USB_UVC",
        "cameraPathLabel": "Plan A · ALC-IMX258 USB/UVC", "sourceType": "usb_uvc",
        "evidenceAssetsDirectory": "assets/plan-a",
        "imageDescription": "Plan A USB adapter simulation · synthetic images",
        "recordDescription": "Recorded synthetic candidate",
        "timelineDescription": "USB connection and recovery simulation",
        "sourceDescription": "Plan A USB adapter simulation",
        "batchId": BATCH_ID, "resolution": f"{width_px} × {height_px}",
        "frameWidthPx": width_px, "frameHeightPx": height_px, "resolutionKind": "synthetic",
        "requestedWidthPx": requested_profile["width_px"],
        "requestedHeightPx": requested_profile["height_px"],
        "requestedResolution": f"{requested_profile['width_px']} × {requested_profile['height_px']}",
        "requestedPixelFormat": requested_profile.get("pixel_format"),
        "requestedFps": requested_profile.get("fps"),
        "requestConfigurationSource": "config/live_service.json#sources.usb_uvc",
        "roiPx": list(roi_px), "framesGenerated": len(frames),
        "framesProcessedWhenSafe": processed_count,
        "framesBlockedDuringRecovery": len(frames) - processed_count,
        "detectionsRecorded": len(detections), "droppedFrames": buffer.dropped_frames,
        "latestFrameCapacity": 1, "staleAfterS": policy.stale_after_s,
        "disconnectAfterS": policy.disconnect_after_s, "recoveryFrames": policy.recovery_frames,
        "physicalMeasurementsAvailable": False, "hardwarePerformanceVerified": False,
        "physicalOutputsAllowed": False, "automaticRejectionAllowed": False,
        "physicalCameraOpened": False, "calibrationId": None,
        "measuredFps": None, "measuredLatencyMs": None,
        "clockDescription": "Simulated scenario clock; not a measured frame rate",
        "manifestFile": "manifest.json",
    }
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(
        "// Generated by scripts/generate_plan_a_gui_evidence.py. Synthetic input only.\n"
        + "// Health allows candidate processing; physical outputs stay inhibited.\n\n"
        + f"export const offlineDetections = {_json(detections)};\n\n"
        + f"export const offlineFrames = {_json(frames)};\n\n"
        + f"export const scenarioTimeline = {_json(timeline)};\n\n"
        + f"export const offlineEvidenceSummary = {_json(summary)};\n",
        encoding="utf-8", newline="\n",
    )
    source_files = (
        "scripts/generate_plan_a_gui_evidence.py", "config/live_service.json", "src/week3/models.py",
        "src/week3/sources.py", "src/synthetic_profile.py", "src/week3/vision.py", "src/week4/camera.py", "src/week4/uvc.py",
    )
    manifest = {
        "schemaVersion": 2, "summary": summary,
        "configuration": {
            "seed": SEED, "frameCount": FRAME_COUNT, "widthPx": width_px, "heightPx": height_px,
            "roiPx": list(roi_px), "sourceName": SOURCE_NAME,
            "referenceSizePx": [640, 360], "generationMode": "native_target_pixels",
            "visionProfile": {**vision_profile, "roi_px": list(roi_px)},
            "targetCamera": "ALC_IMX258_USB", "captureImplementation": "FakeCapture",
            "adapterImplementation": "src.week4.uvc.UsbUvcSource",
            "imageGenerator": "src.week3.sources.SyntheticCameraSource",
            "simulatedEpochUtc": SIMULATION_EPOCH.isoformat(),
            "requestedFps": None, "requestedPixelFormat": "MJPG",
            "hardwareCaptureRequest": {
                "source": "config/live_service.json#sources.usb_uvc",
                "profile": usb_config["default_resolution"],
                **requested_profile,
                "hardwareVerified": False,
            },
            "fakeCaptureReportedProperties": reported_properties,
            "connectionPolicy": {
                "staleAfterS": policy.stale_after_s, "disconnectAfterS": policy.disconnect_after_s,
                "recoveryFrames": policy.recovery_frames,
            },
        },
        "runtime": {"python": sys.version.split()[0], "opencv": cv2.__version__, "numpy": np.__version__},
        "captureRuns": [
            {"implementation": "FakeCapture", "openArgs": list(capture.open_args or ()),
             "framesRead": capture.read_count, "releaseCount": capture.release_count}
            for capture in captures
        ],
        "frames": frames, "detections": detections, "timeline": timeline,
        "sourceSha256": {file: _sha256(ROOT / file) for file in source_files},
        "dataModuleSha256": _sha256(module_path),
        "regenerateCommand": ".venv/Scripts/python.exe scripts/generate_plan_a_gui_evidence.py",
    }
    (assets / "manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    result = generate_evidence()
    print(_json({
        "source": result["summary"]["cameraSource"], "frames": len(result["frames"]),
        "candidates": len(result["detections"]), "hardwareOpened": False,
        "manifest": "gui-prototype/public/assets/plan-a/manifest.json",
    }))
