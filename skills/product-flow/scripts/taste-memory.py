#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
品味记忆 —— 收敛在品味、发散在执行（用户 2026-08-31 拍板）。

═══ 它解决的那个冲突 ═══
  本 skill 原有「跨代反收敛」：同一项目连续两次产出，不得复用同一字体族、同一配色族、
  **同一明暗方向**。重复即 slop。
  gstack 有「Taste Memory」：读跨会话的品味档案，把生成偏置到用户已证明的偏好上。
  两者看似方向相反 —— 一个要求每代不同，一个要求向偏好收敛。

  **真正的问题是老规则切错了地方**：它把「明暗方向」放进了发散轴。
  而明暗恰恰是最典型的品味 —— 一个反复选浅色的用户，你每一代强行给他深色，
  不是在反 slop，是在交付他明确不要的东西。

═══ 两轴的判据（唯一一条，好用） ═══
  对任一属性问：**换掉它，用户会说「这不是我要的方向」，还是「这个也行，甚至更好」？**
    前者 → **品味轴，该收敛**（记进档案，后续偏置）
    后者 → **执行轴，该发散**（记进代际日志，下一代不许重复）

| 轴 | 属性 | 跨代要求 |
|---|---|---|
| **品味（收敛）** | 明暗方向 · 语义档位 · 字体气质类别 · 色彩温度 · 信息密度 · 动效强度 | 与档案强信号一致；不一致要写明理由 |
| **执行（发散）** | 具体字体族 · 具体强调色 · 视觉锚点食谱 · 布局构图与节奏 | Greenfield/Overhaul 不许与上代相同；**Preserve 反过来，必须保持** |

⚠️ 「衬线 vs 无衬线」是品味；「Georgia vs Source Serif」是执行。**同一气质下换具体字体，是发散不是背叛。**

═══ 三条纪律 ═══
1. **偏置不是判据。** 品味档案给的是起点，不是门禁。它永远不许把一个方案判成 FAIL——
   只会 WARN 并要求写理由。**做成硬门禁会让品味固化，而固化的品味就是 slop。**
2. **单次认可不构成品味**（n≥2 才计入强信号）。三选一里选中一个，是「best of 3」，不是「我爱这个」。
3. **否决权重高于认可**（×2）。人会接受平庸，但只会明确拒绝真正不要的东西。

用法:
  taste-memory.py record <profile.json> --dim <维度> --value <值> --verdict approved|rejected
                  [--classifier landing|app-ui] [--why "..."]
  taste-memory.py log-generation <profile.json> --font X --accent Y --anchor Z [--layout W]
  taste-memory.py read  <profile.json> [--classifier X] [--json]
  taste-memory.py check <profile.json> --brief <design-brief.md> --mode greenfield|preserve|overhaul
  taste-memory.py --self-test
