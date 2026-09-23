# 浏览器与桌面 GUI 适配器

浏览器、桌面应用和操作系统不随 SYBuilder 分发。本适配器保留真实 GUI 遍历所需的安全边界。

- 浏览器共用层：`../../scripts/_browser.mjs`、`_cdp.js`
- 竞品遍历：`../../scripts/competitor-walk.mjs`、`deep-walk.cjs`
- 原型审计：`../../scripts/browser-audit.mjs`、`dead-click-gate.mjs`、`flow-walk-gate.mjs`
- Web：使用真实浏览器会话；登录、验证码和权限墙不得绕过
- macOS 应用：获得用户许可后串行启动，优先 CDP；不能使用 CDP 时才使用 GUI 自动化
- Cursor 等敏感输入：只允许合成事件或用户明确批准的方式，禁止并发抢占
- 不可用或无法完成登录：返回 `UNABLE`，不得用网页资料、DOM 摘要或旧截图冒充客户端实测
