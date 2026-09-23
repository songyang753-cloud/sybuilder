# Figma 适配器

Figma 平台与官方 MCP 不随 SYBuilder 分发。适配器定义 S7 所需输入输出、可编辑性与失败语义。

- 操作说明：`../../references/s7-figma.md`
- 可编辑性门：`../../scripts/figma-editability-gate.py`
- 输入：冻结设计契约、唯一 tokens、scene/state/element ID
- 输出：可编辑页面、组件、变量、状态画面和节点回读证据
- 不可用：返回 `UNABLE`；可交设计规格，但不得声称已交付 Figma 文件
- 边界：Figma 只负责 UI 母版；产品架构、流程和功能树由内置制图模块交付
