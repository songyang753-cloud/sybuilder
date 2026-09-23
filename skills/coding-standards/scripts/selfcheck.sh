#!/usr/bin/env bash
# coding-standards 自证门禁
#
# 核的是「这份规范自己是否自洽」，不是「你有没有照做」——
# 按本文 B4，对源码做正则来判断「有没有照做」的判据两头都不承重，故本文故意不提供那种门禁。
#
# 本门禁自己遵守它所要求的东西：
#   A1  三态输出 PASS / FAIL / UNABLE，UNABLE 既不计绿也不计红，但让退出码非零
#   A3  下限断言 + 真实计数上报（收集不到东西时判 UNABLE，不判 PASS）
#   A9  元检查：先用两向反向测试证明「锚点校验机制」本身有效，无效则整体 UNABLE
#   D3  正反两个方向都测（该找到的找得到 / 该找不到的找不到）
#   D5  否定型结论要更强证据：grep 可能被 shell 函数遮蔽，一律用 /usr/bin/grep
#
# 退出码语义（A15：每个脚本必须在文件头声明，且不许比实际粗）：
#   0 = 全 PASS
#   1 = 有 FAIL（测了，不合格）
#   3 = 有 UNABLE 无 FAIL（没能测 —— 不是合格，也不是不合格）
#   4 = 门禁自身内部错误（如断言函数收到多余实参）
#   （2 保留给「用法错误 / 参数不对」，本脚本目前不产生）
# ⚠️ 本行由 [9] 自核：声明的码值集合必须等于脚本里实际用到的 exit 码集合。

set -u

# pwd -P 取**物理路径**：本 skill 的真实调用形态是经 ~/.claude/skills/ 的软链，
# 而逻辑路径会把软链带进后续所有命令 —— BSD grep 的 -r/-R 都不跟随软链（跟随是 -S；GNU 才是 -R 跟随，2026-09-15 实测修正），
# 于是「开发路径全绿、真实调用形态报红」。实测 2026-09-05。
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SKILL="${SKILL_DIR}/SKILL.md"
DERIV="${SKILL_DIR}/references/derivation.md"
SOURCES="${SKILL_DIR}/references/sources.md"
R_L="${SKILL_DIR}/references/rules-load-bearing.md"
R_K="${SKILL_DIR}/references/rules-ai-collab.md"
R_M="${SKILL_DIR}/references/rules-delivery.md"
R_F="${SKILL_DIR}/references/foundation.md"
R_Z="${SKILL_DIR}/references/authority.md"
SRC="${FOUR_NODE_SKILL:-${SKILL_DIR}/../four-node-review/SKILL.md}"
REPO_ENFORCEMENT="${ENG_STD_SKILL:-${SKILL_DIR}/repository-enforcement/PLAYBOOK.md}"
GREP=${GREP:-/usr/bin/grep}   # 与 reverse-test.sh 的写法统一（此前两个脚本对同一件事不一致）

_t0=$(date +%s)
# 记录的基线（**手写**，它是用来发现漂移的参照，不是对现状的描述 —— 见 E7 的两类数字之分）。
# 📌 由来：R 轮量到中位 4.0s 并特意**不加墙钟红线**（G4：时间只用来等和算比值，不判快慢；
#    墙钟断言在并发机器上必然抖动，假红会让判据先被豁免再被删掉）。
#    但那之后**没有人再量过它** —— 今天一量已经 ~15s，涨了近 4 倍，而中间七八轮无人察觉。
#    （当天定位并修掉了热点：[2] 对 90 个锚点各起一次 grep 进程，占了约八成墙钟；
#      合并成一次 python 后回到 ~2s。基线随之从 15 收到 5。）
#    ⚠️ 取 5 而不是 3：本机 8–12 个会话并行（实测负载 22 / 8 核），
#      同一份代码串行单跑在低负载 2s、高负载 8s —— 差 3.5 倍。
#      基线按**最坏可接受**设，不是按你量到的最好那次设：设 3 当天就误报了一次。
#    ⇒ 「记下来的基线」如果没有下一次测量，它就只是一个数字。
#    这里给它加上下一次测量：超过 2× 就出声，但**只提醒、不判失败**（硬失败会把并发抖动变成假红）。
BASELINE_SECONDS=5
n_pass=0; n_fail=0; n_unable=0
declare -a FAILS=() UNABLES=()

