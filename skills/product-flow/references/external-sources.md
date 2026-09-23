# 外部来源与取舍记录

2026-08-16 做的一次外部调研：本机全量 skill 盘点 + GitHub 高分 skill 检索，逐条判断吸收或拒绝。
**留这份记录是为了让「为什么这么设计」可追溯**——否则半年后没人知道某条规则是拍脑袋还是有依据。

## 一、调研范围（诚实说明读到什么程度）

| 对象 | 做了什么 | 深度 |
|---|---|---|
| 本机 `~/.claude/skills` | 全量 115 个 SKILL.md，逐个提取 name/description/行数/references 数 | 描述层**全量**；结构层对 planning/review/design/QA 类提取 H2/H3；正文**只深读了自建 6 个 + gstack `spec`** |
| gstack 套件（约 40 个） | diff 比对发现 7 个 planning/review skill 的 H2 结构**完全相同**，约 1000~1900 行里绝大部分是共享外壳（Preamble/Voice/Telemetry/AskUserQuestion 格式等） | 用 diff 提取差异段，只读独有内容 |
| `ComposioHQ/awesome-claude-skills`（72k★） | 提取产品/设计/测试/工程流程四类条目 | 列表层全量，个别条目深入 |
| `shanraisshan/claude-code-best-practice`（64k★） | 「从 vibe coding 到 agentic engineering」实践综述 | 全文要点提取 |
| `omkamal/pypict-claude-skill` | PICT 成对组合测试方法 | 全文要点提取 |
| `avelikiy/great_cto` | SDLC 流水线 / QA 结构 | README 要点提取 |

⚠️ **诚实边界**：115 个 skill 中**未逐字通读全部正文**——gstack 单个 skill 1000~2000 行、共享外壳占绝大部分，全文通读的边际信息极低而上下文代价极高。读法是「描述全量 + 结构提取 + 差异 diff + 相关者深读」。若某次需要精确复用某个 skill 的内部机制，仍需现场打开该文件读。

## 二、吸收了什么（每条标明落点）

| # | 来源 | 内容 | 落到哪 |
|---|---|---|---|
| 1 | `claude-code-best-practice` | **垂直切片（tracer bullet）优于水平分层**——AI 天然按层拆，导致端到端反馈推迟到最后 | `s3-s4-product.md` S4 硬约束、`s7-s9-build.md` S9.1 |
| 2 | gstack `spec` | **量化门槛**：「若干文件」「提升性能」不可接受，必须给确切数字与指标 | `s3-s4-product.md` S4 硬约束 |
| 3 | gstack `spec` | **失败模式六问**：空 / null / 超大 / 重复提交 / 错误角色 / 调用两次 | `s3-s4-product.md` S4 异常场景判据 |
| 4 | `claude-code-best-practice` | **共同盲区三解法**：换干净上下文再审 / 换模型审 / 对抗式提问（"向我证明这行得通"） | `SKILL.md` M3 诚实边界 |
| 5 | `claude-code-best-practice` | **「原型 > PRD」的反对意见**：构建成本足够低时不该走重流程 | `SKILL.md`「何时不用」 |
| 6 | 本机 `four-node-review` | **门禁三态契约**：假绿 / 假红 / 误导性红三个方向都会错，须有 `UNABLE` 第三态 | `s7-s9-build.md` S9.2 硬约束 |
| 7 | `pypict-claude-skill` | **成对组合覆盖（pairwise）** + 参数/约束建模 + **何时不该用**（空间小可穷举、缺陷需 3+ 参数交互） | `testcases-design.md` 第 6 类 |
| 8 | `great_cto` | **变异测试思路——让测试怀疑自己**：假想需求被改坏，问「有没有用例会失败」，没有则是假覆盖 | `s8-testcases.md` ④.5 |

## 三、明确不吸收（写清理由，避免下次重复讨论）

