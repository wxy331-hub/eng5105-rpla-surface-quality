# Week 4 Implementation (Offline Safety + Live OV3660 Integration)

## Current status (11 August 2026)

- The final project camera is confirmed as XIAO ESP32S3 Sense + OV3660.
- The control page and MJPEG stream at 640x480 passed a 30-second hardware integration test.
- The measured stream result was 792 frames in 30.056 seconds (26.35 FPS).
- `src/week4_live_demo.py` connects the real MJPEG stream to the Week 3 contracts,
  provisional ROI processing, SQLite, JSON, CSV, raw-frame and annotated-frame outputs.
- Live candidate records are labelled `LIVE_INTEGRATION_ONLY`; they do not prove rPLA
  defect detection accuracy, physical size, or position.
- The final live configuration is fixed at SVGA 800x600. The earlier 640x480 result is
  retained as historical integration evidence, not the final resolution or defect result.

## Architecture now implemented

```text
Plan B: XIAO ESP32S3 Sense + OV3660 MJPEG
        -> Esp32MjpegSource
        -> FramePacket
        -> CONNECTING / HEALTHY state gate
        -> provisional pixel ROI
        -> baseline candidate processing
        -> DetectionRecord
        -> SQLite + JSON + CSV + evidence images
```

The earlier offline fault-injection path remains available:

- `LatestFrameBuffer` has capacity one and discards backlogged frames.
- No frame for 1 second produces `STALE`; no frame for 2 seconds produces `DISCONNECTED`.
- Automatic grading or actuation is allowed only in `HEALTHY`.
- After reconnection, three consecutive valid frames are required before processing resumes.
- Connection and recovery events are stored in SQLite.

## Run the final Plan B integration

```powershell
.\.venv\Scripts\python.exe -m src.week4_live_demo `
  --url http://172.20.10.2:81/stream `
  --frames 100 `
  --output data\output\week4_live
```

The current ROI is an active software configuration but still requires real rPLA filament,
fixed camera geometry, and lighting before it can be treated as the final calibrated ROI.

## Run the repeatable offline safety test

```powershell
.\.venv\Scripts\python.exe src\week4_offline_demo.py `
  --config config\week4_offline.json `
  --output data\output\week4_offline
```

`OFFLINE_FAULT_INJECTION_ONLY` proves software behaviour, not camera performance.

## Remaining work

- Deploy the resident Python detection service, API/WebSocket layer, SQLite database, and GUI on Raspberry Pi 4.
- Fix the physical camera position, focus, background and lighting.
- Confirm the active ROI using the fixed inspection fixture and real material.
- Complete pixels-per-mm, defect-size and position calibration.
- Integrate STM32/encoder time synchronisation and real safe-output verification.
- Collect real rPLA samples and ground-truth labels for false-positive/false-negative evaluation.

Temperature, 30-minute stability, and power/network recovery tests are outside the currently
agreed Week 4 scope. All final calibration and performance evidence must be identified as
Plan B / OV3660 evidence; no Plan A hardware results are expected.
