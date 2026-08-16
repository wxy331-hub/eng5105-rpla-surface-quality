# Artifact Check

## Submission-facing artifacts

| Artifact | Language | Format | Status |
|---|---|---|---|
| `ENG5105_Proposal_Design_Report_EN.md` | English | Markdown text | Final manuscript source |
| `ENG5105_Proposal_Design_Report_ZH.md` | Chinese | Markdown text | Final manuscript source |

No `.docx`, `.pdf` or `.tex` manuscript was generated. Mermaid figures remain fenced source diagrams and must be rendered when the user later typesets the submission.

## Verification artifacts

| Artifact | Purpose | Status |
|---|---|---|
| `validate_paired_reports.py` | Citation, structure, equation, reference, URL, evidence-label and critical-number parity | PASS |
| `humanize_matrix.md` | Teaching record of targeted medium-tier style revisions | Complete, 53 rows |
| `humanize_report.md` | Official checker output | PASS, but Markdown paragraph discovery is 0 and therefore not relied on alone |
| `markdown_humanize_stats.py` | Markdown-aware sentence-rhythm diagnostic | EN and ZH both have zero similar-length triples |
| `writing_rationale_matrix.md` | Paragraph-level purpose, evidence and rubric rationale | Finalised |
| `logic_transfer_audit.md` | Confirmed decision-spine transfer | PASS |
| `citation_quality_audit.md` | Source-mix and claim-use review | Updated for the 49-reference final list, including nine unpublished project records |
| `citation_submission_scope_audit.md` | Report-only citation and path-dependency audit | PASS: zero body file/path references and zero citation orphans |
| `structured_review.md` | Rubric-facing readiness review | Complete |
| `integrity_audit.md` | Claim, citation, evidence and safety audit | PASS with disclosed limitations |

## Non-submission process artifacts

Files named `draft_*`, `citation_candidates_*`, `citation_support_bank.md`, `claim_register.md`, `evidence_bank.md`, `figure_asset_map.md`, `selected_references.md`, `section_blueprints.md`, `research_dossier.md` and `sota_gap_map.md` are research or drafting records. Where they differ from the final reports, the final reports and their Appendix A are authoritative.