| 来源 | 内容 | 不收的理由 |
|---|---|---|
| `claude-overkill` | 生成极繁替代方案并按复杂度评分 | **与本机第一写码纪律「简单优先」正面冲突**。用户的准则是 200 行能压到 50 行就重写 |
| `great_cto` | 69 个专家子 agent 编队 | 本机会话规则禁用子 agent 调用；且历史偏好是少而精的 skill，不是 agent 编队 |
| gstack 各 skill | Preamble / Telemetry / Artifacts Sync / Question Tuning 等共享外壳 | 那是 gstack 自己的运行时约定（写自家 analytics 目录），与本 skill 无关，照抄只会引入无用样板 |
| `great_cto` | 网传的「12-angle code review」 | ⚠️ **查证后其 README 中并不存在这个说法**，不引用未经核实的内容 |
| BMAD | Epics / User Stories / Success Metrics / RICE | 已在流程标准阶段判定：排期/工单部分应由项目管理工具承担，不进 PRD；Success Metrics 此前已被用户拍板删除，是空转字段 |
| 各类项目管理集成（Jira/Linear/Asana…） | 工单系统自动化 | 与本流水线正交，需要时单独调用即可，不进流程契约 |

## 三之二、2026-08-16 补充调研：验证工具自身的可信度（落到 M8）

| 来源 | 星数 | 内容 | 落点 |
|---|---|---|---|
| `mbj/mutant` | 2179★ | 命题本身：**"AI writes your code. AI writes your tests. But who tests the tests?"** | M8 开篇 |
| `goldbergyoni/javascript-testing-best-practices` | 24.6k★ | **「传统覆盖率经常说谎」**——覆盖率只记录测试走过哪些行，不确认它断言了正确结果（护照盖章类比）；变异测试判据：**变异存活＝测试没在测东西**；无断言测试＝100% 覆盖 0% 测试；skip 制造"全部通过"假象；占位数据 `Foo` 永远走不到真实分支（Positive-false）；手工 try-catch 代替预期抛错会掩盖真实失败点 | M8 变异测试节 + 已知假绿形态 |
| `stryker-mutator/stryker-js` / `infection/infection` | 3014★ / 2233★ | 变异测试是成熟工程实践、有多语言工具生态，非自创概念 | M8 佐证 |
| superpowers `writing-skills` | 本机插件 | **对照组（no-guidance control）**：对照组不出问题就没有可修的东西；**人工读每条命中**——自动计数会同时高估失败与成功 | M8 四步自证第 4 步 + 对照组节 |

⚠️ 采纳理由：本流水线四类失效形态（fail-open / 结论掩盖 / 假阳性 / 覆盖静默缩水）**全部真实发生过**，其中「结论掩盖」和「假阳性」是本次 2026-08-16 演练当场撞到的。外部资料提供的是**判据与命名**，实例来自本机。

## 四、复核提示

外部实践会变。**引用外部结论时一律带来源与查证日期**（本文所有条目均为 2026-08-16 查证）。
若某条外部实践与本机真实教训冲突，**以本机踩过的坑为准**——那是有证据的，外部是别人的语境。


---

## 五、2026-08-31 补充调研：PRD 侧 + gstack 深读（落到需求质量与设计规则集）

上一轮（08-30）只做了设计/视觉/交互的外部仓（16 个），**PRD 侧与 gstack 是空白**。本轮补齐。

### 本机 gstack 套件（19 个 skill，约 2.6 万行；共享外壳占 64–86%，用行集合求交切出独有段）

| 来源 | 内容 | 落点 |
|---|---|---|
| `plan-design-review` | **12 条认知模式**（Rams/Norman/Krug/Zhuo/Ive/Gebbia 谱系）+ **「taste is debuggable」** | `design-rulesets.md` 第七节 · 铁律 18 |
| `plan-design-review` | **0–10 评分法**：不是 10 就说清 10 长什么样 → 改到那儿；**<7 分直接产出那个 10 分的样子** | `design-rulesets.md` 第八节 · 视角 2 ⑤ |
| `design-review` / `plan-design-review` | **分类器 + 落地页/应用 UI/通用 三套规则集** | `design-rulesets.md` 第一至四节 · 铁律 17 |
| `design-review` | **结构化评审语法**（我注意到 / 我好奇 / 如果…会怎样 / 我认为…因为…） | `design-rulesets.md` 第九节 |
| `design-review` | 浏览器实测设计系统提取（字体族/调色板/标题层级/触控目标） | `browser-audit.mjs` |
| `design-html` | **contenteditable + MutationObserver 的可改文案交互稿**；`document.fonts.ready` 后再量 | `delivery-pipeline.md` ④ · `browser-audit.mjs` 等字体 |
| `design-shotgun` | **反收敛的可证伪判据**：「换掉标题文案没人看得出差别 = 两个方案太像」 | 待并入 S5.1（见「未采纳/待办」） |

