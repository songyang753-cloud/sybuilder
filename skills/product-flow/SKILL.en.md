# product-flow · full product pipeline (ten stages)

> **First-pass English translation of the L0 map.** The Chinese `SKILL.md` remains the
> authoritative source; the deep `references/` are still being translated. This file exists
> so a non-Chinese contributor can read the map, the philosophy, and the rules. Where the
> two disagree, `SKILL.md` wins until this note is removed.

Turn a one-line product direction into a shippable product **plus** hand-off-ready
engineering material — without losing information, fabricating facts, or faking convergence.

## Core tenets (the soul of this thing — deviate and it stops working)

1. **The hand-offs are where accidents happen.** Each stage being correct on its own is not
   enough; the real cost is when the PRD says one thing and the demo does another, the demo
   and the Figma disagree, the Figma and the code disagree. So half of this pipeline's
   machinery guards the space *between* stages, not inside them.
2. **One ID chain, end to end.** `F-xx` (feature) → `FR-###`/`NFR-###` (requirement) →
   `AC-#` (acceptance) → demo scene → Figma layer → test case → commit. Break any link and
   everything downstream is a guess, and a guess cannot be accepted.
3. **Convergence must be falsifiable.** "I reviewed it three times and it feels done" is not
   convergence. The only source of the convergence criteria is the graded contract in
   `references/review-perspectives.md` (zero `[I]` findings per perspective, traceable
   afterward).
4. **Don't know it? Register it — never fill a blank.** Every fact has exactly three
   origins: someone told you / you verified it (with source + date) / you logged it as an
   assumption `ASM-###`. There is no fourth origin; the fourth is fabrication.
5. **Deliverables are for people, not for me.** The *body* of a competitive analysis / PRD /
   design / interaction spec is for people; the *appendices* are for people + the AI that
   writes the code. Technical detail goes to appendices, the body stays human. My own
   process log (gate counts, convergence trace, which round, what I got wrong) goes in
   neither — that belongs in `.proposals/` and commit messages. Source of truth:
   `spec/_audience.json`; gate: `scripts/audience-gate.py`. It only catches mechanical
   mixing, not "is this well written" — that is a human's job.
6. **A visible problem and a readable problem are different classes.** No number of document
   reviews will catch "that sentence on the screen is backwards." So the interactive demo at
   stage 6 is not optional — it is the one time the design leaves text and is checked by an
   eye.

## Triage first (read in 30 seconds; answer three questions before going further)

### Q1 — Should you use this pipeline at all?

| Your situation | Where to go |
|---|---|
| One person can rewrite it in two hours; nobody needs a hand-off / acceptance / accountability | ⛔ **Don't use this pipeline.** Iterate a prototype directly (when the cost of one version < the cost of a spec, prototype > PRD) |
| Fixing copy, fixing a bug | Just fix it |
| Pure technical refactor, no product surface | `engineering-standards` + `four-node-review` |
| **Someone has to take this over, and they are not inside your head** | ✅ Continue |

⭐ That last row is the *only* reason half of this machinery exists — the ID chain, the
two-way reconciliation, the format boundaries, the element identity, all of it is for "the
person taking over is not in your head."

### Q2 — Building from zero, or documenting a shipped product?

| | From zero | Reverse-extraction (documenting a shipped product) |
|---|---|---|
| Path | S1→S10 in order | **Every stage is done differently** — see `templates/prd-complete.md` and the reverse module in flow-tailoring |
| S6 | Build a demo | **Skip** — the real program is the demo, but you MUST lock `baseline.md` |
| Biggest trap | Assuming | ⛔ Anything the code can't tell you (e.g. algorithm-eval data) must be asked for from a person; if you can't get it, register a `TBD` — never invent it |

### Q3 — What shape of product? (decides which chapters / perspectives / gates to cut)

| Shape | Load-bearing | Cutting it is *better* |
|---|---|---|
| **Internal tool** (single operator role) | capability list · ops metrics | ⛔ don't write eight user journeys — pure overhead |
| **Consumer / multi-stakeholder B2B** | user journeys (each named protagonist) · full NFR | — |
| **Compliance / regulatory** | constraints traceable, non-negotiable | user journeys may be irrelevant |
| **Brownfield** | existing code references must be exact · old vs new journeys distinguished | — |

⛔ **Both directions are defects**: over-formalizing (eight journeys for a one-person tool)
and under-formalizing (a consumer product with zero journeys) are equally reportable.

### Then: write the answer down
Three answers + what you cut + **"what if this judgement is wrong?"** → `.product-flow/scope.md`.
⛔ A cut step and a "ran but found nothing" step look identical in the output — if you don't
record it, nobody can later tell whether it was cut or forgotten.

## When to use / not use

**Use**: a new product defined from zero and taken to launch; a major iteration that needs a
full review; the complete chain of "demo for the boss + hand-off for engineering."

