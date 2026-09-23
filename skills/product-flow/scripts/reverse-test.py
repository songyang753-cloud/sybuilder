#!/usr/bin/env python3
"""反向测试跑手 —— 在工作区文件上做**可撤销的**变异，验判据是否承重。

为什么需要它（三条都是 2026-09-05 实测踩到的）：

  ① **变异没生效，而"绿"被读成"复原正常"。**
     我手写的变异脚本抛了 `substring not found`（缩进 4 空格写成 8），
     变异根本没应用，随后那次绿差点被当成结论。
     ⇒ 这里强制断言：变异后文件内容**必须**变化，否则报 2 拒绝继续。

  ② **变异期间被杀 ⇒ 工作区留在变异态。**
     同日一次全量自证被 10 分钟超时 SIGTERM 杀掉。
     ⇒ 这里把还原放进 finally，并接管 SIGINT/SIGTERM。

  ③ **没有锁 ⇒ 两个会话的还原互相覆盖。**
     并行会话（编程规范 skill）实测过：套件层没锁 ⇒ 一个实例的还原
     盖掉另一个实例开跑前的备份，工作区留下 4 处变异态。
     ⇒ 这里对整个仓库加一把文件锁，第二个实例**等**，不并发。

用法:
  reverse-test.py <目标文件> --replace <旧串> <新串> -- <命令...> [--expect N]
  reverse-test.py <目标文件> --delete-re <正则>   -- <命令...> [--expect N]
  reverse-test.py --self-test

退出码: 0=判据承重（变异后命令给出了期望的非零码） 1=**判据不承重**（变异后仍是原码）
        2=跑不了（变异没生效/文件不存在/参数错/还原失败——绝不折叠成 0）
"""
import sys, os, re, io, json, hashlib, signal, subprocess, tempfile, fcntl

REV_TIMEOUT = int(os.environ.get('REVTEST_TIMEOUT', '180'))  # 被测命令超时上限:防「命令挂死→锁被无限持有→第二实例无限等」

def _run(cmd, **kw):
    try:
        return subprocess.run(cmd, timeout=REV_TIMEOUT, **kw)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, e.stdout or b'', e.stderr or b'')  # 124=超时(GNU timeout 约定)

# 🚨🚨 2026-09-10 codex 二轮 #20（Critical）：锁与日志按**工具所在 checkout** 分键，
#   而本工具允许改**任意目标**。两个 checkout 各跑一份、指向同一个外部文件时，
#   两把锁是不同文件 ⇒ **根本不串行**：A 改 O→M1 运行，B 期间读到 M1 改成 M2，
#   A 先还原 O，B 最后按自己的快照还原 M1 —— 目标**永久留在变异态**。
#   ⭐ 上一轮我把「日志与锁同粒度」当成了修复，那只保证两者一起分叉，
#     **并不保证目标安全**。⇒ 锁的粒度必须由**目标**决定。
#   ⛔ 这也意味着 LOCK 不能是模块级常量了（它依赖运行时的 target）。
def _lock_path(target):
    _k = hashlib.sha1(os.path.realpath(target).encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), 'product-flow-rt-lock-%s' % _k)


def _journal_path(target):
    _k = hashlib.sha1(os.path.realpath(target).encode()).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), 'product-flow-rt-journal-%s.json' % _k)


LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.reverse-test.lock')

def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()

# ⭐ 崩溃日志 —— 放在系统临时目录，**不污染仓库**，但路径固定所以下次能找到。
# 🚨🚨 2026-09-10 第六轮独立复核（F4）：日志原本是**全机固定路径**，而锁是
#   **各 checkout 私有**（`scripts/../.reverse-test.lock`）—— 全局日志配局部锁，
#   不同 checkout 之间根本不串行。实测后果比「没自愈」更糟：
#     A 正在 checkout1 上跑（文件处于活变异态），B 从 checkout2 起来，
#     `_recover()` 在拿锁**之前**执行 ⇒ **B 把 A 的活变异当成崩溃残留还原了**，
#     还删了 A 的日志。A 随后拿**未变异的文件**跑出结论，
#     把一条真正承重的判据报成「不承重」——**反向结论**。
#   ⭐ 崩溃自愈的保证，恰好在「两个会话并行」这个它被写出来要覆盖的场景下失效。
#   ⇒ 两处一起改：①日志按 checkout 分键（与锁同粒度）②`_recover()` 移到**拿锁之后**。
_JOURNAL = os.path.join(
    tempfile.gettempdir(),
    'product-flow-rt-journal-%s.json'
    % hashlib.sha1(os.path.dirname(os.path.abspath(__file__)).encode()).hexdigest()[:12])


