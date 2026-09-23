# Module restoration and document-quality remediation

## Scope and authority

This work continues the maintainer-approved remediation of the current public suite,
based on commit `40c5d2f`. Earlier material was selectively restored, not substituted
for the current architecture. Three discoverable Skills remain one distribution;
the modules below are internal libraries, not additional auto-triggered Skills.

The maintainer authorized changes across the affected files, including historical
cross-agent ownership boundaries. That is not a claim that another agent reviewed or
approved this patch. The historical ownership ledger remains intact; its parallel-agent
policy is not evidence of this single-maintainer assignment's approval.

## Implemented changes

| Work package | Change | Verification and boundary |
|---|---|---|
| R1 Architecture and dependencies | Restore research, diagramming, design-quality and prototyping entries; restore four platform adapters; install preflight requires the bundled modules. | Module checker including real render, three-Skill installation and source/entrypoint checks. External programs/accounts are not bundled. |
| R2 Diagrams | Restore ten templates, eight styles, editable JSON/SVG/PNG, canonical renderer and installed-compiler bridge. Bind each diagram's source, output and business IDs to its own document slot. | Invalid edges, invisible/tampered nodes, stale outputs, missing native compiler products and failed renderer fallback have negative controls. Eight rendered previews were inspected and corrected for clipping, text/arrow overlap, legends and cylinder labels. Ten template entrypoints rendered Chinese branching examples with a missing-font fallback. This does not automatically establish all project-specific diagram semantics. |
| R3 Prototypes | Restore offline single-file bundling and isolated browser assertions; preserve deferred/module scripts, reject external/escaping resources and detect delayed errors. | Real browser checks and regression fixtures; missing browser remains UNABLE. |
| R4 Documents | One platform dispatcher; official user CLI for Feishu and separate DingTalk adapter; compare ordered full text, tables, links and images under one native revision. | Body negation/omission, empty or misplaced media, changed revision, failed write and invalid receipts cannot pass. Local supplied artifacts never certify live delivery. |
| R5 GUI evidence | Protect input values/history, refuse unapproved actions and stale-coordinate fallback; reclaim only owned processes; timeout cannot become completion. | Seven crawler regressions plus browser/runtime checks. No private client traversal was performed for this patch. |
| R6 Research depth | Every atomic feature has an exact body section, rules, states, recovery, limits, event and real adjacent image. Depth follows the product, not a fixed number of levels. All three research modes are bound to their required inputs. | Versioned single-product packages, common-to-native feature maps and every comparison node × competitor must reconcile. Missing body/image/row, borrowed evidence and login-wall-as-absence have negative controls. Semantic truth still needs review. |
| R7 PRD alignment | Retain the nine-chapter PRD and existing research scope. Correct chapter/appendix pointers and require explicit evidence → decision → product requirement mapping. | Existing no-loss baseline is unchanged; each intentional rename/replacement has a specific migration reason. Rule preservation does not prove end-product quality equivalence. |
| R8 Professional and page review | Product/UX/QA review records bind all feature/section coverage to source/media hashes. Final review requires current live receipt, same-version native page screenshots through the end and a visual rationale. | Pre-review cannot close S2; missing page coverage, old native version and old receipt schema are rejected. Records cannot authenticate the reviewer or replace professional judgment. |
| R9 Engineering approval | S8/S9 approvals bind exact scope, source and frozen PRD. S9.3 requires QA GUI completion → quality report → separate PM GUI walkthrough on the same build. | Stale PRD, wrong scope/authority, absent artifacts and out-of-order/different-build evidence are rejected. Agent assessments never impersonate human authorization. |
| R10 Distribution | Retain upstream licenses; declare image-decoding dependency; update preview checklist and validate private-denylist, installation and release packaging separately from stable readiness. | Current-tree scans do not certify every historical blob. Previous public history retains two phone-like example strings; no destructive history rewrite was authorized or performed. |

## Reproducible checks

