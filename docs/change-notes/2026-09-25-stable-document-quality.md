# 调研与 PRD 稳定质量改造

日期：2026-09-25。基线：`46d4d77`。在既有 main 上实施，不建立第二套 Skill，不改变原来的九章 PRD、附件职责、制图、原型或飞书/钉钉适配能力。

## 结论边界

本批把“最细功能、可执行规则、异常恢复、真实图片、独立消费”接入模板和正式检查。它保证可确定的缺项被阻断，不声称脚本理解了全部业务、认证了评审身份，或证明任意 Agent 都不会遗漏。

当前代码验证与生成效果验证分开记录。不能拿单元测试或离线回读夹具代替 Claude 的实际产物，不能把 Markdown 等同已发布的飞书/钉钉文档。

## 需求—实现—验证对账

| 工作包 | 实现位置 | 验证方式 | 状态 |
|---|---|---|---|
| 0 反例与合法短功能 | tests/test_delivery_depth.py、test_writing_contract.py；保留原有回归 | 整项遗漏、假字段覆盖、空 AC、缺分支、死循环、假引用、过期批准；只读/N/A/中文冒号/共用 GWT/子小节正例 | 已实施，专项回归通过；全量结果见下节 |
| 1 模板一致性 | evidence-first-writing、delivery-quality-contract、S2 模板、PRD 第七章及附件 E、s3-s4-product、spec/s4-prd | spec 生成对账、模板配对与零丢失；旧截图转换禁令更新为真实上传/回读义务 | 已实施；九章和既有附件保留 |
| 2 锁范围 | chain-gate G0.8、_writing_contract.scope_issues | 上游功能丢失/未经批准新增或拆分被拒，合法处置通过；S2 继续沿用 SURF/AF/事件分母 | 已实施；批准依据可追溯不等于已认证签名 |
| 3 批次与续跑 | state 模板、review 模板、consumer_issues | 样章先行、每叶只属一个批次；正文节哈希防未经复审压缩；变化后重审 | 已实施；最终记录不能独自证明历史执行顺序 |
| 4 功能与交互闭环 | _writing_contract、_prd_parse、PRD/报告/产品结构检查 | 九列行为记录、六类适用性、可达出口、实际角色权限、所属 FR/AC、正文/附件实质覆盖 | 已实施；分支语义与业务正确性仍须独立消费 |
| 5 独立消费 | research-quality-gate、prd-quality-gate、两份审核模板 | 三个非作者实际会话；每叶每角色四问，具体答案与原文引用、轨迹文件和哈希 | 已实施检查；不得把合成测试中的审核记录当真人/Agent 实审 |
| 6 正式入口 | registry、gate-run、_workflow、test-gate-binding | full/only/from 均要求 PRD 质量门；pre/self-test/help/缩写和重复参数不能冒充正式验收；遍历须事件账+证据清单+全部已发现控件处置 | 已实施；输入/正文/图片/轨迹/范围均绑定版本 |
| 7 平台保真 | 复用 _documents、doc-sync-guard、receipt-check、质量门 final | 当前源稿、同版 live 全文/媒体回执、覆盖全文的页面图和阅读判断；旧/模拟回执不算正式完成 | 检查与离线回归已实施；本批没有新建或覆盖真实平台文档 |

路径除顶层 scripts 外，均相对 `skills/product-flow/`。业务事实继续写在原正文/附件；审核记录只保存审查证据，不复制另一套可编辑业务正本。

### 对既有实现的处理

`research-gate.py` 已有 SURF→AF/NON-FEATURE/BLOCKED 的处置与真实事件/证据反查；`traversal-coverage-gate.py` 已拒绝新增未登记控件。保留这些实现和破坏性反例，没有为凑改动数量另写一套。补强的是正式调用不可省略事件账，也不可把低覆盖阈值当全量完成。

`requirements-quality-gate.py` 继续管措辞，不被升级成“自动理解业务”。四类研究模式保留：技术方案调研不被强加 GUI；界面深拆不因画了树图或堆截图就满足逐功能正文。

## 验证记录

专项测试已经运行：PRD 粒度与正文解析、写作合同、正式计划/记录、原有整改回归、S2 黄金样本。第一次诊断性全量发现两处问题：新辅助文件未登记归属、报告自证对“状态变化”用词过严。已登记明确路径并让九列行为表的前/后态被识别；未通过修改基线来隐藏错误。

全量冻结复跑：待本批最终运行后填入真实结果；本行不代表通过。

第二次诊断性全量的两条失败保留：协作反例误用本批已授权共享的路径，已改回真正独占路径并通过全部 21 条自证；平台一致性检查的一条浏览器子进程测试发生异常，单独完整重跑通过，仍需冻结全量重跑确认，不能删去初次失败。

