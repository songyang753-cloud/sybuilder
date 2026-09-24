---
name: product-flow
description: 从需求到上线再到复盘的产品全流程（意图捕获→深度研究→业务梳理与产品定义→产品结构→PRD v0.9→设计交互三锁协同：Figma 高精度稿+HTML 可交互 demo→PRD v1.0 回灌与三方冻结 G7.5→飞书或钉钉技术/算法/测试联合方案→研发、验证与上线→数据复盘；S1–S10 为执行编号）。当用户说「按标准流程做这个产品」「我给你产品定义你做到底」「出 PRD 然后做 demo 再上 Figma 最后写代码」「做技术方案、算法方案和测试方案」「产品方案评审几轮直到收敛」「把这个需求从头做到能上线」时使用。也用于只跑其中某个阶段（`--from` / `--only`）：「按模板出 PRD」「用模板写需求文档」「出 PRD 和设计方案」「PRD 加设计加交互全套出」「做一个产品方案」「出一份技术算法测试联合方案」「出一套设计系统和交互规格」「跑一轮多视角产品评审」，尤其是单跑用例工程：「把这份 PRD 变成测试用例」「根据需求文档写测试用例」「验收标准转成用例集」「这个需求要测哪些点」「需求覆盖率对一下」「哪些需求没有用例」。适用于 web / 移动端 / 双端产品，与具体公司无关。
---

# product-flow · 产品全流程流水线（十阶段）

把「一句话产品方向」做成「可上线的产品 + 可交接的研发物料」，中间不丢信息、不编造事实、不假装收敛。

S2–S9 正式交付必读补充契约：`references/delivery-quality-contract.md`。它规定最细功能正文与截图、单品包逐级横比、内置制图/原型、同版平台回读及独立终审；不会用本地全绿替代原生文档验收。

## 核心信条（这套东西的灵魂，偏离即失效）

1. **交接处才是事故高发区。** 每个阶段自己做得对没用，PRD 说的和 demo 做的不一样、demo 和 Figma 不一样、Figma 和代码不一样，才是真正的成本。所以本流水线一半的机制在管**阶段之间**，不在管阶段之内。
2. **一条 ID 贯穿到底。** `F-xx`（功能）→ `FR-###`/`NFR-###`（需求）→ `AC-#`（验收）→ demo 场景 → Figma 图层 → 测试用例 → commit。任何一环断了，后面全靠猜，而猜出来的东西没人能验收。
3. **收敛必须可证伪。** 「我评审了三轮觉得可以了」不是收敛。收敛判据的唯一源是 `references/review-perspectives.md` 的分级契约（按视角零 [I] 计，留痕可事后核）——⛔ 本表不复述判据。
4. **不知道就登记，绝不填空。** 每个事实只有三种出处：有人明确告诉你 / 你查到的（标来源+日期）/ 登记为假设 `ASM-###`。没有第四种，第四种就是编造。
5. ⭐ **交付物是给人看的，不是给我看的。** 竞品分析 / PRD / 设计稿 / 交互稿的**正文就是给人看的**；
   **附件是给人 + AI 编程看的**（研发按它写代码）。⇒ 技术细节归附件，正文归人；
   而**我的过程日志两边都不进**——门禁条数、收敛轨迹、第几轮、我犯了什么错，
   那些属于 `.proposals/` 与 commit message。口径真源 `spec/_audience.json`，
   门禁 `scripts/audience-gate.py`。⚠️ 它只拦机械可判的混入，**拦不住「写得好不好读」**——那归人审。
6. **能看见的问题和能读出来的问题不是一类。** 文档评审再多轮也发现不了「界面上那句话是反的」。所以第 6 阶段的可交互 demo 不是可选项，是**唯一一次让方案脱离文字被眼睛检验**的机会。

## 内置能力与外部适配器（开箱边界）

SYBuilder 安装后，运行 `product-flow` 不应再要求用户逐个安装零散 Skill：

| 类型 | 内置/适配项 | 规则 |
|---|---|---|
| 内置模块 | `modules/research` · `modules/diagramming` · `modules/design-quality` · `modules/prototyping` | 属于本 Skill 的库；按阶段渐进读取，不单独触发、不另建正本 |
| 套件 Skill | `coding-standards` · `four-node-review` | 随同一仓库安装，以共享契约接入 S8/S9；不把全文复制进本文件 |
| 平台适配器 | `adapters/lark` · `adapters/dingtalk` · `adapters/figma` · `adapters/browser` | 调用平台官方能力；不可用时仅该平台报 `UNABLE`，不伪造回执 |
| 研究来源 | 外部文章、标准、其他 Skill | 可引用事实与方法来源；许可不明确时不复制表达、代码、模板或资产 |

协作文档正文只维护一份 Markdown 语义源；交付平台由用户选择飞书或钉钉，统一从
`scripts/_documents.py` 进入。飞书固定使用官方 `lark-cli` 的用户身份，钉钉固定使用官方
`dws`。飞书适配器实际调用时显式传 `--as user`。两个平台都必须写后回读并验证真实图片实体；某一平台不可用时不得偷偷改投另一
平台，也不得把本地稿称为平台原生交付。

## ⭐⭐ 前置分流表（30 秒读完，先答三个问题再往下看）

> 2026-08-31 第十二轮补入。起因：外部评审指出——
> **裁剪判据散落在五个地方（本节「何时不用」· `--from/--only` · 反向提取 ·
> 形态适配 · `flow-tailoring.md`），缺的不是能力，是入口。**
> ⚠️ 更难看的是：上一轮我为「裁剪」新写了一份 reference，
> **那是把它变成了第五处，而不是给出入口**——
> ⭐ **「交接处才是事故高发区」这条信条，它自己最上游的那个交接（什么时候用、
> 用多重、从哪个方向进）恰恰留给了读者自己拼。**

**答完这三个问题，你就知道该走哪条路、砍哪几段。**

### 问题一：要不要走这套流程？

| 你的情况 | 走哪 |
|---|---|
| **一个人两小时能重写、没人要交接/验收/追责** | ⛔ **不要用本流水线**。直接迭代原型（社区实践：**做一版的成本 < 写清规格的成本时，原型 > PRD**） |
| 改文案、修 bug | 直接改 |
| 纯技术重构、无产品面 | `coding-standards`（含内置 `repository-enforcement`）+ `four-node-review` |
| **有人要接手，而他不在你脑子里** | ✅ 往下走 |

⭐ 最后一行是这套 SOP 一大半机制存在的**唯一理由**——
ID 链、双向对账、格式边界、元素身份，全都是为「接手的人不在你脑子里」而设。

### 问题二：从零做，还是给已上线产品补文档？

| | 从零 | **反向提取（已上线补文档）** |
|---|---|---|
| 走法 | S1→S10 顺序 | **每个阶段的做法都不同**，见 `templates/prd-complete.md` 开头「反向提取型」说明与 flow-tailoring 的 reverse 模块合同 |
| S6 | 做 demo | **跳过**，真实程序即 demo，但**必须锁 `baseline.md`**（否则 G2/G3 进 UNABLE） |
| 最大的坑 | 想当然 | ⛔ **代码里读不到的东西（如算法评测数据）必须找人要真数，要不到就登记 TBD，绝不编** |

