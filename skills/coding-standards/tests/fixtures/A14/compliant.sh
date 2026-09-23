#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A14（references/rules-load-bearing.md）。
fails=0
echo "✗ 第一项不合格"; fails=$((fails+1))
echo "done"
[ "$fails" -gt 0 ] && exit 1 || exit 0
