# ENG5105 — rPLA Filament Surface-Quality Monitoring

A laboratory-scale machine-vision system that watches recycled PLA (rPLA) filament
for visible surface anomalies while it moves, and records each finding as a
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

## Architecture (Plan B)

Plan B uses the university-supplied hardware baseline. Plan A (a global-shutter
camera on the Pi) is retained in the report as a comparator only; it is not built.

```
Controlled optical head + rPLA filament
        |
        v
XIAO ESP32S3 Sense / OV3660  ──MJPEG over controlled 2.4 GHz Wi-Fi──┐
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
  encoder, lighting, watchdog, inhibited safe output
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

Offline demos that need no hardware:

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
| `src/week4/` | Camera connection policy, state monitor, one-slot buffer, ESP32 MJPEG adapter |
| `src/live_service.py` | Resident service: acquisition/inspection threads, REST, MJPEG, WebSocket |
| `config/` | Runtime configuration per scenario (resolution profiles, ROI, gates, thresholds) |
| `tests/` | pytest suite, hardware-free via injected capture/source factories |
| `gui-prototype/` | React operator interface |
| `scripts/` | Launch, stop and scoped network-fault test scripts (PowerShell) |
| `data/input`, `data/output` | Sample images and generated evidence |
| `paper_rewriting_output/` | Bilingual proposal design report and its verification tooling |

## Reports

`paper_rewriting_output/` holds the two submission-facing manuscripts —
`ENG5105_Proposal_Design_Report_EN.md` and `..._ZH.md`. Everything else in that
directory is a research or drafting record; where they disagree, the two final
reports and their Appendix A are authoritative.

Both reports are kept structurally paired. Verify with:

```bash
.venv/Scripts/python.exe paper_rewriting_output/validate_paired_reports.py
```

This checks citation order, reference entries, URLs, equations, table and figure
numbering, evidence labels and critical numeric tokens across both languages.

### Evidence files are hash-anchored

Appendix A of the report records a SHA-256 for nine internal evidence records,
and the artifact manifest records one for each report. `.gitattributes` marks
those eleven files `-text` so Git cannot normalise their line endings — any such
rewrite silently invalidates every recorded hash and breaks the traceability
claim for anyone who clones this.

**If you change one of those files, you must recompute its hash and update both
reports and `final_artifact_manifest.md` in the same change.**

## Academic note

This repository is coursework for an assessed university project. The proposal
report is a submission artifact. Treat the course briefs and rubric PDFs in the
root as third-party material supplied for the assignment.
