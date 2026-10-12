# 当前开发进度 · 2026-09-08

2026-09-08 已按整仓检查结论完成九项问题修复，以及超时参数、历史工具入口和
未使用前端依赖/代码的整理。默认目录为 `D:\12591\Documents\5105`。
逐项结果、回归覆盖和复现命令见 [检查后修复记录](docs/code_review_fixes_20260908.md)。

## 已实现

- Plan A ALC-IMX258 USB/UVC 适配器与 Plan B MJPEG 适配器共用帧和服务接口。
- GUI 默认连接 Plan A 真实摄像头服务。主检测、健康、共享预览和样本采集台
  使用同一驻留进程与同一个相机读取源；合成模式通过显式离线入口保留。
- 每个样本含六个角度、两种照明，共十二个视图；选择角度和照明后，单次请求
  等待请求之后的新相机帧。未连接、旧帧、恢复中与服务断开时禁止采集。
- 每次采集保存原图、标注图、候选、人工照明/角度声明和标定状态；重拍保留历史。
  已完成会话锁定，旧配置归档保持其原始尺寸并阻止混采。
- 每个会话可单独确认删除；文件清理失败可恢复和重试。界面显示目标视图、
  保存反馈及缺图入口，并提供中英文与移动端布局。
- 相机与样本接口已接入；连接说明展示设备索引、backend 与型号核对边界。
  `-WaitForCamera` 可先启动服务与 GUI，点击连接后才打开所配设备。
- 新帧序列、连接代数与保存前检查阻止旧帧跨重连入库。最终检查和数据库提交
  共用短临界区；图像编码/写盘不阻塞相机读取。断连时移除实时图，保留已存图。
- 到货短时观察工具记录同一 API 的原始 JSONL 和摘要，不另开摄像头；
  Windows/Pi、模式/参数锁定、装配和重启恢复验收表已准备。

## 当前边界

最终报告以用户于 2026-09-07 确认的
[Proposal Design Report.pdf](paper_rewriting_output/final/Proposal_Design_Report.pdf)
为准：54 页，封面及第 5.2 节明确采用 **ALC-IMX258-LY0001-ZB V1**。
原文件完整保留，校验信息与版本核对记录见
[最终报告说明](paper_rewriting_output/final/README.md)。此前双语 Markdown/DOCX
与其重建工具保留为历史稿，旧哈希和 Plan B 证据快照继续独立校验。

当前采集台遵循用户确认的单视图操作：明场与暗场分别点击采集，共十二个视图。
这是实现阶段的交互调整；最终 PDF 中单次触发串行双场的叙述原样保留。

3840 × 2160 / MJPG / 30 FPS 是相机请求配置。请求值、驱动报告值与实际接受的
图像尺寸分别记录。软件测试和 GUI 控件不能证明实物相机性能、照明、定位或
缺陷识别效果。毫米尺寸与位置保持空值，物理输出保持禁止。

本机设备枚举只识别到 Integrated Camera，尚未确认 ALC-IMX258 到货。
本轮常用 GUI 使用等待连接启动，不拍摄内置相机。真实相机取帧代码及无硬件
故障注入测试已完成；ALC 实拍、Pi 运行、参数锁定、光学与传感标定仍待实机执行。
照明当前由操作者手动切换，记录 `operator_declared`，不生成模拟硬件确认。

Week 8 范围为到货验收和稳定成像；正式标定按已确认计划在 Week 9 开展。
完整软件行为与待执行硬件项目见 [Week 8 实施说明](WEEK8_IMPLEMENTATION.md)
及 [到货验收表](docs/week8_incoming_acceptance.md)。

本仓库同步源码、测试、正式文档、合成回放资源与必要的历史基线。
用户采集数据库、图像归档、运行日志、临时浏览器脚本与渲染缓存留在开发主机，
不属于 Git 跟踪内容。GitHub 源码更新不代表采集服务已部署上线。

## 验证

- 2026-09-08 最终完整 Python 回归：**405 通过、1 跳过**（47.57 秒）。跳过项沿用 Windows
  符号链接创建条件；原断言未修改。该结果是自动化软件验证。
- 前端证据/适配器 **44 项通过**，Vite 静态构建通过（4.05 秒）。覆盖服务默认值、
  无相机尺寸、WebSocket 断开与异步重连、旧帧清除、单视图采集授权。
- WebSocket 每秒状态心跳、空闲连接关闭、无帧 MJPEG 取消与运行时停机退出
  已补回归；四项新用例修复前失败，修复后通过并包含在最终完整回归中。
- 历史报告/证据基线哈希检查通过。采集验证使用独立注入源和独立测试目录。
- 2026-09-07 本地 HTTP + Chrome 已完成十二视图、单视图重拍、断连禁拍/恢复、归档恢复、
  CSV 与检测页清除旧预览；隔离样本共 13 次采集、26 张 PNG，全部带
  `OFFLINE_FAULT_INJECTION_ONLY`。中文 390/1440/2552 px 与英文布局检查通过。
  最新浏览器流程结束后，隔离服务在无相机帧的状态下正常退出。
- 额外 3840 × 2160 注入源检查已成功保存一对原图/标注图，使用单一源连接；
  仅证明当前主机能运行 UHD 软件归档路径，不是设备模式或帧率验收。
- 2026-09-07 操作前后的旧归档核对：当时已有 **2 个会话、24 张 PNG** 的数据库记录
  和图像 SHA-256 均一致。最终 PDF 的 SHA-256 与其 manifest 一致。
- 2026-09-07 浏览器记录及截图位于 `data/output/week8_gui_acceptance/`；该目录和
  `tmp/week8-browser-check.cjs` 是开发机本地验证产物，不进入源码提交。
- 标准静态构建使用 `pnpm run build`；Sites 打包单独使用 `build:sites`，
  需要相应的本地部署配置。当前整仓没有自动部署 Pages 的根级工作流。

## 入口

在已有 Python 环境和前端依赖的项目根目录运行 `START_RPLA_WEEK8.cmd`，
打开 `http://127.0.0.1:5177/#sample-capture`。相机未到货时使用
`START_RPLA_WEEK8.cmd -WaitForCamera`。新相机归档为 `data/output/week8_service/`；
旧合成归档仍在 `data/output/week7_service/`，通过原 Week 7 入口读取。
安装和启动细节见 [GUI README](gui-prototype/README.md)；接口及归档规则见
[采集流程说明](gui-prototype/SAMPLE_CAPTURE_FLOW.md)。

常规回归：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
```

在 `gui-prototype` 中运行 `pnpm install --frozen-lockfile`、
`pnpm run test:evidence` 和 `pnpm run build`。
