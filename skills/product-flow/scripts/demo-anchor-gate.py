#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo 锚点门禁 —— S6 出场条件的机器实现。

═══ 为什么需要它 ═══
SKILL.md 第 439 行写着「demo 场景必须带锚点：`<section data-scene="f01-pc-empty"
data-fr="FR-011,AC-1">`」，而**没有任何东西在 S6 检查这件事**。
后果不是「少个属性」：G2（验收标准→demo）与 G3（demo→Figma）都以这个锚点为输入，
锚点不在就双双 UNABLE。

⭐ 2026-08-31 实测本 skill 自己的验证项目：demo 一个 `data-scene` 都没有，
   于是 **G2/G3 从未产出过任何结论** —— 而 SKILL.md 把它们列为「最容易出事的三个交接口」
   里的两个。锚点缺失在 S6 是个能当场修的小事，拖到 G2 就变成一句容易被耸肩带过的 UNABLE。

⚠️ 诚实边界：本门禁只查**锚点契约**（在不在、格式对不对、指向的 FR 存不存在），
   **不查 demo 做得好不好**，也不替代 G2/G3 的覆盖对账。

⚠️ 2026-09-01 补 baseline 路径：本门禁建起来时只认 HTML demo，
   而**已上线产品走 `baseline.md`**（S6 跳过、真实程序即 demo，锁基线清单代替）——
   那条路径的 S6 出场契约当时**没有任何机器检查**。
   ⭐ 特例路径断在机器契约上不会报错，只会安静地什么都不查。
   场景解析与 reconcile-gate 共用 `_scene_parse`，不各写一份。

用法:
  demo-anchor-gate.py <demo.html|baseline.md> [--prd <PRD.md>] [--json]
  demo-anchor-gate.py --self-test
