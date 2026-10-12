# Week 8：摄像头接入与到货验收

本阶段依据任务 `week7` 及此前确认的周计划：Week 8 完成到货验收、稳定成像、
原始试拍和重启恢复准备。正式光学/传感标定在 Week 9；开发集调参与 STM32
整机联调在 Week 10；独立性能和长时间记录完整性验证在 Week 11。

当前交付为可连接真实 USB 相机的软件与验收工具。未执行 ALC-IMX258 实机拍摄、
Pi 部署、夹具制作或照明/供电实测。最终报告原文件及历史证据保持独立。

## 软件链路

```text
ALC-IMX258 USB/UVC
  → 单一 InspectionRuntime 相机读取线程
     → 连续候选处理 → REST / WebSocket / 共享 MJPEG → 检测 GUI
     → 触发请求后的新原始帧 → 单视图处理与归档 → 样本采集 GUI
```

两条路径共用一个摄像头连接。预览不会自动写成样本视图，采集操作每次只保存
所选角度、所选照明的一张原图和一张标注图。六角度 × 两照明仍需十二次采集。
重拍保留原尝试；完成锁定、缺图入口、单会话删除和 CSV 导出继续可用。

新帧检查以主机读帧时间、递增序列和连接代数为依据。连接代数用于区分重连前后的
两次设备连接；拍摄请求遇到断连、旧帧或代数变化时会失败，保存前再次检查。
主机收到的新帧不等于传感器曝光触发已同步，USB 驱动缓冲和曝光时刻仍需实机确认。

照明与人工分度由操作者设置，点击采集即记录所选值。元数据标明
`operator_declared` 和 `sensor_confirmed=false`；没有生成模拟 READY/OFF
作为实物照明确认。毫米值保持 `null`，物理输出保持禁止。

## Windows 启动

工作目录为 `D:\12591\Documents\5105`，沿用项目 `.venv` 和已安装的前端依赖：

```powershell
Set-Location 'D:\12591\Documents\5105'
.\START_RPLA_WEEK8.cmd -CheckConfig
.\START_RPLA_WEEK8.cmd -CameraDevice 0 -CameraBackend dshow -Resolution UHD
```

GUI：<http://127.0.0.1:5177/#sample-capture>。接口：
<http://127.0.0.1:8765/api/week7/health>。`/api/week7` 是延续的内部接口路径；
它的 `mode=plan_a_camera` 与相机状态决定实际行为，GUI 使用功能名称。

`UHD` 请求为 3840 × 2160 / MJPG / 30 FPS；`FHD` 请求为 1920 × 1080。
请求参数、驱动报告值和实际解码图像尺寸分开记录。模式不匹配会阻止采集，
不会自动缩放图像或降级模式。设备索引由当前操作系统枚举决定，索引 0 不保证
是 ALC-IMX258；连接前核对设备型号和预览。`auto`、`dshow`、`msmf` 的可用性
以本机 OpenCV 和设备驱动为准。

在硬件未到货、或电脑只有内置摄像头时，可先启动等待状态：

```powershell
.\START_RPLA_WEEK8.cmd -WaitForCamera
```

此时服务与 GUI 可用，启动时不打开设备。接入并核对所配设备后，在 GUI 点击
连接/重连；如设备索引需调整，先停止，再带正确 `-CameraDevice` 启动。
没有有效新帧时禁止采集，界面不使用合成图填充。

```powershell
.\STOP_RPLA_WEEK8.cmd
```

启动器不结束占用端口的其他服务；停止脚本核对记录的 PID 和进程启动时间。
若旧 Week 7 GUI 占用 5177，先使用其停止入口，再运行新入口。

## 数据保存与旧归档

新相机服务使用独立目录：

```text
data/output/week8_service/
  live_inspection.db                 连续候选处理记录
  week8_samples.sqlite3              触发样本归档
  images/<session_id>/<capture_id>/raw.png
  images/<session_id>/<capture_id>/annotated.png
```

旧合成归档继续保存在 `data/output/week7_service/`，从显式
`START_RPLA_WEEK7.cmd` 入口查看；停止相机 GUI 后再启动该入口。不将合成视图
混入真实相机会话，也不原地迁移或重新标记旧图像。新的会话冻结采集和处理配置；
设备、模式或算法配置变化后需新建会话。

真实设备路径的记录属于 `LIVE_INTEGRATION_ONLY`；测试注入源属于
`OFFLINE_FAULT_INJECTION_ONLY`，合成回放属于 `OFFLINE_SYNTHETIC_ONLY`。
这些标签均不表示 rPLA 缺陷性能、照明稳定性、分度准确度或毫米标定已通过。

## 到货观察工具

相机服务启动后，从同一服务只读采样，避免第二个进程占用相机：

```powershell
.\.venv\Scripts\python.exe scripts/record_camera_readiness.py --duration 30
```

默认读取 8765 的相机健康接口。每次在 `data/output/week8_camera_readiness/`
创建新目录，保存 `observations.jsonl` 与 `summary.json`。记录连接变化、请求模式、
可获得的实际尺寸、驱动报告值、计数与采样错误。默认 30 秒，上限 300 秒。
HTTP 采样存在空档或连接代数/计数重置时，不将跨越该区间的计数解释为连续帧率。

这项检查用于短时连接观察；不检查每一个传感器帧，也不构成 R7 的 30 分钟
事件数据库/图像完整性验收。原始成像试拍由样本采集台单独完成。

## Raspberry Pi 接入准备

以下是待在 Pi 上执行的步骤，当前没有 Pi 运行证据。进入 Pi 的项目目录，使用
Python 3.11+ 和该机的隔离环境安装项目依赖，确认摄像头设备及可用模式。
选择稳定的 `/dev/v4l/by-id/...` 路径或明确的 `/dev/videoN`，不要将 Windows
设备索引直接视为 Pi 的设备身份。

```bash
RPLA_CAMERA_DEVICE=/dev/video0 RPLA_CAMERA_BACKEND=v4l2 RPLA_RESOLUTION=UHD \
  .venv/bin/python -m src.week8_service --source-type usb_uvc --port 8765
```

服务绑定回环地址。可在 Windows 保留 GUI，通过 SSH 转发访问 Pi 的同一 API：

```powershell
ssh -L 8765:127.0.0.1:8765 <用户名>@<Pi地址>
```

先停止 Windows 上占用 8765 的相机服务。在另一个终端只启动前端：

```powershell
Set-Location 'D:\12591\Documents\5105\gui-prototype'
$env:VITE_INSPECTION_MODE = 'service'
$env:VITE_INSPECTION_API_URL = 'http://127.0.0.1:8765'
$env:VITE_SAMPLE_API_URL = 'http://127.0.0.1:8765'
pnpm exec vite --host 127.0.0.1 --port 5177 --strictPort
```

USB 供电、总线带宽、模式支持、相机参数锁定、长读帧阻塞及恢复时延都需要在
Pi 实际配置上验证。正式硬件记录填写 [到货验收表](docs/week8_incoming_acceptance.md)。

## 可重复软件检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
Set-Location gui-prototype
pnpm run test:evidence
pnpm run build
```

测试结果和浏览器检查范围见 [当前进度](CURRENT_PROGRESS.md)。测试注入、构建和
浏览器布局检查与实机验收分别记录。