退出码: 0=通过/无阻碍 1=有冲突需处理 2=跑不了
"""
import io, os, re, sys, json, math, datetime, tempfile, subprocess

TASTE_DIMS = ["明暗", "档位", "字体气质", "色温", "密度", "动效"]
EXEC_DIMS = ["字体族", "强调色", "视觉锚点", "布局"]
DECAY_PER_WEEK = 0.05
STRONG_N = 2          # 单次认可不构成品味
REJECT_WEIGHT = 2.0   # 否决权重高于认可


def die(m):
    print("UNABLE: " + m, file=sys.stderr); sys.exit(2)


def today():
    return datetime.date.today().isoformat()


def load(p, create=False):
    if not os.path.exists(p):
        if create: return {"version": 1, "dimensions": {}, "generations": []}
        die("品味档案不存在：%s（先跑 record 或 log-generation 建立）" % p)
    try:
        d = json.load(io.open(p, encoding='utf-8'))
    except Exception as e:
        die("档案不是合法 JSON：%s" % e)
    if d.get("version") != 1: die("档案版本不支持：%s" % d.get("version"))
    return d


def save(p, d):
    d["updated"] = today()
    io.open(p, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))


def weeks_since(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except Exception:
        return 0.0
    return max(0.0, (datetime.date.today() - d).days / 7.0)


def score(e):
    """置信 = (认可 − 否决×2) × 衰减。读时算，不写时算，档案只在变化时增长。"""
    raw = e.get("approved", 0) - e.get("rejected", 0) * REJECT_WEIGHT
    return raw * math.pow(1 - DECAY_PER_WEEK, weeks_since(e.get("last_seen", today())))


def strong_signals(prof, classifier=None):
    """返回 {维度: (值, 置信)} —— 只含强信号（n≥2 且净分>0）。"""
    out = {}
    for dim, entries in prof.get("dimensions", {}).items():
        best = None
        for e in entries:
            if classifier and e.get("classifier") and e["classifier"] != classifier:
                continue
            n = e.get("approved", 0) + e.get("rejected", 0)
            if n < STRONG_N:
                continue
            s = score(e)
            if s > 0 and (best is None or s > best[1]):
                best = (e["value"], s, e.get("why", ""))
        if best: out[dim] = best
    return out


def rejections(prof, classifier=None):
    out = {}
    for dim, entries in prof.get("dimensions", {}).items():
        for e in entries:
            if classifier and e.get("classifier") and e["classifier"] != classifier:
                continue
            if e.get("rejected", 0) > 0 and score(e) < 0:
                out.setdefault(dim, []).append(e["value"])
    return out


# ------------------------------------------------------------------ 命令
def cmd_record(p, dim, value, verdict, classifier, why):
    if dim not in TASTE_DIMS:
        die("维度必须是品味轴之一 %s —— 执行轴的属性用 log-generation 记，不进品味档案" % TASTE_DIMS)
    prof = load(p, create=True)
    ent = prof["dimensions"].setdefault(dim, [])
    hit = next((e for e in ent if e["value"] == value and e.get("classifier") == classifier), None)
    if hit is None:
        hit = {"value": value, "classifier": classifier, "approved": 0, "rejected": 0, "why": why or ""}
        ent.append(hit)
    hit["approved" if verdict == "approved" else "rejected"] += 1
    hit["last_seen"] = today()
    if why: hit["why"] = why
    save(p, prof)
    n = hit["approved"] + hit["rejected"]
    print("✅ 记下 %s=%s（%s）　认可 %d · 否决 %d" % (dim, value, verdict, hit["approved"], hit["rejected"]))
    if n < STRONG_N:
        print("   ⚠️ 样本 %d 次 <%d，**还不构成强信号**——三选一里选中一个是 best of 3，不是「我爱这个」" % (n, STRONG_N))
    return 0


def cmd_log(p, kv):
    prof = load(p, create=True)
    prof.setdefault("generations", []).append(dict(kv, date=today()))
    save(p, prof)
    print("✅ 记下本代执行轴：%s" % " · ".join("%s=%s" % (k, v) for k, v in kv.items() if v))
    print("   下一代（Greenfield/Overhaul）**不许复用这些具体值**；Preserve 模式则必须保持。")
    return 0


def cmd_read(p, classifier, as_json):
    prof = load(p)
    sig = strong_signals(prof, classifier)
    rej = rejections(prof, classifier)
    last = prof.get("generations", [])[-1] if prof.get("generations") else None
    if as_json:
        print(json.dumps({"strong": {k: {"value": v[0], "confidence": round(v[1], 2)} for k, v in sig.items()},
                          "rejected": rej, "last_generation": last}, ensure_ascii=False, indent=1))
        return 0
    print("# 品味档案　%s%s" % (p, ("　分类=" + classifier) if classifier else ""))
    if not sig:
        print("➖ 还没有强信号（每个维度都需要 ≥%d 次样本）——本次不做偏置，正常发挥。" % STRONG_N)
    else:
        print("\n## 品味轴（收敛：把这些当起点）")
        for d, (v, s, why) in sorted(sig.items(), key=lambda x: -x[1][1]):
            print("  %-8s → %-14s 置信 %.2f%s" % (d, v, s, ("　（%s）" % why) if why else ""))
    if rej:
        print("\n## 明确否决（**不许再出现**，否决权重是认可的 %.0f 倍）" % REJECT_WEIGHT)
        for d, vs in rej.items(): print("  %-8s ✗ %s" % (d, " / ".join(vs)))
    if last:
        print("\n## 上一代执行轴（%s）—— Greenfield/Overhaul 时**不许复用**" % last.get("date"))
        for k, v in last.items():
            if k != "date" and v: print("  %-8s = %s" % (k, v))
    print("\n⚠️ **偏置不是判据。** 这里给的是起点，不是门禁——它永远不会把方案判成不合格，")
    print("   只会在你偏离时要求写明理由。做成硬门禁会让品味固化，而固化的品味就是 slop。")
    return 0


AXES_RE = re.compile(r'<!--\s*taste-axes([\s\S]*?)-->')


def parse_brief(path):
    if not os.path.isfile(path): die("读不到设计简报：%s" % path)
    s = io.open(path, encoding='utf-8', errors='replace').read()
    m = AXES_RE.search(s)
    if not m:
        die("设计简报里没有 `<!-- taste-axes ... -->` 块 —— 无法机械比对。\n"
            "       ⚠️ 不许从散文里猜属性：猜出来的比对既不可复核，也会在措辞一变时静默失效。\n"
            "       模板见 templates/design-brief.md。")
    body = m.group(1)
    kv = {}
    for mm in re.finditer(r'([一-龥A-Za-z]+)\s*=\s*([^|\n]+)', body):
        kv[mm.group(1).strip()] = mm.group(2).strip()
    reasons = {}
    for mm in re.finditer(r'偏离\s*([一-龥A-Za-z]+)\s*[:：]\s*([^\n]+)', s):
        reasons[mm.group(1).strip()] = mm.group(2).strip()
    return kv, reasons


def cmd_check(p, brief, mode):
    if mode not in ("greenfield", "preserve", "overhaul"):
        die("--mode 必须是 greenfield / preserve / overhaul（重设计协议三模式）")
    kv, reasons = parse_brief(brief)
    prof = load(p, create=True)
    sig = strong_signals(prof)
    rej = rejections(prof)
    last = prof.get("generations", [])[-1] if prof.get("generations") else None
    rows, bad = [], 0

    # ---- 品味轴：收敛 ----
    if not sig:
        rows.append(("NA", "品味轴", "档案还没有强信号，本次不做偏置"))
    for d, (v, s, _why) in sig.items():
        got = kv.get(d)
        if got is None:
            rows.append(("NA", "品味·" + d, "简报里没写这个维度"))
        elif got == v:
            rows.append(("PASS", "品味·" + d, "与档案一致：%s（置信 %.2f）" % (v, s)))
        elif d in reasons:
            rows.append(("PASS", "品味·" + d, "偏离 %s→%s，已写明理由：%s" % (v, got, reasons[d])))
        else:
            bad += 1
            rows.append(("FAIL", "品味·" + d,
                         "偏离档案（%s → %s）却没写理由。**偏离是允许的，沉默地偏离不允许**——"
                         "在简报里写一行「偏离%s：<为什么这次不一样>」" % (v, got, d)))
    # ---- 明确否决 ----
    for d, vs in rej.items():
        if kv.get(d) in vs:
            bad += 1
            rows.append(("FAIL", "否决·" + d, "「%s」是用户明确否决过的，不许再出现" % kv[d]))

    # ---- 执行轴：按模式定方向 ----
    if not last:
        rows.append(("NA", "执行轴", "没有上一代记录，本次无从比对（跑 log-generation 记下本代）"))
    else:
        same = [d for d in EXEC_DIMS if kv.get(d) and last.get(d) and kv[d] == last[d]]
        diff = [d for d in EXEC_DIMS if kv.get(d) and last.get(d) and kv[d] != last[d]]
        if mode in ("greenfield", "overhaul"):
            if same:
                bad += 1
                rows.append(("FAIL", "执行轴", "与上一代复用了 %s —— %s 模式要求执行轴发散。"
                             "**同一气质下换具体值是发散，不是背叛**（衬线换衬线可以，衬线换无衬线才是改品味）"
                             % ("/".join(same), mode)))
            else:
                rows.append(("PASS", "执行轴", "%d 项全部与上代不同：%s" % (len(diff), "/".join(diff) or "—")))
        else:  # preserve
            if diff:
                bad += 1
                rows.append(("FAIL", "执行轴", "Preserve 模式**反过来**：要保留现有执行，而 %s 变了。"
                             "要动就走 Overhaul 并说明旧方案哪里错了" % "/".join(diff)))
            else:
                rows.append(("PASS", "执行轴", "Preserve 模式下执行轴保持不变"))

    icon = {"PASS": "✅", "FAIL": "❌", "NA": "➖"}
    print("# 品味/执行 两轴校验　模式=%s" % mode)
    for st, k, ev in rows:
        print("%s [%s] %s" % (icon[st], k, ev))
    np_ = sum(1 for r in rows if r[0] == "PASS"); nf = sum(1 for r in rows if r[0] == "FAIL")
    nn = sum(1 for r in rows if r[0] == "NA")
    print("\n通过 %d · 冲突 %d · 不适用 %d（分母只算通过+冲突 = %d）" % (np_, nf, nn, np_ + nf))
    print("⚠️ 品味轴的冲突**不是「你错了」，是「你没说为什么」**——写一行理由即可放行。")
    print("   它记的是偏好，不是真理；用户这次要不一样，档案就该跟着更新。")
    return 1 if bad else 0


# ------------------------------------------------------------------ M8 自证
BRIEF_TMPL = """# 设计简报
<!-- taste-axes
品味轴: 明暗=%(明暗)s | 档位=%(档位)s | 字体气质=%(字体气质)s | 色温=中性 | 密度=宽松 | 动效=克制
执行轴: 字体族=%(字体族)s | 强调色=%(强调色)s | 视觉锚点=%(视觉锚点)s | 布局=%(布局)s
-->
%(extra)s
"""


def brief(path, **kw):
    d = {"明暗": "浅色", "档位": "克制", "字体气质": "衬线",
         "字体族": "Source Serif", "强调色": "#1F6F5C",
         "视觉锚点": "muji-kenya-hara", "布局": "单栏长卷", "extra": ""}
    d.update(kw)
    io.open(path, 'w', encoding='utf-8').write(BRIEF_TMPL % d)
    return path


def self_test():
    t = tempfile.mkdtemp(prefix="tm-")
    me = os.path.abspath(__file__)
    def run(*a):
        return subprocess.call([sys.executable, me] + list(a),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-42s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    P = os.path.join(t, "taste.json")
    # 首次：无档案 → check 应通过（无偏置可施）
    case("首次无档案 → 不阻碍", run('check', P, '--brief', brief(os.path.join(t, 'b0.md')),
                                 '--mode', 'greenfield'), 0)
    # 单次认可不构成强信号
    run('record', P, '--dim', '明暗', '--value', '浅色', '--verdict', 'approved')
    case("单次认可不构成强信号 → 偏离也不拦",
         run('check', P, '--brief', brief(os.path.join(t, 'b1.md'), 明暗='深色'), '--mode', 'greenfield'), 0)
    # 第二次认可 → 强信号成立
    run('record', P, '--dim', '明暗', '--value', '浅色', '--verdict', 'approved')
    case("≥2 次后偏离且无理由 → 冲突",
         run('check', P, '--brief', brief(os.path.join(t, 'b2.md'), 明暗='深色'), '--mode', 'greenfield'), 1)
    case("同样偏离但写明理由 → 放行",
         run('check', P, '--brief', brief(os.path.join(t, 'b3.md'), 明暗='深色',
                                          extra='偏离明暗：本次是影院模式，深色是内容要求'), '--mode', 'greenfield'), 0)
    case("与档案一致 → 通过",
         run('check', P, '--brief', brief(os.path.join(t, 'b4.md')), '--mode', 'greenfield'), 0)
    # 明确否决
    for _ in range(2):
        run('record', P, '--dim', '字体气质', '--value', '展示体', '--verdict', 'rejected')
    case("命中明确否决 → 冲突",
         run('check', P, '--brief', brief(os.path.join(t, 'b5.md'), 字体气质='展示体'), '--mode', 'greenfield'), 1)
    # 执行轴
    run('log-generation', P, '--font', 'Source Serif', '--accent', '#1F6F5C',
        '--anchor', 'muji-kenya-hara', '--layout', '单栏长卷')
    case("Greenfield 复用上代执行轴 → 冲突",
         run('check', P, '--brief', brief(os.path.join(t, 'b6.md')), '--mode', 'greenfield'), 1)
    case("Greenfield 同气质换具体值 → 通过",
         run('check', P, '--brief', brief(os.path.join(t, 'b7.md'), 字体族='Charter', 强调色='#8A4B2A',
                                          视觉锚点='vignelli', 布局='双栏网格'), '--mode', 'greenfield'), 0)
    case("Preserve 模式反过来：执行轴变了 → 冲突",
         run('check', P, '--brief', brief(os.path.join(t, 'b8.md'), 字体族='Charter', 强调色='#8A4B2A',
                                          视觉锚点='vignelli', 布局='双栏网格'), '--mode', 'preserve'), 1)
    case("Preserve 模式保持不变 → 通过",
         run('check', P, '--brief', brief(os.path.join(t, 'b9.md')), '--mode', 'preserve'), 0)
    # 无效输入
    case("简报里没有 taste-axes 块 → 报 2 不报 0",
         run('check', P, '--brief', (io.open(os.path.join(t, 'nb.md'), 'w', encoding='utf-8').write("# 空简报\n"),
                                     os.path.join(t, 'nb.md'))[1], '--mode', 'greenfield'), 2)
    case("--mode 非法 → 报 2",
         run('check', P, '--brief', brief(os.path.join(t, 'ba.md')), '--mode', 'whatever'), 2)
    case("档案不存在时 read → 报 2",
         run('read', os.path.join(t, 'nope.json')), 2)
    case("执行轴属性想进品味档案 → 报 2（两轴不许混）",
         run('record', P, '--dim', '字体族', '--value', 'Georgia', '--verdict', 'approved'), 2)
    print("\n%s" % ("✅ 两轴机制会出声" if ok else "❌ 自证失败"))
    return 0 if ok else 1


# ------------------------------------------------------------------ main
if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    if '--self-test' in sys.argv: sys.exit(self_test())
    OPTS = {'--dim', '--value', '--verdict', '--classifier', '--why', '--brief', '--mode',
            '--font', '--accent', '--anchor', '--layout'}
    argv, pos, kv = sys.argv[1:], [], {}
    i = 0
    while i < len(argv):
        if argv[i] in OPTS and i + 1 < len(argv): kv[argv[i]] = argv[i + 1]; i += 2; continue
        if argv[i].startswith('--'): i += 1; continue
        pos.append(argv[i]); i += 1
    if len(pos) < 2: print(__doc__); sys.exit(2)
    cmd, path = pos[0], pos[1]
    if cmd == 'record':
        if not (kv.get('--dim') and kv.get('--value') and kv.get('--verdict') in ('approved', 'rejected')):
            die("record 需要 --dim --value --verdict approved|rejected")
        sys.exit(cmd_record(path, kv['--dim'], kv['--value'], kv['--verdict'],
                            kv.get('--classifier'), kv.get('--why')))
    if cmd == 'log-generation':
        m = {'字体族': kv.get('--font'), '强调色': kv.get('--accent'),
             '视觉锚点': kv.get('--anchor'), '布局': kv.get('--layout')}
        if not any(m.values()): die("log-generation 至少要给一项 --font/--accent/--anchor/--layout")
        sys.exit(cmd_log(path, m))
    if cmd == 'read':
        sys.exit(cmd_read(path, kv.get('--classifier'), '--json' in sys.argv))
    if cmd == 'check':
        if not kv.get('--brief'): die("check 需要 --brief <design-brief.md>")
        sys.exit(cmd_check(path, kv['--brief'], kv.get('--mode', '')))
    print(__doc__); sys.exit(2)
