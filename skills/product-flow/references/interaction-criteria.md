# 交互的可证伪判据（S5.2 硬约束 / S6 门禁）

> 交互设计的绝大多数材料写的是「**应该怎么做**」，而不是「**怎么判断做对了没有**」。
> 本文件只收后者：每条都能在代码里 grep 到、或在浏览器里点出来。
> 拿不准某条属于哪类，问一句：**「对错误实现，它会不会给出红？」** 给不出就不属于这里。

来源：`vercel-labs/web-interface-guidelines`（MUST/SHOULD/NEVER 体例）·
`Nutlope/hallmark`（状态（**判据见 `interaction-patterns.md`，本文不复述数量**；适用即必须，不适用写理由）与 Bans）· `plugin87/ux-ui-agent-skills`（ARIA 键位表）。

---

## 一、机械可查的反模式（18 条，`scripts/interaction-gate.py` 逐条实现）

> ⚠️ **这张表与代码逐条对齐，改一边必须改另一边。**
> `consistency-gate.py` 的 `rule-count` 会核对条数；条目内容靠这条纪律。
> 📌 教训：本表曾长期声称的条数与脚本实际条数**差了两条**（文档 14 / 代码 16），
> 且**表里有两条代码根本没实现**（大数组无虚拟化 / 手势独占无替代）。
> 照着表核的人会以为它们已被门禁覆盖——这就是**覆盖静默缩水**：宣称的比实测的多。

| # | 规则 id | 模式 | 为什么是错的 |
|---|---|---|---|
| 1 | `zoom-disabled` | `user-scalable=no` / `maximum-scale=1` | 禁用缩放，低视力用户直接被挡在门外 |
| 2 | `paste-blocked` | `onPaste` 里 `preventDefault` | 拦粘贴。密码管理器、验证码、长文本全废 |
| 3 | `transition-all` | `transition: all` | 所有属性同速，且会动到你没想动的东西 |
| 4 | `outline-none` | `outline: none` 且无 `:focus-visible` 替代 | 键盘用户失去焦点位置 |
| 5 | `div-onclick` | `<div>` / `<span>` 挂 click 处理器 | 不可聚焦、不响应 Enter/Space、屏幕阅读器读不出是按钮 |
| 6 | `img-no-dim` | `<img>` 无尺寸 | 加载时布局跳动（CLS） |
| 7 | `input-no-label` | 表单控件无 label | 屏幕阅读器读不出这个框是干什么的 |
| 8 | `iconbtn-no-label` | 图标按钮无 `aria-label` | 同上 |
| 9 | `autofocus` | `autoFocus` 无明确理由 | 打断键盘用户与屏幕阅读器的阅读顺序 |
| 10 | `hover-only` | hover 效果没包进 `@media (hover: hover)` | 触屏用户会卡在 hover 态出不来 |
| 11 | `no-reduced-motion` | 有动效但无 `prefers-reduced-motion` 分支 | 前庭敏感用户无处可逃 |
| 12 | `ease-in-on-ui` | UI 过渡用 `ease-in` | 起步慢，恰好延迟了用户正盯着的那一刻（`motion-spec.md` 3.2，block 级） |
| 13 | `duration-over-budget` | UI 过渡 >300ms 且无举证 | 超预算即缺陷，举证责任倒置（`motion-spec.md` 2.1） |
| 14 | `gif` | 该用压缩视频的地方用动图 | 体积与解码开销 |
| 15 | `hardcoded-format` | 硬编码日期/数字格式 | 应走 `Intl.*`，否则多语言/多地区必错 |
| 16 | `nav-not-anchor` | 内联 `onClick` 导航而不用 `<a>` | ⌘/Ctrl+点击、中键新标签、右键复制链接全失效 |
| 17 | `keyframes-on-transient` | 瞬态/高频元素（toast/tooltip/dropdown/menu/toggle/drawer/tab）用 `@keyframes` 而非 `transition` | **keyframes 从零重启、无法从当前状态重定向** —— 快速连点会看到动画跳回起点 |
| 18 | `scale-from-zero` | 动效从 `scale(0)` 起手 | 从零放大像弹出气球；应从 `scale(0.9–0.97)` + opacity 起 |

