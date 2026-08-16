# Proposal Design Report

## Evidence-Traceable Surface Quality Monitoring for Recycled PLA Filament

| Document field | Status |
|---|---|
| Client context | BioLoop Manufacturing Pty Ltd |
| Discipline | ENG5105 Electrical Engineering |
| Deliverable | Proposal design report |
| Selected quality parameter | Visible rPLA filament surface quality |
| Selected concept | Plan B: ESP32S3 OV3660 acquisition, Raspberry Pi 4 processing and services, STM32 supervision and safe I/O |
| Concept status | Plan A is retained only as a rubric-required comparator; Plan B is the sole implementation and validation path |
| Evidence cut-off | 15 August 2026 |
| Evidence status | Proposal with bounded integration evidence; real-material calibration and defect-performance validation remain pending |

## Executive Summary

BioLoop requires a laboratory-scale system that can monitor visible surface anomalies while recycled polylactic acid (rPLA) filament is moving through a manufacturing process. The client brief identifies bubbles, roughness, contamination, cracks and inclusions as relevant surface-quality concerns, and asks electrical teams to address real-time acquisition, communication, visualisation, fault detection and eventual industrial integration [1]. This report recommends Plan B: an ESP32S3 Sense node with an OV3660 camera will transmit MJPEG over a controlled 2.4 GHz network; the Raspberry Pi 4 is allocated OpenCV processing, data storage, API/WebSocket services and the operator interface; the STM32 Nucleo-L432KC is allocated encoder input, lighting control, watchdog supervision and inhibited downstream I/O. These three computing platforms are within the university-supplied baseline [4]. The current service/API/GUI evidence comes from the Windows development host; it does not establish deployment on the Pi or physical STM32 I/O.

Plan A provides the technically stronger camera option, but it is not deliverable within the selected semester path. The concept couples the Raspberry Pi to a global-shutter camera and C/CS-mount lens. Simultaneous pixel exposure is attractive for rapid-motion imaging [23], yet the camera and lens are not in the university-supplied equipment. Their verified Plan-A-only subtotal is A$136.15 before shipping, comprising an A$92.55 camera and A$43.60 lens; the camera was also out of stock when checked on 15 August 2026 [29], [30]. That extra cost and procurement uncertainty fail the mandatory gates. Shared items such as the Raspberry Pi, STM32, lighting, encoder, enclosure and protection hardware are deliberately excluded from the Plan A subtotal. Plan A therefore remains a fair comparator, but it will not be purchased, built, tested or treated as a future migration path.

Plan B is deliverable, not yet validated as an rPLA defect detector. A recorded 30 s SVGA integration test observed 10.77 processed frames/s with no reported drops under its stated conditions (`RESOLUTION_TEST_RESULTS_2026-08-11.md`; Appendix A, IE1). The run contained no rPLA in the region of interest. It establishes frame transport and processing continuity only. The present software also gates detection during network recovery and preserves uncalibrated physical fields as null, but neither behaviour establishes defect accuracy, minimum detectable size, millimetre position accuracy, usable line speed or industrial readiness. All numerical requirements in Section 3 are marked `PROPOSED_REQUIREMENT`. Physical acceptance depends on controlled optics, optical and encoder calibration, labelled real-material specimens, independent validation groups and documented requirement review after the scheduled Week 5 Thursday material arrival.

## Acknowledgement of Country

We acknowledge the Traditional Owners and Custodians of the unceded lands on which Monash University operates, including the people of the Kulin Nations, and pay respect to their Elders past and present [28]. This project concerns circular use of materials, but circularity alone does not make an engineering system responsible. Our work should conserve resources, avoid preventable waste, and account for the energy, electronics and decisions introduced by the monitoring device. We recognise that care for Country carries responsibilities extending beyond the technical boundary of this proposal.

# 1. Background and Purpose

## 1.1 Client and manufacturing context

BioLoop's proposed manufacturing hub is intended to produce rPLA and rPLA-composite filament for Australian education, engineering, manufacturing and consumer markets. Product monitoring sits inside a wider circular-manufacturing system alongside automation, resource efficiency, safety and economic viability [1]. A filament may reach the customer only after extrusion, cooling, handling and spooling, so a visible anomaly found late can imply rework, rejected product or loss of confidence in the batch. Online observation offers an earlier decision point.

