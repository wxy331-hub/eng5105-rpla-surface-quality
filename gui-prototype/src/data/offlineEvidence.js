import * as planA from "./planAOfflineEvidence.js";
import * as planB from "./week4OfflineEvidence.js";
import { createResolutionMetadata } from "../services/resolutionMetadata.js";

/** Each replay retains its own image files and recorded source identity. */
export function selectOfflineEvidence(profile = "plan_a") {
  if (profile === "plan_b") {
    return {
      ...planB,
      offlineFrames: [],
      offlineEvidenceSummary: {
        ...planB.offlineEvidenceSummary,
        ...createResolutionMetadata({ widthPx: 640, heightPx: 360, synthetic: true }),
        evidenceAssetsDirectory: "assets/week4",
        imageDescription: "Week 4 annotated output · ESP32S3 simulation",
        recordDescription: "Recorded offline candidate",
        timelineDescription: "Recorded connection and recovery simulation",
        physicalOutputsAllowed: false,
      },
    };
  }
  return planA;
}

export const offlineProfile = import.meta.env?.VITE_OFFLINE_PROFILE === "plan_b" ? "plan_b" : "plan_a";
const selected = selectOfflineEvidence(offlineProfile);
export const { offlineDetections, offlineEvidenceSummary, scenarioTimeline, offlineFrames } = selected;
export const resolveDisplayedEvidence = planB.resolveDisplayedEvidence;