def _recover(target=None):
    """启动时先自愈：上一次如果被 SIGKILL/断电打断，把被测物还原回去。

    🚨🚨 2026-09-09：本工具**原地变异真实文件**，还原挂在 `finally` 与
      SIGINT/SIGTERM 处理器上 —— ⛔ 这三条路径**都盖不住 SIGKILL、断电、OOM**。
      本仓早有一条教训叫「finally 非信号安全」，这里是它的活实例。
    ⭐ 触发不是理论风险：同一天，并行会话的同型工具被硬打断，
      **变异串留在了邻座 skill 的工作区里**，把对方的闭环契约门禁卡死，
      两个窗口各花一轮才定位到「那行文本是变异表第 12 条的确切新串」。
    ⭐ `mutation-sweep` 已整体改副本模式（变异只碰副本）。本工具做不到那样：
      它接收的是**调用方给的任意命令**，命令里写的是真实路径，搬走就跑不通了。
      ⇒ 退而求其次但同样有效：**先把原文落盘成日志再变异**，
        任何一次后续运行开头都先自愈。崩溃不再意味着「留在变异态」，
        只意味着「下一次运行时被还原并告知」。
    """
    _j = _journal_path(target) if target else _JOURNAL
    if not os.path.exists(_j):
        return True          # 没有残留 ⇒ 无需还原（⛔ 早退分支必须返回 True，
        #                      否则 `not _recover()` 把「没事」读成「自愈失败」——
        #                      改成带返回值的函数时漏了这一处，自证当场抓到）
    # 🚨🚨 2026-09-10 codex 二轮 #19（Critical）：上一版在 `finally` 里**无条件删除日志** ——
    #   于是「目标暂时不可写」或「SIGKILL 留下半截 JSON」这两条路径上，
    #   还原失败之后**唯一的恢复依据也被删了**，`run()` 随后把变异态当成新的「原文」，
    #   下一次再也没有办法恢复。⭐ docstring 说「任何一次后续运行开头都会自愈」，
    #   而它恰恰在**自愈失败**这条最重要的路径上不成立 —— 又一次「声称≠实际」。
    #   ⇒ 只有**确认还原成功**（或本来就无需还原）才删日志；失败就保留并大声说出来，
    #     ⛔ 并且**拒绝继续**（返回 False），不让调用方拿变异态当原文。
    try:
        j = json.load(io.open(_j, encoding='utf-8'))
        tgt, body = j['target'], j['orig']
        if os.path.exists(tgt) and io.open(tgt, encoding='utf-8').read() != body:
            io.open(tgt, 'w', encoding='utf-8').write(body)
            if io.open(tgt, encoding='utf-8').read() != body:
                raise IOError('写回后内容仍不一致')
            print("⚠️ 上一次运行被硬打断，%s 仍是变异态 —— **已自动还原**。" % tgt,
                  file=sys.stderr)
    except Exception as e:
        print("UNABLE: 崩溃残留**未能还原**（%s）—— ⛔ 日志已保留在 %s，"
              "不要删；先手动 git checkout 该文件再重跑。" % (e, _j),
              file=sys.stderr)
        return False
    try:
        os.remove(_j)
    except OSError:
        pass
    return True


