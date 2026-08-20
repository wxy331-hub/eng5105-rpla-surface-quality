# Proposal Design Report

## Evidence-Traceable Surface Quality Monitoring for Recycled PLA Filament

| Document field | Status |
|---|---|
| Client context | BioLoop Manufacturing Pty Ltd |
| Discipline | ENG5105 Electrical Engineering |
| Deliverable | Proposal design report |
| Selected quality parameter | Visible rPLA filament surface quality |
| Selected concept | Plan A: Raspberry Pi Global Shutter Camera over CSI, Raspberry Pi 4 processing and services, STM32 supervision and safe I/O. Interim implementation: ESP32S3 OV3660 acquisition, same downstream chain |
| Concept status | Plan A, direct global-shutter imaging over CSI, is the selected concept. Its procurement is approved but the hardware is not yet in hand, so Plan B runs as the interim implementation until it arrives. Every measurement in this report comes from the Plan B interim path; no Plan A measurement exists yet |
| Evidence cut-off | 15 August 2026 |
| Evidence status | Proposal with bounded integration evidence; real-material calibration and defect-performance validation remain pending |

## Executive Summary

BioLoop needs a laboratory-scale system that watches recycled polylactic acid (rPLA) filament for visible surface problems. The client brief lists bubbles, roughness, contamination, cracks and inclusions, and asks the electrical teams to cover live capture, communication, display, fault detection and, later, factory integration (Monash University, 2026d). Our selected concept is Plan A: a global-shutter camera on a C/CS-mount lens feeding a Raspberry Pi 4 directly, with an STM32 Nucleo-L432KC holding the encoder, the lighting, the watchdog and an inhibited downstream output. Exposing every pixel at once suits a moving subject (Raspberry Pi Ltd, 2026b). Neither the camera nor the lens comes with the university kit, and neither is in hand, so nothing in this report was measured on Plan A.

Until that hardware arrives the build runs on Plan B, which uses boards the university already supplied (Monash University, 2026c): an ESP32S3 camera node feeding the same Raspberry Pi and STM32 roles over a controlled wireless link. Plan B is an interim front end rather than a rejected alternative, because everything downstream of the frame source is shared; Section 5.8 makes the changeover a front-end swap rather than a redesign. One limit belongs up front. The service, API and GUI evidence all comes from a Windows development host, so it says nothing about running on the Pi and nothing about real STM32 I/O.

Nothing yet shows that the system works as an rPLA defect detector. The recorded integration test ran with no rPLA in the region of interest, so it establishes that frames keep moving through the chain and nothing about defect accuracy, minimum detectable size, millimetre position accuracy, usable line speed or industrial readiness. Every numerical requirement in Section 3 still carries the `PROPOSED_REQUIREMENT` label. One open question is settled provisionally: the first build inspects stationary filament, because no transport mechanism has been fixed and no real material has arrived to show how the filament moves. The encoder is still procured and wired, and its interface is still verified, but travel measurement waits. Physical acceptance depends on controlled optics, optical calibration, labelled real-material specimens, independent validation groups and a documented requirement review once the material is in hand.

## Acknowledgement of Country

This project is carried out at the Monash University Clayton campus. We acknowledge the people of the Kulin Nations, the Traditional Owners and Custodians of the unceded lands on which the University's Australian campuses stand, and pay respect to their Elders past and present (Monash University, 2026e). This project concerns circular use of materials, but circularity alone does not make an engineering system responsible. Our work should conserve resources, avoid preventable waste, and account for the energy, electronics and decisions introduced by the monitoring device. We recognise that care for Country carries responsibilities extending beyond the technical boundary of this proposal.

# 1. Background and Purpose

## 1.1 Client and manufacturing context

BioLoop's proposed manufacturing hub is meant to produce rPLA and rPLA-composite filament for Australian education, engineering, manufacturing and consumer markets. Product monitoring sits inside a wider circular-manufacturing system, alongside automation, resource efficiency, safety and economic viability (Monash University, 2026d). Filament only reaches a customer after extrusion, cooling, handling and spooling, so a visible anomaly caught late can mean rework, a rejected product, or a customer who no longer trusts the batch. Watching the line as it runs moves that decision point earlier.

Recycled PLA is not one uniform input. Published comparisons report that feedstock origin, recycling history and processing conditions can all affect the properties of recycled filament and printed products (Hidalgo-Carvajal et al., 2023; Wei & Bähr, 2024). Moisture can influence morphology and tensile behaviour in PLA-containing fused-filament material as well (Quader et al., 2024). Those findings justify monitoring. They do not let a camera diagnose moisture, degradation or extrusion settings from appearance alone. A pit or a colour patch is evidence of a visible condition, and nothing more; its process cause stays a hypothesis until it is checked against independent process and material data.

The circular-economy argument needs the same restraint. Life-cycle studies of distributed filament production and closed-loop PLA recycling show why recovered material deserves serious consideration, and they also show that the benefits depend on system boundaries, energy and process choices (Caceres-Mendoza et al., 2023; Zhao et al., 2018). This proposal claims no completed life-cycle assessment. Its purpose is narrower: get surface-quality evidence in front of a person, a quality system or a later plant controller early enough to act on.

## 1.2 Purpose, question and boundary

The report asks:

> Can a low-cost, supplied-hardware machine-vision system detect, locate and grade visible anomalies on moving rPLA filament under representative laboratory conditions, while withholding unsafe or uncalibrated outputs?

The system has to make useful detections, and their validity has to be established independently. A stream that looks live can still be stale, badly lit or geometrically uncalibrated. That is why acquisition health and evidence status are design functions here, not interface decoration.

Table 1 fixes the investigation boundary before any concepts get compared.

**Table 1. Proposed project scope.**

| In scope | Outside the present claim boundary |
|---|---|
| Visible bubbles or pits, cracks or scratches, contamination or inclusions, and abnormal surface texture identified from controlled images | Engineering roughness parameters such as Ra without a validated profilometric or structured-light reference |
| Laboratory-scale online acquisition, candidate detection, event recording, alarm presentation and safe-output requests | Internal void metrology, polymer chemistry identification, or proof of a defect's process cause |
| Optical and encoder calibration followed by labelled real-rPLA testing | Uncalibrated millimetre dimensions or positions |
| Basic fault detection and integration with a larger automated process, as required by the brief (Monash University, 2026d) | Safety certification, autonomous production release, or industrial deployment claims |

What the system produces, then, is a traceable candidate record and a decision aid for the operator. Automatic rejection is not authorised yet.

One premise sits under the whole design, and the brief does not actually state it. Nowhere does the brief say the filament is moving. It asks for online, real-time acquisition, for measurement under representative operating conditions, and for a system suitable for integration into an industrial filament manufacturing process (Monash University, 2026d). We read those three phrases together and concluded that the representative condition is a continuously running line, because filament production is a continuous extrusion and take-up process rather than a batch one. That conclusion is ours, so it is labelled `TEAM_INFERENCE` and carried in the open rather than presented as a client requirement. It matters because a good deal rests on it: the global-shutter camera in Section 4 is justified by motion, the 0–5 m/min band in R4 is the same assumption written as a number, and the encoder behind R6 exists only to measure travel. If a stakeholder later confirms that static or indexed inspection is acceptable, R4 and R6 relax and the interim rolling-shutter path stops being a compromise; the architecture, the evidence discipline and the safe-output gating are unaffected either way. The premise joins the consultation questions in Section 3, where representative operating speed is already on the list to confirm. For the first build we have taken the other branch provisionally: inspection is planned on stationary filament, because no transport mechanism has been fixed and no real material has arrived to show how the filament moves. That is a starting configuration recorded in the decision log, not a change to the target design, and it is revisited once the filament is in hand.

# 2. Literature Review and Design Implications

## 2.1 What surface images can establish

Research on rPLA gives us a reason to inspect, not a visual ground truth. Material source, repeated processing and moisture can all change performance (Hidalgo-Carvajal et al., 2023; Quader et al., 2024; Wei & Bähr, 2024), and the brief separately lists bubbles, roughness, contamination, cracks and inclusions as surface conditions that may indicate process or material problems (Monash University, 2026d). The word *may* is doing real work in that sentence. We use the literature to define defect families and challenge conditions, then insist on labelled specimens before anything is assigned a class. Visual evidence on its own cannot tell a moisture-driven bubble from a cavity produced some other way, so a causal label needs independent process evidence.

Industrial anomaly-detection research warns against treating a tidy laboratory image as the operating domain. Recent datasets cover advanced operating scenarios, real industrial imagery and multi-view observations (Carvalho et al., 2024; Heckler-Kram et al., 2026; Wang et al., 2024). Their reported model results do not transfer to rPLA, because the objects, labels, optics and prevalence are all different. What does transfer is the experimental discipline: camera geometry, background, illumination, viewpoint and dataset split have to be controlled and documented.

## 2.2 Motion, optics and acquisition

A moving cylindrical filament is a difficult optical target. Highlights migrate as the filament rotates, a single view cannot guarantee full circumferential coverage, and compression can invent block or edge artefacts. Unsynchronised dynamic line-scan research shows why motion and sampling alignment deserve explicit treatment (Verspeek et al., 2024). A feature-fusion study on hot-rolled steel establishes performance inside its own material and dataset and nothing beyond it; it says nothing about illumination or geometry robustness for rPLA (Sundarrajan & Rajendran, 2023). An experimental comparison of area- and line-scan modalities makes a related point: some surface defects become visible only under particular sensor and illumination arrangements (Krassnig et al., 2025). Controlled diffuse and low-angle illumination, a fixed region of interest, locked focus and exposure where the hardware supports it, and a repeatable guide geometry are therefore part of the measurement concept rather than refinements to add later.

Plan A deals with motion at the sensor. Raspberry Pi's global-shutter camera exposes all pixels at the same instant and accepts C/CS-mount lenses (Raspberry Pi Ltd, 2026b). Plan B uses the supplied OV3660 rolling-shutter imager, whose sensor limits are set out in its datasheet (OmniVision Technologies, 2011), through the supported ESP32 camera stack (Espressif Systems, 2026; Seeed Studio, 2026). No datasheet predicts this application's defect accuracy. Plan B has to reduce motion-skew risk another way: bounded line speed, exposure control, repeatable lighting and empirical validation.

## 2.3 Alternatives to area-scan surface imaging

We considered three measurement families, because they answer different quality questions. Area- or line-scan vision preserves spatial evidence about colour, texture, inclusions, cracks and other visible features, though its response depends on view and illumination (Krassnig et al., 2025). Multi-axis optical diameter sensing has been validated on recycled ABS and PLA filament and can record diameter and shape along a spool (Petsiuk & Pearce, 2021), but a diameter trace on its own classifies no visible surface condition and reveals no internal void. Laser-line profilometry supplies quantitative height and topography, and has detected surface deviations from point clouds in material-extrusion research; it also adds equipment and processing cost, and the validation cited concerns deposited layers rather than moving feedstock (Lafirenza et al., 2023).

Given the present brief, the supplied hardware and the semester constraints, Plan B uses area-scan imaging for visible spatial anomalies and the photodiode only for material-presence and optical-health gating. Diameter sensing or profilometry becomes a scoped extension if stakeholder consultation makes diameter or engineering roughness a primary requirement. Naming them here is not evidence that Plan B already measures those properties. The same distinction is why Table 1 excludes Ra and internal void metrology.

## 2.4 Processing roles and evidence flow

Running every task on the camera node would simplify the wiring and compress acquisition, analysis, storage, interface and fault recovery into one resource-constrained device. Edge-computing literature supports putting time-sensitive visual processing near the equipment while keeping system roles distinct (Katsigiannis & Mykoniatis, 2024). So in this design the ESP32S3 takes image acquisition and transport, the Raspberry Pi 4 takes OpenCV, records, services and the GUI, and the STM32 takes deterministic encoder, watchdog, lighting and output supervision. Manufacturer documents establish that the Pi and Nucleo platforms expose suitable computing and interface resources (Raspberry Pi Ltd, 2026a; STMicroelectronics, 2026). That is capability evidence. It is not proof that these roles have been deployed.

This separation creates a useful failure boundary. In the target Pi/STM32 design, a camera timeout puts the Pi service into a reconnecting or fault state while the STM32 inhibits the marker or stop request. A wired-in latest-frame policy and a frame-age watchdog are what stop an old image from quietly becoming a current quality event. Both controls now sit in the resident Windows service and pass threaded unit tests, but neither has been deployed or verified on the Pi. The architecture consequently treats health metadata, timestamps, calibration identifiers and null physical fields as part of the evidence chain.

## 2.5 Validation implications

Adjacent video frames are highly correlated. If near-duplicate frames from one defect land in both training and test data, reported performance comes out optimistic; broader machine-learning work identifies leakage as a reproducibility threat (Kapoor & Narayanan, 2023), and video-object-detection research shows the specific risk that spatiotemporal correlation creates (Figueiredo & Mendes, 2024). Validation therefore separates data by physical spool or batch and by defect event, never by shuffling individual frames at random.

Accuracy on its own would hide what rare defects cost. The proposed assessment reports event-level precision, recall and F1 score, false alarms per metre, missed events, latency, and stability across the declared lighting and speed conditions. Sample counts and uncertainty go with those values. None of them exists yet.

Table 2 turns these literature findings into design decisions and names the project-specific evidence still missing.

**Table 2. Literature-to-design transfer.**

| Evidence cluster | Design implication | Evidence still required for this project |
|---|---|---|
| rPLA variability and moisture (Hidalgo-Carvajal et al., 2023; Quader et al., 2024; Wei & Bähr, 2024) | Treat visible anomalies as observations, not automatic root-cause diagnoses | Labelled real-rPLA specimens linked to documented conditions |
| Industrial anomaly and multi-view datasets (Carvalho et al., 2024; Heckler-Kram et al., 2026; Wang et al., 2024) | Freeze optics and record viewpoint, lighting and dataset provenance | Representative images from the final fixture |
| Dynamic imaging and surface inspection (Krassnig et al., 2025; Sundarrajan & Rajendran, 2023; Verspeek et al., 2024) | Control exposure, motion, geometry and illumination; test coverage limits | Speed challenge and circumferential-coverage study |
| Optical diameter sensing and laser profilometry (Lafirenza et al., 2023; Petsiuk & Pearce, 2021) | Retain them as requirement-driven alternatives, not capabilities implied by area-scan images | Stakeholder priority, comparative test plan and approved cost/schedule change before any scope extension |
| Leakage and correlated video (Figueiredo & Mendes, 2024; Kapoor & Narayanan, 2023) | Split validation by independent spool/batch/event | Pre-registered dataset split and held-out test results |

# 3. Stakeholders, Needs and Proposed Requirements

## 3.1 Stakeholder evidence status

Nobody has handed us a record of talking to a stakeholder, so this report has none. Everything below comes from the BioLoop brief, the discipline instructions and the literature. None of it should be read as something a client said, a participant agreed to, or a meeting settled. The distinction matters because the rubric asks for engagement and for requirements that actually shape the design (Monash University, 2026a, 2026b). We can write down what ought to be discussed. We cannot invent what someone said.

