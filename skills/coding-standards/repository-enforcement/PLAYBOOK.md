# 仓库执法模块（Repository Enforcement）

> SYBuilder 公开版将原独立 `engineering-standards` 完整融合到
> `coding-standards/repository-enforcement/`。本文是编码规范的仓库级执法模块，
> 不再作为第四个独立 Skill 发布。

把一个仓库从"有 lint 就算有规范"提升到"声称的标准 = CI 真正执行的标准"。
对齐 [Google eng-practices](https://github.com/google/eng-practices) 与各语言官方 Style Guide。

> **上游正本是 `coding-standards`**（研发阶段「写这一行代码当下遵守什么」）。
> 本模块管「怎么强制」：把它的条款变成 CI 门禁 / 章程 / CODEOWNERS。
> **建门禁前先去那边取条款**，别自己另立一套 —— 两套标准并存时，
> 人只会遵守更松的那一套，而「更松的那一套」不会让任何东西报错。

## 何时用

- 用户要为项目"建立/审计/完善工程规范、质量门禁、CI"
- 用户问"规范有没有真正覆盖/落地"
- 给多个项目复制一套可执行的工程基线
- 上线前做工程健康度体检

## 核心信条（这套方法的灵魂）

1. **门禁的真实强度 = CI 放行标准，不是文档措辞。** 文档写 A 但 CI 是 B-，就是"假绿"。
2. **棘轮原则（ratchet）**：新检查若存量违例多 → 先设咨询门禁（`continue-on-error`）→ 存量清零 → 转强制。**只许收紧，不许放松。** 绝不为引入新门禁而大爆炸式打挂 CI。
3. **hermetic / 可复现**：工具与依赖版本必须钉死，今天过明天也过。
4. **固化已有成熟度**：系统实际能力常高于书面规范（可观测/授权/降级常已落地却没写）。隐性原则不写下来，新人就会回退。
5. **诚实边界**：需要外部凭据/法务/真实团队句柄的项（LICENSE、CODEOWNERS 真实 team、远端推送）不要伪造，如实标为 Open Items。

## 工作流（按阶段执行，每阶段先取证再动手）

### 阶段 0 — 取证（先看，别假设）
- 识别技术栈：`go.mod`(Go) / `package.json`(Node) / `pyproject.toml|requirements.txt`(Python) / 其它。
- 读现有 CI：`.github/workflows/*.yml`（或 GitLab/其它）。
- 读现有规范文档：`CONTRIBUTING.md` / `README` / 任何 `*STANDARD*`/`*STYLE*`。
- 列已有治理脚手架：`CODEOWNERS` / `SECURITY.md` / `dependabot.yml` / PR 模板 / `docs/adr/`。

### 阶段 1 — 审计"假绿门禁"（本 skill 最有价值的一步）
对照"文档/直觉声称的检查"与"CI 实际执行的步骤"，逐条核（详见 `references/false-green-gates.md`）：
- **类型检查真的在 CI 跑吗？**（最常见假绿：TS 项目 `no-undef:off` 委托给 TS，但 CI 从不跑 `tsc`/`vue-tsc`）
- **测试带竞态检测吗？**（Go 有并发却 `go test` 不带 `-race`；其它语言的并发测试）
- **工具/依赖版本钉死吗？**（`@latest`、`pip install X`、`npm install` 而非 `npm ci`/lockfile）
- **有供应链扫描吗？**（`govulncheck` / `npm audit` / `pip-audit`，Dependabot）
- **有密钥扫描吗？**（gitleaks）
- **CI 门禁 == 部署门禁吗？**（部署若走 `docker build`/rsync 只编译不跑测试，则 CI 绿 ≠ 上线安全）
- **格式/静态分析/契约校验齐吗？**

把发现按 P0（假绿，会放过真缺陷）/P1（违反 hermetic/供应链）/P2（缺惯例）分级，给出证据。

### 阶段 2 — 硬化门禁（写进 CI）
按栈套用 `templates/ci-*.yml` 的强化 job（见各模板注释）。原则：
- 能力强但存量为零的检查 → **直接强制**（如 `-race`，多数干净仓库能过）。
- 存量多的检查（如 typecheck）→ **咨询门禁 + 记录棘轮计划**（在章程 Open Items 写明"清零后转强制"）。
- 工具钉死：Go 用 `go.mod` 的 `tool` 指令（Go ≥1.24，`go get -tool X@ver` + `go tool X`）；Node 用 `npm ci` + 锁文件 + 钉 major；Python 用 `requirements.lock`/`uv.lock`。
- **运行期环境隔离**（hermetic 的另一半，版本钉死不够）：评测/E2E 类门禁的子进程必须白名单洗净 env + 隔离 config dir，并给隔离机制本身上一道 static tripwire——否则「本地绿 CI 红」或「本地绿是借了操作者状态」。配方见 `references/hermetic-eval-env.md`。**一条不 hermetic 的评测门禁，它的绿不可信。**
- **按成本×确定性分两层 gate / periodic**（借自 gstack，与棘轮正交的第二根轴）：CI 每次提交只跑 **gate** 层（秒级、确定性、阻断合并）；**periodic** 层（贵、慢、非确定性、依赖外部服务）走每周 cron 或手动。分类规则：安全护栏 / 确定性功能测 → gate；质量基准 / 大模型跑分 / 非确定性 / 需外部服务 → periodic。**理由**：把贵而不确定的测试塞进每次 CI，结局是有人偷偷跳过整个 CI；全删又丢覆盖——两层让阻断路径永远快而确定。可配 **diff-based 选择**（每个测试声明文件依赖，改到全局依赖则全跑，且要能预览「这次会跑哪些」）——⚠️ 连它的失败形态一起抄：**一个测试被静默不选中 = 假绿**，所以必须有全局兜底（改到核心文件触发全跑）+ 可预览。棘轮管「随时间只紧不松」，这根轴管「按每次运行成本决定跑在哪」，两者正交。
- 加 `concurrency` 取消旧运行、`permissions: contents: read`。

### 阶段 3 — 清存量（让咨询门禁能转强制）
- 跑该检查拿到存量基线数（如 `tsc` 报 N 个错），记进章程。
- 在不改运行时行为的前提下逐类清零（类型断言、补类型、窄 `@ts-expect-error` 带原因等）。
- **不得为清存量改坏运行时**；清不动的（框架级类型递归等）用最小、带注释的逃逸。
- 清零后删掉对应 CI 的 `continue-on-error`，门禁转强制。

### 阶段 4 — 固化已有成熟度 + 铺治理脚手架
- 写工程章程：`templates/ENGINEERING_STANDARDS.md`（12 域骨架，把项目真实的架构原则/安全模型/可观测/降级策略填进去——这些常已落地却没写）。
- **新项目或想立标杆架构**：直接采用 `references/proven-web-architecture.md`（生产验证过的 API-First 模块化单体蓝图：分层/横切层/事件总线+队列/数据治理/配置即数据/安全/可观测/发布工程/前端 SSR），按栈裁剪后填进章程 §1。**审计老项目**：用蓝图当对照尺，量出架构缺口（如缺降级/缺配置即数据校验/缺审计链）。
- 铺：`CODEOWNERS`、PR 模板、`SECURITY.md`、`dependabot.yml`、`docs/adr/`（模板 + ADR-0001）。
- `CONTRIBUTING.md` 指向章程 + 修过期命令 + 写明提交约定（Conventional Commits）。

### 阶段 5 — 验证 + 诚实收尾
- 本地按 CI 口径跑一遍每个门禁，全绿才算数。
- 列 Open Items：需外部输入的（LICENSE 法务、CODEOWNERS 真实 team、远端/分支保护）如实标，不伪造。
- 小颗粒提交，提交信息说清"为什么"。

## 关键陷阱（实战踩过）

- **加新依赖必须同步锁文件**（改 `package.json` 不跑 `npm install` → CI 的 `npm ci` 会因不一致失败）。
- **`tsc` 报错会因前一个"爆栈"文件 bail 而隐藏后续文件的错** → 修完一个要重跑确认真实剩余。
- **类型门禁宁可咨询起步**：存量类型错误多的仓库直接强制 typecheck 会瞬间打挂 CI。
- **部署路径常绕过 CI 测试门禁**：docker `go build`/前端 `build` 都不跑测试,要么让部署前置跑测试,要么明确风险。
- **CODEOWNERS / LICENSE / 远端**：这些需要人/法务/平台,不要替用户编造。

## 模板与参考

- `templates/ENGINEERING_STANDARDS.md` — 工程章程 12 域骨架（填项目实际内容）
- `templates/ci-go.yml` / `templates/ci-node.yml` — 强化后的 CI job（gofmt/vet/staticcheck-pinned/test-race/govulncheck ‖ npm ci/eslint/typecheck/audit）
- `templates/pull_request_template.md` / `SECURITY.md` / `CODEOWNERS` / `dependabot.yml`
- `templates/adr-0000-template.md` + 写 ADR-0001 记录"采用 ADR"
- `references/proven-web-architecture.md` — **生产验证的 API-First 模块化单体架构蓝图**（新 Web 项目直接采用；老项目当对照尺量缺口）
- `references/false-green-gates.md` — 假绿门禁逐条审计清单
- `references/ratchet.md` — 棘轮原则详解 + 咨询→强制的判定
- `references/hermetic-eval-env.md` — **hermetic 的另一半:运行期环境隔离配方**（子进程白名单洗净 env + 隔离 config dir + 给隔离机制本身上 static tripwire；信条只覆盖了「版本钉死」，这份补「本地信号=CI信号」）

> 用模板时务必**按目标项目实际情况裁剪**：删掉不适用的栈、把占位（团队句柄/域名/许可证）标为待填，不要原样塞给项目。
