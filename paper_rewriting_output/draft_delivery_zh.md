# 8. 环境、安全、伦理与治理影响（含采购）

采用再生原料，并不会自动使这套监测系统产生环境效益。及早预警或可避免继续加工或使用外观明显不合格的线材，这与可持续发展目标12的宗旨一致 [27]。然而，相机、Raspberry Pi、照明和网络均会耗能；新增电子设备带有隐含环境影响，调校不当的检测器还可能造成原本可以避免的废品。目前尚未完成生命周期评估。能源消耗与废品观察结果将分开报告；在没有按照 ISO 14040 定义相容的比较方法之前，不会声称存在净环境收益 [26]。复用大学提供的硬件并采用可维修的夹具部件，属于设计选择，而非环境优越性的证据。

负责任的运行要求将不确定测量排除在自动质量决策之外。陈旧帧、心跳缺失、相机状态异常、校准缺失或编码器状态无效，均会禁止标记、剔除和停机请求。拟议的 STM32 看门狗提供独立监督。保险丝、反接保护、本地去耦及适当的续流抑制用于控制电气危险。运动导向件和可选标记器必须配备防护，并应在低能量条件下调试，同时设置便于触达且独立的停止装置。这些措施参考了 ISO 13849-1 [24]，但该原型既未取得安全认证，也不得被表述为工业安全相关控制系统。

相机则带来另一类责任。它只拍摄封闭的线材区域，在本地裁剪至该 ROI，并保存事件证据而不是连续视频。数据采集前必须商定访问、保留和删除规则，同时设置实验室告示并控制导出；OAIC 指南和《Privacy Act》为此提供背景 [25], [33]，但本提案不作任何法律合规认定。若某帧包含人员影像，则从缺陷数据集中隔离，待审查后再行处理。

配置治理决定了一次演示能否形成可复现的证据。我们会把相机设置、ROI、软件、校准文件、需求状态和协议作为同一基线进行版本管理。每项报告结果都须附带证据标签、条件与配置。在有效的光学校准 ID 和编码器校准 ID 同时存在之前，`position_mm` 与 `size_mm` 保持为 `null`；按卷盘、批次或事件组划分的分组也会在调参前固定。咨询结果、需求变更、失败测试和豁免均写入决策日志，且日志绝不预设利益相关方已批准。该做法落实 ISO/IEC/IEEE 15288 的可追溯性意图 [34]，也遵循 OT 安全对运行、网络与人为控制的区分 [32]。

采购沿用同样的纪律。2026年8月15日，Plan B 唯一经过核验的价格是 400 P/R 编码器的 A$41.30 [31]；照明、电源/保护、夹具和标记器仍采用规划预留额。Plan A 的供应商页面显示，相机价格为 A$92.55，配套镜头为 A$43.60，且相机缺货 [29], [30]。获得批准前，必须重新核查库存、兼容性和交付成本。实施过程中不会订购任何 Plan A 物项。

# 9. 材料清单

现有成本数字中，只有一部分经过供应商核验。因此，表15将大学提供的设备、已核验的供应商价格与团队规划预留额分开列示。所有金额均为澳元；供应商数据访问于2026年8月15日，除非页面另有说明，均含 GST。运费不计。大学供应部件的实际发放、状态和兼容性仍须通过到货检查确认 [4]。

**表15. Plan B 材料清单及追加采购预算区间。**