**Table 3. Stakeholder map and provisional design response.**

| Stakeholder group | Need inferred from brief or system use | Proposed design response | Current status |
|---|---|---|---|
| BioLoop/client representative | Traceable quality evidence, cost awareness and a path to automated integration | Requirement register, event records, API and explicit acceptance gates | Brief-derived; confirmation pending |
| Production operator | Clear health state, actionable alarms and no silent stale-data decision | Single-screen status, candidate overlay, alarm history and inhibited output when unhealthy | Proposed |
| Quality assurance personnel | Reviewable images, batch context, repeatable classification and export | Versioned calibration/model identifiers, immutable event fields and dataset export | Proposed |
| Maintenance and electrical personnel | Diagnosable faults, serviceable interfaces and safe recovery | Camera/processor/encoder/lighting health, watchdog states and manual reset rules | Proposed |
| Laboratory supervisor and technical staff | Safe, testable use of supplied equipment | Enclosed optical path, low-voltage prototype domains and staged fault tests | Brief- and equipment-derived |
| Filament users | Consistent product information without unsupported quality claims | Evidence-backed grading only after validation; retain uncertain events for review | Literature-derived; confirmation pending |

What we can deliver at this stage is the engagement plan itself. No session has been held, so every consultation outcome in this report is recorded as pending. M1 owns the plan. It covers the six groups in Table 3 through short structured sessions built to test assumptions rather than collect a ceremonial signature. Each session asks the same five questions: which defect families cause rejection, what false-alarm burden is tolerable, how long evidence must be retained, who may authorise a stop or reject action, and which operating speeds and lighting conditions count as representative. Answers go into a dated decision log that records the affected requirement, the owner, the rationale and any change to verification. A confirmed answer updates the status column of Table 3 and the stakeholder-basis column of Table 4. An unanswered question stays visible as pending; it does not get closed by assumption. No representative material has arrived and no calibration exists, so every value that depends on measurement is unconfirmed, and nothing in Table 3 is claimed as stakeholder-approved.

## 3.2 Proposed requirements and verification

Every numeric threshold in Table 4 carries the `PROPOSED_REQUIREMENT` label. The numbers exist because the electrical discipline guidance asks for a testable design baseline (Monash University, 2026a), and writing a number down is what makes a requirement arguable in the first place. They are our numbers, though, and stakeholder review or experimental evidence can still move any of them.

**Table 4. Proposed requirements register.**

| ID | Proposed requirement | Stakeholder/source basis | Planned verification | Status or present gap |
|---|---|---|---|---|
| R1 | Detect at least three agreed classes of visible surface anomaly | Defect families from the project brief (Monash University, 2026d); class count is team-proposed and awaits stakeholder confirmation | Held-out, event-level labelled test | `PENDING_REAL_MATERIAL` |
| R2 | For each accepted R1 class, target the declared class-specific characteristic dimension at or above 0.20 mm | Team engineering target under the discipline requirement for measurable specifications (Monash University, 2026a); stakeholder confirmation pending | Calibrated target and labelled specimens using the definitions below | `PENDING_REAL_MATERIAL`; optical scale unavailable |
| R3 | For every accepted R1 class whose events meet R2, achieve event-level precision and recall of at least 90% per class | Team performance target under (Monash University, 2026a); false-alarm and miss tolerance await stakeholder confirmation | Independent spool/batch/event split; report per-class counts and confidence intervals | `PENDING_REAL_MATERIAL`; no accuracy result exists |
| R4 | Process at least 20 frames/s while filament speed is 0–5 m/min | Team throughput target under (Monash University, 2026a); operating envelope awaits stakeholder confirmation | Sustained final-fixture run plus speed challenge | Not achieved: current SVGA integration observation is 10.77 frames/s; latest-frame and drop instrumentation are now in the service but unmeasured on the Pi |
| R5 | At P95, assert the alarm within 500 ms from the first reference-video frame in which a marked defect crosses the frozen ROI entry line | Team alarm target under (Monash University, 2026a); response expectation awaits stakeholder confirmation | Synchronously film the scene reference and GUI/output; include confirmation, processing, communications and indication | Proposed; current brightness-control path timing is not this measure |
| R6 | Limit longitudinal defect-location error to ±10 mm | Team position target under (Monash University, 2026a); stakeholder confirmation pending | Encoder counts/mm calibration and marked-distance test | `PENDING_REAL_MATERIAL`; encoder calibration absent |
| R7 | Store defect type, size, confidence, evidence image, position, time and batch identifier with the required calibration provenance | Data and visualisation need from the brief (Monash University, 2026d), made testable under (Monash University, 2026a) | Schema, file and record audit | Partly implemented; live evidence images and complete optical/encoder provenance remain pending, and size/position stay null until calibration |
| R8 | During a 30 min run, keep confirmed-event record loss below 1%, where `loss = (N_expected - N_complete) / N_expected` and a complete record has its durable database row plus required evidence image | Team reliability target under (Monash University, 2026a); stakeholder tolerance pending | Reconcile frozen expected event IDs against durable database rows, image files and export; report frame drops separately | Proposed; drop instrumentation is now in the service, but the final hardware test remains pending |
| R9 | Enter a safe hold or fault state after camera, lighting, encoder or processor failure | Fault-detection/integration need from the brief (Monash University, 2026d); team safety interpretation, with later risk assessment required | Fault injection and output-state observation on final wiring | Software/network path evidence only; physical safe I/O pending |
| R10 | Store and serve only images confined to the enclosed filament tunnel, with local-only storage and external publication disabled by default | Team privacy-by-design control; legal and stakeholder retention/access rules remain pending | Audit every final-evidence image and the storage/access configuration; accept zero outside-tunnel or person-containing frames | Not achieved by the current full annotated development preview; enclosure and release controls pending |

R2 needs one frozen primary dimension per accepted class, or the same threshold ends up meaning different things to different people. We use equivalent-circle diameter for a compact pit, bubble, inclusion or contamination region; calibrated transverse width for a crack or scratch, with axial length reported separately; and the smaller calibrated bounding dimension for an abnormal-texture patch. Class definitions and the ground-truth method are approved and frozen before data collection, so the 0.20 mm threshold cannot be quietly redefined once results are in. R3 works the same way: precision and recall must both pass for each of the three or more accepted classes, and we keep every class's event counts and confusion matrix so a macro or micro summary cannot bury a failing class. A pilot will indicate the minimum independent event count, but that count is frozen before the untouched test rather than picked afterwards.

R4 is where the design tension shows most clearly. A lower interim demonstration threshold may well help integration along, but it cannot quietly replace the 20 frames/s final target; moving that target takes a documented requirement change. If the final fixture misses it, the defensible responses are optimisation, a justified line-speed limit, or formal renegotiation. Reporting only the runs that passed is not one of them.

# 4. Concepts and Selection

## 4.1 Selection method

The rubric requires at least two differentiated concepts and an evidence-backed recommendation (Monash University, 2026b). We apply four pass/fail gates before any preference scoring: availability of the issued primary imaging hardware, avoidance of an unapproved concept-specific primary-camera purchase, procurement timing, and semester deliverability. A concept that fails a mandatory gate is not a candidate for implementation, however attractive it looks technically. These are team feasibility decisions for this proposal, not stakeholder-approved budget limits.

## 4.2 Plan A: direct global-shutter imaging (selected concept)

Plan A connects a Raspberry Pi Global Shutter Camera to the Pi through CSI, uses a suitable C/CS-mount lens and controlled lighting, and keeps the STM32-based encoder, watchdog, lighting and safe I/O functions. Its main strength is that the whole image array is exposed at once, which suits rapid motion and machine-vision work (Raspberry Pi Ltd, 2026b). Local CSI transport also takes Wi-Fi and MJPEG out of the camera-to-processor path. Optical alignment, reflective cylindrical geometry and single-view coverage would still need calibration.

The concept is credible, and it is the one we selected. Its procurement is approved, but the camera is not university-supplied and was out of stock at the access date, so the hardware is not in hand and no Plan A measurement exists. Table 5 lists only the purchases unique to Plan A.

**Table 5. Verified Plan-A-only incremental procurement, accessed 15 August 2026.**

| Item | Quantity | Price | Observed availability | Source |
|---|---:|---:|---|---|
| Raspberry Pi Global Shutter Camera | 1 | A$92.55 | Out of stock | (Core Electronics, 2026b) |
| Raspberry Pi 6 mm CS-mount lens | 1 | A$43.60 | In stock | (Core Electronics, 2026c) |
| **Plan-A-only subtotal** |  | **A$136.15** | Shipping excluded | Calculated from (Core Electronics, 2026b, 2026c) |

The subtotal sits on top of common prototype needs. No Raspberry Pi, STM32, encoder, lighting, enclosure, power/protection or marker cost is charged twice. Against the Plan B additional-procurement envelope in Section 9, this A$136.15 increment is roughly 53–84%. The purchase is approved, which clears the availability and cost gates. Lead time is the gate still open: the camera was out of stock at the access date and delivery is not confirmed, so the optical chain cannot be integrated and calibrated inside the window this report covers. Plan A is therefore the selected target configuration, and Plan B carries the build until the hardware arrives.

## 4.3 Plan B: supplied-hardware distributed vision (interim implementation)

Plan B uses the university-supplied XIAO ESP32S3 Sense, Raspberry Pi 4 and STM32 Nucleo-L432KC (Monash University, 2026c). Its proposed chain is:

> Controlled optical head and rPLA filament -> ESP32S3 OV3660 acquisition -> 2.4 GHz Wi-Fi MJPEG -> Raspberry Pi 4 OpenCV, API/WebSocket, SQLite and GUI <-> STM32 encoder, watchdog, lighting and inhibited output interface

The OV3660 and ESP32 camera documentation supports the chosen acquisition stack (Espressif Systems, 2026; OmniVision Technologies, 2011; Seeed Studio, 2026), and the Pi and Nucleo documents support their planned processing and interface roles (Raspberry Pi Ltd, 2026a; STMicroelectronics, 2026). Plan B needs no new primary camera and builds on software and a live transport path that are already integrated, which is why it can carry the project while the Plan A hardware is in procurement. It also puts real limitations on display: rolling-shutter distortion, JPEG artefacts, wireless delay or interruption, limited optical control, and no guaranteed full-circumference view. Those constraints become test conditions and risk controls. Choosing Plan A does not make them go away.

## 4.4 Feasibility gates and technical comparison

Table 6 applies the mandatory gates first; Table 7 records the technical preferences afterwards.

**Table 6. Mandatory feasibility gates.**

| Gate | Plan A | Plan B | Decision significance |
|---|---|---|---|
| Primary imaging hardware available, issued or approved for purchase | **Pass**: the global-shutter camera and lens are not issued, but concept-specific procurement is approved | **Conditional pass**: primary camera and computing platforms are listed as supplied; issue, condition and compatibility checks remain pending (Monash University, 2026c) | Plan A starts from an approved purchase instead of the issued baseline |
| No unapproved concept-specific primary-camera purchase | **Pass**: the A$136.15 camera and lens purchase is approved; it still represents approximately 53–84% of the Plan B additional-procurement envelope | **Pass** for primary imaging: no additional main camera purchase; common additions remain subject to approval | Approval removes the budget-authority objection; it does not by itself deliver hardware |
| Procurement/lead-time exposure | **Fail**: camera out of stock when accessed on 15 August 2026 (Core Electronics, 2026b); delivery is not yet confirmed, so no arrival date may be assumed | **Conditional pass with residual risk**: core platforms still need issue checks; the encoder page showed zero local stock and expected dispatch on 24–27 August, while fixture, lighting and protection parts remain unfrozen (Core Electronics, 2026a) | A supplier dispatch estimate is not a delivery commitment; neither concept may rely on an unverified arrival date |
| Semester implementation and validation | **Deferred**: the Plan A optical chain cannot be integrated and calibrated within the window this report covers, so Plan B carries the interim build and Section 5.8 defines the migration | **Pass conditionally**: existing Plan B path can proceed to real-material tests | Plan A validation follows delivery; Plan B interim validation remains conditional on material and fixture availability |

A separate scoring exercise records technical preference, and it does not override those gates. Scores are team-assigned comparative judgements from 1 (weak) to 5 (strong), not measurements. The provisional weights put 65% on measurement capability (R1–R4 and R6), 15% on Pi integration (R4, R7 and R8), and 20% on cost and procurement constraints. They reflect the team's present technical judgement, and we claim no stakeholder approval for them. R5 is not scored separately because neither concept has a physical scene-to-alarm result: Plan A removes the Wi-Fi leg, which is not the same as proving the 500 ms target. R9 and R10 are common STM32, enclosure and governance obligations rather than camera-choice discriminators. R5, R9 and R10 therefore stay mandatory release tests for Plan B; they are not benefits its weighted score implies. The matrix is sensitive to its weights, so it exposes the trade-off rather than certifying the decision.

**Table 7. Weighted concept comparison.**

| Criterion | Weight | Plan A | Plan B | Basis of judgement |
|---|---:|---:|---:|---|
| Defect-classification potential (R1, R3) | 25% | 5 | 3 | Plan A offers a more configurable machine-vision optical chain; neither concept has rPLA accuracy data |
| Motion-imaging suitability (R2, R4) | 20% | 5 | 2 | Global shutter versus rolling shutter and compressed wireless transport (OmniVision Technologies, 2011; Raspberry Pi Ltd, 2026b) |
| Spatial-detail potential (R2, R6) | 20% | 4 | 3 | Interchangeable lens and optical control versus supplied OV3660 path |
| Raspberry Pi integration (R4, R7, R8) | 15% | 5 | 4 | Direct CSI versus supported network acquisition and service integration |
| Concept-specific cost (project constraint) | 10% | 4 | 5 | A$136.15 plus shipping for Plan A imaging, now an approved purchase rather than an unfunded one; no new Plan B main camera |
| Procurement timing (schedule constraint) | 10% | 3 | 5 | Plan A camera out of stock; Plan B core platforms listed as supplied, subject to issue check |
| **Weighted total** | **100%** | **4.50** | **3.35** | Comparative score only |

Plan A leads the weighted matrix and now clears the availability and cost gates, so it is the selected concept. The one gate still open is lead time, and it constrains sequence rather than choice: the camera was out of stock at the access date, delivery is not confirmed, and the optical chain cannot be integrated and calibrated inside the window this report covers. Plan B therefore runs as the interim implementation on supplied hardware — which is what produced the evidence recorded in Sections 5 to 7 — and Section 5.8 defines the migration executed on delivery. The ordering is deliberate: the interim path keeps requirements, contracts, supervision and validation moving while the selected optics are in procurement. Neither configuration is claimed to meet R1-R10 on present images.

# 5. Functional Design and Specifications