⚠️ **走错方向的代价是「凭空写」**——两条路径的填法完全不同。

### 问题三：什么形态？（决定砍哪些章节 / 视角 / 门禁）

| 形态 | 承重的 | **砍掉反而更好的** |
|---|---|---|
| **内部工具**（单一操作角色） | 能力清单 · 运维型指标 | ⛔ **别写八条用户旅程**——那是纯负担 |
| **消费级 / 多干系人 B2B** | 用户旅程（每条具名主角）· 完整 NFR | —— |
| **合规 / 监管更新** | **约束可追溯，不容商量** | 用户旅程可能完全无关 |
| **存量改造** | 现有代码引用必须准确 · **新旧旅程必须区分** | —— |
| **链条顶端**（喂 UX→架构→用例） | 下游可用性权重最高 | —— |

⛔ **两个方向都是缺陷**：过度形式化（给单人工具写八条旅程）与形式化不足
（消费级一条旅程没有）**同样要报**（铁律 39）。

### 然后：把答案写下来
三个答案 + 裁掉了什么 + **「如果这个判断错了会怎样」** → `.product-flow/scope.md`
（格式与定档五问见 `references/flow-tailoring.md`）。
⛔ **被裁掉的环节和「跑了但没发现问题」的环节，在产物上长得一模一样**——
不留痕，事后没人分得清它是被裁了还是被忘了。

---

## 何时用 / 何时不用

**用**：新产品从零定义并做到上线；大版本迭代要走完整评审；需要给老板演示 + 给研发交接的完整链路。

**不用**：改个文案、修个 bug（直接改）；纯技术重构无产品面（用 `coding-standards` 的内置仓库执法模块 + `four-node-review`）；只要一份 PRD 不做后续（`--only prd`＝只写 PRD 本体 S4B；`--only S4`＝连产品结构 S4A 一起做——没有现成产品结构就选后者）；只要一个 demo（直接调用本 skill 的内置 `modules/prototyping`）。

⚠️ **一条要认真对待的反对意见**（来自社区实践综述 `shanraisshan/claude-code-best-practice`，2026-08-16 查证）：**当构建成本足够低时，「原型 > PRD」**——直接做 20~30 个版本，比先写规格更快找到对的东西。
**判据**：做一版的成本 < 写清规格的成本，且没有多人协作/交接需求 → **不要用本流水线**，直接迭代原型。
本流水线的价值前提是「有人要交接、有人要验收、错了要追责」；一个人两小时能重写的东西，套十阶段是纯损耗。

## 十阶段总表

> ⭐ **架构正本是 `references/delivery-pipeline.md`**（专业产品主流程三段 + 四回路 +
> A/B/C 三锁 + 域权威 + 两次冻结）。本表只是执行编号的速查，冲突以正本为准。
> ⚠️ 出场条件里的编号（①、②a、②g…）是**历史追加序＝稳定引用键**（有跨文件引用，⛔ 不重排）；
> **它不代表执行顺序**——执行顺序只认行内「必须排在 X 之前 / 先跑」的显式声明，无声明处顺序不承重。

