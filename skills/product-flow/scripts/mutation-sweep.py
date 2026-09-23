#!/usr/bin/env python3
"""跨门禁系统性变异 —— 逐条把「判据」强行置真，看自证会不会红。

它回答的问题，和 `--self-test` 回答的**不是同一个**：

  `--self-test`   变异的是**被测物**（夹具）⇒ 证明「喂坏输入时门会红」。
  本工具         变异的是**门禁自己**（某一条判据）⇒ 证明「这条判据**承重**」。

一道门可以有 20 个反例、次次全绿，而其中某条判据**从没有任何反例守着** ——
把它整条删掉，自证照样全绿。这两件事之间没有推导关系（见 design-quality-gates.md）。

判据置真的做法是统一的：把 `def add(rid, desc, ok, ev)` 改成
对指定 rid 恒真，其余不变。**只改一条**，逐条来。

⚠️ 量程（诚实边界）：只覆盖两种记录形状（`def add(rid, desc, ok, ev)` 与 `X.append(...)`）。
   其余门禁各有各的记录方式，**本工具够不着**，不许把「没扫到」读成「没问题」。

🚨 **方法适用边界（用错了会得到一个全绿的假安心）**：
   「置真法」只适用于**有反例夹具**的门禁 —— 置真后，本该红的反例会转绿，于是抓得到。
   **直接对真实产品代码断言**的门禁（没有夹具）不适用：干净代码下判据本来就为真，
   置真不改变任何东西，于是**每一条都会被报成「无人守」**。
   那不是发现，是方法错配 —— 这类门禁的等价自证是**对产品代码做变异**。
   ⇒ 本工具会在「一道门里所有判据都报无人守」时**主动提示这个可能**，不让它读成结论。
   （2026-09-05 由并行会话 `fm-agent` 实测反馈：42 条判据置真后全绿。）

退出码: 0=每条判据都有反例守着 1=**发现无人守的判据** 2=跑不了
"""
import sys, os, re, io, ast, glob, subprocess, hashlib, signal, fcntl

ADD_DEF = re.compile(r'^(\s*)def add\(rid, desc, ok, ev\):(.*)$', re.M)
# 策略 B：不用 add(rid,…) 的门，改逐个把「记录一处失败」的调用变成空操作。
# ⚠️ 与 JS 那条同病：**不许要求行首**。`if x: bad.append(...)` 这种同行写法
#    一条都匹配不到，而整个文件会因「找不到失败点」被静默跳过。
#    ⭐ 我先修了 JS 那条、漏了这条 —— 是 2026-09-05 新加的策略 B 自证当场抓出来的。
#    **只修一半的修复，和没修一样安静。**
FAIL_SITE = re.compile(
    r'([ \t]*)((?:bad|fails|failures|problems|issues|errs|miss|missing|thin|hits|dup|bads)'
    r'\.append\()')
# 策略 C：.mjs 门禁同理，只是记录方式是 `bad.push(...)`，空操作写成 `void 0`。
# ⚠️ 不许要求行首：`if (!r.scene) bad.push(...)` 这种**写在同一行**的，
#    行首正则一条都匹配不到 —— 2026-09-05 实测 mock-seam 3 处只扫到 1 处，
#    而输出读起来完全正常（「扫了 1 条判据」不会让人觉得少了什么）。
FAIL_SITE_JS = re.compile(r'([ \t]*)((?:bad|fails|issues|problems|errs|miss)\.push\()')
LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.reverse-test.lock')

def rule_ids(src):
    """add(...) 调用点的第一个实参。返回 (字面量, 是否动态拼接)。

    ⚠️ 2026-09-05 首版**制造了一条不存在的发现**：
    `add("nonempty-" + key, ...)` 的 rid 是运行时拼出来的，
    而变异写的是 `rid == 'nonempty-'` —— **永不成立 ⇒ 变异是空操作 ⇒ 自证当然绿**，
    于是被报成「这条判据没人守」。**假发现比漏报更糟：它让人去修一个没有问题的地方。**
    ⇒ 字面量后面跟着 `+` 的，一律改用 `startswith`。
    """
    out = []
    for m in re.finditer(r'\badd\(\s*[\'"]([^\'"]+)[\'"](\s*\+)?', src):
        out.append((m.group(1), bool(m.group(2))))
    return out

_TRIPLE = ('"' * 3, "'" * 3)