# ⚠️ D22：断言函数必须拒收多余实参 —— 否则 `pass "msg" "$(cond)"` 里的条件会被静默吞掉，
#    断言什么都没验证却永远打印 ✓。本门禁自审时真的踩到过这一条。
_argn(){ [ "$1" -eq "$2" ] || { printf '  内部错误：%s 期望 %s 个参数，收到 %s 个 —— 见 D22\n' "$3" "$1" "$2" >&2; exit 4; }; }
pass(){ _argn 1 $# pass; n_pass=$((n_pass+1)); printf '  PASS   %s\n' "$1"; }
fail(){ _argn 1 $# fail; n_fail=$((n_fail+1)); FAILS+=("$1"); printf '  FAIL   %s\n' "$1"; }
unable(){ _argn 1 $# unable; n_unable=$((n_unable+1)); UNABLES+=("$1"); printf '  UNABLE %s\n' "$1"; }

echo "== coding-standards 自证门禁 =="
echo

# ---------- 0. 前置：文件在不在（不在 = UNABLE，不是 FAIL）----------
echo "[0] 前置"
# ⚠️ 这个集合必须**盖住下游真正会读的每一个文件**（2026-09-05 实测补上 R_F / R_Z）：
#    此前它只有六个，漏掉基础层 P 与权威层 Z —— 而 [10] 明明在读它们。
#    后果不是「少查一个」，是**缺文件时不在这里干净地 UNABLE，而在下游变成别的形状**：
#    实测把 foundation.md 设为不可读，四道判据齐声报「缺 python3 或它自己崩了」，
#    真因（PermissionError + 完整路径）就在几行之上的 stderr 里，而**人读的是结论行**。
for f in "${SKILL}" "${DERIV}" "${SOURCES}" "${R_L}" "${R_K}" "${R_M}" "${R_F}" "${R_Z}"; do
  [ -r "${f}" ] || { unable "读不到 ${f}"; }
done
if [ ${#UNABLES[@]} -gt 0 ]; then
  echo; echo "结论：UNABLE（缺前置文件，没能开始检查）"; exit 3
fi
pass "八个文件可读（主文件 + 三份条款 + 基础层 + 权威层 + 证据链 + 来源）"

if [ ! -r "${SRC}" ]; then
  unable "读不到反推源 ${SRC}（设 FOUR_NODE_SKILL 指向 four-node-review/SKILL.md）—— 锚点校验整块没能执行"
  SRC_OK=0
else
  SRC_OK=1; pass "反推源可读：${SRC}"
fi
echo

# ---------- 1. 元检查：锚点校验机制本身有效吗（A9 + D3 两向）----------
echo "[1] 元检查（先证明校验机制本身有效，否则后面的结论都不可信）"
if [ "${SRC_OK}" = 1 ]; then
  probe_ne="$(${GREP} -c . "${SRC}" 2>/dev/null || echo 0)"
  known_present="四节点终审流水线"
  known_absent="ZZ_这句话绝不可能出现在四节点终审里_9f3a2b_ZZ"
  ok_meta=1
  ${GREP} -qF -- "${known_present}" "${SRC}" || { ok_meta=0; }
  ${GREP} -qF -- "${known_absent}"  "${SRC}" && { ok_meta=0; }
  if [ "${ok_meta}" = 1 ] && [ "${probe_ne}" -gt 100 ]; then
    pass "两向反向测试通过（该命中的命中、该落空的落空；源文件非空行 ${probe_ne}）"
  else
    unable "锚点校验机制自检失败（双向测试=${ok_meta} 非空行=${probe_ne}）—— 本次锚点结论不可采信"
    SRC_OK=0
  fi
else
  unable "跳过元检查（源不可读）"
fi
echo

# ---------- 2. 锚点：每条准则的「反推自」必须真的存在 ----------
echo "[2] 锚点校验（准则 → four-node-review 的存在性）"
anchors="$(sed -n '/ANCHORS:BEGIN/,/ANCHORS:END/p' "${DERIV}" | ${GREP} -E '^[A-J][0-9]+\|' || true)"
n_anchor=$(printf '%s' "${anchors}" | ${GREP} -c . || true)
unver="$(sed -n '/UNVERIFIABLE:BEGIN/,/UNVERIFIABLE:END/p' "${DERIV}" | ${GREP} -E '^[A-J][0-9]+\|' || true)"
n_unver=$(printf '%s' "${unver}" | ${GREP} -c . || true)
# ⭐ 棘轮：例外数**只许降不许升**（2026-09-05 加，由 peer 会话 case-55 的 E7 区分反向推出）。
# 此前它只被打印成一行不阻断的 NOTE，并参与闭世界对账 —— 而对账只保证「每条都登记了」，
# **不限制能有多少条**。于是它从 23 安静地长到 36，涨了 13 条而没有任何东西提醒过，
# 每多一条就多一条「出处没人守」的准则。
# ⚠️ 这个上限是**表达策略的数字，必须手写**：做成可推导（自动跟随现状）等于把红线改成移动靶。
# 📌 上调记录（每次上调都要留一行理由，否则棘轮退化成计数器）：
#    ⚠️ 上调时**同步改 tests/gate-mutations.tsv 里守这条的那行锚点**（`MAX_UNVER=<新值>`）。
#       它没法用 %d 占位：变异要把上限**调小**才会红，而占位只能填「实际值+1」＝放宽＝不会红。
#       ⇒ 只能用字面锚点。好在上调是罕见的显式动作，而 [11] 会当场抓到你忘了改（已抓到 3 次）。
#    36 → 37（2026-09-05）：新增 D37，出处是 peer 会话实证 + 本文实证，两者都不是
#    four-node-review 的锚点，只能进声明例外区。这是棘轮第一次真实生效 ——
#    它没有禁止增长，而是让增长需要一个显式动作和一句理由。
#    37 → 38（2026-09-05）：新增 E8，出处是第五次外部实战（engineering-standards 的 CI 模板），
#    同样不是 four-node-review 的锚点。⚠️ 连续两次上调都来自「外部实战/peer 实证」这一类 ——
#    若这一类继续增长，该考虑的不是继续放宽，而是**给外部实战的出处单开一个可机器校验的桶**。
MAX_UNVER=38
if [ "${n_unver}" -gt "${MAX_UNVER}" ]; then
  fail "出处不可机器校验的条款涨到 ${n_unver} 条，超过棘轮上限 ${MAX_UNVER} —— 每多一条就多一条没人守的准则；确实该放宽就显式上调这个数并写清理由"
elif [ "${n_unver}" -lt "${MAX_UNVER}" ]; then
  # 只提醒、不判失败：做成硬失败会让「减少例外」这件好事本身变红（B16 惩罚正确行为）
  pass "出处不可机器校验 ${n_unver} 条，低于棘轮上限 ${MAX_UNVER} —— 建议把 MAX_UNVER 收到 ${n_unver}"
else
  pass "出处不可机器校验 ${n_unver} 条（已显式声明，非静默跳过），正处棘轮上限"
fi

# A3 下限断言：收不到锚点 = UNABLE，不是「0 个都通过了」
if [ "${n_anchor:-0}" -lt 10 ]; then
  unable "只解析到 ${n_anchor:-0} 个锚点，低于下限 10 —— 是解析坏了，不是没问题"
elif [ "${SRC_OK}" != 1 ]; then
  unable "解析到 ${n_anchor} 个锚点，但源不可读，一个都没能校验"
else
  # ⚡ 一次 python 读完，替代「90 个锚点 × 90 次 grep 进程」（2026-09-05）：
  #    那 90 次 fork+exec 占了本门禁约一半的墙钟时间。语义完全等价 ——
  #    `grep -qF` 是固定字符串子串判断，python 的 `a in src` 就是同一件事。
  #    ⚠️ 加速不许改变行为：改前把全部 54 行结论存下来，改后逐字节对比过（一致），
  #      且变异表里守 [2] 的那条反向测试仍然精确变红。
  _mout="$(ANCHORS="${anchors}" python3 - "${SRC}" <<'PYANCHOR'
import io,os,sys
src=io.open(sys.argv[1],encoding='utf-8').read()
miss=[]; n=0
for line in os.environ['ANCHORS'].split('\n'):
    if not line.strip(): continue
    id_,_,a=line.partition('|')
    if not id_: continue
    n+=1
    if a not in src: miss.append(id_)
print('%d\t%s'%(len(miss),' '.join(miss)))
PYANCHOR
)"
  miss="${_mout%%	*}"; misslist=" ${_mout#*	}"
  [ "${miss}" = 0 ] && misslist=""
  if [ "${miss}" -eq 0 ]; then
    pass "${n_anchor}/${n_anchor} 个锚点在源文件中命中"
  else
    fail "${miss}/${n_anchor} 个锚点在源文件中找不到（源文件改了措辞，或推导写错了）:${misslist}"
  fi
fi
echo

# ---------- 3. 条数：声明的数量 = 实际数量 ----------
echo "[3] 条数对账"
declared=$(${GREP} -oE '（A–J，[0-9]+ 条）' "${R_L}" | ${GREP} -oE '[0-9]+' | head -1 || true)
actual=$(${GREP} -cE '^### [A-J][0-9]+ ·' "${R_L}" || true)
if [ -z "${declared:-}" ]; then
  unable "没能从 SKILL.md 解析出声明条数"
elif [ "${declared:-0}" = "${actual:-0}" ]; then
  pass "声明 ${declared} 条 = 实际 ${actual} 条"
else
  fail "声明 ${declared} 条，实际 ${actual} 条 —— 改了条款没改计数"
fi

# K 层条数
k_declared=$(${GREP} -oE '完整条款（[0-9]+ 条）' "${R_K}" | ${GREP} -oE '[0-9]+' | head -1 || true)
k_actual=$(${GREP} -cE '^### K[0-9]+ · ' "${R_K}" || true)
if [ -z "${k_declared:-}" ]; then
  unable "没能从 SKILL.md 解析出 K 层声明条数"
elif [ "${k_declared:-0}" = "${k_actual:-0}" ]; then
  pass "K 层声明 ${k_declared} 条 = 实际 ${k_actual} 条"
else
  fail "K 层声明 ${k_declared} 条，实际 ${k_actual} 条"
fi

# 闭世界对账：锚点 + 声明例外 = 承重层准则数（B10：每条都要落进一个已分类的桶）
if [ "${n_anchor:-0}" -gt 0 ] && [ "${actual:-0}" -gt 0 ]; then
  total_src=$(( n_anchor + n_unver ))
  if [ "${total_src}" = "${actual}" ]; then
    pass "出处闭世界：锚点 ${n_anchor} + 声明例外 ${n_unver} = 准则 ${actual}"
  else
    fail "出处不闭世界：锚点 ${n_anchor} + 例外 ${n_unver} = ${total_src} != 准则 ${actual} —— 有准则没登记出处，或登记了不存在的准则"
  fi
fi

# M 层条数
m_declared=$(${GREP} -oE '完整条款（[0-9]+ 条）' "${R_M}" | ${GREP} -oE '[0-9]+' | head -1 || true)
m_actual=$(${GREP} -cE '^### M[0-9]+ · ' "${R_M}" || true)
if [ -z "${m_declared:-}" ]; then
  unable "没能从 SKILL.md 解析出 M 层声明条数"
elif [ "${m_declared:-0}" = "${m_actual:-0}" ]; then
  pass "M 层声明 ${m_declared} 条 = 实际 ${m_actual} 条"
else
  fail "M 层声明 ${m_declared} 条，实际 ${m_actual} 条"
fi

# M 层逐条出处覆盖
m_src=$(sed -n '/MSRC:BEGIN/,/MSRC:END/p' "${R_M}" | ${GREP} -cE '^M[0-9]+\|' || true)
if [ "${m_src:-0}" -eq 0 ]; then
  unable "没能从 SKILL.md 解析出 M 层出处表"
elif [ "${m_src}" = "${m_actual:-0}" ]; then
  pass "M 层出处覆盖 ${m_src}/${m_actual}"
else
  fail "M 层出处 ${m_src} 条，准则 ${m_actual} 条 —— 有 M 条款没登记出处"
fi

# K 层逐条出处覆盖
k_src=$(sed -n '/KSRC:BEGIN/,/KSRC:END/p' "${R_K}" | ${GREP} -cE '^K[0-9]+\|' || true)
if [ "${k_src:-0}" -eq 0 ]; then
  unable "没能从 SKILL.md 解析出 K 层出处表"
elif [ "${k_src}" = "${k_actual:-0}" ]; then
  pass "K 层出处覆盖 ${k_src}/${k_actual}"
else
  fail "K 层出处 ${k_src} 条，准则 ${k_actual} 条 —— 有 K 条款没登记出处"
fi
echo

# ---------- 3a. 条款标题格式闭世界（B15：圈不到的不许静默消失）----------
echo "[3a] 条款标题格式"
if ! command -v python3 >/dev/null 2>&1; then
  unable "没有 python3，标题格式检查没能执行"
else
  hdr_out="$(python3 - "${R_L}" "${R_K}" "${R_M}" <<'PYEOF'
import io,re,sys
bad=[]; total=0
for fp in sys.argv[1:]:
    for i,l in enumerate(io.open(fp,encoding='utf-8').read().split('\n'),1):
        # 候选 = ID 紧跟在 # 之后（`###A99 ·` / `### A99 ·`），
        # 不含「标题正文里恰好提到某条款 ID」的小节标题（那是正当写法，误红它就是惩罚正确实现）
        # ⚠️ 候选集**不许用 · 来识别**（2026-09-05 实测）：· 正是本判据要检查的格式的一部分，
        #    拿它当候选条件，「把 · 删掉」的不合格标题会直接掉出候选集 —— 判据永远看不见它。
        #    实测：删掉 D36 标题的 · ，[3a] 一声不吭（当时红的是 [3] 条数对账，理由完全不同，
        #    若改格式时条款数不变，就真漏了）。候选集只能靠**位置**特征（ID 紧跟 #），
        #    那是不属于被检查内容的东西。同 D35 的另一面：范围的**定义方式**让不合格者隐身。
        if not re.match(r'^#+\s*[A-M]\d+(?:\s|\u00b7)', l): continue
        total+=1
        # 标准格式：### <ID> · <标题>
        if not re.match(r'^### [A-M]\d+ \u00b7 \S', l):
            bad.append('%s:%d %s'%(fp.rsplit('/',1)[-1], i, l[:46]))
# 条款内不许再出现同级 ### 标题：它会把条款截断，段内的 ⚠️例外/配套条款结构上脱离该条款
trunc=[]
for fp in sys.argv[1:]:
    inrule=False
    for i,l in enumerate(io.open(fp,encoding='utf-8').read().split('\n'),1):
        if re.match(r'^### [A-M]\d+ \u00b7 ', l): inrule=True; continue
        if re.match(r'^## ', l): inrule=False; continue
        if inrule and l.startswith('### '):
            trunc.append('%s:%d %s'%(fp.rsplit('/',1)[-1], i, l[:40])); inrule=False
# ⚠️ 这里**不许用 elif 串起来**（2026-09-05 实测）：trunc 与 bad 是两类独立缺陷，
# 用 elif 时只报排在前面的那一类，另一类被完全吞掉 —— 修的人只会去修被报出来的那个，
# 要再跑一轮才发现还有另一个（同 **A19**：几种不同的「没过」压成一句话）。
# 实测：把一条条款标题的 · 删掉，两类同时成立，而门禁只说「截断」，一个字都没提格式。
probs=[]
if trunc: probs.append('%d 处同级 ### 标题把条款截断（段内配套条款会结构性脱离）: %s'%(len(trunc),'; '.join(trunc[:3])))
if bad:   probs.append('%d 行长得像条款标题但格式不合规（会静默不被计数）: %s'%(len(bad),'; '.join(bad[:3])))
if total < 50:
    print('UNABLE 只扫到 %d 行疑似条款标题，低于下限 50 —— 是解析坏了'%total)
elif probs:
    print('FAIL '+' | '.join(probs))
else:
    print('PASS %d 行条款标题格式合规，且无条款被同级标题截断'%total)
PYEOF
)"
  case "${hdr_out}" in
    PASS*)   pass "${hdr_out#PASS }" ;;
    UNABLE*) unable "${hdr_out#UNABLE }" ;;
    *)       fail  "${hdr_out#FAIL }" ;;
  esac
fi
echo

# ---------- 3a2. 组内索引闭世界 ----------
echo "[3a2] 组内索引"
if ! command -v python3 >/dev/null 2>&1; then
  unable "没有 python3，组内索引检查没能执行"
else
  idx_out="$(python3 - "${R_L}" <<'PYEOF'
import io,re,sys
s=io.open(sys.argv[1],encoding='utf-8').read()
probs=[]; groups=0; covered=0
for g in 'ABCDEFGHIJ':
    m=re.search(r'IDX:%s:BEGIN(.*?)IDX:%s:END'%(g,g), s, re.S)
    ids=set(re.findall(r'^### (%s\d+) \u00b7 '%g, s, re.M))
    if not m:
        if len(ids)>8: probs.append('%s 组 %d 条但没有组内索引'%(g,len(ids)))
        continue
    groups+=1
    # 只认**可见形态**：索引是给人导航的，藏进 HTML 注释里的条目读者看不到。
    # 先剥掉完整注释段，再从残留的未闭合 <!-- 处截断（END 标记本身会带来一个）。
    body=re.sub(r'<!--.*?-->','',m.group(1),flags=re.S)
    if '<!--' in body: body=body[:body.index('<!--')]
    listed=set(re.findall(r'\*\*(%s\d+)\*\*'%g, body))
    covered+=len(listed)
    miss=ids-listed; extra=listed-ids
    if miss: probs.append('%s 组索引漏了 %s'%(g,sorted(miss)))
    if extra: probs.append('%s 组索引列了不存在的 %s'%(g,sorted(extra)))
if groups==0: print('UNABLE 一个组内索引都没解析到')
elif probs: print('FAIL '+'; '.join(probs))
else: print('PASS %d 个组内索引闭世界，共覆盖 %d 条'%(groups,covered))
PYEOF
)"
  case "${idx_out}" in
    PASS*)   pass "${idx_out#PASS }" ;;
    UNABLE*) unable "${idx_out#UNABLE }" ;;
    *)       fail  "${idx_out#FAIL }" ;;
  esac
fi
echo

# ---------- 3b. 【必须】档闭世界（Z3）----------
echo "[3b] 【必须】档"
if ! command -v python3 >/dev/null 2>&1; then
  unable "没有 python3，【必须】档检查没能执行"
else
  must_out="$(python3 - "${SKILL}" "${R_L}" "${R_K}" "${R_M}" <<'PYEOF'
import io,re,sys
s=io.open(sys.argv[1],encoding='utf-8').read()
try:
    seg=s[s.index('MUST:BEGIN'):s.index('MUST:END')]
except ValueError:
    # 文件可读却没有标记块 = 清单没了，是**不合格**，不是「没能测」。
    # A1：UNABLE 只留给真的没能执行；把不合格洗成 UNABLE 会让它既不计红也不阻断。
    print('FAIL SKILL.md 可读但找不到 MUST:BEGIN/END 标记块 —— 清单缺失'); raise SystemExit
m=re.search(r'### 【必须】(\d+) 条', s)
declared=int(m.group(1)) if m else -1
ids=re.findall(r'[*][*]([A-M][0-9]+)[*][*]', seg)
real=set()
for fp in sys.argv[2:]:
    real |= set(re.findall(r'^### ([A-M][0-9]+) [\u00b7] ', io.open(fp,encoding='utf-8').read(), re.M))
