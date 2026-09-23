# 工具映射与降级(本 skill 可分发,不得硬依赖某台机器)

> 本表是 `SKILL.md` 同名段的外移正文(渐进式披露:需要查某阶段用什么工具/降级方案时再读)。

| 阶段 | 首选 | 降级 |
|---|---|---|
| S2 | `crawl-stack` / `firecrawl` / WebSearch → **出场跑 `research-gate.py`** | 手工检索并标注来源，覆盖面在报告里如实声明；门禁仍要跑 |
| S4/S5 PRD | **`templates/prd-complete.md`**（正文九章 + 附件 A–R，自包含） | 按本文 PRD 结构手写 |
| **S4 需求质量** | **`scripts/requirements-quality-gate.py`**（含糊形容词/占位符/无判据词/术语漂移/近重复/可追溯率）+ `requirements-quality.md` 的歧义扫描（人做） | 按五维度人工逐条核 |
| **S6 浏览器档** | **`node scripts/browser-audit.mjs <demo.html>`** —— 行长/留白/强调色占比/**实测对比度**/字体族数/命中区/**真聚焦量焦点环**/横滚/标题层级 | 人工在真实浏览器里逐条量 |
| S4 图 | 内置 `modules/diagramming` → SVG → CairoSVG/librsvg/本地 Chrome 转 PNG；中文字体由图中文字与渲染器实测确认 | Mermaid 源 + 同模块渲染 |
| **S2 竞品图** | **同上（同一条链）** —— 竞品侧的核心体验路径/模块图/功能树/页面关系图/关键流程图，⛔ 不另找工具：两套风格会让与 PRD 的「同构对照」失去意义 | Mermaid |
| S5.1 设计系统 | 内置 `modules/design-quality` 生成唯一 `DESIGN.md` + `tokens.json`；可选外部设计 Skill 只提供候选令牌或额外审查，不能成为硬依赖或第二正本 | 按内置 visual-spec 与模板手写 |
| **S5.1 验证** | 内置 `design-intent-gate` + `visual-spec-gate` + `token-provenance-gate` + `ai-slop-gate` + 技术可行性 checklist（含对比度）；外部 audit 只能增强 | 人工 WCAG checklist，结论标明未跑自动门 |
| **S5.1 品味** | **`taste-memory.py read`**（拿偏置当起点）→ 出场 `check --mode greenfield\|preserve\|overhaul` → 拍板后 `record` + `log-generation` **回写档案** | 首次无档案＝无偏置，正常发挥 |
| **S5.1 视觉** | `references/visual-spec.md` 五节可量化判据 + 第六节质感走查 | 按表手写 |
| **S5.2 动效** | `references/motion-spec.md` 四问闸门 → 时长/缓动表 → reduced-motion 降级表 | 按表手写 |
| **S5.2 交互** | `references/interaction-criteria.md`（判据）+ `interaction-desktop.md`（桌面四块）+ **`references/keyboard-contracts.md`**（逐控件的键盘契约，取自 W3C APG 与 microsoft/sonder-ui） → `scripts/interaction-gate.py` 验 | 按表手写 |
| **S7 基座库** | `figma-preflight` → `use_figma` 建 Variables(Light/Dark) + Text Styles + Master Components；写入受 `figma-style-binding` / `component-rules` 约束 | 无基座不许开画 |
| S7 原型转稿 | `prototype-to-figma`（demo → 按状态逐帧 + Dev Mode 标注） | 手工逐屏搭 |
| S5.2 交互规格 | `templates/interaction-spec.md` + `references/interaction-patterns.md`（**状态唯一权威源** / 响应时间矩阵 / 9 种模式） | 按模板手写 |
| S5.3 评审 | `references/review-perspectives.md` 11 视角全跑 | 快审 3-4 个最相关视角（**视角 10 不许跳**），**并在报告里标注是快审** |
| **格式边界守卫** | **`doc-sync-guard.py record` → 写入 → 回读 → `check --readback`**（核每张表列数/标题集合/图数；**本地未动而远端变了＝红，禁止覆写**） | 人工逐章比对回读结果，结论写进报告 |
| 协作文档写入 | `scripts/_documents.py` 统一入口；飞书官方 `lark-cli` 用户身份 / 钉钉官方 `dws`，均写后回读正文与图片实体（⚠️多列表格可能静默压列） | 输出 Markdown 候选稿由人工导入；只可报草案，不能报原生交付完成 |

| S6 | 内置 `modules/prototyping`（目录骨架、单文件 bundle、浏览器断言） | 纯手写单文件 HTML，仍须满足零外链与自测门禁 |
| S7 | `figma` MCP `use_figma` 直写（账号与前置见下） | 输出标注齐全的设计规格由设计师执行 |
| S8 | 飞书/钉钉统一文档适配器 + `s8-solution-plan.md` + `s8-solution-gate.py`；技术/算法/测试三专业评审；引用 `coding-standards`/`four-node-review` 锚定版本 | 选定平台不可用时交受控 md，最高 `review-ready`，⛔ 不冒充平台原生交付 |
| S9 | S9.1：`coding-standards` + TDD/构建链；S9.2：`four-node-review` + 测试工程师 GUI 操作能力 + `s9-quality-report.md` + `s9-quality-report-gate.py`；S9.3：产品经理 GUI 操作能力 + `s9-product-walkthrough.md` + `s9-product-walkthrough-gate.py`；S9.4：发布工具 | Web 用真实浏览器 GUI；macOS/移动端须先获授权再操作真实应用。无 GUI 能力或原物不可访问时记 UNABLE，不得用 API/DOM、旧录像或截图摘要冒充亲自实走；其余降级见 `references/s7-s9-build.md` |

**任何降级都必须在最终报告里显式标注**，不许悄悄降级后仍按满配汇报。
飞书适配器调用官方 CLI 时必须显式传 `--as user`；该参数属于 `lark-cli`，不属于统一入口。
⚠️ **协作文档写入一律写后回读校验**——飞书和钉钉都会**静默失败**，写入返回成功不等于内容进去了。链接发出后**原地更新**，不要新建文档换链接。
