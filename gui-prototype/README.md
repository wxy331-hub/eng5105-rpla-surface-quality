# rPLA Surface Quality Monitor

An English-first, bilingual GUI for the ENG5105 recycled PLA filament surface-inspection project.

The resident Python service supports Plan A's ALC-IMX258 USB/UVC camera and
Plan B's ESP32S3/OV3660 MJPEG input through one API/WebSocket contract. The GUI
uses the active source metadata and the backend's shared processed stream.
Plan B keeps its SVGA default; USB acquisition has separate requested capture
and inspection profiles. See `../CAMERA_SOURCES.md` for source selection.

## What the prototype demonstrates

The default dashboard uses dedicated **Plan A USB/UVC simulation** evidence for
the ALC-IMX258 path. Its images, candidate records and connection/recovery trace
come from `scripts/generate_plan_a_gui_evidence.py`, which exercises the USB adapter
with injected synthetic frames. The record picker, CSV and health page refer to
that same evidence bundle. Image dimensions are synthetic test dimensions;
camera performance and physical measurements remain pending hardware validation.

The inspection layout places the image beside its candidate, with saved records
below. Connection-fault diagnostics are in System Health. Actual decoded image
dimensions are separate from the requested camera mode: current synthetic
images are generated natively at 3840 × 2160 px, matching the configured Plan A
pixel canvas. The MJPG/30 FPS camera request still requires hardware verification. Candidate Records provides
type filtering and direct access to saved images. The review, screenshots and
validation scope are documented in [GUI_REVIEW.md](GUI_REVIEW.md).
The current data configuration and archive compatibility rules are documented
in [PLAN_A_SYNTHETIC.md](PLAN_A_SYNTHETIC.md).

Regenerate the bundle from the project root with:

```powershell
.\.venv\Scripts\python.exe scripts/generate_plan_a_gui_evidence.py
```

`VITE_OFFLINE_PROFILE=plan_a` selects this default. An explicit `plan_b` profile
opens the preserved historical offline replay. Service mode continues to derive
camera identity from its running backend.

Validation covers frontend evidence/adapter checks, six Python evidence-generator
checks, a Vite build, and browser checks of the main view, records, health,
candidate-image selection, CSV and bilingual sample navigation. The latest
UHD migration browser results and screenshots are in
`../data/output/plan_a_uhd_migration/`; the preceding layout review is in
`../data/output/gui_review_20260907/`.
These are development-machine historical records. Their screenshots, runtime
archives and `tmp/` browser scripts are ignored by Git and are not included in a clone.
The frame/evidence manifest is
`public/assets/plan-a/manifest.json`.

- Replay of the reproducible Plan A USB connection and recovery scenario
- `CONNECTING`, `HEALTHY`, `STALE`, `DISCONNECTED`, and `RECONNECTING` states
- Safety gating, three-frame recovery, latest-frame buffering, and backlog discard evidence
- Archived synthetic candidate records with pixel bounding boxes and algorithm scores
- Read-only acquisition policy and evidence limitations
- English and Simplified Chinese interface switching from the top bar
- CSV export that uses only fields supported by the offline data contract
- A resident Python camera/detection service with API/WebSocket integration
- Adapter contracts for the pending Raspberry Pi deployment, indexed sample fixture and STM32 lighting supervision

> The public build is offline software evidence. A separate local mode can display the captured Week 4 OV3660 integration evidence without publishing camera files. Neither mode claims validated rPLA defect performance.

## Local development

```bash
pnpm install
pnpm run dev
```

### Local OV3660 evidence mode

The public build remains the offline demonstration. To review the locally captured Week 4
OV3660 integration evidence without committing camera files, run:

```powershell
pnpm run dev:live
```

This copies the current `data/output/week4_live` summary, detections, raw frame and latest
annotated frame into the ignored `public/live-evidence/` directory before starting Vite in
`live` mode. The interface labels these records as unvalidated scene candidates, not rPLA
defects.