probs=[]
if declared!=len(ids): probs.append('声明 %d 条，实际列出 %d 条'%(declared,len(ids)))
miss=[i for i in ids if i not in real]
if miss: probs.append('列了不存在的条款: %s'%miss)
dup=sorted({i for i in ids if ids.count(i)>1})
if dup: probs.append('重复列出: %s'%dup)
if len(ids)<5: probs.append('只列出 %d 条，低于下限 5 —— 是解析坏了'%len(ids))
print(('FAIL '+'; '.join(probs)) if probs else 'PASS 【必须】%d 条全部存在、无重复'%len(ids))
PYEOF
)"
  case "${must_out}" in
    PASS*)   pass "${must_out#PASS }" ;;
    UNABLE*) unable "${must_out#UNABLE }" ;;
    *)       fail  "${must_out#FAIL }" ;;
  esac
fi
echo

# ---------- 4. 场景索引必须覆盖全部十组 ----------
echo "[4] 场景索引覆盖"
# ⚠️ 2026-09-05 修：旧版用 `grep '^### J[0-9]+ ·' SKILL.md` 判断该组是否存在 ——
#    而条款根本不在 SKILL.md 里（在 references/），于是**每组都 continue，循环体一次都没跑过**。
#    实测：把索引表里全部十个组级入口删光，它照样报「十组均可达」。
#    典型的 D20/D31：一道从没执行过断言的门，和一道不存在的门，在结果里完全一样。
#    两处一起修：①组的存在性读 references；②只在**场景索引那一段**里找，不在全文找。
_idx="$(sed -n '/## 怎么用：按「你现在在写什么」翻/,/^# 提交前自检/p' "${SKILL}")"
_ng=0; missing_g=""
for g in A B C D E F G H I J; do
  ${GREP} -qE "^### ${g}[0-9]+ [·‧]" "${R_L}" || continue
  _ng=$((_ng+1))
  printf '%s' "${_idx}" | ${GREP} -qE '\*\*'"${g}"'\*\*' || missing_g="${missing_g} ${g}"
done
if [ "${_ng}" -lt 10 ]; then
  unable "只认出 ${_ng} 个承重层分组（应为 10）—— 是解析坏了，不是索引没问题"
elif [ -z "${missing_g}" ]; then
  pass "十组在场景索引表中均可达（组级入口逐个查过，不是在全文里碰运气）"
else
  fail "以下组没有出现在场景索引表里，读者翻不到:${missing_g}"
fi
echo
echo "[5] 来源清单（两表分列 + 零重叠）"
if ! command -v python3 >/dev/null 2>&1; then
  unable "没有 python3，来源分表检查没能执行"
else
  src_out="$(python3 - "${SOURCES}" <<'PYEOF'
import io,re,sys
d=io.open(sys.argv[1],encoding='utf-8').read()
# D37 做法5：段落锚点必须**恰好命中一次**，否则 .index 取第一处会静默错位
# （不只挡「0 次找不到」，更挡「多处取错第一个」——后者 try/except ValueError 拦不住）
for _m in ('# 表一 ·','# 表二 ·','# 表三 ·'):
    _c=d.count(_m)
    if _c!=1:
        print('FAIL sources.md 里「%s」出现 %d 次（必须恰好 1 次）—— 锚点不唯一，.index 会取错第一处静默错位（D37 做法5）'%(_m,_c)); raise SystemExit
i1=d.index('# 表一 ·'); i2=d.index('# 表二 ·'); i3=d.index('# 表三 ·')
pat=re.compile(r'https://github[.]com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)')
t1=set(pat.findall(d[i1:i2])); t2=set(pat.findall(d[i2:i3])); t3=set(pat.findall(d[i3:]))
probs=[]
# 三方对账：**表头声明的数** == 实际行数 == 门禁期望。
# 实测 2026-09-05：此前只比对「实际行数 vs 门禁写死的常数」，**从不读表头那个数字** ——
# 把「# 表二 · 30 个」改成 77，门禁 rc=0 毫无反应（E7：讲自己是什么的那段没人校验）。
for nm,t,exp in (('表一',t1,50),('表二',t2,30),('表三',t3,19)):
    if len(t)!=exp: probs.append('%s 实际 %d 个，门禁期望 %d'%(nm,len(t),exp))
    dm=re.search(r'# %s · (\d+) '%nm, d)
    if not dm: probs.append('%s 表头缺「N 个」的声明'%nm)
    elif int(dm.group(1))!=exp: probs.append('%s 表头声称 %s 个，实际 %d 个'%(nm,dm.group(1),exp))
for x,y,nm in ((t1,t2,'一二'),(t1,t3,'一三'),(t2,t3,'二三')):
    if x&y: probs.append('表%s重叠: %s'%(nm,sorted(x&y)))
u=t1|t2|t3
if not probs and len(u)!=99: probs.append('合计唯一 %d，应为 99'%len(u))
print(('FAIL '+'; '.join(probs)) if probs else 'PASS 表一 %d + 表二 %d + 表三 %d = %d 唯一，三表零重叠'%(len(t1),len(t2),len(t3),len(u)))
PYEOF
)"
  case "${src_out}" in
    PASS*)   pass "${src_out#PASS }" ;;
    UNABLE*) unable "${src_out#UNABLE }" ;;
    *)       fail  "${src_out#FAIL }" ;;
  esac
fi
echo

# ---------- 6. 源文件漂移（不算错，但要提示复核）----------
echo "[6] 反推源漂移"
if [ "${SRC_OK}" = 1 ]; then
  rec=$(${GREP} -oE '`[0-9a-f]{16}`' "${DERIV}" | head -1 | tr -d '`' || true)
  now=$(shasum -a 256 "${SRC}" | cut -c1-16)
  if [ -z "${rec:-}" ]; then unable "derivation.md 里没记录源文件哈希，无法判断是否漂移"
  elif [ "${rec}" = "${now}" ]; then pass "源文件未变: ${now}"
  else
    echo "  NOTE   源文件已变化：推导时 ${rec} -> 现在 ${now}"
    echo "         不算错。但这份推导需要按 four-node-review 的「逃逸缺陷回流」复核一遍。"
    pass "漂移已如实标注（非阻断）"
  fi
  # 落后量：从源文件真数，不信 derivation.md 自己声称的总数（J1 自洽不算数）
  # ⚠️ 2026-09-10（codex P1-21）：此前只取**最大编号**当总数 —— 删掉第 50 条、或把两条都写成 50，
  #    只要最大值没变，就会继续报「全部」。改为先断言编号唯一且连续，再用条数当总数。
  _srcnum=$(SRC="${SRC}" python3 - <<'SRCEOF'
import io,os,re
ids=[int(x) for x in re.findall(r'^(\d+)\. \*\*', io.open(os.environ['SRC'],encoding='utf-8').read(), re.M)]
if not ids: print('\t'); raise SystemExit
mx=max(ids); miss=sorted(set(range(1,mx+1))-set(ids))
print('%d\t%s'%(mx, ','.join(map(str,miss[:5]))))
SRCEOF
)
  src_max="${_srcnum%%	*}"; _srcmiss="${_srcnum#*	}"
  [ -n "${_srcmiss}" ] && echo "  NOTE   源文件铁律编号有空洞（缺 ${_srcmiss}…）—— 只按最大号当总数会把删号读成没删"

  dec_total=$(${GREP} -oE '\| 源文件铁律总数 \| [0-9]+ \|' "${DERIV}" | ${GREP} -oE '[0-9]+' | head -1 || true)
  if [ -z "${src_max:-}" ] || [ -z "${dec_total:-}" ]; then
    unable "没能数出源文件铁律总数或推导声称总数，落后量未知"
  elif [ "${src_max}" = "${dec_total}" ]; then
    pass "推导覆盖到源文件的全部 ${src_max} 条铁律"
  elif [ "${src_max}" -gt "${dec_total}" ]; then
    echo "  NOTE   源文件现有 ${src_max} 条铁律，本推导只覆盖到 ${dec_total} 条 ⇒ 落后 $(( src_max - dec_total )) 条"
    echo "         非阻断（源文件在持续演进），但复核时先看这 $(( src_max - dec_total )) 条。"
    pass "落后量已量化并标注（非阻断）"
  else
    fail "推导声称覆盖 ${dec_total} 条，而源文件只有 ${src_max} 条 —— 声称大于事实"
  fi
else
  unable "跳过漂移检查（源不可读）"
  # A7：缺席必须留痕 —— 落后量这一项也没能跑，必须显式报，否则本组条数会静默少一条，
  #     而 [9] 会把这个合法的 UNABLE 状态误判成 FAIL（A15）
  unable "跳过落后量核对（源不可读）"
fi
echo

# ---------- 7. 铁律覆盖分区必须闭合（B10 闭世界对账）----------
echo "[7] 铁律覆盖分区"
if ! command -v python3 >/dev/null 2>&1; then
  unable "没有 python3，分区闭合检查没能执行"
else
  part_out="$(python3 - "${DERIV}" <<'PYEOF'
import io,re,sys
d=io.open(sys.argv[1],encoding='utf-8').read()
# D37 做法5：段落锚点必须恰好命中一次，否则 .index 取第一处静默错位
for _m in ('## 十组的推导逻辑','## 哪些机制**没有**被反推进来'):
    if d.count(_m)!=1:
        print('FAIL derivation.md 里「%s」出现 %d 次（必须恰好 1 次）—— 锚点不唯一，组表边界会错位（D37 做法5）'%(_m,d.count(_m))); raise SystemExit
seg=d[d.index('## 十组的推导逻辑'):d.index('## 哪些机制**没有**被反推进来')]
ref=set()
for m in re.finditer(r'铁律\s*([0-9]+(?:/[0-9]+)*)', seg):
    ref.update(int(x) for x in m.group(1).split('/'))
m=re.search(r'逐条点名（(\d+) 条）\*{0,2}：铁律\s*([0-9\-–、]+)', d)
if not m:
    print('UNABLE 找不到排除清单'); raise SystemExit
exc=set()
for part in re.split(r'、', m.group(2)):
    part=part.strip()
    r=re.match(r'^(\d+)[-–](\d+)$', part)
    if r: exc.update(range(int(r.group(1)), int(r.group(2))+1))
    elif part.isdigit(): exc.add(int(part))
total=re.search(r'\| 源文件铁律总数 \| (\d+) \|', d)
N=int(total.group(1)) if total else 0
declared=re.search(r'反推出准则的铁律 \| \*\*(\d+) 条\*\*', d)
D=int(declared.group(1)) if declared else -1
claimed_exc=int(m.group(1))
# 第三个桶：待回流。落后量必须进分区对账，不能只当脚注 —— 否则「诚实边界」少说了一整类。
dfr=set(); claimed_dfr=0
md=re.search(r'待回流点名（(\d+) 条）\*{0,2}：(?:铁律\s*([0-9\-\u2013\u3001]+)|\u65e0)', d)
if md:
    claimed_dfr=int(md.group(1))
    for part in re.split(r'\u3001', md.group(2) or ''):
        part=part.strip()
        r=re.match(r'^(\d+)[-\u2013](\d+)$', part)
        if r: dfr.update(range(int(r.group(1)), int(r.group(2))+1))
        elif part.isdigit(): dfr.add(int(part))
probs=[]
if len(ref)!=D: probs.append('声明反推 %d 条，组表实际引用 %d 条'%(D,len(ref)))
if len(exc)!=claimed_exc: probs.append('声明排除 %d 条，清单实际 %d 条'%(claimed_exc,len(exc)))
if md and len(dfr)!=claimed_dfr: probs.append('声明待回流 %d 条，清单实际 %d 条'%(claimed_dfr,len(dfr)))
for na,a,nb,b in (('反推',ref,'排除',exc),('反推',ref,'待回流',dfr),('排除',exc,'待回流',dfr)):
    if a & b: probs.append('%s与%s有重叠: %s'%(na,nb,sorted(a&b)))