Recycled PLA is not one uniform input. Published comparisons report that feedstock origin, recycling history and processing conditions can affect the properties of recycled filament and printed products [5], [6]. Moisture can also influence morphology and tensile behaviour in PLA-containing fused-filament material [7]. These findings justify monitoring, but they do not let a camera diagnose moisture, degradation or extrusion settings from appearance alone. A pit or colour patch is evidence of a visible condition. Its process cause remains a hypothesis until it is checked against independent process and material data.

The circular-economy rationale needs the same restraint. Life-cycle studies of distributed filament production and closed-loop PLA recycling show why recovered material deserves serious consideration, while also showing that benefits depend on system boundaries, energy and process choices [8], [9]. This proposal does not claim a completed life-cycle assessment. Its narrower purpose is to make surface-quality evidence available soon enough for a person, quality system or later plant controller to act.

## 1.2 Purpose, question and boundary

The report asks:

> Can a low-cost, supplied-hardware machine-vision system detect, locate and grade visible anomalies on moving rPLA filament under representative laboratory conditions, while withholding unsafe or uncalibrated outputs?

The system must make useful detections whose validity is independently established. A stream that looks live can still be stale, poorly illuminated or geometrically uncalibrated, which is why acquisition health and evidence status are design functions rather than interface decoration.

Table 1 fixes the investigation boundary before concepts are compared.

**Table 1. Proposed project scope.**

| In scope | Outside the present claim boundary |
|---|---|
| Visible bubbles or pits, cracks or scratches, contamination or inclusions, and abnormal surface texture identified from controlled images | Engineering roughness parameters such as Ra without a validated profilometric or structured-light reference |
| Laboratory-scale online acquisition, candidate detection, event recording, alarm presentation and safe-output requests | Internal void metrology, polymer chemistry identification, or proof of a defect's process cause |
| Optical and encoder calibration followed by labelled real-rPLA testing | Uncalibrated millimetre dimensions or positions |
| Basic fault detection and integration with a larger automated process, as required by the brief [1] | Safety certification, autonomous production release, or industrial deployment claims |

The intended output is thus a traceable candidate record and an operator-facing decision aid. Automatic rejection is a possible downstream request, not a currently authorised quality decision.

# 2. Literature Review and Design Implications

## 2.1 What surface images can establish

Research on rPLA establishes a reason to inspect but not a visual ground truth. Material source, repeated processing and moisture can change performance [5]-[7]; the brief separately lists bubbles, roughness, contamination, cracks and inclusions as surface conditions that may indicate process or material problems [1]. The word *may* matters. We use the literature to define defect families and challenge conditions, then require labelled specimens before assigning a class. Visual evidence cannot by itself separate a moisture-driven bubble from another cavity-forming mechanism.

Industrial anomaly-detection research also warns against treating a tidy laboratory image as the operating domain. Recent datasets include advanced operating scenarios, real industrial imagery and multi-view observations [10]-[12]. Their reported model results cannot be transferred to rPLA, because the objects, labels, optics and prevalence differ. The transferable lesson is experimental: camera geometry, background, illumination, viewpoint and dataset split must be controlled and documented.

## 2.2 Motion, optics and acquisition

A moving cylindrical filament is a difficult optical target. Highlights migrate as the filament rotates; a single view cannot guarantee full circumferential coverage; compression can create block or edge artefacts. Unsynchronised dynamic line-scan research shows why motion and sampling alignment deserve explicit treatment [13], while surface-defect work demonstrates that appearance features remain sensitive to the inspection context [14]. Controlled diffuse and low-angle illumination, a fixed region of interest, locked focus/exposure where supported, and a repeatable guide geometry are therefore part of the measurement concept.

Plan A addresses motion at the sensor. Raspberry Pi's global-shutter camera exposes all pixels simultaneously and accepts C/CS-mount lenses [23]. Plan B uses the supplied OV3660 rolling-shutter imager, whose sensor limits are described in its datasheet [18], through the supported ESP32 camera stack [19], [20]. No datasheet predicts this application's defect accuracy. Plan B must instead reduce motion-skew risk through bounded line speed, exposure control, repeatable lighting and empirical validation.

## 2.3 Processing roles and evidence flow

