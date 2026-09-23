# 流程度量层（每阶段一对 leading/lagging；借鉴 AI-Native SDLC，2026-09-08）

> 门禁答「产物合格吗」，本层答「流程顺吗」——两问都要，但地位不同：
> ⛔ **度量只进 S10 复盘，不做门禁**（速度指标做门会诱导赶工；共享机器时长只看趋势）。
> 汇算工具：`python3 scripts/flow-metrics.py <项目根>`（只读；算不出打 UNABLE 不编造）。

| 阶段 | Leading（周期） | Lagging（返工/存活） |
|---|---|---|
| S1 | 首次对话→intent commit 时长 | intent 存活率（进入 S2 的比例；no-build 不算失败） |
| S2 | intent→三报告 commit 间隔 | definition 之后 intent 的改动次数 |
| S3A/B | 研究完→Go/No-build 时长 | 定义拍板后被 S4 推翻的项数 |
| S4B | 定义→PRD v0.9 间隔 | A 锁之后 PRD 产品事实的返工 commit 数 |
| S5–S7 | v0.9→C 锁间隔 | 首次过 C 锁比例 · 锁后返工轮数 |
| G7.5 | 三锁齐→冻结时长 | 冻结失效重跑次数 |
| S8 | plan 接受→合并时长 | first-pass 合并率 · change failure rate |
| S10 | band 触发→intent 入队时长（启用持续档时） | 同类事故复发率 |

## 采集口径与诚实边界
- 时间戳来源：git 首提交时间 + `gate-run` 落盘 `ranAt`。**不在 git 里的产物该项 UNABLE**。
- gates 落盘只留末次记录 → 首过率需 `git log .product-flow/gates/` 还原（工具明示未做，不冒充）。
- 归因永远要人做：数字只指向该看哪里，「为什么慢」不在量程内。
- S10 模板「流程效率账」一节消费本层输出。
