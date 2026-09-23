# S7 前置 · Figma 基座库建法

> 高精度可编辑稿的本质是**「实例化组件 + 绑定变量」**，不是「画得像」。
> 没有基座就上手画，只会得到「看着像稿子、但每个色值都是硬编码、改一个按钮圆角要改 60 处」的东西。
>
> ⚠️ **本机绝大多数 Figma 相关 skill 都假设组件库已存在**，其中一个甚至明令禁止创建组件。
> 「怎么建库」这块只有 Figma 官方仓有答案，本文件是它的提炼。

---

## 零、开工前必须先探的两个底（不探就会白干）

### 底 1 · 模式数上限 —— 这条决定令牌结构

```javascript
// 建库第一件事：花一次配额探这个底，不要直接跑建库脚本
const c = figma.variables.createVariableCollection("__probe");
c.renameMode(c.modes[0].modeId, "Light");
try { c.addMode("Dark"); return "双模式可用"; }
catch (e) { return "只能单模式：" + e.message; }
```

| 计划 | 模式数上限 |
|---|---|
| Starter（免费） | **1** |
| Professional | 4 |
| Organization | 40 |

`addMode` 抛 `"in addMode: Limited to N modes only"` 即说明是 Starter。
**免费/View 座位很可能连 Dark 模式都加不上。**

⚠️ 抛错就得改结构：**双模式降级成「两套变量 + 一层语义别名」**，
即 `color/bg-canvas-light` 与 `color/bg-canvas-dark` 两个变量，语义层按主题切换引用。
下游 `tokens.json` 的结构要跟着变——**这是结构性决定，必须在建库前定，不能建到一半发现。**

### 底 2 · 字体可用性
```javascript
const fonts = await figma.listAvailableFontsAsync();
// 中文必须现查，不能按拉丁字体的经验猜字重串
```
服务端**没有 PingFang SC**（会变豆腐块），中文用 `Noto Sans SC`。
字重名带空格（`"Semi Bold"` 不是 `"SemiBold"`）；可变字体只有命名实例可用。
⚠️ 官方仓**全仓零中文内容**，示例字体全是 Inter——中文相关的一切都要自己实测。

---

## 零之二、令牌怎么进来：DTCG → Figma Variables（2026-09-03 补）

⚠️⚠️ **本节未在真机验证**（本账号 Figma 配额耗尽，见 `reference_figma_mcp`）。
来源是 `southleft/skills-for-figma` 的 `import-tokens-figma` / `export-tokens-figma`
的公开契约。⛔ **第一次照做时请当作待验证的方案，不要当作实测过的步骤。**

自 2026-09-03 起 `design/tokens.json` 是 **DTCG 形状**（由 `DESIGN.md` front matter 生成），
这座桥才第一次成立 —— 在此之前令牌是自定义结构，进 Figma 要先手工翻译一遍。

### ⭐⭐ 两条会让人白干一遍的

1. **重跑必须是非破坏性的：按「已保存的 id / key / 名称」匹配已有变量，命中就更新。**
   ⛔ 不匹配直接创建 = 每跑一次多一套同名变量，
   而 Figma 里**同名不同 id 的变量不会报错**，只会让下游绑定指向哪一套变得靠运气。
   ⭐ 这与本 SOP 记过的「令牌单一真源」是同一件事，只是发生在 Figma 那一侧。

2. **走 Plugin API，不要走 Variables REST API。**
   Variables 的 REST 接口是 **Enterprise 版专有**；Plugin API 在**任何 plan 上都能用**。
   📌 这条对本账号尤其要紧：当前是 Starter + View 座位，
   REST 那条路本来就走不通 —— 此前卡住时并不知道还有这个区别。

### 方向

| 方向 | 什么时候用 |
|---|---|
| **code → Figma**（import） | S5 定稿后建基座库：`tokens.json` 一次性灌成 variable collections + modes |
| **Figma → code**（export） | 设计师在 Figma 里改了令牌，回灌 `DESIGN.md` 的 front matter；⚠️ 回灌后必须重跑 `design-to-tokens.py --check`，否则又变成两个源 |

