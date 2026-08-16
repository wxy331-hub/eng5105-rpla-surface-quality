# Citation Compliance Report: Report-Only Submission Scope

## Summary

| Metric | Result |
|---|---|
| Citation style | IEEE numeric, order of first appearance |
| Final reference entries | 49 in each report |
| Expanded in-text citation uses | 169 in each report |
| Orphan in-text citations | 0 |
| Orphan references | 0 |
| Project filenames in manuscript body | 0 |
| Absolute or project-root-relative paths in manuscript body | 0 |
| Internal unpublished records formalised in References | 9 |
| English/Chinese reference and URL parity | PASS |

## Corrections made

| Location | Previous issue | Correction |
|---|---|---|
| Executive Summary, Sections 5–6 and project plan | Claims named local Markdown, JSON or Python files or referred to Appendix A paths | Replaced body filenames and paths with normal numbered citations |
| Evidence table | Row labels depended on local filenames | Replaced them with descriptive record titles and reference numbers |
| Appendix A | Required the reader to resolve `D:\12591\Documents\5105` and project-relative paths | Reframed the appendix as a self-contained provenance register; the report reproduces the relevant values and limitations |
| References | Internal evidence was absent from the numbered list | Added nine `ENG5105 Project Team` unpublished technical/configuration/code/data records, including source filenames for provenance |
| Entire reference list | New records initially disrupted order-of-appearance numbering | Renumbered all citations and references deterministically; first-use order now runs contiguously from 1 to 49 |

## Internal-record references

The formal internal records are [6], [36], [37], [39]–[44]. They have no DOI or public URL because they are unpublished team records. This does not create a hidden dependency: Sections 5–6 and Appendix A reproduce the values, conditions, limitations and SHA-256 identifiers used by the proposal decision. The reference entries retain the original filenames only so the team can identify the source record if requested later.

## Compliance judgement

PASS for a report-only submission. The assessor can follow every material argument from the submitted report; access to the full code repository or project folder is not assumed.
