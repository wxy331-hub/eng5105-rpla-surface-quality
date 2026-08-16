export const offlineDetections = [
  {
    id: "DET-3349BECD33",
    batchId: "W4-OFFLINE-FAULT-001",
    cameraSource: "WEEK4_FAULT_INJECTION",
    frameId: 2,
    receivedAtUtc: "2026-08-02T09:19:55.814+00:00",
    type: "contamination_candidate",
    bboxPx: [360, 162, 52, 40],
    areaPx: 1542,
    algorithmScore: 0.935,
    grade: "Reject",
    algorithmVersion: "week4-roi-baseline-1",
    dataMode: "offline_fault_injection",
    imageFile: "frame_0002.jpg",
  },
  {
    id: "DET-EE95E17EC7",
    batchId: "W4-OFFLINE-FAULT-001",
    cameraSource: "WEEK4_FAULT_INJECTION",
    frameId: 5,
    receivedAtUtc: "2026-08-02T09:19:55.842+00:00",
    type: "scratch_candidate",
    bboxPx: [276, 157, 89, 47],
    areaPx: 662,
    algorithmScore: 0.716,
    grade: "Warning",
    algorithmVersion: "week4-roi-baseline-1",
    dataMode: "offline_fault_injection",
    imageFile: "frame_0005.jpg",
  },
  {
    id: "DET-4983DBD17B",
    batchId: "W4-OFFLINE-FAULT-001",
    cameraSource: "WEEK4_FAULT_INJECTION",
    frameId: 6,
    receivedAtUtc: "2026-08-02T09:19:55.854+00:00",
    type: "contamination_candidate",
    bboxPx: [360, 162, 52, 40],
    areaPx: 1542,
    algorithmScore: 0.935,
    grade: "Reject",
    algorithmVersion: "week4-roi-baseline-1",
    dataMode: "offline_fault_injection",
    imageFile: "frame_0006.jpg",
  },
];

export const scenarioTimeline = [
  { atS: 0.0, event: "CONNECT_REQUESTED", state: "CONNECTING", frameId: null, recoveryCount: 0, automaticActionsAllowed: false },
  { atS: 0.0, event: "VALID_FRAME", state: "CONNECTING", frameId: 0, recoveryCount: 1, automaticActionsAllowed: false },
  { atS: 0.1, event: "VALID_FRAME", state: "CONNECTING", frameId: 1, recoveryCount: 2, automaticActionsAllowed: false },
  { atS: 0.2, event: "VALID_FRAME", state: "HEALTHY", frameId: 2, recoveryCount: 3, automaticActionsAllowed: true },
  { atS: 1.3, event: "FRAME_TIMEOUT_STALE", state: "STALE", frameId: 2, recoveryCount: 0, automaticActionsAllowed: false },
  { atS: 2.3, event: "FRAME_TIMEOUT_DISCONNECTED", state: "DISCONNECTED", frameId: 2, recoveryCount: 0, automaticActionsAllowed: false },
  { atS: 2.4, event: "RECONNECT_ATTEMPT", state: "RECONNECTING", frameId: 2, recoveryCount: 0, automaticActionsAllowed: false },
  { atS: 2.6, event: "VALID_FRAME", state: "RECONNECTING", frameId: 3, recoveryCount: 1, automaticActionsAllowed: false },
  { atS: 2.7, event: "VALID_FRAME", state: "RECONNECTING", frameId: 4, recoveryCount: 2, automaticActionsAllowed: false },
  { atS: 2.8, event: "VALID_FRAME", state: "HEALTHY", frameId: 5, recoveryCount: 3, automaticActionsAllowed: true },
  { atS: 2.9, event: "VALID_FRAME", state: "HEALTHY", frameId: 6, recoveryCount: 3, automaticActionsAllowed: true },
];

export const offlineEvidenceSummary = {
  status: "PASS",
  evidenceLevel: "OFFLINE FAULT INJECTION ONLY",
  source: "PLAN B ADAPTER SIMULATION",
  batchId: "W4-OFFLINE-FAULT-001",
  resolution: "640 × 360",
  roiPx: [28, 140, 584, 80],
  framesGenerated: 7,
  framesProcessedWhenSafe: 3,
  framesBlockedDuringRecovery: 4,
  detectionsRecorded: 3,
  droppedFrames: 1,
  latestFrameCapacity: 1,
  staleAfterS: 1,
  disconnectAfterS: 2,
  recoveryFrames: 3,
  physicalMeasurementsAvailable: false,
  hardwarePerformanceVerified: false,
};

export function resolveDisplayedEvidence(snapshot, selectedDetection) {
  if (selectedDetection) {
    return {
      imageFile: selectedDetection.imageFile,
      ...(selectedDetection.imageUrl ? { imageUrl: selectedDetection.imageUrl } : {}),
      imageFrameNumber: selectedDetection.frameId,
      recordId: selectedDetection.id,
      isSelectedRecord: true,
    };
  }

  return {
    imageFile: snapshot.imageFile,
    ...(snapshot.imageUrl ? { imageUrl: snapshot.imageUrl } : {}),
    imageFrameNumber: snapshot.imageFrameNumber,
    recordId: null,
    isSelectedRecord: false,
  };
}