The design splits the inspection task into two measurement paths, and they are deliberately unequal. The camera path carries the spatial evidence: where a visible candidate region sits and what shape it has. The auxiliary infrared path answers something much narrower — is material there, and is the optical head behaving the way it should? A candidate gets recorded only when acquisition is healthy. An automatic marker or stop request needs a good deal more than that: healthy acquisition, valid calibration, confirmed material presence, a validated event rule, and an output that has been enabled. That boundary is the heart of the design. A bright contour is not a defect just because software can draw a box around it.

The selected acquisition device is the Raspberry Pi Global Shutter Camera on a C/CS-mount lens (Core Electronics, 2026c; Raspberry Pi Ltd, 2026b), wired straight into the Raspberry Pi 4. Until that hardware arrives, acquisition runs on the university-supplied XIAO ESP32S3 Sense with OV3660 (Monash University, 2026c). The processing platforms do not change between the two: the Pi takes the non-deterministic vision and data services, and the STM32 Nucleo-L432KC takes time-critical I/O supervision. The one difference is that the interim ESP32S3 also handles acquisition and JPEG compression, a job the CSI path takes away from it. Manufacturer documents back those platform capabilities (Espressif Systems, 2026; OmniVision Technologies, 2011; Raspberry Pi Ltd, 2026a, 2026b; Seeed Studio, 2026; STMicroelectronics, 2026). What they cannot back is application performance or a finished Pi/STM32 deployment, and every measured value in this report came off the interim configuration.

## 5.1 End-to-end functional architecture

**Figure 1. Proposed hardware, data and inhibited-action architecture, showing the selected Plan A acquisition front end and the interim Plan B front end that feeds the same downstream chain.**

```mermaid
flowchart LR
    subgraph OH["Enclosed optical head"]
        F["Moving rPLA filament"]
        L["Controlled bright-field and dark-field LED strip lighting"]
        CA["Selected: IMX296 global-shutter camera, C/CS lens, fixed focus and exposure"]
        CB["Interim: OV3660 camera at fixed focus and exposure"]
        IR["SFH4555 infrared emitter"]
        PD["BPW46 photodiode"]
        AF["LM324 transimpedance and low-pass stage"]
        F --> CA
        F --> CB
        L --> F
        IR --> F --> PD --> AF
    end
    CA -->|"CSI ribbon; uncompressed frames"| P["Raspberry Pi 4: OpenCV and resident service"]
    CB --> E["XIAO ESP32S3: SVGA MJPEG acquisition"]
    E -->|"Controlled 2.4 GHz Wi-Fi; HTTP/MJPEG"| P
    EN["400 P/R encoder; NPN open collector"] -->|"A/B; 10 kΩ pull-ups to STM32 3.3 V"| S["STM32 Nucleo-L432KC"]
    AF -->|"conditioned analogue; divider and clamp to the STM32 converter"| S
    P <-->|"USB serial: heartbeat, time, position, presence state and commands"| S
    P --> D["SQLite evidence database"]
    P --> A["REST API and WebSocket"]
    A --> G["Web GUI and local operator view"]
    S --> LC["Lighting control"]
    S --> O["Protected marker, reject or stop interface"]
    P -. "Enable only after validation and all health gates" .-> O
    PWR["Auxiliary power and protection (Figure 4)"]
    PWR -->|"5 V"| E
    PWR -->|"switched 12 V"| O
    PWR -->|"switched 12 V"| L
    PWR -->|"12 V"| EN
```

Figure 1 puts the vision and service functions we developed on Windows into the Pi role they are meant to occupy, and separates them from the action authority the STM32 is meant to hold. The arrows describe the target integration baseline, not wiring that exists. Both acquisition front ends are drawn together because everything downstream of the frame source is shared: the Plan A camera reaches the Pi over a CSI ribbon, the interim Plan B camera reaches it over controlled 2.4 GHz MJPEG, and both hand frames to the same source-independent contract. Only one front end runs at a time. That shared boundary is exactly what makes the migration in Section 5.8 a front-end swap instead of a redesign.

The diagram also marks the action boundary. Raspberry Pi software may propose an event; the STM32 owns the physical output and withdraws permission the moment heartbeat, encoder, lighting or communications health is lost. This is a safety-oriented laboratory control architecture. It is not a safety-certified machinery function, and that difference is not a matter of wording. Connecting any of it to production equipment later would need a machine risk assessment and a safety-function design against the relevant framework, ISO 13849-1 included, rather than a prototype watchdog carrying that weight alone (International Organization for Standardization, 2023). OT network segmentation and least-functionality principles would apply as well (Stouffer et al., 2023).

Every requirement below still carries the `PROPOSED_REQUIREMENT` label. The project brief establishes the need for laboratory-scale, online surface-quality monitoring (Monash University, 2026d), and the discipline guidance requires measurable specifications with a verification route (Monash University, 2026a). Neither of those amounts to a stakeholder approving our numbers, and no record supplied to this report shows that anyone has. Table 8 assigns each requirement to functions and a verification route, and leaves the gap visible rather than papering over it.

**Table 8. Functional allocation and verification status of the proposed requirements.**

| ID | Proposed target | Functional allocation | Verification and present status |
|---|---|---|---|
| R1 | Detect at least three visible surface-defect classes. | Optical head; OpenCV/event classifier; labelled database. | Independent real-rPLA event test. `PENDING_REAL_MATERIAL`; current boxes are candidates only. |
| R2 | Demonstrate the frozen class-specific characteristic dimension at or above 0.20 mm. | Fixed optics, pixel scale and class-specific event measurement defined in Section 3.2. | Calibrated reference features at final working distance. `PENDING_REAL_MATERIAL`. |
| R3 | For every accepted R1 class meeting R2, achieve event-level precision and recall of at least 90% per class. | Event logic, ground truth and evaluation scripts. | Held-out spool/segment/event evaluation; report per-class counts, confidence intervals, F1 and macro/micro summaries. `PENDING_REAL_MATERIAL`. |
| R4 | Process at least 20 frames/s from 0–5 m/min. | Selected chain: camera, CSI transport, newest-frame policy and Pi vision. Interim chain adds the Wi-Fi leg. | Sustained final-fixture throughput at each test speed. Not met by the recorded 10.77 FPS SVGA integration result; latest-frame and drop instrumentation are now wired into the resident service but remain unmeasured on the Pi. |
| R5 | At P95, assert the alarm within 500 ms from marked-defect crossing of the frozen ROI entry line. | Timestamped event tracker, confirmation rule, API/UI and STM32 output request. | Synchronously filmed scene reference through GUI/output indication. Existing brightness-step timing is only `LIVE_INTEGRATION_ONLY` and is not this measure. |
| R6 | Limit axial defect-position error to ±10 mm. | Encoder scale, time alignment and camera-to-marker offset. | Repeated known-position trials in both travel directions. `position_mm` remains null. |
| R7 | Store type, size, confidence, evidence image, position, time and batch identifier with required calibration provenance. | `DetectionRecord`, SQLite, image store, calibration manifests and export. | Schema/file round-trip test, then calibrated record audit. Current generic calibration linkage and live image persistence are incomplete; physical fields remain null. |
| R8 | Operate for 30 min with confirmed-event record loss below 1%. | Resident service, SQLite transaction path, durable image store and health log. | Reconcile frozen expected event IDs to complete durable rows/images/exports using the Section 3.2 formula; report acquisition/processing frame drops separately. Not yet tested. |
| R9 | Enter a safe hold or fault state after camera, light, encoder or processor failure. | Pi health gate, STM32 watchdog and protected output. | Hardware fault injection with the final wiring. Software/network evidence exists, but safe I/O remains pending. |
| R10 | Store and serve only the enclosed filament-tunnel view, locally by default. | Shrouded optical head, release crop/mask and Pi-local database. | Audit every final-evidence frame and storage/access configuration for zero outside-tunnel/person content. Current development endpoints serve a full annotated frame rather than an ROI crop; R10 is not achieved (Australian Government, 2025; Office of the Australian Information Commissioner, 2026). |

## 5.2 Optical head and camera specification

The selected camera is the Raspberry Pi Global Shutter Camera. Its published specification is a Sony IMX296LQR-C sensor, 1.58 megapixels at up to 1456 × 1088 and 60 Hz, a 6.3 mm sensor diagonal, 3.45 µm square pixels, a CS-mount with a C-CS adapter supplied, and exposure times as low as 30 µs given enough light (Raspberry Pi Ltd, 2026b). Three things follow for this application. Global-shutter readout exposes the whole array at once, which removes the geometric distortion a rolling shutter puts on a moving target. A 30 µs exposure bounds motion blur directly: at the R4 upper speed of 5 m/min the filament advances 2.5 µm in that interval, which sits below one pixel pitch at any practical magnification, so blur stops being the limit and lighting becomes it. The 1456 × 1088 array also carries about 1.8 times the linear pixel count of the interim SVGA profile, so the same field of view resolves finer detail. None of that is a performance claim. The millimetres-per-pixel scale depends on the lens and the working distance and is fixed only at calibration, so the minimum detectable size under R2 stays `PENDING_REAL_MATERIAL`. A sensor that supports 60 Hz does not deliver R4 either: R4 is a system requirement covering Pi-side decode, inspection and storage, and none of that has been measured in this configuration.

The interim configuration uses the supplied OV3660. It can expose larger frames, but what the project needs is a stable operating point, not the biggest mode in the datasheet. SVGA 800 × 600 is fixed as the interim live profile; VGA 640 × 480 stays available as a manual recovery option, and XGA or anything larger falls outside the selected operating configuration. The active normalised ROI maps at SVGA to `(254, 47, 195, 527)`. Storing the ROI in normalised coordinates is deliberate: it survives the change of sensor and frame size at migration. Its position stays provisional until the fixture and the filament settle the true optical axis. OV3660 rolling-shutter readout, JPEG compression and wireless transport can each introduce motion or timing artefacts, so exposure duration, line speed and candidate persistence have to be tested together rather than one at a time (Espressif Systems, 2026; OmniVision Technologies, 2011). Those three artefact sources are the specific reason the global-shutter CSI configuration was selected, and all three leave the acquisition path on migration.

The proposed head uses a rigid camera bracket, repeatable filament guides, a matte background and an external shroud. Working distance, focus and exposure get locked once calibration is done. Switchable bright-field illumination is there to bring out colour or texture contrast; low-angle dark-field illumination is there to make surface relief cast shadow. Both modes are experimental variables, not evidence that any particular anomaly is detectable. Industrial anomaly datasets make the same point from the other direction: appearance changes and view geometry belong in the validation set, not hidden behind one convenient image condition (Carvalho et al., 2024; Heckler-Kram et al., 2026; Wang et al., 2024).

One camera sees one arc of a round object. It does not give full 360-degree coverage, and no amount of processing invents the hidden side. A mirror or a later multi-view arrangement gets evaluated only if blind-side misses turn out to dominate the Week 5+ evidence, and adding either would require a new optical calibration. The head will carry a scale target plus dark and white references that can be inserted without moving the camera. None of that supports a physical-resolution claim. Engineering roughness and internal voids stay outside this optical design.

## 5.3 Auxiliary photodiode chain

The SFH4555 emits across the filament path and the BPW46 returns a photocurrent that tracks the irradiance reaching it. The LM324 stage turns that current into a voltage and trims high-frequency noise before the STM32 converter samples it. At the proposal stage, the first transimpedance estimate is

\[
R_f=\frac{V_{span}}{I_{PD}},
\]

where \(I_{PD}\) is the photocurrent measured in the final geometry and \(V_{span}\) is the usable output swing. With feedback capacitance \(C_f\), the approximate low-pass corner is

\[
f_c=\frac{1}{2\pi R_f C_f}.
\]

None of \(R_f\), \(C_f\), the LED current or the decision thresholds can be frozen before the optical head is assembled. The provisional constraints are still explicit. M3 will pick the transimpedance gain so the measured path-state range occupies roughly 10–80% of the ADC input range without clipping, then choose \(C_f\) so the measured step response stays at least five times faster than the fastest material-presence transition while still attenuating the high-frequency noise actually observed. LED drive gets current-limited below the manufacturer's continuous rating and rechecked at the measured enclosure temperature. Dark, clear-path, normal-filament, blocked-path and misaligned-filament distributions set the threshold, with a recorded guard band, at G3. A valid auxiliary state can gate inspection or flag optical degradation. It cannot locate a scratch, classify contamination or estimate feature size.

The analogue channel terminates at the microcontroller rather than at the Raspberry Pi. The STM32 Nucleo-L432KC already carries the microcontroller's own converter (STMicroelectronics, 2026), so the supplied MCP3208 is held as a spare rather than wired into the released design; a separate SPI converter would add a second acquisition path for a single auxiliary channel. Routing the channel to the STM32 also places the presence and optical-health decision on the device that owns the physical output, which is the separation Section 5.1 already applies to the encoder. The Pi receives the resulting state in the existing Pi–STM32 frame, so the health gate in Figure 2 keeps the same input. M3 will confirm the converter's resolution, input range and available pins against the device datasheet before the interface is frozen. The conditioning stage must still be bounded. The LM324 is not a rail-to-rail device, so if it operates from the regulated 5 V analogue branch its output range and every normal and single-fault input condition must be checked. M3 will constrain the converter pin to the microcontroller's analogue input range through gain and bias design plus an input series resistor and a measured clamp/divider arrangement, and will measure the minimum, maximum and protection current under normal and single-fault conditions before the microcontroller is connected; component values remain a G2/G3 measurement decision. Raspberry Pi GPIO and SPI remain 3.3 V interfaces, and no 5 V analogue or digital signal may connect directly to either controller. Section 8 records the official component sources for these release constraints.

## 5.4 Raspberry Pi processing, provenance and storage

The planned Pi deployment keeps the source-independent Week 3 contracts rather than replacing them. `FramePacket` carries the image, frame number, acquisition and receipt times, camera source and connection state. A `DetectionRecord` carries a candidate label, pixel bounding box, pixel area, algorithm score, provisional grade and batch context. The SQLite schema holds `batches`, `detections`, `system_events` and `calibrations`, and the service now enables SQLite foreign-key enforcement, so a detection cannot reference a batch that was never opened. Those boundaries are what make a later algorithm change auditable, and they fit the edge-computing role described in current industrial vision work (Katsigiannis & Mykoniatis, 2024). The schema is not finished, though. It carries one generic `calibration_id`, and its calibration table records optical pixels/mm and an evidence path — not encoder counts/mm, not timestamp alignment, not the camera-to-marker offset. Before physical size or position can be traceable, the released design needs separate optical and encoder calibration records, or a hashed composite manifest that identifies both.

**Figure 2. Health-gated candidate-processing and evidence-record flow.**

