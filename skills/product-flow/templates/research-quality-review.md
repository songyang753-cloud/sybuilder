# 研究质量审核记录

本文件是审核工作底稿，不代替读者报告。以下字段只能在真正审阅后填写，不能由模板自动批准。
发布前运行 pre；写后逐页审阅至文末，再填写 final 页面字段。Agent 审核不是人类签字。

```json
{
  "authorSession": "<实际写作会话>",
  "inputs": {"report.md": "<sha256>", "evidence/SHOT-001.png": "<sha256>"},
  "reviews": [
    {"role": "product", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<完整性、颗粒度与决策价值判断>", "features": [], "sections": [], "sessionId": "<独立实际会话>", "trace": {"path": "<相对审核包路径>", "sha256": "<sha256>"}, "consumption": []},
    {"role": "ux", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<流程、状态与图文对应判断>", "features": [], "sections": [], "sessionId": "<独立实际会话>", "trace": {"path": "<相对审核包路径>", "sha256": "<sha256>"}, "consumption": []},
    {"role": "qa", "actorType": "agent", "reviewer": "<reviewer>", "reviewedAt": "<timestamp>", "decision": "UNREVIEWED", "rationale": "<规则、恢复和验收可验证性判断>", "features": [], "sections": [], "sessionId": "<独立实际会话>", "trace": {"path": "<相对审核包路径>", "sha256": "<sha256>"}, "consumption": []}
  ],
  "findings": [],
  "batches": [],
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

## 逐功能消费与批次（同一个 JSON 记录中填写）

每个 reviews 元素还须加 sessionId、trace（path/sha256）与 consumption 数组；缺字段不准填空审批顶替。三个独立实际会话不能与 authorSession 相同，轨迹相对审核包目录且真实存在。每叶的产品 intent/atomicity/scope/decision、UX entry/transition/recovery/journey、测试 normal/boundary/negative/expected 各答一次。条目字段 feature/question/answer/section/quote/decision；section 是含该叶 ID 的精确标题，quote 是原句。写具体规则、流程或测试预期，不写“完整、同上、按需处理”；实际复验通过才填 PASS，角色结论才填 APPROVED。

batches 首项是样章，字段 id/kind=sample/status/units/reviewSessions；后项 kind=batch、calibratedBy 指向样章 ID。units 是 feature/section/sha256 数组，全文叶子恰好覆盖一次；reviewSessions 依序对应最终三个评审会话。首次校准记录独立归档，不事后补表声称先审后写。哈希口径见 `references/evidence-first-writing.md` §8；未审时保持 UNREVIEWED。
