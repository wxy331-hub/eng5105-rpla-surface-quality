import { useEffect, useMemo, useRef, useState } from "react";
import { Archive, ArrowLeft, ArrowsClockwise, Camera, Check, FileCsv, Info, Translate, Trash } from "@phosphor-icons/react";
import { useI18n } from "./i18n.jsx";
import { WEEK7_ANGLES, WEEK7_LIGHTS, week7DataSource } from "./services/week7DataSource.js";
import { createResolutionMetadata } from "./services/resolutionMetadata.js";
import "./week7.css";

// Copy lives with this separate workbench so the public replay vocabulary stays stable.
const copy = {
  eyebrow: ["ENG5105 · PLAN A SAMPLE CAPTURE", "ENG5105 · 方案 A 样本采集"],
  title: ["Offline sample capture", "离线样本采集"],
  backToInspection: ["Back to inspection", "返回检测界面"],
  simulated: ["SIMULATED", "模拟来源"],
  sourceStatus: ["Capture source", "采集来源"],
  syntheticSource: ["Synthetic images", "合成图像"],
  cameraPending: ["Camera interface pending integration", "摄像头接口待接入"],
  cameraGuide: ["Camera connection guide", "摄像头连接说明"],
  cameraGuideBody: ["To capture real images, connect the Plan A USB/UVC camera and integrate it with the sample service. This workbench currently captures synthetic images only. Camera connection has not been tested here.", "真实采集需要连接 Plan A USB/UVC 摄像头，并将其接入样本服务。目前采集台仅支持合成图像，尚未在此检测摄像头连接状态。"],
  simulatedControls: ["The selected angle and lighting mode identify each simulated view. Physical lighting and MCU outputs remain blocked.", "所选角度和照明模式用于标记每个模拟视图。物理照明及 MCU 输出仍被禁止。"],
  close: ["Close", "关闭"],
  intro: ["One specimen. Six angles. Two lighting modes.", "一个样本，六个角度，两种照明。"],
  boundary: ["Synthetic images · calibration pending · physical outputs blocked", "合成图像 · 标定待完成 · 物理输出已禁止"],
  samples: ["Sample sessions", "样本会话"],
  sampleId: ["Sample ID", "样本编号"],
  placeholder: ["e.g. SAMPLE-001", "例如 SAMPLE-001"],
  create: ["Create sample", "创建样本"],
  newConfiguration: ["New session images", "新会话图像"],
  nativeSynthetic: ["Generated at these pixel dimensions", "按此像素尺寸原生生成合成图像"],
  configurationUnavailable: ["Capture configuration unavailable", "采集配置暂不可用"],
  sessionConfiguration: ["Session image dimensions", "会话图像尺寸"],
  viewArchive: ["Review saved captures", "查看已保存图像"],
  incompatibleSession: ["This session uses an earlier capture configuration. Its saved images remain available. Create a new sample session to capture with the current configuration.", "此会话使用早期采集配置，仍可查看已保存图像。请创建新样本会话，使用当前配置采集。"],
  refresh: ["Refresh sessions", "刷新会话"],
  emptySessions: ["Create a sample to begin the capture sequence.", "创建样本以开始采集流程。"],
  resume: ["Open / resume a session", "打开或恢复会话"],
  deleteSession: ["Delete session {sample} · {session}", "删除会话 {sample} · {session}"],
  confirmDelete: ["Delete sample “{sample}” (session {session})? This permanently removes this session's images, candidate records and capture history.", "删除样本“{sample}”（会话 {session}）？此操作将永久删除该会话的图像、候选记录及采集历史。"],
  deletedSession: ["Deleted session {sample} · {session}", "已删除会话 {sample} · {session}"],
  cleanupPending: ["Session {sample} · {session} was removed. Its image-file cleanup is still pending.", "会话 {sample} · {session} 已移除，图像文件清理尚未完成。"],
  retryCleanup: ["Retry file cleanup", "重试文件清理"],
  in_progress: ["In progress", "采集中"],
  completed: ["Complete", "已完成"],
  incomplete_archive: ["Archive needs repair", "归档需要修复"],
  session: ["Session", "会话"],
  angle: ["Specimen angle", "样本角度"],
  captureControls: ["Capture controls", "采集操作"],
  locked: ["Session locked", "会话已锁定"],
  lighting: ["Lighting mode", "照明模式"],
  targetView: ["Target view", "本次目标视图"],
  capture_bright_field: ["Capture bright-field simulation", "采集明场模拟图"],
  capture_dark_field: ["Capture dark-field simulation", "采集暗场模拟图"],
  retake_bright_field: ["Retake bright-field simulation", "重拍明场模拟图"],
  retake_dark_field: ["Retake dark-field simulation", "重拍暗场模拟图"],
  retakeNote: ["Retakes preserve every previous image and candidate record.", "重拍保留所有旧图像及候选记录。"],
  confirmRetake: ["Retake {angle}° · {light}? The new image becomes current for this view; previous attempts remain in the archive.", "确认重拍 {angle}° · {light}？新图将成为此视图的当前图像，旧记录仍保留在归档中。"],
  viewSaved: ["Saved {angle}° · {light}.", "已保存 {angle}° · {light}。"],
  nextMissing: ["Next missing view: {angle}° · {light}", "建议补采：{angle}° · {light}"],
  selectNext: ["Select next missing view", "选择下一待补视图"],
  matrixGuide: ["Select a missing cell to prepare one capture. Select a saved cell to review its raw image.", "选择缺图单元格以准备单张采集；选择已保存单元格以查看原图。"],
  progress: ["Capture coverage", "采集覆盖进度"],
  coverage: ["{count} / 12 views", "{count} / 12 个视图"],
  bright_field: ["Bright field", "明场"],
  dark_field: ["Dark field", "暗场"],
  missing: ["Missing", "缺图"],
  saved: ["Saved", "已保存"],
  missingViews: ["Missing views", "待补视图"],
  allCaptured: ["All 12 views are available. Review the evidence before completing.", "12 个视图均已保存，请检查证据后完成样本。"],
  completedCoverage: ["All 12 views are archived. Select a view to review its saved evidence.", "12 个视图已归档。选择视图以查看保存的证据。"],
  complete: ["Complete sample", "完成样本"],
  completeNote: ["A completed sample is locked. Create a new session for further acquisition.", "已完成的样本会锁定；继续采集需建立新会话。"],
  archiveLockedNote: ["This completed archive has missing files and remains locked. Restore its saved files or start a new session.", "此已完成归档存在缺失文件，仍保持锁定。请恢复已保存文件或建立新会话。"],
  export: ["Export CSV", "导出 CSV"],
  empty: ["Select a session or create a new sample", "选择会话或创建新样本"],
  emptyBody: ["Choose one angle and lighting mode, then capture one view at a time. Review all 12 saved views before completing the sample.", "选择一个角度和一种照明，即可采集一个视图。完成样本前检查全部 12 个已保存视图。"],
  image: ["Saved capture", "已保存图像"],
  imageResolution: ["Saved image · synthetic", "保存图像 · 合成"],
  imageLoading: ["Loading image", "正在加载图像"],
  resolutionNote: ["Pixel dimensions of this saved image. Camera capture settings are configured separately.", "此保存图像的像素尺寸；相机采集参数单独配置。"],
  archiveDetail: ["Archive details", "归档详情"],
  captureId: ["Capture ID", "采集编号"],
  sourceId: ["Recorded source ID", "归档来源编号"],
  archiveMissing: ["Files missing", "文件缺失"],
  raw: ["Raw", "原图"],
  annotated: ["Annotated", "标注图"],
  imageAlt: ["{variant} simulated image at {angle} degrees, {light}", "{angle} 度{light}模拟图像：{variant}"],
  noImage: ["Select a saved view to inspect its evidence.", "选择已保存的视图查看证据。"],
  imageFailure: ["This saved image could not be loaded. Refresh the session to check archive coverage.", "保存的图像加载失败，请刷新会话检查归档完整性。"],
  candidates: ["Pixel-space candidates", "像素空间候选"],
  candidateNote: ["Scores rank candidates by area; they are not defect probabilities.", "分数按面积排列候选，不表示缺陷概率。"],
  noCandidates: ["No candidates recorded in this view.", "此视图未记录候选。"],
  type: ["Candidate type", "候选类型"],
  bbox: ["BBox · x, y, w, h (px)", "边界框 · x、y、宽、高（px）"],
  area: ["Area (px²)", "面积（px²）"],
  score: ["Ranking score", "排序分数"],
  contamination_candidate: ["Contamination candidate", "污染候选"],
  scratch_candidate: ["Scratch candidate", "划痕候选"],
  pit_candidate: ["Pit candidate", "凹坑候选"],
  calibration: ["Calibration", "标定"],
  calibrationId: ["Calibration ID", "标定编号"],
  calibrationReason: ["Validation reason", "有效性判定原因"],
  calibrationPending: ["Calibration profile has not been validated.", "标定文件尚未通过验证。"],
  calibrationUnavailable: ["Calibration is unavailable for this saved view.", "此保存视图没有可用标定。"],
  calibrationSimulation: ["Calibration checks passed for the simulated workflow only.", "仅模拟流程的标定检查已通过。"],
  invalid: ["Invalid", "无效"],
  valid_for_simulation: ["Valid for simulation only", "仅对模拟有效"],
  not_calibrated: ["Not calibrated", "未标定"],
  pending: ["Pending", "待完成"],
  size: ["Physical size (mm)", "物理尺寸（mm）"],
  position: ["Physical position (mm)", "物理位置（mm）"],
  unmeasured: ["Not measured", "未测量"],
  history: ["Capture history", "采集历史"],
  attempts: ["{count} capture records · 2 PNGs per record · includes retakes", "{count} 条采集记录 · 每条含 2 张 PNG · 包括重拍"],
  current: ["Current", "当前"],
  superseded: ["Previous attempt", "历史版本"],
  replaces: ["Supersedes", "替代记录"],
  serviceError: ["The local sample service could not finish this request. Check the service and retry.", "本地样本服务未能完成请求，请检查服务后重试。"],
  refreshFailure: ["Session refresh also failed; displayed coverage may be outdated.", "会话刷新也失败了；当前显示的覆盖进度可能已过时。"],
  detail: ["Technical detail", "技术详情"],
  retry: ["Retry connection", "重试连接"],
  busy: ["Working…", "处理中…"],
  language: ["Interface language", "界面语言"],
  evidence: ["Evidence label", "证据标签"],
  diagnostics: ["Simulated lighting / MCU log", "模拟照明 / MCU 日志"],
  diagnosticNote: ["Recorded simulated messages; physical lighting and MCU outputs remain blocked.", "以下为模拟消息记录；物理照明及 MCU 输出仍被禁止。"],
  latestEvent: ["Latest simulated event", "最近的模拟事件"],
  latestFailure: ["Latest recorded capture fault", "最近记录的采集故障"],
  lastOff: ["Last simulated OFF acknowledgment", "最近的模拟关闭确认"],
  noEvent: ["No recorded event", "暂无事件记录"],
  noFault: ["No recorded capture fault", "暂无采集故障记录"],
  noOff: ["No recorded simulated OFF acknowledgment", "暂无模拟关闭确认记录"],
  recentEvents: ["Most recent 12 events", "最近 12 条事件"],
  LIGHTING_REQUEST: ["Simulated lighting requested", "已请求模拟照明"],
  SIMULATED_READY: ["Simulated readiness message", "模拟就绪消息"],
  CAPTURE_ARCHIVED: ["Capture archived", "采集已归档"],
  CAPTURE_FAILED: ["Capture failed", "采集失败"],
  SIMULATED_OFF_ACK: ["Simulated OFF acknowledged", "模拟关闭已确认"],
};

