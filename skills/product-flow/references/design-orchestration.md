# 设计编排：Skill 调用顺序与规则

本文件定义 **S5.1 设计系统建立**如何串联多个设计 skill，以及视觉层叠加的优先级。

S5「设计交互迭代」内部分三小步：**S5.1 设计系统 → S5.2 交互规格 → S5.3 多视角评审**（评审见 `review-perspectives.md`）。

---

## 〇、S5.1 之前：设计意图从哪来（治「方案自洽但平庸」）

设计自洽只是及格线。**真正的问题是「你在哪里冒险」。** 冒险的依据来自这一步。

开工先读取 S2 的 `设计视觉调研报告`、`downstream-coverage.md` 和相关 `COMP/CLM/INS/OPP` 锚点；
每个视觉参照都要说明“为何适合该竞品的定位、用户和内容”“我们借什么/不借什么”。
只写“参考某竞品”或贴一张情绪图，不构成设计输入。

### 0.1 三层调研综合（不是「看看竞品」）
| 层 | 问什么 | 产出 |
|---|---|---|
| **L1 惯例** | 这个品类**所有**产品共有的模式是什么 | 这些是 table stakes，用户**期待**它们存在，动它们要付代价 |
| **L2 新势** | 当下正在冒头的新模式是什么 | 候选的差异化来源 |
| **L3 第一性** | 针对**这个**产品的用户与定位，**品类惯例哪里是错的**？该在哪里故意背离？ | RISK 的来源 |

### 0.2 ⭐ EUREKA 句式（L3 有真洞察时必须写成这个形状）
```
EUREKA：每个 <品类> 产品都做 X，因为它们假设 <某个假设>。
        但这个产品的用户 <证据>，所以我们应该改做 Y。
```
**写不成这个形状，说明还没有洞察，只是「感觉可以不一样」。**
句式里的三个空格缺一不可：**惯例 X · 惯例背后的假设 · 推翻该假设的证据**。

### 0.3 调研手段的三档降级（用了哪档要写进报告）
① 真实浏览竞品 + 截图 + 网络检索 → ② 只有网络检索 → ③ 只有内置知识
⚠️ 降到 ③ 时**必须显式声明**，因为内置知识对「当下正在冒头」这一层几乎无效。

## 〇之二、⭐⭐ 品味记忆：收敛在品味、发散在执行（用户 2026-08-31 拍板）

### 它解决的那个冲突
本 skill 原有「跨代反收敛」要求每代不得复用同一字体族、同一配色族、**同一明暗方向**；
而 gstack 的 Taste Memory 要求把生成偏置到用户已证明的偏好上。二者看似方向相反。

**真正的问题是老规则切错了地方**：它把「明暗方向」放进了发散轴。
而明暗恰恰是最典型的品味——**一个反复选浅色的用户，你每代强行给他深色，
不是在反 slop，是在交付他明确不要的东西。**

### 两轴（判据只有一条）
> **换掉它，用户会说「这不是我要的方向」，还是「这个也行，甚至更好」？**
> 前者 → 品味轴，**收敛**。后者 → 执行轴，**发散**。

| 轴 | 属性 | 跨代要求 |
|---|---|---|
| **品味（收敛）** | 明暗方向 · 语义档位 · **字体气质类别** · 色彩温度 · 信息密度 · 动效强度 | 与档案强信号一致；偏离要在简报里写理由 |
| **执行（发散）** | **具体字体族** · 具体强调色 · 视觉锚点食谱 · 布局构图与节奏 | Greenfield/Overhaul 不许复用上代；**Preserve 反过来，必须保持** |

⚠️ 「衬线 vs 无衬线」是品味；「Georgia vs Source Serif」是执行。
**同一气质下换具体字体，是发散不是背叛。**

### S5.1 开工前跑（两条命令）
```bash
python3 scripts/taste-memory.py read  .product-flow/design/taste.json          # 拿偏置当起点
python3 scripts/taste-memory.py check .product-flow/design/taste.json \
        --brief .product-flow/design/design-brief.md --mode greenfield          # 出场前校验两轴
```

