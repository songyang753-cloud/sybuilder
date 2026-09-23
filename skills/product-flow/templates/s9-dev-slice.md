# 开发与持续验证：纵向切片交付记录（S9.1 飞书文档模板）

> 受控源稿。⛔ 只有 S8 联合方案 `APPROVED` 才可开始 S9.1。vibecoding 只在切片内放开，**切片边界由 S8 合同锁死**。
> ⚠️ 本模板验的是「切片交付合同齐不齐」，**不替你判断代码写得好不好**——质量由 S9.2 终审与
> `coding-standards` 逐条实现证据裁定；`selfcheck.sh` 绿只证规范正本在场自洽，不证代码合规。

## 0. 文档控制与入场资格

| 项 | 内容 |
|---|---|
| S8 联合方案 | <URL + revision>；**方案结论必须 APPROVED**；receipt: <路径> |
| `coding-standards` 正本 | <解析到的真实路径 + commit/hash>；selfcheck receipt: <路径> |
| 当前构建 / commit | <build / commit> |
| 模式 | Handoff / Build（默认 Handoff） |
| 研发 / 复核 | <姓名；不得只写团队名> |

## 1. 纵向切片与合同锚定（合同先行）

> 合同先行：接口 / schema / 错误 / 超时 / 幂等 / 重试 / 降级 / 权限 / 迁移 / 回滚**先闭合**，再排任务。
> ⛔ 合同未定时，不得用文件级任务清单伪装成可执行计划。切片按依赖拓扑、最小端到端排序，不按前后端水平分层。

| SLICE-ID | 对应 FR/AC | TECH/ALG/STD 锚 | 精确文件 / 接口 | 合同状态（接口/schema/错误/幂等/回滚 已闭合） | 状态 |
|---|---|---|---|---|---|
| SLICE-001 | FR-011 / AC-1 | TECH-03 / STD-07 | src/import.ts:parse() | 已闭合 | PLANNED/RUN/DONE |

## 2. RED→GREEN 证据（每切片）

> 「看它真的失败」不可省：RED 必须为**正确断言、正确原因**失败，不是随便红一下。**diff 每一行都能追溯到某个 FR**——追溯不到的行，要么删掉，要么登记工程基线依据。

| SLICE-ID | RED 证据（为正确原因失败） | 最小 GREEN | 绑定 commit | diff 每行可追溯 FR | 越界改动 |
|---|---|---|---|---|---|
| SLICE-001 | <失败日志/断言/原因> | <实现通过证据> | <commit> | 是 / 否+登记 | 无 / <登记> |

## 3. AI 生成记录与协作层（附件 H.4）

> AI 直出与人复核**可信度完全不同，但写在文档里看起来一模一样**——必须分开记，否则等于把未复核的当已复核。

| SLICE-ID | AI 直出 / 人复核 | 激活的 `coding-standards` K 层条款 | 复核人 / 证据 |
|---|---|---|---|
| SLICE-001 | AI 直出 → 人复核 | 幻觉 API / 写完≠验过 / 上下文腐化 / 为变绿关检查 | <姓名 / PR 链接> |

## 4. 算法切片离线评测门

> 算法改动（prompt / 模型 / 阈值 / 权重）**必须过评测集**才允许合入（呼应假绿证伪：不许凭感觉调）。无算法改动写 `N/A + 理由`。

| 算法改动 | 评测集 / 指标 | 过门结果（未回归） | 或 N/A + 理由 |
|---|---|---|---|
| <检索权重调整> | <recall@10 / test/search-bench> | <通过 / 回归即红> | <无算法改动则 N/A + 理由> |

## 5. 出场结论与偏差回写

| 汇总项 | 结果 | 证据 |
|---|---|---|
| `coding-standards` selfcheck receipt | 在案 | <receipt>——⚠️ 只证正本在场自洽，**不证代码合规** |
| 逐条 STD-ID 实现证据 | 齐 / 缺 | <链接> |
| 偏离 S8 方案 | 已同 commit 回写飞书与受控镜像 / 无偏离 | <链接> |
| 完成度分级 | <self_reported / tested / independently-verified> | <依据>——⛔ 同进程 `selfcheck` 最高只能 `self_reported`；`tested` 须流程外见证 |

> **完成度四级(借 gstack `/cso`)**：`asserted`(只断言) < `self_reported`(执行者自报，如 selfcheck 绿) < `tested`(有测试证据) < `independently-verified`(流程外不可伪造见证)。被测代码与验证器**同进程可伪造 reporter 输出**，故最高只到 `self_reported`。

开发切片出场结论：<READY / PARTIAL / BLOCKED>。⛔ `selfcheck` 绿 ≠ 代码合规；**未逐条留下实现证据不得声称 READY**。

## 6. 代码评审结论（切片交付前必过）

> 切片交付前先过一遍**确定性代码评审**再进 S9.2 终审——把「机器能确定判定的问题」在开发侧就挡掉，人只复核机器判不了的。
> 工具正本：`open-code-review`（`ocr`，Apache-2.0，确定性规则 × Agent 混合评审，本机 `/opt/homebrew/bin/ocr`）——按 path 挂强制规则，delegate 模式跑 diff。
> 安全维度**推荐** `semgrep` + trailofbits 规则集（SQL 注入 / 路径穿越 / 不安全默认值 / 常量时间等）；⛔ 不设硬依赖——未装时人工核安全清单即可，不因缺工具在 fresh clone 判红（门不许惩罚正确代码）。

| 评审维度 | 工具/方式 | 结论（无阻断 / 无高危 / 通过 / 有阻断已处置） | 处置/证据 |
|---|---|---|---|
| 功能 / 质量 | `open-code-review`（ocr）确定性规则 | <无阻断项 / 有阻断已处置> | <链接> |
| 安全 | `semgrep` + trailofbits 规则集（推荐） | <无高危 / 已处置> | <报告链接> |
| 人工复核 | <reviewer 姓名> | <复核通过 / 打回> | <PR 链接> |

> ⚠️ 本节只证「评审已做且结论在场」，**不替代 S9.2 终审**（`s9-quality-report-gate` 侧另有交叉复核）。