def run(target, mutate, cmd, expect):
    if not os.path.exists(target):
        print("UNABLE: 目标文件不存在：" + target); return 2
    # 🚨🚨 2026-09-10 codex 评审 #2（Critical）：上一版**在锁外拍快照** ——
    #   `orig = read(target)` 与 `before_hash` 都在 flock 之前。时序：
    #     A 拿锁把 O 改成 M → B 在锁外读到 orig=**M** 后阻塞 →
    #     A 还原 O 释放锁 → B 拿锁、以 M 为「原文」→ 收尾 restore(**M**)
    #   ⇒ **工作区最终留在变异态**，而 B 的哈希基线也是对 M 算的，
    #     第 134 行还会确认「还原成功」。⭐ 上一轮把 `_recover()` 移进锁是对的，
    #     但**快照本身还在锁外**，保证仍然不成立 —— 又一次「只修了一半」。
    #   ⇒ 拿锁 → 自愈 → **再**拍快照。三步顺序不许换。
    lock = io.open(_lock_path(target), 'w')   # ⛔ 按目标分键（#20），不按 checkout
    fcntl.flock(lock, fcntl.LOCK_EX)          # ③ 第二个实例在这里等
    if not _recover(target):  # ⛔ 必须在拿锁**之后**：锁外自愈会伸进别人的活变异（F4）
        fcntl.flock(lock, fcntl.LOCK_UN)
        return 2        # 自愈失败 ⇒ 跑不了（⛔ 不许拿变异态当原文继续）
    orig = io.open(target, encoding='utf-8').read()
    before_hash = sha(target)
    restored = {'done': False}

    def restore(*_):
        if restored['done']: return
        io.open(target, 'w', encoding='utf-8').write(orig)
        restored['done'] = True
    for s in (signal.SIGINT, signal.SIGTERM):  # ② 被杀也还原
        signal.signal(s, lambda *a: (restore(), sys.exit(2)))
    try:
        # ⛔ **先验基线**：被测命令在**未变异**时必须是绿的。
        #    2026-09-05 实测：我的自证里有个 NameError（`g_bad` 未定义）⇒ 基线就是 1，
        #    变异后仍是 1 ⇒ 本工具判「判据承重」。**那个 1 来自崩溃，不是来自判据。**
        #    ⭐ 这正是「崩溃与有发现同码」在**验证工具自己身上**的第三次发生。
        base = _run(cmd, capture_output=True)
        want = expect if expect is not None else None
        # 🚨 2026-09-10 codex 评审 #13：不传 `--expect` 时**基线保护整条失效** ——
        #   下面那句只在 `expect is not None` 时比较。于是被测命令**恒返回 1**（例如 `false`）
        #   也照跑：变异后仍是 1，第 138 行按「非零即红」判成「判据承重」rc=0。
        #   ⭐ 那个 1 来自命令本身，不来自判据 —— 与本文件早写过的教训
        #     「那个 1 来自崩溃，不是来自判据」是**同一句话的第二次实例**。
        #   ⇒ 默认模式的期望就是「非 0」，基线必须先是 0。
        if want is None and base.returncode != 0:
            print("UNABLE: **基线就不是绿的**（退出码 %d）—— 这次测不出任何东西：\n"
                  "        默认模式判「变异后非 0 即承重」，而变异前就已经非 0。\n"
                  "        ⇒ 先让被测命令在未变异时通过，或显式传 --expect。"
                  % base.returncode)
            return 2
        if want is not None and base.returncode == want:
            print("UNABLE: **基线退出码已经等于期望值（%d）** —— 这次测不出任何东西：\n"
                  "        变异前就是这个结果，变异后还是这个结果，**空变异也会「通过」**。\n"
                  "        ⇒ 反向测的两个合法方向是「基线绿→变异后红」或\n"
                  "          「基线红（门抓到了坏输入）→变异后绿」，两者都要求**基线 ≠ 期望**。"
                  % want)
            return 2
        new = mutate(orig)
        # 🚨 2026-09-10 codex 二轮 #18：默认模式判「变异后非 0 即承重」，
        #   而**变异把程序本身弄崩**（SyntaxError/NameError）同样返回非 0 ⇒
        #   `print("ok")` 改成 `print(` 也会被报「判据承重」。
        #   ⭐ 新加的基线断言只消除了「基线已坏」那半，没消除「变异弄崩」这半 ——
        #     **同型假绿的另一半**。⇒ 变异体先过语法检查（mutation-sweep 早有这一步）。
        if new is not None and target.endswith('.py'):
            try:
                __import__('ast').parse(new)
            except SyntaxError as _e:
                print("UNABLE: **变异体语法不合法**（%s）—— 这次测不出任何东西：\n"
                      "        变异后的非 0 来自解释器，不是来自判据。"
                      % str(_e).split('(')[0].strip())
                return 2
        if new is None or new == orig:
            print("UNABLE: **变异没生效** —— 文件内容一字未变。"
                  "\n        绝不能继续：接下来那次「绿」只会被误读成「复原正常」。")
            return 2                            # ① 硬拒绝
        # ⛔ 顺序不许换：**先落日志再变异**。反过来的话，两条语句之间被杀
        #   就没有任何记录 —— 那正是这条日志要覆盖的窗口。
        io.open(_journal_path(target), 'w', encoding='utf-8').write(
            json.dumps({'target': os.path.abspath(target), 'orig': orig},
                       ensure_ascii=False))
        io.open(target, 'w', encoding='utf-8').write(new)
        r = _run(cmd)
        got = r.returncode
    finally:
        restore()
        try:
            os.remove(_journal_path(target))   # 正常收尾：日志用完即焚
        except OSError:
            pass
        if sha(target) != before_hash:
            print("UNABLE: 还原失败，工作区仍是变异态 —— 立刻 git checkout 该文件"); return 2
        fcntl.flock(lock, fcntl.LOCK_UN)

    ok = (got == expect) if expect is not None else (got != 0)
    print("变异后命令退出码 = %d（期望 %s）" % (got, expect if expect is not None else "非 0"))
    print("✅ 判据承重：删了它这道门就漏" if ok else
          "❌ **判据不承重**：改坏了它门禁照样绿。两种可能，必须分开：\n"
          "   ① 这几行确实没在守什么；\n"
          "   ② 它在守，但**还有另一条路兜住了** —— 冗余判据单点变异永远不红，\n"
          "      要么同时打掉所有路径，要么给每一路各立一个只有它能接住的用例。")
    return 0 if ok else 1

