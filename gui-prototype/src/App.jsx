import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alarm,
  Archive,
  ArrowsClockwise,
  Camera,
  CaretDown,
  Check,
  CircleNotch,
  Database,
  Eye,
  FileCsv,
  Gauge,
  Info,
  MagnifyingGlass,
  PlugsConnected,
  Ruler,
  Timer,
  Trash,
  Translate,
  Warning,
} from "@phosphor-icons/react";
import {
  offlineDetections,
  offlineEvidenceSummary,
  resolveDisplayedEvidence,
  scenarioTimeline,
} from "./data/offlineEvidence.js";
import { collapseCandidateEpisodes, inspectionDataSource, inspectionMode } from "./services/inspectionDataSource.js";
import { I18nProvider, useI18n } from "./i18n.jsx";
import Week7SamplePanel from "./Week7SamplePanel.jsx";
import GlassSurface from "./GlassSurface.jsx";
import { createResolutionMetadata } from "./services/resolutionMetadata.js";

const navItems = [
  { id: "live", label: "Live Inspection", icon: Camera },
  { id: "records", label: "Candidate Records", icon: Archive },
  { id: "health", label: "System Health", icon: Gauge },
];

const isLiveEvidence = inspectionMode !== "offline";
const isServiceMode = inspectionMode === "service";
const cameraStreamUrl = import.meta.env?.VITE_CAMERA_STREAM_URL?.trim() ?? "";

const healthDefinitions = [
  { key: "cameraState", label: "Camera state", icon: Camera },
  { key: "safetyGate", label: "Safety gate", icon: Warning },
  { key: "recovery", label: "Recovery frames", icon: ArrowsClockwise },
  { key: "buffer", label: "Frame buffer", icon: CircleNotch },
  { key: "dropped", label: "Backlog discarded", icon: Archive },
  { key: "evidence", label: "Evidence level", icon: Database },
];

