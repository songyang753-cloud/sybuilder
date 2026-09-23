# product-flow 架构与共创指南(解耦地图·开源必读)

> 这份文件回答一个问题:**改一处,会影响到哪些别处?** —— 以及反过来:**要加一个阶段/门禁/参考,该只碰哪几处?**
> 它是本 skill 为开源共创准备的"边界地图"。⛔ 若你发现改一处却波及一堆看似无关的文件,多半是踩到了本文标记的"单一真源"或"模块边界"——回到这里对照。

## 一、四层架构(权威只存在于 L1,人读的一切要么是判断性散文、要么是 L1 的投影)

| 层 | 是什么 | 谁读它 | 改它的影响面 |
|---|---|---|---|
| **L0 `SKILL.md`** | 地图:十阶段骨架表 + 贯穿机制 + **`## 各阶段执行` 路由表**(每阶段→读哪份参考)+ 铁律 | 每次加载 | 只放骨架与指针;详版按需外移(见渐进披露) |
| **L1 单一真源(机器可读,不进模型上下文)** | `spec/<stage>.json`(结构口径)· `spec/_taxonomy.json`(八类图/附件分类)· `references/workflow-registry.json`(模块依赖 DAG/产物/门禁计划)· `spec/_audience.json` 等 | 脚本 | ⭐改这里=改真源,其余处自动跟随 |
| **L1.5 横切共享参考** | `diagram-standards` · `craft-layer` · `iron-rules` · `evidence-levels` · `review-perspectives` 等被多阶段引用者 | 多模块 | 改它波及所有引用方——**动前先 grep 谁引了它** |
| **L2 模块(逻辑,非物理)** | 每个阶段(S1…S10)= 路由表一行 + 它 owns 的参考 + 模板 + 门禁;⛔ **references/ 保持扁平不按阶段建文件夹**——因为参考天生跨切面(如 `visual-spec.md` 被十余个文件引用),强塞进单一 stage 文件夹会造成假归属+断相对路径(2026-09-20 分析实证) | 跑某阶段时按路由加载 | 模块边界=依赖 DAG(见下) |
| **L3 生成层 `gen-docs.py`** | 把 L1 的口径/分类生成进参考文档的 `<!-- SPEC:BEGIN -->` / `<!-- TAXONOMY:BEGIN -->` 标记区 | —— | 改生成区无效(会被 `--check` 判红);要改先改 L1 再跑生成器 |
| **L4 门禁(drift-catcher)** | `consistency-gate`(元门禁,46 条)+ 各阶段门禁 + `no-loss-gate`(改 skill 自身时) | 交接/维护 | 见门禁总目录 `design-quality-gates.md` |

## 二、模块依赖 DAG(改上游必然波及下游,反之不然)

```
S1 → S2 → S3A → S3B → S4A → S4B → S5 →(S6 ∥ S7)→ G7.5 → S8 → S9.1 → S9.2 → S9.3 → S9.4 → S10
```
正本=`references/workflow-registry.json` 的 `modules.<stage>.dependencies`。**改某阶段的产物契约,只需回归它 + 直接依赖它的下游**(如改 S4B PRD 结构 → 影响 S5/S6/S7/G7.5,不影响 S2/S3)。TESTCASES / REVERSE 是独立入口(deps=[])。

## 二·B、双轨制与产物温度(把「文档形态 / 工程形态」显式化)

⭐ **本 skill 的阶段不是同质一条线,而是两条性质不同的轨,用一个冻结门缝合。** 每个模块在
`workflow-registry.json` 声明 `track` 与 `temperature`,门禁 `track-temperature-declared` 强制。

| track | 阶段 | temperature | 纪律(不同轨不同) |
|---|---|---|---|
| **doc 文档轨** | S1 意图 · S2 竞品调研 · S3A/S3B 定义 · S4A/S4B PRD · S10 复盘 · REVERSE | **anchored 锚定真源** | 交付件**本身就是最终产物**,留存、不可当可丢弃派生物;表结构是契约不许删列;**变更走 delta+归档**(见「单一真源」第 3.x 与 openspec 借鉴);互换测试(换品牌还成立=没信息) |
| **design 设计轨** | S5 体验策略 · S6 HTML · S7 Figma | **anchored** | 设计稿/令牌/交互规格是真源;A/B/C 三锁收敛;渲染出来的方向切片才是评审对象 |
| **eng 工程轨** | S8 技术/算法/测试方案 · S9.1–S9.4 研发验收上线 · TESTCASES | **source(spec 即源、代码是投影)** | spec 变=重新生成/对齐代码;S9 走 **/converge:对照冻结 PRD 读真实代码找缺口,「声明不算证据」**;测试是一等公民 |
| **seam 缝合** | **G7.5 三方冻结** | **gate** | 文档轨真源锁定 → 工程轨据此展开的**单向决策门**;冻结后文档轨改动必须回 G7.5 重新批准 |

