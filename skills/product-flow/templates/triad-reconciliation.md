# G7.5 三方冻结对账报告（PRD ↔ Figma ↔ HTML）

> **执行物是 `scripts/g75-freeze-gate.py`**（本地六查真跑+原生证据三查）；本文件是给人读/给人签的报告模板，⛔ 不许只填表不跑门。

> 每项给 PASS / FAIL / N/A / UNABLE + 证据。⛔ 不许用总分掩盖单项 P0 缺口。
> 只有 MD 摘要/导出/截图/链接的项 → 对应原生检查**不得判 PASS**（最多 UNABLE）。
> ⚠️ 本机现状（2026-09-07）：飞书原生回读依赖 feishu CLI（本机有）；Figma 结构回读
> 卡配额时 2/3 类原生证据缺失 → 冻结结论上限是「本地契约验证通过」，不是 integrated-frozen。

| # | 检查 | 结果 | 证据 |
|---|---|---|---|
| 1 | 飞书原生回读在案：revision/关键段落/批准状态与 contract-manifest 一致 | | |
| 2 | Figma 结构回读 + 关键场景视觉快照在案，version 与 manifest 一致 | | |
| 3 | HTML 真实浏览器跑过：buildHash/场景可达/flow 回放/控制台干净 | | |
| 4 | PRD→Figma：每个需视觉呈现的 FR/AC 有场景与 node（`reconcile-gate G3`） | | |
| 5 | Figma→PRD：每个产品场景反查得到 FR/AC（探索稿显式排除） | | |
| 6 | PRD→HTML：每个可操作 FR/AC 有可达 flow 或显式 N/A（`reconcile-gate G2`） | | |
| 7 | HTML→PRD：行为/验证/权限/错误/恢复反查得到产品规则 | | |
| 8 | Figma↔HTML：同一 SCN 的内容/层级/状态/token/端形态一致（`platform-parity` + 检查点截图） | | |
| 9 | spec 投影与各域权威一致，无手改投影双源（`spec-sync`） | | |
| 10 | 高/中强度 INS 均有处置（洞察账本） | | |
| 11 | PRD 已回灌 v1.0：OPEN 项清零或显式延期（`prd-backfill.md` open=0） | | |
| 12 | 高影响 DELTA 全部回灌/拒绝/批准延期（`deviation-register.md`） | | |
| 13 | contract-manifest 三件套版本/回读时间与实际证据一致 | | |
| 14 | 人工基于飞书原文 + Figma 原图 + 可运行 HTML 完成联合验收 | | |

**冻结**：全部非 FAIL 且 1–3 为 PASS → `TRIAD-vX.Y` 写入 contract-manifest；
任一权威版本变化 → 冻结自动失效。
