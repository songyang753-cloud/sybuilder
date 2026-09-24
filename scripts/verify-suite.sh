#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODE="${1:---quick}"
export PYTHONDONTWRITEBYTECODE=1

case "${MODE}" in
  --quick|--full) ;;
  *) echo "Usage: ./scripts/verify-suite.sh [--quick|--full]" >&2; exit 2 ;;
esac

if [ "${MODE}" = "--full" ]; then
  # Full selftest refreshes measured state consumed by consistency-gate.
  python3 "${ROOT}/skills/product-flow/scripts/selftest-all.py" --fresh
fi

python3 "${ROOT}/skills/product-flow/scripts/gen-docs.py" --check
python3 "${ROOT}/skills/product-flow/scripts/no-loss-gate.py"
python3 "${ROOT}/skills/product-flow/scripts/consistency-gate.py"
FOUR_NODE_SKILL="${ROOT}/skills/four-node-review/SKILL.md" \
  bash "${ROOT}/skills/coding-standards/scripts/selfcheck.sh"
if [ "${MODE}" = "--full" ]; then
  python3 "${ROOT}/scripts/verify-modules.py" --render
else
  python3 "${ROOT}/scripts/verify-modules.py"
fi
python3 -m unittest discover -s "${ROOT}/skills/product-flow/modules/diagramming/tests" -p 'test_*.py'
python3 "${ROOT}/skills/product-flow/scripts/_feishu.py" --self-test
python3 "${ROOT}/skills/product-flow/scripts/dingtalk-delivery-gate.py" --self-test
python3 "${ROOT}/skills/product-flow/scripts/doc-sync-guard.py" --self-test
python3 "${ROOT}/scripts/test-release-regressions.py"
python3 "${ROOT}/scripts/test-remediation-contracts.py"
node "${ROOT}/scripts/test-crawler-regressions.cjs"
python3 "${ROOT}/scripts/test-w5.py"
python3 "${ROOT}/scripts/test-w5-boundaries.py"
python3 "${ROOT}/scripts/test-gate-binding.py"
python3 "${ROOT}/scripts/test-review-boundaries.py"
python3 "${ROOT}/skills/product-flow/tests/s2-golden/run-golden.py"

if [ "${MODE}" = "--full" ]; then
  FOUR_NODE_SKILL="${ROOT}/skills/four-node-review/SKILL.md" \
    bash "${ROOT}/skills/coding-standards/scripts/gate-mutations.sh"
fi

python3 "${ROOT}/scripts/verify-portability.py" "${ROOT}"
bash "${ROOT}/scripts/test-install.sh"
python3 "${ROOT}/scripts/release-audit.py" "${ROOT}"
echo "SYBuilder ${MODE} verification passed."
