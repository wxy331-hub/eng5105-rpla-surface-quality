# ENG5105 检查后修复记录 · 2026-09-08

用户授权按检查结论修复。全部实现、测试和构建位于
`D:\12591\Documents\5105`，继续使用该目录作为默认项目目录。
原始检查记录保留在 `D:\12591\Documents\5105_migration_20260908\code_review_20260908.md`。

## 已完成修复

| 检查项 | 当前行为 | 主要文件 |
|---|---|---|
| 1. 诊断默认覆盖历史证据 | 每次使用带时间与随机标识的新 JSON 文件名；已有目标在设备访问前拒绝，最终写入也采用排他创建 | `src/measure_live_latency.py`、`scripts/test-real-network-fault.ps1` |
| 2. 过期帧重新获得健康状态 | 缓冲携带该帧自身的采集完成时间；处理前及保存/发布前检查帧龄；快照和 JPEG 读取主动清除过期状态 | `src/live_service.py` |
| 3. 多个候选被拆成重复事件 | 在符合批次、类型及帧间隔的事件中按重叠程度匹配；同一事件每帧最多接收一个候选 | `gui-prototype/src/services/inspectionDataSource.js` |
| 4. 代表记录字段错配 | ID、帧号、时间、图像和测量字段统一来自同一条最高分记录；起止帧和全部 `recordIds` 独立保留，匹配依据最新框 | 同上及 `gui-prototype/src/App.jsx` |
| 5. 保存成功却因日志报错返回失败 | 采集与 `CAPTURE_ARCHIVED` 共用原有事务；失败撤回新图片/记录并恢复重拍关系。Week 7 先完成并记录模拟 OFF，再提交采集，提交后不再追加事件 | `src/week7/store.py`、`src/week7/workflow.py`、`src/week8/workflow.py` |
| 6. 数据库失败未更新状态 | Week 8 处理 SQLite 异常并更新 `last_fault`；API 返回结构化 503；Week 7/8 的次生失败日志异常附注到原错误，保留根因 | 两个 workflow 及 `src/week7_service.py` |
| 7. 本地录像被标为硬件证据 | 共享 MJPEG 适配器要求有效 HTTP(S) URL；显式注入采集统一标为 `OFFLINE_FAULT_INJECTION_ONLY`，摘要、数据库、导出及重建保持一致 | `src/week4/camera.py`、`src/week4_live_demo.py` |
| 8. 记录指向错误帧图片 | 旧演示保留一组代表图；原图与标注图对应同一最后处理帧，摘要记录 `representative_frame_id`；没有逐帧存图的候选 `image_path` 为 null | `src/week4_live_demo.py` |
| 9. Week 8 忽略 CORS 配置 | 组合服务统一采用 `runtime.config.cors_allow_origins`；单独 Week 7 入口保留原本机默认值 | `src/week7_service.py`、`src/week8_service.py` |

另外处理了检查报告中的三类维护项：

- Plan B 驻留服务及 Week 2 诊断把 open/read timeout 通过 FFmpeg 的 `open(..., params)` 传入，打开失败释放句柄。这里验证了参数传递，没有测量实际网络超时长度。
- 移除未使用的 Recharts、Vite 图表分块、四个空接口类和确认没有引用的旧 CSS。锁文件减少 312 行，样式净减少 146 行；依赖同步仅移除相关包，没有升级依赖或下载新包。
- 旧校验器入口明确说明其原始源码版本适用范围，并指向现有 `scripts/verify_evidence_baselines.py`。新增 `paper_rewriting_output/README.md` 说明正式 PDF、历史合并/构建脚本和状态填写脚本的用途。历史校验预期值保持原样。

## 验证结果

新增 29 项 Python 回归和 4 项前端回归，涵盖受控时钟、并列候选、SQLite 触发器失败、重拍保全、证据标签、代表图片及诊断输出保护。问题用例先在旧行为下复现失败，再验证修复。

| 检查 | 最终结果 |
|---|---|
| Python 完整回归 | **405 passed、1 skipped，47.57 秒** |
| GUI evidence 测试 | **44 passed、0 failed** |
| Vite 标准构建 | **通过，4.05 秒**，输出 `gui-prototype/dist/client/` |
| 历史报告/证据基线 | `scripts/verify_evidence_baselines.py` **PASS** |
| Week 8 配置检查 | `START_RPLA_WEEK8.cmd -CheckConfig` **通过**，归档路径为 D 盘 |
| 等待相机启动 | `START_RPLA_WEEK8.cmd -WaitForCamera` **通过**；GUI HTTP 200，`DISCONNECTED`，`capture_available=false`，`automatic_actions_allowed=false`；停止后 8765/5177 无监听 |
| 最终 PDF | SHA-256 与原 manifest 相同：`05edec2f456704db89e5d458c53db5fb5adeeb07568508ca872e60973ded399b` |
| 源码差异空白检查 | `git -C D:\12591\Documents\5105 diff --check` **通过** |

唯一跳过项是在当前 Windows 权限下无法创建文件符号链接（WinError 1314）；未提高权限或放宽断言。
第一次整仓回归为 404 通过、1 失败、1 跳过：失败来自相机源码更新后，当前合成重放资源清单仍记录旧指纹。
使用该次测试中实际运行生成器的输出同步了 `src/week4/camera.py` 的指纹；其余 15 个生成数据/图像文件逐字节相同。
之后完整回归全部通过。冻结的历史报告基线没有据此修改。

迁移遗留的 pytest 字节码曾在报错位置显示旧 E 盘路径，已清除相应测试缓存；实际加载的服务文件和代码位置均在 D 盘。
清理后对相关符号链接检查复验为 2 通过、1 跳过，输出已使用当前项目路径。
Python 系统安装与 pnpm 公共缓存仍可位于 E 盘；项目源码、虚拟环境入口和 `node_modules` 均使用 D 盘。

## 复现命令

在 `D:\12591\Documents\5105` 运行：

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -ra -p no:cacheprovider --basetemp=D:\12591\Documents\5105_migration_20260908\pytest_fixes_final
.\.venv\Scripts\python.exe -B scripts/verify_evidence_baselines.py
.\START_RPLA_WEEK8.cmd -CheckConfig
```

再次运行时，为 `--basetemp` 选一个新的目录，以保留本次验证产物。
完整回归日志为 `D:\12591\Documents\5105_migration_20260908\pytest_fixes_final.log`。

在 `D:\12591\Documents\5105\gui-prototype` 运行：

```powershell
$pnpm = 'C:\Users\12591\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd'
& $pnpm run test:evidence
& $pnpm run build
```

以上验证覆盖软件行为和本机构建。真实 ALC 相机、实际网络超时、光学标定和 rPLA 缺陷性能仍按到货验收计划执行。
现有用户修改、样本归档及最终 PDF 保留；本次没有提交或推送代码。

新浏览器渲染检查未记为通过：一次组合浏览器预览命令被自动审批策略拒绝，工具仅返回
`blocked by policy`，没有更具体原因；后续直接浏览器调用也未取得可核验的渲染结果。
上述 HTTP 和等待相机状态结果已独立检查。
