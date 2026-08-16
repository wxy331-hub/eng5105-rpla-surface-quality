# PaperSpine Source Map

## Source-of-truth priority

1. `Electrical teams proposal report rubric 2026.pdf` — assessment categories, HD descriptors, and mandatory report content.
2. `Concept design_ Discipline specific content.docx.pdf` — electrical-discipline section requirements, specifications, BOM, project plan, and risk expectations.
3. `ENG5105-ENG5106 S2 2026 - Project Briefs_Rev0.pdf` — client context, selected surface-quality problem, system objectives, and industrial-integration expectations.
4. `ENG5105 Components - With pictures 2026.pdf` — university-supplied hardware baseline.
5. `PLAN_B_FINAL_ARCHITECTURE_2026-08-11.md` — active architecture decision and evidence boundary.
6. `RESOLUTION_TEST_RESULTS_2026-08-11.md` and `LIVE_PATH_TEST_RESULTS_2026-08-11.md` — live integration evidence only.
7. `WEEK3_OFFLINE_IMPLEMENTATION.md` and `WEEK4_OFFLINE_IMPLEMENTATION.md` — software design and offline synthetic evidence.
8. `ENG5105_rPLA表面质量_概念设计方案.md` — working design synthesis; subordinate to the official brief and rubric.
9. `ESP32S3_OV3660_第二周测试说明.md` and `LIVE_INSPECTION_SERVICE.md` — implementation notes and interface details.

## Fixed design decisions

- The report evaluates at least two concepts because the rubric explicitly requires this.
- Plan A is a comparison concept only. Its global-shutter imaging advantages are acknowledged, but it is rejected before implementation because the required university hardware is unavailable, Plan-A-specific incremental procurement cost is too high for the project, and procurement lead time threatens semester delivery.
- Shared components are not charged against Plan A. Only incremental components unique to that concept belong in its cost comparison.
- Plan B is the sole implementation and validation path: ESP32S3 OV3660 camera to controlled 2.4 GHz Wi-Fi MJPEG, Raspberry Pi 4 OpenCV/API/WebSocket/SQLite/GUI, and STM32 encoder/watchdog/lighting/safe I/O.

## Evidence labels

- `LIVE_INTEGRATION_ONLY`: confirms connectivity, frame transport, service integration, GUI/database behaviour, or recovery behaviour; it does not prove rPLA defect-detection performance.
- `OFFLINE_SYNTHETIC_ONLY`: confirms software-path behaviour on synthetic or non-physical inputs; it does not prove real-material performance.
- `PROPOSED_REQUIREMENT`: a measurable target awaiting stakeholder confirmation and/or experimental validation.
- `PENDING_REAL_MATERIAL`: cannot be tested before physical rPLA and fixture materials arrive in Week 5 on Thursday.

## Prohibited claims

- No invented stakeholder consultation, stakeholder-approved requirement, supplier quote, measured cost, calibration result, millimetre result, defect accuracy, precision, recall, F1 score, line-speed capability, or real-rPLA performance.
- The existing SVGA frame-rate and live-path results may be reported only as integration evidence.
- `position_mm` and `size_mm` remain unavailable until encoder and optical calibration are completed.
- The design target of 20 processed frames per second must not be described as achieved; the current SVGA result exposes a design gap that requires post-arrival validation and possible requirement revision.

## Output contract

- Produce one complete English Markdown report and one complete Chinese Markdown report.
- The two reports must carry the same claims, tables, evidence status, and citations.
- Do not generate Word, PDF, or LaTeX.
- Do not add editing prompts to either report.