⛔ **两个方向不要同时开**。哪一侧是源，在项目开工时定死写进 `state.md`；
两边都能改 = 没有源。

## 一、建 Variables（六步，缺一不可）

```
createVariableCollection → renameMode(默认模式) → addMode×N → createVariable
  → setValueForMode(每个模式) → .scopes = → setVariableCodeSyntax(每平台)
```

```javascript
const colorColl = figma.variables.createVariableCollection("Color");
colorColl.renameMode(colorColl.modes[0].modeId, "Light");   // 自带的 Mode 1 删不掉，只能改名
const lightModeId = colorColl.modes[0].modeId;
const darkModeId  = colorColl.addMode("Dark");              // ← 底 1 探过才写这行
```

### 别名引用（语义层绝不许重复原始值）
```javascript
const v = figma.variables.createVariable(name, colorColl, 'COLOR');
v.setValueForMode(lightModeId, figma.variables.createVariableAlias(getPrim(lightPrim)));
v.setValueForMode(darkModeId,  figma.variables.createVariableAlias(getPrim(darkPrim)));
v.scopes = scopes;
v.setVariableCodeSyntax('WEB', `var(${cssVar})`);
```
- `createVariableAlias()` 传的是 **Variable 对象本身，不是 id 字符串**
- 被引用变量**必须同 `resolvedType`**
- 别名前先把 primitives 全查出来做 name→Variable 映射；**`getPrim()` 找不到就 throw，不许静默降级**

### scopes（**永不用 `ALL_SCOPES`**）
| 角色 | scopes |
|---|---|
| primitive 原始色 | `[]` 对设计师完全隐藏（唯一例外：半透明遮罩给 `["EFFECT_COLOR"]`） |
| 背景填充 | `["FRAME_FILL","SHAPE_FILL"]` |
| 文字色 | `["TEXT_FILL"]` |
| 描边色 | `["STROKE_COLOR"]` |
| 图标色 | `["SHAPE_FILL","STROKE_COLOR"]` |
| 阴影色 | `["EFFECT_COLOR"]` |
| 间距/内边距 · 圆角 · 宽高 | `["GAP"]` · `["CORNER_RADIUS"]` · `["WIDTH_HEIGHT"]` |
| 字号/行高/字距/字重 | `["FONT_SIZE"]` · `["LINE_HEIGHT"]` · `["LETTER_SPACING"]` · `["FONT_WEIGHT"]` |
| 字体族 / 样式名 | `["FONT_FAMILY"]` · `["FONT_STYLE"]`（STRING） |
| BOOLEAN | **不支持 scopes，直接不设** |

⚠️ `ALL_FILLS` 与单项 fill scope **互斥**——设了它就不能再加 `FRAME_FILL` 等。

### ⚠️ 最容易踩且**静默失败**的一条
**WEB 的 code syntax 必须带 `var()` 包装。**
写成 `--color-bg-primary`（没有 `var()`）→ **Dev Mode 会退回显示原始 hex**，
研发拿到的不是变量引用而是写死的色值，而画面看起来完全正常。
ANDROID 与 iOS 不要包装。

---

## 二、建 Text Styles

`createTextStyle` → 设 `fontName`（需先 `loadFontAsync`）→ `fontSize` → `lineHeight` → `letterSpacing`。

- 行距/字距的单位是 `{unit:'PIXELS'|'PERCENT', value}`；官方示例只给了 `PIXELS`
- **中文行距 ≥1.4**，比拉丁文更需要；中文**不用 italic**（浏览器/Figma 合成斜体是低级错误，强调用字重或颜色）
- 阴影走 `createEffectStyle`，与 Text Style 是两套 API

---

## 三、建 Master Components 与变体

```
createComponent ×N（每个变体一个）→ 定位 → combineAsVariants(数组, parent) → 设组件属性
```

### ⛔ 四条硬规则
1. **没有 `figma.createComponentSet()`** —— **建不出空的组件集**。
   组件集只能「先建一堆 component，再合并」。
2. `combineAsVariants` 后**所有变体叠在 (0,0)**，必须手工定位 + `resizeWithoutConstraints`。
3. `addComponentProperty` 的**返回值会被追加 `#id:id` 后缀**——
   后续引用必须**存返回值**，不能用你传进去的名字。