### 外部（GitHub，2026-08-31 查证）

| 来源 | ★ | 内容 | 落点 |
|---|---|---|---|
| `github/spec-kit` | 132318 | **「检查表 = 需求的单元测试」**；五质量维度；**措辞黑白名单**；可追溯 ≥80%；**生成者不许勾自己的框** | `requirements-quality.md` 一~四节 |
| `github/spec-kit` | 同上 | **歧义扫描分类法**（10 类打 Clear/Partial/Missing）+ **影响×不确定性排队 + 最多问 5 个** | `requirements-quality.md` 五节 · `s3-s4-product.md` |
| `github/spec-kit` | 同上 | `analyze` 的六类检测（重复/歧义/欠规格/覆盖缺口/不一致/宪章冲突） | `requirements-quality-gate.py` 的六条规则 |

### 明确不采纳（写清理由，避免下次重复讨论）

| 来源 | 内容 | 不收的理由 |
|---|---|---|
| spec-kit | `.specify/extensions.yml` hook 机制 | 那是它自己的运行时约定，与本流水线正交 |
| spec-kit | `constitution` 完整治理体系 | 过重；只取「产品级不可违背原则，违反即 CRITICAL」一条，落成可选的 `.product-flow/constitution.md` |
| gstack | 共享外壳（Preamble / Telemetry / Artifacts Sync / Voice / Question Tuning 等，占 64–86%） | gstack 自家运行时约定，照抄只会引入无用样板 |
| gstack | `$D` 设计二进制（mockup 生成 / 比较板 / vision 质量门） | 本机不存在该二进制；**但它的「比较板收集结构化反馈」思路优于 AskUserQuestion 选方案**，记为待办 |

| `ui-styling`（gstack/claudekit） | shadcn/Tailwind 具体栈 | 与本 skill「与技术栈无关」的定位冲突；项目已用该栈时按项目规范走 |
| `pm-agent-harness-kit` | 60+ 个 PM 细分 skill（RICE/OKR/北极星…） | 与本流水线正交，需要时单独调用；且排期/工单类此前已判定不进 PRD |


### 2026-08-31 追加采纳：Taste Memory（用户当场拍板「引入，收敛在品味、发散在执行」）

| 来源 | 内容 | 落点 |
|---|---|---|
| gstack `design-shotgun` | 跨会话品味档案 · **5%/周置信衰减（读时算）** · 冲突时提示而非静默覆盖 | `scripts/taste-memory.py` · `design-orchestration.md` 〇之二 |

**采纳时做的三处改动（不是照搬）**：
1. **切出两轴**。gstack 只有「偏好」一个概念；本 skill 已有「跨代反收敛」与之冲突。
   判据定为：**换掉它，用户会说「这不是我要的方向」还是「这个也行，甚至更好」？**
   ⭐ 由此发现**老规则本身切错了地方**——它把「明暗方向」放进了发散轴，而明暗是最典型的品味。
2. **加两条纪律 gstack 没有的**：`n≥2` 才构成强信号（三选一里选中一个是 best of 3，不是「我爱这个」）；
   **否决权重是认可的 2 倍**（人会接受平庸，只会明确拒绝真正不要的）。
3. **明确降级为偏置而非判据**：它永远不许把方案判成不合格，只在偏离时要求写理由。
   **做成硬门禁会让品味固化，而固化的品味就是 slop。**

**不采纳**：gstack 的 `<工具工作目录>/projects/$SLUG/` 路径约定与 schema 迁移逻辑（本机路径专属）。


---

## 六、2026-08-31 第二轮：工艺层（本机 36.6 万行盘点 + 新外部仓）

用户指出广度与深度不足，本轮把本机**全部 110 个**产品/设计/交互相关 skill（md 合计 36.6 万行）
做了盘点，并补了上一轮没碰的外部仓。

