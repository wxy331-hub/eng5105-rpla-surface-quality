import assert from "node:assert/strict";
import test from "node:test";
import {
  collapseCandidateEpisodes,
  createLiveEvidenceSnapshot,
  LiveEvidenceInspectionDataSource,
  ServiceInspectionDataSource,
  toGuiDetection,
} from "../src/services/inspectionDataSource.js";
import { createResolutionMetadata } from "../src/services/resolutionMetadata.js";

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
  assert.equal(snapshot.source, "ESP32S3 OV3660");
  assert.equal(snapshot.cameraSource, "ESP32S3_OV3660");
  assert.equal(snapshot.cameraPath, "PLAN_B_ESP32S3_OV3660_MJPEG");
  assert.equal(snapshot.cameraPathLabel, "Plan B · ESP32S3 OV3660 MJPEG");
  assert.equal(snapshot.resolution, "2048 × 1536");
  assert.equal(snapshot.measuredFps, 2.79);
  assert.equal(snapshot.processingLatencyMs, 12.3);
  assert.equal(snapshot.postDecodeToGuiLatencyMs, null);
  assert.equal(snapshot.framesGenerated, 12);
  assert.equal(snapshot.framesProcessedWhenSafe, 10);
  assert.equal(snapshot.warmupFramesSkipped, 2);
  assert.equal(snapshot.rplaDefectPerformanceVerified, false);
  assert.equal(snapshot.physicalMeasurementsAvailable, false);
  assert.equal(snapshot.calibrationId, null);
  assert.equal(snapshot.physicalOutputsAllowed, false);
  assert.equal(snapshot.imageFrameNumber, 11);
});

test("maps Plan A service metadata and reports delivered dimensions without upgrading evidence", () => {
  const snapshot = createLiveEvidenceSnapshot({
    ...summary,
    camera_source: "ALC_IMX258_USB",
    camera_path: "PLAN_A_ALC_IMX258_USB_UVC",
    source_type: "usb_uvc",
    framesize_name: "UHD",
    frame_width_px: 1920,
    frame_height_px: 1080,
    requested_width_px: 3840,
    requested_height_px: 2160,
    requested_pixel_format: "MJPG",
    requested_fps: 30,
    hardware_stream_verified: false,
  }, [], "http://127.0.0.1:8765/api/frame.jpg");

  assert.equal(snapshot.source, "ALC-IMX258 USB");
  assert.equal(snapshot.cameraSource, "ALC_IMX258_USB");
  assert.equal(snapshot.cameraPath, "PLAN_A_ALC_IMX258_USB_UVC");
  assert.equal(snapshot.cameraPathLabel, "Plan A · ALC-IMX258 USB UVC");
  assert.equal(snapshot.sourceType, "usb_uvc");
  assert.equal(snapshot.framesizeName, "UHD");
  assert.equal(snapshot.resolution, "1920 × 1080");
  assert.equal(snapshot.resolutionKind, "decoded");
  assert.equal(snapshot.frameWidthPx, 1920);
  assert.equal(snapshot.frameHeightPx, 1080);
  assert.equal(snapshot.requestedResolution, "3840 × 2160");
  assert.equal(snapshot.requestedPixelFormat, "MJPG");
  assert.equal(snapshot.requestedFps, 30);
  assert.equal(snapshot.evidenceLevel, "LIVE_INTEGRATION_ONLY");
  assert.equal(snapshot.hardwarePerformanceVerified, false);
  assert.equal(snapshot.rplaDefectPerformanceVerified, false);
  assert.equal(snapshot.physicalMeasurementsAvailable, false);
});

test("maps the explicit Plan B service contract without changing its source or dimensions", () => {
  const snapshot = createLiveEvidenceSnapshot({
    ...summary,
    camera_path: "PLAN_B_ESP32S3_OV3660_MJPEG",
    source_type: "esp32_mjpeg",
    framesize_name: "SVGA",
    frame_width_px: 800,
    frame_height_px: 600,
  }, [], "http://127.0.0.1:8765/api/frame.jpg");

  assert.equal(snapshot.source, "ESP32S3 OV3660");
  assert.equal(snapshot.cameraPathLabel, "Plan B · ESP32S3 OV3660 MJPEG");
  assert.equal(snapshot.sourceType, "esp32_mjpeg");
  assert.equal(snapshot.framesizeName, "SVGA");
  assert.equal(snapshot.resolution, "800 × 600");
});

