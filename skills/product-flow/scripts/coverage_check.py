#!/usr/bin/env python3
"""需求 ↔ 用例 双向覆盖对账。

用法:
    python3 coverage_check.py <requirements.md> <cases 目录> [-o coverage.json] [--gaps readiness.md]

退出码:
    0  双向全覆盖，且缺口清单已核（--gaps 提供且无未解决缺口、无用例级 SKIPPED）
    1  有漏（正向漏 / 反向漏 / 格式违规 / 重复 TC-ID）
    2  输入无效（文件不存在、解析不到任何需求或用例）
    3  双向对账通过，但**不能声称被测充分** —— 存在未解决缺口、存在用例级 SKIPPED、
       或未提供 --gaps（缺口状态未知）。⚠️ 2026-09-15 收紧：此前不带 --gaps 可返 0，
       而 0 的语义写的是「无未解决缺口」——没核过的事不许声称（WO-002 终审 C1）。

设计原则:
    解析不到东西时报错退出(2)，绝不因为"没发现问题"而返回 0。
    fail-open 的门禁等于没有门禁。

    覆盖率的分母只含「PRD 里真实存在的需求」。PRD 本身缺失的需求没有编号、
    进不了分母 —— 所以 100% 覆盖率完全可能出现在一份撑不起用例的 PRD 上。
    这就是退出码 3 与 --gaps 存在的理由：**不许只报覆盖率**。
"""

import json
import re
import sys
from pathlib import Path

REQ_ID = re.compile(r"\b((?:N?FR)-\d+)\b")
SKIP_MARK = "[待补规格·不生成]"
CASE_HEAD = re.compile(r"^#{2,4}\s*(TC-\d+-\d+)\b")
CASE_OWNER = re.compile(r"所属\s*((?:N?FR)-\d+)")
GAP_ID = re.compile(r"\b(GAP-\d+)\b")


def parse_requirements(path):
    """返回 {req_id: 'active'|'skipped'}，按 requirements.md 中出现顺序去重。"""
    reqs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        ids = REQ_ID.findall(line)
        if not ids:
            continue
        status = "skipped" if SKIP_MARK in line else "active"
        for rid in ids:
            # 同一 ID 多次出现时，只要有一行标了不生成就记 skipped
            if reqs.get(rid) != "skipped":
                reqs[rid] = status
    return reqs


# 用例级「跑不了」标记。⚠️ 与需求级的 SKIPPED 是**两件事**：
#   需求级 = 这条需求本轮不生成用例（不进分母）
#   用例级 = 用例写了，但**没真跑**（进分母，却不该被当成测过）
# ⚠️ 2026-09-15 收紧（WO-002 终审 C7，同日复核轮再收一次）：标记必须是**行尾的加粗记号**。
#   第一版裸子串：头行标题「验证未执行任务的提示」被误标（误红）。
#   第二版只要求加粗：复核轮当场两个方向都打穿——`** SKIPPED **`（星号内侧带空格）静默漏检、
#   标题里内联加粗「验证**未执行**任务」照旧误标。⇒ 锚定**行尾**一次堵两个方向：
#   标记约定=写在用例头行末尾（见 s8-testcases.md ④），标题文字天然不在行尾结束于此记号。
#   已知边界（如实登记）：标题恰好以加粗的「未执行」结尾仍会误标——按约定头行末尾属标记位。
CASE_SKIP = re.compile(r'\*\*\s*(SKIPPED|跑不了|未执行)\s*\*\*\s*$')
CASE_SKIP_WHY = re.compile(r'\*{0,2}(?:SKIPPED\s*理由|跳过理由|未执行理由)\*{0,2}\s*[:：]\s*(\S)')