def _guarded(fn, *a, **kw):
    """把「跑不了」与「有发现」分开 —— 本仓 M8 红线。

    🚨 2026-09-10 codex 评审 #17：目标传目录 / `--replace` 缺参数 / `--expect xyz` /
      命令不存在，都会在 `io.open`、列表索引、`int()` 或 `subprocess.run()` 抛未捕获异常，
      进程自然退出码 **1** —— 而文档里 1 的语义是「**判据不承重**」，2 才是「跑不了」。
      ⭐ 一个崩溃被读成一条结论，正是 `crash-is-unable` 这条元规则要治的东西，
        而本脚本自己没守（它不在 gate_files 的量程里，元规则也照不到）。
    """
    try:
        return fn(*a, **kw)
    except SystemExit:
        raise
    except Exception as e:
        print("UNABLE: 工具自身异常（不是「判据不承重」）：%s: %s"
              % (type(e).__name__, e), file=sys.stderr)
        return 2


def self_test():
    print("M8 自证 —— 变异生效才继续 / 判据承重与否分得开 / 还原必须干净\n")
    d = tempfile.mkdtemp(prefix='rt-st-')
    tgt = os.path.join(d, 'gate.py')
    io.open(tgt, 'w', encoding='utf-8').write(
        "import sys\nBAD='坏'\nif BAD in open(sys.argv[1]).read(): sys.exit(1)\nsys.exit(0)\n")
    good = os.path.join(d, 'good.txt'); io.open(good, 'w', encoding='utf-8').write('干净')
    bad  = os.path.join(d, 'bad.txt');  io.open(bad,  'w', encoding='utf-8').write('有坏东西')
    h0 = sha(tgt)
    cases = []
    # 正例：判据承重 —— 把 BAD 改成对不上的值，门对坏输入就不红了
    cases.append(("判据承重（改坏 BAD ⇒ 坏输入不再报红）",
                  run(tgt, lambda s: s.replace("BAD='坏'", "BAD='不可能出现'"),
                      [sys.executable, tgt, bad], 0), 0))
    # 反例①：变异串对不上 ⇒ 必须报 2，不许继续
    cases.append(("变异串对不上 ⇒ 报 2 不许继续",
                  run(tgt, lambda s: s.replace("不存在的串", "x"),
                      [sys.executable, tgt, bad], 0), 2))
    # 反例②：判据不承重 —— 改一行注释,门的行为不变
    io.open(tgt, 'a', encoding='utf-8').write("# 一行不承重的注释\n"); h0 = sha(tgt)
    cases.append(("判据不承重（改注释 ⇒ 门行为不变）",
                  run(tgt, lambda s: s.replace("# 一行不承重的注释", "# 改过了"),
                      [sys.executable, tgt, bad], 0), 1))
    cases.append(("目标文件不存在 ⇒ 报 2",
                  run(os.path.join(d, 'nope.py'), lambda s: s, ['true'], 0), 2))
    # 🆕 基线 == 期望 ⇒ 这次测不出任何东西，必须报 2 拒绝
    #    （2026-09-05 实测：我的自证里一个 NameError 让基线恒为 1，
    #     变异后还是 1，本工具当时判「判据承重」——**那个 1 来自崩溃**。）
    cases.append(("基线退出码就等于期望值 ⇒ 报 2（空变异也会「通过」）",
                  run(good, lambda s: s.replace("BAD='坏'", "BAD='别的'"),
                      [sys.executable, tgt, good], 0), 2))
    ok = True
    for name, got, want in cases:
        g = got == want; ok &= g
        print("  %s %-42s 期望 %d 实得 %d" % ('✅' if g else '❌', name, want, got))
    clean = sha(tgt) == h0
    print("  %s %-42s" % ('✅' if clean else '❌', "每次跑完文件都还原干净"))
    ok &= clean

    # 🚨🚨 2026-09-09：**模拟 SIGKILL 残留** —— 手工造出「日志在、被测物是变异态」
    #   这个状态（正是硬打断留下的现场），然后跑一次，看下一次运行会不会自愈。
    #   ⭐ 为什么必须单独测这条：正常路径的 `finally` 与信号处理器**永远测得过**，
    #     而出事的是它们**跑不到**的那条路径。测正常路径证明不了崩溃安全。
    #   ⚠️ 这条用例不构造真的 SIGKILL（不可靠、会拖慢自证），而是**复现它留下的现场**——
    #     判据要的是「现场能不能被收拾」，不是「怎么造出现场」。
    _orig_body = io.open(tgt, encoding='utf-8').read()
    io.open(_journal_path(tgt), 'w', encoding='utf-8').write(
        json.dumps({'target': os.path.abspath(tgt), 'orig': _orig_body}, ensure_ascii=False))
    io.open(tgt, 'w', encoding='utf-8').write("# 被硬打断，留在变异态\n")
    _recover(tgt)
    _healed = (io.open(tgt, encoding='utf-8').read() == _orig_body
               and not os.path.exists(_journal_path(tgt)))
    print("  %s %-42s" % ('✅' if _healed else '❌',
                          "硬打断留下的变异态，下次运行开头自愈"))
    ok &= _healed
    print("\n" + ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修工具"))
    return 0 if ok else 1

if __name__ == '__main__':
    a = sys.argv[1:]
    # ⛔ 只看 `--` **之前**的参数。首版扫整个 argv ⇒ 被测命令里出现 `--self-test`
    #    （而那恰恰是最常见的用法：反向测一道门的自证）就会**跑成本工具自己的自证**，
    #    返回 0，读起来完全像「判据承重」。2026-09-05 我自己差点据此下结论。
    head_args = a[:a.index('--')] if '--' in a else a
    if '--self-test' in head_args: sys.exit(self_test())
    if '--help' in head_args or not a: print(__doc__.strip()); sys.exit(0 if a else 2)
    if '--' not in a: print("UNABLE: 缺 `--`，命令要写在 `--` 之后"); sys.exit(2)
    # ⛔ 参数解析本身也要「跑不了报 2」：`--expect xyz`、`--replace` 缺参、
    #   目标传目录……上一版都在这里抛未捕获异常，进程自然退出码 **1**
    #   ——而 1 的语义是「判据不承重」（codex #17）。
    def _parse_and_run():
        i = a.index('--'); head, cmd = a[:i], a[i + 1:]
        expect = None
        if '--expect' in cmd:
            j = cmd.index('--expect')
            if j + 1 >= len(cmd) or not re.fullmatch(r'-?\d+', cmd[j + 1]):
                print("UNABLE: --expect 后面要跟一个整数退出码"); return 2
            expect = int(cmd[j + 1]); cmd = cmd[:j] + cmd[j + 2:]
        if not cmd:
            print("UNABLE: `--` 之后没有命令"); return 2
        if not head:
            print("UNABLE: 缺目标文件"); return 2
        target = head[0]
        if os.path.isdir(target):
            print("UNABLE: 目标是目录，不是文件：%s" % target); return 2
        if '--replace' in head:
            k = head.index('--replace')
            if k + 2 >= len(head):
                print("UNABLE: --replace 要给两个参数 <旧> <新>"); return 2
            old_s, new_s = head[k + 1], head[k + 2]
            mut = lambda s: s.replace(old_s, new_s, 1)
        elif '--delete-re' in head:
            k = head.index('--delete-re')
            if k + 1 >= len(head):
                print("UNABLE: --delete-re 要给一个正则"); return 2
            try:
                rx = re.compile(head[k + 1], re.M)
            except re.error as e:
                print("UNABLE: --delete-re 的正则编不了：%s" % e); return 2
            mut = lambda s: rx.sub('', s, count=1)
        else:
            print("UNABLE: 要给 --replace <旧> <新> 或 --delete-re <正则>"); return 2
        return run(target, mut, cmd, expect)

    sys.exit(_guarded(_parse_and_run))
