# Design QA — Recorded-candidate evidence selection

## Comparison target

- Source visual truth:
  - `C:\Users\12591\AppData\Local\Temp\codex-clipboard-8de8c239-fbdf-43e2-b21b-9c8676553624.png` (864 × 327)
  - `C:\Users\12591\AppData\Local\Temp\codex-clipboard-8ddfaa31-1b5a-4550-9849-70420d84e6e6.png` (1500 × 594)
- Implementation: local Vite preview at `http://127.0.0.1:4173/`
- Intended viewport: desktop dashboard at 1500 px width, device scale factor 1.
- State: Simplified Chinese, frame 2 / 5 / 6 candidate rows selected in turn, then return to fault replay.
- Density normalization: the two source screenshots were opened at native pixel dimensions. No implementation normalization was possible because the managed browser runtime could not create its required local assets.

## Findings

- [Blocked] Browser-rendered interaction evidence is unavailable.
  - Location: Recorded candidates table and Inspection evidence replay panel.
  - Evidence: both source screenshots opened successfully, the local preview responds with HTTP 200, but the managed browser runtime failed before it could open or capture the implementation.
  - Impact: visual fidelity, row-click interaction, selected-state labels, image crop, and Chinese wrapping cannot receive a browser-level comparison pass.
  - Required check: select frames 2, 5, and 6 and verify that the image changes respectively to `frame_0002.jpg`, `frame_0005.jpg`, and `frame_0006.jpg`; verify the selected image stays pinned until Return to fault replay is pressed.

## Required fidelity surfaces

- Fonts and typography: existing Inter / IBM Plex Mono tokens are preserved; the new bilingual labels still require rendered clipping and fallback-font inspection.
- Spacing and layout rhythm: no grid geometry was changed; selected-record copy reuses the existing badge, footer, and control rows. Rendered overflow remains unchecked.
- Colors and visual tokens: the selected-record badge reuses the established amber caution palette and dark panel tokens. Browser contrast remains unchecked.
- Image quality and asset fidelity: no asset was generated or approximated. Each record resolves directly to its existing annotated Week 4 JPEG.
- Copy and content: English and Simplified Chinese strings exist for selected record, saved-frame viewing, return to replay, and row accessibility labels.

## Full-view comparison evidence

- Both supplied source screenshots were opened successfully.
- No browser-rendered implementation screenshot is available, so a valid combined comparison could not be produced.

## Focused region comparison evidence

- Required focus regions: the three candidate rows, the top-left replay/selected badge, saved-frame label, lower-right selected record ID, and return-to-replay control.
- Focused implementation screenshot unavailable.

## Interaction checks

- Record-to-image mapping: automated test passed for frames 2, 5, and 6.
- Clear-selection fallback to replay image: automated test passed.
- Keyboard activation with Enter/Space: implemented; browser verification pending.
- Production build: passed.
- Sites packaging and Worker tests: passed.
- Local preview response: HTTP 200.
- Browser console errors: unavailable.

## Comparison history

- Iteration 1: record-specific evidence pinning, selected-state presentation, bilingual copy, return-to-replay behavior, and keyboard row activation implemented.
- Iteration 1 blocker: managed browser runtime could not create its required assets, so the rendered comparison and interactive visual pass could not be completed.

## Implementation checklist

- Capture the dashboard at 1500 px width in Chinese.
- Click frame 2, frame 5, and frame 6 and confirm the image, frame number, record ID, and candidate detail panel change together.
- Leave a record selected while the timeline advances and confirm the image stays pinned.
- Press Return to fault replay and confirm automatic replay presentation resumes.
- Repeat one selection in English and check wrapping, focus outline, and browser console.

final result: blocked
