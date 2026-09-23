#!/usr/bin/env bash
# 反向测试助手：把「变异必须先落地，再谈门禁红不红」变成一个动作，而不是一条纪律。
#
# 用法：reverse-test.sh <文件> <原串> <新串> [期望退出码，默认 1] [期望诊断关键字] [期望组标号]
#
# ⭐ 2026-09-09（codex P0-3）：改为**副本模式** —— 把整份 skill 复制到临时目录，
#    只在副本上变异、只在副本上跑门禁，**真实工作区全程只被 cp 读取、零写入**。
#    收益：即使外层工具 SIGKILL 把本进程杀在变异态，被杀的也只是临时副本，
#    真实工作区不可能留在变异态（旧版靠 trap 还原真实文件，D27 明说 trap 是异常安全
#    不是信号安全，SIGKILL 兜不住 —— 那个窗口现在从根上不存在了）。
#    兄弟 skill（four-node-review / product-flow）是**只读依赖**，
#    在副本根用软链接回真实位置，让 selfcheck 里的 `../兄弟` 相对路径成立（软链只读不写）。
#
# 为什么需要它（本文自身实录，2026-09-05 一天三次）：
#   手写反向测试时，注入用 `bash -c` + python 内联，反引号被命令替换吃掉、
#   `$?` 被前面的命令替换覆盖 …… 于是变异根本没落地，门禁照常绿，
#   而我差点把这个绿读成「判据没抓到缺陷」——最贵的误读方向。
#   D29 做法 2 早就写着「注入之后、跑门禁之前，断言变异串确实在文件里」，
#   但纪律留在脑子里等于没执行（D31）。
#
# 它保证四件事：
#   1. 原串必须**唯一存在**（否则锚点不可靠，直接 exit 4）
#   2. 变异**确实落地**（新串在文件里、文件确实变了），否则 exit 4 —— 绝不进入判读
#   3. 在**副本**上跑门禁并比对期望退出码
#   4. 真实工作区从头到尾只被 `cp -R` 读取，零写入（跑完 git status 可核）
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
[ $# -ge 3 ] || { echo "用法: $(basename "$0") <文件> <原串> <新串> [期望退出码] [期望诊断关键字] [期望组标号]"; exit 4; }
IN="$1"; OLD="$2"; NEW="$3"; WANT="${4:-1}"
WANT_MSG="${5:-}"   # 可选：期望的诊断关键字 —— 只验 rc 不验「是哪道判据红了」等于没分诊
WANT_GATE="${6:-}"  # 可选：期望红的**组标号**（如 3a2 / 10 / 8b）。
                    # 关键字能被别的组说出同样的话；组标号把「红的是它自己」钉死在位置上。
                    # 不给则只验关键字，并在 PASS 行里报出实际命中的组，供填表（不靠手猜）。

# 互斥锁：锁名**不可更改** —— selfcheck [11] 用这个锁路径判断「此刻是否有变异在跑」，
# 从而在变异运行期把锚点活性判成 UNABLE 而非 FAIL（A19：没能测≠不合格）。改锁名会让那道判据失效。
# mkdir 是原子的，用它当锁；拿不到锁就直接退，绝不「先跑了再说」。
LOCK="${TMPDIR:-/tmp}/coding-standards-revtest.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
  echo "内部错误：另一个反向测试正在运行（锁 ${LOCK}）—— 并发会互相污染被测物，本次不跑"
  exit 4
fi

# ---- 副本模式：整份 skill 复制到临时目录，兄弟 skill 软链只读（2026-09-09 codex P0-3）----
WORKROOT="$(mktemp -d "${TMPDIR:-/tmp}/cs-revtest.XXXXXX")" || { rmdir "${LOCK}" 2>/dev/null; exit 4; }
GOUT=""; PRE=""
# trap 只清理临时副本 + 锁 + 临时文件 —— 真实工作区没被写，没有「还原真实文件」这一步。
# 顺序：先删副本（体积最大、最要紧），再删锁与临时文件。SIGKILL 仍跑不到 trap，
# 但那时被留下的只是 /tmp 里的副本，真实工作区不受影响 —— 这正是本次改造要消掉的窗口。
# ⚠️ 2026-09-10（codex P1-26，我上一批漏了这一个文件）：`EXIT INT TERM` 写在一起时，
#    收到信号只是跑一遍 handler 然后**继续往下执行**，最后还可能 rc=0 —— 被打断的反向测试会报成 PASS。
#    信号必须自己退出，EXIT 只管清理。
trap 'rm -rf "${WORKROOT}" 2>/dev/null; rmdir "${LOCK}" 2>/dev/null; rm -f "${GOUT:-}" "${PRE:-}" 2>/dev/null' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "${WORKROOT}/skills" || exit 4
COPY="${WORKROOT}/skills/coding-standards"
cp -R "${DIR}" "${COPY}" || { echo "内部错误：复制 skill 到副本失败"; exit 4; }
# 保留发布套件的相对路径；references 中的 ../../../ 必须仍指向套件根。
SUITE_ROOT="$(cd "${DIR}/../.." && pwd -P)"
for _asset in THIRD_PARTY.md licenses; do
  [ -e "${SUITE_ROOT}/${_asset}" ] && cp -R "${SUITE_ROOT}/${_asset}" "${WORKROOT}/" ||
    { echo "内部错误：无法复制套件来源文件 ${_asset}"; exit 4; }
done
for _sib in four-node-review product-flow; do
  _real="${DIR}/../${_sib}"
  [ -d "${_real}" ] && ln -s "$(cd "${_real}" && pwd -P)" "${WORKROOT}/skills/${_sib}" 2>/dev/null
done
GATE="${COPY}/scripts/selfcheck.sh"
GOUT="$(mktemp "${WORKROOT}/gate.XXXXXX")" || exit 4
# 此时副本尚未变异。用副本私有 TMPDIR 检查干净基线，不让本进程的变异锁
# 把锚点检查提前标成 UNABLE；正式变异检查仍使用原 TMPDIR 和原互斥锁。
TMPDIR="${WORKROOT}" bash "${GATE}" > "${GOUT}" 2>&1
if [ "$?" -ne 0 ]; then
  echo "内部错误：副本的干净基线未通过，不能把既有失败当成变异被拦截"
  cat "${GOUT}"
  exit 4
fi

# ---- 定位副本里的被测文件 ----
if [ "${IN}" = "@SRC" ]; then
  # @SRC = 反推源（four-node）副本模式：真源属别的会话，复制一份到副本内变异，
  # 让门禁经 FOUR_NODE_SKILL 读这份副本。真源全程零触碰。
  COPY_SRC="${FOUR_NODE_SKILL:-${DIR}/../four-node-review/SKILL.md}"
  [ -r "${COPY_SRC}" ] || { echo "内部错误：读不到反推源 ${COPY_SRC}"; exit 4; }
  F="${WORKROOT}/fnr-src.md"
  cp "${COPY_SRC}" "${F}" || { echo "内部错误：复制反推源失败"; exit 4; }
  export FOUR_NODE_SKILL="${F}"
elif [ "${IN}" = "@ENG" ]; then
  # @ENG = 内置仓库执法模块；整份 coding-standards 已复制到临时目录，
  # 故直接变异副本内 PLAYBOOK，真实工作区仍然零写入。
  F="${COPY}/repository-enforcement/PLAYBOOK.md"
  [ -s "${F}" ] || { echo "内部错误：副本里找不到 repository-enforcement/PLAYBOOK.md"; exit 4; }
  export ENG_STD_SKILL="${F}"
else
  # 调用方按契约传真实绝对路径 ${DIR}/…；映射到副本内同名文件。
  case "${IN}" in
    "${DIR}/"*) F="${COPY}/${IN#"${DIR}/"}" ;;
    *) echo "内部错误：被测文件 ${IN} 不在 skill 目录下（副本模式只能测本 skill 内的文件，或用 @SRC）"; exit 4 ;;
  esac
