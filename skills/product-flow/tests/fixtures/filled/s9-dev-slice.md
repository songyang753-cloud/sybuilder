# 开发与持续验证：纵向切片交付记录
## 0. 文档控制与入场资格
| 项 | 内容 |
|---|---|
| S8 联合方案 | https://x r3；方案结论必须 APPROVED；receipt s8.json |
| coding-standards 正本 | /path cs commit c1；selfcheck receipt cs.json |
| 当前构建 / commit | build-9 commit abc123 |
| 模式 | Build |
| 研发 / 复核 | 张三 |
## 1. 纵向切片与合同锚定（合同先行）
合同先行：接口/schema/错误/幂等/回滚先闭合再排任务。
| SLICE-ID | 对应 FR/AC | TECH/STD 锚 | 精确文件 | 合同状态 | 状态 |
|---|---|---|---|---|---|
| SLICE-001 | FR-011/AC-1 | TECH-03/STD-07 | src/import.ts:parse | 接口/幂等/回滚已闭合 | DONE |
## 2. RED→GREEN 证据（每切片）
diff 每行可追溯 FR。
| SLICE-ID | RED 证据 | 最小 GREEN | 绑定 commit | 可追溯 FR | 越界 |
|---|---|---|---|---|---|
| SLICE-001 | RED 先红 assert 原因对 | GREEN 通过 | abc123 | 是 | 无 |
## 3. AI 生成记录与协作层（附件 H.4）
| SLICE-ID | AI 直出/人复核 | K 层条款 | 复核人/证据 |
|---|---|---|---|
| SLICE-001 | AI 直出→人复核 | 幻觉API/写完≠验过 | 张三/pr1 |
## 4. 算法切片离线评测门
| 算法改动 | 评测集/指标 | 过门结果 | 或 N/A |
|---|---|---|---|
| 无 | 评测集 recall@10 | — | N/A：本切片无算法改动 |
## 5. 出场结论与偏差回写
| 汇总项 | 结果 | 证据 |
|---|---|---|
| selfcheck receipt | 在案 不证代码合规 | cs.json |
| STD-ID 实现证据 | 齐 | link |
| 偏离 S8 方案 | 无偏离/已同 commit 回写 | link |
| 完成度分级 | self_reported（同进程 selfcheck） | 逐条 STD 证据升 tested 见 link |
开发切片出场结论：READY。selfcheck 绿 ≠ 代码合规。
## 6. 代码评审结论（切片交付前必过）
| 评审维度 | 工具/方式 | 结论 | 处置/证据 |
|---|---|---|---|
| 功能/质量 | open-code-review (ocr) 确定性规则 | 无阻断项 | ocr-report.json |
| 安全 | semgrep + trailofbits 规则集（推荐） | 无高危项 | semgrep.sarif |
| 人工复核 | reviewer 张三 | 复核通过 | pr1 |
评审正本：ocr（Apache-2.0，确定性×Agent 混合）；安全维度 semgrep 可选，不阻断 fresh clone。
