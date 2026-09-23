---
# ⛔ 这是 DESIGN.md 的骨架。**令牌只在这里写一次** ——
#    `design/tokens.json` 由 `scripts/design-to-tokens.py` 生成，不许手写。
# 格式取 google-labs-code/design.md（脱胎自 W3C DTCG），可被 `npx @google/design.md lint` 校验。
version: alpha
name: <产品名>
description: <一句话说清这套视觉在表达什么>

colors:
  primary: "#000000"      # ← 换成真值
  surface: "#FFFFFF"
  text: "#111111"
  muted: "#666666"
  line: "#E5E5E5"
  accent: "#0000FF"
  danger: "#B3261E"

typography:
  h1:
    fontFamily: <字体族>
    fontSize: 32px
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: <字体族>
    fontSize: 15px
    lineHeight: 1.6

spacing:
  sm: 8px
  md: 16px
  lg: 24px

rounded:
  sm: 6px
  md: 10px

# ⭐ 本 SOP 在 DESIGN.md 标准之外加的一层：逐条出处。
#    三种粒度都认：整组 `colors` / 组内某项 `typography.h1` / 单条 `colors.primary`。
#    格式与判据见 scripts/token-provenance-gate.py：
#      measured:<路径>[:<行号>]  —— 该值必须真能在该文件里 grep 到
#      recipe:<食谱名>           —— 该食谱文件必须存在
#      derived:<推导规则>        —— 规则文字非空
#      ASM-###                  —— 登记为假设，必须在 PRD 附件 B 里
#    ⛔ 整体声称会掩盖逐条编造 —— 实测过 10 条色值只有 4 条有出处、
#       真的那 4 条替编的 6 条背了书。
sources:
  colors: "measured:<从哪量的>"
  typography: "measured:<从哪量的>"
  spacing: "derived:8 的倍数"
  rounded: "derived:<推导规则>"

# 可选：DESIGN.md 规范里的「刻意不做」声明（机器可读版的诚实缺口）
# omitted:
#   - <这一节为什么不做>
---

## Overview

<把这套视觉读作什么：给 <谁> 的 <什么产品>，<什么调性>。
 ⭐ 这段是后面所有决策的裁决依据，不是文案。>

## Colors

<每个颜色**干什么用**，不是它长什么样。⛔ 不要写「优雅的蓝色」，
 要写「唯一的交互驱动色，只给主 CTA / 焦点环 / 链接强调」。>

## Typography

## Layout

## Shapes

## Elevation & Depth

## Components

## Do's and Don'ts

## Responsive Behavior

## Known Gaps

> ⭐ **必需章节**（74 个真实品牌里 43 个有）。`design-to-tokens.py` 缺它即红。
> ⛔ **只写「本轮不做」不够** —— 每条要说清**为什么缺** + **怎么办**。
> 真实写法示例：
> 「表单校验样式在被检视的页面上看不到」（说清是提取方法的限制）
> 「浅色主题没写，因为营销站根本不出浅色」（说清原因）
> 「字体是专有的，**用开源替代可以**」（给出路）
> 「动效时长没提取，**建议 150–200ms ease**」（给可执行的替代）

- <缺什么 · 为什么缺 · 下游该怎么办>

## Iteration Guide

> ⭐ **必需章节**（74 个里 50 个有）。它回答 agent **最先撞上**的那个问题：
> 「我要一个这里没有的值，怎么办？」

1. 一次只动一个组件，按 `components:` 里的令牌名引用它。
2. 需要新值时先问它属于哪一组，⛔ 不要直接写字面量。
3. 改完跑 `python3 scripts/design-to-tokens.py DESIGN.md tokens.json`。
4. 新变体作为独立的组件项，不要往旧项里塞条件。
5. <把稀缺资源写明：哪个颜色/字重是稀缺的，只许用在哪几处>
