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
