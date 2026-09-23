#!/usr/bin/env bash
# 条款 → 判据 夹具对：把样本放进「它最该出声」的处境，看它说不说得出真话。
#
# 设计约束（都是本规范自己的条款）：
#   B4   全部做成**行为夹具**，不做源码正则 —— 后者两头都不承重
#   D3   两个方向都验：违反样本必须被观察到说假话；遵守样本必须说真话
#   D20  「遵守样本必须绿」才是承重的那一半
#   B18  遵守样本要是**照规范真写出来的东西**，不是「刚好能过判据的东西」
#   A15  每例的期望结论按它自己的正确答案写，不是一律 0
#   A1   本 runner 自己也三态：PASS / FAIL / UNABLE
#
# 退出码：0=全 PASS · 1=有 FAIL · 3=有 UNABLE 无 FAIL · 4=内部错误
set -u
D="$(cd "$(dirname "${BASH_SOURCE[0]}")/../tests/fixtures" && pwd)"
T=$(mktemp -d) || { echo "内部错误：无法创建夹具临时目录（基础设施失败，不是被测物不合格）"; exit 4; }
[ -n "${T}" ] && [ -d "${T}" ] || { echo "内部错误：mktemp 返回空/非目录 —— 再往下走会写到 /empty 这种路径上，把基础设施失败报成 FAIL"; exit 4; }
trap 'rm -rf "${T}"' EXIT
np=0; nf=0; nu=0
ok(){ [ $# -eq 3 ] || { echo "内部错误：ok 期望 3 参数收到 $#"; exit 4; }
      if [ "$3" = 1 ]; then np=$((np+1)); printf '  PASS   %-4s %s\n' "$1" "$2"
      else nf=$((nf+1)); printf '  FAIL   %-4s %s\n' "$1" "$2"; fi; }
skip(){ nu=$((nu+1)); printf '  UNABLE %-4s %s\n' "$1" "$2"; }
run(){ bash "$1" "${2:-}" 2>&1; }
rc(){  bash "$1" "${2:-}" >/dev/null 2>&1; echo $?; }
has(){ printf '%s' "$1" | /usr/bin/grep -qF -- "$2"; }
pre(){ printf '%s' "$1" | /usr/bin/grep -q "^$2"; }

echo "== 条款 → 判据 夹具对 =="; echo
for r in A1 A3 A14 A16 D22; do
  if [ ! -r "${D}/${r}/violating.sh" ] || [ ! -r "${D}/${r}/compliant.sh" ]; then
    skip "${r}" "夹具缺失，本条没能验"; continue; fi
  b=0
  case "${r}" in
  A1)
    v=$(run "${D}/A1/violating.sh" "${T}/nope"); c=$(run "${D}/A1/compliant.sh" "${T}/nope"); crc=$(rc "${D}/A1/compliant.sh" "${T}/nope")
    [ "${v}" = "FAIL" ] && b=1 || b=0
    ok A1 "违反样本把「没能测」说成 FAIL，与「测过不合格」不可分辨 → ${v}" "${b}"
    b=0; if pre "${c}" "UNABLE" && [ "${crc}" = 3 ]; then b=1; fi
    ok A1 "遵守样本说出「没能测」且 rc=3 → ${crc}" "${b}"
    ;;
  A3)
    : > "${T}/empty"; echo good > "${T}/good"
    v=$(run "${D}/A3/violating.sh" "${T}/empty"); c=$(run "${D}/A3/compliant.sh" "${T}/empty"); crc=$(rc "${D}/A3/compliant.sh" "${T}/empty")
    g=$(run "${D}/A3/compliant.sh" "${T}/good"); grc=$(rc "${D}/A3/compliant.sh" "${T}/good")
    [ "${v}" = "PASS" ] && b=1 || b=0
    ok A3 "违反样本在空集上假绿 → ${v}" "${b}"
    b=0; if pre "${c}" "UNABLE" && [ "${crc}" = 3 ]; then b=1; fi
    ok A3 "遵守样本触发下限断言且 rc=3 → ${crc}" "${b}"
    b=0; if pre "${g}" "PASS" && [ "${grc}" = 0 ]; then b=1; fi
    ok A3 "反向保护：合法非空输入必须放行，不许恒红 → ${g}" "${b}"
    # 第三侧（2026-09-10 codex P0-1）：**不合格输入**。前两侧只覆盖了 UNABLE 与 PASS，
    # 于是「打印 FAIL 却 rc=0」这条最典型的 A14 假绿一直没有任何一侧能看见。
    echo bad > "${T}/bad"
    bo=$(run "${D}/A3/compliant.sh" "${T}/bad"); brc=$(rc "${D}/A3/compliant.sh" "${T}/bad")
    b=0; if pre "${bo}" "FAIL" && [ "${brc}" = 1 ]; then b=1; fi
    ok A3 "不合格输入：既要说 FAIL，也要让 rc 跟着（A14）→ rc=${brc}" "${b}"
    ;;
  A14)
    vo=$(run "${D}/A14/violating.sh"); vr=$(rc "${D}/A14/violating.sh"); cr=$(rc "${D}/A14/compliant.sh")
    b=0; if has "${vo}" "✗" && [ "${vr}" = 0 ]; then b=1; fi
    ok A14 "违反样本打印 ✗ 却 rc=0 → rc=${vr}" "${b}"
    b=0; [ "${cr}" = 1 ] && b=1
    ok A14 "遵守样本的 fails 追得到 exit → rc=${cr}" "${b}"
    ;;
  A16)
    v=$(run "${D}/A16/violating.sh"); c=$(run "${D}/A16/compliant.sh")
    b=0; has "${v}" "ACTION-RAN" && b=1
    ok A16 "违反样本：门红了动作照跑" "${b}"
    b=1; has "${c}" "ACTION-RAN" && b=0
    ok A16 "遵守样本：门红了动作被挡住" "${b}"
    # A16 的另一半：门红了，整个脚本也得红。只验「动作没跑」会漏掉「挡住了却报成功」
    crc=$(rc "${D}/A16/compliant.sh")
    b=0; [ "${crc}" != 0 ] && b=1
    ok A16 "遵守样本：门的结论也落到退出码上 → rc=${crc}" "${b}"
    ;;
  D22)
    v=$(run "${D}/D22/violating.sh"); c=$(run "${D}/D22/compliant.sh"); cr=$(rc "${D}/D22/compliant.sh")
    b=0; has "${v}" "✓" && b=1
    ok D22 "违反样本：条件为假却打印 ✓" "${b}"
    b=0; if has "${c}" "✗" && [ "${cr}" != 0 ]; then b=1; fi
    ok D22 "遵守样本：条件为假时判失败 → rc=${cr}" "${b}"
    ;;
  esac
done
echo
printf 'PASS=%d  FAIL=%d  UNABLE=%d\n' "${np}" "${nf}" "${nu}"
if   [ "${nf}" -gt 0 ]; then echo "结论：FAIL"; exit 1
elif [ "${nu}" -gt 0 ]; then echo "结论：UNABLE（有条款没能验，不得当作通过）"; exit 3
else echo "结论：PASS"; exit 0; fi