额外渲染旧业务流程 D2 示例时，SVG 校验报告连线与容器相交；用基线 `46d4d77` 原文件和同一渲染器复现相同失败。它不是本批数字标签改动导致，也未靠放宽校验处理；保留为既有示例兼容性问题。内置制图器的结构化输入及自身回归另行验证，不能与这张旧示例混称“所有图均通过”。

## 独立正向试写的实际观察

一次隔离的非 Claude 会话，只读取本地原始演示页面、原始事件和既有截图，没有读取成品报告、作者结论或隐藏答案，生成了一份功能样章及相应 PRD 切片。它没有获得新 GUI 访问：浏览器初始化和隔离启动失败，因此明确披露未新实测、未发布，不声称完整阶段交付。

产物确实解释了必填/空白输入、创建后的可见结果与数据去向，也保留了字符计数、重复名称、临时生命周期等未决事项。它仍出现索引列名改写、只交切片而非完整模板、绝对本地图路径等问题。该轮不记为正式达标，更不记为 Claude 达标。

这次试写直接推动了修复：接受中文冒号；功能正文包含子小节；执行计划帮助列出真实可选值。另在复审中修复模板共同 Given/When/Then 与逐 AC 解析不兼容、正文提及附件标题或围栏示例污染验收集合的问题。模板缺列、未决产品规则、缺原生回执仍保持不通过，不能为了接受试写而放宽。

原始试写和运行日志保存在私有验证目录，不随公共仓库发布。合成测试记录明确标记 synthetic，不能复制去充当真实审批。

## 尚未完成的效果验收

以下不能被本地绿色测试代替：

1. 三类固定证据任务 × 三次独立 Claude 生成，保留首稿、修正、失败轮次与费用；需模型调用预算授权。
2. 获准真实产品功能域的完整遍历、研究→取舍→PRD、三角色独立消费。
3. 所选个人文档平台的实际发布、全文/图片回读和逐页阅读；不覆盖现有业务报告。飞书和钉钉分别验，不能相互代报。

在这些完成前，允许声明“质量约束与阻断机制已改造”，不允许声明“Claude 稳定生成质量已证明”或“全部端到端验收完成”。

## 协作与回归纪律

共享路径逐项说明（不包含本地环境和日志）：

- 入口与协议：`SKILL.md`、`stage-playbook.md`、`delivery-quality-contract.md`、`evidence-first-writing.md`、`s3-s4-product.md`、`workflow-registry.json`、`state.md`，接入样章/批次/消费/正式放行。
- 检查与回归：`_prd_parse.py`、`_workflow.py`、`chain-gate.py`、`prd_completeness_check.py`、`product-structure-gate.py`、`report-structure-gate.py`、`research-quality-gate.py`、`gate-run.py`、`product-flow-run.py`、`test-gate-binding.py`、`test-remediation-contracts.py`、`verify-suite.sh`，补实质覆盖、闭环和拒绝绕过；既有用例不删除。
- 模板与示例：`prd-complete.md`、`research-report.md`、`competitor-teardown-report.md`、`research-quality-review.md`、`tests/fixtures/filled/PRD.md`、`product-structure.md`、`tests/s2-golden/report.md`、`readback.xml`，保持正文/模板/检查兼容；后两者为离线测试材料，不冒充线上回读。
- 教学切片 `templates/examples/report-writing/prd-slice.md`、`research-domain.md` 增加当前正式模板及记录格式指向，明确解释深度样章不等于完整阶段交付，防止旧简写格式误导执行者。
- 规格与目录：`s4-prd.json`、`_writing-contract.json`、`gen-docs.py`、`prd-structure.md`、`consistency-gate.py`、`design-quality-gates.md`、`iron-rules.md`、`substance-over-theater.md`、`business-process.example.d2`、`functional-architecture.example.d2`、`product-architecture.example.d2`，对齐新门禁及诊断口径，数字按实际测量同步。
- 协作与保留：`path-ownership.json` 登记本次职责；`ownership-inventory-baseline.json` 仅减去本次已经认领的两个孤儿，不放宽上限；`no-loss-renames.md` 保留旧义务到新实现的直接映射，`no-loss-baseline.json` 未改。
- `references/.selftest-measured.json` 只由真实全量运行生成；随复跑更新，不手改失败、跳过或通过统计。
- `coordination-gate.py` 的 A2 反例继续验证“不得修改对方独占路径”，目标从本次已授权共享的 PRD 检查改为仍独占的 `ci-unable-baseline.json`；不修改判据或允许未授权路径。

用户已明确要求按方案由 Codex 实施。为本批必要的 PRD 完备度检查和教学夹具登记精确 shared 路径，保留 Claude 历史主责；不追溯改写旧违规记录。新增共享检查及其回归明确登记 Codex 责任。无损映射只登记过期指令到当前义务及理由，不重置原始基线。