| 状态 | 物项或组别 | 数量 | Plan B 用途 | 成本依据 | 计入成本 |
|---|---|---:|---|---|---:|
| 大学提供 | Raspberry Pi 4 4 GB、电源和 32 GB SD 卡 | 1套 | OpenCV 服务、API/WebSocket、SQLite 和 GUI [21] | 已提供；状态待检查 | A$0 |
| 大学提供 | STM32 Nucleo-L432KC | 1 | 编码器、心跳、照明及带禁止逻辑的输出接口 [22] | 已提供；状态待检查 | A$0 |
| 大学提供 | XIAO ESP32S3 Sense with OV3660 | 1 | SVGA MJPEG 采集节点 [18]-[20] | 已提供；状态待检查 | A$0 |
| 大学提供 | SFH4555、BPW46、LM324N 和 MCP3208 | 1通道/套 | 线材存在检测与光学头健康状态通道 | 已提供；最终元件参数待测量 | A$0 |
| 大学提供 | I2C LCD、LED、电位器、电阻、面包板、洞洞板、导线和排针 | 按发放数量 | 本地状态显示、信号调理和原型装配 | 已提供；数量/状态待检查 | A$0 |
| 已核验采购 | 增量式光电旋转编码器，400 P/R | 1 | 长度-位置测量 | 供应商页面 [31] | A$41.30 |
| 规划预留 | 受控漫射与低角度照明 | 1套 | 可重复的明场/暗场成像 | 团队估算区间；供应商未确定 | A$30-A$60 |
| 规划预留 | 12 V 电源、5 V 转换、MOSFET、保险丝、连接器及保护元件 | 1套 | 独立辅助供电与受保护开关 | 团队估算区间；拓扑/报价待定 | A$30-A$50 |
| 规划预留 | 反射镜、外壳、支架和导向件 | 1套 | 封闭光学几何结构与线材控制 | 团队估算区间；尺寸待实物到达后确定 | A$30-A$70 |
| 规划预留 | 标记器/舵机演示装置 | 1 | 可选的基于位置的输出演示 | 团队估算区间；仅在安全输出评审后放行 | A$10-A$25 |
| **Plan B 追加采购预算区间** |  |  |  | **一项已核验价格加四项规划预留** | **A$141.30-A$246.30** |

保留 Plan A 仅为使可行性决策可审计。其 IMX296 全局快门相机在技术上适用于快速运动下的机器视觉成像，并且需要合适的 C/CS 卡口镜头 [23]。这两个物项都不属于实施 BOM；表16将两项仅作对比的采购单独列出。

**表16. 仅作对比的 Plan A 成像采购。**

| 仅作对比的 Plan A 物项 | 数量 | 2026年8月15日的证据 | 已核验价格 |
|---|---:|---|---:|
| Raspberry Pi Global Shutter Camera, CE09593 | 1 | 供应商页面；缺货 [29] | A$92.55 |
| Raspberry Pi 6 mm CS-mount lens, CE06937 | 1 | 供应商页面；有货 [30] | A$43.60 |
| **Plan A 专属成像小计** |  | **不含运费** | **A$136.15** |

将这一概念专属小计加入共同的追加采购预算区间后，Plan A 的总预算区间为**运费前 A$277.45-A$382.45**。这不是报价，也不是采购订单。Raspberry Pi、STM32、照明、电源、夹具、编码器和标记器等共同需求只计算一次，因此该比较既未隐去共同成本，也未将其重复计入 Plan A。

# 10. 项目交付计划与团队职责

交付策略采用阶段门控，并具有近似 V 模型的结构：需求被转化为拟议要求、接口、危险因素和测试定义；实施完成后，依次开展单元检查、子系统集成、经校准的系统测试，以及针对相同标识符的独立验证。只有规定的证据已经存在，对应关口才可通过。

证据状态将在**2026年8月27日星期四（第5周）**发生变化。在此之前，不开展任何 rPLA 实物或夹具材料测试。此前的工作仅限于设计、采购准备、软件/合成测试和边界明确的非 rPLA 实时集成。材料若迟到、不完整、损坏或不安全，实物测试里程碑必须相应顺延；合成结果不能填补这一证据缺口。表17将这种依赖设置为放行关口，而不是隐藏的进度假设。

**表17. 阶段门控交付进度与证据决策。**