fi
[ -f "${F}" ] || { echo "内部错误：副本里找不到被测文件 ${F}"; exit 4; }

# ---- 锚点里的数字用 %d 占位（2026-09-05 加）----
# 病因：变异锚点写成「全部 144 条完整条款」这种含派生数字的字面串，
# 条款一增，四条锚点同时失效。修病因是**让锚点不含具体数字**：
#   原串 `全部 %d 条完整条款`  → 运行时按 (\d+) 匹配出实际那一处，用实际文本当原串
#   新串 `全部 %d 条完整条款`  → 同一位置填「实际值 +1」，保证注入的错值永远与现状不同
# 不含 %d 的原串走原路径，行为不变。
case "$OLD" in
  *%d*)
    _resolved="$(OLD="$OLD" NEW="$NEW" python3 - "$F" <<'PYRESOLVE'
import io,os,re,sys
s=io.open(sys.argv[1],encoding="utf-8").read()
old,new=os.environ["OLD"],os.environ["NEW"]
pat=re.compile("(\\d+)".join(re.escape(x) for x in old.split("%d")))
hits=pat.findall(s)
if len(hits)!=1:
    print("ERR\t占位锚点匹配到 %d 处（必须恰好 1 处）"%len(hits)); raise SystemExit
m=pat.search(s)
nums=[int(g) for g in m.groups()]
out_new=new
for n in nums:
    out_new=out_new.replace("%d",str(n+1),1)