def _mask_noncode(src, is_js):
    """把**注释**里的字符换成空格（长度与换行全保留，偏移量不变）。

    🚨 2026-09-09 第五轮独立复核（A-3）：定位「失败点」时直接在原文上 finditer，
      于是**注释里的 `bad.append(` 被当成一条真判据**，门报出「这条判据没人守」——
      而那条判据**根本不存在**。
      ⭐ 「假发现比漏报更糟」：漏报是少看见一个问题，假发现是**造出一个问题**，
        读的人会去改一段注释，然后发现改不动。
    ⚠️ 不是构造出来的形状：HEAD 版 `scenario-matrix-gate.mjs:191` 有一条纯注释里
      带着 `bad.push(`，实测被报成一条无人守的判据。
    ⚠️ 「变异打错靶子」的硬拒绝**拦不住它** —— 那条断言问的是「删掉的一段里有没有
      `.append(`」，注释里当然有。字符串字面量那种被语法检查挡住了，注释这种挡不住。
    ⚠️⚠️ 2026-09-10 codex 二轮 #16 订正：这里**曾经写着**「只掩码注释，不掩码字符串」，
      而 2026-09-10 早些时候的修复已经把字符串也掩了 —— **注释与实现逐字相反**，
      整整一批提交里它都在说谎。⭐ 在一个母题是「声称≠实际」的仓里，
      **我修完代码忘了改紧挨着它的那句话**。
    ⇒ 现在的实际行为：注释**与**字符串内容都掩码（引号保留），
      长度与换行全保留所以偏移不变。
    ⛔ 已知量程外（codex #16 指出，未修）：JS **模板插值** `${...}` 里是会执行的代码，
      本函数把它当字符串内容一并掩掉 ⇒ 写在插值里的 `bad.push(...)` **会被漏掉**。
      要正确处理得跟踪模板串的嵌套深度，那是另一个决定；此处如实登记，不假装覆盖。
    """
    out = list(src)
    i, n = 0, len(src)
    in_s = None                        # 当前所在字符串的引号
    while i < n:
        c = src[i]
        if in_s:
            # 🚨 2026-09-10 codex 评审 #12：上一版**只掩注释、不掩字符串**，理由写的是
            #   「字符串里的 `bad.append(` 由语法检查兜住」——**那个理由是错的**：
            #     bad = []
            #     """bad.append("phantom")
            #     """
            #     if X: bad.append("real")
            #   这里的三引号是一条**表达式语句**，删掉它之后代码**仍然能 ast.parse**，
            #   于是报出一条根本不存在的「无人守判据」。⭐ 假发现比漏报更糟。
            #   ⚠️ 当初不掩字符串的另一个理由是「会改变偏移语义」——也不成立：
            #     本函数逐字符替换成空格，**长度与换行全保留**，偏移量根本不动。
            #   ⇒ 字符串内容一并掩码（引号本身保留，便于状态机继续走）。
            if c == '\\':
                out[i] = out[min(i + 1, n - 1)] = ' '
                i += 2
                continue
            if src.startswith(in_s, i):
                i += len(in_s)
                in_s = None
                continue
            if c != '\n':
                out[i] = ' '
            i += 1
            continue
        hit3 = next((t for t in _TRIPLE if src.startswith(t, i)), None)
        if hit3:
            in_s = hit3
            i += 3
            continue
        if c in ('"', "'", '`'):
            in_s = c
            i += 1
            continue
        # ⚠️ 2026-09-10 第六轮（F5）：JS **正则字面量**里的引号会开启一个假字符串态，
        #   其后的注释不再被掩码 ⇒ 注释又被报成判据（正是 063bd77 要消除的东西）。
        #   诚实边界：当前仓库里**没有活实例**（49 个脚本无一在 EOF 留下未闭合串态），
        #   这是潜在回归不是现行假发现；但堵住比等它复发便宜。
        #   ⭐ 正则 vs 除法本质上要看语法上下文，这里用**前一个非空白字符**做启发式：
        #     `( , = : [ ! & | ? { } ; return` 之后的 `/` 才当正则（覆盖绝大多数写法）。
        if is_js and c == '/' and not src.startswith('//', i) \
                and not src.startswith('/*', i):
            _prev = src[:i].rstrip()
            if not _prev or _prev[-1] in '(,=:[!&|?{};+~^' or _prev.endswith('return'):
                j = i + 1
                while j < n:
                    if src[j] == '\\':
                        j += 2
                        continue
                    if src[j] == '\n':
                        break                 # 正则不跨行 ⇒ 判断错了，当普通字符
                    if src[j] == '[':
                        while j < n and src[j] != ']':
                            j += 2 if src[j] == '\\' else 1
                    if src[j] == '/':
                        i = j + 1
                        break
                    j += 1
                else:
                    i = n
                continue
        if is_js and src.startswith('/*', i):
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != '\n':
                    out[k] = ' '
            i = j
            continue
        if (c == '#' and not is_js) or (is_js and src.startswith('//', i)):
            j = src.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ' '
            i = j
            continue
        i += 1
    return ''.join(out)


def _cut_text(src, mutated, width=110):
    """返回变异删掉的那段原文（单行化、截断）。用于识别「变异打错了靶子」。"""
    i = 0
    while i < min(len(src), len(mutated)) and src[i] == mutated[i]:
        i += 1
    j = 0
    while (j < min(len(src), len(mutated)) - i
           and src[len(src) - 1 - j] == mutated[len(mutated) - 1 - j]):
        j += 1
    cut = src[i:len(src) - j].strip()
    cut = re.sub(r'\s+', ' ', cut)
    return (cut[:width] + '…') if len(cut) > width else (cut or '（空 —— 变异只做了插入，没删任何东西）')