function candidateLabel(value) {
  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function stateTone(state) {
  if (state === "HEALTHY") return "healthy";
  if (state === "DISCONNECTED") return "reject";
  return "warning";
}

// The static inspector located the specimen but did not judge this frame
// (for example out of focus), so neither "waiting for material" nor
// "no candidates" describes it.
function frameNotJudged(snapshot) {
  return snapshot.cameraState === "HEALTHY" && snapshot.targetPresent && Boolean(snapshot.viewInspection)
    && snapshot.viewInspection.geometry_status !== "valid";
}

// The outline could not verify focus (defocus, or a material whose edge
// images softly): the system declines to judge and hands over to a person.
function manualInspectionAdvised(snapshot) {
  return frameNotJudged(snapshot) && (snapshot.viewInspection.reason_codes ?? []).includes("FOCUS_UNVERIFIABLE");
}

// The demo roughness grade of the current frame, as text that follows the
// interface language (the banner on the image is English only).
const DEMO_GRADE_TEXT = {
  demo_good: "Surface roughness: good (demo thresholds, uncalibrated)",
  demo_moderately_rough: "Surface roughness: moderately rough (demo thresholds, uncalibrated)",
  demo_clearly_rough: "Surface roughness: clearly rough (demo thresholds, uncalibrated)",
};

function demoGradeText(snapshot) {
  return DEMO_GRADE_TEXT[snapshot.viewInspection?.surface?.quality_label] ?? null;
}

function stateDetail(snapshot, key, t) {
  const values = {
    cameraState: { value: t(snapshot.cameraState), meta: t("Event: {event}", { event: t(snapshot.currentStep.event) }) },
    safetyGate: {
      value: t(isServiceMode
        ? snapshot.automaticActionsAllowed ? "DETECTION ACTIVE" : frameNotJudged(snapshot) ? "FRAME NOT JUDGED" : snapshot.cameraState === "HEALTHY" ? "WAITING FOR MATERIAL" : "BLOCKED"
        : isLiveEvidence ? snapshot.cameraState : snapshot.automaticActionsAllowed ? "ENABLED" : "BLOCKED"),
      meta: t("Image processing only · no actuator output"),
    },
    recovery: {
      value: `${snapshot.recoveryCount} / ${snapshot.recoveryFrames}`,
      meta: t("Consecutive valid frames"),
    },
    buffer: { value: t("LATEST ONLY"), meta: t("Capacity: 1 frame") },
    dropped: {
      value: String(isServiceMode ? snapshot.droppedFrames : isLiveEvidence ? snapshot.warmupFramesSkipped ?? 0 : snapshot.droppedFrames),
      meta: t(isServiceMode ? "Live processing backlog" : isLiveEvidence ? "Connection stabilisation" : "Verified by offline test"),
    },
    evidence: {
      value: t(isServiceMode ? "CONTINUOUS SERVICE" : isLiveEvidence ? "Captured evidence" : "Saved simulation evidence"),
      meta: t(isServiceMode ? "Python API and WebSocket" : isLiveEvidence ? "Saved integration evidence" : "Hardware performance not verified"),
    },
  };
  return values[key];
}

function StatusDot({ tone = "healthy" }) {
  return <span className={`status-dot status-dot--${tone}`} aria-hidden="true" />;
}

function Panel({ className = "", children, ...props }) {
  return <section className={`panel ${className}`} {...props}>{children}</section>;
}

function PanelHeader({ title, meta, action }) {
  return (
    <div className="panel-header">
      <div>
        <h2>{title}</h2>
        {meta ? <p>{meta}</p> : null}
      </div>
      {action}
    </div>
  );
}

/**
 * A measured value the operator can lift into a log or a ticket. The press is
 * the whole affordance: the row sinks a pixel and the value inverts while it is
 * on the clipboard.
 */
/**
 * The async Clipboard API is unavailable whenever this GUI is opened over plain
 * http from another machine on the bench network, which is a normal way to use
 * it. Fall back to a selection copy there, and say so when neither path works —
 * a press that silently does nothing is worse than no affordance at all.
 */
function writeClipboard(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  return new Promise((resolve, reject) => {
    const carrier = document.createElement("textarea");
    carrier.value = text;
    carrier.setAttribute("readonly", "");
    carrier.style.cssText = "position:fixed;top:0;left:0;opacity:0;pointer-events:none";
    document.body.append(carrier);
    carrier.select();
    const ok = document.execCommand?.("copy");
    carrier.remove();
    return ok ? resolve() : reject(new Error("copy-unavailable"));
  });
}

function CopyRow({ icon: Icon, label, value, valueClassName = "" }) {
  const { t } = useI18n();
  const [state, setState] = useState("idle");
  const resetRef = useRef(null);

  useEffect(() => () => window.clearTimeout(resetRef.current), []);

  const settle = (next) => {
    setState(next);
    window.clearTimeout(resetRef.current);
    resetRef.current = window.setTimeout(() => setState("idle"), 900);
  };

  const copy = () => {
    writeClipboard(String(value)).then(() => settle("copied")).catch(() => settle("failed"));
  };

  const copied = state === "copied";
  const shown = copied ? t("Copied") : state === "failed" ? t("Copy blocked") : value;

  return (
    <div
      className={`copy-row ${copied ? "is-copied" : ""} ${state === "failed" ? "is-copy-failed" : ""}`}
      role="button"
      tabIndex={0}
      onClick={copy}
      onKeyDown={(event) => {
        if (!["Enter", " "].includes(event.key)) return;
        event.preventDefault();
        copy();
      }}
      aria-label={t("Copy {label}", { label })}
      title={t("Click to copy")}
    >
      <dt><Icon size={15} /> {label}</dt>
      <dd className={valueClassName}>{shown}</dd>
    </div>
  );
}

const HEARTBEAT_SAMPLES = 72;

/**
 * One bar per frame id this interface actually observed, newest at the right.
 * Bar height is the gap since the previous frame, so a stall shows as a spike
 * instead of being averaged away into a single rate. These are arrival times at
 * the GUI, not a camera-side measurement, and the caption says so.
 */
function FrameHeartbeat({ snapshot }) {
  const { t } = useI18n();
  const [gaps, setGaps] = useState([]);
  const lastRef = useRef({ frame: null, at: 0 });

  useEffect(() => {
    const frame = snapshot.frameNumber;
    if (!(snapshot.framesGenerated > 0 && snapshot.frameWidthPx > 0 && snapshot.frameHeightPx > 0)) return;
    if (frame == null || frame === lastRef.current.frame) return;
    const now = performance.now();
    const previousAt = lastRef.current.at;
    lastRef.current = { frame, at: now };
    if (!previousAt) return;
    setGaps((current) => [...current, now - previousAt].slice(-HEARTBEAT_SAMPLES));
  }, [snapshot.frameNumber, snapshot.framesGenerated, snapshot.frameWidthPx, snapshot.frameHeightPx]);

  const sorted = [...gaps].sort((left, right) => left - right);
  const median = sorted.length ? sorted[Math.floor(sorted.length / 2)] : 0;
  const ceiling = Math.max(median * 2.4, 1);

  return (
    <div className={`heartbeat ${gaps.length ? "" : "heartbeat--empty"}`}>
      <div className="heartbeat__track" aria-hidden="true">
        {gaps.map((gap, index) => (
          <i
            key={`${index}-${gap.toFixed(1)}`}
            className={`${gap > median * 1.8 ? "is-slow" : ""} ${index === gaps.length - 1 ? "is-latest" : ""}`}
            style={{ "--h": `${Math.min(100, Math.max(10, (gap / ceiling) * 100))}%` }}
          />
        ))}
      </div>
      <div className="heartbeat__legend">
        <span>{t("Frame arrivals at this interface · bar height is the gap since the previous frame")}</span>
        <span>{median ? <>{t("Median gap")} <b>{Math.round(median)} ms</b></> : t("Waiting for a second frame")}</span>
      </div>
    </div>
  );
}

/**
 * The screen shows what it does not know in the place the reading would have
 * been, rather than dropping the field. size_mm and position_mm stay null
 * without a calibration id, and that is a result worth displaying.
 */
function UnmeasuredFields() {
  const { t } = useI18n();
  return (
    <section className="unmeasured">
      <div className="unmeasured__caption"><span>{t("NOT MEASURED")}</span></div>
      <dl>
        <div className="unmeasured__row"><dt>{t("Size")}</dt><dd aria-label={t("No measurement")} /></div>
        <div className="unmeasured__row"><dt>{t("Sample position")}</dt><dd aria-label={t("No measurement")} /></div>
      </dl>
      <p className="unmeasured__reason">{t("Size and position require valid calibration.")}</p>
    </section>
  );
}

function LanguageSwitcher() {
  const { language, setLanguage, t } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const closeOnOutsideClick = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const selectLanguage = (nextLanguage) => {
    setLanguage(nextLanguage);
    setOpen(false);
  };

  return (
    <div className="language-switcher" ref={rootRef}>
      <button
        className="language-button"
        type="button"
        aria-label={t("Select language")}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Translate size={17} weight="bold" />
        <span>{language === "zh-CN" ? "中文" : "EN"}</span>
        <CaretDown size={12} weight="bold" />
      </button>
      {open ? (
        <GlassSurface className="language-menu" role="menu" aria-label={t("Language")}>
          <button type="button" role="menuitemradio" aria-checked={language === "en"} onClick={() => selectLanguage("en")}>
            <span>English</span>{language === "en" ? <Check size={16} weight="bold" /> : null}
          </button>
          <button type="button" role="menuitemradio" aria-checked={language === "zh-CN"} onClick={() => selectLanguage("zh-CN")}>
            <span>中文</span>{language === "zh-CN" ? <Check size={16} weight="bold" /> : null}
          </button>
        </GlassSurface>
      ) : null}
    </div>
  );
}

function TopBar({ snapshot }) {
  const { t } = useI18n();
  const tone = stateTone(snapshot.cameraState);
  return (
    <header className="topbar">
      <div className="topbar__title">
        <p>{t("ENG5105 · MACHINE VISION DEMONSTRATOR")}</p>
        <h1>{t("rPLA Surface Quality Monitor")}</h1>
      </div>
      <div className="topbar__actions">
        <span className="source-badge"><Camera size={17} weight="fill" /> {t(snapshot.source)}</span>
        <span className="demo-badge"><Info size={15} weight="bold" /> {t(snapshot.mode)}</span>
        <span className={`connection-state connection-state--${tone}`}><StatusDot tone={tone} /> {isLiveEvidence ? t(snapshot.cameraState) : t("Simulation: {state}", { state: t(snapshot.cameraState) })}</span>
        <span className="batch-id">{t("Batch")} {t(snapshot.batchId)}</span>
        <LanguageSwitcher />
      </div>
    </header>
  );
}

function Sidebar({ activeView, setActiveView, snapshot }) {
  const { t } = useI18n();
  const tone = stateTone(snapshot.cameraState);
  return (
    <aside className="sidebar">
      <div className="brand-mark" aria-label={t("rPLA vision system")}>
        <Eye size={29} weight="duotone" />
        <span>RV</span>
      </div>
      <nav
        aria-label={t("Primary navigation")}
        style={{ "--nav-index": Math.max(0, navItems.findIndex((item) => item.id === activeView)) }}
      >
        <span className="nav-indicator" aria-hidden="true" />
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-item ${activeView === id ? "nav-item--active" : ""}`}
            onClick={() => setActiveView(id)}
            aria-current={activeView === id ? "page" : undefined}
            aria-label={t(label)}
            title={t(label)}
          >
            <Icon size={23} weight={activeView === id ? "fill" : "regular"} />
            <span>{t(isLiveEvidence && id === "records" ? "Candidate Records" : label)}</span>
          </button>
        ))}
        <a
          href="#sample-capture"
          className="nav-item"
          aria-label={t("Sample capture")}
          title={t("Sample capture")}
          style={{ textDecoration: "none" }}
        >
          <Camera size={23} weight="duotone" />
          <span>{t("Sample capture")}</span>
        </a>
      </nav>
      <div className="sidebar__footer">
        <StatusDot tone={tone} />
        <div>
          <strong>{t(isServiceMode ? "Live detection active" : isLiveEvidence ? "Captured evidence active" : "Offline replay active")}</strong>
          <span>{t(isServiceMode ? "Python service · WebSocket" : isLiveEvidence ? "OV3660 integration snapshot" : "No physical hardware connected")}</span>
        </div>
      </div>
    </aside>
  );
}

function LiveCamera({ snapshot, selectedDetection, onReplay }) {
  const { t } = useI18n();
  const cameraRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState("");
  const [streamRevision, setStreamRevision] = useState(0);
  const [streamFailed, setStreamFailed] = useState(false);
  useEffect(() => {
    const updateFullscreen = () => setIsFullscreen(document.fullscreenElement === cameraRef.current);
    document.addEventListener("fullscreenchange", updateFullscreen);
    return () => document.removeEventListener("fullscreenchange", updateFullscreen);
  }, []);

  const toggleFullscreen = async () => {
    setFullscreenError("");
    const camera = cameraRef.current;
    if (!camera?.requestFullscreen || !document.exitFullscreen) {
      setFullscreenError("Fullscreen view is unavailable in this browser.");
      return;
    }
    try {
      if (document.fullscreenElement === camera) await document.exitFullscreen();
      else await camera.requestFullscreen();
    } catch {
      setFullscreenError("Could not change fullscreen view. Please try again.");
    }
  };
  // Size the stage to the frame the sensor actually delivers, so the picture
  // fills its box instead of being letterboxed inside a decorative widescreen
  // band. Read from the decoded image rather than a declared resolution string,
  // which keeps it right for every source.
  const [frameAspect, setFrameAspect] = useState(() => {
    const width = selectedDetection?.frameWidthPx ?? snapshot.frameWidthPx;
    const height = selectedDetection?.frameHeightPx ?? snapshot.frameHeightPx;
    return width > 0 && height > 0 ? `${width} / ${height}` : null;
  });
  const [decodedImage, setDecodedImage] = useState(null);
  const [failedImage, setFailedImage] = useState(null);
  useEffect(() => {
    if (isServiceMode && snapshot.currentFrameAvailable) {
      setStreamFailed(false);
      setStreamRevision((value) => value + 1);
    }
  }, [snapshot.currentFrameAvailable]);
  const blocked = !snapshot.automaticActionsAllowed;
  const tone = stateTone(snapshot.cameraState);
  const displayedEvidence = resolveDisplayedEvidence(snapshot, selectedDetection);
  const evidenceImageUrl = displayedEvidence.imageUrl ?? (displayedEvidence.imageFile ? `${import.meta.env.BASE_URL}${snapshot.evidenceAssetsDirectory ?? "assets/week4"}/${displayedEvidence.imageFile}` : null);
  const streamUrl = isServiceMode ? snapshot.streamUrl ?? "" : cameraStreamUrl;
  const directStreamConfigured = isLiveEvidence && !selectedDetection && Boolean(streamUrl);
  const directStreamActive = directStreamConfigured && !streamFailed;
  const separator = streamUrl.includes("?") ? "&" : "?";
  const directStreamUrl = `${streamUrl}${separator}session=${streamRevision}`;
  const imageUrl = directStreamActive ? directStreamUrl
    : isServiceMode && !selectedDetection && streamFailed ? null : evidenceImageUrl;
  // Requested capture modes never substitute for decoded image dimensions.
  const displayedResolution = decodedImage?.url === imageUrl && failedImage !== imageUrl
    ? decodedImage.resolution
    : t("Waiting for frame");

  const refreshCamera = () => {
    setStreamFailed(false);
    setStreamRevision(Date.now());
    onReplay();
  };
  return (
    <Panel className="camera-card" id="inspection-camera" ref={cameraRef}>
      <PanelHeader
        title={t(directStreamActive ? "Live inspection camera" : isLiveEvidence ? "Inspection camera evidence" : "Inspection evidence replay")}
        meta={t(isLiveEvidence ? snapshot.cameraPathLabel : snapshot.imageDescription)}
        action={<span className="resolution">{t(isLiveEvidence ? "Displayed image" : "Synthetic image")}<b>{displayedResolution} {decodedImage?.url === imageUrl ? "px" : ""}</b></span>}
      />
      {snapshot.requestedResolution ? <div className="capture-request"><span>{t("Requested camera mode")}</span><b>{snapshot.requestedResolution} · {snapshot.requestedPixelFormat} · {snapshot.requestedFps} FPS</b><span>{t("Hardware verification pending")}</span></div> : null}
      {/* Readouts live on the matte, never on top of the picture: nothing should
          sit over pixels an operator is being asked to judge. */}
      <div className={`camera-stage ${blocked && !displayedEvidence.isSelectedRecord ? "camera-stage--blocked" : ""}`}>
        <div className="camera-stage__rail">
          <div className={`live-pill ${displayedEvidence.isSelectedRecord ? "live-pill--selected" : ""}`}>
            <StatusDot tone={displayedEvidence.isSelectedRecord ? "warning" : tone} />
            {t(displayedEvidence.isSelectedRecord ? "SELECTED RECORD" : directStreamActive ? "LIVE CAMERA" : isLiveEvidence ? "INSPECTION CAPTURE" : "OFFLINE REPLAY")}
          </div>
          <div className="frame-number">{directStreamActive ? <>{t("Reported frame")} {snapshot.frameNumber}</> : <>{t(isLiveEvidence ? "CAPTURED FRAME" : "SAVED FRAME")} {displayedEvidence.imageFrameNumber}</>}</div>
        </div>
        <div className="camera-stage__viewport">
          <div className="camera-stage__frame" style={frameAspect ? { "--frame-aspect": frameAspect } : undefined}>
            {imageUrl
              ? <img
                  key={`${imageUrl}:${streamRevision}`}
                  className={directStreamActive ? "camera-stream" : undefined}
                  src={imageUrl}
                  alt={t(directStreamActive ? "Live {source} inspection stream" : "Saved {source} image from frame {frame}",
                  { source: t(snapshot.source), frame: displayedEvidence.imageFrameNumber })}
                  onLoad={(event) => {
                    const { naturalWidth, naturalHeight } = event.currentTarget;
                    if (naturalWidth && naturalHeight) {
                      setFrameAspect(`${naturalWidth} / ${naturalHeight}`);
                      setDecodedImage({ url: imageUrl, ...createResolutionMetadata({ widthPx: naturalWidth, heightPx: naturalHeight }) });
                      setFailedImage(null);
                    }
                  }}
                  onError={() => { setFailedImage(imageUrl); if (directStreamActive) setStreamFailed(true); }}
                />
              : <div className="camera-loading"><Camera size={28} /> {t(isServiceMode ? snapshot.serviceAvailable ? "Verify the configured camera is connected, then reconnect the camera stream." : "Connect the camera and start the local camera service, then retry." : "Loading captured evidence")}</div>}
          </div>
        </div>
        {imageUrl && failedImage === imageUrl ? <div className="frame-notice" role="alert">{t("Image unavailable. Retry loading the evidence.")}</div> : null}
        {isServiceMode && snapshot.loadError ? <div className="frame-notice" role="alert">{snapshot.loadError}</div> : null}
        {blocked && !displayedEvidence.isSelectedRecord ? <div className="frame-notice"><Warning size={17} /> {t(isServiceMode && frameNotJudged(snapshot) ? "FRAME NOT JUDGED" : isServiceMode && snapshot.cameraState === "HEALTHY" ? "WAITING FOR MATERIAL" : "PROCESSING HOLD")} · {t(snapshot.cameraState)}{isServiceMode && manualInspectionAdvised(snapshot) ? <> · {t("Manual inspection recommended")}</> : null}</div> : null}
        {isServiceMode && !displayedEvidence.isSelectedRecord && demoGradeText(snapshot) ? <div className="frame-notice" role="status">{t(demoGradeText(snapshot))}</div> : null}
        <div className="camera-stage__footer">
          <span>ROI: {snapshot.roiPx.join(", ")} px</span>
          <span>{displayedEvidence.isSelectedRecord
            ? t("Selected record: {id}", { id: displayedEvidence.recordId })
            : t(directStreamActive ? isServiceMode ? "Shared processed MJPEG stream" : "Direct MJPEG stream" : isLiveEvidence ? "Latest annotated image only" : "Pixel coordinates · x, y, width, height")}</span>
        </div>
      </div>
      {isServiceMode ? <FrameHeartbeat snapshot={snapshot} /> : null}
      {fullscreenError ? <div className="frame-notice" role="alert">{t(fullscreenError)}</div> : null}
      <div className="camera-controls">
        <button className="button button--secondary camera-fullscreen-button" type="button" onClick={toggleFullscreen} aria-controls="inspection-camera" aria-pressed={isFullscreen}>
          {t(isFullscreen ? "Exit fullscreen" : "Fullscreen view")}
        </button>
        <button className="button button--secondary" type="button" onClick={refreshCamera}>
          <ArrowsClockwise size={16} /> {t(isServiceMode || directStreamConfigured ? "Reconnect camera stream" : isLiveEvidence ? "Refresh captured evidence" : displayedEvidence.isSelectedRecord ? "Return to fault replay" : "Replay fault scenario")}
        </button>
        <span><CircleNotch size={15} /> {directStreamActive
          ? t(isServiceMode ? "Live camera · detections update over WebSocket" : "Direct camera feed · saved evidence updates separately")
          : isServiceMode && !snapshot.currentFrameAvailable
          ? t("Waiting for a stable image source.")
          : isLiveEvidence
          ? t("Captured run · frame {frame}", { frame: displayedEvidence.imageFrameNumber })
          : displayedEvidence.isSelectedRecord
          ? t("Viewing saved evidence frame {frame}", { frame: displayedEvidence.imageFrameNumber })
          : t("Step {current} of {total} · scenario frame {frame}", { current: snapshot.currentStepIndex + 1, total: scenarioTimeline.length, frame: snapshot.frameNumber })}</span>
        <span><Warning size={15} /> {t("Image processing {state}", { state: t((snapshot.candidateProcessingAllowed ?? snapshot.automaticActionsAllowed) ? "enabled" : "blocked") })}</span>
        <span className="demo-control-note"><Info size={15} /> {t(isLiveEvidence ? "Integration evidence only · no actuator output" : "Test replay only · no hardware output")}</span>
      </div>
    </Panel>
  );
}

function LatestDetection({ detection, snapshot, selected = false }) {
  const { t } = useI18n();
  const physicalMeasurementsAvailable = snapshot?.physicalMeasurementsAvailable === true;
  if (!detection) {
    return (
      <Panel className="quality-card quality-card--empty">
        <PanelHeader title={t(isLiveEvidence ? "Latest candidate event" : "Latest candidate")} meta={t(isLiveEvidence ? "Inspection event" : snapshot.recordDescription)} />
        <div className="empty-candidate">
          <CircleNotch size={35} />
          <strong>{t("No candidate recorded at this step")}</strong>
          <span>{t(snapshot.cameraState !== "HEALTHY" ? "Waiting for a stable image source." : frameNotJudged(snapshot) ? "The specimen is in view but this frame was not judged; see the reason on the image." : snapshot.automaticActionsAllowed ? "No candidate in the current processed frame." : isServiceMode ? "Place material inside the configured ROI to begin detection." : "The replay safety gate is holding image processing.")}</span>
        </div>
        {!physicalMeasurementsAvailable ? <UnmeasuredFields /> : null}
      </Panel>
    );
  }

  const tone = "evidence";
  return (
    <Panel className="quality-card">
      <PanelHeader title={t(selected ? "Selected candidate" : isLiveEvidence ? "Latest candidate event" : "Current frame candidate")} meta={t(isLiveEvidence ? "Inspection event" : snapshot.recordDescription)} />
      <div className={`quality-banner quality-banner--${tone}`}>
        <Warning size={34} weight="fill" />
        <div>
          <span>{t("CANDIDATE DETECTED")}</span>
          {!isLiveEvidence ? <small>{t("Synthetic image candidate")}</small> : null}
        </div>
      </div>
      <dl className="defect-details">
        <CopyRow icon={Alarm} label={t("Candidate type")} value={t(candidateLabel(detection.type))} valueClassName="text-critical" />
        <CopyRow icon={Ruler} label={t("BBox · x, y, w, h")} value={`${detection.bboxPx.join(", ")} px`} />
        <CopyRow icon={Gauge} label={t("Area")} value={`${detection.areaPx} px²`} />
        <CopyRow icon={PlugsConnected} label={t("Ranking score")} value={detection.algorithmScore.toFixed(3)} />
        <CopyRow icon={Camera} label={t("Frame ID")} value={detection.frameId} />
        <CopyRow icon={Database} label={t("Record ID")} value={detection.id} />
      </dl>
      <p className="candidate-explanation">{t("Area-derived score; not a defect probability. Physical output is disabled.")}</p>
      {physicalMeasurementsAvailable ? null : <UnmeasuredFields />}
    </Panel>
  );
}

function KpiRow({ snapshot, eventCount }) {
  const { t } = useI18n();
  const definitions = [
    { key: "cameraState", label: "Connection state", icon: Camera },
    { key: "fps", label: "Measured pipeline rate", icon: Timer },
    { key: "events", label: "Candidate events", icon: Archive },
    { key: "latency", label: "Frame telemetry latency", icon: Timer },
  ];
  const values = {
    cameraState: t(snapshot.cameraState),
    safety: t(snapshot.automaticActionsAllowed ? "ENABLED" : "BLOCKED"),
    recovery: `${snapshot.recoveryCount}/${snapshot.recoveryFrames}`,
    processed: `${snapshot.framesProcessedWhenSafe}/${snapshot.framesGenerated}`,
    inspection: String(snapshot.inspectionFrames ?? 0),
    dropped: String(snapshot.droppedFrames),
    fps: `${snapshot.measuredFps?.toFixed(2) ?? "—"} FPS`,
    received: String(snapshot.framesGenerated),
    warmup: String(snapshot.warmupFramesSkipped ?? 0),
    events: String(eventCount),
    latency: snapshot.postDecodeToGuiLatencyMs == null ? "-- ms" : `${snapshot.postDecodeToGuiLatencyMs} ms`,
  };
  return (
    <GlassSurface className="kpi-surface">
      <section className="kpi-grid" aria-label={t(isLiveEvidence ? "Live integration metrics" : "Verified offline state metrics")}>
        {definitions.map(({ key, label, icon: Icon }) => (
          <article className="kpi-card" key={key}>
            <Icon size={34} weight="duotone" />
            <div><span>{t(label)}</span><strong>{values[key]}</strong></div>
          </article>
        ))}
      </section>
    </GlassSurface>
  );
}

function SampleWorkflowSummary({ snapshot }) {
  const { t } = useI18n();
  return (
    <Panel className="sample-workflow-card">
      <PanelHeader title={t("Sample workflow")} meta={t(snapshot.cameraPathLabel)} />
      <p>{t("Hold the specimen still. Index six angles manually; capture one lighting view at a time.")}</p>
      <div className="sample-workflow-views"><b>6 × 2</b><span>{t("12 views per sample")}</span></div>
      <a className="button button--primary" href="#sample-capture"><Camera size={17} />{t("Open sample capture")}</a>
    </Panel>
  );
}

function ConnectionTimeline({ currentStepIndex }) {
  const { t } = useI18n();
  return (
    <Panel className="timeline-card">
      <PanelHeader title={t("Connection fault timeline")} meta={t(offlineEvidenceSummary.timelineDescription)} />
      <p className="timeline-clock-note">{t("Scenario clock · not a camera frame rate")}</p>
      <div className="timeline-track" aria-label={t("Connection state timeline")}>
        {scenarioTimeline.map((step, index) => {
          const current = index === currentStepIndex;
          const complete = index < currentStepIndex;
          return (
            <article aria-current={current ? "step" : undefined} className={`timeline-step ${current ? "is-current" : ""} ${complete ? "is-complete" : ""}`} key={`${step.event}-${index}`}>
              <div className="timeline-step__marker"><span>{index + 1}</span></div>
              <small>+{step.atS.toFixed(1)} s</small>
              <strong>{t(step.state)}</strong>
              <span>{t(step.event)}</span>
            </article>
          );
        })}
      </div>
    </Panel>
  );
}

function CandidateTable({ events, onSelect, onDelete, selectedId, large = false }) {
  const { t } = useI18n();
  return (
    <div className={`table-wrap ${large ? "table-wrap--large" : ""}`}>
      <table>
        <thead><tr>{large ? <><th>{t("Record ID")}</th><th>{t(isLiveEvidence ? "UTC time" : "Simulation time (UTC)")}</th></> : null}<th>{t(isLiveEvidence ? "Frame range" : "Frame")}</th>{isLiveEvidence ? <th>{t("Evidence frames")}</th> : null}<th>{t("Candidate type")}</th><th>{t("BBox · x, y, w, h (px)")}</th><th>{t("Area (px²)")}</th><th>{t("Ranking score")}</th>{onDelete ? <th className="actions-column">{t("Actions")}</th> : null}</tr></thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.recordIds?.[0] ?? event.id}
              className={onSelect ? `selectable-row ${event.id === selectedId ? "is-selected" : ""}` : ""}
              onClick={() => onSelect?.(event)}
            >
              {large ? <><td className="mono">{event.id}</td><td className="mono">{event.receivedAtUtc.slice(11, 23)}</td></> : null}
              <td className="mono">{onSelect ? <button type="button" className="event-select" aria-pressed={event.id === selectedId} aria-label={t("View record {id}, frame {frame}", { id: event.id, frame: event.frameId })} onClick={(clickEvent) => { clickEvent.stopPropagation(); onSelect(event); }}>{event.frameId}<Eye size={15} /></button> : isLiveEvidence ? event.frameLabel : event.frameId}</td>
              {isLiveEvidence ? <td className="mono">{event.occurrences}</td> : null}
              <td>{t(candidateLabel(event.type))}</td>
              <td className="mono">{event.bboxPx.join(", ")}</td>
              <td className="mono">{event.areaPx}</td>
              <td className="mono">{event.algorithmScore.toFixed(3)}</td>
              {onDelete ? <td className="actions-cell"><button className="delete-record-button" type="button" onClick={(clickEvent) => { clickEvent.stopPropagation(); onDelete(event); }} aria-label={t("Delete candidate event {id}", { id: event.id })} title={t("Delete recorded event")}><Trash size={15} /><span>{t("Delete")}</span></button></td> : null}
            </tr>
          ))}
          {!events.length ? <tr><td className="table-empty" colSpan={5 + (large ? 2 : 0) + (isLiveEvidence ? 1 : 0) + (onDelete ? 1 : 0)}>{t("No matching candidates. Try another search or filter.")}</td></tr> : null}
        </tbody>
      </table>
    </div>
  );
}

function RecentCandidates({ events, rawCount, selectedId, onSelect, onDelete, onClear }) {
  const { t } = useI18n();
  const visibleEvents = isLiveEvidence ? events.slice(-6).reverse() : events;
  return (
    <Panel className="events-card">
      <PanelHeader title={t(isLiveEvidence ? "Detected candidate events" : "Recorded candidates")} meta={t(isLiveEvidence ? "{events} events from {frames} evidence frames" : "{count} recorded offline candidates", { events: events.length, frames: rawCount, count: events.length })} action={onClear ? <button className="button button--danger clear-records-button" type="button" onClick={onClear} disabled={!rawCount}><Trash size={16} /><span>{t("Clear records")}</span></button> : null} />
      <CandidateTable events={visibleEvents} selectedId={selectedId} onSelect={isLiveEvidence ? undefined : onSelect} onDelete={onDelete} />
      {!isLiveEvidence ? <p className="candidate-explanation">{t("Select a frame to inspect its saved image. Scores rank candidate regions.")}</p> : null}
    </Panel>
  );
}

function LiveView({ snapshot, events, rawEventCount, selectedEvent, setSelectedEvent, onReplay, onDelete, onClear }) {
  const detection = selectedEvent ?? (isLiveEvidence ? events.at(-1) : snapshot.currentDetection);
  return (
    <div className="dashboard-view view-enter">
      {isLiveEvidence ? <KpiRow snapshot={snapshot} eventCount={events.length} /> : null}
      <LiveCamera snapshot={snapshot} selectedDetection={selectedEvent} onReplay={onReplay} />
      <div className="inspection-sidebar">
        <LatestDetection detection={detection} snapshot={snapshot} selected={Boolean(selectedEvent)} />
        {!isLiveEvidence ? <SampleWorkflowSummary snapshot={snapshot} /> : null}
      </div>
      <RecentCandidates events={events} rawCount={rawEventCount} selectedId={selectedEvent?.id} onSelect={setSelectedEvent} onDelete={onDelete} onClear={onClear} />
    </div>
  );
}

function RecordsView({ events, rawCount, snapshot, onExport, onDelete, onClear, onInspect }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [candidateType, setCandidateType] = useState("");
  const filtered = events.filter((event) => {
    const matchesQuery = `${event.id} ${event.type} ${t(candidateLabel(event.type))} ${event.frameId}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (!candidateType || event.type === candidateType);
  });

  return (
    <div className="secondary-view view-enter">
      <div className="page-heading">
        <div><p>{t(isLiveEvidence ? "INSPECTION EVENT LOG" : "TRACEABLE OFFLINE EVENT LOG")}</p><h2>{t("Candidate Records")}</h2><span>{isLiveEvidence ? t("{events} events from {frames} evidence frames · Batch {batch}", { events: events.length, frames: rawCount, batch: snapshot.batchId }) : t("{source} · Batch {batch}", { source: t(snapshot.source), batch: snapshot.batchId })}</span></div>
        <div className="page-heading__actions">{onClear ? <button className="button button--danger" onClick={onClear} type="button" disabled={!rawCount}><Trash size={18} /> {t("Clear records")}</button> : null}<button className="button button--secondary" onClick={onExport} type="button"><FileCsv size={19} /> {t("Export evidence CSV")}</button></div>
      </div>
      <Panel className="records-panel">
        <div className="filter-bar">
          <label><MagnifyingGlass size={18} /><input aria-label={t("Search candidate records")} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Search record, frame or candidate")} /></label>
          <select value={candidateType} onChange={(event) => setCandidateType(event.target.value)} aria-label={t("Filter by candidate type")}><option value="">{t("All candidate types")}</option>{[...new Set(events.map(event => event.type))].map(type => <option key={type} value={type}>{t(candidateLabel(type))}</option>)}</select>
          <span>{t(isLiveEvidence ? "{count} candidate events" : "{count} saved candidates", { count: filtered.length })}</span>
        </div>
        <CandidateTable events={filtered} large onDelete={onDelete} onSelect={isLiveEvidence ? undefined : onInspect} />
        {!isLiveEvidence ? <div className="records-note"><Info size={18} /><span>{t("Physical dimensions and sample position require valid camera and fixture calibration.")}</span></div> : null}
      </Panel>
    </div>
  );
}