```mermaid
flowchart TD
    FP["FramePacket"] --> HG{"Camera healthy and material present?"}
    HG -->|"No"| SE["System event; no candidate processing or action"]
    HG -->|"Yes"| ROI["Normalised ROI and baseline OpenCV processing"]
    ROI --> PC["Pixel-space candidate regions"]
    PC --> ET["Multi-frame event merge: planned for real material"]
    ET --> DR["DetectionRecord"]
    CAL["Versioned optical and encoder calibration records"] --> CG{"All required calibration IDs valid?"}
    CG -->|"Yes"| DR
    CG -->|"No"| NULL["Keep size_mm and position_mm null"]
    NULL --> DR
    DR --> DB["SQLite: batches, detections, system_events, calibrations"]
    DR --> EX["JSON, CSV and evidence images"]
    DB --> API["REST snapshot/events and WebSocket updates"]
    API --> UI["Operator GUI"]
```

Figure 2 shows where health, calibration and provenance step in to stop a pixel-space candidate from picking up physical meaning it has not earned.

The Windows development baseline uses a configurable threshold of 145, a minimum area of 120 px and an enabled material-presence gate (ENG5105 Project Team, 2026a, 2026i). These are prototype parameters, not settled ones. The gate currently expects a dark target through 80% of the ROI height, which keeps a nearby hand or a small background object from starting inspection, and it will need retuning once rPLA is in front of the camera. The one-slot `LatestFrameBuffer` and the 1 s `STALE`/2 s `DISCONNECTED` monitor started as `OFFLINE_FAULT_INJECTION_ONLY` primitives; the resident service now instantiates both. Acquisition and inspection run on separate threads. The reader publishes each frame into the one-slot buffer, a backlogged frame is discarded and counted, and the inspection thread judges health from the age of the newest frame it holds rather than from whether the last read returned inside its configured 3000 ms timeout. That distinction matters: a frame older than the configured stale window downgrades the service state even while reads keep succeeding, and three consecutive frames are required before inspection resumes. The `dropped_frames` field now reports the buffer's discard count instead of a constant zero, and every snapshot carries `frame_age_ms` beside its configured thresholds. All of this is development-host software evidence from threaded unit tests. It does not establish Pi deployment, backlog suppression under real network load, or the R4, R8 and R9 results, which still need the final fixture. Multi-frame merging turns repeated frame candidates into event candidates only once representative material exists.

The current model-level data rule is strict: without its generic `calibration_id`, `size_mm` and `position_mm` stay null. That safeguard is not the same thing as proven provenance. The resident live service leaves `image_path` and the calibration linkage null, and the current calibration table cannot identify the separate optical and encoder/offset evidence a position needs. Synthetic records carry `OFFLINE_SYNTHETIC_ONLY`; live camera candidates carry `LIVE_INTEGRATION_ONLY`. Neither supports a physical claim. Before R7 can pass, the release schema has to require the relevant calibration IDs or a composite-manifest hash, plus a durable evidence-image path.

## 5.5 STM32 supervision and safe I/O

The proposed STM32 firmware will count pulses from the 400-pulse/revolution encoder, timestamp position updates, sample the auxiliary optical channel, check the Pi heartbeat, switch lighting through a protected driver, and own the marker/reject/stop demonstrator output (STMicroelectronics, 2026). The selected encoder presents A and B channels as NPN open-collector outputs. Each channel is pulled up to the STM32 3.3 V logic supply through 10 kΩ and shares a ground with the encoder supply — never to the 4.8–24 V encoder rail. Input protection, low and high levels, electrical edges, and counting integrity at the highest test speed all get measured at G2/G3. None of these functions has been demonstrated on physical STM32 wiring yet. If quadrature decoding counts all four quadrature edges, the theoretical scale is 1600 counts/revolution. For measured effective wheel circumference \(C\),

\[
k_e=\frac{1600}{C}\;\text{counts/mm}, \qquad q_e=\frac{C}{1600}\;\text{mm/count}.
\]

No value is assigned to \(C\). Wheel slip, eccentricity, preload and the camera-to-marker offset all have to be measured, and encoder resolution on its own cannot justify R6. The selected encoder is specified as an NPN open-collector A/B device supplied with 10 kΩ resistors and a 4.8–24 V supply range. The proposed bench interface will power it from a confirmed regulated branch and pull each A/B collector up through 10 kΩ to the STM32's 3.3 V rail, with a common ground and measured input filtering and protection. Pulling up to 5 V, or to the encoder supply, is prohibited. G2 verifies high and low levels and rise time at the selected cable length before the 1600-count/revolution assumption is released. The first build does not exercise any of that. Pending real material, inspection is planned on stationary filament: the encoder is installed and its electrical interface verified at G2, while counts/mm calibration, the R6 axial position and travel-based event merging are deferred until the filament arrives and the transport is decided. This is a provisional configuration recorded in the decision log, not a requirement change.

**Figure 3. Proposed acquisition-health states and output-inhibition behaviour.**

```mermaid
stateDiagram-v2
    [*] --> CONNECTING
    CONNECTING --> HEALTHY: three consecutive valid frames
    HEALTHY --> STALE: no frame for 1 s
    STALE --> DISCONNECTED: no frame for 2 s
    DISCONNECTED --> RECONNECTING: reconnect requested
    RECONNECTING --> HEALTHY: three consecutive valid frames
    RECONNECTING --> DISCONNECTED: connection attempt fails
    HEALTHY --> HEALTHY: material gate false, wait without inspection
    note right of HEALTHY
      Output remains inhibited unless material,
      calibration, event and watchdog gates also pass.
    end note
    note right of STALE
      Candidate processing and automatic action are false.
    end note
    note right of DISCONNECTED
      STM32 holds the protected output safe.
    end note
```

Figure 3 defines what counts as a qualified recovery, and which states must keep candidate processing or physical output inhibited. The resident Windows service does not enforce the 1 s and 2 s transitions or the three-consecutive-frame recovery rule; it uses synchronous reads and a configured 3000 ms read timeout. The state timing in the figure is a design tested in offline components and still waiting to be ported and verified on the Pi. It is not evidence of live timeouts running in the resident service.

The released Pi service must not replay old frames. It will require three consecutive valid, age-bounded frames before processing resumes, and a Pi restart or a heartbeat loss will clear output permission. After a latched hardware fault, re-enabling any automatic demonstrator will take a manual acknowledgement. If the web interface fails while the STM32 is still alive, the operator loses visibility, but the proposed watchdog and output inhibition stay local to the control path. These are target behaviours, pending live-service integration and the final wiring tests.

## 5.6 Communications, API and user interface

Table 9 separates transport that is implemented from hardware interfaces that are only proposed. Table 10 then fixes the Windows development API behind the present GUI evidence.

**Table 9. Subsystem communications and integrity rules, covering the selected and interim acquisition chains.**

| Interface | Payload and present/planned mode | Integrity, timing and recovery rule |
|---|---|---|
| Global-shutter camera → Pi (selected) | CSI-2 ribbon carrying uncompressed frames at up to 1456 × 1088 (Raspberry Pi Ltd, 2026b); no wireless leg and no JPEG stage. | `PROPOSED_INTERFACE`: ribbon seating, CSI bandwidth and capture-stall behaviour become the acquisition fault classes and must be fault-injected at G5 before the migration is accepted. |
| OV3660/ESP32S3 → Pi (interim) | HTTP multipart MJPEG over controlled 2.4 GHz Wi-Fi; SVGA 800 × 600. Replaced by the CSI link on migration. | Resident service is the only direct MJPEG client. Read/open timeout and reconnect logic gate processing; rate is measured, not assumed. |
| Pi ↔ STM32 | Proposed USB serial baseline: 115200 bit/s, 8-N-1; framed monotonic sequence, millisecond timestamp, encoder count, material-presence state, health bitmask, lighting command and output request. | `PROPOSED_INTERFACE`: CRC-16 per frame and 10 Hz heartbeat; three invalid/missing heartbeats or more than 300 ms without a valid frame inhibits output. M5 freezes the framing/timing after G2 bench checks, and G5 verifies fault response. |
| Encoder → STM32 | Two-channel A/B NPN open-collector signal; 400 pulses per revolution per channel, each pulled up to the STM32 3.3 V rail through 10 kΩ. | Encoder supply and logic pull-up stay separate but share a common ground; pulling up to the 4.8–24 V encoder supply rail is prohibited. Quadrature decoding may be frozen only after measured logic levels, edges, direction and full-speed counts. |
| Optical channel → STM32 | Proposed conditioned analogue input sampled by the microcontroller's converter, timestamped and reported beside the encoder count in the existing Pi–STM32 frame; initial bench rate 200 samples/s per active channel. | `PROPOSED_INTERFACE`: for the shortest measured presence transition \(t_{min}\), require \(f_s\geq10/t_{min}\) so at least ten samples span it; stale/out-of-range values create an optical-health fault. M3 sets thresholds from the five-state distributions at G3. |
| STM32 → local LCD | I2C summary of system health and safe-output state. | Diagnostic only; it does not override the web/database record. |
| Pi → browser | REST and WebSocket over the local Ethernet/Wi-Fi network. | Local-by-default access; the UI must show disconnection and last update rather than silently freeze. |
| Future plant link | MQTT or Modbus TCP/RTU is an option, not part of the validated baseline. | Requires an interface-control revision, OT security review and separate acceptance (ISO/IEC/IEEE, 2023; Stouffer et al., 2023). |

The implemented Windows development service listens on port 8765 (ENG5105 Project Team, 2026e). Its current API contract is explicit:

**Table 10. Implemented development-service API contract.**

| Method and endpoint | Response or action | GUI use |
|---|---|---|
| `GET /api/health` | Acquisition, processing, gate and evidence state, including the development field `automatic_actions_allowed`. | Health banner and diagnostics; this field is not actuator authorisation. |
| `GET /api/snapshot` | Current summary plus candidate records. | Initial page state and resynchronisation. |
| `GET /api/events?limit=` | Bounded event history for the active batch. | Event table and export preparation. |
| `POST /api/events/delete` | Development-only hard deletion of selected database rows. It now writes a `DETECTION_RECORDS_DELETED` event naming the requested identifiers, but still records no operator identity, reason or tombstone. | Traceable clean-up only; disable before evidence release and replace with role-identified quarantine/tombstone handling. |
| `GET /api/frame.jpg` | Latest annotated JPEG, or 503 before a frame is available. | Single-frame view. |
| `GET /api/stream.mjpg` | Shared annotated MJPEG output. | Live view without another direct camera client. |
| `POST /api/control/reconnect` | Requests camera recovery. | Manual recovery control. |
| `WS /ws` | Pushes changed snapshots. | Low-delay health and event updates. |

These endpoints are Windows-host implementation evidence. Deployment and start-up persistence on the Raspberry Pi, the USB serial contract and physical STM32 I/O are all still plans. One name in the present service is actively misleading. `automatic_actions_allowed` is no more than a development readiness Boolean computed from `camera_state == HEALTHY` and the material-presence gate. It does not check calibration, event validation, STM32 heartbeat, fault latches or operator authorisation, and no actuator is connected to it. It must be renamed before release. The target interface should expose a separate `safe_output_authorized` that goes true only when frame data is not stale, optical and encoder calibration are valid, the event rule is validated, the encoder and lighting are healthy, the Pi–STM32 heartbeat and watchdog are live, the operator has explicitly enabled output, and no fault is latched. Until every G5 release condition passes — physical fault injection, a confirmed safe default level and owner sign-off — that value stays false and physical output stays inhibited. The hard-delete endpoint now writes an audit event naming what was removed, but an irreversible delete still contradicts the proposed append-only evidence governance and has no place in an evidence-release configuration. Before acceptance it should be disabled, or replaced by a controlled soft delete carrying identity, time, reason, retention policy and an append-only audit record. Existing evidence must never disappear without a trace.

The GUI should let an operator understand the whole chain at a glance: camera and material-gate health, evidence label, live ROI, candidate overlays, frame rate, post-decode-to-GUI latency, batch and calibration identifiers, Pi/STM32/encoder/lighting states, event history and export. Before calibration it shows pixel measurements. Physical size and position stay blank, and candidate status must never be dressed up as a validated quality grade. The local LCD carries only a small health summary, so that losing the browser does not look like losing the controller.

## 5.7 Power budget and protection

The proposal keeps computing separate from lighting and switched loads. Table 11 allocates the 5.1 V computing domain; Table 12 gives an all-in 12 V auxiliary-domain allocation that includes the marker. Both are team values for sizing and protection. They are not measured consumption, and they are not manufacturer-declared application loads (Monash University, 2026a, 2026c; Raspberry Pi Ltd, 2026a; STMicroelectronics, 2026). The Pi and STM32 figures bound the intended service and USB load; the auxiliary figures allocate the proposed camera, analogue, lighting, encoder and marker branches. M3 replaces every allocation with start-up and steady-state current evidence at G2, before any fuse or conductor selection is released.

**Table 11. Proposed 5.1 V Raspberry Pi-domain power allocation.**

| 5.1 V Raspberry Pi domain load | Normal | Peak |
|---|---:|---:|
| Raspberry Pi 4 | 7.50 W | 12.50 W |
| STM32 Nucleo via USB | 0.25 W | 0.50 W |
| **Domain total** | **7.75 W** | **13.00 W** |

A 5.1 V, 3 A supply provides \(P_{available}=5.1\times3=15.3\ \text{W}\). The allocated peak margin is

\[
M_{Pi}=\frac{15.3-13.0}{15.3}\times100=15.0\%.
\]

**Table 12. Proposed 12 V auxiliary-domain power allocation.**

| 12 V auxiliary-domain load | Normal | Peak | Path |
|---|---:|---:|---|
| ESP32S3 Sense + OV3660 | 1.50 W | 2.50 W | 12 V to regulated 5 V |
| IR/analogue/LCD electronics | 0.40 W | 0.80 W | Mixed regulated rails: LM324/auxiliary devices as confirmed; conditioned output clamped to the STM32 analogue input range |
| Controlled lighting | 8.00 W | 12.00 W | 12 V branch |
| Encoder | 0.50 W | 1.20 W | Rated branch after component confirmation |
| Marker/servo demonstrator | 0 W | 5.00 W | Protected switched branch; calculation treats 5.00 W as a 12 V-side allocation |

Assuming 85% conversion efficiency for the 5 V loads,

\[
P_{12V,normal}=\frac{1.50+0.40}{0.85}+8.00+0.50=10.74\ \text{W},
\]

\[
P_{12V,peak}=\frac{2.50+0.80}{0.85}+12.00+1.20+5.00=22.08\ \text{W}.
\]

A regulated 12 V, 5 A source supplies 60 W, leaving

\[
M_{12V}=\frac{60-22.08}{60}\times100=63.2\%.
\]

Peak allocation is not the final electrical design. The 22.08 W value assumes the marker's 5.00 W is already expressed at the 12 V source; if the selected device draws from a converted 5 V rail instead, its peak has to be divided by the measured converter efficiency and the total recalculated before G2. Week 5+ tests must capture start-up inrush, steady current, Pi undervoltage logs and regulator temperature before fuse, conductor and connector ratings are frozen. Every domain gets branch fusing, reverse-polarity protection and labelled isolation. Switched inductive loads need flyback suppression, lighting is switched by a rated transistor/MOSFET driver, and signal returns meet at a controlled ground point. The Pi supply must never source the marker or servo.

