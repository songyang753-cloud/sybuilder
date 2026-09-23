# Public source preview checklist

This checklist governs **public source distribution**, not stable or production approval.
The maintainer requested public open-source distribution and approved Apache-2.0 for the
original suite on 2026-09-22. Do not equate publication with completion of
[the stable-release work](RELEASE_BLOCKERS.md).

- [x] PUB-1 Original-material publication authority and Apache-2.0 choice confirmed, including the original prototyping and repository-enforcement modules. Root LICENSE and NOTICE state the boundary.
- [x] PUB-2 Known bundled/adapted sources have a reviewed destination/changes manifest and retained terms. CC BY/CC BY-SA/W3C sections are identified; external platforms and unbundled research references are distinguished. Historical unknown revisions are not invented.
- [x] PUB-3 Final files and paths pass configured privacy checks plus the external private denylist. Previously visually reviewed images are byte-unchanged. Public history is newly initialized from this export, with no private source history, live account links, secrets, private denylist or working evidence; Git objects are checked before upload.
- [x] PUB-4 Exported files pass quick verification, 30 release regressions and isolated clean installation on macOS with Python 3.10.20 and Node 22.4.0. Required Skills and core modules remain present. This is not a new full-fresh or native-platform validation claim.
- [x] PUB-5 README labels the work as a development preview, records known quality/platform limits, preserves upstream attribution and makes no trademark or stable-readiness claim.

The checker verifies checklist completion, manifest structure and retained files; it
cannot establish legal rights or visually inspect images. Human/agent review records must
support the checkmarks. External private denylist and detailed operational logs stay outside
this public repository. Public commit metadata uses a project identity, not a private account
or employer address; the repository owner's public GitHub handle remains visible by design.