### 本机（此前只读过摘要，本轮下钻）
| 来源 | 体量 | 取了什么 | 落点 |
|---|---|---|---|
| `cc-design/references` | **2.46 万行设计理论** | 栅格四型 · 基线网格 · 模块化比例（音程） · F/Z 阅读模式 · 三分法 · **光学对齐** · opsz/字偶距/悬挂标点/孤行寡行 · **情绪基调决策树** | `craft-layer.md` 一~四章 |
| `web-design-engineer/style-recipes` | 25 个真实品牌配方 | **配方的七块结构**——尤其 **Signature moves**（眼前一亮的来源）与 **Don't use when**（锚点何时不适用） | `craft-layer.md` 七章 |

### 外部（GitHub，2026-08-31 查证）
| 来源 | ★ | 取了什么 | 落点 |
|---|---|---|---|
| `educlopez/ui-craft` | 298 | **「Delight is specificity, not decoration」**＋四类候选按安全性排序＋按动效强度门控；**bolder/quieter 的有序操作手册**；**similar-prompt 自测**；**首屏构图 10/10 坍缩的实测证据** | `craft-layer.md` 五/六/八章 · 铁律 18 |
| `meodai/skill.color-expert` | 565 | 色彩空间选型表 · OKLCH 色阶 · **令牌三层图（组件永不直引参考层）** · **序列色阶的 flat perceptual derivative 判据** · 不要用 coolors.co | `craft-layer.md` 三章 |
| `originaleric/dig-ui-skill` | 229 | **运行时/后台专项 anti-tells**（执行页不做营销 hero · 不用装饰性假终端 · 不用 glow 替代状态与层级） | `craft-layer.md` 九章 |

### 明确不采纳
| 来源 | 内容 | 理由 |
|---|---|---|
| `color-expert/references` 140+ 篇 | 色彩史/色彩神秘学/鸟类四色视觉等 | 是百科不是判据；只取 SKILL.md 里可操作的部分 |
| `ui-styling` (shadcn/Tailwind) | 具体栈的组件与主题 | 与本 skill「与技术栈无关」的定位冲突 |
| `AThevon/genjutsu` | Compose/AGSL/3D 创意编码 | 平台专属（Android/Compose），与本流水线正交 |
| `addyosmani/web-quality-skills` | Core Web Vitals 细则 | 性能已在 NFR 与「性能即设计」里覆盖；细则属工程侧，需要时单独调用 |


---

## 七、2026-08-31 第三轮：外部仓扩到 32 个（用户要求 ≥30 并全部落盘）

全部落盘在 `<外部skill下载目录>/` 下三个目录，可复核。

### 本轮新下载并深读（12 个）
| 仓 | ★ | md 行数 | 取了什么 | 落点 |
|---|---|---:|---|---|
| `educlopez/ui-craft`（全量） | 298 | 110300 | **craft-intent 的三个正交旋钮 + variance 默认值表** · **当代默认坍缩三簇** · **二阶反射检查** · **签名赌注候选清单** · **finish-bar 十道 pass** · **copy.md 的 Voice/Tone 体系** | `craft-layer.md` 四之二~四之四 · 新 `finish-bar.md` · 新 `copy-voice.md` · 铁律 18–20 |
| `meodai/skill.color-expert`（全量） | 565 | 24359 | 色彩空间选型 · OKLCH 色阶 · 序列色阶感知导数 | `craft-layer.md` 三 |
| `Ryan-yang125/motion-lexicon` | — | 5686 | **动效必须由事件发起** · **为状态变化预留空间** · ⭐**可打断性** | `motion-spec.md` 新增三条 + 规格表加「可打断？」列 |
| `hamen/material-3-skill` | 1339 | 4302 | M3 组件目录（作为组件规格的权威参照之一） | 权威正本表 |
| `senlindesign/taste-skill` | 325 | 1196 | 从网站反推设计品味 → 具体令牌 | 与 `taste-memory` 互补，记为待评估 |
| `superdesigndev/superdesign-skill` | 486 | 2248 | 设计流程编排 | 与现有 S5 重叠，未采纳 |
| `carmahhawwari/ui-design-brain` | 875 | 1544 | 组件知识库 | 与 M3 重叠 |
| `csthink/dashmotion` | — | 1424 | 仪表盘动效 | 并入 anti-tells 场景 |
| `AThevon/genjutsu` | 297 | 15770 | Compose/AGSL/M3-expressive | 平台专属，未采纳 |
| `arvindrk/extract-design-system` | 193 | 505 | 令牌提取 | 与 `token-provenance` 重叠 |
| `deanpeters/Product-Manager-Skills` | — | 60631 | 60+ PM 细分 skill（JTBD/精益 UX 画布/发现流程…） | 与流水线正交，需要时单独调用 |
| `kwakseongjae/oh-my-design` | 472 | 657303 | 400+ 质量门控组件 | 素材库，非方法论；未采纳 |

