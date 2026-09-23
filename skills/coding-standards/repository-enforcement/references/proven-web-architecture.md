# 已验证的 Web 应用架构蓝图（Proven Web Architecture）

一套在真实社区产品（22000+ 用户、44 后端模块、多轮总监级审计 + 100+ E2E）打磨过的
**API-First 模块化单体**架构。模式栈无关；参考实现以 **Go(Gin+GORM) + Nuxt3(Vue3 SSR)** 为例，
换成 NestJS/Spring/Django + Next/Nuxt 同样适用。新 Web 项目可直接以此为起点。

> 用法：在阶段 4（固化成熟度）把本蓝图的相关原则填进项目 `docs/ENGINEERING_STANDARDS.md`，
> 按实际栈替换参考实现。**先采用，再按需裁剪**——不要无脑全搬，但每条偏离都该有理由。

---

## 0. 总体形态：模块化单体（不是微服务）

```
┌──────────── 前端 SSR (Nuxt/Next) ────────────┐
│  pages / components ──$api──▶ 统一网络层      │
└───────────────────────┬───────────────────────┘
                        │ HTTP /api/v1 (OpenAPI 契约)
┌───────────────────────▼───────────────────────┐
│            后端 API 进程 (单体)                 │
│  ┌──────── 领域模块 internal/<domain> ───────┐ │
│  │ model · repository · service · handler   │ │
│  └───────────────┬──────────────────────────┘ │
│  横切层: auth/audit/ratelimit/sanitize/cache   │
│  解耦: event bus ──▶ queue (异步)              │
└───────┬──────────────────┬──────────┬──────────┘
        │                  │          │
   ┌────▼───┐         ┌────▼───┐  ┌───▼────┐
   │ MySQL  │         │ Redis  │  │ ES/OSS │   ← 托管中间件
   └────────┘         └────────┘  └────────┘

独立进程: worker(异步消费) · ops 一次性命令(reconcile/reindex/auditverify)
```

**为什么单体**：一个可部署单元、运维简单、事务边界清晰；模块边界清楚后可随时拆服务。
**何时拆**：单模块成为独立扩缩容/独立团队/独立发布节奏的瓶颈时——而非一开始就拆。

---

## 1. 后端领域分层（每个模块的内部结构）

每个 `internal/<domain>` 自带四层，对外只暴露 `Module()` + `RegisterRoutes()`：

| 层 | 职责 | 不该做 |
|---|---|---|
| **model** | 领域实体 + 字段约定（持久化/派生标记） | 含业务逻辑 |
| **repository** | 所有 DB I/O，SQL/ORM，事务 | 含业务规则 |
| **service** | 业务逻辑、校验、编排、事务边界 | 直接碰 HTTP |
| **handler** | HTTP 绑定/参数校验/把领域错误映射成稳定 code | 含业务逻辑 |

**铁律**：跨模块**不得直接调用对方 repository**；要协作走事件总线（§3）或显式依赖注入接口。

---

## 2. 横切关注点（cross-cutting，基础设施层）

这些是"每个模块都要用、但不属于任何单一模块"的能力，独立成包：

| 关注点 | 模式 | 参考实现 |
|---|---|---|
| **认证** | httpOnly cookie 会话 + 写请求 CSRF 双提交 | `internal/auth` |
| **授权** | 能力位(capability) + DB 实时角色（降权立即生效，不信 JWT 内嵌角色） | `RequireCap(CapXxx)` |
| **审计** | 管理操作落不可改日志，**hash 链防篡改** + 外部 WORM 锚 | `internal/audit` + `cmd/auditverify` |
| **限流** | 令牌桶/计数窗口，按 IP/用户，Lua 原子 | `internal/ratelimit` |
| **内容安全** | XSS 白名单消毒(bluemonday/DOMPurify) + 敏感词分级 | `internal/sanitize` + `moderation` |
| **缓存** | 优雅降级：未配置/挂了则直连 DB（no-op 回退） | `internal/cache` |
| **配置** | 启动期 fail-fast 校验（prod 缺密钥/弱密钥直接退出） | `internal/config` |

---

## 3. 解耦：事件总线 + 异步队列

```
service 完成主事务 ──event.Publish──▶ 事件总线
                                        │
                ┌───────────────────────┼─────────────────┐
           notify 订阅              credit 订阅         search 订阅
           (经 queue 异步)         (经 queue 异步)     (经 queue 异步)
```

- **事件总线**：模块间副作用（通知/积分/统计/索引）经 `internal/event` 发布订阅，发布方不知道订阅方。
- **异步队列**：耗时/可重试副作用经 `internal/queue`(Asynq/Sidekiq/Celery) 异步处理，**独立 worker 进程**，
  不阻塞请求路径；队列不可用时降级同步兜底。
- **订阅方 panic 不得拖垮发布方**（隔离 + 日志）。

---

## 4. 数据层治理