def sweep(paths):
    """🚨🚨 2026-09-09：**改副本模式，真实工作区零写入。**

    此前是**原地改真实文件**（`open(p,'w').write(mutated)`），靠 `finally`
    与 SIGINT/SIGTERM 处理器还原。⛔ 那个还原路径**盖不住 SIGKILL、断电、OOM**——
    本仓早有一条教训叫「finally 非信号安全」，而这里正是它的活实例。
    ⭐ 触发不是理论风险：同一天，并行会话的 reverse-test 被硬打断，
      **变异串留在了邻座 skill 的工作区里**，把对方的闭环契约门禁卡死，
      两个窗口各花一轮才定位到「那行文本是变异表第 12 条的确切新串」。
    ⇒ 整份 skill 复制到临时目录，变异只碰副本；**被测文件一次都不写**。
      这样连「还原」这个动作都不需要存在 —— 不存在的路径不会失效。
    ⚠️ 诚实边界（2026-09-10 codex #4 订正）：此前这里写的是「真实文件**一次都不写**」，
      **那句话是假的** —— 本函数仍以写模式打开仓库里的 `.reverse-test.lock`（跨进程串行
      必须共享一个锁文件）。⇒ 准确说法是「**被测文件**零写入；锁文件仍写」，
      因此「只读 checkout 可运行」也**不成立**（只读仓库上锁都建不了）。
      现有只读夹具只把被测 gate chmod 444，没把仓库设成只读，所以照不出这一条。
    """
    import shutil as _sh, tempfile as _tf
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 🚨 2026-09-10 codex 二轮 #14：上一版**先复制整棵树、后拿锁** ⇒
    #   若此刻 `reverse-test` 正持锁把某个被 import 的 helper 改坏，
    #   副本里就固化了那个坏 helper；等真实文件恢复后基线在真实树上是绿的，
    #   而变异测试跑在**带旧变异的副本**上，所有判据都可能因无关错误被判「有反例守着」。
    #   ⭐ 这正是 reverse-test 刚修掉的「锁外快照」在另一个工具里的**同型复发** ——
    #     我修了一个工具，没回头查同一形状的另一处。
    #   ⇒ 拿锁 → 再复制。
    lock = io.open(LOCK, 'w'); fcntl.flock(lock, fcntl.LOCK_EX)
    _work = _tf.mkdtemp(prefix='ms-copy-')
    _copy = os.path.join(_work, os.path.basename(_root))
    # 🚨🚨 2026-09-10 codex 评审 #4（Critical）：`symlinks=True` **保留软链** ⇒
    #   若 `scripts/x-gate.py` 是指向真实源码的**绝对**软链，副本里那条链还指着真文件，
    #   后面的 `chmod` 与 `open(_mp,'w')` 全都**跟随链接写到真实目标上** ——
    #   「副本模式」这个隔离边界当场不成立，SIGKILL 时原问题完整复发。
    #   ⭐ 本仓早有一条同名教训：**软链拆沙箱**。而我在写副本模式时照抄了 `symlinks=True`。
    #   ⇒ 改 `symlinks=False`：复制**内容**而不是链接，副本里没有任何东西指向仓库。
    # 🚨 2026-09-10 codex 二轮 #15：`symlinks=False` 消除了「写穿文件软链」，
    #   却会**跟随目录软链递归复制任意外部树** —— `loop -> ..` 就能把它拖进
    #   无界遍历/爆盘。⭐ 我把「写到真实目标」的风险换成了一个 DoS 触发器。
    #   ⇒ 文件软链解引用（安全），**目录软链一律跳过**（并说出来，⛔ 不静默）。
    _skipped_links = []

    def _ig(_d, _names):
        _out = {'.git', 'node_modules', '__pycache__'}
        for _n in _names:
            _fp = os.path.join(_d, _n)
            if os.path.islink(_fp) and os.path.isdir(_fp):
                _out.add(_n)
                _skipped_links.append(os.path.relpath(_fp, _root))
        return _out

    _sh.copytree(_root, _copy, symlinks=False, ignore=_ig)
    if _skipped_links:
        print("   ⏭️  跳过目录软链（跟随它会无界遍历）：%s"
              % "、".join(_skipped_links[:4]))

    _ext = {}

    def _make_writable(_d):
        """副本必须可写 —— `copytree` 会把源文件的只读位一并复制过来。

        ⚠️ 这条是只读夹具那发自证**当场抓出来的**：报错路径指向副本
          （`ms-copy-*/ext-0/…`）而不是真实文件，说明真实文件确实没被写，
          但副本也写不进去 ⇒ 整个扫描崩。⭐ 顺带说明源码树只读时（只读检出、
          CI 缓存目录）本工具本来就跑不了，而没人会想到是权限位。
        """
        for _r, _, _fs in os.walk(_d):
            for _f in _fs:
                _fp = os.path.join(_r, _f)
                try:
                    os.chmod(_fp, os.stat(_fp).st_mode | 0o200)
                except OSError:
                    pass

    _make_writable(_copy)

    def _mirror(_p):
        """真实路径 → 副本里的对应路径。

        ⚠️ 被扫文件**不一定在 skill 根之内**：自证会在临时目录里造假门禁，
          直接 `relpath` 会算出一串 `../../..` 逃出副本（第一版就这么崩的）。
        ⇒ 根外的文件**镜像它所在的整个目录**（假门禁可能依赖同目录的夹具）。
        """
        _ap = os.path.abspath(_p)
        if os.path.commonpath([_ap, _root]) == _root:
            return os.path.join(_copy, os.path.relpath(_ap, _root))
        _d = os.path.dirname(_ap)
        if _d not in _ext:
            _dst = os.path.join(_work, 'ext-%d' % len(_ext))
            _sh.copytree(_d, _dst, symlinks=False)
            _make_writable(_dst)
            _ext[_d] = _dst
        return os.path.join(_ext[_d], os.path.basename(_ap))

    naked, checked, skipped, per_gate = [], 0, [], {}
    try:
        for p in paths:
            src = io.open(p, encoding='utf-8').read()
            m = ADD_DEF.search(src)
            if m:
                ids = sorted(set(rule_ids(src)))      # [(字面量, 动态?)]
                strat = 'A'
                if not ids:
                    skipped.append((os.path.basename(p), 'add() 调用点取不到字面量 rid')); continue
            else:
                # 策略 B / C：逐个把「记录一处失败」的调用改成空操作
                rx = FAIL_SITE_JS if p.endswith('.mjs') else FAIL_SITE
                _scan = _mask_noncode(src, p.endswith('.mjs'))   # 注释不算判据
                sites = [(mm.start(), src[:mm.start()].count('\n') + 1)
                         for mm in rx.finditer(_scan)]
                if not sites:
                    skipped.append((os.path.basename(p),
                                    '既不是 add(rid,…) 形状，也找不到 X.append/push 式的失败点')); continue
                ids = [('L%d' % ln, off) for off, ln in sites]
                strat = 'C' if p.endswith('.mjs') else 'B'
            h0 = hashlib.sha256(src.encode()).hexdigest()
            base = subprocess.run((['node'] if p.endswith('.mjs') else [sys.executable])
                                  + [p, '--self-test'], capture_output=True, text=True)
            if base.returncode != 0:
                skipped.append((os.path.basename(p), '自证本来就不绿，变异结果无意义')); continue
            if m: print("── %s（%d 条判据）" % (os.path.basename(p), len(ids)))
            print("── %s（策略 %s）" % (os.path.basename(p), strat)) if strat == 'B' else None
            for rid, dyn in ids:
                if strat == 'A':
                    cond = ("rid.startswith(%r)" if dyn else "rid == %r") % rid
                    mutated = ADD_DEF.sub(
                        lambda mm: "%sdef add(rid, desc, ok, ev):%s" % (
                            mm.group(1),
                            mm.group(2).replace(' ok', " (True if %s else ok)" % cond, 1)),
                        src, count=1)
                else:
                    off = dyn                      # 策略 B/C 里第二个元素是字节偏移
                    mm = (FAIL_SITE_JS if p.endswith('.mjs') else FAIL_SITE).match(src, off)
                    if not mm: continue
                    # 把这一处失败记录换成同缩进的 pass（不动其余任何一处）
                    # 🚨 A-4：文件**末尾没有换行**且最后一行就是失败点时，
                    #   `index` 抛 ValueError ⇒ traceback 退 1（＝「有发现」的语义）。
                    #   ⇒ 找不到换行就取到文件末尾。
                    _nl = src.find('\n', off)
                    end = len(src) if _nl < 0 else _nl
                    depth, i = 0, off
                    while i < len(src):            # 跨多行调用要吃到配平的右括号
                        if src[i] == '(': depth += 1
                        elif src[i] == ')':
                            depth -= 1
                            if depth == 0: end = src.index('\n', i) if '\n' in src[i:] else len(src); break
                        i += 1
                    noop = 'void 0;' if p.endswith('.mjs') else 'pass'
                    mutated = src[:off] + mm.group(1) + noop + src[end:]
                if mutated == src:
                    print("   ⚠️ %-28s 变异没生效，跳过（不计入结论）" % rid); continue
                # ⛔ 变异体必须仍是**合法程序**。语法坏掉时自证会非零退出，
                #    而那会被读成「有反例守着」—— 一个假阴性，比漏报更难发现。
                # ⛔ 硬拒绝：**被删掉的那一段必须真的是一处「记录失败」的调用**。
                #    「判据没红」的第三种解释是**变异打错了靶子**，而它每一步都"成功"了：
                #    变异执行了、文件改了、语法合法、门禁跑完了。
                #    实测两次都出在正则上（`\s` 含换行 ⇒ 起点漂到上一行）——
                #    不断言就会把「我删错了地方」读成「这条判据没人守」。
                #    （硬拒绝这一手由并行会话 fm-agent 提出，与下面的"打印删了什么"叠加：
                #     它保住「不会有人基于错误前提继续」，打印保住「诊断信息不丢」。）
                #    ⚠️ 策略 A 与 B/C 要断言的**对象不同**：A 看插入了什么，B/C 看删掉了什么。
                #       ⭐ 订正一处我自己说错的事实：我原以为 A 是「纯插入、不删任何东西」，
                #       而加了打印之后才看见它输出 `删掉的是 → ok` —— 它把 ` ok` 替换掉了，
                #       是**删+插**。首版断言之所以会误伤 A，不是因为差异段为空，
                #       而是因为删掉的那段是 `ok` 而不是 `def add(`。
                #       **打印出来才发现我对自己工具的行为描述是错的。**
                if strat == 'A':
                    _ins = _cut_text(mutated, src, width=4000)     # 方向反过来 = 插入的内容
                    _ok, _want, _shown = ('True if' in _ins and rid in _ins), 'True if …%s' % rid, _ins
                else:
                    _cut = _cut_text(src, mutated, width=4000)
                    _want = '.push(' if p.endswith('.mjs') else '.append('
                    _ok, _shown = (_want in _cut), _cut
                if not _ok:
                    print("   ⚠️ %-28s **变异打错了靶子**（%s里没有 `%s`），跳过（不计入结论）"
                          "\n        实际动的是 → %s"
                          % (rid, '插入的内容' if strat == 'A' else '删掉的一段',
                             _want, _shown[:110])); continue

                if p.endswith('.mjs'):
                    import tempfile as _tf
                    _fd = os.path.join(_tf.mkdtemp(prefix='ms-syn-'), 'm.mjs')
                    io.open(_fd, 'w', encoding='utf-8').write(mutated)
                    if subprocess.run(['node', '--check', _fd],
                                      capture_output=True).returncode != 0:
                        print("   ⚠️ %-28s 变异体语法不合法，跳过（不计入结论）" % rid); continue
                else:
                    try:
                        ast.parse(mutated)
                    except SyntaxError as e:
                        print("   ⚠️ %-28s 变异体语法不合法（%s），跳过（不计入结论）"
                              % (rid, str(e).split('(')[0].strip())); continue
                # ⭐ 只写副本；真实文件从头到尾没被打开过写模式。
                _mp = _mirror(p)
                io.open(_mp, 'w', encoding='utf-8').write(mutated)
                try:
                    r = subprocess.run((['node'] if p.endswith('.mjs') else [sys.executable])
                                       + [_mp, '--self-test'], capture_output=True, text=True)
                finally:
                    io.open(_mp, 'w', encoding='utf-8').write(src)
                # ⛔ 真实文件必须原样：这条断言现在是**不变量**而不是「还原成功了吗」
                assert hashlib.sha256(
                    io.open(p, encoding='utf-8').read().encode()).hexdigest() == h0, \
                    '真实文件被改动了 —— 副本模式失效'
                checked += 1
                # 🚨 2026-09-09 第五轮独立复核：`per_gate` 用 **basename** 做键 ⇒
                #   同名不同目录互相顶包（1 个健康文件 + 3 个基线红文件，
                #   12 条判据一条没测却 exit 0，还打印「每条判据都有反例守着」）。
                #   ⭐ 上一批的修复注释写「按文件判」，实现成了「按**文件名**判」。
                _key = os.path.relpath(os.path.abspath(p), _root)
                per_gate[_key] = per_gate.get(_key, 0) + 1
                if r.returncode == 0:
                    # ⭐ 报「无人守」时必须同时给出**被删掉的原文**。
                    #    「判据没红」有三种解释，而第三种（**变异打错了靶子**）
                    #    每一步都"成功"了：变异执行了、文件变了、语法合法、门禁跑完了。
                    #    唯一能把它和前两种区分开的信息，就是「你到底删了什么」——
                    #    而工具通常不打印它。（形状由并行会话 fm-agent 归纳。）
                    cut = _cut_text(src, mutated)
                    # 🚨 2026-09-10 codex 二轮 #17：写端上一轮改成了**相对路径**键，
                    #   而 `naked` 仍是 basename，于是汇总端又拿 basename 去合并 ——
                    #   **等于在汇总端撤销了路径身份**，同名不同目录的冲突原样回来。
                    #   ⭐ 「修一半」这次发生在同一个修复的两端之间。⇒ 两端统一用相对路径。
                    naked.append((_key, rid, cut))
                    print("   ❌ %-28s 置真后自证**照样绿** ⇒ 没有反例守着它" % rid)
                else:
                    print("   ✅ %-28s 置真 ⇒ 自证红（有反例守着）" % rid)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        _sh.rmtree(_work, ignore_errors=True)
    print()
    # 🚨 一道门里**所有**判据都报「无人守」，先怀疑方法错配（见文件头的适用边界），
    #    而不是先怀疑那道门。全绿的假安心正是这类工具最容易制造的东西。
    from collections import Counter
    # 🚨 2026-09-10 codex 评审 #16：`per_gate` 的键在上一轮改成了**相对路径**
    #   （`scripts/foo-gate.py`），而这里的 `naked` 与 `per_file` 仍是 **basename** ⇒
    #   `per_gate.get(f)` 恒为 0，`total >= 2` **永远不成立**，
    #   「整门全部无人守 ⇒ 先怀疑方法错配」这条提示**基本不会触发**。
    #   ⭐ 上一轮修掉了 basename 冲突，**只修了写入端，读取端留在旧键空间** ——
    #     「修一半的修复，和没修一样安静」（本工具自己的注释里就写着这句）。
    #   ⇒ 读取端按同一口径归一：拿 basename 去匹配相对路径的尾段。
    per_file = Counter(x[0] for x in naked)
    for f, n in per_file.items():
        total = per_gate.get(f, 0)
        if total >= 2 and n == total:      # 1/1 触发太吵，够不成信号
            print("   🚨 %s：**全部 %d 条判据都报「无人守」** —— 先怀疑方法错配"
                  "（这道门可能没有反例夹具、直接断言生产代码，那就该用变异法而不是置真法），"
                  "不要先当成 %d 个缺陷。" % (f, total, total))
    for f, why in skipped: print("   ⏭️  %-28s %s（量程外，不是「没问题」）" % (f, why))
    print("\n扫了 %d 条判据 · 无人守的 %d 条" % (checked, len(naked)))
    if naked:
        print("⚠️ 这些判据可以整条删掉而自证不红（**先核对删掉的是不是你以为的那一段**）：")
        for f, r, cut in naked:
            print("     %s :: %s" % (f, r))
            print("        删掉的是 → %s" % cut)
    # 🚨 2026-09-09 三轮独立复核揪出：`checked == 0` 时（所有门禁基线都红 ⇒ 全部 skipped）
    #   `naked` 为空，于是 `return 0` —— 而 0 的语义是「每条判据都有反例守着」。
    #   ⭐ **退出码把「一条都没测」折叠成了「全都有人守」** —— 本仓
    #   `feedback_silent_truncation_counts` 的母题：截断本身可能合理，不说才是错。
    #   ⇒ 一条都没扫到时返回 2（UNABLE：应该测而没能测），⛔ 不是通过也不是失败。
    # 🚨🚨 2026-09-09 第四轮独立复核揪出：`checked` 是**全局计数器** ——
    #   单跑一个「4 条判据全部变异没生效」的门禁能正确返回 2，
    #   但**加一个健康文件同跑就变成 exit 0**（「扫了 2 条 · 无人守 0 条」），
    #   那 4 条真判据一条没测到，而汇总行不告诉读者。
    #   ⭐ 默认调用就是 glob 全部 `*-gate.*`，所以这是**常规路径不是边角**。
    #   ⇒ 按**文件**判：任何一个文件一条判据都没扫到，整体就是 UNABLE。
    _zero = [os.path.relpath(os.path.abspath(p), _root) for p in paths
             if per_gate.get(os.path.relpath(os.path.abspath(p), _root), 0) == 0]
    if _zero:
        print("\n⚠️ UNABLE：这些文件**一条判据都没扫到**（不是「全都有人守」，是没测）：\n"
              "   %s\n"
              "   常见原因：门禁基线本来就红（先修绿再扫）、add() 取不到字面量 rid、"
              "或变异没生效。\n"
              "   ⛔ 其余文件扫过多少条，都不能替它们背书。" % "、".join(_zero[:8]))
    # 🚨 2026-09-09 第五轮独立复核：此前 **exit 2 压过 exit 1** ——
    #   有真的「无人守」判据时，只要另一个文件是 UNABLE，结论就变成 2，
    #   **真发现在机器结论里消失了**（消费方按 2 读成「没测成」，不会去看那条发现）。
    #   ⭐ 两件事都是真的，但「确定存在的缺陷」比「有一块没量到」更该被行动。
    #   ⇒ 有发现就退 1（UNABLE 清单照样打印，不省略）；只有 UNABLE 才退 2。
    if naked:
        return 1
    return 2 if _zero else 0

