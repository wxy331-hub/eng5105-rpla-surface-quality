# Plan A GUI review

This is the layout-review snapshot from before the UHD synthetic-data migration.
Its screenshots retain the image dimensions observed at that time. The current
native UHD defaults and subsequent validation are in [PLAN_A_SYNTHETIC.md](PLAN_A_SYNTHETIC.md).

Reviewed on 2026-09-07 against the supplied screen, the current Plan A sample workflow, `CLAUDE.md`, and this GUI's `AGENTS.md`. Scope: inspection, candidate records, system health, and offline sample capture in English and Simplified Chinese. The installed Chrome browser was used after the in-app browser runtime failed to initialize.

## Findings and implemented changes

| Flow | Finding | Result |
| --- | --- | --- |
| Inspection | Small image beside dominant recovery counters and a large fault timeline | Main image and adjacent candidate details; full-width candidate table below. Fault replay diagnostics live in System Health. |
| Image dimensions | A generic resolution label conflated synthetic image pixels with camera configuration | Actual decoded dimensions and requested capture mode have independent labels and data fields. The synthetic image remains **640 × 360 px**; the configured USB request is **3840 × 2160 / MJPG / 30 FPS**, pending hardware validation. |
| Evidence interpretation | “Reject”, defect terminology, and an unexplained score implied a physical decision | Candidate terminology throughout the default GUI; an area-derived ranking score with an explicit meaning. Original prototype grades remain in traceable CSV data. |
| Image review | Processing-hold UI obscured image pixels; ordinary image failures had no explanation | Status and errors sit outside the image. Decoded aspect ratio is preserved. Reload also retries the same image URL. |
| Candidate records | No image entry from records; grade filtering and an empty table obscured the task | Candidate-type search/filter, meaningful empty state, keyboard-accessible frame buttons, and selection that opens and pins the matching saved image. |
| Navigation | Icon-only navigation at narrow sizes lacked accessible names | Named controls, visible mobile navigation labels, and hash routes for inspection, records, health, and sample capture. |
| System health | Diagnostic emphasis and several translated/source labels were misleading | Separate source configuration and actual image dimensions, a wrapping fault timeline, and secondary technical details. Static evidence is described as saved files. |
| Service telemetry | Old captured-image age could appear as current GUI latency; requested profile name appeared in the frame rail | Static snapshot latency stays null. Current service telemetry requires valid, fresh frame metadata. The rail identifies reported frame information, independently of the image dimensions. |
| Sample capture | Controls and coverage occupied separate full-width rows; finished sessions retained misleading acquisition instructions | Parallel acquisition/coverage, a larger evidence area, locked-session instructions, translated calibration reasons, and saved-image dimensions. |
| Responsive presentation | Tiny secondary text, fixed empty panel heights and zoom-related excess page height | Increased text contrast and readable sizes, content-sized panels, corrected viewport-height scaling, and responsive reflow. Wide data tables scroll within their own region. |

## Evidence and limits

The image, record, metadata and CSV still identify their actual source. Six manually indexed angles and two illumination modes form twelve required sample views. Existing sample sessions and original image archives were preserved during the review.

This is local browser/software verification. Synthetic images, API/WS fixtures and a requested UHD mode do not verify delivered-camera resolution, frame rate, optical quality, real lighting, positioning, calibration or defect accuracy. Physical measurements remain unavailable without valid provenance, and physical outputs remain disabled. Frame telemetry arrival time does not prove that the independent MJPEG image has painted the same frame. The review is not a full assistive-technology or WCAG certification.

## Validation

The results below record checks run on the development machine. The referenced
`data/output/` artifacts and `tmp/` browser scripts are local historical material,
ignored by Git and absent from a clone. File identifiers are retained for local
traceability; the tracked tests and build commands below remain available.

- English and Chinese across four pages and six widths: **390, 900, 1440, 1920, 2552 and 3840 px**; 48 layout cases passed. Page content does not overflow horizontally; wide tables retain internal scrolling.
- Candidate-type filtering, no-match state, native-button keyboard selection, pinned record image, CSV source/evidence/output fields, primary navigation, sample entry/return, image proportions, and actual/requested resolution labels passed browser checks.
- Completed and in-progress sample sessions, raw/annotated selection, angle-confirmation reset and a simulated service error/retry were inspected without writing to the existing sample archive.
- Final fresh-browser checks had no JavaScript errors, failing HTTP resources or console errors. A favicon request initially failed; its declaration was corrected and the failure record retained separately.
- **30 frontend evidence/adapter tests**, **6 Python evidence-generator tests**, the Vite build and protected historical evidence hash checks passed. Machine-readable results and screenshots are under `data/output/gui_review_20260907/` in the project root.
- A separate service-mode browser test used mocked API, WebSocket and image responses: **6 checks passed**, including actual 1920 × 1080 pixels versus requested UHD, HEALTHY with processing held for material, disconnected state, null latency/calibration, disabled physical output, and no invented heartbeat interval on the first frame. It used port 5178, stopped its own test server, and did not open a camera. See `service-smoke.json`; the normal GUI/API on 5177/8766 were preserved.

Tracked checks (project root unless a directory is shown):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_plan_a_gui_evidence.py
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py

# From gui-prototype/
pnpm run test:evidence
pnpm run build
```

The original local browser scripts were `tmp/gui-review-check.cjs` and
`tmp/sample-gui-review.cjs`; these require the development machine's browser
runtime and archives.

Local entry points: `http://127.0.0.1:5177/#inspection`, `#records`, `#health`, and `#sample-capture`.

## Screens reviewed

1. Inspection: actual synthetic pixels, requested USB mode, current candidate and saved records.

Local file: `data/output/gui_review_20260907/zh-CN-main-2552.png`.

2. Candidate records: type filtering and access to each archived image.

Local file: `data/output/gui_review_20260907/zh-CN-records-2552.png`.

3. System health: readable camera configuration and fault timeline.

Local file: `data/output/gui_review_20260907/zh-CN-health-2552.png`.

4. Sample capture: completed, locked session with twelve saved views. The visible sample identifier is an existing archive identifier.

Local file: `data/output/gui_review_20260907/zh-CN-capture-2552.png`.

Original supplied screen, on the development machine: `data/output/gui_review_20260907/user-reference.png`. Additional mobile, laptop, English, empty/error-state images and machine-readable checks are in the same local directory. All file identifiers in this section are relative to the project root.
