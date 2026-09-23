# Contributing to SYBuilder

1. Keep each change scoped to one Skill or one explicit cross-Skill contract.
2. Do not duplicate a rule that already has an authoritative source in another Skill; link to its anchor instead.
3. Add a positive and negative verification case for every new blocking criterion.
4. Treat an unavailable dependency or incomplete coverage as `UNABLE`, never as `PASS`.
5. Do not commit personal names, tenant URLs, document tokens, screenshots containing user data, absolute home paths, credentials, or private project aliases.
6. Run `./scripts/verify-suite.sh --quick` before every pull request and `--full` before a release.
7. Use path-scoped commits. Do not bundle unrelated formatting or cleanup.

Changes that add third-party text, code, templates, or assets must record the source URL, exact version/commit, license, and what was copied or adapted.

