#!/usr/bin/env bash
# 提交前守卫：把 D30「你验的那份和你提交的那份可能不是同一份」变成一个可执行动作。
#
# 做三件事：
#   1. 取被测物指纹 → 跑门禁 → 再取一次指纹；不一致就报 UNABLE（并发写入下门禁读到的是半成品）
#   2. 门禁不绿就不让提交（A16：门的结论必须落在退出码上）
#   3. 顺带在显式配置或本次调用的**真实加载路径**再跑一次（D32）
#
# 退出码：0=可以提交 · 1=门禁判定不合格 · 3=没能测（被测物变化/采集不足/门禁有 UNABLE）· 4=门禁自身坏了或没跑
#
# ⚠️ 文件枚举用 `sort -u`：`git ls-files -com` 会把「已跟踪且已修改」的文件**列两次**，
#    不去重的话报出来的「N 个文件」不是文件数（实测 20 个文件曾报成 25）。
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
REPO="$(cd "${DIR}" && git rev-parse --show-toplevel 2>/dev/null)" || { echo "内部错误：不在 git 仓库里"; exit 4; }
REL="${DIR#"${REPO}"/}"
MIN=15
# GUARD_MIN 只允许**调高**下限，不允许调低 —— 环境可以让判据更严，
# 绝不许让它更松（B20：环境变量不得决定失败算不算数）。存在的意义是让反向测试跑得起来。
case "${GUARD_MIN:-}" in
  ''|*[!0-9]*) ;;
  *) [ "${GUARD_MIN}" -gt "${MIN}" ] && MIN="${GUARD_MIN}" ;;
esac

files(){ git -C "${REPO}" ls-files -com --exclude-standard "${REL}/" | sort -u; }
# 指纹：门禁跑之前/之后各取一次。git diff 那道检查只在**开跑前**成立，
# 挡不住「跑的这一秒里隔壁会话把文件改了」——本机常年 8–10 个会话改同一批文件（COORDINATION.md）。
# ⚠️ 2026-09-10：这个函数在 P0-2 重写（0cd389e）里被**静默删掉**，而头部注释和
#    references/gates.md 都还在承诺它 —— 本 skill 自己的 E1「注释承诺必须成立」被自己违反了一次。
snap(){ files | while IFS= read -r f; do [ -f "${REPO}/${f}" ] && shasum -a256 "${REPO}/${f}"; done | shasum -a256 | cut -c1-16; }

n=$(files | ${GREP:-/usr/bin/grep} -c . || true)
if [ "${n:-0}" -lt "${MIN}" ]; then
  echo "UNABLE  只枚举到 ${n:-0} 个文件（下限 ${MIN}）—— 是采集坏了，不是没文件（A3）"
  exit 3
fi

# 独立临时输出文件 + trap 统一清理（2026-09-09 codex P2：临时文件此前各 exit 路径都没删）
GATE_OUT="$(mktemp -t precommit-gate)" || { echo "内部错误：mktemp 失败"; exit 4; }
trap 'rm -f "${GATE_OUT}"' EXIT

# P0-2（2026-09-09 codex）：**先确保工作区 == 暂存**,否则「验的工作区」≠「将提交的暂存」（D30）。
# 原实现直接对工作区跑门禁,而 git 提交的是暂存区 ⇒「暂存坏、工作区好」会被放行 → 提交坏的暂存。
# 修法用 git diff 比对已跟踪文件的工作区 vs 暂存:不一致就 UNABLE,逼你 git add 归一;
# 归一后「跑工作区」就等于「跑将提交的那份」。比「导出暂存快照跑」鲁棒——
# 后者会连带 selfcheck 的跨 skill 依赖（four-node 反推源 / engineering-standards 回链 / 变异表第 12 条）
# 都要在隔离快照里重新解析,每个都得单独 env 化,脆而易漏。
# P0-2 第二半（2026-09-10 codex）：未跟踪文件。`files()` 用 `ls-files -com` 把它们纳入被测范围，
# 而 `git diff` 不看它们、带路径提交也带不走它们 ⇒ 门禁可以依赖一个未跟踪文件而通过，
# 最终提交里却没有它（下一个人干净检出跑同一道门禁会红）。
_untracked="$(git -C "${REPO}" ls-files --others --exclude-standard -- "${REL}/")"
if [ -n "${_untracked}" ]; then
  echo "UNABLE  被测范围内有未跟踪文件——门禁读得到，提交带不走（D30 的第三种形态）："
  printf '%s\n' "${_untracked}" | sed 's/^/          /'
  echo "        要么 git add 它们，要么从工作区移走再重跑守卫。"
  exit 3
