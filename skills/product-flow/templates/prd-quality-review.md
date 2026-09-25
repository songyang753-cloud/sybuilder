# PRD 独立消费与交付审核记录

复制同目录 `research-quality-review.md` 的记录结构及逐功能消费协议填写本文件；审核底稿不是另一份业务正本。不得预填批准，不同角色改名不等于独立审核。

- inputs 以 PRD 文件名绑定 SHA256，保留图片路径/哈希，增加 `@scope` 为上游批准范围 SHA256。
- features 是 6.2 清单全部 F；每个 F 有产品、UX、测试答案和批次绑定；sections 覆盖全部实际标题。
- 产品核上游范围和取舍，UX 还原状态与异常及跨功能旅程，测试反写用例引用附件 A 的 FR/AC 与 D/E/F，不代产品填未知规则。
- 记录真实 authorSession、独立 sessionId 及包内 trace.path/sha256；问题关闭、页面截图、同版 live 回执要求与共同记录相同。
- S4 设计合法 OPEN，不等于业务规则未定也能通过；S7/G7.5 回灌后重新评审本版。

发布前诊断：`prd-quality-gate.py --source PRD.md --scope definition-final.md --review prd-review.md --phase pre`。

正式验收改为 `--phase final` 经 gate-run 落证。独立 PRD 没上游先请用户确认 scope.md 再作为 --scope，不复制 PRD 自证范围。缺独立审核/真实发布/同版回读保留未完成，模拟记录不算验收。
