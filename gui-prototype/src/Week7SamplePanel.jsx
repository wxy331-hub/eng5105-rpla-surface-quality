import { useEffect, useMemo, useRef, useState } from "react";
import { Archive, ArrowLeft, ArrowsClockwise, Camera, Check, FileCsv, Info, Translate, Trash } from "@phosphor-icons/react";
import { useI18n } from "./i18n.jsx";
import { WEEK7_ANGLES, WEEK7_LIGHTS, week7DataSource, sampleCaptureState } from "./services/week7DataSource.js";
import { createResolutionMetadata } from "./services/resolutionMetadata.js";
import GlassSurface from "./GlassSurface.jsx";
import "./week7.css";

// Copy lives with this separate workbench so the public replay vocabulary stays stable.
const copy = {
  eyebrow: ["ENG5105 · PLAN A SAMPLE CAPTURE", "ENG5105 · 方案 A 样本采集"],
  title: ["Sample capture", "样本采集"],
  backToInspection: ["Back to inspection", "返回检测界面"],
  simulated: ["SIMULATED", "模拟来源"],
  sourceStatus: ["Capture source", "采集来源"],
  syntheticSource: ["Synthetic images", "合成图像"],
  cameraPending: ["Connect the camera and start the local camera service.", "请连接摄像头并启动本地摄像头服务。"],
  cameraGuide: ["Camera connection guide", "摄像头连接说明"],
  cameraGuideBody: ["Connect the Plan A USB/UVC camera to the computer running the local camera service. Select the device, requested mode and inspection ROI in the service startup configuration. The service owns the camera and shares its preview with this interface.", "将 Plan A USB/UVC 摄像头连接到运行本地摄像头服务的电脑。在服务启动配置中选择设备、请求模式和检测 ROI。服务统一读取摄像头，并向界面共享预览。"],
  simulatedControls: ["The selected angle and lighting mode identify each simulated view. Physical lighting and MCU outputs remain blocked.", "所选角度和照明模式用于标记每个模拟视图。物理照明及 MCU 输出仍被禁止。"],
  close: ["Close", "关闭"],
  intro: ["One specimen. Six angles. Two lighting modes.", "一个样本，六个角度，两种照明。"],
  boundary: ["Synthetic images · calibration pending · physical outputs blocked", "合成图像 · 标定待完成 · 物理输出已禁止"],
  cameraBoundary: ["Camera acquisition · calibration pending · physical outputs blocked", "相机采集 · 标定待完成 · 物理输出已禁止"],
  cameraBadge: ["CAMERA SERVICE", "摄像头服务"],
  sourceUnavailable: ["Waiting for camera source", "等待摄像头来源"],
  preview: ["Camera preview", "摄像头预览"],
  previewAlt: ["Live shared camera preview", "实时共享摄像头预览"],
  previewUnavailable: ["Preview unavailable. Check the camera connection, then retry.", "预览不可用，请检查摄像头连接后重试。"],
  previewNote: ["Shared inspection preview; saved captures retain the acquired image dimensions.", "共享检测预览；保存图像保留采集尺寸。"],
  cameraReady: ["Connected · capture available", "已连接 · 可采集"],
  cameraRecovering: ["Connected · waiting for a fresh stable frame", "已连接 · 等待新鲜稳定帧"],
  captureBlocked: ["Capture is unavailable until a fresh stable camera frame arrives.", "收到新鲜稳定的摄像头图像后方可采集。"],
  manualLighting: ["Set the specimen angle and lighting manually, then capture this view. Lighting is recorded as operator-declared; it has no sensor confirmation.", "手动调整样本角度和照明后，直接采集此视图。照明记录为操作员声明，尚无传感器确认。"],
  cameraDimensions: ["Acquired frame dimensions; requested mode is shown separately.", "采集帧尺寸；请求模式另行显示。"],
  requestedMode: ["Requested camera mode", "相机请求模式"],
  hardwarePending: ["Hardware validation pending", "待实机验证"],
  connectionState: ["Connection state", "连接状态"],
  HEALTHY: ["Healthy", "连接稳定"],
  CONNECTING: ["Connecting", "连接中"],
  RECONNECTING: ["Reconnecting", "重连中"],
  DISCONNECTED: ["Disconnected", "已断开"],
  STALE: ["Stale frame", "图像已过期"],
  SYNTHETIC: ["Explicit offline simulation", "显式离线模拟"],
  samples: ["Sample sessions", "样本会话"],
  sampleId: ["Sample ID", "样本编号"],
  placeholder: ["e.g. SAMPLE-001", "例如 SAMPLE-001"],
  create: ["Create sample", "创建样本"],
  newConfiguration: ["New session images", "新会话图像"],
  nativeSynthetic: ["Generated at these pixel dimensions", "按此像素尺寸原生生成合成图像"],
  configurationUnavailable: ["Capture configuration unavailable", "采集配置暂不可用"],
  waitingFirstFrame: ["Waiting for first frame", "等待首帧"],
  cameraDeferred: ["Connect and verify the configured camera, then select Connect camera.", "接入并核对配置设备后，点击连接摄像头。"],
  cameraDisconnected: ["Camera service running · verify the configured device and retry.", "摄像头服务已启动 · 请核对配置设备后重试。"],
  connectCamera: ["Connect camera", "连接摄像头"],
  device: ["Configured device", "配置设备"],
  backend: ["Capture backend", "采集后端"],
  configuredSource: ["Configured source name", "配置来源名称"],
  identityNote: ["The source name is a configuration label. A device index does not confirm a camera model.", "来源名称为配置标签；设备索引不构成摄像头型号识别。"],
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
  capture_bright_field: ["Capture bright field", "采集明场图"],
  capture_dark_field: ["Capture dark field", "采集暗场图"],
  retake_bright_field: ["Retake bright field", "重拍明场图"],
  retake_dark_field: ["Retake dark field", "重拍暗场图"],
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
  imageResolution: ["Saved image", "保存图像"],
  imageLoading: ["Loading image", "正在加载图像"],
  resolutionNote: ["Pixel dimensions of this saved image. Camera capture settings are configured separately.", "此保存图像的像素尺寸；相机采集参数单独配置。"],
  archiveDetail: ["Archive details", "归档详情"],
  captureId: ["Capture ID", "采集编号"],
  sourceId: ["Recorded source ID", "归档来源编号"],
  archiveMissing: ["Files missing", "文件缺失"],
  raw: ["Raw", "原图"],
  annotated: ["Annotated", "标注图"],
  imageAlt: ["{variant} saved image at {angle} degrees, {light}", "{angle} 度{light}保存图像：{variant}"],
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
  width_bulge_candidate: ["Local bulge candidate", "局部鼓包候选"],
  width_neck_candidate: ["Local neck candidate", "局部缩颈候选"],
  width_out_of_range_candidate: ["Width outside reference range", "宽度超出参考范围"],
  unmeasuredStretches: ["Unmeasured stretches (not defects)", "未测区段（不是缺陷）"],
  surface_bright_spot_candidate: ["Bright spot candidate (possible glare)", "亮斑候选（反光待复核）"],
  surface_dark_spot_candidate: ["Dark spot candidate", "暗斑候选"],
  surface_scratch_candidate: ["Dark line candidate (possible scratch)", "暗线候选（疑似划痕，待复核）"],
  surface_texture_deviation_candidate: ["Texture clearly deviates from the reference", "纹理明显偏离参照"],
  surface_demo_roughness_candidate: ["Rough surface (demo thresholds, uncalibrated)", "表面粗糙（演示门限，未标定）"],
  surface_contamination_candidate: ["Contamination candidate (dark mark, review required)", "污染候选（局部黑斑，待复核）"],
  surface_texture_direction_candidate: ["Texture direction anomaly: dark line across the filament (possible crack, review required)", "纹理方向异常：横穿丝材的暗线（可能断裂，待复核）"],
  surfaceAnalysis: ["Surface analysis", "表面分析"],
  surfaceMetrics: ["Texture {texture} · streaks {streaks} (relative contrast)", "纹理 {texture} · 条纹 {streaks}（相对对比度）"],
  surfaceRatio: ["{ratio}× the reference {reference}", "为参照 {reference} 的 {ratio} 倍"],
  surface_near_reference: ["Close to the reference", "接近参照"],
  surface_near_reference_with_local_candidates: ["Close to the reference; local candidates to review", "接近参照；有局部候选待复核"],
  surface_deviates: ["Deviates from the reference", "偏离参照"],
  surface_strongly_deviates: ["Clearly deviates from the reference", "明显偏离参照"],
  surface_not_graded: ["Metrics only, not graded (no comparable reference)", "只给指标，未分级（没有可比的参照）"],
  surface_reference_metric_too_low: ["Reference metric too low to show the surface is close", "参照指标过低，无法判断是否接近参照"],
  surface_not_graded_bright_structure: ["Long bright structure (possible glare); grade suspended", "存在细长亮结构（可能是反光），暂停分级"],
  surface_not_judged: ["Surface not judged", "表面未判定"],
  surface_demo_good: ["Surface roughness: good (demo thresholds, uncalibrated)", "表面粗糙度：良好（演示门限，未标定）"],
  surface_demo_moderately_rough: ["Surface roughness: moderately rough (demo thresholds, uncalibrated)", "表面粗糙度：中等粗糙（演示门限，未标定）"],
  surface_demo_clearly_rough: ["Surface roughness: clearly rough (demo thresholds, uncalibrated)", "表面粗糙度：明显粗糙（演示门限，未标定）"],
  surfaceScope: ["Bench demo starting point; not a validated quality grade.", "台架演示起点，不是经过验证的质量等级。"],
  geometryCandidateNote: ["Geometry candidates are ranked by how far the width change exceeds its limit; the score is not a defect probability. Sizes are in pixels.", "几何候选按宽度变化超出门限的程度排序，分数不表示缺陷概率；尺寸单位为像素。"],
  analysis: ["Geometry analysis", "几何分析"],
  analysis_valid: ["Judged", "已判定"],
  analysis_rejected: ["Not judged", "未判定"],
  analysis_not_assessed: ["Not assessed in this phase", "本阶段不评估"],
  analysisRejectedBody: ["This view was archived but not judged, so an empty candidate list does not mean the specimen is defect-free.", "此视图已归档但未判定，候选为空不代表样本无缺陷。"],
  edgeWidth: ["Edge width / limit (px)", "边缘宽度 / 门限（px）"],
  reasonCodes: ["Reason codes", "原因代码"],
  reason_FOCUS_INADEQUATE: ["Edges are too blurred for the configured feature size.", "边缘过于模糊，达不到设定的特征尺度。"],
  reason_FOCUS_UNVERIFIABLE: ["The outline cannot verify the required sharpness: either out of focus or a material whose edge images softly. View not judged; manual inspection recommended.", "轮廓无法验证所需清晰度：可能失焦，也可能是材料边缘本身成像偏软，本视图未判定，建议人工识别。"],
  reason_SAMPLE_NOT_LOCALIZED: ["No specimen was found in the search area.", "检测区域内未找到样本。"],
  reason_SEGMENTATION_AMBIGUOUS: ["More than one separate object is in view; check the placement and whether the filament is broken.", "视野中有多个分离的物体；请检查摆放，以及丝材是否断开。"],
  reason_BACKGROUND_BAND_OBSTRUCTED: ["The background at the sides of the search area is obstructed.", "检测区域两侧的背景被遮挡。"],
  reason_AXIS_COVERAGE_LOW: ["The specimen does not span the search area; check the position and whether the filament is broken or has a gap.", "样本未贯穿检测区域；请检查位置，以及丝材是否断开或有间隙。"],
  reason_AXIS_ORIENTATION_UNEXPECTED: ["The specimen is not along the configured axis.", "样本方向与配置不符。"],
  reason_SPECIMEN_TOO_NARROW: ["The specimen is too narrow to measure both edges.", "样本过窄，无法测量两侧边缘。"],
  reason_EDGES_NOT_RESOLVED: ["Edges could not be measured along enough of the specimen.", "可测量边缘的轴向覆盖不足。"],
  reason_EXPOSURE_CLIPPED: ["Specimen pixels are clipped by exposure.", "样本区域曝光截断。"],
  reason_CURVATURE_OUT_OF_SCOPE: ["The specimen bends beyond the supported range; clamp it straight.", "样本弯曲超出支持范围，请夹直后重拍。"],
  reason_DEMO_ANGLE_NOT_SUPPORTED: ["The demo roughness grade applies to 0° bright-field views only.", "演示粗糙度分级只适用于 0° 明场视图。"],
  reason_GLARE_OR_BRIGHT_STRUCTURE_AMBIGUOUS: ["A long bright structure (possible glare) suspends the surface grade; adjust the light.", "存在细长亮结构（可能是反光），表面分级暂停；请调整灯位。"],
  reason_DARK_FIELD_GEOMETRY_NOT_IN_PHASE_1: ["Dark-field geometry is not assessed in this phase.", "本阶段不评估暗场几何。"],
  summary_candidates_present: ["Geometry candidates present", "存在几何候选"],
  summary_no_geometry_candidates_in_assessed_scope: ["No geometry candidates within the assessed scope", "在已评估范围内未发现几何候选"],
  summary_geometry_coverage_incomplete: ["Geometry coverage incomplete; no sample-level conclusion", "几何覆盖不完整，不给出试样结论"],
  summaryCounts: ["{valid}/6 bright-field views judged · surface not assessed", "{valid}/6 个明场视图已判定 · 表面未评估"],
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
  cameraDiagnostics: ["Capture / lighting log", "采集 / 照明日志"],
  cameraDiagnosticNote: ["Acquisition events and operator-declared lighting metadata. Physical lighting and MCU outputs are not controlled by this interface.", "以下记录采集事件和操作员声明的照明信息。此界面尚未控制物理照明与 MCU 输出。"],
  diagnosticNote: ["Recorded simulated messages; physical lighting and MCU outputs remain blocked.", "以下为模拟消息记录；物理照明及 MCU 输出仍被禁止。"],
  latestEvent: ["Latest recorded event", "最近记录事件"],
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
  MANUAL_LIGHTING_DECLARED: ["Lighting declared by operator", "操作员已声明照明模式"],
  LIGHTING_DECLARED: ["Lighting declared by operator", "操作员已声明照明模式"],
  CAMERA_CAPTURE_REQUESTED: ["Camera capture requested", "已请求摄像头采集"],
  CAPTURE_CONFIGURATION: ["Capture configuration recorded", "已记录采集配置"],
  OPERATOR_CAPTURE_REQUEST: ["Operator requested one view", "操作员请求单视图采集"],
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
  const [cameraGuideOpen, setCameraGuideOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [variant, setVariant] = useState("raw");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [imageFailed, setImageFailed] = useState(false);
  const [decodedImage, setDecodedImage] = useState(null);
  const [previewFailed, setPreviewFailed] = useState(false);
  const [previewRevision, setPreviewRevision] = useState(0);
  const [previewDimensions, setPreviewDimensions] = useState(null);
  const cameraState = sampleCaptureState(serviceHealth);
  const archiveSynthetic = sample?.evidence_label === "OFFLINE_SYNTHETIC_ONLY";
  const requestedMode = serviceHealth?.camera?.requested_mode;
  const captures = sample?.captures ?? [];
  const currentViews = sample?.current_views ?? [];
  const missingViews = sample?.missing_views ?? [];
  const selected = captures.find((item) => item.capture_id === selectedId)
    ?? currentViews.find((item) => item.capture_id === selectedId) ?? null;
  const calibrationReasons = [...new Set([
    selected?.calibration?.reason,
    ...(Array.isArray(selected?.calibration?.reasons) ? selected.calibration.reasons : []),
  ].filter((reason) => typeof reason === "string" && reason.trim()).map((reason) => reason.trim()))];
  const analysis = selected?.analysis ?? null;
  // Only reasons with operator copy are listed; the raw codes stay in the detail.
  const analysisReasons = (analysis?.reason_codes ?? []).filter((code) => copy[`reason_${code}`]);
  const edgeWidth = analysis?.metrics?.edge_spread_px_median;
  const inspectionSummary = sample?.inspection_summary ?? null;
  const surface = analysis?.surface ?? null;
  const surfaceLabel = surface ? (surface.status === "valid" ? surface.comparison?.quality_label ?? "not_graded" : "not_judged") : null;
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
    synthetic: archiveSynthetic,
  });
  const newResolution = createResolutionMetadata({
    widthPx: serviceHealth?.image_size_px?.[0], heightPx: serviceHealth?.image_size_px?.[1], synthetic: cameraState.synthetic,
  });
  const sessionResolution = createResolutionMetadata({
    widthPx: sample?.capture_configuration?.image_size_px?.[0],
    heightPx: sample?.capture_configuration?.image_size_px?.[1], synthetic: archiveSynthetic,
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

  // Poll only while the workbench is mounted. A failed poll revokes capture immediately.
  useEffect(() => {
    let active = true;
    let timer;
    let pollInterval = 2000;
    const poll = async () => {
      try {
        const next = await dataSource.getHealth();
        pollInterval = 2000;
        if (active) { setServiceHealth(next); setPendingDeletions(pendingDeletionSessions(next)); }
      } catch {
        pollInterval = Math.min(pollInterval * 2, 30000);
        if (active) setServiceHealth(null);
      } finally { if (active) timer = window.setTimeout(poll, pollInterval); }
    };
    if (typeof dataSource.getHealth === "function") timer = window.setTimeout(poll, pollInterval);
    return () => { active = false; window.clearTimeout(timer); };
  }, [dataSource]);

  useEffect(() => {
    setPreviewFailed(false);
    setPreviewDimensions(null);
    setPreviewRevision((value) => value + 1);
  }, [cameraState.available, serviceHealth?.camera?.generation]);

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
    if (!sample || busy || captureLocked || !cameraState.available) return;
    if (viewExists && !window.confirm(text("confirmRetake", { angle, light: text(lightingMode) }))) return;
    run(async () => {
      try {
        const next = await dataSource.capture(sample.session_id, angle, { lightingMode, retake: viewExists });
        applySample(next, angle, lightingMode);
        setVariant("raw");
        setCaptureNotice({ angle, lightingMode, next: next.missing_views?.[0] ?? null });
      } catch (cause) {
        if (cause.sample) applySample(cause.sample, angle);
        if (cause.status === 503 || cause.status === 0) setServiceHealth(null);
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

  const reconnect = () => run(async () => {
    setPreviewFailed(false);
    setPreviewRevision((value) => value + 1);
    setServiceHealth(null);
    await dataSource.reconnect();
    setServiceHealth(await dataSource.getHealth());
  });

  return (
    <div className="week7-shell">
      <header className="week7-topbar">
        <div className="week7-brand"><Camera size={29} weight="duotone" /><div><p>{text("eyebrow")}</p><h1>{text("title")}</h1></div></div>
        <div className="week7-topbar-actions"><a className="button button--secondary week7-back-link" href="#inspection"><ArrowLeft size={17} aria-hidden="true" />{text("backToInspection")}</a><span className="week7-badge">{text(cameraState.synthetic ? "simulated" : "cameraBadge")}</span><label className="week7-language"><Translate size={18} /><select aria-label={text("language")} value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option><option value="zh-CN">简体中文</option></select></label></div>
      </header>
      <div className="week7-boundary"><Info size={17} /><span>{text(cameraState.synthetic ? "boundary" : "cameraBoundary")}</span><code>{serviceHealth?.evidence_label ?? "—"}</code></div>
      <main className="week7-layout">
        <aside className="week7-sessions panel">
          <div className="week7-panel-heading"><h2>{text("samples")}</h2><button className="week7-icon-button" type="button" title={text("refresh")} aria-label={text("refresh")} disabled={busy} onClick={refresh}><ArrowsClockwise size={18} /></button></div>
          <form className="week7-create" onSubmit={createSample}>
            <div className="week7-new-configuration"><span>{text("newConfiguration")}</span><strong className="mono">{newResolution.frameWidthPx ? `${newResolution.resolution} px` : text(requestedMode ? "waitingFirstFrame" : "configurationUnavailable")}</strong>{newResolution.frameWidthPx ? <small>{text(cameraState.synthetic ? "nativeSynthetic" : "cameraDimensions")}</small> : null}{requestedMode ? <><span>{text("requestedMode")}</span><strong className="mono">{requestedMode.width_px} × {requestedMode.height_px}<br />{requestedMode.pixel_format} · {requestedMode.fps} FPS</strong><small>{text("hardwarePending")}</small></> : null}</div>
            <label htmlFor="week7-sample-id">{text("sampleId")}</label><input id="week7-sample-id" value={sampleId} onChange={(event) => setSampleId(event.target.value)} placeholder={text("placeholder")} required maxLength={100} disabled={busy} autoComplete="off" /><button className="button button--primary" type="submit" disabled={busy || configurationUnavailable || !sampleId.trim()}><Archive size={17} />{text("create")}</button>
          </form>
          <p className="week7-list-label">{text("resume")}</p>
          <div className="week7-session-list">{sessions.length ? sessions.map((item) => <div className="week7-session-row" key={item.session_id}><button type="button" className={`week7-session ${sample?.session_id === item.session_id ? "is-selected" : ""}`} aria-pressed={sample?.session_id === item.session_id} disabled={busy} onClick={() => openSession(item.session_id)}><strong className="mono">{item.sample_id}</strong><span>{text(item.status)}</span><small className="mono">{item.session_id}</small></button><button type="button" className="week7-delete-session" aria-label={text("deleteSession", { sample: item.sample_id, session: item.session_id.slice(0, 8) })} title={text("deleteSession", { sample: item.sample_id, session: item.session_id.slice(0, 8) })} disabled={busy} onClick={() => deleteSession(item)}><Trash size={17} aria-hidden="true" /></button></div>) : <p className="week7-muted">{text("emptySessions")}</p>}</div>
        </aside>
        <div className="week7-workspace" aria-busy={busy}>
          <section className="panel week7-source-status"><div><h2>{text("sourceStatus")}</h2><strong className="mono">{cameraState.sourceName ?? text("sourceUnavailable")}</strong><span role="status">{text(cameraState.synthetic ? "SYNTHETIC" : cameraState.available ? "cameraReady" : cameraState.connected ? "cameraRecovering" : serviceHealth?.camera?.connection_deferred ? "cameraDeferred" : serviceHealth ? "cameraDisconnected" : "cameraPending")} · {text(cameraState.status)}</span></div><div className="week7-source-actions">{!cameraState.synthetic ? <button type="button" className="button button--secondary" disabled={busy} onClick={reconnect}><ArrowsClockwise size={17} />{text(serviceHealth?.camera?.connection_deferred ? "connectCamera" : "retry")}</button> : null}<button type="button" className="button button--secondary" onClick={() => { cameraDialog.current?.showModal(); setCameraGuideOpen(true); }}><Info size={17} aria-hidden="true" />{text("cameraGuide")}</button></div></section>
          {!cameraState.synthetic ? <section className="panel week7-preview"><div className="week7-panel-heading"><h2>{text("preview")}</h2><span className="mono">{cameraState.available && !previewFailed && previewDimensions ? `${previewDimensions.width} × ${previewDimensions.height} px` : "—"}</span></div>{cameraState.available && !previewFailed ? <img key={previewRevision} className="week7-image" src={dataSource.previewUrl(previewRevision)} alt={text("previewAlt")} onLoad={(event) => setPreviewDimensions({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={() => setPreviewFailed(true)} /> : <div className="week7-image-empty"><Camera size={38} /><p>{text(previewFailed ? "previewUnavailable" : "captureBlocked")}</p></div>}<p className="week7-preview-note">{text("previewNote")}</p></section> : null}
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
                <button className="button button--primary" type="button" disabled={busy || !cameraState.available} onClick={capture}><Camera size={18} />{text(busy ? "busy" : `${viewExists ? "retake" : "capture"}_${lightingMode}`)}</button>
                <p className="week7-muted">{text(cameraState.synthetic ? "simulatedControls" : cameraState.available ? "manualLighting" : "captureBlocked")}</p>
              </div>}
              <p className="week7-muted">{text(sample.status === "incomplete_archive" ? "archiveLockedNote" : complete ? "completeNote" : captureIncompatible ? "incompatibleSession" : "retakeNote")}</p>
              {captureIncompatible && sample.capture_block_reason ? <details className="week7-capture-block-detail"><summary>{text("detail")}</summary><code>{sample.capture_block_reason}</code></details> : null}
            </section>
            <section className="panel week7-coverage">
              <div className="week7-panel-heading"><h2>{text("progress")}</h2><span className="mono">{text("coverage", { count: sample.completed_views ?? currentViews.length })}</span></div>
              <p className="week7-matrix-guide">{text("matrixGuide")}</p>
              <div className="week7-matrix-wrap" tabIndex={0} role="region" aria-label={text("progress")}><table className="week7-matrix"><thead><tr><th aria-label={text("progress")} />{WEEK7_ANGLES.map((value) => <th className="mono" scope="col" key={value}>{value}°</th>)}</tr></thead><tbody>{WEEK7_LIGHTS.map((light) => <tr key={light}><th scope="row">{text(light)}</th>{WEEK7_ANGLES.map((value) => { const view = currentViews.find((item) => item.angle_deg === value && item.lighting_mode === light); const missing = missingViews.some((item) => item.angle_deg === value && item.lighting_mode === light); const saved = Boolean(view && !missing); const active = saved ? selectedId === view.capture_id : !captureLocked && angle === value && lightingMode === light; return <td key={value}><button type="button" className={`week7-view-cell ${saved ? "is-saved" : "is-missing"} ${active ? "is-selected" : ""}`} disabled={busy || (!saved && captureLocked)} aria-pressed={active} aria-label={`${value}° · ${text(light)} · ${text(saved ? "saved" : "missing")}`} onClick={() => { if (saved) { setSelectedId(view.capture_id); setVariant("raw"); } else chooseMissingView({ angle_deg: value, lighting_mode: light }); }}>{saved ? <Check size={16} /> : <span aria-hidden="true">—</span>}<span>{text(saved ? "saved" : "missing")}</span></button></td>; })}</tr>)}</tbody></table></div>
              <p className="week7-coverage-note" role="status">{missingViews.length ? <><strong>{text("missingViews")}: </strong>{missingViews.map((view) => `${view.angle_deg}° ${text(view.lighting_mode)}`).join(" · ")}</> : text(complete ? "completedCoverage" : "allCaptured")}</p>
              {inspectionSummary ? <p className={`week7-inspection-summary is-${inspectionSummary.conclusion}`} role="status"><strong>{text(`summary_${inspectionSummary.conclusion}`)}</strong><span>{text("summaryCounts", { valid: inspectionSummary.geometry_valid_angles.length })}</span></p> : null}
            </section>
            </div>
            {captureNotice ? <div className="week7-capture-success" role="status"><strong>{text("viewSaved", { angle: captureNotice.angle, light: text(captureNotice.lightingMode) })}</strong>{captureNotice.next ? <><span>{text("nextMissing", { angle: captureNotice.next.angle_deg, light: text(captureNotice.next.lighting_mode) })}</span><button type="button" className="button button--secondary" disabled={busy} onClick={() => chooseMissingView(captureNotice.next)}>{text("selectNext")}</button></> : <span>{text("allCaptured")}</span>}</div> : null}
            <div className="week7-evidence-layout">
              <section className="panel week7-viewer"><div className="week7-panel-heading"><div><h2>{text("image")}</h2>{selected ? <span className="week7-muted"><b className="mono">{selected.angle_deg}°</b> · {text(selected.lighting_mode)} · {text(currentIds.has(selected.capture_id) ? "current" : "superseded")}</span> : null}</div><div className="week7-image-tabs">{["raw", "annotated"].map((value) => <button type="button" key={value} aria-pressed={variant === value} onClick={() => setVariant(value)}>{text(value)}</button>)}</div></div>
                {selected && !imageFailed ? <img key={imageKey} className="week7-image" src={dataSource.imageUrl(selected.capture_id, variant)} alt={text("imageAlt", { variant: text(variant), angle: selected.angle_deg, light: text(selected.lighting_mode) })} onLoad={(event) => setDecodedImage({ key: imageKey, width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={() => setImageFailed(true)} /> : <div className="week7-image-empty"><Camera size={38} /><p>{text(imageFailed ? "imageFailure" : "noImage")}</p></div>}
                {selected ? <div className="week7-image-footer"><div className="week7-image-resolution" title={text("resolutionNote")}><span>{text("imageResolution")}</span><code>{!imageFailed && imageResolution.frameWidthPx ? `${imageResolution.resolution} px` : text(imageFailed ? "archiveMissing" : "imageLoading")}</code></div><details><summary>{text("archiveDetail")}</summary><dl><div><dt>{text("captureId")}</dt><dd><code>{selected.capture_id}</code></dd></div><div><dt>{text("sourceId")}</dt><dd><code>{selected.source_name}</code></dd></div><div><dt>{text("evidence")}</dt><dd><code>{sample.evidence_label}</code></dd></div>{selected.supersedes_capture_id ? <div><dt>{text("replaces")}</dt><dd><code>{selected.supersedes_capture_id}</code></dd></div> : null}</dl></details></div> : null}
              </section>
              <section className="panel week7-candidates"><div className="week7-panel-heading"><div><h2>{text("candidates")}</h2><p>{text(analysis ? "geometryCandidateNote" : "candidateNote")}</p></div></div><dl className="week7-measurements"><div><dt>{text("calibration")}</dt><dd>{text(selected?.calibration_status ?? selected?.calibration?.status ?? "pending")}</dd></div>{selected?.calibration_id ? <div><dt>{text("calibrationId")}</dt><dd><code>{selected.calibration_id}</code></dd></div> : null}{calibrationReasons.length ? <div className="week7-calibration-reason"><dt>{text("calibrationReason")}</dt><dd><span>{text(selected.calibration.valid && archiveSynthetic ? "calibrationSimulation" : calibrationReasons.includes("unvalidated") || (selected.calibration_status ?? selected.calibration.status) === "not_calibrated" ? "calibrationPending" : "calibrationUnavailable")}</span><details><summary>{text("detail")}</summary><code>{calibrationReasons.join("; ")}</code></details></dd></div> : null}{["size", "position"].map((key) => <div key={key}><dt>{text(key)}</dt><dd className="week7-unmeasured" aria-label={text("unmeasured")} title={text("unmeasured")}><span />{text("unmeasured")}</dd></div>)}</dl>
                {analysis ? <div className={`week7-analysis is-${analysis.geometry_status}`} role="status"><strong>{text("analysis")} · {text(`analysis_${analysis.geometry_status}`)}</strong>{analysisReasons.length ? <ul>{analysisReasons.map((code) => <li key={code}>{text(`reason_${code}`)}</li>)}</ul> : null}{typeof edgeWidth === "number" ? <span className="mono">{text("edgeWidth")}: {edgeWidth.toFixed(1)} / {Number(analysis.parameters?.effective_edge_spread_limit_px).toFixed(1)}</span> : null}{(analysis.unmeasured_stretches ?? []).length ? <span>{text("unmeasuredStretches")}: {analysis.unmeasured_stretches.length}</span> : null}{surface ? <div className="week7-surface"><strong>{text("surfaceAnalysis")} · {text(`surface_${surfaceLabel}`)}</strong>{surface.status === "valid" ? <span className="mono">{text("surfaceMetrics", { texture: Number(surface.metrics.texture_mad).toFixed(5), streaks: Number(surface.metrics.longitudinal_energy).toFixed(5) })}</span> : <span>{(surface.reason_codes ?? []).join(" ")}</span>}{typeof surface.comparison?.ratio === "number" ? <span>{text("surfaceRatio", { ratio: surface.comparison.ratio.toFixed(2), reference: surface.comparison.reference_id })}</span> : null}<small>{text("surfaceScope")}</small></div> : null}<details><summary>{text("reasonCodes")}</summary><code>{(analysis.reason_codes ?? []).join(" ")}</code></details></div> : null}
                {(selected?.candidates ?? []).length ? <div className="week7-candidate-list">{selected.candidates.map((candidate, index) => <article key={candidate.detection_id ?? index}><strong>{text(candidate.defect_type)}</strong><dl><div><dt>{text("bbox")}</dt><dd>{candidate.bbox_px?.join(", ") ?? "—"}</dd></div><div><dt>{text("area")}</dt><dd>{candidate.area_px ?? "—"}</dd></div><div><dt>{text("score")}</dt><dd>{typeof candidate.confidence === "number" ? candidate.confidence.toFixed(3) : "—"}</dd></div></dl></article>)}</div> : <p className="week7-muted week7-no-candidates">{text(!selected ? "noImage" : analysis && analysis.geometry_status !== "valid" ? "analysisRejectedBody" : "noCandidates")}</p>}
              </section>
            </div>
            <details className="panel week7-history"><summary><strong>{text("history")}</strong><span>{text("attempts", { count: captures.length })}</span></summary><div className="week7-history-list">{[...captures].reverse().map((item) => <button type="button" key={item.capture_id} className={selectedId === item.capture_id ? "is-selected" : ""} onClick={() => setSelectedId(item.capture_id)} aria-pressed={selectedId === item.capture_id}><code>{item.angle_deg}°</code><span>{text(item.lighting_mode)}</span><span>{text(currentIds.has(item.capture_id) ? "current" : "superseded")}</span><code>{item.capture_id}</code></button>)}</div></details>
            <details className="panel week7-diagnostics"><summary>{text(archiveSynthetic ? "diagnostics" : "cameraDiagnostics")}</summary><p className="week7-muted">{text(archiveSynthetic ? "diagnosticNote" : "cameraDiagnosticNote")}</p><dl>
              <div><dt>{text("latestEvent")}</dt><dd>{events.length ? text(events.at(-1).event_type) : text("noEvent")}</dd></div>
              <div><dt>{text("latestFailure")}</dt><dd>{latestFailure ? <><code>{latestFailure.details?.reason ?? latestFailure.details?.error}</code><time>{latestFailure.occurred_at_utc}</time></> : text("noFault")}</dd></div>
              {archiveSynthetic ? <div><dt>{text("lastOff")}</dt><dd>{lastOff ? <><span>{text(lastOff.event_type)}</span><time>{lastOff.occurred_at_utc}</time><code>{lastOff.details?.request_id}</code></> : text("noOff")}</dd></div> : null}
            </dl><p className="week7-muted">{text("recentEvents")}</p><div className="week7-event-log">{events.slice(-12).reverse().map((event) => <details key={event.event_id}><summary><span>{text(event.event_type)}</span><time>{event.occurred_at_utc}</time></summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details>)}</div></details>
          </> : <section className="panel week7-empty"><Camera size={52} weight="duotone" /><p>{text("intro")}</p><h2>{text("empty")}</h2><span>{text("emptyBody")}</span></section>}
        </div>
      </main>
      <dialog className="week7-camera-dialog" ref={cameraDialog} onClose={() => setCameraGuideOpen(false)} aria-labelledby="week7-camera-guide-title">{cameraGuideOpen ? <GlassSurface><h2 id="week7-camera-guide-title">{text("cameraGuide")}</h2><p>{text("cameraGuideBody")}</p><p>{text(cameraState.synthetic ? "simulatedControls" : "manualLighting")}</p><p><code>{dataSource.baseUrl}</code></p>{serviceHealth?.camera ? <><p>{text("configuredSource")}: <code>{cameraState.sourceName}</code><br />{text("device")}: <code>{String(serviceHealth.camera.device ?? "—")}</code><br />{text("backend")}: <code>{serviceHealth.camera.backend ?? "—"}</code></p><p>{text("identityNote")}</p></> : null}<form method="dialog"><button autoFocus className="button button--primary" type="submit">{text("close")}</button></form></GlassSurface> : null}</dialog>
    </div>
  );
}
