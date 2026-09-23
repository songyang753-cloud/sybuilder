# 研究质量审核记录

本文件是审核工作底稿，不代替读者报告。以下字段只能在真正审阅后填写，不能由模板自动批准。
发布前运行 pre；写后逐页审阅至文末，再填写 final 页面字段。Agent 审核不是人类签字。

```json
{
  "inputs": {"report.md": "<sha256>", "evidence/SHOT-001.png": "<sha256>"},
  "reviews": [
    {"role": "product", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<完整性、颗粒度与决策价值判断>", "features": [], "sections": []},
    {"role": "ux", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<流程、状态与图文对应判断>", "features": [], "sections": []},
    {"role": "qa", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<规则、恢复和验收可验证性判断>", "features": [], "sections": []}
  ],
  "findings": [],
  "document": "<canonical document>",
  "nativeVersion": "<same-version native revision>",
  "receipt": "<current live receipt path>",
  "pageSections": [],
  "pageEvidence": [],
  "visualDecision": "UNREVIEWED",
  "visualRationale": "<逐页检查图片、比例、邻接、表格、导航及文末>"
}
```

features/sections 覆盖当前报告全部 AF 与真实标题；页面截图条目为 path/sha256/nativeVersion/sections（该截图实际显示的章节）。所有截图记录的 sections 合集必须覆盖全文，不用一张首页图代表全部页面。
每项 P0/P1 发现记录 severity/status/evidence，关闭依据必须可复查。
修改正文、图片、上传映射或远端版本后重新评审受影响部分，不修改旧评审日期伪装已批准。
