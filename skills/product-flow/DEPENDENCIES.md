# Dependencies & Adapters

What product-flow needs to run, and what happens when a dependency is absent. The design
principle: **only a POSIX shell + Python 3 are hard requirements**; everything else is an
adapter with a documented degrade path, so a fresh clone is useful out of the box and
becomes more capable as you plug things in.

## Hard requirements

| Requirement | Used by | Notes |
|---|---|---|
| **Python 3.9+** | every gate, the generator, the meta-gate | the core is pure-Python and self-contained |
| **POSIX shell** | self-test runners, a few glue scripts | bash |

Run `python3 scripts/selftest-all.py --fresh` on a clean checkout — the Python gate suite
must pass with nothing else installed. (One gate's own self-test may report `UNABLE` in a
bare environment; `UNABLE ≠ pass` and it is reported as such.)

## Optional: Node.js (for `.mjs` gates)

Some later-stage gates are JavaScript (browser/DOM-shaped checks). Without Node they report
`UNABLE`, never a silent pass.

| Gate family | Stage | Without Node |
|---|---|---|
| `*-gate.mjs` (scenario / flow / platform-parity / dead-click / browser-audit …) | S6 HTML | `UNABLE`; do the check by hand in a real browser and record the result |

## Optional: sibling skills

product-flow *orchestrates* other Claude Code skills at specific stages. It calls them by
name; it does not vendor them. When one is not installed, that stage degrades to the
fallback below — the stage still runs, it just does more by hand.

| Skill (by name) | Stage | Purpose | Without it |
|---|---|---|---|
| `crawl-stack` | S2 | multi-engine web crawling for research | fall back to manual search + cite sources; the research gate still runs |
| `demo-html` | S6 | scaffold the interactive HTML demo | hand-write a single-file HTML demo meeting the same self-test gates |
| `ui-ux-pro-max`, `web-design-engineer`, `design-system` | S5.1 | design-system / token starting points | hand-write the `DESIGN.md` tokens |
| `impeccable` | S5.1 | design audit + AI-slop detection | manual WCAG checklist + the built-in `ai-slop-gate` |
| `chinese-font-selector` | S5.1 | CJK font pairing (only for CJK products) | not needed for non-CJK products |
| `taste-memory` | S5.1 | carry a taste profile across runs | first run has no profile — normal |
| `coding-standards` | S9.1 | the coding rules the build is held to | anchor any coding-standard doc your project already uses; the dev-slice gate reads the resolved path |
| `four-node-review` | S9.2 | the final multi-node review pipeline | run your own review checklist; the quality gate records what actually ran |
| `engineering-standards` | (non-product refactor path) | pure-tech refactors with no product surface | out of scope for this pipeline anyway |

⭐ These are references to *a class of tool*, not to any specific vendor's implementation.
Any skill (or plain checklist) that fills the same role at that stage works — the gates
check the *output contract*, not which tool produced it.

## Optional: delivery channels (pluggable adapters)

Later stages produce documents that need to live somewhere a team can read and edit. The
pipeline treats the destination as a **delivery adapter**. The default adapter is the local
filesystem (Markdown files under `.product-flow/`); a hosted-doc adapter is one option, not
a requirement.

| Adapter | Stages | Default fallback |
|---|---|---|
| Hosted collaborative docs (any team wiki / doc host with a CLI or API) | S8, S9 canonical reports | write the same Markdown locally; a human posts it. Max claim without a live round-trip: `review-ready`, never "delivered". |
| Design tool with a write API (for the visual master) | S7 | emit a fully-annotated design spec for a designer to execute by hand |

Whatever the adapter, the rule is the same: **write, then read back**, and mark the claim
down to what the round-trip actually proved. A degraded adapter must be declared in the
final report — never reported at full configuration.

## What is NOT a dependency

The pipeline is company-agnostic and carries no bundled brand, account, or private path.
Example product names in docs and fixtures are generic placeholders. If you find a real
brand, account, or absolute local path anywhere, that is a bug — please report it.
