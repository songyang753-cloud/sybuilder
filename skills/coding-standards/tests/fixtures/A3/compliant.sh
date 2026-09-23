#!/usr/bin/env bash
# 出处：coding-standards skill · 条款 A3（references/rules-load-bearing.md）。
# 遵守 A3：下限断言 + 真实计数上报。与 violating 的唯一差别就是这条下限断言。
MIN=1
checked=0; failures=0
while IFS= read -r x; do checked=$((checked+1)); [ "$x" = bad ] && failures=$((failures+1)); done < "$1"
[ "$checked" -lt "$MIN" ] && { echo "UNABLE 只收集到 ${checked} 项，低于下限 ${MIN}"; exit 3; }
# ⚠️ 2026-09-10（codex P0-1）：此前这一行是
#   [ "$failures" -eq 0 ] && echo "PASS ..." || echo "FAIL ..."
# —— 打印 FAIL 却 rc=0，正是 A14/A16 说的「结论没串在退出码上」。
# 而它是 [10m]「本 skill 脚本守住 A14/A16」的**正向基线** ⇒ 基线自己犯病，判据当然抓不到。
if [ "$failures" -gt 0 ]; then
  echo "FAIL checked=${checked} failures=${failures}"
  exit 1
fi
echo "PASS checked=${checked}"
exit 0
