# Week 7 — 离线样本采集与到货准备

本阶段沿用任务 `week6` 中确认的安排：Week 7 完成无新硬件的软件和准备工作，
Week 8 预计到货。Plan A 为 ALC-IMX258 USB 相机；本工作台的图像由合成源生成，
STM32 消息由模拟器生成。所有采集结果标记 `OFFLINE_SYNTHETIC_ONLY`。

## 本周已实现

| 要求 | 实现与可检查的结果 |
|---|---|
| 样本与采集身份 | 操作者的 `sample_id`、独立检查 `session_id`、每次采集 `capture_id`；相同样本标签不会混合不同会话 |
| 12 视图 | 0°、60°、120°、180°、240°、300°，各含 `bright_field` 和 `dark_field` |
| 触发流程 | 选择角度及一种照明并点击采集 → 模拟请求该照明 → 检查就绪 → 取得一帧 → 候选处理 → 保存 → 模拟 OFF 确认 |
| 证据保存 | 每次保存原图 PNG、标注 PNG、帧身份、候选、灯光消息及标定检查；零候选视图同样保存 |
| 缺图和重拍 | 完成要求 12 个当前视图的两种图像都存在；重复采集须显式重拍；保留旧行、旧图和替代关系 |
| 归档与恢复 | 独立 SQLite，重启后可找回样本；完成后锁定；已完成样本缺文件显示 `incomplete_archive` |
| GUI | 双语工作台、角度及照明选择、6 × 2 进度、原图/标注切换、候选、历史、模拟通信记录及 CSV |
| 通信工具 | 有界 JSON、会话/请求关联、递增序号、就绪/材料/参考门控、超时、心跳失效和 OFF 恢复 |
| 标定工具 | 加载模板/档案，检查有效期、撤销和采集条件一致性，保存检查原因；本阶段毫米值始终为空 |
| 硬件准备 | [夹具概念图与到货准备表](docs/week7_hardware_preparation.md)，实物装配及物理标定留给到货后执行 |

## 运行

工作目录：`E:\Claude Code\5105`。使用现有 `.venv` 和前端依赖。

```powershell
Set-Location 'E:\Claude Code\5105'
.\START_RPLA_WEEK7.cmd
```

工作台：<http://127.0.0.1:5177>。离线 API：<http://127.0.0.1:8766/api/week7/health>。
启动器检查端口，已有服务占用时给出错误，不结束不相关进程。
GUI 和 API 均绑定本机回环地址；进程与日志登记在 `data/output/week7_runtime/`。

```powershell
.\STOP_RPLA_WEEK7.cmd
```

也可单独运行 API：

```powershell
.\.venv\Scripts\python.exe -m src.week7_service --port 8766
```

GUI 的手动启动命令见 [GUI README](gui-prototype/README.md)。原连续预览和 Week 4
回放继续通过原入口使用。Week 7 使用单独的显式触发工作台，预览帧不会自动变成样本记录。

## 操作与归档

1. 输入样本标签，例如 `W7-B001-S001`，创建一次检查会话。
2. 选择一个角度和一种照明，点击对应按钮采集一张模拟图。检查该视图的原图和标注图。
3. 每个角度分别采集明场与暗场，共 12 次。已有记录的视图显示重拍操作；重拍保留旧图和记录，另一照明视图不变。
4. 检查全部 12 个视图后完成样本；导出 CSV。完成只表示采集归档齐全。
5. 采集失败时刷新实际归档状态。选择缺图单元格补采对应视图；故障原因及模拟关灯确认进入会话事件。
6. 已完成会话不能重拍。如需新一轮检查，使用相同样本标签建立新会话，以新 `session_id` 区分。
7. 侧栏每个会话都有独立删除按钮。确认弹窗会标明样本和会话，确认后删除该会话的记录、事件及所有原图/标注图；取消不会请求删除。其他会话不受影响。