function HealthView({ snapshot }) {
  const { t } = useI18n();
  const connectionTone = stateTone(snapshot.cameraState);
  const primaryDefinitions = healthDefinitions.filter(({ key }) => ["cameraState", "safetyGate", "evidence"].includes(key));
  const technicalDetails = [
    [t("Source"), t(snapshot.source)],
    [t("Camera path"), t(snapshot.cameraPathLabel ?? "Camera path unavailable")],
    [t(isLiveEvidence ? "Decoded frame" : "Synthetic image"), t(snapshot.resolution)],
    ["ROI", `${snapshot.roiPx.join(", ")} px`],
    [t("Recovery frames"), `${snapshot.recoveryCount} / ${snapshot.recoveryFrames}`],
    [t("Buffer policy"), t("Latest frame only")],
    [t("Backlog discarded"), String(snapshot.droppedFrames ?? 0)],
    [t("Safely processed"), `${snapshot.framesProcessedWhenSafe} / ${snapshot.framesGenerated}`],
    [t("Physical output"), t("Disabled")],
    [t("Calibration"), snapshot.calibrationId ?? t("Not calibrated")],
    [t("Evidence level"), snapshot.evidenceCode ?? snapshot.evidenceLevel],
  ];
  return (
    <div className="secondary-view view-enter">
      <div className="page-heading">
        <div><p>{t(isLiveEvidence ? "INSPECTION SYSTEM STATUS" : "SIMULATION & DIAGNOSTICS")}</p><h2>{t("System Health")}</h2><span>{t(isLiveEvidence ? "Camera, processing and storage status" : "Recorded software simulation states")}</span></div>
        <span className={`connection-state connection-state--${connectionTone}`}><StatusDot tone={connectionTone} /> {isServiceMode
          ? t("{source} · {state}", { source: t(snapshot.source), state: t(snapshot.cameraState) })
          : t(isLiveEvidence ? "Saved integration evidence" : "Hardware not connected")}</span>
      </div>
      <div className="health-overview-grid">
        {primaryDefinitions.map(({ key, icon: Icon }) => {
          const detail = stateDetail(snapshot, key, t);
          const visibleLabel = key === "cameraState" ? isLiveEvidence ? "Camera" : "Simulated camera" : key === "safetyGate" ? "Image processing" : "Evidence archive";
          const visibleDetail = key === "evidence"
            ? { value: detail.value, meta: t(isServiceMode ? "API, WebSocket and SQLite" : "Saved images and evidence manifest") }
            : detail;
          const tone = key === "cameraState"
            ? stateTone(snapshot.cameraState)
            : key === "safetyGate" && !snapshot.automaticActionsAllowed ? "warning"
            : key === "evidence" && !isLiveEvidence ? "warning"
            : "healthy";
          return (
            <Panel className={`health-overview-card health-overview-card--${tone}`} key={key}>
              <Icon size={36} weight="duotone" />
              <div>
                <span>{t(visibleLabel)}</span>
                <strong>{visibleDetail.value}</strong>
                <small><StatusDot tone={tone} /> {visibleDetail.meta}</small>
              </div>
            </Panel>
          );
        })}
      </div>
      <Panel className="capture-configuration">
        <PanelHeader title={t("Camera configuration")} meta={t(snapshot.cameraPathLabel)} />
        <dl>
          <div><dt>{t(isLiveEvidence ? "Decoded frame" : "Synthetic image")}</dt><dd>{t(snapshot.resolution)}<small>{t("Actual image pixels")}</small></dd></div>
          <div><dt>{t("Requested camera mode")}</dt><dd>{snapshot.requestedResolution ?? t("Not specified")}<small>{snapshot.requestedResolution ? `${snapshot.requestedPixelFormat} · ${snapshot.requestedFps} FPS · ${t("Hardware verification pending")}` : t("Read-only source configuration")}</small></dd></div>
          <div><dt>{t("Physical measurements")}</dt><dd>{t("Not calibrated")}<small>{t("Size and position require valid calibration.")}</small></dd></div>
        </dl>
      </Panel>
      {!isLiveEvidence ? <ConnectionTimeline currentStepIndex={snapshot.currentStepIndex} /> : null}
      <Panel className="safety-policy-panel">
        <PanelHeader title={t("Safety policy")} meta={t(isLiveEvidence ? "System protection rules" : "Verified prototype behaviour")} />
        <div className="policy-grid">
          <article><Warning size={24} /><div><strong>{t("Camera connection loss")}</strong><span>{t("Image processing and all automatic outputs enter a blocked state.")}</span></div></article>
          <article><ArrowsClockwise size={24} /><div><strong>{t("Controlled recovery")}</strong><span>{t("Three consecutive valid frames are required before processing resumes.")}</span></div></article>
          <article><Database size={24} /><div><strong>{t("Local-first evidence")}</strong><span>{t(isLiveEvidence ? "Connection events and candidate records are stored in SQLite." : "Saved images, candidate records and connection events remain traceable in the evidence archive.")}</span></div></article>
        </div>
      </Panel>
      <details className="panel technical-details">
        <summary>
          <div><strong>{t("Technical details")}</strong><span>{t("Secondary engineering diagnostics")}</span></div>
          <CaretDown size={18} weight="bold" />
        </summary>
        <dl className="technical-details-grid">
          {technicalDetails.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
        </dl>
      </details>
      {!isLiveEvidence ? <Panel className="evidence-callout">
        <Info size={24} weight="fill" />
        <div><strong>{t("Evidence boundary")}</strong><span>{t("Synthetic images and simulated connection states. Camera, lighting, fixture positioning and physical measurements require hardware validation and calibration. Physical outputs remain blocked.")}</span></div>
      </Panel> : null}
    </div>
  );
}

function exportCsv(events, snapshot) {
  const header = ["detection_id", "batch_id", "camera_source", "frame_id", "received_at_utc", "candidate_type", "bbox_px", "area_px", "algorithm_score", "prototype_grade", "algorithm_version", "data_mode"];
  header.push("evidence_level", "image_file", "calibration_id", "physical_outputs_allowed");
  const rows = events.map((event) => [event.id, event.batchId, event.cameraSource, event.frameId, event.receivedAtUtc, event.type, event.bboxPx.join(" "), event.areaPx, event.algorithmScore, event.grade.toLowerCase(), event.algorithmVersion, event.dataMode, snapshot.evidenceCode ?? snapshot.evidenceLevel, !isLiveEvidence && event.imageFile ? `${snapshot.evidenceAssetsDirectory}/${event.imageFile}` : "", snapshot.calibrationId ?? "", false]);
  const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = isLiveEvidence ? "inspection-candidate-evidence.csv" : "offline-candidate-evidence.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function AppContent() {
  const { t } = useI18n();
  const viewFromHash = () => ({ "#records": "records", "#health": "health" }[window.location.hash] ?? "live");
  const [activeView, setActiveView] = useState(viewFromHash);
  const navigateView = (view) => { window.location.hash = view === "live" ? "inspection" : view; setActiveView(view); };
  const [snapshot, setSnapshot] = useState(() => inspectionDataSource.getSnapshot());
  const [events, setEvents] = useState(() => isLiveEvidence ? [] : offlineDetections);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const displayEvents = useMemo(() => isLiveEvidence ? collapseCandidateEpisodes(events) : events, [events]);
  useEffect(() => {
    const updateView = () => setActiveView(viewFromHash());
    window.addEventListener("hashchange", updateView);
    return () => window.removeEventListener("hashchange", updateView);
  }, []);

  useEffect(() => inspectionDataSource.subscribe((nextSnapshot) => {
    setSnapshot(nextSnapshot);
    if (nextSnapshot.defects) setEvents(nextSnapshot.defects);
  }), []);

  const replay = () => {
    setSelectedEvent(null);
    inspectionDataSource.replayScenario();
  };

  const deleteCandidateEvent = isServiceMode ? async (candidateEvent) => {
    const recordIds = candidateEvent.recordIds?.length ? candidateEvent.recordIds : [candidateEvent.id];
    if (!window.confirm(t("Delete this candidate event and its {count} stored record(s)? This cannot be undone.", { count: recordIds.length }))) return;
    try {
      await inspectionDataSource.deleteDefects(recordIds);
      if (selectedEvent?.id === candidateEvent.id) setSelectedEvent(null);
    } catch (error) {
      window.alert(t("Could not delete the candidate event: {message}", { message: error.message }));
    }
  } : undefined;

  const clearCandidateEvents = isServiceMode ? async () => {
    if (!events.length || !window.confirm(t("Clear all {count} stored candidate records? This cannot be undone.", { count: events.length }))) return;
    try {
      await inspectionDataSource.deleteDefects(events.map((event) => event.id));
      setSelectedEvent(null);
    } catch (error) {
      window.alert(t("Could not clear candidate records: {message}", { message: error.message }));
    }
  } : undefined;

  const page = useMemo(() => {
    if (activeView === "records") return <RecordsView events={displayEvents} rawCount={events.length} snapshot={snapshot} onExport={() => exportCsv(events, snapshot)} onDelete={deleteCandidateEvent} onClear={clearCandidateEvents} onInspect={(event) => { setSelectedEvent(event); navigateView("live"); }} />;
    if (activeView === "health") return <HealthView snapshot={snapshot} />;
    return <LiveView snapshot={snapshot} events={displayEvents} rawEventCount={events.length} selectedEvent={selectedEvent} setSelectedEvent={setSelectedEvent} onReplay={replay} onDelete={deleteCandidateEvent} onClear={clearCandidateEvents} />;
  }, [activeView, displayEvents, events, selectedEvent, snapshot]);

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} setActiveView={navigateView} snapshot={snapshot} />
      <div className="workspace">
        <TopBar snapshot={snapshot} />
        <main className="main-content">{page}</main>
      </div>
    </div>
  );
}

export function App() {
  const [route, setRoute] = useState(() => window.location.hash);

  useEffect(() => {
    const onHashChange = () => setRoute(window.location.hash);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return <I18nProvider>{route === "#sample-capture" ? <Week7SamplePanel /> : <AppContent />}</I18nProvider>;
}
