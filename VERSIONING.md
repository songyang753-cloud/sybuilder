# Versioning policy

SYBuilder uses Semantic Versioning after the first public release.

- **Major**: changes to stage semantics, required gates, artifact contracts, exit-code meaning, or the set of
  discoverable Skills that require downstream migration.
- **Minor**: backward-compatible stages, adapters, modules, templates or gates.
- **Patch**: fixes and clarifications that do not change a consuming contract.

Machine-readable suite and workflow schema versions are independent from the repository release version.
Changing either requires a changelog entry and migration note. Gate counts and self-test counts are measured
facts, not version identifiers; they must never be used as compatibility promises.
