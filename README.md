# ENG5105 — rPLA Filament Surface-Quality Monitoring

The default working directory is `D:\12591\Documents\5105`.
Codex project instructions are maintained in [AGENTS.md](AGENTS.md).
The dated presentation projects and earlier report workflow materials are retained
alongside the current software and the final report archive.

The 2026-09-08 review fixes and their verification are recorded in
[the implementation follow-up](docs/code_review_fixes_20260908.md).

The Plan A profile now uses a static-specimen geometry inspector
(`static-rpla-geometry-2`): it measures the projected width of a held specimen
in bright field and reports why a view was not judged instead of reporting it
as defect-free. Its design, parameters, reason codes and the remaining phases
are in [docs/static_rpla_inspection.md](docs/static_rpla_inspection.md).
Saved images can be replayed with
`.\.venv\Scripts\python.exe scripts/replay_static_inspection.py IMAGE ...`.

A laboratory-scale machine-vision system that inspects held recycled PLA (rPLA) filament
for visible surface anomalies, and records each finding as a
traceable candidate event.

Built for the ENG5105 Integrated Design brief from BioLoop Manufacturing Pty Ltd,
which asks electrical teams to select one product quality parameter and design an
online monitoring solution. This team selected **surface quality**.

## Status and evidence boundary

Read this before quoting any number out of this repository.

This is a **proposal-stage prototype**, not a validated defect detector. The
software runs end to end on a Windows development host, but nothing here
establishes rPLA defect accuracy, minimum detectable size, millimetre position
accuracy or usable line speed.

| Established | Not established |
|---|---|
| MJPEG transport, decode, inspection and persistence run continuously | Zero frame loss, or any accuracy figure |
| Candidate regions are detected, recorded and served with provenance fields | That a candidate is a real defect |
| Health gating, recovery and stale-frame downgrade behave as specified in unit tests | The same behaviour on Raspberry Pi, or under real network load |
| A 30 s SVGA integration run observed 10.77 processed frames/s | The proposed 20 frames/s requirement (not met) |

Physical quantities stay honest by construction: `size_mm` and `position_mm`
remain `null` unless the record carries a `calibration_id`, enforced in
`DetectionRecord.__post_init__`. The `confidence` field is an uncalibrated
ranking score derived from pixel area — **not** a probability that a region is a
defect. No actuator output is enabled.

Real-material calibration and validation begin only after the scheduled material
receipt gate.

## Camera sources and shared pipeline

### 本机相机展示

接上外接 USB 相机后，在项目根目录双击 `START_CAMERA_DEMO.cmd`，浏览器会打开
<http://127.0.0.1:5177/>。默认使用此前在这台电脑识别的 DirectShow 设备 `1`，
请求 UHD / MJPG；实际分辨率和刷新状态以连接后的界面为准。
点击画面下方的 **Fullscreen view / 全屏展示** 放大画面，按 Esc 或点击退出全屏返回。
右上角可切换中英文，**Reconnect camera stream / 重新连接相机** 用于重新连接。

未接相机时显示等待连接状态。展示结束后双击 `STOP_CAMERA_DEMO.cmd` 释放相机和本次服务。
再次启动前先停止旧服务；仅关闭网页不会停止采集。展示产生的样本记录单独存放在
`data/output/camera_demo/`，日志位于 `data/output/week8_runtime/`。

只预览界面而不打开设备时，在根目录运行 `./START_CAMERA_DEMO.cmd -WaitForCamera`；
需要确认启动配置时运行 `./START_CAMERA_DEMO.cmd -CheckConfig`。
设备编号在换电脑或改变设备连接后可能变化，确认编号后可用 `-CameraDevice 2` 覆盖。
当前展示用于查看相机画面与采集流程；材料缺陷判定和毫米测量仍需实物验证与标定。

The GUI defaults to the Plan A ALC-IMX258 USB/UVC camera service. Inspection,
camera preview and the sample workbench share one acquisition process. Without
a connected camera the interface shows the connection state and disables capture.
The sample workbench saves one selected angle/lighting view per click, with raw
and annotated images, retake history and CSV traceability. Camera connection
evidence does not establish optical calibration or defect performance.

The resident software accepts either Plan A's ALC-IMX258 USB/UVC source or Plan B's
ESP32S3/OV3660 network MJPEG source through the same `CameraSource` / `FramePacket`
contract. The Week 8 launcher selects Plan A explicitly; the legacy live launcher
retains its Plan B configuration. The USB adapter has hardware-free software tests. Its requested capture
modes and provisional inspection settings are not camera-performance results.

```
Controlled optical head + rPLA filament
        |
        v
ALC-IMX258 USB/UVC or XIAO ESP32S3 Sense / OV3660 MJPEG ───────────┐
                                                                    v
                                          Raspberry Pi 4 (target deployment)
                                            - OpenCV candidate detection
                                            - SQLite evidence store
                                            - REST + WebSocket API :8765
                                            - shared MJPEG output
                                                    |
                                          React GUI :5173
                                                    ^
STM32 Nucleo-L432KC ────────────────────────────────┘
  lighting, watchdog, inhibited safe output (target interface)
```

Acquisition and inspection run on **separate threads**. The reader publishes each
frame into a one-slot buffer; a backlogged frame is discarded and counted. The
inspection thread derives health from the age of the newest frame it holds, not
from whether the last read returned — so a stream that looks live but is stale
gets downgraded rather than silently inspected.

The Pi and STM32 roles above are the target deployment. Current evidence comes
from the Windows development host.

## Quick start

