#!/bin/bash
# One validation/export chain; temporary output prevents stale-image success.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
    echo "Usage: $0 <existing.svg>" >&2
    exit 1
fi
RENDER_DIR=$(mktemp -d "${TMPDIR:-/tmp}/sybuilder-svg-check.XXXXXX")
trap 'rm -rf "$RENDER_DIR"' EXIT
python3 "${SCRIPT_DIR}/render-svg.py" "$1" "$RENDER_DIR/render.png"
