#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A1（references/rules-load-bearing.md）。
# 违反 A1：二态。目标不可达时返回 false —— 与「测过了、不合格」无法分辨。
check_target() { [ -r "$1" ] && grep -q OK "$1"; }
check_target "$1" && echo "PASS" || echo "FAIL"
