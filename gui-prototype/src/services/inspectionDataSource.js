import {
  offlineDetections,
  offlineEvidenceSummary,
  scenarioTimeline,
  offlineFrames,
} from "../data/offlineEvidence.js";
import { createResolutionMetadata } from "./resolutionMetadata.js";

export class CameraSource {
  async connect() { throw new Error("CameraSource.connect() is not implemented"); }
  async disconnect() { throw new Error("CameraSource.disconnect() is not implemented"); }
  subscribeFrames() { throw new Error("CameraSource.subscribeFrames() is not implemented"); }
  async readStatus() { throw new Error("CameraSource.readStatus() is not implemented"); }
}

export class TelemetrySource {
  async connect() { throw new Error("TelemetrySource.connect() is not implemented"); }
  subscribeTelemetry() { throw new Error("TelemetrySource.subscribeTelemetry() is not implemented"); }
  async readHealth() { throw new Error("TelemetrySource.readHealth() is not implemented"); }
}

export class DefectRepository {
  async append() { throw new Error("DefectRepository.append() is not implemented"); }
  async list() { throw new Error("DefectRepository.list() is not implemented"); }
  async exportCsv() { throw new Error("DefectRepository.exportCsv() is not implemented"); }
}

export class AlarmController {
  async raise() { throw new Error("AlarmController.raise() is not implemented"); }
  async acknowledge() { throw new Error("AlarmController.acknowledge() is not implemented"); }
  async holdOutputs() { throw new Error("AlarmController.holdOutputs() is not implemented"); }
}

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

export function collapseCandidateEpisodes(detections, { maxFrameGap = 1, minIou = 0.5 } = {}) {
  const sorted = [...detections].sort((left, right) => left.frameId - right.frameId);
  const episodes = [];

  for (const detection of sorted) {
    const previous = episodes.at(-1);
    const continuesPrevious = previous
      && previous.batchId === detection.batchId
      && previous.type === detection.type
      && detection.frameId - previous.frameEnd <= maxFrameGap
      && bboxIoU(previous.bboxPx, detection.bboxPx) >= minIou;

    if (!continuesPrevious) {
      episodes.push({
        ...detection,
        frameStart: detection.frameId,
        frameEnd: detection.frameId,
        occurrences: 1,
        recordIds: [detection.id],
      });
      continue;
    }

    previous.frameEnd = detection.frameId;
    previous.occurrences += 1;
    previous.recordIds.push(detection.id);
    if (detection.algorithmScore >= previous.algorithmScore) {
      previous.algorithmScore = detection.algorithmScore;
      previous.areaPx = detection.areaPx;
      previous.bboxPx = detection.bboxPx;
    }
  }

  return episodes.map((episode) => ({
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
  const currentDetection = defects.at(-1) ?? null;
  const cameraState = summary.camera_state ?? "HEALTHY";
  const frameNumber = summary.current_frame_id ?? Math.max(0, summary.frames_received - 1);
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
    automaticActionsAllowed: summary.automatic_actions_allowed ?? cameraState === "HEALTHY",
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
    imageUrl,
    imageFrameNumber: frameNumber,
    measuredFps: summary.measured_pipeline_fps,
    processingLatencyMs: summary.processing_latency_ms ?? null,
    postDecodeToGuiLatencyMs,
    inspectionFrames: summary.inspection_frames ?? summary.frames_processed_when_healthy,
    targetPresent: summary.target_present ?? true,
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

const serviceApiUrl = import.meta.env?.VITE_INSPECTION_API_URL?.trim() || "http://127.0.0.1:8765";
const serviceWsUrl = import.meta.env?.VITE_INSPECTION_WS_URL?.trim()
  || `${serviceApiUrl.replace(/^http/, "ws")}/ws`;

export class ServiceInspectionDataSource extends InspectionDataSource {
  #listeners = new Set();
  #socket = null;
  #retryTimer = null;
  #closed = false;
  #defects = [];
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
    imageUrl: `${serviceApiUrl}/api/frame.jpg`,
    streamUrl: `${serviceApiUrl}/api/stream.mjpg`,
    imageFrameNumber: 0,
    measuredFps: 0,
    processingLatencyMs: null,
    postDecodeToGuiLatencyMs: null,
    calibrationId: null,
    physicalMeasurementsAvailable: false,
    physicalOutputsAllowed: false,
    defects: [],
  };

  async connect() {
    this.#closed = false;
    await this.#loadOnce();
    this.#openSocket();
    return this.getSnapshot();
  }

  async disconnect() {
    this.#closed = true;
    if (this.#retryTimer) window.clearTimeout(this.#retryTimer);
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
    const response = await fetch(`${serviceApiUrl}/api/events/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record_ids: recordIds }),
    });
    if (!response.ok) throw new Error("Could not delete the selected candidate event");
    const payload = await response.json();
    this.#applyPayload(payload.snapshot);
    return payload.deleted;
  }

  replayScenario() {
    fetch(`${serviceApiUrl}/api/control/reconnect`, { method: "POST" }).catch(() => {});
  }

  #emit() {
    this.#listeners.forEach((listener) => listener(this.#snapshot));
  }

  #applyPayload(payload) {
    this.#snapshot = {
      ...createLiveEvidenceSnapshot(payload.summary, payload.detections, `${serviceApiUrl}/api/frame.jpg`, { serviceFrame: true }),
      mode: "LIVE DETECTION",
      streamUrl: `${serviceApiUrl}/api/stream.mjpg`,
    };
    this.#defects = this.#snapshot.defects;
    this.#emit();
  }

  async #loadOnce() {
    try {
      const response = await fetch(`${serviceApiUrl}/api/snapshot`, { cache: "no-store" });
      if (!response.ok) throw new Error("Inspection service is unavailable");
      this.#applyPayload(await response.json());
    } catch (error) {
      this.#snapshot = {
        ...this.#snapshot,
        cameraState: "DISCONNECTED",
        automaticActionsAllowed: false,
        postDecodeToGuiLatencyMs: null,
        currentStep: { event: "LIVE_SERVICE_UNAVAILABLE", state: "DISCONNECTED" },
        loadError: error.message,
      };
      this.#emit();
    }
  }

  #openSocket() {
    if (this.#closed || this.#socket?.readyState === WebSocket.OPEN || this.#socket?.readyState === WebSocket.CONNECTING) return;
    const socket = new WebSocket(serviceWsUrl);
    this.#socket = socket;
    socket.onmessage = (event) => this.#applyPayload(JSON.parse(event.data));
    socket.onclose = () => {
      if (this.#socket === socket) this.#socket = null;
      if (this.#closed || this.#listeners.size === 0) return;
      this.#snapshot = {
        ...this.#snapshot,
        cameraState: "RECONNECTING",
        automaticActionsAllowed: false,
        postDecodeToGuiLatencyMs: null,
        currentStep: { event: "LIVE_SERVICE_RECONNECTING", state: "RECONNECTING" },
      };
      this.#emit();
      this.#retryTimer = window.setTimeout(() => this.#openSocket(), 1000);
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

const requestedMode = import.meta.env?.VITE_INSPECTION_MODE;
export const inspectionMode = requestedMode === "service" ? "service" : requestedMode === "live" ? "live" : "offline";
export const inspectionDataSource = inspectionMode === "service"
  ? new ServiceInspectionDataSource()
  : inspectionMode === "live"
    ? new LiveEvidenceInspectionDataSource()
    : new OfflineReplayInspectionDataSource();
