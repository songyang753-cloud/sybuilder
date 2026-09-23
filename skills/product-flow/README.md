# product-flow

> A spec-driven, gated pipeline that turns a one-line product direction into a shippable
> product **plus** hand-off-ready engineering material — without losing information,
> fabricating facts, or faking convergence.
>
> 一条 spec 驱动、带门禁的流水线：把「一句话产品方向」做成「可上线的产品 + 可交接的
> 研发物料」，中间不丢信息、不编造事实、不假装收敛。

*(The examples below use generic placeholder products; this project is company-agnostic.)*

## What it is

product-flow is a [Claude Code](https://docs.claude.com/en/docs/claude-code) **skill**: a
ten-stage workflow (intent → research → definition → structure → PRD → design/interaction
→ freeze → engineering plan → build/verify/ship → retro) whose defining idea is that
**most defects live at the hand-offs**, not inside any single stage. So roughly half its
machinery guards the seams *between* stages:

- **One ID chain end-to-end** — `F-xx` → `FR-###`/`NFR-###` → `AC-#` → demo scene → design
  layer → test case → commit. Break any link and everything downstream is a guess.
- **Falsifiable convergence** — "I reviewed it three times" is not convergence; a
  perspective contract is.
- **Register, never fill blank** — every fact is either sourced, told, or logged as an
  assumption. There is no fourth option.
- **Self-proving gates** — a gate is not trusted until it has been shown to go *red* on a
  bad input (positive green / negative red / invalid → error). Green ≠ correct; it only
  means "no mechanical defect found." Whether the thing is *good* is a human judgement.

The full stage map, tenets, and rules: **[SKILL.en.md](SKILL.en.md)** (English, first pass) /
[SKILL.md](SKILL.md) (Chinese, authoritative). The deeper `references/` are still being
translated — help wanted.

## Architecture (read this before changing anything)

The system is deliberately layered so that "change one thing → what else moves?" has a
clear answer. See **[references/architecture.md](references/architecture.md)** — the
boundary map:

- **L0 `SKILL.md`** — the map: stage table, cross-cutting mechanisms, routing table, rules.
- **L1 single source** (machine-readable, not loaded into context) — `spec/*.json`,
  `references/workflow-registry.json`. Edit here and everything else follows.
- **L2 logical modules** — each stage owns its references / templates / gates.
- **L3 generation** — `scripts/gen-docs.py` projects L1 into docs; hand-edits in generated
  regions are rejected.
- **L4 gates** — a self-verifying gate suite plus a meta-gate (`consistency-gate.py`) and a
  no-loss guard for editing the skill itself.

Two tracks meet at one freeze gate: a **doc track** (research/PRD are final deliverables,
"anchored") and an **eng track** (spec is the source, code is a projection). The freeze
gate is the single one-way hand-off between them.

## Status

Open-source **development preview** (not a stable release). Known gaps, help wanted:

- English translation of the deeper `references/` layer (the entry layer is already bilingual).
- Decoupling the optional sibling-skill and delivery-channel dependencies fully into adapters.
- The multi-agent coordination tooling (`coordination-gate.py` + `path-ownership.json`) assumes
  the skill sits at `skills/<name>/` under the repo root; making it portable to other layouts
  is a to-do.

Contributions welcome — see below.

## Contributing

See **[CONTRIBUTING.md](CONTRIBUTING.md)**. In short: change the single source (L1), run the
generator, and let the gates check you. Every change must pass:

```bash
python3 scripts/gen-docs.py --check        # L1 → L3 consistent
python3 scripts/consistency-gate.py        # meta-gate
python3 scripts/no-loss-gate.py            # editing the skill: zero semantic units lost
python3 scripts/selftest-all.py            # touched a self-testing script: re-measure
```

## License

[Apache License 2.0](LICENSE).
