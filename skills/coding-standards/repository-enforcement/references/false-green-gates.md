# 假绿门禁审计清单（False-Green Gates）

"假绿" = 文档/直觉以为有这道检查，但 CI 实际不执行或执行得不可信。
逐条核对"声称 vs 实际"，把命中项按 P0/P1/P2 分级并附证据。

## P0 — 假绿（会放过真缺陷，最高优先）

| 检查 | 怎么核 | 常见假绿形态 |
|---|---|---|
| **类型检查真在跑？** | CI 里有 `tsc`/`vue-tsc`/`mypy` 步骤吗？ | ESLint 关了 `no-undef` 说"交给 TS"，但 CI 从不跑 TS → 类型错误畅通入主干 |
| **测试带竞态？** | Go：`go test` 有 `-race` 吗？有并发/锁/goroutine 吗？ | 有并发却不带 `-race`，数据竞争无人拦 |
| **测试真在 CI 跑？** | 部署/构建步骤是否= CI？ | 部署走 `docker build`(只 `go build`/`build` 不跑 test)→ CI 绿但部署路径从不验证测试；签名变更静默漏过 |
| **lint 真阻断？** | `--max-warnings 0`？还是只 warn 不 fail？ | warnings 不计入失败，长期腐烂 |

## P1 — 违反 hermetic / 供应链

| 检查 | 怎么核 | 修法 |
|---|---|---|
| **工具版本钉死？** | CI 有 `@latest`、`install X`(无版本) 吗？ | Go：`go.mod` tool 指令；Node：钉 major/锁文件；Python：lock |
| **依赖安装可复现？** | `npm install` 还是 `npm ci`？有 lockfile 且校验？ | `npm ci` / `go mod verify && tidy 无 diff` / `pip --require-hashes` |
| **供应链漏洞扫描？** | 有 `govulncheck`/`npm audit`/`pip-audit`/Dependabot 吗？ | 加扫描步骤 + Dependabot |
| **密钥扫描？** | 有 gitleaks 吗？ | 加 gitleaks job（起步咨询） |

## P2 — 缺工程惯例

- 错误处理约定落地吗（如 Go 的 `%w` 包装实际用了多少）？
- 日志统一吗（裸 `print`/`log` 散落 vs 结构化）？
- 覆盖率有信号吗？
- CODEOWNERS / PR 模板 / SECURITY / ADR / 提交约定齐吗？
- 迁移安全约定（expand-contract、可回滚 down）写了吗？

## 输出格式（给用户）

先给总判：**"门禁真实强度 = CI 放行标准，当前是 B-/A- ..."**，
再逐条列 P0/P1/P2 + 证据（具体文件:行 / CI 步骤缺失），最后给整改清单。
强调最危险的是 P0：声称的标准高于 CI 实际执行的标准。

---

## 自查：把「哪些步骤其实不阻断」一次列出来

`continue-on-error: true` 是**假绿最常见的合法外衣** —— 检查照跑、日志照有、
而 job 结论是绿的。它散落在 YAML 各处时，没有人能一眼说清「这条流水线到底有几道门是真的」。

⚠️ 下面这段不依赖任何工具链，粘进终端即可（2026-09-05 用它审出本 skill 自己模板里的 3 处问题）：

```bash
python3 - <<'PY'
import io,glob,yaml
for f in glob.glob('.github/workflows/*.yml')+glob.glob('.github/workflows/*.yaml'):
    d=yaml.safe_load(io.open(f,encoding='utf-8')) or {}
    for jn,j in (d.get('jobs') or {}).items():
        steps=j.get('steps') or []
        soft=[s.get('name') or s.get('uses') or (s.get('run','') or '')[:24]
              for s in steps if s.get('continue-on-error')]
        print(f'{f} :: {jn}  共 {len(steps)} 步；**不阻断** {len(soft)} 步 -> {soft}')
        if j.get('continue-on-error'): print(f'   ⛔ 整个 job 都不阻断')
PY
```

**读它的方式**（三问，顺序不能反）：
1. **不阻断的那几步，是不是恰好就是你以为在保护你的那几步？**
   （密钥扫描、供应链、类型检查 —— 这三样最常年挂在咨询档）
2. 每一处豁免，能不能在**章程 Open Items 里找到对应的一行**（存量 N / 到期日 / 责任人）？
   找不到的，它已经不是棘轮，是**永久豁免**（见 [`ratchet.md`](ratchet.md) 第 2 步）。
3. **一整个 job 的 `continue-on-error`** 比单步危险得多：它一次让整组门失去拦截力，
   而每一道门自己都还在正确工作、日志里也照写失败。

⭐ **顺带一条从本 skill 自己身上审出来的**（2026-09-05）：
**模板是给人抄的，而抄走的只有模板，不是这份文档。**
`ratchet.md` 要求「测基线、写进章程 Open Items」——那条要求不会跟着 YAML 一起被复制。
于是「起步咨询」在抄走的那一刻失去上下文，剩下一个**永久**豁免，
而它看起来和一道正常的门完全一样。
⇒ **给别人抄的模板，必须就地自带它所依赖的纪律**（现在 `templates/ci-node.yml` 每处豁免都带了必填清单）。