退出码: 0=通过 1=不通过 2=跑不了
"""
import io, os, re, sys, json, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _prd_parse
import _scene_parse

SCENE_RE = re.compile(r'data-scene\s*=\s*"([^"]*)"([^>]*)')
FR_RE = re.compile(r'data-fr\s*=\s*"([^"]*)"')
# G3 按 `f01-empty` 拆「功能-状态」，所以 ID 必须以 fNN 开头且至少两段
ID_RE = re.compile(r'^f\d{2}(?:-[a-z0-9]+)+$', re.I)
# ⚠️ 先剥 HTML 注释再扫。首版没剥，于是 templates/demo-scaffold.html 在注释里
#    写「data-scene="fNN-状态"」示范契约，**被当成了第 4 个真场景并判不合规** ——
#    一道会因为「你把契约写进注释」而报红的门是反的；被注释掉的场景也本就不该计数。
COMMENT_RE = re.compile(r'<!--.*?-->', re.S)


def die(m):
    print("UNABLE: %s" % m, file=sys.stderr)
    sys.exit(2)


def check(path, prd=None):
    if not os.path.exists(path):
        die("不存在 %s" % path)
    is_md = path.lower().endswith('.md')
    is_dump = path.lower().endswith('.json')
    raw = io.open(path, encoding='utf-8', errors='replace').read()
    if is_dump:
        # 可运行原型：锚点是运行时写到 body 上的，静态扫 HTML 一个也看不到。
        # 输入换成 `scenario-matrix-gate --dump` 的**实测**锚点。
        # ⚠️ 这里此前把非 .md 一律当 HTML 扫 —— 喂 dump 进来会报「零锚点」，
        #    而「零锚点」与「真的没贴锚点」在输出上一模一样。
        kind = 'demo(实测)'
        scenes = _scene_parse.measured_scenes(raw)
    elif is_md:
        kind = 'baseline'
        scenes = [(sid, frs) for sid, frs in _scene_parse.baseline_scenes(raw)]
    else:
        kind = 'demo'
        html = COMMENT_RE.sub('', raw)
        scenes = [(sid, [x.strip() for x in (m.group(1) or '').split(',') if x.strip()])
                  for sid, m in ((mm.group(1), FR_RE.search(mm.group(2)))
                                 for mm in SCENE_RE.finditer(html))]
    res = []

    def add(rid, desc, ok, ev):
        res.append({"id": rid, "desc": desc, "ok": ok, "ev": ev})

    add("has-anchor",
        "demo 要有 data-scene 锚点 / baseline 要有「场景×需求」表（没有它 G2/G3 只能 UNABLE）",
        bool(scenes), "%s：%d 个场景锚点" % (kind, len(scenes)) if scenes else
        ("%s 里一个都没有" % kind))
    if not scenes:
        return res  # 后面几条无从谈起，如实短路，不假装查过

    bad_id = [sid for sid, _ in scenes if not ID_RE.match(sid or '')]
    add("id-format", "场景 ID 形如 `f01-empty`（G3 按段拆「功能-状态」，命名不合就对不上）",
        not bad_id, ("不合规: " + ", ".join(bad_id[:6])) if bad_id else "%d 个全合规" % len(scenes))

    no_fr = [sid for sid, fr in scenes if not fr]
    add("has-fr", "每个场景都要有非空 data-fr（反查不到需求的场景 = 没人要的画面）",
        not no_fr, ("缺 data-fr: " + ", ".join(no_fr[:6])) if no_fr else "全部有")

    if prd:
        if not os.path.exists(prd):
            die("PRD 不存在 %s" % prd)
        text = io.open(prd, encoding='utf-8', errors='replace').read()
        seg = _prd_parse.appendix(text)
        if seg is None:
            die("PRD 里找不到附件 A（`# 附件 A` … `# 附件 B`）")
        known = set(_prd_parse.fr_owners(text, seg)) | set(_prd_parse.ac_ids(text, seg))
        if not known:
            die("PRD 附件 A 里解析不出任何 FR/AC —— 判据失配，这不是通过")
        # ⚠️ 认**带归属**写法 `FR-031/AC-2`：2026-09-03 给 reconcile-gate G2 加了这种写法，
        #    却没同步教本门禁，于是它把新写法整片当成悬空引用。
        #    ⭐ 引入一种新记号，必须更新**每一个消费它的地方** —— 加一个能力不是只加了那个能力。
        def resolvable(x):
            if x in known: return True
            if '/' in x:
                f, _, a = x.partition('/')
                return f in known and a in known
            return False
        ghost = sorted({x for _, fr in scenes for x in (fr or []) if not resolvable(x)})
        add("fr-resolvable", "场景引用的需求编号必须在 PRD 附件 A 里真的存在（悬空引用）",
            not ghost, ("PRD 里没有: " + ", ".join(ghost[:6])) if ghost else "全部可解析")
    return res


def report(res, as_json=False):
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for r in res:
            print("  %s [%s] %s" % ("✅" if r["ok"] else "❌", r["id"], r["desc"]))
            print("       %s" % r["ev"])
        bad = [r for r in res if not r["ok"]]
        print("\n结论：%s" % ("通过" if not bad else "不通过（%d 条）" % len(bad)))
        print("⚠️ 只查锚点契约，不查 demo 做得好不好；覆盖对账仍要跑 reconcile-gate G2/G3。")
    return 0 if all(r["ok"] is not False for r in res) else 1   # N/A 不算失败，口径同其余门禁


def _w(d, name, body):
    p = os.path.join(d, name)
    io.open(p, 'w', encoding='utf-8').write(body)
    return p


def self_test():
    """每条判据都要有**反例**：只有正例的门永远绿。"""
    ok = True

    def run(name, html, want_fail, prd=None, ext='.html'):
        nonlocal ok
        d = tempfile.mkdtemp()
        f = os.path.join(d, 'demo' + ext)
        io.open(f, 'w', encoding='utf-8').write(html)
        pf = None
        if prd is not None:
            pf = os.path.join(d, 'prd.md')
            io.open(pf, 'w', encoding='utf-8').write(prd)
        res = check(f, pf)
        got = [r["id"] for r in res if not r["ok"]]
        good = (set(got) == set(want_fail))
        print(("  ✓ " if good else "  ✗ ") + name + ("　期望红 %s 实得 %s" % (want_fail, got) if not good else ""))
        ok = ok and good

    GOOD = '<section data-scene="f01-empty" data-fr="FR-011">x</section>'
    PRD = "# 附件 A\n### FR-011　所属 F-01　MUST\n# 附件 B"
    run("正例：锚点齐全", GOOD, [])
    run("反例1 一个锚点都没有（验证项目 实测就是这种）", '<section>x</section>', ["has-anchor"])
    run("反例2 场景 ID 不合 fNN-… 命名", '<section data-scene="empty" data-fr="FR-011">x</section>',
        ["id-format"])
    run("反例3 data-fr 为空（画面反查不到需求）", '<section data-scene="f01-empty" data-fr="">x</section>',
        ["has-fr"])
    run("反例4 data-fr 指向 PRD 里不存在的 FR（悬空引用）",
        '<section data-scene="f01-empty" data-fr="FR-999">x</section>', ["fr-resolvable"], PRD)
    run("正例：带 PRD 时可解析", GOOD, [], PRD)
    # ⚠️ 这条是本门禁自己踩过的坑：注释里写契约示范，被当成真场景判红。
    run("注释里的锚点示范不算真场景（模板正是这么写文档的）",
        '<!-- 示范：data-scene="fNN-状态" data-fr="FR-x" -->\n' + GOOD, [])
    run("被注释掉的整个场景不计数（否则删不干净的旧场景会一直报红）",
        '<!--<section data-scene="bad" data-fr="">旧的</section>-->\n' + GOOD, [])
    # ── baseline 路径（已上线产品）也要有正反例 ──
    BL_GOOD = ("| 场景ID | 对应需求 | 进入路径 |\n|---|---|---|\n"
               "| f01-empty | FR-011 | 菜单>导入 |\n")
    run("baseline 正例：场景×需求表齐全", BL_GOOD, [], PRD, ext='.md')
    run("baseline 反例1 根本没有那张表（S6 只锁了个空文件）",
        "# 基线清单\n还没填。\n", ["has-anchor"], ext='.md')
    run("baseline 反例2 场景 ID 不合 fNN-… 命名",
        BL_GOOD.replace('f01-empty', 'empty'), ["id-format"], ext='.md')
    # ⚠️ 期望写错过一次：需求列留空时场景**仍被解析出来**，该红的是 has-fr（有场景没需求），
    #    不是 has-anchor（连场景都没有）。两者语义不同，别混。
    run("baseline 反例3 对应需求列留空（有场景没需求）",
        "| 场景ID | 对应需求 |\n|---|---|\n| f01-empty |  |\n", ["has-fr"], ext='.md')
    run("baseline 反例4 引用 PRD 里不存在的 FR",
        BL_GOOD.replace('FR-011', 'FR-999'), ["fr-resolvable"], PRD, ext='.md')

    # ── 实测锚点路径（可运行原型）也要有正反例 ──
    # ⚠️ 这条分支此前不存在：非 .md 一律当 HTML 扫，喂 dump 进来会报「零锚点」，
    #    而「零锚点」与「真的没贴锚点」在输出上一模一样 —— 又一处安静的假红。
    DUMP = ('{"measuredBy":"scenario-matrix-gate","scenes":['
            '{"scene":"f01-pc-empty","fr":"FR-011"}]}')
    run("实测锚点正例：dump 里的场景认得出", DUMP, [], PRD, ext='.json')
    run("实测锚点反例1 一个场景都没走到（矩阵门跑空了）",
        '{"measuredBy":"scenario-matrix-gate","scenes":[]}', ["has-anchor"], ext='.json')
    run("实测锚点反例2 场景 ID 不合 fNN-… 命名",
        DUMP.replace('f01-pc-empty', 'empty'), ["id-format"], ext='.json')
    run("实测锚点反例3 fr 为空（走到了但反查不到需求）",
        DUMP.replace('"fr":"FR-011"', '"fr":""'), ["has-fr"], ext='.json')
    run("实测锚点反例4 引用 PRD 里不存在的 FR",
        DUMP.replace('FR-011', 'FR-999'), ["fr-resolvable"], PRD, ext='.json')

    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：这道门不可信，先修它"))

    # 🆕 2026-09-05 `unexecuted-check --unable` 实测：本门 6 个「跑不了」出口
    #    **5 个从没被触发过** —— `die()` 函数体本身都没执行过，
    #    说明这道门的自证**一条「跑不了」用例都没有**。
    #    ⭐ 「读不到就报 UNABLE」这类守卫锚点写错时会**两头都不出声** ——
    #    既不报「没跑过」也不报缺陷。（形状由并行会话 peer-agent-c0 提出。）
    import subprocess as _sp
    _me = os.path.abspath(__file__)
    _d = tempfile.mkdtemp()

    def _rc(args):
        return _sp.call([sys.executable, _me] + args,
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)

    _demo = os.path.join(_d, 'ok.html')
    io.open(_demo, 'w', encoding='utf-8').write(GOOD)
    for _name, _args in [
        ("demo 不存在 → 2", [os.path.join(_d, 'nope.html')]),
        ("PRD 不存在 → 2", [_demo, '--prd', os.path.join(_d, 'nope.md')]),
        ("PRD 里没有附件 A → 2",
         [_demo, '--prd', _w(_d, 'noa.md', "# 附件 B\n随便写点\n")]),
        ("附件 A 里解析不出任何 FR/AC → 2",
         [_demo, '--prd', _w(_d, 'empty_a.md', "# 附件 A\n（空）\n# 附件 B\n")]),
    ]:
        _got = _rc(_args); _g = _got == 2; ok = ok and _g
        print(("  ✓ " if _g else "  ✗ ") + _name + ("" if _g else "　期望 2 实得 %d" % _got))

    return ok



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
            # ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.py）
            import os as _os, sys as _sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            from _argv import reject_unknown
            reject_unknown({'--json', '--prd', '--self-test'},
                "本门禁：demo-anchor-gate.py <demo.html> [--prd <PRD.md>]")
            a = sys.argv[1:]
            if '--self-test' in a:
                sys.exit(0 if self_test() else 1)
            if not a:
                print(__doc__); sys.exit(2)
            prd = a[a.index('--prd') + 1] if '--prd' in a else None
            sys.exit(report(check(a[0], prd), '--json' in a))
    _main_guarded(_entry)
