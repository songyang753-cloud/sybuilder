# 文档回读 v2 与媒体映射

两平台共用 `_document_sync.py` 的正文/图片解析。Markdown 行内图、引用图、带空格尖括号
路径、`<img src>` 和 `<image path>` 都属于图片；不能因不是 `<@./...>` 就当成零图。
图必须先渲染为真实文件；原始 Mermaid 围栏在交付前被阻止。源图是受控编辑资料，不是
占位文字。平台不支持的格式需显式转换并回验，不得忽略。

`evidence-manifest.json` 原有 `evidence` 保留。逐图上传适配器另写 `delivery`：

```json
{
  "document": "actual-native-document-id",
  "nativeVersion": "actual-native-revision",
  "uploadEvidenceRef": "upload-evidence.json",
  "uploadEvidenceHash": "sha256-of-upload-evidence",
  "images": [{"evidenceId": "SHOT-001", "sourceHash": "sha256-of-source-image", "mediaId": "actual-native-image-id"}]
}
```

以上是字段说明，不是可通过的证据。images 按源稿出现顺序排列。uploadEvidenceRef 指向
真实上传适配器保存的原始证据，包含同一次上传的 sourceHash/mediaId 对及平台原始响应；
不得手猜 ID 或用数量推导身份。适配器应在上传时计算源图哈希并保存平台响应。未提供
这种能力的 CLI 批量导入可用于草稿写入，但**不得签发图文验收 PASS**，需要补用该平台
支持的逐图上传/读取接口后重验。当前两个 CLI 的实际字段需经获准账号验收，不能据此
文档宣称已经实现所有平台版本的自动映射。

本地链路同时验证：源图→清单→上传证据→原生媒体 ID→真实章节标题→同一远端 revision。
飞书支持有序 heading/title/h1–h6 + image/img XML 块；钉钉支持有序 blocks/children 原生
结构及图片 sectionTitle。未知布局是 UNABLE；不能人工把未知布局拍平后谎称原生证据。
平台重编码图片时不要求远端字节等于源图，身份由真实上传映射证明。

写入尝试采用独立 attemptId。最终正文回读、媒体回读与 receipt 必须同版本；失败后旧
receipt 仍保留审计，但不再代表最新尝试。媒体/源稿/上传证据被改过后也须重验。单独
`doc-sync-guard readback` 不能越过逐图验收；有图片时须走完整适配器链路。
手动 check 只诊断，不推进已验基线；重新 record 会令旧成功失效。

这些哈希与本地记录是防误用的对应关系，不是身份认证或防恶意伪造签名。批准记录要
说明 human/agent、授权依据、版本、范围和证据，不能将 AI 角色审查称为人类签核。
最终还要在真实 GUI 中逐图检查可打开、比例、可读性、邻接正文和文末完整性；机器通过
不等于阅读质量通过。真实平台验收前，发布阻断项保持未关闭。