**Figure 4. Auxiliary power and protection domain, showing the branches the 12 V source feeds and where protection and switching sit.**

```mermaid
flowchart TB
    PS["12 V 5 A regulated supply"]
    PT["Branch fusing, reverse-polarity protection and labelled isolation"]
    BK["5 V 3 A buck converter"]
    DR["Logic-level MOSFET drivers"]
    PS --> PT
    PT --> BK
    PT --> DR
    PT -->|"12 V"| ENC["400 P/R encoder branch"]
    BK -->|"5 V"| ESP["XIAO ESP32S3 with OV3660"]
    BK -->|"5 V"| ANA["LM324 and auxiliary devices"]
    DR -->|"switched 12 V"| LT["Protected LED strip lighting branch"]
    DR -->|"switched 12 V"| MK["Protected marker or servo branch"]
    STM["STM32 output control"] --> DR
    PIS["Separate 5.1 V 3 A supply"] --> PI["Raspberry Pi 4"]
```

Figure 4 separates the computing supply from the auxiliary domain. No switched load draws from the Raspberry Pi rail, every 12 V branch passes the protection stage before it reaches a load, and both switched branches sit behind logic-level drivers the STM32 commands. The auxiliary analogue channel is referenced to the microcontroller's own supply rather than to the 12 V domain, which is what keeps the conditioned signal inside the input limits recorded in Section 5.3. Component values, fuse ratings and conductor sizes stay a G2 measurement decision.

## 5.8 Migration from the interim configuration to the selected concept

We chose the interim path so that migration would be a front-end replacement rather than a redesign. Everything from the frame contract downwards is shared: `src/week3/` holds source-independent contracts that no camera adapter may reach into, the acquisition adapter is injected through a `capture_factory`, and the inspection thread receives frames without knowing where they came from. That separation already exists in the current code, and it is the reason the selected concept can be adopted without reopening the requirement set, the supervision layer or the evidence schema.

Table 13 states what changes, what is preserved, and what evidence has to be re-established. The last column is the one that matters. Migration replaces the measurement instrument, so every value describing optical or timing performance dies with the change and has to be measured again on the new chain. No interim figure crosses over.

**Table 13. Migration from the interim OV3660 path to the selected global-shutter CSI path.**

| Layer | Change on migration | Preserved | Evidence status after migration |
|---|---|---|---|
| Camera and transport | Raspberry Pi Global Shutter Camera on CSI ribbon replaces OV3660 over 2.4 GHz MJPEG; the ESP32S3 leaves the acquisition role | Enclosure, mounting bracket, filament guides, matte background, lighting modes | All acquisition timing and image-quality evidence is void and must be re-recorded |
| Acquisition software | A CSI capture adapter replaces the MJPEG client behind the existing `capture_factory`; the one-slot latest-frame buffer and frame-age monitor are retained and re-tuned | `FramePacket` contract, inspection thread, health state machine, drop instrumentation | Threaded unit tests re-run with the new adapter injected; hardware-free test strategy unchanged |
| Optical calibration | New optical calibration for the new sensor, lens and working distance; a new `calibration_id` is issued | Normalised ROI definition, calibration record schema, provenance rules | Previous `calibration_id` is retired; `size_mm` and `position_mm` return to `null` until the new calibration is recorded |
| Processing, storage and interface | No change required | OpenCV baseline, `DetectionRecord`, SQLite schema, REST/WebSocket API, GUI, export | Contract tests re-run unchanged; schema evidence carries over because the schema does not change |
| Supervision and safe I/O | No change required | STM32 encoder, watchdog, heartbeat, lighting control, inhibited output, G5 release gate | Fault-injection evidence must be repeated on the migrated wiring before the G5 gate is re-cleared |
| Requirements | No change to R1-R10 targets | Requirement identifiers, verification routes, acceptance rules | R2, R3, R4, R5 and R6 results revert to `PENDING_REAL_MATERIAL` and are re-measured on the selected chain |

Three conditions apply before any Plan A result gets reported. The hardware must pass incoming inspection for issue, condition and lens compatibility, C-CS back-focus at the intended working distance included. A new versioned optical calibration must exist, because the pixel scale changes with the sensor and lens, and without it no millimetre value holds. The supervised fault tests behind the G5 safe-output release gate must be repeated, because removing the wireless leg changes the acquisition failure modes: Wi-Fi loss disappears as a fault class, while ribbon seating, CSI bandwidth and Pi-side capture stalls arrive as new ones. RSK-13 covers the case where delivery or calibration blocks the migration; the interim configuration then stays the delivered path, and the change is reported as not performed rather than assumed.

Removing the wireless leg narrows the risk register too, not just the throughput problem. RSK-01 loses its rolling-shutter and JPEG components, and RSK-03 loses its Wi-Fi latency and stale-buffer components. Migration alone closes neither risk. Multi-frame confirmation, frame-age monitoring and output inhibition all stay in force, and both entries have to be re-rated against measurements from the new chain rather than against the expectation that it performs better.

# 6. Current Integration Evidence and Limitations

Current work materially reduces integration risk. It also answers a different question from defect validation, and the two should not be confused. Every record below came off the interim OV3660 configuration, so none of it describes the selected global-shutter chain; Section 5.8 states which of these results migration invalidates. Table 14 records what happened under the documented conditions and, just as importantly, what cannot follow from it.

**Table 14. Current integration evidence, permitted inferences and claim boundaries.**

| Evidence and label | Exact recorded observation | Allowed inference | Does not establish |
|---|---|---|---|
| Week 4 camera-link record, `LIVE_INTEGRATION_ONLY` (ENG5105 Project Team, 2026h) | At 640 × 480, 792 frames arrived in 30.056 s, giving 26.35 FPS in the hardware integration test. | Physical camera identity, MJPEG connectivity and source-adapter operation. | Final SVGA throughput or any rPLA result. |
| Resolution and frame-rate record, `LIVE_INTEGRATION_ONLY` (ENG5105 Project Team, 2026f) | VGA recent window ≈10.48 FPS; SVGA windows 14.74, 15.60 and 13.96 FPS plus 10.77 FPS over a sustained 30 s test; XGA windows 9.72, 7.51 and 9.42 FPS. The displayed drop field was 0, but the resident counter was then initialised to zero and never incremented. SVGA 800 × 600 was selected. | An operating profile and exposed throughput constraint under the recorded no-filament condition. | Zero frame loss, R4, usable line speed, clarity or defect sensitivity; no raw per-frame rate trace is frozen. |
| Live-path brightness-step record, `LIVE_INTEGRATION_ONLY` (ENG5105 Project Team, 2026b, 2026d) | Ten reversible transitions gave 101.32 ms median, 222.99 ms P95, 87.12 ms minimum and 222.99 ms maximum. With only \(n=10\), the reported P95 equals the sample maximum and is a weak tail estimate. Brightness returned to 1; service state remained `HEALTHY`. | Camera-control request → OV3660 → Wi-Fi MJPEG → Python processing → local API JPEG response in that small integration sample. | Sensor-exposure-to-browser-paint latency, a stable production P95 or R5. |
| Live-path network-fault record, `LIVE_INTEGRATION_ONLY` (ENG5105 Project Team, 2026b, 2026c) | Scoped outbound blocking to camera `172.20.10.2` was recognised in 654.64 ms as `RECONNECTING`; detection and the development `automatic_actions_allowed` field were `false`; a 4 s hold added 0 frames; recovery to `HEALTHY` took 5689.35 ms; the firewall rule was removed. | The tested Windows path gated candidate processing and recovered from this injected fault. | Actuator authorisation, final Pi/Wi-Fi reliability, STM32 wiring or certified safe action. |
| Week 3 contract record, `OFFLINE_SYNTHETIC_ONLY` (ENG5105 Project Team, 2026g) | `FramePacket` → `BaselineVisionProcessor` → `DetectionRecord` → SQLite/JSON/CSV/annotated frames; physical fields are rejected without `calibration_id`. | Data-flow, provenance and null-field safeguards operate on repeatable synthetic inputs. | Classification of real bubbles, pits, scratches, cracks, contamination or inclusions. |
| Week 4 policy-primitive record, `OFFLINE_FAULT_INJECTION_ONLY` (ENG5105 Project Team, 2026h) | In the offline harness, buffer capacity is 1; no frame for 1 s produces `STALE`; no frame for 2 s produces `DISCONNECTED`; three consecutive valid frames are required after reconnection. The resident service now instantiates the same primitives behind a separate acquisition thread. | The one-slot buffer and 1 s/2 s state-policy primitives pass offline fault injection, and their service integration passes threaded unit tests on the development host. | Live backlog suppression under network load, live timeout compliance, full hardware safe-output behaviour or 30 min reliability. |

R4 is the clearest open design gap: 20 processed frames/s is proposed, while the sustained SVGA observation is 10.77 FPS. For line speed \(v\) and processed rate \(f\), axial travel between frames is \(\Delta x=v/f\). At 1, 3 and 5 m/min the observed rate gives 1.55, 4.64 and 7.74 mm/frame, and 20 FPS would give 0.83, 2.50 and 4.17 mm/frame. Those values describe axial sampling spacing, not detectable feature size. Whether a feature can be observed at all still comes down to frame overlap, field of view, blur and event tracking.

Timing needs the same restraint. A 500 ms R5 alarm window corresponds to 8.33 mm of travel at 1 m/min and 41.67 mm at 5 m/min. The recorded 222.99 ms P95 maps mathematically to 18.58 mm at 5 m/min, but its measurement path has no sensor-exposure timestamp and no browser-paint completion. It also rests on ten transitions, where the reported P95 simply equals the maximum. We therefore do not use it as physical alarm-delay evidence, or as a stable estimate of the tail.

# 7. Calibration and Validation Strategy

Physical rPLA and fixture materials are expected on Thursday in Week 5, so application performance cannot be tested against the intended target yet. Until receipt and condition are confirmed, every application-performance item stays `PENDING_REAL_MATERIAL`. The method follows an evidence ladder: freeze the geometry, calibrate the measurement channels, tune only on separated development material, then evaluate once on independent units. Randomly splitting adjacent video frames would leak nearly identical appearances into both training and test sets and inflate the result (Figueiredo & Mendes, 2024; Kapoor & Narayanan, 2023).

## 7.1 Week 5+ calibration sequence

On receipt, the team will identify each spool and segment and photograph the test fixture before touching any threshold. The camera mount, guides, working distance, focus, exposure, SVGA profile, ROI, background and bright-/dark-field settings are then frozen as one optical configuration. Dark and white references reveal saturation, drift and uneven illumination. The planned immutable configuration and calibration manifest records provenance, the relative path to raw data, measurement units, valid range, uncertainty, software version and file hash, and a configuration hash plus an optical calibration identifier links every later record to those choices.

Optical scale comes next. If a traceable reference of length \(L_{ref}\) spans \(P_{ref}\) pixels in the filament plane,

\[
s=\frac{L_{ref}}{P_{ref}}\;\text{mm/pixel}, \qquad L_{candidate}=sP_{candidate}.
\]

The optical-scale calibration is repeated at several positions across the ROI, and again after remounting. Encoder calibration uses measured travel in both directions to estimate counts/mm, slip and repeatability, and it also establishes Pi–STM32 timestamp alignment and the camera-to-marker offset. Only records carrying valid optical and encoder calibration identifiers — or a hashed composite manifest that resolves to both — may populate `size_mm` or `position_mm`. The current single generic `calibration_id` field does not carry that provenance, so the schema has to be extended before any physical value is released.

The auxiliary channel is calibrated last, inside the frozen head, because its current depends on the same geometry. We measure the five path states defined in Section 5.3, choose a gain that does not saturate, set the low-pass corner from the noise and dynamics actually observed, and keep the raw converter values beside the health decision. It stays a presence and health channel even if its signal happens to correlate with a visible anomaly.

## 7.2 Dataset and event-level evaluation

Ground truth attaches to physical sampling units, not to isolated frames. Normal segments and deliberately characterised anomalous segments are labelled with class, axial location, physical extent where it can be measured, spool and batch, optical configuration, and the annotator's decision. Spools, segments or complete events are assigned to development and independent test partitions before any tuning. Difficult but foreseeable changes — material colour, surface gloss, speed, illumination level, camera remounting — belong in the test matrix; real-world anomaly benchmarks warn against presenting one narrow acquisition domain as general performance (Carvalho et al., 2024; Heckler-Kram et al., 2026; Wang et al., 2024).

Repeated boxes from the same moving region will be merged into one event using time and calibrated encoder overlap. For event counts \(TP\), \(FP\) and \(FN\),

\[
Precision=\frac{TP}{TP+FP},\qquad Recall=\frac{TP}{TP+FN},\qquad
F1=\frac{2\,Precision\,Recall}{Precision+Recall}.
\]

The report pairs these with false alarms per metre, misses by class and condition, and uncertainty or confidence intervals. Sample counts are set after a pilot and stakeholder review; naming a large sample-size target now would not make the future estimate any more reliable. The minimum independent event count for every accepted class is frozen before the untouched test all the same. We keep every failed case, and we freeze the independent test set before the final run.

## 7.3 Verification gates and decision rules

Table 15 turns R1–R10 into configuration-specific acceptance decisions, each with an explicit response to failure.

**Table 15. Planned verification gates and acceptance decisions.**

| Gate | Method and acceptance decision |
|---|---|
| Optical visibility: R1–R2 | Use calibrated references and independently labelled physical events at the fixed SVGA geometry. Freeze the class-specific primary dimensions defined in Section 3.2. Accept only if at least three agreed visible classes and the proposed 0.20 mm primary-dimension target are demonstrated under declared conditions; otherwise revise optics or the requirement before the untouched test. |
| Classification: R3 | Freeze the minimum independent event count after the pilot, then score merged events once on the untouched spool/segment/event partition. For every accepted R1 class meeting R2, both event-level precision and recall must reach 90%; report per-class counts and confidence intervals, and do not let F1 or macro/micro aggregation conceal one failing class. |
| Throughput and speed: R4 | Measure received, decoded, processed and accepted-frame rates separately at 0–5 m/min, with jitter, stalls and reconnects. If SVGA remains below 20 FPS, optimise capture/ROI/algorithm or formally revise R4 with stakeholder approval. The 10.77 FPS result cannot be relabelled as compliance. |
| Alarm path: R5 | Freeze an ROI entry line and event-confirmation rule. Synchronously film a marked defect crossing that line, a millisecond reference and the GUI/physical indication; measure from the first reference-video crossing frame to visible alarm assertion, including confirmation, processing and communications. Compute the sensor-to-GUI and sensor-to-output distributions separately and retain the raw video with per-trial results. P95 must be within 500 ms on the predeclared test set. The present n = 10 brightness-control-path test does not count towards R5 acceptance. |
| Position: R6 | Place references at known axial positions, run forward and reverse trials across speeds, and include wheel slip plus camera-to-marker offset. Accept only if absolute error remains within ±10 mm under the declared test range. |
| Records and endurance: R7–R8 | Freeze expected confirmed-event IDs before a 30 min run. A complete durable record requires its database row, required evidence image, batch/time fields and applicable optical/encoder provenance. Compute loss as \((N_{expected}-N_{complete})/N_{expected}\), require it below 1%, audit for orphan/duplicate records, and report source-frame and processing drops separately. `dropped_frames` is now counted by the one-slot buffer, but it must not replace this item-by-item reconciliation. |
| Fault safety and safe-output release: R9 | Disconnect camera, block/attenuate lighting, interrupt encoder and serial messages, stop the Pi service, and exercise watchdog timeout on real wiring. Every case must inhibit physical output and create a timestamped fault; recovery requires valid health and acknowledgement where latched. Any failure blocks G5 and keeps automatic output inhibited. |
| Privacy and enclosure: R10 | Inspect every stored and served final-evidence frame, the full field of view, enclosure and local storage/access configuration. Accept zero frames containing a person or pixels outside the enclosed filament tunnel; external publication remains disabled by default (Australian Government, 2025; Office of the Australian Information Commissioner, 2026). The current full-frame development preview cannot satisfy this gate. |