**Don't**: fix copy / a bug (just fix it); pure technical refactor with no product surface
(`engineering-standards` + `four-node-review`); only a PRD and nothing after (`--only prd`);
only a demo (use `demo-html` directly).

⚠️ A serious objection to take seriously: **when build cost is low enough, prototype > PRD** —
make 20–30 versions instead of a spec. The pipeline's value premise is "someone will take it
over, someone will accept it, someone is accountable." A thing one person can rewrite in two
hours is pure overhead under ten stages.

## The ten stages (quick reference)

The architecture source of truth is `references/delivery-pipeline.md` (three-segment
professional main flow + four loops + A/B/C triple-lock + domain authority + two freezes).

| Stage | Name | Human sign-off |
|---|---|---|
| S1 | Requirement / problem clarification | user gives |
| S2 | Deep research | no |
| S3A | Business mapping | no |
| S3B | Product definition & scope | **yes** (the most expensive sign-off) |
| S4A | Product structure | no |
| S4B | PRD v0.9 baseline | **yes** (final review) |
| S5 | Experience direction & shared contract (A concept-lock) | **yes** |
| S6 | HTML executable UX baseline (∥ S7) | **yes** (B/C lock, interaction half) |
| S7 | Figma high-fidelity visual master (∥ S6) | **yes** (B/C lock, visual half) |
| G7.5 | Three-way back-fill & freeze → PRD v1.0 | **yes** (freeze) |
| S8 | Tech / algorithm / test plan | **yes** (three professionals each approve) |
| S9.1 | Development & continuous verification | no |
| S9.2 | Engineering test, audit & quality acceptance | **yes** (quality; must PASS) |
| S9.3 | PM GUI walkthrough & four-way acceptance | **yes** (product) |
| S9.4 | Canary & launch | **yes** (launch) |
| S10 | Post-launch retro | **yes** (conclusion) |

Stages have preconditions but each segment has loops; `--from S4B` resumes, `--only S6` runs
one stage. Skipping a precondition breaks the ID chain and invalidates all downstream
reconciliation.

## Cross-cutting mechanisms (M1–M11; every stage obeys them)

Full text in `references/mechanisms.md`. In brief: **M1** ID chain · **M2** three sources ·
**M3** incremental guard · **M4** reconciliation gate (+**M4b** cross-table consistency) ·
**M5** evidence independence · **M6** stop-lines · **M7** escaped-defect reflow · **M8** gate
self-proof · **M9** format boundary · **M10** structural-spec single source · **M11**
landing-detail must be executable (as a module, not prose).

## Iron rules — the compression layer (P1–P10)

Full 52 rules in `references/iron-rules.md`. If you can't remember 52, at least never break
these ten:

- **P1 Order & loops** — stages have preconditions; going back is legal but must leave a
  trace; ⛔ no silent skipping or reordering (the ID chain breaks).
- **P2 Claim = reality** — every "done / verified" must point to evidence; a capability you
  write down must actually exist.
- **P3 A rule existing ≠ a rule being enforced** — a new criterion ships with a counter-
  example; changing a criterion requires a reverse test; a gate that has never gone red is
  not trusted.
- **P4 Single source of authority** — a fact is editable in exactly one place; everywhere
  else is a reference or a generated projection.
- **P5 Silence is a defect** — truncating / skipping / exempting / cutting is often fine;
  *not saying so* is the error. "Didn't check" and "checked, found nothing" must be
  distinguishable.
- **P6 UNABLE ≠ pass** — can't-run / didn't-run / can't-check must never fold into green;
  NOT-RUN is not N/A either.
- **P7 Hand-offs are accident-prone** — cross-stage / cross-artifact must be reconciled; IDs
  and reconciliation tables pass verbatim (paraphrase drifts).
- **P8 Human sign-off can't be delegated** — Go/No-build, final review, A/B/C locks, the
  G7.5 freeze, launch, and irreversible operations.
- **P9 Numbers are always measured, anchored** — what can be reconciled mechanically isn't
  left to memory; a defect count without a timestamp isn't written.
- **P10 Red gate = stop; all-green is not an endorsement** — the gate and the commit are
  separate commands; continuing while red is dismantling your own gate. All-green only proves
  "no mechanical defect found"; whether it is *good* is a human's judgement.

## Where to read the execution contract for each stage

`SKILL.md` has a `## 各阶段执行` routing table mapping each stage to the reference to read
before running it. See `references/architecture.md` for the layer map (which single source
to edit for what) and the "how to safely add a gate / reference / stage" checklists.

## Tooling & degradation

This skill is distributable and must not hard-depend on any one machine. See
`DEPENDENCIES.md` and the suite-root pinned runtime requirements (Python 3.10+ with parsers
and image decoding; Node 22.4+ for browser/HTML stages), bundled modules and platform adapters — each with a
documented degrade path. Any degradation must be declared in the final report, never
silently downgraded while reported at full configuration.
