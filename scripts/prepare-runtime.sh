#!/usr/bin/env bash
# Explicit local preparation. Does not install browsers, CLIs or credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<22 || (a===22 && b<4) || typeof WebSocket!=="function" || typeof fetch!=="function") throw Error("Node 22.4+ with WebSocket/fetch required")'
mkdir -p "${ROOT}/.sybuilder"
# Never upgrade an existing environment in place. Failed preparation leaves it intact.
RUNTIME="$(mktemp -d "${ROOT}/.sybuilder/runtime.XXXXXX")"
python3 -m venv "${RUNTIME}"
"${RUNTIME}/bin/python" -m pip install --disable-pip-version-check -r "${ROOT}/requirements.txt"
PATH="${RUNTIME}/bin:${PATH}" python3 "${ROOT}/scripts/verify-modules.py" --render
echo "Runtime prepared and real diagram rendering checked. Activate: source \"${RUNTIME}/bin/activate\""
echo "Optional account/platform access has NOT been authorized or tested."