| 阶段 | 名称 | 输入 | 产出 | 角色 | 人拍板 |
|---|---|---|---|---|---|
| S1 | 需求/机会与问题澄清（用户给或**对话捕获**：四追问=范围/谁用/约束/成功长什么样，模板 `templates/intent.md` 五要素）—— **`intent-gate.py` 通过**（只查捕获结构与诚实留白，⛔ 不判想法对错——那归 S3B；S1→S2 对账仍由 chain-gate G0 补） | — | `input/definition.md`（问题陈述/目标/约束/未知） | **用户给** | — |
| S2 | 深度研究 | S1 **+ `scope.md` 已声明（开工=S1 交付物就位那一刻；S2 动手前必须存在）**（`flow-tailoring.md`；⛔ 裁剪必须开工前定，不许中途静默跳过） | 产品/视觉/交互三报告 + 原子功能账本 + 洞察账本 | 研究员 | 否 |
| **S3A** | **业务梳理** | S1+S2 | `business-map.md`（角色/现状流程/价值成本/指标树）—— **`business-map-gate.py` 通过**（四判据：角色真实/流程有卡点/指标有现值或 TBD/规则带后果） | 产品总监 | 否 |
| **S3B** | **产品定义与范围** | S3A | `definition-final.md`（覆盖下游 18 项）+ **增删提案表** + **Go/No-build**，或 `no-build.md`（合法产出）；⭐ 含 AI 时加 **AI 能力清单**：哪些功能用 AI · **为什么用** · **不用会怎样**（⛔ 答不出第三问的，多半不该用） | 产品总监 | **是** |
| **S4A** | **产品结构设计** | S3B | `product-structure.md`（功能架构/IA/任务流/对象权限状态关系）+ **四张图**：产品模块图（`M-xx`，⭐ 先业务域后模块，一圈=一个团队）· 产品功能架构图/功能树（`F-xx`，⭐ 拆到叶子可直接开发）· 信息架构+站点地图（`P-xx`，层级无回环）· **页面关系图**（`P-xx`，跳转拓扑有回环，⭐ 必须与 4.4 用户流程图一一对得上），判据见 `diagram-standards.md` —— **`product-structure-gate.py` 通过**（五判据：F-xx 落号/任务流有出路/权限矩阵/状态只用①类/零技术栈词；⭐ **`diagram-id-gate.py` 通过**——图与表 ID 对账三组：双向集合相等 / 颗粒度同族 / 跨章逻辑一致，差集非空即红） | 产品总监 | 否 |
| **S4B** | **PRD v0.9 产品基线** | S4A | **PRD v0.9**＝完整骨架（九章+附件结构齐；FR/NFR/AC 实写，设计相关项以 **OPEN 项清单**登记留空——`prd_completeness_check --stage S4` 允许设计列空即此义）+ **业务流程图**（五章）与**用户流程图**（4.4）+ **AI 产品四件套**（附件 B.3 算法与模型需求 · B.4 AI 数据需求 · C.5 数据生命周期图 · A.4 AI 效果验收）—— **`diagram-id-gate.py` 通过**（图与表 ID 对账；⛔ 图源非文本时它报 UNABLE 而不报通过） | 产品总监（5 视角轮换） | **是**（终审） |
| S5 | 体验方向与共同契约 | S4B | 视觉方向 + 交互原则 + scene/state/element/flow 契约；主导 **A 概念锁** | 设计总监（5 视角轮换） | **是**（A 锁批准） |
| S6 | HTML 可执行 UX 基准 | S4B+S5（与 S7 **并行协同**） | 交互稿（=demo：同一交互逻辑的 HTML 形式；目录版开发、bundle 单文件分发） | 演示工程 | **是**（B/C 锁交互半边） |
| S7 | Figma 高精度视觉母版 | S4B+S5（与 S6 **并行协同**；⛔ 不再等 S6 锁定） | Figma 文件 + 设计系统 | 设计执行 | **是**（B/C 锁视觉半边） |
| **G7.5** | **三方回灌与冻结** | A/B/C 三锁齐 | **PRD v1.0**（OPEN 项清零或显式延期，附件 M 回灌协议填齐）+ 三方对账记录 + ⭐ **第十五查：`diagram-id-gate.py` 通过**（六张图与表的 ID 对账无差集）且**图源文件已入库**；⭐ **第十六查（AI 产品）：附件 A.4 里标为「冻结阻断项」的技术指标全部达标** —— ⛔ 未达标即不予冻结；⚠️ 标「否」的观测指标**只记录不阻断**（别让一个观测指标卡住冻结）（⛔ 只有 PNG 没有 `.mmd`/`.d2` 源 ⇒ 下一轮没人改得动） —— **`g75-freeze-gate.py <项目根>` 通过**（本地六查真跑：OPEN/backfill/偏差/INS 处置/reconcile 在案/切片登记；原生证据三查缺则冻结上限=本地契约验证，报告模板 `templates/triad-reconciliation.md`） | 产品+设计+交互 | **是**（冻结） |
| **S8** | **技术、算法与测试方案** | G7.5 | **协作文档原生联合方案（飞书或钉钉）** + 可编辑技术架构图 + 模块接口/数据/存储/性能容量方案 + 算法/N-A 方案 + 七类测试方案 + 测试工程师/产品经理两次 GUI 实走预案 + `TECH/ALG/TEST/STD` 双向追溯 + `four-node-review` 终审预案 + 三专业批准/回读 receipt（⛔ 不得反向篡改产品合同） | 研发总监 + 算法负责人 + 测试负责人 | **是**（三方分别批准；算法 N/A 也须复核） |
| **S9.1** | 开发与持续验证 | S8 已批准（模板 `templates/s8-solution-plan.md`；偏离时同 commit 定位更新协作文档正本与镜像） | 可运行应用 + 按锚定 `coding-standards` 实施的 RED/GREEN、单元/组件/契约/集成与构建证据（**开发切片交付：模板 `templates/s9-dev-slice.md` + 门禁 `scripts/s9-dev-slice-gate.py`**——合同先行/RED-GREEN 绑 commit/AI 生成记录/算法离线评测门；⚠️ selfcheck≠代码合规；**降门槛监测 `scripts/bar-weakening-scan.py`** 扫本次 diff 抓抑制注释/删测试/剥断言/阈值改小/假实现，命中须豁免） | 研发 | 否 |
| **S9.2** | 工程测试、审计与质量验收 | S9.1 | **飞书或钉钉工程测试与四节点终审报告** + 功能/边界/接口/性能/安全/兼容无障碍/算法七域证据 + **测试工程师对当前构建的 GUI 全流程实走证据** + four-node 风险档/覆盖/收敛/证伪记录；`coverage_check.py`、`s9-quality-report-gate.py` | 测试负责人 + 研发/算法复核 | **是**（质量；必须 PASS） |
| **S9.3** | 产品经理 GUI 走查与四方一致性验收 | **S9.2 同构建 PASS** | **飞书或钉钉产品经理 GUI 走查与四方验收报告** + 产品经理基于冻结 PRD 的独立 GUI 实走 + PRD/Figma/HTML/最终应用分别对账 + 未批准高影响偏差清零；`s9-product-walkthrough-gate.py` | 产品负责人 + 设计/测试复核 | **是**（产品） |
| **S9.4** | 灰度与正式上线 | S9.3 | 灰度结论 + 监测/回滚条件 + 上线记录（**模板 `templates/s9-launch-rollback.md` + 门禁 `scripts/s9-launch-rollback-gate.py`**——放量梯度单向门/SLI 绑不可伪造数据源/回滚必须演练过） | 研发总监 | **是**（上线） |
| **S10**（流程效率账见 `references/flow-metrics.md`，工具 `flow-metrics.py`——只进复盘不做门禁） | **上线后复盘** | 线上数据（**无真实数据只能 PENDING**） | `retro.md` + 回流 `lessons.md` | 产品总监 + CEO | **是**（结论） |

**阶段有先决条件但各段有回路**（回路定义见架构正本）；`--from S4B` 断点续跑、`--only S6` 单跑；
`--only S3`/`--only S4` 可精确到 `S3A/S3B/S4A/S4B`。跳过先决条件会让 ID 链断掉，后面所有对账失效。
⚠️ 兼容：旧写法 `S3`＝S3A+S3B 顺做，`S4`＝S4A+S4B 顺做；自 2026-09-13 起 `S8` 只指联合方案，研发到上线整段用 `S9`＝S9.1→S9.4，复盘为 S10。旧 S8.x 编号不得混用，以免把“方案批准”误报成“研发完成”。

## 术语与编号体系速查（30 秒）

| 记号 | 是什么 | 正本在哪 |
|---|---|---|
| `F-xx / FR-xxx / AC-x` | 功能 / 需求 / 验收标准 | PRD（M1 ID 链起点） |
| `AF-xxx` | S2 原子功能（全部正式竞品按同一行集横向对账） | `research/atomic-feature-ledger.md` |
| `OPP-xx` | S2 机会（S3B 必须逐个给归宿） | `research/insights.md` |
| **`INS-xxx`** | S2 洞察条目（高强度的沉默消失即缺陷） | `research-decision-ledger.md`（洞察账本） |
| `ASM-xxx / TBD-xxx / SL-xxx` | 假设 / 待查数字 / 停止线 | `state.md` + `evidence-levels.md` |
| `DEC-xxx / DELTA-xxx / DEV-xxx` | 设计决策 / 回灌项 / 已批准偏差 | design-decisions / prd-backfill / deviation-register |
| **A/B/C 三锁** | 概念锁→代表切片锁→全量锁（S5/S6/S7 共同收敛的里程碑） | 架构正本 `delivery-pipeline.md` §四 |
| **切片** | B 锁选的 1–3 个代表画面（四覆盖类型） | `templates/slice-registry.md` |
| **原生证据三查** | 所选协作文档平台回读 / Figma 结构回读 / HTML 浏览器真跑 | `contract-manifest.json` + g75 门 |
| G0/G0.5/G0.6/G0.8/G0.9 | `chain-gate.py` 的链路前段对账方向（数量以门禁目录为准，不在此复述） | 门禁目录 `design-quality-gates.md` |
| G1/G2/G3 · G4 · G7.5 | `reconcile-gate.py` · `coverage_check.py` · `g75-freeze-gate.py` | 同上 |

## 两种入口

