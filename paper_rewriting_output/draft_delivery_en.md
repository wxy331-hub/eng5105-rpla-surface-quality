# 8. Environmental, Safety, Ethical and Governance Implications, including Procurement

A recycled feedstock does not make the monitor environmentally beneficial by default. Earlier warning may avoid further processing or use of visibly non-conforming filament, which supports the intent of Sustainable Development Goal 12 [27]. Yet the camera, Raspberry Pi, lighting and network consume energy, added electronics carry embodied impacts, and a poorly tuned detector may create avoidable rejects. No life-cycle assessment has been completed. Energy and reject observations will be reported separately; a net benefit will not be claimed without a defined ISO 14040-compatible comparison [26]. Reused university hardware and repairable fixture parts are design choices, not proof of environmental superiority.

Responsible operation requires uncertain measurements to remain outside automatic quality decisions. A stale frame, missing heartbeat, unhealthy camera, absent calibration or invalid encoder state will inhibit marking, rejection and stop requests. The proposed STM32 watchdog provides independent supervision. Fuses, reverse-polarity protection, local decoupling and appropriate flyback suppression address electrical hazards. Moving guides and the optional marker require guarding, low-energy commissioning and an accessible independent stop. These measures are informed by ISO 13849-1 [24], but the prototype is neither safety-certified nor suitable for representation as an industrial safety-related control system.

The camera creates a different obligation. It will view an enclosed filament region, crop locally to that ROI and save event evidence rather than continuous video. Access, retention and deletion rules must be agreed before data collection, with laboratory notice and controlled export; OAIC guidance and the Privacy Act provide context [25], [33], but this proposal makes no legal-compliance finding. A frame containing a person is quarantined from the defect dataset pending review.

Configuration governance separates a convincing demonstration from reproducible evidence. We will version camera settings, ROI, software, calibration files, requirement status and protocol as one baseline. A reported result needs its evidence label, conditions and configuration. `position_mm` and `size_mm` stay null until valid optical and encoder calibration IDs exist, while spool-, batch- or event-group partitions are fixed before tuning. Consultation outcomes, requirement changes, failed tests and waivers enter a decision log that never assumes stakeholder approval, applying the traceability intent of ISO/IEC/IEEE 15288 [34] and OT security's separation of operational, network and human controls [32].

Procurement uses the same discipline. On 15 August 2026, the only verified Plan B price was A$41.30 for the 400 P/R encoder [31]; lighting, power/protection, fixture and marker figures remain planning allowances. Plan A listings showed A$92.55 for the camera and A$43.60 for its lens, with the camera out of stock [29], [30]. Approval requires a fresh stock, compatibility and delivered-cost check. No Plan A item will be ordered for implementation.

# 9. Bill of Materials

Only a subset of the present cost numbers is supplier-verified. Table 15 therefore separates university-supplied equipment, verified supplier prices and team planning allowances. All amounts are Australian dollars; supplier figures were accessed on 15 August 2026 and include GST unless the listing indicates otherwise. Shipping is excluded. Physical issue, condition and compatibility of supplied parts still require an incoming check [4].

**Table 15. Plan B bill of materials and additional-procurement envelope.**