摄像头目前仅显示“待接入”并提供连接说明；没有探测物理设备的连接状态，也不会申请浏览器相机权限。真实采集需后续接入 Plan A USB 相机与服务。目前的采集按钮明确生成模拟图像。

默认归档目录：

```text
data/output/week7_service/
  week7_samples.sqlite3
  images/<session_id>/<capture_id>/raw.png
  images/<session_id>/<capture_id>/annotated.png
```

数据库的 `samples`、`captures` 和 `sample_events` 通过会话和采集 ID 关联。
CSV 每行对应一次采集尝试，包括重拍前的行及零候选行，并包含图像相对路径和候选 JSON。
一次采集尝试有两张 PNG；12 个视图加一次双照明重拍，共 **14 次采集、28 张 PNG**。
“当前视图”只选每个角度/照明的最新有效尝试。CSV 导出不会删除或替换原始图像。

正常写入失败会撤销该次数据库事务并清理该次新图像。进程或断电中断可能留下未入库目录；
它不会计入完成状态。复制归档时应停止工作台并复制整个目录，保持 SQLite 与图像一起保存。
完整性检查目前核对文件存在性；没有把它描述为图像内容篡改检测或断电恢复验收。

## 接口与模块

| 路径 | 用途 |
|---|---|
| `src/week7/store.py` | 短连接 SQLite、原图/标注归档、重拍及完成规则、会话事件、CSV |
| `src/week7/workflow.py` | 单角度、单照明的 `capture_view`，复用 `FramePacket` 与 `BaselineVisionProcessor`；脚本仍可显式调用双视图兼容方法 |
| `src/week7/protocol.py` | MCU 握手、故障和帧授权的可注入时钟模拟 |
| `src/week7/calibration.py` | 标定档案校验及失效原因 |
| `src/week7_service.py` | 本机 REST API；不启动原 live service 或相机 |
| `src/week7_offline_demo.py` | 一次完整 12 视图和双照明重拍，输出摘要与 CSV |
| `config/week7_offline.json` | 合成图像尺寸、ROI、种子、六角度及两照明的固定配置 |
| `config/week7_calibration.template.json` | 未标定模板，未知值为 `null` |
| `gui-prototype/src/Week7SamplePanel.jsx` | 工作台，通过独立 adapter 使用 API |

主要 API 前缀为 `/api/week7`：

| 方法与路径 | 请求或响应 |
|---|---|
| `GET /health` | 合成来源、单视图采集方式、摄像头接口待接入状态、标定原因、输出禁止状态 |
| `POST /samples` | `{"sample_id":"W7-B001-S001"}` → 新会话 |
| `GET /samples` | `{"samples":[...]}`，包含已保存会话 |
| `GET /samples/{session_id}` | 当前视图、缺图、全部尝试、事件及状态 |
| `POST /samples/{session_id}/capture` | `{"angle_deg":60,"lighting_mode":"bright_field","retake":false}` → 仅采集此视图后的会话；照明字段必填 |
| `DELETE /samples/{session_id}` | 删除指定会话及图像；返回删除数量，若最终文件清理待重试则返回 202 和 `cleanup_pending:true` |
| `POST /samples/{session_id}/complete` | 只在 12 图像对齐全时完成 |
| `GET /samples/{session_id}/export.csv` | UTF-8 CSV 下载 |
| `GET /captures/{capture_id}/{raw\|annotated}.png` | 数据库指向的已保存 PNG |

非法类型返回 422，状态冲突返回 409，未知会话/采集返回 404，归档文件不可用返回 503。
操作者输入的样本标签不拼入文件路径。这里没有连接真实硬件的控制端点。

## 通信与标定边界

模拟协议为一行一个 JSON 对象，最多 4096 字节。命令包含 `session_id`、`request_id`、
`seq`、`lighting_mode`、`angle_deg`；状态还有 `ready`、`material_present`、
`reference_ok`、`fault`、`heartbeat`、`driver_value` 和 `reference_reading`。
接收旧序号、错误关联、错误照明或故障时拒绝采集；三项就绪条件未满足时不取帧。

