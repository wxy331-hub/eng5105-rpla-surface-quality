import assert from "node:assert/strict";
import test from "node:test";
import {
  offlineDetections, offlineEvidenceSummary, offlineFrames,
  resolveDisplayedEvidence, scenarioTimeline, selectOfflineEvidence,
} from "../src/data/offlineEvidence.js";
import { OfflineReplayInspectionDataSource } from "../src/services/inspectionDataSource.js";

test("explicit offline replay consumes the separate Plan A USB simulation evidence", () => {
  const snapshot = new OfflineReplayInspectionDataSource().getSnapshot();
  assert.equal(snapshot.cameraSource, "PLAN_A_USB_SIMULATION");
  assert.equal(snapshot.cameraPath, "PLAN_A_ALC_IMX258_USB_UVC");
  assert.equal(snapshot.sourceType, "usb_uvc");
  assert.equal(snapshot.evidenceAssetsDirectory, "assets/plan-a");
  assert.equal(snapshot.hardwarePerformanceVerified, false);
  assert.equal(snapshot.physicalMeasurementsAvailable, false);
  assert.equal(snapshot.resolution, "3840 × 2160");
  assert.equal(snapshot.frameWidthPx, 3840);
  assert.equal(snapshot.frameHeightPx, 2160);
  assert.deepEqual(snapshot.roiPx, [168, 864, 3504, 432]);
  assert.equal(snapshot.resolutionKind, "synthetic");
  assert.equal(snapshot.requestedResolution, "3840 × 2160");
  assert.equal(snapshot.requestedPixelFormat, "MJPG");
  assert.equal(snapshot.requestedFps, 30);
  assert.equal(snapshot.measuredFps, null);
  assert(offlineDetections.every(item => item.cameraSource === snapshot.cameraSource));
});

test("switching replay profile preserves the historical source and image identifiers", () => {
  const history = selectOfflineEvidence("plan_b");
  assert.equal(history.offlineEvidenceSummary.source, "PLAN B ADAPTER SIMULATION");
  assert.equal(history.offlineEvidenceSummary.evidenceAssetsDirectory, "assets/week4");
  assert.equal(history.offlineEvidenceSummary.resolution, "640 × 360");
  assert.deepEqual(history.offlineDetections.map(item => item.id),
    ["DET-3349BECD33", "DET-EE95E17EC7", "DET-4983DBD17B"]);
  assert(offlineDetections.every(item => !history.offlineDetections.some(old => old.id === item.id)));
});

test("each replay state uses its own saved image and always inhibits physical outputs", () => {
  const previousWindow = globalThis.window;
  let tick;
  globalThis.window = {
    setInterval(callback) { tick = callback; return 1; },
    clearInterval() {},
  };
  try {
    const source = new OfflineReplayInspectionDataSource();
    const snapshots = [];
    const unsubscribe = source.subscribe(snapshot => snapshots.push(snapshot));
    for (let step = 1; step < scenarioTimeline.length; step++) tick();
    unsubscribe();
    assert.equal(snapshots.length, scenarioTimeline.length);
    assert.equal(snapshots[0].currentDetection, null);
    for (const snapshot of snapshots) {
      const frame = offlineFrames.find(item => item.frameId === snapshot.frameNumber);
      assert.equal(snapshot.imageFile, frame.imageFile);
      assert.equal(snapshot.imageFrameNumber, frame.frameId);
      assert.equal(snapshot.frameWidthPx, frame.frameWidthPx);
      assert.equal(snapshot.frameHeightPx, frame.frameHeightPx);
      assert.equal(snapshot.physicalOutputsAllowed, false);
      assert.equal(snapshot.candidateProcessingAllowed, snapshot.cameraState === "HEALTHY");
    }
  } finally {
    globalThis.window = previousWindow;
  }
});

test("candidate selection pins the exact archived Plan A frame through later replay states", () => {
  for (const record of offlineDetections) {
    const image = resolveDisplayedEvidence({ imageFile: "frame_0006.jpg", imageFrameNumber: 6 }, record);
    assert.equal(image.imageFile, record.imageFile);
    assert.equal(image.imageFrameNumber, record.frameId);
    assert.equal(image.recordId, record.id);
    assert.equal(image.isSelectedRecord, true);
    assert.equal(record.imageIsFrameSpecific, true);
  }
  assert.equal(offlineEvidenceSummary.physicalOutputsAllowed, false);
});