| Status | Item or group | Qty. | Plan B purpose | Cost basis | Cost charged |
|---|---|---:|---|---|---:|
| University supplied | Raspberry Pi 4 4 GB, power supply and 32 GB SD card | 1 set | OpenCV service, API/WebSocket, SQLite and GUI [21] | Supplied; condition to be checked | A$0 |
| University supplied | STM32 Nucleo-L432KC | 1 | Encoder, heartbeat, lighting and inhibited output interface [22] | Supplied; condition to be checked | A$0 |
| University supplied | XIAO ESP32S3 Sense with OV3660 | 1 | SVGA MJPEG acquisition node [18]-[20] | Supplied; condition to be checked | A$0 |
| University supplied | SFH4555, BPW46, LM324N and MCP3208 | 1 channel/set | Filament-presence and optical-head health channel | Supplied; final component values pending measurement | A$0 |
| University supplied | I2C LCD, LEDs, potentiometers, resistors, breadboard, protoboard, wire and headers | As issued | Local status, conditioning and prototype assembly | Supplied; quantity/condition to be checked | A$0 |
| Verified purchase | Incremental photoelectric rotary encoder, 400 P/R | 1 | Length-position measurement | Supplier listing [31] | A$41.30 |
| Planning allowance | Controlled diffuse and low-angle lighting | 1 set | Repeatable bright-/dark-field imaging | Team range; supplier not fixed | A$30-A$60 |
| Planning allowance | 12 V supply, 5 V conversion, MOSFET, fuses, connectors and protection | 1 set | Separate auxiliary power and protected switching | Team range; topology/quote pending | A$30-A$50 |
| Planning allowance | Mirrors, enclosure, brackets and guides | 1 set | Enclosed optical geometry and filament control | Team range; dimensions pending receipt | A$30-A$70 |
| Planning allowance | Marker/servo demonstrator | 1 | Optional position-based output demonstration | Team range; released only after safe-output review | A$10-A$25 |
| **Plan B additional-procurement envelope** |  |  |  | **One verified price plus four allowances** | **A$141.30-A$246.30** |

Plan A remains visible only so the feasibility decision is auditable. Its IMX296 global-shutter camera is technically suited to rapid-motion machine-vision imaging and requires a suitable C/CS-mount lens [23]. Neither item belongs to the implementation BOM; Table 16 isolates both comparison-only purchases.

**Table 16. Comparison-only Plan A imaging procurement.**

| Comparison-only Plan A item | Qty. | Evidence on 15 Aug. 2026 | Verified price |
|---|---:|---|---:|
| Raspberry Pi Global Shutter Camera, CE09593 | 1 | Supplier listing; out of stock [29] | A$92.55 |
| Raspberry Pi 6 mm CS-mount lens, CE06937 | 1 | Supplier listing; in stock [30] | A$43.60 |
| **Plan-A-only imaging subtotal** |  | **Shipping excluded** | **A$136.15** |

Adding that concept-specific subtotal to the common additional-procurement envelope gives a Plan A total envelope of **A$277.45-A$382.45 before shipping**. This is not a quotation or purchase order. Shared Raspberry Pi, STM32, lighting, power, fixture, encoder and marker needs are counted once, so the comparison neither hides common costs nor charges them against Plan A twice.

# 10. Project Delivery Plan and Team Responsibilities

The delivery strategy is stage-gated and V-model-like: needs become proposed requirements, interfaces, hazards and test definitions; implementation is followed by unit checks, subsystem integration, calibrated system tests and independent validation against the same identifiers. Each gate passes only when its specified evidence exists.

The evidence status changes on **Thursday 27 August 2026 (Week 5)**. Before then, no physical rPLA or fixture-material testing occurs. Earlier work is limited to design, procurement preparation, software/synthetic tests and bounded non-rPLA live integration. Late, incomplete, damaged or unsafe materials move the physical milestones; synthetic results cannot fill the gap. Table 17 makes that dependency a release gate rather than a hidden schedule assumption.

**Table 17. Stage-gated delivery schedule and evidence decisions.**