| 阶段与时间 | 计划工作 | 关口输出与决策规则 |
|---|---|---|
| S0：基线，截至2026年8月26日星期三 | 冻结需求、接口、风险、夹具图纸和协议；保留 `synthetic`/`live-integration` 标签 | G0：经负责人评审的版本化基线；不得发布实物性能结论 |
| G1：材料关口，2026年8月27日星期四 | 记录收货情况、数量、状态、尺寸、可追溯信息和危险因素 | 通过后方可开展实物相关工作；未通过则重新排期并审查范围 |
| S1：安全试运行，G1 后 | 装配夹具；以低能量检查防护、供电、通信和处于禁止状态的输出 | G2：安全检查清单完成、采集稳定且无失控输出 |
| S2：校准，第6-7周 | 锁定光学设置；建立比例尺、counts/mm、相机-标记器偏移和参考基准 | G3：形成版本化 ID；校准无效时，毫米字段保持 `null` |
| S3：采集，第7-8周 | 在计划速度/光学挑战条件下采集已标注事件；审计标签和分组 | G4：调参冻结前具备可追溯的基准真值与相互独立的分组 |
| S4：稳健性，第8-9周 | 集成各子系统；在监督下注入网络、供电和传感器故障 | 形成恢复证据并安全禁止输出；存在未解决的高风险时，阻止自动输出 |
| S5：验证，第10周 | 在留出组上评估事件指标、误报次数/m、位置、吞吐量、延迟和记录丢失 | 接受、优化、缩小适用范围或修订需求；如实报告失败 |
| S6：发布，第11-12周 | 冻结配置、汇总证据并对主张开展同行评审 | 登记册把每项获接受的主张关联至配置、测试和负责人 |

这一顺序直接暴露出吞吐量缺口。已记录的 SVGA 集成测试测得 10.77 FPS（`RESOLUTION_TEST_RESULTS_2026-08-11.md`，`LIVE_INTEGRATION_ONLY`；附录 A，IE1），低于拟议的 20 FPS。因此，独立验证关口要求采取以下决策之一：优化系统、缩小速度/视场范围，或形成有记录的需求变更；绝不能事后声称已经合规。

由于尚未提供成员姓名，本计划使用六个角色标识符。表18中的规划工作量占比合计为 100%，用于指导任务均衡，而不决定个人成绩。

**表18. 拟议团队职责、工作量占比与贡献证据。**

| 角色 | 占比 | 主要责任 | 固定支持与评审 | 必需的贡献证据 |
|---|---:|---|---|---|
| M1，系统/项目 | 17% | 需求、利益相关方协议、架构、进度、接口、风险和集成 | M4 支持报警/验收；所有模块负责人参与 | 决策日志、基线和需求状态记录 |
| M2，光学/相机 | 16% | 相机、照明、外壳、覆盖范围、图像质量和校准 | M4 支持图像/ROI；M6 开展光学重复测试 | 图纸、设置、校准和图像记录 |
| M3，传感/供电 | 16% | 光电二极管/ADC、供电、保护和电气检查 | M5 支持布线/故障；M4 提供健康状态日志 | 原理图、计算、检查记录和日志 |
| M4，视觉/UI/数据 | 18% | OpenCV、GUI、数据库、跟踪、评估和分析 | M2 支持成像；M6 提供独立标签/测试 | 代码、schema、测试输出和可复现分析 |
| M5，嵌入式/通信 | 17% | STM32、编码器、时序、看门狗、通信和安全输出 | M3 支持供电；M6 开展机械/输出测试 | 固件、接口轨迹以及故障/位置记录 |
| M6，验证/机械/质量 | 16% | 试验台、基准真值、分组划分、验证、不确定性和安全评审 | M4 支持指标；M5 支持对准/重复性 | 协议、标签审计、留出结果和评审记录 |

集成仍由全体成员共同承担。每项工作都要指定负责人、评审者、内部日期与证据输出。任何接口变更在纳入基线前，必须递增版本号，经负责人评审，并记录影响检查。已发布的校准/测试数据设为只读；更正内容采用追加方式，不得替换原记录。我们将每周运行一次集成构建，并从 G3 起直至独立验证关口提高频率，使交接始终可见，同时避免把未完成工作默认交给 M1 或 M4。

# 11. 风险登记册

只有团队能够观察到风险正在逼近时，一条风险记录才真正有用。因此，表19为每项提案阶段风险配置了可观察触发条件、负责人、控制措施和残余优先级。各项评级均为定性判断，并非实测概率。残余评级以所列控制措施已经实施并通过测试为前提；它不表示危险已经消失。

**表19. 提案阶段风险登记册。**