def parse_cases(case_dir):
    """返回 [(tc_id, owner_req_or_None, source_file, skipped, has_reason)]。

    ⚠️⚠️ 2026-09-04 补的是一个能让「100% 覆盖」变成谎话的洞：
    此前本门禁只问「有没有一条用例引用了这条需求」，
    **一条写着「跑不了」的用例，与一条真跑通过的用例完全等价**。
    实跑时它对一份 11 条用例里 3 条明写跑不了的用例集报出
    「覆盖率 100.0% · ✅ 双向对账通过」——看的人只会理解成「测过了」。
    ⭐ 而门禁目录里那句「没真跑的记 SKIPPED，不许折叠成通过」
      描述的正是它**当时并不具备**的能力（那句话是同一天写进去的，
      作者就是我）—— **给门禁写介绍时，很容易把「它应该做到的」写成「它做到的」。**
    ⛔ 用例级跳过**必须写理由**：不写理由的跳过就是静音开关
      （与端差异登记同一条纪律）。
    """
    cases = []
    for md in sorted(case_dir.rglob("*.md")):
        current = None
        for line in md.read_text(encoding="utf-8").splitlines():
            head = CASE_HEAD.match(line.strip())
            if head:
                if current:
                    cases.append(current)
                owner = CASE_OWNER.search(line)
                current = [head.group(1), owner.group(1) if owner else None, md.name,
                           bool(CASE_SKIP.search(line)), False]
                continue
            if not current:
                continue
            if current[1] is None:
                owner = CASE_OWNER.search(line)
                if owner:
                    current[1] = owner.group(1)
            if CASE_SKIP_WHY.search(line):
                current[3] = True
                current[4] = True
        if current:
            cases.append(current)
    return [tuple(c) for c in cases]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    out_path = None
    if "-o" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("-o") + 1])
        args = [a for a in args if a != str(out_path)]
    gaps_path = None
    if "--gaps" in sys.argv:
        gaps_path = Path(sys.argv[sys.argv.index("--gaps") + 1])
        args = [a for a in args if a != str(gaps_path)]
    if len(args) != 2:
        print(__doc__)
        return 2

    req_file, case_dir = Path(args[0]), Path(args[1])
    if not req_file.is_file():
        print(f"❌ 需求清单不存在: {req_file}")
        return 2
    if not case_dir.is_dir():
        print(f"❌ 用例目录不存在: {case_dir}")
        return 2

    gap_ids, readiness = set(), "UNKNOWN"
    if gaps_path is not None:
        if not gaps_path.is_file():
            print(f"❌ 缺口清单不存在: {gaps_path}")
            return 2
        gap_ids = set(GAP_ID.findall(gaps_path.read_text(encoding="utf-8")))
        readiness = "HAS_GAPS" if gap_ids else "CLEAN"

    reqs = parse_requirements(req_file)
    cases = parse_cases(case_dir)

    if not reqs:
        print(f"❌ 在 {req_file} 中解析不到任何 FR/NFR 编号——无法对账")
        return 2
    if not cases:
        print(f"❌ 在 {case_dir} 中解析不到任何 TC 用例——无法对账")
        return 2

    covered = {}
    orphans = []          # 反向漏：用例找不到需求
    unlabeled = []        # 格式违规：用例没写「所属」
    skipped_but_cased = []  # 违规：标了「不生成」却有人写了用例
    case_skips = []       # 用例写了但**没真跑**（进分母，不该被当成测过）
    skip_no_reason = []   # 违规：跳过却不写理由 = 静音开关
    # 重复 TC-ID（2026-09-15 WO-002 终审 C8）：铁律「用例 ID 只增不改」此前零判据——
    # 同一 TC-011-1 写两遍会被静默双计进分子，追溯链从此指不清是哪一条。
    _seen_tc = {}
    dup_case_ids = []
    for tc_id, _o, src, _s, _r in cases:
        if tc_id in _seen_tc:
            dup_case_ids.append((tc_id, _seen_tc[tc_id], src))
        else:
            _seen_tc[tc_id] = src
    for tc_id, owner, src, skipped_case, has_reason in cases:
        if skipped_case:
            case_skips.append((tc_id, owner, src))
            if not has_reason:
                skip_no_reason.append((tc_id, src))
        if owner is None:
            unlabeled.append((tc_id, src))
            continue
        if owner not in reqs:
            orphans.append((tc_id, owner, src))
            continue
        # 标了 [待补规格·不生成] 却有用例 —— 这正是「有人违反铁律猜着把用例补上了」的指纹。
        # 旧版把它记进 covered 又归入 skipped，既不报错也不进分母，对账门对它完全是瞎的。
        if reqs[owner] == "skipped":
            skipped_but_cased.append((tc_id, owner, src))
            continue
        covered.setdefault(owner, []).append(tc_id)

    active = [r for r, s in reqs.items() if s == "active"]
    skipped = [r for r, s in reqs.items() if s == "skipped"]
    gaps = [r for r in active if r not in covered]          # 正向漏

    rows = []
    for rid in reqs:
        if reqs[rid] == "skipped":
            status = "skipped"
        elif rid in covered:
            status = "covered"
        else:
            status = "gap"
        rows.append({"fr_id": rid, "tc_ids": sorted(covered.get(rid, [])), "status": status})

    # 分母只算 active（真核过且可生成的），skipped 不并进覆盖率
    rate = (len(active) - len(gaps)) / len(active) * 100 if active else 0.0
    ok = (not gaps and not orphans and not unlabeled
          and not skipped_but_cased and not dup_case_ids)

    # 只被跳过用例覆盖的需求：覆盖率对它们是虚的（要跟着数据进 JSON，不许只留在 stdout）
    covered_only_by_skip = sorted({o for _, o, _ in case_skips if o
                                   and all(c[3] for c in cases if c[1] == o)})

    result = {
        "requirements_total": len(reqs),
        "requirements_active": len(active),
        "requirements_skipped": len(skipped),
        "cases_total": len(cases),
        "coverage_rate_percent": round(rate, 1),
        "forward_gaps": sorted(gaps),
        "reverse_orphans": [{"tc": t, "claims": o, "file": f} for t, o, f in orphans],
        "unlabeled_cases": [{"tc": t, "file": f} for t, f in unlabeled],
        "skipped_but_cased": [{"tc": t, "claims": o, "file": f} for t, o, f in skipped_but_cased],
        "reconcile_passed": ok,
        "readiness": readiness,
        "open_gaps": sorted(gap_ids),
        # ⚠️ 2026-09-15（WO-002 终审 C2，铁律 46 形状）：case_skips 此前只打印到 stdout、
        #   不进 JSON，且本字段不看它 ⇒ 同一次运行退出码 3 而 JSON 说 sufficient=true——
        #   机器正本与退出码互相矛盾。标志必须跟着数据走到消费方。
        "case_skips": [{"tc": t, "claims": o, "file": f} for t, o, f in case_skips],
        "skip_no_reason": [{"tc": t, "file": f} for t, f in skip_no_reason],
        "covered_only_by_skips": covered_only_by_skip,
        "dup_case_ids": [{"tc": t, "first_file": a, "dup_file": b} for t, a, b in dup_case_ids],
        # 覆盖率只对「PRD 里已存在的需求」成立，不代表被测充分。
        "coverage_means_sufficient": (ok and readiness == "CLEAN" and not case_skips),
        "rows": rows,
    }

    print(f"需求 {len(reqs)}（有效 {len(active)} · SKIPPED {len(skipped)}）｜用例 {len(cases)}")
    print(f"覆盖率 {rate:.1f}%（分母只算有效需求，SKIPPED 不计入）")
    if gaps:
        print(f"🔴 正向漏 {len(gaps)}（需求没测）: {', '.join(sorted(gaps))}")
    if orphans:
        print(f"🔴 反向漏 {len(orphans)}（用例反查不到需求）:")
        for t, o, f in orphans:
            print(f"    {t} 声称所属 {o}，但需求清单里没有此项　[{f}]")
    if unlabeled:
        print(f"🔴 格式违规 {len(unlabeled)}（用例未写「所属」）:")
        for t, f in unlabeled:
            print(f"    {t}　[{f}]")
    if skip_no_reason:
        print(f"🔴 跳过不写理由 {len(skip_no_reason)}（不写理由的跳过＝静音开关）:")
        for tc, f in skip_no_reason:
            print(f"    {tc}　[{f}]")
    if dup_case_ids:
        print(f"🔴 重复 TC-ID {len(dup_case_ids)}（用例 ID 只增不改，重复 ID 会静默双计且追溯指不清）:")
        for t, a, b in dup_case_ids:
            print(f"    {t}　首见 [{a}]，重复于 [{b}]")
    if case_skips:
        print(f"⚠️ 用例级 SKIPPED {len(case_skips)} 条 —— **写了但没真跑**，"
              f"它们进了覆盖率分子却没有测到任何东西")
        for tc, o, f in case_skips:
            print(f"    {tc}（{o}）　[{f}]")
        if covered_only_by_skip:
            print(f"⛔ 其中 {len(covered_only_by_skip)} 条需求**只被跳过的用例覆盖**："
                  f"{', '.join(covered_only_by_skip)} —— 覆盖率对它们是虚的")
    if skipped_but_cased:
        print(f"🔴 猜补用例 {len(skipped_but_cased)}（需求已标「待补规格·不生成」，却有人写了用例）:")
        for t, o, f in skipped_but_cased:
            print(f"    {t} 挂在 {o} 上，而 {o} 的规格还没补　[{f}]")
        print("    → 猜出来的用例测的是想象，不是需求。删掉，或先补规格再写。")
    if ok:
        print("✅ 双向对账通过")

    # 覆盖率不许单独呈现：必须同时给出就绪度结论，否则会被读成"已测充分"
    if readiness == "UNKNOWN":
        print("🔴 未提供缺口清单（--gaps）：缺口状态未知 ⇒ 退出码 3，不许当完成信号用。"
              "s8-testcases.md 明写「--gaps 不是可选项」——没核过的事不许声称（2026-09-15 收紧）")
    elif gap_ids:
        print(f"🔴 存在 {len(gap_ids)} 个未解决缺口：{', '.join(sorted(gap_ids))}")
        print("   覆盖率只对 PRD 里已存在的需求成立，**不代表产品被测充分**")

    if out_path:
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {out_path}")

    # 跳过不写理由属于**格式违规**，与「用例没写所属」同级 → 1
    if skip_no_reason:
        ok = False
    if not ok:
        return 1
    # ⭐ 用例级 SKIPPED 存在时**不许返 0**：退出码 3 的语义正是
    #   「双向对账通过，但覆盖率不代表被测充分」—— 这就是它该出现的地方。
    #   ⛔ 返 0 会让「11 条用例里 3 条根本没跑」被读成「测过了」。
    # ⭐ 2026-09-15 收紧（C1）：未提供 --gaps ⇒ 缺口状态未知，同样不许返 0。
    #   0 的语义是「无未解决缺口」——没读过缺口清单就返 0 是在声称没核过的事。
    return 3 if (gap_ids or case_skips or readiness == "UNKNOWN") else 0




