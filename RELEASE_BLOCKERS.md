# Stable-release readiness

SYBuilder is being published as an open-source **development preview** at the maintainer's
request. Source-publication requirements are tracked separately in
[PUBLICATION_CHECKLIST.md](PUBLICATION_CHECKLIST.md). This distinction does not turn
untested capabilities into passing results or permit bypassing product delivery gates.

`scripts/release-audit.py --public-preview` checks source-distribution packaging.
`--publish` remains the stricter stable-release mode and **fails while any item below
is unchecked**. No stable tag or production-readiness claim should be made yet.

## P0 — required before a stable release

- [ ] Verify the exact final stable artifact from a clean clone: clean installation, rendered-image review and two fresh full verifications. Previous successful runs are historical evidence only.
- [ ] Complete the separately authorized Git-history privacy response. Current files no longer reproduce the previously tracked user-content labels, but older public Git objects remain reachable; ordinary commits cannot remove copies, forks or cached objects. Do not claim historical erasure without a coordinated rewrite and host-side follow-up.
- [ ] Validate W5 using an explicitly authorized production project adapter, judge and baseline. Missing production evidence remains UNABLE; installation grants no model or private-project access.
- [ ] Validate native Feishu and DingTalk delivery with authorized test accounts: text, tables, real images, per-image identity/section placement, raw readback, conflict behavior and delivery receipts. Offline fixtures are not native compatibility evidence.
  - Evidence gathered 2026-09-28 (narrows, does not close): the Feishu whiteboard channel was live-tested on both a personal tenant and the Guangfan enterprise tenant via `lark-cli --as user` — inline `<whiteboard type="mermaid">` creation, styled-SVG import landing as native editable nodes (126 nodes: 52 shapes + 62 texts + 7 connectors), and verbatim mermaid source readback all passed. Text/tables/images/conflict behavior remain unverified.
- [ ] Compare representative research/PRD/design/interactive deliverables under the same brief and runtime. Rule preservation and unit tests alone do not establish quality or performance equivalence.
- [ ] Close testcases design versus execution approval, engineering-standard traceability, compound-requirement coverage and standalone run-instruction gaps; see [the forward trial](docs/forward-trial-2026-09.md). Do not weaken execution evidence to approve design-only work.
- [x] Corrected overlap/clipping in bundled diagram fixtures and regenerated all eight previews; rendered PNGs were visually inspected on 2026-09-23. Actual project diagrams still require their own semantic and visual review.

## Existing foundations (not substitutes for the open items)

- [x] Three core Skills, shared contracts and required diagramming/prototyping modules retained.
- [x] Portable W5 runner, adapter contract, six-dimension scoring and scripted positive/negative controls bundled. These are mechanism tests, not product-effect validation.
- [x] CI runs the quick verification on pushes and pull requests.
- [x] Supported-environments matrix, isolated installation test and semantic-versioning policy supplied.
- [x] Feishu and DingTalk remain separately authorized platform adapters.

## Separate legal/branding follow-up

The original rights holder approved Apache-2.0 and publication of original suite material.
Third-party terms and modifications are recorded separately. The selected project name
does not claim trademark registration or legal clearance; see [TRADEMARKS.md](TRADEMARKS.md).
Commercial branding and jurisdiction-specific advice remain separate from technical testing.
