# Releasing product-flow within SYBuilder

Publish **one suite from the repository root**, including all three Skills and shared modules.
Do not export this subdirectory alone: that drops shared contracts and third-party notices.

Use the root [publication checklist](../../PUBLICATION_CHECKLIST.md),
[release blockers](../../RELEASE_BLOCKERS.md), [supported environments](../../docs/supported-environments.md)
and [contributing guide](../../CONTRIBUTING.md). Current-file privacy checks do not erase history.

## Required checks

From a clean, frozen root checkout:

```bash
bash scripts/verify-suite.sh --full
python3 scripts/release-audit.py --public-preview .
```

Run fresh verification twice without editing between runs. Also test a newly unpacked release
archive and its installation. Confirm observed GitHub CI results; a local pass does not certify CI.
Do not omit directories, tests or licenses to make checks green.

The complete distribution must include root LICENSE, NOTICE, THIRD_PARTY.md, licenses/,
and component licenses. Original work uses Apache-2.0; identified upstream adaptations retain
their applicable terms. Preserve copyright holders and license notices.

## Publication boundary

A development preview is not a stable release. Native platform trials, GUI walkthroughs and
final-page review require authorized targets and real evidence. Missing trials remain explicitly
UNABLE/unverified, never converted to PASS by synthetic fixtures.

Never import private monorepo history. Do not rewrite public history, force-push, delete a remote,
or remove existing user data without explicit authorization. Audit the current tree, archive and
history separately before publication; keep private deny lists outside the repository.
