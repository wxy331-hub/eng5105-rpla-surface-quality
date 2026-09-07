# Camera source selection

The existing resident pipeline supports two selectable inputs. Both use the same
preview, candidate processing, SQLite records, REST/WebSocket API and GUI.

| Source type | Input | Default requested profile |
|---|---|---|
| `esp32_mjpeg` | ESP32S3 / OV3660 HTTP MJPEG | SVGA, 800 x 600 |
| `usb_uvc` | ALC-IMX258 local USB/UVC device | UHD, 3840 x 2160, MJPG, 30 FPS request |

The default source remains `esp32_mjpeg`. USB modes are configuration requests,
not enumerated camera capabilities or measured frame rates. The USB adapter
rejects failed mode requests and frames whose actual size differs from the
selected profile. The GUI shows received dimensions; before the first valid
frame it shows a waiting state.

## Windows launcher

Validate configuration without camera, network discovery or process startup:

```powershell
.\START_RPLA_LIVE.cmd -SourceType usb_uvc -CameraDevice 0 -CameraBackend dshow -CheckConfig
.\START_RPLA_LIVE.cmd -SourceType esp32_mjpeg -CheckConfig
```

`-ValidateOnly` is an alias for `-CheckConfig`. The output explicitly distinguishes
configuration from a hardware connection. Preflight does not change environment
variables or create service logs.

Start the existing service and GUI using USB:

```powershell
.\START_RPLA_LIVE.cmd -SourceType usb_uvc -CameraDevice 0 -CameraBackend dshow
```

Start the existing Plan B path:

```powershell
.\START_RPLA_LIVE.cmd -SourceType esp32_mjpeg
```

Use `-CameraIp <address>` to select an ESP32 explicitly. USB acquisition skips
ESP32 network discovery, its port check and HTTP controls. `-Resolution` selects
a profile under that source: Plan B retains its named profiles and USB includes
UHD and FHD requests. The launcher starts the GUI after receiving the first valid
camera frame; a missing device produces a source-specific connection error.
Stop project services with `STOP_RPLA_LIVE.cmd`.

`auto`, `dshow`, `msmf` and `v4l2` are available backend selections. The chosen
OpenCV build and host must provide that backend. Windows backends use a numeric
device index. Linux device paths may name `/dev/videoN` or `/dev/v4l/by-id/...`
or `/dev/v4l/by-path/...`; this is an adapter input option, not a Pi deployment.
The USB source does not accept network URLs or ordinary media files.

## Configuration

`config/live_service.json` contains:

- `default_source_type`: source selected when none is explicitly requested.
- `sources`: device-specific connection details and resolution profiles.
- `inspection_profiles`: independent Plan A and Plan B ROI, presence-gate,
  threshold, morphology, candidate-score and pixel-area heuristic settings.
- Common service settings: database, CORS, frame-age policy, reconnect timing
  and output JPEG quality.

Plan B's original parameter values remain intact. Plan A begins with a full-frame
provisional ROI and explicitly unvalidated copies of the existing heuristic
defaults. Changing one inspection profile does not change the other. No physical
scale, camera-specific optimum or real-defect accuracy is implied by these values.

Normalized ROI coordinates are converted to pixels using the selected width and
height. Every received frame must match those dimensions before it is processed
or recorded; a mismatch is an error rather than an implicit resize.

The configuration loader still accepts the original flat Plan B file format.
Direct Python startup can use `RPLA_CONFIG_PATH`, `RPLA_SOURCE_TYPE`,
`RPLA_CAMERA_DEVICE`, `RPLA_CAMERA_BACKEND` and `RPLA_RESOLUTION`. Legacy ESP32
overrides remain available for that source. The launcher fixes the configuration
path and clears overrides belonging to the other camera type when switching.

The backend publishes `source_type`, `camera_source`, `camera_path`,
`inspection_profile` and `parameter_status`. Requested width/height/format/FPS
are separate from received dimensions and measured pipeline FPS. Batch and
detection records retain the source identity. Historical OV3660 evidence keeps
its original identity in replay.

## Software checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
```

From `gui-prototype`:

```powershell
npm run test:evidence
npx vite build
```

USB adapter and service tests inject capture objects. They check source
selection, mode rejection, recovery, dimensions, database persistence and API
output without opening a physical camera. Existing Plan B and offline tests
remain in the suite. Size and position stay null without calibration, and
candidate scores remain uncalibrated ranking values.
