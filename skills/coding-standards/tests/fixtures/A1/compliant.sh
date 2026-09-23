#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A1（references/rules-load-bearing.md）。
# 遵守 A1：三态。照规范写的样子——「没能测」是第三种东西，且带可操作原因。
check_target() {
  [ -r "$1" ] || { echo "UNABLE 读不到目标：$1"; return 3; }
  grep -q OK "$1" && { echo "PASS"; return 0; }
  echo "FAIL"; return 1
}
check_target "$1"
