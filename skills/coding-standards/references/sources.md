# 来源清单

本文引用三组独立语料，**互不重叠**（99 个唯一仓库，全部经 GitHub API 核实存在与星数，0 个 UNABLE，2026-09-03 起采集；见文末合计）：

| 表 | 数量 | 供给哪一层 | 是什么 |
|---|---|---|---|
| **表一** | 50 | **基础层 P** | 编程规范 / 准则类文档（style guide、best practices、principles、cheat sheet） |
| **表二** | 30 | **AI 协作层 K** | agent skills / AGENTS.md 规则 / cursorrules（给 AI 写码用的规则集） |
| **表三** | 19 | **权威层 Z**（阈值 / 安全条目 / 分级制度） | 两类混合:**正式规范**（阿里 p3c / 腾讯 / Google / Microsoft / OWASP / OpenSSF / CNCF / ISO C++——供给可引用的具体条款）+ 少数**体系性佐证资料**（ByteByteGo 图解 / awesome-scalability 列表等——仅佐证「这类语料成体系」,**不是条款出处**,见文末诚实边界)。两者角色不同,别把后者当规范条文引用 |

**三表零重叠，合计 99 个唯一仓库。**

⚠️ **两表的证据强度不同**（也写进了 SKILL.md 的诚实边界）：
表一是**成文多年、被大量项目采用**的规范；表二多数是 2025–2026 年的新仓库，条款来自它们**对自己在治什么的声明**——我核实了仓库与正文，但**没有独立复现它们声称的失效率**。

---

# 表一 · 50 个编程规范 / 准则仓库（供给基础层 P）

**采集方式**：`gh search repos` 跑 40 组关键词（coding standards / style guide / clean code / best practices / secure coding / api guidelines / testing / conventional commits / SRE 等），去重后得 1074 个候选；按「**是规范性文档**（guide / standard / checklist / principles），不是工具、不是设计模式代码示例、不是无关项目」筛出 50 个。50 份 README 正文已抓取（2.8MB）用于共识提取，未凭印象复述。

⚠️ **诚实边界（2026-09-10 外部评审收窄了其中最要紧的一条）**：

1. 我核实了每个仓库的**存在与星数**（2026-09-05 逐个复核：99 个全部仍存在、星数偏差全部 <15%，
   1 个上游改名已修正），并对 50 份正文做了主题共识统计；**没有**逐条验证每份文档内部的每个断言。
2. ⚠️⚠️ **「50 份独立规范」这个说法站不住**，别把它当证据强度：这 50 个里混着
   **索引/清单型仓库**（awesome-* 这类，它本身不主张任何条款）、**反面教材**（unmaintainable-code）、
   **Clean Code 的多语言移植**（同一个上游，算不上互相独立）、以及 SRE/system-design 这类
   **体裁不同的资料**。⇒ 它们既不全是规范性文档，也**不彼此独立**。
3. 更要命的是**统计口径**：下表数的是「**多少份文档提到这个主题**」，
   而「提到测试」和「在这一条上与我们一致」是两件事（本 skill 自己的
   **「数『提到』≠数『用了』」**正是这个病）。⇒ 下表只能用来**排优先级**，
   **不能用来证明某一条具体条款「无实质分歧」**。
4. ⇒ 正确的说法是：**表一是候选工程语料，不是 50 份独立规范**。真要主张共识，
   分母只能是**主张性的规范文档**（索引 / 教程 / 反面教材 / 聚合资料不进分母），
   同一上游的移植与 fork 按**一个来源**计，并且要落到
   `来源 × 条款 × 立场（支持/反对/未提）`的可核对矩阵上——**本文尚未做到这一步**。

## 共识度统计（50 份文档里各主题的命中份数）

用于决定基础层收哪些条款的**优先级**（不是共识证明——见上方诚实边界第 3、4 条）：