if N and (ref|exc|dfr)!=set(range(1,N+1)):
    miss=set(range(1,N+1))-(ref|exc|dfr)
    extra=(ref|exc|dfr)-set(range(1,N+1))
    if miss: probs.append('未被任何一桶覆盖的铁律: %s'%sorted(miss))
    if extra: probs.append('点名了源文件里不存在的铁律: %s'%sorted(extra))
print(('FAIL '+'; '.join(probs)) if probs else
      'PASS 反推 %d + 排除 %d + 待回流 %d = %d，三桶互斥、并集完整'%(len(ref),len(exc),len(dfr),N))
PYEOF
)"
  case "${part_out}" in
    PASS*)   pass "${part_out#PASS }" ;;
    UNABLE*) unable "${part_out#UNABLE }" ;;
    *)       fail  "${part_out#FAIL }" ;;
  esac
fi
echo

# ---------- 8. 退出码语义自核（A15：声明不许比实际粗）----------
echo "[8] 退出码语义"
_decl=$(${GREP} -oE '^#   [0-9] = ' "${BASH_SOURCE[0]}" | ${GREP} -oE '[0-9]' | sort -u | tr '\n' ' ')
_used=$(${GREP} -oE '(^|[^0-9])exit [0-9]+' "${BASH_SOURCE[0]}" | ${GREP} -oE '[0-9]+$' | sort -u | tr '\n' ' ')
if [ -z "${_decl// /}" ]; then
  unable "文件头没解析出退出码声明"
elif [ "${_decl}" = "${_used}" ]; then
  pass "退出码声明 = 实际使用（${_used% })"
else
  fail "退出码声明与实际不符：声明 [${_decl% }]，实际 [${_used% }] —— 声明比实际粗会让调用方读错结论（A15）"
fi
echo

# ---------- 9. 门禁自述与自身实际对账（D23：累计量的判据必须跑在累计完成之后 —— 本条必须是最后一条）（H10：写规则的人正在犯它，交给机器守）----------
echo "[8b] 条款→判据夹具对（行为夹具，非源码正则）"
_fx="$(dirname "${BASH_SOURCE[0]}")/rule-fixtures.sh"
if [ ! -r "${_fx}" ]; then
  unable "夹具 runner 不存在（${_fx}），本项没能验"
else
  _fo="$(bash "${_fx}" 2>&1)"; _frc=$?
  _fp=$(printf '%s' "${_fo}" | ${GREP} -oE 'PASS=[0-9]+' | ${GREP} -oE '[0-9]+' || true)
  case "${_frc}" in
    0) if [ "${_fp:-0}" -ge 10 ]; then
         pass "夹具对全绿（${_fp} 项断言，5 条准则 × 违反/遵守双向）"
       else
         fail "夹具 runner 报 PASS 但断言数只有 ${_fp:-0}（下限 10）—— 见 A3"
       fi ;;
    3) unable "夹具 runner 报 UNABLE：$(printf '%s' "${_fo}" | ${GREP} -c '^  UNABLE' || true) 条没能验" ;;
    1) fail "夹具对有失败：$(printf '%s' "${_fo}" | ${GREP} '^  FAIL' | head -3 | tr '\n' ';')" ;;
    *) fail "夹具 runner 内部错误 rc=${_frc}" ;;
  esac
fi
echo

echo "[10] 基础层 P / 权威层 Z 承重（此前两层零判据，D20 实测：整段清空全绿）"
# 10a 单源：MUST 标记块全库有且仅有一处（I2 / B19，被害者是文档自己）
# 用 find -L 显式枚举（跟随软链），不依赖 grep -r 的遍历语义
# 与 D5 同一纪律：用绝对路径，不依赖 PATH（缺 find 时会把「清单没了」这种假红说出口）
# 可覆盖：写死就没法给「扫描没跑成」这条分支做阳性对照（F3：配置外置不只是别写死值，
# 是能不能测）。2026-09-05 实测：写死时 `FIND=/nonexistent bash selfcheck.sh` 毫无效果，
# 判据照报 PASS —— 我一度以为是判据坏了，其实是**探针打错了靶子**（D36 第③类）。
FIND=${FIND:-/usr/bin/find}
[ -x "${FIND}" ] || FIND=find
_nmust=$(${FIND} -L "${SKILL_DIR}" -name '*.md' -type f -exec ${GREP} -l '<!-- MUST:BEGIN' {} + 2>/dev/null | ${GREP} -c . || true)
if [ "${_nmust:-0}" -eq 1 ]; then
  pass "【必须】清单单源（全库 1 处 MUST 标记块）"
elif [ "${_nmust:-0}" -eq 0 ]; then
  fail "全库找不到 MUST 标记块 —— 清单没了，不是「没能测」"
else
  fail "【必须】清单有 ${_nmust} 份拷贝 —— 必然漂移一份（I2 单源 / B19）"
fi

# 10b F 层：四个小节齐 + 要点数下限（下限取当前值的约 8 折，防的是整段消失，不是防小改）
_fz="$(python3 - "${R_F}" "${R_Z}" <<'PYEOF'
import io,re,sys
f=io.open(sys.argv[1],encoding='utf-8').read(); z=io.open(sys.argv[2],encoding='utf-8').read()
p=[]
secs=re.findall(r'^## (P\d)\b', f, re.M)
for w in ['P0','P1','P2','P3']:
    if w not in secs: p.append('基础层 P 缺小节 '+w)
def seg(t,a,b):
    m=re.search(r'^## %s\b(.*?)(?=^## %s\b|\Z)'%(a,b), t, re.S|re.M)
    return m.group(1) if m else ''
n1=len(re.findall(r'^- ', seg(f,'P1','P2'), re.M))
n3=len(re.findall(r'^\| ', seg(f,'P3','ZZZ'), re.M))
if n1<20: p.append('P1 共识条款只剩 %d 条（下限 20）'%n1)
if n3<12: p.append('P3 修正表只剩 %d 行（下限 12）'%n3)
zs=re.findall(r'^## (Z\d)\b', z, re.M)
for w in ['Z1','Z2','Z3']:
    if w not in zs: p.append('Z 层缺小节 '+w)
# Z1 阈值：写死具体数值，静默改动即报（J1 事实性数据）。
# ⚠️ 2026-09-10（codex P1-24）：此前只守 LCP/INP/CLS 的 **good** 值 ——
#    poor 阈值和 FCP/TTFB 改成任意数字都照样 PASS。五行两列全守。
for k,good,poor in [('LCP','2500 ms','4000 ms'),('INP','200 ms','500 ms'),('CLS','0.1','0.25'),
                    ('FCP','1800 ms','3000 ms'),('TTFB','800 ms','1800 ms')]:
    m=re.search(r'^\|\s*\*\*%s\*\*[^|]*\|([^|]*)\|([^|]*)\|'%k, z, re.M)
    if not m: p.append('Z1 少了 %s 那一行'%k); continue
    g,b=m.group(1).replace('*','').strip(), m.group(2).replace('*','').strip()
    if g!=good or b!=poor: p.append('Z1 %s 阈值对不上：实得 good=%s / poor=%s（应为 %s / %s）'%(k,g,b,good,poor))
apis=set(re.findall(r'\*\*API(\d+)\*\*', z))
missing=[i for i in map(str,range(1,11)) if i not in apis]
if missing: p.append('Z2 OWASP 缺 API%s'%','.join(missing))
print(('FAIL '+'; '.join(p)) if p else 'PASS 基础层 P 四节齐（P1 %d 条 / P3 %d 行）· Z 层三节齐（Z1 五行 good/poor 两列全对 + OWASP 10 条）'%(n1,n3))
PYEOF
)"
case "${_fz}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_fz#PASS }" ;;
  UNABLE*) unable "${_fz#UNABLE }" ;;
  FAIL*) fail "${_fz#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_fz}" ;;
esac

# 10c 总条数单源：SKILL.md 里**只有一处**写总数，且必须等于 L+K+M 实际
# 实测 2026-09-05：此前散落 5 处手写总数（127/108/120 三个不同的值），全部过期。
_tot="$(python3 - "${SKILL}" "${R_L}" "${R_K}" "${R_M}" <<'PYEOF'
import io,re,sys
t=io.open(sys.argv[1],encoding='utf-8').read()
real=sum(len(re.findall(p, io.open(f,encoding='utf-8').read(), re.M))
         for f,p in zip(sys.argv[2:5], [r'^### [A-J]\d+ ', r'^### K\d+ ', r'^### M\d+ ']))
m=re.findall(r'全部 (\d+) 条完整条款', t)
if len(m)==0:
    print('FAIL SKILL.md 里找不到「全部 N 条完整条款」的总数声称')
elif len(m)>1:
    print('FAIL 总数被写了 %d 处（应单源，否则必然漂移一处）'%len(m))
elif int(m[0])!=real:
    print('FAIL 总数声称 %s 条，实际 L+K+M = %d 条'%(m[0],real))
else:
    print('PASS 总条数单源且对账一致（%d 条 = 承重 + K + M）'%real)
PYEOF
)"
case "${_tot}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_tot#PASS }" ;;
  UNABLE*) unable "${_tot#UNABLE }" ;;
  FAIL*) fail "${_tot#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_tot}" ;;
esac

# 10d 交叉引用闭世界：被引用的条款号必须真的存在
# 「反推过程中被修正的初稿（留痕）」一节是**历史记录**，会提到已被合并/删除的旧编号，故整节跳过。
_xref="$(python3 - "${SKILL_DIR}" <<'PYEOF'
import io,re,sys,glob,os,collections
d=sys.argv[1]
files=[os.path.join(d,'SKILL.md')]+sorted(glob.glob(os.path.join(d,'references','*.md')))
exist=set(); texts={}
for f in files:
    s=io.open(f,encoding='utf-8').read(); texts[f]=s
    # L 是层名（承重层 L），不是条款前缀；ASVS 的 L1/L2/L3 会撞形，故排除
    exist|=set(re.findall(r'^#{2,3} ([A-KMPZ]\d+) [·‧]', s, re.M))
if len(exist)<100:
    print('UNABLE 只解析到 %d 个条款号（下限 100）——是解析坏了'%len(exist)); raise SystemExit
# 裸写也要抓：表格里 "I4 接缝、I5 作用域" 这种此前整批漏过（观测面太窄，B12）
    # ⚠️ 这行注释本身 2026-09-05 被扫出写过一个不存在的 I6（I 组只到 I5）——
    #    **讲「抓漏引用」的注释里自己写了个漏引用**。不做成判据：占位符（A99）与
    #    ASVS 等级（L1/L2/L3）都会撞形，排除规则比收益脆弱（E7 做法 3：别为它养一道门）。
pat=re.compile(r'(?<![A-Za-z0-9])([A-KMPZ]\d{1,2})(?![A-Za-z0-9])')
# ⚠️ 2026-09-10（codex P1-22）：豁免此前写成 `body = r.split(body)[0]` ——
#    那是**从匹配处砍掉整个尾巴**，不是删掉豁免段。foundation.md 第 3 行正是改名标记，
#    于是该文件 122 行里**只有 3 行**进过检查，而判据照报「全部指得到」。
#    改为只挖掉豁免段本身，并**把跳过了多少行报出来**（A4：截断必须跟着数据走到消费方）。
SKIP=(re.compile(r'^## 反推过程中被修正的初稿.*?(?=^## |\Z)', re.M|re.S),  # 历史留痕：按定义会提已删编号
      re.compile(r'^> ⚠️ \*\*2026-09-05 改名\*\*(?:.*\n)(?:>.*\n)*', re.M))  # 改名说明本身要写旧编号
bad=collections.defaultdict(list); n_skip=0
for f,s in texts.items():
    body=s
    for r in SKIP:
        body2=r.sub(lambda m:'\n'*m.group(0).count('\n'), body)   # 用等量空行占位，保住行号
        n_skip+=body.count('\n')-body2.count('\n')+sum(1 for _ in r.finditer(body))*0
        body=body2
    for n,line in enumerate(body.split('\n'),1):
        for m in pat.finditer(line):
            if m.group(1) not in exist: bad[m.group(1)].append('%s:%d'%(os.path.basename(f),n))
