# 工程测试与四节点终审报告

## 0. 文档控制、对象与依据

commit abc123；revision r9；hash h8。S8 / coding-standards / four-node-review 均锚定。
coding-standards 的 selfcheck 只证明规范源在场且自洽，不证明本次代码已遵守。
飞书：https://example.feishu.cn/docx/q
receipt: receipts/q.json

## 1. 风险定档、覆盖合同与入场门

最终风险档：A；决策人：张三；理由：接口迁移。

| 包 | 文件 | 来源 | 风险 | 状态 |
|---|---|---|---|---|
| PKG-001 | src/a.py | FR-001/API-001 | 接口 | RUN |

真实分母：共 1 包；覆盖 1/1；来自 git diff。

### 1.3 入场门（Entry）

版本一致 PASS；RED/GREEN PASS；环境 PASS，证据 receipts/e.json。

## 2. 显式测试执行结果

| 测试域 | ID | 范围 | 结果 | 证据/失败原因 |
|---|---|---|---|---|
| 功能与业务规则 | TEST-001 | 正向 | PASS | f.json |
| 边界、异常、并发与恢复 | TEST-002 | 越界恢复 | PASS | b.json |
| 接口、契约与集成 | API-001 | schema/授权 | PASS | a.json |
| 性能、容量与稳定性 | PERF-001 | load/soak | PASS | p.json |
| 安全与隐私 | SEC-001 | 扫描+人工 | PASS | s.json |
| 兼容、无障碍与交互工程质量 | TEST-006 | 键盘读屏 | PASS | c.json |
| 算法评测与退化 | N/A-001 | 不适用 | PASS | n.json |

SKIPPED/UNABLE 必须写原因、影响、owner、解除条件。

### 2.1 测试工程师 GUI 全流程实走

从真实入口操作当前构建；主流程、关键分支、失败与恢复、角色权限全部覆盖。API/DOM 只能辅助定位，不能替代 GUI。证据绑定构建、环境、角色、时间。

| GUI-ID | 来源 | 操作 | 结果 | 证据 |
|---|---|---|---|---|
| GUI-S92-001 | FLOW-01/FR-001 | 登录、导入、失败后恢复 | PASS | gui.mp4 |

GUI 结论：PASS。

## 3. `coding-standards` 执行与偏离

| STD-ID | 范围 | 如何证明遵守 | 结论 | 豁免 |
|---|---|---|---|---|
| STD-001 | src/a.py | 测试与人工复核 | PASS | N/A |

## 4. `four-node-review` 终审执行

| 节点 | 轮次 | 覆盖包 n/m | 已用镜头/本轮新增镜头 | 结论 | 独立新证据 |
|---|---:|---:|---|---|---|
| entry | 1 | 1/1 | 入口 | CLEAN | e.json |
| gates | 2 | 1/1 | 变异 | CLEAN | g.json |
| security | 2 | 1/1 | 权限 | CLEAN | s.json |
| review | 2 | 1/1 | 并发 | CLEAN | r.json |
| qa | 2 | 1/1 | 边界 | CLEAN | q.json |
| bench | 1 | 1/1 | 性能 | CLEAN | b.json |

CLEAN/DIRTY/UNABLE；每轮有独立新证据。

| Finding | 节点 | 严重度 | 证据 | 根因 | 修复 commit | 反例预期原因 | 复验 |
|---|---|---|---|---|---|---|---|
| FIND-001 | qa | HIGH | q1 | 边界 | commit def456 | 预期断言变红 | CLEAN |

precision=1/1。

## 5. 最终回归、缺口与质量结论

需求覆盖 1/1；代码行/分支/变异覆盖分别 90/85/70；全量回归与构建 fresh PASS。
质量结论：PASS。
S 档：不得有 Open Item；UNABLE 永不等于 PASS。
移交 S9.3 仅说明工程质量，不得声称 PRD/Figma/HTML/最终应用已一致。

## 6. 批准、写入与回读

| 角色 | 结论 | 人/时间 | 证据 |
|---|---|---|---|
| 测试负责人 | 批准 | 王五 | t.json |
| 研发负责人 | 已知悉并接受修复 | 张三 | d.json |
| 算法负责人/N-A复核人 | N-A批准 | 李四 | a.json |

回读结论：READY
