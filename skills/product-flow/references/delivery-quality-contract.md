# 文档质量与恢复能力交付契约

本契约补充现有 S2–S9 规则，不删减既有研究维度、九章 PRD、八类产品图或 S8/S9 职责。目标是让不认识产品的读者理解它，并让后续 PRD、设计、交互与研发测试能消费同一份证据。机器全绿不等于专业判断正确。

写作执行读 `evidence-first-writing.md`：先样章校准，逐单元取证/写作/评审，再组装，摘要最后生成。下述 GUI 叶子合同适用于 teardown/competitive-pack/full-research 的产品研究；新增 tech-approach 保留 `s2-tech-approach-runbook.md` 的源码机制合同，不要求虚构操作或 UI 截图。两类共同遵守事实边界、真实配图、下游决策和同版平台验收。

## S2：先走到叶子，再写正文

1. 先声明研究决定、产品版本、角色/套餐、授权范围、页面与可见控件全集。Web 或客户端均串行操作；只使用获准的 GUI/CDP 通道。下载、安装、读私人内容、发送、删除、支付、改变权限等另需相应授权。不抓会话凭据，不误杀用户进程，不把未操作控件算已实测。
2. 功能按原生产品层级拆分，不固定三级或四级。最细叶子是同一角色对同一对象执行一个可独立验收的动作；新增、编辑、取消、删除若规则不同必须拆开。3–5 个重点实验只是额外深入，不能免除范围内其他叶子的正文。不可把候选池的所有产品都称作已深拆；只案头/被阻断者单独列为背景，不能进入“已验收单品包”。
3. 每个叶子正文逐项说明：为什么使用、角色/入口/前置、对象/字段/默认值/校验、具体动作、前后态、准确反馈、失败/取消/恢复、权限/端/档位/限额、拆分理由、下游输入。字段没有或状态不变时说明可观察行为；不知道就写未知和补证计划，不编造参数。索引只是导航，树图只是地图，都不能代替正文。
4. 一个 AF 对应一个精确正文标题和索引行；完整功能路径、正文、操作事件、真实图片必须对应。截图放在解释它的功能旁边，写出它能证明什么、不能证明什么。动效不能靠静态图证明。截图不允许占位图片、文字代图或生成式仿真竞品 UI；制图器只画分析图，不制造实测证据。
5. 先完成一个有主路径、校验/失败及恢复的最细功能样章，由产品/UX/测试分别评审后再铺开。审核样章时用未参与撰写的读者复述操作与规则；复述不了就返回补写，不用凑字数解决。完成后全部叶子及全部正文都再评审。

## 三种模式都不能绕过颗粒度

| 模式 | 人读正本 | 机器结构物 | 必需检查 |
|---|---|---|---|
| teardown | `templates/competitor-teardown-report.md` | 功能账本、遍历事件、`templates/evidence-manifest.json` | 遍历覆盖、带四项输入的报告结构、读者检查、所选平台完整回读、最终质量评审 |
| competitive-pack | `templates/research-report.md`，逐级横比正文 | `templates/competitive-research-pack.md` 是语料结构；`templates/research-package.json` 索引版本锁定的全部单品包 | 研究语料检查、报告结构 + package、所选平台回读、最终质量评审 |
| full-research | 同上并输出功能/设计/交互定向报告 | 上述单品包 + 五条研究线及 G0 | 不因模式名为 full 就免除单品深度或逐级横比 |

横比 manifest 的每个 COMP 提供 report/ledger/evidence/events 的路径和 SHA256；公共 AF→原生 AF 单独映射，不能伪造各产品树完全一样。`comparisonNodes` 从公共树根逐层列到叶子，每节点写父节点及子 AF 全集。报告增加“逐节点逐竞品对比”六列表：节点、COMP、状态、原生路径、依据、影响；每节点×每竞品恰好一行。状态 FULL/PARTIAL/ABSENT/UNKNOWN/N/A，登录墙和未获授权只能是 UNKNOWN，ABSENT 必须带实测检索范围与日期。模块比较不能替代中间层和叶子比较。

结构检查调用：`report-structure-gate.py <报告> --mode teardown --atomic-ledger <账本> --evidence-manifest <清单> --events <操作账>`；横比改为 `--mode competitive-pack` 或 `full-research` 并提供 `--package-manifest <research-package.json>`。不传模式是旧诊断入口，不是正式完成入口。

## S2 → 九章 PRD → 设计/交互/测试

研究覆盖 PRD 一至九章需要的事实：背景/目标/用户/场景/业务流程/概要设计/详细设计/数据埋点/非功能要求，以及附件中的字段、状态、权限、风险和验收。重点对账 6.1 模块 M、6.2 功能 F、6.3 页面 P、第七章逐功能卡、附件 D 字段和 E 状态。研究 AF 是事实粒度，我方 F/FR 是需求决策粒度，两者用显式映射，不强行一对一。