### ⭐⭐ 第 17 条：把「可打断性」从「只能人工」变成可查的（2026-09-03）

`motion-spec.md` 一直把「可打断？」列成规格里要人填的一列，**没有任何机器判据**。
⭐ 转折点是换了个问法：**不查「它有没有被打断」（动态、难测），
查「它用的机制能不能被打断」（静态、确定）** ——
CSS `transition` 从当前计算值重定向，`@keyframes` / `animation` 从 0 重启。

> 来源：`memi-design/design-skills` 的 `review-animations`（承自 Emil Kowalski / animations.dev）
> 第 6 条：「Rapidly-triggered or gesture-driven motion must be interruptible —
> CSS transitions or springs that **retarget from current state**,
> not keyframes that **restart from zero**.」

⚠️ **诚实边界**：只看**选择器名**里有没有那几个词。名字里不带 toast 的 toast 查不出来；
JS 驱动的弹簧动画（本身可打断）也不在扫描范围内 —— 那是**漏报，不是误报**。

### ⭐ 顺带：我原有的两条动效阈值得到了独立佐证

同一份外部标准里：
- 「`ease-in` on UI is a **block**」→ 与我的第 12 条 `ease-in-on-ui` 逐字同义
- 「UI animations stay **under 300ms**；超过要举证」→ 与我的第 13 条 `duration-over-budget` 同阈值

⇒ 这两条**不是我拍脑袋定的**。此前我无法回答「300ms 这个数从哪来」，现在能了。

### ⚠️ 门禁**查不了**、必须人工核的两条（曾被误列进上表）

| 模式 | 为什么门禁查不了 | 谁来查 |
|---|---|---|
| 大数组 `.map()` 无虚拟化 | 需要知道数据量级与渲染成本，静态文本判不出「多大算大」 | S5.3 研发负责人视角 + S6 真实数据走查 |
| 手势独占的操作无点击与键盘替代 | 需要知道该手势是不是功能本身（相册的捏合缩放就是功能核心） | S5.2 交互规格逐条回答 + UE 五人格「手不方便的人」 |

**它们的合法结论只有「已人工核，发现 N 处」或「本轮未核」，不许写 ✓ pass。**

## 二、MUST / SHOULD / NEVER（原体例，可逐条核）

**触控与命中**
- MUST 命中区：**桌面指针 ≥24px · 触屏 ≥44px**；视觉元素更小时**扩大命中区**而不是放大图形
  ⚠️ 两个阈值对应两种输入方式，**不是同一条规则的宽严两档**。
  一个纯桌面产品把按钮做成 32px 是合规的；同一个按钮上触屏就不合规。
  **判定前必须先确定目标输入方式**，否则这条判据会自相矛盾。
- MUST 移动端 `<input>` 字号 ≥16px（防 iOS 自动缩放）
- MUST `touch-action: manipulation`（防双击缩放）
- NEVER 禁用浏览器缩放

**表单（15 条，相册的筛选/重命名/规则编辑器全踩）**
- MUST 输入框在重渲染后**不丢焦点、不丢值**
- NEVER 拦截 `<input>`/`<textarea>` 的粘贴
- MUST 加载中的按钮显示 spinner 且**保留原标签**（不要变成「加载中…」把标签吃掉）
- MUST Enter 提交聚焦的输入框；`<textarea>` 里用 ⌘/Ctrl+Enter 提交
- MUST 提交按钮**保持可用直到请求真正开始**，之后再禁用并转圈
- MUST 接受自由文本，**输入后再校验，不要边打字边拦**
- MUST 允许提交不完整的表单，好让校验错误浮出来
- MUST 错误内联在字段旁；提交时**焦点移到第一个错误**
- MUST `autocomplete` + 有意义的 `name`；正确的 `type` 与 `inputmode`
- SHOULD 邮箱/验证码/用户名关掉拼写检查
- SHOULD 占位符以 `…` 结尾并给出示例格式
- MUST 有未保存改动时，离开前警告
- MUST 兼容密码管理器与 2FA；**允许粘贴验证码**
- MUST 修剪首尾空格
- MUST 复选框/单选无死区，label 与控件**共用一个命中区**

