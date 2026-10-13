import {
  offlineDetections,
  offlineEvidenceSummary,
  scenarioTimeline,
  offlineFrames,
} from "../data/offlineEvidence.js";
import { createResolutionMetadata } from "./resolutionMetadata.js";

/**
 * Integration boundary for the Week 4/8/9 system work.
 * The GUI consumes this contract and does not know whether data comes from
 * USB UVC, ESP32-S3 MJPEG, STM32 serial, or a database.
 */
export class InspectionDataSource {
  async connect() {
    throw new Error("connect() must be implemented by an integration adapter");
  }

  async disconnect() {
    throw new Error("disconnect() must be implemented by an integration adapter");
  }

  getSnapshot() {
    throw new Error("getSnapshot() must be implemented by an integration adapter");
  }

  subscribe() {
    throw new Error("subscribe() must be implemented by an integration adapter");
  }

  async listDefects() {
    throw new Error("listDefects() must be implemented by an integration adapter");
  }

  async deleteDefects() {
    throw new Error("deleteDefects() must be implemented by an integration adapter");
  }
}

export class OfflineReplayInspectionDataSource extends InspectionDataSource {
  #listeners = new Set();
  #timer = null;
  #stepIndex = 0;

  async connect() {
    this.#start();
    this.#emit();
    return this.getSnapshot();
  }

  async disconnect() {
    this.#stop();
  }

  getSnapshot() {
    const step = scenarioTimeline[this.#stepIndex];
    const frameId = step.frameId ?? 0;
    const currentDetection = [...offlineDetections].reverse().find((item) => item.frameId <= frameId) ?? null;
    const imageEvidence = offlineFrames.find((item) => item.frameId === frameId)
      ?? currentDetection ?? offlineDetections[0];
    const lastFrameAgeS = step.state === "STALE" ? 1.1 : step.state === "DISCONNECTED" ? 2.1 : 0;

    return {
      ...offlineEvidenceSummary,
      ...createResolutionMetadata({
        widthPx: imageEvidence.frameWidthPx ?? offlineEvidenceSummary.frameWidthPx,
        heightPx: imageEvidence.frameHeightPx ?? offlineEvidenceSummary.frameHeightPx,
        synthetic: true,
        requestedWidthPx: offlineEvidenceSummary.requestedWidthPx,
        requestedHeightPx: offlineEvidenceSummary.requestedHeightPx,
        requestedPixelFormat: offlineEvidenceSummary.requestedPixelFormat,
        requestedFps: offlineEvidenceSummary.requestedFps,
      }),
      mode: "OFFLINE EVIDENCE",
      currentStepIndex: this.#stepIndex,
      currentStep: step,
      cameraState: step.state,
      automaticActionsAllowed: step.automaticActionsAllowed,
      candidateProcessingAllowed: step.automaticActionsAllowed,
      physicalOutputsAllowed: false,
      recoveryCount: step.recoveryCount,
      frameNumber: frameId,
      lastFrameAgeS,
      currentDetection,
      imageFile: imageEvidence.imageFile,
      imageFrameNumber: imageEvidence.frameId,
    };
  }

  subscribe(listener) {
    this.#listeners.add(listener);
    listener(this.getSnapshot());
    this.#start();
    return () => {
      this.#listeners.delete(listener);
      if (this.#listeners.size === 0) this.#stop();
    };
  }

  replayScenario() {
    this.#stepIndex = 0;
    this.#emit();
    this.#start();
  }

  async listDefects() {
    return offlineDetections;
  }

  #start() {
    if (this.#timer || this.#stepIndex >= scenarioTimeline.length - 1) return;
    this.#timer = window.setInterval(() => {
      if (this.#stepIndex >= scenarioTimeline.length - 1) {
        this.#stop();
        return;
      }
      this.#stepIndex += 1;
      this.#emit();
    }, 1200);
  }

  #stop() {
    if (this.#timer) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  #emit() {
    const snapshot = this.getSnapshot();
    this.#listeners.forEach((listener) => listener(snapshot));
  }
}

export function toGuiDetection(item, imageUrl) {
  const grade = item.quality_grade.charAt(0).toUpperCase() + item.quality_grade.slice(1);
  return {
    id: item.detection_id,
    batchId: item.batch_id,
    cameraSource: item.camera_source,
    frameId: item.frame_id,
    receivedAtUtc: item.received_at_utc,
    type: item.defect_type,
    bboxPx: item.bbox_px,
    areaPx: item.area_px,
    algorithmScore: item.confidence,
    grade,
    algorithmVersion: item.algorithm_version,
    dataMode: item.data_mode,
    imageUrl,
    imageIsFrameSpecific: false,
  };
}

