# S4A 产品结构设计 · 门禁与结构口径

> S4A 防的是「结构未清就填 PRD 模板」。门禁 `product-structure-gate.py`，模板 `templates/product-structure.md`。

## 结构口径（由 spec 生成）

<!-- SPEC:BEGIN s4a -->

> ⚠️ **本段由 `scripts/gen-docs.py` 从 `spec/s4a-structure.json` 生成，⛔ 不要手改** —— 手改会被 `gen-docs.py --check` 判红。要改先改 spec。

**门禁**：`scripts/product-structure-gate.py` ｜ **形态**：`single-file`

**怎么跑**：`product-structure-gate.py <product-structure.md>`

**结构来源**：模板 `templates/product-structure.md`

### 必需的小节

| 小节 | 文件/位置 | 判据 |
|---|---|---|
| `1. 功能架构（功能怎么分组，不是怎么实现）` | `product-structure.md` | — |
| `2. 信息架构与导航` | `product-structure.md` | — |
| `3. 关键任务流（每个核心任务一条）` | `product-structure.md` | — |
| `4. 数据对象与关系` | `product-structure.md` | — |
| `5. 权限矩阵（附件 C.2 的上游）` | `product-structure.md` | — |
| `6. 状态与异常结构` | `product-structure.md` | — |
| `7. 结构性风险` | `product-structure.md` | — |

### ⭐ 读者分区（交付物给谁看）

**正文给人看；附件给人 + AI 编程看；⛔ 过程日志两边都不进**

- 正文：给**人**（产品总监 / 评审 / 业务方）—— 结论先行、自足，图表证据直接放正文
- 附件：给**人 + AI 编程**（研发按它写代码）—— 字段规格、状态机、ID 映射、内部锚点
- ⛔ **过程日志两边都不进**：门禁条数 / 收敛轨迹 / 第几轮 / 我犯了什么错 ⇒ 去 `.proposals/` 与 commit message

**门禁**：`audience-gate.py <交付文档.md>`　⚠️ 只拦机械可判的混入（内部路径/过程数字/自检编号/把读者支出去），拦不住「写得好不好读」

### 格式硬要求（⭐ 这些是**跑门禁才发现**的，光读判据代码看不出来）

- **数据对象**：只写**业务含义**的关键字段，⛔ 不写表结构——模板自己踩过这个坑
- **功能架构要落到 F 编号**：「功能架构」小节里必须出现 `F-xx` 形态的功能编号——判据 ① 直接搜它。⛔ 只写分组名而不挂编号 ⇒「结构没落到功能编号，PRD 3.2 接不上」。
- **任务流条目的字面**：「关键任务流」小节里每条任务必须以 **`任务：`** 开头（判据 ② 搜这个字面）。⛔ 写成「流程 1」「用例 A」都不算。
- **权限矩阵要有真实行**：「权限矩阵」必须有 ≥1 行真实数据行（表头与分隔行不算）。

### ⚠️ 已知纠错（spec 自己踩过的坑）

- **三条要求 spec 里原先没有**：⚠️ 2026-09-17 首次跑 `product-structure-gate` 才发现这三条——**读 spec 与读判据代码都看不出来**，只有拿脚手架骨架去撞门禁才会显形。⇒ 这正是「spec 三处消费」里最容易漏的一环：**scaffold 生成的骨架必须真去跑一次门禁**，否则 spec 永远停在「结构对、内容不知道要什么」。

### 怎么用

1. `python3 scripts/scaffold.py --stage s4a --out <目标>` 生成合规骨架；
2. 把每个 `⟨TODO⟩` 换成真内容（⛔ 留着占位＝**还没开始**，不是快完成了）；
3. 跑门禁到退出码 0 —— **那一步就是交付本身**，不是最后检查一下。

<!-- SPEC:END s4a -->
