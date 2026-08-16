# rPLA Surface Quality Monitor

An English-first, bilingual GUI for the ENG5105 recycled PLA filament surface-inspection project.

The final selected architecture is Plan B: an ESP32S3 OV3660 camera sends SVGA
800x600 MJPEG video to a Raspberry Pi 4, which hosts the Python inspection service,
API/WebSocket layer, SQLite database, and GUI. An STM32 provides the encoder,
watchdog, lighting, and safe actuator I/O. Plan A global-shutter hardware is not part
of the implementation because the required camera materials are not being supplied.

## What the prototype demonstrates

- Replay of the reproducible Week 4 offline connection-fault scenario
- `CONNECTING`, `HEALTHY`, `STALE`, `DISCONNECTED`, and `RECONNECTING` states
- Safety gating, three-frame recovery, latest-frame buffering, and backlog discard evidence
- Three SQLite-backed candidate records with pixel bounding boxes and algorithm scores
- Read-only acquisition policy and evidence limitations
- English and Simplified Chinese interface switching from the top bar
- CSV export that uses only fields supported by the offline data contract
- A resident Python camera/detection service with API/WebSocket integration
- Adapter contracts for the pending Raspberry Pi deployment and STM32/encoder/safe-output integration

> The public build is offline software evidence. A separate local mode can display the captured Week 4 OV3660 integration evidence without publishing camera files. Neither mode claims validated rPLA defect performance.

## Local development

```bash
pnpm install
pnpm run dev
```

### Local OV3660 evidence mode

The public build remains the offline demonstration. To review the locally captured Week 4
OV3660 integration evidence without committing camera files, run:

```powershell
pnpm run dev:live
```

This copies the current `data/output/week4_live` summary, detections, raw frame and latest
annotated frame into the ignored `public/live-evidence/` directory before starting Vite in
`live` mode. The interface labels these records as unvalidated scene candidates, not rPLA
defects.

## Production checks

```bash
pnpm run build
pnpm run test:evidence
pnpm run test:sites
```

GitHub Pages is deployed automatically from `main` by `.github/workflows/deploy-pages.yml`.
