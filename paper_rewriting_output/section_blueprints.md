# Section Blueprints — ENG5105 Proposal Design Report

## Controlling throughline

The report will make one client-facing argument: Plan B is not selected because it is theoretically the best camera system; it is selected because it is the strongest implementable concept after availability, Plan-A-specific incremental cost, procurement lead time, and semester delivery are treated as mandatory feasibility gates. Its technical credibility then rests on a traceable chain from need and proposed requirement to functional block, interface, risk control, evidence status, and scheduled verification.

## Planned manuscript structure

| Unit | Planned function | Principal evidence | Claim boundary | Planned visual/table |
|---|---|---|---|---|
| Title and document status | Identify the client problem, selected quality parameter, proposal status, and team discipline. | Project brief; confirmed motivation | Proposal, not final validated design | Document-control table |
| Executive Summary | State the client need, Plan A/B comparison, feasibility decision, Plan B architecture, current integration evidence, unresolved physical validation, estimated procurement envelope, and recommendation. | REF001-REF012; verified supplier pages | No real-rPLA performance claim | None; concise prose |
| Acknowledgement of Country | Use Monash's Kulin Nations location basis and connect engineering stewardship to care for land, materials, and resources without appropriating Indigenous knowledge. | Monash official guidance | Respectful acknowledgement, not a technical sustainability claim | None |
| 1. Background and purpose | Establish BioLoop's circular-manufacturing context, explain why surface quality matters, define the laboratory proposal purpose, and set scope boundaries. | REF004; rPLA literature | Visible anomaly monitoring only; not Ra or internal-void metrology | Project-scope table |
| 2. Literature and design implications | Synthesize rPLA quality evidence, controlled machine vision, edge/distributed roles, and validation methodology into design implications. | Verified citation subset | Transfer principles, not external performance figures | Literature-to-design table |
| 3. Stakeholders, needs and proposed requirements | Distinguish brief-derived needs from direct consultation; list stakeholder groups, engagement method, and measurable proposed requirements with provenance/status. | REF001, REF002, REF004 | No invented meeting, quotation, approval, or stakeholder priority | Stakeholder map; requirement/verification matrix |
| 4. Concept A | Describe the Raspberry Pi global-shutter/CSI concept, its benefits, limits, and unique incremental procurement. | Raspberry Pi official data; supplier pages | Comparator only; no Plan A measured result | Concept-A block diagram; unique-cost table |
| 5. Concept B | Describe the ESP32S3 OV3660/Wi-Fi/Pi/STM32 concept, its benefits, limits, and supplied-hardware fit. | REF003, REF005, REF006; manufacturer docs | Sole implementation path; capability is not achieved application performance | Concept-B block diagram |
| 6. Concept selection | Apply pass/fail feasibility gates before weighted technical comparison; explain why a lower technical score can still yield the valid project decision. | Confirmed motivation; cost/stock evidence | Scoring assumptions transparent; shared costs excluded | Feasibility-gate table; weighted matrix |
| 7. Functional system architecture | Present end-to-end information and control flow, power domains, health states, and safe output boundary. | REF005, REF006, REF009-REF012 | Proposed final system plus bounded implemented software elements | Full functional block diagram |
| 7.1 Optical head | Specify camera resolution, fixture, ROI, controlled bright/dark-field lighting, focus/exposure locking, and angular-coverage limits. | REF006-REF008; optics literature | No full-360-degree or minimum-size claim | Optical-head diagram/spec table |
| 7.2 Auxiliary sensing | Explain SFH4555/BPW46/LM324/MCP3208 presence and optical-health channel, signal-conditioning calculation method, and role boundary. | REF003, REF005; datasheets | Health/presence support, not spatial defect classification | Analogue signal-chain table |
| 7.3 Processing and data | Explain newest-frame acquisition, OpenCV baseline, candidate merging, calibration gates, data contracts, SQLite records, and evidence labels. | REF009-REF012 | Candidate events until validated; physical values null before calibration | Software pipeline/state diagram |
| 7.4 STM32 and safe I/O | Explain encoder counting, timestamp exchange, heartbeat, lighting control, and inhibited marker/stop output. | REF006, REF010; STM32 docs | Safety-oriented prototype, not certified machinery safety | State/action table |
| 7.5 Communications and API | Specify Wi-Fi MJPEG, USB serial, SPI, I2C, REST, WebSocket, schemas, timing, and recovery. | REF005, REF006, REF012; source code | Existing Windows endpoints identified; Pi deployment remains planned | Interface-control table; API table |
| 7.6 User interface | Link operator information needs to health, live candidates, evidence status, alarm history, export, and local LCD states. | REF005, REF012 | No unvalidated quality grade or metric displayed | UI-information table |
| 7.7 Power and protection | Provide separate computing and 12 V auxiliary allocations, margin calculation, fusing, reverse-polarity protection, flyback suppression, grounding, and measurement plan. | REF003, REF005; datasheets | Design allocation, not measured consumption | Power-budget table |
| 8. Current implementation evidence | Report SVGA selection, throughput, bounded latency, fault/recovery, offline software contracts, and explicit non-results. | REF006-REF012 | Preserve `LIVE_INTEGRATION_ONLY` and `OFFLINE_SYNTHETIC_ONLY` labels | Evidence-status table |
| 9. Calibration and validation | Convert Option C into an optical/encoder calibration and independent spool/batch/event validation plan with acceptance logic. | REF002, REF004; evaluation literature | All physical metrics pending Week 5 Thursday materials | V-model/verification table; dataset split diagram |
| 10. Environmental, safety, ethical and governance implications | Address SDG 12, energy/e-waste/reject trade-offs, camera minimisation, machinery risk assessment, access/retention, procurement, and configuration control. | ISO/OAIC/UN sources; REF001-REF004 | No certified safety, legal compliance, or net lifecycle benefit claim | Governance-control table |
| 11. Bill of materials | Separate supplied, common additional, and Plan-A-only items; give quantities, purpose, price basis/date, and uncertainty. | REF003, REF005; current supplier pages | Allowances labelled; shipping and unquoted costs excluded | BOM and cost comparison |
| 12. Project delivery plan | Explain stage-gated/V-model strategy, Week 5 Thursday material dependency, milestones, verification outputs, six-member allocation, and integration cadence. | User timing; REF005; rubric | Future work stated as planned, not completed | Timeline; responsibility matrix |
| 13. Risk register | Rank technical, electrical, mechanical, privacy, procurement, data, and schedule risks with owners, triggers, mitigations, and residual risk. | REF005; standards/guidance | Risk reduction does not imply elimination | Risk register |
| 14. Recommendation and conclusion | Close the decision loop: Plan B is recommended for implementability and evidence discipline; acceptance depends on explicit post-arrival gates. | All preceding evidence | No repetition-only conclusion; no overclaim | Recommendation-gate table |
| References | Supply a coherent IEEE-style subset of verified primary/authoritative sources. | Citation support bank | No unverified or mismatched citation | Numbered reference list |

## Target balance

- Functional architecture, component operation, power, communications, API, and traceability receive the greatest depth because Functional Details carry 25%.
- Project strategy, schedule, responsibilities, risks, recommendation, and conclusion form the second-largest block because the corresponding rubric category carries 20%.
- Literature and stakeholder material is analytical but compact; direct consultation remains explicitly incomplete rather than fabricated.
- Tables and diagrams carry repeated technical fields; prose interprets why each item changes the engineering decision.