Running every task on the camera node would simplify wiring, but it would compress acquisition, analysis, storage, interface and fault recovery into one resource-constrained device. Edge-computing literature supports placing time-sensitive visual processing near the equipment while retaining clear system roles [15]. In this design, the ESP32S3 is allocated image acquisition and transport; the Raspberry Pi 4 is allocated OpenCV, records, services and the GUI; the STM32 is allocated deterministic encoder, watchdog, lighting and output supervision. Manufacturer documents establish that the Pi and Nucleo platforms expose suitable computing and interface resources [21], [22]. They are capability evidence, not proof that these roles have been deployed.

This separation creates a useful failure boundary. A camera timeout can put the Pi service into a reconnecting state while the STM32 inhibits the marker or stop request. Latest-frame handling prevents an old image from silently becoming a current quality event. The architecture consequently treats health metadata, timestamps, calibration identifiers and null physical fields as part of the evidence chain.

## 2.4 Validation implications

Adjacent video frames are highly correlated. If near-duplicate frames from one defect appear in both training and test data, reported performance can be optimistic; broader machine-learning work identifies leakage as a reproducibility threat [16], and video-object-detection research shows the specific risk created by spatiotemporal correlation [17]. Validation will therefore separate data by physical spool or batch and by defect event, not by randomly shuffling individual frames.

Accuracy alone would hide the cost of rare defects. The proposed assessment will report event-level precision, recall and F1 score, false alarms per metre, missed events, latency and stability across declared lighting and speed conditions. Sample counts and uncertainty must accompany those values. None exists yet.

Table 2 converts these literature findings into design decisions and identifies the project-specific evidence still missing.

**Table 2. Literature-to-design transfer.**

| Evidence cluster | Design implication | Evidence still required for this project |
|---|---|---|
| rPLA variability and moisture [5]-[7] | Treat visible anomalies as observations, not automatic root-cause diagnoses | Labelled real-rPLA specimens linked to documented conditions |
| Industrial anomaly and multi-view datasets [10]-[12] | Freeze optics and record viewpoint, lighting and dataset provenance | Representative images from the final fixture |
| Dynamic imaging and surface inspection [13], [14] | Control exposure, motion, geometry and illumination; test coverage limits | Speed challenge and circumferential-coverage study |
| Leakage and correlated video [16], [17] | Split validation by independent spool/batch/event | Pre-registered dataset split and held-out test results |

# 3. Stakeholders, Needs and Proposed Requirements

## 3.1 Stakeholder evidence status

No direct stakeholder consultation record has been supplied for this proposal report. The needs below are derived from the BioLoop project brief, discipline instructions and literature; they are not attributed to a meeting, participant or client approval. This distinction matters because the rubric expects engagement and requirements that inform the design [2], [3]. The report can state what should be discussed. It cannot invent what someone said.

**Table 3. Stakeholder map and provisional design response.**

| Stakeholder group | Need inferred from brief or system use | Proposed design response | Current status |
|---|---|---|---|
| BioLoop/client representative | Traceable quality evidence, cost awareness and a path to automated integration | Requirement register, event records, API and explicit acceptance gates | Brief-derived; confirmation pending |
| Production operator | Clear health state, actionable alarms and no silent stale-data decision | Single-screen status, candidate overlay, alarm history and inhibited output when unhealthy | Proposed |
| Quality assurance personnel | Reviewable images, batch context, repeatable classification and export | Versioned calibration/model identifiers, immutable event fields and dataset export | Proposed |
| Maintenance and electrical personnel | Diagnosable faults, serviceable interfaces and safe recovery | Camera/processor/encoder/lighting health, watchdog states and manual reset rules | Proposed |
| Laboratory supervisor and technical staff | Safe, testable use of supplied equipment | Enclosed optical path, low-voltage prototype domains and staged fault tests | Brief- and equipment-derived |
| Filament users | Consistent product information without unsupported quality claims | Evidence-backed grading only after validation; retain uncertain events for review | Literature-derived; confirmation pending |

Engagement should now test assumptions rather than seek a ceremonial sign-off. A short structured session can ask which defect families cause rejection, what false-alarm burden is tolerable, how long evidence must be retained, who may authorise a stop or reject action, and which operating speeds and lighting conditions are representative. Each answer should enter a dated decision log with the affected requirement, owner, rationale and verification change. Until that record exists, no priority in Table 3 is claimed as stakeholder-approved.

## 3.2 Proposed requirements and verification

