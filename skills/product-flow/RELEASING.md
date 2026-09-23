# Releasing product-flow as open source

This skill currently lives inside a **private** monorepo. Extracting it to a public repo has
one hard rule and a short checklist.

## ⛔ Hard rule: fresh repo, do NOT carry the monorepo history

The monorepo's git history contains other private skills, brand names, accounts, and internal
work logs. **Do not** `git filter-branch` / `git subtree split` the monorepo history into the
public repo — old commits would leak private data even after the current tree is clean.

Instead, publish the **current tree only**, with fresh history:

```bash
# from a clean checkout of the current skill directory
rsync -a --delete \
  --exclude='.git' \
  --exclude='.proposals' \
  --exclude='.four-node-review' \
  --exclude='__pycache__' \
  --exclude='node_modules' \
  ./  /path/to/product-flow-public/
cd /path/to/product-flow-public
git init && git add -A && git commit -m "Initial public release"
```

## What to exclude from the public repo

| Path | Why |
|---|---|
| `.proposals/` | internal work logs — contain brand names, private paths, personal process notes |
| `.four-node-review/state.md` | a specific run's state |
| `.git` of the monorepo | private history (see hard rule) |
| `__pycache__/`, `node_modules/` | build artifacts |

`references/no-loss-baseline.json` and `references/.selftest-measured.json` are derived and
carry no private data — keep them (they let contributors run the guards immediately) or
regenerate on first commit.

Add a `.gitignore` at the public root covering `__pycache__/`, `node_modules/`, `*.pyc`,
`.DS_Store`.

## Pre-release checklist (all must pass)

```bash
# 1. Hermetic self-test — the gate suite passes with only Python 3
python3 scripts/selftest-all.py --fresh          # 0 failures (UNABLE is reported, never folded to pass)

# 2. Consistency / generation / no-loss
python3 scripts/gen-docs.py --check
python3 scripts/consistency-gate.py

# 3. Privacy scan — every category must be 0 (grep -c, NOT grep|head)
SCAN="references scripts templates tests spec SKILL.md SKILL.en.md architecture.en.md README.md CONTRIBUTING.md DEPENDENCIES.md"
X='no-loss-baseline|\.selftest-measured'
grep -rIiE '<your brands here>|<personal handles>' $SCAN | grep -vE "$X" | grep -c .   # → 0
grep -rIiE '/Users/[a-z]+/|~/<named private projects>' $SCAN | grep -vE "$X" | grep -c .  # → 0
```

The privacy scan is only as good as the pattern list — keep it broad. As of the last audit,
all four categories (brands / personal / private paths / doc-host tokens) scanned **0** across
the publishable surface.

## Decisions to make before publishing (not code — product calls)

1. **Audience.** If the contributor community is Chinese-speaking, the deep `references/` need
   no translation and gap #1 is effectively done (entry layer is already bilingual). If
   global, the 51 references are a large `help-wanted` i18n effort — publish anyway with the
   English entry layer and mark it up for grabs.
2. **Project name.** `product-flow` is generic for discovery. Candidates:
   Throughline · Seamkeeper · SpecLoom · Keystone · Provenance. (See `.proposals/oss-readiness`.)
3. **License.** Currently Apache-2.0 (`LICENSE`). Confirm, and if you want an attribution add a
   `NOTICE` file — the Apache text itself needs no name.
4. **Delivery adapters.** S8/S9 default to local Markdown; if you keep a hosted-doc adapter,
   ship it as an optional plugin, not a hard dependency (see `DEPENDENCIES.md`).

## What is already done (OSS-readiness batches, 2026-09-22/23)

- Removed a leaked account handle; made the traversal gate product-agnostic.
- Added LICENSE (Apache-2.0), README (bilingual), CONTRIBUTING, DEPENDENCIES, SKILL.en.md,
  architecture.en.md, this file.
- Anonymized the validation-project name across ~20 files (zero structural loss proven).
- Confirmed no regression vs the pre-refactor tree (stages / gates / iron rules / mechanisms
  all preserved or increased) and a clean privacy scan.
