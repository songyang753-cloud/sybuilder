# Third-party review remediation — 2026-09-24

## Scope and acceptance boundary

This change implements the approved remediation plan against the full SYBuilder suite, not an independently copied skill directory. It preserves the existing templates, required evidence, diagramming/prototyping modules, two document adapters, and PASS / FAIL / UNABLE distinctions. Work remains on main.

**This note records implementation and targeted regression evidence, not a release certificate.** Publication requires two frozen full-suite runs; stable quality claims also require an independently executed research-writing trial and live document-platform readback/visual acceptance. Synthetic adapter/CDP fixtures are never production or platform acceptance. Actual run results are recorded separately.

## Disposition of every external finding

| ID | Disposition and change | Regression / boundary |
|---|---|---|
| A01 | Fixed S2 record writer, status and consumer to use one exact required-rule set. N/A stays in the plan. | test-gate-binding: real planner/writer/consumer, stale and foreign binding rejection, real research-gate positive/negative. |
| A02 | Git checkout/revision/merge/diff failures now stop with UNABLE. Replaced unavailable private ADR checker with the actual suite release/module audits. | test-review-boundaries injects each Git failure before downstream execution. This is current package governance, **not equivalent to historical private ADR validation**. |
| A03 | Full-suite root calculation was correct; added supported-install markers and guarded test lookup. | Helper tests reject a split copy; no duplicated test implementation. |
| A04 | Private target-bound recovery journal with content hashes, no-follow/single-link checks, explicit conflict refusal. | Wrong target/hash, symlink and later user edit cannot overwrite a file. Hard-kill recovery tested. |
| A05 | Capture uses an owned temporary profile and ephemeral loopback endpoint, bounded waits and cleanup. | Offline transport regressions; real Electron capture remains a separate acceptance boundary. |
| A06 | Shared outbound privacy scan now checks source, manifest and declared evidence dependencies, including decoded nested JSON and an external private denylist. | Both platform adapters are blocked before API creation on seeded leakage. |
| A07 | Image review binds exact scope, evidence ID, image/event hashes, date and destination. | Wrong binding and changed bytes rejected. Local metadata is **not authenticated human identity** or automatic visual privacy certification. |
| A08 | Browser transport validates its endpoint/page, bounds requests, rejects disconnects and removes its temporary profile. | Browser self-test plus simulated startup/foreign endpoint/timeout/disconnect/exception/signal regressions. |
| A09 | Both mutation tools share tree and canonical-target locks. | Actual reverse-test and mutation-sweep copies in different synthetic checkouts serialize on the same external target; sweep observes the restored original. Noncooperating editors can still race; no universal filesystem transaction claim. |
| A10 | Serial sweep forwards reviewed actions, validates names and retains incomplete-coverage semantics. | No default approval of send/purchase/delete; bounded navigation is not full product coverage. |
| A11 | Root dependencies are present in the full suite; no capability removed. | Supported installer remains the contract; arbitrary isolated directory copies are not supported. |
| A12 | Active diagram instructions now resolve to the bundled module. | Original licensed/source attribution remains; no external diagram skill requirement added. |
| A13 | M3/M6 naming aligned; M9 points to and explains existing format boundaries. | No newly invented mechanism or weakened requirement. |
| A14 | Obsolete literal gate count removed in favor of the registry's count semantics. | Registry consistency check remains authoritative; measured counts must come from a fresh run. |
| A15 | Rejected as a current defect: cited ignore files absent and tracked-file Git semantics were misstated. | Do not change ignore policy to fabricate a fix. |
| A16 | English/build instructions use coding-standards and bundled prototyping. | Historical source references remain distinguishable from current commands. |
| A17 | Secret scanner no longer prints secret prefixes/source text; research scanner does not print phone suffixes. | Seeded scans check diagnostics without exposing the seeded values. |
| A18 | Converge/audience subprocess deadlines added. No process-name/profile heuristic kills. | Cleanup is restricted to owned child groups; detached external services are outside the claim. |
| A19 | Existing unused classify helper acknowledged as low-priority maintenance debt. | Left untouched; not a runtime blocker and no unrelated refactor. |
| A20 | Rejected: diagram tests were already in unified verification. | Existing tests retained, not duplicated or removed. |
| A21 | Cited historical object not present in this repository. | No claim that all history is clean; no unauthorized history rewrite or force-push. |
| A22 | Sweep rejects invalid/duplicate names and escaping policies before output. | Traversal probes include absolute paths, parent traversal and duplicate names. |
| B01 | Explicit type validation and uniform UNABLE reason/errorCode/exit 3 for invalid or incomplete execution. | Illegal configuration/stdout types now produce bounded diagnostic evidence. |
| B02 | Missing timeout uses 120s; explicit null/bool/string/nonpositive/nonfinite values rejected. | No silent timeout disabling. |
| B03 | Registered direct entry or explicit supported Python/Node invocation required. | Shell/-c/-m/tail-argument bypasses rejected; legal interpreters preserved. |
| B04 | References must be relative files resolving inside the configuration directory. | Absolute, parent and symlink escape rejected before adapter calls. |
| B05 | Owned POSIX process groups terminated on timeout/error/interruption, direct child reaped. | Synthetic process-tree tests only; unrelated long-lived services never swept. |
| B06 | Default calibration remains strict. Optional reviewed six-dimensional scoreBounds permit graded known controls. | Correct control safety stays perfect; product regression/jitter/safety thresholds unchanged. |
| B07 | Legacy host/name/Obsidian references aligned; bundled dependency retained. | agent-evaluation is the suite executor; external tools remain explicitly named dependencies. |
| B08 | All six W5 dimensions are required for formal PASS. | SKIPPED can describe partial diagnostics but yields overall UNABLE. |
| B09 | Duplicate laws use one normative statement plus cross-reference/historical case. | Additional incremental handoff meaning retained. |
| B10 | Rejected as inapplicable: cited skill-level ignore file absent. | No fictitious configuration change. |
| B11 | Existing W5 tests retained and boundary coverage expanded. | Types, escapes, commands, controls, budgets, permissions, overwrite and process cleanup. |
| B12 | Validation/configuration/owned invocation extracted for the actual fixes. | No unrelated style rewrite. |
| B13 | Evidence directory 0700, result 0600, complete exclusive publication; ignore guidance added. | Existing output is never overwritten; ignore does not retract previously tracked evidence. |
| B14 | OCR install guidance pinned to inspected 1.12.5 and records registry integrity/provenance. | Availability/version check is not a claim that full OCR/remote model review ran. |
| B15 | Planned call count includes controls plus cases × repeats × 2, with explicit call and wall-clock budgets. | Oversized repeats rejected through the total budget; no silent truncation or budget increase. |