| 入口 | 什么时候用 | 怎么走 |
|---|---|---|
| **全流程** | 从零定义产品、要交接要验收 | **S1→S10** 顺序执行（⚠️ **S10 在上线后，别把它当可选尾巴**），`.product-flow/` 目录承载全部产物 |
| **单跑某阶段** | 手上已有上游产物，只要某一步 | `--only S6` 做 demo、`--only S8` 出协作文档技术/算法/测试联合方案、`--only testcases` 出独立测试用例、`--only S9` 跑研发到上线…… 此时**不需要建 `.product-flow/` 全套目录** |

⭐ 具名模块入口（等价于对应编号；合同表见 `flow-tailoring.md`「各独立模块的硬边界」）：
`--only business`=S3A · `definition`=S3B · `structure`=S4A · `prd`=S4B · `research`=S2 ·
`experience`=S5 · `interaction`=S6 · `design`=S7 · `core`=三锁束 · `solution`=S8 · `delivery`=S9.1→S9.4 · `testcases` · `retro`=S10 · `reverse`。
单跑一律走 flow-tailoring 的**七步小闭环**（Route→Intake→Gap→Work→Validate→Backfill/Handoff→Claim）。
⚠️ **单跑的入场条件以模块合同表为准**（SOP 表/总表的入场条件属于完整运行——那些跨阶段前置在单跑里按 Gap 三分法处理）；用例工程等「直接读某 reference 执行」的说法是七步里 Work 那一步读什么，不是绕过七步。

⚠️ 最常用的单跑是**用例工程**：手上只有一份别人写的 PRD，要出测试用例与覆盖对账 → 直接读 `references/s8-testcases.md` 执行，不必走前七阶段。
⚠️ 单跑时 ID 链只在本阶段内部成立，**跨阶段对账（M4）不适用**，报告里要写明「单跑，未做跨产物对账」，不要让人误以为整条链路都验过了。

## 【SOP】一页纸操作规程
> **这一节是操作规程本体。** 上面是理念、下面是细则，照着这张表就能跑。
> 每个阶段三件事：**进得来（入场条件）→ 做什么 → 出得去（出场门禁）**。
> **门禁不过不许进下一阶段** —— 带病进入的代价在后面每一步都要重付一次。

> **每阶段的入场条件 · 核心动作 · 出场门禁(硬性)详见 [`references/stage-playbook.md`](references/stage-playbook.md)** —— 渐进式披露:跑到哪个阶段再读哪一行,SKILL 只留骨架。

### 每阶段的视角表（收敛靠它，不是靠感觉）

| 阶段 | 必跑视角 | 出处 |
|---|---|---|
| S3 | 产品总监 · 竞品对标 · 用户旅程完整性 · **边界守卫** · **逆向（什么会让它失败）** | `references/s3-definition.md` |
| S4 | 产品总监 · 竞品对标 · 用户旅程完整性 · 研发可行性 · 商业化与运营成本 · **合规与数据边界** | 同上 |
| S5 | UI 专家 · UE 专家 · 研发负责人 · **多端一致性**（双端产品必跑） | `references/s5-s6-design.md` |
| 任何阶段终审 | **11 视角库全跑**（算法总监/UI/UE/市场/营销/CEO/研发/算法负责人/多端一致性/**AI Slop**/**架构与可演进性**） | `references/review-perspectives.md` |

⚠️ **视角表未跑满一遍不得宣告收敛**；快审（只跑 3-4 个）**必须在报告里标明是快审**。

### 三条贯穿全程的判据

1. **收敛 ≠ 我觉得可以了。** 收敛＝视角表跑满一遍、**连续两大轮零结构性发现**、每轮留痕可事后核（M3 + M5）。
2. **门禁绿 ≠ 东西是对的。** 每道门禁在被信任前必须先自证会出声：正例绿、每类反例红、无效输入报错不返绿（M8）。**没见过它变红，就等于没有这道门。**
3. **不知道就登记，绝不填空。** 每个事实只有三种出处：`[用户]` / `[查证·来源·日期]` / `[ASM-###]`。没有第四种，第四种就是编造。

### 最容易出事的三个交接口

| 交接 | 典型失真 | 挡它的门 |
|---|---|---|
| S4→S5 | 有功能没人设计 | M4 对账：每个 `F-xx` 是否都有交互说明 |
| S5→S6 | demo 看着完整实则漏演关键路径 | M4 对账：每个 `FR/AC` 有场景或显式「不演示·理由」 |
| S6→S7→S8→S9 | 方案遗漏设计状态；研发测了没人要的东西 | M4 双向对账：**正向漏与反向漏同等对待** |
| **md → 飞书/钉钉 / Figma / HTML** | **表格被静默压列、内容缺一大块而返回 success；远端被别人改过而本地不知道，下次覆写抹掉** | **M9 格式边界守卫** |

⚠️ **第四行是最容易被漏掉的一类交接**：前三行是「我的上游 → 我的下游」，
而第四行是「**我的产物 → 别人的系统**」。它不在任何阶段的内部，所以**每个阶段都以为它不归自己管**。

## 十一个贯穿机制（M1–M11 + M4b；每个阶段都要遵守，不是某一步的事）

> **全文见 `references/mechanisms.md`**（M1 ID 贯穿链 / M2 三来源 / M3 增量守卫 /
> M4 对账门+M4b 跨表一致性 / M5 证据独立 / M6 停止线 / M7 逃逸回流 / M8 门禁自证 / M9 格式边界 /
> **M10 结构口径规格**）。

### M10 · 结构口径规格（2026-09-17 立；治「门禁知道要什么，而执行者不知道」）

🚨 **立它的代价是一次可复现的失败**：按作业清单从零建一份 S2 语料，门禁开局 **40 条红**，
靠「改一处 → 跑一次 → 看报错 → 猜」磨到 24 后**不再收敛**。
根因不是语料缺内容，是**结构口径只活在 2260 行判据代码里，从未被写下来**。

**`spec/<stage>.json` 是单一真源，三处消费**：

| 消费方 | 工具 | 守它的判据 |
|---|---|---|
| 门禁判结构 | 各流程门禁 | `spec-check.py`：**双向对账** —— spec 写的门禁得认（正向）＋ 门禁认的 spec 得写（反向，防硬编码静默逃出规格） |
| 脚手架生骨架 | `scaffold.py` | `no-placeholder-left`：⟨TODO⟩ 没清空就红（⛔ 防「结构全绿内容全空」的假语料） |
| 文档写给人看 | `gen-docs.py` | `spec-doc-in-sync`：生成区手改或 spec 改了不重跑，都红 |

**四种门禁形态**（spec 的 `kind`）：`corpus`（S2 目录）· `single-file`（S3/S4A 模板）·
`single-file+perEntity`（S4 PRD 清单表+重复块）· `cross-artifact`（G0–G0.9 上下游对账）。

**收敛报告** `converge.py`：把红分成**结构红**（跑 scaffold / 改 spec）与**内容红**
（只能去做研究），并对比上次进度。⛔ **它不是交付判据** —— 交付只认门禁退出码 0。

