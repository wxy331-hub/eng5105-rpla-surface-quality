# Claim Register

| Claim | Evidence ID | Strength | Allowed Wording | Avoid |
|---|---|---|---|---|
| At least two concepts must be discussed. | E01 | Authoritative | “The rubric requires at least two concepts; therefore Plan A is retained as a bounded comparator.” | Implying Plan A will be built or tested |
| Plan B is the only implementation path. | E05 | Strong project decision | “Plan B is selected for implementation and subsequent validation.” | Describing a future migration to Plan A |
| Plan A has an imaging advantage. | External primary source pending | Provisional | “A global-shutter concept is expected to reduce motion-skew risk relative to the rolling-shutter Plan B camera.” | Quoting unmeasured accuracy or line speed |
| Plan A fails feasibility. | E04, E05, E12 | Strong decision; cost source pending | “Plan A fails the availability, incremental-cost, and schedule gates.” | Charging shared Raspberry Pi/STM32/lighting items twice; inventing quotes |
| SVGA is selected and 10.77 FPS was observed. | E06 | Strong integration evidence | “At SVGA, a 30 s integration test observed 10.77 FPS with no reported drops under the recorded conditions.” | “The defect detector operates at 10.77 FPS on rPLA”; “R4 is met” |
| The existing latency test is bounded. | E07 | Strong integration evidence | State the measured path and explicitly exclude sensor-exposure-to-browser latency. | Calling it total system latency |
| Network fault handling works in the tested path. | E08 | Strong integration evidence | Report the fault-injection method, states, suppression action, and recovery timing. | Generalising to final deployed reliability |
| Software contracts exist before physical testing. | E09, E10 | Strong software evidence | “The pipeline, storage schema, latest-frame policy, and evidence labels have been implemented and tested offline/live.” | Treating synthetic detections as physical defects |
| Physical defect performance is unknown. | E06-E11 | Certain limitation | “Precision, recall, F1, minimum detectable defect size, millimetre accuracy, and usable line speed remain pending real-material validation.” | Any numerical physical-performance claim before Week 5 Thursday |
| Proposed R1-R10 are design targets. | REF005 | Provisional | Label every requirement as proposed or pending stakeholder confirmation. | “Stakeholders approved…” without records |
| Stakeholder consultation is incomplete. | Source-map prohibition | Certain limitation | Describe a consultation plan, questions, decision log, and requirement-change method. | Inventing participants, dates, quotes, or approvals |