function bboxIoU(left, right) {
  const [leftX, leftY, leftWidth, leftHeight] = left;
  const [rightX, rightY, rightWidth, rightHeight] = right;
  const overlapWidth = Math.max(0, Math.min(leftX + leftWidth, rightX + rightWidth) - Math.max(leftX, rightX));
  const overlapHeight = Math.max(0, Math.min(leftY + leftHeight, rightY + rightHeight) - Math.max(leftY, rightY));
  const intersection = overlapWidth * overlapHeight;
  const union = leftWidth * leftHeight + rightWidth * rightHeight - intersection;
  return union > 0 ? intersection / union : 0;
}

// Every processed live frame records its candidates. On the 2026-10-12 bench one
// marker dot (about 1.3 frames/s, a few frames not judged in between) gave 631
// records and 52 displayed events under a one-frame gap; allowing a gap of up to
// five frames (about 4 s) gives about 27. Matching stays on IoU >= 0.5: the share
// of the smaller box also merged a separate defect nested inside a larger one,
// and capping the area ratio then split one mark whose box shrank with the
// lighting (Codex review 2026-10-12). Known limit: two nested defects of similar
// size can still swap events, since each record takes its best match in turn.
export function collapseCandidateEpisodes(detections, { maxFrameGap = 5, minIou = 0.5 } = {}) {
  const sorted = [...detections].sort((left, right) => left.frameId - right.frameId);
  const episodes = [];

  for (const detection of sorted) {
    let previous = null;
    let bestIou = minIou;
    // ponytail: scan the bounded snapshot; index active events if history grows.
    for (const episode of episodes) {
      const gap = detection.frameId - episode.frameEnd;
      if (episode.batchId !== detection.batchId || episode.type !== detection.type
        || gap <= 0 || gap > maxFrameGap) continue;
      const iou = bboxIoU(episode.lastBboxPx, detection.bboxPx);
      if (iou >= bestIou) { previous = episode; bestIou = iou; }
    }

    if (!previous) {
      episodes.push({
        ...detection,
        frameStart: detection.frameId,
        frameEnd: detection.frameId,
        lastBboxPx: detection.bboxPx,
        occurrences: 1,
        recordIds: [detection.id],
      });
      continue;
    }

    previous.frameEnd = detection.frameId;
    previous.lastBboxPx = detection.bboxPx;
    previous.occurrences += 1;
    previous.recordIds.push(detection.id);
    // Keep the peak record's identity, image and measurements together. Matching
    // follows the latest box independently of the representative's older frame.
    if (detection.algorithmScore >= previous.algorithmScore) {
      Object.assign(previous, detection);
    }
  }

  return episodes.map(({ lastBboxPx, ...episode }) => ({
    ...episode,
    frameLabel: episode.frameStart === episode.frameEnd
      ? String(episode.frameStart)
      : `${episode.frameStart}–${episode.frameEnd}`,
  }));
}

const cameraSources = {
  ALC_IMX258_USB: {
    name: "ALC-IMX258 USB",
    path: "PLAN_A_ALC_IMX258_USB_UVC",
    type: "usb_uvc",
  },
  ESP32S3_OV3660: {
    name: "ESP32S3 OV3660",
    path: "PLAN_B_ESP32S3_OV3660_MJPEG",
    type: "esp32_mjpeg",
  },
};

const cameraPathLabels = {
  PLAN_A_ALC_IMX258_USB_UVC: "Plan A · ALC-IMX258 USB UVC",
  PLAN_B_ESP32S3_OV3660_MJPEG: "Plan B · ESP32S3 OV3660 MJPEG",
};

export function createCameraSourceMetadata(summary = {}) {
  const cameraSource = summary.camera_source?.trim() || null;
  const knownSource = cameraSources[cameraSource];
  // Older captured evidence has only camera_source. Its original identity is
  // sufficient to name the path; missing or unfamiliar sources stay explicit.
  const cameraPath = summary.camera_path?.trim() || knownSource?.path || null;
  return {
    source: knownSource?.name ?? cameraSource?.replaceAll("_", " ") ?? "Waiting for camera source",
    cameraSource,
    cameraPath,
    cameraPathLabel: cameraPathLabels[cameraPath] ?? cameraPath?.replaceAll("_", " ") ?? "Camera path unavailable",
    sourceType: summary.source_type?.trim() || knownSource?.type || null,
  };
}