## Offline sample capture

Select **Offline sample capture / 离线样本采集** in the main GUI's left navigation.
The workbench opens in the same page at `#sample-capture`; its **Back to inspection**
link returns to the dashboard. Both routes support refresh and browser Back/Forward.

With the existing project Python environment and GUI dependencies installed,
start the offline API and GUI from the project root:

```powershell
.\scripts\start-rpla-week7.ps1
```

Open `http://127.0.0.1:5177` and select **Offline sample capture**. A direct link is
`http://127.0.0.1:5177/#sample-capture`. The launcher selects
`VITE_INSPECTION_MODE=week7` and the local sample API at
`http://127.0.0.1:8766`. This workbench uses synthetic images and simulated
lighting/MCU messages. Its evidence label is `OFFLINE_SYNTHETIC_ONLY`;
physical outputs are blocked and physical dimensions remain unmeasured.

Create or resume a sample session, select one angle and lighting mode, and
capture **one view per request**. Bright-field and dark-field
views are acquired separately. Retaking a view preserves its previous attempt and
leaves the other lighting view unchanged. Coverage lists the required 6 × 2 views;
select a missing cell to prepare that capture or select a saved view
to compare its raw and annotated PNGs and inspect pixel-space candidates.
New sessions record their capture configuration and generate native UHD images.
Sessions from a different source or resolution remain viewable; create a new
session to acquire with the current configuration. Existing images are preserved.
Retaking a view requires confirmation and preserves previous capture records.
If capture fails, the workbench reloads the durable session state and keeps
the original error visible. The simulated
lighting/MCU disclosure includes the latest recorded fault and OFF acknowledgment.

Each capture record contains two PNGs: raw and annotated. A completed sample is
locked, including an archive whose files later become incomplete. CSV export
retains the capture history, calibration status and evidence labels. Restore
missing archive files or create a new session for further acquisition.

Each session in the sidebar has its own delete button. Confirmation names the
sample and session and explains that its images, candidates and history will be
permanently removed. Cancellation sends no deletion request. Deletion leaves
other sessions intact. If final file cleanup cannot finish, the UI identifies
the pending cleanup and provides a retry for that session.

The camera status explicitly says its capture interface is pending integration.
The connection information dialog explains the future Plan A USB camera/service
prerequisite. Current capture buttons generate synthetic images; opening this
workbench does not probe, connect to or acquire from a physical camera.
The current interaction, deletion recovery and verification are documented in
[SAMPLE_CAPTURE_FLOW.md](SAMPLE_CAPTURE_FLOW.md).

Stop the launcher-owned processes from the project root:

```powershell
.\scripts\stop-rpla-week7.ps1
```

For separate frontend development, run the API from the project root with
`.\.venv\Scripts\python.exe -m src.week7_service --port 8766`, then run the
following commands in `gui-prototype`:

```powershell
$env:VITE_INSPECTION_MODE = 'week7'
$env:VITE_WEEK7_API_URL = 'http://127.0.0.1:8766'
pnpm exec vite --host 127.0.0.1 --port 5177 --strictPort
```

The inspection dashboard uses its configured data source. The sample API is
requested only while the sample workbench is open. Verify the sample adapter with:

```powershell
node --test tests/week7-data-source.test.mjs
```

## Build and checks

From `gui-prototype/`, install the pinned dependencies and build the static GUI:

```bash
pnpm install --frozen-lockfile
pnpm run build
pnpm run test:evidence
```

The static output is `dist/client/`. Sites packaging additionally requires the
deployment-specific `.openai/hosting.json`, which is not included in this checkout:

```bash
pnpm run build:sites
pnpm run test:sites
```

The Pages workflow example is stored at
`gui-prototype/.github/workflows/deploy-pages.yml` relative to the repository root.
It is nested rather than configured as a root workflow for this repository;
automatic deployment would require a root `.github/workflows/` configuration
with the GUI's working directory and artifact paths. This update publishes source
progress only.