Every numeric threshold in Table 4 is a `PROPOSED_REQUIREMENT`. The values provide a testable design baseline, as requested by the electrical discipline guidance [2], but remain open to stakeholder review and experimental revision.

**Table 4. Proposed requirements register.**

| ID | Proposed requirement | Planned verification | Status or present gap |
|---|---|---|---|
| R1 | Detect at least three classes of visible surface anomaly | Held-out, event-level labelled test | `PENDING_REAL_MATERIAL` |
| R2 | Target defects with a characteristic feature size of at least 0.20 mm | Calibrated target and labelled specimens | `PENDING_REAL_MATERIAL`; optical scale unavailable |
| R3 | For defects meeting R2, achieve at least 90% precision and 90% recall | Independent spool/batch/event split | `PENDING_REAL_MATERIAL`; no accuracy result exists |
| R4 | Process at least 20 frames/s while filament speed is 0-5 m/min | Sustained final-fixture run plus speed challenge | Not achieved: current SVGA integration observation is 10.77 frames/s |
| R5 | Issue an alarm within 500 ms of confirmed detection | Physical timing reference from exposure/event to alarm | Proposed; current brightness-control path timing is not this measure |
| R6 | Limit longitudinal defect-location error to +/-10 mm | Encoder counts/mm calibration and marked-distance test | `PENDING_REAL_MATERIAL`; encoder calibration absent |
| R7 | Store defect type, size, confidence, image, position, time and batch identifier | Schema and record audit | Partly implemented; size/position stay null until calibration |
| R8 | Run continuously for 30 min with less than 1% record loss | Soak test with reconciled frame/event counts | Proposed; final hardware test pending |
| R9 | Enter a safe hold or fault state after camera, lighting, encoder or processor failure | Fault injection and output-state observation | Software/network path evidence only; physical safe I/O pending |
| R10 | Image only the enclosed filament region and store data locally by default | Field-of-view inspection and configuration/access audit | Proposed privacy-by-design control |

R4 exposes the largest current design tension. A lower interim demonstration threshold may be useful for integration, but it cannot replace the 20 frames/s final target without a documented requirement change. Failure at the final fixture will trigger optimisation, a justified line-speed limit, or formal renegotiation. Selective reporting is not an acceptance method.

# 4. Concepts and Selection

## 4.1 Selection method

The rubric requires at least two differentiated concepts and an evidence-backed recommendation [3]. We apply four pass/fail gates before preference scoring: availability of the issued primary imaging hardware, avoidance of an unapproved concept-specific primary-camera purchase, procurement timing, and semester deliverability. A technically attractive concept that fails a mandatory gate is not a candidate for implementation. These are team feasibility decisions for the present proposal, not stakeholder-approved budget limits.

## 4.2 Plan A: direct global-shutter imaging comparator

Plan A connects a Raspberry Pi Global Shutter Camera to the Pi through CSI, uses a suitable C/CS-mount lens and controlled lighting, and retains STM32-based encoder, watchdog, lighting and safe I/O functions. Its main strength is simultaneous exposure of the image array, which is suited to rapid motion and machine-vision use [23]. Local CSI transport also removes Wi-Fi and MJPEG from the camera-to-processor path. Optical alignment, reflective cylindrical geometry and single-view coverage would still require calibration.

The concept is credible. It is also unavailable to this project. Table 5 includes only purchases unique to Plan A.

**Table 5. Verified Plan-A-only incremental procurement, accessed 15 August 2026.**

| Item | Quantity | Price | Observed availability | Source |
|---|---:|---:|---|---|
| Raspberry Pi Global Shutter Camera | 1 | A$92.55 | Out of stock | [29] |
| Raspberry Pi 6 mm CS-mount lens | 1 | A$43.60 | In stock | [30] |
| **Plan-A-only subtotal** |  | **A$136.15** | Shipping excluded | Calculated from [29], [30] |

The subtotal is additional to common prototype needs. No Raspberry Pi, STM32, encoder, lighting, enclosure, power/protection or marker cost has been charged twice. Against the Plan B additional-procurement envelope in Section 9, this A$136.15 increment raises the estimated total by approximately 55–96%, depending on the common allowance realised. Because the purchase is unapproved, the camera was out of stock on the access date, and the new optical chain would consume limited integration time, the team treats the uplift as too high for this implementation path. Plan A fails the availability, cost, lead-time and semester-delivery gates and will not proceed to procurement or validation.

