# Final Integrity Audit

## Result

Pass with disclosed external-input limitations.

## Claim integrity

- Proposed thresholds are labelled `PROPOSED_REQUIREMENT`; they are not described as client-approved or measured.
- Windows-development evidence is not presented as Raspberry Pi deployment, STM32 wiring, safe-output validation or production-line performance.
- Synthetic and non-rPLA tests do not support rPLA defect-accuracy claims.
- The observed 10.77 FPS SVGA result remains below the proposed 20 FPS requirement and is not hidden by the recommendation.
- Physical dimensions, calibrated units, per-class accuracy, supply-current measurements and automatic rejection authority remain gated.
- No stakeholder consultation outcome, Traditional Owner identity, team name or headshot was invented.

## Citation and bilingual integrity

- Numeric references follow contiguous first-use order 1–49 in both reports.
- Both reports contain 49 identical reference entries and URLs.
- The paired validator expands 169 citation uses in each report.
- Nine internal project records are formally listed as unpublished references; their decision-relevant results and limitations are reproduced in the report, and no body claim requires the assessor to resolve a project path.
- All nine display equations, Tables 1–20, Figures 1–3, evidence labels, critical values and SHA-256 strings pass parity checks.
- Peer-reviewed results are used for design implications and comparison, not as substitute measurements for this project.

## Internal evidence integrity

Appendix A identifies IE1–IE9 by title/date, project-root-relative path and SHA-256. The two raw JSON traces are registered separately. Current evidence supports development-path and integration observations only within the limits stated in Section 6.

## Safety and electrical integrity

- MCP3208 VDD/VREF and Pi-facing SPI are specified at 3.3 V; the analogue output must be scaled or clamped to the ADC range.
- Encoder NPN open-collector outputs use 10 kΩ pull-ups to the STM32 3.3 V rail.
- The development API readiness flag is explicitly not actuator authorisation.
- Release use of hard deletion is forbidden; release records require auditable retention or tombstoning.
- G5 prevents safe-output authority until wiring, watchdog, fault-state and end-to-end tests pass.

## Same-date software revision

A code review on the evidence cut-off date found that several controls the report
described as pending were still absent from the resident service. They were
implemented and the report was updated in the same pass:

- The one-slot frame buffer, frame-age watchdog and recovery gate are now
  instantiated by the service on a separate acquisition thread; `dropped_frames`
  reports a real discard count instead of a constant zero.
- The detection store enables SQLite foreign-key enforcement, so a detection
  cannot reference a batch that was never opened.
- Hard deletion writes a `DETECTION_RECORDS_DELETED` audit event naming the
  requested identifiers before the rows are removed.
- The uncalibrated area-to-score and grade constants are named and documented as
  heuristics that authorise no rejection.

Evidence level is unchanged. These are development-host software results covered
by threaded unit tests; no Pi-deployment, network-load, physical or defect-accuracy
claim was added, and the recorded 10.77 FPS observation was not revisited. The
Appendix A hashes for the configuration, resident-service and vision records were
recomputed accordingly; the other six internal records were verified as unchanged.

## Known limitations

The integrity result does not certify future material tests, calibration, procurement availability, stakeholder approval or final typesetting. Those states can change only through new dated evidence.