fi
if ! git -C "${REPO}" diff --quiet -- "${REL}"; then
  echo "UNABLE  工作区与暂存区不一致(有已跟踪文件改了没 git add)——你验的工作区**不是**将提交的暂存（D30）。"
  echo "        先 git add 让两者一致(或用 git commit -- 精确路径),再重跑守卫。差异文件:"
  git -C "${REPO}" diff --name-only -- "${REL}" | sed 's/^/          /'
  exit 3
fi
before="$(snap)"
bash "${DIR}/scripts/selfcheck.sh" > "${GATE_OUT}" 2>&1; rc=$?
after="$(snap)"

printf '文件 %d 个 · 门禁 rc=%s · 工作区==暂存(已验一致,D30) · 指纹 %s -> %s\n' "${n}" "${rc}" "${before}" "${after}"
if [ "${before}" != "${after}" ]; then
  echo "UNABLE  被测物在检查期间发生变化 —— 这次的绿/红都不指向你手上这份（D30）"
  echo "        通常是并发会话在改同一批文件；隔几秒重跑。"
  exit 3
fi
# A19：五种「非 0」不是同一件事。全都拦住提交，但**必须说清是哪一种** ——
# 报成「门禁未过」会让人去找一条根本不存在的失败项，而真因是门禁自己没跑起来。
case "${rc}" in
  0) ;;
  1) echo "FAIL    门禁判定不合格，不许提交（A16）。详见 ${GATE_OUT}："; tail -8 "${GATE_OUT}"; exit 1 ;;
  3) echo "UNABLE  门禁有检查项没能执行（不是通过，也不是不合格）。详见 ${GATE_OUT}："; tail -8 "${GATE_OUT}"; exit 3 ;;
  4) echo "FAIL    门禁自身内部错误（判据坏了，结论不可采信）。详见 ${GATE_OUT}："; tail -8 "${GATE_OUT}"; exit 4 ;;
  126|127) echo "FAIL    门禁不可执行或不存在（rc=${rc}）—— 这不是「没过」，是**根本没跑**"; exit 4 ;;
  *) echo "FAIL    门禁以未声明的退出码 ${rc} 结束（见 selfcheck.sh 头部的退出码契约）"; tail -8 "${GATE_OUT}"; exit 4 ;;
esac

# D32：真实加载路径（软链）也跑一次
if [ -n "${SYBUILDER_SKILLS_DIR:-}" ]; then
  LINK="${SYBUILDER_SKILLS_DIR}/$(basename "${DIR}")"
else
  LINK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -L)"
fi
if [ -e "${LINK}/scripts/selfcheck.sh" ]; then
  bash "${LINK}/scripts/selfcheck.sh" >/dev/null 2>&1; lrc=$?
  # ⚠️ 2026-09-10（codex P1-26）：这里原来把 3/4/126/127 全折叠成 exit 1 ——
  #    「真实路径上门禁没跑起来」被报成「真实路径不合格」。与上面主门禁用同一张映射。
  case "${lrc}" in
    0) ;;
    1) echo "FAIL    开发路径绿，但**真实加载路径** ${LINK} 判定不合格（D32）"; exit 1 ;;
    3) echo "UNABLE  真实加载路径 ${LINK} 有检查项没能执行（不是不合格）"; exit 3 ;;
    126|127) echo "FAIL    真实加载路径 ${LINK} 的门禁不可执行（rc=${lrc}）—— 根本没跑"; exit 4 ;;
    *) echo "FAIL    真实加载路径 ${LINK} 以未声明的退出码 ${lrc} 结束"; exit 4 ;;
  esac
  echo "真实加载路径同样通过：${LINK}"
else
  echo "NOTE    未找到真实加载路径 ${LINK}，跳过 D32 这一项（缺席已留痕，A7）"
fi

echo "✓ 可以提交。记得用：git commit -- ${REL}/   （K11：git commit 提交的是整个索引）"
