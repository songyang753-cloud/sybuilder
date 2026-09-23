# SYBuilder 内置原型模块

本模块让 S6 在没有额外 `demo-html` Skill 时仍可完成：目录版原型、零外链单文件分发、
真实浏览器断言。产品骨架的唯一正本仍在 `../../templates/proto/`，本模块不复制第二套 UI。

## 入口

- 工作流与输入适配（必读）：`WORKFLOW.md`。不能仅运行 bundle 就声明完成 S6。
- 开发骨架：`../../templates/proto/`
- 单文件打包：`node scripts/bundle.mjs <源码目录> <输出.html>`
- 浏览器断言：`node scripts/selftest.mjs <输出.html> <断言.js>`
- 示例断言：`asserts.example.js`
- 产品级门禁：继续使用 `../../scripts/dead-click-gate.mjs`、`flow-walk-gate.mjs`、
  `scenario-matrix-gate.mjs`、`browser-audit.mjs` 和 `mock-seam-gate.mjs`。

## 出场契约

1. 打包产物必须单文件、零外链，缺素材或越界读取均判失败。
2. 原型状态必须由数据和路由产生，不能把空态、错误态画成互不相干的幻灯片。
3. 自动门禁只能证伪；交付前仍须用 GUI 完整走通关键路径。
4. Chrome 缺失或无法启动记 `UNABLE`，不能把“没能测”洗成“通过”。

本模块的打包与自测脚本来自 SYBuilder 的原型实践；原创部分的发布授权已由权利人于
2026-09-22 确认，采用 Apache-2.0。第三方材料的独立条款见根目录 `NOTICE` 与 `THIRD_PARTY.md`。
