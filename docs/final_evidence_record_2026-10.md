# Final-report evidence record (October 2026)

Measurements and test totals cited in the final design report. Each row states
its evidence level. Code revision: `5d5e68e` unless stated. Raw images and logs
stay on the development host (`data/output/` is not version-controlled).

## 1. Environment

| Item | Value |
|---|---|
| Inspection host | Raspberry Pi 4B, 4 GB; Raspberry Pi OS 64-bit (Debian 13 trixie), kernel 6.18 aarch64 |
| Pi runtime | Python 3.13.5; OpenCV 4.12.0 (pip wheel 4.12.0.88); NumPy 2.2.6 |
| Pi OS packages present on the desktop image | git, libgl1, python3-dev, v4l-utils (no extra apt installs were needed); `pip install -r requirements.txt` used prebuilt aarch64 wheels and took about 1 min |
| Development host | Windows PC (32 threads); Node.js 24.16.0 for the GUI build |
| Camera | ALC-IMX258-LY0001-ZB V1, USB ID 1bcf:28c4, USB 2.0 (480 Mbit/s), UVC, `/dev/video0` on the Pi |

## 2. Camera modes and read throughput on the Pi (2026-10-13)

`v4l2-ctl -d /dev/video0 --list-formats-ext` (MJPG): 3840×2160, 3264×2448,
2592×1944 and 2560×1440 at 30 fps only; 1920×1080 and 1280×720 at 60 fps.

| Test (6–10 s each, service stopped) | Frames/s | CPU | Evidence level |
|---|---|---|---|
| `cv2.VideoCapture.read()` at 3840×2160 MJPG (`scripts/benchmark_static_inspection.py --camera 0 --seconds 10`) | 10.2 (decoded) | one core fully used | bench timing |
| `grab()` only | 30.4 (not decoded) | ≈0% of one core | bench timing |
| `grab()` with `retrieve()` every 5th frame | 30.0 grabbed, 6.0 decoded | 56% of one core | bench timing |

## 3. Inspection timing

`scripts/benchmark_static_inspection.py IMAGE --repeat 3` (median of 3):

| Host / input | Decode | Geometry | Surface | Whole inspection | Evidence level |
|---|---|---|---|---|---|
| Pi 4B, archived 4K L1 | 97 ms | 3295 ms | 1194 ms | 4539 ms | bench timing; 52.5 °C, `get_throttled=0x0` |
| Pi 4B, archived 4K L4 | 98 ms | 3337 ms | 1263 ms | 4676 ms | bench timing |
| Windows PC, 4K (service idle) | ≈20 ms | ≈280 ms | ≈250 ms | ≈0.6 s per frame | bench timing |

Pi live frame with one hand-applied marker dot (`live_scene` captured on the Pi,
2026-10-13): one inspection took 11.9 s, of which three whole-strip
`cv2.dilate` calls took 7.5 s (cProfile). After `surface._dilate` (local
dilation per region, falling back to whole-mask dilation for many regions) the
same frame took 4.5–4.7 s alone and 5.4–5.6 s with an emulated 10 fps
acquisition load. In the running split-preview service with a marked specimen:
`processing_latency_ms` 5655, pipeline 0.18 analyses/s, displayed analysis age
about 6–12 s, CPU temperature up to 73 °C, no throttling.

Acquisition-load emulation on L4 (decode thread at the stated rate plus a 5 fps
preview resize/encode): no load 4.1–4.3 s; unthrottled decode 4.9 s; 5 fps
decode 4.6–4.7 s; 3 fps decode 4.4–4.5 s.

Equivalence of the two speed changes (`cv2.transpose` in geometry; local
dilation in surface): nine 4K captures, including the Pi live frame, produced
identical `to_dict()` results (timing fields excluded) and byte-identical
annotated images before and after each change (offline replay).

## 4. Demonstration specimens (captured 2026-10-12, 0°, bright field)

Offline replay of the archived 4K raw captures with `static-rpla-geometry-6` /
`static-rpla-geometry-surface-8`; demonstration thresholds 0.0025 / 0.0099 on
streak energy are **uncalibrated**.