每个研究结论标 adopt/adapt/reject/defer/watch 和理由、目标位置及证伪指标；反方向每项 PRD/设计/交互规则要能追溯到研究证据或显式产品决策。研究应比后续选择集更宽、更细，不能为了支持已定方案删掉反例。竞品行为不自动变成我方需求。

## 内置制图与原型

`modules/diagramming` 提供本地结构化 JSON → SVG → PNG；原有 D2/Mermaid/PlantUML 也可用 `render-diagram.py` 调用已安装编译器交付真实 SVG/PNG，缺编译器返回 UNABLE，不用源码或占位文字冒充图片。正式交付填写 `templates/diagram-manifest.json`，逐图绑定图位、类型、PRD 章节及源；通过 `diagram-id-gate.py <项目目录> --formal`。JSON 使用 `templates/diagram-source.json`，SVG 必须从本版结构源完整复建；其他图源在清单补 diagramType/targetSection/svg/png/receipt，并保存真实编译回执。每张图独立对账，其他图不能补漏，PNG 真解码，回执绑定源/SVG/PNG 三个哈希。迁移图源时保留旧源，逐条核对节点与边，不能丢业务关系。

选择适用图位并写依据，不强制八张空图；未适用也不能省略记录。画完必须目检真实渲染结果的中文、比例、层级、箭头、文字遮挡和业务含义；机器不代替这个检查。内置渲染器逐个尝试可用后端，失败不拿旧 PNG 冒充成功。

`modules/prototyping` 提供离线打包与隔离浏览器断言；打包保留模块语义，外部依赖/越界引用拒绝。浏览器非零退出、超时、页面异常和未执行断言均不能通过。Figma、飞书、钉钉和浏览器软件本身仍是外部适配器，缺能力报 UNABLE，不复制其实现。

## 平台交付与独立终审

统一文档适配入口选择飞书或钉钉，见 `scripts/_documents.py`。

飞书用官方 `lark-cli --as user`；钉钉用官方适配通道。写入前逐图隐私检查、授权范围确认；`privacyReviewed=true` 必须附真实主体、时间、检查范围及 APPROVED 结论，不能预填。GUI 图片绑事件文件与事件 ID，分析图绑结构源、SVG 和渲染记录。

写入后的验证必须覆盖完整正文、否定词、表格值、链接、顺序、图片实体及其所在功能；文本和媒体须属同一平台原生版本。未知回读格式、空图片实体、内容丢失或版本变化即 FAIL/UNABLE。离线夹具与本地预检查永远不是 live 回执。

`templates/research-quality-review.md` 是三角色专业评审记录。先 `research-quality-gate.py --source <源稿> --review <记录> --phase pre`，上传回读后检查原生页面直至文末，复核全部章节的图文邻接、长表、字号和图尺寸，再 `--phase final`。最终检查必须绑定当前源稿/图片哈希、有效 live 回执、同版平台页面截图。未完成原生阅读检查，S2 不关闭；作者不能伪造他人的批准。

## S8/S9：批准必须对应本版产物

四个方案/质量/产品走查/发布门的正式调用均提供 `--context <contract-manifest.json>`。在其中的 `approvalBindings` 为 S8、S9.2、S9.3、S9.4 分别填写 sourceHash/version/scope/artifacts（kind/path/sha256）及 approvalEvidence（JSON，含 sourceHash/version 和批准来源）；表内批准版本和范围必须一致。主体类型 agent 与 human 分开，助手评审不冒充业务负责人签字。

S9.3 还必须绑定同一构建的 S9.2 qualityEvidence（status=PASS、build、prdHash），artifacts 含 frozen-prd 的路径/哈希，并各有独立 qaGuiEvidence 与 pmGuiEvidence：测试先按测试方案完整 GUI 实走，产品经理再结合冻结 PRD、产品经验走全流程。代码或 PRD 变化后旧批准失效；不能拿同一截图改文件名充当两个角色的独立实走。

批准来源 JSON 还必须含 scope 和 approvals 数组，每条含 role、actorType、reviewer、authority、decision=APPROVED、reviewedAt，角色/授权依据与表格逐一一致；所有阶段都绑定 frozen-prd。GUI 记录必须含 role（qa/product）、sessionId、reviewer、status=PASS、build、prdHash、带时区的 startedAt/completedAt，以及逐步 steps：action/expected/actual/status 和 screenshot（path/sha256）。截图必须真实可解码。S9.2 的 completedAt 在 QA 结束之后、PM 开始之前，两个会话不同；这些字段只防误用、混版和证据缺失，不认证签字人身份。

## 发布验收边界

依赖使用套件根 DEPENDENCIES/requirements，安装前验证内置模块。发布前完整回归两遍、逐项整改复核、公开包隐私扫描和新环境安装检查。离线验证通过只支持 preview：真实云端适配、整份报告盲审、跨平台和性能未经实测的项目仍保留在发布阻断清单，不能宣称生产就绪。