## Additional confirmed defects carried forward

- Comparison coverage uses the complete native feature-leaf inventory, including rows after blank lines. A leaf cannot disappear simply because it is absent from mapping. Tests delete one mapping, require rejection, then restore it and require acceptance.
- Technical research is a first-class planner mode. Its output templates are registered; required plan/quality/delivery gates remain. It does not pretend to have GUI traversal evidence.
- Real image decoding replaces file-signature acceptance. Formal technical post-check compares full text and image placement/version through either document adapter, not just keywords.
- S8 design-only coverage explicitly reports product execution NOT_VERIFIED. S9 cannot use that flag to claim executed tests.
- Current PRD chapter and diagram/prototype instructions are aligned. Historical examples are labeled as obsolete instead of silently deleted.
- Capture no longer auto-accepts policy/onboarding dialogs or removes overlays. Real screenshots must preserve the observed UI.
- Recovery review additionally found that reverse-test could treat timeout exit 124 as a killed mutation. Timeout now means UNABLE; its owned child group exits before restoration, including SIGTERM.
- The outbound scan includes the evidence manifest itself, not just its referenced files. A nested private metadata seed blocks both adapters before API creation.

## Migration and operational notes

1. Rerun invalid/stale S2 gate records. Do not edit old ruleIds to impersonate a fresh verification.
2. Reapprove evidence against the actual destination and current image/event bytes. Do not fill approval metadata merely to satisfy the gate.
3. Legacy recovery journals require manual inspection; never auto-import an unbound target. Recovery refuses later user edits and retains the journal.
4. W5 null timeouts and escaping references previously accepted by accident now fail closed. Move declared inputs inside the configuration root and review the explicit argv/budget before executing.
5. Formal W5 keeps all six dimensions and production safety. Scripted verification cannot issue production PASS.
6. Runtime export checks cover **declared export dependencies**, not a recursive search through every file on the machine. Screenshots still need actual visual review. Local approval records cannot prove reviewer identity.
7. Signal cleanup covers normally inherited POSIX process groups. SIGKILL cannot execute finally; mutation journals enable later recovery. Deliberately detached services need their own ownership/recovery contract.
8. Technical research remote checks are tested with synthetic Feishu/DingTalk fixtures. No live platform document was created or asserted verified in this remediation.