### 累计 32 个仓（三个目录）
`_design-research/` 20 个（08-30 首轮：emilkowalski · figma/mcp-server-guide · hallmark ·
huashu-design · ux-ui-agent-skills · designer-skills · web-interface-guidelines · motion-design-skill ·
effective-html · ui-skills · stitch-skills · claude-design-system-prompt · scroll-craft ·
refactoring-ui-plugin · tinte · ui-aesthetics-skill · **HIGAgentSkills · aria-practices ·
act-rules · statecharts**）
`_prd-research/` 1 个（github/spec-kit）
`_design-research-2/` + `_research-3/` 共 11+ 个（本轮，见上表）

### 本轮明确不采纳（写清理由）
| 来源 | 理由 |
|---|---|
| `oh-my-design`(65 万行) | **素材库不是方法论**——400+ 组件是可复制的成品，不产生判据 |
| `genjutsu` | Android/Compose/AGSL 平台专属，与「与技术栈无关」的定位冲突 |
| `superdesign-skill` / `ui-design-brain` | 与已有 S5 编排与 M3 目录重叠，无新机制 |
| `Product-Manager-Skills` 60+ 个 | 与流水线正交（JTBD、定价、组织建议…），需要时单独调用；不进流程契约 |
| `color-expert/references` 140+ 篇 | 色彩史与色彩神秘学是百科，不是判据 |


---

## 八、2026-08-31 第七轮：S3 产品定义（外部仓 40 → 50）

⚠️ **用户三次修正了本阶段的定位**，这三句是本轮的骨架：
1. 「产品定义说的是 **S3 定义收敛**」
2. 「S3 **从名字上看收敛，其实做的是产品定义的事情**」
3. 「S3 做的是**从 S1 用户需求 + S2 调研和分析中，给出产品的定义**」
→ 于是 S3 从 `s3-s4-product.md` 里的 52 行附属段，独立成 `s3-definition.md`（206 行）。

### 本轮新下载（10 个，落在 `<外部skill下载目录>/_def-research/`）
`Fission-AI/OpenSpec`(★66705) · `buildermethods/agent-os`(★5351) · `gsd-build/gsd-2`(★7771) ·
`gemini-cli-extensions/conductor`(★3714) · `Gentleman-Programming/agent-teams-lite`(★1249) ·
`modu-ai/moai-adk`(★1191) · `doncheli/don-cheli-sdd` · `ductienuit/SpecForge` ·
`scottconverse/productteam` · `avelikiy/great_cto`

### 采纳（每条标明落点）
| 来源 | 内容 | 落点 |
|---|---|---|
| `great_cto/agents/product-owner.md` | **WHAT 与 HOW 分离，且 WHAT 是唯一的人工闸门**——「**这是最贵的决定，因为你要到六个阶段之后才知道它错了**」 | `s3-definition.md` 〇 · 铁律 34 |
| 同上 | ⭐⭐ **「不做这个」是最高价值的产出之一**：把每个想法都验证通过的产品负责人是没用的 → `no-build.md` 是合法产出 | 〇 · 铁律 34 · 文件体系 |
| 同上 | **框定 → 生成 → 辩论 → 综合** 四步（评审只能改进已有方案，不能产生更好的） | 第三节 |
| 同上 | ⚠️ **未被闸门批准的 brief 不一定更差，但声称有签名而其实没有，是整条流水线接下来赖以为基的谎言** | 拍板状态如实标注 + 门禁 |
| gstack `plan-ceo-review` | ⭐⭐ **单向门 / 双向门**（可逆性 × 量级）：**大多数是双向门，快速决定；只为不可逆+高量级放慢** | 第五节 · 铁律 36 |
| 同上 | **70% 信息就足以决定**（但只适用于双向门） | 第五节 |
| 同上 | **逆向反射**：问完「怎么赢」必须问「**什么会让我们失败**」 | 4.2 · 视角 5 · 模板第十二节 |
| 同上 | **专注即减法**：主要价值是决定**不做什么**（Jobs 从 350 砍到 10） | 第六节 |
| 同上 | **理想态映射**（现状 → 本方案 → 12 个月理想态三段对照） | 4.3 · 模板第十四节 |
| gstack `office-hours` | **前提挑战**：是不是正确的问题？是不是最直接的路径还是在解决代理问题？什么都不做会怎样 | 4.1 |

