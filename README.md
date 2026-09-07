# ENG5105 — rPLA Filament Surface-Quality Monitoring

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

The GUI opens the Plan A ALC-IMX258 USB/UVC simulation by default, using a
separate generated image and candidate-evidence bundle. The dashboard, records,
CSV export and health page share that source identity. It remains synthetic
software evidence; physical USB capture is selected separately using the camera
configuration below. The offline sample workbench is available in the GUI's
left navigation.

The resident software accepts either Plan A's ALC-IMX258 USB/UVC source or Plan B's
ESP32S3/OV3660 network MJPEG source through the same `CameraSource` / `FramePacket`
contract. Plan B remains the default runnable configuration; select `usb_uvc` for
Plan A. The USB adapter has hardware-free software tests. Its requested capture
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

Run the live service and GUI together (needs the camera powered and on the same
network; the ESP32 CameraWebServer preview must be closed, since the Python
service has to be the only direct MJPEG client):

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

Week 7 adds a triggered sample workbench for six angles and two lighting modes.
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
