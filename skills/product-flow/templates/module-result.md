# 模块运行结果（`--only` 七步小闭环的人类可读报告）

> 本报告解释结果，不承担机器导入。机器合同用 `templates/module-result.json`，
> 每次签发写入 `.product-flow/runs/<runId>/modules/<moduleId>/<resultId>.json`；
> 固定路径 `.product-flow/module-result.md` 不再作为可导入事实，避免后一次覆盖前一次。

| 项 | 内容 |
|---|---|
| 模块 | <S3A/S4B/S6/…> |
| runId / resultId | <PF-… / MR-…，与 JSON 合同一致> |
| 注册表 | <registryVersion + registryHash> |
| 输入与版本 | <每个输入：路径 · 版本/哈希 · 访问等级（原生/镜像/截图/链接）> |
| 假设 | ASM-xxx（缺口里可假设的） |
| 停止线 | SL-xxx（缺口里必须停止的；无则写「无」） |
| 产物 | <清单> |
| 回灌 delta | <对上游的新增/变更；用 `prd-backfill.md` 登记，无则写「无」> |
| 交接 | <给下游什么 + 未关闭依赖> |
| 门禁结果 | <逐门 PASS/FAIL/N/A/UNABLE；没跑的写 NOT-RUN，不许折叠> |
| **声明级别** | <exploration/draft/review-ready/module-approved —— 上限见 flow-tailoring 阶梯> |
| 本模块验不了什么 | <诚实边界，必填> |
| 机器合同 | <唯一 module-result.json 路径 + moduleResultHash> |
