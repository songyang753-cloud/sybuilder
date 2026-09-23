# 交付流水线（架构正本）：专业产品主流程 · S1–S10 映射 · 三件套共同收敛

> **本文件是全流程唯一的架构正本**（2026-09-07 按 Codex 外审改造拍板重立）。
> 其他文件只许引用本文的流程与权威关系，不许自己再画一遍。
> ⛔ 旧版标题写「PRD → Figma → 回灌 → HTML」而 SKILL 写「S6 HTML → S7 Figma」——
> **两份最承重的文档把顺序写反了，26 条元门禁没有一条看得见**。教训：架构只能有一处。

## 一、专业产品主流程（上层真相）

S1–S10 是执行编号，不是流程本身。真正的流程是三段各带回路：

```text
一、产品发现    需求/机会 → 问题澄清 → 研究(用户/市场/竞品/相邻) → 业务梳理
               → 产品定义、范围与 Go / No-build
二、体验定义    产品结构设计 → PRD v0.9 产品基线
               → [核心体验闭环：视觉方向+交互模型 ⇄ Figma ⇄ HTML，A/B/C 三锁]
               → PRD v1.0 回灌 → 三方冻结(G7.5)
三、产品交付    技术、算法与测试联合方案（飞书） → 开发与持续验证 → 测试工程师 GUI 全流程实走 + 工程测试与审计
               → 产品经理 GUI 独立走查 + 四方一致验收
               → 灰度 → 正式上线 → 数据监测与复盘 → 回流下一轮
```

不是僵硬瀑布：阶段有先决条件，但每段内部有回路（见 §三）。
回退必须更新决策、版本与受影响产物，**不能静默改掉下游**。

## 二、专业步骤 ↔ S1–S10 执行编号

| 专业产品步骤 | 编号 | 核心问题 | 必须产物/决定 |
|---|---|---|---|
| 需求/机会与问题澄清 | S1 | 这是问题、机会还是预设方案？ | 问题陈述、目标、约束、已知/未知 |
| 深度研究 | S2 | 问题是否真实重要？已有方案与相邻机会？ | 产品/视觉/交互三报告 + 洞察账本 |
| 业务梳理 | **S3A** | 用户价值、业务价值、角色、现有流程、指标如何成立？ | `business-map.md`（角色/流程/价值/指标树） |
| 产品定义与范围 | **S3B** | 为谁做什么、不做什么、为什么现在？ | `definition-final.md` + Go/No-build（no-build 是合法产出） |
| 产品结构设计 | **S4A** | 功能、IA、任务、对象、权限、状态如何组织？ | `product-structure.md` |
| PRD v0.9 产品基线 | **S4B** | 哪些产品事实必须在设计前锁定？ | PRD v0.9（FR/NFR/AC/规则 + OPEN 项清单） |
| 体验方向与共同契约 | S5 | 该给人什么感觉、如何完成任务？ | 视觉方向、交互原则、scene/state/element/flow 契约 |
| HTML 可执行 UX 基准 | S6 | 所有操作、状态、反馈、恢复真实可运行吗？ | 交互稿（=demo，同一交互逻辑的 HTML 形式） |
| Figma 高精度视觉母版 | S7 | 最终视觉高级、贴合、完整且可维护吗？ | 可编辑 Figma + 设计系统 + 视觉检查点 |
| 三方回灌与冻结 | **G7.5** | 三件核心产物描述的是同一个产品吗？ | PRD v1.0、对账结果、偏差与批准记录 |
| 技术、算法与测试联合方案 | **S8** | 如何实现、算法是否值得用、哪些风险须怎样证伪？ | **飞书原生联合方案** + `TECH/ALG/TEST` 追溯 + 三专业批准/回读 receipt（⛔ 不得反向篡改产品合同） |
| 开发与持续验证 | **S9.1** | 每个纵向切片持续符合冻结三件套和 S8 方案吗？ | 代码 + 单元/组件/集成证据；偏离方案同 commit 回写 |
| 工程测试与审计 | **S9.2** | 风险、功能、算法、质量属性和失败恢复是否被真实验证，测试工程师是否从 GUI 真实入口完整走过？ | 飞书质量报告 + 七域测试/覆盖/four-node 证据 + 当前构建 GUI 主流程/分支/失败恢复逐步证据；结论必须 PASS |
| 产品经理走查与产品验收 | **S9.3** | 测试通过后，产品经理亲自操作时，产品是否正确、完整、清楚、好用且与 PRD/Figma/HTML 一致？ | 飞书产品走查报告 + 独立 GUI 实走 + 三条四方对账 + 未批准高影响偏差清零 |
| 灰度与正式上线 | **S9.4** | 可控放量？能监测、能回滚？ | 灰度结论、监测/回滚条件、上线记录 |
| 数据监测与复盘 | S10 | 价值发生了吗？哪些假设该保留或调整？ | `retro.md`；无真实数据只能 PENDING |

