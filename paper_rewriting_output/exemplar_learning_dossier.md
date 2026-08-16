# Exemplar Learning Dossier

## Authority and scope

This dossier studies transferable reporting practices only; it supplies neither report prose nor new project claims. The local `Electrical teams proposal report rubric 2026.pdf` remains authoritative, followed by `Concept design_ Discipline specific content.docx.pdf`. ENG5105's mandatory content, evidence limits, and assessment criteria override every external source below.

## Exemplar inventory

| Source | Institution / year | Why selected |
|---|---|---|
| [Report Writing Guide for Engineers](https://www.unsw.edu.au/engineering/sites/default/files/documents/Report_Writing_Guide_for_Engineers_2018ed.pdf) | UNSW Engineering, 2018 ed. | Conventions for summaries, navigation, units, tables, figures, and graphs. |
| [Short Reports](https://ecp.engineering.utoronto.ca/resources/online-handbook/types-of-documents/short-reports/) | University of Toronto Engineering Communication Program, current guide (accessed 2026) | A compact problem-purpose-analysis-conclusion-recommendation arc with explicit reader orientation. |
| [Stakeholder Analysis, User Needs & Functions, Specifications](https://www.capstone.gatech.edu/stakeholder-analysis-user-needs-functions-specifications/) | Georgia Tech Capstone Design, current guide (accessed 2026) | Connects stakeholder mapping to user needs, constraints, and quantitative specification sheets. |
| [Concept Generation & Selection](https://designlab.eng.rpi.edu/edn/projects/capstone-support-dev/wiki/Concept_Generation_%26_Selection) | Rensselaer Design Lab, current capstone guide (accessed 2026) | Shows requirements-based comparison using meaningful performance metrics rather than unexplained binary scores. |
| [NASA Systems Engineering Handbook, Rev. 2](https://www.nasa.gov/wp-content/uploads/2018/09/nasa_systems_engineering_handbook_0.pdf) | NASA, 2016 | Patterns for requirements metadata, trade studies, decision records, verification, uncertainty, cost, schedule, and risk. |
| [Micropower: Design and Development of a Hydrokinetic Turbine](https://depts.washington.edu/pmec/docs/20110615_ME495_report_Micropower.pdf) | University of Washington capstone report, 2011 | Accessible full-report example linking design requirements to weighted criteria, selection narrative, figures, calculations, sources, and an itemised cost appendix. |

## Structural patterns

1. **Maintain one traceable decision spine.** Move from client problem and stakeholder needs to labelled, measurable requirements, complete-concept comparison, selected architecture, specifications, BOM, risks, verification, schedule, and recommendation. A compact table can map `requirement -> design feature -> evidence/verification method -> status`.
2. **Separate feasibility from preference.** Apply non-negotiable constraints first, then compare feasible alternatives with criterion definitions, weights, data sources, scoring rationale, assumptions, and limitations. This supports ENG5105's Plan A comparison/Plan B selection: procurement availability, incremental cost, and semester lead time can be explicit feasibility gates before any weighted preference matrix.
3. **Layer the report for two audiences.** Put the problem, recommendation, decisive trade-offs, cost/schedule implications, and validation gaps in the executive summary; place detailed calculations and supplementary data in signposted sections or appendices.

## Rhetorical patterns

Open with the decision context, not generic history: identify the client problem, report purpose, alternatives evaluated, and governing criteria. State the recommendation early, then earn it through traceable evidence. Close by synthesising why the selected concept best satisfies the stated needs, what remains unverified, and which scheduled actions will close each gap; do not merely repeat section summaries.

## Table, figure, and evidence conventions

- Use tables for repeated fields: requirement units/tolerances and provenance; concept performance; BOM quantity, cost, justification, and availability; risk ratings and mitigation; milestone dependencies and evidence outputs.
- Give every table and figure a numbered, informative caption, introduce it before it appears, and interpret its decision significance afterward. Keep block-diagram arrows directional and label signals/interfaces, protocols, power domains, and system boundaries. Use graphs only for relationships or measured trends, with labelled axes and units.
- Distinguish requirement, assumption, prediction, calculation, simulation, integration observation, and validated result. Record source, date, conditions, sample basis, limitations, and verification method. Preserve the project's evidence labels; never convert `LIVE_INTEGRATION_ONLY`, `OFFLINE_SYNTHETIC_ONLY`, `PROPOSED_REQUIREMENT`, or `PENDING_REAL_MATERIAL` into performance proof.

## Language patterns

Use concise, client-aware engineering English: concrete subjects and verbs, defined acronyms, consistent units, and calibrated claims. Prefer “the live integration test observed … under … conditions” to unqualified success language. Cite primary sources near the technical claim they support, and make recommendation sentences explicitly refer back to requirements, comparison evidence, risks, and remaining validation work.