### 收工后记（否则档案不会长）
```bash
# 用户拍板之后，把这一轮的取舍记回去
python3 scripts/taste-memory.py record .product-flow/design/taste.json \
        --dim 明暗 --value 浅色 --verdict approved --why "照片保真优先"
python3 scripts/taste-memory.py log-generation .product-flow/design/taste.json \
        --font "Source Serif" --accent "#1F6F5C" --anchor muji-kenya-hara --layout 单栏长卷
```

### ⛔ 三条纪律（不守就会把品味变成 slop）
1. **偏置不是判据。** 品味档案给的是**起点，不是门禁**——它永远不许把方案判成不合格，
   只会在偏离时要求写理由。**做成硬门禁会让品味固化，而固化的品味就是 slop。**
2. **单次认可不构成品味**（n≥2）。三选一里选中一个是「best of 3」，不是「我爱这个」。
3. **否决权重是认可的 2 倍**。人会接受平庸，但只会明确拒绝真正不要的东西。
   ⚠️ 置信按 **5%/周衰减**，读时计算——半年前的偏好不该压过上周的。

⭐ **档案要能被推翻**：如果一条 RISK 提案**故意背离**了品味档案而用户认可了，
那是比旧档案**更强**的信号——立刻 `record` 更新它，不要留着旧偏好继续偏置。

## 一、S5.1 设计系统建立（串行，不可并行）

### 调用顺序

```
S5.1a  ui-ux-pro-max --design-system --json   →  行业基线数据（不落盘！见下）
  │         ↑ 已有设计系统 → 跳过此步
  ▼
S5.1b  web-design-engineer 选定 1 个视觉锚点食谱  →  精确 hex/字体/间距/圆角/阴影/缓动
  │         ⭐ 必须在 impeccable 之前 —— 见「为什么食谱属于 S5.1 而不是 S6」
  ▼
S5.1c  impeccable /init 或 /document          →  唯一 DESIGN.md（把 a 的数据 + b 的精确值一起喂进去）
  │                                           →  同时产出 tokens.json（机器可读，逐条带 source）
  ▼
S5.1d  design-system 的 component-specs        →  组件像素级规格并进 DESIGN.md 组件节
  ▼
S5.1e  验证四关（缺一不可）
  │    ① impeccable /audit                  → 设计一致性（LLM 判断）
  │    ② detect.mjs                         → 确定性检测器（补充证据，见下方诚实边界）
  │    ③ token-provenance-gate + ai-slop-gate → 见 references/design-quality-gates.md
  │    ④ 技术可行性 checklist（含对比度）      → 见第三节
  ▼
S5.1f  design-shotgun（可选）                 →  多方案对比板
  ▼
S5.1g  人裁决 + 落盘                          →  decisions.md（模板 `templates/design-decisions.md`）
```

⚠️ **S5.1a 只用 `--json`，绝不用 `--persist`。** `--persist` 会落一份 `MASTER.md`——
⭐⭐ **2026-09-03：令牌从「两份手工同步」改成「一份生成」。**
原契约是 `DESIGN.md`（正本）+ `tokens.json`（**镜像**）——「镜像」就是手工同步的第二个源。
本 SOP 今天已经在**文案、校验规则、元素身份**三处修过同一个病：
**两处各写一遍必然分叉，而分叉那天两边都还是绿的**。令牌是第四处。
⇒ front matter 是唯一源，`tokens.json` 由 `design-to-tokens.py` 生成，
`--check` 会抓出「手改了产物」或「改了 front matter 没重新生成」。
**骨架在 `templates/design-md.md`** —— front matter 的 schema、`sources:` 的三种粒度、
以及下面两节必需章节的写法示例都在里面，从它起步。

⭐ **占位符蒙混不过去**（实测）：模板自带的 `measured:<从哪量的>` 能过结构检查，
但 `token-provenance-gate` 会逐条去 grep 那个路径 —— 文件不存在即红。
⇒ 两道门是**分层**的：`design-to-tokens.py` 查**结构**（章节在不在、有没有 source），
`token-provenance-gate.py` 查**出处是不是真的**。缺任一层，另一层都会漏。