- **版本化迁移**，遵循 **expand–contract**：先加(向后兼容)→双写/回填→再删旧结构，**禁单步破坏性变更**；每个 up 有可回滚 down。
- **跨库可移植 SQL**：生产 MySQL / 测试内存 SQLite 同一套代码，**不用 MySQL 专有语法**（`INSERT IGNORE`→`OnConflict`，`GREATEST`→`CASE WHEN`）。
- **软删优先**（`status=-1`），保留可恢复 + 审计；硬删需理由 + 关联清理。
- **计数策略**：低基数统计**读时派生**（不维护易漂移的计数器）；高频高基数才用反范式列，且经条件更新(`WHERE ... AND old_state`)幂等 + 防负。
- **索引按查询谓词建**；列表查询默认 `Omit` 大字段（正文/隐藏内容）+ 必分页 + 杜绝 N+1（批量回填关联）。

---

## 5. 配置即数据（Config-as-Data）

运营可配项（导航/Banner/会员组/积分规则/主题/公告…）存 **key-value 白名单表**，不写死代码。

**铁律**：凡"管理员配置 → 渲染给用户"的字段，后端必须**严格强类型 schema 校验**
（`DisallowUnknownFields` + 每 key 专属 struct + URL/颜色白名单）——"来源是管理员"绝不构成免检理由
（CMS 类配置天然不可信，存储型 XSS 高发区）。新增配置 key 必须同步扩 validate。

---

## 6. 安全模型

- 认证 httpOnly cookie，前端不持久化明文凭据；写请求 CSRF 双提交。
- 授权能力位 + DB 实时角色；新增管理操作必须挂能力位，不靠前端隐藏入口。
- **服务端为权威校验闸**，前端校验仅体验；所有外部输入校验长度/格式/枚举白名单。
- 密钥只经环境/密钥管理注入，**永不入库**；CI 跑密钥扫描。
- 审计 hash 链 + WORM 外部锚（DBA 改库也无法同步改锚）。

---

## 7. 可观测性与可靠性

- 健康检查 `/health`(存活) + `/readyz`(就绪，内网) 真实反映依赖；指标 `/metrics`(Prometheus)。
- 结构化日志（slog/zap），分级，**不含密钥/PII**；禁裸 print 调试日志入主干。
- 关键路径（队列积压/错误率/时延）有指标 + 告警规则。
- **优雅降级是契约**：任一外部依赖故障不得级联拖垮主流程。

---

## 8. 发布工程

- **CI 门禁 ≠ 部署门禁**：警惕部署若 `docker build` 只编译不跑测试 → CI 绿 ≠ 上线安全。让部署前置跑测试或只部署 CI 已验证的提交。
- 发布前**数据门禁**（predeploy）：迁移加唯一约束前先查历史脏数据，非 0 即中止发布。
- 顺序：predeploy → 备份 → 迁移(expand-contract) → 滚动重启；迁移失败不带病启动。
- 备份可恢复 + 回滚（代码回退 + down 迁移）+ 同机多服务资源隔离。

---

## 9. 前端架构

- **SSR**（Nuxt/Next）：SEO 友好 + 首屏；避免 computed 内重计算/脱作用域 API。
- **网络层收口**：业务代码禁直连 fetch，统一走 `$api`（集中 baseURL/凭据/CSRF/SSR cookie 透传），lint 强制。
- 共享领域类型与后端 wire 契约对齐（属性 snake_case 是契约）；类型门禁(tsc/vue-tsc)强制。
- **XSS**：`v-html`/`dangerouslySetInnerHTML` 内容只来自后端消毒字段。
- **可信渲染白名单**：管理员可配的 URL（广告/图标）图片/链接经统一 safe-url 白名单（https 或站内绝对路径，拒协议相对 `//` 与反斜杠绕过）。
- **设计系统**：颜色/圆角/密度走 CSS 变量(设计令牌)，支持后台换肤；不硬编码视觉值。

---

## 10. API 与进程拓扑

- 对外 `/api/v1` 版本化；**契约先行**（OpenAPI），CI 校验；同版本只向后兼容，破坏性升版本。
- **进程拆分**：API 进程 + 异步 worker 进程独立扩缩容；运维/对账是独立一次性命令（reconcile 计数对账 / reindex 重建索引 / auditverify 审计链校验），不塞进 API 启动路径。

---

## 采用清单（新项目落地顺序）

1. 立 `docs/ENGINEERING_STANDARDS.md`（用 `templates/ENGINEERING_STANDARDS.md`，把本蓝图填进 §1 架构）。
2. 搭单体骨架：一个领域模块跑通 model/repo/service/handler + Module()/RegisterRoutes()。
3. 铺横切层：config(fail-fast) → auth(cap) → audit → ratelimit → sanitize → cache(降级)。
4. 接事件总线 + 队列 + 独立 worker。
5. 迁移工具(expand-contract) + 跨库可移植测试(内存 SQLite)。
6. 前端 SSR + $api 收口 + 类型门禁 + safe-url。
7. 可观测(health/readyz/metrics/日志) + 发布工程(predeploy/备份/回滚)。
8. 全程门禁见 `templates/ci-*.yml` + `references/false-green-gates.md`。