n_lines=sum(t.count('\n')+1 for t in texts.values())
if bad:
    print('FAIL 引用了不存在的条款：'+'; '.join('%s(%d次,例 %s)'%(k,len(v),v[0]) for k,v in sorted(bad.items())))
else:
    print('PASS 交叉引用闭世界：%d 个条款号，扫过 %d 行（两处历史留痕豁免段已挖空，行号未移位），含裸写形态，全部指得到'%(len(exist),n_lines))
PYEOF
)"
case "${_xref}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_xref#PASS }" ;;
  UNABLE*) unable "${_xref#UNABLE }" ;;
  FAIL*) fail "${_xref#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_xref}" ;;
esac

# 10f 【必须】档必须从**给人用的**场景索引到达
# 实测 2026-09-05：本轮新增的 8 条准则全部进了机器可读的组内索引（有门禁守），
# 却一条都没进场景索引 —— 而后者是本文自己说的「唯一真正会被翻开的入口」。
_nav="$(python3 - "${SKILL}" <<'NAVEOF'
import io,re,sys
t=io.open(sys.argv[1],encoding='utf-8').read()
# D37 做法5：中文标题锚点必须恰好命中一次（MUST 标记是结构标记、唯一性另由 [10] 守，仍走 try 挡缺失）
for _m in ('## 怎么用：按「你现在在写什么」翻','# 提交前自检'):
    if t.count(_m)!=1:
        print('FAIL SKILL.md 里「%s」出现 %d 次（必须恰好 1 次）—— 锚点不唯一，场景索引段会错位（D37 做法5）'%(_m,t.count(_m))); raise SystemExit
try:
    idx=t[t.index('## 怎么用：按「你现在在写什么」翻'):t.index('# 提交前自检')]
    must=re.findall(r'\*\*([A-KMPZ]\d+)\*\*', t[t.index('MUST:BEGIN'):t.index('MUST:END')])
except ValueError:
    print('FAIL 找不到场景索引或 MUST 标记块 —— 结构缺失，不是没能测'); raise SystemExit
if len(must)<10:
    print('UNABLE 只解析到 %d 条【必须】（下限 10）'%len(must)); raise SystemExit
byid=set(re.findall(r'\*\*([A-KMPZ]\d{1,2})\*\*', idx))      # 逐条点名
bygrp=set(re.findall(r'\*\*([A-KMPZ])\*\*\s', idx))          # 组级入口，如「**A** 自陈述诚实性」
un=sorted({m for m in must if m not in byid and m[0] not in bygrp})
if un:
    print('FAIL 【必须】档有 %d 条从场景索引到不了：%s —— 加了等于没加（索引是给人用的唯一入口）'%(len(un),un))
else:
    print('PASS 【必须】%d 条全部可从场景索引到达（逐条点名 %d 个 + 组级入口 %s）'%(len(must),len(byid),''.join(sorted(bygrp))))
NAVEOF
)"
case "${_nav}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_nav#PASS }" ;;
  UNABLE*) unable "${_nav#UNABLE }" ;;
  FAIL*) fail "${_nav#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_nav}" ;;
esac

# 10g frontmatter 的 description 也要对账
# 它是这个 skill 被加载时**唯一会被读到的那段文字**（模型据它判断要不要加载），
# 而实测 2026-09-05：里面四个数字随便改成 900/99/77/12，门禁一律全绿。
_fm="$(python3 - "${SKILL}" "${R_L}" "${R_K}" "${R_M}" <<'FMEOF'
import io,re,sys
sk=io.open(sys.argv[1],encoding='utf-8').read()
nl=len(re.findall(r'^### [A-J]\d+ [·‧]', io.open(sys.argv[2],encoding='utf-8').read(), re.M))
nk=len(re.findall(r'^### K\d+ [·‧]',  io.open(sys.argv[3],encoding='utf-8').read(), re.M))
nm=len(re.findall(r'^### M\d+ [·‧]',  io.open(sys.argv[4],encoding='utf-8').read(), re.M))
try:
    fm=sk[sk.index('description:'):sk.index('\n---',sk.index('description:'))]
except ValueError:
    print('FAIL frontmatter 里找不到 description —— 结构缺失'); raise SystemExit
nmust=len(re.findall(r'\*\*([A-KMPZ]\d+)\*\*', sk[sk.index('MUST:BEGIN'):sk.index('MUST:END')]))
# 仓库数**不再**在 frontmatter 复述（2026-09-09 codex 7.2：来源规模是宣传数字、不证明规则正确，
# 且长描述劣化路由）——其真相源单独在 [5]（sources.md 三表 50+30+19=99）守着，
# frontmatter 不再当它的第 N 份拷贝（E7：讲自己是什么的数字只留一处，多一处必静默漂移）。
checks=[('承重层',      r'承重层 (\d+) 条由终审', nl),
        ('AI 协作层',   r'AI 协作层 (\d+) 条',     nk),
        ('交付层',      r'交付层 (\d+) 条',        nm),
        ('【必须】',    r'含【必须】(\d+) 条',     nmust)]
p=[]
for name,pat,want in checks:
    mm=re.search(pat, fm)
    if not mm: p.append('description 里找不到「%s N 条」'%name)
    elif int(mm.group(1))!=want: p.append('%s 声称 %s，实际 %d'%(name,mm.group(1),want))
# 2026-09-06：五层表是同一批数字的**第三份拷贝**（frontmatter/总数行之外），
# 实测它停在 123 而真值 128、三桶细目停在两轮前 —— 没盖到的拷贝必然静默漂移（E7）。
for name,pat,want in [('五层表·承重层', r'\| \*\*承重层 L\*\*（A–J） \| (\d+) \|', nl),
                      ('五层表·K 层',   r'\| \*\*AI 协作层 K\*\* \| (\d+) \|',    nk),
                      ('五层表·M 层',   r'\| \*\*交付层 M\*\* \| (\d+) \|',       nm)]:
    mm=re.search(pat, sk)
    if not mm: p.append('SKILL.md 找不到「%s」那行（表结构变了要同步改本判据）'%name)
    elif int(mm.group(1))!=want: p.append('%s 写 %s，实际 %d'%(name,mm.group(1),want))
print(('FAIL '+'; '.join(p)) if p else
      'PASS frontmatter description 四项数字与实际一致（承重%d/K%d/M%d/必须%d），五层表 L/K/M 同值'%(nl,nk,nm,nmust))
FMEOF
)"
case "${_fm}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_fm#PASS }" ;;
  UNABLE*) unable "${_fm#UNABLE }" ;;
  FAIL*) fail "${_fm#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_fm}" ;;
esac

# 10h ⭐ 与【必须】是两个正交的轴，且这件事必须被说出来
# 实测 2026-09-05：⭐ 这套记号全库从未被解释过，而它与【必须】视觉同类、含义不同，
# 且两轴有大量不一致（当初加这道门时约 47 处：15 条【必须】无星 + 32 条 ⭐⭐⭐ 按【应当】；随条数增长，现值以下方 PASS 行为准）⇒ 读者必然误读其一。
_ax="$(python3 - "${R_L}" "${SKILL}" "${R_K}" "${R_M}" <<'AXEOF'
import io,re,sys
lb=io.open(sys.argv[1],encoding='utf-8').read()
sk=io.open(sys.argv[2],encoding='utf-8').read()
k =io.open(sys.argv[3],encoding='utf-8').read()
m =io.open(sys.argv[4],encoding='utf-8').read()
if '## ⭐ 是什么意思' not in lb:
    print('FAIL 承重层顶部缺「⭐ 是什么意思」说明 —— ⭐ 与【必须】视觉同类而含义不同，不解释必被误读'); raise SystemExit
if '本层的 ⭐ 与承重层不是同一把尺' not in m:
    print('FAIL 交付层 M 顶部缺「本层 ⭐ 标的是后果严重度」的说明 —— 它的来源是清单条目而非事故记录'); raise SystemExit
stars={}
for txt in (lb,k,m):
    for mm in re.finditer(r'^### ([A-KM]\d+) [·‧](.*)$', txt, re.M):
        stars[mm.group(1)]=mm.group(2).count('⭐')
must=set(re.findall(r'\*\*([A-KMPZ]\d+)\*\*', sk[sk.index('MUST:BEGIN'):sk.index('MUST:END')]))
if len(must)<10 or len(stars)<100:
    print('UNABLE 只解析到【必须】%d 条 / 带星表 %d 条（下限 10 / 100）'%(len(must),len(stars))); raise SystemExit
nostar=len([r for r in must if stars.get(r,0)==0])
hi=len([r for r,n in stars.items() if n>=3 and r not in must])
p=[]
for name,pat,want in [('无星的【必须】', r'【必须】\d+ 条里有 (\d+) 条一颗星都没有', nostar),
                      ('按【应当】的 ⭐⭐⭐', r'另有 (\d+) 条 ⭐⭐⭐ 按【应当】', hi)]:
    mm=re.search(pat, sk)
    if not mm: p.append('SKILL.md 里找不到「%s」的数字'%name)
    elif int(mm.group(1))!=want: p.append('%s 声称 %s，实际 %d'%(name,mm.group(1),want))
mm=re.search(r'\*\*【必须】(\d+) 条里，(\d+) 条一颗星都没有\*\*', lb)
if not mm: p.append('承重层说明里找不到两轴数字')
elif int(mm.group(1))!=len(must) or int(mm.group(2))!=nostar:
    p.append('承重层说明称【必须】%s 条/无星 %s 条，实际 %d/%d'%(mm.group(1),mm.group(2),len(must),nostar))
mm2=re.search(r'\*\*(\d+) 条 ⭐⭐⭐ 不在【必须】档\*\*', lb)
if not mm2: p.append('承重层说明里找不到 ⭐⭐⭐ 数')
elif int(mm2.group(1))!=hi: p.append('承重层说明称 ⭐⭐⭐ 非必须 %s 条，实际 %d'%(mm2.group(1),hi))
print(('FAIL '+'; '.join(p)) if p else
      'PASS 两轴说明在场且四处数字一致（【必须】%d/无星 %d/⭐⭐⭐按应当 %d）'%(len(must),nostar,hi))
AXEOF
)"
case "${_ax}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_ax#PASS }" ;;
  UNABLE*) unable "${_ax#UNABLE }" ;;
  FAIL*) fail "${_ax#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_ax}" ;;
esac

# 10i Markdown 链接完整性
# 实测 2026-09-05：4 处文件链接多带了 references/ 前缀（在 references/ 里又写一遍），
# 12 处 [D20](#d20) 形式的锚点链接**全部跳不到**（GitHub 会把「### D20 · 防假绿的门… ⭐⭐⭐」
# 转成含中文与星号的长 slug）。读者点了没反应，而任何判据都不会报错。
_lk="$(python3 - "${SKILL_DIR}" <<'LKEOF'
import io,re,sys,glob,os
d=sys.argv[1]
files=[os.path.join(d,'SKILL.md')]+sorted(glob.glob(os.path.join(d,'references','*.md')))
if len(files)<5:
    print('UNABLE 只枚举到 %d 个 md 文件（下限 5）'%len(files)); raise SystemExit
badf=[]; bada=[]; total=0
for f in files:
    s=io.open(f,encoding='utf-8').read()
    for m in re.finditer(r'\[[^\]]*\]\(([^)\s]+)\)', s):
        t=m.group(1); total+=1
        if t.startswith('http'): continue
        if t.startswith('#'):
            # 标题含中文与 ⭐，GitHub 的 slug 不稳定 ⇒ 同文件内交叉引用一律用粗体，不用锚点链接
            bada.append('%s → %s'%(os.path.basename(f),t)); continue
        p=os.path.normpath(os.path.join(os.path.dirname(f), t.split('#')[0]))
        if not os.path.exists(p): badf.append('%s → %s'%(os.path.basename(f),t))
if total<20:
    print('UNABLE 只扫到 %d 个链接（下限 20）——是解析坏了'%total); raise SystemExit
