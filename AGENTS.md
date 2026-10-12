# ENG5105 项目规则

## 默认工作目录

- 本项目的唯一默认工作目录是 `D:\12591\Documents\5105`。读取、修改、运行、验证和交付均以此目录为准。
- 本项目使用 Codex 和本文件中的项目规则，不依赖上级或其他位置的 `CLAUDE.md`。较早材料中将 E 盘指定为主副本的说明已经失效，不得据此把工作转回 E 盘。
- 默认用简体中文沟通；保留必要的英文代码名称、命令和报错。
- 用户要求检查、解释或计划时只读；要求实现时完成必要改动及相关验证。保护已有未提交修改，不自行提交、推送或发布。

## 当前项目与架构

- ENG5105 项目检查固定、人工分度的 rPLA 样本表面，记录可追溯的候选异常；当前软件结果不代表已验证的缺陷检测性能。
- Plan A 采用 ALC-IMX258 USB/UVC 相机。Plan B ESP32S3/OV3660 MJPEG 保留为已有的可选采集路径。不同来源的参数和证据保持独立。
- 驻留 Python 服务独占相机读取；GUI 通过服务的 REST、WebSocket 和共享图像接口访问相机。
- 每个样本有六个角度、两种照明，共十二个视图。每次只采集当前选定的一个角度和一种照明；重拍保存历史，已完成会话锁定，配置改变时不得混采。
- `src/week3/` 保存来源无关的数据与检测契约；相机适配器可以依赖它，它不得反向依赖具体适配器。
- `src/week4/camera.py` 管理连接状态和单帧缓冲。采集线程不直接访问 SQLite；检测线程持有自己的数据库连接。
- 维持 `capture_factory`、`source_factory` 等注入入口，以便不打开实物相机就能验证软件行为。

## 数据与证据

- 最终报告是 `paper_rewriting_output/final/Proposal_Design_Report.pdf`，版本信息见同目录 manifest。保留原始字节；实现变化记录在独立文档中。
- 上级目录的配对 Markdown/DOCX、报告加工脚本和带日期的 PPT 项目是历史材料。旧的合并、重排、状态填写脚本不得自动作为当前报告生成或验证步骤。
- 历史报告证据使用 `scripts/verify_evidence_baselines.py` 对照冻结快照验证；不要用当前应用源码替换历史快照。
- 未有有效 `calibration_id` 时，`size_mm` 和 `position_mm` 保持空值。`confidence` 是未标定的排序分数，不是缺陷概率；候选等级不得直接授权物理剔除。
- 离线、合成、故障注入、真实连接观察、标定测量和待验证目标分别记录。软件改进、测试通过或配置请求不得升级硬件证据等级。
- 保留原始数据、样本归档、重拍记录和失败记录；新实验使用独立输出位置。删除用户数据、覆盖既有证据及外部发布需要对应授权。
- `data/output/`、`tmp/` 和各构建缓存包含开发机产物；不因整理目录或迁移而自动删除。

## 运行与验证

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_evidence_baselines.py
.\START_RPLA_WEEK8.cmd -CheckConfig
```

在 `gui-prototype` 中运行 `pnpm run test:evidence` 和 `pnpm run build`。涉及 Sites 打包时再执行对应打包及专用测试。

`pytest.ini` 使用 `tmp/pytest`，保留 `tmp/.gitkeep`。只读检查可使用 `-B -p no:cacheprovider` 和独立 `--basetemp`。不默认打开实物相机、执行网络故障测试或修改防火墙。

GUI 的布局、语言、采集交互和具体前端规则见 `gui-prototype/AGENTS.md`。
