# rPLA Live Inspection Service

## One-click use

1. Power the XIAO ESP32S3 Sense camera and connect the computer to the same network.
2. Do not start the ESP32 CameraWebServer preview. The Python service must be the only direct MJPEG client.
3. Double-click `START_RPLA_LIVE.cmd` in the project root.
4. Wait for the browser to open `http://127.0.0.1:5173/`.
5. Double-click `STOP_RPLA_LIVE.cmd` when the test is finished.

The launcher does not require a global `pnpm` installation. It uses a system Node.js executable when available and otherwise uses the Node.js runtime bundled with Codex.
The selected live profile is fixed at `SVGA` (800×600). Normal one-click use does not perform or request any further resolution selection.

If the camera IP changes, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-rpla-live.ps1 -CameraIp 192.168.1.50
```

## Runtime architecture

```text
ESP32 OV3660 MJPEG (one client)
              |
              v
Resident Python inspection service :8765
  - configurable camera resolution; SVGA default
  - camera reconnect and recovery gate
  - material-presence gate
  - continuous candidate processing
  - SQLite candidate persistence
  - REST health/events/latest-frame API
  - shared MJPEG output
  - WebSocket snapshot updates
              |
              v
React GUI :5173
```

## Current physical-validation boundary

The service and GUI connection are live. The material-presence gate and bright-region baseline are configurable prototypes. The default gate requires a dark target through 80% of the ROI height so a nearby hand or partial background object does not start inspection. Thresholds, ROI, lighting, focus, false-positive rate, accuracy, calibration and physical measurements must be tuned and validated again with the real rPLA material. No actuator output is enabled.

## Live path verification

- `python src/measure_live_latency.py` measures a reversible physical-camera control transition through OV3660, Wi-Fi MJPEG, Python processing, and API JPEG publication. It restores the original brightness in all cases.
- `scripts/test-real-network-fault.ps1` performs a scoped Windows firewall fault test, verifies fail-safe state and recovery, and removes its rule in a `finally` block. It requires an elevated PowerShell session.
- The GUI displays `Post-decode-to-GUI latency`. This begins when OpenCV has received a decoded frame; it is not a sensor exposure timestamp.
- Results from 2026-08-11 are documented in `LIVE_PATH_TEST_RESULTS_2026-08-11.md`.

## 一键使用

1. 给 XIAO ESP32S3 Sense 摄像头上电，并让电脑连接同一网络。
2. 不要启动 ESP32 CameraWebServer 的视频预览；Python 服务必须是唯一的相机流客户端。
3. 双击项目根目录中的 `START_RPLA_LIVE.cmd`。
4. 等待浏览器自动打开 `http://127.0.0.1:5173/`。
5. 测试结束后双击 `STOP_RPLA_LIVE.cmd`。

启动脚本不再要求系统全局安装 `pnpm`；它会优先使用系统 Node.js，找不到时自动使用 Codex 自带的 Node.js 运行环境。
默认实时档位为 `SVGA`（800×600）。需要测试其他档位时，可运行 `START_RPLA_LIVE.cmd -Resolution VGA`，或将 `VGA` 替换为 `XGA`、`SXGA`、`UXGA`、`QXGA`。

当前服务和 GUI 已经实时连接。默认门控要求深色目标连续覆盖 ROI 高度的 80%，防止手或局部背景物体误启动检测。材料存在门控、ROI、亮度阈值和候选算法仍需要在真实 rPLA 线材到达后重新标定；目前不会启用执行器输出，也不能把候选区域当成已经验证的真实缺陷。