p=[]
if badf: p.append('文件链接指向不存在的路径：%s'%'; '.join(badf[:5]))
if bada: p.append('存在 #锚点链接（标题含中文与 ⭐，slug 不稳定，一律改粗体）：%s'%'; '.join(bada[:5]))
print(('FAIL '+'; '.join(p)) if p else 'PASS 链接完整性：%d 个 inline 链接（`[x](path)` 形态）全部可达、无不稳定的 #锚点链接；尖括号目标/引用式链接/带括号目标未检查'%total)
LKEOF
)"
case "${_lk}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_lk#PASS }" ;;
  UNABLE*) unable "${_lk#UNABLE }" ;;
  FAIL*) fail "${_lk#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_lk}" ;;
esac

# 10i2 代码围栏配对
# 实测 2026-09-10：rules-load-bearing.md 里有**一个孤立的闭栏**（A4 那段散文末尾多写了一行 ```），
# 它把此后**整份文件的围栏奇偶性翻了个个儿** —— 最长的一段 812 行散文被渲染成代码块，
# 而 40 条门禁全绿：没有任何一条看的是「这份 Markdown 渲染出来是什么样」。
_fc="$(python3 - "${SKILL_DIR}" <<'FCEOF'
import io,re,sys,glob,os
d=sys.argv[1]
files=[os.path.join(d,'SKILL.md')]+sorted(glob.glob(os.path.join(d,'references','*.md')))
if len(files)<5:
    print('UNABLE 只枚举到 %d 个 md 文件（下限 5）'%len(files)); raise SystemExit
total=0; bad=[]
for f in files:
    # 三种形态各自成栈（2026-09-10 codex P1-23：此前只认列首三反引号，
    # 而本文里真实存在 `> ```（引用块内围栏）与最多三格缩进的形态 —— 看不见 = 声称超出量程）
    st={'top':[],'quote':[]}; b=os.path.basename(f)
    for i,l in enumerate(io.open(f,encoding='utf-8').read().split('\n'),1):
        kind='top'; t=l
        if re.match(r'^ {0,3}>[ ]?', t): kind, t = 'quote', re.sub(r'^ {0,3}>[ ]?','',t)
        t=re.sub(r'^ {1,3}','',t)
        if not (t.startswith('```') or t.startswith('~~~')): continue
        total+=1; k=st[kind]
        if k:
            # 闭栏不该带语言标签；带了就说明它其实是个开栏 ⇒ 前面漏了一个开栏（奇偶性已翻）
            if t.strip() not in ('```','~~~'): bad.append('%s:%d 闭栏带语言标签（说明前面漏了一个开栏）'%(b,i))
            k.pop()
        else:
            k.append(i)
    for kind,k in st.items():
        if k: bad.append('%s:%d 围栏未闭合（%s 层，此后整段会被渲染成代码块）'%(b,k[0],kind))
if total<10:
    print('UNABLE 只扫到 %d 个围栏（下限 10）——是解析坏了'%total); raise SystemExit
print(('FAIL 代码围栏配对：'+'; '.join(bad[:4])) if bad else 'PASS 代码围栏配对：%d 个围栏全部成对（含引用块内与缩进形态、~~~），语言标签只出现在开栏'%total)
FCEOF
)"
case "${_fc}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_fc#PASS }" ;;
  UNABLE*) unable "${_fc#UNABLE }" ;;
  FAIL*) fail "${_fc#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_fc}" ;;
esac

# 10j 薄入口有硬上限：SKILL.md 曾是 1700 行，拆薄后没有任何判据守着它别长回去
# （「慢慢长回去」不会让任何东西报错 —— G 组说的正是这种）
_max=350
_cur=$(${GREP} -c '' "${SKILL}" || echo 0)
_dec=$(${GREP} -oE '硬上限（([0-9]+) 行' "${SKILL}" | ${GREP} -oE '[0-9]+' | head -1 || true)
if [ -z "${_dec:-}" ]; then
  fail "SKILL.md 里找不到「硬上限（N 行」的声明 —— 上限必须写在文件里，否则读者不知道有这条约束"
elif [ "${_dec}" != "${_max}" ]; then
  fail "SKILL.md 声称上限 ${_dec} 行，门禁里写的是 ${_max} 行 —— 两处必须一致（E7）"
elif [ "${_cur}" -le "${_max}" ]; then
  pass "薄入口未超限（${_cur}/${_max} 行）"
else
  fail "SKILL.md ${_cur} 行，超过 ${_max} 行上限 —— 该往 references/ 拆了，别让它长回 1700 行"
fi

# 10k 本 skill 自己的脚本不许写死临时路径（C12 做法 1：修完一类立刻做成判据，
# 因为判据不区分「既有代码」和「你五分钟后写的代码」，而人的注意力区分）
# 实测 2026-09-05：precommit-guard 刚改成 mktemp，一轮后新写的 reverse-test.sh 又写死了 /tmp/xxx.out
_tmp_bad=$(${GREP} -nE '(>|>>|=)[[:space:]]*"?/tmp/[A-Za-z0-9_.-]+' "${SKILL_DIR}"/scripts/*.sh \
           | ${GREP} -v 'mktemp' | ${GREP} -v '^[^:]*:[0-9]*:[[:space:]]*#' || true)
_tmp_n=$(printf '%s' "${_tmp_bad}" | ${GREP} -c . || true)
# 顺带查不可见控制字符：用工具改写脚本时，`\b` 之类的转义会被解释成真正的控制字节写进文件，
# 它在编辑器和 grep 输出里**看不见**，却会静默改变正则语义（实测 2026-09-05：
# 两个 `\b` 变成退格字符，A14 的词边界失效 ⇒ 正向基线从 3 掉到 1）。
_ctl=0; _nsf=0
for _sf in "${SKILL_DIR}"/scripts/*.sh; do
  [ -f "${_sf}" ] || continue
  _nsf=$((_nsf+1))
  _n=$(tr -cd '\001-\010\013\014\016-\037' < "${_sf}" | wc -c | tr -d ' ')
  # $VAR 紧跟全角标点：bash 3.2 会把多字节字符连读进变量名，`set -u` 下直接崩。
  # 今天命中 4 次，**其中 3 次在告警路径上** —— 那正是最需要它说话的时刻（C12 做法 1：做成判据）。
  _fw=$(${GREP} -cE '\$[A-Za-z_][A-Za-z0-9_]*[（），、。：；「」]' "${_sf}" || true)
  [ "${_fw:-0}" -gt 0 ] && { _ctl=$((_ctl+_fw)); _tmp_bad="${_tmp_bad}
$(basename "${_sf}"): ${_fw} 处 \$VAR 紧跟全角标点（bash 3.2 会连读成变量名）"; }
  [ "${_n:-0}" -gt 0 ] && { _ctl=$((_ctl+_n)); _tmp_bad="${_tmp_bad}
$(basename "${_sf}"): ${_n} 个不可见控制字符"; }
done
# A3 的第二个数：判据自己筛完还剩几个。glob 没展开时循环体一次都不跑，
# 而 _tmp_n=0 且 _ctl=0 会让它直接报 PASS —— 与 [4] 同型（本轮普查同型时补上）。
if [ "${_nsf}" -lt 4 ]; then
  unable "只扫到 ${_nsf} 个脚本（下限 4）—— 是枚举坏了，不是脚本都干净"
elif [ "${_tmp_n:-0}" -eq 0 ] && [ "${_ctl}" -eq 0 ]; then
  pass "脚本卫生：扫过 ${_nsf} 个脚本，无写死临时路径、无不可见控制字符"
else
  fail "脚本卫生不合格（写死临时路径 ${_tmp_n} 处 / 控制字符 ${_ctl} 个）：$(printf '%s' "${_tmp_bad}" | head -2 | tr '\n' ' ')"
fi

# 10l 「闭环」是双向契约，判据分三档 —— 每档报**不同**的诊断（同一句话报三种病等于没分诊）
# 三档取自 case-05 的同源实践：只提不定权，链接就只是礼貌，不是契约。
# SYBuilder 把旧的外部仓库规范融合成内置 repository-enforcement 模块。
# 因此闭环检查直接读取随 coding-standards 一起发布的 PLAYBOOK；反向测试通过
# ENG_STD_SKILL 显式覆盖为临时副本，既能造反例，也不会改真实工作区。
_sib="${REPO_ENFORCEMENT}"; _sib_src="内置仓库执法模块"
# ⚠️ 三档是**三个独立缺陷**，不许串成 elif（2026-09-05 自查发现，改前正是 elif 链）：
#    串起来只会报排在最前的那一档，另外两档被完全吞掉 —— 而上一行注释明明写着
#    「每档报不同的诊断」。**设计写对了，实现没守住**（同 A19 / A20）。
_cc=()
if [ ! -r "${_sib}" ]; then
  unable "找不到 repository-enforcement/PLAYBOOK.md，回链检查没能执行"
else
  ${GREP} -q '上游正本是 `coding-standards`' "${_sib}" || _cc+=("① 链接缺失：仓库执法模块没有明确声明 coding-standards 是上游正本 —— 「闭环」是单向的，别这么写")
  ${GREP} -qE '(上游|正本|为准)' "${_sib}" || _cc+=("② 只提不定权：仓库执法模块提到了本 skill，却没写「以谁为准」—— 两套标准并存时人只会遵守更松的那套")
  ${GREP} -q '实然与应然的差距' "${SKILL}" || _cc+=("③ 把愿望写成了现状：本文缺少「实然与应然的差距」那段 —— 闭环目前只有部分接通，不许当成现状描述")
  # ④ 2026-09-06：那段「实然」描述自己也会漂移 —— product-flow 补了回链而本文停在「命中 0」。
  #    漂移方向是好消息也一样是过期描述。清单行是机器可比对的锚，与两个兄弟 skill 实测比对。
  _u4=""
  _claim_line="$(${GREP} -E '未接通清单（门禁 \[10l\] 与实际比对）：' "${SKILL}" | head -1 || true)"
  if [ -z "${_claim_line}" ]; then
    _cc+=("④ 找不到「未接通清单（门禁 [10l] 与实际比对）：」那行 —— 回链现状没有可比对的锚，下次漂移无人发现")
  else
    _claim_n="$(printf '%s' "${_claim_line#*：}" | tr '、,' '  ' | tr -s ' ' '\n' | ${GREP} -vE '^$|（无）' | sort | tr '\n' ' ' || true)"
    _actual=""; _unread=""
    for _n in four-node-review product-flow; do
      _p="${SKILL_DIR}/../${_n}/SKILL.md"
      if [ ! -r "${_p}" ]; then _unread="${_unread}${_n} "; continue; fi
      ${GREP} -q 'coding-standards' "${_p}" || _actual="${_actual}${_n} "
    done
    _actual_n="$(printf '%s' "${_actual}" | tr -s ' ' '\n' | ${GREP} -v '^$' | sort | tr '\n' ' ' || true)"
    if [ -n "${_unread}" ]; then
      _u4="没能读到 ${_unread}—— 回链状态未知，清单比对没能执行（A19：这不是「未接通」也不是「已接通」）"
    elif [ "${_claim_n}" != "${_actual_n}" ]; then
      _cc+=("④ 回链清单漂移：清单写[${_claim_n:-无}]，实测未接通[${_actual_n:-无}] —— 过期的实然描述和把愿望写成现状是同一种病")
    fi
  fi
  if [ "${#_cc[@]}" -gt 0 ]; then
    fail "$(printf '%s | ' "${_cc[@]}" | sed 's/ | $//')"
  elif [ -n "${_u4}" ]; then
    unable "${_u4}"
  else
    pass "闭环契约四档齐（有链接 · 定了权 · 实然段在场 · 未接通清单与实测一致）"
  fi
fi
[ -n "${_sib_head:-}" ] && rm -f "${_sib_head}"

# 10m 本 skill 自己的脚本必须遵守 A14/A16（累加器要追得到 exit；门的结论不许被分号旁路）
# ⭐ 它的**正向基线**就是 tests/fixtures 里的 violating 样本 —— 那三处必须被扫出来，
#    否则说明这把尺子根本不会开火（D4：对比型断言必须先有正向基线）。
_scan() {  # $1=模式 $2=文件
  ${GREP} -nE "$1" "$2" 2>/dev/null | ${GREP} -vE '^[0-9]+:[[:space:]]*#' || true
}
_bad=""; _base=0
for _f in "${SKILL_DIR}"/scripts/*.sh "${SKILL_DIR}"/tests/fixtures/*/*.sh; do
  [ -f "${_f}" ] || continue
  _hit=""
  [ -n "$(_scan '^[[:space:]]*(gate|check|verify)[a-z_]*[[:space:]]*;[[:space:]]*[^ ]' "${_f}")" ] && _hit="A16"
  _acc=$(${GREP} -cE '^[^#]*\b(fail|fails|failures)[a-z_]*=\$\(\(' "${_f}" || true)
  _ex=$(${GREP} -cE '\bexit [0-9]' "${_f}" || true)
  [ "${_acc:-0}" -gt 0 ] && [ "${_ex:-0}" -eq 0 ] && _hit="${_hit}A14"
  case "${_f}" in
    */violating.sh) [ -n "${_hit}" ] && _base=$((_base+1)) ;;
    *) [ -n "${_hit}" ] && _bad="${_bad} $(basename "$(dirname "${_f}")")/$(basename "${_f}")[${_hit}]" ;;
  esac
