<!-- 复制到 .github/pull_request_template.md。标题用 Conventional Commits：type(scope): 摘要 -->

## 做了什么
<!-- 一句话概括本 PR 的单一目的 -->

## 为什么 / 影响面
<!-- 背景、动机；影响到的模块/接口/数据 -->

## 关联
<!-- 需求 / Issue / ADR（重大架构决策须附 docs/adr/ 链接） -->

## 自检清单（对齐 Definition of Done）
- [ ] 单一目的、小颗粒，便于评审与回滚
- [ ] 本地按 CI 口径跑过全部门禁（格式/静态分析/测试含竞态/类型/构建/漏洞扫描）
- [ ] 改了对外接口 → 同步更新契约（OpenAPI/schema）
- [ ] 改了 schema → expand-contract 迁移 + 可回滚 down + 必要索引
- [ ] Bug 修复带回归测试；新并发代码在竞态检测下绿
- [ ] 无密钥/PII 入库或入日志
- [ ] 重大架构/选型变更附 ADR