4. **变体组合数有 30 的上限**，超了要拆成多个组件集（例：把 size 拆出去单独成组件）。

### 变体命名
`type=primary, state=hover, size=md` —— 属性名与值都用小写，逗号加空格分隔。

---

## 四、写后必须回读校验（这一步最容易被跳过）

官方流水线里有独立的 `validateCreation` 环节。**写完不等于写对**，
尤其是上面那条「code syntax 少写 `var()`」——画面正常但 Dev Mode 是错的。

校验至少覆盖：
- 变量数量与预期一致；每个变量的每个模式都有值（没有空模式）
- scopes 不为 `ALL_SCOPES`；primitives 的 scopes 为空
- code syntax 的 WEB 项带 `var()`
- 组件集的变体数 = 预期组合数；组件属性名取自返回值
- **孤儿清理**：合并变体、改结构后会留下无父节点的残留节点，跑 `cleanupOrphans` 类逻辑清掉

⚠️ 校验必须**重新读回来**，不能用「我刚写的所以我知道它是什么」——
这正是 M5 证据独立性要防的东西。

---

## 五、建完之后：跑可编辑性门禁

```bash
python3 scripts/figma-editability-gate.py <fileKey> --strict
```
走 REST API 读取，**不消耗 MCP 写入配额**，可反复跑。四个比率见 `design-quality-gates.md`。

**基座建成后 strict 档必须过**——它是「基座真的建成了」的可证伪判据，
比「我跑完了建库脚本」可信得多。

---

## 六、画屏阶段的纪律（基座建好之后）

- **实例化而非重建**：库里有的组件一律 `importComponentByKeyAsync` + `createInstance()`，
  **绝不重画**。禁止重建的基础件：Button / Input / Checkbox / Toggle / Badge / Tag /
  Avatar / Icon / Tab / Breadcrumb / Toast / Alert / Spinner。
- **组件存在但缺 variant** → 仍然 instance + 逐实例覆盖 fill/text/size + 打 Drift 标注，
  **不许降级成 primitive**。可安全覆盖而不断链的属性：`fills` / `strokes` / 子节点 `characters` /
  `resize()` / 嵌套文本样式。
- **「60 个 badge = 60 个 instance，绝不是 60 个 frame」**——像素完美但全是 primitive 的稿子＝失败。
- **Auto Layout 顺序铁律**：`resize()` 必须在 `primaryAxisSizingMode`/`counterAxisSizingMode` **之前**
  （反了会塌成 1px 不可见）；`layoutMode` 必须在任何 `setBoundVariable` **之前**。
- **语义命名**：每个节点斜杠层级命名（`Card / Title`、`Button / Primary`），绝不留 `Frame 12` 默认名。
- **一次 `use_figma` 只做一个 section**，并 `return { created: {...node ids} }` 回传，供写后校验用。

---

## 七、写入契约（本机 MCP 直写）

- 换页必须 `await figma.setCurrentPageAsync()`，不能直接设 `figma.currentPage`
- 文本先 `loadFontAsync`
- **脚本原子执行**，报错整段不生效
- 结果靠 `return` 回传，**`console.log` 不回传**
- 禁用：`loadAllPagesAsync` / `setPluginData` / `createImageAsync`
- `node.query()` **不吃中文选择器**（会抛 `Invalid selector`）——中文图层名一律 `findAll` + JS filter
- 改 instance 子节点必须**先 appendChild 挂载再改**，别用 `.children[i]` 索引
- 组件 instance 内部节点 `I<id>;0:x` **不可单独寻址**

---

## 八、诚实边界

- 本文件解决「稿子能不能维护、研发能不能用」，**解决不了「稿子好不好看」**
- 官方仓的绑定脚本只覆盖 8 个属性（fills/strokes/四向 padding/itemSpacing/cornerRadius），
  **不含 width/height、strokeWeight、opacity、字号/行高**——而 scopes 能力表里这些都有。
  **能力表比绑定脚本宽，缺的要自己补。**
- **文字节点绑 Text Style 的写法官方仓里没有**，要自己实测（走 `setTextStyleIdAsync`，不是变量 API）
