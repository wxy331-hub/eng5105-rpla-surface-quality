import assert from "node:assert/strict";
import test from "node:test";
import { collapseCandidateEpisodes, createLiveEvidenceSnapshot, toGuiDetection } from "../src/services/inspectionDataSource.js";

const summary = {
  camera_source: "ESP32S3_OV3660",
  batch_id: "RPLA-PLANB-OV3660-QXGA-001",
  frame_width_px: 2048,
  frame_height_px: 1536,
  roi_px: [650, 120, 500, 1350],
  recovery_frames_required: 3,
  frames_received: 12,
  frames_processed_when_healthy: 10,
  recovery_frames_skipped: 2,
  measured_pipeline_fps: 2.79,
  frame_received_at_utc: new Date().toISOString(),
  processing_latency_ms: 12.3,
  evidence_level: "LIVE_INTEGRATION_ONLY",
  hardware_stream_verified: true,
  rpla_defect_performance_verified: false,
  physical_measurements_available: false,
  interpretation: "Pipeline evidence only",
};

const rawDetection = {
  detection_id: "DET-TEST",
  batch_id: summary.batch_id,
  camera_source: summary.camera_source,
  frame_id: 11,
  received_at_utc: "2026-08-10T10:42:10.000+00:00",
  defect_type: "contamination_candidate",
  bbox_px: [674, 780, 18, 18],
  area_px: 25159.5,
  confidence: 0.95,
  quality_grade: "reject",
  algorithm_version: "week4-live-roi-baseline-1",
  data_mode: "LIVE_INTEGRATION_ONLY",
};

test("maps live database rows without claiming frame-specific images", () => {
  const detection = toGuiDetection(rawDetection, "/live-evidence/annotated_frame.jpg");
  assert.equal(detection.frameId, 11);
  assert.equal(detection.imageIsFrameSpecific, false);
  assert.equal(detection.dataMode, "LIVE_INTEGRATION_ONLY");
});

test("builds an honest OV3660 capture snapshot from the measured run", () => {
  const snapshot = createLiveEvidenceSnapshot(summary, [rawDetection], "/live-evidence/annotated_frame.jpg");
  assert.equal(snapshot.mode, "INSPECTION RUN");
  assert.equal(snapshot.resolution, "2048 × 1536");
  assert.equal(snapshot.measuredFps, 2.79);
  assert.equal(snapshot.processingLatencyMs, 12.3);
  assert.ok(snapshot.postDecodeToGuiLatencyMs >= 0);
  assert.equal(snapshot.framesGenerated, 12);
  assert.equal(snapshot.framesProcessedWhenSafe, 10);
  assert.equal(snapshot.warmupFramesSkipped, 2);
  assert.equal(snapshot.rplaDefectPerformanceVerified, false);
  assert.equal(snapshot.physicalMeasurementsAvailable, false);
  assert.equal(snapshot.imageFrameNumber, 11);
});

test("maps resident service waiting state without creating a false detection", () => {
  const snapshot = createLiveEvidenceSnapshot({
    ...summary,
    camera_state: "HEALTHY",
    status: "WAITING_FOR_MATERIAL",
    current_frame_id: 27,
    frames_received: 28,
    frames_processed_when_healthy: 26,
    inspection_frames: 0,
    target_present: false,
    automatic_actions_allowed: false,
  }, [], "http://127.0.0.1:8765/api/frame.jpg");

  assert.equal(snapshot.currentStep.event, "WAITING_FOR_MATERIAL");
  assert.equal(snapshot.targetPresent, false);
  assert.equal(snapshot.inspectionFrames, 0);
  assert.equal(snapshot.automaticActionsAllowed, false);
  assert.equal(snapshot.currentDetection, null);
});

test("collapses consecutive overlapping frame candidates into one display event", () => {
  const detections = [2, 3, 4, 5].map((frameId, index) => ({
    ...toGuiDetection({ ...rawDetection, detection_id: `DET-${frameId}`, frame_id: frameId, bbox_px: [86 + index % 2, 60, 218, 120] }, "/live-evidence/annotated_frame.jpg"),
  }));
  const episodes = collapseCandidateEpisodes(detections);
  assert.equal(episodes.length, 1);
  assert.equal(episodes[0].frameLabel, "2–5");
  assert.equal(episodes[0].occurrences, 4);
  assert.deepEqual(episodes[0].recordIds, ["DET-2", "DET-3", "DET-4", "DET-5"]);
});

test("keeps spatially separate candidates as separate events", () => {
  const first = toGuiDetection({ ...rawDetection, detection_id: "DET-A", frame_id: 2, bbox_px: [10, 10, 20, 20] }, "/live-evidence/annotated_frame.jpg");
  const second = toGuiDetection({ ...rawDetection, detection_id: "DET-B", frame_id: 3, bbox_px: [200, 200, 20, 20] }, "/live-evidence/annotated_frame.jpg");
  assert.equal(collapseCandidateEpisodes([first, second]).length, 2);
});
