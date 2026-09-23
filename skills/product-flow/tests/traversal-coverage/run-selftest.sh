#!/usr/bin/env bash
# M8 门禁自证:满报告绿 / 浅报告红 / 缺输入UNABLE。任一不符即退出1。
# ⭐ 退出码已统一为全队标准 STD:0=绿 1=红 2=UNABLE(旧为 0/2/3);门内 --self-test 是正本,本脚本仅冗余保留。
set -u; cd "$(dirname "$0")"; G=../../scripts/traversal-coverage-gate.py; DT=fixtures/deep-tree.mini.json; fail=0
python3 $G --deep-tree $DT --report fixtures/report-full.mini.md   >/dev/null 2>&1; [ $? -eq 0 ] || { echo "✗ 满报告应绿(0)"; fail=1; }
python3 $G --deep-tree $DT --report fixtures/report-shallow.mini.md >/dev/null 2>&1; [ $? -eq 1 ] || { echo "✗ 浅报告应红(1)"; fail=1; }
python3 $G --deep-tree /nope.json --report fixtures/report-full.mini.md >/dev/null 2>&1; [ $? -eq 2 ] || { echo "✗ 缺输入应UNABLE(2)"; fail=1; }
[ $fail -eq 0 ] && echo "✅ 门禁自证全过(绿/红/UNABLE 三态正确)" || echo "❌ 门禁自证失败"; exit $fail