| Specimen (colour) | Geometry | Median width (px) | Edge spread (px) | Texture MAD | Streak energy | Demonstration result |
|---|---|---|---|---|---|---|
| L1 (white) | valid | 473.6 | 10.2 | 0.00285 | 0.00100 | good |
| L2 (deep grey) | rejected: FOCUS_UNVERIFIABLE | — | 35.0 (limit 30) | — | — | not judged; manual inspection recommended |
| L3 (light grey) | valid | 472.5 | 12.4 | 0.01758 | 0.00699 | moderately rough |
| L4 (green) | valid | 453.7 | 17.1 | 0.02886 | 0.01305 | clearly rough |

The four specimens differ in colour; no same-colour specimens of different
quality were available. L3's texture value differed by 42% between two captures.

## 5. Contamination observations

- Live integration observation (2026-10-12, Windows host): marker-pen dots on a
  specimen were detected on successive preview frames, about two candidate boxes
  per frame.
- Pi live frame (2026-10-13), white L1-type specimen with one hand-applied ink
  mark: one `surface_contamination_candidate` (dark core 84 × 73 px). The same
  frame graded moderately rough (streak energy 0.00333). With the marked section
  cropped off (rows 0–1250), streak energy was 0.00074 (good). Cause: the pale
  ink smear and tail lay outside the 2 s exclusion around the dark core, and the
  ink at the filament edge removed rows from the analysed region, separating the
  tail from the core. Not changed in the algorithm (team decision, 2026-10-13).

## 6. Split preview and remote viewing (Pi, 2026-10-13)

`bash scripts/start-rpla-pi.sh` (`RPLA_SPLIT_PREVIEW=1`, `--host 0.0.0.0`):
health `HEALTHY` with raw frame age 16–117 ms; another computer on the same Wi-Fi
opened `http://<Pi address>:8765/` and showed the unanalysed preview (about 5 new
frames/s, about 40 KB per 960 × 540 frame) and the analysed frame with its age.
Ctrl+C with two MJPEG streams open: exit in 2.9 s with
"Application shutdown complete" (camera released). Live integration observation.

## 7. Software verification at `5d5e68e`

- `python -m pytest -q`: 554 passed, 1 skipped (automated software tests).
- `node --test` evidence/adapter suites in `gui-prototype`: 48 passed; Vite
  build passes.

## 8. Lamp controller and watchdog (Pi, 2026-10-14)

Board identified over SWD as STM32F446 (DBGMCU IDCODE `0x10006421`, 512 KB flash),
i.e. NUCLEO-F446RE. The team's original firmware was read back in full before the
board was reprogrammed with `firmware/stm32_lamp_watchdog` (16 MHz HSI, TIM1 ARR 799
= 20 kHz with 800 duty steps on PA8, heartbeat watchdog, IWDG about 1 s). The Pi runs
the bench scripts over the ST-LINK virtual COM port `/dev/ttyACM0`.

| Test | Result | Evidence level |
|---|---|---|
| `bench/hb_test.py`, 10 scenarios | 10 passed: heartbeat stop → SUSPECT 0.52 s, lamp off 3.56 s; host TIMEOUT → off 3.02 s; 1.2 s stall recovered in 0.28 s without switching off; `HANG` → IWDG reset 1.06 s, restart in FAULT; port closed → lamp off | live integration observation (controller state reports) |
| `bench/pwm_probe.py`, PA8 sampled 2000 times over SWD | high fraction 50.5 % / 20.4 % / 0.0 % for set duty 50 / 20 / 0 % | bench measurement (statistical sampling, not an oscilloscope) |
| `scripts/lamp_watchdog.py` with the inspection service | lamp on 0.12 s after the service answered; service frozen (SIGSTOP) → lamp off 4.8 s later; resumed → on in 0.4 s; service stopped (SIGINT) → client exited within 1.5 s, controller in FAULT | live integration observation |
| Nucleo USB unplugged with the lamp on | lamp went off | team observation |

Direct Ethernet link: the Pi's wired connection runs in NetworkManager shared mode
(`10.42.0.1`); the viewing computer received `10.42.0.135` by DHCP and showed the
live interface. Default lamp duty for inspection is 30 %.
