# `templates/proto/` — 可运行原型骨架（S6 的推荐形态）

**从这里起步，不要从 `demo-scaffold.html` 起步。**
那份是最小锚点示例，它示范的「一个状态一个 `<section>`」会把 demo 钉死成幻灯片。

## 为什么是四层

```
① fixtures / scenarios   种子数据 · 场景开关（条数 / 时延 / 失败 / 权限）
        ↓
② api.js                 唯一调用面。签名 = 未来真实接口的形状
        ↓
③ store.js + router.js   状态由数据推导；URL 即状态
        ↓
④ views.js               渲染 + 事件（copy.js / validators.js 是它的单一真源）
```

**单向依赖，不许倒挂。** 视图直接读 fixtures 的那一刻，「把 mock 换成真接口」
就从「改一个文件」变成「全文件搜索」——而那正是 demo 与真实实现开始分叉的地方。

> 借的是 MSW 的 **Deviation-free**：上层代码不知道自己是不是被 mock 了。
> 把 `api.js` 整体换成真 `fetch`，其余三层一行都不用改。
>
> ⛔ **这句话是本模型存在的唯一理由** —— 交互稿之所以能声称「与真实实现一致」，
> 全靠它。它此前是一句**没有任何东西验过的声称**，而 2026-09-04 实测**它当时是假的**：
> `P.scenarios` / `P.currentScenario` 都定义在 mock 层，删掉后 `boot` 直接抛，
> 页面上只剩演示外壳、产品内容一个字都不渲染。
> ⇒ 现由 `scripts/mock-seam-gate.mjs` 守着（S6 出场条件 ②g）：
> 它真的把 mock 层删掉、api 换成 fetch 桩，然后要求 boot 不抛、锚点仍在、
> **内容区渲染的是服务端来的数据**。

## 状态是跑出来的，不是画出来的

`#/inbox?scn=empty` 不是另一屏，它只是**把 fixture 换成空数组**，界面自己走到空态。
`scn=slow` 只是把时延调到 2500ms；`scn=api-500` 只是让接口抛错。

⛔ 一旦你开始为「空态」新建一个页面/分节，这份原型就退回幻灯片了。

## 三个必须遵守的机器契约

| 契约 | 谁在读 | 不遵守会怎样 |
|---|---|---|
| `window.__PROTO_ROUTES__`（路由 × 场景全展开，由 `buildRouteMatrix()` 生成） | `dead-click-gate.mjs` · `browser-audit.mjs --all-routes` | 门禁只审打开时那一屏 |
| `body[data-busy]`（有请求在飞就挂着，**归 api 层维护**） | 两道门禁的 `settle()` | 探针在异步落定前就量 → **把正确实现判成死按钮** |
| `body[data-scene]` / `body[data-fr]`（由 `boot` 自动写） | `demo-anchor-gate.py` · `reconcile-gate.py G2/G3` | G2/G3 进 UNABLE，两道对账门从不产出结论 |

⚠️ `data-busy` **只能有一个归属**（api 层）。视图层再设一遍必然分叉，
而分叉的那一次就是探针量错的那一次 —— 本骨架自己撞过。

## 怎么用

```bash
cp -r templates/proto <项目>/.product-flow/demo/src
# 1) 改 10-scenarios.js：你的产品有哪些「服务端状态」
# 2) 改 20-api.js：函数名/入参/返回/错误码 = 交给研发的接口草案
# 3) 改 60-copy.js / 70-validators.js：文案与校验规则的单一真源（研发直接拿走）
# 4) 改 50-views.js：只渲染，不判断数据从哪来
# 5) index.html 底部 PROTO.boot({end, frMap}) 填端与需求映射
#    frMap 的键有三层，写哪层由**验收标准本身的粒度**决定：
#      'f01'              界面级 —— 这个界面每个状态都算演示了它
#      'f01-error'        状态级 —— 只有 error 那一屏算
#      'f01-mobile-empty' 端+状态级 —— 只在某一端成立的 AC
#    ⛔ 别为了让 G2 变绿把状态级 AC 提到界面级：那会让空态也宣称
#       「我演示了失败重试」。锚点说谎时对账门不会报错，它会报绿。

# 文案与校验规则**从 spec 生成**，不手写
python3 scripts/spec-to-js.py <项目>/spec src/js

# 交付：合成零外链单文件
node <本仓根>/skills/product-flow/modules/prototyping/scripts/bundle.mjs src ../demo.html

# 出场前的门（都要跑）
node scripts/dead-click-gate.mjs      ../demo.html --max-dead-pct 0
node scripts/flow-walk-gate.mjs       ../demo.html --flows  <项目>/spec/flows.json
# ⚠️ 矩阵门必须**带 --dump 先跑**：本骨架的锚点是运行时写到 body 上的，
#    静态扫 HTML 一个都取不到，后面 demo-anchor / G2 / G3 拿不到输入只会 UNABLE。
#    dump 里只有**真走到过**的场景 —— 走不到的不会被一张手写表补成「有」。
node scripts/scenario-matrix-gate.mjs ../demo.html --states <项目>/spec/states.json --dump ../anchors.json
python3 scripts/demo-anchor-gate.py   ../anchors.json --prd <项目>/prd/PRD.md
python3 scripts/gate-run.py scripts/reconcile-gate.py G2 <项目>/prd/PRD.md ../anchors.json   # 经 gate-run 分键落盘（G7.5 ⑤ 读它）
python3 scripts/spec-sync-gate.py     <项目>/spec ../demo.html --js src/js
node scripts/browser-audit.mjs        ../demo.html --all-routes --all-viewports

# 双端产品必跑：端形态对账（判据见 references/platform-parity.md）
# ⛔ 实证：桌面组件工具箱与移动端框架的组件词汇**只重合 6 个** ——
#    一套 DOM 两个断点，不可能同时像最终 PC app 和最终移动 app。
node scripts/platform-parity-gate.mjs ../demo.html \
     --routes "#/inbox,#/task,#/create" --declared <项目>/spec/end-differences.json
```