- Full gate self-tests: `python3 skills/product-flow/scripts/selftest-all.py --fresh`.
- Cross-rule consistency, original no-loss baseline and generated-document alignment.
- `python3 scripts/test-remediation-contracts.py`: 23 focused contract tests.
- `python3 scripts/test-release-regressions.py`: 32 release regressions.
- 14 diagram unit tests, 7 crawler probes, 2 evaluation-harness tests and the S2
  teaching sample (three cooperating gates plus seven destructive controls).
- `python3 scripts/verify-modules.py --render`, isolated installation and public
  packaging/privacy checks. Private denylist contents and operational logs are kept
  outside the public repository.

The teaching sample is a real screenshot of the bundled local demo, not a commercial
competitor screenshot or a live cloud-document readback. The supplied XML is a
synthetic contract fixture and is labelled as such.

## Frozen-tree acceptance (2026-09-23)

Two independent clean local clones of `be8458dc49be6536e03f8ee2105c80b6f037ef6f`
ran `bash scripts/verify-suite.sh --full` sequentially on macOS, Python 3.10.20
and Node 22.4.0. Both complete commands exited 0. Both recorded a clean input tree;
only the generated measurement snapshot changed during each run.

| Check | Clean run 1 | Clean run 2 |
|---|---|---|
| Gate self-tests | 82 scripts, 1363 cases, 0 failures | Same |
| Actual execution / cached reuse | 82 / 0 | 82 / 0 |
| Unable scripts / count disagreements | 0 / 0 | 0 / 0 |
| Cross-rule consistency / original no-loss baseline | PASS / PASS | PASS / PASS |
| Coding-standard baseline / deliberate mutations | 41 PASS; 45/45 caught, 0 unable | Same |
| Release / remediation regression tests | 32 / 23 PASS | Same |
| Real diagram rendering, prototype bundling, installation and packaging | PASS | PASS |

The self-test snapshots match in every field except the timestamp, including all
per-script hashes and counts. The committed snapshot is the second fresh run;
the earlier cached diagnostic measurement is not used as final evidence.
Any subsequent evidence-only commit preserves this measured source revision in
`headAt`; it must not be presented as a third fresh run.

The original deliberately shallow comparison/full-research sample passes the old
retained baseline but is rejected here for missing versioned single-product inputs.
The body-deleted readback, previously accepted with one remaining image, now fails
with `body-mismatch`. The four supplied-template heading mismatches are eliminated.
These are specific regression demonstrations, not a claim to have repaired a user's
live document or completed a whole-product research study.

The final review also found that the coding-standard mutation helper copied its
Skill without the suite-root license/attribution files. This contaminated four
expected-UNABLE controls with unrelated link failures. Its temporary layout now
preserves the complete relative paths and a pristine-copy check runs before each
mutation. The expected exit codes and link criteria were not relaxed.

### Narrow performance check

The unchanged optimized requirements checker was compared with locally retained
baseline `08793449b1c535c1dff699f12594c8bd9aa6130a`, using the same 60 synthetic
requirements and interpreter. Six launches per version alternated order; all exit
codes and parsed JSON outputs matched. The first launch took 218 ms / 91 ms
(baseline / candidate). The next five launches had medians 214 ms / 89 ms and
ranges 209–220 ms / 88–91 ms. Median peak RSS was 14,794,752 / 14,778,368 bytes.
No filesystem-cache eviction was performed: the first launch is not a proven
cold-cache measurement. This validates only that checker and input, not total
Skill latency, token cost, model quality or native-platform performance.

## What this does not certify

The source remains a development preview. Stable approval still requires authorized
native Feishu/DingTalk round trips, real-project research/PRD/design/GUI deliverables,
quality/performance comparison under the same brief/runtime, and closure of the
remaining forward-trial items in `RELEASE_BLOCKERS.md`. Rendering and passing unit
tests must never be advertised as those missing experiments.

For an actual research delivery, start with one fully traversed, illustrated leaf
feature and have an unfamiliar reader reproduce its rules and recovery path. Expand
only after that sample is accepted. Review all remaining leaves and the final native
document; do not infer report quality from a passing test count.