| ID | 风险与后果 | 初始评级 | 可观察触发条件 | 负责人 | 规划控制措施与应急方案 | 残余评级 |
|---|---|---|---|---|---|---|
| RSK-01 | 滚动快门、MJPEG 或运动伪影与缺陷相似，或将缺陷掩盖 | 高 | 候选率随速度/JPEG 设置急剧变化；边缘形状在帧间偏移 | M2/M4 | 锁定曝光与几何条件，按速度测试各项设置，采用多帧确认并保留原始事件证据；必要时缩小运行范围 | 中 |
| RSK-02 | 眩光或角度覆盖不完整导致误报或表面漏检 | 高 | ROI 饱和、背景直方图不稳定或出现可重复的盲区 | M2 | 采用封闭的明场/暗场照明和哑光背景；只有完成覆盖范围实测后才使用反射镜，并报告未覆盖角度 | 中 |
| RSK-03 | Wi-Fi 丢失、延迟或陈旧缓冲破坏在线决策 | 高 | 帧龄超过阈值、健康端点失败或积压增长 | M5/M4 | 使用受控 2.4 GHz 网络、最新帧缓冲、重连状态、健康帧资格判定和自动输出禁止逻辑 | 中 |
| RSK-04 | 第5周材料迟到、不完整或不适用 | 高 | 8月27日收货关口未通过，或夹具尺寸冲突 | M1/M6 | 在 G1 检查；关口前工作保持为非实物工作；重排软件/文档任务，并在不虚构测试的前提下上报范围和日期问题 | 中-高 |
| RSK-05 | 代表性缺陷数量过少，导致验证薄弱或存在偏差 | 高 | 所需类别/分组缺失，或标签无法得到独立核查 | M6/M4 | 预先定义样本/标注协议，保留可解释的 OpenCV 基线，报告类别覆盖并收窄主张；通过获批准的渠道寻求更多材料 | 中-高 |
| RSK-06 | 相邻帧或事件泄漏夸大性能 | 高 | 同一卷盘、批次或事件的帧同时进入调参与测试集 | M6 | 调参前冻结组级划分，保存来源信息，执行划分审计，并拒绝受污染的评估 | 低-中 |
| RSK-07 | 校准漂移使尺寸或位置值失效 | 高 | 焦点、工作距离、滚轮几何参数或配置哈希发生变化；参考检查失败 | M2/M5 | 将光学与编码器校准 ID 绑定到记录；执行参考检查，变化后使物理字段失效并重新校准 | 中 |
| RSK-08 | 电源噪声、欠压或感性开关使控制器复位，或产生不安全输出 | 高 | Pi 欠压/复位日志、供电轨电压跌落、MCU 复位，或开关动作期间出现输出脉冲 | M3/M5 | 分离电源域，设置保险丝、去耦和续流抑制，开展启动冲击/稳态实测，并采用看门狗安全默认状态 | 中 |
| RSK-09 | 导向件或标记器造成夹伤、缠绕或意外运动危险 | 高 | 防护打开、对准卡阻、看门狗丢失，或在受监督命令之外出现输出 | M6/M5 | 设置防护、低能量调试和独立停止装置；开展受监督测试，并在 G2/G4 通过前禁止输出 | 中 |
| RSK-10 | 相机拍摄到人员，或证据在没有商定规则的情况下被保留/访问 | 中 | ROI 外出现人脸/身体、未经批准的导出，或尚未作出删除决定 | M1/M4 | 封闭/裁剪视野，仅在本地保存事件，设置告示，并作出基于角色的访问决定；隔离偶然拍到的影像 | 低-中 |
| RSK-11 | 接口或配置不匹配，导致后期集成失败 | 高 | schema/baud/state 不匹配、设置未版本化，或模块单独通过但在基线构建中失败 | M1 与所有负责人 | 建立接口控制记录和契约测试，使用版本化配置，开展每周集成，并由负责人-评审者签核 | 中 |

停止规则最为关键。RSK-04 阻止实物测试；RSK-06 使受影响的性能估计无效；RSK-07 强制物理输出恢复为 `null`；RSK-08 或 RSK-09 禁止执行机构动作。对于残余“中-高”的数据或进度风险，只能通过收窄主张或在决策日志中修订计划予以接受，不能通过降低证据标签来处理。

