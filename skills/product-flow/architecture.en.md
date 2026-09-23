# product-flow architecture & co-creation guide (the decoupling map)

> **First-pass English translation of `references/architecture.md`.** The Chinese file is
> authoritative until the deeper references are translated.
>
> This file answers one question: **change one thing — what else does it touch?** And the
> reverse: **to add a stage / gate / reference, which few places should I touch?** If you
> find that changing one thing ripples into a pile of seemingly unrelated files, you've hit a
> "single source" or "module boundary" marked here — come back and check against this map.

## 1. Four layers (authority lives only in L1; everything a human reads is either judgement prose or a projection of L1)

| Layer | What | Who reads it | Blast radius of changing it |
|---|---|---|---|
| **L0 `SKILL.md`** | The map: ten-stage table + cross-cutting mechanisms + the `## 各阶段执行` routing table (each stage → which reference to read) + iron rules | loaded every time | holds only skeleton + pointers; detail is externalized on demand |
| **L1 single source** (machine-readable, NOT loaded into model context) | `spec/<stage>.json` (structure spec) · `spec/_taxonomy.json` (diagram/appendix taxonomy) · `references/workflow-registry.json` (module dependency DAG / artifacts / gate plan) · `spec/_audience.json` | scripts | ⭐ change here = change the source; everything else follows |
| **L1.5 cross-cutting shared references** | `diagram-standards` · `craft-layer` · `iron-rules` · `evidence-levels` · `review-perspectives`, etc. — referenced by many stages | many modules | changing one ripples to all referrers — **grep who references it before touching** |
| **L2 modules** (logical, not physical) | each stage (S1…S10) = one routing-table row + the references / templates / gates it owns. ⛔ `references/` stays flat, no per-stage folders — references are inherently cross-cutting (e.g. `visual-spec.md` is referenced by a dozen files); forcing them into one stage folder creates false ownership + breaks relative paths | loaded per stage when running it | module boundary = the dependency DAG (below) |
| **L3 generation `gen-docs.py`** | projects L1's spec/taxonomy into the `<!-- SPEC:BEGIN -->` / `<!-- TAXONOMY:BEGIN -->` regions of reference docs | — | editing a generated region is void (`--check` fails it); change L1 first, then run the generator |
| **L4 gates (drift-catcher)** | `consistency-gate` (meta-gate) + per-stage gates + `no-loss-gate` (when editing the skill itself) | hand-off / maintenance | see the gate catalog `design-quality-gates.md` |

## 2. Module dependency DAG (changing an upstream necessarily touches downstream, not vice versa)

```
S1 → S2 → S3A → S3B → S4A → S4B → S5 →(S6 ∥ S7)→ G7.5 → S8 → S9.1 → S9.2 → S9.3 → S9.4 → S10
```

Source of truth = `workflow-registry.json`'s `modules.<stage>.dependencies`. **Changing a
stage's artifact contract only requires regressing it + the stages that directly depend on
it** (e.g. changing the S4B PRD structure → affects S5/S6/S7/G7.5, not S2/S3). TESTCASES and
REVERSE are independent entry points (deps=[]).

## 2b. Dual track & artifact temperature (make "document form / engineering form" explicit)

⭐ **The stages are not one homogeneous line — they are two tracks of different nature,
seamed by one freeze gate.** Each module declares `track` and `temperature` in
`workflow-registry.json`; the `track-temperature-declared` gate enforces it.

| Track | Stages | Temperature | Discipline (differs by track) |
|---|---|---|---|
| **doc** | S1 intent · S2 competitive research · S3A/S3B definition · S4A/S4B PRD · S10 retro · REVERSE | **anchored** | the deliverable IS the final product; kept, not a disposable projection; table structure is a contract, no columns dropped; changes go through delta+archive; the swap test (still holds with a different brand = no information) |
| **design** | S5 experience strategy · S6 HTML · S7 Figma | **anchored** | designs / tokens / interaction specs are the source; A/B/C triple-lock converges; the review target is a rendered direction slice, not a token table |
| **eng** | S8 tech/algo/test plan · S9.1–S9.4 build/verify/ship · TESTCASES | **source** (spec is the source, code is a projection) | spec changes = regenerate/align code; S9 uses `/converge` (read the real code against the frozen PRD, find gaps; "a declaration is not evidence"); tests are first-class |
| **seam** | **G7.5 three-way freeze** | **gate** | the doc-track source is locked → the one-way decision gate the eng-track builds on; after freeze, doc-track changes must return to G7.5 for re-approval |

