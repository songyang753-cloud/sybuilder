# Supported environments

This matrix describes intended runtime requirements, not a claim that every listed version,
operating system or optional platform has passed end-to-end testing.

| Area | Supported baseline | Notes |
|---|---|---|
| Agent hosts | Codex and Claude Code environments that discover filesystem Skills | Install all three Skill directories together |
| Operating systems | macOS 13+; Linux with Bash/Python/Node | Native macOS application walkthroughs require an authorized GUI runtime |
| Python | 3.10+ with pinned dependencies | Install `requirements.txt` into a virtual environment; YAML and Markdown parsers are core dependencies |
| Node.js | 22.4+ with native `WebSocket` and `fetch` | Required for browser and HTML verification; installer tests capabilities, not just the version string |
| Git | 2.30+ | Required for provenance, diff-based review and repository enforcement |
| Feishu/Lark | Official `lark-cli`, user or tenant identity as configured by the user | Personal Feishu operations must use user identity; SYBuilder stores no token |
| DingTalk | Official DingTalk Workspace CLI (`dws`) | Workspace permissions determine write/readback capability |
| Figma | Official Figma MCP with the user's authorized account | Native structure readback is required for frozen claims |
| Browsers | Current Chromium-family browser | Browser gates report `UNABLE` when the runtime cannot launch or attach |

## Support levels

- **Core supported**: suite structure, specs, templates, local gates and installation verification.
- **Adapter supported**: SYBuilder owns the adapter contract and tests, while the external platform owns
  authentication, API availability and account permissions.
- **Environment-dependent**: GUI automation, native application access, browser launch and proprietary
  document workspaces. These must be measured at runtime.

An `UNABLE` result is an honest capability boundary, not a pass. A local Markdown file cannot be promoted to
an approved remote deliverable without native write and readback evidence.

## Evidence available for this remediation

Local full runs passed on macOS with Python 3.14.7 / Node 26.7.0 (two fresh runs), and
Python 3.10.20 / Node 22.4.0 (one fresh run on 2026-09-22, before the follow-up transcript fix).
Each completed run reported 76 scripts, 1,337 self-test cases, zero failures, zero UNABLE,
zero cached scripts and 46 passing consistency rules. The full wrapper also passed its
installation, rendering, adapter-fixture and release-regression checks.

An earlier minimum-version attempt stopped when the disk filled; it is neither a passing run
nor evidence of runtime incompatibility. Linux CI is configured for Python 3.10 and 3.11 with
Node 22.4.0, but no remote CI completion has been observed. Local results do not certify Linux,
every later runtime version, or the exact future release archive. Follow-up source changes need
fresh verification; see the release checklist.

Only the local help/version interfaces of `lark-cli 1.0.96` and `dws v1.0.60` were checked during
this remediation. No authorized native document write/readback trial was performed. These version
observations are not compatibility certification; see `document-evidence.md` and `RELEASE_BLOCKERS.md`.
