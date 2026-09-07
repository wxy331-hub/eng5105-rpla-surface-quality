# Plan A native UHD synthetic data

The default inspection replay and new offline sample sessions generate images
directly on a **3840 × 2160 px** canvas. This is synthetic software evidence;
the camera's requested **3840 × 2160 / MJPG / 30 FPS** mode still awaits hardware
validation. Actual image dimensions and the requested camera mode remain separate
GUI fields. Calibration is pending, physical measurements remain null, and
physical outputs remain disabled.

## Generation and records

- `scripts/generate_plan_a_gui_evidence.py` reads the Plan A capture dimensions
  from `config/live_service.json`. It exercises the USB adapter with injected
  native synthetic frames and regenerates the replay images, records and manifest.
- `config/week7_offline.json` configures new sample capture at 3840 × 2160 px,
  source `PLAN_A_SYNTHETIC_TRIGGERED`, and ROI `[168, 864, 3504, 432]` in
  `[x, y, width, height]` pixels. The calibration template uses the same geometry.
- `src/synthetic_profile.py` shares the scene's pixel-scale processing parameters.
  The 640 × 360 reference geometry provides length and area scale factors of
  6 and 36. Noise is generated at target resolution. Candidate boxes, contour
  areas and ranking scores are recalculated from the new pixels. They are not
  copied from old records. Annotation strokes and text scale with the canvas.
- The native replay contains three candidates: frames 2 and 6 have contamination
  boxes `[2158, 975, 310, 234]`, contour area 55347 px² and ranking score 0.934;
  frame 5 has a scratch box `[1651, 943, 539, 275]`, area 22262 px² and score 0.705.
  These area-based scores are synthetic ranking values, not defect probabilities.
- The unconfigured legacy synthetic source and explicit small test fixtures remain
  available for quick regression checks. Tests verify that their original pixels
  stay unchanged and that native generation does not call image resize.

## Session and image integrity

New sample sessions freeze the capture configuration in their event history.
Acquisition checks that configuration and the source/dimensions of existing
captures before writing images or events. An incompatible archive remains
readable, with acquisition disabled; create a new session to use the current
configuration. Empty legacy sessions may adopt the configuration on first capture.

The GUI reads new-session dimensions from the service, selected-session dimensions
from its saved configuration, and displayed-image dimensions from decoded pixels.
Completing a sample updates its main area and sidebar together, then locks capture.
Existing archive identifiers, records and original images are preserved.

## Verification on 2026-09-07

- **168 Python tests passed** across the native source/profile, replay generator,
  original pipeline, sample workflow/API, calibration, protocol and store.
- **32 frontend evidence/adapter tests passed**; `pnpm exec vite build` passed.
- The real local browser flow captured six confirmed angles with two simulated
  lighting modes, completed and locked the session, reviewed raw/annotated images,
  and exported CSV. All 24 output PNG headers report 3840 × 2160 px. The recorded
  demo session is `3d491bcb5d4944e0a5916659df38f175`.
- Browser checks cover UHD image proportions, candidate selection/pinning, source
  and ROI labels, saved-image dimensions, Chinese/English sample pages, and
  desktop/mobile layouts at 2552, 1440 and 390 px without page overflow. No page
  JavaScript errors were observed. A separate mocked-browser check covers immediate
  sidebar completion updates, changed/unavailable service dimensions and old-session
  capture blocking without writing to real archives.
- The two pre-existing sessions retained every original field and all **28 original
  image SHA-256 hashes**. ISO timestamps are compared as instants: the PowerShell
  pre-change JSON snapshot had serialized UTC values with the local timezone offset.
  The initial comparison failure is retained alongside the successful follow-up.
- Protected historical report/evidence hashes passed independently.

The data-migration screenshots, CSV and machine-readable browser result are in
`data/output/plan_a_uhd_migration/` relative to the project root. The earlier GUI
layout review remains in [GUI_REVIEW.md](GUI_REVIEW.md). This verification does
not measure real camera delivery, lighting, positioning, optics or defect accuracy.
The referenced `data/output/` archives and `tmp/` browser scripts are historical
material retained only on the development machine. Git ignores them, so their
file identifiers and recorded session IDs are not resources available in a clone.

Tracked generation and checks from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/generate_plan_a_gui_evidence.py
.\.venv\Scripts\python.exe -m pytest tests/test_synthetic_profile.py tests/test_week3_pipeline.py tests/test_plan_a_gui_evidence.py tests/test_week7_workflow.py tests/test_week7_api.py tests/test_week7_calibration.py tests/test_week7_protocol.py tests/test_week7_store.py -q
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
.\scripts\start-rpla-week7.ps1

# From gui-prototype/
pnpm run test:evidence
pnpm run build
```

The original browser verification used the local script
`tmp/plan-a-uhd-browser-check.cjs` and the recorded demo session above. That script
and session belong to the development-machine archive.

Open `http://127.0.0.1:5177/#inspection`; the sidebar and inspection-page sample
card link directly to `#sample-capture`.