**Why make the tracks explicit** (the disease it treats):
- ⛔ Don't treat the **doc track** as a "disposable projection" — competitive research / PRD
  are final deliverables, not an intermediate to be regenerated.
- ⛔ Don't treat the **eng track** as "written = done" — code must re-check against the spec
  (`/converge`); a declaration is not evidence.
- ⭐ The two meet at **G7.5**: the single one-way door where "document source" hands off to
  "code implementation" (maps to spec-kit's discovery→delivery decide gate).

## 3. Single-source list (⛔ every fact has one author; everywhere else is a projection or a pointer)

| Fact | Sole source | How to get it elsewhere | Gate that guards it |
|---|---|---|---|
| gate count / script count / case count / perspective count / NFR-class count / stage count | computed live (`_roster` / git-tracked / `.selftest-measured.json` / `review-perspectives` / `single-source`) | ⛔ don't hand-write drift-prone numbers in prose | gate-count · script-count · perspective-count · selftest-count-measured · single-source |
| eight diagram classes / appendix A–R taxonomy | `spec/_taxonomy.json` | prd-structure table generated by gen-docs | spec-doc-in-sync |
| each stage's structure skeleton (sections/tables/columns) | `spec/<stage>.json` | reference SPEC regions generated by gen-docs; scaffold makes skeletons | spec-doc-in-sync · spec-check |
| gate roster | `scripts/_roster.py` | all consumers go through it | gate-roster-single-source |
| heading/paragraph parsing | `scripts/_section.py` | other scripts delegate to it | section-parser-single-source |
| gate exit-code semantics | `gate-run.py`'s `EXIT_SEMANTICS` | — | exit-semantics-declared · gate-registered |
| module dependencies / artifacts / gate plan | `workflow-registry.json` | — | — |

## 4. Progressive disclosure (SKILL is only the map; the detailed version loads on demand)

`SKILL.md` does not hold the detailed body — externalized: `references/stage-playbook.md`
(the one-page operating procedure detail table) · `references/tool-mapping.md` (tool mapping &
degradation) · iron-rules / mechanisms / PRD structure / S7 bodies each have a `(body moved
out)` pointer.

## 5. How to safely add an X (change-surface checklists)

- **Add a gate**: ① `scripts/<name>-gate.py` (with `--self-test` + `_main_guarded` fallback +
  a ⚠️ boundary sentence on both green and red) ② register in `gate-run.py` EXIT_SEMANTICS ③
  add a row to `design-quality-gates.md` ④ wire the name onto its stage in
  `SKILL.md`/`stage-playbook.md` ⑤ register in `consistency-gate.py`'s GATE_TEMPLATE_PAIRS or
  GATE_PAIRING_EXEMPT ⑥ run `selftest-all.py` to re-measure → sync the case count. ⭐ Miss a
  step and a meta-gate reports exactly which.
- **Add a taxonomy item (diagram/appendix class)**: edit `spec/_taxonomy.json` → run
  `gen-docs.py` → git diff to confirm only markers were added.
- **Add a reference**: create `references/X.md` → wire an entry into the `SKILL.md` routing
  table (else `reference-reachable` goes red). ⭐ If it belongs to no single stage
  (cross-cutting infra), register ownership + reason in `consistency-gate.py`'s
  `MODULE_INFRA_REFS` — the `module-ownership` gate enforces: no orphan reference.
- **Add a stage**: add a node + dependencies in `workflow-registry.json`; wire it into the
  ten-stage table + stage-playbook + the per-stage routing table.

## 6. Run after every change (delivery criteria, not optional)

```
python3 scripts/gen-docs.py --check      # L1 → L3 consistent
python3 scripts/consistency-gate.py      # meta-gate
python3 scripts/no-loss-gate.py          # editing the skill itself: zero semantic units lost
python3 scripts/selftest-all.py          # touched any --self-test script: re-measure case count
```
⛔ All-green gates only prove the skill is **mechanically clean** — they cannot prove the
material is **good**. That needs judgement (see `substance-over-theater.md`).