function pendingDeletionSessions(health) {
  return (Array.isArray(health?.pending_deletions) ? health.pending_deletions : [])
    .filter((item) => typeof item.deleted_session_id === "string")
    .map((item) => ({ ...item, session_id: item.deleted_session_id }));
}

export default function Week7SamplePanel({ dataSource = week7DataSource }) {
  const { language, setLanguage } = useI18n();
  const text = (key, parameters = {}) => (copy[key]?.[language === "zh-CN" ? 1 : 0] ?? key)
    .replace(/\{(\w+)\}/g, (_, name) => String(parameters[name] ?? `{${name}}`));
  const [sessions, setSessions] = useState([]);
  const [serviceHealth, setServiceHealth] = useState(null);
  const [sample, setSample] = useState(null);
  const [sampleId, setSampleId] = useState("");
  const [angle, setAngle] = useState(0);
  const [lightingMode, setLightingMode] = useState("bright_field");
  const [captureNotice, setCaptureNotice] = useState(null);
  const [deletedNotice, setDeletedNotice] = useState(null);
  const [pendingDeletions, setPendingDeletions] = useState([]);
  const cameraDialog = useRef(null);
  const [selectedId, setSelectedId] = useState(null);
  const [variant, setVariant] = useState("raw");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [decodedImage, setDecodedImage] = useState(null);
  const captures = sample?.captures ?? [];
  const currentViews = sample?.current_views ?? [];
  const missingViews = sample?.missing_views ?? [];
  const selected = captures.find((item) => item.capture_id === selectedId)
    ?? currentViews.find((item) => item.capture_id === selectedId) ?? null;
  const currentIds = useMemo(() => new Set(currentViews.map((item) => item.capture_id)), [currentViews]);
  const viewExists = currentViews.some((item) => item.angle_deg === angle && item.lighting_mode === lightingMode);
  const complete = Boolean(sample?.completed_at_utc) || ["completed", "incomplete_archive"].includes(sample?.status);
  const captureIncompatible = sample?.capture_compatible === false;
  const captureLocked = complete || captureIncompatible;
  const configurationUnavailable = typeof dataSource.getHealth === "function" && !serviceHealth;
  const events = sample?.events ?? [];
  const latestFailure = events.findLast((event) => event.event_type === "CAPTURE_FAILED");
  const lastOff = events.findLast((event) => event.event_type === "SIMULATED_OFF_ACK");
  const imageKey = selected ? `${selected.capture_id}/${variant}` : null;
  const imageResolution = createResolutionMetadata({
    widthPx: decodedImage?.key === imageKey ? decodedImage.width : null,
    heightPx: decodedImage?.key === imageKey ? decodedImage.height : null,
    synthetic: true,
  });
  const newResolution = createResolutionMetadata({
    widthPx: serviceHealth?.image_size_px?.[0], heightPx: serviceHealth?.image_size_px?.[1], synthetic: true,
  });
  const sessionResolution = createResolutionMetadata({
    widthPx: sample?.capture_configuration?.image_size_px?.[0],
    heightPx: sample?.capture_configuration?.image_size_px?.[1], synthetic: true,
  });

  useEffect(() => {
    let active = true;
    setBusy(true);
    // An unavailable capture service must not hide sessions already returned by the archive API.
    Promise.allSettled([
      dataSource.listSamples(),
      typeof dataSource.getHealth === "function" ? dataSource.getHealth() : Promise.resolve(null),
    ]).then(([sessionResult, healthResult]) => {
      if (!active) return;
      if (sessionResult.status === "fulfilled") setSessions(sessionResult.value);
      if (healthResult.status === "fulfilled") {
        setServiceHealth(healthResult.value);
        setPendingDeletions(pendingDeletionSessions(healthResult.value));
      }
      setError(sessionResult.status === "rejected" ? sessionResult.reason
        : healthResult.status === "rejected" ? healthResult.reason : null);
      setBusy(false);
    });
    return () => { active = false; };
  }, [dataSource]);

  useEffect(() => { setImageFailed(false); }, [selectedId, variant]);

  const applySample = (next, preferredAngle, preferredLight = lightingMode) => {
    setSample(next);
    // The mutation response is the current session snapshot. Apply it to both
    // views together instead of waiting for a second archive-list request.
    setSessions((items) => items.some((item) => item.session_id === next.session_id)
      ? items.map((item) => item.session_id === next.session_id ? next : item)
      : [next, ...items]);
    setCaptureNotice(null);
    setDeletedNotice(null);
    setImageFailed(false);
    const views = next.current_views ?? [];
    setSelectedId((views.find((item) => item.angle_deg === (preferredAngle ?? 0) && item.lighting_mode === preferredLight) ?? views[0])?.capture_id ?? null);
  };

  const run = async (operation) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try { await operation(); }
    catch (cause) { setError(cause); }
    finally { setBusy(false); }
  };

  const refresh = () => run(async () => {
    const [sessionResult, healthResult] = await Promise.allSettled([
      dataSource.listSamples(),
      typeof dataSource.getHealth === "function" ? dataSource.getHealth() : Promise.resolve(null),
    ]);
    if (sessionResult.status === "fulfilled") setSessions(sessionResult.value);
    setServiceHealth(healthResult.status === "fulfilled" ? healthResult.value : null);
    if (healthResult.status === "fulfilled") setPendingDeletions(pendingDeletionSessions(healthResult.value));
    if (sample) applySample(await dataSource.getSample(sample.session_id), angle);
    if (sessionResult.status === "rejected") throw sessionResult.reason;
    if (healthResult.status === "rejected") throw healthResult.reason;
  });

  const openSession = (sessionId) => run(async () => {
    const next = await dataSource.getSample(sessionId);
    const target = next.missing_views?.[0] ?? { angle_deg: 0, lighting_mode: "bright_field" };
    applySample(next, target.angle_deg, target.lighting_mode);
    setAngle(target.angle_deg);
    setLightingMode(target.lighting_mode);
    setVariant("raw");
  });

  const createSample = (event) => {
    event.preventDefault();
    if (configurationUnavailable) return;
    run(async () => {
      applySample(await dataSource.createSample(sampleId), 0, "bright_field");
      setAngle(0);
      setLightingMode("bright_field");
      setSampleId("");
    });
  };

  const capture = () => {
    if (!sample || busy || captureLocked) return;
    if (viewExists && !window.confirm(text("confirmRetake", { angle, light: text(lightingMode) }))) return;
    run(async () => {
      try {
        const next = await dataSource.capture(sample.session_id, angle, { lightingMode, retake: viewExists });
        applySample(next, angle, lightingMode);
        setVariant("raw");
        setCaptureNotice({ angle, lightingMode, next: next.missing_views?.[0] ?? null });
      } catch (cause) {
        if (cause.sample) applySample(cause.sample, angle);
        throw cause;
      }
    });
  };

  const chooseMissingView = (view) => {
    setAngle(view.angle_deg);
    setLightingMode(view.lighting_mode);
    setCaptureNotice(null);
    setSelectedId(null);
  };

  const applyDeletion = (item, result) => {
      if (result.deleted_session_id !== item.session_id) throw new Error("Deleted session response does not match the requested session");
      setSessions((items) => items.filter((entry) => entry.session_id !== item.session_id));
      if (sample?.session_id === item.session_id) {
        setSample(null);
        setSelectedId(null);
        setCaptureNotice(null);
      }
      setPendingDeletions((items) => [...items.filter((entry) => entry.session_id !== item.session_id), ...(result.cleanup_pending ? [item] : [])]);
      setDeletedNotice(result.cleanup_pending ? null : { sample: item.sample_id, session: item.session_id.slice(0, 8) });
  };

  const deleteSession = (item) => {
    if (busy || !window.confirm(text("confirmDelete", { sample: item.sample_id, session: item.session_id }))) return;
    run(async () => applyDeletion(item, await dataSource.deleteSample(item.session_id)));
  };

  const finish = () => run(async () => {
    applySample(await dataSource.completeSample(sample.session_id), angle);
  });

  return (
    <div className="week7-shell">
      <header className="week7-topbar">
        <div className="week7-brand"><Camera size={29} weight="duotone" /><div><p>{text("eyebrow")}</p><h1>{text("title")}</h1></div></div>
        <div className="week7-topbar-actions"><a className="button button--secondary week7-back-link" href="#inspection"><ArrowLeft size={17} aria-hidden="true" />{text("backToInspection")}</a><span className="week7-badge">{text("simulated")}</span><label className="week7-language"><Translate size={18} /><select aria-label={text("language")} value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="zh-CN">简体中文</option></select></label></div>
      </header>
      <div className="week7-boundary"><Info size={17} /><span>{text("boundary")}</span><code>OFFLINE_SYNTHETIC_ONLY</code></div>
      <main className="week7-layout">
        <aside className="week7-sessions panel">
          <div className="week7-panel-heading"><h2>{text("samples")}</h2><button className="week7-icon-button" type="button" title={text("refresh")} aria-label={text("refresh")} disabled={busy} onClick={refresh}><ArrowsClockwise size={18} /></button></div>
          <form className="week7-create" onSubmit={createSample}>
            <div className="week7-new-configuration"><span>{text("newConfiguration")}</span><strong className="mono">{newResolution.frameWidthPx ? `${newResolution.resolution} px` : text("configurationUnavailable")}</strong>{newResolution.frameWidthPx ? <small>{text("nativeSynthetic")}</small> : null}</div>
            <label htmlFor="week7-sample-id">{text("sampleId")}</label><input id="week7-sample-id" value={sampleId} onChange={(event) => setSampleId(event.target.value)} placeholder={text("placeholder")} required maxLength={100} disabled={busy} autoComplete="off" /><button className="button button--primary" type="submit" disabled={busy || configurationUnavailable || !sampleId.trim()}><Archive size={17} />{text("create")}</button>
          </form>
          <p className="week7-list-label">{text("resume")}</p>
          <div className="week7-session-list">{sessions.length ? sessions.map((item) => <div className="week7-session-row" key={item.session_id}><button type="button" className={`week7-session ${sample?.session_id === item.session_id ? "is-selected" : ""}`} aria-pressed={sample?.session_id === item.session_id} disabled={busy} onClick={() => openSession(item.session_id)}><strong className="mono">{item.sample_id}</strong><span>{text(item.status)}</span><small className="mono">{item.session_id}</small></button><button type="button" className="week7-delete-session" aria-label={text("deleteSession", { sample: item.sample_id, session: item.session_id.slice(0, 8) })} title={text("deleteSession", { sample: item.sample_id, session: item.session_id.slice(0, 8) })} disabled={busy} onClick={() => deleteSession(item)}><Trash size={17} aria-hidden="true" /></button></div>) : <p className="week7-muted">{text("emptySessions")}</p>}</div>
        </aside>
        <div className="week7-workspace" aria-busy={busy}>
          <section className="panel week7-source-status"><div><h2>{text("sourceStatus")}</h2><strong>{text("syntheticSource")}</strong><span>{text("cameraPending")}</span></div><button type="button" className="button button--secondary" onClick={() => cameraDialog.current?.showModal()}><Info size={17} aria-hidden="true" />{text("cameraGuide")}</button></section>
          {deletedNotice ? <p className="week7-action-notice" role="status">{text("deletedSession", deletedNotice)}</p> : null}
          {pendingDeletions.map((item) => <div className="week7-cleanup-pending" role="status" key={item.session_id}><p>{text("cleanupPending", { sample: item.sample_id, session: item.session_id.slice(0, 8) })}</p><button type="button" className="button button--secondary" disabled={busy} onClick={() => run(async () => applyDeletion(item, await dataSource.deleteSample(item.session_id)))}>{text("retryCleanup")}</button></div>)}
          {error ? <div className="week7-error" role="alert"><strong>{text("serviceError")}</strong><details><summary>{text("detail")}</summary><code>{error.message}</code>{error.sampleRefreshError ? <><p>{text("refreshFailure")}</p><code>{error.sampleRefreshError.message}</code></> : null}</details><button className="button button--secondary" type="button" disabled={busy} onClick={refresh}>{text("retry")}</button></div> : null}
          {sample ? <>
            <section className="week7-summary"><div><p>{text("intro")}</p><h2 className="mono">{sample.sample_id}</h2><span>{text("session")} <code>{sample.session_id}</code></span>{sessionResolution.frameWidthPx ? <span className="week7-session-resolution">{text("sessionConfiguration")} <code>{sessionResolution.resolution} px</code></span> : null}</div><div className="week7-summary-actions"><span className="week7-status">{text(sample.status)}</span><a className="button button--secondary" href={dataSource.exportUrl(sample.session_id)} download><FileCsv size={18} />{text("export")}</a><button type="button" className="button button--primary" onClick={finish} disabled={busy || complete || missingViews.length > 0 || currentViews.length !== 12}><Check size={18} />{text("complete")}</button></div></section>
            <div className="week7-capture-layout">
            <section className={`panel week7-acquire ${captureLocked ? "is-locked" : ""}`}>
              <h2>{text(complete ? "locked" : captureIncompatible ? "viewArchive" : "captureControls")}</h2>
              {captureLocked ? <Archive size={28} aria-hidden="true" /> : <div className="week7-acquire-controls">
                <div className="week7-target-selectors"><label className="week7-angle">{text("angle")}<select className="mono" value={angle} disabled={busy} onChange={(event) => { setAngle(Number(event.target.value)); setCaptureNotice(null); }}>{WEEK7_ANGLES.map((value) => <option key={value} value={value}>{value}°</option>)}</select></label><label className="week7-angle">{text("lighting")}<select value={lightingMode} disabled={busy} onChange={(event) => { setLightingMode(event.target.value); setCaptureNotice(null); }}>{WEEK7_LIGHTS.map((value) => <option key={value} value={value}>{text(value)}</option>)}</select></label></div>
                <p className="week7-target-view">{text("targetView")} <strong><span className="mono">{angle}°</span> · {text(lightingMode)}</strong></p>
                <button className="button button--primary" type="button" disabled={busy} onClick={capture}><Camera size={18} />{text(busy ? "busy" : `${viewExists ? "retake" : "capture"}_${lightingMode}`)}</button>
              </div>}
              <p className="week7-muted">{text(sample.status === "incomplete_archive" ? "archiveLockedNote" : complete ? "completeNote" : captureIncompatible ? "incompatibleSession" : "retakeNote")}</p>
              {captureIncompatible && sample.capture_block_reason ? <details className="week7-capture-block-detail"><summary>{text("detail")}</summary><code>{sample.capture_block_reason}</code></details> : null}
            </section>
            <section className="panel week7-coverage">
              <div className="week7-panel-heading"><h2>{text("progress")}</h2><span className="mono">{text("coverage", { count: sample.completed_views ?? currentViews.length })}</span></div>
              <p className="week7-matrix-guide">{text("matrixGuide")}</p>
              <div className="week7-matrix-wrap" tabIndex={0} role="region" aria-label={text("progress")}><table className="week7-matrix"><thead><tr><th aria-label={text("progress")} />{WEEK7_ANGLES.map((value) => <th className="mono" scope="col" key={value}>{value}°</th>)}</tr></thead><tbody>{WEEK7_LIGHTS.map((light) => <tr key={light}><th scope="row">{text(light)}</th>{WEEK7_ANGLES.map((value) => { const view = currentViews.find((item) => item.angle_deg === value && item.lighting_mode === light); const missing = missingViews.some((item) => item.angle_deg === value && item.lighting_mode === light); const saved = Boolean(view && !missing); const active = saved ? selectedId === view.capture_id : !captureLocked && angle === value && lightingMode === light; return <td key={value}><button type="button" className={`week7-view-cell ${saved ? "is-saved" : "is-missing"} ${active ? "is-selected" : ""}`} disabled={busy || (!saved && captureLocked)} aria-pressed={active} aria-label={`${value}° · ${text(light)} · ${text(saved ? "saved" : "missing")}`} onClick={() => { if (saved) { setSelectedId(view.capture_id); setVariant("raw"); } else chooseMissingView({ angle_deg: value, lighting_mode: light }); }}>{saved ? <Check size={16} /> : <span aria-hidden="true">—</span>}<span>{text(saved ? "saved" : "missing")}</span></button></td>; })}</tr>)}</tbody></table></div>
              <p className="week7-coverage-note" role="status">{missingViews.length ? <><strong>{text("missingViews")}: </strong>{missingViews.map((view) => `${view.angle_deg}° ${text(view.lighting_mode)}`).join(" · ")}</> : text(complete ? "completedCoverage" : "allCaptured")}</p>
            </section>
            </div>
            {captureNotice ? <div className="week7-capture-success" role="status"><strong>{text("viewSaved", { angle: captureNotice.angle, light: text(captureNotice.lightingMode) })}</strong>{captureNotice.next ? <><span>{text("nextMissing", { angle: captureNotice.next.angle_deg, light: text(captureNotice.next.lighting_mode) })}</span><button type="button" className="button button--secondary" disabled={busy} onClick={() => chooseMissingView(captureNotice.next)}>{text("selectNext")}</button></> : <span>{text("allCaptured")}</span>}</div> : null}
            <div className="week7-evidence-layout">
              <section className="panel week7-viewer"><div className="week7-panel-heading"><div><h2>{text("image")}</h2>{selected ? <span className="week7-muted"><b className="mono">{selected.angle_deg}°</b> · {text(selected.lighting_mode)} · {text(currentIds.has(selected.capture_id) ? "current" : "superseded")}</span> : null}</div><div className="week7-image-tabs">{["raw", "annotated"].map((value) => <button type="button" key={value} aria-pressed={variant === value} onClick={() => setVariant(value)}>{text(value)}</button>)}</div></div>
                {selected && !imageFailed ? <img key={imageKey} className="week7-image" src={dataSource.imageUrl(selected.capture_id, variant)} alt={text("imageAlt", { variant: text(variant), angle: selected.angle_deg, light: text(selected.lighting_mode) })} onLoad={(event) => setDecodedImage({ key: imageKey, width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={() => setImageFailed(true)} /> : <div className="week7-image-empty"><Camera size={38} /><p>{text(imageFailed ? "imageFailure" : "noImage")}</p></div>}
                {selected ? <div className="week7-image-footer"><div className="week7-image-resolution" title={text("resolutionNote")}><span>{text("imageResolution")}</span><code>{!imageFailed && imageResolution.frameWidthPx ? `${imageResolution.resolution} px` : text(imageFailed ? "archiveMissing" : "imageLoading")}</code></div><details><summary>{text("archiveDetail")}</summary><dl><div><dt>{text("captureId")}</dt><dd><code>{selected.capture_id}</code></dd></div><div><dt>{text("sourceId")}</dt><dd><code>{selected.source_name}</code></dd></div><div><dt>{text("evidence")}</dt><dd><code>{sample.evidence_label}</code></dd></div>{selected.supersedes_capture_id ? <div><dt>{text("replaces")}</dt><dd><code>{selected.supersedes_capture_id}</code></dd></div> : null}</dl></details></div> : null}
              </section>
              <section className="panel week7-candidates"><div className="week7-panel-heading"><div><h2>{text("candidates")}</h2><p>{text("candidateNote")}</p></div></div><dl className="week7-measurements"><div><dt>{text("calibration")}</dt><dd>{text(selected?.calibration_status ?? selected?.calibration?.status ?? "pending")}</dd></div>{selected?.calibration_id ? <div><dt>{text("calibrationId")}</dt><dd><code>{selected.calibration_id}</code></dd></div> : null}{selected?.calibration?.reason ? <div className="week7-calibration-reason"><dt>{text("calibrationReason")}</dt><dd><span>{text(selected.calibration.valid ? "calibrationSimulation" : selected.calibration.reason === "unvalidated" ? "calibrationPending" : "calibrationUnavailable")}</span><details><summary>{text("detail")}</summary><code>{selected.calibration.reason}</code></details></dd></div> : null}{["size", "position"].map((key) => <div key={key}><dt>{text(key)}</dt><dd className="week7-unmeasured" aria-label={text("unmeasured")} title={text("unmeasured")}><span />{text("unmeasured")}</dd></div>)}</dl>
                {(selected?.candidates ?? []).length ? <div className="week7-candidate-list">{selected.candidates.map((candidate, index) => <article key={candidate.detection_id ?? index}><strong>{text(candidate.defect_type)}</strong><dl><div><dt>{text("bbox")}</dt><dd>{candidate.bbox_px?.join(", ") ?? "—"}</dd></div><div><dt>{text("area")}</dt><dd>{candidate.area_px ?? "—"}</dd></div><div><dt>{text("score")}</dt><dd>{typeof candidate.confidence === "number" ? candidate.confidence.toFixed(3) : "—"}</dd></div></dl></article>)}</div> : <p className="week7-muted week7-no-candidates">{text(selected ? "noCandidates" : "noImage")}</p>}
              </section>
            </div>
            <details className="panel week7-history"><summary><strong>{text("history")}</strong><span>{text("attempts", { count: captures.length })}</span></summary><div className="week7-history-list">{[...captures].reverse().map((item) => <button type="button" key={item.capture_id} className={selectedId === item.capture_id ? "is-selected" : ""} onClick={() => setSelectedId(item.capture_id)} aria-pressed={selectedId === item.capture_id}><code>{item.angle_deg}°</code><span>{text(item.lighting_mode)}</span><span>{text(currentIds.has(item.capture_id) ? "current" : "superseded")}</span><code>{item.capture_id}</code></button>)}</div></details>
            <details className="panel week7-diagnostics"><summary>{text("diagnostics")}</summary><p className="week7-muted">{text("diagnosticNote")}</p><dl>
              <div><dt>{text("latestEvent")}</dt><dd>{events.length ? text(events.at(-1).event_type) : text("noEvent")}</dd></div>
              <div><dt>{text("latestFailure")}</dt><dd>{latestFailure ? <><code>{latestFailure.details?.reason}</code><time>{latestFailure.occurred_at_utc}</time></> : text("noFault")}</dd></div>
              <div><dt>{text("lastOff")}</dt><dd>{lastOff ? <><span>{text(lastOff.event_type)}</span><time>{lastOff.occurred_at_utc}</time><code>{lastOff.details?.request_id}</code></> : text("noOff")}</dd></div>
            </dl><p className="week7-muted">{text("recentEvents")}</p><div className="week7-event-log">{events.slice(-12).reverse().map((event) => <details key={event.event_id}><summary><span>{text(event.event_type)}</span><time>{event.occurred_at_utc}</time></summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details>)}</div></details>
          </> : <section className="panel week7-empty"><Camera size={52} weight="duotone" /><p>{text("intro")}</p><h2>{text("empty")}</h2><span>{text("emptyBody")}</span></section>}
        </div>
      </main>
      <dialog className="week7-camera-dialog" ref={cameraDialog} aria-labelledby="week7-camera-guide-title"><h2 id="week7-camera-guide-title">{text("cameraGuide")}</h2><p>{text("cameraGuideBody")}</p><p>{text("simulatedControls")}</p><form method="dialog"><button autoFocus className="button button--primary" type="submit">{text("close")}</button></form></dialog>
    </div>
  );
}