done
if [ "${_base}" -lt 3 ]; then
  unable "正向基线不足：violating 夹具里只扫出 ${_base} 处（应 ≥3）—— 这把尺子可能根本不会开火，本项结论不可采信"
elif [ -n "${_bad}" ]; then
  fail "A14/A16 源码启发式扫描告警（形状可疑，需人工确认是不是真违反）：${_bad}"
else
  pass "A14/A16 源码启发式扫描无告警（正向基线 ${_base} 处 violating 夹具全部被扫出）——⚠️ 它只看源码形状，**不是**「守住了 A14/A16」的证明：2026-09-10 那条「打印 FAIL 却 rc=0」的夹具就带着累加器又有 exit，本判据一声不吭。承重结论在 [8b] 的行为夹具"
fi
# 10e 自述段落对账：「自证门禁」一节里写的数字，必须等于门禁实际算出来的
# 实测 2026-09-05：门禁核了「15 组 N 条」那个数，却没人核它旁边那段「我都检查了什么」——
# 四处数字（锚点/例外/【必须】/三桶分区）同时过期。讲自己有多严的那段话，恰恰没人校验。
_claim="$(python3 - "${SKILL}" "${DERIV}" "${R_L}" <<'PYEOF'
import io,re,sys
sk=io.open(sys.argv[1],encoding='utf-8').read()
dv=io.open(sys.argv[2],encoding='utf-8').read()
lb=io.open(sys.argv[3],encoding='utf-8').read()
def blk(t,a,b):
    m=re.search(a+r'.*?-->(.*?)'+b, t, re.S)
    return m.group(1) if m else ''
anchors=len(re.findall(r'^[A-J]\d+\|', blk(dv,'ANCHORS:BEGIN','ANCHORS:END'), re.M))
unver=len(re.findall(r'^[A-J]\d+\|', blk(dv,'UNVERIFIABLE:BEGIN','UNVERIFIABLE:END'), re.M))
must=len(re.findall(r'\*\*([A-M]\d+)\*\*', sk[sk.index('MUST:BEGIN'):sk.index('MUST:END')])) if 'MUST:BEGIN' in sk else -1
p=[]
def chk(name, pat, want):
    m=re.search(pat, sk)
    if not m: p.append('自述段落里找不到「%s」的声称'%name)
    elif int(m.group(1))!=want: p.append('%s 声称 %s，实际 %d'%(name,m.group(1),want))
chk('锚点数', r'\*\*(\d+) 个锚点在源文件中的存在性\*\*', anchors)
chk('声明例外数', r'\*\*(\d+) 条声明例外\*\*', unver)
chk('【必须】条数', r'\*\*【必须】(\d+) 条全部存在且无重复\*\*', must)
# derivation 自己那句「当前 N/N 命中」也要对账（E7：讲自己是什么的那段最没人校验）
mh=re.search(r'当前 (\d+)/(\d+) 命中', dv)
if not mh: p.append('derivation 逐条对照表缺「当前 N/N 命中」的自述')
elif int(mh.group(1))!=anchors or int(mh.group(2))!=anchors:
    p.append('对照表自述 %s/%s 命中，实际锚点 %d'%(mh.group(1),mh.group(2),anchors))
# 三桶正本在 derivation（SKILL.md 2026-09-06 起不再复述，去掉那份手抄拷贝，E7）⇒ 从 dv 读、验正本自洽
m=re.search(r'反推 (\d+) \+ 排除 (\d+) \+ 待回流 (\d+) = (\d+)', dv)
if not m: p.append('derivation 里找不到三桶分区的声称')
else:
    a,b,c,tot=(int(x) for x in m.groups())
    if a+b+c!=tot: p.append('三桶声称 %d+%d+%d≠%d（derivation 内部就不自洽）'%(a,b,c,tot))
    dm=re.search(r'\| 源文件铁律总数 \| (\d+) \|', dv)
    if dm and int(dm.group(1))!=tot: p.append('三桶合计声称 %d，derivation 记的源总数 %s'%(tot,dm.group(1)))
print(('FAIL '+'; '.join(p)) if p else 'PASS 自述段落四项数字与实际一致（锚点%d/例外%d/必须%d/三桶合计%d）'%(anchors,unver,must,tot))
PYEOF
)"
case "${_claim}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_claim#PASS }" ;;
  UNABLE*) unable "${_claim#UNABLE }" ;;
  FAIL*) fail "${_claim#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_claim}" ;;
esac
echo
# 10p ⭐⭐⭐ 条款的场景索引可达率（**只报数，不判失败**）
# 由来（2026-09-05）：拿当天真实遇到的 5 个问题去翻索引，**新增的 5 条条款一条都翻不到**；
# 一量才发现是长期累积 —— 当初 51 条 ⭐⭐⭐ 里索引只覆盖 23 条（现值以下方 PASS 行为准，只报数不判失败）。
# ⚠️ 刻意**不做成硬判据**：那会逼着把 51 条全塞进索引，而索引的价值恰恰在于**精选**，
#    撑爆了就没人看了 —— 那是拿一道门去惩罚正确设计（B16）。
#    但「索引跟不上条款增长」必须**可见**，否则它会一直无声累积（这已经是第二次复发）。
# ⇒ 只打印比率；掉得太狠时人自己会看见。阻断力决定阈值宽窄（G4）：不阻断的信号可以敏感。
_hi_out="$(SKILL="${SKILL}" R_L="${R_L}" R_K="${R_K}" R_M="${R_M}" python3 - <<'PYEOF2'
import io,os,re
s=io.open(os.environ['SKILL'],encoding='utf-8').read()
# D37 做法5：短前缀锚点更易将来误匹配 —— 必须恰好命中一次否则 .index 取错第一处静默错位
for _m in ('## 怎么用：按','# 提交前自检'):
    if s.count(_m)!=1: print('FAIL SKILL.md 里「%s」出现 %d 次（必须恰好 1 次）—— 锚点不唯一，场景索引段会错位（D37 做法5）'%(_m,s.count(_m))); raise SystemExit
try: idx=s[s.index('## 怎么用：按'):s.index('# 提交前自检')]
except ValueError: print('UNABLE 找不到场景索引段'); raise SystemExit
hi=set()
for k in ('R_L','R_K','R_M'):
    for m in re.finditer(r'^### ([A-M]\d+) [·‧] (.+)$', io.open(os.environ[k],encoding='utf-8').read(), re.M):
        if '⭐⭐⭐' in m.group(2): hi.add(m.group(1))
if len(hi) < 20: print('UNABLE 只认出 %d 条 ⭐⭐⭐（下限 20）—— 是解析坏了'%len(hi)); raise SystemExit
ok={r for r in hi if re.search(r'(?<![A-Za-z0-9])'+r+r'(?![0-9])', idx)}
print('OK %d %d'%(len(ok), len(hi)))
PYEOF2
)"
case "${_hi_out}" in
  OK*) set -- ${_hi_out}; pass "⭐⭐⭐ 场景索引可达 $2/$3 —— 索引是**精选**不是全覆盖，这个数只用来看趋势（不判失败）" ;;
  UNABLE*) unable "${_hi_out#UNABLE }" ;;
  *) unable "⭐⭐⭐ 可达率没能算出来（判据没有输出）—— 真因看上方 stderr" ;;
esac

# 10o 定档理由表全库单源（2026-09-05：发现它一直有两份，且已漂移）
# 由来：门禁早就有「【必须】清单全库单源」判据，但它只认 `MUST:BEGIN` 标记块 ——
# **看不见紧挨着它的定档理由表**。那张表在 SKILL.md 与 authority.md 各有一份：
# 后者停在 4 条（C5/K1/M4/A8）、标题数字停在「26 条」，前者已有 8 条。门禁一直全绿。
# ⇒ 教训比判据本身重要：**修了一个拷贝，没检查它旁边还有没有别的拷贝**（同 C6）。
# ⚠️ 先证明扫描真的跑成了（2026-09-05 自审补）：没有这一层的话，
#    FIND 不可用 / SKILL_DIR 不对时两个计数都是 0，判据会报「找不到正本」——
#    **把「没能测」洗成了「不合格」**（A19）。而我恰好是在写完 A19 那两段补充的当天犯的。
_rscan=$(${FIND} -L "${SKILL_DIR}" -name '*.md' -type f 2>/dev/null | ${GREP} -c . || true)
_rn=$(${FIND} -L "${SKILL_DIR}" -name '*.md' -type f -exec ${GREP} -l '<!-- RATIONALE:BEGIN' {} + 2>/dev/null | ${GREP} -c . || true)
_rh=$(${FIND} -L "${SKILL_DIR}" -name '*.md' -type f -exec ${GREP} -h '^| 条款 | 争议 | 处置 |' {} + 2>/dev/null | ${GREP} -c . || true)
if [ "${_rscan:-0}" -lt 5 ]; then
  unable "只扫到 ${_rscan:-0} 个 .md 文件（下限 5）—— 是扫描没跑成，不是定档理由表有问题"
elif [ "${_rn:-0}" -eq 0 ]; then
  fail "全库找不到 <!-- RATIONALE:BEGIN 标记 —— 定档理由表没有可机器识别的正本"
elif [ "${_rn}" -ne 1 ] || [ "${_rh:-0}" -ne 1 ]; then
  fail "定档理由表不是单源：标记块 ${_rn} 处、「条款|争议|处置」表头 ${_rh} 处（各应恰好 1）—— 第二份必然漂移"
else
  pass "定档理由表全库单源（标记块 1 处 · 表头 1 处）"
fi

