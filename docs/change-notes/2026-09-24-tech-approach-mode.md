# 变更说明:S2 新增 researchMode=tech-approach(技术方案调研模式)

- **动因**:2026-09 A2A 意图分发调研实跑复盘——19 次用户提醒沉淀为判据(明细见该项目 skill-improvement/00-需求史与根因)。
- **新文件(claude 名下)**:`references/s2-tech-approach-runbook.md`(模式正本)、`templates/tech-research-report.md`、`scripts/tech-research-gate.py`(--pre/--post/--self-test,自证 4 用例)。
- **本次触及的 shared 全路径(点名,合并时以本说明为准,均为只增/机械同步)**:
  `skills/product-flow/SKILL.md` · `skills/product-flow/references/design-quality-gates.md` · `skills/product-flow/references/stage-playbook.md` · `skills/product-flow/scripts/gate-run.py` · `skills/product-flow/scripts/consistency-gate.py` · `skills/product-flow/references/workflow-registry.json` · `skills/product-flow/references/path-ownership.json` · `skills/product-flow/references/no-loss-renames.md` · `skills/product-flow/references/diagram-standards.md` · `skills/product-flow/references/.selftest-measured.json` · `skills/product-flow/references/substance-over-theater.md` · `skills/product-flow/templates/diagrams/business-process.example.d2` · `skills/product-flow/templates/diagrams/functional-architecture.example.d2` · `skills/product-flow/templates/diagrams/product-architecture.example.d2` · `skills/product-flow/references/iron-rules.md`
- 明细:
  - `SKILL.md`:S2 路由行加 tech-approach 枚举与入口;「45 道门禁」→46。
  - `design-quality-gates.md`:目录加 tech-research-gate 行;计数 45→46;自证用例数 1363→1367(实测)。
  - `stage-playbook.md`:S2 行 mode 枚举+tech-approach 例外(不做 UI 遍历,不适用遍历族门禁,改过 tech-research-gate)。
  - `gate-run.py`:EXIT_SEMANTICS 登记新门;docstring 45→46。
  - `consistency-gate.py`:GATE_PAIRING_EXEMPT 登记新门(验报告实例非模板,理由在表内)。
  - `workflow-registry.json`:R-S2-RESEARCH-TECH 条目(when researchMode=tech-approach)。
  - `path-ownership.json`:三个新文件登记 claude 名下。
  - `iron-rules.md`/`substance-over-theater.md`/三个 .d2 示例:门禁计数 45→46。
  - `no-loss-renames.md`:门禁总目录改名映射直改到 46(不接龙)。
  - `diagram-standards.md`:文末新增「视觉质量与受众分层」节(只增)。
- **给 codex 的建议(不直改你名下文件)**:`s2-research.md` 「七之三」节可加一行指针→tech-approach runbook;文本见本文件末尾附录。
- 验证:verify-suite 46/46 · no-loss 零丢失 · selftest-all 83 脚本 1367 用例 · gate 自证 4/4 · coordination-gate --who claude 通过。

## 附录:建议 codex 在 s2-research.md 七之三节后加的指针
> ⭐ 调研对象是**代码实现/技术机制/行业技术方案**(为设计自家方案)时,声明 `researchMode=tech-approach`,判据正本=`s2-tech-approach-runbook.md`(三路来源纪律在该模式同样适用)。
