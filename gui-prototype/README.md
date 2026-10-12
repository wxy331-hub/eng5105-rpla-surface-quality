# rPLA Surface Quality Monitor

The English-first, bilingual ENG5105 GUI opens the resident **camera service** by
default. Inspection, connection status and sample acquisition share the local
Python service at `http://127.0.0.1:8765`. Camera identity comes from its response;
an unavailable service or camera leaves the live picture empty and offers a
connection retry. It never fills that view with replay images.

The current inspection layout is preserved: image and candidate details side by
side, saved candidate events below, and engineering diagnostics in System Health.
**Sample capture / 样本采集** opens the six-angle, two-lighting workbench at
`#sample-capture`; **Back to inspection / 返回检测界面** returns to the dashboard.
Both routes support refresh and browser Back/Forward.

## Start the camera workflow

From the project root, with the project Python environment and GUI dependencies
installed:

```powershell
.\scripts\start-rpla-week8.ps1
```

The GUI is available at `http://127.0.0.1:5177`. The service is the sole acquisition
client for Plan A's ALC-IMX258 USB/UVC camera; browser camera permission is not used.
Device selection, requested mode and inspection ROI are service startup settings.
See [CAMERA_SOURCES.md](../CAMERA_SOURCES.md) and the project README for configuration.
Plan B remains an explicitly selected backend source with its own recorded identity.

When preparing the interface before the selected camera is connected, use
`.\scripts\start-rpla-week8.ps1 -WaitForCamera`. This starts the API and GUI
without opening a device until **Connect camera / 连接摄像头** is selected.
Verify the configured device before connecting; index 0 may be a built-in webcam.

```powershell
.\scripts\stop-rpla-week8.ps1
```

For frontend development against an already running camera service, run in
`gui-prototype`:

```powershell
$env:VITE_INSPECTION_MODE = 'service'
$env:VITE_INSPECTION_API_URL = 'http://127.0.0.1:8765'
$env:VITE_SAMPLE_API_URL = 'http://127.0.0.1:8765'
pnpm exec vite --host 127.0.0.1 --port 5177 --strictPort
```

`VITE_INSPECTION_MODE` defaults to `service`. The sample adapter resolves its base
URL from `VITE_SAMPLE_API_URL`, then the historical `VITE_WEEK7_API_URL`, then
`VITE_INSPECTION_API_URL`, and finally port 8765. Set both service URLs together
when using a custom port. The retained `/api/week7` sample route is an API
compatibility detail; it does not select synthetic acquisition.

## Camera and capture behavior

- Inspection consumes `/api/snapshot`, `/ws` and `/api/stream.mjpg`. The browser
  clears the live image and current candidate when the camera is stale, disconnected,
  recovering or service telemetry is lost. Stored records remain available; a
  previous detection is never presented as the current frame's candidate.
- The sample workbench polls `/api/week7/health` while open. It only permits camera
  capture when `camera.connected` and `camera.capture_available` are both true.
  Its preview uses the same shared stream. `POST /api/control/reconnect` retries
  the service-owned camera, and failure remains visible.
- Select one of 0°, 60°, 120°, 180°, 240° and 300°, select bright field or dark
  field, physically set that view, and click capture. Each request saves exactly
  one raw PNG and one annotated PNG. Physical lighting is currently manual and
  recorded as `operator_declared`, with no sensor-confirmed READY/OFF exchange.
- Retakes name the selected view in their confirmation and preserve previous
  attempts. The other lighting view is unchanged. Missing coverage cells prepare
  a capture; saved cells and history select that record's saved evidence image.
- Twelve current views are required for completion. Completed sessions are locked.
  Each session has its own confirmed delete action and a recoverable pending-file
  cleanup state. CSV export retains source, evidence and capture history.
- Actual decoded preview pixels, acquired image dimensions and requested camera
  mode are separate fields. A session's source and image configuration must remain
  compatible; old archives stay viewable when acquisition is blocked.

The detailed flow and historical acceptance record are in
[SAMPLE_CAPTURE_FLOW.md](SAMPLE_CAPTURE_FLOW.md).

## Explicit offline and historical modes

Offline synthetic sample capture remains available through the existing
`scripts/start-rpla-week7.ps1` launcher and port 8766. Its evidence response selects
the synthetic labels and retains its independent archive. Real-camera sessions
are stored separately. The main GUI navigation still uses the task name
**Sample capture / 样本采集** in either mode.

To review only the bundled Plan A simulation, set these before starting Vite:

```powershell
$env:VITE_INSPECTION_MODE = 'offline'
$env:VITE_OFFLINE_PROFILE = 'plan_a'
pnpm run dev
```

An explicit `plan_b` offline profile retains the historical ESP32S3/OV3660 replay.
`VITE_INSPECTION_MODE=week7` is a compatibility alias for offline inspection.
To read a captured Week 4 integration snapshot, run `pnpm run sync:live`, set
`VITE_INSPECTION_MODE=live`, and start Vite. These files are a saved integration
snapshot; their camera source, size and evidence history remain unchanged.

Synthetic bundle generation and archived UHD validation are described in
[PLAN_A_SYNTHETIC.md](PLAN_A_SYNTHETIC.md). Prior layout acceptance is recorded in
[GUI_REVIEW.md](GUI_REVIEW.md). These documents describe their dated evidence;
they do not validate connected-camera performance.

## Build and checks

From `gui-prototype`:

```powershell
pnpm install --frozen-lockfile
pnpm run test:evidence
pnpm run build
```

The static output is `dist/client/`. Adapter checks cover source selection, stale
and disconnected state, WebSocket loss, reconnect failure, single-view requests,
archive behavior and capture gating without requiring camera hardware.

Sites packaging uses the local deployment configuration `.openai/hosting.json`.
With that configuration available,
`pnpm run build:sites` and `pnpm run test:sites` validate the additional package.
The nested `.github/workflows/deploy-pages.yml` is an example, not an enabled root
repository deployment workflow. This work does not publish the GUI.

Camera software integration is separate from hardware acceptance. Actual
ALC-IMX258 negotiation, focus, exposure, lighting stability, fixture positioning,
calibration and rPLA candidate performance need their own real-hardware evidence.
Physical sizes and positions remain unmeasured, and physical outputs are disabled.