### ⭐⭐ DESIGN.md 正文必须有的两节（拿 74 个真实品牌对出来的）

在 `VoltAgent/awesome-design-md` 里数了 **74 个真实品牌的 DESIGN.md**
（linear / stripe / notion / vercel / figma / shopify / apple / tesla …）的章节分布：

| 章节 | 出现率 | 我原来有没有 |
|---|---:|---|
| overview / colors / typography / layout / components / shapes / elevation | 63–64 / 74 | ✅ 有 |
| do's and don'ts | 63 / 74 | ✅ 有（散在规则集里） |
| responsive behavior | 51 / 74 | ✅ 有（断点行为） |
| **iteration guide** | **50 / 74** | ⛔ **完全没有** |
| **known gaps** | **43 / 74** | ⚠️ 有原则（诚实缺口），**没有固定落点** |

⇒ 这两节现在是**必需**的，`design-to-tokens.py` 查（缺任一即红）。

**`## Known Gaps`** —— 诚实缺口的固定落点。
⭐ 真实文件的写法比我原来的标准高一档：**每条都说清「为什么缺」和「怎么办」**。
> linear：「表单校验样式在被检视的页面上看不到」「浅色主题没写，因为营销站根本不出浅色」
> 「字体是专有的，**用开源替代可以**」
> notion：「动效时长没提取，**建议 150–200ms ease**」「色调映射是观察得来的，**真实品牌库可能更多**」
⛔ 只写「本轮不做」不够 —— 读的人还是不知道该怎么办。

**`## Iteration Guide`** —— 回答 agent **最先撞上**的那个问题：
「我要一个这里没有的值，怎么办？」
> linear 的写法：一次只动一个组件、按 `components:` 的令牌名引用它 ·
> 新增区块先决定它落在哪一层表面 · 正文默认 `{typography.body}` 400 ·
> 改完跑 lint · 新变体作为独立组件项 · **把稀缺色当稀缺资源用**（只给品牌标记/主 CTA/焦点/链接强调）

⭐ 附带收益：这个格式**别的 agent 直接读得懂**，也能被 `npx @google/design.md lint`
校验（断链的 token 引用、对比度），并能双向转换到 Figma variables / Tailwind / Style Dictionary。

里面已含四个组件的完整 CSS 和一份交付前 checklist，与随后 impeccable 产出的 `DESIGN.md`
大面积重复且数值可能不同。**仓库里出现两份「设计系统文件」是这条流水线最容易踩的坑。**

### ⭐ 为什么食谱属于 S5.1 而不是 S6

食谱给的是**令牌级精确值**——按角色命名的 hex、真实字体名与字重字号、间距阶梯、圆角、
阴影具体值、缓动曲线与时长。这些是**令牌本身**，不是「视觉表达」。

把它放在 S6 视觉层会直接违反本文件第四节定的「中层不许改令牌」：食谱一旦生效，令牌必然变。
所以它必须在 `DESIGN.md` 定稿**之前**进来。

⚠️ **锚点可以只借设计语言、不照搬底色**。例：某深色底的开发者工具食谱，
其间距阶/圆角阶/快捷键 chip/浮层阴影都可借，但照片类产品必须浅色（内容才是主角）——
底色走自己的，用 Variables 的 Light/Dark 两个 Mode 两头覆盖。**借了什么、没借什么，写进 decisions.md。**

### 为什么是串行不是并行

ui-ux-pro-max 和 impeccable 都会产出 DESIGN.md，并行跑会得到两份冲突的令牌文件。
串行的逻辑是：先用行业数据生成基线（ui-ux-pro-max），再在基线上做产品化定制（impeccable）。
最终只有**一份 DESIGN.md**，下游 demo 和 Figma 只读这一份。

### ⭐ 令牌的单一真源与两个下游