**为什么要显式分轨**(治的病):
- ⛔ 别把**文档轨**当"可丢弃投影"——竞品调研/PRD 是最终交付物,不是待再生成的中间态(否则与"竞品调研正本/表结构是契约"冲突)。
- ⛔ 别把**工程轨**当"写完就完"——代码要回对 spec(/converge),声明不算证据。
- ⭐ 两轨在 **G7.5** 缝合:这是"文档真源"移交"代码实现"的唯一单向门,对应 spec-kit 的 discovery→delivery `decide gate`。

## 三、单一真源清单(⛔ 每个事实只有一个作者,别处都是投影或指针)

| 事实 | 唯一真源 | 别处怎么拿 | 守它的门 |
|---|---|---|---|
| 门禁道数 / 脚本数 / 用例数 / 视角数 / NFR 类数 / 阶段数 | 由脚本**实时算**(`_roster` / git 跟踪 / `.selftest-measured.json` / `review-perspectives` / `single-source`) | ⛔ 别在散文里手写会漂移的数;写了就被 gate-count/script-count/… 对账 | gate-count · script-count · perspective-count · selftest-count-measured · single-source |
| 八类图 / 附件 A–R 分类 | `spec/_taxonomy.json` | prd-structure 表由 gen-docs 生成 | spec-doc-in-sync |
| 各阶段结构骨架(章节/表/列) | `spec/<stage>.json` | 参考文档 SPEC 区由 gen-docs 生成;scaffold 生骨架 | spec-doc-in-sync · spec-check |
| 门禁名册 | `scripts/_roster.py` | 消费方全走它,⛔ 不各 glob 一套 | gate-roster-single-source |
| 标题/段落解析 | `scripts/_section.py` | 其余脚本委托它 | section-parser-single-source |
| 门禁退出码语义 | `gate-run.py` 的 `EXIT_SEMANTICS` | —— | exit-semantics-declared · gate-registered |
| 状态模型分类 | `interaction-patterns.md` | 别处引用不复述数量 | —— |
| 模块依赖/产物/门禁计划 | `workflow-registry.json` | —— | —— |

## 四、渐进式披露(SKILL 只当地图,详版按需加载)

主文件 `SKILL.md` 不放详版正文——已外移的:`references/stage-playbook.md`(一页纸操作规程详表)· `references/tool-mapping.md`(工具映射与降级)· 铁律/机制/PRD 结构/S7 的正文各有 `(正文已迁出)` 指针。
⚠️ 外移含门禁名的段落时,记得 `gate-wired` / `gate-stage-match` 读的是 `SKILL.md` 的 `## 十阶段总表`→`## 铁律` 段 **+ `stage-playbook.md`**;新增外移点若含独有门禁名,要把新文件加进这两门的读取面(见 `consistency-gate.py` 对应两条)。

## 五、怎么安全地加一个 X(改动面清单)

- **加一个门禁**:① `scripts/<name>-gate.py`(带 `--self-test` + `_main_guarded` 兜底 + 绿/红都带 ⚠️ 边界句)② `gate-run.py` EXIT_SEMANTICS 登记 ③ `design-quality-gates.md` 目录加行 ④ `SKILL.md`/`stage-playbook.md` 对应阶段挂上名 ⑤ `consistency-gate.py` GATE_TEMPLATE_PAIRS 或 GATE_PAIRING_EXEMPT 登记 ⑥ 跑 `selftest-all.py` 重测 → 同步用例数。⭐ 漏一处元门禁会精确报出。
- **加一个分类项(图/附件类)**:改 `spec/_taxonomy.json` → 跑 `gen-docs.py` → git diff 验只增标记。
- **加一份参考**:建 `references/X.md` → 在 `SKILL.md` `## 各阶段执行` 路由表挂入口(否则 reference-reachable 红)。⭐ 若它不归任何单一阶段(跨阶段基础设施),改在 `consistency-gate.py` 的 `MODULE_INFRA_REFS` 登记归属+理由——**`module-ownership` 门强制:没有无主参考**(改一处影响面才可界定)。
- **加一个阶段**:`workflow-registry.json` modules 加节点 + dependencies;十阶段总表 + stage-playbook + 各阶段执行路由三处挂上。

## 六、每次改完必跑(交付判据,不是可选检查)

```
python3 scripts/gen-docs.py --check      # L1→L3 一致
python3 scripts/consistency-gate.py      # 元门禁 46/46
python3 scripts/no-loss-gate.py          # 改 skill 自身时:语义单元零丢失
python3 scripts/selftest-all.py          # 改了任何带 --self-test 的脚本时:重测用例数
```
⛔ 门禁全绿只证明**机械上干净**,证明不了**这份物料是好的**——那需要判断(见 `substance-over-theater.md`)。
