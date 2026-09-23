#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [[ "$1" != /* ]] || [[ "${2:-}" != "" && "${2}" != --prepare ]]; then
  echo "Usage: ./install.sh /absolute/path/to/skills [--prepare]" >&2
  exit 2
fi

TARGET="$1"
for module in research diagramming design-quality prototyping; do
  test -f "${ROOT}/skills/product-flow/modules/${module}/MODULE.md" || {
    echo "Incomplete suite: missing internal module ${module}" >&2; exit 1;
  }
done
for adapter in lark dingtalk figma browser; do
  test -f "${ROOT}/skills/product-flow/adapters/${adapter}/MODULE.md" || {
    echo "Incomplete suite: missing adapter ${adapter}" >&2; exit 1;
  }
done
for required in LICENSE NOTICE THIRD_PARTY.md shared/module-registry.json skills/product-flow/modules/diagramming/LICENSE skills/product-flow/scripts/_documents.py skills/product-flow/modules/prototyping/scripts/bundle.mjs; do
  test -f "${ROOT}/${required}" || { echo "Incomplete suite: ${required}" >&2; exit 1; }
done
mkdir -p "${TARGET}"

for name in product-flow coding-standards four-node-review; do
  dst="${TARGET}/${name}"
  if [ -e "${dst}" ] || [ -L "${dst}" ]; then
    if [ ! -L "${dst}" ] || [ "$(readlink "${dst}")" != "${ROOT}/skills/${name}" ]; then
      echo "Refusing to overwrite existing target: ${dst}" >&2
      exit 1
    fi
  fi
  test -f "${ROOT}/skills/${name}/SKILL.md"
done

if [ "${2:-}" = --prepare ]; then
  # Explicit opt-in: installs only pinned Python dependencies in a private venv.
  bash "${ROOT}/scripts/prepare-runtime.sh"
fi

for name in product-flow coding-standards four-node-review; do
  src="${ROOT}/skills/${name}"
  dst="${TARGET}/${name}"
  [ -L "${dst}" ] || ln -s "${src}" "${dst}"
  echo "Linked ${name} -> ${dst}"
done

echo "SYBuilder installed. Restart or reload your agent so it can discover the skills."
echo "Loaded-path checks: export SYBUILDER_SKILLS_DIR=\"${TARGET}\""
echo "Without --prepare, runtime and platform capabilities remain unverified."