三个 skill 会产出三种不兼容的令牌文件（impeccable 的 `DESIGN.md` / ui-ux-pro-max 的 `MASTER.md` /
design-system 的 `tokens.css`+`tokens.json`）。**裁决**：

| 文件 | 角色 |
|---|---|
| `design/DESIGN.md` | **唯一源**：YAML front matter（令牌，机器读）+ 正文（理由，人读）。<br>格式取 **google-labs-code/design.md**（27k★，给编码 agent 的视觉身份格式规范，脱胎自 W3C DTCG）<br>⭐ 本 SOP 在标准之外加了 `sources:` 段（逐条出处）—— 标准没有这一层 |
| `design/tokens.json` | **生成物**（`scripts/design-to-tokens.py`），⛔ 不许手改 |
| ~~`MASTER.md`~~ | 不落盘（S5.1a 只用 `--json`） |
| ~~独立的 `tokens.css`~~ | 不保留；design-system 的组件规格作为**内容**并进 DESIGN.md |

**`tokens.json` 一份、两个下游**：S6 由它生成 CSS `:root`，S7 由它生成 Figma Variables。
这解决了「demo 的令牌与 Figma 的 Variables 各写一遍、然后悄悄不一致」。

### ⚠️ 改版场景（不是新建）走另一套：重设计协议

**先分类，三选一，写进 `decisions.md`**：

| 模式 | 含义 | 旋钮限制 |
|---|---|---|
| **Greenfield** | 从零建 | 无限制 |
| **Preserve** | 保留现有品牌与结构，只提升执行质量 | **视觉丰富度与动效强度最多只准 ±1 档** |
| **Overhaul** | 方向性重做 | 需明确授权，且要说明旧方案哪里错了 |

### ⛔ 八条受保护契约（改版时**绝不许静默变更**）
1. 路由 / slug / 锚点　2. Logo　3. 表单字段名与顺序　4. 法务文案
5. 埋点与其依赖的选择器　6. 已有的无障碍成果　7. 公开的组件 API　8. 用户的真实数据

要动其中任何一条，**必须单独提出并拿到确认**——这些东西的下游依赖是隐形的，
改了不会立刻出错，会在几周后以「数据对不上」「链接失效」的形式冒出来。

### 最小改动阶梯（Preserve 模式下按顺序爬，能停就停）
令牌值 → 间距节奏 → 排版层级 → 组件内部结构 → 组件替换 → 布局 → 信息架构 → 品牌
**爬得越高，风险越大。在能解决问题的最低一级停下。**

### 已有设计系统时的处理

如果项目已有设计系统（自有 design system / 公司 UI 规范 / 第三方组件库主题），跳过 S5.1a，直接以现有系统为基线进入 S5.1b。
impeccable /init 时把现有系统的令牌值喂进去作为约束。

---

## 二、语义四档旋钮

设计简报里用语义档，不用数字——因为各 skill 的数字刻度不同。

| 语义档 | 含义 | taste DESIGN_VARIANCE | ui-ux-pro-max --variance | impeccable 适用命令 |
|--------|------|----------------------|--------------------------|-------------------|
| **克制** | 极简、功能优先、零装饰 | 3 | 2 | /distill |
| **标准** | 行业常规、平衡感 | 6 | 5 | — |
| **丰富** | 有个性、视觉丰满 | 8 | 7 | /bolder |
| **极致** | 大胆、突破常规 | 10 | 9 | /overdrive |

| 语义档 | taste MOTION_INTENSITY | ui-ux-pro-max --motion |
|--------|----------------------|----------------------|
| **克制** | 2 | 2 |
| **标准** | 5 | 4 |
| **丰富** | 7 | 7 |
| **极致** | 10 | 9 |

| 语义档 | taste VISUAL_DENSITY | ui-ux-pro-max --density |
|--------|---------------------|------------------------|
| **克制** | 3 | 3 |
| **标准** | 5 | 5 |
| **丰富** | 7 | 7 |
| **极致** | 9 | 9 |

---

## 三、S5.1e 四重验证

### ① 设计一致性（impeccable /audit）

