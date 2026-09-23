# 个人飞书适配器

平台实现不随 SYBuilder 分发；本适配器封装官方 `lark-cli --as user` 的身份预检、写入、
原地更新、Markdown/XML 回读和真实图片实体对账。

- 实现：`../../scripts/_feishu.py`
- 统一入口：`../../scripts/_documents.py --platform feishu`
- 图片与结构验真：`../../scripts/feishu-delivery-gate.py`
- 必要身份：`lark-cli whoami --as user` 返回 user / available / ready
- 不可用：返回 `UNABLE`，保留受控 Markdown 源稿；不得改用未知第三方 CLI 冒充同一通道
- 写入边界：远端存在未合并编辑时不得覆盖；所有“成功”都必须以回读为准

已有文档默认定位更新。统一入口只实现经明确授权的整篇重建：先真实回读并合并，
用 `doc-sync-guard.py record`/`readback` 建立 PASS 基线，获准后才加 `--allow-overwrite`。
入口仍会在写前校验租约，写后保留 `<源稿>.remote.*`、同步回执与
`<源稿>.delivery-receipt.json`。平台无法原子比较并写入时仍有检查后竞态，不能宣称独占锁。
图片交付必须提供证据清单；真实账号的端到端兼容性须单独验收，离线自证不等于平台实测。

官方入口：https://www.feishu.cn/feishu-cli

正文、媒体、原生版本和回执 v2 的共用合同见套件 `docs/document-evidence.md`。
图片数量门通过只是必要条件，缺逐图上传身份/章节映射时完整交付仍是 UNABLE。