⭐ **作者侧棘轮** `spec-authoring-gate.py`（§4.2）：改完 `spec/*.json` 立跑——对每阶段
「`scaffold` 生骨架 → `converge` 数结构红」，与 `spec/_structural-red-baseline.json` 比：
涨了＝这次把结构改坏（红）、无理由降基线＝腐烂（红）。把「改 spec 只在下游 corpus 门暴露、
磨 7 轮」的反馈提前到作者侧（改动任何 `spec/*.json` 之后跑）。

⛔ **三条纪律**：① spec **人工编写**，禁止静态反推（实测 6 对 2 错且错得自信，比没有更糟）；
② 结构性空格脚手架可填合法值，**内容性空格必须留 `⟨TODO⟩`**（判据：这个格子的值会不会被
读者当成研究结论）；③ 门禁说「数字对不上」时**先问是数字错了还是分类错了** ——
实测三个生成器被当成门禁，正解是登记豁免而不是改计数。

### 为什么这套 SOP 值得走
> > 「代码大概只占你带来的价值的 10–20%，另外 80–90% 在**结构化的沟通**里。」
> > —— Sean Grove, *The New Code*
>
> **代码是输出，规格是工作；代码是投影，规格是源。**
> 代码是**机器**执行的，规格是**人**对齐的。
> ⚠️ 「直接让 AI 写完得了」是可以试的——**它会快、会碎、会没法维护，
> 然后你花十倍的额度去修**。S2–S7 省下的正是这十倍。

### M11 · 落地细节必须可执行（2026-09-17 立；治「教训写了却读不到」）

**实证**：`references/competitive-research.md:503` 一字不差写着「⛔ 别取 `/json/list` 的 `t[0]`」，
连 QClaw 的 `#/sandbox-guard-bar` 都点名了。2026-09-17 重写遍历器时**照样踩进去**——
拿到 0 个控件，而脚本正常退出 0，差一点得出「这个产品界面是空的」这个错误结论。

**不是不够认真**：写代码时读的是任务与记忆，不会去检索一份 1300 行文档的第 503 行。
⭐ 同一次实测里的对照组：抄 `grab.sh` 的部分（启动 / 挪虚拟屏 / pkill）**一次通过**，
凭记忆重写的部分（WebSocket 处理 / target 选择）**全踩坑**。

⇒ **落地细节以可 require 的模块存在才有约束力；以散文存在等于不存在。**

| 形式 | 约束力 |
|---|---|
| 参考文档里的一段话 | **零**——写代码时不会被读到 |
| 可 require 的模块（`scripts/_cdp.js`） | 直接复用，绕不过去 |
| 机器检查（`cdp-reuse-gate.py`） | 自己重写一份就判红 |
| 脚手架生成 | 生成出来就是对的 |

**适用范围**：凡是「跑起来才知道、光读判据看不出」的落地细节——CDP 连接与枚举、
协作文档写入与回读、Figma 写入契约、浏览器节流与窗口摆放——都按这条办：
先抽成模块，再用门禁强制复用，⛔ 不要只写进文档就算解决了。

**判据自己的边界**：`cdp-reuse-gate` 只保证「不再各写一份、各踩一遍」，
⛔ 验不了复用之后用得对不对，也验不了被复用的正本自身正确。

**同理「一次只跑一件」**：竞品遍历每个都起浏览器 + node，并发会打爆内存——这条纪律以散文
存在照样并发照样爆，故变机器门 **`serial-orchestration-gate.py`**：竞品遍历只走唯一串行编排器
`competitor-sweep.mjs`（for…of + await，⛔ 无并发旋钮），退化成 `Promise.all` 或绕过它直起
`competitor-walk` 即红（改任何碰竞品遍历/编排的脚本时跑）。

## M1 · ID 贯穿链（正文已迁出）

> **M1–M9 全文见 `references/mechanisms.md`**（ID 贯穿链/对账门/证据等级/停止线等九机制的完整契约）。


## S10 · 上线后复盘（正文已迁出）

> **S10 专节全文见 `references/s10-retro-in-skill.md`**（四本账/决策质量账/因果性诚实声明），出场门禁见十阶段总表。


## 文件体系（跨会话续跑靠它）

```
.product-flow/
  state.md              ← 当前阶段/轮次/视角进度/阻塞/决策日志（唯一续跑依据）
  input/definition.md   ← S1 用户给的原始输入，只读不改
  research/             ← S2 五条线
    competitor-landscape.md ← 竞品双轴全景：直接/间接/替代/潜在进入者 × 头部/对手/越级/反面
    <竞品名>.md         ← 每家一份档案（含「它故意不做什么」与**为什么**）
    matrix.md           ← 公共维度 + 功能 + AI 条件矩阵（价值在空列与满列）
    key-flows.md        ← 同一任务关键流程对比图 + 可编辑图源 + 步骤/耗时/失败/恢复
    downstream-coverage.md ← 研究 ↔ PRD/Figma/HTML 双向覆盖与去向
    lines.md            ← 五条线结论「或本轮不做+理由」· 需求侧竞品 · Can't/Won't 判断
    insights.md         ← 码本 → 主题 → 核心范畴 → 机会 → 解法候选（给 S3 的判据）
    功能调研报告.md      ← 喂 S3 提案表 · PRD 3.2/第四章/附件 D/E　（飞书/钉钉一篇）
    设计视觉调研报告.md  ← 喂 S5.1 设计系统 · S7 Figma　　　　　　（飞书/钉钉一篇）
    交互调研报告.md      ← 喂 S5.2 交互规格 · S6 demo　　　　　　（飞书/钉钉一篇）
    sources.md          ← 每条结论可回溯到 URL + 访问日期
  definition-final.md   ← S3 产品定义（覆盖下游 18 项，模板 templates/definition-final.md）
  proposals.md          ← S3 功能增删提案表（每条带 S2 证据，单独成表等用户拍板）
  no-build.md           ← ⭐ 证据不支持做时的合法产出（停在这里是成功，不是失败）
  constitution.md       ← 可选：产品级不可违背原则 5–10 条，违反即 CRITICAL
  prd/                  ← S4/S5 PRD 本地副本（**选定的飞书或钉钉节点为对外正本**，这里留可 diff 的版本）
  business-map.md       ← S3A 业务梳理（模板 templates/business-map.md）
  product-structure.md  ← S4A 产品结构（模板 templates/product-structure.md）
  run-manifest.json     ← 本次运行合同（claimCeiling 硬上限；gate-run --status 读它分栏）
  contract-manifest.json← 三件套版本/回读账本（g75 门读它）
  slice-registry.md     ← B 锁切片登记 · deviation-register.md ← S9.3 偏差登记
  prd-backfill.md       ← 设计/交互 → PRD 的 DELTA 登记
  runs/<runId>/modules/ ← --only 单跑的不可覆盖 JSON 结果（按 moduleId/resultId 分层）
  gates/                ← gate-run.py 落盘的每道门结论 <门禁名>[.子门].json（G2/G3 分键，如 reconcile-gate.py.G2.json）
  spec/                 ← S5.2 机器契约组（operations/copy/validators/elements/states/flows/…）
  research/research-decision-ledger.md ← 洞察账本（INS 唯一登记处）
  design/
    taste.json          ← 品味档案（品味轴强信号 + 代际执行日志），`taste-memory.py` 维护
    design-brief.md     ← S5.1 设计简报（含 `<!-- taste-axes -->` 机读块）
    DESIGN.md           ← S5.1 唯一设计系统令牌，下游 demo/Figma 只读这一份
    PRODUCT.md          ← S5.1 产品上下文
    decisions.md        ← S5.1 设计决策记录（含决策权列）
  interaction-spec.md   ← S5.2 交互规格书（动效规格的唯一权威源）
  demo/                 ← S6 交互稿（目录开发 · bundle 分发）
  figma-link.md         ← S7 Figma 文件链接 + 各 F-xx 的 node-id
  handoff/              ← S8 联合方案受控镜像/接口契约/算法评测与测试用例集（选定平台节点是方案正本）
  quality/              ← S9.2 工程测试与 four-node 终审受控镜像/执行证据（选定平台节点是报告正本）
  reviews/rN-<视角>.md  ← 每轮评审留痕（M3 要求）
  reconcile/<交接>.md   ← 每次对账报告（M4 要求）
  lessons.md            ← 逃逸缺陷回流（M7 要求，跨阶段常驻）
  scope.md              ← ⭐ 流程裁剪声明（开工前第一件事，`flow-tailoring.md`）
  env.md                ← 运行前探测到的环境（Figma 账号/plan 等），不回写进 skill
  retro.md              ← S10 上线后复盘：**先给决定** + 四本账（模板 `templates/retro.md`）
  *.sync.json           ← 外发文档的结构指纹与远端指纹（`doc-sync-guard.py` 维护）
```

