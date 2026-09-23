# 「模板填好内容后」的夹具

这些是**真实填过一遍**的文档（来自 2026-09-04 的全链实跑），
每一份都能让它对应的那道门禁**退出 0**。

## 它们干什么用

`consistency-gate.py` 的 `gate-reads-template` 规则拿它们做断言：
**每道门禁必须能读懂「照它的模板正确填出来」的文档。**

⭐ 为什么不用 `templates/` 里的空模板做断言：
空模板里全是占位符，门禁**应该**因此报红 —— 那种红是正确行为。
于是「模板红了」这件事本身没有信息量，
真正要守的是「**填对了就必须绿**」。

⚠️ 2026-09-04 我第一版判据是「扫门禁在空模板上的报错措辞，
出现『整节缺失/解析不出』就算定位器坏了」—— 反向测试当场证明它只覆盖 5 处里的 2 处
（element-identity 那处报的是「不是合法标识符」，不在词表里）。
⭐⭐ **反例没红，不等于规则没问题；它也可能是规则量程盖不住。**

## 覆盖面（2026-09-04 扩到 10 对）

| 夹具 | 被哪些门禁消费 |
|---|---|
| `definition.md` + `insights.md` | `chain-gate G0` |
| `insights.md` + `definition-final.md` | `chain-gate G0.5` |
| `definition-final.md` | `definition-gate` |
| `definition-final.md` + `PRD.md` | `chain-gate G0.8` |
| `definition-final.md` + `state.md` | `chain-gate G0.9` |
| `PRD.md` | `prd_completeness_check --stage S4` · `requirements-quality-gate` |
| `PRD.md` + `cases/` | `coverage_check`（**期望退出码 3**，见下） |
| `design-brief.md` | `design-intent-gate` |
| `interaction-spec.md` | `element-identity-gate` |
| `retro.md` | `retro-gate` |

⭐ **「门禁必须绿」不等于「退出码必须是 0」**：`coverage_check` 对这份夹具的
**正确**结论是 3（对账通过，但 3 条需求只被跳过的用例覆盖）。
期望值写死 0 会逼人去删掉那三条诚实的 SKIPPED —— 三态门的合法结论不止一个。

## ⚠️ 覆盖边界（快照 2026-09-05，别读成「全覆盖」）

⚠️ **门禁总数此后已增至 43**；下面的 23/9/14 是 2026-09-05 的快照,仅用于**说明分类形态**,不是当前数字（`tests/**` 不在任何计数判据量程内,数字会静默过期）。

（快照当时）23 道门禁里，这套夹具直接服务 **9 道**。其余 14 道的情况**不一样，不要合并统计**：

| 情况 | 道数 | 说明 |
|---|---|---|
| 吃 demo.html / CSS / JSON | 12 | 它们的「填好的模板」等价物是骨架 `templates/proto`，**一直在对它跑**（`mock-seam` / `flow-walk` / `scenario-matrix` / `platform-parity` / `dead-click` 等）。不是缺口，只是不归这张表管 |
| **吃模板产出的 markdown 却没有夹具** | **2** | `research-gate`（研究目录）、`reconcile-gate`（PRD + 锚点）—— **这两道是真缺口** |

🚨 `research-gate` 的夹具**故意没有造**：它要 ≥8 份竞品档案、每份带 URL 与访问日期。
**编造出来会毁掉这套夹具自己的作用** —— 它同时是「填对了长什么样」的唯一实证，
一份编的研究档案会教人编研究。⇒ 等哪次真跑 S1 时把产物挪进来，在那之前如实空着。

## 改动这些文件的规矩

⛔ **不要为了让门变绿而改这里。** 门禁变严格时，
正确动作是**先判断新判据对不对**，对就更新夹具并在提交里说明改了什么、为什么。
这些夹具同时是给人看的**范例**：它们是「填对了」长什么样的唯一实证。