## 与 `templates/spec/` 的关系

骨架**消费**六份 sidecar，不自己造事实：

| 骨架里的 | 来自 |
|---|---|
| `js/60-copy.js` · `js/70-validators.js` | **生成物**，源是 `spec/copy.json` / `spec/validators.json` |
| `js/20-api.js` 的方法与错误码 | `spec/operations.json`（`spec-sync-gate` 双向核） |
| 可点元素的可访问名称 | `spec/elements.json` |
| `?scn=` 场景与它触发的状态 | `spec/states.json`（`scenario-matrix-gate` 逐项真触发） |
| 关键路径 | `spec/flows.json`（`flow-walk-gate` 真走一遍，S8 用例也由它生成） |

## 双端 —— 交互稿必须有**两种形式**，不是一套布局换个宽度

骨架自带两个端外壳（`js/80-shell.js` + `css/app.css` 里的 `body[data-end=…]`）：

| | 桌面端 | 移动端 |
|---|---|---|
| 外框 | 1200 宽窗口 + 46px 标题栏 | **390×844 手机框**，圆角 44、顶部状态栏、底部 Home 条 |
| 导航 | **常驻左侧栏**（品牌 + 主导航） | **顶部 app bar**（标题 + 返回‹），无侧栏 |
| 页面标题 | 主区 `h1` | 在 app bar 上（`h1` 隐藏，不重复） |
| 命中区 | ≥24px | **≥44px**（列表行、按钮全部放大） |
| 列表行 | 一行内 标题/属性/操作 三段 | **堆叠**，避免把标题挤成每行 20 出头个字 |

⛔ **「两端同一套交互」（`endMode: same`）说的是交互同一套，不是形式同一套。**
桌面的常驻侧栏与移动的顶部返回，信息架构本来就不同 —— 用同一套布局糊两端，
到 S7 画稿时一定返工。

**端切换器**在设备外框**外面**、页面顶部（`#endbar`），是给评审的人用的脚手架，
⛔ 不是产品 UI，也不许放在页面底部（对方浏览器不够高就看不见，实战翻过车）。
切换会写进 URL（`?end=mobile`）——端是状态，状态就该进地址栏，也才深链得了。

⚠️ **交互稿常常是「在桌面屏幕上展示一个手机外框」**：视口 1600、指针是 fine，
但那一屏的目标输入方式就是触屏。视口宽度和媒体查询都判不出来，
所以页面自己声明 `body[data-end="mobile"]`，`browser-audit` 认这个声明去套 44px 阈值。

`spec/states.json` 每个界面必答三选一：`same` / `degraded` / `pc-only`。
路由矩阵按 `ends` 展开（`#/task/T-1000?scn=default&end=mobile`），
端进场景 ID（`f02-mobile-success`），矩阵门**逐端真跑一遍**。

⛔ **降级必须是实现**：骨架里 `f02` 声明 `degraded`，移动端的推进按钮就真的
`disabled` 且给出原因；`f03` 声明 `pc-only`，移动端就给「仅在桌面端提供」而**不是**
渲染一个点不动的表单。写了却没实现，矩阵门会当场报出来（实测抓到 3 处）。

## 已知边界（诚实缺口）

- 程序化 `.click()` **只能证伪不能证真**：门禁绿 ≠ 关键路径走得通，真人仍要点一遍。
- 瞬态区域（toast / `aria-live`）内的控件**不进点击探针**（会稳定产生假阳性），
  由 flow-walk 覆盖；门禁会单独打印「未探测 N 个」，**不折叠进通过**。
- 默认跨停靠点去重（同一路由下同名控件只点一次）。要全量：`--exhaustive`。