def self_test():
    """自证：造一个「有反例守着」的判据和一个「没人守」的判据，必须分得开。"""
    import tempfile
    d = tempfile.mkdtemp(prefix='ms-st-')
    tpl = '''import sys
def main(strict):
    rows = []
    def add(rid, desc, ok, ev): rows.append({"id": rid, "ok": ok})
    add("R-guarded", "d", ("坏" not in strict), "")
    add("R-naked", "d", ("绝不出现" not in strict), "")
    # ⚠️ 判据必须与 R-guarded **不同**：首版两者都用「坏」，任一被置真时另一个仍为假、
    #    自证照样红 ⇒ **三条全被误报成「无人守」**。冗余遮蔽在夹具自己身上重演了一次。
    #    第二版改成「动态坏」仍然错 —— 它**包含**「坏」，R-guarded 照样被触发。
    #    ⇒ 每条判据必须有一个**只有它能触发**的输入，标记之间不能有子串关系。
    for k in ("甲", "乙"):
        add("R-dyn-" + k, "d", ("犬" not in strict), "")
    return 0 if all(r["ok"] for r in rows) else 1
def self_test():
    cases = [("正例", main("干净"), 0), ("反例：含坏", main("有坏东西"), 1),
             ("反例：只触发动态 rid", main("有犬"), 1)]
    ok = all(g == w for _, g, w in cases)
    for n, g, w in cases: print("  %s %s 期望 %d 实得 %d" % ("OK" if g==w else "NG", n, w, g))
    return 0 if ok else 1
if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main(open(sys.argv[1]).read()))
'''
    p = os.path.join(d, 'fake-gate.py'); io.open(p, 'w', encoding='utf-8').write(tpl)

    # ⭐ 策略 B（**删除**型）必须**单独**有一个夹具 ——
    #    上面那个是 add(rid,…) 形状，走策略 A（**插入**恒真条件，不删任何东西）。
    #    「变异打错了靶子」的硬拒绝对两者要断言的对象**是相反的**，
    #    而首版一律断言「删掉的一段」，把所有策略 A 判成打错靶子、当场废掉一半用法。
    #    ⛔ 只有 A 的自证 ⇒ 这个修复本身没有守卫，下次有人"简化"回去不会有任何东西报警。
    tplB = '''import sys
def main(strict):
    bad = []
    if "坏" in strict: bad.append("有坏东西")
    if "绝不出现" in strict: bad.append("这条没人守")
    return 1 if bad else 0
def self_test():
    cases = [("正例", main("干净"), 0), ("反例：含坏", main("有坏东西"), 1)]
    for n, g, w in cases: print("  %s %s 期望 %d 实得 %d" % ("OK" if g==w else "NG", n, w, g))
    return 0 if all(g == w for _, g, w in cases) else 1
if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main(open(sys.argv[1]).read()))
'''
    pB = os.path.join(d, 'fakeb-gate.py'); io.open(pB, 'w', encoding='utf-8').write(tplB)

    # 🚨 2026-09-09 第五轮独立复核（A-3）：**注释里的 `bad.append(` 被当成一条真判据**，
    #   门报「这条判据没人守」—— 而那条判据根本不存在。
    #   ⭐ 「假发现比漏报更糟」：漏报是少看见一个问题，假发现是**造出一个问题**，
    #     读的人会去改一段注释，然后发现改不动。
    #   ⚠️ 不是构造出来的形状：HEAD 版 `scenario-matrix-gate.mjs` 上实测
    #     旧版报「4 条判据 · 无人守 2 条」（含纯注释的那条），新版「3 条 · 1 条」——
    #     **假发现消失，真发现保留**。
    _phantom = os.path.join(d, 'phantom-gate.py')
    io.open(_phantom, 'w', encoding='utf-8').write(
        "import sys\n"
        "def check(md):\n"
        "    bad = []\n"
        "    # 历史写法曾经是 bad.append(\"旧的\")，后来改成下面这行\n"
        "    if 'X' not in md: bad.append(\"缺 X\")\n"
        "    return bad\n"
        "if '--self-test' in sys.argv:\n"
        "    sys.exit(0 if check('') else 1)\n"
        "sys.exit(1 if check(open(sys.argv[1]).read()) else 0)\n")
    import io as _io2, contextlib as _ctx2      # 本块比下面的 import 早，就地取用
    _pb = _io2.StringIO()
    with _ctx2.redirect_stdout(_pb):
        sweep([_phantom])
    _pout = _pb.getvalue()
    _phantom_ok = ('扫了 1 条判据' in _pout) and ('无人守的 0 条' in _pout)

    print("M8 自证 —— 「有反例守着」与「没人守」必须分得开\n")
    print("  %s 注释里的 `bad.append(` **不算判据**（假发现比漏报更糟）"
          % ('✅' if _phantom_ok else '❌'))
    import io as _io, contextlib
    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf): rc = sweep([p, pB])
    out_buf = buf.getvalue()
    # ⚠️ 回显的是 sweep 对夹具的报告，里面的 ❌ 是**被测场景的预期产物**，不是本自证的失败。
    #   加「│ 」归属前缀 —— selftest-all.py 曾把这两行数成「mutation-sweep 自证失败 2 条」。
    for _ln in out_buf.splitlines(): print('  │ ' + _ln)
    src_after = io.open(p, encoding='utf-8').read()
    tail = out_buf.split("可以整条删掉")[-1]
    only_naked = ("R-naked" in tail) and ("R-dyn-" not in tail) and ("R-guarded" not in tail)
    # 策略 B：`bad.append("这条没人守")` 无人守、`bad.append("有坏东西")` 有反例守着。
    #   两条都必须被正确分类，且**都不能被「打错了靶子」误拒**。
    b_ok = ('fakeb-gate.py' in tail) and ('打错了靶子' not in out_buf)
    print("  %s 策略 B（删除型）也被正确分类，且没被「打错靶子」误拒"
          % ('✅' if b_ok else '❌'))
    # 🚨🚨 2026-09-09：副本模式的**结构性**验证 —— 把夹具设成**只读**再扫一遍。
    #   原地变异模式在这里必然崩（写不进去）；副本模式照跑不误。
    #   ⭐ 为什么要这么测而不是「跑完比对文件没变」：后者只能证明**还原成功了**，
    #     证明不了**从没写过** —— 而出事的恰恰是「写了但没还原成」那条路径
    #     （SIGKILL/断电时 finally 与信号处理器都跑不到；同一天并行会话真的踩了，
    #      变异串留在邻座 skill 的工作区里，把对方门禁卡死）。
    #     只读夹具把「有没有写」变成了**不可伪造的事实**。
    _ro_ok = False
    try:
        os.chmod(p, 0o444); os.chmod(pB, 0o444)
        _buf2 = _io.StringIO()
        with contextlib.redirect_stdout(_buf2):
            _rc2 = sweep([p, pB])
        _ro_ok = (_rc2 == rc)
    except Exception as _e:
        print("  ❌ 只读夹具下崩了（说明仍在写真实文件）：%s" % _e)
    finally:
        os.chmod(p, 0o644); os.chmod(pB, 0o644)
    print("  %s 夹具设为**只读**仍能扫完且结论一致（证明真实文件从没被写过）"
          % ('✅' if _ro_ok else '❌'))
    ok = (rc == 1) and (src_after == tpl) and only_naked and b_ok and _ro_ok \
         and _phantom_ok \
         and io.open(pB, encoding='utf-8').read() == tplB
    print("\n  %s 恰好只报出 R-naked（R-guarded 与**动态 rid** 都不许被误报）"
          % ('✅' if (rc == 1 and only_naked) else '❌'))
    print("  %s 跑完文件还原干净" % ('✅' if src_after == tpl else '❌'))
    print("\n" + ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修工具"))
    return 0 if ok else 1

if __name__ == '__main__':
    a = sys.argv[1:]
    if '--self-test' in a: sys.exit(self_test())
    if '--help' in a: print(__doc__.strip()); sys.exit(0)
    here = os.path.dirname(os.path.abspath(__file__))
    # 🚨 2026-09-10 codex #14：默认名册原本只 glob `*-gate.*` ⇒ 比元门禁的口径**少 4 道**
    #   （prd_completeness_check / coverage_check / browser-audit 等具名门禁）。
    #   那 4 道**连「跳过」都不会出现在输出里**，而结论行照样写「变异全部被杀死」。
    #   ⇒ 改用 `_roster.sweepable()` 这一个正本。
    sys.path.insert(0, here)
    from _roster import sweepable          # noqa: E402  门禁名册唯一正本
    files = [x for x in a if not x.startswith('--')] or sweepable(
        os.path.dirname(here))
    # 🚨 2026-09-09 第五轮独立复核：空路径 / 不存在的文件 / 传目录 / 文件末尾无换行，
    #   四种输入都会走到未捕获异常，**traceback 退 1** —— 而 1 的语义是「有发现」。
    #   ⭐ 本仓 M8 的红线之一就是「崩溃必须报 2，不许和『有发现』共用退出码」，
    #     元规则 `crash-is-unable` 也在查这件事，而本脚本自己没守。
    _bad = [f for f in files if not (f and os.path.isfile(f))]
    if _bad:
        print("UNABLE: 这些输入不是可读文件：%s" % "、".join(str(x) or '(空串)' for x in _bad[:5]),
              file=sys.stderr)
        sys.exit(2)
    if not files: print("UNABLE: 没有可扫的门禁"); sys.exit(2)
    try:
        sys.exit(sweep(files))
    except SystemExit:
        raise
    except Exception as e:                     # ⛔ 崩了就是 2，不许伪装成「有发现」
        print("UNABLE: 变异扫描自身异常（不是「有发现」）：%s: %s"
              % (type(e).__name__, e), file=sys.stderr)
        sys.exit(2)
