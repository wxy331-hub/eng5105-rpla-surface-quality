# ENG5105 Project Instructions

Project-specific rules for this repository. The workspace `CLAUDE.md` one level
up still applies; this file adds only what is particular to ENG5105 and does not
restate the general working method, verification or Git rules from there.

User-facing setup, architecture and command documentation lives in `README.md`.
This file covers agent behaviour and the constraints that are easy to violate.

## Working copy

`E:\Claude Code\5105` is the authoritative working copy. A historical copy exists
at `D:\12591\Documents\5105`; do not read it, diff against it, or edit it. If a
question seems to need that copy, ask instead.

## What this project is

A proposal-stage machine-vision monitor for visible surface anomalies on moving
rPLA filament, for the ENG5105 Integrated Design brief. Plan B (supplied ESP32S3
/ OV3660, Raspberry Pi 4, STM32 Nucleo-L432KC) is the sole implementation path.
Plan A is a report comparator only and is never built, purchased or tested.

Requirement priority: assignment brief and discipline-specific content, then the
Electrical Teams rubric, then required interfaces and formats, then this file,
then existing implementation.

## Hard constraint: hash-anchored files

Appendix A of the proposal report records a SHA-256 for nine internal evidence
records, and `final_artifact_manifest.md` records one for each report. Eleven
files are marked `-text` in `.gitattributes` for this reason:

```
ENG5105_Proposal_Design_Report_EN.md      config/live_service.json
ENG5105_Proposal_Design_Report_ZH.md      src/live_service.py
RESOLUTION_TEST_RESULTS_2026-08-11.md     src/week3/vision.py
LIVE_PATH_TEST_RESULTS_2026-08-11.md      data/output/latency/latency_20260811.json
WEEK3_OFFLINE_IMPLEMENTATION.md           data/output/network_fault/network_fault_20260811.json
WEEK4_OFFLINE_IMPLEMENTATION.md
```

Never remove those `-text` markers: end-of-line normalisation rewrites the bytes
and silently invalidates every recorded hash.

**Changing any of these files is a four-part change, all in the same pass:**

1. Make the edit.
2. Recompute the file's SHA-256.
3. Update Appendix A in **both** reports, and `final_artifact_manifest.md` if a
   report itself changed.
4. Re-run `validate_paired_reports.py`.

Skipping step 3 leaves the report asserting a hash that no longer resolves, which
is exactly the traceability claim the report is built on.

## Evidence discipline

This is the core value of the project and the easiest thing to break.

- Every result carries an evidence label: `OFFLINE_SYNTHETIC_ONLY`,
  `OFFLINE_FAULT_INJECTION_ONLY`, `LIVE_INTEGRATION_ONLY`,
  `PENDING_REAL_MATERIAL`, `PROPOSED_REQUIREMENT`, `PROPOSED_INTERFACE`.
  Their counts are checked for parity between the two reports.
- **Never upgrade an evidence level because code improved.** Wiring a control in
  makes it "implemented on the development host and unit-tested" — never
  "verified". Pi deployment, network-load behaviour and physical performance
  require new dated evidence.
- Historical observations stay as recorded. If a past run lacked instrumentation,
  say so in the past tense rather than rewriting what it showed.
- `size_mm` and `position_mm` stay `null` without a `calibration_id`; this is
  enforced in `DetectionRecord.__post_init__` and must not be relaxed.
- `confidence` is an uncalibrated area-derived ranking score. Do not describe it
  as a probability, and do not let `quality_grade` authorise rejection.
- Do not fabricate measurements, timings or accuracy figures. The observed
  10.77 FPS SVGA result is below the proposed 20 FPS target and must not be
  presented as compliant.

## Changing code changes the report

Sections 5–6, the requirement tables, the API table, the evidence tables and the
risk register all describe the current state of the software in specific terms.
Modifying the service will make some of those sentences false. Grep both reports
for the affected behaviour and update them in the same change, then re-validate.

## Bilingual report parity

`validate_paired_reports.py` is the gate. It enforces identical citation
sequences, 49 reference entries, URLs, nine display equations, Tables 1–20,
Figures 1–3, evidence-label counts, SHA-256 values and critical numeric tokens.

It also rejects:

- English connectives: firstly, secondly, finally, furthermore, moreover,
  additionally, in conclusion, it is worth noting.
- Chinese connectives: 首先、其次、再次、最后、综上所述、总而言之、此外、另外、
  不仅如此、值得注意的是、需要指出的是.
- Untranslated leftovers in the Chinese body: `Week 3/4/5`, `Thursday`,
  `Section 5.3`, `360-degree`, `processed frames/s`.

The two reports are not sentence-aligned translations; some paragraphs exist in
only one language. Match meaning and the checked invariants, not sentence count.

## Commands

```bash
.venv/Scripts/python.exe -m pytest                                   # full suite
.venv/Scripts/python.exe paper_rewriting_output/validate_paired_reports.py
```

`pytest.ini` pins `--basetemp=tmp/pytest`; the tracked `tmp/.gitkeep` must stay,
because pytest creates the leaf directory but not its parent.

The camera path needs the ESP32 powered and its CameraWebServer preview closed —
the Python service must be the only direct MJPEG client. See `README.md` for
launch commands.

## Module boundaries

- `src/week3/` holds source-independent contracts. Camera adapters depend on it;
  it depends on no adapter. Keep it that way.
- `src/week4/camera.py` owns connection policy and the one-slot buffer.
- `src/live_service.py` runs acquisition and inspection on separate threads. The
  acquisition thread must not touch SQLite — it queues events for the processing
  thread, which owns the repository connection.
- Tests stay hardware-free through injected `capture_factory` / `source_factory` /
  `opener`. Preserve that injection when adding code.

## Submission

Assessed against the Electrical Teams Proposal Report rubric: Executive Summary
and Acknowledgement of Country 5%, Background/Literature/Stakeholders 10%,
Concept Description 10%, Functional Details 25%, Environmental/Safety/Ethical 5%,
Bill of Materials 5%, Project Plan and Conclusions 20%, Figures and Tables 5%,
Grammar 5%, References 5%, Report Structure 5%.

Known gaps, all requiring either team action or format work:

- The risk register uses single-axis ratings. The discipline-specific brief asks
  for its Probability × Harm severity matrix (Certain…Eliminated × Negligible…
  Catastrophic). Not yet applied.
- No dated stakeholder consultation record exists; the report says so rather than
  inventing one. Do not fabricate consultation outcomes to fill this.
- The Acknowledgement of Country uses University-wide wording because the exact
  campus was never supplied.
- Team member names and headshots are placeholders `M1`–`M6`.
- Deliverables are Markdown only. Mermaid figures and LaTeX equations still need
  rendering for a typeset submission.