test("loading sources remain unidentified and service images use the shared API", () => {
  for (const source of [new ServiceInspectionDataSource(), new LiveEvidenceInspectionDataSource()]) {
    const snapshot = source.getSnapshot();
    assert.equal(snapshot.source, "Waiting for camera source");
    assert.equal(snapshot.cameraSource, null);
    assert.equal(snapshot.cameraPath, null);
    assert.equal(snapshot.cameraPathLabel, "Camera path unavailable");
    assert.equal(snapshot.sourceType, null);
    assert.equal(snapshot.resolution, "Waiting for frame");
    assert.equal(snapshot.automaticActionsAllowed, false);
  }
  const serviceSnapshot = new ServiceInspectionDataSource().getSnapshot();
  assert.equal(serviceSnapshot.streamUrl, "http://127.0.0.1:8765/api/stream.mjpg");
  assert.equal(new URL(serviceSnapshot.streamUrl).origin, new URL(serviceSnapshot.imageUrl).origin);
});

test("missing and unfamiliar metadata do not inherit a camera identity or invented resolution", () => {
  const missing = createLiveEvidenceSnapshot({
    ...summary,
    camera_source: undefined,
    frame_width_px: 0,
    frame_height_px: 0,
  }, [], "/api/frame.jpg");
  assert.equal(missing.source, "Waiting for camera source");
  assert.equal(missing.cameraPath, null);
  assert.equal(missing.resolution, "Waiting for frame");

  const unfamiliar = createLiveEvidenceSnapshot({
    ...summary,
    camera_source: "TEST_CAMERA",
    source_type: "usb_uvc",
  }, [], "/api/frame.jpg");
  assert.equal(unfamiliar.source, "TEST CAMERA");
  assert.equal(unfamiliar.cameraPath, null);
  assert.equal(unfamiliar.cameraPathLabel, "Camera path unavailable");
  assert.equal(unfamiliar.sourceType, "usb_uvc");
});

test("a requested mode never fills missing or invalid image dimensions", () => {
  for (const [widthPx, heightPx] of [[0, 0], [640, null], [NaN, 360], [640.5, 360], ["640", "360"]]) {
    const metadata = createResolutionMetadata({
      widthPx, heightPx, requestedWidthPx: 3840, requestedHeightPx: 2160,
      requestedFps: 30, requestedPixelFormat: "MJPG",
    });
    assert.equal(metadata.resolution, "Waiting for frame");
    assert.equal(metadata.resolutionKind, "unavailable");
    assert.equal(metadata.frameWidthPx, null);
    assert.equal(metadata.frameHeightPx, null);
    assert.equal(metadata.requestedResolution, "3840 × 2160");
  }
  const absent = createResolutionMetadata({ widthPx: 640, heightPx: 360, synthetic: true });
  assert.equal(absent.resolution, "640 × 360");
  assert.equal(absent.resolutionKind, "synthetic");
  assert.equal(absent.requestedResolution, null);
  assert.equal(absent.requestedFps, null);
});

test("only a fresh current service frame can provide a telemetry arrival interval", () => {
  const receivedAtMs = Date.parse("2026-09-07T01:00:00.000Z");
  const currentFrame = {
    ...summary,
    camera_state: "HEALTHY",
    current_frame_id: 11,
    frame_received_at_utc: new Date(receivedAtMs).toISOString(),
    snapshot_published_at_utc: new Date(receivedAtMs + 20).toISOString(),
    frame_age_ms: 20,
    stale_after_ms: 1000,
  };
  const make = (changes = {}, serviceFrame = true, nowMs = receivedAtMs + 35) => createLiveEvidenceSnapshot(
    { ...currentFrame, ...changes }, [], "/api/frame.jpg", { serviceFrame, nowMs },
  );
  assert.equal(make().postDecodeToGuiLatencyMs, 35);
  assert.equal(make({}, false).postDecodeToGuiLatencyMs, null);
  assert.equal(make({}, true, receivedAtMs + 86400000).postDecodeToGuiLatencyMs, null);
  for (const changes of [
    { camera_state: "DISCONNECTED" },
    { frame_age_ms: 1001 },
    { current_frame_id: undefined },
    { frame_width_px: 0 },
    { stale_after_ms: undefined },
    { snapshot_published_at_utc: undefined },
    { frame_received_at_utc: "invalid" },
    { frame_received_at_utc: new Date(receivedAtMs + 100).toISOString() },
  ]) assert.equal(make(changes).postDecodeToGuiLatencyMs, null);
});

test("physical measurements require explicit calibration provenance", () => {
  for (const calibrationId of [undefined, null, "", "  "]) {
    const snapshot = createLiveEvidenceSnapshot({
      ...summary, physical_measurements_available: true, calibration_id: calibrationId,
    }, [], "/api/frame.jpg");
    assert.equal(snapshot.calibrationId, null);
    assert.equal(snapshot.physicalMeasurementsAvailable, false);
    assert.equal(snapshot.physicalOutputsAllowed, false);
  }
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