# 10n 会被**复制走**的产物必须就地自带出处（E8 用在自己身上，2026-09-05）
# 夹具与「提交前自检」清单都是会被整段抄进别处的东西；抄走后，右侧的条款编号
# （A1 / D3 …）在新家指向不存在的东西，而「答不上来就去翻那一组」这句话失效 —— 翻哪儿？
# ⇒ 出处必须写在**会被一起复制的位置**：夹具写在文件头，清单写在代码块**内**（写块外抄不走）。
_fx_n=0; _fx_bad=""
for _ff in "${SKILL_DIR}"/tests/fixtures/*/*.sh; do
  [ -f "${_ff}" ] || continue
  _fx_n=$((_fx_n+1))
  head -3 "${_ff}" | ${GREP} -q 'coding-standards' || _fx_bad="${_fx_bad} $(basename "$(dirname "${_ff}")")/$(basename "${_ff}")"
done
_ck="$(sed -n '/^# 提交前自检/,/^# 自证门禁/p' "${SKILL}" | ${GREP} -c '── 出处 coding-standards' || true)"
if [ "${_fx_n}" -lt 6 ]; then
  unable "只扫到 ${_fx_n} 个夹具（下限 6）—— 是 glob 没展开，不是夹具都合规"
elif [ -n "${_fx_bad}" ] || [ "${_ck:-0}" -eq 0 ]; then
  _p=""
  [ -n "${_fx_bad}" ] && _p="${_fx_n} 个夹具中这些头部没有出处:${_fx_bad}"
  [ "${_ck:-0}" -eq 0 ] && _p="${_p}${_p:+ | }提交前自检清单的代码块**内**没有出处行（写在块外会被抄漏）"
  fail "${_p}"
else
  pass "会被复制走的产物都自带出处（${_fx_n} 个夹具 + 提交前自检清单，E8）"
fi

echo "[11] 变异套件的活性（它太慢不进门禁 ⇒ 它坏了没有任何东西会说）"
# 由来（2026-09-05 实测）：变异表 29 条里有 4 条的**原串已经不存在了** ——
# 锚点绑在会漂移的派生数字上（141/120/34），正本一改表就死，套件实际 FAIL 而本门禁全绿。
# ⚠️ 这两条判据**不许加 `2>/dev/null`**（2026-09-05 自查）：兜底分支的文案写着
#    「真因看上方 stderr」，而 `2>/dev/null` 会把那份 stderr 扔掉 ——
#    **承诺指向的证据，被同一个文件里的代码丢掉了**（E2）。
#    最小复现：`out="$(python3 -c 'raise SystemError()' 2>/dev/null)"` 之后
#    捕获到的是空串，而 traceback 无处可寻；去掉重定向，traceback 就打在结论上方。
# ⭐ 「跑得贵所以不进门禁」和「坏了没人知道」是**可以解耦的**：
#    贵的是执行变异（每条各跑一次完整门禁，全表数分钟），便宜的是校验锚点还在（一次 grep）。
# ⚠️ 这道判据在**变异套件运行期间无意义**：那时被测文件正被故意改坏，
#    别的条目的锚点当然找不到。若照报 FAIL，会把两条期望 rc=3（UNABLE）的用例
#    打成 rc=1 —— 判据收紧后把**正确用法**一起挡在外面（**B16**）。
#    定义域用 reverse-test 的锁来表达：锁在 = 有变异在跑 = 此时不可判（**A19**：没能测≠不合格）。
# @ENG 锚点直接检查内置仓库执法模块；反向测试会显式覆盖为临时副本。
_claim="$(GATE_SELF="${BASH_SOURCE[0]}" SRCFILE="${SRC}" ENGFILE="${REPO_ENFORCEMENT}" RTLOCK="${TMPDIR:-/tmp}/coding-standards-revtest.lock" TSV="${SKILL_DIR}/tests/gate-mutations.tsv" python3 - <<'PYEOF2'
import io,os,re,sys
tsv=os.environ['TSV']
if os.path.isdir(os.environ.get('RTLOCK','')):
    print('UNABLE 变异套件正在运行（被测文件此刻是变异态）—— 锚点活性此时不可判，不是不合格'); raise SystemExit
if not os.path.exists(tsv): print('UNABLE 找不到变异表 '+tsv); raise SystemExit
raw=[l.rstrip('\n') for l in io.open(tsv,encoding='utf-8')]
rows=[l.split('\t') for l in raw if l.strip() and not l.startswith('#')]
p=[]
bad=[str(i+1) for i,r in enumerate(rows) if len(r)!=6]
if bad: print('FAIL 变异表有 %d 行字段数不是 6（行 %s）—— 会被静默当成别的东西跑掉'%(len(bad),','.join(bad[:5]))); raise SystemExit
# A3 下限要盖两个数：①读到几行 ②筛完还剩几行（后者更容易漏）
if len(rows)<10: print('UNABLE 只读到 %d 条变异（下限 10）—— 是表坏了，不是判据都验过了'%len(rows)); raise SystemExit
d=os.path.dirname(tsv.rstrip('/').rsplit('/tests/',1)[0]+'/x') or '.'
base=tsv.rsplit('/tests/',1)[0]
alive=0
for i,(f,old,new,want,msg,gate) in enumerate(rows):
    # @SRC/@ENG = 副本模式（真文件不许原地变异）：@SRC 查 four-node 反推源，
    # @ENG 查内置 repository-enforcement 的临时副本。
    if f=='@SRC': fp = os.environ.get('SRCFILE','')
    elif f=='@ENG': fp = os.environ.get('ENGFILE','')
    else: fp = os.path.join(base,f)
    if not fp or not os.path.exists(fp): p.append('第%d条指向不存在的文件 %s'%(i+1,f)); continue
    txt=io.open(fp,encoding='utf-8').read()
    if '%d' in old:   # 占位锚点：按 (\d+) 匹配，数字自己跟随，不随条款增减失效
        n=len(re.compile(r'(\d+)'.join(re.escape(x) for x in old.split('%d'))).findall(txt))
    else:
        n=txt.count(old)
    if n!=1: p.append('第%d条锚点在 %s 中出现 %d 次（必须恰好 1 次）：%s'%(i+1,f,n,old[:28]))
    else: alive+=1
# 组标号闭世界：每个标号必须是本门禁里真实存在的组
gates=set(re.findall(r'^echo "\[([0-9a-z]+)\]', io.open(os.environ['GATE_SELF'],encoding='utf-8').read(), re.M))
ghost=sorted({r[5] for r in rows} - gates)
if ghost: p.append('组标号指向不存在的判据组：'+','.join(ghost))
if alive==0: print('UNABLE 一条锚点都没验成（%d 条全被跳过）—— 不是全过了'%len(rows)); raise SystemExit
if p: print('FAIL '+'; '.join(p[:4])); raise SystemExit
print('PASS 变异表 %d 条锚点全部唯一命中，覆盖 %d/%d 个判据组'%(len(rows),len({r[5] for r in rows}),len(gates)))
PYEOF2
)"
case "${_claim}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_claim#PASS }" ;;
  UNABLE*) unable "${_claim#UNABLE }" ;;
  FAIL*) fail "${_claim#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_claim}" ;;
esac
[ -n "${_eng_head_11:-}" ] && rm -f "${_eng_head_11}"

# 覆盖度自述对账：此前 SKILL.md 手写「34 道判据里 24 道被机器验过（27 条变异）」，
# 三个数字全过期 —— 因为它们在任何地方都不可推导，只能手写（E7）。
# ⚠️ 「哪几道判据被验过」在当前结构下**确实不可精确推导**（判据没有稳定 ID，
#    一个组里有十几条判据）。正确处置不是猜一个数，而是**换一个可推导的量说同一件事**。
_claim="$(TSV="${SKILL_DIR}/tests/gate-mutations.tsv" SKILL="${SKILL}" GATE_SELF="${BASH_SOURCE[0]}" python3 - <<'PYEOF2'
import io,os,re
tsv=os.environ['TSV']
if not os.path.exists(tsv): print('UNABLE 找不到变异表'); raise SystemExit
rows=[l.rstrip('\n').split('\t') for l in io.open(tsv,encoding='utf-8') if l.strip() and not l.startswith('#')]
rows=[r for r in rows if len(r)==6]
if not rows: print('UNABLE 变异表读到 0 条有效行'); raise SystemExit
n, ng = len(rows), len({r[5] for r in rows})
s=io.open(os.environ['SKILL'],encoding='utf-8').read()
m=re.search(r'\*\*(\d+) 条变异[^*]{0,40}?覆盖 (\d+)/(\d+) 个判据组\*\*', s)
if not m: print('FAIL SKILL.md 里找不到「**N 条变异…覆盖 X/Y 个判据组**」的覆盖度自述'); raise SystemExit
cn,cx,cy=(int(x) for x in m.groups())
# 分母也要对（2026-09-10 codex P1-21）：此前只比 X 不比 Y ⇒ 写成「覆盖 14/999」照样 PASS。
ngates=len(set(re.findall(r'^echo "\[([0-9a-z]+)\]', io.open(os.environ['GATE_SELF'],encoding='utf-8').read(), re.M))) if os.environ.get('GATE_SELF') else None
p=[]
if cn!=n:  p.append('自述 %d 条变异，实际 %d 条'%(cn,n))
if cx!=ng: p.append('自述覆盖 %d 个组，实际 %d 个'%(cx,ng))
if ngates is None: p.append('拿不到门禁自身路径，分母没能核（不是核过了）')
elif cy!=ngates: p.append('自述判据组总数 %d，实际 %d'%(cy,ngates))
print(('FAIL '+'; '.join(p)) if p else 'PASS 覆盖度自述可推导且一致（%d 条变异 · %d/%d 个判据组）'%(n,ng,cy))
PYEOF2
)"
case "${_claim}" in
  '') unable "判据没有任何输出 —— 没能执行，不是不合格（A19）。**真因看上方 stderr**，别照搬这句猜：常见是缺 python3 / 输入文件不可读 / 脚本自身异常" ;;
  PASS*) pass "${_claim#PASS }" ;;
  UNABLE*) unable "${_claim#UNABLE }" ;;
  FAIL*) fail "${_claim#FAIL }" ;;
  *) unable "判据输出不符合三态契约（既不是 PASS/FAIL/UNABLE 开头）——多半是内联 python 打了半截就崩，**这不是不合格，是没能测**（A19）。实得：${_claim}" ;;
esac
echo
echo "[9] 门禁自述（最后一条）"
_claim="$(${GREP} -oE '检查项（\*\*[0-9]+ 组 [0-9]+ 条\*\*）' "${SKILL}" | head -1 || true)"
_cg=$(printf '%s' "${_claim}" | ${GREP} -oE '[0-9]+' | head -1 || true)
_cn=$(printf '%s' "${_claim}" | ${GREP} -oE '[0-9]+' | tail -1 || true)
_ag=$(${GREP} -cE '^echo "\[[0-9a-z]+\]' "${BASH_SOURCE[0]}" || true)
_an=$(( n_pass + n_fail + n_unable + 1 ))   # +1 = 本条自己
if [ -z "${_cg:-}" ] || [ -z "${_cn:-}" ]; then
  unable "SKILL.md 里没找到「检查项（N 组 M 条）」的自述，无法对账"
elif [ "${_cg}" = "${_ag}" ] && [ "${_cn}" = "${_an}" ]; then
  pass "门禁自述与实际一致（${_ag} 组 / ${_an} 条）"
else
  fail "门禁自述对不上：SKILL.md 说 ${_cg} 组 ${_cn} 条，实际 ${_ag} 组 ${_an} 条"
fi
echo

# ---------- 汇总（三态分列，UNABLE 既不计绿也不计红）----------
_elapsed=$(( $(date +%s) - _t0 ))
if [ "${_elapsed}" -gt $(( BASELINE_SECONDS * 2 )) ]; then
  echo "  NOTE   本次 ${_elapsed}s，超过记录基线 ${BASELINE_SECONDS}s 的两倍 —— 不判失败（并发机器上墙钟必然抖动），"
  echo "         但该看一眼是不是判据涨太多了：门禁慢到没人跑，等于没有门禁（A13）。核实后请上调 BASELINE_SECONDS。"
fi
echo "===================== 结论 ====================="
printf 'PASS=%d  FAIL=%d  UNABLE=%d\n' "${n_pass}" "${n_fail}" "${n_unable}"
if [ "${n_fail}" -gt 0 ]; then printf '\nFAIL 项：\n'; for x in "${FAILS[@]}"; do printf '  - %s\n' "${x}"; done; fi
if [ "${n_unable}" -gt 0 ]; then printf '\nUNABLE 项（没能测，不是测过了）：\n'; for x in "${UNABLES[@]}"; do printf '  - %s\n' "${x}"; done; fi

if   [ "${n_fail}" -gt 0 ];   then echo; echo "结论：FAIL"; exit 1
elif [ "${n_unable}" -gt 0 ]; then echo; echo "结论：UNABLE（有检查项没能执行，不得当作通过）"; exit 3
else echo; echo "结论：PASS"; exit 0; fi
