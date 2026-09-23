#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A14（references/rules-load-bearing.md）。
fails=0
echo "✗ 第一项不合格"; fails=$((fails+1))
# 违反 A14：fails 累加了，却没有任何一条 exit/raise 消费它
echo "done"
