# Dependencies and adapters

SYBuilder separates **suite-owned logic** from **external platform adapters**. Installing the repository
provides the three Skills and their internal modules; it does not silently install, copy, or authorize a
third-party platform.

## Core runtime

| Dependency | Required for | Policy |
|---|---|---|
| Bash | Installer and suite orchestration | Required |
| Python 3.10+ | Gates, contracts, document adapters and tests | Required |
| PyYAML 6.0.3 | DESIGN.md front matter to tokens | Required for design generation; install `requirements.txt` into a virtual environment, not a global interpreter |
| markdown-it-py 3.0.0 / mdurl 0.1.2 | Shared document content/media parsing and independent verification | Included in core `requirements.txt`; missing parser is UNABLE, never a pass |
| Pillow 12.3.0 | Decode screenshot/diagram files and reject corrupt or header-only images | Pinned core dependency; missing decoder is UNABLE |
| Node.js 22.4+ with native WebSocket/fetch | Browser/HTML gates and selected diagram helpers | Required for web/HTML stages; feature-tested during preparation |
| Git 2.30+ | Version anchors, diffs and repository enforcement | Required for build/review stages |

## Optional platform adapters

Run `./install.sh /absolute/path/to/skills --prepare` for the three discovery links,
a separate pinned Python environment and a real diagram-render smoke test. This option
requires network/install permission for Python packages. With an approved offline wheel
directory, pip's standard `PIP_NO_INDEX=1 PIP_FIND_LINKS=...` settings can be used; an offline
distribution itself is not included or certified here. Preparation does not install Node,
Chrome, platform CLIs or accounts silently. Missing prerequisites stop preparation before
any discovery links change. Re-running without `--prepare` is idempotent for identical links;
a conflicting directory is never overwritten. Failed runtime directories remain under
`.sybuilder/` for diagnosis; an existing working environment is never upgraded in place.

| Capability | Official external runtime | SYBuilder adapter | If unavailable |
|---|---|---|---|
| Feishu/Lark documents | [`lark-cli`](https://www.feishu.cn/feishu-cli) | `skills/product-flow/adapters/lark/` | Feishu delivery is `UNABLE`; local Markdown remains a candidate only |
| DingTalk documents | [`dws`](https://open.dingtalk.com/dingtalk-cli) | `skills/product-flow/adapters/dingtalk/` | DingTalk delivery is `UNABLE`; local Markdown remains a candidate only |
| Figma | Official Figma MCP | `skills/product-flow/adapters/figma/` | Native design write/readback is `UNABLE` |
| Browser/desktop GUI | An authorized local browser or computer-use runtime | `skills/product-flow/adapters/browser/` | GUI-dependent claims are `UNABLE` |
| Diagram rendering | Bundled JSON→SVG generator and validated Cairo/rsvg/Chromium render chain; other sources require their actual D2/Mermaid compiler | `skills/product-flow/modules/diagramming/` | Missing renderer is `UNABLE`; placeholder text is forbidden |

## Document-platform contract

- One Markdown semantic source feeds both document adapters.
- Each run chooses exactly one `documentPlatform`: `feishu` or `dingtalk`.
- The selected remote node is the only canonical collaborative document for that run.
- Write success alone is insufficient: content, structure and real media entities must be read back.
- An unavailable adapter never triggers a silent fallback to the other platform.
- Credentials remain in each official runtime's credential store and are never committed to SYBuilder.

Exact commands and evidence contracts live in the adapter `MODULE.md` files. They are internal modules,
not separately discoverable Skills.
