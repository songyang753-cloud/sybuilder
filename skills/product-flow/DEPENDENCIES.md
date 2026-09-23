# Dependencies and adapters

This is one component of the **SYBuilder suite**, not a stand-alone release.
The maintained runtime contract is [suite dependencies](../../DEPENDENCIES.md) and
[supported environments](../../docs/supported-environments.md).

## Included implementation

Install all three Skills together: product-flow, coding-standards and four-node-review.
Research, diagram generation, design quality and offline HTML prototyping are internal
modules under `modules/`; platform contracts are under `adapters/`.
Missing modules are installation defects, not permission to substitute a checklist.
An individual stage may skip unrelated work, but may not claim missing required stages passed.

## Runtime

Use Python 3.10+ with the pinned root `requirements.txt` (including real image decoding).
Browser/HTML stages require Node 22.4+ and an available Chromium-family browser.
The suite is not standard-library-only. Install dependencies in the isolated suite environment;
do not downgrade credential storage or silently install browsers.

## External platforms

Choose Feishu/Lark or DingTalk per run. Personal Feishu uses official `lark-cli --as user`;
DingTalk uses official `dws`. Figma and GUI access use the user's authorized environment.
Unavailable platforms are UNABLE for their dependent claims, not for unrelated local work.
Local Markdown is the editing source or review candidate, not proof of remote delivery.
Write, read back the same version, verify body and images, then review the complete page.

Optional external research/design Skills may add methods; they do not replace included modules
or relax the output contracts. Licensed upstream names/attributions are retained; private brands,
accounts, tokens and personal paths must not be shipped.