| Stage and timing | Planned work | Gate output and decision rule |
|---|---|---|
| S0: baseline, through Wed. 26 Aug. | Freeze requirements, interfaces, risks, fixture drawings and protocols; retain synthetic/live-integration labels | G0: owner-reviewed versioned baseline; no physical-performance release |
| G1: material gate, Thu. 27 Aug. | Record receipt, quantity, condition, dimensions, traceability and hazards | Pass releases physical work; failure reschedules it and reviews scope |
| S1: safe shakedown, after G1 | Assemble fixture; check guarding, power, communications and inhibited outputs at low energy | G2: completed safety checklist, stable acquisition, no uncontrolled output |
| S2: calibration, Weeks 6-7 | Lock optics; establish scale, counts/mm, camera-marker offset and references | G3: versioned IDs; invalid calibration keeps millimetre fields null |
| S3: acquisition, Weeks 7-8 | Collect labelled events across planned speeds/optical challenges; audit labels and partitions | G4: traceable ground truth and independent groups before tuning freeze |
| S4: robustness, Weeks 8-9 | Integrate subsystems; inject supervised network, power and sensor faults | Recovery evidence and safe inhibition; high unresolved risk blocks automatic output |
| S5: validation, Week 10 | Evaluate event metrics, false alarms/m, location, throughput, latency and record loss on held-out groups | Accept, optimise, narrow the envelope or revise a requirement; report failures |
| S6: release, Weeks 11-12 | Freeze configuration, assemble evidence and peer-review claims | Register links each accepted claim to configuration, test and owner |

This sequence exposes the throughput gap. The recorded SVGA integration test observed 10.77 FPS (`RESOLUTION_TEST_RESULTS_2026-08-11.md`, `LIVE_INTEGRATION_ONLY`; Appendix A, IE1), below the proposed 20 FPS. The independent-validation gate therefore requires optimisation, a narrower speed/field-of-view envelope or a documented requirement change, never a retrospective claim of compliance.

Six role identifiers are used because member names have not been provided. Planned workload shares in Table 18 sum to 100% and guide balancing; they do not determine individual marks.

**Table 18. Proposed team responsibilities, workload shares and contribution evidence.**

| Role | Share | Primary accountability | Fixed support and review | Required contribution evidence |
|---|---:|---|---|---|
| M1, systems/project | 17% | Requirements, stakeholder protocol, architecture, schedule, interfaces, risk and integration | M4 on alarms/acceptance; all module owners | Decision log, baseline and requirement-status records |
| M2, optics/camera | 16% | Camera, lighting, enclosure, coverage, image quality and calibration | M4 images/ROI; M6 optical repeats | Drawings, settings, calibration and image records |
| M3, sensing/power | 16% | Photodiode/ADC, power, protection and electrical inspection | M5 wiring/faults; M4 health logs | Schematics, calculations, inspections and logs |
| M4, vision/UI/data | 18% | OpenCV, GUI, database, tracking, evaluation and analysis | M2 imaging; M6 independent labels/tests | Code, schema, test output and reproducible analysis |
| M5, embedded/comms | 17% | STM32, encoder, timing, watchdog, communications and safe output | M3 power; M6 mechanical/output tests | Firmware, interface traces and fault/position records |
| M6, validation/mechanical/quality | 16% | Rig, ground truth, group split, validation, uncertainty and safety review | M4 metrics; M5 alignment/repeatability | Protocols, label audit, held-out results and review |

Integration remains shared. Each work item names an owner, reviewer, internal date and evidence output. Any interface change requires a version increment, owner review and recorded impact check before it joins the baseline. Released calibration/test data are read-only; corrections are appended, not substituted. We will run a weekly integration build and increase cadence from G3 through the independent-validation gate, keeping hand-offs visible without making M1 or M4 the default owner of unfinished work.

# 11. Risk Register

A risk entry is useful only if the team can see it approaching. Table 19 therefore pairs each proposal-stage risk with an observable trigger, owner, control and residual priority. The ratings are qualitative, not measured probabilities. Residual ratings assume the listed controls are implemented and tested; they do not mean the hazard has disappeared.

**Table 19. Proposal-stage risk register.**