function currentFrameTelemetryLatency(summary, nowMs) {
  const receivedAtMs = Date.parse(summary.frame_received_at_utc ?? "");
  const publishedAtMs = Date.parse(summary.snapshot_published_at_utc ?? "");
  const frameAgeMs = summary.frame_age_ms;
  const staleAfterMs = summary.stale_after_ms;
  const elapsedMs = nowMs - receivedAtMs;
  // This measures current-frame telemetry arriving at the GUI. The separate
  // MJPEG stream has no browser-side frame identity, so this is not paint time.
  const valid = summary.camera_state === "HEALTHY"
    && Number.isInteger(summary.current_frame_id) && summary.current_frame_id >= 0
    && Number.isInteger(summary.frame_width_px) && summary.frame_width_px > 0
    && Number.isInteger(summary.frame_height_px) && summary.frame_height_px > 0
    && Number.isFinite(staleAfterMs) && staleAfterMs > 0
    && Number.isFinite(frameAgeMs) && frameAgeMs >= 0 && frameAgeMs <= staleAfterMs
    && Number.isFinite(receivedAtMs) && Number.isFinite(publishedAtMs)
    && publishedAtMs >= receivedAtMs && publishedAtMs <= nowMs
    && elapsedMs >= 0 && elapsedMs <= staleAfterMs;
  return valid ? Math.round(elapsedMs) : null;
}

export function createLiveEvidenceSnapshot(summary, rawDetections, imageUrl, { serviceFrame = false, nowMs = Date.now() } = {}) {
  const defects = rawDetections.map((item) => toGuiDetection(item, imageUrl));
  const cameraState = summary.camera_state ?? (serviceFrame ? "DISCONNECTED" : "HEALTHY");
  const frameNumber = summary.current_frame_id ?? Math.max(0, summary.frames_received - 1);
  const currentFrameAvailable = !serviceFrame || (cameraState === "HEALTHY"
    && Number.isInteger(summary.current_frame_id) && summary.frame_width_px > 0 && summary.frame_height_px > 0
    && Number.isFinite(summary.frame_age_ms) && Number.isFinite(summary.stale_after_ms)
    && summary.frame_age_ms >= 0 && summary.stale_after_ms > 0 && summary.frame_age_ms <= summary.stale_after_ms);
  const currentDetection = serviceFrame
    ? currentFrameAvailable ? defects.findLast((item) => item.frameId === summary.current_frame_id) ?? null : null
    : defects.at(-1) ?? null;
  // Loading a saved snapshot must never turn its age into a latency reading.
  const postDecodeToGuiLatencyMs = serviceFrame ? currentFrameTelemetryLatency(summary, nowMs) : null;
  return {
    mode: "INSPECTION RUN",
    ...createCameraSourceMetadata(summary),
    batchId: summary.batch_id,
    ...createResolutionMetadata({
      widthPx: summary.frame_width_px,
      heightPx: summary.frame_height_px,
      requestedWidthPx: summary.requested_width_px,
      requestedHeightPx: summary.requested_height_px,
      requestedPixelFormat: summary.requested_pixel_format,
      requestedFps: summary.requested_fps,
    }),
    framesizeName: summary.framesize_name,
    roiPx: summary.roi_px,
    cameraState,
    automaticActionsAllowed: serviceFrame ? currentFrameAvailable && summary.automatic_actions_allowed === true
      : summary.automatic_actions_allowed ?? cameraState === "HEALTHY",
    recoveryCount: cameraState === "HEALTHY" ? summary.recovery_frames_required : 0,
    recoveryFrames: summary.recovery_frames_required,
    framesGenerated: summary.frames_received,
    framesProcessedWhenSafe: summary.frames_processed_when_healthy,
    warmupFramesSkipped: summary.recovery_frames_skipped,
    droppedFrames: summary.dropped_frames ?? 0,
    currentStepIndex: 0,
    currentStep: {
      event: summary.status === "WAITING_FOR_MATERIAL" ? "WAITING_FOR_MATERIAL" : summary.status === "RUNNING" ? "LIVE_FRAME_UPDATED" : "LIVE_EVIDENCE_REFRESHED",
      state: cameraState,
    },
    frameNumber,
    lastFrameAgeS: 0,
    currentDetection,
    imageUrl: currentFrameAvailable ? imageUrl : null,
    currentFrameAvailable,
    serviceAvailable: serviceFrame,
    loadError: summary.last_error ?? null,
    imageFrameNumber: frameNumber,
    measuredFps: summary.measured_pipeline_fps,
    processingLatencyMs: summary.processing_latency_ms ?? null,
    postDecodeToGuiLatencyMs,
    inspectionFrames: summary.inspection_frames ?? summary.frames_processed_when_healthy,
    targetPresent: summary.target_present ?? true,
    viewInspection: summary.view_inspection ?? null,
    evidenceLevel: summary.evidence_level,
    hardwarePerformanceVerified: summary.hardware_stream_verified,
    rplaDefectPerformanceVerified: summary.rpla_defect_performance_verified,
    calibrationId: typeof summary.calibration_id === "string" ? summary.calibration_id.trim() || null : null,
    physicalMeasurementsAvailable: summary.physical_measurements_available === true
      && typeof summary.calibration_id === "string" && summary.calibration_id.trim().length > 0,
    physicalOutputsAllowed: false,
    captureInterpretation: summary.interpretation,
    defects,
  };
}

