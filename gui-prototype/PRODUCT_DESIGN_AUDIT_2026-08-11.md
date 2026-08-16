# Product Design audit — live inspection and system health

## Audit scope

- Surface: local rPLA live inspection dashboard and System Health page.
- User goal: understand whether inspection is ready, whether candidates are being found, and whether the camera/data path needs attention.
- Evidence: the three GUI screenshots supplied on 2026-08-11 and the corresponding React/CSS implementation.

## Findings

### 1. Live inspection metrics

Health: needs simplification.

- Cumulative received frames and inspection-frame counts do not support an operator decision.
- Six equal KPI cards give low-value counters the same prominence as connection and pipeline rate.
- Keep connection, pipeline rate, candidate events, and post-decode-to-GUI latency.

### 2. Repeated live-page health strip

Health: redundant.

- Recovery frames, latest-only buffer policy, and skipped-frame counters are engineering diagnostics.
- The same concepts already belong on System Health, so the repeated strip adds height without improving the live task.
- Remove the strip from Live Inspection and retain the values behind a technical-details disclosure on System Health.

### 3. System Health page

Health: structurally sound but overly technical.

- Six equal cards obscure the three questions that matter: is the camera available, is inspection running, and is the data service ready?
- Acquisition settings and safety rules create a dense upper half followed by a large empty canvas.
- Use three primary status cards, one horizontal safety-policy panel, and a collapsed technical-details section.

## Accessibility considerations

- The technical-details section uses native `details` and `summary`, preserving keyboard activation and semantic expanded/collapsed state.
- Status remains available as text and is not communicated by colour alone.
- Responsive layouts reflow the four KPI cards and technical details to two columns and then one column.
- Screenshot evidence cannot confirm screen-reader announcements, browser zoom behaviour, or every focus style; those require interactive accessibility testing.

## Implemented result

- Live KPIs reduced from six to four.
- Live-page health strip removed.
- Inspection summary no longer repeats received/processed frame totals.
- System Health reduced to Camera, Inspection, and Data service overview cards.
- Recovery, buffer, ROI, resolution, source, and discarded-frame diagnostics moved into a collapsed Technical details section.
- English and Simplified Chinese strings remain complete.