# 12. 建议与结论

建议将 Plan B 作为唯一实施路径：ESP32S3 OV3660 通过受控 2.4 GHz MJPEG 完成采集，Raspberry Pi 4 承担视觉/服务/数据库/GUI，STM32 负责编码器、看门狗、照明和安全 I/O 监督。Plan A 在技术上仍具可信度，尤其适用于运动成像 [23]；但它未通过大学硬件可用性、增量成本、库存/交付周期和学期内交付关口。该决策意在选择最强且可实施的概念，并非声称 Plan B 相机在理论上更优。

成本边界支持这一判断。Plan B 所需追加采购预算区间为**运费前 A$141.30-A$246.30**；其中仅 A$41.30 的编码器价格经供应商核验，其余均为预留估算。在此基础上加入已核验的 A$136.15 Plan A 专属相机/镜头小计，得到**Plan A 运费前总预算区间 A$277.45-A$382.45**；2026年8月15日，所列相机处于缺货状态 [29]-[31]。这些数字支持概念选择，但不构成采购授权。

该建议授权的是分阶段开发，而非验收。Plan B 只有依次通过8月27日材料关口、安全装配检查、版本化光学与编码器校准、可追溯的真实材料采集、留出验证和受监督故障测试后，方可推进。精确率、召回率、F1、最小可检出的物理尺寸、毫米精度、可用线速度和最终延迟仍待确定。利益相关方对数值指标的批准，也有待形成书面咨询记录。若某一关口未通过，可辩护的应对方式是优化、限制运行范围，或在记录理由后修订需求。

拟议贡献由此落在一条状态边界清晰、受控的测量链上：图像采集形成候选记录；校准可以赋予其物理含义；独立验证或可支持缺陷主张；只有健康、当前且已获授权的状态，才可以请求动作。Plan B 应以此为基础获得经费、完成构建并接受评价。

# 附录 A. 内部证据登记册

报告中的集成与实施主张以表20所列、已经冻结的本地制品为依据。SHA-256 值标识证据截止时实际审查的文件；这些哈希不会把开发主机证据转化为 Pi、STM32 或实物缺陷证据。

**表20. 截至2026年8月15日的内部集成、配置和代码证据。**

| ID | 制品相对路径 | 证据作用与日期 | SHA-256 |
|---|---|---|---|
| IE1 | `RESOLUTION_TEST_RESULTS_2026-08-11.md` | VGA/SVGA/XGA 筛选与持续速率观察，2026年8月11日 | `A75C316FBD64AFF205F48350EA37271ADEE31FF036F3040AA46EA5C350CDDC3E` |
| IE2 | `LIVE_PATH_TEST_RESULTS_2026-08-11.md` | 亮度阶跃时序与限定范围的网络故障观察，2026年8月11日 | `16CFB2FF0C0449AACD100090F80CE764337888F1D67731E60207F5662A58B93D` |
| IE3 | `WEEK3_OFFLINE_IMPLEMENTATION.md` | 离线契约、来源信息与 `null` 字段保护，2026年8月10日 | `EDB6D6645245F0882FFEC8CDC0B3738FE5109641D9518BC69A7F11204F2F5920` |
| IE4 | `WEEK4_OFFLINE_IMPLEMENTATION.md` | 实时连接、缓冲与故障状态证据摘要，2026年8月11日 | `68D8AA905507B54CFDE71B15CA8D7D7CC6BDA270AA7859C2EC43C7B12FB933C8` |
| IE5 | `config/live_service.json` | Windows 开发环境的 ROI、阈值、最小面积和材料关口配置 | `EEE7038C8A648B48B4518E3FF8F25648E02C4F968B62DD6C0A17E6618F01F67A` |
| IE6 | `src/live_service.py` | Windows 开发环境的常驻服务、健康状态逻辑和 API 端点 | `4696AD50719C1BAA6EBC724FB262084647634B09A0DB2F674F218064E189E203` |
| IE7 | `src/week3/vision.py` | 与图像源无关的基线视觉处理器和默认阈值 | `9198E135ADED4A8DE845700F4250591BF529AB497136A1D389C136A61FE5E432` |

