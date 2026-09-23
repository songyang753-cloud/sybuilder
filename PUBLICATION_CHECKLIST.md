# Public source preview checklist

This checklist governs **public source distribution**, not stable or production approval.
The maintainer requested public open-source distribution and approved Apache-2.0 for the
original suite on 2026-09-22. Do not equate publication with completion of
[the stable-release work](RELEASE_BLOCKERS.md).

- [x] PUB-1 Original-material publication authority and Apache-2.0 choice confirmed, including the original prototyping and repository-enforcement modules. Root LICENSE and NOTICE state the boundary.
- [x] PUB-2 Known bundled/adapted sources have a reviewed destination/changes manifest and retained terms. CC BY/CC BY-SA/W3C sections are identified; external platforms and unbundled research references are distinguished. Historical unknown revisions are not invented.
- [x] PUB-3 Current files and paths were checked with the configured privacy rules and external private denylist. The local teaching screenshot and eight regenerated diagram previews were visually inspected; they contain synthetic example content, not private accounts. This statement covers the current source tree, not all historical Git objects: earlier public commits retain two phone-like sample strings that were removed from current files. History was not rewritten without separate approval. The private denylist and operational logs are not distributed.
- [x] PUB-4 The restored module entries, release regressions and isolated installation have been checked on macOS with Python 3.10.20 and Node 22.4.0. Final frozen-tree regression results are recorded in [the remediation review](docs/remediation-review-2026-09-23.md); this is not a claim of native-platform or production validation.
- [x] PUB-5 README labels the work as a development preview, records known quality/platform limits, preserves upstream attribution and makes no trademark or stable-readiness claim.

The checker verifies checklist completion, manifest structure and retained files; it
cannot establish legal rights or visually inspect images. Human/agent review records must
support the checkmarks. External private denylist and detailed operational logs stay outside
this public repository. Public commit metadata uses a project identity, not a private account
or employer address; the repository owner's public GitHub handle remains visible by design.