Acceptance is configuration-specific. A change to camera position, lens or focus, exposure, illumination geometry, ROI, encoder wheel, event logic or model invalidates the affected calibration and triggers regression tests under the project lifecycle record (ISO/IEC/IEEE, 2023). We release a physical claim only when its requirement, optical and encoder provenance, independent dataset, stable evidence-record identifier, verified SHA-256 hash, result and limitation are all traceable. Until then the system is a well-instrumented candidate detector with bounded integration evidence — not a validated rPLA quality monitor.

# 8. Environmental, Safety, Ethical and Governance Implications, including Procurement

A recycled feedstock does not make the monitor environmentally beneficial by default. Earlier warning may avoid further processing or use of visibly non-conforming filament, which supports the intent of Sustainable Development Goal 12 (United Nations Department of Economic and Social Affairs, 2026). The camera, Raspberry Pi, lighting and network all consume energy, though; added electronics carry embodied impacts, and a poorly tuned detector can create avoidable rejects. No life-cycle assessment has been completed. Energy and reject observations are reported separately, and we will not claim a net benefit without a defined ISO 14040-compatible comparison (International Organization for Standardization, 2006). Reusing university hardware and choosing repairable fixture parts are design choices, not proof of environmental superiority.

Responsible operation means keeping uncertain measurements out of automatic quality decisions. A stale frame, a missing heartbeat, an unhealthy camera, absent calibration or an invalid encoder state all inhibit marking, rejection and stop requests. The proposed STM32 watchdog provides independent supervision. Fuses, reverse-polarity protection, local decoupling and appropriate flyback suppression address the electrical hazards. Moving guides and the marker need guarding, low-energy commissioning and an accessible independent stop. These measures are informed by ISO 13849-1 (International Organization for Standardization, 2023), but the prototype is not safety-certified and must not be presented as an industrial safety-related control system.

The camera creates a different obligation. The release configuration views an enclosed filament region, crops or masks locally to the tunnel, and saves event evidence rather than continuous video. The current development endpoints still serve a full annotated frame with an ROI overlay, so they do not satisfy R10. Access, retention and deletion rules have to be agreed before data collection, with laboratory notice and controlled export; OAIC guidance and the Privacy Act give the context (Australian Government, 2025; Office of the Australian Information Commissioner, 2026), though this proposal makes no legal-compliance finding. Any frame containing a person is quarantined from the defect dataset pending review.

Configuration governance is what separates a convincing demonstration from reproducible evidence. We version camera settings, ROI, software, calibration files, requirement status and protocol as one baseline. A reported result needs its evidence label, its conditions and its configuration. `position_mm` and `size_mm` stay null until valid optical and encoder calibration provenance exists, and spool, batch or event-group partitions are fixed before tuning. An acceptance evidence package must assign a stable evidence-record identifier and store a SHA-256 for raw data, logs, the database, images and video, test manifests and scripts. Consultation outcomes, requirement changes, failed tests and waivers enter a decision log that never assumes stakeholder approval, applying the traceability intent of ISO/IEC/IEEE 15288 (ISO/IEC/IEEE, 2023) and OT security's separation of operational, network and human controls (Stouffer et al., 2023). The current `/api/events/delete` route is a development-only hard deletion; it now writes an audit event naming the removed identifiers, but it still lacks authentication, a deletion reason and tombstones, so it must be disabled before evidence release. Deletion and export tests belong to the R10 audit. Released evidence will use role-identified quarantine/tombstone records with reason, time and operator identity; corrections will be appended rather than silently substituted, and no existing evidence chain may be erased.

Procurement uses the same discipline. On 15 August 2026, the encoder page displayed A$41.30, zero local stock, “available with a lead time,” and an expected dispatch window of 24–27 August (Core Electronics, 2026a). That dated supplier-page snapshot is a schedule risk, not proof of delivery; fixture, auxiliary power and marker figures stay planning allowances. Plan A listings showed A$92.55 for the camera and A$43.60 for its lens, with the camera out of stock (Core Electronics, 2026b, 2026c). The approved purchase still needs a fresh stock, compatibility, delivered-cost and delivered-lead-time check before the order goes in.

Electrical release uses official component limits rather than the equipment-list shorthand. Raspberry Pi documents its GPIO and alternate-function interfaces as 3.3 V (Raspberry Pi Ltd, 2026c); Microchip specifies the supplied MCP3208's operation, SPI and \(V_{REF}\)-bounded analogue input, which is the comparison behind using the microcontroller's own converter instead (Microchip Technology, 2008); and the LM324 data sheet establishes the supply and non-rail-to-rail output behaviour that must be allowed for in the conditioning stage (Texas Instruments, 2025). These sources support the Section 5.3 interface constraints. They do not verify the proposed wiring or component values.

# 9. Bill of Materials

Only a subset of the present cost numbers is supplier-verified. Table 16 therefore separates university-supplied equipment, verified supplier prices and team planning allowances. All amounts are Australian dollars; supplier figures were accessed on 15 August 2026 and include GST unless the listing indicates otherwise. Shipping is excluded. Physical issue, condition and compatibility of supplied parts still require an incoming check (Monash University, 2026c).

**Table 16. Plan B bill of materials and additional-procurement envelope.**

| Status | Item or group | Qty. | Plan B purpose | Cost basis | Cost charged |
|---|---|---:|---|---|---:|
| University supplied | Raspberry Pi 4 4 GB, power supply and 32 GB SD card | 1 set | OpenCV service, API/WebSocket, SQLite and GUI (Raspberry Pi Ltd, 2026a) | Supplied; condition to be checked | A$0 |
| University supplied | STM32 Nucleo-L432KC | 1 | Encoder, heartbeat, lighting and inhibited output interface (STMicroelectronics, 2026) | Supplied; condition to be checked | A$0 |
| University supplied | XIAO ESP32S3 Sense with OV3660 | 1 | SVGA MJPEG acquisition node (Espressif Systems, 2026; OmniVision Technologies, 2011; Seeed Studio, 2026) | Supplied; condition to be checked | A$0 |
| University supplied | SFH4555, BPW46 and LM324N, with the MCP3208 held as a spare | 1 channel/set | Filament-presence and optical-head health channel sampled by the STM32 | Supplied; final component values pending measurement | A$0 |
| University supplied | I2C LCD, LEDs, potentiometers, resistors, breadboard, protoboard, wire and headers | As issued | Local status, conditioning and prototype assembly | Supplied; quantity/condition to be checked | A$0 |
| Verified purchase | Incremental photoelectric rotary encoder, 400 P/R | 1 | Length-position measurement | Supplier page: zero local stock, available with lead time, expected dispatch 24–27 Aug. (Core Electronics, 2026a) | A$41.30 |
| Existing equipment | LED strip lighting set | 1 set | Controlled bright-field and low-angle dark-field illumination | Already purchased and held; no further procurement | A$0 |
| Planning allowance | Enclosed 12 V DC supply with screw terminals, 5 V conversion, MOSFET drivers, fuses, connectors and protection | 1 set | Separate auxiliary power and protected switching | Team range for an Australian-sourced set; ratings and quotation provisional | A$80–A$120 |
| Planning allowance | Mirrors, enclosure, brackets and guides | 1 set | Enclosed optical geometry and filament control | Team range; dimensions pending receipt | A$30–A$70 |
| Planning allowance | Marker/servo demonstrator | 1 | Position-based output demonstration | Team range; purchased with the rest of the build, with its physical output released only after G5 and an authorised validated event rule | A$10–A$25 |
| **Plan B additional-procurement envelope** |  |  | Camera/compute supplied; lighting already purchased; encoder, power/protection, fixture and marker all required | **One verified price plus three allowances** | **A$161.30–A$256.30** |

Plan A is the selected concept and an approved purchase. Its IMX296 global-shutter camera is technically suited to rapid-motion machine-vision imaging and requires a suitable C/CS-mount lens (Raspberry Pi Ltd, 2026b). Neither item is part of the interim build that produced the evidence in this report, and neither is yet in hand; Table 17 keeps them separate so the interim and selected budgets stay auditable.

**Table 17. Approved Plan A imaging procurement for the selected concept.**

| Approved Plan A item | Qty. | Evidence on 15 Aug. 2026 | Verified price |
|---|---:|---|---:|
| Raspberry Pi Global Shutter Camera, CE09593 | 1 | Supplier listing; out of stock (Core Electronics, 2026b) | A$92.55 |
| Raspberry Pi 6 mm CS-mount lens, CE06937 | 1 | Supplier listing; in stock (Core Electronics, 2026c) | A$43.60 |
| **Plan-A-only imaging subtotal** |  | **Shipping excluded** | **A$136.15** |

Adding that concept-specific subtotal to the common additional-procurement envelope gives a Plan A total of **A$297.45–A$392.45 before shipping**. These are not quotations or purchase orders. Shared Raspberry Pi, STM32, power, fixture, encoder and marker needs are counted once, so the comparison neither hides common costs nor charges them against Plan A twice. Before commitment, every charged item requires a fresh availability, compatibility, delivered-cost and delivered-lead-time record; the present Plan B evidence does not establish delivery timing.

## 9.1 Purpose and intended use of each procured item

Tables 16 and 17 record what each item costs and where that figure came from. This section records what each item is for and how the build will use it, which at this stage matters more than the price. Nothing below is a measured or calibrated value. Every quantity that governs performance — gains, thresholds, counts per unit length, working distance, drive currents, fuse ratings — is fixed later under the Section 7 calibration sequence, and none of it is claimed now.

**Incremental rotary encoder, 400 P/R.** A camera frame shows where a candidate sits inside an image; it cannot show where that candidate sits along the filament. The encoder supplies that second coordinate. It is coupled so that it turns with filament travel, the STM32 counts its A/B quadrature edges, and every count is timestamped so a frame can be matched to a travel figure. Four functions depend on it. R6 asks for an axial defect position, which only becomes meaningful once travel is measured, and `position_mm` stays null until it is. Event merging needs it as well, because one physical defect crosses the region of interest over several consecutive frames, and travel is what separates one defect seen repeatedly from several distinct defects. The marker sits downstream of the camera, so acting on a defect means knowing when that defect reaches the marker, which is again a travel measurement rather than a timing guess. The encoder doubles as a liveness signal: if the line is meant to be running and the count stops changing, the STM32 treats that as a fault and withholds output. The mounting arrangement, the drive that moves the filament, and the calibration that converts counts to length are all Section 7 work, which is why Section 5.5 deliberately leaves the effective wheel circumference unassigned. The encoder's purpose rests on the material-motion premise labelled `TEAM_INFERENCE` in Section 1.2. For the first build we have provisionally set that premise aside and planned static inspection, so the encoder is procured, wired and interface-verified while its travel role stays dormant until real material shows how the filament moves.

**LED strip lighting set.** Surface defects on a translucent cylinder are visible or invisible depending almost entirely on how they are lit, and the project brief names lighting control as a design challenge for this quality parameter. The strip is the controllable source that makes illumination a design variable rather than whatever the room happens to provide. It is mounted inside the enclosed head in two roles: bright-field, aimed to bring out colour and texture contrast, and low-angle dark-field, aimed across the surface so that relief casts shadow. The STM32 switches it through a protected driver, so illumination state is recorded alongside every frame and loss of lighting becomes a detectable fault rather than a silent change in image appearance. Geometry, angle, drive current and which mode suits which defect family are experimental questions for Section 7. The strip exists so that those questions can be asked at all.

**Enclosed 12 V supply with screw terminals, 5 V conversion, MOSFET drivers, fuses, connectors and protection.** This is the auxiliary power domain drawn in Figure 4, and it exists to keep switched loads away from the computing supply. The enclosed screw-terminal form was chosen over a barrel-jack unit because the branches fan out to several loads and each needs a secure, inspectable termination rather than a shared adapter. The 12 V rail feeds the lighting, the encoder and the marker branch. The buck stage derives the 5 V that the acquisition node and the analogue devices need. The MOSFET drivers are what let the STM32 switch the lighting and marker branches without either load touching a controller pin. The fuses, reverse-polarity protection and labelled isolation are what make the assembly safe to work on and safe to leave powered. Ratings, fuse values and conductor sizes remain G2 measurement decisions.

**Mirrors, enclosure, brackets and guides.** These make the optical measurement repeatable. The enclosure shrouds the head so that ambient light does not enter the frame and so that stored images contain only the filament tunnel, which is what R10 asks for. The brackets hold the camera rigidly, because a working distance that shifts invalidates the optical calibration it was measured at. The guides hold the filament on a repeatable path through the field of view, since a filament free to wander in depth defeats a locked focus. The mirrors are held against the circumferential-coverage question: one camera sees one arc of a round object, and if later evidence shows that blind-side misses dominate, a mirror arrangement is the first thing to try. Adding one would require a fresh optical calibration, so it is deliberately a later option rather than part of the initial head.

**Marker/servo demonstrator.** This is the project's physical output, and it is what separates a detector from a monitoring system that can act. When an event is confirmed and every authorisation condition holds, the STM32 drives the marker to tag the affected length of filament so that the defect can be found again after the run. It is also the test object for the whole safety argument: fault injection under R9 means something precisely because a real actuator exists that must stay inhibited when heartbeat, calibration, encoder or lighting health is lost. Its physical output stays disabled until the G5 release gate passes.

**Global-shutter camera and C/CS-mount lens.** These replace the interim acquisition front end. The camera exposes the whole sensor array at once, which is the property that matters when the subject is moving, and it reaches the Raspberry Pi over a ribbon cable instead of the wireless link the interim path depends on. The lens is a separate purchase because the camera ships without fixed optics: the mount is what lets working distance and field of view be chosen for the filament tunnel rather than accepted from a module. Section 5.2 records the reasoning behind the choice, and Section 5.8 records what has to be re-established after the swap, since every acquisition-timing and image-quality result recorded so far belongs to the interim configuration and does not carry across.

