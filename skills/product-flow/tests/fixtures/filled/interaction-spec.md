# 门禁结果看板 · 交互规格（S5.2）

## 元素标识表

**同一个标识符必须原样出现在四个地方**，这样它们才对得上：

| 出现在哪 | 形态 |
|---|---|
| 本表 | 标识符本体 |
| HTML 交互稿 | `id="..."` |
| Figma 图层名 | 同名 |
| 测试用例的选择器 | 同名（或 `data-testid`） |

> ⚠️ 这张映射表是**照官方模板保留的** —— 它的数据行含「标识符本体」四字，
> 曾让 `element-identity-gate` 误把 `HTML 交互稿` / `Figma 图层名` 当成元素，
> 并报出 `igma` 这种文档里根本不存在的字符串。
> ⭐ 夹具必须**忠实于模板的结构**，否则它守不住那一类缺陷（2026-09-04 实测：
> 第一版夹具把这张表写成了散文，反向测试因此没有变红）。

| 标识符 | 类型 | 归属区块 | 用途（这个元素的活儿） | 触发它的用户动作 | 服务哪条需求/驱动力 | 怎么算成功 |
|---|---|---|---|---|---|---|
| `board-gap-section` | 容器 | 顶部 | 承载「从来没跑过」的那批门，置顶 | — | `FR-031` | 打开后第一眼落在它上面 |
| `board-gap-title` | 文本 | gap-section | 写出数量的整句：「这 N 道门从来没跑过」 | — | `FR-031` `AC-8` | 不用图例就能懂 |
| `board-gate-table` | 容器 | 主区 | 已跑过的门，按结论排序 | — | `FR-011` | 一屏内可扫完 20 行 |
| `board-gate-row` | 交互 | gate-table | 一行＝一道门，点开看详情 | 点击 / Enter | `FR-011` `FR-021` | 打开详情覆盖层 |
| `board-verdict-mark` | 展示 | gate-row | 结论标记（通过/失败/跑不了/**从没跑过**） | — | `FR-011` `AC-2` | 四种状态互不相同 |
| `board-stale-badge` | 展示 | gate-row | 产物比结论新时出现 | — | `FR-012` `AC-4` | 不覆盖结论标记 |
| `board-detail-overlay` | 容器 | 全局 | 桌面居中 modal / 移动底部 sheet | 点行 | `FR-021` `AC-6` | ESC 或下滑可关 |
| `board-detail-stdout` | 展示 | detail-overlay | 门禁原始输出，等宽 | — | `FR-021` `AC-5` | 与结果文件逐字相同 |
| `board-detail-close` | 交互 | detail-overlay | 关闭并把焦点还给来源行 | 点击 / ESC | `FR-021` | 键盘用户不丢位置 |
| `board-error-note` | 反馈 | 主区 | 三种读取失败各自的文案 | — | `NFR-OBS-001` `AC-12` | 三句互不相同 |

## 状态四类

| 元素 | 数据状态 | 业务状态 | 表现策略 | 权限 |
|---|---|---|---|---|
| `board-gate-table` | loading / success / **all-not-run** / error | — | skeleton（行数＝期望清单长度） | — |
| `board-gap-section` | — | 有缺口 / 缺口为 0（**整个消失，不留空壳**） | — | — |
| `board-detail-overlay` | loading / success / error | 打开 / 关闭 | 桌面 pop-in 140ms · 移动 sheet-up 220ms | — |

⛔ 没有 `empty` 态：**空表会被读成「没有门禁」**，而真相是「一道都没跑过」。

## 键盘契约

| 元素 | 键 | 行为 |
|---|---|---|
| `board-gate-row` | Enter / Space | 打开详情 |
| `board-detail-overlay` | ESC | 关闭，焦点回到来源行 |
| `board-detail-overlay` | Tab | 焦点在覆盖层内循环，不逃逸到背景 |
