# Evidence Bank

| Evidence ID | Source File | Claim Supported | Figure/Table Link | Verification Needed |
|---|---|---|---|---|
| E01 | `Electrical teams proposal report rubric 2026.pdf` | The report must identify, discuss, and compare at least two concepts; functional details carry the largest single rubric weight (25%). | Rubric-alignment table | None |
| E02 | `Concept design_ Discipline specific content.docx.pdf` | The report must contain measurable requirements, functional-unit specifications, sensing/UI/communications/power detail, a BOM, risks, and a project plan. | Requirements traceability; power budget; risk register | None |
| E03 | `ENG5105-ENG5106 S2 2026 - Project Briefs_Rev0.pdf`, pp. 7-8 | Electrical teams must design a laboratory-scale online/real-time quality monitoring system; surface quality includes bubbles, roughness, contamination, cracks, and inclusions. | Problem definition; defect taxonomy | None |
| E04 | `ENG5105 Components - With pictures 2026.pdf` | Raspberry Pi 4, STM32 Nucleo-L432KC, ESP32S3 Sense, and auxiliary optoelectronic parts are university supplied. | BOM baseline | Confirm physical issue/condition of each part when received |
| E05 | `PLAN_B_FINAL_ARCHITECTURE_2026-08-11.md` | Plan B is the active and sole implementation path; Plan A remains only a concept comparison. | Architecture block diagram; concept decision | None |
| E06 | `RESOLUTION_TEST_RESULTS_2026-08-11.md` | SVGA 800 × 600 is selected; a 30 s sustained live throughput test measured 10.77 FPS with zero reported drops, without rPLA in the ROI. | Integration-evidence table | Re-test on final fixture and real material |
| E07 | `LIVE_PATH_TEST_RESULTS_2026-08-11.md` | Camera-control-to-local-API brightness-step response had a 101.32 ms median and 222.99 ms P95 across ten transitions; this is not physical exposure-to-display latency. | Latency evidence table | Physical end-to-end latency test with visible timing reference |
| E08 | `LIVE_PATH_TEST_RESULTS_2026-08-11.md` | A controlled network fault produced `RECONNECTING`, suppressed detection/automatic action, and recovered to `HEALTHY`; timings are integration evidence. | Fault-response table | Repeat on final Raspberry Pi/network hardware |
| E09 | `WEEK3_OFFLINE_IMPLEMENTATION.md` | The software pipeline and record schema are frozen; uncalibrated `position_mm` and `size_mm` must remain null. | Software pipeline diagram; API schema | Optical and encoder calibration after materials arrive |
| E10 | `WEEK4_OFFLINE_IMPLEMENTATION.md` | Live candidate records are labelled `LIVE_INTEGRATION_ONLY`; the latest-frame buffer and health gate prevent stale-frame actuation. | State diagram; fault table | Real wiring and STM32 safe-output test |
| E11 | User schedule statement | Physical rPLA/fixture materials arrive in Week 5 on Thursday, so physical validation cannot be reported before that date. | Project timeline | Confirm actual receipt date and any delay |
| E12 | User design decision | Plan A must be rejected not only for unavailable university hardware but also for excessive Plan-A-specific incremental cost and procurement lead-time risk. | Feasibility-gate table | Add current supplier evidence; exclude shared components |