# 10. Project Delivery Plan and Team Responsibilities

The delivery strategy runs on stage gates with a V-model structure. Needs become proposed requirements, interfaces, hazards and test definitions; implementation is followed by unit checks, subsystem integration, calibrated system tests, and independent validation against the matching requirement IDs. A gate does not pass because time has moved on. It passes when the evidence named for that stage has been created, reviewed and linked to its owner.

The evidence status changes on **Thursday 27 August 2026 (Week 5)**. Nothing before that date involves physical rPLA or fixture-material testing. Earlier work is limited to design, procurement preparation, software and synthetic tests, and bounded non-rPLA live integration. If material turns up late, incomplete, damaged or unsafe, the physical milestones move with it; synthetic results cannot cover the gap. Table 18 puts that dependency in the open. It is a release gate, not a schedule assumption we are hiding.

**Table 18. Stage-gated delivery schedule and evidence decisions.**

| Stage and timing | Planned work | Gate output and decision rule |
|---|---|---|
| S0: baseline, through Wed. 26 Aug. | Freeze requirements, interfaces, risks, fixture drawings and protocols; retain synthetic/live-integration labels | G0: owner-reviewed versioned baseline; no physical-performance release |
| G1: material gate, Thu. 27 Aug. | Record receipt, quantity, condition, dimensions, traceability and hazards | Pass releases physical work; failure reschedules it and reviews scope |
| S1: safe shakedown, after G1 | Assemble fixture; check guarding, power, communications and inhibited outputs at low energy | G2: completed safety checklist, stable acquisition, no uncontrolled output |
| S2: calibration, Weeks 6–7 | Lock optics; establish scale, counts/mm, camera-marker offset and references | G3: versioned IDs; invalid calibration keeps millimetre fields null |
| S3: acquisition, Weeks 7–8 | Collect labelled events across planned speeds/optical challenges; audit labels and partitions | G4: traceable ground truth and independent groups before tuning freeze |
| S4: robustness, Weeks 8–9 | Integrate subsystems; inject supervised network, power and sensor faults | **G5 safe-output release gate:** every R9 case inhibits physical output and records a timestamped fault; any failure or unresolved high risk keeps output inhibited |
| S5: validation, Week 10, after G5 | Evaluate event metrics, false alarms/m, location, throughput, latency and record loss on held-out groups | Accept, optimise, narrow the envelope or revise a requirement; report failures. Automatic output still requires an authorised validated event rule and all live health/calibration gates |
| S6: release, Weeks 11–12 | Freeze configuration, assemble evidence and peer-review claims | Register links each accepted claim to its requirement ID, configuration, stable evidence-record identifier and SHA-256, test and owner |
| SA: migration to the selected concept, on delivery | Inspect the camera and lens on arrival; fit the CSI front end behind the existing capture contract, re-calibrate, and repeat the S2–S5 protocol on the selected optical chain | GA: migration accepted only after incoming inspection, a new versioned calibration and repeated G5 fault tests. No Plan A result may be reported before its own calibration exists, and interim figures are never carried across |

This sequence puts the throughput gap on the table. The recorded SVGA integration test observed 10.77 FPS under the `LIVE_INTEGRATION_ONLY` evidence state (ENG5105 Project Team, 2026f), below the proposed 20 FPS. The independent-validation gate therefore demands one of three things: optimisation, a narrower speed and field-of-view envelope, or a documented requirement change. A retrospective claim of compliance is not on that list. Stage SA re-measures the same throughput on the selected optical chain after migration, since CSI transport takes the Wi-Fi and MJPEG legs out of the path. We assume no improvement in advance. Any figure for the selected chain comes from measurements taken after its own calibration, and the interim result never gets restated as a Plan A result.

Table 19 maps each role identifier to the member who holds it; the identifiers are reused elsewhere in this report to keep the ownership columns compact. The planned workload shares in Table 19 sum to 100% and exist to guide balancing. They do not determine individual marks.

**Table 19. Proposed team responsibilities, workload shares and contribution evidence.**

| Role | Share | Primary accountability | Fixed support and review | Required contribution evidence |
|---|---:|---|---|---|
| M1 — Letu Ma, systems/project | 17% | Requirements, stakeholder protocol, architecture, schedule, interfaces, risk and integration | M4 on alarms/acceptance; all module owners | Decision log, baseline and requirement-status records |
| M2 — Tingyu Zheng, optics/camera | 16% | Camera, lighting, enclosure, coverage, image quality and calibration | M4 images/ROI; M6 optical repeats | Drawings, settings, calibration and image records |
| M3 — Zhiqian Wang, sensing/power | 16% | Photodiode/ADC, power, protection and electrical inspection | M5 wiring/faults; M4 health logs | Schematics, calculations, inspections and logs |
| M4 — Xinyang Wu, vision/UI/data | 18% | OpenCV, GUI, database, tracking, evaluation and analysis | M2 imaging; M6 independent labels/tests | Code, schema, test output and reproducible analysis |
| M5 — Niewei Fan, embedded/comms | 17% | STM32, encoder, timing, watchdog, communications and safe output | M3 power; M6 mechanical/output tests | Firmware, interface traces and fault/position records |
| M6 — Haowei Ding, validation/mechanical/quality | 16% | Rig, ground truth, group split, validation, uncertainty and safety review | M4 metrics; M5 alignment/repeatability | Protocols, label audit, held-out results and review |

Integration stays shared. Every work item names an owner, a reviewer, an internal date and an evidence output. Any interface change takes a version increment, an owner review and a recorded impact check before it joins the baseline. Released calibration and test data are read-only: corrections get appended rather than substituted, and the development hard-delete route is excluded from the release configuration. We will run a weekly integration build and raise the cadence from G3 through the independent-validation gate, which keeps hand-offs visible without letting M1 or M4 become the default owner of whatever is unfinished.

# 11. Risk Register

A risk entry is only useful if the team can see it coming. Table 20 therefore pairs each proposal-stage risk with an observable trigger, an owner, a control and a rating. Ratings are read off the discipline brief's matrix: a probability drawn from Certain, Likely, Possible, Unlikely, Rare and Eliminated, and a harm severity drawn from Negligible, Marginal, Critical and Catastrophic, which together give Low, Medium, High or Very high. Every cell states the pair and the rating it produces, so the judgement can be checked instead of taken on trust. The probabilities are qualitative engineering estimates, not measured frequencies. No row is rated Eliminated, because no hazard has been physically removed yet. Residual ratings assume the listed controls are implemented and tested; they do not mean the hazard has gone away.

**Table 20. Proposal-stage risk register rated on the probability × harm-severity matrix.**

| ID | Risk and consequence | Initial probability × severity → rating | Observable trigger | Owner | Planned control and contingency | Residual probability × severity → rating |
|---|---|---|---|---|---|---|
| RSK-01 | Rolling-shutter, MJPEG or motion artefacts resemble or hide defects | Likely × Critical → High | Candidate rate changes sharply with speed/JPEG setting; edge shape shifts between frames | M2/M4 | Lock exposure and geometry, test settings by speed, use multi-frame confirmation, retain raw event evidence; narrow operating envelope if needed | Unlikely × Critical → Medium |
| RSK-02 | Glare or incomplete angular coverage causes false alarms or missed surfaces | Likely × Critical → High | Saturated ROI, unstable background histogram or repeatable blind sector | M2 | Enclosed bright-/dark-field lighting, matte background, mirrors only after measured coverage test; report uncovered angles | Unlikely × Critical → Medium |
| RSK-03 | Wi-Fi loss, latency or stale buffering corrupts online decisions (interim chain; narrowed by migration) | Likely × Critical → High | Frame age exceeds threshold, health endpoint fails or backlog grows | M5/M4 | The one-slot buffer, age/state monitor and drop instrumentation now sit in the resident service and pass threaded unit tests; **still proposed:** Pi deployment, a controlled 2.4 GHz network and STM32-held output inhibition on real wiring. No live guarantee is claimed yet | Unlikely × Critical → Medium |
| RSK-04 | Week 5 materials are late, incomplete or unsuitable | Possible × Catastrophic → Very high | Receipt gate fails on 27 Aug. or fixture dimensions conflict | M1/M6 | Inspect at G1, keep pre-gate work non-physical, re-sequence software/documentation, escalate scope and dates without fabricating tests | Possible × Critical → High |
| RSK-05 | Too few representative defects produce weak or biased validation | Likely × Catastrophic → Very high | Required classes/groups are absent or labels cannot be independently checked | M6/M4 | Predefine sample/label protocol, retain interpretable OpenCV baseline, report class coverage and narrow claims; seek further material through approved channels | Possible × Critical → High |
| RSK-06 | Adjacent-frame or event leakage inflates performance | Possible × Critical → High | Frames from one spool, batch or event appear in tuning and test sets | M6 | Freeze group-level partitions before tuning, store provenance, run a partition audit and reject contaminated evaluation | Rare × Critical → Medium |
| RSK-07 | Calibration drift makes size or position values invalid | Likely × Critical → High | Focus, working distance, wheel geometry or configuration hash changes; reference check fails | M2/M5 | Bind provenance-verified optical and encoder calibration IDs to records, perform reference checks, invalidate physical fields and recalibrate after change | Unlikely × Critical → Medium |
| RSK-08 | Power noise, undervoltage, inductive switching or a 5 V analogue output resets, damages or drives unsafe output from the controllers | Possible × Catastrophic → Very high | Pi undervoltage/reset log, rail sag, conditioned analogue input outside the microcontroller's range, MCU reset or output pulse during switching | M3/M5 | Separate power domains, clamp and limit the LM324 output to the STM32 analogue input range, fuses, decoupling, flyback suppression, measured inrush/steady-state/fault tests and watchdog-safe defaults | Unlikely × Catastrophic → High |
| RSK-09 | Guides or marker create pinch, entanglement or unexpected-motion hazards | Possible × Catastrophic → Very high | Guard open, alignment jam, watchdog loss or output occurs outside supervised command | M6/M5 | Guarding, low-energy commissioning, independent stop, supervised tests and inhibit output until G5 plus an authorised validated event rule and all live gates pass | Unlikely × Catastrophic → High |
| RSK-10 | Camera captures people, or evidence is retained, accessed or hard-deleted without an agreed rule | Possible × Critical → High | Face/body pixels outside the ROI appear in stored/served output, unapproved export, the development delete endpoint remains enabled, or no retention/deletion decision has been made | M1/M4 | Enclose and crop the view, local event-only storage, notice, role-based access; disable the unaudited hard-delete route and quarantine incidental images | Rare × Critical → Medium |
| RSK-11 | Interface or configuration mismatch prevents late integration | Likely × Critical → High | Schema/baud/state mismatch, unversioned setting or module passes alone but fails baseline build | M1 with all owners | Interface-control record, contract tests, versioned configurations, weekly integration and owner-reviewer sign-off | Unlikely × Critical → Medium |
| RSK-12 | Encoder or common-part procurement arrives late or incompatible, delaying the fixture and validation | Possible × Catastrophic → Very high | No approved delivered quote/lead time by the procurement checkpoint, stock changes, or incoming electrical/mechanical checks fail | M1/M3/M6 | Obtain fresh stock, compatibility, delivered-cost and delivered-lead-time evidence; identify approved substitutes before order; repeat interface/power checks after any substitution and re-sequence without fabricating physical tests | Possible × Critical → High |
| RSK-13 | The selected camera arrives too late to migrate, or cannot be calibrated on the fixture, so the project delivers on the interim chain | Possible × Marginal → Medium | No confirmed dispatch by the procurement checkpoint, or C/CS back-focus and working distance cannot be set on the fixture | M1/M2 | Keep the interim configuration fully validated so no requirement depends on migration; confirm lens compatibility and back-focus before ordering; report the migration as not performed rather than presenting interim figures as Plan A results | Rare × Marginal → Low |

The two ratings move for different reasons, and that difference is the mitigation strategy. Physical-harm severity does not fall. RSK-08 and RSK-09 stay Catastrophic because guarding, an independent stop and watchdog-safe defaults change how often a hazardous state is reached, not what happens once it is. Their residual High is exactly why actuation stays inhibited until the G5 release gate, rather than being released on the strength of a favourable rating. Schedule and material risks work the other way round, reducing severity instead of probability: RSK-04, RSK-05 and RSK-12 fall from Catastrophic to Critical because re-sequencing and narrowed claims preserve a defensible deliverable when a part or material fails to arrive, while the arrival date itself stays outside team control. RSK-06 and RSK-10 are the only two rows where a procedural control genuinely makes the event Rare, because frozen group partitions and an enclosed, release-cropped view remove the mechanism rather than soften the consequence.

The stop rules matter most. RSK-04 blocks physical testing. RSK-06 invalidates the affected performance estimate. RSK-07 forces physical-value fields back to null. RSK-08 or RSK-09 inhibits actuation. RSK-12 can move the affected gate and validation schedule, and RSK-13 can cancel the migration without touching any interim acceptance decision. A residual High data or schedule risk is accepted only by narrowing the claim or revising the plan through the decision log — never by lowering the evidence label.

# 12. Recommendation and Conclusion

Plan A is recommended as the selected concept: a Raspberry Pi Global Shutter Camera on a C/CS-mount lens, connected to the Raspberry Pi 4 over CSI, with the same STM32 encoder, watchdog, lighting and safe-I/O supervision. Global-shutter capture removes the rolling-shutter and compressed-wireless artefacts that constrain the interim path (OmniVision Technologies, 2011; Raspberry Pi Ltd, 2026b). Its procurement is approved, and lead time is the only feasibility gate still open. That makes Plan B, on the supplied ESP32S3 OV3660 over controlled 2.4 GHz MJPEG, the interim implementation rather than a rejected alternative: it keeps the requirement set, the source-independent contracts, the supervision layer and the validation protocol in working order while the selected optics are procured. Section 5.8 defines the migration and the evidence that has to be re-established afterwards.

The cost boundary supports that judgement. Plan B has an additional-procurement envelope of **A$161.30–A$256.30 before shipping**, and every item in it is required by the build; only the A$41.30 encoder carries a verified supplier price, and the rest is allowance-based. Adding the supplier-verified A$136.15 Plan A camera and lens subtotal gives a **Plan A total of A$297.45–A$392.45 before shipping**, with the listed camera out of stock on 15 August 2026 (Core Electronics, 2026a, 2026b, 2026c). That subtotal is an approved commitment for the selected concept, not a comparison-only figure, and stock and delivered lead time have to be re-established at the point of order. Availability and delivered lead time for the Plan B common parts still need fresh evidence. These figures support the sequencing decision. They do not authorise a purchase on their own.