# 参考文献

[1] Monash University, *ENG5105/ENG5106 Integrated Design Semester 2 2026: Common Context and Project Briefs*, Rev. 0, 2026.

[2] Monash University, *Concept Design: Discipline-Specific Content (Electrical)*, ENG5105, 2026.

[3] Monash University, *Electrical Teams Proposal Report Rubric 2026*, 2026.

[4] Monash University, *ENG5105 Components - With Pictures 2026*, 2026.

[5] D. Hidalgo-Carvajal, Á. Hortal Muñoz, J. J. Garrido-González, R. Carrasco-Gallego and V. Alcázar Montero, “Recycled PLA for 3D Printing: A Comparison of Recycled PLA Filaments from Waste of Different Origins,” *Polymers*, vol. 15, no. 17, art. 3651, 2023. https://doi.org/10.3390/polym15173651

[6] X. Wei and R. Bähr, “A comparative study of 3D printing with virgin and recycled polylactic acid filaments,” *CIRP Journal of Manufacturing Science and Technology*, vol. 54, pp. 75-84, 2024. https://doi.org/10.1016/j.cirpj.2024.08.007

[7] R. Quader, E. Dramko, D. Grewell, J. Randall and L. K. Narayanan, “Characterizing the Effect of Filament Moisture on Tensile Properties and Morphology of Fused Deposition Modeled Polylactic Acid/Polybutylene Succinate Parts,” *3D Printing and Additive Manufacturing*, vol. 11, no. 3, pp. 1151-1161, 2024. https://doi.org/10.1089/3dp.2022.0222

[8] C. Caceres-Mendoza, P. Santander-Tapia, F. A. Cruz Sanchez, N. Troussier, M. Camargo and H. Boudaoud, “Life cycle assessment of filament production in distributed plastic recycling via additive manufacturing,” *Cleaner Waste Systems*, vol. 5, art. 100100, 2023. https://doi.org/10.1016/j.clwas.2023.100100

[9] P. Zhao et al., “Close-looped recycling of polylactic acid used in 3D printing: An experimental investigation and life cycle assessment,” *Journal of Cleaner Production*, vol. 197, pp. 1046-1055, 2018. https://doi.org/10.1016/j.jclepro.2018.06.275

[10] L. Heckler-Kram, J.-H. Neudeck, U. Scheler, R. König and C. Steger, “The MVTec AD 2 Dataset: Advanced Scenarios for Unsupervised Anomaly Detection,” *International Journal of Computer Vision*, vol. 134, no. 4, 2026. https://doi.org/10.1007/s11263-026-02743-0

[11] P. Carvalho et al., “Detecting visual anomalies in an industrial environment: Unsupervised methods put to the test on the AutoVI dataset,” *Computers in Industry*, vol. 163, art. 104151, 2024. https://doi.org/10.1016/j.compind.2024.104151

[12] C. Wang et al., “Real-IAD: A Real-World Multi-View Dataset for Benchmarking Versatile Industrial Anomaly Detection,” in *Proc. IEEE/CVF Conference on Computer Vision and Pattern Recognition*, pp. 22883-22892, 2024. https://doi.org/10.1109/CVPR52733.2024.02159

[13] S. Verspeek, T. De Kerf, B. Ribbens, X. Maldague, S. Vanlanduit and G. Steenackers, “A Novel Line-Scan Algorithm for Unsynchronised Dynamic Measurements,” *Applied Sciences*, vol. 14, no. 1, art. 235, 2024. https://doi.org/10.3390/app14010235

[14] K. Sundarrajan and B. K. Rajendran, “Explainable efficient and optimized feature fusion network for surface defect detection,” *The International Journal of Advanced Manufacturing Technology*, 2023. https://doi.org/10.1007/s00170-023-11789-0

[15] M. Katsigiannis and K. Mykoniatis, “Enhancing industrial IoT with edge computing and computer vision: An analog gauge visual digitization approach,” *Manufacturing Letters*, vol. 41, pp. 1264-1273, 2024. https://doi.org/10.1016/j.mfglet.2024.09.153

