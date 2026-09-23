#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自证期间**从未执行过**的失败记录行 —— 变异扫描区分不了的那一类。

═══ 它补的是哪个洞 ═══
`mutation-sweep` 回答「这条判据有没有反例守着」，但它**区分不了两种「没红」**：
  · 判据执行了，只是被别的判据遮住了
  · 判据**根本没执行过**（前提从没成立 —— 比如「有 <table> 才要求 tabular-nums」，
    而夹具里根本没有 <table>）
⭐ **一条被前提挡住的断言，和一条跑了且通过的断言，在门禁输出里完全一样。**
（形状由并行会话 fm-agent 提出，它那边做成了 `unexecuted-assertions.js`。）

═══ ⚠️ 它测不了什么（诚实边界，不许当成「没问题」）═══
`trace` **追不进子进程**。而本仓多数门禁的自证是
`subprocess.call([sys.executable, me, fixture])` —— 判据行在子进程里执行，
父进程一个都看不见 ⇒ **会把「执行过」全部误报成「从未执行」**。
2026-09-05 首版就是这么干的，差点报出 4 条不存在的发现
（其中 2 条刚被变异扫描证明**有反例守着**）。
⇒ 这类自证一律报 **UNABLE**，不猜。（注入法的理由是**零依赖**。
   ⚠️ 订正的订正：我一度写「复核发现 coverage 本机就有，先前那句『没装』是错的」——
   **那句订正本身才是错的**。查安装时间：`site-packages/coverage` 的 mtime 是
   2026-09-05 17:57，是并行会话当天 `pip install --user` 装的。
   ⭐⭐ **重新测量得到不同结果时，第一问是「环境变了吗」，不是「我原来错了」。**
   我因为环境在两次观测之间被改动，把一个**当时正确**的结论订正成了错的。）