⭐ S3/S4 拆子阶段防两个常见错误：把业务流程当功能列表；结构未清就填 PRD 模板。
兼容：`--only S3` 允许精确选 `S3A/S3B`；`--only S4` 同理；不指定子阶段时按序全做。

## 三、四个运行回路

1. **产品发现** `S1 ⇄ S2 ⇄ S3A ⇄ S3B`：研究证明问题不成立 → `no-build.md`，不进结构与设计；发现新问题回 S1/S2，不在 PRD 里偷偷换目标。
2. **产品结构** `S3B ⇄ S4A ⇄ S4B`：结构暴露范围/权限/规则冲突可回产品定义；PRD 不得用文字完整度掩盖结构缺陷。此段可做早期技术/合规可行性咨询，但只验证可行性，不替工程锁协议/框架/存储/接口路径。
3. **核心体验** `PRD v0.9 ⇄ S5 ⇄ S6 ⇄ S7`：按 A/B/C 三锁共同收敛（见 §四）。体验验证发现产品问题 → 回 S4A/S4B 并记 `DEC-xxx` 与影响范围。
4. **产品交付** `G7.5 ⇄ S8 ⇄ S9.1 ⇄ S9.2 ⇄ S9.3 ⇄ S9.4`：S8 先让技术、算法与测试在写代码前对齐；后续发现不可实现或方案证伪 → 回 S8 或对应域权威重新决策，**不能由代码静默改产品**；S10 结论回流下一轮。

## 四、核心体验闭环：三条工作流 · 三个锁

⛔ **旧模型（S6 锁死 → S7 照 HTML 画）作废**。S5/S6/S7 是三条**协同工作流**，
Figma 与 HTML 互相验证；真正的时间里程碑是三个锁：

| 锁 | 内容 | 出场判据 |
|---|---|---|
| **A 概念锁** | 目标用户/关键任务/场景/成功指标；带 `INS-xxx` 的产品/视觉/交互原则；无既定品牌时 ≥3 个**成体系且实质不同**的视觉方向（构图/字形气质/色彩材质/密度/关键交互至少四项不同，换色不算）；SAFE 基线 + RISK 提案制（带收益/成本/可逆性/验证方法，默认 2–3 个；**零提案合法但须写理由**） | **人工批准**一个视觉命题与交互原则 |
| **B 代表切片锁** | 按风险选 1–3 个代表切片，覆盖：最核心完成路径 + 密度/层级最难一屏 + 一个错误/空态/权限/恢复场景 + （双端时）一个体现端差异的场景。同一切片在 Figma 与 HTML 用**同一份真实内容、同一 FR/AC/SCN/EL、同一状态与端声明** | 实际操作 HTML + 对照 Figma 视觉审查，人工批准 |
| **C 全量覆盖锁** | 全部适用页面/场景/状态/验证/权限/异常/恢复/端差异/键盘触控/动效及 reduced-motion；Figma 与 HTML 场景矩阵完整，无手写豁免掩盖的缺口 | 各门禁全绿 + 场景矩阵对账 |

分工：**S5** 主导 A（方向与契约）；**S6** 主导行为验证与 B/C 的交互半边；
**S7** 主导 B/C 的视觉半边。三者迭代靠 `DEC-xxx` 决策日志同步，不靠口头。