检查 DESIGN.md 自身的一致性：
- WCAG AA 对比度（正文 ≥4.5:1，大字 ≥3:1）
- 色彩系统连贯：**主色 ≤3 个**、非灰色总数 ≤12、强调色占比 5–10%（`visual-spec.md` 3.2）
  ⚠️ 这三条可量；「关系是否协调」不可量，归 S5.3 的 UI 视角人工判，**不要写进 checklist**
- 字号层级连贯（标题→正文→辅助 递减有序）
- 间距比例系统（基于 4px 或 8px 倍数）
- 圆角一致（同类组件圆角值相同）

### ② 技术可行性（研发 checklist）

```
DESIGN.md 技术可行性审查：
- [ ] ⭐ 对比度：正文 ≥4.5:1 · 大字(≥18px 或 bold ≥14px) ≥3:1 · UI 组件/图标/边框 ≥3:1
      （长文阅读建议 7:1；正文对背景 ≥4.5:1 即合格 —— ⚠️ 旧文写「不得浅于 #525252，#666 只有 3.8:1」，
        那个数是错的：#666666 对白实测 5.74:1，见 visual-spec.md 3.1）
- [ ] ⭐ 暗色模式不是反色：surface 用高度表达层级、文字用 off-white(~#E0E0E0) 不用纯白、
      主强调色去饱和 10-20%
- [ ] 色值格式目标浏览器全支持（oklch → 提供 fallback hex）
- [ ] 字体在目标平台可加载
      Web: Google Fonts / 自托管
      Figma MCP: Noto Sans SC（PingFang SC 服务端不存在）
      嵌入式/离线 Web: 内嵌字体需计入 bundle 预算
- [ ] 间距值与 CSS 框架基准兼容（Tailwind 4px 倍数 / 自定义）
- [ ] 圆角/阴影/滤镜不依赖浏览器特性标志
- [ ] 动效 timing 在低端设备可接受（嵌入式浏览器、低端安卓尤其注意）
- [ ] 无需 GPU 加速的场景未使用 GPU 密集特效（blur/backdrop-filter）
```

### ③ 确定性门禁（见 `references/design-quality-gates.md`）
```bash
python3 scripts/token-provenance-gate.py design/tokens.json --asm prd/附件B.md
python3 scripts/ai-slop-gate.py design/ --profile zh
node ~/.claude/skills/impeccable/scripts/detect.mjs --json <样例页面>
```

⚠️ **detect.mjs 的诚实边界**：它有四个引擎，但**静态文件下只跑得动 3 个**——
依赖布局与视口的规则（巨标题占比、实际渲染对比度）全部弃权。实测埋 6 个缺陷只报出 2 个。
**它的发现可采信，它的沉默不可采信**（M6）。不得据其 exit 0 宣告干净。

### ④ 字体裁决（三个 skill 的字体判据互相打架，必须裁决）

同一台机器上：impeccable 禁 15 个 OVERUSED_FONTS（含 Inter / Space Grotesk / Plus Jakarta Sans /
Newsreader）；web-design-engineer 的 `advanced-patterns.md` 字体推荐表**正好推荐这四个**；
ui-ux-pro-max 生成的基线经常直接回落到 Inter；taste 另禁 Fraunces / Instrument Serif。

**裁决：以禁用侧为准**（禁用是可证伪的，推荐是品味）。
- 合并三家黑名单去重，DESIGN.md 里出现任一即红
- **例外**：食谱本身规定的字体（如某食谱故意用系统字体、某食谱只用 Helvetica）——
  此时必须在 `decisions.md` 里显式登记「食谱例外 + 理由」，否则仍判红
- ⛔ **`web-design-engineer/references/advanced-patterns.md` 的字体推荐表在本流程中作废，不许引用**

不通过 → 修 DESIGN.md 对应令牌 → 重跑 impeccable /audit 确认没有因修改引入新问题。

---

## 四、S6 视觉层叠加优先级

三层从低到高：

