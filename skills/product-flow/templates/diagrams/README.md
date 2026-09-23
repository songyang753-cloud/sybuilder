# 图源目录（示例 + 约定）

> ⛔ **图的唯一正本是本目录下的文本源**（`.d2` / `.mmd` / `.puml`）；PNG 是产物。
> 改图改源，⛔ 不改 PNG。判据见 `references/diagram-standards.md`，决定见 ADR-0012。

## 项目里放哪

```
<项目根>/.product-flow/diagrams/*.d2|.mmd|.puml     ← diagram-id-gate 在这里找
```

## 出图（本机 2026-09-12 实测）

```bash
# 产品模块图：D2 + TALA
d2 --layout=tala product-architecture.d2 out.svg    # SVG
d2 --layout=tala product-architecture.d2 out.png    # PNG，⚠️ 中文正常，无需额外字体
```

⚠️ **一个只有栅格化才炸的假绿**（实测复现）：

| 写法 | 结果 |
|---|---|
| 不传任何字体参数 | ✅ PNG 正常，中文无豆腐块 |
| 只传 `--font-regular` | ❌ `retained font bytes exceed limit 67108864` **硬失败** |

⇒ **要么都不传，要么 `--font-regular` 与 `--font-bold` 成对传。**
⭐ 出 SVG 不报错，只有出 PNG 才炸 —— 先出 SVG 会以为没事。

## 为什么产品模块图用 TALA 而不用 Mermaid

实测同一张四层架构图：一旦出现**节点级跨层连线**（真实架构图必然有），
Mermaid 的 `direction` 失效、层散开；D2 默认布局塌成一条横带。**只有 TALA 扛住**。
⚠️ 这是 **2026-09 的工具事实**，不是永久结论（见 ADR-0012 边界）。

## 九张示例（八类图各一张，产品模块图两种合法分组各一张）

⭐ **九张全部拿 product-flow 自己当对象**（⚠️ 无例外：`product-module-domain` 初稿曾用电商域举例，被 `diagram-id-gate` 端到端正例当场判红——示例图的 `M-xx` 必须与夹具 PRD 的 6.1 表双向集合相等） —— 这样跨图的 `M-xx` / `F-xx` / `P-xx`
本身就构成一次**跨章一致性**的示范，而不是七个互不相干的玩具。

| 文件 | 图类 | ID 族 | 对应 PRD 位置 |
|---|---|---|---|
| `user-flow.example.d2` | 用户流程图 | ⛔ 无 ID 族（步骤是行为不是功能条目） | 4.4 |
| `business-process.example.d2` | 业务流程图 | 泳道=角色，动作标 `F-xx` | 五章 |
| `functional-architecture.example.d2` | 功能架构图 | `F-01`…`F-06` | 6.2 |
| `product-architecture.example.d2` | 产品模块图（**行业三层**分组） | `M-01`…`M-05` | 6.1 |
| `product-module-domain.example.d2` | 产品模块图（**业务域**分组，⭐ 一圈=一个团队） | `M-01`…`M-05`（⚠️ 与上一行**同一套 ID**，只换分组方式；初稿用 `M-06/07/08` 被门禁判红） | 6.1 |
| `information-architecture.example.d2` | 信息架构 / 站点地图（层级，⛔ 无回环） | `P-01`…`P-05` | 6.3 |
| `page-relation.example.d2` | **页面关系图**（跳转拓扑，✅ 有回环） | `P-01`…`P-05` | 6.3.1 |
| `data-lifecycle.example.d2` | 数据生命周期图 | data store ↔ 附件 D 实体 | 附件 C.5 |
| `tech-architecture-c4.example.d2` | 技术架构图 C4 · Container | 容器名 | 附件 N |

⚠️ 它们是**示例不是模板**：你的 `M-xx` / `F-xx` / `P-xx` 必须来自你自己 PRD 的表，
⛔ 否则 `diagram-id-gate` 的双向集合对账会红。

### 每张图末尾都写了「这张图答不了什么」

⛔ 这不是客套 —— 八类图最常见的误用就是**拿一张图去回答它结构上回答不了的问题**
（拿功能架构图问部署、拿站点地图问数据留存）。示例里把边界写进图源本身。

### ⭐ 画的时候渲染出来才发现的一个建模错误（已留在图源注释里）

业务流程图最初画了一个 ◆「走全档还是轻档？」，两条分支**都指向同一个活动**。
读源码看不出问题，**渲染出来一眼就看见两条线并到一处**。
⇒ 轻档/全档是**输入参数**，不是决策分叉；BPMN 的网关必须导向**不同的活动**。
⚠️ 同一条教训的普遍形式：**图源写完不渲染，等于没验。**

### 本批七张的实测

```
7/7 出 SVG 成功 · 7/7 出 PNG 成功（d2 --layout=tala，未传任何字体参数）
目检 3 张 PNG：中文无豆腐块
```
⚠️ 只目检了 3 张（业务流程 / 功能架构 / 用户流程），另外 4 张只验了**渲染不报错**，
⛔ 没有逐张目检版式 —— 这是本批的诚实边界。
