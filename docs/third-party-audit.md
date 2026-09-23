# Third-party publication review

Reviewed 2026-09-22. This is an engineering provenance record, not a legal clearance
opinion or a guarantee that no undiscovered claim can exist.
[THIRD_PARTY.md](../THIRD_PARTY.md) describes license boundaries;
[licenses/sources.json](../licenses/sources.json) records the inspected revisions,
destination files, adaptation scope, changes and retained notices.

## Vendored diagramming baseline

- Source: [fireworks-tech-graph v1.0.5](https://github.com/yizhiyanhua-ai/fireworks-tech-graph/tree/v1.0.5).
- Peeled commit: `14be3ad3b05389a5d603562c207eb37157637127`.
- MIT license retained verbatim; SHA-256:
  `a71a3dde0999e54206cc012fd97f358e9407e030b1110bac31aaf83834ea2c6d`.
- Of 51 local module files, 37 matched that baseline byte for byte, 13 were
  modified and one had no corresponding file. This is a source comparison,
  not a claim of functional equivalence.

| Local file in module | Original file |
|---|---|
| MODULE.md | SKILL.md |
| references/style-6-warm-editorial.md | references/style-6-claude-official.md |
| references/style-7-minimal-green.md | references/style-7-openai.md |
| assets/samples/sample-style6-warm.png | assets/samples/sample-style6-claude.png |
| assets/samples/sample-style7-minimal-green.png | assets/samples/sample-style7-openai.png |

Modified files: the three Markdown mappings above, style-6 PNG, package.json,
fixtures/system-architecture-style6.json, references/style-diagram-matrix.md,
references/svg-layout-best-practices.md, scripts/generate-diagram.sh,
scripts/generate-from-template.py, scripts/test-all-styles.sh,
scripts/validate-svg.sh and tests/test_skill_compatibility.py.
The local-only script is scripts/chrome-svg-to-png.py. Local changes integrate
module discovery, portable rendering, neutral labels and compatibility checks.
The style-7 image is unchanged upstream content, not a private screenshot.

## Adapted guidance and legal notices

The review followed the source inventories and local destination sections, including
design rules, color guidance, keyboard contracts, security categories, review
methods and engineering practices. Known adaptations retain the applicable
MIT, Apache-2.0, CC BY 3.0/4.0, CC BY-SA 4.0 or W3C terms.
The exact source and destination map is machine-readable; it is not merely a list
of popular repositories. Current upstream revisions are explicitly marked as
**publication-review snapshots**, not reconstructed historical provenance.

Two previously ambiguous aliases were investigated:

- `web-design-engineer/style-recipes` matches ConardLi/garden-skills;
  the Linear recipe's palette, typography and component guidance were compared.
  Its MIT notice is retained.
- `cc-design/references` matches ZeroZ-lab/cc-design layout, typography and
  brand-emotion references (including the four grid categories). Its README at
  the pinned revision explicitly declares MIT. No separate LICENSE or dated
  copyright statement was present; the retained notice states that limitation
  rather than substituting a different fork's license.

The original historical revision for these method sources could not be reconstructed.
No source archive, private research cache or third-party article collection is bundled.
In particular, @meodai's external reference articles are not automatically CC BY
merely because its own SKILL.md is. OWASP-derived Z2 is a separately labeled
CC BY-SA section, including local additions; it is not relicensed as Apache.

## Distribution decisions

- Original suite material, including the prototyping and repository-enforcement
  modules, has the rights holder's publication approval under Apache-2.0.
- Retain the full root notice set and component licenses with copies. Installation
  links into the whole checkout so the notices and shared contracts remain available.
- References to engineering facts, ideas, rejected proposals and optional tools
  are not claims that their implementations are vendored. Additional copying
  requires a new scoped license review.
- External platform authorization remains the user's decision; no account,
  token, logo or proprietary client is included.
- The project name is selected, not trademark-cleared. Known similar uses are
  disclosed in TRADEMARKS.md. This record must not be advertised as legal advice.
