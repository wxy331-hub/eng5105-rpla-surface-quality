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

A proposal-stage machine-vision monitor for visible surface anomalies on moving
rPLA filament, for the ENG5105 Integrated Design brief. Plan B (supplied ESP32S3
/ OV3660, Raspberry Pi 4, STM32 Nucleo-L432KC) is the path built and validated
now. Plan A imaging procurement was approved on 20 August 2026 but was not
ordered on that date; Plan A is a post-delivery comparison, so no Plan A
measurement may be reported until its own hardware arrives and is calibrated.

Requirement priority: assignment brief and discipline-specific content, then
required interfaces and formats, then this file, then existing implementation.

## Evidence discipline

This is the core value of the project and the easiest thing to break.

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
  10.77 FPS SVGA result is below the proposed 20 FPS target and must not be
  presented as compliant.

## Commands

```bash
.venv/Scripts/python.exe -m pytest                                   # full suite
```

`pytest.ini` pins `--basetemp=tmp/pytest`; the tracked `tmp/.gitkeep` must stay,
because pytest creates the leaf directory but not its parent.

The camera path needs the ESP32 powered and its CameraWebServer preview closed —
the Python service must be the only direct MJPEG client. See `README.md` for
launch commands.

## Module boundaries

- `src/week3/` holds source-independent contracts. Camera adapters depend on it;
  it depends on no adapter. Keep it that way.
- `src/week4/camera.py` owns connection policy and the one-slot buffer.
- `src/live_service.py` runs acquisition and inspection on separate threads. The
  acquisition thread must not touch SQLite — it queues events for the processing
  thread, which owns the repository connection.
- Tests stay hardware-free through injected `capture_factory` / `source_factory` /
  `opener`. Preserve that injection when adding code.

