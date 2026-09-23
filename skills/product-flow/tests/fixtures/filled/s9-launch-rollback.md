# 灰度、正式上线与回滚记录
## 0. 文档控制与入场资格
产品/版本/构建/commit：App 1.0 build-20 commit def456。
| 入场依据 | 版本 | 原物 | 结论 |
|---|---|---|---|
| S9.3 飞书报告 | r9 | 是 | 产品验收结论必须 APPROVED；receipt s93.json |
| S9.2 同构建 | r8 | 是 | PASS；receipt s92.json |
| 最终上线候选构建 | build-20 commit def456 | 是 | receipt build.json |
## 1. 灰度计划与放量梯度
| 灰度档 | 放量比例 | 观察时长 | 进入本档的条件 | 停止线 | 状态 |
|---|---|---|---|---|---|
| G-CANARY-1 | 1% | ≥2 小时 | 关键 SLI 达标 | 错误率>1% | RUN |
| G-CANARY-2 | 10% | ≥4 小时 | G-CANARY-1 DONE | 错误率>1% | PLANNED |
| G-FULL | 100% | 持续观察 | 前档 DONE + 上线批准 | 错误率>1% | PLANNED |
放量单向门：只允许升档；命中停止线只暂停或回滚。
## 2. 监测与告警口径（SLI/SLO）
每个指标绑真实数据源。
| SLI-ID | 指标 | SLO 阈值 | 观察窗 | 数据源 | 告警 | 实测 |
|---|---|---|---|---|---|---|
| SLI-001 | 错误率 | 1% | 5min | 监控看板 grafana/x | oncall | 0.2% |
| SLI-002 | P95 延迟 | 300ms | 5min | grafana/x | oncall | 180ms |
## 3. 回滚方案与演练
| 项 | 内容 |
|---|---|
| 回滚触发条件 | 命中任一停止线 |
| 回滚步骤 | 关灰度开关→切回 build-19 |
| 数据兼容与不可逆点 | 无不可逆迁移 |
| RTO | 5 分钟 |
| 回滚演练证据 | 2026-09-17 预发演练通过 receipt drill.json；未演练即 UNABLE |
## 4. 上线记录、结论与飞书回读
| 汇总项 | 结果 | 证据 |
|---|---|---|
| 未消除的停止线命中 | 0 | dash.png |
| 回滚演练 | 已演练 | drill.json |
| 证据构建绑定 | 灰度/监测/演练证据均绑定 build-20/def456；换构建即作废重跑 | dash.png |
灰度上线结论：PASS。只有 `PASS` 才算完成上线。
| 角色 | 结论 | 人/时间 | 证据 |
|---|---|---|---|
| 研发总监 | 批准上线 | 张三/2026-09-18 | r.json |
| 测试负责人 | 确认同构建 S9.2 PASS 仍有效 | 王五/2026-09-18 | q.json |
| 产品负责人 | 确认 S9.3 APPROVED 仍有效 | 李四/2026-09-18 | p.json |
飞书：https://example.feishu.cn/docx/launch
revision: r5
receipt: receipts/launch.json
回读结论：READY
