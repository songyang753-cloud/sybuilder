# September review remediation

This is an implementation map, not permission to publish. Public-release blockers remain authoritative.

| Review ID | Implementation | Regression or inspection entry |
|---|---|---|
| R01, N1 | Shared safe control enumeration, explicit action policy and fresh target identity | `scripts/test-crawler-regressions.cjs` |
| R02 | Real-path containment for entry, scripts, CSS and images | `scripts/test-release-regressions.py` |
| R03, R05, N5 | Shared Markdown content model; supported media syntax; native identity, order and section comparison | `scripts/test-release-regressions.py`; both delivery gates |
| R04, R08 | Current-attempt receipts; diagnostic reads never advance the accepted baseline | `scripts/test-release-regressions.py`; `doc-sync-guard.py --self-test` |
| R06, R12 | Clean threshold plus lens coverage; execution provenance rather than unequal hashes | `skills/four-node-review/SKILL.md`; production convergence remains to validate |
| R07 | Official CLI relative content path with an explicit working directory | Offline complete Feishu adapter-chain regression; native trial pending |
| R09, R13 | Capability-checked runtime preparation; actual install-root resolution | `scripts/test-install.sh`; minimum-version CI still requires a completed run |
| R10 | Applicable executable changed lines remain in the coverage denominator | `skills/product-flow/references/s9-quality-gates.md` |
| R11 | Preserve and align all nine algorithm-table columns | `scripts/test-release-regressions.py` |
| R14, N8 | Scan path names and links before opening files; remove account-shaped navigation exceptions | Privacy regressions and external-denylist scan; final public history remains blocked |
| R15 | Synthetic S2 integration samples, with exact rejection reasons | `skills/product-flow/tests/s2-golden/run-golden.py` |
| N2 | Explicit reload/capture/limit gaps; zero evidence cannot mean complete | Crawler regressions; real application trial pending |
| N3 | Page route identity, no blanket navigation exception, separate accounted and verified rates | Traversal coverage self-tests and S2 integration samples |
| N4 | Actual feature headings and resolvable event/screenshot references | Report-structure self-tests and S2 integration samples |
| N6 | Input/rule fingerprints before and after execution, checked at approval and consumption | `_module_contract.py --self-test`; workflow regressions |
| N7 | Exact role decision and explicit actor, authority, version, scope and evidence fields | Four S8/S9 fixture gates; invalid-decision and missing-field regressions |

## Deliberate boundaries

- Follow-up minimum-runtime verification and a same-brief forward trial are recorded in
  `supported-environments.md` and `forward-trial-2026-09.md`. The transcript false positive
  was fixed with a reproduce-before-fix regression; remaining semantic findings are explicit
  release blockers rather than hidden by the earlier self-test totals.
- A crawler's completion only describes its authorized, enumerated scope. It cannot prove that an
  unknown application's entire feature set has been discovered. Account permissions, hidden roles
  and private content still need a scoped research plan and human review.
- Every applicable research leaf needs explanatory text and evidence. The optional 3–5 deep dives
  are additional business analysis, not a waiver for the rest of the feature inventory.
- Approval fields validate a record's structure; they do not authenticate a person or grant an agent
  authority. Referenced authorization and actual product version must be reviewed under the project contract.
- Gate evidence includes explicit file/directory inputs and the rule tree. Dependencies hidden inside
  an input file must also be declared as gate inputs. A hash is not proof of an action being performed.
- The image delivery contract requires raw upload mappings and stable native revisions. An adapter
  cannot infer these from image counts. When its CLI cannot provide them, remote writing may produce
  a draft, but delivery approval remains UNABLE. Offline adapter tests do not resolve this platform gap.
- W5 scripted tests exercise failure handling and scoring. They do not establish real-model quality,
  performance or equivalence with the source suite.
- No source template information was intentionally removed; erroneous rules were corrected and
  the existing no-loss checks retained. Final clean-history, rights and real-task acceptance remain open.

## Record migration

Historical gate results without the input/rule evidence binding cannot approve current outputs.
Re-run the applicable checks; never backfill a new hash into an old execution record.
Document receipts use the current attempt and schema-v2 readback binding. A failed or re-registered
attempt invalidates the previous success for current delivery while retaining it as historical evidence.

The complete regression entry is `bash scripts/verify-suite.sh --full`. Freeze the file set during
measurement, inspect failure/UNABLE/skipped/cache counts separately, and repeat after the final edit.
