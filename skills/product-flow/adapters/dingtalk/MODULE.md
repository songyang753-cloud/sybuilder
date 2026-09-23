# 钉钉文档适配器

本适配器通过钉钉官方 DingTalk Workspace CLI（`dws`）交付 SYBuilder 的人读文档。
它只负责平台边界，不改变 PRD、调研或测试方案的内容契约。

## 运行契约

1. 只调用官方 `dws`；结构化返回固定使用 JSON，并按真实结果判断。
2. 新建使用 `dws doc +create`，读取使用 `dws doc +fetch`，原地更新使用
   `dws doc +update --command overwrite`；不另建第二份“正本”。
3. 复用真实返回的 URL/nodeId；零命中、多候选、profile 不明或跨组织时停止，不猜。
4. 写后必须回读正文，并用 `dws doc +inspect --include-media` 验证真实图片实体。
5. `partial_success`、未知提交状态、回读不一致或媒体无法验证都不能报完成；分类为
   `FAIL` 或 `UNABLE`。
6. 用户要求重要更新与恢复点时，优先用官方 `+checkpoint-update` 工作流；未经确认不
   绕过 revision 冲突。

## SYBuilder 入口

```bash
python3 scripts/_documents.py --platform dingtalk \
  --title "<标题>" --source <报告.md> \
  --evidence-manifest <evidence-manifest.json>
```

更新已有文档加 `--document <URL或nodeId>`。本地图片必须是真实文件，并紧邻所证明的
正文；占位文字不能通过交付门。

默认不允许整篇覆盖。定位编辑按官方 CLI 当前能力执行；确需整篇重建，先经真实
回读与合并、`doc-sync-guard.py record`/`readback` 建立 PASS 基线，再经用户明确授权
增加 `--allow-overwrite`；适配器才会传官方确认参数 `--yes`，且仍检查写前漂移。
检查后仍可能发生并发编辑，当前 CLI 路径不是原子写锁；有并发作者时使用平台的
版本冲突/检查点工作流，不用此入口整篇覆盖。
原始回读保留在 `<源稿>.remote.json`，聚合结果在 `<源稿>.delivery-receipt.json`。
平台真实图片字段与逐图锚点仍需真实账号验收，离线夹具不构成平台兼容性证明。

## 不可用语义

未安装、未登录、组织未授权、profile 不唯一、目标不可访问或媒体回读不可用时报告
`UNABLE`，保留本地 Markdown 候选稿；不得改走非官方接口，也不得把候选稿声称为钉钉
原生交付。

官方入口：https://open.dingtalk.com/dingtalk-cli

正文、媒体、原生版本和回执 v2 的共用合同见套件 `docs/document-evidence.md`。
图片数量门通过只是必要条件，缺逐图上传身份/章节映射时完整交付仍是 UNABLE。
