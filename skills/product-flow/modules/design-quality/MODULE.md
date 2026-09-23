# SYBuilder 内置设计质量模块

S5–S7 的最低完整能力由本模块自带；`impeccable`、`ui-ux-pro-max`、
`web-design-engineer` 等只作为可选增强，不得成为隐性硬依赖。

## 内置正本

- 设计编排与冲突裁决：`../../references/design-orchestration.md`
- 视觉规格：`../../references/visual-spec.md`
- 动效规格：`../../references/motion-spec.md`
- 交互规格：`../../templates/interaction-spec.md`
- 设计质量门：`../../references/design-quality-gates.md`
- 可执行门禁：`../../scripts/design-intent-gate.py`、`visual-spec-gate.py`、
  `interaction-gate.py`、`token-provenance-gate.py`、`ai-slop-gate.py`

## 适配规则

外部设计 Skill 可提供候选配色、字体、视觉锚点或额外审查，但最终只允许存在一份
`DESIGN.md` 和一份 `tokens.json`。外部 Skill 不可用时按本模块手工生成并跑相同门禁，
不因缺少可选增强而将整个阶段记为 `UNABLE`。
