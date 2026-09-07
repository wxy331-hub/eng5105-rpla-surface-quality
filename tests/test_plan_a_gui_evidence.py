"""Verify the GUI fixture is actual USB-adapter simulation with matching images."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np
import pytest

from scripts.generate_plan_a_gui_evidence import ROOT, generate_evidence
from src.week3.sources import SyntheticCameraSource
from src.week3.vision import BaselineVisionProcessor
from src.week4.uvc import UsbUvcSource


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    gui_root = tmp_path_factory.mktemp("plan-a-gui")
    adapter_frame_ids = []
    processed_frame_ids = []
    original_frames = UsbUvcSource.frames
    original_process = BaselineVisionProcessor.process

    def adapter_frames(self, limit):
        for packet in original_frames(self, limit):
            adapter_frame_ids.append(packet.frame_id)
            yield packet

    def process(self, packet, batch_id):
        processed_frame_ids.append(packet.frame_id)
        return original_process(self, packet, batch_id)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cv2, "VideoCapture", lambda *a, **kw: pytest.fail("physical camera access"))
        monkeypatch.setattr(cv2, "resize", lambda *a, **kw: pytest.fail("native evidence must not resize a small image"))
        monkeypatch.setattr(UsbUvcSource, "frames", adapter_frames)
        monkeypatch.setattr(BaselineVisionProcessor, "process", process)
        manifest = generate_evidence(gui_root)
    return gui_root, manifest, adapter_frame_ids, processed_frame_ids


def test_real_usb_adapter_controls_recovery_and_candidate_processing(generated):
    _, manifest, adapter_frame_ids, processed_frame_ids = generated
    assert adapter_frame_ids == list(range(7))
    assert processed_frame_ids == [2, 5, 6]
    assert [run["framesRead"] for run in manifest["captureRuns"]] == [3, 4]
    assert all(run["releaseCount"] == 1 for run in manifest["captureRuns"])
    timeline = manifest["timeline"]
    assert [entry["state"] for entry in timeline] == [
        "CONNECTING", "CONNECTING", "CONNECTING", "HEALTHY", "STALE",
        "DISCONNECTED", "RECONNECTING", "RECONNECTING", "RECONNECTING", "HEALTHY", "HEALTHY",
    ]
    for entry in timeline:
        assert entry["candidateProcessingAllowed"] == (entry["state"] == "HEALTHY")
        assert entry["automaticActionsAllowed"] == entry["candidateProcessingAllowed"]
        assert entry["physicalOutputsAllowed"] is False


def test_every_displayed_frame_has_its_own_matching_raw_image_and_hash(generated):
    gui_root, manifest, _, _ = generated
    assets = gui_root / "public" / "assets" / "plan-a"
    source = SyntheticCameraSource(
        width_px=3840, height_px=2160, seed=manifest["configuration"]["seed"],
        reference_size_px=(640, 360),
    )
    source.connect()
    try:
        expected = list(source.frames(7))
    finally:
        source.disconnect()
    assert len(manifest["frames"]) == 7
    assert len({frame["rawSha256"] for frame in manifest["frames"]}) == 7
    for frame, packet in zip(manifest["frames"], expected, strict=True):
        assert frame["frameId"] == packet.frame_id
        assert frame["imageIsFrameSpecific"] is True
        assert (frame["frameWidthPx"], frame["frameHeightPx"]) == (3840, 2160)
        assert frame["imageFile"] == f"frame_{packet.frame_id:04d}.jpg"
        for file_key, hash_key in (("rawImageFile", "rawSha256"), ("imageFile", "displaySha256")):
            image_path = assets / frame[file_key]
            assert hashlib.sha256(image_path.read_bytes()).hexdigest() == frame[hash_key]
            assert cv2.imread(str(image_path)).shape == (2160, 3840, 3)
        raw = cv2.imread(str(assets / frame["rawImageFile"]))
        np.testing.assert_array_equal(raw, packet.image)
        # Header rows contain only the synthetic source image: interface status
        # text is rendered in the GUI rails, not baked into every display frame.
        display = cv2.imread(str(assets / frame["imageFile"]))
        assert np.abs(display[:35].astype(np.int16) - raw[:35]).mean() < 2


def test_candidate_records_match_their_displayed_frame_and_annotation(generated):
    gui_root, manifest, _, _ = generated
    frames = {frame["frameId"]: frame for frame in manifest["frames"]}
    assert [record["frameId"] for record in manifest["detections"]] == [2, 5, 6]
    for record in manifest["detections"]:
        frame = frames[record["frameId"]]
        assert frame["processed"] is True
        assert record["id"] in frame["detectionIds"]
        assert record["imageFile"] == frame["imageFile"]
        assert record["receivedAtUtc"] == frame["receivedAtUtc"]
        image = cv2.imread(str(gui_root / "public/assets/plan-a" / record["imageFile"]))
        x, y, width, height = record["bboxPx"]
        assert 0 <= x < x + width < image.shape[1]
        assert 0 <= y < y + height < image.shape[0]
        # The exported image must actually carry the candidate's coloured box,
        # rather than merely claiming an image filename with the right number.
        top_edge = image[y, x:x + width].astype(np.int16)
        assert np.mean(top_edge[:, 2] - top_edge[:, 0] > 100) > 0.8
    for frame in frames.values():
        if not frame["processed"]:
            assert frame["detectionIds"] == []


def test_simulation_never_claims_physical_calibration_performance_or_outputs(generated):
    _, manifest, _, _ = generated
    summary = manifest["summary"]
    assert summary["cameraSource"] == "PLAN_A_USB_SIMULATION"
    assert summary["sourceType"] == "usb_uvc"
    assert summary["batchId"] == "PLAN-A-UHD-SIM-001"
    assert manifest["configuration"]["targetCamera"] == "ALC_IMX258_USB"
    assert manifest["configuration"]["captureImplementation"] == "FakeCapture"
    assert manifest["configuration"]["requestedFps"] is None
    assert manifest["configuration"]["fakeCaptureReportedProperties"]["fps"] is None
    assert summary["resolution"] == "3840 × 2160"
    assert summary["roiPx"] == [168, 864, 3504, 432]
    assert manifest["configuration"]["generationMode"] == "native_target_pixels"
    assert manifest["configuration"]["visionProfile"]["score_area_divisor_px"] == 4000 * 36
    assert summary["resolutionKind"] == "synthetic"
    assert summary["requestedResolution"] == "3840 × 2160"
    assert summary["requestedFps"] == 30
    assert summary["requestedPixelFormat"] == "MJPG"
    assert manifest["configuration"]["hardwareCaptureRequest"]["hardwareVerified"] is False
    for key in ("physicalMeasurementsAvailable", "hardwarePerformanceVerified",
                "physicalOutputsAllowed", "automaticRejectionAllowed", "physicalCameraOpened"):
        assert summary[key] is False
    for key in ("calibrationId", "measuredFps", "measuredLatencyMs"):
        assert summary[key] is None
    for record in manifest["detections"]:
        assert record["dataMode"] == "plan_a_usb_simulation"
        assert record["cameraSource"] == summary["cameraSource"]
        assert record["physicalOutputsAllowed"] is False
        assert all(record[key] is None for key in ("calibrationId", "positionMm", "sizeMm"))


def test_js_exports_match_manifest_and_have_no_course_week_label(generated):
    gui_root, manifest, _, _ = generated
    module = gui_root / "src/data/planAOfflineEvidence.js"
    exports = dict(re.findall(r"export const (\w+) = ([\s\S]*?);\n", module.read_text(encoding="utf-8")))
    for js_key, manifest_key in (
        ("offlineDetections", "detections"), ("offlineFrames", "frames"),
        ("scenarioTimeline", "timeline"), ("offlineEvidenceSummary", "summary"),
    ):
        assert json.loads(exports[js_key]) == manifest[manifest_key]
    assert hashlib.sha256(module.read_bytes()).hexdigest() == manifest["dataModuleSha256"]
    assert not re.search(r"week\s*7", module.read_text(encoding="utf-8"), re.I)


def test_checked_in_evidence_reproduces_from_current_source(generated):
    gui_root, manifest, _, _ = generated
    checked_in = ROOT / "gui-prototype"
    module_relative = Path("src/data/planAOfflineEvidence.js")
    assert (checked_in / module_relative).read_bytes() == (gui_root / module_relative).read_bytes()
    stored = json.loads((checked_in / "public/assets/plan-a/manifest.json").read_text(encoding="utf-8"))
    # Runtime versions are recorded but platform differences need not prevent
    # semantic comparison when the generated fixture bytes remain identical.
    assert {key: value for key, value in stored.items() if key != "runtime"} == {
        key: value for key, value in manifest.items() if key != "runtime"
    }
    for frame in manifest["frames"]:
        for file_key, hash_key in (("rawImageFile", "rawSha256"), ("imageFile", "displaySha256")):
            target = checked_in / "public/assets/plan-a" / frame[file_key]
            assert hashlib.sha256(target.read_bytes()).hexdigest() == frame[hash_key]