## Shared-path change explanation

The user explicitly approved a cross-suite implementation plan. The following shared paths are changed for that plan, not by pretending another contributor approved them. Existing Claude ownership is retained; narrowly listed paths are also shared for this implementation. Newly owned inventory items are removed from the unregistered ratchet rather than increasing/resetting the baseline.

- skills/four-node-review/SKILL.md — W5, dependencies, evidence handling, duplicate normative wording.
- skills/four-node-review/agent-evaluation/MODULE.md — executable contract and calibration/budget/permission semantics.
- skills/four-node-review/agent-evaluation/run.py — enforce that contract with fail-closed validation and owned execution.
- scripts/verify-suite.sh — wire targeted regressions into normal acceptance.
- scripts/test-remediation-contracts.py — preserve previous repair coverage and native feature-leaf denominator.
- scripts/test-release-regressions.py — migrate the existing offline image-upload fixture to explicit synthetic, destination/hash-bound review metadata; real preflight remains strict.
- skills/product-flow/SKILL.md and skills/product-flow/SKILL.en.md — naming/mechanism/current-stage consistency.
- skills/product-flow/references/design-orchestration.md, skills/product-flow/references/design-quality-gates.md, skills/product-flow/references/diagram-standards.md — use bundled capabilities.
- skills/product-flow/references/no-loss-renames.md — exact documented migrations; original no-loss baseline unchanged.
- skills/product-flow/references/path-ownership.json and skills/product-flow/references/ownership-inventory-baseline.json — explicit authorized scope, no broad ownership takeover or ratchet reset.
- skills/product-flow/references/prd-structure.md, skills/product-flow/references/s3-s4-product.md, skills/product-flow/references/s5-s6-design.md, skills/product-flow/references/s7-s9-build.md, skills/product-flow/references/stage-playbook.md — current chapter/route references.
- skills/product-flow/references/s2-tech-approach-runbook.md — planner mode and pre/post acceptance contract.
- skills/product-flow/scripts/_browser.mjs — owned ephemeral browser transport and deadlines.
- skills/product-flow/scripts/_feishu.py — common preflight and bounded audience process.
- skills/product-flow/scripts/competitor-sweep.mjs — validated policy forwarding and serial execution.
- skills/product-flow/scripts/consistency-gate.py — include research-mode output templates in the two-way inventory.
- skills/product-flow/scripts/converge.py — bounded invocation and UNABLE handling.
- skills/product-flow/scripts/coordination-gate.py — stop on Git failure; replace unavailable private governance entry with current suite checks.
- skills/product-flow/scripts/gate-run.py — exact required bindings; formal technical post-check; S9 rejects design-only execution claims.
- skills/product-flow/scripts/scaffold.py — current PRD chapter and bundled diagram routing.
- skills/product-flow/scripts/sec-scan.py — no secret prefix or source echo.
- skills/product-flow/scripts/tech-research-gate.py — real images, heading compatibility, full-body/platform media verification.
- skills/product-flow/templates/prd-complete.md — retain historical content, explicitly retire obsolete routing instructions.
- skills/product-flow/references/.selftest-measured.json — may only be regenerated by fresh tests; never hand-edit totals to pass a gate.

## Remaining acceptance work

The exact targeted-test results and any blockers are recorded privately alongside the implementation checkpoint. This note must not be cited as two completed full runs, an independent research-writing trial, visual platform review, or a historical privacy certificate. Final publication requires those applicable checks and an explicit honest record of unavailable external checks.
