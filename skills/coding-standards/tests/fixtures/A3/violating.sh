#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A3（references/rules-load-bearing.md）。
# 违反 A3：空集时 failures 恒为 0 ⇒ 报通过，且不上报真实计数。
failures=0
while IFS= read -r x; do [ "$x" = bad ] && failures=$((failures+1)); done < "$1"
[ "$failures" -eq 0 ] && echo "PASS" || echo "FAIL"