### 明确不采纳
| 来源 | 理由 |
|---|---|
| `moai-adk`(107 万行) / `gsd-2`(9.4 万行) 的编排框架 | 它们是**完整的开发流水线**，与本 skill 定位重叠而非互补；只取思想不接入 |
| `great_cto` 的 69 个 agent 编队 | 与本机偏好（少而精）冲突，且此前已判定过 |
| SDD 系各仓的目录与命令约定 | 本流水线用自己的阶段编号 |

## 2026-09-03 · 设计与交互专项（58 个仓）

语料在 `<外部skill下载目录>/_design-research/`（本轮 58 个 + 08-30 那轮 20 个）。
**只登记真的改动了本 SOP 的那些**，其余是背景。

| 仓（★） | 拿它改了什么 |
|---|---|
| `w3c/aria-practices`（29 个模式）· `microsoft/sonder-ui`（**做过可用性研究**的 7 个） | 新建 `references/keyboard-contracts.md`（逐组件键盘契约）+ `templates/spec/keyboard-flows.json` + `spec-sync-gate` 的 `keyboard-covered` 规则 |
| `google-labs-code/design.md`（27k★，给编码 agent 的视觉身份格式规范） | `DESIGN.md` 改为 **YAML front matter 承载令牌**的单一源；`tokens.json` 由 `design-to-tokens.py` 生成。格式脱胎自 `design-tokens/community-group`（W3C DTCG） |
| `memi-design/design-skills` 的 `review-animations`（承 Emil Kowalski / animations.dev） | `interaction-gate` 第 17 条 `keyframes-on-transient`（**把「可打断性」从只能人工变成可查**）+ 第 18 条 `scale-from-zero`；并**独立佐证**了我原有的 `ease-in-on-ui` 与 `duration-over-budget`(300ms) 两条阈值 |
| `alphagov/govuk-design-system` · `primer/design` | 状态模型补 `pressed`（≠ `active`）与 `visited`；并得到一个可用的经验分布：govuk 语料里 `error` 259 次 vs `empty` 14 次 |
| `dequelabs/axe-core` | **没有内置**（要 vendor 约 600KB，与「可分发」冲突），改为在门禁目录里写清**无障碍覆盖边界** |

### ⭐ 这一轮学到的选材判据

⛔ **不是「星星多就抄」**：`plugin87/ux-ui-agent-skills` 的 `ux-writing` 只有 30 行，
比我现有的 `copy-voice.md`（73 行，含 Voice 三轴 / 九种语境 / 可读性硬指标）**薄**，
所以一个字没抄。
⭐ 真正有价值的是那些**把我说「只能人工」的事变成可查**的（review-animations 就是），
和那些**给我已有阈值提供出处**的（300ms 从哪来）。


---

## ⭐ 附：可核实的来源清单（2026-09-04 建）

> ⚠️ **为什么单列这一节**：`.proposals/interaction-revamp-2026-09-02.md` 里写着
> 「91 仓 / 6010 篇文档」。那个数字来自一次下载跑，**而下载目录已被清理，现在无从复核**。
> 按本 SOP 自己的规矩（实证数字要配一条可复跑命令），
> 一个不可核实的数字不该继续以事实的形态存在。
> ⇒ 这里把**能点名的**逐条列出，并明写哪一部分已不可核实。

