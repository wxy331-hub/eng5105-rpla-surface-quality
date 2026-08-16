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
} from "./data/week4OfflineEvidence.js";
import { collapseCandidateEpisodes, inspectionDataSource, inspectionMode } from "./services/inspectionDataSource.js";
import { I18nProvider, useI18n } from "./i18n.jsx";

const navItems = [
  { id: "live", label: "Live Inspection", icon: Camera },
  { id: "records", label: "Defect Records", icon: Archive },
  { id: "health", label: "System Health", icon: Gauge },
];

const isLiveEvidence = inspectionMode !== "offline";
const isServiceMode = inspectionMode === "service";
const cameraStreamUrl = import.meta.env?.VITE_CAMERA_STREAM_URL?.trim() ?? "";
const cameraStreamResolution = import.meta.env?.VITE_CAMERA_RESOLUTION?.trim() ?? "";

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

function stateDetail(snapshot, key, t) {
  const values = {
    cameraState: { value: t(isServiceMode ? snapshot.cameraState : isLiveEvidence ? "CAPTURE PASSED" : snapshot.cameraState), meta: t("Event: {event}", { event: t(snapshot.currentStep.event) }) },
    safetyGate: {
      value: t(isServiceMode
        ? snapshot.automaticActionsAllowed ? "DETECTION ACTIVE" : snapshot.cameraState === "HEALTHY" ? "WAITING FOR MATERIAL" : "BLOCKED"
        : isLiveEvidence ? snapshot.cameraState : snapshot.automaticActionsAllowed ? "ENABLED" : "BLOCKED"),
      meta: t(isLiveEvidence ? "Image processing only · no actuator output" : "Automatic decisions only when HEALTHY"),
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
      value: t(isServiceMode ? "CONTINUOUS SERVICE" : isLiveEvidence ? "CAMERA PIPELINE" : snapshot.evidenceLevel ?? "OFFLINE ONLY"),
      meta: t(isServiceMode ? "Python API and WebSocket" : isLiveEvidence ? "OV3660 stream path verified" : "Hardware performance not verified"),
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
        <div className="language-menu" role="menu" aria-label={t("Language")}>
          <button type="button" role="menuitemradio" aria-checked={language === "en"} onClick={() => selectLanguage("en")}>
            <span>English</span>{language === "en" ? <Check size={16} weight="bold" /> : null}
          </button>
          <button type="button" role="menuitemradio" aria-checked={language === "zh-CN"} onClick={() => selectLanguage("zh-CN")}>
            <span>中文</span>{language === "zh-CN" ? <Check size={16} weight="bold" /> : null}
          </button>
        </div>
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
        <span className={`connection-state connection-state--${tone}`}><StatusDot tone={tone} /> {t(isServiceMode ? snapshot.cameraState : isLiveEvidence ? "CAPTURE PASSED" : snapshot.cameraState)}</span>
        <span className="batch-id">{t("Batch")} {snapshot.batchId}</span>
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
      <nav aria-label={t("Primary navigation")}>
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-item ${activeView === id ? "nav-item--active" : ""}`}
            onClick={() => setActiveView(id)}
            aria-current={activeView === id ? "page" : undefined}
          >
            <Icon size={23} weight={activeView === id ? "fill" : "regular"} />
            <span>{t(isLiveEvidence && id === "records" ? "Candidate Records" : label)}</span>
          </button>
        ))}
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
  const [streamRevision, setStreamRevision] = useState(0);
  const [streamFailed, setStreamFailed] = useState(false);
  const blocked = !snapshot.automaticActionsAllowed;
  const tone = stateTone(snapshot.cameraState);
  const displayedEvidence = resolveDisplayedEvidence(snapshot, selectedDetection);
  const evidenceImageUrl = displayedEvidence.imageUrl ?? (displayedEvidence.imageFile ? `${import.meta.env.BASE_URL}assets/week4/${displayedEvidence.imageFile}` : null);
  const directStreamConfigured = isLiveEvidence && !selectedDetection && Boolean(cameraStreamUrl);
  const directStreamActive = directStreamConfigured && !streamFailed;
  const separator = cameraStreamUrl.includes("?") ? "&" : "?";
  const directStreamUrl = `${cameraStreamUrl}${separator}session=${streamRevision}`;
  const imageUrl = directStreamActive ? directStreamUrl : evidenceImageUrl;
  const displayedResolution = isServiceMode
    ? snapshot.resolution
    : directStreamConfigured && cameraStreamResolution
    ? cameraStreamResolution
    : snapshot.resolution;

  const refreshCamera = () => {
    setStreamFailed(false);
    setStreamRevision(Date.now());
    onReplay();
  };
  return (
    <Panel className="camera-card">
      <PanelHeader
        title={t(directStreamActive ? "Live inspection camera" : isLiveEvidence ? "Inspection camera evidence" : "Inspection evidence replay")}
        meta={t(directStreamActive ? "OV3660 MJPEG stream · Final system" : isLiveEvidence ? "OV3660 inspection camera · Final system" : "Week 4 annotated output · ESP32S3 simulation")}
        action={<span className="resolution">{t("Resolution")} {displayedResolution}</span>}
      />
      <div className={`camera-stage ${blocked && !displayedEvidence.isSelectedRecord ? "camera-stage--blocked" : ""}`}>
        {imageUrl
          ? <img
              key={imageUrl}
              className={directStreamActive ? "camera-stream" : undefined}
              src={imageUrl}
              alt={t(directStreamActive ? "Live OV3660 inspection camera stream" : "Annotated Week 4 inspection evidence from frame {frame}", { frame: displayedEvidence.imageFrameNumber })}
              onError={directStreamActive ? () => setStreamFailed(true) : undefined}
            />
          : <div className="camera-loading"><CircleNotch size={28} /> {t("Loading captured evidence")}</div>}
        <div className={`live-pill ${displayedEvidence.isSelectedRecord ? "live-pill--selected" : ""}`}>
          <StatusDot tone={displayedEvidence.isSelectedRecord ? "warning" : tone} />
          {t(displayedEvidence.isSelectedRecord ? "SELECTED RECORD" : directStreamActive ? "LIVE CAMERA" : isLiveEvidence ? "INSPECTION CAPTURE" : "OFFLINE REPLAY")}
        </div>
        <div className="frame-number">{directStreamActive ? t("QXGA STREAM") : <>{t(isLiveEvidence ? "CAPTURED FRAME" : "SAVED FRAME")} {displayedEvidence.imageFrameNumber}</>}</div>
        {blocked && !displayedEvidence.isSelectedRecord ? (
          <div className="paused-overlay"><Warning size={21} weight="fill" /> {t(isServiceMode && snapshot.cameraState === "HEALTHY" ? "WAITING FOR MATERIAL" : "PROCESSING HOLD")} · {t(snapshot.cameraState)}</div>
        ) : null}
        <div className="camera-stage__footer">
          <span>ROI: {snapshot.roiPx.join(", ")} px</span>
          <span>{displayedEvidence.isSelectedRecord
            ? t("Selected record: {id}", { id: displayedEvidence.recordId })
            : t(directStreamActive ? "Direct MJPEG stream" : isLiveEvidence ? "Latest annotated image only" : "Frame buffer: latest only")}</span>
        </div>
      </div>
      <div className="camera-controls">
        <button className="button button--secondary" type="button" onClick={refreshCamera}>
          <ArrowsClockwise size={16} /> {t(directStreamConfigured ? "Reconnect camera stream" : isLiveEvidence ? "Refresh captured evidence" : displayedEvidence.isSelectedRecord ? "Return to fault replay" : "Replay fault scenario")}
        </button>
        <span><CircleNotch size={15} /> {directStreamActive
          ? t(isServiceMode ? "Live camera · detections update over WebSocket" : "Direct camera feed · saved evidence updates separately")
          : isLiveEvidence
          ? t("Captured run · frame {frame}", { frame: displayedEvidence.imageFrameNumber })
          : displayedEvidence.isSelectedRecord
          ? t("Viewing saved evidence frame {frame}", { frame: displayedEvidence.imageFrameNumber })
          : t("Step {current} of {total} · scenario frame {frame}", { current: snapshot.currentStepIndex + 1, total: scenarioTimeline.length, frame: snapshot.frameNumber })}</span>
        <span><Warning size={15} /> {isLiveEvidence
          ? t("Processing gate {state}", { state: t(snapshot.cameraState) })
          : t("Automatic actions {state}", { state: t(snapshot.automaticActionsAllowed ? "enabled" : "blocked") })}</span>
        <span className="demo-control-note"><Info size={15} /> {t(isLiveEvidence ? "Integration evidence only · no actuator output" : "Test replay only · no hardware output")}</span>
      </div>
    </Panel>
  );
}

function LatestDetection({ detection }) {
  const { t } = useI18n();
  if (!detection) {
    return (
      <Panel className="quality-card quality-card--empty">
        <PanelHeader title={t(isLiveEvidence ? "Latest candidate event" : "Latest candidate")} meta={t(isLiveEvidence ? "Inspection event" : "Verified Week 4 offline record")} />
        <div className="empty-candidate">
          <CircleNotch size={35} />
          <strong>{t("No candidate recorded at this step")}</strong>
          <span>{t(isServiceMode ? "Place material inside the configured ROI to begin detection." : "The replay safety gate is holding image processing.")}</span>
        </div>
      </Panel>
    );
  }

  const tone = isLiveEvidence ? "evidence" : detection.grade === "Reject" ? "reject" : "warning";
  return (
    <Panel className="quality-card">
      <PanelHeader title={t(isLiveEvidence ? "Latest candidate event" : "Latest candidate")} meta={t(isLiveEvidence ? "Inspection event" : "Verified Week 4 offline record")} />
      <div className={`quality-banner quality-banner--${tone}`}>
        <Warning size={34} weight="fill" />
        <div>
          <span>{t(isLiveEvidence ? "CANDIDATE DETECTED" : detection.grade).toUpperCase()}</span>
          {!isLiveEvidence ? <small>{t("Prototype grade · no actuator response")}</small> : null}
        </div>
      </div>
      <dl className="defect-details">
        <div><dt><Alarm size={18} /> {t("Candidate type")}</dt><dd className="text-critical">{t(candidateLabel(detection.type))}</dd></div>
        <div><dt><Ruler size={18} /> {t("Bounding box")}</dt><dd>{detection.bboxPx.join(", ")} px</dd></div>
        <div><dt><Gauge size={18} /> {t("Area")}</dt><dd>{detection.areaPx} px²</dd></div>
        <div><dt><PlugsConnected size={18} /> {t("Algorithm score")}</dt><dd>{detection.algorithmScore.toFixed(3)}</dd></div>
        <div><dt><Camera size={18} /> {t("Frame ID")}</dt><dd>{detection.frameId}</dd></div>
        <div><dt><Database size={18} /> {t("Record ID")}</dt><dd>{detection.id}</dd></div>
      </dl>
      {!isLiveEvidence ? <div className="quality-readonly">
        <Info size={19} weight="fill" />
        <div><strong>{t("Physical measurements unavailable")}</strong><small>{t("Size and web position remain hidden until Week 7 calibration.")}</small></div>
      </div> : null}
    </Panel>
  );
}

const offlineKpiDefinitions = [
  { key: "cameraState", label: "Connection state", icon: Camera },
  { key: "safety", label: "Safety gate", icon: Warning },
  { key: "recovery", label: "Recovery frames", icon: ArrowsClockwise },
  { key: "processed", label: "Safely processed", icon: Gauge },
  { key: "dropped", label: "Backlog discarded", icon: Archive },
];

function KpiRow({ snapshot, eventCount }) {
  const { t } = useI18n();
  const definitions = isLiveEvidence ? [
    { key: "cameraState", label: "Connection state", icon: Camera },
    { key: "fps", label: "Measured pipeline rate", icon: Timer },
    { key: "events", label: "Candidate events", icon: Archive },
    { key: "latency", label: "Post-decode-to-GUI latency", icon: Timer },
  ] : offlineKpiDefinitions;
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
    <section className="kpi-grid" aria-label={t(isLiveEvidence ? "Verified live integration metrics" : "Verified offline state metrics")}>
      {definitions.map(({ key, label, icon: Icon }) => (
        <article className="kpi-card" key={key}>
          <Icon size={34} weight="duotone" />
          <div><span>{t(label)}</span><strong>{values[key]}</strong></div>
        </article>
      ))}
    </section>
  );
}

function LiveCaptureSummary({ snapshot, eventCount }) {
  const { t } = useI18n();
  return (
    <Panel className="timeline-card live-summary-card">
      <PanelHeader title={t("Inspection Run Summary")} meta={t("OV3660 inspection camera · Final system")} />
      <dl className="live-summary-grid">
        <div><dt>{t("Camera path")}</dt><dd>ESP32-S3 + OV3660 MJPEG</dd></div>
        <div><dt>{t("Resolution")}</dt><dd>{snapshot.resolution}</dd></div>
        <div><dt>{t("Active inspection ROI")}</dt><dd>{snapshot.roiPx.join(", ")} px</dd></div>
        <div><dt>{t("Candidate events")}</dt><dd>{t("{count} recorded events", { count: eventCount })}</dd></div>
      </dl>
    </Panel>
  );
}

function ConnectionTimeline({ currentStepIndex }) {
  const { t } = useI18n();
  return (
    <Panel className="timeline-card">
      <PanelHeader title={t("Connection fault timeline")} meta={t("Deterministic Week 4 state-machine replay")} />
      <div className="timeline-track" aria-label={t("Connection state timeline")}>
        {scenarioTimeline.map((step, index) => {
          const current = index === currentStepIndex;
          const complete = index < currentStepIndex;
          return (
            <article className={`timeline-step ${current ? "is-current" : ""} ${complete ? "is-complete" : ""}`} key={`${step.event}-${index}`}>
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
        <thead><tr>{large ? <><th>{t("Record ID")}</th><th>{t("UTC time")}</th></> : null}<th>{t(isLiveEvidence ? "Frame range" : "Frame")}</th>{isLiveEvidence ? <th>{t("Evidence frames")}</th> : null}<th>{t("Candidate type")}</th><th>{t("BBox (px)")}</th><th>{t("Area (px²)")}</th><th>{t("Score")}</th>{!isLiveEvidence ? <th>{t("Grade")}</th> : null}{onDelete ? <th className="actions-column">{t("Actions")}</th> : null}</tr></thead>
        <tbody>
          {events.map((event) => (
            <tr
              key={event.id}
              className={onSelect ? `selectable-row ${event.id === selectedId ? "is-selected" : ""}` : ""}
              onClick={() => onSelect?.(event)}
              onKeyDown={(keyboardEvent) => {
                if (!onSelect || !["Enter", " "].includes(keyboardEvent.key)) return;
                keyboardEvent.preventDefault();
                onSelect(event);
              }}
              role={onSelect ? "button" : undefined}
              tabIndex={onSelect ? 0 : undefined}
              aria-pressed={onSelect ? event.id === selectedId : undefined}
              aria-label={onSelect ? t("View record {id}, frame {frame}", { id: event.id, frame: event.frameId }) : undefined}
            >
              {large ? <><td className="mono">{event.id}</td><td className="mono">{event.receivedAtUtc.slice(11, 23)}</td></> : null}
              <td className="mono">{isLiveEvidence ? event.frameLabel : event.frameId}</td>
              {isLiveEvidence ? <td className="mono">{event.occurrences}</td> : null}
              <td>{t(candidateLabel(event.type))}</td>
              <td className="mono">{event.bboxPx.join(", ")}</td>
              <td className="mono">{event.areaPx}</td>
              <td className="mono">{event.algorithmScore.toFixed(3)}</td>
              {!isLiveEvidence ? <td><span className={`grade grade--${event.grade.toLowerCase()}`}>{t(event.grade)}</span></td> : null}
              {onDelete ? <td className="actions-cell"><button className="delete-record-button" type="button" onClick={(clickEvent) => { clickEvent.stopPropagation(); onDelete(event); }} aria-label={t("Delete candidate event {id}", { id: event.id })} title={t("Delete recorded event")}><Trash size={15} /><span>{t("Delete")}</span></button></td> : null}
            </tr>
          ))}
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
      <PanelHeader title={t(isLiveEvidence ? "Detected candidate events" : "Recorded candidates")} meta={t(isLiveEvidence ? "{events} events from {frames} evidence frames" : "{count} SQLite-backed Week 4 records", { events: events.length, frames: rawCount, count: events.length })} action={onClear ? <button className="button button--danger clear-records-button" type="button" onClick={onClear} disabled={!rawCount}><Trash size={16} /><span>{t("Clear records")}</span></button> : null} />
      <CandidateTable events={visibleEvents} selectedId={selectedId} onSelect={isLiveEvidence ? undefined : onSelect} onDelete={onDelete} />
    </Panel>
  );
}

function LiveView({ snapshot, events, rawEventCount, selectedEvent, setSelectedEvent, onReplay, onDelete, onClear }) {
  const detection = selectedEvent ?? (isLiveEvidence ? events.at(-1) : snapshot.currentDetection);
  return (
    <div className="dashboard-view">
      <div className="hero-grid">
        <LiveCamera snapshot={snapshot} selectedDetection={selectedEvent} onReplay={onReplay} />
        <LatestDetection detection={detection} />
      </div>
      <KpiRow snapshot={snapshot} eventCount={events.length} />
      <div className="evidence-grid">
        {isLiveEvidence ? <LiveCaptureSummary snapshot={snapshot} eventCount={events.length} /> : <ConnectionTimeline currentStepIndex={snapshot.currentStepIndex} />}
        <RecentCandidates events={events} rawCount={rawEventCount} selectedId={selectedEvent?.id} onSelect={setSelectedEvent} onDelete={onDelete} onClear={onClear} />
      </div>
    </div>
  );
}

function RecordsView({ events, rawCount, snapshot, onExport, onDelete, onClear }) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("All grades");
  const filtered = events.filter((event) => {
    const matchesQuery = `${event.id} ${event.type} ${t(candidateLabel(event.type))} ${event.frameId}`.toLowerCase().includes(query.toLowerCase());
    return matchesQuery && (grade === "All grades" || event.grade === grade);
  });

  return (
    <div className="secondary-view">
      <div className="page-heading">
        <div><p>{t(isLiveEvidence ? "INSPECTION EVENT LOG" : "TRACEABLE OFFLINE EVENT LOG")}</p><h2>{t(isLiveEvidence ? "Candidate Events" : "Defect Records")}</h2><span>{isLiveEvidence ? t("{events} events from {frames} evidence frames · Batch {batch}", { events: events.length, frames: rawCount, batch: snapshot.batchId }) : t("Week 4 fault-injection evidence · Batch W4-OFFLINE-FAULT-001")}</span></div>
        <div className="page-heading__actions">{onClear ? <button className="button button--danger" onClick={onClear} type="button" disabled={!rawCount}><Trash size={18} /> {t("Clear records")}</button> : null}<button className="button button--secondary" onClick={onExport} type="button"><FileCsv size={19} /> {t("Export evidence CSV")}</button></div>
      </div>
      <Panel className="records-panel">
        <div className="filter-bar">
          <label><MagnifyingGlass size={18} /><input aria-label={t("Search candidate records")} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("Search record, frame or candidate")} /></label>
          {!isLiveEvidence ? <select value={grade} onChange={(event) => setGrade(event.target.value)} aria-label={t("Filter by prototype grade")}><option value="All grades">{t("All grades")}</option><option value="Warning">{t("Warning")}</option><option value="Reject">{t("Reject")}</option></select> : null}
          <span>{t(isLiveEvidence ? "{count} candidate events" : "{count} verified offline records", { count: filtered.length })}</span>
        </div>
        <CandidateTable events={filtered} large onDelete={onDelete} />
        {!isLiveEvidence ? <div className="records-note"><Info size={18} /><span>{t("Physical size and web position are intentionally omitted because no calibration or encoder evidence exists.")}</span></div> : null}
      </Panel>
    </div>
  );
}

function HealthView({ snapshot }) {
  const { t } = useI18n();
  const primaryDefinitions = healthDefinitions.filter(({ key }) => ["cameraState", "safetyGate", "evidence"].includes(key));
  const technicalDetails = [
    [t("Source"), t(snapshot.source)],
    [t("Resolution"), snapshot.resolution],
    ["ROI", `${snapshot.roiPx.join(", ")} px`],
    [t("Recovery frames"), `${snapshot.recoveryCount} / ${snapshot.recoveryFrames}`],
    [t("Buffer policy"), t("Latest frame only")],
    [t("Backlog discarded"), String(snapshot.droppedFrames ?? 0)],
  ];
  return (
    <div className="secondary-view">
      <div className="page-heading">
        <div><p>{t(isLiveEvidence ? "INSPECTION SYSTEM STATUS" : "FAIL-SAFE OFFLINE OBSERVABILITY")}</p><h2>{t("System Health")}</h2><span>{t(isLiveEvidence ? "Camera, processing and storage status" : "Only states verified by the Week 4 software test are displayed")}</span></div>
        <span className={`connection-state connection-state--${isLiveEvidence ? "healthy" : "warning"}`}><StatusDot tone={isLiveEvidence ? "healthy" : "warning"} /> {t(isLiveEvidence ? "OV3660 stream path verified" : "Hardware not connected")}</span>
      </div>
      <div className="health-overview-grid">
        {primaryDefinitions.map(({ key, icon: Icon }) => {
          const detail = stateDetail(snapshot, key, t);
          const visibleLabel = key === "cameraState" ? "Camera" : key === "safetyGate" ? "Inspection" : "Data service";
          const visibleDetail = key === "evidence"
            ? { value: detail.value, meta: t("API, WebSocket and SQLite") }
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
      <Panel className="safety-policy-panel">
        <PanelHeader title={t("Safety policy")} meta={t(isLiveEvidence ? "System protection rules" : "Verified prototype behaviour")} />
        <div className="policy-grid">
          <article><Warning size={24} /><div><strong>{t("Camera or network loss")}</strong><span>{t("Image processing and all automatic outputs enter a blocked state.")}</span></div></article>
          <article><ArrowsClockwise size={24} /><div><strong>{t("Controlled recovery")}</strong><span>{t("Three consecutive valid frames are required before processing resumes.")}</span></div></article>
          <article><Database size={24} /><div><strong>{t("Local-first evidence")}</strong><span>{t("Connection events and candidate records are stored in SQLite.")}</span></div></article>
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
        <div><strong>{t("Evidence boundary")}</strong><span>{t("This screen does not claim camera FPS, latency, temperature, lighting, STM32, encoder, physical size, web position, classification accuracy or actuator performance. Those fields return only after physical Week 2–4 work and later calibration are completed.")}</span></div>
      </Panel> : null}
    </div>
  );
}

function exportCsv(events) {
  const header = ["detection_id", "batch_id", "frame_id", "received_at_utc", "candidate_type", "bbox_px", "area_px", "algorithm_score", "prototype_grade", "algorithm_version", "data_mode"];
  const rows = events.map((event) => [event.id, event.batchId, event.frameId, event.receivedAtUtc, event.type, event.bboxPx.join(" "), event.areaPx, event.algorithmScore, event.grade.toLowerCase(), event.algorithmVersion, event.dataMode]);
  const csv = [header, ...rows].map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = isLiveEvidence ? "inspection-candidate-evidence.csv" : "week4-offline-detection-evidence.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}

function AppContent() {
  const { t } = useI18n();
  const [activeView, setActiveView] = useState("live");
  const [snapshot, setSnapshot] = useState(() => inspectionDataSource.getSnapshot());
  const [events, setEvents] = useState(() => isLiveEvidence ? [] : offlineDetections);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const displayEvents = useMemo(() => isLiveEvidence ? collapseCandidateEpisodes(events) : events, [events]);

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
    if (activeView === "records") return <RecordsView events={displayEvents} rawCount={events.length} snapshot={snapshot} onExport={() => exportCsv(events)} onDelete={deleteCandidateEvent} onClear={clearCandidateEvents} />;
    if (activeView === "health") return <HealthView snapshot={snapshot} />;
    return <LiveView snapshot={snapshot} events={displayEvents} rawEventCount={events.length} selectedEvent={selectedEvent} setSelectedEvent={setSelectedEvent} onReplay={replay} onDelete={deleteCandidateEvent} onClear={clearCandidateEvents} />;
  }, [activeView, displayEvents, events, selectedEvent, snapshot]);

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} setActiveView={setActiveView} snapshot={snapshot} />
      <div className="workspace">
        <TopBar snapshot={snapshot} />
        <main className="main-content">{page}</main>
      </div>
    </div>
  );
}

export function App() {
  return <I18nProvider><AppContent /></I18nProvider>;
}
