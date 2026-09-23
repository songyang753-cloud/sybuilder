# Contributing to product-flow

Thanks for helping. This skill is unusually gated on purpose — the gates are what let many
people change it without silently breaking the hand-off guarantees. Work *with* them.

## The golden rule: change the single source, not its projection

Many facts have exactly one author (see the "single-source list" in
[references/architecture.md](references/architecture.md) §三). Editing a projection is
wasted work — the generator or a gate will overwrite or reject it.

- Structure of a stage (sections/tables/columns) → edit `spec/<stage>.json`, then
  `python3 scripts/gen-docs.py` to regenerate the doc regions.
- Diagram / appendix taxonomy → edit `spec/_taxonomy.json`, then regenerate.
- Counts (gates, scripts, cases, perspectives) → never hand-write them; they are computed
  live and reconciled against prose by dedicated gates.

## Before every change

```bash
python3 scripts/no-loss-gate.py --snapshot   # baseline, so you can prove nothing was lost
```

## After every change (delivery criteria, not optional)

```bash
python3 scripts/gen-docs.py --check          # L1 → L3 consistent
python3 scripts/consistency-gate.py          # meta-gate (claims vs. reality)
python3 scripts/no-loss-gate.py              # zero semantic units lost vs. your snapshot
python3 scripts/selftest-all.py              # if you touched any --self-test script
```

A red gate means stop, not "commit anyway." Never bundle the gate command and the commit
into one line — a red must be able to block the commit.

## Adding things (impact checklists)

The exact "how to safely add a gate / a taxonomy item / a reference / a stage" checklists
live in [references/architecture.md](references/architecture.md) §五. In brief:

- **A gate** needs a `--self-test`, an exit-semantics registration, a catalog entry, a
  stage wiring, a pairing registration, and a self-test re-measure. A meta-gate reports
  precisely which step you missed.
- **A reference** must be reachable from the routing table, or owned as cross-cutting infra
  — there is no orphan reference (a meta-rule enforces it).

## What the gates do *not* check

Green gates prove the skill is mechanically clean. They cannot tell you whether a piece of
guidance is *good*, well-written, or correctly reasoned — that needs human review. Don't
use a green run to back a judgement it can't make.

## Style

- Keep `SKILL.md` a map. Detailed prose belongs in `references/`, loaded on demand.
- Keep examples company-agnostic — use generic placeholder product names, never a real
  brand, account, personal name, or absolute local path.
- Python: PEP 8, no secrets in code. Type annotations are encouraged on new/changed
  signatures — the existing code is largely untyped, so typing is a gradual goal, not a
  merge gate.

## License

By contributing you agree your contributions are licensed under the
[Apache License 2.0](LICENSE).

Identified upstream adaptations retain their own terms. Preserve the suite-root
NOTICE, THIRD_PARTY.md, licenses/ and component licenses in every distribution.