⭐ **交互稿与 demo 是同一件东西**（用户 2026-09-07 拍板）：同一套交互逻辑的 HTML 形式，
即「可执行 UX 基准」——开发用 `templates/proto/` 目录版（app mode），
分发时由 `demo-html` 的 bundle 构建单文件（share mode）；⛔ 不得出现第二套手写实现。

## 五、域权威与两次冻结

### 域权威表（谁对什么有唯一编辑权）

| 事实域 | 唯一编辑权威 | 其他载体 |
|---|---|---|
| 用户/问题/范围/功能/业务规则/权限语义/AC/指标 | **飞书 PRD** 对应段落 | 本地 md 是受控镜像；Figma/HTML 引用不改写 |
| 跨产物逐字一致的文案/枚举/校验/状态/流程步骤 | **`spec/*.json`** 对应记录 | PRD/Figma/HTML 消费同一 ID，不分别手写 |
| 构图/层级/排版/色彩/材质/组件外观 | **Figma 原生节点** | PRD 写产品含义+锚点；HTML 实现批准结果 |
| 视觉系统语义与令牌 | **`DESIGN.md` front matter**（从批准切片提炼） | `tokens.json` 与 Figma Variables/HTML CSS 均为生成物/对账物 |
| 导航/操作/反馈/状态转换/异常恢复/键盘触控/动效行为 | flow/state 契约定义预期，**HTML 运行结果**证明实现 | PRD 记产品含义；Figma 覆盖关键帧 |
| 技术决策/算法决策/测试策略及实施基线 | **S8 飞书联合方案**对应章节；OpenAPI/Schema/DDL/图源/评测配置/测试清单仍各自为机器权威 | 本地 S8 md 是受控镜像；S9 实现只消费并回写偏离，不另造方案 |
| 流程/决策理由/delta/评审记录 | 对应 **md** | 不承担原生视觉/行为/远端批准状态 |

冲突按域解决；跨域冲突由产品/设计/交互共立 `DEC-xxx`，更新受影响权威后其余载体跟随。
⛔ **没有任何一个文件可以跨域静默覆盖另一个。**

### PRD 两次冻结

- **v0.9（S4B 出场）**：锁问题/对象/范围/FR/NFR/业务规则/权限语义/AC/优先级/指标。
  允许 OPEN：最终 IA、页面组织、视觉层级、组件选择、微交互、动效、响应式细节、
  设计中才能定的文案——**每个 OPEN 项必须有 owner、决策阶段、回灌位置**。
- **v1.0（G7.5 前）**：Figma/HTML 定稿后回灌——最终 IA 与路由语义、关键任务交互序列、
  三类状态与恢复、最终文案与校验、键盘/触控/读屏/reduced-motion、端差异、
  组件与令牌摘要、Figma file/node 锚点、HTML route/scene 锚点、被采纳/拒绝的洞察与决策、
  已批准偏差。**回灌产品决策，不复制像素**；细节由锚点指向原件。
- **冻结失效**：PRD 修订/Figma version 或关键 node/HTML 构建或 flow/契约/DESIGN.md
  任一变化，旧三方冻结自动失效——只重跑受影响对账，但不得沿用旧 PASS。

---

以下为**执行细节**（工具命令与坑）。⚠️ 序号只是本页内的引用编号，
不再表示严格串行——③④ 在 B/C 锁里是并行协同的两条工作流。

---

## 第 0 步 · 开工前（一次性）

