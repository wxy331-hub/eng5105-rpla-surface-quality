import assert from "node:assert/strict";
import test from "node:test";
import {
  collapseCandidateEpisodes,
  createLiveEvidenceSnapshot,
  LiveEvidenceInspectionDataSource,
  ServiceInspectionDataSource,
  toGuiDetection,
  resolveInspectionMode,
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
  assert.equal(serviceSnapshot.streamUrl, null);
  assert.equal(serviceSnapshot.imageUrl, null);
  assert.equal(serviceSnapshot.currentFrameAvailable, false);
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

test("one static mark stays one event across skipped frames and a changing box", () => {
  // 2026-10-12 bench: a marker dot's thresholded box grows and shrinks between
  // frames, and some frames in between are not judged.
  const records = [[1, [1664, 1715, 205, 183]], [2, [1662, 1649, 263, 252]], [6, [1705, 1806, 142, 184]]]
    .map(([frame, bbox]) => toGuiDetection({ ...rawDetection, detection_id: `M${frame}`, frame_id: frame, bbox_px: bbox }, "/api/frame.jpg"));
  const [event, extra] = collapseCandidateEpisodes(records);
  assert.equal(extra, undefined);
  assert.deepEqual(event.recordIds, ["M1", "M2", "M6"]);
  // A longer gap starts a new event.
  const later = toGuiDetection({ ...rawDetection, detection_id: "M13", frame_id: 13, bbox_px: [1705, 1806, 142, 184] }, "/api/frame.jpg");
  assert.equal(collapseCandidateEpisodes([...records, later]).length, 2);
});

test("a separate defect nested inside a larger one keeps its own event and identity", () => {
  // Codex review 2026-10-12: a dark ring and a separate dot inside it.
  const make = (id, frame, bbox) => toGuiDetection({ ...rawDetection, detection_id: id, frame_id: frame, bbox_px: bbox }, "/api/frame.jpg");
  const ring = [55, 55, 91, 91];
  const dot = [100, 90, 21, 21];
  assert.deepEqual(collapseCandidateEpisodes([make("A1", 1, ring), make("B3", 3, dot)]).map((event) => event.recordIds), [["A1"], ["B3"]]);
  assert.deepEqual(collapseCandidateEpisodes([make("A1", 1, ring), make("B1", 1, dot), make("A2", 2, ring), make("B2", 2, dot)])
    .map((event) => event.recordIds), [["A1", "A2"], ["B1", "B2"]]);
});

test("keeps spatially separate candidates as separate events", () => {
  const first = toGuiDetection({ ...rawDetection, detection_id: "DET-A", frame_id: 2, bbox_px: [10, 10, 20, 20] }, "/live-evidence/annotated_frame.jpg");
  const second = toGuiDetection({ ...rawDetection, detection_id: "DET-B", frame_id: 3, bbox_px: [200, 200, 20, 20] }, "/live-evidence/annotated_frame.jpg");
  assert.equal(collapseCandidateEpisodes([first, second]).length, 2);
});

test("matches interleaved candidates to their own event and keeps all deletion IDs", () => {
  const records = [1, 2, 3].flatMap((frameId) => [
    ["A", [10 + frameId, 10, 20, 20]],
    ["B", [200 + frameId, 200, 20, 20]],
  ].map(([label, bbox]) => toGuiDetection({
    ...rawDetection, detection_id: `${label}${frameId}`, frame_id: frameId, bbox_px: bbox,
  }, "/api/frame.jpg")));
  const original = structuredClone(records);
  const events = collapseCandidateEpisodes(records);
  assert.equal(events.length, 2);
  assert.deepEqual(events.map((event) => event.recordIds), [["A1", "A2", "A3"], ["B1", "B2", "B3"]]);
  assert.deepEqual(events.map((event) => event.frameLabel), ["1–3", "1–3"]);
  assert.deepEqual(events.map((event) => event.occurrences), [3, 3]);
  assert.deepEqual(records, original, "event grouping must not change the raw CSV/archive records");
});

test("an event represents one complete real record while tracking its latest frame", () => {
  const records = [
    { detection_id: "first", frame_id: 1, confidence: 0.6, area_px: 150, bbox_px: [10, 10, 20, 20], received_at_utc: "2026-09-08T00:00:01Z" },
    { detection_id: "peak", frame_id: 2, confidence: 0.9, area_px: 300, bbox_px: [11, 10, 20, 20], received_at_utc: "2026-09-08T00:00:02Z" },
    { detection_id: "last", frame_id: 3, confidence: 0.7, area_px: 200, bbox_px: [12, 10, 20, 20], received_at_utc: "2026-09-08T00:00:03Z" },
  ].map((changes) => toGuiDetection({ ...rawDetection, ...changes }, `/images/${changes.detection_id}.jpg`));
  const [event] = collapseCandidateEpisodes(records);
  for (const key of Object.keys(records[1])) assert.deepEqual(event[key], records[1][key], `representative ${key} must come from the peak record`);
  assert.equal(event.frameLabel, "1–3");
  assert.equal(event.occurrences, 3);
  assert.deepEqual(event.recordIds, ["first", "peak", "last"]);
});

test("overlapping candidates in the same frame remain distinct and match at most once next frame", () => {
  const records = [["A1", 1, 10], ["B1", 1, 15], ["A2", 2, 11], ["B2", 2, 16]]
    .map(([id, frame, x]) => toGuiDetection({ ...rawDetection, detection_id: id, frame_id: frame, bbox_px: [x, 10, 20, 20] }, "/api/frame.jpg"));
  assert.deepEqual(collapseCandidateEpisodes(records).map((event) => event.recordIds), [["A1", "A2"], ["B1", "B2"]]);
});

test("event continuity follows the most recent box even when the peak score was earlier", () => {
  const records = [1, 2, 3].map((frame) => toGuiDetection({
    ...rawDetection, detection_id: `D${frame}`, frame_id: frame,
    bbox_px: [frame * 5, 10, 20, 20], confidence: frame === 1 ? 0.9 : 0.7,
  }, "/api/frame.jpg"));
  const [event, extra] = collapseCandidateEpisodes(records);
  assert.equal(extra, undefined);
  assert.equal(event.id, "D1");
  assert.deepEqual(event.recordIds, ["D1", "D2", "D3"]);
});

test("camera service is the default and archived modes require explicit selection", () => {
  for (const mode of [undefined, "", "service", "week8", "unknown"]) assert.equal(resolveInspectionMode(mode), "service");
  assert.equal(resolveInspectionMode("offline"), "offline");
  assert.equal(resolveInspectionMode("week7"), "offline");
  assert.equal(resolveInspectionMode("live"), "live");
});

test("service frames expire without presenting an old candidate as the current frame", () => {
  const current = { ...summary, camera_state: "HEALTHY", current_frame_id: 12, frame_age_ms: 10, stale_after_ms: 1000, automatic_actions_allowed: true };
  const older = { ...rawDetection, frame_id: 11 };
  const fresh = createLiveEvidenceSnapshot(current, [older], "/api/frame.jpg", { serviceFrame: true });
  assert.equal(fresh.currentDetection, null);
  assert.equal(fresh.defects.length, 1, "stored evidence remains in the archive list");
  assert.equal(fresh.currentFrameAvailable, true);
  for (const changes of [{ camera_state: "DISCONNECTED" }, { camera_state: "STALE" }, { frame_age_ms: 1001 }, { current_frame_id: null }]) {
    const stale = createLiveEvidenceSnapshot({ ...current, ...changes }, [older], "/api/frame.jpg", { serviceFrame: true });
    assert.equal(stale.imageUrl, null);
    assert.equal(stale.currentDetection, null);
    assert.equal(stale.automaticActionsAllowed, false);
    assert.equal(stale.defects.length, 1);
  }
});

test("WebSocket loss clears live imagery and reconnect failure stays visible", async () => {
  let socket;
  const payload = { summary: { ...summary, camera_state: "HEALTHY", current_frame_id: 12, frame_age_ms: 10, stale_after_ms: 1000, automatic_actions_allowed: true, view_inspection: { geometry_status: "valid", reason_codes: [] } }, detections: [{ ...rawDetection, frame_id: 12 }] };
  const source = new ServiceInspectionDataSource({
    baseUrl: "http://127.0.0.1:9876",
    fetchImpl: async (url) => ({ ok: !url.endsWith("/reconnect"), status: 503, json: async () => payload }),
    socketFactory: () => (socket = { readyState: 1, close() { this.readyState = 3; this.onclose?.(); } }),
  });
  const unsubscribe = source.subscribe(() => {});
  await new Promise((resolve) => setImmediate(resolve));
  try {
    assert.equal(source.getSnapshot().streamUrl, "http://127.0.0.1:9876/api/stream.mjpg");
    assert.equal(source.getSnapshot().currentDetection.frameId, 12);
    assert.equal(source.getSnapshot().viewInspection.geometry_status, "valid");
    socket.close();
    assert.equal(source.getSnapshot().cameraState, "RECONNECTING");
    // The analysis belongs to the withdrawn frame (Codex review 2026-10-07).
    assert.equal(source.getSnapshot().viewInspection, null);
    assert.equal(source.getSnapshot().imageUrl, null);
    assert.equal(source.getSnapshot().streamUrl, null);
    assert.equal(source.getSnapshot().currentDetection, null);
    assert.equal((await source.listDefects()).length, 1);
    await source.replayScenario();
    assert.equal(source.getSnapshot().cameraState, "DISCONNECTED");
    assert.match(source.getSnapshot().loadError, /503/);
  } finally { unsubscribe(); }
});

test("an unsubscribed HTTP result cannot restore a disconnected service or open a socket", async () => {
  let resolveFetch;
  let socketCalls = 0;
  const source = new ServiceInspectionDataSource({ fetchImpl: () => new Promise((resolve) => { resolveFetch = resolve; }), socketFactory: () => { socketCalls += 1; } });
  const unsubscribe = source.subscribe(() => {});
  unsubscribe();
  resolveFetch({ ok: true, json: async () => ({ summary, detections: [] }) });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(socketCalls, 0);
  assert.equal(source.getSnapshot().imageUrl, null);
});
