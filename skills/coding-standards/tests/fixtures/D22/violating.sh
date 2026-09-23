#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 D22（references/rules-load-bearing.md）。
ok() { echo "✓ $1"; }                      # 违反 D22：单参，条件被静默丢弃
ok "这条断言什么都没验证" "$(false && echo t)"