[16] S. Kapoor and A. Narayanan, “Leakage and the Reproducibility Crisis in Machine-Learning-Based Science,” *Patterns*, vol. 4, no. 9, art. 100804, 2023. https://doi.org/10.1016/j.patter.2023.100804

[17] R. B. D. Figueiredo and H. A. Mendes, “Analyzing Information Leakage on Video Object Detection Datasets by Splitting Images Into Clusters With High Spatiotemporal Correlation,” *IEEE Access*, vol. 12, pp. 47646-47655, 2024. https://doi.org/10.1109/ACCESS.2024.3383047

[18] OmniVision Technologies, *OV3660 Color CMOS QSXGA Image Sensor Datasheet*, ver. 1.3, 2011. https://files.seeedstudio.com/wiki/SeeedStudio-XIAO-ESP32S3/res/OV3660_datasheet.pdf

[19] Espressif Systems, *esp32-camera: ESP32 Camera Driver*, official repository and driver documentation, accessed 15 Aug. 2026. https://github.com/espressif/esp32-camera

[20] Seeed Studio, *Getting Started with Seeed Studio XIAO ESP32S3 Series*, updated 14 May 2026, accessed 15 Aug. 2026. https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/

[21] Raspberry Pi Ltd, *Raspberry Pi 4 Model B Product Brief*, Apr. 2026. https://pip.raspberrypi.com/documents/RP-008344-DS-raspberry-pi-4-product-brief.pdf

[22] STMicroelectronics, *STM32 Nucleo-32 Boards: NUCLEO-L432KC*, DB2638 Rev. 9, Apr. 2026. https://www.st.com/resource/en/data_brief/nucleo-l432kc.pdf

[23] Raspberry Pi Ltd, *Raspberry Pi Global Shutter Camera*, accessed 15 Aug. 2026. https://www.raspberrypi.com/products/raspberry-pi-global-shutter-camera/

[24] International Organization for Standardization, *ISO 13849-1:2023 Safety of Machinery - Safety-Related Parts of Control Systems - Part 1: General Principles for Design*, 2023. https://www.iso.org/standard/73481.html

[25] Office of the Australian Information Commissioner, *Posting Photos and Videos*, accessed 15 Aug. 2026. https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/handling-personal-information/posting-photos-and-videos

[26] International Organization for Standardization, *ISO 14040:2006 Environmental Management - Life Cycle Assessment - Principles and Framework*, 2006. https://www.iso.org/standard/37456.html

[27] United Nations Department of Economic and Social Affairs, *Sustainable Development Goal 12: Responsible Consumption and Production*, accessed 15 Aug. 2026. https://sdgs.un.org/goals/goal12

[28] Monash University, *Welcome to Country and Acknowledgement of Traditional Owners*, accessed 15 Aug. 2026. https://www.monash.edu/brandbook/about/welcome-to-country-and-acknowledgement-of-traditional-owners

[29] Core Electronics, *Official Camera Modules - Raspberry Pi Global Shutter Camera*, A$92.55 and out of stock when accessed 15 Aug. 2026. https://core-electronics.com.au/raspberry-pi/camera/official-camera-modules.html

[30] Core Electronics, *Raspberry Pi 6 mm Wide Angle Camera Lens (CS-Mount)*, A$43.60 when accessed 15 Aug. 2026. https://core-electronics.com.au/raspberry-pi-6mm-wide-angle-lens.html

[31] Core Electronics, *Incremental Photoelectric Rotary Encoder - 400 P/R*, A$41.30 when accessed 15 Aug. 2026. https://core-electronics.com.au/incremental-photoelectric-rotary-encoder-400p-r.html

[32] K. Stouffer et al., *Guide to Operational Technology (OT) Security*, NIST SP 800-82 Rev. 3, 2023. https://doi.org/10.6028/NIST.SP.800-82r3

[33] Australian Government, *Privacy Act 1988*, Compilation No. 103, 10 June 2025. https://www.legislation.gov.au/C2004A03712/2025-06-10

[34] ISO/IEC/IEEE, *ISO/IEC/IEEE 15288:2023 Systems and Software Engineering - System Life Cycle Processes*, 2023. https://www.iso.org/standard/81702.html