**状态与导航**
- MUST **URL 反映状态**：筛选 / 标签页 / 分页 / 展开的面板都要能深链
- MUST 前进后退**恢复滚动位置**
- MUST 导航用 `<a>`（支持 ⌘/Ctrl/中键点击）
- NEVER 用 `<div onClick>` 做导航

**反馈**
- SHOULD 乐观更新，响应回来对账；失败则回滚**或**提供撤销
- MUST 破坏性操作要么确认，要么给撤销窗口
- MUST Toast 与内联校验用 `aria-live="polite"`
- SHOULD 会打开后续步骤的选项用省略号（`重命名…`），加载态同理（`加载中…`）

**指针与拖拽**
- MUST 命中区宽裕、可供性明确，避免精细操作
- MUST 第一个 tooltip 延迟出现，**同组后续的立即出现**（hover 延迟 800–1000ms，**focus 延迟 0ms**）
- MUST 弹窗/抽屉用 `overscroll-behavior: contain`
- MUST 拖拽期间禁用文本选择，并把被拖元素设为 `inert`
- MUST 拖/滑/捏/轨迹手势都要有点击与键盘替代（除非该手势本身即功能）
- MUST **看起来能点的，就必须能点**

## 三、状态：适用即必须（**四类与成员见 `interaction-patterns.md`，本文不复述**）

交互元素必须齐备**它适用的**全部状态——适用性按 `interaction-patterns.md` 四类判：
可交互元素必有 ② `hover/focus/active`；有异步即有 ① `loading/error`；
可禁用/受权限才有 ③；④ 按组件语义。

> 判据：**「适用的状态少了任何一个，这个元素就没做完；
> 不适用的状态硬凑出来，比缺失更糟——制造出来的状态会被当成真需求实现。」**
> （关闭按钮没有 loading，导航链接没有 empty——它们不是漏了。）

## 三之二、简洁 = 认知负担（正面判据；dead-click/flow-walk 管「能用」，这里管「省力」）

- MUST **每屏一个主动作**：主强调样式的 CTA 每屏唯一（多主 CTA = 没人替用户做优先级）
- MUST **渐进披露**：次要/危险操作默认收起，展开有据可查（谁、什么时候需要它）
- MUST **反馈不可删测试**：逐个问「删掉这个反馈用户会不会迷路」——会=必要留下，
  不会=删（简洁不等于删必要反馈，等于删不承担确认职责的装饰）
- 评审问句进「人工审美评审表」第 13 维；机器可查的主 CTA 唯一性归 interaction-gate B 层

## 四、Bans（硬禁，命中即缺陷）

- 把 placeholder 当 label 用
- **只在 hover 下才有的功能**（触屏用户永远够不到）
- 移除焦点环且无替代
- **给低风险操作弹确认框**（该用撤销）
- **触屏**触控目标 <44px　/　**桌面指针**目标 <24px（两者阈值不同，别混用）
- 交互元素上用自定义鼠标指针
- **禁用状态不说明为什么禁用**
- 只靠颜色表达错误
- 该用骨架屏（能显示布局）的地方用转圈

⚠️ hover 效果要放进 `@media (hover: hover)`，否则触屏用户会卡在 hover 态出不来。

## 五、输出契约

跑这套判据出报告时：**定位到 `文件:行号`、不写前言、通过就写 `✓ pass`**。
含糊的「基本符合」「大部分做到了」不算结论。
