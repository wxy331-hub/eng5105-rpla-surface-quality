import assert from "node:assert/strict";
import test from "node:test";
import {
  offlineDetections,
  offlineEvidenceSummary,
  resolveDisplayedEvidence,
  scenarioTimeline,
} from "../src/data/week4OfflineEvidence.js";

test("uses the three recorded Week 4 offline candidates", () => {
  assert.equal(offlineDetections.length, 3);
  assert.deepEqual(offlineDetections.map((item) => item.frameId), [2, 5, 6]);
  assert.ok(offlineDetections.every((item) => item.bboxPx.length === 4));
});

test("does not expose unsupported physical measurements", () => {
  assert.equal(offlineEvidenceSummary.physicalMeasurementsAvailable, false);
  assert.equal(offlineEvidenceSummary.hardwarePerformanceVerified, false);
  assert.ok(offlineDetections.every((item) => !("sizeMm" in item) && !("positionMm" in item)));
});

test("covers every verified Week 4 connection state", () => {
  const states = new Set(scenarioTimeline.map((step) => step.state));
  assert.deepEqual(states, new Set(["CONNECTING", "HEALTHY", "STALE", "DISCONNECTED", "RECONNECTING"]));
});

test("blocks automatic actions outside HEALTHY", () => {
  for (const step of scenarioTimeline) {
    assert.equal(step.automaticActionsAllowed, step.state === "HEALTHY");
  }
});

test("pins the exact saved image for every selected candidate", () => {
  const replaySnapshot = { imageFile: "frame_0006.jpg", imageFrameNumber: 6 };

  assert.deepEqual(
    offlineDetections.map((detection) => resolveDisplayedEvidence(replaySnapshot, detection)),
    [
      { imageFile: "frame_0002.jpg", imageFrameNumber: 2, recordId: "DET-3349BECD33", isSelectedRecord: true },
      { imageFile: "frame_0005.jpg", imageFrameNumber: 5, recordId: "DET-EE95E17EC7", isSelectedRecord: true },
      { imageFile: "frame_0006.jpg", imageFrameNumber: 6, recordId: "DET-4983DBD17B", isSelectedRecord: true },
    ],
  );
});

test("uses the replay image again after the record selection is cleared", () => {
  assert.deepEqual(
    resolveDisplayedEvidence({ imageFile: "frame_0005.jpg", imageFrameNumber: 5 }, null),
    { imageFile: "frame_0005.jpg", imageFrameNumber: 5, recordId: null, isSelectedRecord: false },
  );
});