# ------------------------------------------------------------------ M8 自证
def _run_bad_encoding(t, me, req_text):
    """造一个非法 UTF-8 的用例文件，跑主入口拿退出码。
    钉的是 _main_guarded 的 UNABLE 路径（崩溃→2）——此前该守卫零自证（WO-002 终审 C5）。"""
    import os, sys, subprocess, tempfile, io as _io
    d = tempfile.mkdtemp(dir=t); cd = os.path.join(d, "cases"); os.makedirs(cd)
    _io.open(os.path.join(d, "req.md"), "w", encoding="utf-8").write(req_text)
    with open(os.path.join(cd, "bad.md"), "wb") as f:
        f.write(b"### TC-011-1 \x80\xff invalid\n")
    return subprocess.call([sys.executable, me, os.path.join(d, "req.md"), cd],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _self_test():
    """⚠️ 2026-08-31 补 —— 由 consistency-gate 的 selftest-claim 规则抓出来的：
    本脚本是 M4 的 G4 对账门，却一直没有自证。"""
    import os, sys, tempfile, subprocess, io as _io
    t = tempfile.mkdtemp(prefix="cc-"); me = os.path.abspath(__file__)
    def mk(req, cases, gaps=None):
        d = tempfile.mkdtemp(dir=t); cd = os.path.join(d, "cases"); os.makedirs(cd)
        _io.open(os.path.join(d, "req.md"), "w", encoding="utf-8").write(req)
        _io.open(os.path.join(cd, "a.md"), "w", encoding="utf-8").write(cases)
        g = None
        if gaps is not None:
            g = os.path.join(d, "gaps.md"); _io.open(g, "w", encoding="utf-8").write(gaps)
        return os.path.join(d, "req.md"), cd, g
    def run(req, cd, g=None):
        a = [sys.executable, me, req, cd] + (["--gaps", g] if g else [])
        return subprocess.call(a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    R = "FR-011 登录\nFR-012 锁定\n"
    C_ok = "### TC-011-1 所属 FR-011\n### TC-012-1 所属 FR-012\n"
    G_clean = "# 缺口清单\n（本轮无未解决缺口）\n"
    # ⚠️ 2026-09-15 起正例必须带净 gaps 文件：不带 --gaps 时 0 已不可达（C1 收紧），
    #    正例语义不变（双向全覆盖 ⇒ 0），只是把「缺口已核」这个前提显式补上。
    cases = [
        ("正例 双向全覆盖", run(*mk(R, C_ok, G_clean)), 0),
        ("反例 正向漏(需求没测)", run(*mk(R, "### TC-011-1 所属 FR-011\n")), 1),
        ("反例 反向漏(用例反查不到)", run(*mk(R, C_ok + "### TC-099-1 所属 FR-099\n")), 1),
        ("反例 用例没写「所属」", run(*mk(R, C_ok + "### TC-013-1 无归属\n")), 1),
        ("反例 猜补用例(标了不生成却有用例)",
         run(*mk("FR-011 登录\nFR-012 锁定 [待补规格·不生成]\n", C_ok)), 1),
        ("有未解决缺口 → 退出码 3 不是 0", run(*mk(R, C_ok, "GAP-01 字段规格缺失\n")), 3),
        # ⭐ 2026-09-04：此前**一条写着「跑不了」的用例，与一条真跑通过的用例完全等价** ——
        #    实跑时对「11 条里 3 条明写跑不了」的用例集报出「100% · ✅ 通过」。
        ("用例级 SKIPPED 存在 → 退出码 3（100% 也不许返 0）",
         run(*mk(R, "### TC-011-1 所属 FR-011\n"
                    "### TC-012-1 所属 FR-012 **SKIPPED**\n"
                    "**SKIPPED 理由**：依赖尚未落地\n")), 3),
        # 🚨 跳过不写理由＝静音开关，必须按格式违规红（1），不是 3
        ("反例 跳过却不写理由（静音开关）→ 1",
         run(*mk(R, "### TC-011-1 所属 FR-011\n"
                    "### TC-012-1 所属 FR-012 **SKIPPED**\n")), 1),
        # 🚨 反向：没有任何跳过时仍必须返 0（新判据不许把正常情形也拖成 3）
        ("反向 无跳过时仍返 0（新判据不许殃及正常情形）", run(*mk(R, C_ok, G_clean)), 0),
        ("需求文件不存在 → 2", run(os.path.join(t, "nope.md"), t), 2),
        # ── 2026-09-15 WO-002 终审新增（C1/C7/C8 + UNABLE 正例）──
        ("反例 未提供 --gaps → 3（缺口状态未知不算完成）", run(*mk(R, C_ok)), 3),
        ("正例 头行含「未执行」字样的正常标题 → 不误标跳过",
         run(*mk(R, "### TC-011-1 所属 FR-011 · 验证未执行任务的提示\n"
                    "### TC-012-1 所属 FR-012\n", G_clean)), 0),
        ("反例 重复 TC-ID → 1（用例 ID 只增不改，重复会静默双计）",
         run(*mk(R, C_ok + "### TC-011-1 所属 FR-011\n", G_clean)), 1),
        ("反例 用例文件不可解码 → 2（UNABLE，⛔ 不许伪装成「有漏」）",
         _run_bad_encoding(t, me, R), 2),
        # ── 同日复核轮抓出的两个方向（修法=标记锚定行尾）──
        ("正例 星号内侧带空格的行尾标记 ** SKIPPED ** → 仍识别（3）",
         run(*mk(R, "### TC-011-1 所属 FR-011\n"
                    "### TC-012-1 所属 FR-012 ** SKIPPED **\n"
                    "**SKIPPED 理由**：依赖尚未落地\n")), 3),
        ("正例 标题内联加粗「验证**未执行**任务」→ 不误标（净 gaps 返 0）",
         run(*mk(R, "### TC-011-1 所属 FR-011 · 验证**未执行**任务的提示页\n"
                    "### TC-012-1 所属 FR-012\n", G_clean)), 0),
    ]
    # ── JSON 正本断言（C2）：标志必须跟着数据进 coverage.json，不许只活在 stdout ──
    import json as _json
    d2 = tempfile.mkdtemp(dir=t); cd2 = os.path.join(d2, "cases"); os.makedirs(cd2)
    _io.open(os.path.join(d2, "req.md"), "w", encoding="utf-8").write(R)
    _io.open(os.path.join(cd2, "a.md"), "w", encoding="utf-8").write(
        "### TC-011-1 所属 FR-011\n### TC-012-1 所属 FR-012 **SKIPPED**\n"
        "**SKIPPED 理由**：依赖尚未落地\n")
    g2 = os.path.join(d2, "gaps.md"); _io.open(g2, "w", encoding="utf-8").write(G_clean)
    o2 = os.path.join(d2, "cov.json")
    rc_json = subprocess.call([sys.executable, me, os.path.join(d2, "req.md"), cd2,
                               "-o", o2, "--gaps", g2],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        j = _json.load(_io.open(o2, encoding="utf-8"))
        json_ok = (rc_json == 3
                   and j.get("coverage_means_sufficient") is False
                   and [x.get("tc") for x in j.get("case_skips", [])] == ["TC-012-1"]
                   and j.get("covered_only_by_skips") == ["FR-012"])
    except Exception:
        json_ok = False
    cases.append(("JSON 与退出码同口径：skip 进 case_skips 且 sufficient=False（净 gaps 下也不许 True）",
                  0 if json_ok else 1, 0))
    ok = True
    print("M8 自证 —— 正例绿 / 每类漏各造一个反例必红 / 缺口存在时不许返 0\n")
    for n, got, want in cases:
        g = got == want; ok &= g
        print("  %s %-38s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, got))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败"))
    return 0 if ok else 1


# ── 意外异常必须报「跑不了」，不许和「有发现」共用退出码 ────────────────
# 🚨 2026-09-05 实测：喂一个坏 JSON 给本门，得到 **rc=1 + Traceback** ——
#    **崩溃与「发现缺陷」在退出码上完全一样**。后果有两层：
#    ① 报告里它长成「有发现」，把人送去查一个不存在的缺陷；
#    ② 自证里只看退出码的反例，**崩溃会被读成「反例红了」**。
#    （形状由并行会话 peer-agent-c0 提出，它那边是「反例对象被别的判据消费 ⇒ KeyError」。）
# ⛔ `except Exception` 不捕获 `SystemExit`，所以门禁自己的 exit(0/1/2) 不受影响。
def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 门禁自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    def _entry():
            sys.exit(_self_test() if "--self-test" in sys.argv else main())
    _main_guarded(_entry)