退出码: 0=每条失败记录行都执行过 1=有从未执行的 2=跑不了/量程外
"""
import ast, sys, os, re, io, trace, runpy, tempfile, subprocess

# ⚠️ 变量名清单是按**语义**挑的，不是照单全收：
#    `findings` 记的是发现（纳入）；`out` **要看它 append 的是什么形状** ——
#    `out.append((...))` / `out.append({...})` 是一条结论（纳入），
#    而 `out.append(str(v))` / `out.append(css[i:])` 是**字符串累加器**（排除）。
#    ⚠️ 首版按变量名一律纳入 `out` ⇒ 5 个命中里 2 个是假阳性（40%）。
#    `notes` / `decay` / `fwd` 记的是**说明文字与中间数据**（不纳入 —— 纳入只会制造噪音，
#    而假阳性会让人给这道门加豁免清单，然后就没人跑它了）。
#    ⭐ 加宽量程前先看那个变量到底在记什么，不许照变量名猜。
# 两种「记录一处结论」的形态都要认：
#   ① `bad.append(...)` —— 记录一处失败
#   ② `add(rid, desc, ok, ev)` —— 记录一条规则的结论
# ⚠️ 只认 ① 时，17 道门里 11 道被判「量程外」—— 而它们只是用了另一种写法。
#    「工具测不了」和「这些门用了别的写法」是两回事，前者会被读成后者。
SITE = re.compile(r"""([ \t]*)((?:bad|fails|failures|problems|issues|errs|miss|missing"""
                  r"""|thin|hits|dup|bads|findings)\.append\(|out\.append\(\s*[({]|add\(\s*['"])""")
# ⚠️ 不许按字面模块名识别：`import subprocess as _sp` 一别名就骗过去了 ——
#    2026-09-05 我自己在夹具里写了 `_sp.call(...)`，工具当场走错采集路径、
#    把子进程里跑过的三条判据全报成「从没执行」。**又一次「用名字当代理指标」。**
SUBPROC = re.compile(r'\w+\.(?:call|run|check_call|Popen)\(\s*\[\s*sys\.executable')


def sites(src):
    """返回 (可测的行号集合, 同行写法的行号集合)。

    ⚠️ 行级 trace 的根本限制：`if cond: bad.append(...)` **写在同一行**时，
    条件被求值就算「该行执行过」—— **分辨不出 append 有没有真的跑**。
    2026-09-05 自证当场抓到：我的正例夹具正是同行写法，于是「从没走到的行」
    被判成走到了。⇒ 同行写法一律列为**测不了**，不许算进「都执行过」。
    """
    lines = src.split('\n')
    ok, inline = set(), set()
    for m in SITE.finditer(src):
        ln = src[:m.start()].count('\n') + 1
        head = lines[ln - 1][:m.start() - (src.rfind('\n', 0, m.start()) + 1)]
        (inline if head.strip() else ok).add(ln)
    return ok, inline


SITECUSTOMIZE = """import sys, os, threading
_T = os.environ.get('UE_TARGET'); _D = os.environ.get('UE_OUT')
if _T and _D:
    _T = os.path.abspath(_T); _seen = set()
    def _tr(frame, event, arg):
        if event == 'line' and os.path.abspath(frame.f_code.co_filename) == _T:
            _seen.add(frame.f_lineno)
        return _tr
    def _dump():
        if _seen:
            with open(os.path.join(_D, 'h-%d' % os.getpid()), 'w') as f:
                f.write(repr(sorted(_seen)))
    import atexit; atexit.register(_dump)
    threading.settrace(_tr); sys.settrace(_tr)
"""


def _trace_via_children(target):
    """让**每个子进程**自己开 trace，把命中的行号写进共享目录后汇总。"""
    d = tempfile.mkdtemp(prefix='ue-inj-')
    io.open(os.path.join(d, 'sitecustomize.py'), 'w', encoding='utf-8').write(SITECUSTOMIZE)
    out = os.path.join(d, 'out'); os.makedirs(out, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONPATH'] = d + os.pathsep + env.get('PYTHONPATH', '')
    env['UE_TARGET'] = os.path.abspath(target)
    env['UE_OUT'] = out
    try:
        subprocess.run([sys.executable, target, '--self-test'],
                       env=env, capture_output=True, timeout=900)
    except Exception:
        return None
    hit = set()
    for f in os.listdir(out):
        try:
            hit |= set(ast.literal_eval(io.open(os.path.join(out, f), encoding='utf-8').read()))
        except Exception:
            pass
    return hit or None


# 第三类站点：**UNABLE 出口**（`--unable` 模式）。
# ⭐ 形状由并行会话 peer-agent-c0 提出：「读不到就报 UNABLE」这类前提守卫，
#   **锚点写错时会静默失效** —— 既不报「没跑过」，也不报缺陷，**两头都不出声**，
#   比漏判更隐蔽。本仓共 78 处这样的出口，此前一条都没被证明会出声。
SITE_UNABLE = re.compile(r"""([ \t]*)((?:print|console\.error)\([^\n]*UNABLE|die\()""")

SITE_MJS = re.compile(r"""([ \t]*)((?:bad|fails|issues|problems|errs|miss)\.push\()""")


def _trace_mjs(target):
    """Node 侧：用内置 `NODE_V8_COVERAGE` 采集（零依赖）。

    ⚠️⚠️ **必须在门禁自己的目录里跑**。2026-09-05 我把门禁拷到 /tmp 做对照，
    它 `import './_browser.mjs'` 找不到依赖、**模块根本没加载成功**，
    退出码 1 是加载失败不是自证失败 —— 于是「一行覆盖都没有」，
    而我把这读成了「Node 覆盖对真门禁不可用」，还沿着这个错误前提做了三轮归因。
    ⭐ **对照组失败时，第一嫌疑人是对照组自己。**

    V8 给的是**字节偏移区间 + 命中次数**，`count == 0` 的是没走到的段。
    """
    import json, glob, tempfile, subprocess
    d = tempfile.mkdtemp(prefix='ue-mjs-')
    env = dict(os.environ); env['NODE_V8_COVERAGE'] = d
    try:
        subprocess.run(['node', os.path.basename(target), '--self-test'],
                       cwd=os.path.dirname(os.path.abspath(target)),
                       env=env, capture_output=True, timeout=1800)
    except Exception:
        return None
    src = io.open(target, encoding='utf-8').read()
    # ⚠️⚠️ 自证是**用子进程**跑门禁的：父进程那份覆盖里业务逻辑当然全是死的。
    #    首版把各覆盖文件的死区间做**并集** ⇒ `scenario-matrix` 5 个站点 5 个都被判死，
    #    而它们在子进程里跑得好好的。**一个站点只有在所有覆盖文件里都死，才算真死** ⇒ 取交集。
    per_file, seen = [], False
    for f in glob.glob(os.path.join(d, '*.json')):
        try: cov = json.load(io.open(f, encoding='utf-8'))
        except Exception: continue
        for s in cov.get('result', []):
            if not s.get('url', '').endswith(os.path.basename(target)): continue
            seen = True
            per_file.append([(r['startOffset'], r['endOffset'])
                             for fn in s.get('functions', []) for r in fn.get('ranges', [])
                             if r.get('count') == 0])
    if not seen:
        return None
    # 交集：站点必须在**每一份**覆盖里都落在死区间内
    def in_any(off, rs): return any(a <= off < z for a, z in rs)
    dead = [(a, z) for a, z in (per_file[0] if per_file else [])
            if all(in_any(a, rs) for rs in per_file[1:])]
    # ⚠️⚠️ V8 的偏移是**字符**（UTF-16 code unit），**不是 UTF-8 字节**。
    #    本仓文件满是中文注释 ⇒ 按字节切算出的行号**系统性偏小**，
    #    2026-09-05 实测：注入在 L121 的必死分支，被算成落在 (109,118) 之外 ⇒ 漏报。
    #    ⭐ 又是「用一个没验证过的代理指标」——我拿字节当了字符。
    # ⛔ 不许把「死区间」摊成「整行集合」—— 一个跨行的死区间会把相邻行一起标死。
    #    2026-09-05 实测：这么做会误报一条**有反例守着**的判据（假阳性）。
    #    正确做法是**按站点自身的偏移**判断它是否落在某个死区间内。
    return dead


def _trace_py_inproc(target):
    """在**本进程**里跑目标的自证并追行（适用于自证不开子进程的门禁）。"""
    tr = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix])
    argv0 = sys.argv[:]
    sys.argv = [target, '--self-test']
    try:
        tr.runfunc(runpy.run_path, target, run_name='__main__')
    except SystemExit:
        pass
    except Exception:
        return None
    finally:
        sys.argv = argv0
    return {ln for (f, ln) in tr.results().counts
            if os.path.abspath(f) == os.path.abspath(target)} or None


def _strip_selftest(src):
    """砍掉自证函数自身 —— 它里面的 UNABLE 字样是**在讲自己**，不是门禁的出口。"""
    for marker in ('\ndef _self_test', '\ndef self_test', '\nasync function selfTest',
                   '\nfunction selfTest'):
        i = src.find(marker)
        if i > 0: return src[:i]
    return src


def check(target, mode='conclusion'):
    src = io.open(target, encoding='utf-8').read()
    if mode == 'unable':
        body = _strip_selftest(src)
        want = {body[:m.start(2)].count('\n') + 1: m.start(2)
                for m in SITE_UNABLE.finditer(body)}
        if not want:
            print("UNABLE: %s 没有 UNABLE/die 出口（量程外）" % os.path.basename(target)); return 2
        if target.endswith('.mjs'):
            dead = _trace_mjs(target)
            if dead is None:
                print("UNABLE: %s 采集不到 V8 覆盖" % os.path.basename(target)); return 2
            never = sorted(ln for ln, off in want.items()
                           if any(a <= off < z for a, z in dead))
        else:
            hit = (_trace_via_children(target) if SUBPROC.search(src)
                   else _trace_py_inproc(target))
            if hit is None:
                print("UNABLE: %s 采集不到覆盖" % os.path.basename(target)); return 2
            never = sorted(ln for ln in want if ln not in hit)
        print("%-30s UNABLE 出口 %d 处 · 自证期间从没被触发 %d 处"
              % (os.path.basename(target), len(want), len(never)))
        for ln in never:
            print("     L%-5d %s" % (ln, src.split('\n')[ln - 1].strip()[:88]))
        return 1 if never else 0
    if target.endswith('.mjs'):
        want = {src[:m.start()].count('\n') + 1 for m in SITE_MJS.finditer(src)}
        if not want:
            print("UNABLE: %s 找不到 bad.push( 式的结论记录（量程外，不是「没问题」）"
                  % os.path.basename(target)); return 2
        dead = _trace_mjs(target)
        if dead is None:
            print("UNABLE: %s 采集不到 V8 覆盖数据" % os.path.basename(target)); return 2
        # 站点自身的字符偏移落在任一死区间内 ⇒ 这条判据从没执行
        offs = {src[:m.start(2)].count('\n') + 1: m.start(2) for m in SITE_MJS.finditer(src)}
        never = sorted(ln for ln, off in offs.items() if any(a <= off < z for a, z in dead))
        print("%-30s 结论记录行 %d 处 · 自证期间从未执行 %d 处"
              % (os.path.basename(target), len(want), len(never)))
        for ln in never:
            print("     L%-5d %s" % (ln, src.split('\n')[ln - 1].strip()[:88]))
        return 1 if never else 0
    use_child = bool(SUBPROC.search(src))
    want, inline = sites(src)
    if inline:
        print("   ⏭️  %d 处**同行写法**（`if cond: append(...)`）行级 trace 测不了，"
              "已排除在结论外：%s" % (len(inline), sorted(inline)))
    if not want and not inline:
        print("UNABLE: %s 既没有 X.append 也没有 add(rid,…)（量程外，不是「没问题」）"
              % os.path.basename(target)); return 2
    if not want:
        print("UNABLE: %s 的失败记录**全是同行写法**，行级 trace 一条都测不了"
              % os.path.basename(target)); return 2
    if use_child:
        # ⭐ 自证用子进程跑门禁，而 `trace` 追不进子进程。不装 coverage.py 的解法：
        #    用 PYTHONPATH 注入 sitecustomize，**让每个子进程自己开 trace**。
        #    2026-09-05：首版直接对这类报 UNABLE ⇒ 17 道门一道都测不了，
        #    工具等于不存在。**「我测不了」是诚实，但不该是终点。**
        hit = _trace_via_children(target)
        if hit is None:
            print("UNABLE: %s 注入 trace 没拿到任何命中行（可能自证没真跑）"
                  % os.path.basename(target)); return 2
    else:
        t = trace.Trace(count=1, trace=0, ignoredirs=[sys.prefix])
        argv0 = sys.argv[:]
        sys.argv = [target, '--self-test']
        try:
            t.runfunc(runpy.run_path, target, run_name='__main__')
        except SystemExit:
            pass
        finally:
            sys.argv = argv0
        hit = {ln for (f, ln) in t.results().counts
               if os.path.abspath(f) == os.path.abspath(target)}
    never = sorted(want - hit)
    print("%-30s 结论记录行 %d 处 · 自证期间从未执行 %d 处"
          % (os.path.basename(target), len(want), len(never)))
    for ln in never:
        print("     L%-5d %s" % (ln, src.split('\n')[ln - 1].strip()[:88]))
    return 1 if never else 0


def self_test():
    import tempfile
    d = tempfile.mkdtemp(prefix='ue-')
    good = os.path.join(d, 'g.py')
    io.open(good, 'w', encoding='utf-8').write('''import sys
def run(s):
    bad = []
    if "坏" in s: bad.append("走得到")
    if "绝不出现" in s:
        bad.append("永远走不到")
    return 1 if bad else 0
def self_test():
    print(run("有坏东西"), run("干净")); return 0
sys.exit(self_test() if "--self-test" in sys.argv else run(open(sys.argv[1]).read()))
''')
    sub = os.path.join(d, 's.py')
    io.open(sub, 'w', encoding='utf-8').write('''import sys, subprocess
def run(s):
    bad = []
    if "坏" in s:
        bad.append("走得到")
    if "绝不出现" in s:
        bad.append("永远走不到")
    return 1 if bad else 0
def self_test():
    import tempfile, os
    f = os.path.join(tempfile.mkdtemp(), "x.txt")
    open(f, "w").write("有坏东西")
    subprocess.call([sys.executable, __file__, f]); return 0
sys.exit(self_test() if "--self-test" in sys.argv else run(open(sys.argv[1]).read()))
''')
    # ⭐ add(rid,…) 形态：一条规则写在**只有某种输入才走到**的分支里 ——
    #    那条规则整个没被评估过，而门禁输出里看不出任何异常。
    addf = os.path.join(d, 'a.py')
    io.open(addf, 'w', encoding='utf-8').write("""import sys
def run(s):
    rows = []
    def add(rid, desc, ok, ev): rows.append((rid, ok))
    add("always", "d", "坏" not in s, "")
    if "表格" in s:
        add("only-table", "d", "空格子" not in s, "")
    return 1 if any(not ok for _, ok in rows) else 0
def self_test():
    print(run("有坏东西"), run("干净"))
    return 0
sys.exit(self_test() if "--self-test" in sys.argv else run(open(sys.argv[1]).read()))
""")
    plain = os.path.join(d, 'p.py')
    io.open(plain, 'w', encoding='utf-8').write('print("no sites")\n')
    print("M8 自证 —— 走不到的要报出来 / 子进程式自证要报 UNABLE 而不是瞎猜\n")
    cases = [('从没走到的失败行必须被报出来（多行写法）', check(good), 1),
             ('⭐ 子进程式自证：注入 trace 后能测出「永远走不到」那行', check(sub), 1),
             ('⭐ add(rid,…) 形态：只在某种输入下才走到的规则要被报出来',
              check(addf), 1),
             ('没有失败记录行 → 报 2（量程外）', check(plain), 2)]
    ok = True
    for n, got, want in cases:
        g = got == want; ok &= g
        print("  %s %-46s 期望 %d 实得 %d" % ('✅' if g else '❌', n, want, got))
    print("\n" + ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修工具"))
    return 0 if ok else 1


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--self-test' in a: sys.exit(self_test())
    if '--help' in a or not a: print(__doc__.strip()); sys.exit(0 if a else 2)
    mode = 'unable' if '--unable' in a else 'conclusion'
    sys.exit(max(check(x, mode) for x in a if not x.startswith('-')))