⚠️ `state.md` 是**唯一**续跑依据。清窗/换会话后先读它，不要靠对话历史——对话历史会被摘要，摘要会丢细节。模板见 `templates/state.md`。
⭐ **三个账本各管一域，不互为备份**：续跑进度问 `state.md`；门禁执行记录问 `.product-flow/gates/`（`gate-run --status`，按 `run-manifest.json` 分栏）；三件套版本与回读指纹问 `contract-manifest.json`。冲突时各归各域裁决，⛔ 不许拿一个账本的字段去顶替另一个的缺失。

## 各阶段执行

> 操作顺序看上面的 **【SOP】一页纸**；这里是每个阶段的**详细执行契约**，开跑对应阶段前必须读。

| 阶段 | 读哪份 |
|---|---|
| S2 深度研究 | 先选 `researchMode`：`teardown`（单品最细拆解）、`competitive-pack`（多竞品逐级横比）、`full-research`（五线全量研究）或 `tech-approach`（技术方案调研：对象=代码实现/技术机制/行业方案，为设计自家方案；判据读 `references/s2-tech-approach-runbook.md`，模板 `templates/tech-research-report.md`，出场门 `tech-research-gate.py --pre/--post`，不适用遍历族门禁），再选唯一 `documentPlatform`：`feishu` 或 `dingtalk`；共同遵守**先真实遍历、再写正文，颗粒度按实际能力自适应下钻到最细可独立验收单元**。执行主线读 `references/s2-research.md`，单品逐功能拆解读 `references/s2-teardown-runbook.md`，横向竞品规则读 `references/competitive-research.md`；模板分别为 `templates/competitor-teardown-report.md`、`templates/competitive-research-pack.md` 与 `templates/research-report.md`。任何正式交付都必须有逐功能正文、真实内联截图、状态/异常/恢复、证据事件账、下游 PRD/设计/技术/测试输入，并通过模式对应门禁与所选平台回读校验。 |
| **格式边界**（任何外发写入前后） | **`references/format-boundaries.md`** —— md ↔ 飞书/钉钉/Figma/HTML 会丢什么、会留下什么；**远端被别人改过**怎么发现；`doc-sync-guard.py` 用法；⭐ **消费侧边界**（一份 md 能证明什么、不能证明什么——摘要不得作下一阶段唯一输入，截图与结构元数据互不替代） |
| **S3 产品定义** | **`references/s3-definition.md`** —— 它做的是**从 S1 需求 + S2 调研中给出产品定义**（不是打磨 S1）；**覆盖下游 18 项** · 三候选生成 · **单向门 vs 双向门** · 逆向思维 · 前提挑战 · `no-build` 是合法结论。模板 `templates/definition-final.md`，门禁 `scripts/definition-gate.py` |
| S4 产品方案 | `references/s3-s4-product.md`　→ 配套 **`requirements-quality.md`**（需求的单元测试：五维度 · 措辞黑白名单 · 歧义扫描 · 最多问 5 个） ＋ ⭐ **结构口径规格**：`spec/*.json` 单一真源，三处消费（门禁判结构 / `scripts/scaffold.py` 生骨架 / `scripts/gen-docs.py` 写文档）—— `references/product-structure-gate.md`（S4A 结构门禁口径）· `references/chain-reconcile.md`（G0–G0.9 跨产物对账口径）|
| S5 设计交互 / S6 demo | `references/s5-s6-design.md`　→ 配套 `design-orchestration.md`（S5.1 编排 + 令牌单一真源 + 字体裁决）、`interaction-patterns.md`（**状态模型唯一权威源** / 响应时间矩阵 / 9 种交互模式）、**`motion-spec.md`（动效四问闸门 / 时长 / 缓动 / reduced-motion 降级）** |
| **设计规则集**（S5.1 先分类再动手） | **`references/design-rulesets.md`** —— 分类器（落地页 / 应用 UI / 混合）+ **三套规则集** + 七条硬否决 + Litmus 七问 + **可辩护的品味与 12 条认知模式** + 0–10 评分法 + 结构化评审语法 |
| **文案 Voice/Tone**（附件 F 的上游） | **`references/copy-voice.md`** —— Voice 三轴矩阵（锁定并写样例句）+ **九种语境的 Tone 表** + 可读性硬指标（句 ≤20 词 · **前置关键词** · 缩写是一种税）。⭐ **Voice 漂移＝读起来像十二个人写的** |
| **收尾横杆**（交付前，精细度 ≥8 必跑） | **`references/finish-bar.md`** —— **十道彼此没有共同盲区的 pass**；⛔ **没有理由的「延期」不是延期，是跳过**；⚠️ **跑垂直切片，不要在整个 app 上跑** |
| **工艺层**（把「正确」抬到「高级」） | **`references/craft-layer.md`** —— 构图与栅格 · **光学对齐** · 排印工艺（opsz/字偶距/悬挂标点/孤行寡行）· **色彩科学**（空间选型/OKLCH 色阶/序列色阶感知导数）· **情绪基调 × 强度两个正交旋钮** · **Delight 的可证伪定义** · 旋钮怎么动一档 · 锚点配方取什么 · **构图层 slop** |
| **视觉规格**（S5.1 正面做法） | **`references/visual-spec.md`** —— 排版 / 间距与留白 / 色彩 / 圆角 / 组件像素规格（可量化）＋ **质感·景深·光影**（⚠️ 本节不可自动验，只能人看） |
| **元素身份**（S5.2 填表 · S6/S7 对账） | 模板 `templates/interaction-spec.md` 的**元素标识表** → `scripts/element-identity-gate.py` —— ⭐⭐ **M1 的 ID 链管条目，管不到界面元素**：同一标识符必须原样出现在规格表 / `spec/elements.json` / HTML `data-el` / Figma 图层名 / 用例选择器**五处**。⛔ 命名**按功能不按内容**（`welcome-message` 坏在文案会变，`blue-button` 坏在把令牌钉死进名字）|
| **键盘契约**（S5.2 交互规格） | **`references/keyboard-contracts.md`** —— 逐控件的键盘行为契约（Tab/箭头/Home/End/Esc 各该做什么），取自 W3C APG 与 `microsoft/sonder-ui`。⛔ 「键盘可达」不等于「键盘好用」：能 Tab 到不代表箭头键在列表里能用 |
| **交互判据**（S5.2 硬约束 / S6 门禁） | **`references/interaction-criteria.md`** —— 18 条机械可查的反模式 + MUST/SHOULD/NEVER 全条目 + 状态判据（**数量以 `interaction-patterns.md` 为准**）+ Bans |
| **桌面交互四块** | **`references/interaction-desktop.md`** —— 多选与批量语义 · 右键菜单 · 撤销/重做/历史栈 · 快捷键冲突仲裁 · 焦点管理。**标 📐 的取自平台人机界面指南** |
| **门禁结果落盘**（全流程共用） | **`scripts/gate-run.py`** —— 跑一道门并把结论写进 `.product-flow/gates/<门禁名>.json`；`--status` 列出「哪些跑过 / 哪些从来没跑过」。⚠️ **退出码语义在门禁之间并不一致**（`prd_completeness_check` 的 `2` 是有缺口不是跑不了），语义表由元规则 `exit-semantics-declared` 守着 |
| **八类图的规范**（S4A/S4B/附件 N 共用） | **`references/diagram-standards.md`** —— 用户流程图（4.4）/ 业务流程图（五章，**主/分支/异常三类必画** + 六色图例）/ 功能架构图（6.2）/ 产品模块图（6.1，原称产品架构图）/ 信息架构+站点地图（6.3）/ **页面关系图（6.3.1，2026-09-15 新增）**/ 数据生命周期图 / 技术架构图 C4 的定义、必含元素、**基线档与 AI 追加档两档判定清单**、工具与交付链。⭐ **第一性约束：图与 PRD 必须 ID 对齐、颗粒度同族**——图里不许出现表里没有的东西，表里的东西也不许在该出现的图上缺席。⛔ 文首显式声明**哪些是标准、哪些是团队约定**（BPMN 没有 AI 节点记法；「产品/技术/系统架构图」三分法无国际标准；「生态层/优化层」查无依据不许写） |
| **多 agent 并行改本仓时**（协同期，不属十阶段） | **`scripts/coordination-gate.py`** + 路径所有权清单 **`references/path-ownership.json`** —— 各自改各自的，重叠区显式登记。合并前必须 `--merge-check <对方分支>`：**造出合并结果并在结果上**跑全套门禁。⭐ 2026-09-12 实测：两边分别都绿，**合完元门禁 41→39、零丢失变红** ⇒ ⛔「我这边是绿的」不构成合并依据。⚠️ 它**验不了**两边都对但合起来语义矛盾 —— 那层靠 `.proposals/` 闭环对话 |
| **改造本 skill / 开源共创**（先读架构与解耦地图） | **`references/architecture.md`** —— 四层架构（SKILL 地图 / L1 单一真源 / L2 逻辑模块 / L3 生成 / L4 门禁）· 模块依赖 DAG · **单一真源清单**（每个事实一个作者:改哪处、影响哪些）· 渐进式披露 · **怎么安全地加一道门/一个分类/一份参考/一个阶段** · 每次改完必跑。⛔ 改一处却波及一堆看似无关文件时回这里对照 |
| **改造本 skill 时**（维护期，不属十阶段） | **`scripts/no-loss-gate.py`** + 改名映射表 **`references/no-loss-renames.md`** —— 改结构/改章序/改名之前先 `--snapshot` 抽基线，改完跑差集：**旧的语义单元一条都不许消失**。⛔ 改名必须在映射表里登记，且新名必须真的存在（假登记挡不住）。⚠️ 它**验不了**内容有没有被改坏，那一层靠评审与变异测试 |
| **门禁总目录**（全流程共用） | **`references/design-quality-gates.md`** —— **46 道门禁 + 5 个专项扫描**的判据、用法与**诚实边界**；新增门禁不进这张表会被元门禁拦下。⭐ **每次阶段交接跑一次 `consistency-gate.py --project <项目目录>`** —— 查**交付物**里的声称≠实际（查证指针悬空 / 自称「自动生成」却没有生成器 / 正本路径指错）。⚠️ 2026-08-31 实测：这套门禁此前**只照自己**，交付物里的 8 个此类缺陷一个都没抓到 |
| **S6 端形态**（双端产品） | **`references/platform-parity.md`** —— PC 形态像 PC app、移动形态像移动 app：**必须不同的 12 项形式** vs **必须相同的 6 项实质**；配门禁 `scripts/platform-parity-gate.mjs` 与登记表 `templates/spec/end-differences.json` |
| **S7 建基座库** | **`references/figma-baseline.md`** —— Variables/Text Styles/Components 的完整 API 序列与坑；**开工前必须先探的两个底** |
| **任何阶段的多视角评审** | `references/review-perspectives.md` —— 11 视角库；⭐⭐ **九个薄视角已补完七个**（市场/营销/CEO/研发负责人/算法负责人/算法总监/架构，20 行 0 表 → 47–57 行 3–14 表）：唯一功能测试 · **砍到 MVP 的顺序表** · 激活漏斗五步必须填数 · **五秒测试必须找外人真做** · **增量交付切片表** · ⭐**技术债登记位**（此前全流程没有这个位置）· **AI 接口契约的产品侧那一面**（每格都是「用户看到什么」）· **单向门清单（S4 拍板，S8 拍不了）**；⛔ **视角 9/10 刻意不加厚**——它们的判据已在别处（模板三选一 / `ai-slop-gate`），**给已有判据的东西再叠一张表就是过度形式化**（铁律 38 用在自己身上）；视角 1/8 的边界已切清（含专问什么 + 典型发现 + 防锚定隔离机制），S4 终审 / S5.3 / S6 出场前都用它 |
| S7 Figma / S9 研发测试 | `references/s7-s9-build.md` |
| **S8 技术、算法与测试方案** | **`references/s8-solution-plan.md`** + 协作文档模板 `templates/s8-solution-plan.md` + 门禁 `scripts/s8-solution-gate.py` —— 技术架构图、模块接口、数据、存储、性能容量、算法/N-A、七类测试与 GUI 双角色实走共享一份接口/指标/失败合同；`coding-standards` 做适用映射，`four-node-review` 只配 S9.2 预案；选定的飞书或钉钉节点为正本，本地 md 为受控镜像 |
| **流程裁剪**（开工前第一件事） | **`references/flow-tailoring.md`** —— ⭐⭐ **被裁掉的环节和「跑了但没发现问题」的环节，在产物上长得一模一样** → 必须开工前一次性声明进 `.product-flow/scope.md` 并写「如果这个判断错了会怎样」。五问定档（⭐**第 3 问「谁来接」权重最大**：一大半机制存在的唯一理由是「有人要接手而他不在你脑子里」）。⚠️ **档位表是推演的不是跑出来的，当参考不当判据，且刻意不给它配门禁** |
| **证据等级 E0–E5**（S3 拍板必填） | **`references/evidence-levels.md`** —— ⭐⭐⭐ **「连续两大轮零结构性发现」是文档收敛的信号，不是市场风险收敛的信号**。单向门/S3 拍板最低 **E2**（和真实用户谈过）；⛔ 写 E0 不违规，**写了 E0 却不写停止线才违规** |
| **S10 上线后复盘** | **`references/s10-retro.md`** + 模板 `templates/retro.md` + 门禁 `scripts/retro-gate.py` —— ⛔ **只有实测值、没有决定的 retro 不算跑过 S10**；⭐**验证测量必须在验证效果之前**；⚠️**「没有变化」有三种来源**（机制没生效/样本不够/判据出界），样本不足要写「读不出来」 |
| **实质 vs 摆设**（S3 收口 · **S4 出场前必跑** · 任何一次门禁全绿之后） | **`references/substance-over-theater.md`** —— ⭐⭐ 门禁判的是「填了没有」，这一层判「填了但是不是家具」：**四种摆设**（人设/创新/NFR/愿景）· **互换测试**（换成竞品还成立＝没有信息）· **形态适配**（过度形式化与形式化不足**同样是缺陷**）· 七维度四档 · **RAT Top-5 假设按「错了产品就不成立」排序** |
| **技术方案就绪度**（S4 出场 · S7 定稿后各跑一遍） | **`references/techspec-readiness.md`** —— 判「S2–S7 够不够写出技术方案」（T1–T14）。⭐ 与用例就绪度对称：**不够就报缺口，绝不猜补**；⛔ 不存在「基本可以，我按常规假设一下」——**那是把技术假设伪装成需求** |
| **S8 测试方案 / 独立用例工程** | S8 联合方案的测试章读 `references/s8-testcases.md`；用例工程也可 `--only testcases` 单跑 → 配套 `testcases-readiness.md`（就绪度判定）、`testcases-design.md`（用例设计七类，含安全用例）、`testcases-adapters.md`（四种 PRD 形态）、**五件套模板 `templates/testcases-pack.md`**；对账门 `coverage_check.py` **四态退出码，0 才算完成（3=不能声称被测充分）**。⛔ 方案与用例生成不等于 S9.2 已执行 |
| **S9 质量与产品验收** | `references/s9-quality-gates.md`；S9.2 用协作文档模板 `templates/s9-quality-report.md` + `scripts/s9-quality-report-gate.py`，要求测试工程师对当前构建做 GUI 全流程实走；S9.3 用协作文档模板 `templates/s9-product-walkthrough.md` + `scripts/s9-product-walkthrough-gate.py`，只在同构建质量 `PASS` 后由产品经理依据冻结 PRD 独立 GUI 走查。S9.1 用 `templates/s9-dev-slice.md` + `scripts/s9-dev-slice-gate.py`（开发切片交付：合同先行/RED-GREEN 绑 commit/AI 生成记录/算法离线评测门）；S9.4 用 `templates/s9-launch-rollback.md` + `scripts/s9-launch-rollback-gate.py`（灰度上线回滚：放量梯度单向门/SLI 绑不可伪造数据源/回滚必须演练过）。⛔ `coding-standards`/`four-node-review` 只引用锚定正本；Node qa、自动化或测试录像都不能替代产品经理亲自验收 |
| **交付流水线**（PRD→Figma→回灌→HTML） | **`references/delivery-pipeline.md`** —— 三种终态形式的执行契约与顺序；**回灌是最容易被忘的一步** |
| 任何交接 | `references/reconcile-gate.md`　→ 跑 `scripts/reconcile-gate.py G1/G2/G3` + `coverage_check.py`(G4) |
| 想知道某条规则的依据 | `references/external-sources.md`（外部来源与取舍记录） |