| ID | Risk and consequence | Initial | Observable trigger | Owner | Planned control and contingency | Residual |
|---|---|---|---|---|---|---|
| RSK-01 | Rolling-shutter, MJPEG or motion artefacts resemble or hide defects | High | Candidate rate changes sharply with speed/JPEG setting; edge shape shifts between frames | M2/M4 | Lock exposure and geometry, test settings by speed, use multi-frame confirmation, retain raw event evidence; narrow operating envelope if needed | Medium |
| RSK-02 | Glare or incomplete angular coverage causes false alarms or missed surfaces | High | Saturated ROI, unstable background histogram or repeatable blind sector | M2 | Enclosed bright-/dark-field lighting, matte background, mirrors only after measured coverage test; report uncovered angles | Medium |
| RSK-03 | Wi-Fi loss, latency or stale buffering corrupts online decisions | High | Frame age exceeds threshold, health endpoint fails or backlog grows | M5/M4 | Controlled 2.4 GHz network, latest-frame buffer, reconnection state, healthy-frame qualification and automatic-output inhibition | Medium |
| RSK-04 | Week 5 materials are late, incomplete or unsuitable | High | Receipt gate fails on 27 Aug. or fixture dimensions conflict | M1/M6 | Inspect at G1, keep pre-gate work non-physical, re-sequence software/documentation, escalate scope and dates without fabricating tests | Medium-High |
| RSK-05 | Too few representative defects produce weak or biased validation | High | Required classes/groups are absent or labels cannot be independently checked | M6/M4 | Predefine sample/label protocol, retain interpretable OpenCV baseline, report class coverage and narrow claims; seek further material through approved channels | Medium-High |
| RSK-06 | Adjacent-frame or event leakage inflates performance | High | Frames from one spool, batch or event appear in tuning and test sets | M6 | Freeze group-level partitions before tuning, store provenance, run a partition audit and reject contaminated evaluation | Low-Medium |
| RSK-07 | Calibration drift makes size or position values invalid | High | Focus, working distance, wheel geometry or configuration hash changes; reference check fails | M2/M5 | Bind optical and encoder calibration IDs to records, perform reference checks, invalidate physical fields and recalibrate after change | Medium |
| RSK-08 | Power noise, undervoltage or inductive switching resets controllers or produces unsafe output | High | Pi undervoltage/reset log, rail sag, MCU reset or output pulse during switching | M3/M5 | Separate power domains, fuses, decoupling, flyback suppression, measured inrush/steady-state tests and watchdog-safe defaults | Medium |
| RSK-09 | Guides or marker create pinch, entanglement or unexpected-motion hazards | High | Guard open, alignment jam, watchdog loss or output occurs outside supervised command | M6/M5 | Guarding, low-energy commissioning, independent stop, supervised tests and inhibit output until G2/G4 pass | Medium |
| RSK-10 | Camera captures people or evidence is retained/accessed without an agreed rule | Medium | Face/body appears outside ROI, unapproved export or missing deletion decision | M1/M4 | Enclose/crop view, local event-only storage, notice, role-based access decision and quarantine incidental images | Low-Medium |
| RSK-11 | Interface or configuration mismatch prevents late integration | High | Schema/baud/state mismatch, unversioned setting or module passes alone but fails baseline build | M1 with all owners | Interface-control record, contract tests, versioned configurations, weekly integration and owner-reviewer sign-off | Medium |

The stop rules matter most. RSK-04 blocks physical testing; RSK-06 invalidates the affected performance estimate; RSK-07 forces physical outputs back to null; RSK-08 or RSK-09 inhibits actuation. A residual Medium-High data or schedule risk is accepted only by narrowing the claim or revising the plan through the decision log, not by lowering the evidence label.

# 12. Recommendation and Conclusion

Plan B is recommended as the sole implementation path: ESP32S3 OV3660 acquisition over controlled 2.4 GHz MJPEG, Raspberry Pi 4 vision/service/database/GUI, and STM32 encoder, watchdog, lighting and safe-I/O supervision. Plan A remains technically credible, particularly for motion imaging [23], but it fails the university-hardware availability, incremental-cost, stock/lead-time and semester-delivery gates. The decision is about the strongest buildable concept, not a claim that the Plan B camera is theoretically superior.

