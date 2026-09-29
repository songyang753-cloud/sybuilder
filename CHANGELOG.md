# Changelog

SYBuilder follows Semantic Versioning for tagged releases. Public source is currently
a development preview; changes remain **Unreleased** and no stable version is claimed.

## Unreleased

### Added

- PRD-carrier reconciliation across four sources at an 18-row denominator (authoritative table, pack template, scaffold spec, research gate), including copy, motion, AI-capability and privacy-visibility carriers.
- Flow-diagram enforcement: user-flow and business-flow slots can no longer be waived when triggered, and business-flow sources must carry branch/exception edges (main-flow-only fails).
- R&D-side stage contracts: atomic acceptance criteria, capacity-anchored performance NFRs, concurrency/offline semantics for dual-platform PRDs, eval sets as tracked dependencies, effect-regression triggers, online sampling & bad-case reflow, testcase readiness before the G7.5 freeze, engineering/algorithm/testing sign-off on the freeze record, and a PRD-stage hard-technical-constraint registry.
- Feishu editable-board delivery for architecture and flow diagrams (mermaid source inlining; styled-SVG-to-native-node import), with a seven-point layered-architecture style contract and a neutral exemplar.
- Metric-baseline provenance at the definition stage (S3A-to-S3B handoff): bare numbers fail, sources or explicit TBD/无 required.
- Three-Skill suite: `product-flow`, `coding-standards`, and `four-node-review`.
- Internal research, diagramming, design-quality, prototyping and repository-enforcement modules.
- Adaptive competitive-research granularity down to the smallest independently verifiable behavior.
- Technical, algorithm and test solution stage, followed by engineering QA and independent product GUI review.
- Feishu/Lark and DingTalk document adapters sharing one Markdown semantic source.
- Cross-Skill contracts, no-loss controls, module verification and clean-install checks.
- Offline safety, approval, document-delivery and research integration regressions.
- A portable internal W5 evaluator with six-dimension scoring, repeated runs and judge controls.
- Opt-in isolated runtime preparation before installation, without automatic account authorization.

### Changed

- Second-round cross-review (independent re-review of the first 32-finding batch) closed 21 more findings: runId/resultId injection sealed at the load_active_run boundary and both module-contract entry points (issue/import) with a shared validator; interpreter self-identification hardened with binary/shebang file-header prechecks and bare-name coverage; git rev-parse exit 128 no longer blanket-reports outside-git (locale pinned, message prefix discriminated); owned process-group cleanup is unconditional with non-ESRCH errors recorded as evidence; the metric-baseline check is a provenance whitelist (unit-suffixed and approx-sign numbers fail) with a markdown header-row state machine and column-order lock cases; the pre-commit hash guard propagates subshell exits and validates the full digest; the hook checks git's own exit code; the evidence-independence clause is an explicit per-node convergence matrix; suite-asset whitelisting for 10i ships with a directional mutation row and hash/hook behavior fixtures; walk scripts validate OUT presence and strict decimal arguments; SVG path stripping is file-level and quote-agnostic.
- Interpreter-entry hardening in the W5 evaluator: relative interpreter paths are rejected (project-root-relative venv launchers excepted, with root-escape checks), absolute interpreters must self-identify as real Python/Node, and the basename-only comparison hole is closed; judge FAIL controls now validate failDimensions as a nonempty six-dimension list, git detection uses structured rev-parse results instead of English message matching, private writes share one O_EXCL/0600/fsync helper, and process-group cleanup no longer races reaped pids.
- coding-standards: hash tooling falls back to sha256sum with fingerprint format assertions (missing tools report UNABLE, not silent PASS), the pre-commit hook uses -z raw paths with explicit awk exit triage and a truthful copy-install message, D32 gains the internal-error exit mapping and skips same-path re-runs, the 11 duplicated three-state dispatch cases collapse into one helper, script-hygiene globs cover hooks/, CI templates gain per-job timeouts, and suite-root links degrade to UNABLE instead of FAIL in single-skill distribution.
- product-flow: run-id validation is shared across plan/resume (path traversal refused), the consumer index update takes the mutation-state lock, the metric-baseline check only inspects the declared baseline column (guardrail baselines no longer false-positive, name-matching rows no longer skip), delivery-depth regressions join the PRD gate self-test, walk/sweep scripts validate numeric arguments, subprocess timeouts land with UNABLE semantics, and line-number lookups stop copying string prefixes.
- four-node-review: lens scheduling gains an explicit priority-exception clause (L9 first-half, L10-before-L1) with counting rules, the evidence-independence clause 5 is clarified as per-node with provider-absent notation, and the W5 acceptance tests ship inside the skill directory (single-repo verifiable).
- Suite-root references across skills now carry single-distribution notes; external-skill absolute paths become placeholders with UNABLE fallbacks; per-skill .gitignore files ship so runtime artifacts stay ignored in single-skill distribution.

- Collaborative-document delivery is platform-neutral: each run chooses one canonical Feishu or DingTalk node.
- Diagramming is mandatory and bundled as an internal module rather than an external Skill dependency.
- Gate results and delivery receipts now bind current inputs, rules, document revision and execution attempt.
- Research coverage separates enumerated scope, accounted items and actually verified features.
- Document verification preserves ordered text, table values and code, and requires per-image native identity and placement evidence.
- Approval records distinguish human and agent reviewers and require authority, version, scope and evidence fields.
- PRD algorithm columns, review convergence, changed-line coverage and host-root resolution were corrected without replacing the product templates.
- Preserved consistency-check transcripts no longer become product claims merely by quoting the checker; actual claims in the same file remain checked.
- Research templates use the current target product instead of a historical project's name.

### Security and release

- The candidate does not import the original private Git history; its working history still requires a final privacy audit and clean export before publication.
- Added containment checks for prototype assets, fresh-target action checks and path/symlink privacy scanning.
- Original material is Apache-2.0; retained scoped third-party notices and a pinned publication-review source manifest. Historical source revisions not reconstructable are explicitly identified.
- Public-preview packaging checks are separate from strict stable-release checks; known quality and platform gaps remain open.
- Local minimum-runtime verification passed on macOS. Linux quick CI passed for the earlier private candidate; native platform trials, production W5 evaluation and representative quality/performance comparison remain required.
- Removed a historical project alias from case labels without removing the rules or case explanations.