## 4.3 Plan B: supplied-hardware distributed vision

Plan B uses the university-supplied XIAO ESP32S3 Sense, Raspberry Pi 4 and STM32 Nucleo-L432KC [4]. Its proposed chain is:

> Controlled optical head and rPLA filament -> ESP32S3 OV3660 acquisition -> 2.4 GHz Wi-Fi MJPEG -> Raspberry Pi 4 OpenCV, API/WebSocket, SQLite and GUI <-> STM32 encoder, watchdog, lighting and inhibited output interface

The OV3660 and ESP32 camera documentation support the chosen acquisition stack [18]-[20]; the Pi and Nucleo documents support their planned processing and interface roles [21], [22]. Plan B avoids a new primary-camera purchase and builds on the software and live transport path already integrated. It also exposes real limitations: rolling-shutter distortion, JPEG artefacts, wireless delay or interruption, limited optical control and no guaranteed full-circumference view. Those constraints become test conditions and risk controls. They are not hidden by the selection decision.

## 4.4 Feasibility gates and technical comparison

Table 6 applies the mandatory gates before the technical preferences recorded in Table 7.

**Table 6. Mandatory feasibility gates.**

| Gate | Plan A | Plan B | Decision significance |
|---|---|---|---|
| Issued primary imaging hardware available | **Fail**: global-shutter camera and lens not supplied | **Conditional pass**: primary camera and computing platforms are listed as supplied; issue, condition and compatibility checks remain pending [4] | Plan A cannot begin from the issued baseline |
| No unapproved concept-specific primary-camera purchase | **Fail**: at least A$136.15 plus shipping, a 55–96% uplift over the Plan B envelope | **Pass** for primary imaging: no additional main camera purchase; common additions remain subject to approval | Team proposal gate, not a client-approved budget threshold; shared costs excluded from both sides |
| Procurement/lead-time exposure | **Fail**: camera out of stock on 15 August 2026 [29] | **Pass with residual risk**: supplied core platforms; fixture and common parts still need confirmation | Plan A timing cannot be relied upon |
| Semester implementation and validation | **Fail**: new optical chain would arrive, integrate and calibrate late | **Pass conditionally**: existing Plan B path can proceed to real-material tests | Validation remains conditional on material and fixture availability |

A separate scoring exercise records technical preference without overriding these gates. Scores are team-assigned comparative judgements from 1 (weak) to 5 (strong), not measurements. The provisional weights allocate 65% to measurement capability (R1–R4 and R6), 15% to Pi integration (R4, R7 and R8), and 20% to cost and procurement constraints. They reflect the team's present technical judgement; no stakeholder approval is claimed. The matrix is sensitive to those weights, so it exposes the trade-off rather than certifying the decision.

**Table 7. Weighted concept comparison.**

| Criterion | Weight | Plan A | Plan B | Basis of judgement |
|---|---:|---:|---:|---|
| Defect-classification potential (R1, R3) | 25% | 5 | 3 | Plan A offers a more configurable machine-vision optical chain; neither concept has rPLA accuracy data |
| Motion-imaging suitability (R2, R4) | 20% | 5 | 2 | Global shutter versus rolling shutter and compressed wireless transport [18], [23] |
| Spatial-detail potential (R2, R6) | 20% | 4 | 3 | Interchangeable lens and optical control versus supplied OV3660 path |
| Raspberry Pi integration (R4, R7, R8) | 15% | 5 | 4 | Direct CSI versus supported network acquisition and service integration |
| Concept-specific cost (project constraint) | 10% | 3 | 5 | A$136.15 plus shipping for Plan A imaging; no new Plan B main camera |
| Procurement timing (schedule constraint) | 10% | 3 | 5 | Plan A camera out of stock; Plan B core platforms listed as supplied, subject to issue check |
| **Weighted total** | **100%** | **4.40** | **3.35** | Comparative score only |

Plan A leads the weighted comparison because its sensor and lens arrangement better address motion and optical control. The feasibility result is decisive: a higher preference score cannot supply unavailable hardware or recover uncertain lead time. Plan B is therefore selected as the sole implementation path. Its recommendation rests on deliverability and a clear validation strategy, not on a claim that its present images already meet R1-R10.