**可核实 53 个**（本文与 `platform-parity.md` 逐条点名过的）：

- `AThevon/genjutsu`
- `ComposioHQ/awesome-claude-skills`
- `Fission-AI/OpenSpec`
- `Gentleman-Programming/agent-teams-lite`
- `OnsenUI/OnsenUI`
- `Ryan-yang125/motion-lexicon`
- `addyosmani/web-quality-skills`
- `alphagov/govuk-design-system`
- `arvindrk/extract-design-system`
- `avelikiy/great_cto`
- `buildermethods/agent-os`
- `carmahhawwari/ui-design-brain`
- `cc-design/references`
- `color-expert/references`
- `csthink/dashmotion`
- `deanpeters/Product-Manager-Skills`
- `dequelabs/axe-core`
- `design-tokens/community-group`
- `doncheli/don-cheli-sdd`
- `ductienuit/SpecForge`
- `educlopez/ui-craft`
- `framework7io/framework7`
- `gemini-cli-extensions/conductor`
- `github/spec-kit`
- `goldbergyoni/javascript-testing-best-practices`
- `google-labs-code/design.md`
- `gsd-build/gsd-2`
- `hamen/material-3-skill`
- `infection/infection`
- `ionic-team/ionic-framework`
- `kwakseongjae/oh-my-design`
- `mbj/mutant`
- `memi-design/design-skills`
- `meodai/skill.color-expert`
- `microsoft/sonder-ui`
- `microsoft/vscode-webview-ui-toolkit`
- `modu-ai/moai-adk`
- `omkamal/pypict-claude-skill`
- `originaleric/dig-ui-skill`
- `plugin87/ux-ui-agent-skills`
- `primer/design`
- `references/keyboard-contracts.md`
- `scottconverse/productteam`
- `scripts/platform-parity-gate.mjs`
- `scripts/taste-memory.py`
- `senlindesign/taste-skill`
- `shanraisshan/claude-code-best-practice`
- `spec/copy.json`
- `spec/validators.json`
- `stryker-mutator/stryker-js`
- `superdesigndev/superdesign-skill`
- `w3c/aria-practices`
- `web-design-engineer/style-recipes`

**本机仍有 tarball 可查的 25 个**（`/tmp/*.tgz`，与上表有重叠）：

`OpenSpec`、`Product-Manager-Skills`、`SpecForge`、`agent-os`、`agent-teams-lite`、`conductor`、`dashmotion`、`don-cheli-sdd`、`extract-design-system`、`genjutsu`、`great_cto`、`gsd-2`、`lenny-skills`、`material-3-skill`、`moai-adk`、`motion-lexicon`、`oh-my-design`、`productteam`、`skill.color-expert`、`superdesign-skill`、`taste-skill`、`ui-craft`、`ui-design-brain`、`ultraship`、`user-research-skill`

⛔ **不可核实的部分**：当初那次下载的总量（提案称 91 仓）**大于**上面能点名的数量，
差额部分的仓库名**没有落档，现已无法复核**。

⭐ 结论按可核实的部分陈述：**已点名 53 个高星外部仓库**，
其中设计/交互侧的关键来源（Ionic 52.6k · Framework7 18.7k · Onsen UI 8.9k ·
`microsoft/vscode-webview-ui-toolkit` 2.1k）在 `platform-parity.md` 里
逐条标了用途与实测数字。

📌 **下次的做法**：下载脚本要**同时写一份 manifest 落档**，
否则「下载了 N 个」这句话在目录被清理的那一刻就变成了不可核实的声称。

---

## 平台设计规范外链核验（2026-09-08）

用户指定四条平台设计规范入口（清单正本在 `platform-parity.md`）。核验实况：
Apple HIG（cn/layout）、微信小程序、Ant Design overview-cn 均 200；
**Android 用户原链接 `developer.android.google.cn/design/ui/mobile/guides/layout-and-content/canonical-layouts` 已 404**
（连英文版同路径也 404——搜索索引还留着旧地址），现行页迁至
`developer.android.com/develop/adaptive-apps/guides/canonical-layouts`（zh-cn 200）。
⚠️ 这类官方文档会搬家：引用前重核，死链更新正本清单并在此记一笔核验日期。