The cost boundary supports that judgement. Plan B requires an additional-procurement envelope of **A$141.30-A$246.30 before shipping**; only the A$41.30 encoder is supplier-verified, and the balance is allowance-based. Adding the verified A$136.15 Plan-A-only camera/lens subtotal produces a **Plan A total envelope of A$277.45-A$382.45 before shipping**, while the listed camera was out of stock on 15 August 2026 [29]-[31]. These figures support concept selection but do not authorise a purchase.

The recommendation authorises staged development, not acceptance. Plan B proceeds only through the 27 August material gate, safe assembly inspection, versioned optical and encoder calibration, traceable real-material acquisition, held-out validation and supervised fault testing. Precision, recall, F1, minimum detectable physical size, millimetre accuracy, usable line speed and final latency remain pending. Stakeholder numerical approval is also pending documented consultation. If a gate fails, the defensible response is to optimise, restrict the operating envelope or revise the requirement with a recorded rationale.

The proposed contribution is therefore a controlled measurement chain with honest state boundaries: image acquisition becomes a candidate record; calibration may add physical meaning; independent validation may support a defect claim; only a healthy, current and authorised state may request action. That is the basis on which Plan B should be funded, built and judged.

# Appendix A. Internal Evidence Register

The report's integration and implementation claims are anchored to the frozen local artifacts in Table 20. SHA-256 values identify the exact files reviewed at the evidence cut-off; they do not convert development-host evidence into Pi, STM32 or physical-defect evidence.

**Table 20. Internal integration, configuration and code evidence at 15 August 2026.**

| ID | Relative artifact path | Evidence function and date | SHA-256 |
|---|---|---|---|
| IE1 | `RESOLUTION_TEST_RESULTS_2026-08-11.md` | VGA/SVGA/XGA screen and sustained-rate observations, 11 Aug. 2026 | `A75C316FBD64AFF205F48350EA37271ADEE31FF036F3040AA46EA5C350CDDC3E` |
| IE2 | `LIVE_PATH_TEST_RESULTS_2026-08-11.md` | Brightness-step timing and scoped network-fault observations, 11 Aug. 2026 | `16CFB2FF0C0449AACD100090F80CE764337888F1D67731E60207F5662A58B93D` |
| IE3 | `WEEK3_OFFLINE_IMPLEMENTATION.md` | Offline contracts, provenance and null-field safeguards, 10 Aug. 2026 | `EDB6D6645245F0882FFEC8CDC0B3738FE5109641D9518BC69A7F11204F2F5920` |
| IE4 | `WEEK4_OFFLINE_IMPLEMENTATION.md` | Live link, buffering and fault-state evidence summary, 11 Aug. 2026 | `68D8AA905507B54CFDE71B15CA8D7D7CC6BDA270AA7859C2EC43C7B12FB933C8` |
| IE5 | `config/live_service.json` | Windows development ROI, threshold, minimum area and material-gate configuration | `EEE7038C8A648B48B4518E3FF8F25648E02C4F968B62DD6C0A17E6618F01F67A` |
| IE6 | `src/live_service.py` | Windows development resident service, health logic and API endpoints | `4696AD50719C1BAA6EBC724FB262084647634B09A0DB2F674F218064E189E203` |
| IE7 | `src/week3/vision.py` | Source-independent baseline vision processor and default threshold | `9198E135ADED4A8DE845700F4250591BF529AB497136A1D389C136A61FE5E432` |

# References

[1] Monash University, *ENG5105/ENG5106 Integrated Design Semester 2 2026: Common Context and Project Briefs*, Rev. 0, 2026.

[2] Monash University, *Concept Design: Discipline-Specific Content (Electrical)*, ENG5105, 2026.

[3] Monash University, *Electrical Teams Proposal Report Rubric 2026*, 2026.

