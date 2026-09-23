#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A16（references/rules-load-bearing.md）。
gate() { echo "GATE: FAIL"; return 1; }
gate; echo "ACTION-RAN"        # 违反 A16：; 而不是 &&，门红了动作照做
