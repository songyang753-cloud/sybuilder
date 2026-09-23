#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/sybuilder-install.XXXXXX")"
trap 'rm -rf "${TMP_ROOT}"' EXIT

TARGET="${TMP_ROOT}/host with spaces/skills"
"${ROOT}/install.sh" "${TARGET}"
"${ROOT}/install.sh" "${TARGET}"  # same installation is idempotent

for name in product-flow coding-standards four-node-review; do
  test -L "${TARGET}/${name}"
  test -f "${TARGET}/${name}/SKILL.md"
done
COUNT=$(find -L "${TARGET}" -name SKILL.md -type f | wc -l | tr -d ' ')
if [ "${COUNT}" != "3" ]; then
  echo "Expected exactly 3 discoverable Skills, found ${COUNT}" >&2
  exit 1
fi

if find -L "${TARGET}/product-flow/modules" -name SKILL.md -print -quit | grep -q .; then
  echo "Internal modules must not expose nested SKILL.md files" >&2
  exit 1
fi

COLLISION="${TMP_ROOT}/collision"
mkdir -p "${COLLISION}/four-node-review"
if "${ROOT}/install.sh" "${COLLISION}" >/dev/null 2>&1; then
  echo "Installer accepted an existing target" >&2
  exit 1
fi
test ! -e "${COLLISION}/product-flow"
test ! -e "${COLLISION}/coding-standards"

echo "PASS: clean install exposes exactly three Skills; collision leaves no partial installation"