先建两份账本（模板在 `templates/`）：
- `.product-flow/run-manifest.json`（`templates/run-manifest.json`）——本次运行的模式/适用门禁/假设/**claimCeiling 硬上限**；`gate-run.py --status` 会按它分栏呈现
- `.product-flow/contract-manifest.json`（`templates/contract-manifest.json`）——三件套版本/锚点/回读账本，G7.5 的 `g75-freeze-gate.py` 读它
- `.product-flow/runs/<runId>/modules/<moduleId>/<resultId>.json`（`templates/module-result.json`）——独立模块的不可覆盖签发结果；由 `product-flow-run.py result/import` 生成和校验，不得手填或复用固定文件名

**原生证据 receipt（2026-09-11 接线）**：`contract-manifest.json` 的
`prd.readbackReceipt` / `figma.structureReceipt` / `html.runReceipt` 三项**只认 receipt**
（模板 `templates/evidence-receipt.json`，校验器 `scripts/receipt-check.py`）。
⛔ 裸时间戳（`lastReadbackAt` 等旧字段）**不再计入冻结上限** ——
此前三个任意字符串 `'T'` 就能把上限抬到 `integrated-frozen`，根因是
**时间戳由执行者手填自证**：没有签发方、没有原始证据指向、没有 live/test 之分。
receipt 由适配器在真实动作后签发（如 `doc-sync-guard.py readback` 写盘的回读凭据），
执行者只能引用，不能编造。
⚠️ 诚实边界：这不防伪造，它把伪造成本从「填一个 T」抬到
「编一整套带真实原始证据指向的凭据」；`environment=test` 的 receipt 即使有效也只证契约，
不解除真实声明上限。

B 锁开工时建 `.product-flow/slice-registry.md`（`templates/slice-registry.md`，四覆盖类型对账）；
S9.3 起用 `.product-flow/deviation-register.md`（`templates/deviation-register.md`，偏差的合法出口）。


```bash
# 本地稿目录
mkdir -p .product-flow/{prd,design,demo}
# 若已有飞书文档：登记它，后面每次写入都要比对指纹
python3 scripts/doc-sync-guard.py record .product-flow/prd/PRD.md \
        --url <飞书链接> --kind feishu
```

⚠️ **链接一旦发给别人就固定下来，一律原地更新，不新建文档换链接**（用户已定）。

---

## ①之前 · S2 三份调研报告（飞书，形式与 PRD 相同）

**S2 的产出不是内部资料，是交付物。** ⚠️ 与 PRD 同一口径：**飞书为对外正本**、本地 md 是受控镜像（写后必回读）。 三份定向报告各自一个飞书链接：
**功能调研报告**（喂 S3 提案表与 PRD 功能清单/详细设计/附件 D/E）·
**设计视觉调研报告**（喂 S5.1 与 S7）· **交互调研报告**（喂 S5.2 与 S6）。
三份合称**竞品体验报告包**；另有六个可独立消费的结构物：
`competitor-landscape.md`（双轴全景）· `atomic-feature-ledger.md`（原子功能词典、`AF×COMP` 事实长表、同分母横向面板与下游映射）· `matrix.md`（公共/功能/AI 条件矩阵）·
`key-flows.md`（关键流程对比图+可编辑图源）· `insights.md`（机会清单+优先级）·
`downstream-coverage.md`（双向对账 PRD / Figma / HTML）。完整契约见 `competitive-research.md`。

`competitor-landscape.md` 同时保存候选池、纳入/排除理由与按维度取证计划；
`key-flows.md#实测采集回执` 是 `RUN-xx` 的唯一执行事实正本。Web 由浏览器实测，macOS 原生应用
仅在用户对具体产品/版本/官方来源明确授权后下载并由 Codex Computer Use 遍历；报告和单体档案只引用回执，
不得各自复制一份授权、版本和覆盖数字。市场线执行时独立交付 `market-landscape.md`。

```bash
python3 scripts/research-gate.py research/                       # 出场门禁
python3 scripts/doc-sync-guard.py record research/<报告>.md --url <链接> --kind feishu
# 新建候选文档；已有文档用 --document，整篇重建须单独获准 --allow-overwrite
python3 scripts/_documents.py --platform feishu --title "调研报告" --source research/report.md --evidence-manifest research/evidence-manifest.json
python3 scripts/research-quality-gate.py --source research/report.md --review research/research-quality-review.md --phase final
```

⚠️ **调研的深度由下游反推**（`s2-research.md` 〇之二）：
下游要填附件 D 的字段规格，S2 就得实测竞品表单的字段与校验；
下游要填设计令牌，S2 就得量竞品的色值字距间距。
**只查「有没有这个功能」的调研，填不了下游任何一个字段。**
所有正式竞品还必须使用同一套 `AF-xxx` 原子功能定义逐项对账：
功能先拆到一个角色/触发/动作/状态变化/可观察结果，再为每个 `AF×COMP` 记录字段、规则、反馈、失败恢复、
权限/端/档位/限额与证据；Feishu 宽表可拆竞品列，但各面板不得删功能行或改变定义。
⚠️ 深度由下游反推，**广度仍必须高于下游**：替代方案、反证、潜在进入者、失败样本、
邻接模式与“竞品有而我们没有的”不得因当前 PRD 没有字段就被删掉。

## ① PRD 写作（S4B 出 **v0.9**，产出 md 本地稿；v1.0 在 G7.5 回灌后成形）

按 `templates/prd-complete.md` 搭**完整骨架**：正文九章 + 附件 A–R **结构齐**，
FR/NFR/AC 实写，**设计相关章节/字段以 OPEN 项登记留空**（这就是 v0.9）。
⭐ **九章填满＝G7.5 回灌之后的 v1.0**——S4B 不写设计结论。顺序上有两条硬约束：

1. **先写到「绝大部分完成」再去做设计**。判据＝**功能清单表不再增删行**。
   还在增删说明范围没定，这时候画稿是白画。
2. **第七章「设计稿」列先留空**，它在第 ⑤ 步回灌。
   ⚠️ **反过来做（先画稿再补 PRD）必然出现「稿子里有的功能 PRD 里没有」**，
   那部分不在任何需求文档里，永远不会被验收和测试覆盖。

**出场必须全绿：**
```bash
python3 scripts/prd_completeness_check.py .product-flow/prd/PRD.md      # 填没填
python3 scripts/requirements-quality-gate.py .product-flow/prd/PRD.md   # 写得好不好
python3 scripts/reconcile-gate.py G1 .product-flow/prd/PRD.md           # 功能↔交互↔验收
```

---

## ② 写入所选协作文档（形式转换 #1）

使用统一适配器，选择 `feishu` 或 `dingtalk`。本地 Markdown 只是源稿，不是远端完成证据。

```bash
python3 scripts/_documents.py --platform feishu --title "PRD" --source .product-flow/prd/PRD.md --evidence-manifest .product-flow/prd/evidence-manifest.json
```

已有文档传 `--document`。没有核实远端漂移、没有用户明确批准整篇重建时，不传
`--allow-overwrite`；不得为了绕过保护另建同名文档。局部更新只能使用当前官方 CLI/API
已经核实的能力；完成后仍对完整正文、媒体和版本回读。旧第三方 CLI 的定位语法不可复用。

### 正文与实图是同一交付

- 使用 Markdown 普通/引用式图片或官方本地资源写法，把真实截图/渲染图放在相关功能旁。
- 证据清单区分 GUI 截图与分析图，保留输入版本、文件哈希、用途和未证明内容。
- 先检查真实图片可解码及逐图隐私审核，再写入；不能用文件头或“见附件”冒充图。
- 逐段比较标题、文字、表格、链接、代码与顺序；正文丢失、否定词/数值变化均 FAIL。
- 上传原始返回与原生图片实体逐张匹配，核验媒体所在章节及同一远端版本。
- 同版本逐图映射不可获取时报告 UNABLE，保留候选源稿，不伪造媒体 ID。
- 最后逐页检查图片比例、文字可读性、邻接关系、表格和文末；只查首页不算完成。

### ⚠️ 三条会让你丢东西的地方

| 坑 | 表现 | 守法 |
|---|---|---|
| overwrite 销毁图片/白板 | 重建正文可能删除已有媒体及协作者修改 | 写前漂移检查、逐图上传映射；整篇覆盖须单独获准 |
| 多列表格被压列 | 远端少列、少行或错位 | 比较完整单元格、顺序和表头，再检查原生页面 |
| 静默失败 | 命令返回成功但正文尾部或媒体缺失 | 必须回读全文和同版媒体，不以返回码单独签收 |

### ⭐ 定稿之后：局部更新，不再 overwrite

⛔ 不许全文套一个推算偏移（实测同一篇 PRD 图表段 −2、功能段 −8）。定位以当前远端块和版本为准，不复用旧位置。
必须通过 `doc-sync-guard.py readback` 保存回读证据；旧第三方 `feishu fetch` 命令不再作为入口。
正文可声明本地图片，适配器必须先建立本版正文锚点再上传、绑定真实媒体；不是先写文字占位而不补图。
设计稿与交互稿完成后，链接必须回到 PRD 第七章的「设计稿」列，每行都要有。

---

## ③ Figma 工作流（形式转换 #2；与 ④ 并行协同，见 §四三锁）

**产品事实的输入是 PRD v0.9；视觉与 HTML 互相验证、共同收敛**——
⛔ 不再是「S6 锁死后照 HTML 画」：B 锁的代表切片在 Figma 与 HTML **同步做**。

```
S7.0  探两个底（不探就白干）→ addMode 模式数上限 · 中文字体可用性
S7.1  探索切片（≤B 锁）：按 A 锁批准方向画 1–2 屏真实内容 —— 允许直接写值，⛔ 不进正稿库
S7.2  B 锁批准切片 → 从切片**提炼**令牌，建基座库：Variables(Light/Dark) + Text Styles + Master Components
S7.3  跑 figma-editability-gate --strict —— 这是「基座真建成了」的可证伪判据
S7.4  全量铺开：按载体逐个 F-xx 画屏（两端功能出两套稿），全部组件实例+绑定变量
S7.5  每批写入后回读校验 + 再跑一次可编辑性门禁
```

细节见 `figma-baseline.md`（API 序列与坑）与 SKILL.md 的 S7 专节。这里只强调三条：

- **无基座不许铺全量；但基座从批准的切片提炼，不在真实视觉方向出现之前锁死**。
  没有基座就铺量，只会得到「每个色值都是硬编码、改一个圆角要改 60 处」的东西；
  反过来先锁令牌再画，会把探索钉死在没人看过的表格里——两个方向都是坑
- **图层命名带端与状态**：`F-03/PC/收藏筛选`、`F-03/移动端/收藏筛选`——G3 对账靠它
- **一次 `use_figma` 只做一个 section**，并 `return` 回传新建节点 id 供写后校验

---

## ⭐ 跑门禁的推荐方式：让结论落盘

```bash
# 直接跑：结论只在终端里，关掉窗口就没了
python3 scripts/definition-gate.py .product-flow/def/definition-final.md

# 落盘跑：同样的行为、同样的退出码，外加一份 .product-flow/gates/<门禁名>.json
python3 scripts/gate-run.py scripts/definition-gate.py .product-flow/def/definition-final.md

# 随时看：哪些跑过 / 哪些**从来没跑过**
python3 scripts/gate-run.py --status
```

⛔ **「一道门从来没跑过」与「跑过且通过」在项目里长得一模一样** ——
实测：验证项目 的 `.product-flow/reconcile/` 是空目录，而那份 PRD 有 431 条 AC，
G2/G3 从未产出过任何结论，无人察觉。
⭐ `gate-run.py` 不改任何门禁，只是让它的结论留下来。
⚠️ `--status` 只呈现，**不替你判断哪些「该跑」** ——「没跑过」不等于「不适用」。

---

## ④ HTML 工作流（形式转换 #3；与 ③ 并行协同，见 §四三锁）

```bash
# 场景锚点是硬契约，G2 对账靠它
# <section data-scene="f01-pc-empty" data-fr="FR-011,AC-1">
node scripts/scenario-matrix-gate.mjs .product-flow/demo/demo.html --states .product-flow/demo/spec/states.json --dump .product-flow/demo/anchors.json
python3 scripts/gate-run.py scripts/reconcile-gate.py G2 .product-flow/prd/PRD.md .product-flow/demo/anchors.json
node    scripts/browser-audit.mjs   .product-flow/demo/demo.html      # 浏览器档
python3 scripts/ai-slop-gate.py     .product-flow/demo/demo.html
python3 scripts/interaction-gate.py .product-flow/demo/demo.html
python3 scripts/visual-spec-gate.py .product-flow/demo/demo.html      # 静态档
```

⚠️ **静态档与浏览器档查的是不同的东西，不能互相替代**：
静态档看得到 `line-height:1.5`，看不到这一行实际排了几个字；
看得到 `color:var(--fg)`，算不出它在实际背景上的对比度。

⭐ **可直接改文案的交互稿**（借自 gstack `design-html`）：
给文本节点加 `contenteditable` + `MutationObserver` 重排 + `ResizeObserver` 重算，
评审的人可以**当场把文案改成他想要的样子**，而不是在会上口述。
这比任何静态稿都更快收敛文案——而文案往往是评审现场最大的分歧点。

---

## ⑤ 回灌（形式转换 #4，最容易被忘的一步）

设计稿与交互稿完成后，链接回到 PRD 第七章的「设计稿」列，每个对应功能都要有。
先更新受控源稿，再按②的当前官方适配器和授权边界更新原链接；核对双锚与完整回读。

```bash
python3 scripts/doc-sync-guard.py figma-anchors .product-flow/prd/PRD.md
python3 scripts/doc-sync-guard.py readback .product-flow/prd/PRD.md
```

**回灌的同时还要回灌三样**（否则设计成果只活在 Figma 里），
外加**反向锚**（2026-09-08 借鉴 SDLC playbook「Linkage as the minimum bar」——两边互记对方版本）：
把 `TRIAD-vX.Y + git 短 SHA` 写进 ①飞书 PRD「文档信息」表（一行）②Figma 封面页说明。
⛔ 此前只有 repo 单向记飞书/Figma 版本——从飞书侧看，无从知道它对应哪个冻结版本。
写完在 `contract-manifest.json` 置 `triad.reverseLinkWritten: true`（g75 原生三查通过时顺带核）。

| 回灌什么 | 到哪 |
|---|---|
| 设计稿链接（双锚） | 第四章「设计稿」列，**每行都要有** |
| 令牌摘要 + 组件像素规格 + **伸缩行为** | 附件 K |
| 动效清单（**七列**，含闸门答案、可打断、降级样子）+ **被否决的动效** | 附件 L |

⚠️ **设计稿展示「长什么样」，逻辑列写「怎么交互」，改了一边另一边必须同步。**

---

## ⑥ 每次跨形式之后：对账

| 交接 | 命令 |
|---|---|
| PRD → 交互稿 | `python3 scripts/gate-run.py scripts/reconcile-gate.py G2 <PRD> <anchors.json>` ⚠️ 见下 |
| 交互稿 → 设计稿 | `python3 scripts/gate-run.py scripts/reconcile-gate.py G3 <anchors.json> <figma-link.md>` ⚠️ 见下 |

⛔ **G2/G3 必须经 `gate-run.py` 跑**：落盘是**分键**记录（`reconcile-gate.py.G2.json` / `.G3.json`），
G7.5 第⑤查读的就是这两条——**裸跑不留痕＝NOT-RUN**，跑了也白跑。
| PRD ↔ 飞书 | `doc-sync-guard.py check <md> --readback <回读>` |
| 需求 → 用例 | `coverage_check.py <requirements> <cases>` |

⚠️ **G2/G3 对可运行原型不能直接传 `demo.html`。**
锚点是**运行时**写到 `body[data-scene]` 上的，静态扫 HTML 一个都取不到 ——
直接传会得到 `UNABLE: demo 里没有场景锚点`，而 UNABLE 最容易被当成「跑过了」耸肩带过。
先导出实测锚点，再拿导出的文件对账：

```bash
node scripts/scenario-matrix-gate.mjs <demo.html> --states spec/states.json \
     --dump .product-flow/demo/anchors.json
python3 scripts/gate-run.py scripts/reconcile-gate.py G2 <PRD.md> .product-flow/demo/anchors.json
```

2026-09-05 实测：真 demo 直接传 → `rc=2 UNABLE`；换成 dump（18 个实测场景）→ `rc=1` 才产出结论。
（场景稿式的旧 demo 仍可直接传 `demo.html`，按扩展名自动分流。）

⚠️ **对账不通过 → 回上一步补，不允许带病进入下一步。**

---

## 诚实边界

- 本文件规定**顺序与动作**，不规定内容质量。内容质量归门禁与 11 视角评审。
- 飞书、Figma 账号与 CLI 属于**本机专属**：换一台机器这些工具不存在，
  但**流程与判据不依赖它们**——把工具逐项换成当地等价物即可，
  **不要因为某个工具不存在就跳过该步骤**。
- 第 ⑤ 步回灌是**全流程最容易被忘的一步**，而忘了它的代价是：
  设计成果不在需求文档里 → 研发按旧稿做 → 测试按旧需求测 → 没有人发现。