| 份数 | 主题 | 份数 | 主题 |
|---|---|---|---|
| 37 | 测试 | 15 | 副作用 |
| 31 | 类型 | 15 | 输入校验 |
| 31 | 文档 | 14 | 代码评审 |
| 28 | 命名 | 13 | 并发 |
| 26 | 注释 | 12 | 日志 / 不可变 / 耦合 / 抽象 |
| 21 | 重构 / 异常 / 重复 | 11 | 超时 / 嵌套 / 覆盖率 / SOLID |
| 18 | 依赖 | 10 | 密钥 / 注入 / 错误处理 |
| 17 | 可空 / 提交规范 | 9 | 链路追踪 / 指标 |
| 16 | 接口 | 7 | 单一职责 / 重试 |

## 清单（按星数降序）

| # | 星数 | 仓库 | 类别 | 贡献给本文的 |
|---|---|---|---|---|
| 1 | 367537 | [donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) | 架构 | 系统设计入门 |
| 2 | 148140 | [airbnb/javascript](https://github.com/airbnb/javascript) | 风格 | Airbnb JS |
| 3 | 105602 | [goldbergyoni/nodebestpractices](https://github.com/goldbergyoni/nodebestpractices) | 通用 | Node最佳实践清单 |
| 4 | 100370 | [mtdvio/every-programmer-should-know](https://github.com/mtdvio/every-programmer-should-know) | 通用 | 每个程序员应知 |
| 5 | 94756 | [ryanmcdermott/clean-code-javascript](https://github.com/ryanmcdermott/clean-code-javascript) | 通用 | CleanCode JS版 |
| 6 | 39566 | [google/styleguide](https://github.com/google/styleguide) | 风格 | Google多语言风格 |
| 7 | 33053 | [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) | 安全 | OWASP速查 |
| 8 | 24625 | [goldbergyoni/javascript-testing-best-practices](https://github.com/goldbergyoni/javascript-testing-best-practices) | 测试 | JS测试最佳实践 |
| 9 | 23331 | [microsoft/api-guidelines](https://github.com/microsoft/api-guidelines) | API | 微软REST规范 |
| 10 | 23305 | [google/eng-practices](https://github.com/google/eng-practices) | 流程 | Google工程实践 |
| 11 | 17676 | [uber-go/guide](https://github.com/uber-go/guide) | 风格 | Uber Go |
| 12 | 16547 | [rubocop/ruby-style-guide](https://github.com/rubocop/ruby-style-guide) | 风格 | Ruby |
| 13 | 14903 | [Sairyss/domain-driven-hexagon](https://github.com/Sairyss/domain-driven-hexagon) | 架构 | DDD六边形 |
| 14 | 14189 | [kettanaito/naming-cheatsheet](https://github.com/kettanaito/naming-cheatsheet) | 命名 | 命名速查A/HC/LC |
| 15 | 13156 | [kodecocodes/swift-style-guide](https://github.com/kodecocodes/swift-style-guide) | 风格 | Swift |
| 16 | 12680 | [ruanyf/document-style-guide](https://github.com/ruanyf/document-style-guide) | 文档 | 中文技术文档写作规范 |
| 17 | 11082 | [Kristories/awesome-guidelines](https://github.com/Kristories/awesome-guidelines) | 索引 | 规范聚合 |
| 18 | 10210 | [Droogans/unmaintainable-code](https://github.com/Droogans/unmaintainable-code) | 反面 | 如何写出不可维护代码 |
| 19 | 9809 | [labs42io/clean-code-typescript](https://github.com/labs42io/clean-code-typescript) | 风格 | CleanCode TS |
| 20 | 9803 | [upgundecha/howtheysre](https://github.com/upgundecha/howtheysre) | 可靠性 | 各家SRE实践 |
| 21 | 9561 | [thoughtbot/guides](https://github.com/thoughtbot/guides) | 通用 | thoughtbot风格指南 |
| 22 | 9250 | [codeguy/php-the-right-way](https://github.com/codeguy/php-the-right-way) | 风格 | PHP正确姿势 |
| 23 | 9208 | [conventional-commits/conventionalcommits.org](https://github.com/conventional-commits/conventionalcommits.org) | 提交 | 约定式提交 |
| 24 | 7730 | [thangchung/clean-code-dotnet](https://github.com/thangchung/clean-code-dotnet) | 风格 | CleanCode .NET/C# |
| 25 | 7622 | [vipshop/vjtools](https://github.com/vipshop/vjtools) | 风格 | 唯品会Java规范 |
| 26 | 5290 | [OWASP/Go-SCP](https://github.com/OWASP/Go-SCP) | 安全 | Go安全编码 |
| 27 | 5138 | [joho/awesome-code-review](https://github.com/joho/awesome-code-review) | 评审 | 代码评审资源 |
| 28 | 5116 | [agis/git-style-guide](https://github.com/agis/git-style-guide) | 提交 | Git风格 |
| 29 | 4837 | [zedr/clean-code-python](https://github.com/zedr/clean-code-python) | 风格 | CleanCode Python |
| 30 | 4426 | [christopheradams/elixir_style_guide](https://github.com/christopheradams/elixir_style_guide) | 风格 | Elixir |
| 31 | 4390 | [goldbergyoni/nodejs-testing-best-practices](https://github.com/goldbergyoni/nodejs-testing-best-practices) | 测试 | Node测试进阶 |
| 32 | 4097 | [bbatsov/clojure-style-guide](https://github.com/bbatsov/clojure-style-guide) | 风格 | Clojure |
| 33 | 3469 | [phodal/migration](https://github.com/phodal/migration) | 重构 | 系统重构与迁移 |
| 34 | 3238 | [zalando/restful-api-guidelines](https://github.com/zalando/restful-api-guidelines) | API | Zalando REST |
| 35 | 3095 | [webpro/programming-principles](https://github.com/webpro/programming-principles) | 通用 | 编程原则总览 |
| 36 | 3091 | [Pungyeon/clean-go-article](https://github.com/Pungyeon/clean-go-article) | 风格 | Clean Go |
| 37 | 2808 | [databricks/scala-style-guide](https://github.com/databricks/scala-style-guide) | 风格 | Scala |
| 38 | 2750 | [airbnb/swift](https://github.com/airbnb/swift) | 风格 | Airbnb Swift |
| 39 | 2722 | [microsoft/code-with-engineering-playbook](https://github.com/microsoft/code-with-engineering-playbook) | 流程 | 微软工程手册 |
| 40 | 2708 | [twelve-factor/twelve-factor](https://github.com/twelve-factor/twelve-factor) | 架构 | 12要素 |
| 41 | 2561 | [bregman-arie/sre-checklist](https://github.com/bregman-arie/sre-checklist) | 可靠性 | SRE检查清单 |
| 42 | 2180 | [transmissions11/solcurity](https://github.com/transmissions11/solcurity) | 安全 | Solidity安全标准 |
| 43 | 2048 | [kriasoft/Folder-Structure-Conventions](https://github.com/kriasoft/Folder-Structure-Conventions) | 结构 | 目录结构约定 |
| 44 | 1881 | [ktaranov/naming-convention](https://github.com/ktaranov/naming-convention) | 命名 | 多语言命名模板 |
| 45 | 1866 | [johnousterhout/aposd-vs-clean-code](https://github.com/johnousterhout/aposd-vs-clean-code) | 争议 | APOSD对CleanCode之争 |
| 46 | 1805 | [hysnsec/awesome-threat-modelling](https://github.com/hysnsec/awesome-threat-modelling) | 安全 | 威胁建模 |
| 47 | 1737 | [NoriSte/ui-testing-best-practices](https://github.com/NoriSte/ui-testing-best-practices) | 测试 | UI测试 |
| 48 | 1520 | [treffynnon/sqlstyle.guide](https://github.com/treffynnon/sqlstyle.guide) | 风格 | SQL风格 |
| 49 | 1515 | [lucasvegi/Elixir-Code-Smells](https://github.com/lucasvegi/Elixir-Code-Smells) | 坏味道 | Elixir坏味道目录 |
| 50 | 1348 | [rust-lang/api-guidelines](https://github.com/rust-lang/api-guidelines) | API | Rust API |

## 表一各条款的具体出处

| 本文条款 | 主要出处 |
|---|---|
| P1 命名（S-I-D、A/HC/LC、动作动词、布尔前缀） | kettanaito/naming-cheatsheet；ktaranov/naming-convention；各语言 style guide |
| P1 函数与控制流（早返回、单一抽象层次、CQS） | webpro/programming-principles；ryanmcdermott/clean-code-javascript 及其各语言移植（python/typescript/php/dotnet） |
| P1 错误（不吞、保留原因链、可操作信息） | uber-go/guide；Pungyeon/clean-go-article；各 clean-code-* |
| P1 依赖与结构（内聚耦合、依赖倒置、组合优于继承、迪米特、为删除而优化） | webpro/programming-principles；Sairyss/domain-driven-hexagon；kriasoft/Folder-Structure-Conventions |
| P1 变更与提交（一个 CL 一件事、为什么写正文、重构与功能分开） | google/eng-practices（`review/developer/small-cls.md`、`cl-descriptions.md`）；conventional-commits；agis/git-style-guide |
| P1 API（向后兼容、统一错误结构、非法状态不可表示） | microsoft/api-guidelines；zalando/restful-api-guidelines；rust-lang/api-guidelines |
| P1 安全（参数化查询、按上下文转义、不信客户端、密钥不落地） | OWASP/CheatSheetSeries；OWASP/Go-SCP；transmissions11/solcurity |
| P0 交给工具的清单 | 各 linter/formatter 类仓库反证：它们能自动化的就不该写进人肉规范 |
| P2 五条分歧 | **johnousterhout/aposd-vs-clean-code**（方法长度 / 注释 / TDD 三处的原文对谈）+ 用户全局规范的 YAGNI 立场 |
| 可靠性（超时、重试、降级、可观测） | upgundecha/howtheysre；bregman-arie/sre-checklist；twelve-factor |
| 反面教材 | Droogans/unmaintainable-code；lucasvegi/Elixir-Code-Smells |

## 表一里发现的实质冲突（进了 P2，没有假装有标准答案）

| 冲突 | 一方 | 另一方 |
|---|---|---|
| 函数该多小 | clean-code-* 系列：小到不能再小 | **aposd-vs-clean-code** 里 Ousterhout 的原话：过度分解**增加**理解成本，被拆开又互相纠缠的方法比不拆更难读 |
| 注释该多少 | clean-code-*：注释多为失败的表现 | Ousterhout 自述会写 **5–10 倍**于对方的注释量；认为「缺注释造成的损失远大于坏注释」 |
| 要不要 TDD | clean-code-* / Martin：短周期先写测试 | Ousterhout：TDD **鼓励坏设计**，「打包式」后写测试可得同样效果 |
| DRY 抽多早 | 多数指南：见到重复就抽 | YAGNI 派 + 本机全局规范：不为投机性复用抽 |
| 防御性编程的度 | 安全类文档：处处校验 | 简单优先派：不写不可能场景的错误处理 |

> **这五条在 50 份文档里是互相矛盾的，而绝大多数文档只讲自己那一边、不提对面存在。**
> 本文的处理是：点名分歧 + 给决策依据（见基础层 P2），而不是替项目选边。

---

# 表二 · 30 个 agent skills / 规则仓库（供给 AI 协作层 K）

**采集方式**：`gh search repos` 跑 25 组关键词（claude skills / agent skills / AGENTS.md / cursorrules / ai code review / coding agent rules / secure coding agent 等），去重后得 641 个候选；筛出与**代码质量**直接相关的 30 个（剔通用索引站、非编码类技能、纯工具）。

| # | 星数 | 仓库 | 类别 | 贡献给本文的 |
|---|---|---|---|---|
| 1 | 280942 | [obra/superpowers](https://github.com/obra/superpowers) | 方法论 | 子代理驱动开发、红绿TDD、YAGNI/DRY、先出规格再写码 |
| 2 | 173323 | [anthropics/skills](https://github.com/anthropics/skills) | 规范 | Agent Skills 官方格式与范例 |
| 3 | 102765 | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | 上下文 | 极致压缩 token 的表达方式 |
| 4 | 91789 | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 工程 | spec/plan/build/test/constraints/review 九个生产级技能 |
| 5 | 74341 | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 索引 | Claude Skills 精选 |
| 6 | 53422 | [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | 索引 | Claude Code 资源精选(含anti-hallucination模式) |
| 7 | 40711 | [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | 规则 | 含17条LLM编码诚实性指令(anti-sycophancy) |
| 8 | 38577 | [github/awesome-copilot](https://github.com/github/awesome-copilot) | 规则 | Copilot 指令/代理/技能集 |
| 9 | 35845 | [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | 索引 | 官方插件目录 |
| 10 | 33662 | [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 索引 | 1000+ agent skills |
| 11 | 30763 | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 工程 | Vercel 官方 agent skills |
| 12 | 26598 | [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files) | 计划 | 基于文件的持久化计划 |
| 13 | 24981 | [agentskills/agentskills](https://github.com/agentskills/agentskills) | 规范 | Agent Skills 规范文档 |
| 14 | 24824 | [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | 子代理 | 100+ 专用子代理 |
| 15 | 24086 | [agentsmd/agents.md](https://github.com/agentsmd/agents.md) | 规范 | AGENTS.md 开放格式 |
| 16 | 21848 | [alibaba/open-code-review](https://github.com/alibaba/open-code-review) | 评审 | 确定性+LLM混合的代码评审(precision over recall) |
| 17 | 19301 | [google/skills](https://github.com/google/skills) | 工程 | Google 产品技术的 agent skills |
| 18 | 7401 | [anthropics/defending-code-reference-harness](https://github.com/anthropics/defending-code-reference-harness) | 安全 | 威胁建模/扫描/分诊/打补丁技能 |
| 19 | 6182 | [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) | 治理 | 策略执行/零信任身份/执行沙箱 |
| 20 | 3893 | [sanyuan0704/sanyuan-skills](https://github.com/sanyuan0704/sanyuan-skills) | 评审 | SOLID/安全/性能/错误处理/边界条件评审技能 |
| 21 | 3162 | [sentrux/sentrux](https://github.com/sentrux/sentrux) | 架构 | 实时架构传感器，治"函数幻觉/代码放错位置/改坏旧文件" |
| 22 | 2677 | [ciembor/agent-rules-books](https://github.com/ciembor/agent-rules-books) | 规则 | 从经典书蒸馏的AGENTS.md规则(full/mini/nano三档) |
| 23 | 1475 | [dirac-run/dirac](https://github.com/dirac-run/dirac) | 工具 | 哈希锚定编辑、拒绝陈旧写入、完成度校验器 |
| 24 | 1251 | [BehiSecc/VibeSec-Skill](https://github.com/BehiSecc/VibeSec-Skill) | 安全 | bug bounty 视角的 AI 安全编码技能 |
| 25 | 1213 | [ChristopherKahler/paul](https://github.com/ChristopherKahler/paul) | 流程 | Plan-Apply-Unify 环，治 context rot 与假完成 |
| 26 | 1139 | [Gentleman-Programming/gentleman-guardian-angel](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | 评审 | provider无关的AI代码评审 |
| 27 | 636 | [SonarSource/sonarqube-mcp-server](https://github.com/SonarSource/sonarqube-mcp-server) | 工具 | SonarQube 官方 MCP，把代码质量接进 agent |
| 28 | 580 | [ramziddin/solid-skills](https://github.com/ramziddin/solid-skills) | 工程 | SOLID/TDD/整洁架构 agent skill |
| 29 | 341 | [fr33d3m0n/threat-modeling](https://github.com/fr33d3m0n/threat-modeling) | 安全 | LLM驱动的代码优先威胁建模技能 |
| 30 | 329 | [cosai-oasis/project-codeguard](https://github.com/cosai-oasis/project-codeguard) | 安全 | CoSAI 的 secure-by-default AI 编码规则框架 |

---

# 表三 · 19 个大厂 / 标准组织的正式规范（供给权威层 Z）

**为什么单列**：表一是**社区规范**（写得好但没有强制力），表二是**给 AI 的规则集**（新且证据弱）。
这一表是**有组织背书、被大规模执行过**的正式标准——它们提供两样前两表给不了的东西：

1. **可引用的绝对阈值**（性能指标的 good/poor 分界线、安全验证的分级）——本文 G 组此前只有相对判据（「设在实测中位的 10–30 倍」），缺权威绝对目标。
2. **强制力分级制度**（阿里 p3c 的强制/推荐/参考、C++ Core Guidelines 的逐条 Enforcement；OWASP ASVS 的 L1/L2/L3 是**安全验证深度**、是另一根正交的轴，不并入强制力分级）——**一份没有分级的规范，执行时所有条款都会被当成建议。**

| # | 星数 | 仓库 | 类别 | 贡献给本文的 |
|---|---|---|---|---|
| 1 | 246525 | [torvalds/linux](https://github.com/torvalds/linux) | 大厂·规范 | Linux 内核编码风格（Documentation/process） |
| 2 | 88365 | [ByteByteGoHq/system-design-101](https://github.com/ByteByteGoHq/system-design-101) | 架构 | 系统设计图解 |
| 3 | 73700 | [binhnguyennus/awesome-scalability](https://github.com/binhnguyennus/awesome-scalability) | 架构·性能 | 大规模系统的可扩展/可靠/高性能模式 |
| 4 | 45293 | [isocpp/CppCoreGuidelines](https://github.com/isocpp/CppCoreGuidelines) | 标准·规范 | C++ Core Guidelines；**每条规则各带 Enforcement 小节**（写明该怎么检查——静态分析／评审／运行期，官方明说有一部分不可机械执行） |
| 5 | 30852 | [alibaba/p3c](https://github.com/alibaba/p3c) | 大厂·规范 | 阿里巴巴Java开发手册；强制/推荐/参考三档 + PMD 可执行规则 |
| 6 | 24702 | [chromium/chromium](https://github.com/chromium/chromium) | 大厂·规范 | Chromium 编码风格与安全实践 |
| 7 | 15664 | [github/opensource.guide](https://github.com/github/opensource.guide) | 大厂·协作 | 开源协作与维护指南 |
| 8 | 13476 | [Tencent/secguide](https://github.com/Tencent/secguide) | 大厂·安全 | 腾讯代码安全指南；6 语言，DevSecOps「从源头规避漏洞」 |
| 9 | 12618 | [google/oss-fuzz](https://github.com/google/oss-fuzz) | 大厂·测试 | 持续模糊测试基础设施 |
| 10 | 9785 | [OWASP/wstg](https://github.com/OWASP/wstg) | 标准·安全 | Web 安全测试指南 |
| 11 | 8606 | [GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals) | 大厂·性能 | Core Web Vitals 指标与阈值的权威实现 |
| 12 | 5668 | [ossf/scorecard](https://github.com/ossf/scorecard) | 标准·供应链 | 开源项目安全健康度量 |
| 13 | 3590 | [OWASP/ASVS](https://github.com/OWASP/ASVS) | 标准·安全 | 应用安全验证标准，L1/L2/L3 分级 |
| 14 | 2343 | [OWASP/API-Security](https://github.com/OWASP/API-Security) | 标准·安全 | API Security Top 10（2023） |
| 15 | 2262 | [cncf/tag-security](https://github.com/cncf/tag-security) | 标准·安全 | CNCF 安全技术咨询组 |
| 16 | 2019 | [MicrosoftDocs/architecture-center](https://github.com/MicrosoftDocs/architecture-center) | 大厂·架构 | Azure 架构中心与云设计模式 |
| 17 | 2004 | [swiftlang/swift-book](https://github.com/swiftlang/swift-book) | 大厂·规范 | Swift 官方语言手册（原 `apple/swift-book`，上游已改名，2026-09-05 复核发现） |
| 18 | 1067 | [ossf/wg-best-practices-os-developers](https://github.com/ossf/wg-best-practices-os-developers) | 标准·供应链 | OpenSSF 开发者最佳实践工作组 |
| 19 | 1061 | [alibaba/Alibaba-Java-Coding-Guidelines](https://github.com/alibaba/Alibaba-Java-Coding-Guidelines) | 大厂·规范 | 阿里 Java 规约 Gitbook 版 |

## 表三各条款的具体出处

| 本文条款 | 出处 | 取的是什么 |
|---|---|---|
| **Z1 性能阈值表** | `GoogleChrome/web-vitals` 的**源码常量**（`src/onLCP.ts` 等的 `*Thresholds`） | LCP `[2500,4000]`ms · INP `[200,500]`ms · CLS `[0.1,0.25]` · FCP `[1800,3000]`ms · TTFB `[800,1800]`ms；语义「≤[0] good，>[1] poor」取自 README |
| **Z2 API 安全必查表** | `OWASP/API-Security` 2023 版 `0x11-t10.md` | API1–API10 十项原文条目 |
| **Z3 强制力分级** | `alibaba/p3c`（强制/推荐/参考）+ `isocpp/CppCoreGuidelines`（**每条规则各带 Enforcement 小节**） | 「分级 + **逐条标注用什么方式检查**」这个结构（不是「都能机械检查」——2026-09-10 外部评审纠正，正本说明在 authority.md）；`OWASP/ASVS` 的 L1/L2/L3 归 Z2 的**安全验证深度**、不作条款强制力分级 |
| K15 安全清单补强 | `Tencent/secguide`（6 语言，DevSecOps「从源头规避漏洞」） | 定位与本文一致：**在写的时候防，不在事后审** |
| P0 交给工具 | `google/oss-fuzz`、`ossf/scorecard` | 模糊测试与供应链健康度属于工具层，不写进人肉规范 |
| G 规模与架构 | `binhnguyennus/awesome-scalability`、`MicrosoftDocs/architecture-center` | 规模拐点与云设计模式的对照 |

## 表三的诚实边界

1. **`Tencent/secguide` 最后修订 2021-05-18**，已有数年未更新。取它的**定位与语言覆盖**（6 语言、从源头规避），**不取具体 API 清单**——那部分可能过期。
2. **本文只引用了这 19 个里的一小部分**。`torvalds/linux`、`chromium/chromium`、`swiftlang/swift-book`、`ByteByteGoHq/system-design-101` 等我核实了存在与星数、确认了它们属于「大厂正式规范」这一类，但**没有逐份精读**——它们在本文里的作用是**佐证这一类语料存在且成体系**，不是具体条款的出处。哪几份被真正读过并取用，上表已逐条写明。
3. **阈值会随时间变化**。Core Web Vitals 的指标集与阈值 Google 改过若干次（FID 已被 INP 取代）。本文的数字取自 **2026-09-04 的源码**，用之前建议核一次上游。