[4] Monash University, *ENG5105 Components - With Pictures 2026*, 2026.

[5] D. Hidalgo-Carvajal, Á. Hortal Muñoz, J. J. Garrido-González, R. Carrasco-Gallego and V. Alcázar Montero, “Recycled PLA for 3D Printing: A Comparison of Recycled PLA Filaments from Waste of Different Origins,” *Polymers*, vol. 15, no. 17, art. 3651, 2023. https://doi.org/10.3390/polym15173651

[6] X. Wei and R. Bähr, “A comparative study of 3D printing with virgin and recycled polylactic acid filaments,” *CIRP Journal of Manufacturing Science and Technology*, vol. 54, pp. 75-84, 2024. https://doi.org/10.1016/j.cirpj.2024.08.007

[7] R. Quader, E. Dramko, D. Grewell, J. Randall and L. K. Narayanan, “Characterizing the Effect of Filament Moisture on Tensile Properties and Morphology of Fused Deposition Modeled Polylactic Acid/Polybutylene Succinate Parts,” *3D Printing and Additive Manufacturing*, vol. 11, no. 3, pp. 1151-1161, 2024. https://doi.org/10.1089/3dp.2022.0222

[8] C. Caceres-Mendoza, P. Santander-Tapia, F. A. Cruz Sanchez, N. Troussier, M. Camargo and H. Boudaoud, “Life cycle assessment of filament production in distributed plastic recycling via additive manufacturing,” *Cleaner Waste Systems*, vol. 5, art. 100100, 2023. https://doi.org/10.1016/j.clwas.2023.100100

[9] P. Zhao et al., “Close-looped recycling of polylactic acid used in 3D printing: An experimental investigation and life cycle assessment,” *Journal of Cleaner Production*, vol. 197, pp. 1046-1055, 2018. https://doi.org/10.1016/j.jclepro.2018.06.275

[10] L. Heckler-Kram, J.-H. Neudeck, U. Scheler, R. König and C. Steger, “The MVTec AD 2 Dataset: Advanced Scenarios for Unsupervised Anomaly Detection,” *International Journal of Computer Vision*, vol. 134, no. 4, 2026. https://doi.org/10.1007/s11263-026-02743-0

[11] P. Carvalho et al., “Detecting visual anomalies in an industrial environment: Unsupervised methods put to the test on the AutoVI dataset,” *Computers in Industry*, vol. 163, art. 104151, 2024. https://doi.org/10.1016/j.compind.2024.104151

[12] C. Wang et al., “Real-IAD: A Real-World Multi-View Dataset for Benchmarking Versatile Industrial Anomaly Detection,” in *Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition*, pp. 22883-22892, 2024. https://doi.org/10.1109/CVPR52733.2024.02159

[13] S. Verspeek, T. De Kerf, B. Ribbens, X. Maldague, S. Vanlanduit and G. Steenackers, “A Novel Line-Scan Algorithm for Unsynchronised Dynamic Measurements,” *Applied Sciences*, vol. 14, no. 1, art. 235, 2024. https://doi.org/10.3390/app14010235

[14] K. Sundarrajan and B. K. Rajendran, “Explainable efficient and optimized feature fusion network for surface defect detection,” *The International Journal of Advanced Manufacturing Technology*, 2023. https://doi.org/10.1007/s00170-023-11789-0

[15] M. Katsigiannis and K. Mykoniatis, “Enhancing industrial IoT with edge computing and computer vision: An analog gauge visual digitization approach,” *Manufacturing Letters*, vol. 41, pp. 1264-1273, 2024. https://doi.org/10.1016/j.mfglet.2024.09.153

[16] S. Kapoor and A. Narayanan, “Leakage and the Reproducibility Crisis in Machine-Learning-Based Science,” *Patterns*, vol. 4, no. 9, art. 100804, 2023. https://doi.org/10.1016/j.patter.2023.100804