## PRD 结构（S4/S5 的产出形态）（正文已迁出）

> **PRD 九章+附件 A–R 的结构说明见 `references/prd-structure.md`**；可执行模板是 `templates/prd-complete.md`（正本）。


## S7 · Figma 高精度设计稿（正文已迁出）

> **S7 专节全文见 `references/s7-figma.md`**（S7.0 探底/基座库/写后回读/G3 对账），API 细节见 `figma-baseline.md`。


## 铁律

> **全文 52 条在 `references/iron-rules.md`**（原编号保留，引用不断链；新铁律只追加；
> 每条的压缩层归属见该文件文末映射表，守卫 iron-rule-mapped）。
> 下面十条是它们的**压缩层**——记不住 52 条时，至少这十条不许破：

- **P1 顺序与回路**：阶段有先决条件；回退合法但必须留痕，⛔ 不许静默跳过或乱序（ID 链会断）。
- **P2 声称=实际**：每个「已完成/已验证」都要能指出证据；写下的能力必须真的存在。
- **P3 规则存在≠规则在守**：新增判据同增反例；改判据必反向测试；从没红过的门不可信。
- **P4 单一权威源**：同一事实只有一处可编辑（域权威表），其余是引用或生成物。
- **P5 沉默是缺陷**：截断/跳过/豁免/裁剪本身常常合理，**不说才是错**——「没查」与「查过没问题」必须可分辨。
- **P6 UNABLE≠通过**：跑不了、没跑、查不了都不许折叠成绿；NOT-RUN 更不是 N/A。
- **P7 交接处是事故高发区**：跨阶段/跨产物必须对账；ID 与对账表逐字传递，⛔ 复述会漂移。
- **P8 人拍板的不许代劳**：Go/No-build、终审、A/B/C 锁、G7.5 冻结、上线与不可逆操作。
- **P9 数字一律实测锚定**：能机械对账的不靠人记得改；带不了时间戳的缺陷计数不许写。
- **P10 门禁红了就停，全绿也不是背书**：门禁与提交分开命令，红着继续等于自己拆门；全绿只证明「没查出机械破绽」，好不好、值不值得做归评审与人的判断（铁律 15/39/44）。


## 工具映射与降级（本 skill 可分发，不得硬依赖某台机器）

> **各阶段首选工具与降级方案详见 [`references/tool-mapping.md`](references/tool-mapping.md)** —— 渐进式披露:本 skill 可分发不硬依赖某台机器,需要时再查。
