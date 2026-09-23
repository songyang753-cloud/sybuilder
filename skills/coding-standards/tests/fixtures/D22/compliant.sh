#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 D22（references/rules-load-bearing.md）。
ok() { [ $# -eq 2 ] || { echo "内部错误：ok 期望 2 个参数，收到 $#"; exit 4; }
       if [ "$2" = "true" ]; then echo "✓ $1"; else echo "✗ $1"; return 1; fi; }
ok "这条断言真的判了条件" "false" || exit 1
