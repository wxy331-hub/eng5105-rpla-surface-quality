# ENG5105 Proposal Design Report: Scene Research Dossier

**Scene:** report review | **Target:** ENG5105 Electrical | **Tier:** pro | **Authority order:** rubric -> discipline-specific instructions -> project brief -> supplied-components list.

## Venue Requirements

This is a complete, client-facing engineering proposal, not a catalogue of concepts. Its spine is: Executive Summary and personalised/localised Acknowledgement of Country; literature, stakeholders and measurable requirements; at least two concepts and justified selection; selected-concept functional details; environmental/safety/ethical/governance/procurement implications; BOM; project plan, recommendation and conclusion; figures/tables; references; and professional structure/headshots ([Rubric, p. 1](../Electrical%20teams%20proposal%20report%20rubric%202026.pdf)). Electrical content adds a relevant UN SDG, camera privacy, unit specifications, sensing/UI/communications, calculated power budget, interfaces, supplier/quantity/cost BOM, timeline, planning strategy, and risk matrix with mitigations ([Discipline content, pp. 1-3](../Concept%20design_%20Discipline%20specific%20content.docx.pdf)). The sources state no page limit, anonymisation rule, or citation style; do not invent one.

## Review Criteria

HD (>80%) requires analysis and traceability, not description. Highest leverage is **Functional Details (25%)**: provide a detailed sensor-to-output/API block diagram, explain every block, specify units, calculate power, define communications/API, and map choices to numbered requirements. **Project Plan/Recommendations/Conclusions (20%)** must connect milestones, strategy, risks, validation and recommendation to stakeholder needs. Background (10%) needs critical literature plus genuine engagement; Concepts (10%) needs two differentiated alternatives, evidence-backed trade-offs and requirement-linked selection. The remaining 35% rewards implications/BOM accuracy and report-wide graphics, grammar, primary-source referencing and navigation. Use a requirement-to-evidence matrix to prevent repetition.

## Accepted Report Patterns

1. **Need-to-decision arc:** context -> literature-derived and stakeholder-confirmed requirements -> two concepts -> transparent selection -> selected architecture -> implementation/validation plan, matching the brief's demand for evaluated alternatives and justified decisions ([Project brief, p. 3](../ENG5105-ENG5106%20S2%202026%20-%20Project%20Briefs_Rev0.pdf)).
2. **Evidence-chain arc:** requirement -> specification -> functional block -> verification method -> risk/mitigation. For surface quality, the brief specifically identifies industrial camera/machine vision/structured light, with lighting control, image processing and defect classification as design challenges ([Project brief, pp. 7-8](../ENG5105-ENG5106%20S2%202026%20-%20Project%20Briefs_Rev0.pdf)).

## Constraints for This Report

- Present **Plan A and Plan B** to satisfy the mandatory two-concept comparison. Apply feasibility gates first: supplied hardware, approved budget, lead time and semester deliverability. Plan A may retain global-shutter imaging benefits but is comparison-only because its required hardware is not university-supplied and its incremental procurement cost/lead time are unresolved. Charge only Plan-A-specific additions, not shared parts. Plan B alone proceeds to functional design, BOM, schedule and validation; its Raspberry Pi 4, STM32 and ESP32S3 are within the supplied baseline ([Components, pp. 1-4](../ENG5105%20Components%20-%20With%20pictures%202026.pdf)).
- **Stakeholder gap:** no documented consultation outcomes currently support “approved” requirements. Provide an engagement plan and label numerical targets `PROPOSED_REQUIREMENT` until consultation is evidenced; do not fabricate meetings, quotations, approvals or client priorities.
- Camera/GUI/database/recovery results are `LIVE_INTEGRATION_ONLY` or `OFFLINE_SYNTHETIC_ONLY`; they do not prove real-rPLA defect classification, robustness, accuracy or industrial suitability. The 20 processed-FPS target is unresolved against approximately 10.77 FPS at SVGA.
- Prohibit invented supplier quotes, measured costs, calibration, millimetre size/position, encoder performance, accuracy/precision/recall/F1, line-speed compliance, automatic rejection effectiveness or real-rPLA results. State pending physical-material, fixture, labelled-dataset and calibration tests explicitly.
