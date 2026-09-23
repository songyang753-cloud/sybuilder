# SYBuilder

**English** · [中文](README.md)

**Evidence-driven product delivery skills**

**Open-source development preview** · original parts Apache-2.0 · third-party material keeps its own license.
You may download, use, modify, and redistribute it; this is not a stable release that has passed all real-platform acceptance.

SYBuilder composes three independently usable Skills into one reconcilable product-development flow:

| Skill | Owns | Does not own |
|---|---|---|
| `product-flow` | Research, PRD, design/interaction, tech/algorithm/test plans, dev slices, GUI acceptance and retro | Doesn't copy the full coding-standard or final-review rules into the flow docs |
| `coding-standards` | Implementation-phase coding constraints, honesty gates, reverse tests and pre-commit self-check; bundles `repository-enforcement/` with CI, charter, ADR, CODEOWNERS and ratchet templates | Doesn't replace product decisions or final review |
| `four-node-review` | Pre-delivery risk tiering, coverage reconciliation, adversarial falsification, QA/security/performance final review | Doesn't replace day-to-day CI, and doesn't back-write product requirements |

## Why a suite, not one giant SKILL.md

The three Skills can run as a whole, but they don't share one ever-growing rule body. They integrate through artifacts, gates and stage bindings:

```text
product-flow defines what to build, why, and with what evidence to accept it
     ↓ S8 joint plan / S9 dev slices
coding-standards constrains how it's implemented, emitting reviewable gate evidence
     ↓ an independently shippable slice
four-node-review independently falsifies and rules on whether it can ship
```

Any missing link must report `UNABLE` — never degrade to "pass by default". The suite-level contract is in
[`shared/integration-contract.md`](shared/integration-contract.md); the machine-readable manifest is
[`shared/suite-contract.json`](shared/suite-contract.json).

## Out-of-the-box capabilities

Rules and core tools for research, diagramming, prototyping and repository governance ship with SYBuilder — this does not mean every external platform and specialized evaluation is verified out of the box:

- `product-flow/modules/` bundles research, diagramming, design-quality and HTML-prototype capabilities.
- `coding-standards/repository-enforcement/` bundles repo charter, CI, ADR, CODEOWNERS and ratchet templates.
- `product-flow/adapters/` integrates Feishu (Lark), DingTalk, Figma and a real browser / desktop GUI.
- Feishu and DingTalk share one Markdown semantic source and evidence manifest, but a single run picks exactly one remote canonical.

The platforms themselves are not copied into the repo: Feishu uses the official `lark-cli`, DingTalk uses the official `dws`, Figma uses the official MCP, and the browser uses a locally authorized session. When a platform is absent, only that platform reports `UNABLE`. See [`DEPENDENCIES.md`](DEPENDENCIES.md) for the full required/optional dependencies and degrade boundaries.

## Install

Download and unzip via **Code → Download ZIP** on this repo's GitHub page (or copy the HTTPS URL and clone with Git), enter the repo directory, then pick a directory where your agent discovers Skills:

```bash
./install.sh /absolute/path/to/skills
```

The installer creates symlinks by default and refuses to overwrite existing targets. Keep the full repo to preserve cross-Skill references, shared contracts and license files. When redistributing, don't copy only the three Skill directories and drop the root `LICENSE`, `NOTICE`, `THIRD_PARTY.md`, `licenses/` and component licenses.

After installing, ask your agent: "Use product-flow, start from S1 and work out the requirements for my product." Existing projects can also call coding-standards or four-node-review on their own.

## Verify

```bash
./scripts/verify-suite.sh --quick
./scripts/verify-suite.sh --full
```

- `--quick`: structure, zero-loss, cross-Skill anchor and portability checks.
- `--full`: additionally runs `product-flow`'s full fresh self-test and `coding-standards`' mutation suite (slower).

## Runtime dependencies

Base environment: Bash, Python 3, Node.js, Git. Later stages may also need a local Chrome/Chromium, D2/Mermaid, Figma, Feishu or DingTalk. These are not "installed therefore assumed available" dependencies: every run judges by the actual result in the current environment.

`product-flow`'s Feishu delivery uses the official `lark-cli --as user`; DingTalk delivery uses the official `dws`. The repo bundles no company tenant, personal account, private document or authorization. Official entry points:
[Feishu CLI](https://www.feishu.cn/feishu-cli) ·
[DingTalk CLI](https://open.dingtalk.com/dingtalk-cli).

The support matrix is in [`docs/supported-environments.md`](docs/supported-environments.md); the version-compatibility policy is in [`VERSIONING.md`](VERSIONING.md).

## Publication status

This is an **open-source development preview**, not a stable-release promise. The three core Skills, the diagrammer, the prototyping tools, the shared contracts and the verification scripts are all retained. Publishing the source and proving it works for every platform and every real project are two different things.

Verification still open includes real Feishu/DingTalk delivery, production-project W5 evaluation, and multi-task quality/performance comparison; known semantic gaps in test-case engineering and layout issues in some example diagrams are listed too. These capabilities can't be claimed done just because unit tests pass; missing evidence is still handled as `UNABLE`.

The source-publication check is in [`PUBLICATION_CHECKLIST.md`](PUBLICATION_CHECKLIST.md); stable-release to-dos are in [`RELEASE_BLOCKERS.md`](RELEASE_BLOCKERS.md). The publication check does not auto-mark stable-release to-dos as done.

## License & attribution

The original parts are under [Apache-2.0](LICENSE). Adapted and bundled third-party material keeps its own MIT, Apache, Creative Commons or W3C terms — see [NOTICE](NOTICE) and [THIRD_PARTY.md](THIRD_PARTY.md). The OWASP-adapted sections use CC BY-SA 4.0 and can't be re-licensed as Apache-2.0 content. SYBuilder is an independent project and does not represent any referenced product or organization; see [TRADEMARKS.md](TRADEMARKS.md) for the naming note.