```
┌─────────────────────────────────┐
│  顶层：taste 反 slop 质检        │  只检查不改令牌
│  （AI 默认风格检测、禁用字体…）   │  发现问题 → 报告，由人决定是否修
├─────────────────────────────────┤
│  中层：cc-design 高保真实现      │  按 DESIGN.md 令牌做视觉
│  （食谱已在 S5.1b 锚定）          │  不改令牌值，只做视觉表达
├─────────────────────────────────┤
│  底层：DESIGN.md 令牌值          │  不可覆盖
│  （色值/字号/间距/圆角/阴影）     │  唯一来源，上层不许改
└─────────────────────────────────┘
```

**冲突解决规则**：
1. 令牌值冲突 → DESIGN.md 优先，中层不许改
2. cc-design 的视觉建议与 taste 的反 slop 规则冲突 → taste 优先（安全 > 美观）
3. 多个视觉 skill 同时适用 → 只叠一个中层，在设计简报里选定

**怎么选中层 skill**：

| 场景 | 选谁 | 理由 |
|------|------|------|
| 有 Figma 设计稿要还原 | cc-design | 像素级还原 |
| 有明确风格需求（极简/brutalist/…） | **食谱已在 S5.1b 选定** | 25 个食谱在 S5.1 阶段就已锚定，S6 不再选风格 |
| 没有设计稿、没有风格偏好 | cc-design（默认） | 最通用 |
| 着重反模板化 | 叠 taste 作为唯一层 | taste 自带设计能力 |

---

## 五、S6 骨架验证门

内置 `modules/prototyping` 搭完骨架（所有场景空壳 + 导航跑通）、填内容之前，跑一遍验证：

```
骨架验证 checklist：
- [ ] 每个页面的布局能容纳所有业务状态（Empty/Loading/Error/Success/Disabled/Skeleton）
      + AI 扩展态（Generating/Partial/Fallback/Rate Limited，如适用）
- [ ] 响应式断点行为与 interaction-spec.md 一致
      宽视口/中视口/窄视口 三个截图对比 interaction-spec 的断点表
- [ ] 侧栏/顶栏/底栏的折叠/展开逻辑可工作
- [ ] 场景间导航全部可达（从任意场景能到任意其他场景，或明确单向）
```

不通过 → 回 S5.2 改 interaction-spec.md 对应页面的布局/断点 → 至少重跑 S5.3「可实现性」视角一轮。

---

## 六、S6.3 技术栈对照审查

demo 锁定前，逐项审查 demo 中的复杂交互在目标技术栈中是否可实现：

```
技术栈对照表：

| demo 中的交互 | 目标组件库 | 可实现？ | 备注 |
|---|---|---|---|
| 拖拽排序 | React DnD Kit | ✅ | — |
| 流式文字输出 | 自研 SSE 渲染 | ✅ | 需自研 |
| 3D 卡片翻转 | — | ⚠️ 需自研 | 评估 2pd |
| 手势左滑删除 | SwiftUI .swipeActions | ✅ | iOS 原生 |
```

⚠️ 标注「需自研」的交互必须附工作量评估，让产品判断是否值得保留。
⚠️ 这不是要求 demo 用目标框架写，而是确保锁定的交互方案在实现侧可行。

---

## 七、S6.4 演示版分支（按需）

**触发条件**：产品明确说「这个 demo 要给客户/投资人/领导看」。

与交接版的区别：

| 维度 | 交接版（默认） | 演示版（按需） |
|------|-------------|-------------|
| 数据 | 诚实占位 + 假数据标注 | 市场认可的样例数据（看起来真实） |
| 视觉 | 骨架为主 + 可选视觉层 | 必须叠满视觉层 |
| 文案 | 产品定义的功能文案 | 品牌层文案（市场确认） |
| 交付件 | 一份 HTML | 交接版 + 演示版 两份 HTML |
| 标注 | 占位/补齐逐条列出 | 不标注占位（看起来像成品） |

⚠️ 演示版不替代交接版——研发仍然按交接版开发（有诚实标注的那份）。
⚠️ 演示版的样例数据由市场提供或确认，不由产品/设计随手编。
