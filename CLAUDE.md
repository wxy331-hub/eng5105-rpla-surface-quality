# ENG5105 Project Instructions

Project-specific rules for this repository. The workspace `CLAUDE.md` one level
up still applies; this file adds only what is particular to ENG5105 and does not
restate the general working method, verification or Git rules from there.

User-facing setup, architecture and command documentation lives in `README.md`.
This file covers agent behaviour and the constraints that are easy to violate.

## Working copy

`E:\Claude Code\5105` is the authoritative working copy. A historical copy exists
at `D:\12591\Documents\5105`; do not read it, diff against it, or edit it. If a
question seems to need that copy, ask instead.

## What this project is

A proposal-stage machine-vision monitor for visible surface anomalies on a held,
indexed rPLA filament specimen, for the ENG5105 Integrated Design brief. The
specimen is stationary because the magnification a 1.75 mm strand needs leaves
about 1.4 mm of depth of field, which a fixture can hold and a running strand
cannot; the reports state plainly that this narrows the brief's in-line context.

Plan A, the ALC-IMX258 camera over USB video class, is the selected concept.
The current service supports USB and ESP32 inputs through the same frame contract.
No Plan A measurement may be reported until its own hardware arrives and is calibrated.
Plan B (supplied ESP32S3 / OV3660, Raspberry Pi 4, STM32 Nucleo-L432KC) produced
every measurement recorded so far and becomes the acquisition front end for the
build only if the procurement decision gate fails.

Requirement priority: assignment brief and discipline-specific content, then
required interfaces and formats, then this file, then existing implementation.

## Evidence discipline

This is the core value of the project and the easiest thing to break.

- The user-confirmed final report is `paper_rewriting_output/final/Proposal_Design_Report.pdf`.
  Its version and checksum are recorded alongside it. Preserve the PDF unchanged;
  the older paired Markdown/DOCX files and their build tools are historical records.
  The final report's designation does not cancel later explicit user decisions
  about GUI behaviour. Record any implementation differences separately.

- Every result carries an evidence label: `OFFLINE_SYNTHETIC_ONLY`,
  `OFFLINE_FAULT_INJECTION_ONLY`, `LIVE_INTEGRATION_ONLY`,
  `PENDING_REAL_MATERIAL`, `PROPOSED_REQUIREMENT`, `PROPOSED_INTERFACE`.
- **Never upgrade an evidence level because code improved.** Wiring a control in
  makes it "implemented on the development host and unit-tested" — never
  "verified". Pi deployment, network-load behaviour and physical performance
  require new dated evidence.
- Historical observations stay as recorded. If a past run lacked instrumentation,
  say so in the past tense rather than rewriting what it showed.
- `size_mm` and `position_mm` stay `null` without a `calibration_id`; this is
  enforced in `DetectionRecord.__post_init__` and must not be relaxed.
- `confidence` is an uncalibrated area-derived ranking score. Do not describe it
  as a probability, and do not let `quality_grade` authorise rejection.
- Do not fabricate measurements, timings or accuracy figures. The observed
  10.77 FPS SVGA result is a preview rate on the interim chain, not a
  capture-to-result time, and must never be restated as compliance with the
  responsiveness requirement.

## Commands

```bash
.venv/Scripts/python.exe -m pytest                                   # full suite
```

`pytest.ini` pins `--basetemp=tmp/pytest`; the tracked `tmp/.gitkeep` must stay,
because pytest creates the leaf directory but not its parent.

Select a camera source through the launcher or configuration. For Plan B the
ESP32 must be powered and its CameraWebServer preview closed. For Plan A the
Python service owns the selected USB device. See `CAMERA_SOURCES.md` for commands.

## Module boundaries

- `src/week3/` holds source-independent contracts. Camera adapters depend on it;
  it depends on no adapter. Keep it that way.
- `src/week4/camera.py` owns connection policy and the one-slot buffer.
- `src/live_service.py` runs acquisition and inspection on separate threads. The
  acquisition thread must not touch SQLite — it queues events for the processing
  thread, which owns the repository connection.
- Tests stay hardware-free through injected `capture_factory` / `source_factory` /
  `opener`. Preserve that injection when adding code.