The recommendation authorises staged development, not acceptance. Plan B may advance only by passing the 27 August material gate, safe assembly inspection, versioned optical and encoder calibration, traceable real-material acquisition, held-out validation, supervised fault testing and the G5 safe-output release gate. Precision, recall, F1, minimum detectable physical size, millimetre accuracy, usable line speed and final latency are all still pending. So is stakeholder approval of the numerical requirements, which waits on documented consultation. If a gate fails, the defensible responses are to optimise, to restrict the operating envelope, or to revise the requirement with a recorded rationale. Plan A carries the same discipline: no Plan A performance may be reported until its hardware passes incoming inspection and its own versioned calibration, and this report records no Plan A measurement of any kind. Choosing a concept is not evidence that it performs.

What we propose, then, is a controlled measurement chain with honest state boundaries. Image acquisition produces a candidate record. Calibration may give that record physical meaning. Independent validation may support a defect claim. Only a healthy, non-stale, authorised state may request an action. That is the basis on which the interim Plan B build should be judged now, and the basis on which the selected Plan A configuration should be judged after migration.

# Appendix A. Internal Evidence Register

The report is intended to stand alone, so the measured values and their limitations are reproduced in Sections 5–6 rather than requiring access to the wider project directory. Table 21 identifies each team record by its reference entry and SHA-256; the corresponding entries are (ENG5105 Project Team, 2026a, 2026b, 2026c, 2026d, 2026e, 2026f, 2026g, 2026h, 2026i). Filenames remain in those entries solely for provenance. They are not assumed to accompany submission. The hashes identify the records reviewed at the evidence cut-off; they do not convert development-host evidence into Pi, STM32 or physical-defect evidence.

**Table 21. Internal integration, configuration and code evidence at 15 August 2026.**

| ID | Formal record reference | Evidence function and date | SHA-256 |
|---|---|---|---|
| IE1 | (ENG5105 Project Team, 2026f) | Summary-only VGA/SVGA/XGA screen and sustained-rate observations, 11 Aug. 2026 | `A75C316FBD64AFF205F48350EA37271ADEE31FF036F3040AA46EA5C350CDDC3E` |
| IE2 | (ENG5105 Project Team, 2026b) | Brightness-step timing and scoped network-fault observations, 11 Aug. 2026 | `16CFB2FF0C0449AACD100090F80CE764337888F1D67731E60207F5662A58B93D` |
| IE3 | (ENG5105 Project Team, 2026g) | Offline contracts, provenance and null-field safeguards, 10 Aug. 2026 | `EDB6D6645245F0882FFEC8CDC0B3738FE5109641D9518BC69A7F11204F2F5920` |
| IE4 | (ENG5105 Project Team, 2026h) | Historical live-link summary plus offline-only one-slot-buffer and state-policy evidence, 11 Aug. 2026 | `68D8AA905507B54CFDE71B15CA8D7D7CC6BDA270AA7859C2EC43C7B12FB933C8` |
| IE5 | (ENG5105 Project Team, 2026i) | Windows development ROI, threshold, minimum area, material-gate, frame-age and allowed-origin configuration | `CD63D586FAC65FD96BD66666D0EBEC535E7A1AE009FA8B35B471B84F4C7F1438` |
| IE6 | (ENG5105 Project Team, 2026e) | Windows development resident service, health logic and API endpoints | `551492CEA484C71EB2021B9C24766542B6D8E36A7F3D1C0FFD58FEB33FA91D4A` |
| IE7 | (ENG5105 Project Team, 2026a) | Source-independent baseline vision processor and default threshold | `A07C139F14C31C02B1EC209575A9579AE4FEEBC4DC1676050C2D0A760017B3F8` |
| IE8 | (ENG5105 Project Team, 2026d) | Raw ten-transition brightness-step timing record, 11 Aug. 2026 | `D2E1E23A9B8350906CADD0494775320A8CD973E3CEBBCB1DE0C7C5027F910298` |
| IE9 | (ENG5105 Project Team, 2026c) | Raw scoped network-fault and recovery record, 11 Aug. 2026 | `9F82F6D88965D99F9979610A508EF03347B7A4AF46749F7A02878FDFF07873AF` |

IE8 and IE9 supply machine-readable raw records for the timing and network-fault summaries. No equivalent raw per-frame trace is frozen for IE1, so the resolution/FPS evidence remains reproducible only at summary level and cannot substantiate frame-loss statistics. Before R2, R3, R5, R8, R9 or R10 acceptance, the evidence pack must also assign stable record identifiers and retain a SHA-256 for the remaining raw material, calibration provenance files, fixture scripts and test manifests; every summary value in this report must be recomputable from that pack.

# References

Australian Government. (2025). *Privacy Act 1988* (Compilation No. 103). https://www.legislation.gov.au/C2004A03712/2025-06-10

Caceres-Mendoza, C., Santander-Tapia, P., Cruz Sanchez, F. A., Troussier, N., Camargo, M., & Boudaoud, H. (2023). Life cycle assessment of filament production in distributed plastic recycling via additive manufacturing. *Cleaner Waste Systems, 5*, Article 100100. https://doi.org/10.1016/j.clwas.2023.100100

Carvalho, P., Lafou, M., Durupt, A., Leblanc, A., & Grandvalet, Y. (2024). Detecting visual anomalies in an industrial environment: Unsupervised methods put to the test on the AutoVI dataset. *Computers in Industry, 163*, Article 104151. https://doi.org/10.1016/j.compind.2024.104151

Core Electronics. (2026a). *Incremental photoelectric rotary encoder – 400 P/R*. Retrieved 15 August 2026, from https://core-electronics.com.au/incremental-photoelectric-rotary-encoder-400p-r.html

Core Electronics. (2026b). *Official camera modules – Raspberry Pi Global Shutter Camera*. Retrieved 15 August 2026, from https://core-electronics.com.au/raspberry-pi/camera/official-camera-modules.html

Core Electronics. (2026c). *Raspberry Pi 6 mm wide angle camera lens (CS-mount)*. Retrieved 15 August 2026, from https://core-electronics.com.au/raspberry-pi-6mm-wide-angle-lens.html

ENG5105 Project Team. (2026a). *Baseline vision processor snapshot* [Unpublished internal source-code record; source file: `src/week3/vision.py`].

ENG5105 Project Team. (2026b). *Live-path brightness-step and network-fault test record* [Unpublished internal technical record; source file: `LIVE_PATH_TEST_RESULTS_2026-08-11.md`].

ENG5105 Project Team. (2026c). *Raw scoped network-fault and recovery record* [Unpublished internal dataset; source file: `data/output/network_fault/network_fault_20260811.json`].

ENG5105 Project Team. (2026d). *Raw ten-transition brightness-step timing record* [Unpublished internal dataset; source file: `data/output/latency/latency_20260811.json`].

ENG5105 Project Team. (2026e). *Resident live-service implementation snapshot* [Unpublished internal source-code record; source file: `src/live_service.py`].

ENG5105 Project Team. (2026f). *Resolution and frame-rate integration test* [Unpublished internal technical record; source file: `RESOLUTION_TEST_RESULTS_2026-08-11.md`].

ENG5105 Project Team. (2026g). *Week 3 offline contracts and provenance record* [Unpublished internal technical record; source file: `WEEK3_OFFLINE_IMPLEMENTATION.md`].

ENG5105 Project Team. (2026h). *Week 4 camera-link and offline fault-policy record* [Unpublished internal technical record; source file: `WEEK4_OFFLINE_IMPLEMENTATION.md`].

ENG5105 Project Team. (2026i). *Windows live-service configuration snapshot* [Unpublished internal configuration record; source file: `config/live_service.json`].

Espressif Systems. (2026). *esp32-camera: ESP32 camera driver* [Computer software repository]. Retrieved 15 August 2026, from https://github.com/espressif/esp32-camera

Figueiredo, R. B. D., & Mendes, H. A. (2024). Analyzing information leakage on video object detection datasets by splitting images into clusters with high spatiotemporal correlation. *IEEE Access, 12*, 47646–47655. https://doi.org/10.1109/ACCESS.2024.3383047

Heckler-Kram, L., Neudeck, J.-H., Scheler, U., König, R., & Steger, C. (2026). The MVTec AD 2 dataset: Advanced scenarios for unsupervised anomaly detection. *International Journal of Computer Vision, 134*(4). https://doi.org/10.1007/s11263-026-02743-0

Hidalgo-Carvajal, D., Hortal Muñoz, Á., Garrido-González, J. J., Carrasco-Gallego, R., & Alcázar Montero, V. (2023). Recycled PLA for 3D printing: A comparison of recycled PLA filaments from waste of different origins. *Polymers, 15*(17), Article 3651. https://doi.org/10.3390/polym15173651

International Organization for Standardization. (2006). *Environmental management – Life cycle assessment – Principles and framework* (ISO 14040:2006). https://www.iso.org/standard/37456.html

International Organization for Standardization. (2023). *Safety of machinery – Safety-related parts of control systems – Part 1: General principles for design* (ISO 13849-1:2023). https://www.iso.org/standard/73481.html

ISO/IEC/IEEE. (2023). *Systems and software engineering – System life cycle processes* (ISO/IEC/IEEE 15288:2023). https://www.iso.org/standard/81702.html

Kapoor, S., & Narayanan, A. (2023). Leakage and the reproducibility crisis in machine-learning-based science. *Patterns, 4*(9), Article 100804. https://doi.org/10.1016/j.patter.2023.100804

Katsigiannis, M., & Mykoniatis, K. (2024). Enhancing industrial IoT with edge computing and computer vision: An analog gauge visual digitization approach. *Manufacturing Letters, 41*, 1264–1273. https://doi.org/10.1016/j.mfglet.2024.09.153

Krassnig, P. J., Haselmann, M., Kremnitzer, M., & Gruber, D. P. (2025). Efficient surface defect detection in industrial screen printing with minimized labeling effort. *Integrated Computer-Aided Engineering, 32*(1), 3–23. https://doi.org/10.3233/ICA-240742

Lafirenza, M., Guerra, M. G., & Lavecchia, F. (2023). A layerwise monitoring methodology based on blue laser line profilometer for material extrusion processes. *The International Journal of Advanced Manufacturing Technology, 127*, 5421–5436. https://doi.org/10.1007/s00170-023-11864-6

Microchip Technology. (2008). *MCP3204/3208: 2.7 V 4-channel/8-channel 12-bit A/D converters with SPI serial interface* (DS21298E). https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/21298e.pdf

Monash University. (2026a). *Concept design: Discipline-specific content (Electrical)* [ENG5105 course material].

Monash University. (2026b). *Electrical teams proposal report rubric 2026*.

Monash University. (2026c). *ENG5105 components – with pictures 2026*.

Monash University. (2026d). *ENG5105/ENG5106 integrated design semester 2 2026: Common context and project briefs* (Rev. 0).

Monash University. (2026e). *Welcome to Country and acknowledgement of Traditional Owners*. Retrieved 15 August 2026, from https://www.monash.edu/brandbook/about/welcome-to-country-and-acknowledgement-of-traditional-owners

Office of the Australian Information Commissioner. (2026). *Posting photos and videos*. Retrieved 15 August 2026, from https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/handling-personal-information/posting-photos-and-videos

OmniVision Technologies. (2011). *OV3660 color CMOS QSXGA image sensor datasheet* (Ver. 1.3). https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/OV3660_datasheet.pdf

Petsiuk, A., & Pearce, J. M. (2021). Open source filament diameter sensor for recycling, winding, and additive manufacturing machines. *Journal of Manufacturing Science and Engineering, 143*(10). https://doi.org/10.1115/1.4050762

Quader, R., Dramko, E., Grewell, D., Randall, J., & Narayanan, L. K. (2024). Characterizing the effect of filament moisture on tensile properties and morphology of fused deposition modeled polylactic acid/polybutylene succinate parts. *3D Printing and Additive Manufacturing, 11*(3), 1151–1161. https://doi.org/10.1089/3dp.2022.0222

Raspberry Pi Ltd. (2026a). *Raspberry Pi 4 Model B product brief*. https://pip.raspberrypi.com/documents/RP-008344-DS-raspberry-pi-4-product-brief.pdf

Raspberry Pi Ltd. (2026b). *Raspberry Pi Global Shutter Camera*. Retrieved 15 August 2026, from https://www.raspberrypi.com/products/raspberry-pi-global-shutter-camera/

Raspberry Pi Ltd. (2026c). *Raspberry Pi hardware documentation: GPIO and the 40-pin header*. Retrieved 15 August 2026, from https://www.raspberrypi.com/documentation/hardware/rf/

Seeed Studio. (2026). *Getting started with Seeed Studio XIAO ESP32S3 series*. Retrieved 15 August 2026, from https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/

STMicroelectronics. (2026). *STM32 Nucleo-32 boards: NUCLEO-L432KC* (DB2638 Rev. 9). https://www.st.com/resource/en/data_brief/nucleo-l432kc.pdf

Stouffer, K., Pease, M., Tang, C., Zimmerman, T., Pillitteri, V., Lightman, S., Hahn, A., Saravia, S., Sherule, A., & Thompson, M. (2023). *Guide to operational technology (OT) security* (NIST Special Publication 800-82r3). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-82r3

Sundarrajan, K., & Rajendran, B. K. (2023). Explainable efficient and optimized feature fusion network for surface defect detection. *The International Journal of Advanced Manufacturing Technology*. https://doi.org/10.1007/s00170-023-11789-0

Texas Instruments. (2025). *LMx24, LMx24x, LMx24xx, LM2902, LM2902x, LM2902xx, LM2902xxx quadruple operational amplifiers* (SLOS066AE). https://www.ti.com/lit/ds/symlink/lm324.pdf

United Nations Department of Economic and Social Affairs. (2026). *Sustainable Development Goal 12: Responsible consumption and production*. Retrieved 15 August 2026, from https://sdgs.un.org/goals/goal12

Verspeek, S., De Kerf, T., Ribbens, B., Maldague, X., Vanlanduit, S., & Steenackers, G. (2024). A novel line-scan algorithm for unsynchronised dynamic measurements. *Applied Sciences, 14*(1), Article 235. https://doi.org/10.3390/app14010235

Wang, C., Zhu, W., Gao, B.-B., Gan, Z., Zhang, J., Gu, Z., Qian, S., Chen, M., & Ma, L. (2024). Real-IAD: A real-world multi-view dataset for benchmarking versatile industrial anomaly detection. In *2024 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)* (pp. 22883–22892). https://doi.org/10.1109/CVPR52733.2024.02159

Wei, X., & Bähr, R. (2024). A comparative study of 3D printing with virgin and recycled polylactic acid filaments. *CIRP Journal of Manufacturing Science and Technology, 54*, 75–84. https://doi.org/10.1016/j.cirpj.2024.08.007

Zhao, P., Rao, C., Gu, F., Sharmin, N., & Fu, J. (2018). Close-looped recycling of polylactic acid used in 3D printing: An experimental investigation and life cycle assessment. *Journal of Cleaner Production, 197*, 1046–1055. https://doi.org/10.1016/j.jclepro.2018.06.275