Requires Python 3.11+ (the code uses `StrEnum` and PEP 604 unions).

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

Run the test suite:

```bash
.venv/Scripts/python.exe -m pytest
```

Start the camera service and GUI for Plan A, including before camera arrival:

```powershell
.\START_RPLA_WEEK8.cmd
```

Open `http://127.0.0.1:5177/#sample-capture`. Startup succeeds when the service
and GUI are ready; camera readiness is shown separately. Stop with
`STOP_RPLA_WEEK8.cmd`. Select an explicit device or mode with
`-CameraDevice 0 -CameraBackend dshow -Resolution UHD`; append `-CheckConfig`
to check the selection without opening hardware or launching services.

See [WEEK8_IMPLEMENTATION.md](WEEK8_IMPLEMENTATION.md) for acquisition,
independent archives, incoming inspection and the Windows/Pi preparation steps.

The legacy continuous service remains available for Plan B (camera powered and
on the same network; close its CameraWebServer preview before starting):

```bash
START_RPLA_LIVE.cmd
```

Stop it with `STOP_RPLA_LIVE.cmd`. If the camera IP differs from the configured
one:

```bash
powershell -ExecutionPolicy Bypass -File .\scripts\start-rpla-live.ps1 -CameraIp 192.168.1.50
```

Inspect the Plan A configuration without opening a camera or starting services:

```powershell
.\START_RPLA_LIVE.cmd -SourceType usb_uvc -CameraDevice 0 -CameraBackend dshow -CheckConfig
```

For USB acquisition, omit `-CheckConfig` when using the device. See
[CAMERA_SOURCES.md](CAMERA_SOURCES.md) for source selection, independent inspection
profiles, requested versus actual image sizes, and software checks.

Offline demos that need no hardware:

The explicit Week 7 offline launcher retains the synthetic sample workbench for six angles and two lighting modes.
Run `START_RPLA_WEEK7.cmd` and open `http://127.0.0.1:5177`. It uses synthetic
images and simulated MCU messages, archives raw/annotated images and retakes,
and keeps physical measurements and outputs disabled. See
[WEEK7_IMPLEMENTATION.md](WEEK7_IMPLEMENTATION.md) for the workflow, archive,
verification and hardware preparation. The existing preview launchers remain
available separately.

```bash
.venv/Scripts/python.exe src/week3_offline_demo.py --config config/week3_offline.json --output data/output/week3_offline
```

GUI development (see `gui-prototype/package.json` for the full script list):

```bash
cd gui-prototype && pnpm install && pnpm run dev
```

## Repository layout

| Path | Contents |
|---|---|
| `src/week3/` | Source-independent contracts: `FramePacket`, `DetectionRecord`, vision baseline, SQLite repository |
| `src/week4/` | Camera connection policy, state monitor, one-slot buffer, ESP32 MJPEG and USB/UVC adapters |
| `src/camera_config.py` | Source selection, per-camera capture/inspection profiles and legacy configuration support |
| `src/live_service.py` | Resident service: acquisition/inspection threads, REST, MJPEG, WebSocket |
| `src/week8_service.py` | Plan A service combining continuous preview and triggered camera sample capture |
| `config/` | Runtime configuration per scenario (resolution profiles, ROI, gates, thresholds) |
| `tests/` | pytest suite, hardware-free via injected capture/source factories |
| `gui-prototype/` | React operator interface |
| `scripts/` | Launch, stop and scoped network-fault test scripts (PowerShell) |
| `data/input`, `data/output` | Sample images and generated evidence |
| `data/baselines/` | Byte-preserved historical source snapshots and their manifests |
| `paper_rewriting_output/` | Bilingual proposal design report and its verification tooling |

## Reports

The current development snapshot is indexed in [CURRENT_PROGRESS.md](CURRENT_PROGRESS.md).
The final report is the user-confirmed
[Proposal Design Report PDF](paper_rewriting_output/final/Proposal_Design_Report.pdf),
preserved unchanged from the supplied file. Its cover and Section 5.2 specify
the ALC-IMX258-LY0001-ZB V1 module. The [version record](paper_rewriting_output/final/README.md)
identifies its checksum and the scope of the historical manuscripts below.

`paper_rewriting_output/` also retains the earlier paired manuscripts —
`ENG5105_Proposal_Design_Report_EN.md`, `..._ZH.md` and their generated DOCX files —
for historical traceability. They are not the source of the final PDF.

Verify the historical manuscript pair with:

```bash
.venv/Scripts/python.exe paper_rewriting_output/validate_paired_reports.py
```

This checks citation order, reference entries, URLs, equations, table and figure
numbering, evidence labels and critical numeric tokens across both languages.

### Evidence files are hash-anchored

Appendix A of the historical manuscript pair records a SHA-256 for nine internal
evidence records, and its artifact manifest records one for each manuscript. `.gitattributes` marks
those eleven files `-text` so Git cannot normalise their line endings — any such
rewrite silently invalidates every recorded hash and breaks the traceability
claim for anyone who clones this.

The three source/configuration files extended for USB acquisition now have frozen
copies in `data/baselines/plan_b_before_uvc_20260906/`. Historical source references
resolve to these exact bytes through `scripts/verify_evidence_baselines.py`;
current source files are a later implementation. Other evidence records and
the existing report artifacts still have to match their recorded hashes.
The historical report-local verifier checks live paths only; use the version-aware
verifier for the current development tree:

```powershell
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
```

## Academic note

This repository is coursework for an assessed university project. The proposal
report is a submission artifact. Treat the course briefs and rubric PDFs in the
root as third-party material supplied for the assignment.