print("OK\t%s\t%s"%(m.group(0),out_new))
PYRESOLVE
)"
    case "$_resolved" in
      OK*) OLD="$(printf '%s' "$_resolved" | cut -f2)"; NEW="$(printf '%s' "$_resolved" | cut -f3)" ;;
      *)   echo "内部错误：$(printf '%s' "$_resolved" | cut -f2)"; exit 4 ;;
    esac
    ;;
esac

# 副本的**变异前快照**，仅供「变异是否落地」的断言用（不是用来还原真实文件 —— 真实文件根本没被写）。
PRE="$(mktemp "${WORKROOT}/pre.XXXXXX")" || exit 4
cp "$F" "$PRE"

n=$(OLD="$OLD" python3 -c 'import io,os,sys;print(io.open(sys.argv[1],encoding="utf-8").read().count(os.environ["OLD"]))' "$F")
if [ "$n" != 1 ]; then echo "内部错误：原串在文件中出现 ${n} 次（必须恰好 1 次，否则锚点不可靠）"; exit 4; fi

OLD="$OLD" NEW="$NEW" python3 -c '
import io,os,sys
p=sys.argv[1]; s=io.open(p,encoding="utf-8").read()
io.open(p,"w",encoding="utf-8").write(s.replace(os.environ["OLD"],os.environ["NEW"],1))' "$F"

# 变异是否真的落地 —— 这一步就是本脚本存在的理由。
# 落地判据：①文件确实变了 ②新串在文件里。
# ⚠️ 不要求「原串消失」—— 追加式变异（新串包含原串）原串本就还在，
#    那样写会把正确用法判成没落地（B16：判据过紧同样是缺陷）。
ok=$(NEW="$NEW" python3 -c '
import io,os,sys
s=io.open(sys.argv[1],encoding="utf-8").read()
b=io.open(sys.argv[2],encoding="utf-8").read()
print("yes" if (os.environ["NEW"] in s and s!=b) else "no")' "$F" "$PRE")
if [ "$ok" != yes ]; then
  echo "内部错误：变异没有落地（新串不在文件里，或文件内容根本没变）—— 这次的绿/红都不作数"
  exit 4
fi

bash "$GATE" > "${GOUT}" 2>&1; rc=$?

# ⚠️ 要在**全部** FAIL/UNABLE 行里找，不能只看第一行：
# 一次变异可能同时触发多道判据，只看第一行会把「红的不是那道」这个结论下错 —— 最贵的误读方向。
_all="$(${GREP:-/usr/bin/grep} -E '^  (FAIL|UNABLE)' "${GOUT}" | sed 's/^ *//' || true)"
# 每条诊断挂回它所属的组：组标题形如 `[3a2] 组内索引`，其后缩进行是该组的判据结论。
_pairs="$(awk '/^\[[0-9a-z]+\] /{g=$1; gsub(/[][]/,"",g)} /^  (FAIL|UNABLE)/{sub(/^ +/,""); print g"\t"$0}' "${GOUT}" || true)"
_diag="$(printf '%s' "${_all}" | head -1)"
[ -n "${_diag}" ] || _diag='（无 FAIL/UNABLE 行）'
if [ "$rc" = "$WANT" ]; then
  if [ -n "${WANT_MSG}" ] && ! printf '%s' "${_all}" | ${GREP:-/usr/bin/grep} -qF -- "${WANT_MSG}"; then
    echo "FAIL   rc 对了（${rc}），但**没有任何一条** FAIL/UNABLE 含「${WANT_MSG}」。实得 $(printf '%s' "${_all}" | ${GREP:-/usr/bin/grep} -c . || true) 条：${_diag}"
    exit 1
  fi
  # 命中组带上状态标注：FAIL 和 UNABLE 折在一个列表里害过人（A19：两种含义不许共用一个格式）。
  _hit="$(printf '%s' "${_pairs}" | ${GREP:-/usr/bin/grep} -F -- "${WANT_MSG}" | awk -F'\t' '{split($2,a," "); print $1"("a[1]")"}' | sort -u | tr '\n' ',' | sed 's/,$//')"
  if [ -n "${WANT_GATE}" ]; then
    if ! printf '%s' "${_pairs}" | awk -F'\t' -v g="${WANT_GATE}" '$1==g' | ${GREP:-/usr/bin/grep} -qF -- "${WANT_MSG}"; then
      echo "FAIL   rc 与关键字都对，但红的**不是** [${WANT_GATE}]，实际命中组：${_hit:-（无）}"
      exit 1
    fi
  fi
  echo "PASS   变异已落地且门禁按预期 rc=${rc}（命中组 ${_hit:-?}）：${_diag}"
  exit 0
fi
echo "FAIL   变异已落地，但门禁 rc=${rc}（期望 ${WANT}）—— 判据没有接住这次变异"
tail -6 "${GOUT}"
exit 1