// A build with VITE_SERVICE_SAME_ORIGIN=1 is served by the camera service itself
// (Raspberry Pi demonstration): a browser on another computer talks to the host it
// loaded the page from. An empty VITE_* URL would instead fall back to its own 127.0.0.1.
const serviceSameOrigin = import.meta.env?.VITE_SERVICE_SAME_ORIGIN === "1";
const serviceApiUrl = (serviceSameOrigin ? globalThis.location?.origin : import.meta.env?.VITE_INSPECTION_API_URL?.trim())
  || "http://127.0.0.1:8765";
const serviceWsUrl = (serviceSameOrigin ? null : import.meta.env?.VITE_INSPECTION_WS_URL?.trim())
  || `${serviceApiUrl.replace(/^http/, "ws")}/ws`;

export class ServiceInspectionDataSource extends InspectionDataSource {
  #listeners = new Set();
  #socket = null;
  #retryTimer = null;
  #closed = false;
  #defects = [];
  #epoch = 0;
  #watchdog = null;
  #lastPayloadAt = 0;
  #fetch;
  #socketFactory;
  #apiUrl;
  #wsUrl;
  #snapshot = {
    mode: "LIVE DETECTION",
    ...createCameraSourceMetadata(),
    batchId: "Starting service",
    ...createResolutionMetadata(),
    roiPx: [0, 0, 0, 0],
    cameraState: "CONNECTING",
    automaticActionsAllowed: false,
    recoveryCount: 0,
    recoveryFrames: 3,
    framesGenerated: 0,
    framesProcessedWhenSafe: 0,
    warmupFramesSkipped: 0,
    droppedFrames: 0,
    currentStepIndex: 0,
    currentStep: { event: "CONNECT_REQUESTED", state: "CONNECTING" },
    frameNumber: 0,
    currentDetection: null,
    imageUrl: null,
    streamUrl: null,
    currentFrameAvailable: false,
    imageFrameNumber: 0,
    measuredFps: 0,
    processingLatencyMs: null,
    postDecodeToGuiLatencyMs: null,
    calibrationId: null,
    physicalMeasurementsAvailable: false,
    physicalOutputsAllowed: false,
    defects: [],
  };

  constructor({ baseUrl = serviceApiUrl, wsUrl, fetchImpl = globalThis.fetch.bind(globalThis),
    socketFactory = (url) => new WebSocket(url) } = {}) {
    super();
    this.#apiUrl = baseUrl.replace(/\/+$/, "");
    this.#wsUrl = wsUrl ?? (baseUrl === serviceApiUrl ? serviceWsUrl : `${this.#apiUrl.replace(/^http/, "ws")}/ws`);
    this.#fetch = fetchImpl;
    this.#socketFactory = socketFactory;
  }

  async connect() {
    this.#closed = false;
    const epoch = ++this.#epoch;
    await this.#loadOnce(epoch);
    if (this.#closed || epoch !== this.#epoch) return this.getSnapshot();
    this.#openSocket();
    if (!this.#watchdog) this.#watchdog = globalThis.setInterval(() => {
      if (this.#lastPayloadAt && Date.now() - this.#lastPayloadAt > 5000) {
        this.#unavailable("RECONNECTING", "Inspection service telemetry timed out");
        this.#socket?.close();
      }
    }, 1000);
    return this.getSnapshot();
  }

  async disconnect() {
    this.#closed = true;
    this.#epoch += 1;
    if (this.#watchdog) globalThis.clearInterval(this.#watchdog);
    this.#watchdog = null;
    if (this.#retryTimer) globalThis.clearTimeout(this.#retryTimer);
    this.#retryTimer = null;
    this.#socket?.close();
    this.#socket = null;
  }

  getSnapshot() {
    return this.#snapshot;
  }

  subscribe(listener) {
    this.#listeners.add(listener);
    listener(this.getSnapshot());
    if (this.#listeners.size === 1) this.connect();
    return () => {
      this.#listeners.delete(listener);
      if (this.#listeners.size === 0) this.disconnect();
    };
  }

  async listDefects() {
    return this.#defects;
  }

  async deleteDefects(recordIds) {
    const response = await this.#fetch(`${this.#apiUrl}/api/events/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record_ids: recordIds }),
    });
    if (!response.ok) throw new Error("Could not delete the selected candidate event");
    const payload = await response.json();
    this.#applyPayload(payload.snapshot);
    return payload.deleted;
  }

  async replayScenario() {
    try {
      const response = await this.#fetch(`${this.#apiUrl}/api/control/reconnect`, { method: "POST" });
      if (!response.ok) throw new Error(`Camera reconnect failed (HTTP ${response.status})`);
      this.#unavailable("RECONNECTING");
      await this.#loadOnce(this.#epoch);
      this.#openSocket();
    } catch (error) { this.#unavailable("DISCONNECTED", error.message); }
  }

  #emit() {
    this.#listeners.forEach((listener) => listener(this.#snapshot));
  }

  #applyPayload(payload) {
    if (!payload?.summary || !Array.isArray(payload.detections)) throw new Error("Invalid inspection service snapshot");
    this.#lastPayloadAt = Date.now();
    const live = createLiveEvidenceSnapshot(payload.summary, payload.detections,
      `${this.#apiUrl}/api/frame.jpg?t=${payload.summary.current_frame_id ?? "waiting"}`, { serviceFrame: true });
    // Split preview (Raspberry Pi demonstration): the analysed frame changes only
    // every few seconds, so it is fetched once per frame id instead of over MJPEG;
    // the unanalysed live picture comes from its own stream while the camera is healthy.
    const split = payload.summary.split_preview ?? null;
    this.#snapshot = {
      ...live,
      mode: "LIVE DETECTION",
      streamUrl: live.currentFrameAvailable && !split ? `${this.#apiUrl}/api/stream.mjpg` : null,
      splitPreview: split && {
        previewUrl: live.cameraState === "HEALTHY" ? `${this.#apiUrl}${split.preview_path}` : null,
        analysisAgeMs: payload.summary.frame_age_ms ?? null,
        analysisStaleAfterMs: split.analysis_stale_after_ms,
        interpretation: split.interpretation,
      },
    };
    this.#defects = this.#snapshot.defects;
    this.#emit();
  }

  #unavailable(state, message) {
    this.#snapshot = {
      ...this.#snapshot, cameraState: state, automaticActionsAllowed: false, serviceAvailable: false,
      currentFrameAvailable: false, currentDetection: null, imageUrl: null, streamUrl: null, splitPreview: null,
      viewInspection: null, processingLatencyMs: null, postDecodeToGuiLatencyMs: null, measuredFps: null,
      currentStep: { event: state === "RECONNECTING" ? "LIVE_SERVICE_RECONNECTING" : "LIVE_SERVICE_UNAVAILABLE", state },
      loadError: message ?? null,
    };
    this.#emit();
  }

  async #loadOnce(epoch = this.#epoch) {
    try {
      const response = await this.#fetch(`${this.#apiUrl}/api/snapshot`, { cache: "no-store", signal: AbortSignal.timeout(5000) });
      if (!response.ok) throw new Error("Inspection service is unavailable");
      const payload = await response.json();
      if (!this.#closed && epoch === this.#epoch) this.#applyPayload(payload);
    } catch (error) {
      if (!this.#closed && epoch === this.#epoch) this.#unavailable("DISCONNECTED", error.message);
    }
  }

  #openSocket() {
    if (this.#closed || [0, 1].includes(this.#socket?.readyState)) return;
    let socket;
    try { socket = this.#socketFactory(this.#wsUrl); }
    catch (error) { this.#unavailable("DISCONNECTED", error.message); return; }
    this.#socket = socket;
    socket.onmessage = (event) => {
      if (this.#closed || this.#socket !== socket) return;
      try { this.#applyPayload(JSON.parse(event.data)); }
      catch (error) { this.#unavailable("DISCONNECTED", error.message); socket.close(); }
    };
    socket.onclose = () => {
      if (this.#socket !== socket) return;
      this.#socket = null;
      if (this.#closed || this.#listeners.size === 0) return;
      this.#unavailable("RECONNECTING");
      this.#retryTimer = globalThis.setTimeout(() => { this.#loadOnce(); this.#openSocket(); }, 1000);
    };
  }
}

export class LiveEvidenceInspectionDataSource extends InspectionDataSource {
  #listeners = new Set();
  #timer = null;
  #defects = [];
  #snapshot = {
    mode: "INSPECTION RUN",
    ...createCameraSourceMetadata(),
    batchId: "Loading",
    ...createResolutionMetadata(),
    roiPx: [0, 0, 0, 0],
    cameraState: "CONNECTING",
    automaticActionsAllowed: false,
    recoveryCount: 0,
    recoveryFrames: 3,
    framesGenerated: 0,
    framesProcessedWhenSafe: 0,
    droppedFrames: 0,
    currentStepIndex: 0,
    currentStep: { event: "LOADING_LIVE_EVIDENCE", state: "CONNECTING" },
    frameNumber: 0,
    currentDetection: null,
    imageUrl: null,
    imageFrameNumber: 0,
    calibrationId: null,
    physicalMeasurementsAvailable: false,
    physicalOutputsAllowed: false,
    defects: [],
  };

  async connect() {
    await this.#load();
    return this.getSnapshot();
  }

  async disconnect() {
    if (this.#timer) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  getSnapshot() {
    return this.#snapshot;
  }

  subscribe(listener) {
    this.#listeners.add(listener);
    listener(this.getSnapshot());
    this.#load();
    if (!this.#timer) this.#timer = window.setInterval(() => this.#load(), 2000);
    return () => {
      this.#listeners.delete(listener);
      if (this.#listeners.size === 0) this.disconnect();
    };
  }

  async listDefects() {
    return this.#defects;
  }

  replayScenario() {
    this.#load();
  }

  async #load() {
    try {
      const base = `${import.meta.env.BASE_URL}live-evidence`;
      const cacheKey = Date.now();
      const [summaryResponse, detectionsResponse] = await Promise.all([
        fetch(`${base}/summary.json?t=${cacheKey}`, { cache: "no-store" }),
        fetch(`${base}/detections.json?t=${cacheKey}`, { cache: "no-store" }),
      ]);
      if (!summaryResponse.ok || !detectionsResponse.ok) throw new Error("Live evidence files are unavailable");
      const summary = await summaryResponse.json();
      const rawDetections = await detectionsResponse.json();
      const imageUrl = `${base}/annotated_frame.jpg?t=${cacheKey}`;
      this.#snapshot = createLiveEvidenceSnapshot(summary, rawDetections, imageUrl);
      this.#defects = this.#snapshot.defects;
      this.#listeners.forEach((listener) => listener(this.#snapshot));
    } catch (error) {
      this.#snapshot = {
        ...this.#snapshot,
        cameraState: "DISCONNECTED",
        automaticActionsAllowed: false,
        currentStep: { event: "LIVE_EVIDENCE_UNAVAILABLE", state: "DISCONNECTED" },
        loadError: error.message,
      };
      this.#listeners.forEach((listener) => listener(this.#snapshot));
    }
  }
}

export function resolveInspectionMode(requestedMode) {
  return requestedMode === "live" ? "live" : ["offline", "week7"].includes(requestedMode) ? "offline" : "service";
}
export const inspectionMode = resolveInspectionMode(import.meta.env?.VITE_INSPECTION_MODE);
export const inspectionDataSource = inspectionMode === "service"
  ? new ServiceInspectionDataSource()
  : inspectionMode === "live"
    ? new LiveEvidenceInspectionDataSource()
    : new OfflineReplayInspectionDataSource();