帧授权要求当前请求已就绪、心跳有效、帧来自就绪之后且该请求尚未授权过帧。
默认就绪超时 2 s、心跳超时 1 s 仅为软件模拟参数，到货后需结合实测协商。
每一分支结束均请求 OFF 并收到模拟确认后才开始下一分支。`outputs_enabled` 始终为 false。
记录里的单调时间是开发主机的模拟时间，不能作为相机曝光时间、真实照明稳定时间或 R4/R5 达标证据。

标定档案需要绑定相机源、图像大小、ROI、镜头、工作距离、照明模式、夹具和样本轴方向，
并带版本、证据引用、验证时间、到期时间及撤销标记。每次采集重新读取档案，避免使用缓存的过期许可。
模板为 `unvalidated`；已有 ID 也不能绕过条件核对。本周模块只验证档案逻辑，
`physical_mm_allowed` 始终为 false，`size_mm` 和 `position_mm` 始终为 null。

## 可重复验证

```powershell
# 全部 Python 回归（现有模块及 Week 7）
.\.venv\Scripts\python.exe -m pytest -q --basetemp=tmp/pytest-week7-full

# 完整合成样本：默认产生新的输出目录
.\.venv\Scripts\python.exe -m src.week7_offline_demo

# 新前端 adapter 与原有证据回归
Set-Location gui-prototype
node --test tests/week7-data-source.test.mjs tests/offline-evidence.test.mjs tests/live-evidence.test.mjs
$env:VITE_INSPECTION_MODE = 'week7'
pnpm exec vite build
Remove-Item Env:VITE_INSPECTION_MODE
```

本轮验证记录：Python **280 passed**；实际测试覆盖身份隔离、12 视图、零候选、重拍、
并发重复、图像/数据库失败补偿、标定过期/撤销/条件变化、JSON 校验、错序/重复消息、
未就绪取帧禁止、旧帧拒收、半角失败恢复以及真实本机 HTTP 路由。

离线演示产物：`data/output/week7_acceptance_final_20260907/`。
其中 `export-dcef90b749fc47cb994d95aa88eadd0f/summary.json` 记录配置、种子、运行时版本、
全部尝试、模拟通信事件及标定状态。示例为 12 个当前视图、14 次采集尝试，状态 `completed`。

前端新旧 adapter 测试 **23 passed**，Week 7 模式 `pnpm exec vite build` 成功。
本机 Chrome 端到端操作通过：创建、缺图时禁止完成、六角度双照明、重拍及旧图、
原图/标注图、完成后锁定、CSV 下载、刷新恢复和中英文切换；1440 px 与 900 px
窗口截图经视觉检查，窄屏无横向溢出。运行时未捕获到页面脚本错误。
浏览器检查结果、CSV 和截图位于 `data/output/week7_browser_20260907/`；
`result.json` 保存该次会话 ID 与检查范围。SVG 概念图也经过本机浏览器渲染检查。
启动器已完成停止/重启检查，重启后同一会话仍为 `completed`，含 12 个当前视图、
14 次采集和 56 条事件。历史证据与报告的 hash 校验通过。

原 `pnpm run build` 的 Vite 阶段可运行；Sites 后处理仍缺 `.openai/hosting.json`，本轮不进行发布。

## Week 8 接续

软件已具备可重放的采集、归档和故障检查入口。到货后仍需确认实际相机模式/控制能力、
Pi 运行、夹具与照明装配、真实串口/STM32 固件、材料存在/照明参考读数以及独立关闭输出的行为。
真实新帧的曝光与照明关联必须用实物采集链验证后接入工作台。
光学标定、真实缺陷性能、R4/R5 耗时和物理安全输出尚无本周实测结论。
