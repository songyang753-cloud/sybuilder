#!/usr/bin/env bash
# 门禁自己的变异套件：逐条注入一个**已知缺陷**，断言门禁变红、且红的是**预期那道判据**。
#
# 为什么需要它：本 skill 的诚实边界此前只说「自证门禁核不了你有没有照做」，
# 却**没说清哪几道判据从没被变异验证过**。这一整场我用 reverse-test.sh 逐个验过十几道，
# 而那些验证只存在于对话里 —— 没留下可重跑的东西 = 下次改判据没有任何东西替你守着（E6/D31）。
#
# 表 = tests/gate-mutations.tsv，它是「哪几道判据被机器验过」的唯一真相源。
# 每条变异跑一次完整门禁，全表数分钟且随条数增长，故本脚本不进 selfcheck，改判据后手动跑一次。
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
TSV="${DIR}/tests/gate-mutations.tsv"
RT="${DIR}/scripts/reverse-test.sh"
[ -r "${TSV}" ] || { echo "内部错误：找不到 ${TSV}"; exit 4; }
[ -x "${RT}" ] || { echo "内部错误：找不到 ${RT}"; exit 4; }

# ⚠️ 套件层也要互斥（2026-09-05 实测）：锁原本只在 reverse-test.sh 里，
#    于是**两个套件实例可以同时跑** —— 它们在单条变异上串行，却整体交错，
#    一个实例的「还原」可能盖掉另一个实例开跑前的备份。实测撞到过一次
#    （我用 `&` 丢到后台一个没跑完，转头又启了一个）。
SUITE_LOCK="${TMPDIR:-/tmp}/coding-standards-mutations.lock"
if ! mkdir "${SUITE_LOCK}" 2>/dev/null; then
  echo "内部错误：已有一个变异套件在运行（锁 ${SUITE_LOCK}）—— 两个实例会互相污染被测物，本次不跑"
  echo "         若确认没有在跑，删掉该目录再试：rmdir '${SUITE_LOCK}'"
  exit 4
fi
# ⚠️ 2026-09-10（codex P1-26，本机实测确认）：写成 `trap ... EXIT INT TERM` 时，
#    收到 TERM 后只是**跑一遍 handler 然后继续往下执行**，最后还 rc=0 ——
#    被打断的套件会报成「全部通过」。信号必须自己退出，EXIT 单独管清理。
trap 'rmdir "${SUITE_LOCK}" 2>/dev/null' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# 表自己也要被校验：它是「哪几道判据被机器验过」的唯一真相源，
# 一行字段数不对就会被静默当成别的东西跑掉（E7：真相源自己没人校验就不是真相源）。
_bad_rows=$(awk -F'\t' '!/^#/ && NF>0 && NF!=6 {print NR": 字段="NF}' "${TSV}")
if [ -n "${_bad_rows}" ]; then
  echo "内部错误：变异表有格式错误的行（每行必须 6 个制表符分隔字段）："
  printf '%s\n' "${_bad_rows}"
  exit 4
fi

n=0; ok=0; bad=0; unab=0
echo "== 门禁变异套件 =="
while IFS=$'\t' read -r f old new want msg gate; do
  case "${f}" in ''|'#'*) continue ;; esac
  n=$((n+1))
  # @SRC 是特殊标记（反推源的副本模式），不是相对路径 —— 不许拼前缀。
  # 2026-09-05 实测：拼了前缀后 reverse-test 认不出它，报「文件不存在」⇒ 计入「没能测」。
  # ⭐ 这次正好验证了三态分类的价值：若还是两态，它会被报成「判据没接住」，人就会去查判据。
  case "${f}" in
    @*) _target="${f}" ;;
    *)  _target="${DIR}/${f}" ;;
  esac
  out="$(bash "${RT}" "${_target}" "${old}" "${new}" "${want}" "${msg}" "${gate}" 2>&1)"; _rr=$?
  # ⚠️ 2026-09-10（codex P1-26）：此前**只看 stdout 前缀**，退出码整个丢掉 ——
  #    reverse-test 被信号打死 / shell 起不来 / 输出为空时，全被归成「判据没接住」，
  #    而那明明是「没能测」。分诊指错方向正是 A19/D19 治的病。
  # ⚠️ 给本套件做阳性对照时注意：往表里临时加一条「锚点不存在」的行，会让 [11] 持续报 FAIL，
  #    从而把**期望 rc=3 的那几条用例挤成 rc=1** —— 于是对照组自己制造出 3 条假的「未接住」。
  #    实测 2026-09-05：分类逻辑其实是对的（「没能测 1」准确），是探针污染了被测环境。
  #    ⇒ 验完必须还原表并重跑一次干净的全量，否则那 3 条会被当成真发现。
  # 三态，不是两态（2026-09-05 修）：此前所有非 PASS 都计入 bad，结论一律说
  # 「有判据没接住它该接住的变异」—— 而「这条变异根本没能测」（锚点失效 / 变异没落地）
  # 与判据毫无关系。今天早上 4 条锚点失效正是被报成了前者，**诊断指错了方向**，我当场被误导过。
  # 同 A19（不合格与没能测不许混为一谈）+ D19（只报红不分诊等于没分诊）。
  case "${_rr}:${out}" in
    0:PASS*)  ok=$((ok+1));  printf '  ✓ %-30s [%-3s] %s\n' "$(basename "${f}")" "${gate}" "${msg}" ;;
    *:内部错误*|4:*|126:*|127:*|13[0-9]:*|14[0-9]:*)
              unab=$((unab+1)); printf '  ⊘ %-30s [%-3s] %s\n     rc=%s %s\n' "$(basename "${f}")" "${gate}" "${msg}" "${_rr}" "${out}" ;;
    1:*)      bad=$((bad+1)); printf '  ✗ %-30s [%-3s] %s\n     %s\n' "$(basename "${f}")" "${gate}" "${msg}" "${out}" ;;
    *)        unab=$((unab+1)); printf '  ⊘ %-30s [%-3s] %s\n     契约外结果 rc=%s：%s\n' "$(basename "${f}")" "${gate}" "${msg}" "${_rr}" "${out}" ;;
  esac
done < "${TSV}"

echo
# A3 下限断言：表被清空/读坏时不许报「0 条全过」
if [ "${n}" -lt 10 ]; then
  echo "UNABLE  只读到 ${n} 条变异（下限 10）—— 是表坏了，不是判据都验过了"
  exit 3
fi
printf '变异 %d 条 · 判据如期变红 %d · 未接住 %d · 没能测 %d\n' "${n}" "${ok}" "${bad}" "${unab}"
[ "${bad}" -eq 0 ] || { echo "结论：FAIL —— 有判据没接住它该接住的变异"; exit 1; }
[ "${unab}" -eq 0 ] || { echo "结论：UNABLE —— 有 ${unab} 条变异没能测（锚点失效／变异没落地），**不是判据的问题，也不算通过**"; exit 3; }
echo "结论：PASS —— 这 ${n} 道判据都被机器验过会红，且红的是它自己"
