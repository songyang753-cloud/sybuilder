#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A16（references/rules-load-bearing.md）。
# 遵守 A16：动作串在门的退出码链上，**并且**门的结论本身也落到退出码上。
# ⚠️ 这里刻意不写 `exit 0`：挡住动作只是 A16 的一半，另一半是「门红了，整个脚本也得红」，
#    否则调用方看到 exit 0，会以为门过了（那正是 A14 说的「累加器追不到 exit」）。
gate() { echo "GATE: FAIL"; return 1; }
if gate; then
  echo "ACTION-RAN"
else
  echo "门为红，动作未执行"
  exit 1
fi
