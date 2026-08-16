# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Prototype-specific decisions

- Default to English for the ENG5105 presentation GUI, with a top-bar language menu that switches the complete interface between English and Simplified Chinese. Every new user-facing string must be provided in both languages.
- Treat the selected dark industrial dashboard mock in `design-reference/selected-dashboard-concept.png` as the visual source of truth.
- This is the Week 5 mock-data GUI deliverable, with Week 4 acquisition and Week 8/9 hardware/database integrations represented by adapter contracts only.
- The final selected architecture is Plan B: ESP32S3 OV3660 camera acquisition, Raspberry Pi 4 inspection/API/database/GUI processing, and STM32 encoder, watchdog, lighting, and actuator I/O. The school is not supplying Plan A camera materials, so do not present a future global-shutter migration as active project work.
- Do not couple React components directly to camera, STM32, encoder, alarm, or database implementations; consume the unified inspection data-source contract.
- The Week 5/6 public demo must not show controls that imply unconnected hardware actions. Keep alarms, safety state, and adapter configuration read-only until their real backend interfaces are integrated and validated.
- Keep the current public navigation focused on Live Inspection, Defect Records, and System Health; batch analytics and writable settings return only when real Week 8/9 data and hardware integrations exist.
- Until physical Week 2–4 work is complete, drive the GUI from the reproducible Week 4 offline fault-injection evidence. Show pixel-space candidates and software safety states only; defer physical measurements and hardware performance fields until their evidence exists.
- Selecting a recorded candidate pins that record's saved evidence image in the inspection viewer. The automatic fault timeline may continue internally, but it must not replace the selected image until the user returns to fault replay.
- Live Week 4 evidence must be described as a captured OV3660 integration snapshot, not a continuous stream. Scene candidates from the ceiling/glare test are unvalidated and must never be presented as rPLA defects or actuator grades. Because the current live run retains only the latest annotated image, live candidate rows are read-only and must not imply frame-specific image evidence.
- The final-project GUI groups consecutive, spatially overlapping frame-level candidates into one displayed candidate event. Raw frame records remain available for CSV/database traceability, while the dashboard and records page show event-level results and avoid validation-status notes.
- Local physical-hardware mode uses the resident Python inspection service as the sole ESP32 MJPEG client. The GUI receives the shared processed stream from the service and live state/candidate updates over WebSocket; it must not connect directly to the ESP32 stream in this mode.
- Live candidate events may be deleted from either the dashboard or records page. Deleting one collapsed event must remove every linked raw detection from both the resident service and SQLite after explicit confirmation.
- Preserve the current laptop density, but automatically enlarge the full interface at 2K and 4K desktop breakpoints so small industrial-dashboard text stays legible on a 27-inch external display.
- Keep the live operator view focused on connection, pipeline rate, candidate events, and post-decode GUI latency. Do not promote cumulative frame counts, inspection-frame counts, recovery counters, buffer policy, or skipped-frame counters as primary KPIs; keep secondary engineering diagnostics in the System Health technical-details disclosure and do not repeat a health-card strip on the live page.
- The Plan B resident service uses named resolution profiles with normalized ROI scaling. Keep SVGA 800×600 as the fixed live default selected on 2026-08-11; do not continue resolution-selection trials. VGA remains a manual fallback only.