[17] R. B. D. Figueiredo and H. A. Mendes, “Analyzing Information Leakage on Video Object Detection Datasets by Splitting Images Into Clusters With High Spatiotemporal Correlation,” *IEEE Access*, vol. 12, pp. 47646-47655, 2024. https://doi.org/10.1109/ACCESS.2024.3383047

[18] OmniVision Technologies, *OV3660 Color CMOS QSXGA Image Sensor Datasheet*, ver. 1.3, 2011. https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/OV3660_datasheet.pdf

[19] Espressif Systems, *esp32-camera: ESP32 Camera Driver*, official repository and driver documentation, accessed 15 Aug. 2026. https://github.com/espressif/esp32-camera

[20] Seeed Studio, *Getting Started with Seeed Studio XIAO ESP32S3 Series*, updated 14 May 2026, accessed 15 Aug. 2026. https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/

[21] Raspberry Pi Ltd, *Raspberry Pi 4 Model B Product Brief*, Apr. 2026. https://pip.raspberrypi.com/documents/RP-008344-DS-raspberry-pi-4-product-brief.pdf

[22] STMicroelectronics, *STM32 Nucleo-32 Boards: NUCLEO-L432KC*, DB2638 Rev. 9, Apr. 2026. https://www.st.com/resource/en/data_brief/nucleo-l432kc.pdf

[23] Raspberry Pi Ltd, *Raspberry Pi Global Shutter Camera*, accessed 15 Aug. 2026. https://www.raspberrypi.com/products/raspberry-pi-global-shutter-camera/

[24] International Organization for Standardization, *ISO 13849-1:2023 Safety of Machinery - Safety-Related Parts of Control Systems - Part 1: General Principles for Design*, 2023. https://www.iso.org/standard/73481.html

[25] Office of the Australian Information Commissioner, *Posting Photos and Videos*, accessed 15 Aug. 2026. https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/handling-personal-information/posting-photos-and-videos

[26] International Organization for Standardization, *ISO 14040:2006 Environmental Management - Life Cycle Assessment - Principles and Framework*, 2006. https://www.iso.org/standard/37456.html

[27] United Nations Department of Economic and Social Affairs, *Sustainable Development Goal 12: Responsible Consumption and Production*, accessed 15 Aug. 2026. https://sdgs.un.org/goals/goal12

[28] Monash University, *Welcome to Country and Acknowledgement of Traditional Owners*, accessed 15 Aug. 2026. https://www.monash.edu/brandbook/about/welcome-to-country-and-acknowledgement-of-traditional-owners

[29] Core Electronics, *Official Camera Modules - Raspberry Pi Global Shutter Camera*, A$92.55 and out of stock when accessed 15 Aug. 2026. https://core-electronics.com.au/raspberry-pi/camera/official-camera-modules.html

[30] Core Electronics, *Raspberry Pi 6 mm Wide Angle Camera Lens (CS-Mount)*, A$43.60 when accessed 15 Aug. 2026. https://core-electronics.com.au/raspberry-pi-6mm-wide-angle-lens.html

[31] Core Electronics, *Incremental Photoelectric Rotary Encoder - 400 P/R*, A$41.30 when accessed 15 Aug. 2026. https://core-electronics.com.au/incremental-photoelectric-rotary-encoder-400p-r.html

[32] K. Stouffer et al., *Guide to Operational Technology (OT) Security*, NIST SP 800-82 Rev. 3, 2023. https://doi.org/10.6028/NIST.SP.800-82r3

[33] Australian Government, *Privacy Act 1988*, Compilation No. 103, 10 June 2025. https://www.legislation.gov.au/C2004A03712/2025-06-10

[34] ISO/IEC/IEEE, *ISO/IEC/IEEE 15288:2023 Systems and Software Engineering - System Life Cycle Processes*, 2023. https://www.iso.org/standard/81702.html
