#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一致性元门禁 —— 查「文档声称的」与「代码/模板实际的」之间的差。

为什么需要它（2026-08-30 多视角评审的直接产物）：
  那次评审的 12 条硬缺陷里，**7 条是同一类**：
    · SKILL 说有 `--self-test`，脚本里没有
    · SKILL 说第 8 项会拦，实测永不触发
    · 文档 5 处写「14 条规则」，实际 16 条，且清单内容对不上
    · 「三道门禁一览」实列 4 行，最新一道零出现
    · 视角数 10 / 9 / 5 三处打架，流程列表漏掉「不许跳」的那个视角
    · 安全的附件号 5 处指错（写 D，实为 C）
    · PRD 模板教的画图法与 SKILL 的返工教训完全相反
  这类差异**全部可机械比对，而人通读永远发现不了** —— 因为每一处单独看都是自洽的。

  ⚠️ 更根本的一条：这些缺陷之所以能长期存活，是因为
  **两个会话分工维护本 skill，而分工线同时切断了检查线**。
  本门禁是唯一跨分工线的检查，必须整棵树一起扫，不许只扫自己那半边。

⚠️⚠️ 2026-08-31 补 `--project`：本门禁此前**只照自己**。
  6 条规则全部指向 skill 自身（规则条数/参数存在/引用存在/门禁目录），
  **从不看它产出的东西**。实测拿 本 skill 的验证项目核对，
  当天在交付物里找到的 8 个「声称≠实际」缺陷，这套门禁一个都抓不到 ——
  **把治声称≠实际的那道门瞄准了自己，而不是交付物。**

用法:
  python3 consistency-gate.py [skill根目录]        # 默认取本脚本的上级目录
  python3 consistency-gate.py --project <项目目录>  # 查**交付物**里的声称≠实际
  python3 consistency-gate.py --self-test          # 变异测试：逐条注入缺陷，必须被抓到
  python3 consistency-gate.py --json

退出码: 0=一致 1=有不一致 2=跑不了（缺输入/结构不对，绝不折叠成 0）
"""
import io, os, re, sys, json, shutil, tempfile, subprocess, glob

def read(p):
    try: return io.open(p, encoding='utf-8').read()
    except Exception: return None

def md_files(root):
    """全部被扫的 Markdown。

    🚨 2026-09-12：`no-loss-renames.md`（零丢失门禁的改名映射表）**必须排除** ——
      那张表按设计就装着**旧字符串**（`旧 → 新`），于是 `gate-count` 之类的内容规则
      会把「旧名里的 28 道门禁」当成一句活的声称并报红。
      ⭐ 与「规则扫到自己的夹具」同族：**控制文件不是内容**。
      ⛔ 排除仅限这一个文件，不开后门给别的 md。
    """
    out = []
    for d in ('.', 'references', 'templates'):
        out += sorted(glob.glob(os.path.join(root, d, '*.md')))
    return [p for p in out if os.path.basename(p) != 'no-loss-renames.md']

RULES = []
def rule(rid, desc):
    def deco(fn):
        RULES.append({"id": rid, "desc": desc, "fn": fn}); return fn
    return deco

# --------------------------------------------------------------- R1 规则条数
def fixture_lines(src):
    """返回「变异靶 / 自证夹具」块内的行号集合 —— 那里的违例是**故意造的**。

    ⭐ 2026-09-10 抽成模块级：同一形状已经犯过三次（gate-record-fields 把变异靶判成真违例、
      no-positional-window 早年同病、新立的 gate-roster-single-source 又一次）。
      ⛔ 每条规则各写一份跳过逻辑 = 每条规则各漏一次。**共用一份，一处修全仓好。**
    """
    out, depth, inb = set(), 0, False
    for i, l in enumerate(src.split('\n'), 1):
        st = l.lstrip()
        # ⚠️ 2026-09-10 codex 二轮 #5：`startswith('def self_test')` 是**前缀匹配** ⇒
        #   一个正经生产函数 `def self_test_registry():` 会被整段当成夹具跳过，
        #   它里面的真违例**永远看不见**。⭐ 前缀匹配当判据，第 N 次出事。
        #   ⇒ 要求精确的函数定义边界（后面必须紧跟 `(`）。
        if (st.startswith('MUTATIONS = [')
                or re.match(r'def _?self_test\s*\(', st)):
            inb, depth = True, len(l) - len(st)
        elif inb and st and (len(l) - len(st)) <= depth \
                and not st.startswith((')', ']', '}')):
            inb = False
        if inb:
            out.add(i)
    return out


@rule("rule-count", "文档声称的规则条数 = 脚本 --list-rules 实际条数")
def r_count(root):
    """按**行**匹配，不限语序。

    ⚠️ 首版要求「N 条」出现在「规则/机械反模式」之前，于是当标题被改写成
    「机械可查的反模式（16 条，…）」时，规则**整条失配、静默不再检查**，
    而变异自证里它照样报 PASS。
    **反证不生效往往不是反证写错，是被守的东西已经不在量程里。**
    """
    counts = {}
    for script in ("interaction-gate.py", "ai-slop-gate.py"):
        p = os.path.join(root, 'scripts', script)
        if not os.path.exists(p): continue
        try:
            out = subprocess.run([sys.executable, p, '--list-rules'],
                                 capture_output=True, text=True).stdout
            counts[script] = len([l for l in out.strip().split('\n') if l.strip()])
        except Exception as e:
            return None, "跑不了 %s: %s" % (script, e)
    if not counts: return None, "没有可比对的门禁脚本"
    bad = []
    for f in md_files(root):
        s = read(f) or ''
        for ln_no, line in enumerate(s.split('\n'), 1):
            for script, n in counts.items():
                stem = script.replace('.py', '')
                if stem not in line and stem.replace('-gate', '') not in line:
                    continue
                # ⚠️ 「第 N 条」是**序数**（第 N 号规则），不是「总共 N 条」。
                #    2026-09-03：写「第 17 条 keyframes-on-transient」时被误报成
                #    「声称 17 条」。⭐ 与「哪一道门禁」那次同型：
                #    **量词前面的字决定它是不是一个声称**，不看会把陈述读成计数。
                # ⚠️ 先把「第 N 条」这类**序数**整体剥掉再扫。
                #    定宽后顾断言吃不掉「第 <空格> 17 条」里的空格 —— 首版就栽在这。
                #    ⭐ 与「哪一道门禁」那次同型：**量词前面的字决定它是不是一个声称**。
                scan = re.sub(r'第\s*[0-9零一二三四五六七八九十]+\s*条', '', line)
                for m in re.finditer(r'(\d+)\s*条', scan):
                    if int(m.group(1)) != n:
                        bad.append("%s:%d 提到 %s 时写「%s 条」，实际 %d 条"
                                   % (os.path.relpath(f, root), ln_no, script, m.group(1), n))
    return (not bad), bad or "条数一致（" + " · ".join("%s=%d" % (k, v) for k, v in counts.items()) + "）"

# --------------------------------------------------------------- R2 脚本参数
@rule("flag-exists", "文档里提到的脚本参数，脚本必须真的接受")
def r_flag(root):
    bad = []
    for f in md_files(root):
        s = read(f) or ''
        # ⚠️⚠️ 这条规则被修过两次，两次都是「量程」问题：
        #    ① 首版间隔模式 `[^\n`]{0,80}?` **把反引号排除在外**，而参数几乎总写成
        #       `--baseline` 这种带反引号的形态 → 「`x.py`：`--html` 换成 `--baseline`」
        #       整条匹配不上，规则静默不查，元门禁照报「参数都存在」。
        #    ② 第二版只取脚本名后的**第一个**参数 → 同一句里列了两个参数时，
        #       后面那个永远不被检查（变异自证当场抓到：`--exempt` 合法就放过了 `--no-such-flag`）。
        #    ⭐⭐ 两次都是「被守的东西已不在量程里」，而它放跑的恰好是本 SOP
        #       最核心的那类缺陷（声称≠实际）。**规则存在 ≠ 规则在守。**
        # ⚠️ 第三次量程问题：窗口原本只在下一个 **`.py`** 处截断，
        #    遇到 `browser-audit.mjs` 不截 → 它的 `--all-viewports` 被算到前一个 .py 头上。
        #    ⭐ **脚本不只有 .py**——判据的边界必须覆盖它实际会遇到的全部形态。
        for m in re.finditer(r'`?([a-z0-9_-]+\.(?:py|mjs))`?', s):
            script = m.group(1)
            p = os.path.join(root, 'scripts', script)
            if not os.path.exists(p): continue
            # 锚到句末而不是固定 120 字符（四轮复核：窗口小会让超出部分静默逃检）
            _nl = s.find('\n', m.end())
            tail = s[m.end(): _nl if _nl > 0 else len(s)]
            tail = tail.split('\n')[0]
            nxt = re.search(r'[a-z0-9_-]+\.(?:py|mjs)', tail)
            if nxt: tail = tail[:nxt.start()]      # 后面的参数归下一个脚本
            src = read(p) or ''
            for flag in set(re.findall(r'(--[a-z][a-z-]+)', tail)):
                if flag in src: continue
                bad.append("%s: 文档提到 %s %s，脚本源码里没有这个参数" %
                           (os.path.relpath(f, root), script, flag))
    return (not bad), bad or "参数都存在"

# --------------------------------------------------------------- R3 附件字母
@rule("self-flag-exists", "门禁自己打印的提示语里提到的参数，它自己必须接受")
def r_self_flag(root):
    """R2（flag-exists）管的是**文档**提到的参数，盖不到这一类：
    脚本在自己的错误提示里写「用法见 --help」，而它自己拒绝 --help，
    于是提示把人指向一个同样报错的出口。

    2026-09-05 实测三处（chain-gate / element-identity-gate / reconcile-gate）。
    ⚠️ 第一版普查用了 `timeout`，而 macOS 没有它 —— 每次调用都没执行、
    日志是空的、grep 零命中，普查**报了假绿**。所以这里：
      ① 不用任何非自带命令；
      ② 自证里带一个必然命中的对照组，量具报零发现时先怀疑量具。
    """
    import re as _re
    sd = os.path.join(root, 'scripts')
    if not os.path.isdir(sd): return None, "没有 scripts/ 目录"
    bad, checked = [], 0
    for fn in sorted(os.listdir(sd)):
        if not (fn.endswith('.py') or fn.endswith('.mjs')): continue
        # ⛔ selftest-all 是跑手不是门禁：它打印的 --fresh 是**零前置参数即全量执行**的开关，
        #   拿去探测＝点一发 25 分钟 sweep。2026-09-08 凌晨实测：consistency 每跑一次
        #   （含变异套件每个副本）都点一发 ⇒ 几十个并发 sweep 各开浏览器 ⇒ load 146 + fd 耗尽。
        #   ⭐ 本规则的模型假设「只给 flag 不给目标会快速失败」对零参可跑的工具不成立。
        if fn.startswith('_') or fn in ('consistency-gate.py', 'selftest-all.py'): continue
        src = read(os.path.join(sd, fn)) or ''
        # 只看**会被打印出来**的行里提到的长参数
        flags = set()
        for line in src.split('\n'):
            if 'print(' not in line and 'console.log' not in line: continue
            flags |= set(_re.findall(r'--[a-z][a-z0-9-]{2,}', line))
        flags -= {'--list-rules'}          # 由 selftest-claim / 各自自证覆盖
        if not flags: continue
        checked += 1
        for fl in sorted(flags):
            cmd = ([sys.executable] if fn.endswith('.py') else ['node']) + [os.path.join(sd, fn), fl]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            except Exception:
                continue
            blob = (r.stdout or '') + (r.stderr or '')
            if _re.search(r'不认识的参数 ' + _re.escape(fl) + r'\b', blob) or \
               _re.search(r'[Uu]nknown (?:argument|option) ' + _re.escape(fl) + r'\b', blob):
                bad.append("%s 的提示里写了 %s，但它自己拒绝这个参数" % (fn, fl))
    if not checked: return None, "没有任何脚本在输出里提到长参数（量程为空，按不适用处理）"
    return (not bad), ("；".join(bad) if bad else "扫了 %d 个脚本，提示语提到的出口都真实存在" % checked)


@rule("appendix-letter", "references 引用的附件字母 = 模板里该附件的实际内容")
def r_apx(root):
    """判据是**句级**的，不是邻近的。

    ⚠️ 两次收敛的教训（都在自证时撞到）：
      · 只看后向窗口 → 漏掉「产品级安全规则……必须来自 PRD 附件 D。」这类主题词在前的
      · 加上前向窗口 → 同一行里两个附件被串起来，「进附件 A」被判成「附件 A 讲权限矩阵」
    **邻近不等于相关。** 所以改成：按句切分，一句里只提到**一个**附件字母时才判；
    提到多个的句子一律弃权记 N/A —— 判不了就说判不了，不许猜。
    """
    tpl = read(os.path.join(root, 'templates', 'prd-complete.md'))
    if tpl is None: return None, "模板不存在，无法比对"
    titles = dict(re.findall(r'^#\s*附件\s*([A-M])\s*·\s*(.+)$', tpl, re.M))
    if not titles: return None, "模板里解析不出附件标题"
    SEC = next((L for L, nm in titles.items() if '安全' in nm or '合规' in nm), None)
    topic = {}
    for t in ('权限矩阵', '数据清单', '脱敏', '合规约束', '个人信息', '产品级安全规则', '安全规则'):
        if SEC: topic[t] = SEC
    for L, nm in titles.items():
        if '字段' in nm or '数据字典' in nm: topic['字段规格'] = L; topic['数据字典'] = L
        if '状态机' in nm: topic['状态机'] = L
        if '文案' in nm:   topic['文案规格'] = L
        if '验收' in nm:   topic['验收标准'] = L
    bad, skipped = [], 0
    for f in md_files(root):
        if f.endswith('prd-complete.md'): continue
        s2 = read(f) or ''
        for ln_no, line in enumerate(s2.split('\n'), 1):
            for sent in re.split(r'[。；]', line):
                letters = set(re.findall(r'附件\s*([A-M])', sent))
                if len(letters) != 1:
                    if len(letters) > 1: skipped += 1
                    continue
                letter = letters.pop()
                for t, want in topic.items():
                    if t in sent and letter != want:
                        bad.append("%s:%d 写「附件 %s」讲的是「%s」，模板里那是附件 %s（%s）"
                                   % (os.path.relpath(f, root), ln_no, letter, t, want, titles[want]))
    if skipped:
        bad = bad + ["（另有 %d 句同时提到多个附件，判不了，已弃权 —— 不计入通过也不计入失败）" % skipped] if bad else bad
    return (not [b for b in bad if not b.startswith('（')]), bad or "附件字母一致"

# --------------------------------------------------------------- R4 引用存在
@rule("ref-exists", "md 里引用的本 skill 内文件必须存在")
def r_ref(root):
    have = {os.path.basename(p) for p in
            glob.glob(os.path.join(root, '**', '*.*'), recursive=True)}
    bad = []
    for f in md_files(root):
        s = read(f) or ''
        for m in re.finditer(r'`(?:references/|scripts/|templates/)?([a-z0-9][a-z0-9_.-]*\.(?:md|py|js|mjs))`', s):
            fn = m.group(1)
            if fn in have: continue
            # 只管本 skill 内部引用：出现在 references/ scripts/ templates/ 前缀里的才算
            # ⚠️ 必须排除「别的 skill 的 references/」——实测 web-design-engineer 的
            #    advanced-patterns.md 被误判成本 skill 缺文件。
            if re.search(r'(?<![\w/-])(references|scripts|templates)/' + re.escape(fn), s):
                line = s[:m.start()].count('\n') + 1
                bad.append("%s:%d 引用 %s，本 skill 内不存在" % (os.path.relpath(f, root), line, fn))
    return (not bad), bad or "引用都存在"

# --------------------------------------------------------------- R5 门禁目录

# ⚠️⚠️ 2026-09-02：这三条元规则原本只 glob `scripts/*-gate.py`。
#    于是新增的 `dead-click-gate.mjs` **整个落在量程之外** ——
#    gate-wired / gate-catalog / gate-count 会照常报绿，
#    而它们报绿只说明**它们没看见**，不说明那道门挂上了。
#    ⭐ 这是本仓第三次栽在「元门禁量程盖不住实际写法」上（前两次是反引号、第二参数）。
# 不按 `-gate` 命名、但确实是门禁的那几个（历史命名，改名会打断一堆引用）
# 🚨 2026-09-09：`browser-audit.mjs` 同样漏在量程外 —— 它在门禁目录里出现 13 次、
#   被 SKILL 列为 S6 出场必跑，却因为文件名不含 `-gate` 而不被 `*-gate.mjs` 命中。
#   ⭐ **「命名约定被当成判据」在同一个函数上第二次发生**（上一次是那两个 `_check.py`，
#   注释就写在下面）。⇒ 具名清单是唯一可靠的补丁：门禁是不是门禁，看它在流程里
#   被当什么用，不看文件名。
# 🚨 2026-09-10 codex 二轮 #6：`NAMED_GATES` 与 `GATE_LIKE_EXEMPT` **在这里又原样定义了一遍**，
#   随后才被 `from _roster import ...` 覆盖 —— ⭐ 我上一批刚把名册收成「唯一正本」，
#   而正本旁边就躺着一份同名副本，只是恰好被 import 盖住了。
#   **「唯一正本」这句话在源码层面当时是假的**（读的人会以为这里才是定义处）。
#   ⇒ 删掉本地副本，只留 import；新增元规则量程也覆盖这种手写名单。



# 🚨 2026-09-10 codex #14：`gate_files` 的实现已移入 `_roster.py`（门禁名册唯一正本）。
#   此前三个消费方（本文件 / gate-run / mutation-sweep）各 glob 一套，实测得到
#   28 / 27 / 24 三个不同的集合 —— 而 `single-source` 这条元规则治的正是
#   「同一概念在全仓有两种口径」，⭐ **它自己就发生在门禁名册上，且没有任何东西在守**。
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from _roster import gate_files, gate_names, GATE_LIKE_EXEMPT, NAMED_GATES   # noqa: E402,F401



@rule("gate-catalog", "scripts/ 下的每个门禁都必须出现在 design-quality-gates.md 目录里")
def r_gate(root):
    cat = read(os.path.join(root, 'references', 'design-quality-gates.md'))
    if cat is None: return None, "门禁目录文件不存在"
    GATES = [os.path.basename(p) for p in gate_files(root)]
    miss = [g for g in GATES if g not in cat]
    return (not miss), ["门禁 %s 未出现在 design-quality-gates.md" % g for g in miss] or "目录完整"

# --------------------------------------------------------------- R6 门禁道数
@rule("diagram-slot-anchored", "八类图规范声称的落位，在 PRD 模板里必须真有那一节")
def r_diagram_slot(root):
    """🚨 2026-09-12：`diagram-standards.md` 的六个小节标题各自声称一个落位
    （`（五章）`、`（6.2）`、`（附件 N）`…），而**没有任何东西在对账**。
    模板一旦重排或改名（本轮就重排过一次九章），规范会**安静地指向不存在的章节** ——
    ⭐ 而它看起来完全正常：规范还在、模板还在、门禁全绿，只是那句指路话没人走过。

    ⚠️ 这与既有的「查证指针悬空」同族，只是指针这次指的是**章节**不是文件路径。
    ⛔ 本规则**不检查那一节里有没有真的插图** —— 那是 diagram-id-gate 在项目上做的事，
      模板本来就是空的。本规则只回答：**规范说的那个位置在模板里存不存在。**
    """
    std = os.path.join(root, 'references', 'diagram-standards.md')
    tpl = os.path.join(root, 'templates', 'prd-complete.md')
    ss, ts = read(std), read(tpl)
    if ss is None or ts is None:
        return None, "diagram-standards.md 或 prd-complete.md 不存在"
    # ⚠️ 标题本身可能含括号（`## 4 · 信息架构（内容组织）+ 站点地图（6.3）`）——
    #   非贪婪会咬住**第一对**括号，把「内容组织）+ 站点地图（6.3」当成落位。
    #   ⭐ 落位永远是**最后一对**括号 ⇒ 贪婪前缀吃掉前面的，内层禁含括号。
    slots = re.findall(r'(?m)^##\s*\d\s*·\s*(.+)（([^（）]+)）\s*$', ss)
    if not slots:
        return None, "解析不出八类图的落位声明（标题形如 `## 1 · 业务流程图（五章）`）"
    bad = []
    for name, where in slots:
        # 落位写法有三类：章名（五章）、小节号（6.2）、附件（附件 N / 附件 C.5，可带后缀说明）
        w = where.split('，')[0].strip()
        if re.fullmatch(r'[一二三四五六七八九十]+章', w):
            pat = r'(?m)^##\s*%s、' % w[0]
        elif re.fullmatch(r'\d+\.\d+', w):
            pat = r'(?m)^#{2,4}\s*%s\s' % re.escape(w)
        else:
            pat = r'(?m)^#{1,4}.*%s' % re.escape(w.replace('附件 ', '').strip())
        if not re.search(pat, ts):
            bad.append('「%s」声称落在 %s，但模板里找不到该节（锚 %s）' % (name, where, pat))
    return (not bad), bad or "八类图的落位在模板里都真实存在"


@rule("gate-count", "「N 道门禁」的 N = scripts/ 下门禁实际数量")
def r_gate_n(root):
    import re as _re
    n = len(gate_files(root))
    # ⚠️ 中文数字必须支持「十X」。首版字符类不含「十」，于是「十一道门禁」只截到末尾的
    #    「一」，把 11 判成 1 —— **规则自己读错了它要守的那个数**。
    D = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
         '六': 6, '七': 7, '八': 8, '九': 9}
    def cn2int(v):
        if v.isdigit(): return int(v)
        if '十' not in v: return D.get(v)
        a, _, b = v.partition('十')
        return (D.get(a, 1) if a else 1) * 10 + (D.get(b, 0) if b else 0)
    bad = []
    # 🚨 2026-09-10：本规则**只扫 md** ⇒ 脚本 docstring 里的同类声称它看不见。
    #   实测代价：`gate-run.py` 的模块 docstring 写着「本流水线有 **22** 道门禁」，
    #   而正本名册当时已是 **28** —— 一句过期六道的声称，在门禁全绿的情况下活着。
    #   ⭐ 与本轮那个 phantom 同族：**不是判据写错了，是它没往那儿看**。
    #   ⇒ 量程加上 scripts/ 下的 .py/.mjs（注释与 docstring 同样是「文档」）。
    #   ⚠️ 第一版直接把脚本并进同一条判据 ⇒ **3 条里几乎全是误伤**：
    #     脚本里的「N 道门禁」多指**上下文里的那几道**
    #     （`_browser` 说的是四个浏览器门、`_section` 说的是它的 9 个依赖方），
    #     与文档里「流水线总数」是**两个语义**。⭐ 一个词在两种上下文里意思不同，
    #     把量程扩过去就是在惩罚正确的注释。
    #   ⇒ 脚本里只认**明确指总数**的句式（本流水线/全流程/本 SOP + 共/有 + N 道门禁）。
    _TOTAL = _re.compile(r'(?:本流水线|全流程|本\s*SOP|整条流水线)\s*(?:共)?\s*有?\s*'
                         r'([零一二三四五六七八九十\d]+)\s*道门禁')
    for _f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))
                     + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        _src = read(_f) or ''
        _skip = fixture_lines(_src)   # 变异靶里的「八道门禁」是故意造的（第五次犯同一形状）
        for _ln, _line in enumerate(_src.split('\n'), 1):
            if _ln in _skip:
                continue
            _m = _TOTAL.search(_line)
            if _m and cn2int(_m.group(1)) != n:
                bad.append("%s:%d 声称流水线共 %s 道门禁，实际 %d 道"
                           % (os.path.basename(_f), _ln, _m.group(1), n))
    for f in md_files(root):
        s = read(f) or ''
        # ⚠️ 疑问/指代量词不是「声称的数量」：「本该被**哪一道**门禁拦住」
        #    「**每一道**门禁都要自证」——首版把这里的「一」读成了声称 1 道，
        #    于是**一句提问被当成了不一致**。⭐ 过度宽松会漏，过度贪婪会误报，
        #    而误报的代价是逼人去改本来正确的文案来迁就门禁。
        for m in re.finditer(r'(?<![哪每这那某任])([零一二三四五六七八九十两\d]+)\s*道(?:确定性)?门禁', s):
            v = m.group(1)
            got = cn2int(v)
            if got and got != n:
                line = s[:m.start()].count('\n') + 1
                bad.append("%s:%d 声称 %s 道门禁，实际 %d 道" % (os.path.relpath(f, root), line, v, n))
    # 🚨 2026-09-12：量程**第三次**被发现开小了 —— 这次漏的是**图源**。
    #   实测代价：我当天新画的三张示例图里，`(30 道)`、`41 道`、`(41 道)` 三处全错，
    #   ⛔ 而且两张图**互相矛盾**（30 vs 41）；元门禁 41/0 全绿，一条都没拦。
    #   ⭐ 41 是**元门禁规则数**不是门禁道数 —— 我把两个量搞混了，正是「量错对象」。
    #   ⇒ 量程加上图源（图上的数字和文档里的数字是同一种声称，只是换了载体）。
    #   ⚠️ 只扫**本 skill 自己的** templates/diagrams —— 产品经理项目里的图写自己的数，
    #     扫过去就是惩罚正确的图（同 md 与脚本那两次的教训）。
    #   ⚠️ **量程边界（实测踩出来的）**：判据认的是规范句式「N 道门禁」。
    #     图源标签常写成 `"跑确定性门禁\n(31 道)"` —— 数字在「门禁」**之后**，
    #     ⛔ 本判据**认不出**。⭐ 我第一次验这条扩展时就选中了这种写法，
    #       于是「扩了量程」和「扩了个死的」一模一样，差点当成功收工。
    #     ⇒ 处置：把 skill 自己的图源**统一成规范句式**（已逐张变异验过在量程内），
    #       ⛔ 不去猜行尾/跨行的花式写法 —— 猜出来的判据下次还会漏。
    for f in sorted(glob.glob(os.path.join(root, 'templates', 'diagrams', '*.d2'))
                    + glob.glob(os.path.join(root, 'templates', 'diagrams', '*.mmd'))
                    + glob.glob(os.path.join(root, 'templates', 'diagrams', '*.puml'))):
        src = read(f) or ''
        for m in re.finditer(r'(?<![哪每这那某任])([零一二三四五六七八九十两\d]+)\s*道(?:确定性)?门禁', src):
            got = cn2int(m.group(1))
            if got and got != n:
                line = src[:m.start()].count('\n') + 1
                bad.append("%s:%d 图源里声称 %s 道门禁，实际 %d 道"
                           % (os.path.relpath(f, root), line, m.group(1), n))
    return (not bad), bad or "门禁道数一致"

# --------------------------------------------------------------- R7 视角
@rule("perspective-count", "视角数声称 = review-perspectives 实际视角数，且流程列表覆盖全部视角")
def r_persp(root):
    p = os.path.join(root, 'references', 'review-perspectives.md')
    s = read(p)
    if s is None: return None, "视角库文件不存在"
    ids = sorted(int(x) for x in re.findall(r'^###\s*视角\s*(\d+)\s*·', s, re.M))
    if not ids: return None, "解析不出视角编号"
    n = max(ids)
    bad = []
    # 流程列表必须覆盖每个视角
    # ⚠️ 锚点必须锚到真正的流程块（含 R1 那段），不能锚到正文里第一次提到「第一大轮」
    #    的散句 —— 否则规则会对所有视角都报缺失，是典型的假阳性。
    flow = None
    for m in re.finditer(r'第一大轮', s):
        # 锚到下一个同级标题，不用 1500 字符窗口（本规则自己禁止的形状）
        _nx = re.search(r'^#{1,3}\s', s[m.end():], re.M)
        seg = s[m.start(): m.end() + (_nx.start() if _nx else len(s))]
        if re.search(r'^\s*R1\s', seg, re.M):
            flow = re.match(r'[\s\S]*', seg); break
    if flow:
        rounds = set(int(x) for x in re.findall(r'^\s*R(\d+)\s', flow.group(0), re.M))
        miss = [i for i in ids if i not in rounds]
        if miss:
            bad.append("标准流程列表缺视角 %s（review-perspectives.md 第一大轮）" %
                       ",".join("视角%d" % i for i in miss))
    for f in md_files(root):
        t = read(f) or ''
        for m in re.finditer(r'(\d+)\s*个?\s*视角(?:库)?(?:全跑|跑满|各跑)', t):
            # ⚠️ 阶段「必跑子集」不是全库口径，不许当成不一致 —— 但子集必须被显式标注为子集，
            #    否则读的人分不清「跑满 5 个」是全库还是本阶段。判据：附近 120 字内出现
            #    「必跑 / 子集 / 本阶段」即认定为子集声明，放行；否则按全库口径核。
            near = t[max(0, m.start() - 120): m.end() + 120]
            if any(k in near for k in ('必跑', '子集', '本阶段')):
                continue
            if int(m.group(1)) != n:
                line = t[:m.start()].count('\n') + 1
                bad.append("%s:%d 声称「%s 视角」，视角库实际 %d 个" %
                           (os.path.relpath(f, root), line, m.group(1), n))
        # ⚠️ 判据必须覆盖**实际出现过的所有写法**，不是我设想的那两种。
        #    首版只认「N 视角全跑/跑满/各跑」与「完整视角库（N 个」，
        #    而「视角库见 …（11 视角，含专问什么）」这种写法**整个不在量程里** ——
        #    变异改到了文件、规则却照样放行。**反证不生效往往不是反证写错，是量程不对。**
        for ln_no, line in enumerate(t.split('\n'), 1):
            if '视角库' not in line and 'review-perspectives' not in line:
                continue
            for m in re.finditer(r'(\d+)\s*个?\s*视角', line):
                # ⚠️ 豁免必须按**每个数字自己的上下文**判，不能按整行判 ——
                #    「视角库（11 视角…）；时间紧张时快审 3-4 个」这一行里，
                #    「快审」把同一行的**库容量声称**也一起豁免掉了，变异因此存活。
                near = line[max(0, m.start() - 24): m.end() + 24]
                if any(k in near for k in ('必跑', '子集', '本阶段', '快审')):
                    continue
                if int(m.group(1)) != n:
                    bad.append("%s:%d 提到视角库时写「%s 视角」，实际 %d 个"
                               % (os.path.relpath(f, root), ln_no, m.group(1), n))
    return (not bad), bad or "视角口径一致（%d 个）" % n

@rule("template-vs-gate", "模板跑完备度门的缺口集合只许缩小（门禁要求的东西，模板里必须有地方写）")
def r_tpl_gate(root):
    """⭐ 2026-09-01 新增。起因是一处**只有两端对账才能发现**的错位：

    完备度门要求「AI 功能必须在附件 B.2 有算法能力边界」，判据是「F-xx 出现在附件 B」；
    而模板的 B.2 是**能力项表**（推理延迟/准确率/…），**整段一个 F-xx 都没有**。
    照模板填完 → 门禁必红 → 而且看不出该改哪里。**门禁要求的东西，模板里必须有地方写。**

    判据用棘轮而不是「必须零缺口」：模板是骨架、带占位符，有些缺口是**应有的**
    （只放一个示例小节、附件只给表头）。所以钉住当前集合，**只许缩小**。
    """
    tpl = os.path.join(root, 'templates', 'prd-complete.md')
    chk = os.path.join(root, 'scripts', 'prd_completeness_check.py')
    if not (os.path.isfile(tpl) and os.path.isfile(chk)):
        return None, "模板或完备度门禁不存在"
    r = subprocess.run([sys.executable, chk, tpl], capture_output=True, text=True)
    if r.returncode not in (0, 2):
        return False, ["完备度门禁在模板上跑不了（exit=%d）：%s" % (r.returncode, (r.stderr or '')[:120])]
    # ⛔ 2026-09-06 修：原来 `split()[0]` 只取第一个 token ——
    #   「附件 A 验收标准 未覆盖」被压成「附件」，四类附件缺口坍缩成一个身份，
    #   **任何新的附件类缺口都进不了棘轮**（而本规则的立规起因 B.2 恰恰是附件问题）。
    #   变异自证当场证实：从模板 B.2 删掉 F-xx，本规则照样绿。
    #   类别与尾部 ID 列表之间是列对齐的连续空格 ⇒ 按「2+ 空格」切，保住完整类别名。
    got = {re.split(r'\s{2,}', ln.strip().lstrip('· ').strip())[0]
           for ln in r.stdout.splitlines() if ln.startswith('  · ')}
    BASE = {"第四章缺整节",
            "附件 A 验收标准 未覆盖", "附件 D 字段规格 未覆盖",
            "附件 E 状态机边界 未覆盖", "附件 F 文案规格 未覆盖",
            "全局 NFR 缺类别",
            "双端功能未在第四章回答三选一（两端同一套交互/降级版/只在一端存在）"}
    extra = sorted(x for x in got if x not in BASE)
    return (not extra), (["模板出现新的缺口类别（多半是门禁加了要求而模板没地方写）：" + ", ".join(extra)]
                         if extra else "模板缺口 %d 类，均在骨架基线内" % len(got))


@rule("selftest-claim", "每个门禁都必须真的接受 --self-test（M8：没见过它变红＝没有这道门）")
def r_selftest(root):
    """⚠️ 本规则起因：`design-quality-gates.md` 曾写着「**全部**门禁与扫描均自带 --self-test」，
    而当时 5 道门禁并没有 —— 我自己犯的「声称 ≠ 实际」。
    这类断言不会让任何东西报错，只会让人以为门禁验过了。现在它常驻被守着。
    """
    import glob as _g
    bad = []
    # ⚠️ 2026-09-01 两次扩量程，第二次把「按文件名猜」换成「按目录登记」：
    #    ① 第一次：`*-gate.py` / `*_check.py` 之外还有**共用解析器**（`_prd_parse` /
    #       `_scene_parse`）—— 它们编码的是判据，一旦错，每个下游门禁看到的东西都跟着错
    #       且不会有任何东西报错（今天 G1 假阳性 100% 的根因正是一个解析器正则）。
    #    ② 第二次：按文件名匹配**总会漏**——`sec-scan.py` / `taste-memory.py` /
    #       `tokens-to-css.py` 三个都在门禁目录里登记着，却一个模式都不匹配。
    #       ⭐ 改为**从目录反查**：凡是 design-quality-gates.md 里点名的 scripts/*.py，
    #       都必须能自证。量程从此跟着目录走，不跟着命名习惯走。
    cat_txt = read(os.path.join(root, 'references', 'design-quality-gates.md')) or ''
    named = set(re.findall(r'`?(\w[\w.-]*\.py)`?', cat_txt))
    # 🚨 2026-09-10：新元规则 `gate-roster-single-source` **当场在这里又抓到一套自己的 glob**
    #   —— 我刚把三个消费方统一到正本，而元门禁内部还留着第四套。
    #   ⭐ 「一处正本 N 处照做入口」的第 N+1 次实证：**改正本不核消费方，就是没改完**。
    #   ⇒ 名册走正本，再并上「目录里点名的 .py」与解析辅助（本条的量程比名册更宽，
    #     它要求的是「凡是目录点过名的都得能自证」，那是名册之外的额外要求）。
    gates = sorted(set(gate_files(root))
                   | {p for p in _g.glob(os.path.join(root, 'scripts', '*.py'))
                      if os.path.basename(p) in named}
                   | set(_g.glob(os.path.join(root, 'scripts', '_*_parse.py'))))
    # Round 2 R-2：共用判据模块不一定叫 *_parse；只要被其它 Python 脚本 import，
    # 就必须进入自证量程。用 AST 读真实 import，不再靠文件名白名单。
    import ast as _ast
    imported_private = set()
    for consumer in _g.glob(os.path.join(root, 'scripts', '*.py')):
        try:
            tree = _ast.parse(read(consumer) or '')
        except SyntaxError:
            continue
        modules = []
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, _ast.Import):
                modules.extend(alias.name for alias in node.names)
        for module in modules:
            if module.startswith('_') and '.' not in module:
                target = os.path.join(root, 'scripts', module + '.py')
                if os.path.isfile(target) and os.path.abspath(target) != os.path.abspath(consumer):
                    imported_private.add(target)
    gates = sorted(set(gates) | imported_private)
    def code_only(src):
        """剥掉三引号字符串与 # 注释 —— 只看**代码**。

        🚨 2026-09-01：本规则原来全文 grep `--self-test`，于是**注释里提一句就算通过**。
        实测：把 `_scene_parse.py` 的参数处理改坏，它照样报绿（因为同一文件的注释里
        写着「统一接受 `--self-test`」）。⭐ 「提一句就算数」今天第三次出现，
        这回在元门禁自己身上 —— **判据要看实现，不看提及**。
        """
        src = re.sub(r'(?s)""".*?"""|\'\'\'.*?\'\'\'', '', src)
        return re.sub(r'#[^\n]*', '', src)

    # 🚨🚨 2026-09-10 第六轮独立复核（E4）：本条**结构性不可能变红** ——
    #   它的名单 `gates` 来自 `gate_files()`，而 `gate_files()` 的第一道前置条件是
    #   `if '--self-test' not in _s: continue`。⭐ **被强制的属性正是被检查的前提条件**：
    #   一道没有 `--self-test` 的真门禁根本进不了名单，于是这条规则永远说「全部具备」。
    #   而它自己的自证夹具造的 `stealth-check.py` **写着 `--self-test`**，
    #   只覆盖了前置条件之后那一层，天生测不到这个盲区。
    #   ⇒ 本条改用**更宽的名册**：scripts/ 下所有非 `_` 前缀、非显式豁免的脚本。
    #     ⛔ 只改这一条的量程，不动 `gate_files()`（那会把生成器全扫进另外 8 条规则）。
    _roster = sorted(set(gates) | {
        _p for _p in (glob.glob(os.path.join(root, 'scripts', '*.py'))
                      + glob.glob(os.path.join(root, 'scripts', '*.mjs')))
        if not os.path.basename(_p).startswith('_')
        and os.path.basename(_p) not in GATE_LIKE_EXEMPT})
    for gp in _roster:
        src = code_only(read(gp) or '')
        if '--self-test' not in src:
            bad.append("%s 没有 --self-test —— M8 要求每道门在被信任前先自证会出声"
                       % os.path.basename(gp))
    return (not bad), bad or "%d 个脚本全部具备 --self-test" % len(_roster)

# --------------------------------------------------------------- R8 模板对冲
# 🚨🚨 2026-09-12：本表原来锚的是 `### 3.2` / `### 3.3` —— **会变的章号**。
#   方案 A 章序重排（三章→六章）之后，两条判据**整个失效**：它们不报错，
#   而是**静默地不再检查任何东西**（`re.search` 找不到节 ⇒ `continue`）。
#   ⭐ 与 `no-positional-window` 治的是同一件事：**判据不许锚在会变的位置上**。
#     章号会随重排变，**节名不会**。⇒ 一律锚**节名**。
#   ⚠️ 发现路径值得记：是 harness 报「变异是 no-op，用例失效」把它牵出来的 ——
#     一发打空的变异，顺藤摸到了**两条已经死掉的判据**。
BANNED = [
    ("templates/prd-complete.md", r'###\s*[\d.]*\s*功能清单[\s\S]{0,900}',
     r'思维导图|Mind\s*Map', "功能清单不许画思维导图（SKILL.md「先选对表现形式」，返工换来的）"),
    ("templates/prd-complete.md", r'###\s*[\d.]*\s*页面结构[\s\S]{0,900}',
     r'流程图|Flowchart', "页面结构不许画流程图，要 IA Sitemap（同上）"),
]
@rule("template-vs-skill", "模板教的做法不得与 SKILL 明令禁止的相反")
def r_tpl(root):
    # ⚠️ 必须区分「用 X」与「不要用 X」。首版只查关键词出现，于是把我自己新写的
    #    **禁止句**也判成了违规 —— 规则不能只认词，要认这句话在主张什么。
    PROHIBIT = ('⛔', '❌', '不要', '不许', '别用', '不是', '而非', '不得')
    bad = []
    for rel, seg_pat, ban_pat, why in BANNED:
        s = read(os.path.join(root, rel))
        if s is None: continue
        m = re.search(seg_pat, s)
        if not m: continue
        seg = m.group(0)
        for hit in re.finditer(ban_pat, seg):
            # 句界：中文句号/换行/列表符
            # ⚠️ 按**整行**判，不按句判。禁止句常常跨句延续（「不要画流程图。页面一多，
            #    跨层箭头必然交叉；而且流程图只画得出跳转」）—— 按句切会把后半句判成违规。
            a = seg.rfind('\n', 0, hit.start())
            b = seg.find('\n', hit.end()); b = b if b > 0 else len(seg)
            line_txt = seg[a + 1: b]
            if any(k in line_txt for k in PROHIBIT):
                continue
            line = s[:m.start() + hit.start()].count('\n') + 1
            bad.append("%s:%d 出现「%s」—— %s" % (rel, line, hit.group(0), why))
    return (not bad), bad or "模板与 SKILL 无对冲"


# ------------------------------------------------- R13 目录的「什么时候跑」= 阶段表实际挂的
@rule("gate-stage-match", "门禁目录说某道门在 S<n> 跑，S<n> 的门禁栏就必须挂着它")
def r_gate_stage(root):
    """⚠️ 2026-08-31 自审发现 7 处：目录写着「S6 交付前跑」「S7 每批写入后跑」，
    而 S6/S7 的出场条件里**根本没有这几道**。
    ⭐⭐ 与 `gate-wired` 的区别：那条查「有没有被挂在任何地方」，
    这条查**「挂的位置对不对得上目录说的时机」**——
    挂错阶段和没挂，后果一样：**该拦的那一刻它不在场。**
    """
    cat = read(os.path.join(root, 'references', 'design-quality-gates.md'))
    md = read(os.path.join(root, 'SKILL.md'))
    if not cat or not md: return None, "读不到目录或 SKILL.md"
    try:
        # ⚠️ 锚定行首（与 no-positional-window 的要求一致——规则对自己也生效）
        seg = md[md.index('\n## 十阶段总表'):md.index('\n## 铁律')]
    except ValueError:
        return None, "SKILL.md 结构变了"
    # ⭐ SOP 详表(每阶段出场门禁栏)已按渐进式披露外移到 stage-playbook.md;接线面 = SKILL 段 + playbook。
    seg += '\n' + (read(os.path.join(root, 'references', 'stage-playbook.md')) or '')
    rows = re.findall(r'\|\s*[\w.]+\s*\|\s*`([\w.\-]+\.(?:py|mjs))`[^|]*\|[^|]*\|[^|]*\|([^|]*)\|', cat)
    if not rows: return None, "目录里解析不出「门禁 × 什么时候跑」"
    bad = []
    for script, when in rows:
        for st in sorted(set(re.findall(r'S(\d+(?:\.\d+)?)', when))):
            lines = [l for l in seg.split('\n')
                     if re.match(r'\|\s*\*\*S%s\*\*' % re.escape(st), l.strip())]
            if not lines: continue
            if not any(script in l for l in lines):
                bad.append("目录说 %s 在 S%s 跑，但 S%s 的门禁栏没挂它" % (script, st, st))
    if bad: return False, bad[:8]
    return True, "%d 条「门禁 × 阶段」对得上" % len(rows)



# ------------------------------------------------- R12 门禁必须被挂进某个阶段
@rule("crash-is-unable", "门禁自身崩溃必须报 2，不许和「有发现」共用退出码 1")
def r_crash_unable(root):
    """🚨 2026-09-05 实测：喂一个坏 JSON 给 `demo-anchor-gate`，
    得到 **rc=1 + Traceback** —— **崩溃与「发现缺陷」在退出码上完全一样**。

    后果有两层，第二层更隐蔽：
      ① 报告里它长成「有发现」，把人送去查一个**不存在的缺陷**；
      ② 自证里只看退出码的反例，**崩溃会被读成「反例红了」** ——
         于是一条其实没在守任何东西的反例，看起来一直是绿的。
    （形状由并行会话 fm-agent 提出，它那边是「反例对象被别的判据消费 ⇒ KeyError」。）

    ⭐ 本规则**真跑**，不做静态匹配：喂一个畸形输入，断言退出码不是 1。
       静态查 `except Exception` 会把「写了但没接到入口上」判成通过。
    """
    # ⚠️ 成本：实测半边每次要跑 17 个子进程，而**变异型自证会为每条变异重跑一遍元门禁**
    #    ⇒ 平方级（实测卡在 7 分钟以上还没跑完）。
    #    ⭐ **一道要跑 20 分钟的自证等于没人会跑它** —— 那正是这套东西要防的。
    #    ⇒ 变异自证里只做结构半边，并**在证据行里写明跳过了实测**（不静默）。
    #    实测半边由 R24 自己的反向测试与日常整跑覆盖。
    fast = os.environ.get('CG_FAST') == '1'
    import tempfile as _tf
    bad = os.path.join(_tf.mkdtemp(prefix='crash-'), 'bad.json')
    io.open(bad, 'w', encoding='utf-8').write('not json at all {{{')
    offenders, checked = [], 0
    for g in ([] if fast else gate_files(root)):
        fn = os.path.basename(g)
        if fn == 'consistency-gate.py' or g.endswith('.mjs'):
            continue                      # 元门禁自己 / .mjs 另有入口约定
        try:
            r = subprocess.run([sys.executable, g, bad],
                               capture_output=True, text=True, timeout=120)
        except Exception:
            continue
        checked += 1
        if r.returncode == 1 and 'Traceback' in (r.stderr or ''):
            offenders.append(fn)
    # ⚠️ 只做实测是不够的：**探针输入不一定能让每道门崩**。
    #    2026-09-05 反向测实证：拆掉 `retro-gate` 的兜底，本规则**照样绿** ——
    #    因为它拿到坏 JSON 根本不崩（按文本读，读什么都行）。
    #    ⇒ 「通过」不是因为都安全，而是因为多数门在这个输入上不崩。
    #    ⭐ 补结构半边：入口必须**真的被兜底包住**，否则下次换个输入就穿了。
    unwrapped = []
    for g in gate_files(root):
        fn = os.path.basename(g)
        if fn == 'consistency-gate.py' or g.endswith('.mjs'): continue
        s = read(g) or ''
        # ⛔ 查**调用点**，不是查名字 —— `def _main_guarded(fn):` 本身就含这个字符串，
        #    首版写 `'_main_guarded(' not in s` ⇒ 删掉调用它照样通过（反向测当场证伪）。
        #    ⭐ 「查名字在不在」而不是「它有没有被接线」，今天第 N 次同一形状。
        # ⛔ **不给兜底路径**：原本写成 `not wired and not (except…exit(2))`，
        #    而多数门两者都有 ⇒ 拆掉 wrap 时第二条把它兜住 ⇒ 反向测连续两次判「不承重」。
        #    ⭐ 这正是本轮第一条教训（多路兜底 ⇒ 单点变异不会红）在最后一条规则上的重演。
        #    17 道门现已全部 wrap，直接要求 wired，不留第二条路。
        wired = re.search(r'^\s+_main_guarded\(\s*\w+\s*\)\s*$', s, re.M)
        if not wired:
            unwrapped.append(fn)
    if not checked and not fast: return None, "没有可跑的门禁"
    bad = []
    if offenders: bad.append("崩溃被报成「有发现」（rc=1 且带 Traceback）：" + "、".join(offenders))
    if unwrapped: bad.append("入口没有被「意外异常 → 2」兜底包住：" + "、".join(unwrapped))
    return (not bad,
            "；".join(bad) if bad else
            ("⚡ CG_FAST：只做了结构半边（入口都有兜底）—— **实测半边本次跳过**，"
             "由 R24 自己的反向测试与日常整跑覆盖"
             if fast else
             "%d 道门禁：实测自身异常不会被误报成「有发现」，且入口都有兜底" % checked))


@rule("boundary-on-green", "每道门禁都要在输出里说清它**验不了什么**")
def r_boundary(root):
    """一道不说边界的绿，会被当成比它实际更强的保证。

    2026-09-06 实测：`retro` / `element-identity` / `scenario-matrix` /
    `token-provenance` 四道门通过时只说「通过」，一句边界都没有。
    比如 `token-provenance` 绿了只说「全部令牌来源可追」——
    而它**不验那个来源说的是不是真的**：`derived:` 没有任何东西核对，
    `measured:` 只核到「文件存在」，不核「文件里真有这个数」。

    ⚠️ **判据是弱的，故意的。** 我先写了个按措辞匹配的强正则，报出 14 道，
    抽查两道发现它们**都有**边界句、只是措辞不在词表里 ⇒ **大面积假阳性**。
    改成实跑一遍看输出，13 道里只有 3 道真的缺。
    ⇒ 这里退回到只查「输出语句里有没有 ⚠️/⛔」：**宁可漏，不可误伤** ——
    一个会把 11 道正常门标红的规则，最终会被加豁免清单然后没人跑。
    （剥掉自证段，否则自证里讲 ⚠️ 的字样会自噪。）
    """
    import re as _re
    bad = []
    for g in gate_files(root):
        fn = os.path.basename(g)
        if fn == 'consistency-gate.py': continue
        s = read(g) or ''
        for mk in ('\ndef _self_test', '\ndef self_test',
                   '\nasync function selfTest', '\nfunction selfTest'):
            i = s.find(mk)
            if i > 0: s = s[:i]; break
        if not _re.search(r'(print|console\.log)\([^\n]*[⚠⛔]', s):
            bad.append(fn)
    return (not bad,
            ("这些门禁的输出里一句边界都没有：" + "、".join(bad)) if bad
            else "每道门禁的输出里都说了它验不了什么")


@rule("gate-registered", "每道门禁都要在 gate-run.py 的退出码语义表里登记（回落是静默的）")
def r_gate_registered(root):
    """`gate-wired` 管的是「门禁在不在某个阶段的出场条件里」，
    盖不到这一层：**gate-run.py 认不认得它**。

    gate-run 取语义用的是 `EXIT_SEMANTICS.get(fn, STD)` —— **回落是静默的**。
    对退出码非标的门（`prd_completeness_check` 是 2=FAIL、
    `coverage_check` 是 3=PASS_WITH_GAPS），一旦漏登记，
    它的**红会被记成 UNABLE**，而 `--status --gate` 打印出来
    和「跑了但没法查」一模一样 —— 一条真实的失败被读成环境问题。

    ⭐ 与 gate-wired 是两个不同的「存在 ≠ 在守」：
      gate-wired：门在，但没人调用它。
      本条    ：门在、也被调用，但**记录它的人不认识它的语言**。
    """
    import re as _re
    gates = [os.path.basename(g) for g in gate_files(root)]
    gr = read(os.path.join(root, 'scripts', 'gate-run.py'))
    if gr is None: return None, "读不到 gate-run.py"
    m = _re.search(r"EXIT_SEMANTICS = \{.*?\n\}", gr, _re.S)
    if not m: return None, "gate-run.py 里找不到 EXIT_SEMANTICS 表"
    known = set(_re.findall(r"'([a-z0-9_][a-z0-9_.-]*\.(?:py|mjs))'", m.group(0)))
    EXEMPT = {"consistency-gate.py", "no-loss-gate.py"}   # 元门禁不进阶段流水线
    missing = sorted(set(gates) - known - EXEMPT)
    ghost = sorted(known - set(gates))
    bad = []
    if missing: bad.append("gate-run 认不得：" + "、".join(missing))
    if ghost:   bad.append("gate-run 登记了但磁盘上没有：" + "、".join(ghost))
    return (not bad), ("；".join(bad) if bad
                       else "%d 道门禁全部登记在案（含 %d 道非标退出码）"
                            % (len(gates) - len(EXEMPT & set(gates)),
                               sum(1 for g in gates if g in ('prd_completeness_check.py', 'coverage_check.py'))))


@rule("every-rule-has-a-guard", "每条元规则自己都必须有反例守着（skill 规则→变异靶，项目规则→case 夹具）")
def r_every_rule_guarded(root):
    """🚨 2026-09-11 立。**第三次**「立完规则忘配靶」之后加的工具，不是纪律。

    前两次：`section-parser-single-source`（我自己刚立的）、`gate-pairing-declared`。
    本会话第三次是 `gate-has-negative`。⭐ 本仓记过：
    **错到第三次去加工具，别加纪律** —— 写下的教训不会拦住我，机器检查会。

    ⭐ 一条没人守的规则，和没有这条规则，在输出上是一样的：全绿。

    ⚠️⚠️ 判据必须按**两种守卫机制**分别看，⛔ 不能只数变异表：
      · skill 规则（`RULES`）跑在 skill 自身上 → 守卫是 `MUTATIONS` 里的靶；
      · 项目规则（`PROJECT_RULES`）跑在项目目录上 → 守卫是 `case()` 夹具。
      立本条时我第一版只数了变异表，得出「5 条无靶」—— 那 5 条**全是项目规则，
      各自有 1~7 条 case 反例守着**。⭐ 差点给 5 条已经守好的规则再补一遍靶：
      **量错对象比量不到更危险**，因为它会产出一个看起来很像发现的数字。
    """
    # 🚨🚨 第一版这里用 `os.path.abspath(__file__)` 读**正在运行的自己**，
    #   而 RULES / MUTATIONS 也取自**运行中的模块** —— 于是变异测试对本条**结构性无效**：
    #   harness 跑的是原件（`sys.executable, __file__, dst`），改的是副本，本条永远看不见。
    #   ⭐ 与「修在拷贝没修事实源」同族，方向相反：**判在事实源，而被判的是拷贝**。
    #   ⇒ 一律从 `root` 静态解析，四个集合同源。
    gate_src_path = os.path.join(root, 'scripts', 'consistency-gate.py')
    src = read(gate_src_path) or ''
    if not src:
        return None, "读不到 %s —— 本条**没验**（⛔ 不是通过）" % gate_src_path
    skill_ids = set(re.findall(r'@rule\(\s*"([^"]+)"', src))
    proj_ids = set(re.findall(r'@prule\(\s*"([^"]+)"', src))
    if not skill_ids:
        return None, "在 %s 里一条 @rule 都没解析到 —— 本条**没验**（⛔ 不是通过）" % gate_src_path
    mut_block = src[src.find('\nMUTATIONS = ['):] if '\nMUTATIONS = [' in src else ''
    mut_ids = set(re.findall(r'\(\s*"([^"]+)",\s*"', mut_block))
    # 项目规则的守卫：`case(... , ["rule-id", ...])` 里点名它的反例
    # 项目规则的守卫：`case(..., ["rule-id"])` 里点名它的反例（同样从 root 的源码里找）
    cased = {rid for rid in proj_ids if ('["%s"]' % rid) in src}
    bad = []
    naked_skill = sorted(skill_ids - mut_ids - RULE_GUARD_EXEMPT.keys())
    naked_proj = sorted(proj_ids - cased - RULE_GUARD_EXEMPT.keys())
    if naked_skill:
        bad.append("skill 规则没有变异靶：%s" % "、".join(naked_skill))
    if naked_proj:
        bad.append("项目规则没有 case 反例：%s" % "、".join(naked_proj))
    # ⛔ 豁免登记表本身也要对账：登记了一条已经不存在的规则 ⇒ 表在腐烂，早晚豁免掉真东西
    stale = sorted(set(RULE_GUARD_EXEMPT) - skill_ids - proj_ids)
    if stale:
        bad.append("豁免表里登记了不存在的规则：%s（表在腐烂）" % "、".join(stale))
    return (not bad), ("；".join(bad) if bad
                       else "%d 条规则各有守卫（skill %d 条有靶 · 项目 %d 条有夹具 · 豁免 %d 条）"
                            % (len(skill_ids | proj_ids), len(skill_ids & mut_ids),
                               len(cased), len(RULE_GUARD_EXEMPT)))


# ⛔ 棘轮上限：只许降不许升。改这个数之前先问「我是在锚定判据，还是在放宽门槛」。
UNPINNED_NEGATIVE_CEILING = 59


@rule("negative-case-pins-criterion", "反例要锚定**是哪条判据红的**，不能只断言退出码（棘轮）")
def r_negative_pins(root):
    """🚨 2026-09-11 立。起因是同一形状当天出现两次：

      · `adr-check` 的反例②用了个不存在的路径 ⇒ 它红的原因是「文件不存在」
        而不是它声称的「符号不在」；
      · `g75-freeze-gate` 的反例①c 写死 `deferred(至2026-10-01)` ⇒
        过了那天它会**因为期限过期而红**，不再测它声称测的「无 owner」。

    ⭐ 一条只断言 `rc == 1` 的反例，只能证明**门红了**，不能证明**为这条理由红**。
      门一旦有多条判据（g75 有六查、product-structure 有十几条），
      夹具很容易在无意中同时触发另一条 —— 那时它看起来仍然是绿的。

    ## 量程与形态（实测 2026-09-11）

      · `case(名称, 夹具, 期望ID)` 34 条 —— **天然锚定**（第三参就是期望哪条规则红）；
      · `chk(名称, rc == 1)` 63 条 —— **未锚定**，本条数的就是它；
      · 其余 4 条形态特殊，不计入。

    ## ⚠️ 为什么是棘轮不是「全部修完」

    63 条里多数**当下是对的**（夹具只触发一条判据）。把它们一次性机械改写，
    收益不确定而回归风险真实。⇒ 记下上限，**只许降不许升**：
      新写的反例必须锚定；存量逐批改善。
    ⛔ 诚实边界：棘轮**不保证存量是对的**，它只保证这个数不再变大。
      「有 N 条未锚定」与「这 N 条都有问题」是两回事，⛔ 不许把前者说成后者。

    ⚠️ 量程只含 `.py`（`.mjs` 无可用 AST，见 ADR-0008），且只认
      **函数名字面是 chk/case、首参是含「反例」的字符串常量**的调用 ——
      换个 helper 名字就数不到。⛔ 如实写在这里，不假装扫全了。
    """
    import ast as _ast
    unpinned = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        src = read(f) or ''
        try:
            tree = _ast.parse(src)
        except Exception:
            continue
        for n in _ast.walk(tree):
            if not (isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)):
                continue
            if n.func.id not in ('chk', 'case') or not n.args:
                continue
            nm = n.args[0]
            if not (isinstance(nm, _ast.Constant) and isinstance(nm.value, str)
                    and '反例' in nm.value):
                continue
            if n.func.id == 'case':
                continue                      # 第三参即期望规则 id ⇒ 天然锚定
            if len(n.args) < 2:
                continue
            c = _ast.get_source_segment(src, n.args[1]) or ''
            has_rc = (any(k in c for k in ('rc ==', 'rc !=', 'returncode', 'run('))
                      or '== 1' in c or '== 2' in c)
            has_txt = any(k in c for k in ("' in ", '" in ', 'in out', 'in msg',
                                           'in _m', 'in log', 'in data'))
            if has_rc and not has_txt:
                unpinned.append('%s:%d' % (os.path.basename(f), n.lineno))
    n = len(unpinned)
    if n > UNPINNED_NEGATIVE_CEILING:
        from collections import Counter as _C
        top = '、'.join('%s×%d' % (k, v) for k, v in
                        _C(x.split(':')[0] for x in unpinned).most_common(3))
        return False, ("未锚定判据的反例 %d 条 > 棘轮上限 %d —— 新写的反例必须验**是哪条判据红的**"
                       "（只断言退出码证明不了这一点）。集中在：%s"
                       % (n, UNPINNED_NEGATIVE_CEILING, top))
    return True, ("未锚定判据的反例 %d 条 ≤ 棘轮上限 %d（⛔ 棘轮只保证不再变大，"
                  "**不保证存量都是对的**）" % (n, UNPINNED_NEGATIVE_CEILING))


@rule("no-always-true-assertion", "判据里不许出现**恒为真**的表达式（恒绿的用例什么都不测）")
def r_no_always_true(root):
    """🚨 2026-09-11 立。当天我自己写出**三个恒绿判据**，三次同形：

      · `adr-check` 的 superseded 检查：`re.search(pat, src.split(X)[0] + src)` ——
        `+ src` 让它永远包含全文，而每份 ADR 标题里就有自己的编号 ⇒ 永远通过；
      · `receipt-check` 的去重：`b.split(' ')[1]` 取到的是「字段」两个字不是字段名 ⇒ 永不匹配；
      · `g75-freeze-gate` 我新写的正例：`A if isinstance(_, tuple) else True` ——
        `_` 是字符串不是元组 ⇒ **恒为 True，这条用例什么都不测**。

    ⭐ 三次同形说明它不是偶发失误，是写判据时的稳定倾向：**写完就觉得它在守了**。
      本仓记过「错到第三次去加工具，别加纪律」——ADR-0003（承重确认）早就写着这条，
      而我今天仍然三次没做。⇒ 做成静态检查。

    ⚠️ 只报**静态可判**的三种形状（`X if C else True` / `… or True` / `assert True`），
      ⛔ 不做「猜这个条件实际会不会永远真」那种推断 —— 那会误伤一大片正常代码。
      诚实边界：**它抓不到我今天那另外两个**（`+ src`、`split(' ')[1]` 都要语义推理）。
      那两类靠承重确认（破坏判据看它红不红）抓，本条只兜最省事、也最常犯的那一类。
    ⚠️ 量程只含 `.py`：`.mjs` 没有可用的 AST（不引依赖，见 ADR-0008），
      ⛔ 这一条如实写在这里，不假装扫过了。
    """
    import ast as _ast
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        b = os.path.basename(f)
        try:
            tree = _ast.parse(read(f) or '')
        except Exception:
            continue                      # 语法坏掉由 py-parses 那条管，不在这里重复报
        for n in _ast.walk(tree):
            if (isinstance(n, _ast.IfExp) and isinstance(n.orelse, _ast.Constant)
                    and n.orelse.value is True):
                bad.append('%s:%d `X if C else True` —— C 为假时**恒通过**' % (b, n.lineno))
            if isinstance(n, _ast.BoolOp) and isinstance(n.op, _ast.Or):
                for v in n.values:
                    if isinstance(v, _ast.Constant) and v.value is True:
                        bad.append('%s:%d `… or True` —— 整个条件恒为真' % (b, n.lineno))
            if (isinstance(n, _ast.Assert) and isinstance(n.test, _ast.Constant)
                    and n.test.value is True):
                bad.append('%s:%d `assert True` —— 断言什么都没断' % (b, n.lineno))
    return (not bad), ("；".join(bad) if bad
                       else "%d 个脚本里没有静态可判的恒真判据"
                            % len(glob.glob(os.path.join(root, 'scripts', '*.py'))))


@rule("gate-has-negative", "名册里每道门禁都必须产出用例，且至少在一个口径下有反例")
def r_gate_has_negative(root):
    """🚨 2026-09-11 立。起因是我自己前一天写的代码开了个盲区。

    `design-quality-gates.md` 写着「**每道门禁至少在一个口径下有反例**」——
    实测当时是真的（28 道门，无零用例、无零反例），
    ⭐ **但没有任何东西在守它**，它可以随时悄悄变假。

    而 09-10 我给 `selftest-all` 加的 UNABLE 降级（非零退出 + 零用例 ⇒ UNABLE）
    正好把这句话最危险的那一半藏了起来：**一道自证悄悄什么都不产出的门，
    从此被归进 unableScripts 而不是 failedScripts** —— 看上去像「环境没跑起来」，
    实际是「这道门不再验任何东西」。本仓记过这一条：
    **降级成 UNABLE 与静音真缺陷，在代码上无法区分。**
    ⇒ 那就别靠代码区分，靠这条规则从**另一侧**查：门在名册里，就必须拿出用例和反例。

    ⚠️ 与 `selftest-claim` 的分工：那条查「**接受** --self-test」（结构），
      本条查「**产出了什么**」（实测）。前者结构上不可能红（名册前置条件就是它），
      后者才是真正会红的那一侧。
    """
    import json as _json
    # ⚠️⚠️ 2026-09-11：这里**曾经**读 `.selftest-progress.jsonl`，那是个自指回路 ——
    #   progress 是**边跑边追加**的，而本规则就在那次运行里被调用：跑到 consistency-gate 时
    #   字母序靠后的门还没测，于是规则报「名册里的门没被测过」，干净 clone 上必红。
    #   ⭐ 与 810↔747 振荡同源：**判据消费的文件，正由调用它的那次运行生产**。
    #   ⇒ 改读 `.selftest-measured.json` 的 perGate —— 那份是全部跑完之后**一次性写完**的。
    mf = os.path.join(root, 'references', '.selftest-measured.json')
    if not os.path.exists(mf):
        # 与 selftest-count-measured 同一裁决：gitignore 的运行生成物，新 clone 上本来就没有。
        # ⛔ 不折成通过，也不冒充内容失败。
        return None, ("没有 references/.selftest-measured.json（gitignore 的运行生成物）—— "
                      "本条**没验**：跑 `python3 scripts/selftest-all.py` 后它才有依据。"
                      "⛔ 不是「通过」也不是「不合格」")
    try:
        last = (_json.load(io.open(mf, encoding='utf-8')) or {}).get('perGate')
    except Exception as e:
        return False, "实测文件读不了（%s）—— 重跑 scripts/selftest-all.py" % e
    if not isinstance(last, dict):
        return None, ("实测文件里没有 perGate（旧版工具量的）—— 本条**没验**："
                      "重跑 `python3 scripts/selftest-all.py`。⛔ 不是「通过」")
    roster = gate_names(root)
    no_record, no_case, no_neg = [], [], []
    for g in roster:
        r = last.get(g)
        if r is None:
            no_record.append(g)            # 在名册里却从没被测过
        elif not r.get('cases'):
            no_case.append(g)              # ⭐ UNABLE 降级会把这一类藏起来
        elif not (r.get('negNumeric') or r.get('negLabel')):
            no_neg.append(g)
    bad = []
    if no_record:
        bad.append("在名册里但实测记录中没有：%s（跑过一次才有依据）" % "、".join(no_record))
    if no_case:
        bad.append("**零用例**：%s —— 自证跑了却什么都没产出，"
                   "在 selftest-all 里会被归进 unableScripts 看起来像「环境没起来」" % "、".join(no_case))
    if no_neg:
        bad.append("两个口径都没有反例：%s —— 只有正例的门禁没人见过它变红" % "、".join(no_neg))
    return (not bad), ("；".join(bad) if bad
                       else "%d 道门禁全部产出用例，且各自至少一个口径有反例" % len(roster))


@rule("selftest-count-measured", "文档里的自证用例数 = 实测值，且实测不早于任何自证脚本的改动")
def r_selftest_count(root):
    """2026-09-06：文档写「23 道门禁的自证共 358 个用例」。
    我当天给 platform-parity 加了 1 条用例 —— 那一刻 358 就是错的，
    **而元门禁 25 条全绿**：没有任何一条在守这个数字。

    ⭐ 它和 script-count 是同一族（数字型声称会安静过期），但多一层：
      script-count 的真值 `ls` 一下就有；用例数的真值**只有跑一遍才知道**。
      ⇒ 所以不能只对账数字，还要对账**这个数字是什么时候量的**：
        任何带 --self-test 的脚本比测量文件新 ⇒ 这个数字已经没有依据了。
      这与 gate-run.py 里「元门禁比门禁旧就拦住」是同一个形状：
      **让过期必须被主动绕过，而不是靠人记得重跑。**

    ⚠️ 只把「带 --self-test 的脚本」算进新旧比较 —— 改一个不参与自证的文件
       不会改变用例数，拿它去判过期就是**误伤**（宁可漏，不可误伤）。
    """
    import re as _re, json as _json
    claims, neg_claims = [], []
    for f in md_files(root):
        s0 = read(f) or ''
        for ln, line in enumerate(s0.split('\n'), 1):
            for m in _re.finditer(r'(\d+)\s*个用例', line):
                claims.append((os.path.basename(f), ln, int(m.group(1))))
            # 🚨 2026-09-09（独立复核揪出）：**反例两个口径的数字从立规则起就在量程外** ——
            #   文档写「按期望非零 351 个 / 按标题带反例 332 个」，而实测早已是别的数，
            #   三处口径互不相同且没有任何东西在守。⭐ 这条规则治的就是「数字型声称
            #   安静过期」，而它自己漏掉了同一段落里紧挨着的另外两个数字。
            # 🚨 2026-09-09 第二轮独立复核揪出：这条正则写的是「按期望非零」，
            #   而文档实际写法是「按**「期望非零退出码」**」（带书名号+完整词）⇒ **0 命中**。
            #   我上一批声称「两个口径都纳入量程」，实际只守住了一个。
            #   ⭐ 而它看起来是绿的，因为**变异测试当时的基线本来就红**（见下方 self_test
            #   的绿基线断言）——一个没在守的判据，配一个证不了任何东西的变异。
            for m in _re.finditer(r'按「?期望非零(?:退出码)?」?\s*(\d+)\s*个', line):
                neg_claims.append((os.path.basename(f), ln, int(m.group(1)),
                                   'negativesByExpectation', '按期望非零'))
            for m in _re.finditer(r'按标题带「反例」\s*(\d+)\s*个', line):
                neg_claims.append((os.path.basename(f), ln, int(m.group(1)),
                                   'negativesByLabel', '按标题带「反例」'))
    if not claims:
        return None, "没有任何文档声称用例数（无可对账）"
    mf = os.path.join(root, 'references', '.selftest-measured.json')
    if not os.path.exists(mf):
        # 🚨 2026-09-09 第二轮独立复核揪出：该文件是 **gitignore 的运行生成物**，
        #   于是**每个全新 clone 上这条规则都硬红** —— 而同一批我刚给 doc-sync-guard
        #   下过裁决：「依赖缺失是 UNABLE 不是 FAIL」。同一条纪律，元门禁自己没守。
        #   ⭐ 更糟的是它让**变异测试的基线在干净 clone 上永远不绿**（见 self_test 的
        #   绿基线断言），三发变异因此全部空转。
        #   ⇒ 改 UNABLE：说清缺什么、怎么补，⛔ 不折成通过、也不冒充内容失败。
        return None, ("没有实测文件 references/.selftest-measured.json（gitignore 的运行生成物，"
                      "新 clone 上本来就没有）—— 本条**没验**：跑 `python3 scripts/selftest-all.py` "
                      "后它才有依据。⛔ 不是「通过」也不是「不合格」")
    try:
        d = _json.load(open(mf, encoding='utf-8'))
    except Exception as e:
        # ⛔ 不是 N/A：声称已经写在文档里了，背书读不了 = 声称失去依据，和文件不存在同罪
        return False, "实测文件读不了（%s）—— 声称的数字失去背书，重跑 scripts/selftest-all.py" % e
    # 🚨 2026-09-11：残缺的实测文件此前让本条**整个崩掉**（`%d` 格式化 None，TypeError）——
    #   门禁崩了比判错更糟：它连个裁决都给不出，而调用方只看到一个非零退出码。
    #   实证：给它一份只有 perGate 的 measured.json（另一条规则的合成靶），当场 traceback。
    #   ⛔ 按本仓纪律，依赖残缺是 UNABLE，不是崩、也不是不合格。
    missing = [k for k in ('cases',) if not isinstance(d.get(k), int)]
    if missing:
        return None, ("实测文件缺字段 %s（旧版工具量的，或被别的流程改写过）—— "
                      "本条**没验**：重跑 `python3 scripts/selftest-all.py`。"
                      "⛔ 不是「通过」也不是「不合格」" % "、".join(missing))
    bad = ["%s:%d 写「%d 个用例」，实测 %d" % (a, b, c, d.get('cases'))
           for a, b, c in claims if c != d.get('cases')]
    bad += ["%s:%d 写「%s %d 个」，实测 %s" % (a, b, label, c, d.get(key))
            for a, b, c, key, label in neg_claims
            if isinstance(d.get(key), int) and c != d.get(key)]
    # ⚠️ 口径字段缺失 ≠ 数字对不上：拿 None 去比会打印「实测 None」，那是句没依据的话。
    bad += ["%s:%d 写「%s %d 个」，而实测文件里**没有这个口径**（重跑 selftest-all）"
            % (a, b, label, c)
            for a, b, c, key, label in neg_claims if not isinstance(d.get(key), int)]
    # 🚨 2026-09-10：数字对不上时，**先说清这次实测量的是哪个总体**。
    #   文档声称的是 clone 口径；实测跑在工作树上。别人一个未提交的文件就能让
    #   两者差 10 个用例（09-10 实测：并行会话的 receipt-check.py + evidence-receipt.json）。
    #   ⛔ 判决不变（仍红）：树脏不是豁免，否则真的文档漂移就能躲在脏树后面。
    #   ⭐ 改的是**诊断**：不带这句话时，照着报错去改文档 = 把 clone 口径的正确数字改成错的。
    if bad:
        td = d.get('treeDiff')
        if td:
            bad.append("⚠️ 上面这些数是在**与 %s 有 %d 处差异的工作树**上量的（%s%s）；"
                       "文档写的是 clone 口径。⭐ 先在干净克隆上复核："
                       "`git archive HEAD | tar -x -C <tmp> && cd <tmp>/skills/product-flow "
                       "&& python3 scripts/selftest-all.py --fresh`，**以那个数为准**"
                       % ('HEAD=' + d['headAt'] if d.get('headAt') else 'HEAD（量的时候是哪个 commit 没记下来）',
                          len(td), '、'.join(td[:4]), ' 等' if len(td) > 4 else ''))
        elif td is None:
            bad.append("⚠️ 问不到 git，**不知道**这次实测跑在什么树上（⛔ 不等于树是干净的）—— "
                       "数字对不上时先在干净克隆上复核")
    # ⚠️ 过期判据锚**内容哈希**不锚 mtime（2026-09-06 改）：
    #   mutation-sweep / reverse-test 的复原是重写文件 —— 内容一个字没变、mtime 变了，
    #   按 mtime 判会把「复原过」误读成「改过」，这条规则当天就误报了一次。
    import hashlib as _hl
    shas = d.get('shas')
    if not isinstance(shas, dict):
        return False, "实测文件没有 shas 表（旧版工具量的）—— 重跑 scripts/selftest-all.py"
    stale = []
    for g in (glob.glob(os.path.join(root, 'scripts', '*.py'))
              + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        try:
            src = open(g, 'rb').read()
            if b'--self-test' not in src:
                continue
        except Exception:
            continue
        if shas.get(os.path.basename(g)) != _hl.sha1(src).hexdigest():
            stale.append(os.path.basename(g))
    if stale:
        bad.append("这些自证脚本的内容与实测时不一致（改了没重测，或从没被测过）：%s"
                   % "、".join(sorted(stale)[:6]))
    return (not bad), ("；".join(bad) if bad
                       else "用例数声称与实测一致（%d 个），且全部自证脚本内容与实测时一致" % d.get('cases'))


@rule("help-exits-zero", "每个 CLI 的 --help 只显示帮助并退 0（求助不该触发一次全量运行）")
def r_help_zero(root):
    """2026-09-07 登记册#1：普查 22 个脚本 --help 报 2/3（当成缺输入拒绝），
    consistency-gate 自己更是会跑 40s 全量。已统一注入帮助分支；本规则守住不回退。
    ⚠️ CG_FAST（变异自证）下只查结构（帮助分支存在），全速下真跑逐个断言 rc=0 ——
    结构查会漏「分支在但放错位置永远不达」，真跑查不进变异循环（22 进程×35 变异太贵）。"""
    import subprocess as _sp
    fast = os.environ.get('CG_FAST') == '1'
    bad = []
    for g in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))
                    + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        fn = os.path.basename(g)
        if fn.startswith('_'):
            continue
        src = read(g) or ''
        # argparse 自带 --help（源码里可以不含字面量）；显式分支两者认其一。
        # 真跑半边（非 CG_FAST）才是最终判据 —— 结构半边只为变异套件里的快速红。
        if "--help" not in src and 'argparse' not in src:
            bad.append("%s 没有 --help 处理分支（也不用 argparse）" % fn); continue
        if fast:
            continue
        cmd = ([sys.executable] if fn.endswith('.py') else ['node']) + [g, '--help']
        try:
            r = _sp.run(cmd, capture_output=True, timeout=10)
            if r.returncode != 0:
                bad.append("%s --help 退出 %d（应为 0）" % (fn, r.returncode))
        except Exception as e:
            bad.append("%s --help 跑不动/超时：%s" % (fn, str(e)[:40]))
    note = "（CG_FAST：只查了分支存在，未真跑）" if fast else ""
    return (not bad), (bad or "全部 CLI 的 --help 都只显示帮助并退 0%s" % note)


@rule("stage-artifact-wired", "templates/ 下每个模板必须被 SKILL 或某 reference 路由（孤儿模板没人会用）")
def r_artifact_wired(root):
    """2026-09-08（终局规格 1-5）：一轮改造造出五个孤儿模板（module-result/run-manifest/
    contract-manifest/slice-registry/deviation-register 全都零路由）——
    与 gate-wired 同源：**产物存在 ≠ 有人会用它**，孤儿是结构性复发，得有结构性守卫。"""
    import glob as _g
    corpus = read(os.path.join(root, 'SKILL.md')) or ''
    for f in _g.glob(os.path.join(root, 'references', '*.md')):
        corpus += read(f) or ''
    EXEMPT = {'demo-scaffold.html'}          # 已标注反面教材，路由与否都不该被抄
    bad = []
    for f in sorted(_g.glob(os.path.join(root, 'templates', '*.md'))
                    + _g.glob(os.path.join(root, 'templates', '*.json'))
                    + _g.glob(os.path.join(root, 'templates', 'spec', '*.json'))):
        b = os.path.basename(f)
        if b in EXEMPT:
            continue
        if b not in corpus:
            bad.append("templates/%s 没有任何入口 —— 照 SKILL/references 走的人永远用不到它" % b)
    return (not bad), (bad or "全部模板都有路由入口")


@rule("spec-doc-in-sync", "spec 的结构口径已写进参考文档且未漂移（文档由 gen-docs.py 生成）")
def _spec_doc_in_sync(root):
    """⭐ 抄 gstack：文档的结构口径段**由脚本从 spec 生成，不许手改** ⇒ 两边不可能各说各话。

    ⚠️ 它守的是「文档 == spec」。⛔ 守不了「spec == 门禁」—— 那是 `spec-check.py`；
      也守不了「spec 写得对不对」—— 那要人读。三层各守一段，⛔ 别拿这一层的绿替另外两层背书。
    """
    gd = os.path.join(root, 'scripts', 'gen-docs.py')
    if not os.path.exists(gd):
        return None, 'N/A：本语料没有 gen-docs.py（它的存在性由 ref-exists 守）'
    if not glob.glob(os.path.join(root, 'spec', '*.json')):
        return None, 'N/A：本语料没有 spec/ —— 没有口径就无所谓漂移'
    import subprocess
    r = subprocess.run([sys.executable, gd, '--check'], cwd=root,
                       capture_output=True, text=True)
    if r.returncode == 0:
        return True, 'spec 口径与参考文档一致'
    bad = [l.strip('❌ ').strip() for l in (r.stdout or '').splitlines() if l.startswith('❌')]
    return False, bad[:4] or ['gen-docs.py --check 退出码 %d' % r.returncode]


@rule("output-template-parity", "registry 每个 outputs 项都已分类；template 类必须真有模板")
def r_output_template(root):
    """🚨 它补的是 `stage-artifact-wired` 的**反方向**。

    那条守「模板有没有人用」（防孤儿模板）；**没有任何东西守「声明了产出物却没给模板」** ——
    WO-002 终审的种子发现正是这个形状：`s8-testcases.md` ⑤ 定义了 5 种产出物，
    而 `templates/` 下**一个都没有**，照着做的人无从下手。
    ⭐ 手工补完模板不算完：下次谁往 ⑤ 里加第六种，仍然没有东西会红。

    ⛔ 为什么不能直接判「每个 output 都要有同名模板」（2026-09-16 实测否决）：
      18 个模块 60 个 outputs 里，37 条是**散文描述**（「A 锁批准记录」「运行证据」）、
      若干条是**生成物**（`coverage.json` 是 coverage_check 产出，⑤ 里明写⛔ 不给模板）、
      还有**外部原生产物**（飞书 PRD、Figma 稿）。一刀切会红 10 条而其中多数是正确做法 ——
      那是一道惩罚正确用法的门，按本仓历史它会被加豁免然后删掉。
    ⇒ 判据分两层：① 每个 output **必须被分类**（新增不分类就红）；
                  ② 只有 `template` 类才要求 `templates/` 下真有文件。

    kind 取值：template（该有模板）/ generated:<谁产出>（工具产物，⛔ 不给模板）/
              external:<在哪>（飞书/Figma 等原生）/ evidence:<是什么>（证据或记录，不模板化）。
    ⚠️ 除 template 外三类**必须带冒号后的理由**——不写理由的分类就是静音开关。
    """
    import json as _j
    reg = os.path.join(root, 'references', 'workflow-registry.json')
    if not os.path.exists(reg):
        # ⚠️ 2026-09-16 自证抓到：这里原来返回 UNABLE，于是**自证跑在没有 registry 的夹具根上时
        #   整轮退出码变 2**，而正文照印「自证通过」——退出码与结论脱节，正是本仓要治的形状。
        #   ⭐ 没有 registry ⇒ 没有被声明的产出物 ⇒ 本条**无对象**，是 N/A 不是「没测成」。
        #   ⛔ 它不等于「registry 可以没有」：registry 本身的存在由 `ref-exists` 守
        #     （flow-tailoring.md 与 s8-testcases.md 都引用了它）。
        return None, 'N/A：本语料没有 workflow-registry.json（registry 的存在性由 ref-exists 守）'
    try:
        data = _j.loads(read(reg) or '{}')
    except Exception as _e:
        return None, 'UNABLE：registry 解析失败 %s' % _e

    def _walk(o, path=''):
        if isinstance(o, dict):
            if 'outputs' in o and 'maxClaim' in o:
                yield path.split('/')[-1], o
            for k, v in o.items():
                yield from _walk(v, path + '/' + k)
    mods = dict(_walk(data))
    base = os.path.join(root, 'references', 'output-kind-baseline.json')
    pending = set()
    if os.path.exists(base):
        try:
            pending = set(_j.loads(read(base) or '{}').get('unclassified') or [])
        except Exception:
            pending = set()
    bad, n_t, n_c = [], 0, 0
    for mid, m in sorted(mods.items()):
        kinds = m.get('outputKinds') or {}
        tmpls = m.get('outputTemplates') or {}
        outputs = set(m['outputs'])
        for variants in m.get('outputsByResearchMode', {}).values():
            outputs.update(variants)
        for out in sorted(outputs):
            key = '%s::%s' % (mid, out)
            k = kinds.get(out)
            if not k:
                if key in pending:
                    continue                      # 棘轮基线：存量待分类，只许减不许增
                bad.append('%s 的产出物「%s」**没有分类** —— 加 outputKinds（template / '
                           'generated:<谁产出> / external:<在哪> / evidence:<是什么>）' % (mid, out))
                continue
            n_c += 1
            if key in pending:
                bad.append('%s 的「%s」已经分类了，却还挂在 output-kind-baseline —— ⛔ 划掉它' % (mid, out))
            if k == 'template':
                n_t += 1
                t = tmpls.get(out)
                if not t:
                    bad.append('%s 的「%s」标了 template，却没在 outputTemplates 里指出是哪个模板' % (mid, out))
                elif not os.path.exists(os.path.join(root, t)):
                    bad.append('%s 的「%s」指向的模板 %s **不存在**' % (mid, out, t))
            elif ':' not in k:
                bad.append('%s 的「%s」分类为 %s 却没写理由（冒号后）—— 不写理由的分类是静音开关'
                           % (mid, out, k))
    # 反方向：基线里挂着的项若已不存在于 registry，同样要划掉（防清单腐烂）
    live = {'%s::%s' % (mid, o) for mid, m in mods.items()
            for o in set(m['outputs']).union(*(set(v) for v in m.get('outputsByResearchMode', {}).values()))}
    for key in sorted(pending - live):
        bad.append('output-kind-baseline 里的「%s」已不在 registry 里 —— ⛔ 划掉它' % key)
    return (not bad), (bad[:8] if bad else
                       '%d 个产出物已分类（其中 template 类 %d 个，模板均存在）；待分类存量 %d'
                       % (n_c, n_t, len(pending)))


@rule("no-http-in-operations", "产品契约 operations.json 不得出现 HTTP 动词/路径/状态码（工程决定）")
def r_no_http(root):
    """2026-09-07 Codex P0-7 转正：api.json 曾写死 GET /tasks 与 403/404/500，
    与 techspec-readiness「产品不决定协议/路径/错误码」直接冲突。改名语义化后，
    这条规则防它长回来。"""
    import re as _re
    f = os.path.join(root, 'templates', 'spec', 'operations.json')
    if not os.path.exists(f):
        return None, "operations.json 不存在（无可对账）"
    raw = read(f) or ''
    bad = []
    for m in _re.finditer(r'"(?:GET|POST|PUT|PATCH|DELETE)\s+/', raw):
        bad.append("出现 HTTP 动词+路径：%s…" % raw[m.start():m.start()+28])
    if _re.search(r'"http"\s*:', raw):
        bad.append('出现 "http" 字段')
    for m in _re.finditer(r'"(40[0-9]|50[0-9])"\s*:', raw):
        bad.append("出现 HTTP 状态码键：%s" % m.group(1))
    return (not bad), (bad or "operations.json 只含语义操作，无工程接口决定")


@rule("skeleton-not-a-state", "Skeleton/骨架屏不得作为独立状态行出现（它是 loading 的呈现策略）")
def r_skeleton(root):
    """2026-09-07：批 1 修掉 PRD 模板的「6 态含 Skeleton」，当天又在
    interaction-spec 挖出两处漏网 —— 没有规则守着，改回去不会有任何声音。
    量程：templates/ 与 references/ 的 md；唯一源 interaction-patterns.md 除外。"""
    import re as _re
    bad = []
    for base in ('templates', 'references'):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.md') or fn == 'interaction-patterns.md':
                continue
            for ln, line in enumerate((read(os.path.join(d, fn)) or '').split('\n'), 1):
                if _re.match(r'^\|[^|]*\|\s*Skeleton\s*\|', line) or \
                   _re.search(r'\bSkeleton\s*(→|->)', line):
                    bad.append("%s/%s:%d 把 Skeleton 当独立状态：%s" % (base, fn, ln, line.strip()[:60]))
    return (not bad), (bad or "无 Skeleton 独立状态行（呈现策略归位于 loading）")


@rule("script-count", "「N 个脚本/骨架 js」的 N = 实际文件数")
def r_script_count(root):
    """2026-09-05：文档写「已扫过一遍自己的 48 个脚本/骨架 js」，
    而当天新增两个脚本后实际是 50 —— **那句「已扫过」对新文件并不成立**。

    ⭐ 这是当天找到的**第三个过期数字**（另两个：「每道最少 9 条反例」实际最少 4 条、
    自证用例名写「五条路径」而实际 6 条）。数字型声称会安静地过期，
    而且**读起来永远像是查过的**。能机械对账的就不要靠人记得改。
    """
    import re as _re
    _paths = (glob.glob(os.path.join(root, 'scripts', '*.py'))
              + glob.glob(os.path.join(root, 'scripts', '*.mjs'))
              + glob.glob(os.path.join(root, 'templates', 'proto', 'js', '*.js')))
    # 🚨 2026-09-09 第四轮独立复核（N1）：此前数的是**磁盘文件** ——
    #   于是本机多出几个未跟踪文件，文档就得写工作树的数；而那个数在**任何干净
    #   clone 上都对不上** ⇒ script-count 红 ⇒ 绿基线断言拒跑 ⇒
    #   **整套变异自证只有作者那台机器能跑绿**。
    #   ⭐ 受门禁守护的数字必须是**任何人 clone 下来都能复现**的那个。
    #   ⇒ 在 git 仓库里只数**已跟踪**文件；不在仓库里（如临时副本）时退回数磁盘。
    try:
        import subprocess as _sp
        _tracked = _sp.run(['git', '-C', root, 'ls-files',
                            'scripts/*.py', 'scripts/*.mjs', 'templates/proto/js/*.js'],
                           capture_output=True, text=True, timeout=20)
        _names = {os.path.basename(x) for x in _tracked.stdout.split() if x}
        if _names:
            _paths = [p for p in _paths if os.path.basename(p) in _names]
    except Exception:
        pass                      # 非 git 环境（临时副本）：退回数磁盘，语义不变
    n = len(_paths)
    if not n: return None, "找不到任何脚本（量程为空）"
    bad = []
    for f in md_files(root):
        s = read(f) or ''
        for ln, line in enumerate(s.split('\n'), 1):
            for m in _re.finditer(r'(\d+)\s*个脚本', line):
                if int(m.group(1)) != n:
                    bad.append("%s:%d 写「%s 个脚本」，实际 %d"
                               % (os.path.basename(f), ln, m.group(1), n))
    return (not bad), ("；".join(bad) if bad else "脚本数声称与实际一致（%d）" % n)


@rule("gate-wired", "每道门禁都要出现在某个阶段的出场条件里（存在 ≠ 会被跑）")
def r_gate_wired(root):
    """⚠️⚠️ 2026-08-31 自审发现：设计侧四道门禁
    （`ai-slop` / `visual-spec` / `token-provenance` / `interaction`）
    写了、自证绿了、在门禁目录里，**却不在任何阶段的出场条件里**——
    `visual-spec-gate` 在 SKILL.md 里甚至一次都没出现过。
    照 SOP 走的人在 S5 出场时根本不会跑它们。

    ⭐⭐ **这是「规则存在 ≠ 规则在守」的第四例，也是最贵的一种：
    门禁本身完好无损，只是没人调用它。**
    ⭐ 前几例是「规则的量程盖不住」，这一例是「规则根本不在链路上」。

    豁免：`consistency-gate`（元门禁，改任何文档后跑，不属于任何阶段）、
    转换器与非门禁脚本。
    """
    EXEMPT = {"consistency-gate.py", "no-loss-gate.py"}
    md = read(os.path.join(root, 'SKILL.md'))
    if md is None: return None, "读不到 SKILL.md"
    try:
        i = md.index('\n## 十阶段总表'); j = md.index('\n## 铁律')   # 同上：锚定行首
    except ValueError:
        return None, "SKILL.md 结构变了，定位不到阶段表与铁律之间的区段"
    # ⭐ SOP 详表(每阶段出场门禁栏)已按渐进式披露外移到 stage-playbook.md;出场条件面 = SKILL 段 + playbook。
    seg = md[i:j] + '\n' + (read(os.path.join(root, 'references', 'stage-playbook.md')) or '')
    gates = sorted(os.path.basename(x) for x in gate_files(root))
    bad = [g for g in gates if g not in EXEMPT and g not in seg]
    if bad:
        return False, ["%s 不在任何阶段的出场条件里 —— 它不会被跑" % g for g in bad]
    return True, "%d 道门禁全部挂在阶段上" % (len(gates) - len(EXEMPT & set(gates)))



# ------------------------------------------------- R10 铁律编号必须严格递增

@rule("template-literal-backtick",
      "模板字面量不许被注释里的反引号提前闭合（node --check 不可依赖：残码合法时它放行）")
def r_tpl_backtick(root):
    """⚠️ 2026-09-04 立。这是同一个坑的**第七次**复发 ——
    而第七次就发生在我**写注释解释这个坑的那一行里**：

        //   `[data-demo-chrome]` 是给交互稿自己的评审外壳留的出口

    这行在一个模板字面量**内部**，第一个反引号直接把模板闭合，
    后面 `[data-demo-chrome]` 被当成 JS 求值 → 运行时 ReferenceError。

    ⛔ **`scripts-parse`（node --check）挡不住它**，而且是最坏的那种挡不住：
    **有时查得出，有时查不出** —— 取决于截断后的残码碰巧是不是合法语法。
    2026-09-04 实测两种形态：
      `[data-demo-chrome]`  → node --check **退出 0**（放行，运行时才 ReferenceError）
      `node --check`        → node --check 退出 1（抓到）
    ⭐⭐ 「有时能抓到」比「从来抓不到」更危险：它会制造虚假信心 ——
    你见过它抓到一次，就会以为它一直在守。
    ⭐⭐ 七次复发说明：**「我知道这条规则」对这类错误零防御力**，
    能挡住的只有一条机械判据。

    判据（低误报）：扫描出每个模板字面量，若它的**闭合反引号所在的那一行**，
    在该反引号之前的文本以 `//` 开头 —— 那必然是作者以为自己在写注释。
    （反引号出现在真注释里本身无害，所以不能一律报；关键在「它闭合了一个模板」。）
    """
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        src = io.open(f, encoding='utf-8').read()
        i, n, in_tpl, start = 0, len(src), False, 0
        while i < n:
            c = src[i]
            if not in_tpl:
                if c == '\\':
                    i += 2; continue
                if c == '/' and i + 1 < n and src[i+1] == '/':
                    j = src.find('\n', i); i = n if j < 0 else j + 1; continue
                if c == '/' and i + 1 < n and src[i+1] == '*':
                    j = src.find('*/', i); i = n if j < 0 else j + 2; continue
                if c in '"\'':
                    q = c; i += 1
                    while i < n and src[i] != q:
                        i += 2 if src[i] == '\\' else 1
                    i += 1; continue
                if c == '`':
                    in_tpl, start = True, i
                i += 1; continue
            # 模板内部
            if c == '\\':
                i += 2; continue
            if c == '$' and i + 1 < n and src[i+1] == '{':
                depth, i = 1, i + 2
                while i < n and depth:
                    if src[i] == '{': depth += 1
                    elif src[i] == '}': depth -= 1
                    i += 1
                continue
            if c == '`':
                ls = src.rfind('\n', 0, i) + 1
                line_head = src[ls:i]
                if line_head.lstrip().startswith('//'):
                    ln = src.count('\n', 0, i) + 1
                    bad.append("%s:%d 模板字面量被一行「注释」里的反引号提前闭合 —— "
                               "node --check 不可依赖（残码合法时它放行）"
                               % (os.path.relpath(f, root), ln))
                in_tpl = False
            i += 1
    return (not bad,
            bad if bad else "%d 个 .mjs 的模板字面量都没有被注释里的反引号截断"
            % len(glob.glob(os.path.join(root, 'scripts', '*.mjs'))))


# 门禁 ↔ 它自己的模板。左边是脚本，右边是「照它做出来的文档」。
# 第三列是「模板填好内容后」的夹具（tests/fixtures/filled/），门禁必须对它退出 0。
# 第四列是额外参数；`@` 开头的参数会被替换成 filled 目录下的另一份夹具。
# ⭐ 2026-09-04 扩面：从 5 对扩到 11 对。起因是「行内出现某个词就触发」这个形态
#   **一天里出现了三次**（G0 的「」· 元素表的「标识符」· G0.9 的「未解除」），
#   而三次都是**拿真实文档跑一遍**才发现的 —— 静态读代码看不出来。
#   ⛔ 按「同一个错误复发到第三次就别再加纪律，去加工具」：
#     最有效的工具不是再写一条静态判据，是**让更多门禁被真实文档撞一遍**。
GATE_TEMPLATE_PAIRS = (
    ("design-intent-gate.py", "design-brief.md", "design-brief.md", ()),
    ("definition-gate.py", "definition-final.md", "definition-final.md", ()),
    ("prd_completeness_check.py", "prd-complete.md", "PRD.md", ("--stage", "S4")),
    ("retro-gate.py", "retro.md", "retro.md", ()),
    ("element-identity-gate.py", "interaction-spec.md", "interaction-spec.md", ()),
    # 多输入的门禁：第二个输入用 `@名字` 指向 filled 目录下的另一份夹具
    ("chain-gate.py", None, "@G0.9", ("definition-final.md", "state.md")),
    ("chain-gate.py", None, "@G0.5", ("insights.md", "definition-final.md")),
    ("chain-gate.py", None, "@G0.8", ("definition-final.md", "PRD.md")),
    ("requirements-quality-gate.py", None, "PRD.md", ()),
    # ⚠️ coverage_check 对这份夹具的**正确**结论是 3（对账通过，但 3 条需求只被
    #    跳过的用例覆盖）—— 期望值写死 0 会逼人去删掉那三条诚实的 SKIPPED。
    #    ⭐ 「门禁必须绿」不等于「退出码必须是 0」：三态门的合法结论不止一个。
    ("coverage_check.py", None, "PRD.md", ("@cases",), 3),
    ("token-provenance-gate.py", None, "@skip", ()),   # 夹具需 tokens.json + 相对源文件，单列
    ("g75-freeze-gate.py", None, "triad-root", ()),    # 三件套夹具目录，本地六查须 0
    ("business-map-gate.py", None, "business-map.md", ()),
    ("intent-gate.py", None, "intent.md", ()),
    ("product-structure-gate.py", None, "product-structure.md", ()),
    ("s8-solution-gate.py", "s8-solution-plan.md", "s8-solution-plan.md", ()),
    ("s9-quality-report-gate.py", "s9-quality-report.md", "s9-quality-report.md", ()),
    ("s9-product-walkthrough-gate.py", "s9-product-walkthrough.md", "s9-product-walkthrough.md", ()),
    ("s9-dev-slice-gate.py", "s9-dev-slice.md", "s9-dev-slice.md", ()),
    ("s9-launch-rollback-gate.py", "s9-launch-rollback.md", "s9-launch-rollback.md", ()),
    # 🚨 2026-09-09（批 X）：spec-sync 此前不在本表，于是没人验它读不读得懂
    #   **SOP 自己规定的开发态**——目录版 proto。实跑当场 5 过 4 败（假阳性：
    #   四条判据只搜单文件，而内容分散在 js/*.js 里）。⭐ 「门禁 ↔ 模板」的配对
    #   不能只想到 md 模板：**产物形态（目录版/单文件）也是模板的一种**。
    #   `@proto` 特例：被测对象取 templates/proto/ 而不是 filled 夹具。
    ("spec-sync-gate.py", None, "@proto", ()),
)

# 显式豁免表 —— 与配对表互补，**合起来必须覆盖每一道门禁**（规则 gate-pairing-declared）。
# ⛔ 豁免不是「先欠着」，是「已经决定不配，理由在此」；空理由不算豁免。
GATE_PAIRING_EXEMPT = {
    'tech-research-gate.py':   '验报告实例结构（scope.md 声明的编号/图/摘录/口径），不读模板骨架——模板 2.N 为占位形态不可判；自证内建正例+三类反例夹具',
    'research-quality-gate.py': '跨报告/图片/平台回执/三角色评审做版本对账；模板 research-quality-review.md，自证与 test-remediation-contracts.py 覆盖空评审和版本失效',
    'audience-gate.py':        '吃**任意交付文档**（竞品分析/PRD/设计稿/交互稿），不绑单一模板；'
                               '口径来自 spec/_audience.json，自证内建 8 个夹具（含「内部路径写在附件里→放行」正例）',
    'coordination-gate.py':    '读 git 状态与路径清单做协同检查，不读任何项目模板；自证内建清单夹具',
    'diagram-id-gate.py':      '跨 PRD 多节 + 图源目录做集合对账，不绑单一模板；自证内建完整 PRD 夹具',
    'no-loss-gate.py':         '元门禁：判 skill 自身的语义单元有没有丢，不读任何项目模板',
    # 吃 HTML/浏览器产物，没有 md 模板可配；行为验证由它们自己的 --self-test 承担
    'browser-audit.mjs':       '吃真实浏览器渲染，无 md 模板；自证内建 fixture 页面',
    'dead-click-gate.mjs':     '吃真实浏览器渲染，无 md 模板；自证内建 fixture 页面',
    'flow-walk-gate.mjs':      '吃真实浏览器渲染，无 md 模板；自证内建 fixture 页面',
    'scenario-matrix-gate.mjs': '吃真实浏览器渲染，无 md 模板；自证内建 fixture 页面',
    'platform-parity-gate.mjs': '吃真实浏览器渲染，无 md 模板；自证内建 fixture 页面',
    'mock-seam-gate.mjs':      '吃骨架源码目录而非模板；自证内建最小四层原型',
    'demo-anchor-gate.py':     '吃 demo.html / anchors.json，无 md 模板；已用 demo-scaffold 实跑核过',
    'ai-slop-gate.py':         '吃 HTML/CSS 产物，无 md 模板；已用 templates/proto 实跑核过',
    'visual-spec-gate.py':     '吃 HTML/CSS 产物，无 md 模板；已用 templates/design-md.md 实跑核过',
    'interaction-gate.py':     '吃 HTML 产物，无 md 模板；已用 templates/interaction-spec.md 实跑核过',
    'figma-editability-gate.py': '吃 Figma 原生结构回读结果，本地无夹具（需真 Figma 文件）',
    'reconcile-gate.py':       '多输入跨产物对账，输入组合由 G1/G2/G3 子门各自决定；'
                               '子门已在 chain-gate 系列与 g75 的落盘记录里被消费',
    'token-provenance-gate.py': '夹具需 tokens.json + 相对源文件成对存在，配对表里以 @skip 单列；'
                                'gate-reads-template 不验它，靠自身 --self-test 覆盖',
    'research-gate.py':        '吃 research/ 目录（多文件），非单一 md 模板；'
                               '2026-09-09 已人工拿 templates/ 实跑并修掉禁令句假阳性',
    # ===== 2026-09-20 补登记：S2 竞品调研 + spec 作者侧五道门。共性=不绑单一 md 模板，
    #        行为由各自内建 --self-test 承担（不是「先欠着」，是已决定不配、理由在此）。=====
    'traversal-coverage-gate.py': '吃 deep-tree.json + 报告 md 做覆盖对账，非单一模板；'
                                  '自证 tests/traversal-coverage/fixtures 五例（绿/红/UNABLE/未披露红/披露绿）',
    'cdp-reuse-gate.py':       '吃遍历器源码 + competitive-research.md 查 CDP 落地坑复用，无 md 产物模板；自证内建',
    'report-structure-gate.py': '吃竞品调研报告 md（交付文档非固定模板），与 audience-gate 配用同守报告；自证内建',
    'feishu-delivery-gate.py': '吃本地报告、飞书 XML 回读与证据清单做跨载体守恒，不绑单一模板；自证内建',
    'dingtalk-delivery-gate.py': '吃本地报告、钉钉回读与证据清单做跨载体守恒，不绑单一模板；自证内建',
    'serial-orchestration-gate.py': '吃编排器 competitor-sweep.mjs 源码查「串行无并发旋钮」，无 md 模板；自证内建',
    'spec-authoring-gate.py':  '吃 spec/*.json + scaffold/converge 数结构红棘轮，无 md 产物模板；自证内建',
}
# 「定位器失败」的措辞 —— 门禁**找不到**模板产出的结构时会说的话。
# ⚠️ 与「占位符失败」要分开：模板里全是占位符，因此报「只有表头/仍是 <占位>」
#    是**正确行为**，不该被这条规则判红。
LOCATOR_FAIL = re.compile(
    r'整节缺失|解析不出|解析不到|读不到|读不出|找不到.{0,6}表|没有.{0,4}这张表|不是合法 JSON')


@rule("exit-semantics-declared",
      "每道门禁的退出码语义必须在 gate-run.py 里登记（**退出码语义并不统一**）")
def r_exit_semantics(root):
    """⚠️⚠️ 2026-09-04 普查 22 道门发现：**退出码语义在门禁之间并不一致**。

      20 道：0=通过  1=不通过  2=跑不了
      `prd_completeness_check.py`：0=达标  **2=有缺口**  **3=输入无效**
      `coverage_check.py`：0=通过  1=有漏  2=输入无效  **3=对账通过但有缺口**

    ⛔ 任何按「2 就是跑不了」写的自动化，都会把 `prd_completeness` 的**真失败**
    标成「跑不了」—— 而「跑不了」正是最容易被耸肩带过的那一档。
    ⭐⭐ **把 FAIL 伪装成 UNABLE 是最坏的一种误标**（我今天自己就对 G2 干过一次：
    它的 AC 集合恒空时，「UNABLE」与「通过」在我眼里没有区别）。

    这条规则守的是：**新增门禁没登记语义 → 元门禁红**，不许靠默认值猜。
    ⭐ 它与 `gate-wired` 是一对：那条查「有没有人调用它」，这条查「调用它的人
      能不能正确读懂它的结论」。
    """
    import importlib.util
    gr = os.path.join(root, 'scripts', 'gate-run.py')
    if not os.path.exists(gr):
        return None, "gate-run.py 不存在（结果落盘尚未启用）"
    spec = importlib.util.spec_from_file_location("_gr", gr)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, ["gate-run.py 载入失败：%s" % e]
    declared = set(getattr(m, 'EXIT_SEMANTICS', {}))
    external = set(getattr(m, 'EXTERNAL_GATES', {}))
    gates = {os.path.basename(x) for x in gate_files(root)} - {'consistency-gate.py'}
    miss = sorted(gates - declared)
    # 外部挂接（EXTERNAL_GATES 单源登记，如 coding-standards 的 selfcheck.sh）不在本地 scripts/，
    # 不算「登记了不存在的门禁」；但外部键必须真在 EXTERNAL_GATES 里声明过，不许口头外部。
    extra = sorted(declared - gates - {'consistency-gate.py'} - external)
    orphan_ext = sorted(external - declared)
    if orphan_ext:
        extra += ['EXTERNAL_GATES 声明了 %s 却没登记退出码语义' % g for g in orphan_ext]
    bad = ["门禁 %s 没在 gate-run.py 的 EXIT_SEMANTICS 里登记退出码语义 —— "
           "落盘时会被标成 UNKNOWN" % g for g in miss]
    bad += ["EXIT_SEMANTICS 里登记了不存在的门禁 %s（改名或删除后没跟）" % g for g in extra]
    return (not bad), bad or "%d 道门禁的退出码语义都已登记" % len(gates)


@rule("gate-reads-template",
      "**配对表登记的每对**「门禁↔模板」必须读得通（可以因占位符而红，不许因「找不到」而红）"
      "；未配对的门由 gate-pairing-declared 要求显式豁免")
def r_gate_template(root):
    """⚠️⚠️ 2026-09-04 全链实跑立的：一次跑完当时的 S1→S9，**12 处缺陷里 11 处同型** ——
    门禁与它自己的模板对不上。照着官方模板认真填的人，会在门上撞得莫名其妙：

      · `definition-gate` 找 `### 不服务谁` 小节，而模板写成**表行** → 报「整节缺失」
      · `prd_completeness_check` 认 `| ID | 功能名称 |`，而 S3 模板给的是 `| ID | 功能 |`
        → 报「ERR 解析不出功能清单表」，整道门什么都没查
      · `element-identity-gate` 被模板里另一张表的**数据行**误触发 → 报出 `igma` 这种
        **文档里根本不存在**的字符串
      · `design-intent-gate` 要求同一行，而模板的内容在**下一行** → 模板自己永远过不了

    ⭐ 判据的关键在**区分两种红**：
      模板里全是占位符 → 报「只有表头 / 仍是 <占位>」是**正确行为**；
      而「整节缺失 / 解析不出 / 读不到」说明**定位器根本没找到那个结构** —— 那是缺陷。
    ⭐⭐ 这条规则替代了一次性的人工审计。一次性审计的问题不是不准，
      是**它需要人记得重跑**，而下一个新门禁不会提醒任何人。
    """
    import subprocess
    bad, checked = [], 0
    FDIR = os.path.join(root, 'tests', 'fixtures', 'filled')
    for _pair in GATE_TEMPLATE_PAIRS:
        gate, tpl, filled, extra = _pair[:4]
        want_rc = _pair[4] if len(_pair) > 4 else 0
        # 🚨 2026-09-09 三轮复核（B3）：`want_rc` 此前**没有任何守卫** —— 把它填成 2
        #   就等于把「跑不了/UNABLE」登记成「读得通」，规则照样全绿。
        #   ⭐ 隔壁 exit-semantics-declared 的 docstring 正写着「**把 FAIL 伪装成
        #   UNABLE 是最坏的一种误标**」，而配对表允许反过来做同一件事。
        #   ⇒ 只允许 0（通过）与 3（coverage_check 的「对账通过但有缺口」，已在案）。
        if want_rc not in (0, 3):
            bad.append("%s 的配对期望退出码是 %d —— ⛔ 2 是 UNABLE（跑不了），"
                       "把它登记成「读得通」等于用没验过冒充验过" % (gate, want_rc))
            continue
        gp = os.path.join(root, 'scripts', gate)
        if not os.path.exists(gp) or filled == '@skip':
            continue
        tp = os.path.join(root, 'templates', tpl) if tpl else None
        # `@proto` 形态：被测对象是 SOP 规定的**开发态目录版原型**，不是 filled 夹具。
        if filled == '@proto':
            _pr = os.path.join(root, 'templates', 'proto')
            if not os.path.isdir(_pr):
                continue
            fp, extra = os.path.join(root, 'templates', 'spec'), [
                os.path.join(_pr, 'index.html'), '--js', os.path.join(_pr, 'js')]
            tp = None
        # `@Gx.y` 形态：门禁名后跟一个子命令，其余参数都是 filled 里的夹具
        elif filled.startswith('@'):
            argv = [filled[1:]] + [os.path.join(FDIR, x) for x in extra]
            fp, extra = None, argv
        else:
            fp = os.path.join(FDIR, filled)
            extra = [os.path.join(FDIR, x[1:]) if x.startswith('@') else x for x in extra]
        checked += 1
        # ① 承重的那一半：**填对了就必须绿**。
        if fp is not None and not os.path.exists(fp):
            bad.append("%s 没有「填好内容」的夹具 tests/fixtures/filled/%s —— "
                       "没有夹具就没人守「照模板填对了能不能过」" % (gate, filled))
        else:
            try:
                argv = ['python3', gp] + ([fp] if fp else []) + list(extra)
                r = subprocess.run(argv, capture_output=True, text=True, timeout=180)
                if r.returncode != want_rc:
                    head = next((l.strip() for l in
                                 ((r.stdout or '') + (r.stderr or '')).splitlines()
                                 if '❌' in l or 'ERR' in l or 'UNABLE' in l), '')
                    bad.append("%s 对**填好的**夹具报了 %d（期望 %d）：%s"
                               % (gate, r.returncode, want_rc, head[:110]))
            except Exception as e:
                bad.append("%s 跑不起来：%s" % (gate, e))
        # ② 辅助信号：在空模板上不许出现「定位器失败」措辞（占位符失败是正确行为）
        # 🚨 2026-09-09 三轮复核（B2）：配对项指向**不存在的模板**时这里静默跳过 ——
        #   不计数、不报警，两条规则全绿。豁免表有 ghost 检查，配对表**没有**，
        #   两张互补的表判据不对称。⇒ 声明了模板就必须存在。
        if tp and not os.path.exists(tp):
            bad.append("%s 配对的模板不存在：templates/%s —— 声明了却没有＝这一对从没被验过"
                       % (gate, tpl))
        if tp and os.path.exists(tp):
            try:
                r2 = subprocess.run(['python3', gp, tp] + list(extra),
                                    capture_output=True, text=True, timeout=180)
                out = (r2.stdout or '') + (r2.stderr or '')
                m = LOCATOR_FAIL.search(out)
                if m:
                    line = next((l.strip() for l in out.splitlines() if m.group(0) in l), m.group(0))
                    bad.append("%s 读不懂 templates/%s：%s" % (gate, tpl, line[:110]))
            except Exception:
                pass
    if not checked:
        return None, "没有可核的「门禁 ↔ 模板」配对"
    return (not bad), bad or ("%d 对「门禁 ↔ 模板」：填好的夹具全部通过，"
                              "空模板上也没有定位器失败" % checked)


@rule("coding-standards-linked",
      "S8/S9 必须指向编码规范正本并声明项目规范优先（否则兜底短表会事实上变成标准）")
def r_cs_link(root):
    """⚠️ 2026-09-05 立。实测：product-flow 全仓**一次都没提过 `coding-standards`** ——
    照本流程走的人不会被指到编码规范正本，
    而 `references/s9-quality-gates.md` 里的「最小基线」会**事实上变成标准**。

    ⭐ 这不是「少了个链接」，是**同一概念两处各写一份**：
      正本 120+ 条五层规范 vs 流程内嵌 10 行短表。
      两处必然分叉，**而分叉那天两边都还是绿的**
      （本 skill 在自己身上撞过：`gate-count` 数 20、`gate-wired` 数 21）。
    ⇒ 判据不只是「提到了」，还要**写明冲突时以谁为准** —— 否则链接只是礼貌，不是契约。

    由 peer 会话 `编程规范skill` 核出并提出，本会话独立复核（`grep -rc` 全仓 0 次）后补上。
    对方在 engineering-standards 一侧加了对称的门（[10l]）。
    """
    sk = read(os.path.join(root, 'SKILL.md'))
    q = read(os.path.join(root, 'references', 's9-quality-gates.md'))
    if sk is None or q is None:
        return None, "读不到 SKILL.md 或 s9-quality-gates.md"
    bad = []
    if 'coding-standards' not in sk:
        bad.append("SKILL.md 没有指向 `coding-standards` —— "
                   "照流程走的人不会被指到编码规范正本")
    if 'coding-standards' not in q:
        bad.append("references/s9-quality-gates.md 没有指向 `coding-standards` —— "
                   "它那份「最小基线」会事实上变成标准")
    elif not re.search(r'项目明确规范\s*>\s*`?coding-standards`?', q):
        bad.append("references/s9-quality-gates.md 提到了 `coding-standards`，"
                   "但**没写明项目规范优先** —— 只提不定权，两份规范照样会分叉")
    return (not bad), bad or "S8/S9 均指向编码规范正本，且写明项目规范优先与证据边界"


@rule("reference-reachable", "每个 references/*.md 都必须在 SKILL.md 里有入口（没入口＝没人会读到它）")
def r_ref_reach(root):
    """⚠️ 2026-09-05 立。实测抓到一个孤儿：`keyboard-contracts.md`（117 行，
    逐控件键盘契约，取自 W3C APG）—— **SKILL.md 从没提过它**，
    照流程走的人永远读不到。

    ⭐ 这是「规则存在 ≠ 规则在守」用在**文档**上的形态：
      与 `gate-wired`（门禁写了但不在链路上）完全同源 ——
      **写了、内容是对的、就是没人被告知去读它。**
    ⚠️ 反过来也查：SKILL.md 引用的 references 必须真的存在
      （那一半已由 `flag-exists` / 路径引用扫描覆盖，这里只补孤儿方向）。
    """
    refs = sorted(os.path.basename(x) for x in glob.glob(os.path.join(root, 'references', '*.md')))
    if not refs:
        return None, "没有 references/ 目录"
    sk = read(os.path.join(root, 'SKILL.md'))
    if sk is None:
        return None, "读不到 SKILL.md"
    orphan = [r for r in refs if r not in sk]
    return (not orphan), (["references/%s 在 SKILL.md 里没有任何入口 —— "
                           "照 SKILL.md 走的人永远读不到它" % o for o in orphan]
                          or "%d 个 reference 都在 SKILL.md 里有入口" % len(refs))


# 跨阶段基础设施参考:不归任何单一阶段(SKILL 的机制/铁律/PRD 结构/复盘等节的正文,
# 或渐进式披露外移的正文),显式登记归属+理由。⛔ 空理由不算;新参考要么被某阶段路由、要么进这里。
MODULE_INFRA_REFS = {
    'delivery-quality-contract.md': 'S2–S9 正文、真实图片、平台回读、图位与审批版本的跨阶段交付契约',
    'iron-rules.md':         '铁律正文(SKILL `## 铁律` 节迁出),贯穿全阶段',
    'mechanisms.md':         'M1–M9 贯穿机制正文,跨全阶段',
    'prd-structure.md':      'PRD 结构正文(SKILL `## PRD 结构` 节迁出),S4/S5 共用',
    's7-figma.md':           'S7 Figma 正文(SKILL `## S7` 节迁出)',
    's10-retro-in-skill.md': 'S10 复盘正文(SKILL `## S10` 节迁出)',
    'stage-playbook.md':     '一页纸操作规程详表(SKILL SOP 段渐进披露外移)',
    'tool-mapping.md':       '工具映射与降级(SKILL 末段渐进披露外移),分发适配',
    'flow-metrics.md':       '流程效率账(S10 复盘参考,只进复盘不做门禁)',
}


@rule("module-ownership", "每份参考要么被某阶段路由(有模块归属),要么登记为跨阶段基础设施——没有无主参考")
def r_module_ownership(root):
    """治「改一处影响面不明」:`reference-reachable` 只保证参考在 SKILL 有入口,保证不了它
    **归哪个模块**。本条要求每份参考有明确归属——被 `## 各阶段执行` 路由表的某阶段行引用,
    或在 `MODULE_INFRA_REFS` 登记为跨阶段基础设施(带理由)。
    ⇒ 改某参考的影响面 = 它的 owner 阶段 + 依赖该阶段的下游(registry DAG),可机器界定;
      无主参考 = 改它会波及哪里没人说得清。这是解耦从「文档」变「机器强制」的那道门(见 architecture.md)。
    """
    import glob as _g
    sk = read(os.path.join(root, 'SKILL.md'))
    if sk is None:
        return None, "读不到 SKILL.md"
    try:
        rest = sk[sk.index('\n## 各阶段执行') + 1:]
    except ValueError:
        return None, "SKILL.md 里没有 `## 各阶段执行` 路由表 —— 无法判定参考归属"
    nxt = rest.find('\n## ')
    ax = rest[:nxt] if nxt >= 0 else rest         # 只看 各阶段执行 这一节(路由表)
    routed = set(re.findall(r'([\w.-]+\.md)', ax))
    refs = sorted(os.path.basename(x) for x in _g.glob(os.path.join(root, 'references', '*.md')))
    if not refs:
        return None, "没有 references/ 目录"
    orphan = [r for r in refs if r not in routed and r not in MODULE_INFRA_REFS]
    ghost = sorted(set(MODULE_INFRA_REFS) - set(refs))
    noreason = sorted(k for k, v in MODULE_INFRA_REFS.items() if len(v.strip()) < 6)
    bad = []
    if orphan:
        bad.append("这些参考没有模块归属(既没被阶段路由、也没登记 INFRA)——改它影响面不明:"
                   + "、".join(orphan))
    if ghost:
        bad.append("MODULE_INFRA_REFS 登记了磁盘上不存在的参考(改名/删除没跟):" + "、".join(ghost))
    if noreason:
        bad.append("INFRA 登记没写理由:" + "、".join(noreason))
    return (not bad), ("；".join(bad) if bad else
                       "%d 份参考全部有模块归属(阶段路由 %d · 跨阶段基础设施 %d)"
                       % (len(refs), len(refs) - len([r for r in refs if r in MODULE_INFRA_REFS]),
                          len([r for r in refs if r in MODULE_INFRA_REFS])))


# track → 该轨的产物温度(纪律后果)。⛔ 两者必须一致,否则一个模块"说自己是文档轨却按工程轨留存"就自相矛盾。
_TRACK_TEMPERATURE = {'doc': 'anchored', 'design': 'anchored', 'eng': 'source', 'seam': 'gate'}


@rule("track-temperature-declared", "每个阶段模块声明 track(doc/design/eng/seam)与 temperature,且两者一致")
def r_track_temperature(root):
    """把用户点的『竞品调研/PRD 是文档形态、技术/研发/算法/测试是软件工程形态』
    从隐性变**显式 + 机器强制**(见 architecture.md「双轨制」):
      · doc/design 轨 → 交付件是**锚定真源** anchored(不可当可丢弃派生物;变更走 delta+归档)
      · eng 轨 → **spec 即源、代码是投影** source(spec 变=重生成/对齐;走 /converge 读真码)
      · seam(G7.5)→ 冻结决策 gate(文档轨真源锁定→工程轨据此展开)
    无 track 的新模块 = 没人知道它该按哪套纪律走。track↔temperature 必须一致,防"说文档轨却按工程轨"。
    """
    import json as _json
    rp = os.path.join(root, 'references', 'workflow-registry.json')
    if not os.path.exists(rp):
        return None, "没有 workflow-registry.json(结构口径尚未启用)"
    try:
        mods = _json.load(io.open(rp, encoding='utf-8')).get('modules', {})
    except Exception as e:
        return False, "workflow-registry.json 读不了:%s" % e
    if not mods:
        return None, "registry 无 modules"
    bad = []
    for k, m in mods.items():
        tr, tp = m.get('track'), m.get('temperature')
        if tr not in _TRACK_TEMPERATURE:
            bad.append("%s 的 track 缺失或非法(应 doc/design/eng/seam):%r" % (k, tr))
        elif tp != _TRACK_TEMPERATURE[tr]:
            bad.append("%s track=%s 应配 temperature=%s,实为 %r" % (k, tr, _TRACK_TEMPERATURE[tr], tp))
    return (not bad), (bad[:8] if bad else
                       "%d 个模块 track/temperature 齐且一致(doc/design=anchored · eng=source · seam=gate)"
                       % len(mods))


@rule("gate-record-fields",
      "读 gate 落盘记录的地方，字段名必须与 gate-run.py 真实写入的一致（读错字段＝判据永远看不见真记录）")
def r_gate_record_fields(root):
    """🚨 2026-09-09 自查抓到的真缺陷，做成守卫防复发：
    我新写的 `claim-ladder-backed` 读 `pass` 字段，而 `gate-run.py` 真实写的是
    `verdict`/`exitCode`/`ranAt` —— **那个字段根本不存在于真实记录里**。后果两头都坏：
    真实的通过记录认不出来（该绿不绿），手写一个 `{"pass": true}` 直接过关（该红不红）。

    ⭐ 这是本轮反复出现那个形状的又一副面孔：**判据与真实产物对不上**
    （此前是表格列数、段落形态、文件形态，这次是字段名）。自造夹具永远发现不了它 ——
    因为夹具是照着判据写的，不是照着生产者真实写出来的格式。

    判据：从 `gate-run.py` 抽出它写入记录时用的键，任何消费方 `.get('X')` 取的 X
    若不在这个集合里（且看起来是在读 gate 记录），即报。
    ⛔ 只覆盖「读 gate 落盘」这一类，不声称能查所有 JSON 字段。
    """
    import re as _re
    gr = read(os.path.join(root, 'scripts', 'gate-run.py'))
    if gr is None:
        return None, "读不到 gate-run.py（无从得知真实字段）"
    # gate-run 写记录时的键：从它构造 rec/json.dump 的字面量里取
    written = set(_re.findall(r"'(\w+)':\s", gr))
    if 'verdict' not in written:
        return None, "从 gate-run.py 里解析不出写入字段（判据失去锚点）"
    bad = []
    # 🚨 2026-09-09 第五轮独立复核：通过时的证据串写的是 `"%d …" % 3` ——
    #   **3 是字面量，与实际扫到几个消费方无关**（实测全仓只有 1 行满足匹配条件）。
    #   ⭐ 在一个母题是「假数据比缺数据更糟」的仓里，元门禁自己在报假数字。
    #   ⇒ 真数一遍；并且**一个消费方都没扫到时不许说「都一致」**：
    #     那是「没东西可比」，属 UNABLE，不是通过（本仓 P6）。
    # 🚨 量程第二次订正（同一批内）：把「同一行必须含 gates/RESULT_DIR」当上下文
    #   **太窄了** —— 真实消费方（claim-ladder 读 `_r.get('verdict')`）那几行
    #   一个字都不含。⭐ 上一版因此只匹配到 1 行、去掉字符串字面量后是 0 行，
    #     却一直打印「3 个消费方都一致」—— **量程窄到 0，结论仍报通过**。
    #   ⇒ 上下文改**文件级**（这个文件读不读 gate 记录），字段改**记录字段名域**
    #     （只对像记录字段的键较真，免得把无关 dict 的 .get 也拖进来）。
    # ⚠️ 2026-09-09：量程放开后**当场把变异靶判成真违例** ——
    #   `MUTATIONS` 表里那条 `.get('verdict') → .get('passed')` 是**故意造的违例**，
    #   用来证明本规则会红。⭐ `no-positional-window` 早有跳过靶区的状态机，
    #     这条没有 —— **同一形状在同一个文件里第二次**（一处修完不查同类）。
    #   ⇒ 跳过 `MUTATIONS = [` 与 `def self_test` 这两类块内的行。

    _RECORD_KEYS = {'verdict', 'exitCode', 'ranAt', 'gate', 'stdout', 'stderr',
                    'pass', 'ok', 'status', 'result', 'code', 'runId',
                    'invocationId', 'inputHash', 'passed', 'success'}
    seen = 0
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        if os.path.basename(f) == 'gate-run.py':
            continue
        src = read(f) or ''
        if not _re.search(r'\.product-flow|RESULT_DIR|[\'"]gates[\'"]|gates\b', src):
            continue                       # 这个文件根本不读 gate 记录
        _skip = fixture_lines(src)
        for ln, line in enumerate(src.split('\n'), 1):
            if ln in _skip:
                continue                   # 变异靶/自证夹具里的违例是故意的
            # ⚠️ 2026-09-09：**本条改完当场误伤了它自己** —— 我新写的那句 UNABLE 提示语
            #   里含 `.get('字段')`，被当成真代码判红。⭐ 注释与提示串里写形状是在讲清楚，
            #   不是在用它；判据必须只看**代码**。（同一天在 no-positional-window 上
            #   修的是同一个形状 —— 一处修完不查同类，下一处照犯。）
            _code = _re.sub(r'#.*$', '', line) if not line.lstrip().startswith('#') else ''
            # ⚠️ 显式豁免：有些 `.get('status')` 读的**不是 gate-run 的记录**
            #   （如本文件 run_silent 解析的是元门禁自己的 --json 输出）。
            #   ⭐ 按本仓惯例用**可审计的行内标记**登记，而不是让规则静默跳过某些文件 ——
            #     沉默的豁免下次没人知道它存在。
            if '# 非门禁记录' in line:
                continue
            for k in _re.findall(r"\.get\('(\w+)'\)", _code):
                if k not in _RECORD_KEYS:
                    continue               # 不是记录字段名，多半是别的 dict
                seen += 1
                if k not in written:
                    bad.append("%s:%d 读 gate 记录的 '%s'，而 gate-run 从不写这个字段"
                               % (os.path.basename(f), ln, k))
    if bad:
        return False, bad[:5]
    if seen == 0:
        return None, ("没扫到任何读 gate 记录的消费方 —— **本条没验**（不是通过）。"
                      "判据只认 `.get('字段')` 且同行含 gates/RESULT_DIR 的写法，"
                      "消费方换个写法就落在量程外。")
    return True, "%d 处消费方读取的字段名都与 gate-run 实际写入一致" % seen


@rule("gate-pairing-declared",
      "每道门禁要么在配对表里、要么在豁免表里写明理由（⛔ 沉默地不配对＝没人验它读不读得懂模板）")
def r_gate_pairing(root):
    """🚨 2026-09-09（独立复核揪出）：`gate-reads-template` 标题写「**每道**门禁」，
    实现却是**手维护的配对表**——26 道门里只配了 14 道，而且**没有任何东西
    强制新门进表**。于是下一道新门同样不会有人被提醒。

    ⭐ 实证代价：`research-gate` 就在未配对的那 12 道里，它「把模板中『这些词一律
      禁止』的禁令句判成编造」这个假阳性，是 2026-09-09 **靠人工**拿模板实跑才发现的。
      配对表覆盖不到的地方，只能靠有人恰好想起来去试。

    判据：门禁 ∈ 配对表 ∪ 豁免表。豁免必须写理由（多为「吃 HTML/浏览器，无 md 模板」
    或「归并行会话车道」），⛔ 不许空豁免。
    ⚠️ 本规则**不要求**立刻把 12 道都配上——那会逼人造假夹具；它要求的是
      **每一道都被显式决定过**：配了，或者说清为什么不配。沉默才是缺陷。
    """
    import re as _re
    src = read(os.path.join(root, 'scripts', 'consistency-gate.py')) or ''
    m = _re.search(r'GATE_TEMPLATE_PAIRS = \((.*?)\n\)', src, _re.S)
    if not m:
        return None, "找不到 GATE_TEMPLATE_PAIRS"
    # 🚨 2026-09-09 二轮独立复核揪出的**旁路**：`@skip` 条目被 gate-reads-template
    #   直接跳过（不验），却仍被本规则算成「已配对」⇒ 把一道门写成 `@skip` 就能
    #   同时躲开验证与豁免理由，而规则**照常报绿、配对数还会变大**。
    #   实证：复核者把 research-gate 从豁免表挪成 `@skip`，规则保持绿、数字从 14→15。
    #   ⇒ `@skip` 不算配对，按「未验证」并入豁免侧，一样要求写明理由。
    _all_pairs = _re.findall(r'\("([\w.-]+\.(?:py|mjs))",\s*[^,]+,\s*"([^"]*)"', m.group(1))
    paired = {g for g, f in _all_pairs if f != '@skip'}
    skipped = {g for g, f in _all_pairs if f == '@skip'}
    me = _re.search(r'GATE_PAIRING_EXEMPT = \{(.*?)\n\}', src, _re.S)
    exempt = dict(_re.findall(r"'([\w.-]+)':\s*'([^']*)'", me.group(1))) if me else {}
    gates = {os.path.basename(g) for g in gate_files(root)}
    # `@skip` 的门必须在豁免表里写明理由 —— 它没被验证，和没配对是同一件事
    unlisted = sorted(gates - paired - set(exempt) - {'consistency-gate.py'})
    skip_noreason = sorted(skipped & gates - set(exempt))
    noreason = sorted(k for k, v in exempt.items() if len(v.strip()) < 6)
    ghost = sorted(set(exempt) - gates)
    bad = []
    if unlisted:
        bad.append("这些门禁既没配对也没豁免（没人验它读不读得懂自己的模板）：%s"
                   % "、".join(unlisted[:6]))
    if skip_noreason:
        bad.append("这些门禁写成 @skip（gate-reads-template 不验它）却没在豁免表里写理由：%s"
                   % "、".join(skip_noreason[:6]))
    if noreason:
        bad.append("豁免没写理由：%s" % "、".join(noreason))
    if ghost:
        bad.append("豁免表里有磁盘上不存在的门禁：%s" % "、".join(ghost))
    return (not bad), bad or ("%d 道门禁：配对 %d · 显式豁免 %d（都被决定过）"
                              % (len(gates) - 1, len(paired & gates), len(exempt)))


@rule("no-positional-window", "判据不许用固定字符窗口或未锚定行首的段分隔符（两个方向都是假绿）")
def r_no_window(root):
    """🚨 2026-09-09 立，起因是一次自查在**五处**抓到同一形状（批 O/P/Q/R）：

      · `md[i:i+1200]` 固定字符窗口 —— 窗口大就**吃进下一节**（拿别人的行给本节背书），
        窗口小就让段内超出部分**静默逃检**。实测：把非法状态放在第 1200 字符之后，
        门报「五判据全过」；business-map 更狠，**官方夹具两节间距只有 151 字符**，
        它从上线起就在跨节判。
      · 未锚定行首的 `find('## ')` —— 正文合法写「文档里用 ## 表示二级标题」即提前截断，
        **同一份产物上同时制造假阳性与漏报，点名的是无辜者**。

    ⭐ 为什么值得立成元规则：这类错**不会抛异常、不会报错**，只会让判据判到一段
      不该判的文本；而正例通常恰好落在窗口内 ⇒ 自证全绿。修实例不修形状，
      换个文件必然复发（同一文件上面刚修过，下面几行就漏了 —— 实证）。

    量程：scripts/ 下所有 .py **与 .mjs**。⛔ 白名单只给「显示截断」（`[:16]` 这类
    给人看的省略），判据用的位置切分一律要求锚定结构边界（`\\n## ` / 同级标题 / 下一条同类记录）。
    ⚠️ 2026-09-09 独立复核指出：首版只扫 .py，而本仓 `gate_files()` 的注释恰恰写着
    「门禁是不是门禁跟它用什么语言写无关」—— **新规则把这条教训又按语言切了一刀**。
    已扩到 .mjs（扫时当前无活违例，属堵潜在缺口）。
    """
    import re as _re
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))
                    + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        src = read(f)
        if src is None:
            continue
        # ⚠️ 2026-09-09 二轮复核：此前按文件名硬白名单 consistency-gate.py ——
        #   而它需要豁免的真正原因是「形状写在 docstring/注释里」，那是**所有**门禁
        #   都会有的情况。⭐ 按文件名开后门 = 规则对自己失效。⇒ 白名单撤掉，
        #   改为统一跳过注释与三引号串（下面），本文件与别的门走同一条路径。
        # ⚠️ 只查**判据代码**，不查自证段：自证里 `GOOD.index('## 三个方向表')` 这类
        #   是在**构造夹具字符串**（对着自己写的常量切，位置确定），不是在解析产物。
        #   第一版没排除它，当场误伤两处 —— 门不许惩罚正确用法。
        # ⚠️ 2026-09-09：`MUTATIONS` 表里的字面量**是故意造出来的违例靶**（用来证明
        #   本规则会红），不是判据在用这个形状 —— 与自证段同理，一并排除。
        #   ⭐ 否则「给规则加一发变异」这个动作本身会让规则红，逼人删掉自己的守卫。
        # 🚨🚨 2026-09-09 第三轮独立复核揪出：**本规则自己就是它禁止的那个形状** ——
        #   `src[:min(_cuts)]` 是一个未锚定结构、按位置切掉文件整个尾巴的窗口。
        #   实测代价：**28.1% 的门禁代码从来没被这条规则扫过**，而结论文案写「无固定
        #   字符窗口」；排除段里今天就住着一条**活的判据函数**（r_oversize 定义在
        #   MUTATIONS 之后）；把违例写在第一个标记之后即完全隐身。
        #   ⭐ 「规则作用于产物，但决定作用范围的那段代码不受任何规则约束」。
        #   ⇒ 改**逐行状态机**：只跳过「自证/变异靶」这两类**具名函数或赋值块**的行，
        #     不再一刀切掉文件尾巴；文件的其余部分**全部照扫**。
        _skip_starts = ('def self_test', 'def _self_test', 'def self_check',
                        'def project_self_test', 'SELF_TEST', 'MUTATIONS = [',
                        'PROBES = [', 'async function selfTest', 'function selfTest')
        _in_skip, _skip_indent = False, 0
        _kept = []
        for _l in src.split('\n'):
            _st = _l.lstrip()
            _ind = len(_l) - len(_st)
            if _in_skip:
                # 顶格的新定义 ⇒ 跳过段结束（空行与缩进行仍属于它）
                if _st and _ind <= _skip_indent and not _st.startswith((')', ']', '}')):
                    _in_skip = False
                else:
                    _kept.append('')          # 占位保持行号
                    continue
            if any(_st.startswith(p) for p in _skip_starts):
                _in_skip, _skip_indent = True, _ind
                _kept.append('')
                continue
            _kept.append(_l)
        src = '\n'.join(_kept)
        # 🚨 2026-09-09 **自攻**：逐物理行扫描看不到跨行表达式
        #   （`md[\n    i:i + 1200\n]` 拆三行后每行都不匹配）。
        #   ⚠️ 但第一版修法（把括号未闭合的行整体拼成逻辑行）**引入了更糟的假阳性**：
        #   相邻两个 print 被拼成一行后，`%d` 与 `≥` 凑出「数字窗口」形状，
        #   在一份完全正确的文件上报红。⭐ **修漏检不许换来误伤** —— 回退，
        #   改成只对**以 `[` 结尾**（明显未写完的切片）的行做一次窄拼接。
        _phys = src.split('\n')
        _logical = []
        _i = 0
        while _i < len(_phys):
            _l = _phys[_i]
            if _re.search(r'\[\s*$', _re.sub(r'#.*$', '', _l)) and _i + 2 < len(_phys):
                _logical.append((_i + 1, _l.rstrip() + _phys[_i + 1].strip()
                                 + _phys[_i + 2].strip()))
                _i += 3
                continue
            _logical.append((_i + 1, _l))
            _i += 1
        in_doc = False
        for ln, line in _logical:
            if line.lstrip().startswith('#') or line.lstrip().startswith('//'):
                continue      # 注释里写形状是为了讲教训，不是在用它（含 JS 的 //）
            # 🚨 2026-09-09 二轮复核：只跳过 `#` 开头 ⇒ **docstring 里写这条教训会被判红**
            #   （复核者把教训文本加进 intent-gate 的模块 docstring，规则在一份语法完全
            #   正确的文件上报红）。`consistency-gate.py` 被按文件名硬白名单，正是因为它
            #   自己踩过——⭐ 那是给自己开后门，不是修好。⇒ 跳过三引号串区间。
            # 🚨 2026-09-09 **自攻**：单行三引号（`"""反面示例: md[i:i+1200]"""`，
            #   一行里出现两次）此前不进 in_doc ⇒ **文档字符串里的反面示例被当代码判红**。
            #   ⇒ 一行内成对闭合的三引号：把引号之间的内容剥掉再判。
            if in_doc:
                if '"""' in line or "'''" in line:
                    in_doc = False
                continue
            # 🚨 2026-09-09 四轮复核：**一行末尾加 `# """` 能让整个文件后续全部隐身** ——
            #   注释里的三引号被状态机当成 docstring 起点，之后的真违例全被跳过。
            #   ⇒ 判 docstring 边界前先去掉行内注释（注释里的引号不是语法边界）。
            _nc = _re.sub(r'#.*$', '', line) if not line.lstrip().startswith('#') else ''
            for _mark in ('"""', "'''"):
                if _nc.count(_mark) >= 2:
                    line = _re.sub(_mark + r'.*?' + _mark, '', line)
                    _nc = _re.sub(_mark + r'.*?' + _mark, '', _nc)
            _q = _re.search(r'("""|\'\'\')', _nc)
            if _q and line.count(_q.group(1)) == 1:
                in_doc = True
                continue
            # Python 切片 `[i:i+1200]` 与 JS `slice(i, i + 1200)` / `substring(...)`
            # 是同一个形状的两种写法 —— 只认其中一种，等于按语言放过另一半。
            # ⚠️ 2026-09-09 三轮复核补的六处检测缺口（每一处都实测放过过）：
            #   ①宽度写成变量 `md[i:i + W]` ②两位数窗口 `md[i:i + 80]`
            #   （而本规则 docstring 自己写着「窗口小就让段内超出部分静默逃检」——
            #     `\d{3,}` 把自己描述的一半失效模式排在了量程外）
            #   ③`j = i + 1200; md[i:j]` 分两行写 ④`find('##')` 无尾空格
            #   ⑤`find('#### ')` 四级标题 ⑥`partition('## ')` / `re.search('## ', md)`
            # 🚨🚨 2026-09-09 第四轮复核：15 个变体 **12 个逃逸** ——
            #   `md[i:i + w]`（小写变量）· `md[m.start():m.start()+1200]`（调用表达式）·
            #   `md[:1200]`（省略起点）· `md[i:i+9]`（个位）· `r[:600]` ……
            #   而**仓里当场就住着 3 处活违例**（consistency-gate:354 自己拿 1500 窗口、
            #   design-intent-gate:133 的 `r[:600]` —— 正是本规则 docstring 描述的失效模式、
            #   retro-gate:70 的 `[:300]`）。
            #   ⭐ 前几版都在给「起点/宽度长什么样」列白名单，而**真正的不变量是
            #   「切片的边界里出现了字面数字」** —— 不管它在起点、宽度还是省略处。
            #   ⇒ 判：切片/slice/substring 的任一边界含 ≥2 位字面数字，或宽度是变量加法。
            # ⚠️ 放宽到「边界含字面数字」会**大面积误伤**（实测）：CSS 串 `min-width:120px`、
            #   URL、`all.slice(0,800)`（取前 N 个**元素**不是字符）、`snippet[:60]`
            #   （显示截断）全部命中。⭐ 不变量不是「有数字」，是
            #   **「用位置从一段文本里切出子串来判内容」** ⇒ 三个必要条件同时成立才算：
            #     ①被切的是文本变量（md/src/s/seg/text/body/content/ins/doc 之类）
            #     ②切片带**起点**（纯 `[:N]` 的显示截断除外，除非变量名是文本变量）
            #     ③窗口宽度是三位以上字面量或变量加法
            # 🚨 2026-09-09 第五轮：`\b` 在下划线前**不成立**（`_` 是 `\w`）⇒
            #   `s[:2000]` 抓得到、`_s[:2000]` 逃逸。而本文件第 313 行当时就写着
            #   `re.search(..., _s[:2000])` —— **规则对自己文件里的活违例视而不见**，
            #   还打印「无固定字符窗口」。⇒ 变量名允许 `_` 前缀。
            _TEXTVAR = (r'(?:_?(?:md|src|txt|text|body|content|doc|seg|ins|raw|s|lg|dd|r|'
                        r'payload|chunk|markdown|md2))')
            _slice_pat = (
                r'\b' + _TEXTVAR + r'\s*\[\s*[\w.()]+\s*:\s*[\w.()]*\s*\+\s*(?:\d{2,}|[A-Za-z_]\w*)\s*\]'
                r'|\b' + _TEXTVAR + r'\s*\[\s*:\s*\d{3,}\s*\]'
                r'|\b' + _TEXTVAR + r'\s*\[\s*[\w.()]+\s*:\s*[\w.()]+\s*\+\s*\d{2,}\s*\]'
                # 🚨 2026-09-09 第五轮：这里只写了 `substring|substr`，**漏了 `.slice`** ——
                #   而正上方三行的注释就写着「只认其中一种，等于按语言放过另一半」。
                #   ⭐ 更值得记的是**它怎么被发现的**：`_argv.mjs` 那发变异一直报「通过」，
                #     因为当时**基线本来就红**（变异测试作废）。基线转绿的第一次运行
                #     就把这条存活变异照了出来 —— 绿基线断言不是形式主义。
                #   ⚠️ 判据仍要求「起点变量 + 加法」形态，所以 `all.slice(0, 800)`
                #     （取前 N 个**元素**）不会被误伤。
                r'|\.(?:substring|substr|slice)\(\s*[\w.()]+\s*,\s*[\w.()]*\s*\+\s*\d{2,}\s*\)')
            # ⚠️ **显示截断豁免**：切片结果直接进 print/append/消息串（`%s…`、
            #   `"text": txt[:160]`）是给人看的省略，不是判据在按位置切内容。
            #   规则从第一版起就写明只查判据用的位置切分 —— 这条豁免是它的原意。
            # 🚨 2026-09-09 第五轮：这条豁免**搜的是含行尾注释的原始行** ⇒
            #   给任意违例行加一个 ` # msg` 或 ` # 信息` 就整行豁免。
            #   ⭐ 正是 `8f01a7b`（「豁免没有边界」）要治的形状，在同一次修复里换层复发。
            #   ⇒ 判豁免前先剥掉行尾注释：注释里写什么都不改变这行**代码**在做什么。
            _code_only = _re.sub(r'#.*$', '', line) if not line.lstrip().startswith('#') else ''
            _is_display = bool(_re.search(
                r'(?:print|append|format|f"|f\'|"[^"]*%s|snippet|"text"|"line"|msg|信息)',
                _code_only))
            if _is_display:
                continue
            if (_re.search(_slice_pat, line)
                    or _re.search(r'\[\s*\w+\s*:\s*\w+\s*\+\s*[A-Za-z_]\w*\s*\]', line)
                    or _re.search(r'^\s*\w+\s*=\s*\w+\s*\+\s*\d{2,}\s*$', line)):
                bad.append("%s:%d 固定字符窗口：%s"
                           % (os.path.basename(f), ln, line.strip()[:52]))
            if _re.search(r"""(?:find|split|index|partition|rfind)\(\s*['"]#{2,4}\s*['"]""", line) \
               or _re.search(r"""re\.(?:search|match|split)\(\s*r?['"]#{2,4} """, line):
                bad.append("%s:%d 段分隔符未锚定行首（应为 '\\n## '）：%s"
                           % (os.path.basename(f), ln, line.strip()[:52]))
            # 🚨🚨 2026-09-09 第五轮独立复核（三个代理各自独立报到）：**本规则的量程
            #   漏掉了正在造成假绿的那一族**。它禁 `find('## ')`，却不禁
            #   `find('状态与异常结构')` —— 而两者失效模式**完全相同**：
            #   按文本位置切分，正文里一句交叉引用即错位。全仓当时 9 处活实例
            #   （business-map ×2、product-structure ×4、design-intent ×1、
            #   prd_completeness ×2），而规则报「无未锚定段分隔符」全绿。
            #   实证代价：一句「本文的状态与异常结构一节见文末。」让 product-structure
            #   判据④ **整条静默失效**（4 个真违例从 rc=1 变 rc=0）；
            #   一行目录让一份**完全合规**的文档同时报 ①②③ 三条假错。
            #   ⇒ 用**中文字面量**定位段落一律判违例，改用 `_section.section_at()`。
            # ⚠️ 诚实边界（2026-09-10 重新分类）：把字面量**先赋给变量**再 `s.index(var)`
            #   的间接形态，本条查不到。
            #   ⭐ **这属于「未试」不属于「做不到」** —— 做一次单文件内的朴素数据流
            #     （找 `X = '中文串'`，再找 `.index(X)`）就能覆盖大部分，
            #     只是会漏跨函数传参、也会有误报。⛔ 不写成「不可能」：
            #     并行会话今天刚踩过同型（把「我的实现做不到」写成「结构上验不了」，
            #     外部评审换个变异对象当场就测到了）。
            #   ⇒ 现状是**没做**，不是**不能做**；要做就一并配正反例，别只加检测。
            #   ⭐ 2026-09-10 订正：上一版这里点名「`prd_completeness_check.py` 就是这么写的」——
            #     那处**已经修了**（`appendix()` 两端改锚行首，b5be32d），
            #     注释若不同步就变成一条**常驻的错误记录**，下一个读它的人会据此得出错误结论。
            #     本仓早有同型教训（research-gate 那条错误病因注释误导过一次复核）。
            #   ⛔ 仍不假装能查这一族 —— 但「查不到」不等于「放着不修」：
            #     当时登记的那一处，事后复现出的是**误伤**（一句交叉引用让附件 C 被判成空壳），
            #     比漏报更贵，所以它值得单独修掉而不是留在边界声明里。
            # ⚠️ 第一版检测器**当场制造两类误伤**（门不许惩罚正确用法）：
            #   ① `md.index('\\n## 十阶段总表')` —— 它**已经锚定行首了**，正是本规则
            #      要求的正确写法，却被自己判红。⭐ 判据把「正确答案」也收进了违例集。
            #   ② `v.partition('十')` —— 解析中文数字，跟定位段落无关。
            #   ⇒ 收窄不变量：字面量**不以换行/井号开头**（即没锚定），
            #     且含 **≥2 个连续汉字**（一个字的多半不是节名）。
            if _re.search(r"""\.(?:find|index|rfind|split|partition)\(\s*"""
                          r"""(?!['"][\\n#])['"][^'"]*[\u4e00-\u9fff]{2,}[^'"]*['"]""", line):
                bad.append("%s:%d 用中文字面量定位段落（正文提一次即错位，应锚定标题）：%s"
                           % (os.path.basename(f), ln, line.strip()[:52]))
    return (not bad), bad[:6] or "无固定字符窗口、无未锚定段分隔符"


@rule("gate-roster-single-source",
      "门禁名册只许有一个正本（`_roster.py`）—— 消费方不许各 glob 一套")
def r_roster(root):
    """🚨 2026-09-10 codex 专家评审 #14 立。当时实测：

        consistency-gate 的 gate_files():  28
        gate-run --status 的口径:          27   （漏 browser-audit.mjs）
        mutation-sweep 的默认口径:         24   （另漏两个 `_check.py`）

    **三个消费方三个集合**，而每一个都拿自己那份当「全部门禁」用：
      · mutation-sweep 打印「变异全部被杀死」时，另外 4 道门连「跳过」都不出现；
      · gate-run 的「哪些门没跑过」天生看不见 browser-audit.mjs（S6 出场必跑）。
    ⭐ 而 `single-source` 这条元规则治的正是「同一概念在全仓有两种口径」——
      **它自己就发生在门禁名册上，且没有任何东西在守**。

    判据（结构性，不是数数）：除 `_roster.py` 外，scripts/ 下**没有任何脚本
    自己 glob `*-gate.*` 去凑名册**。谁要名册，就 import 正本。
    ⚠️ 只查 glob 形态，查不到「手写一个名字清单」那种 —— 那一族靠评审，已如实声明。
    """
    import re as _re
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))
                    + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        b = os.path.basename(f)
        if b == '_roster.py':
            continue
        src = read(f) or ''
        _skip = fixture_lines(src)      # 变异靶里的违例是故意造的（同一形状第三次）
        for ln, line in enumerate(src.split('\n'), 1):
            if ln in _skip:
                continue
            _code = _re.sub(r'#.*$', '', line) if not line.lstrip().startswith('#') else ''
            # ⚠️ 2026-09-10：首版要求引号**紧挨** `*-gate.` ⇒ 带路径前缀的真实写法
            #   （`_g.glob(root + '/scripts/*-gate.py')`）**整条逃逸**。
            #   ⭐ 是我给这条新规则配的那发变异当场照出来的 —— 变异靶的价值正在这儿：
            #     它打的是「规则声称守的形状」，而不是「作者写的那一发反例」。
            # 🚨 2026-09-10 codex 二轮 #4：上一版匹配的是**任意字符串** ⇒
            #   ①误伤：帮助文本 `print("Do not glob *-gate.py here")` 被报「自己 glob 名册」；
            #   ②逃逸：`glob("*-" + "gate.py")`、`Path("scripts").glob("*-gate.*")` 照造名册。
            #   ⭐ 判据认的是「像不像那句话」，不是「有没有在调 glob」。
            #   ⇒ 同一行必须**真的在调 glob**，且模式含 `-gate`（`.py/.mjs/.*` 三种收尾）。
            #   ⚠️ 诚实边界：跨行拼接出来的模式仍认不出，已如实登记。
            if (_re.search(r'\b(?:glob|iglob|rglob)\s*\(', _code)
                    and _re.search(r"""['"][^'"]*-gate\.(?:py|mjs|\*)""", _code)):
                bad.append("%s:%d 自己 glob 门禁名册（应 `from _roster import gate_files`）：%s"
                           % (b, ln, line.strip()[:52]))
    if not os.path.exists(os.path.join(root, 'scripts', '_roster.py')):
        return None, "没有 scripts/_roster.py —— 本条**没验**（正本不在，无从对账）"
    return (not bad), bad[:5] or "门禁名册只有一个正本，消费方全部走 _roster"


# 仍在手写标题解析、且**已登记理由**的脚本（2026-09-10 立表）。
# ⛔ 进这张表要写清「为什么不能用 _section」，不是「还没来得及改」。
SECTION_PARSER_EXEMPT = {
    'chain-gate.py':           '抽的是 `### INS-xxx` 这类**编号记录**而非节，'
                               '边界由编号自身决定；S1 方向那处已改用 _section',
    'g75-freeze-gate.py':      '并行会话未提交的 WIP，本会话零接触（已转告）',
    'doc-sync-guard.py':       '它比对的是**标题层级结构本身**（外发协议），'
                               '需要原始层级序列，_section 返回的是正文',
    'research-gate.py':        '同 chain-gate：`### INS-xxx` 编号记录',
    'design-to-tokens.py':     '匹配的是**令牌小节的固定命名**（中英双写），'
                               '不做段落切分',
    'intent-gate.py':          '⚠️ 试改过，改不动，理由如下（2026-09-10 实测）：'
                               'intent.md 用 `---` 当分节符，而 **CommonMark 里紧跟正文的 '
                               '`---` 是 setext 二级标题** —— `_section` 会正确地在那里切断，'
                               '于是「Open questions」节取到空、正例当场变红。'
                               '⭐ 这是**产物约定与 Markdown 语义冲突**，不是委托能解决的；'
                               '要根治得先改模板的分节写法。',
    'prd_completeness_check.py': '附件解析已委托正本（_section + end 标记）；'
                                 '功能块收尾切分走 _iter_headings。'
                                 '⚠️ 仍留一处 `re.split(r"^### M: …/ (F-\\d+):")` —— '
                                 '那是按**记录标记**切(边界由标记自身定义)，与「定位一节」不同族，'
                                 '故不改。⭐ 2026-09-10 自查订正：上一版这里写「**已全部**委托正本」，'
                                 '而那处 split 还在 —— **登记表自己犯了「声称≠实际」**。',
    'consistency-gate.py':     '两类站点，都不是「按关键词定位任意一节」：'
                               '①读 SKILL.md 的**固定锚点**（`\\n## 十阶段总表`，已锚定行首）；'
                               '②`r_gate_stage` 用「遍历所有『第一大轮』命中、'
                               '取其中真正含 R1 的那一段」—— ⭐ 这已经是'
                               '「**锚点可能命中多处，必须挑对那一个**」的正确写法，'
                               '比单纯 find 更严。'
                               '⚠️ 2026-09-10 自查订正：上一版理由**只描述了 ① 这一个站点**，'
                               '读的人会以为全文只有那一处。',
    'design-intent-gate.py':   '自证夹具构造（对着自己写的常量切）',
}

@rule("section-parser-single-source",
      "标题/段落解析只许有一个正本（`_section.py`）—— 手写一份就多一份要单独修的量程")
def r_section_parser(root):
    """🚨 2026-09-10 立。九处构造空间穷举扫出的缺陷**高度集中在同一个根因**：
      判据自己手写标题匹配（附件解析 / S1 方向抽取 / 状态节 / 决策域 / 痛点段…）。

    ⭐ 把问题从「还有多少个正则写错了」换成「**还有多少地方没接正本**」——
      前者不可枚举，后者可枚举。本规则就是那个枚举器。

    实测起点（2026-09-10）：9 个脚本、18 处真解析器仍在手写。其中
    `definition-gate.section()` 是**本仓的第二个 section 解析器**，
    而 `_section` 上修过的每一条（缩进 0–3 / `#` 后空白 / setext / 围栏 /
    空标题不崩 / 同名节）**在它那里一条都没有** —— 它已改为委托正本。

    判据：非 `_` 前缀脚本里，**解析调用**（re.search/find/split/index…）
    与**标题模式**（`#{1,N}`、`\n## `）同时出现在一行 ⇒ 记一处；
    不在 `SECTION_PARSER_EXEMPT` 里说明理由的，判红。
    ⛔ 豁免必须写理由 —— 沉默地留一份手写解析器，下次没人知道它存在。
    ⚠️ 量程：只查同一行同时出现两者的形态；跨行拼出来的、或先赋给变量的，查不到。
      ⭐ 这条边界本身就是本仓的教训（「变量间接形态查不到」），如实写在这里。
    """
    import re as _re
    _PARSE = _re.compile(r'(?:re\.(?:search|match|split|findall|finditer)'
                         r'|\.find|\.rfind|\.index|\.split|\.partition)\s*\(')
    _HEAD = _re.compile(r'#\{1,\d\}|\\n#{1,4}')
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        b = os.path.basename(f)
        if b.startswith('_'):
            continue
        src = read(f) or ''
        skip = fixture_lines(src)
        for ln, line in enumerate(src.split('\n'), 1):
            if ln in skip or line.lstrip().startswith('#'):
                continue
            if _PARSE.search(line) and _HEAD.search(line):
                key = '%s:%d' % (b, ln)
                if b in SECTION_PARSER_EXEMPT:
                    continue
                bad.append('%s 手写标题解析（应 `from _section import section_at`）：%s'
                           % (key, line.strip()[:52]))
    return (not bad), bad[:6] or "标题/段落解析只有一个正本，其余脚本要么委托要么已登记豁免"


@rule("doc-symbols-exist",
      "注释/docstring 里用反引号点名的**本地函数**必须真的存在（承诺一个不存在的函数＝声称≠实际）")
def r_doc_symbols(root):
    """🚨 2026-09-10 立，起因是一个**躲过七轮独立复核 + 两轮 codex 评审 + 九处穷举**的缺陷：

      `_sweep_lib.py` 的模块 docstring 从第一版起就写着
        「⇒ `assert_weight_bearing()` 把这件事变成**机器检查**」
      而**那个函数根本不存在** —— 承重确认全是手工做的。
      ⭐⭐ **在为了治「声称≠实际」而写的模块里，犯了「声称≠实际」。**
      它躲过所有评审的原因很简单：**没有任何东西在查「文档提到的代码实体是否存在」**。
      （最后是 codex 第三轮跑到一半的一次 grep 偶然照出来的。）

    判据：反引号包着的 `名字()` 形态，若既不是本仓任何脚本里定义的函数、
    也不在标准库常见名单里 ⇒ 判红。

    ⛔ **只查函数名，不查文件名。** 文件名那一支实测**几乎全是误伤** ——
      脚本会合法地点名**项目侧产物**（`DESIGN.md` / `tokens.json` / `flows.json`）
      与**假设性例子**（`stealth-check.py` / `no-such-file.md`），11 个脚本全中。
      ⭐ 建一条大面积惩罚正确文档的规则，比不建更糟；这条边界是**实测后的决定**，
        不是「还没做」。
    ⚠️ 量程：只认 `` `name()` `` 这一种写法；不带括号的、跨语言的、
      动态生成的名字都查不到 —— 这是「未试」，可以做（比如放宽到不带括号），
      但那样误伤会上来，需要先有正例集。
    """
    import re as _re
    defined = set()
    for f in (glob.glob(os.path.join(root, 'scripts', '*.py'))
              + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        src = read(f) or ''
        defined |= set(_re.findall(r'^\s*def\s+(\w+)', src, _re.M))
        defined |= set(_re.findall(
            r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', src, _re.M))
        defined |= set(_re.findall(r'^\s*(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(',
                                   src, _re.M))
    STD = {'print', 'open', 'len', 'set', 'sorted', 'int', 'str', 'list', 'dict', 'range',
           'next', 'max', 'min', 'search', 'match', 'sub', 'findall', 'finditer', 'join',
           'exit', 'run', 'get', 'append', 'strip', 'split', 'format', 'index', 'find'}
    # ⚠️ 2026-09-10：本规则**当场把自己判红** —— 它的 docstring 里写着
    #   「只认 `name()` 这一种写法」，而 `name` 是**元描述用的占位名**不是真引用。
    #   ⭐ 「规则扫到自己造的东西」本会话第四次（注释剥掉了被查的模式 / 变异靶 ×2 / 这次）。
    #   ⇒ 占位名单列。⛔ 不按文件名给自己开后门（那是第五轮批过的做法）。
    PLACEHOLDER = {'name', 'foo', 'bar', 'baz', 'xxx', 'fn', 'func', 'f', 'x', 'y'}
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))
                    + glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        src = read(f) or ''
        skip = fixture_lines(src)
        for ln, line in enumerate(src.split('\n'), 1):
            if ln in skip:
                continue
            for m in _re.finditer(r'`([A-Za-z_]\w*)\(\)`', line):
                n = m.group(1)
                if n in defined or n in STD or n in PLACEHOLDER:
                    continue
                bad.append('%s:%d 点名了不存在的函数 `%s()`（承诺≠实现）'
                           % (os.path.basename(f), ln, n))
    return (not bad), bad[:6] or "注释里点名的本地函数全部真实存在"


@rule("scripts-parse", "scripts/ 下每个脚本都必须能被解释器解析（语法坏了就不是门禁了）")
def r_parse(root):
    """⚠️ 2026-09-03 立，起因是**同一会话里三次**把反引号写进了注入页面的模板字面量
    （`const PROBE = ` + 反引号），当场截断模板、报一个位置离得很远的 SyntaxError。

    ⛔ 我的第一版规则是**装饰的**：它在「从模板开头到第一个反引号」这段里找反引号，
    而那段按定义就不含反引号 —— 恒为空，永远报绿。文件明明是坏的，规则说没问题。
    ⭐ 教训：**判据里出现「到第一个 X 为止」再去找 X，就是循环**。
    改成直接调解释器 —— 它不可能循环，也不会因为我换个写法就失效。
    """
    import subprocess
    bad = []
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.mjs'))):
        if subprocess.call(['node', '--check', f], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) != 0:
            bad.append("%s 语法错误（node --check 不过）" % os.path.relpath(f, root))
    for f in sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        # ⛔ 原用 py_compile：会往被审目录写 __pycache__，且任何写失败/环境问题都会
        #   被折叠成「语法错误」。ast.parse 纯内存、只判语法；读不了文件是 UNABLE 类问题，单独说。
        try:
            import ast as _ast
            _ast.parse(io.open(f, encoding='utf-8').read())
        except SyntaxError as e:
            bad.append("%s 语法错误（ast.parse: line %s）" % (os.path.relpath(f, root), e.lineno))
        except Exception as e:
            bad.append("%s 读不了（环境问题，非语法）：%s" % (os.path.relpath(f, root), e))
    return (not bad), bad or "全部脚本可解析"

@rule("iron-rule-seq", "SKILL.md 铁律编号严格递增无重号（多轮追加最容易在这里出事）")
def r_iron_seq(root):
    """⚠️ 为什么单独立一条：原来的 rule-count 只数**总条数**，
    23 条之后重新出现 18、19 再接 24，总数照样对得上，它一声不吭。
    而**别处引用「铁律 18」时会指到两条不同的规则**——引用者无从判断以哪条为准。
    （2026-08-31 由 Codex 外部评审揪出，本门当时守不住。）"""
    # 2026-09-08（终局规格 Phase D）：铁律正文迁 references/iron-rules.md（保留原编号，
    # 全仓引用不断链）；SKILL 只留十条元原则 + 指针。本规则**优先读新位置**，
    # 没有新文件时退回 SKILL 旧位置（两种布局都守，迁移不产生盲窗）。
    ir = read(os.path.join(root, 'references', 'iron-rules.md'))
    if ir is not None:
        lines = ir.split('\n'); start = 0
    else:
        md = read(os.path.join(root, 'SKILL.md'))
        if md is None: return None, "读不到 SKILL.md"
        lines = md.split('\n')
        try:
            start = next(i for i, l in enumerate(lines) if l.strip() == '## 铁律')
        except StopIteration:
            return None, "SKILL.md 里没有「## 铁律」小节，也没有 references/iron-rules.md"
    nums = [int(re.match(r'^(\d+)\.', l).group(1))
            for l in lines[start:] if re.match(r'^\d+\. ', l)]
    if not nums: return None, "铁律小节里没有编号条目"
    bad = [(i + 1, n) for i, n in enumerate(nums) if n != i + 1]
    if bad:
        return False, ["第 %d 条被标成了 %d" % (pos, n) for pos, n in bad[:8]] + \
                      ["共 %d 条，编号乱了 %d 处" % (len(nums), len(bad))]
    dangling = []
    for f in md_files(root) + sorted(glob.glob(os.path.join(root, 'scripts', '*.py'))):
        c = read(f)
        if not c: continue
        for m in re.findall(r'铁律 (\d+)', c):
            if int(m) > len(nums):
                dangling.append("%s 引用了不存在的铁律 %s" % (os.path.basename(f), m))
    if dangling: return False, dangling[:8]
    return True, "%d 条编号连续，引用全部有效" % len(nums)

@rule("iron-rule-mapped", "压缩层 P1–P10 必须真覆盖铁律全集（映射可核对；无家条目显式登记有棘轮）")
def r_iron_mapped(root):
    """⚠️ 为什么：P1–P10 自称是铁律全集的压缩层，而「覆盖」此前只是一句宣称——
    没有任何东西能查出「有一条铁律被压缩层漏掉」或「有一条 P 压缩自空集」。
    2026-09-09 映射表落地当天两种都真实存在：P9 无基条（铁律 52 为此补）、
    P10 只写了红的一半（全绿≠背书那半在 15/39/44 里悬着）。
    判据：①每条铁律在映射表里恰好一行 ②归属只认 P<n> / 域:<存在的文件> / —（带原因）
    ③被引的 P 必须在 SKILL.md 定义 ④每条 P ≥1 个基条（死原则=压缩层在撒谎）
    ⑤「—」≤2 条（棘轮，当前实值）⑥SKILL 声称的「全文 N 条」= 实际条数。"""
    ir = read(os.path.join(root, 'references', 'iron-rules.md'))
    md = read(os.path.join(root, 'SKILL.md'))
    if ir is None or md is None: return None, "读不到 iron-rules.md 或 SKILL.md"
    total = len([1 for l in ir.split('\n') if re.match(r'^\d+\. ', l)])
    if not total: return None, "iron-rules.md 里没有编号条目"
    try:
        sec = md[md.index('\n## 铁律'):]
    except ValueError:
        return None, "SKILL.md 没有「## 铁律」节"
    nxt = sec.find('\n## ', 4)
    if nxt > 0: sec = sec[:nxt]
    p_def = set(int(x) for x in re.findall(r'^- \*\*P(\d+)', sec, re.M))
    mi = ir.find('\n## 映射表')
    if mi < 0:
        return False, ["iron-rules.md 没有映射表 —— 压缩层的覆盖退回宣称"]
    rows = re.findall(r'^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|', ir[mi:], re.M)
    bad, seen, members, homeless = [], {}, set(), 0
    for num_s, cell in rows:
        n = int(num_s)
        if n in seen: bad.append("铁律 %d 在映射表出现了两次" % n)
        seen[n] = cell
        ps = [int(x) for x in re.findall(r'P(\d+)', cell)]
        doms = re.findall(r'域[:：]\s*([\w\-.]+\.md)', cell)
        dash = cell.lstrip().startswith('—')
        if not ps and not doms and not dash:
            bad.append("铁律 %d 的归属看不懂：%s" % (n, cell.strip()[:30]))
        for p in ps:
            if p not in p_def: bad.append("铁律 %d 归到了未定义的 P%d" % (n, p))
            members.add(p)
        for d in doms:
            if not os.path.exists(os.path.join(root, 'references', d)):
                bad.append("铁律 %d 的域正本不存在：references/%s" % (n, d))
        if dash:
            homeless += 1
            if len(cell.strip()) < 8: bad.append("铁律 %d 标了「—」却没写原因" % n)
    missing = sorted(set(range(1, total + 1)) - set(seen))
    extra = sorted(set(seen) - set(range(1, total + 1)))
    if missing: bad.append("这些铁律不在映射表里（压缩层漏掉了它们）：%s" % missing[:8])
    if extra: bad.append("映射表里有不存在的铁律：%s" % extra[:8])
    orphan = sorted(p_def - members)
    if orphan: bad.append("这些 P 压缩自空集（原则悬空无基条）：%s"
                          % "、".join("P%d" % p for p in orphan))
    if homeless > 2:
        bad.append("「—」无家条目 %d 条 > 棘轮上限 2 —— 新增的先想清楚该并进哪条 P" % homeless)
    m = re.search(r'全文 (\d+) 条', md)
    if m and int(m.group(1)) != total:
        bad.append("SKILL 声称「全文 %s 条」，实际 %d 条" % (m.group(1), total))
    return (not bad), bad[:8] or ("%d 条铁律全部有归属；P 层 %d 条各有基条；无家 %d/2"
                                  % (total, len(p_def), homeless))


# ------------------------------------------------- R11 语义口径单一真源
@rule("single-source", "同一概念的分类数在全仓只能有一种口径（NFR 类数 / 阶段数）")
def r_single_source(root):
    """⚠️ 这是 rule-count / gate-count 覆盖不到的一层：
    它们比对的是「声称 vs 实际存在的东西」，
    而这里比对的是**「声称 vs 另一处声称」**——两处都只是文字，没有任何实体可比。
    实测发现时，同一份 SKILL.md 里 NFR 同时写着四类、五类、六类，模板里还是三类。
    ⭐ **照着做的人不知道以哪一份为准，而没有任何东西会报错。**"""
    CN = {'三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    probes = [
        ("全局 NFR 分类数",
         re.compile(r'NFR[^。\n]{0,24}?([三四五六七八九十\d]+)\s*类'
                    r'|([三四五六七八九十\d]+)\s*类[^。\n]{0,12}?NFR')),
        ("流程阶段数",
         re.compile(r'完整\s*([三四五六七八九十\d]+)\s*阶段|套\s*([三四五六七八九十\d]+)\s*阶段')),
    ]
    bad = []
    for name, pat in probes:
        seen = {}
        for f in md_files(root):
            c = read(f)
            if not c: continue
            for i, ln in enumerate(c.split('\n'), 1):
                if ln.lstrip().startswith('>') or '原来' in ln or '此前' in ln:
                    continue
                m = pat.search(ln)
                if not m: continue
                v = next(g for g in m.groups() if g)
                n = CN.get(v) or (int(v) if v.isdigit() else None)
                if n: seen.setdefault(n, []).append("%s:%d" % (os.path.relpath(f, root), i))
        if len(seen) > 1:
            bad.append("%s 出现 %d 种口径：%s" %
                       (name, len(seen),
                        " / ".join("%d(%s)" % (k, v[0]) for k, v in sorted(seen.items()))))
    if bad: return False, bad
    return True, "NFR 类数与阶段数口径唯一"



# --------------------------------------------------------------- 执行
# ═══════════════════════════════════════════════════════════════════
# 项目模式：查**交付物**（不是本 skill）里的「声称≠实际」
# 三条规则各自对应 2026-08-31 在 验证项目 上实测到的一个真缺陷。
# ═══════════════════════════════════════════════════════════════════
PROJECT_RULES = []
SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', '.venv', 'venv',
             '__pycache__', 'models', 'vendor', '.morph'}
TEXT_EXT = {'.md', '.json', '.css', '.html', '.htm', '.py', '.js', '.mjs', '.cjs', '.sh', '.txt'}
MAX_BYTES = 2_000_000


def prule(rid, desc):
    def deco(fn):
        PROJECT_RULES.append({"id": rid, "desc": desc, "fn": fn}); return fn
    return deco


SKIPPED_OVERSIZE = []          # 被 MAX_BYTES 挡下的文件，供 oversize-disclosed 规则报出
PROJECT_SCANNED = False        # walk_text 至少产出过一次 —— 没扫过就不许说「没有超大文件」


def walk_text(root, exts=None):
    """产出 (相对路径, 内容)。跳过 vendor/生成目录与超大文件。

    ⚠️⚠️ 2026-09-04：超大文件此前是**静默 `continue`** —— 不提示、不计数。
    于是一份 2.5MB 的 SKILL.md 会被整个跳过，**而依赖它的每条规则照样报绿**。
    ⛔ 这是「静默截断」那一族最标准的形态：跳过本身可能合理，
      **但被跳过的事实必须说出来**，否则「没扫到」与「扫过没问题」长得一模一样。
    ⇒ 记进 `SKIPPED_OVERSIZE`，由 `oversize-disclosed` 规则报出来。
    """
    for r, ds, fs in os.walk(root):
        ds[:] = [d for d in ds if d not in SKIP_DIRS and not d.startswith('.git')]
        for f in sorted(fs):
            ext = os.path.splitext(f)[1].lower()
            if exts is not None and ext not in exts:
                continue
            if ext not in TEXT_EXT:
                continue
            full = os.path.join(r, f)
            try:
                _sz = os.path.getsize(full)
                if _sz > MAX_BYTES:
                    SKIPPED_OVERSIZE.append((os.path.relpath(full, root), _sz))
                    continue
                global PROJECT_SCANNED
                PROJECT_SCANNED = True
                yield os.path.relpath(full, root), io.open(full, encoding='utf-8', errors='replace').read()
            except OSError:
                continue


# ── P1 查证标记 ──────────────────────────────────────────────
# 实测缺陷：PRD 写 `[查证·design/tokens.json contrastPolicy]`，而 contrastPolicy
# 这个字段**只在另一份文件里**。查证指针指向的文件里没有被查证的东西 ——
# 而 M2「每个事实标出处」正是靠这个标记落地的，它一旦悬空，出处就是装饰。
# ⚠️ 判据必须照**真实形态**造，不能照想象造。首版假设标记是「路径 + 关键词」，
#    实测 验证项目 的 146 个标记里主流是 `[查证·inspector.test.js·2026-08-30]`
#    （来源 + 日期，用 `·` 分段），于是日期段被当成路径 → 一次报出上百条假阳性。
#    真实并存的四种：
#      [查证·kernel/main.js·<日期>]        路径 + 日期
#      [查证·inspector.test.js·<日期>]     裸文件名 + 日期（按 basename 全仓找）
#      [查证·CLAUDE.md 约定]               文件 + 空格 + 关键词
#      [查证·代码·<日期>]                  散文来源 —— **机械解析不了，不报红**
VERIFY_RE = re.compile(r'\[查证[·:：]\s*([^\]]+)\]')
# 扩展名必须含字母，否则章节号 `7.2` 会被当成文件名（实测报出过这条假阳性）
HAS_EXT = re.compile(r'^[\w.\-/]+\.[A-Za-z][A-Za-z0-9]{0,5}$')
# 关键词只有长得像**标识符**时才回文件里搜。`[查证·CLAUDE.md 约定]` 的「约定」是
# 泛指「那份文件里的约定」，不是可 grep 的字面量 —— 拿它去搜必然假阳性（实测 8 条）。
IDENT_KW = re.compile(r'^[A-Za-z_][A-Za-z0-9_.\-]{2,}$')


@prule("verify-marker", "`[查证·文件 关键词]` 的文件必须存在，关键词必须真能在里面搜到")
def p_verify(root):
    index = {}
    for rel, _ in walk_text(root):
        index.setdefault(os.path.basename(rel), []).append(rel)
    bad, checked, skipped = [], 0, 0
    for rel, text in walk_text(root, {'.md'}):
        for m in VERIFY_RE.finditer(text):
            head = m.group(1).split('·')[0].strip()       # 后面的段是日期/上下文
            target, _, kw = head.partition(' ')
            target, kw = target.strip(), kw.strip()
            if target.startswith(('http://', 'https://')) or not HAS_EXT.match(target):
                skipped += 1                              # 散文来源，机械解析不了：不猜也不报红
                continue
            if '/' in target:
                cand = [target] if os.path.exists(os.path.join(root, target)) else []
            else:
                cand = index.get(target, [])
            if not cand:
                bad.append("%s: 查证指向的文件找不到 —— %s" % (rel, target)); continue
            checked += 1
            probe = kw.split()[0] if kw else ''
            if not IDENT_KW.match(probe):
                continue                      # 泛指词不回文件里搜，只确认文件在
            if not any(probe in io.open(os.path.join(root, c), encoding='utf-8',
                                        errors='replace').read() for c in cand):
                bad.append("%s: 关键词 `%s` 在 %s 里搜不到 —— 指针指向的文件里没有被查证的东西"
                           % (rel, probe, target))
    if not checked and not bad:
        return None, "没有可机械核实的查证标记（%d 处是散文来源）" % skipped
    return (not bad), bad or "%d 处查证标记可核并全部命中（另 %d 处是散文来源，未机械核）" % (checked, skipped)


# ── P2 生成物必须有生成器 ────────────────────────────────────
# 实测缺陷：demo 头部写着「自动生成，勿手改」，而**没有任何脚本会生成它** ——
# 改了真源它不会变，也不会有任何东西报错。一份没有生成器的「生成物」。
GEN_MARK = re.compile(r'自动生成|勿手改|请勿手动|DO NOT EDIT|AUTO-?GENERATED', re.I)


def product_claim_text(text):
    """Remove this gate's exact diagnostic blocks, not files or arbitrary code fences.

    A preserved rule description is not a product claim. Keep all surrounding prose;
    this is a lint distinction, not authentication of the transcript or its verdict.
    """
    headers = {f'{icon} [{r["id"]}] {r["desc"]}'
               for r in PROJECT_RULES for icon in ('✅', '❌', '➖')}

    def strip_diagnostics(value):
        lines, diagnostic = [], False
        for line in value.splitlines():
            if line in headers:
                diagnostic = True
                continue
            if diagnostic and line.startswith('      '):
                continue
            diagnostic = False
            lines.append(line)
        return '\n'.join(lines)

    try:
        record = json.loads(text)
    except (ValueError, TypeError):
        record = None
    if (isinstance(record, dict) and record.get('gate') == 'consistency-gate.py'
            and isinstance(record.get('stdout'), str)):
        # Only clean the transcript field; other fields remain subject to inspection.
        record['stdout'] = strip_diagnostics(record['stdout'])
        return json.dumps(record, ensure_ascii=False)
    return strip_diagnostics(text)


# ⚠️ 判据是「有脚本**写**它」，不是「有脚本**提到**它」。
#    首版用 `base in t`，于是 asserts.js 注释里的一句
#    `node selftest.mjs sample-interaction-demo.html` 就让它判「有生成器」——
#    正是本文件在别处刚治掉的「提一句就算数」，在新规则里原样复发。
WRITE_HINT = re.compile(r'write|dump|savefig|outfile|>>|>\s|tee\b', re.I)


@prule("claim-ladder-backed",
       "声明的完成级别必须有对应证据（`integrated-frozen`/`production-validated` 尤其）")
def p_claim_ladder(root):
    """🚨 2026-09-09：**六级声明阶梯此前零机器守卫**（方案 §13-27 点名「不得越级」）。
    阶梯定义在 `flow-tailoring.md`，写得很清楚，但**没有任何东西在查产物有没有越级**——
    而这恰恰是最容易越的一级：写「已冻结」比做到冻结容易得多。

    判据（只查能机械证明的那部分，⛔ 不声称能判「批准得对不对」）：
      · 声称 `integrated-frozen` → 项目里必须有 G7.5 的落盘结论
        （`.product-flow/gates/g75-freeze-gate.py*.json`）且其 pass 为真；
      · 声称 `production-validated` → 还必须有 S9 的真实观察记录（`retro.md` 且非 PENDING）。
    ⚠️ 找不到 `.product-flow/` 的项目（还没开跑）→ N/A，不是失败。
    """
    import json as _json
    # 🚨 2026-09-09 第五轮独立复核：`lvl in text` 是**裸子串匹配** ——
    #   否定句照样算「声称」。实证：把本 skill **自带的**
    #   `templates/triad-reconciliation.md`（第 8 行写「…**不是** integrated-frozen」）
    #   抄进一个空项目的 docs/，`--project` 立刻报红。
    #   ⭐ **照着 skill 做的人第一天就被判违规** —— 本仓纪律：门不许惩罚正确产物。
    #   ⇒ 命中前若紧邻否定/条件语（不是/非/未/尚未/不算/而不是/不得/不能声称），不算声称。
    # ⚠️ 2026-09-10 第六轮（F8）：否定词要求**紧邻**命中点 ⇒
    #   「本文档不会声称 integrated-frozen」被判成声称（中间隔了「声称」二字）。
    #   ⇒ 允许中间夹一个**声称类动词**（封闭小集），⛔ 不放宽成「前面出现过否定词」——
    #     那会把「本轮不含新功能，状态：integrated-frozen」也豁免掉。
    _NOT_CLAIM = re.compile(r'(?:不是|不算|而不是|并非|非|未|尚未|不得|不能|不会|别|⛔)'
                            r'\s{0,2}(?:声称|宣称|标记为|标为|算作|写成|视为|等于)?'
                            r'[\s「『"*_`（(]{0,4}$')
    hits = []
    for rel, text in walk_text(root, {'.md'}):
        text = product_claim_text(text)
        for lvl in ('integrated-frozen', 'production-validated'):
            for _m in re.finditer(re.escape(lvl), text):
                _lo = text.rfind('\n', 0, _m.start()) + 1
                if _NOT_CLAIM.search(text[max(_lo, _m.start() - 12):_m.start()]):
                    continue          # 「不是 integrated-frozen」是在讲清楚，不是在声称
                # 🚨 2026-09-10 codex 评审 #5：仍是**裸子串扫描** ⇒
                #   「状态枚举值包括 `integrated-frozen`，含义见流程规范」被报成声称。
                #   ⭐ 这是**门惩罚正确产物** —— 写文档解释状态枚举是完全正当的事。
                #   ⇒ 两条结构性豁免（都不是词表）：
                #     ①命中落在**行内代码跨**（反引号）里 ⇒ 那是在**提这个词**，不是在用它；
                #     ②同一行出现枚举/讲解语境词 ⇒ 在描述取值域，不是在声明本轮状态。
                _line = text[_lo:(text.find('\n', _m.end()) + 1) or len(text)]
                # ⚠️⚠️ 2026-09-10 **构造空间穷举**（语境 × 包裹 × 位置，84 例）扫出 12 例失配：
                #   「反引号内＝提及」这条启发式**方向就是错的** ——
                #   `本轮状态：`integrated-frozen`。` 是再正常不过的**真实声称**
                #   （人们习惯给状态值加代码格式），却被整族豁免掉。
                #   ⭐ 我为了消除 codex #5 那一处误伤，顺手加了「包裹」这个代理指标，
                #     而真正的区分从来不在包裹，在**这句话在主张什么**。
                #   ⇒ 撤掉包裹豁免，只留两条语义判定：否定语境、描述取值域。
                #     codex #5 的原例（「状态枚举值包括 …，含义见流程规范」）
                #     由「枚举/包括」那条兜住，不需要靠反引号。
                # ⚠️ 2026-09-10 codex 二轮 #2：上一版的豁免词表含「说明/示例」⇒
                #   `**状态说明**：integrated-frozen` **整条被豁免**，真实声明不要证据了。
                #   ⭐ 我为了消除一种误伤，造了一个比它更大的漏报口子。
                #   ⇒ 收窄到**只描述取值域**的那几个词，且要求它们出现在**命中之前**
                #     （「枚举值包括 X」是讲取值域；「状态说明：X」是在声明状态）。
                if re.search(r'枚举|取值范围|可选值|合法值|之一是|包括', _line[:_m.start() - _lo]):
                    continue
                hits.append((rel, lvl))
                break
    if not hits:
        return None, "产物里没有声称 integrated-frozen / production-validated（无可对账）"
    import datetime as _dtm

    def _parse_iso(t):
        for _f in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S',
                   '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
            try:
                return _dtm.datetime.strptime(t[:len('2026-01-01T00:00:00')].rstrip('Z'), _f)
            except Exception:
                pass
        return None

    _now = _dtm.datetime.now()
    gates = os.path.join(root, '.product-flow', 'gates')
    frozen_ok = False
    _cands = []
    if os.path.isdir(gates):
        for fn in os.listdir(gates):
            if fn.startswith('g75-freeze-gate.py'):
                try:
                    _r = _json.load(io.open(os.path.join(gates, fn), encoding='utf-8'))
                except Exception:
                    continue
                # 🚨 2026-09-09 自查（第三轮复核前）：首版读的是 `pass` 字段，
                #   而 `gate-run.py` 真实写的是 `verdict`/`exitCode`/`ranAt` ——
                #   ⭐ **判据读的字段根本不存在于真实记录里**，于是它既漏真记录，
                #   又让手写一个 `{"pass": true}` 直接过关（实测确认）。
                #   ⛔ 「只验存在不验内容」在这条上尤其致命：它守的是冻结声明。
                #   ⇒ 认真实 schema：verdict 必须是 PASS、exitCode 必须是 0、
                #     且带 ranAt 执行时间戳（手写的假记录通常凑不齐这三样）。
                #   ⚠️ 诚实边界：这仍**挡不住刻意伪造**——机器判据只能提高伪造成本，
                #     真正的不可伪造性要靠 receipt 体系（登记册 #3，并行会话在做）。
                # 🚨 2026-09-09 第四轮复核：**121 个字符即可伪造** —— `ranAt` 只测真值性
                #   （整数 1 就行）、文件不需要 `.json` 后缀（判据用 startswith 而
                #   `gate-run --status` 用 *.json glob ⇒ 同一记录一个消费者看得见另一个看不见）、
                #   陈旧记录不检测（ranAt=1970 + stdout 写着「全部红了」照样绿）。
                #   ⇒ 提高伪造成本到「必须编一份看起来像真跑过的完整记录」：
                #     ①文件名必须是 .json（与 gate-run --status 的 glob 一致）
                #     ②ranAt 必须是可解析的 ISO 时间且不早于产物最近改动
                #     ③记录里的 stdout/verdict 不许自相矛盾
                #   ⚠️ 诚实边界：这仍**不是不可伪造**——真正的不可伪造要靠 receipt
                #     体系（登记册 #3）。机器判据只能让「顺手糊一个」变得不顺手。
                if not fn.endswith('.json'):
                    continue
                # 🚨 2026-09-09 第五轮：上面注释写「ISO 时间**且不早于产物最近改动**」，
                #   而代码只有一个**形状正则** —— `2999-12-31`、`2026-13-45T99:99`、
                #   `1970-01-01` 全部通过。⭐ 注释承诺了陈旧性检查，代码没做；
                #   而 `gate-run.py --status` **是**做陈旧性比较的 ——
                #   同一条记录，两个消费者两套判法。
                #   ⇒ 本条现在做的是**真解析 + 拒未来时间戳**（形状对但不存在的时间
                #     `2026-13-45T99:99`、`2999-12-31` 一律不认）；陈旧性见下方说明。
                _ts = str(_r.get('ranAt') or '')
                _dt = _parse_iso(_ts)
                if _dt is None:
                    continue      # 不是**真实存在**的时间 ⇒ 不认（不只是形状对）
                if _dt > _now + _dtm.timedelta(days=1):
                    continue      # 未来时间戳 ⇒ 不认
                # ⚠️⚠️ 这里**曾经**加过一条「记录不得早于产物最近改动」的陈旧性判据，
                #   当场把本门自己的**合法正例**判红了（自证抓到）。⇒ 已撤掉。
                #   ⭐ 撤的理由不是「难做」，是**我量错了对象**：拿「项目里任意 .md 的
                #     最新 mtime」当基准，意味着改个 README 错字就让冻结记录失效 ——
                #     那会惩罚正确产物，而本仓纪律里「量错对象比量不到更危险」。
                #   ⭐ 真正的陈旧性判定需要知道「G7.5 到底读了哪些产物」，
                #     那是 receipt 体系（登记册 #3）的事，不是 mtime 能替的。
                #   ⇒ 本条**不声称**做陈旧性检查（上一版注释声称了而代码没做，
                #     那才是更糟的状态：声称≠实际）。
                _out = str(_r.get('stdout') or '')
                if re.search(r'❌|FAIL|失败|不通过', _out):
                    continue      # 记录自己的输出与 verdict 矛盾 ⇒ 不认
                # 🚨🚨 2026-09-10 codex 评审 #1（Critical）：**G7.5 的 rc=0 只代表
                #   「本地六查通过」，不代表「可以宣 integrated-frozen」** ——
                #   它自己的输出里会写「⛔ 冻结上限=本地契约验证通过（原生证据 0/3）」。
                #   而本条只读 `verdict/exitCode`，于是**零原生证据的项目照样拿到绿灯**。
                #   ⭐ 我此前用「真正不可伪造要靠 receipt」把这块划成了边界 ——
                #     那条边界**掩盖了一个当下就能修的语义错配**：
                #     消费 G7.5 已经打印出来的冻结上限，不需要任何密码学 receipt。
                #   ⇒ 记录里若声明了低于 integrated-frozen 的上限，本条不认它当背书。
                # 🚨 2026-09-10 codex 二轮 #1（Critical）：上一版把不够格的记录直接
                #   `continue` 掉 ⇒ 它**不进候选**，于是「取 ranAt 最新那条」会**回退到旧记录**——
                #   一条更早的、可宣 integrated-frozen 的 PASS 就能替最新的降级结论背书。
                #   ⭐ 我把失效触发器从「rc=0」换成了「stdout 没写低上限」，而没换掉那条回退路径。
                #   ⇒ 不够格的记录**照样进候选**（带上标记），由「最新那条」统一裁决。
                _ceil = re.search(r'冻结上限\s*[=＝:：]\s*([^\n）)]{2,24})', _out)
                _ok_ceiling = not (_ceil and 'integrated-frozen' not in _ceil.group(1))
                # 🚨 第五轮：此前**任取一条命中即算通过** —— 真实的
                #   `g75-freeze-gate.py.json`(FAIL) 旁边放一个 `.old.json`(PASS) 就判过。
                #   ⇒ 只认 ranAt **最新**的那一条；旧记录不许替新结论背书。
                _cands.append((_dt, _r, _ok_ceiling,
                               _ceil.group(1).strip() if _ceil else None))
    _ceiling_note = None
    if _cands:
        _dt, _r, _ok_ceiling, _note = max(_cands, key=lambda x: x[0])
        frozen_ok = (_r.get('verdict') == 'PASS' and _r.get('exitCode') == 0
                     and _ok_ceiling)
        if not _ok_ceiling:
            _ceiling_note = _note
    retro = os.path.join(root, '.product-flow', 'retro', 'retro.md')
    retro_txt = read(retro) or ''
    retro_ok = bool(retro_txt) and 'PENDING' not in retro_txt
    bad = []
    for rel, lvl in hits[:8]:
        if lvl == 'integrated-frozen' and not frozen_ok:
            bad.append("%s 声称 integrated-frozen，但没有 G7.5 通过的落盘结论"
                       "（.product-flow/gates/g75-freeze-gate.py*.json）" % rel)
        if lvl == 'production-validated' and not (frozen_ok and retro_ok):
            bad.append("%s 声称 production-validated，但缺 G7.5 落盘或 S9 真实观察"
                       "（retro.md 不存在或仍是 PENDING）" % rel)
    return (not bad), bad[:5] or "声称的完成级别都有对应证据"


@prule("generated-has-generator", "标了「自动生成/勿手改」的文件，项目里必须真有脚本会写它")
def p_gen(root):
    scripts = {rel: t for rel, t in walk_text(root, {'.py', '.js', '.mjs', '.cjs', '.sh'})}
    bad, n = [], 0
    for rel, text in walk_text(root):
        if os.path.splitext(rel)[1].lower() in {'.py', '.js', '.mjs', '.cjs', '.sh'}:
            continue                      # 脚本自己带这类字样通常是在描述别人
        text = product_claim_text(text)
        # 「自动生成」标记按惯例在文件头部：锚前 10 行，不锚字符数
        if not GEN_MARK.search('\n'.join(text.split('\n')[:10])):
            continue
        n += 1
        base = os.path.basename(rel)

        def writes(t):
            i = t.find(base)
            while i >= 0:
                if WRITE_HINT.search(t[max(0, i - 200): i + 200]):
                    return True
                i = t.find(base, i + 1)
            return False

        if not any(writes(t) for t in scripts.values()):
            bad.append("%s: 自称「自动生成」，但项目里没有任何脚本提到它 —— 改了真源它不会变" % rel)
    if not n:
        return None, "没有标「自动生成」的文件"
    return (not bad), bad or "%d 个生成物都有生成器" % n


# ── P3 「正本/真源在 X」里的 X 必须存在 ──────────────────────
# 实测缺陷：交互规格写「令牌一律引用 design/tokens.json」，而实际用的是另一份；
# PRD 表格把 v1 文件标成「（v2）」。指错正本比不写正本更糟：它看起来是有据可依的。
SOT_RE = re.compile(r'(?:正本(?:在|是|=)|真源[:：]?)\s*`([^`\n]+)`')


@prule("source-of-truth-exists", "「正本在 `X`」/「真源：`X`」里的 X 必须真的存在")
def p_sot(root):
    # ⚠️ 2026-09-04：裸文件名与 URL 此前是**静默跳过** —— 不计数、不提示，
    #    而结论文案写「N 处正本声称都指得到」。于是一份全用裸文件名写正本的文档
    #    会得到「都指得到」这个结论，**而一处都没查**。
    #    ⛔ 跳过合理（裸文件名无法定位，不该猜），**但跳过的事实必须说出来**。
    bad, n, skipped = [], 0, 0
    for rel, text in walk_text(root, {'.md'}):
        for m in SOT_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(('http://', 'https://')) or '/' not in target:
                skipped += 1          # 裸文件名/URL 无法定位，不猜 —— 但要报出来
                continue
            n += 1
            # ⚠️ `~` 必须先展开:os.path.join(root, '~/x') 会拼成 <root>/~/x,
            # 于是**任何用 ~ 写的正本路径都会被误报为不存在**(2026-09-02 在 验证项目 实测)。
            # 绝对路径同理 —— join 会直接丢掉 root,但仍需按绝对路径判存在。
            probe = os.path.expanduser(target)
            probe = probe if os.path.isabs(probe) else os.path.join(root, probe)
            if not os.path.exists(probe):
                bad.append("%s: 声称正本在 %s，而它不存在" % (rel, target))
    if not n:
        return None, ("文档里没有可定位的「正本在 `路径`」式声称"
                      + ("（另有 %d 处是裸文件名/URL，无法定位，未查）" % skipped if skipped else ""))
    return (not bad), bad or ("%d 处正本声称都指得到" % n
                              + ("；另有 %d 处是裸文件名/URL，**未查**" % skipped if skipped else ""))


def run_project(root, as_json=False):
    if not os.path.isdir(root):
        print("UNABLE: 不是目录 %s" % root, file=sys.stderr); sys.exit(2)
    res, fail = [], 0
    for r in PROJECT_RULES:
        ok, ev = r["fn"](root)
        status = "N/A" if ok is None else ("PASS" if ok else "FAIL")
        if status == "FAIL": fail += 1
        res.append({"id": r["id"], "desc": r["desc"], "status": status,
                    "evidence": ev if isinstance(ev, list) else [ev]})
    if as_json:
        print(json.dumps({"fail": fail, "rules": res}, ensure_ascii=False, indent=1)); return 1 if fail else 0
    for x in res:
        print("%s [%s] %s" % ({"PASS": "✅", "FAIL": "❌", "N/A": "➖"}[x["status"]], x["id"], x["desc"]))
        for e in x["evidence"][:20]:
            print("      %s" % e)
    npass = sum(1 for x in res if x["status"] == "PASS")
    nna = sum(1 for x in res if x["status"] == "N/A")
    print("\n通过 %d · 失败 %d · 不适用 %d" % (npass, fail, nna))
    print("⚠️ 只查**可机械比对**的三类声称。查不出「这句话说得对不对」，"
          "更查不出没写下来的声称 —— 那要靠 11 视角评审。")
    return 1 if fail else 0


def run(root, as_json=False):
    if not os.path.isdir(os.path.join(root, 'references')):
        print("UNABLE: %s 看起来不是 product-flow 根目录" % root, file=sys.stderr); sys.exit(2)
    res, fail = [], 0
    for r in RULES:
        ok, ev = r["fn"](root)
        status = "N/A" if ok is None else ("PASS" if ok else "FAIL")
        if status == "FAIL": fail += 1
        res.append({"id": r["id"], "desc": r["desc"], "status": status,
                    "evidence": ev if isinstance(ev, list) else [ev]})
    if as_json:
        print(json.dumps({"fail": fail, "rules": res}, ensure_ascii=False, indent=1))
        return 1 if fail else 0
    npass = sum(1 for x in res if x["status"] == "PASS")
    nna = sum(1 for x in res if x["status"] == "N/A")
    for x in res:
        icon = {"PASS": "✅", "FAIL": "❌", "N/A": "➖"}[x["status"]]
        print("%s [%s] %s" % (icon, x["id"], x["desc"]))
        for e in x["evidence"][:20]:
            print("      %s" % e)
    print("\n通过 %d · 失败 %d · 不适用 %d（分母只算通过+失败 = %d）" %
          (npass, fail, nna, npass + fail))
    if fail:
        print("⚠️ 不一致本身不会让任何产物报错——它只会让照着文档做的人做错，且没人发现。")
    return 1 if fail else 0

# --------------------------------------------------------------- M8 变异自证
MUTATIONS = [
    # 2026-09-17：spec→文档 漂移守卫的两向变异。
    #   ① 手改生成区 → 必须红（防「有人直接改文档，从此文档与 spec 各说各话」）
    #   ② 改 spec 不重跑生成器 → 必须红（防「口径变了文档还是旧的」）
    ("spec-doc-in-sync", "references/competitive-research.md",
     lambda s: s.replace('**门禁**：`scripts/research-gate.py`',
                         '**门禁**：`scripts/被人手改了.py`', 1)),
    ("spec-doc-in-sync", "spec/s2-research.json",
     lambda s: s.replace('"stage": "S2"', '"stage": "S2", "gateInvocation": "改了spec没重跑生成器"', 1)),
    # 2026-09-16：新增产出物→模板对账的两向变异。⭐ 两个方向都要有，否则只证明了一半：
    #   ① 去掉分类 → 必须红（防「新增 output 不分类」静默溜过）
    #   ② 把 template 指到不存在的模板 → 必须红（防「指了但没有」）
    ("output-template-parity", "references/workflow-registry.json",
     lambda s: s.replace('"readiness.md": "template",', '', 1)),
    ("output-template-parity", "references/workflow-registry.json",
     lambda s: s.replace('"readiness.md": "templates/testcases-pack.md"',
                         '"readiness.md": "templates/根本不存在.md"', 1)),
    # ⚠️ 变异用例必须跟着被测对象走。本条曾因目标文本被改写而**静默失效**（变异是 no-op，
    #    门禁报 PASS 看着正常）—— 这正是「变异存活」要抓的东西，只不过存活的是我的测试。
    ("rule-count", "references/interaction-criteria.md",
     lambda s: re.sub(r'（\d+\s*条', '（99 条', s, count=1)),
    ("flag-exists", "SKILL.md",
     lambda s: s + "\n附注：跑 `prd_completeness_check.py --no-such-flag` 即可。\n"),
    # ⭐ 反向：证明散文形态（脚本名后跟反引号包住的参数）现在抓得到
    ("flag-exists", "references/design-quality-gates.md",
     lambda s: s + "\n执行时 `reconcile-gate.py`：`--exempt` 换成 `--no-such-flag` 即可。\n"),
    # ⭐ 反向：.mjs 脚本的参数也必须被检查（此前窗口不在 .mjs 处截断，参数被算到前一个 .py 头上）
    ("flag-exists", "references/design-quality-gates.md",
     lambda s: s + "\n跑 `browser-audit.mjs --no-such-viewport` 即可。\n"),
    ("appendix-letter", "references/s9-quality-gates.md",
     lambda s: s.replace("附件 C", "附件 D")),
    ("ref-exists", "references/s8-testcases.md",
     lambda s: s + "\n方法见 `references/no-such-file.md`。\n"),
    ("gate-catalog", "references/design-quality-gates.md",
     lambda s: s.replace("ai-slop-gate.py", "ai_slop_gate_REMOVED")),
    # 🚨 2026-09-12：六类图规范声称的落位与模板章节之间此前**没人对账** ——
    #   模板重排（本轮就重排过九章）会让规范安静地指向不存在的章节。
    #   两发：改模板（落位消失）/ 改规范（指向不存在的节）—— 两个方向都要红。
    # ⚠️ 第一版变异写的是**改标题文字**（`页面结构`→`页面与信息架构`）—— **没被杀死**。
    #   查清后确认：⭐ 是**变异测错了东西**，不是规则有洞 ——
    #   本规则对数字型落位锚的是**小节号**，改标题文字不该让它红（那会惩罚正常改标题）。
    #   ⇒ 改成**重编号**，那才是真会让「（6.3）」指空的动作。
    ("diagram-slot-anchored", "templates/prd-complete.md",
     lambda s: s.replace("### 6.3 页面结构", "### 6.9 页面结构", 1)),
    ("diagram-slot-anchored", "references/diagram-standards.md",
     lambda s: s.replace("## 6 · 技术架构图 C4（附件 N）",
                         "## 6 · 技术架构图 C4（附件 Z9）", 1)),
    ("gate-count", "SKILL.md", lambda s: s + "\n本流水线共有八道门禁。\n"),
    # 🚨 2026-09-12：量程第三次被发现开小了（这次漏的是**图源**）。
    #   ⭐ 加这一发是因为：我扩完量程第一次自验时选中了非规范句式的那张图 ⇒ 没红，
    #     「扩了量程」和「扩了个死的」在产物上一模一样。这发变异专门钉住图源在量程内。
    ("gate-count", "templates/diagrams/product-architecture.example.d2",
     lambda s: re.sub(r'\d+(?= 道确定性门禁)', lambda m: str(int(m.group()) + 1), s, count=1)),
    # 🚨 2026-09-09 第五轮：给**字面量定位段**这条新分支配靶 ——
    #   量程扩了却没有变异守着，等于「没人守的判据」（本仓 §14.4 的原话）。
    ("no-positional-window", "scripts/retro-gate.py",
     lambda s: s + "\n\ndef _mutant_probe(md):\n    return md.find('观察周期依据')\n"),

    # ⭐ 反向：加了「哪一道」的排除后，必须证明**紧邻排除词的真实声称仍能被抓到**。
    ("gate-count", "references/design-quality-gates.md",
     lambda s: s + "\n先想清楚该跑哪一道门禁；本 SOP 共有三道门禁。\n"),
    ("perspective-count", "references/s5-s6-design.md",
     lambda s: re.sub(r'（\d+\s*视角', '（77 视角', s, count=1)),
    ("selftest-claim", "scripts/visual-spec-gate.py",
     lambda s: s.replace('--self-test', '--self-TEST-removed')),
    # ⚠️ 2026-09-20:SOP 详表(每阶段门禁栏)按渐进式披露外移到 references/stage-playbook.md,
    #    这两条变异靶随被测对象一起搬到 playbook(SKILL 段里已无这些门名,留在 SKILL 上会变 no-op)。
    ("gate-stage-match", "references/stage-playbook.md",
     lambda s: s.replace("`figma-editability-gate.py` 每批写入后跑", "某道门 每批写入后跑")),
    # ⚠️ 变异必须跟着被测对象走：ai-slop-gate 同时挂在 playbook 的 S5 与 S6 两行，
    #    只改一处另一处仍在 → 规则照样 PASS,变异存活。⭐ 要制造「没挂在任何阶段」须**全部**抹掉。
    ("gate-wired", "references/stage-playbook.md",
     lambda s: s.replace("ai-slop-gate.py", "某道门.py")),
    ("iron-rule-seq", "references/iron-rules.md",
     lambda s: re.sub(r'^20\. ', '18. ', s, count=1, flags=re.M)),
    ("single-source", "SKILL.md",
     lambda s: s + "\n本流程的全局 NFR 最小集是四类。\n"),
    # 🚨 2026-09-12：本发曾因章序重排（方案 A）变成**空操作** —— 靶锚的是 `### 3.2 功能清单`，
    #   而功能清单已随三章→六章变成 `### 6.2`。harness 当场报「变异是 no-op，用例失效」。
    #   ⭐ 这正是它该有的样子：**改了结构而没改靶，会让一发变异静默失效**，
    #     而在输出上与「被杀死」长得一模一样（若没有 no-op 检测的话）。
    #   ⇒ 靶改锚**功能清单**这个名字本身，⛔ 不锚章号 —— 章号会随重排变，名字不会。
    ("template-vs-skill", "templates/prd-complete.md",
     lambda s: re.sub(r'(###\s*[\d.]+\s*功能清单)', r'\1\n> 用 Mind Map 画。', s, count=1)),
    # selftest-count-measured 的两个方向：数字对不上 / 实测过期。
    # ⚠️ 依赖工作树里有 references/.selftest-measured.json（copytree 会带上）——
    #   没有它时基线本来就红，变异结果是噪声（09-01 教训：审计前先确认基线绿）。
    ("selftest-count-measured", "references/design-quality-gates.md",
     lambda s: re.sub(r'\d+(\s*个用例)', r'999\1', s, count=1)),
    # ⭐ 反例两个口径此前在量程外（2026-09-09 独立复核揪出）：文档写 351/332 而实测早已不同，
    #   三处口径互不相同且无人守。两个口径各打一发，证明扩量程后它们真的承重。
    ("selftest-count-measured", "references/design-quality-gates.md",
     lambda s: re.sub(r'按「期望非零退出码」\d+ 个', '按「期望非零退出码」999 个', s, count=1)),
    ("selftest-count-measured", "references/design-quality-gates.md",
     lambda s: re.sub(r'按标题带「反例」\d+ 个', '按标题带「反例」888 个', s, count=1)),
    ("selftest-count-measured", "references/.selftest-measured.json",
     # 实测文件里某个脚本的 sha 与磁盘不符 = 「改了没重测」（过期判据锚内容不锚 mtime）
     lambda s: re.sub(r'"[0-9a-f]{40}"', '"%s"' % ('0' * 40), s, count=1)),
    # ── 2026-09-06 补：以下 12 条规则此前在本表**一条用例都没有** ——
    #    它们的「反向测过」都是立规则当天的一次性动作，从没变成持久守卫。
    #    从没被反向测过的判据和不存在的判据效果没区别；一次性测过的会退化成前者。
    ("self-flag-exists", "scripts/chain-gate.py",
     # 提示语把人指向 --helpp，而它自己会拒绝 --helpp（三处实测缺陷的原始形态）
     lambda s: s.replace('用法见 --help"', '用法见 --helpp"', 1)),
    ("template-vs-gate", "templates/prd-complete.md",
     # B.2 小节里不再有任何 F-xx（判据 grep 的是 F-xx 不是列名 ——
     # 第一版变异只改列名，单元格里的 F-02 还在，变异整个是无效的）
     lambda s: (lambda i: s[:i] + s[i:].replace('F-02', 'F-99'))(s.index('## B.2'))),
    ("crash-is-unable", "scripts/retro-gate.py",
     # 结构半边（CG_FAST 下唯一在跑的半边）：入口不再被兜底包住
     lambda s: s.replace('\n    _main_guarded(_entry)', '\n    _entry()')),
    ("boundary-on-green", "scripts/retro-gate.py",
     # 绿的时候一句边界都不说（⚠️/⛔ 全没了；自证段本来就被剥掉，不影响判定范围）
     lambda s: s.replace('⚠', '').replace('⛔', '')),
    ("gate-registered", "scripts/gate-run.py",
     lambda s: s.replace("'reconcile-gate.py': STD,", "", 1)),
    ("exit-semantics-declared", "scripts/gate-run.py",
     lambda s: s.replace("'mock-seam-gate.mjs': STD,", "", 1)),
    ("script-count", "references/design-quality-gates.md",
     lambda s: s + "\n附注：本 skill 共 999 个脚本。\n"),
    ("template-literal-backtick", "scripts/_argv.mjs",
     # 模板在「作者以为是注释」的行里被反引号提前闭合（第七次复发的那个形态）
     lambda s: s + "\nconst _MUT = `\n// 注释里的 ` 提前闭合\n`;\n"),
    ("gate-reads-template", "tests/fixtures/filled/retro.md",
     # 「填好内容」的夹具被截成空壳 → 门禁在它上面必须红出来（承重的那一半）
     lambda s: s[:80]),
    ("coding-standards-linked", "references/s9-quality-gates.md",
     lambda s: s.replace('coding-standards', 'coding-stds')),
    ("reference-reachable", "SKILL.md",
     lambda s: s.replace('keyboard-contracts.md', 'keyboard-contracts-REMOVED.md')),
    # module-ownership:从阶段路由中抹掉一份真实参考 → 它变成无主参考 → 本条红。
    # ⛔ 不变异本脚本里的 MODULE_INFRA_REFS：自证子进程执行的是原脚本、只把 dst 当输入根，
    #    改副本里的 Python 常量不会被加载，过去那发因此一直是假靶。
    ("module-ownership", "SKILL.md",
     lambda s: s.replace("references/s2-research.md", "references/s2-research-REMOVED.md", 1)),
    # track-temperature-declared:把某模块 track 改成非法值 → 本条红
    ("track-temperature-declared", "references/workflow-registry.json",
     lambda s: s.replace('"track": "doc"', '"track": "bogus"', 1)),
    ("scripts-parse", "scripts/taste-memory.py",
     lambda s: s + "\ndef broken(:\n"),
    # gate-record-fields：读错字段＝判据永远看不见真记录（2026-09-09 我自己犯过）
    ("gate-record-fields", "scripts/flow-metrics.py",
     lambda s: s.replace(".get('verdict')", ".get('passed')", 1)),
    # no-positional-window 两个方向各一发（形状回潮时必须当场报红）。
    # ⚠️ 变异必须注入到**自证段之前**：本规则有意只查判据代码（自证段构造夹具字符串
    #    时用 `GOOD.index('## x')` 是正当的）——追加到文件末尾会落在被排除的区段里，
    #    于是变异存活。⭐ 第一版就是这么写的，自证当场把它抓了出来。
    ("no-positional-window", "scripts/taste-memory.py",
     lambda s: s.replace("\ndef self_test():",
                         "\ndef _w(md, i):\n    return md[i:i + 1200]\n\ndef self_test():", 1)),
    ("no-positional-window", "scripts/taste-memory.py",
     lambda s: s.replace("\ndef self_test():",
                         "\ndef _w2(md, i):\n    return md.find('## ', i)\n\ndef self_test():", 1)),
    # 🚨 2026-09-09 第五轮：`\b` 在下划线前不成立 ⇒ `s[:2000]` 抓得到、`_s[:2000]` 逃逸。
    #   而本文件当时就住着一条活违例（gate_files 里的 `_s[:2000]`），规则却报全绿。
    ("no-positional-window", "scripts/taste-memory.py",
     lambda s: s.replace("\ndef self_test():",
                         "\ndef _w3(_md, i):\n    return _md[i:i + 1200]\n\ndef self_test():", 1)),
    # 🚨 2026-09-10 codex #14：给「名册唯一正本」这条新规则配靶 ——
    #   量程加了却没人守，等于又造了一条装饰性规则。
    # 🚨 2026-09-10：**变异覆盖审计**（枚举 42 条规则各有没有靶）抓到两条无守卫的，
    #   其中 `section-parser-single-source` 是我自己刚立的 —— **立完忘了配靶**。
    #   ⭐ 一条没人守的规则，和没有这条规则在输出上是一样的（全绿）。
    ("section-parser-single-source", "scripts/taste-memory.py",
     lambda s: s + "\n\ndef _own_section(md):\n"
                   "    return re.search(r'^#{1,3}\\s', md, re.M)\n"),
    # `gate-pairing-declared` 同样无靶：删掉配对表里的一条，某道门就变成「沉默地没配对」。
    # ⚠️ 第一版这条靶的变异串 `('definition-gate.py',` **在配对表里根本不存在**
    #   （表里是双引号 `("definition-gate.py", …`）—— 又一个**空操作靶**，
    #   ⭐ 「变异打错了靶子」本会话第四次。⇒ 用表里真实的写法。
    ("gate-pairing-declared", "scripts/consistency-gate.py",
     lambda s: s.replace('("retro-gate.py", "retro.md"', '("retro-gate-GONE.py", "retro.md"', 1)),

    # 🚨 2026-09-10：给 `doc-symbols-exist` 配靶 —— 这条规则治的正是
    #   「文档点名一个不存在的函数」，那它自己必须有人守。
    ("doc-symbols-exist", "scripts/taste-memory.py",
     lambda s: s + "\n\n# 说明：见 `never_defined_helper()` 的实现。\n"),

    # 🚨 2026-09-11：本会话**第三次**「立完规则忘配靶」（前两次 section-parser-single-source /
    #   gate-pairing-declared）。⭐ 靶必须打在**实测输入**上 —— 本规则读的是 progress jsonl，
    #   源码怎么改都动不了它（这与 selftest-count-measured 同型，那条的靶就是 measured.json）。
    # ⭐ 本条的靶：把变异表里某条 rid 写错一个字 —— 那条规则就此「沉默地没人守」，
    #   而在它自己的输出里看不出任何区别（全绿）。这正是本规则存在的理由。
    # 🚨🚨 第一版这发是**空操作**，形状是本会话最刁的一次：
    #   lambda 的搜索串**字面出现在本文件里**（就是它自己），而本条又排在真靶之前 ⇒
    #   `replace(..., 1)` 打中的是**自己的搜索串**，把 lambda 变成 no-op，
    #   真正的 `("help-exits-zero", …)` 那条纹丝不动 ⇒ 规则照样绿，harness 判「未被杀死」。
    #   ⭐ 本会话第五次「变异打错靶子」，前四次都是「串不存在」，这次是**串存在两份，
    #     第一份是变异自己**。⇒ 拼接构造，让搜索串不以字面形态出现在本文件里。
    ("every-rule-has-a-guard", "scripts/consistency-gate.py",
     lambda s: s.replace('("help-exits-' + 'zero", "scripts/retro-gate.py",',
                         '("help-exits-' + 'zero-TYPO", "scripts/retro-gate.py",', 1)),
    # 靶：把一条已锚定的反例退化成「只断言退出码」——棘轮必须立刻发现
    ("negative-case-pins-criterion", "scripts/g75-freeze-gate.py",
     lambda s: s.replace("rc == 1 and '缺期限' in out_d", "rc == 1", 1)),
    ("no-always-true-assertion", "scripts/taste-memory.py",
     lambda s: s + "\n\ndef _always():\n    return (1 == 2) or True\n"),
    ("gate-has-negative", "references/.selftest-measured.json",
     lambda s: s.replace('"negNumeric": 1, "negLabel": 1', '"negNumeric": 0, "negLabel": 0', 1)),
    ("gate-roster-single-source", "scripts/taste-memory.py",
     lambda s: s + "\n\nimport glob as _g2\n"
                   "def _own_roster(root):\n"
                   "    return _g2.glob(root + '/scripts/*-gate.py')\n"),
    # ⭐ 第三发打 **.mjs**：量程按语言切一刀的话，9 个 .mjs 门禁整片在外
    #   （2026-09-09 独立复核指出；本仓自己的注释写着「门禁是不是门禁跟语言无关」）。
    ("no-positional-window", "scripts/_argv.mjs",
     lambda s: s + "\nexport function _w(md, i) { return md.slice(i, i + 1200); }\n"),
    ("no-http-in-operations", "templates/spec/operations.json",
     lambda s: s.replace('"op": "listTasks",', '"op": "listTasks", "http": "GET /tasks",', 1)),
    # ⚠️ 原靶串在旧六列对照表里,该表已删(错误旧表会被照抄)——靶改新表的表现策略行,
    #   把它变异成「第二列=Skeleton」的独立状态行,正中判据 ^\|[^|]*\|\s*Skeleton\s*\|
    ("skeleton-not-a-state", "templates/interaction-spec.md",
     lambda s: s.replace("| ↳ **表现策略** | ①的一部分 |", "| ↳ 骨架屏 | Skeleton |", 1)),
    ("help-exits-zero", "scripts/retro-gate.py",
     lambda s: s.replace("'--help' in sys.argv", "'--HELP-REMOVED' in sys.argv", 1)),
    # intent.md 已有 SKILL 与技术研究参考两条入口。harness 对参考文档同步变异，
    # 真正删除全部路由；不能把删掉其中一条后仍 PASS 误认成规则漏检。
    ("stage-artifact-wired", "SKILL.md",
     lambda s: s.replace("intent.md", "intent-GONE.md")),
    # iron-rule-mapped：映射表是「压缩层覆盖可核对」的唯一载体，每类缺陷各一发。
    ("iron-rule-mapped", "references/iron-rules.md",
     lambda s: s.replace("| 51 | P3 |", "| 51GONE | P3 |", 1)),       # 条目失踪＝铁律被漏
    ("iron-rule-mapped", "references/iron-rules.md",
     lambda s: s.replace("| 51 | P3 |", "| 51 | P99 |", 1)),          # 归到未定义的 P
    ("iron-rule-mapped", "references/iron-rules.md",
     lambda s: s.replace("| 6 | P6 |", "| 6 | P2 |", 1)),             # P6 变成压缩自空集
    ("iron-rule-mapped", "references/iron-rules.md",                   # 无家条目超棘轮上限
     lambda s: s.replace("| 24 | 域:motion-spec.md |",
                         "| 24 | —（为反向测试而存在的假理由，足够长不触发缺原因判据） |", 1)),
    ("iron-rule-mapped", "references/iron-rules.md",
     lambda s: s.replace("| 17 | 域:design-rulesets.md |",
                         "| 17 | 域:design-rulesets-GONE.md |", 1)),  # 域正本不存在
    ("iron-rule-mapped", "SKILL.md",
     lambda s: s.replace("全文 52 条", "全文 53 条", 1)),              # 声称条数漂移
]

# ⛔ 豁免只给「机制上不可能有守卫」的，且必须写明理由；拿不准就别登记（宁可多守一个）。
#   ⚠️ 方向与 _roster.GATE_LIKE_EXEMPT 一致：**默认必须有守卫**，例外要显式登记。
RULE_GUARD_EXEMPT = {}

_MISSING = object()


def self_test(root):
    print("M8 变异自证 —— 逐条把缺陷注入一份临时副本，门禁必须抓到那一条\n")
    base = run_silent(root)
    base_bad = run_silent(root, ids=True)
    print("  基线（未变异）：失败 %d 条" % base)
    # 🚨🚨 2026-09-09 第二轮独立复核揪出的**元层假绿**（本轮最严重一条）：
    #   基线此前**只打印、不断言**。而任何一条规则在基线上就红时，
    #   针对它的变异必然报 FAIL ⇒ 被读成「被杀死」——**变异什么都没证明**。
    #   ⭐ 实证：干净 clone 上基线本来就有 1 条红（缺 .selftest-measured.json），
    #   于是三发 selftest-count-measured 变异**全部是空转**，而 harness 打印
    #   「✅ 变异全部被杀死：这道门在测东西」。其中一发的正则根本不匹配文档写法，
    #   它「被杀死」纯属基线红的副产物。
    #   ⛔ 本文件第 1705 行的注释早就写着这条纪律（「审计前先确认基线绿」），
    #   **写下了却没有执行** —— 现在把它变成断言。
    # 🚨🚨 2026-09-09 第五轮末自查：**「基线全绿才跑变异」制造了一个自指振荡**。
    #   实测同一棵干净树连跑五次：810 → 747 → 810 → 747 → …，**每跑一次翻一次**。
    #   回路是这样闭合的：
    #     本门的用例数包含变异段(63 条) → 变异段在基线不绿时整体中止 →
    #     `selftest-count-measured` 在「文档数 ≠ 实测数」时红 →
    #     而那个实测数**正是上一次运行写下的**（含或不含那 63 条）→ 下一次必然对不上。
    #   ⭐ 后果：文档里的用例数**永远稳不下来**，那条规则一半时间是红的，
    #     而一个 clone 下来的人第一次跑得到 810、第二次得到 747 —— 两个数都「真」。
    #   ⇒ 绿基线断言**收窄到逐规则**：一发变异打的是规则 R，就只要求 **R 在基线上绿**。
    #     其余规则红不红，不影响这发变异的可归因性（它只看 R 有没有变红）。
    #     这样变异段**不再整体中止**，本门用例数与基线状态解耦，振荡消失。
    #   ⛔ 被跳过的那几发仍然**逐条打印并计入用例**（保持计数恒定），
    #     且**不许算成「被杀死」** —— 那正是二轮复核揪出的元层假绿。
    if base != 0:
        print("  ⚠️ 基线有 %d 条红：%s" % (base, "、".join(sorted(base_bad)) or "(取不到 id)"))
        print("     针对这些规则的变异会被**跳过**（它们证明不了任何事）；")
        print("     其余规则的变异照跑 —— 基线红不该让整轮变异测试作废。")
    ok = True
    _skipped = []
    for rid, rel, mut in MUTATIONS:
        if rid in base_bad:
            # ⛔ 这一发证明不了任何事：目标规则在基线上就红，变异后照样红。
            # 🚨 2026-09-12 查清的一桩悬案：这里原本用 ✗，而 selftest-all 把 ✗ 当**失败**记号
            #   ⇒ 「基线红所以跳过」被数成 4 个失败。⭐ 一个记号两个含义、严重性相反
            #     （真的「变异没被杀死」也是 ✗）—— 这正是「一值两消费方安全方向相反」。
            #   ⇒ 跳过改用 ⊘。⛔ 仍然打印、仍然计数为一条用例 —— 跳过必须可见，
            #     只是不许被算成失败（也不许被悄悄抹掉）。
            print("   ⊘ %-22s 基线上本来就红 ⇒ **这发变异跳过，不算被杀死**" % rid)
            _skipped.append(rid)
            continue
        tmp = tempfile.mkdtemp(prefix="cg-")
        dst = os.path.join(tmp, "product-flow")
        shutil.copytree(root, dst)
        # 🚨 2026-09-09：`selftest-count-measured` 的判据**依赖**实测文件；干净 clone 上
        #   它不存在 ⇒ 规则返回 N/A ⇒ 针对它的三发变异全部空转（绿基线断言一上线就暴露了）。
        #   ⭐ 变异要测的是**规则本身**，不是这台机器有没有跑过 selftest。
        #   ⇒ 副本里先补一个最小实测文件，让判据有依据可判；本机已有则原样用。
        # ⚠️ 与上面同理：本规则的判据依赖实测生成物。副本里合成一份「全部达标」的记录，
        #   让这份环境本身是绿的 —— ⛔ 基线红的话这发变异证明不了任何事（本会话已犯过一次）。
        if rid == 'gate-has-negative':
            _pf = os.path.join(dst, 'references', '.selftest-measured.json')
            io.open(_pf, 'w', encoding='utf-8').write(json.dumps({"perGate": {
                _g: {"cases": 3, "negNumeric": 1, "negLabel": 1} for _g in gate_names(dst)}},
                ensure_ascii=False))
        if rid == 'selftest-count-measured':
            _mf = os.path.join(dst, 'references', '.selftest-measured.json')
            if not os.path.exists(_mf):
                _doc = read(os.path.join(dst, 'references', 'design-quality-gates.md')) or ''
                _m1 = re.search(r'(\d+)\s*个用例', _doc)
                _m2 = re.search(r'按「?期望非零(?:退出码)?」?\s*(\d+)\s*个', _doc)
                _m3 = re.search(r'按标题带「反例」\s*(\d+)\s*个', _doc)
                # 🚨 2026-09-09 第三轮独立复核揪出：合成靶的 `shas` 此前只放一个假键，
                #   于是**全部脚本的 sha 都对不上，规则在变异之前就已经 FAIL** ——
                #   这 4 发变异全部空转，而 harness 判它们「被杀死」。
                #   ⭐ 批①的绿基线断言只打在**顶层**基线上，没打在它自己新造的
                #   **逐发环境**里 —— 同一个缺陷在同一个修复里原样复发。
                #   ⇒ 合成靶必须用**真实 sha**（照 selftest-all 的算法逐个算），
                #     让这份环境本身是绿的，变异才有意义。
                import hashlib as _hl
                _shas = {}
                for _d in ('scripts',):
                    for _n in sorted(os.listdir(os.path.join(dst, _d))):
                        if not _n.endswith(('.py', '.mjs')):
                            continue
                        _p2 = os.path.join(dst, _d, _n)
                        if b'--self-test' not in io.open(_p2, 'rb').read():
                            continue
                        _shas[_n] = _hl.sha1(io.open(_p2, 'rb').read()).hexdigest()
                io.open(_mf, 'w', encoding='utf-8').write(json.dumps({
                    "measuredAt": "2026-01-01T00:00:00", "scripts": len(_shas),
                    "cases": int(_m1.group(1)) if _m1 else 1,
                    "negativesByExpectation": int(_m2.group(1)) if _m2 else 0,
                    "negativesByLabel": int(_m3.group(1)) if _m3 else 0,
                    "failures": 0, "failedScripts": [], "unableScripts": [],
                    "cachedScripts": [], "disagree": [],
                    # ⚠️ 真实 sha（见上）：既让环境本身绿，也保证另一发变异
                    #   （靶就是本文件、要替换掉一个 40 位 sha）不是 no-op。
                    "shas": _shas}, ensure_ascii=False))
        p = os.path.join(dst, rel)
        s = read(p)
        if s is None and rel.endswith('.selftest-measured.json'):
            # 🚨 2026-09-09（独立复核揪出）：这个靶是 **gitignore 的运行生成物** ——
            #   本机有、**任何新 clone 上没有** ⇒ 元门禁自证在全新环境必然失败，
            #   而我历次「干净 worktree 复证」都手工把它拷了进去，
            #   **前置条件根本没复现**，于是这个洞被自己的验证方法掩盖了整整两个窗口。
            #   ⭐ 对一个要分发的 skill，「只在作者机器上绿」等于没绿。
            #   ⇒ 靶不存在时就地造一个最小合法的：变异测的是**规则**，不是这台机器。
            #   ⚠️ 最小靶必须**含变异要改的那个东西**（这里是 40 位 sha）——
            #   否则变异变成 no-op，自证从「靶不存在」换成「用例失效」，一样红。
            _sha = 'a' * 40
            s = json.dumps({"measuredAt": "2026-01-01T00:00:00", "scripts": 1,
                            "cases": 1, "failures": 0, "failedScripts": [],
                            "unableScripts": [], "cachedScripts": [], "disagree": [],
                            "perScript": [{"file": "consistency-gate.py",
                                           "sha": _sha, "cases": 1}]},
                           ensure_ascii=False)
            io.open(p, 'w', encoding='utf-8').write(s)
        if s is None:
            print("  ❌ %-20s 变异目标不存在: %s" % (rid, rel)); ok = False; continue
        mutated = mut(s)
        # ⚠️ **变异如果没真改到文件，它就不是「被杀死」也不是「存活」，它是坏的。**
        #    本自证两次因为被测文本被改写而让变异变成 no-op，门禁照报 PASS —— 
        #    也就是说「测试没在测东西」这件事，发生在了测「测试有没有在测东西」的那层。
        #    不加这道守卫，自证本身就是假绿。
        if mutated == s:
            print("  ❌ %-20s **变异是 no-op**（目标文本已改写）—— 用例失效，先修用例" % rid)
            ok = False; shutil.rmtree(tmp, True); continue
        io.open(p, 'w', encoding='utf-8').write(mutated)
        if rid == 'stage-artifact-wired':
            # 与判据的路由量程一致，仅改临时副本；正常多入口仍应被允许。
            for ref in glob.glob(os.path.join(dst, 'references', '*.md')):
                original = read(ref) or ''
                updated = mut(original)
                if updated != original:
                    io.open(ref, 'w', encoding='utf-8').write(updated)
        out = subprocess.run([sys.executable, os.path.abspath(__file__), dst, '--json'],
                             env=dict(os.environ, CG_FAST='1'),
                             capture_output=True, text=True)
        try: data = json.loads(out.stdout)
        except Exception:
            print("  ❌ %-20s 门禁自身崩了" % rid); ok = False; shutil.rmtree(tmp, True); continue
        st = next((x["status"] for x in data["rules"] if x["id"] == rid), "?")
        killed = (st == "FAIL")
        ok &= killed
        print("  %s %-20s 注入到 %-38s → 该条 %s" %
              ("✅" if killed else "❌", rid, rel, st))
        shutil.rmtree(tmp, True)
    # ===== 2026-09-10：数字对不上时，诊断必须说清「量的是哪个总体」 =====
    # 🚨 实证起点：并行会话两个**未提交**文件（receipt-check.py + evidence-receipt.json）
    #   让工作树实测 879，而 clone 实测 869 —— 本条报的是「文档数字过期」。
    #   判决没错，**诊断错了**：照着它改文档，会把 clone 口径的正确数字改成错的。
    #   ⛔ 成对：树脏**不豁免**（判决仍红），否则真的文档漂移能躲在脏树后面。
    # ⚠️ 第一版这里只有 want_in：于是「不加那句归因」这条用例的**断言查的是基础消息在不在**，
    #   名字说的和它量的不是一回事 —— 把归因整段删掉它照样绿。⇒ 补 want_not_in。
    def _tdcase(name, tree_diff, want_in, want_fail=True, want_not_in=None, _head="abc1234"):
        nonlocal ok
        _d = tempfile.mkdtemp(prefix="cg-td-")
        _r = os.path.join(_d, "product-flow")
        shutil.copytree(root, _r)
        io.open(os.path.join(_r, 'references', 'doc.md'), 'w', encoding='utf-8').write(
            "自证共 **1 个用例**\n")
        _payload = {"measuredAt": "2026-09-10T00:00:00", "scripts": 1, "cases": 999,
                    "headAt": _head,
                    "failures": 0, "failedScripts": [], "unableScripts": [],
                    "cachedScripts": [], "disagree": [], "shas": {},
                    "negativesByExpectation": 0, "negativesByLabel": 0}
        if tree_diff is not _MISSING:
            _payload["treeDiff"] = tree_diff
        io.open(os.path.join(_r, 'references', '.selftest-measured.json'),
                'w', encoding='utf-8').write(json.dumps(_payload))
        _v, _msg = r_selftest_count(_r)
        _hit = ((_v is False) == want_fail and want_in in _msg
                and (want_not_in is None or want_not_in not in _msg))
        ok &= _hit
        print("  %s %-20s %s" % ("✅" if _hit else "❌", "measured-population", name))
        if not _hit:
            print("     实得 verdict=%r msg=%s" % (_v, _msg[:200]))
        shutil.rmtree(_d, True)

    _tdcase("树脏 → 仍红，但点名差异路径并给出 clone 复核命令",
            ["skills/product-flow/scripts/receipt-check.py"], "干净克隆")
    _tdcase("树干净（treeDiff=[]）→ 仍红，且**不加**那句归因（别把干净树说成脏的）",
            [], "写「1 个用例」", want_not_in="干净克隆")
    _tdcase("问不到 git（treeDiff=null）→ 仍红，且说「不知道」而非「干净」",
            None, "⛔ 不等于树是干净的")
    # ⭐ 第一版把这条写成「退回原诊断」，跑出来是红的 —— **用例期望写错了，不是代码错**：
    #   字段缺失与显式 null 语义相同（都不知道量在什么树上），沿用「不知道」才诚实。
    #   ⛔ 反面（当成「干净」）会让旧版工具量的数悄悄获得 clone 口径的信用。
    _tdcase("旧版实测文件没有 treeDiff 字段 → 与 null 同义：说「不知道」（⛔ 不当成干净）",
            _MISSING, "⛔ 不等于树是干净的")
    # ⚠️ 2026-09-11：treeDiff 单独存在说不清「跟哪个 HEAD 比的」——
    #   落盘后一次提交，那些文件已经不脏了，读的人却以为还脏着。本仓早有这条：差集判据必须锚 commit。
    # ===== 2026-09-11：no-always-true-assertion 的六条（三真形状 + 三正常写法）=====
    # ⛔ 三条正例是必须的：这条规则是**收紧**，而收紧最容易误伤正确代码
    #   （本仓记过「门不许惩罚正确代码」）。三元、or、and 的正常用法都要证明不报。
    def _atcase(name, snippet, want_fail):
        nonlocal ok
        _d = tempfile.mkdtemp(prefix="cg-at-")
        _r = os.path.join(_d, "product-flow")
        shutil.copytree(root, _r)
        io.open(os.path.join(_r, 'scripts', 'probe_at.py'), 'w', encoding='utf-8').write(
            "def _p(cond, a, b, out, _):\n    return %s\n" % snippet)
        _v, _msg = r_no_always_true(_r)
        _hit = ((_v is False) == want_fail) and (not want_fail or 'probe_at.py' in _msg)
        ok &= _hit
        print("  %s %-24s %s" % ("✅" if _hit else "❌", "no-always-true", name))
        if not _hit:
            print("     实得 verdict=%r msg=%s" % (_v, _msg[:160]))
        shutil.rmtree(_d, True)

    _atcase('反例 `X if C else True` → 红（我今天那行的原形）',
            "(a not in out) if isinstance(_, tuple) else True", True)
    _atcase('反例 `… or True` → 红', "cond or True", True)
    _atcase('正例 正常三元 `a if c else b` → 不报', "a if cond else b", False)
    _atcase('正例 正常条件 `a not in out` → 不报', "a not in out", False)
    _atcase('正例 `cond and True` → 不报（and 的恒真项不改变结果，⛔ 不许顺手一起禁）',
            "cond and True", False)
    _atcase('正例 `X if C else False` → 不报（else 是假，不是恒通过）',
            "(a not in out) if cond else False", False)

    # ⚠️ 规则有 `assert True` 这个分支却没有用例守着 —— 本仓记的「新能力必配新正例」。
    _d3 = tempfile.mkdtemp(prefix="cg-at3-")
    _r3 = os.path.join(_d3, "product-flow")
    shutil.copytree(root, _r3)
    io.open(os.path.join(_r3, 'scripts', 'probe_at3.py'), 'w', encoding='utf-8').write(
        "def _p():\n    assert True\n")
    _v3, _m3 = r_no_always_true(_r3)
    _h3 = (_v3 is False) and ('probe_at3.py' in _m3) and ('assert' in _m3)
    ok &= _h3
    print("  %s %-24s %s" % ("✅" if _h3 else "❌", "no-always-true",
                             '反例 `assert True` → 红（断言什么都没断）'))
    shutil.rmtree(_d3, True)

    # ===== 2026-09-11：gate-has-negative 的五条 =====
    # ⛔ 夹具必须**照着真名册造记录** —— 随便编几个文件名，规则只会说「名册里没被测过」，
    #   那测的是另一条判据。第一版就想这么写，写之前先自问了一句「这测的是哪条」。
    def _ghncase(name, doctor, want_fail, want_in):
        nonlocal ok
        _d = tempfile.mkdtemp(prefix="cg-ghn-")
        _r = os.path.join(_d, "product-flow")
        shutil.copytree(root, _r)
        _rows = [{"file": g, "cases": 3, "negNumeric": 1, "negLabel": 1}
                 for g in gate_names(_r)]
        doctor(_rows)
        _pf = os.path.join(_r, 'references', '.selftest-measured.json')
        io.open(_pf, 'w', encoding='utf-8').write(json.dumps(
            {"perGate": {r["file"]: {k: r[k] for k in ("cases", "negNumeric", "negLabel")}
                         for r in _rows}}, ensure_ascii=False))
        _v, _msg = r_gate_has_negative(_r)
        _hit = ((_v is False) == want_fail) and (want_in in _msg)
        ok &= _hit
        print("  %s %-20s %s" % ("✅" if _hit else "❌", "gate-has-negative", name))
        if not _hit:
            print("     实得 verdict=%r msg=%s" % (_v, _msg[:180]))
        shutil.rmtree(_d, True)

    _ghncase("正例 全部有用例有反例 → 绿", lambda rows: None, False, "全部产出用例")
    _ghncase("反例 某门两个口径都零反例 → 红（只有正例的门没人见过它变红）",
             lambda rows: rows[0].update(negNumeric=0, negLabel=0), True, "都没有反例")
    _ghncase("反例 只剩一个口径有反例 → 仍绿（判据是「至少一个口径」，不是「两个都要」）",
             lambda rows: rows[0].update(negNumeric=0), False, "全部产出用例")
    # ⭐ 这条是本规则存在的理由：09-10 的 UNABLE 降级把「零用例」藏进了 unableScripts。
    _ghncase("反例 某门**零用例** → 红，且消息点破它会被 UNABLE 降级藏起来",
             lambda rows: rows[0].update(cases=0), True, "unableScripts")
    _ghncase("反例 名册里的门在实测记录中缺席 → 红（没被测过 ≠ 通过）",
             lambda rows: rows.pop(0), True, "没有")

    # 缺实测文件 ⇒ UNABLE，⛔ 不折成通过（与 selftest-count-measured 同一裁决）
    _nd = tempfile.mkdtemp(prefix="cg-ghn-na-")
    _nr = os.path.join(_nd, "product-flow")
    shutil.copytree(root, _nr)
    _p2 = os.path.join(_nr, 'references', '.selftest-measured.json')
    if os.path.exists(_p2):
        os.remove(_p2)
    _v2, _m2 = r_gate_has_negative(_nr)
    _h2 = (_v2 is None) and ("不是「通过」" in _m2)
    ok &= _h2
    print("  %s %-20s %s" % ("✅" if _h2 else "❌", "gate-has-negative",
                             "缺实测文件 → UNABLE（⛔ 不是通过、也不是不合格）"))
    shutil.rmtree(_nd, True)

    _tdcase("归因点名测量时的 commit（⛔ 不许只说「HEAD」——HEAD 会动）",
            ["skills/product-flow/scripts/x.py"], "HEAD=abc1234")
    _tdcase("旧文件没记 headAt → 明说「没记下来」，不冒充某个 commit",
            ["skills/product-flow/scripts/x.py"], "没记下来", _head=None)

    # 无效输入必须返 2 而不是 0
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), tempfile.mkdtemp()],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    good = (rc == 2); ok &= good
    print("  %s %-20s 空目录 → 期望 2 实得 %d" % ("✅" if good else "❌", "unable-not-green", rc))
    # 🚨 2026-09-09 第五轮：`gate_files()` 的量程决定了 **8 条元规则**管不管得到一个文件。
    #   造一道措辞刻意避开所有关键词的真门禁（`CANNOT = 1 + 1` 三态退出），
    #   旧实现 **0 条规则**点到它，改成「默认当门禁」后 **8 条**点到。
    #   ⭐ 这条用例守的是**默认方向**，不是某个词表 —— 词表迟早还会差一个词。
    _st_dir = tempfile.mkdtemp(prefix="cg-stealth-")
    _st_root = os.path.join(_st_dir, "product-flow")
    shutil.copytree(root, _st_root)
    io.open(os.path.join(_st_root, 'scripts', 'stealth-check.py'),
            'w', encoding='utf-8').write(
        "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"
        '"""措辞避开全部关键词的东西。"""\n'
        "import sys\nCANNOT = 1 + 1\n"
        "if '--self-test' in sys.argv:\n    sys.exit(0)\n")
    _seen = 'stealth-check.py' in {os.path.basename(x) for x in gate_files(_st_root)}
    # 🚨 2026-09-10 第六轮（E4）：`selftest-claim` **结构性不可能变红** ——
    #   它要求「每道门禁都有 --self-test」，而名单来自 `gate_files()`，
    #   后者第一道前置条件恰恰是 `if '--self-test' not in _s: continue`。
    #   ⭐ **被强制的属性正是被检查的前提条件**：没有自测的真门禁进不了名单，
    #     于是这条规则永远说「全部具备」。上一版的隐身门禁夹具**写着 `--self-test`**，
    #     只覆盖了前置条件之后那一层，天生测不到这个盲区。
    io.open(os.path.join(_st_root, 'scripts', 'stealth2-check.py'),
            'w', encoding='utf-8').write(
        "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n"
        "# 一道真判据，不叫 -gate，也不接受自测。\n"
        "import sys\nCANNOT = 1 + 1\n"
        "if len(sys.argv) < 2:\n    sys.exit(CANNOT)\n"
        "sys.exit(1 if 'X' not in open(sys.argv[1]).read() else 0)\n")
    io.open(os.path.join(_st_root, 'scripts', '_shared_criterion.py'),
            'w', encoding='utf-8').write(
        "def decides(value):\n    return bool(value)\n")
    io.open(os.path.join(_st_root, 'scripts', 'shared-consumer.py'),
            'w', encoding='utf-8').write(
        "import sys\nfrom _shared_criterion import decides\n"
        "if '--self-test' in sys.argv:\n    sys.exit(0 if decides('x') else 1)\n")
    _sc_fn = next(r["fn"] for r in RULES if r["id"] == 'selftest-claim')
    _sc_ok, _sc_evidence = _sc_fn(_st_root)
    _caught = (_sc_ok is False)
    _shared_caught = any('_shared_criterion.py' in str(item)
                         for item in (_sc_evidence if isinstance(_sc_evidence, list)
                                      else [_sc_evidence]))
    print("   %s 没有 --self-test 的真门禁**也会被抓到**（被强制的属性不许当前提条件）"
          % ('✅' if _caught else '❌'))
    ok = ok and _caught
    print("   %s 被其它脚本 import 的 `_*.py` 共用判据**也会被抓到**（不靠文件名白名单）"
          % ('✅' if _shared_caught else '❌'))
    ok = ok and _shared_caught
    shutil.rmtree(_st_dir, ignore_errors=True)
    print("   %s 措辞避开全部关键词的门禁**仍被收进量程**（默认当门禁，不是「像门禁才算」）"
          % ('✅' if _seen else '❌'))
    ok = ok and _seen

    if _skipped:
        # ⛔ 有跳过就不许说「全部被杀死」——那正是二轮复核揪出的元层假绿的措辞。
        print("\n⚠️ %d 发变异**没验**（目标规则基线上就红）：%s"
              % (len(_skipped), "、".join(sorted(set(_skipped)))))
        print("   其余变异%s。⛔ 这不是「全部被杀死」。"
              % ("全部被杀死" if ok else "里有存活"))
        # 🚨🚨 2026-09-10 第六轮独立复核（E6）：措辞是诚实的，**退出码不是** ——
        #   上一版跳过分支只往 `_skipped` 追加，从不动 `ok`，末尾 `return 0 if ok else 1`
        #   ⇒ 打印「⛔ 这不是全部被杀死」的同一次运行**退 0**。
        #   实测两个消费方两个结论：`selftest-all.py` 按打印内容判
        #   「❌ 打印了红却退出 0 …（landmine）」，而按退出码把关的（gate-run / CI）拿到绿。
        #   ⭐ 本仓自己列过这条形状：**会红不阻断＝错觉门**。
        #   ⚠️ 这是 `d573610`（修振荡）引入的：那次把「基线不绿 → return 1」换成了
        #     「跳过 + 继续 + 退 0」——**振荡是修掉了，代价是一条会红不阻断的门**。
        #   ⇒ 有跳过 ⇒ 退 2（没验成）：不是通过，也不冒充「有发现」。
        print("   ⇒ 本次自证退 **2**（没验成）：⛔ 既不是通过，也不是「有发现」。")
        return 2
    else:
        print("\n%s" % ("✅ 变异全部被杀死：这道门在测东西" if ok else
                        "❌ 有变异存活：门禁没在测它声称测的东西"))
    return 0 if ok else 1

def run_silent(root, ids=False):
    """跑一遍自己，返回失败条数；`ids=True` 时返回**失败规则 id 的集合**。

    ⭐ 要 id 是为了把「绿基线」从**全局**改成**逐规则**（见 self_test 的说明）。
    """
    out = subprocess.run([sys.executable, os.path.abspath(__file__), root, '--json'],
                         capture_output=True, text=True)
    try:
        d = json.loads(out.stdout)
        if not ids:
            return d["fail"]
        # ⚠️ 记录里的字段是 `status`（PASS/FAIL/NA），不是 `ok` ——
        #   第一版按 `ok is False` 取，**永远取到空集**：逐规则跳过等于没接上。
        #   ⭐ 与 `gate-record-fields` 治的是同一件事（读错字段＝判据永远看不见真记录），
        #     而我在给那条规则收紧的同一天，自己在这里读错了字段。
        # ⚠️ 2026-09-10 codex 评审 #15：上一版只排除 **FAIL** ⇒ 状态为 **N/A** 的规则
        #   照样跑变异，而 N/A 意味着「这条判据对该对象不适用」——
        #   对它注入变异同样证明不了任何事（变异前后都 N/A）。
        #   ⭐ 「绿基线」要求的是 **PASS**，不是「不是 FAIL」。
        return {r.get('id') for r in d.get('rules', d.get('checks', []))   # 非门禁记录
                if r.get('status') != 'PASS' and r.get('ok') is not True}   # 非门禁记录
    except Exception:
        return set() if ids else -1

def project_self_test():
    """项目模式的变异自证：三条规则各造一个**真实形态**的反例，必须被对应那条抓到。

    ⚠️ 反例都取自 2026-08-31 在 验证项目 上的实测缺陷，不是编的：
      · 查证指针指向的文件里没有那个字段
      · demo 自称「自动生成」而没有任何脚本会写它
      · 文档声称的正本路径已被删除
    """
    ok = True

    def case(name, files, expect_fail):
        nonlocal ok
        # ⚠️ `SKIPPED_OVERSIZE` / `PROJECT_SCANNED` 是**模块级累积态**：
        #   一个进程里连跑多个 case 时，前一个 case 的超大文件会残留到后一个，
        #   于是「这条用例红了」可能是**上一条留下的**。⭐ 真实运行是一次一进程所以看不见，
        #   而自证恰恰是唯一会连跑多次的场合 —— 用例之间必须互不污染。
        global SKIPPED_OVERSIZE, PROJECT_SCANNED
        SKIPPED_OVERSIZE = []
        PROJECT_SCANNED = False
        d = tempfile.mkdtemp()
        for rel, body in files.items():
            f = os.path.join(d, rel)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            io.open(f, 'w', encoding='utf-8').write(body)
        got = set()
        for r in PROJECT_RULES:
            st, _ = r["fn"](d)
            if st is False:
                got.add(r["id"])
        shutil.rmtree(d, ignore_errors=True)
        good = (got == set(expect_fail))
        print(("  ✓ " if good else "  ✗ ") + name +
              ("" if good else "　期望红 %s 实得 %s" % (sorted(expect_fail), sorted(got))))
        ok = ok and good

    GOOD = {
        'docs/prd.md': "正本在 `design/tokens.json`\n判据 `[查证·design/tokens.json contrastPolicy]`\n",
        'design/tokens.json': '{"contrastPolicy": "\u2265 4.5:1"}',
        'out/built.css': "/* 自动生成，勿手改 */\nbody{}",
        'gen.py': "open('out/built.css','w').write(x)",
    }
    case("正例：三条都成立", GOOD, [])

    bad1 = dict(GOOD); bad1['design/tokens.json'] = '{"other": 1}'
    case("反例1 查证指针指向的文件里没有那个关键词（验证项目 实测）", bad1, ["verify-marker"])

    bad1b = dict(GOOD); del bad1b['design/tokens.json']
    case("反例1b 查证指向的文件根本不存在", bad1b, ["verify-marker", "source-of-truth-exists"])

    bad2 = dict(GOOD); del bad2['gen.py']
    case("反例2 自称「自动生成」却没有任何脚本会写它（验证项目 实测）", bad2,
         ["generated-has-generator"])

    bad2b = dict(GOOD)
    bad2b['gen.py'] = "# 用法: node selftest.mjs out/built.css asserts.js\nprint(1)"
    case("反例2b 脚本只是**提到**文件名（注释里），不算有生成器 —— 本规则自己踩过的坑",
         bad2b, ["generated-has-generator"])

    fp1 = dict(GOOD)
    fp1['docs/prd.md'] = GOOD['docs/prd.md'] + "另见 `[查证·CLAUDE.md 约定]` 与 `[查证·7.2 章]`\n"
    fp1['CLAUDE.md'] = "# 项目约定\n随便写点什么"
    case("防假阳性：泛指词「约定」不回文件里搜、章节号 `7.2` 不当文件名", fp1, [])

    bad3 = dict(GOOD)
    bad3['docs/prd.md'] = "正本在 `design/deleted.json`\n"
    case("反例3 声称的正本路径不存在（v1 删了文档没跟）", bad3, ["source-of-truth-exists"])
    # 🚨 2026-09-09：六级声明阶梯此前**零机器守卫**（方案 §13-27「不得越级」）——
    #   阶梯定义得很清楚，但没有任何东西查产物有没有越级，
    #   而这恰恰最容易越：**写「已冻结」比做到冻结容易得多**。
    case("反例4 声称 integrated-frozen 却没有 G7.5 落盘结论（越级）",
         {"report.md": "# 交付\n本轮状态：**integrated-frozen**，三方已冻结。\n"},
         ["claim-ladder-backed"])
    # 🚨 2026-09-09 自查：首版读 `pass` 字段，而 gate-run 真实写的是
    #   verdict/exitCode/ranAt ⇒ 判据读的字段**不存在于真实记录里**，
    #   手写一个 {"pass": true} 就能过（实测确认）。⇒ 认真实 schema。
    case("反例5 手写伪造的落盘（只有 pass:true，没有 verdict/exitCode/ranAt）",
         {"report.md": "# 交付\n状态：**integrated-frozen**\n",
          ".product-flow/gates/g75-freeze-gate.py.json": '{"pass": true}'},
         ["claim-ladder-backed"])
    # 🚨 2026-09-10 自查：全仓 39 条规则里，**只有 `oversize-disclosed` 一条没有任何靶**——
    #   「没人守的判据」这个母题作用在元门禁自己身上。⇒ 补一对。
    #   ⭐ 它的靶不能进 MUTATIONS 表（那是文本变异），必须是**一个真的超大文件**。
    #   ⚠️ 第一版夹具**没隔离**：只写了引用 tokens.json 的 prd.md 而没写那个文件，
    #     于是 `source-of-truth-exists` 一起红 —— 用例测的就不再是它声称测的那条。
    #     ⭐ 隔离＝**在正例基础上只加/挪一样东西**（这条纪律本文件里已经写过两次）。
    case("反例 有文件超过 MAX_BYTES → 必须报出来（静默跳过＝没扫到看起来像没问题）",
         dict(GOOD, **{'docs/huge.md': "x" * (MAX_BYTES + 10)}),
         ["oversize-disclosed"])
    case("正例 没有超大文件 → 不报（判据不是「不许有大文件」，是「跳过必须说出来」）",
         dict(GOOD, **{'docs/small.md': "x" * 1000}),
         [])

    # 🚨 2026-09-10 codex #1（Critical）：G7.5 的 rc=0 只代表「本地六查过」，
    #   不代表可宣 integrated-frozen —— 它自己就打印「冻结上限=本地契约验证通过」。
    case("反例 G7.5 通过但输出写明「冻结上限=本地契约验证通过」→ 仍红（上限不够）",
         {"report.md": "本轮状态：**integrated-frozen**。\n",
          ".product-flow/gates/g75-freeze-gate.py.json":
              '{"verdict":"PASS","exitCode":0,"ranAt":"2026-09-09T10:00:00",'
              '"stdout":"\\u2705 \\u672c\\u5730\\u516d\\u67e5\\u5168\\u8fc7 '
              '\\u26d4 \\u51bb\\u7ed3\\u4e0a\\u9650=\\u672c\\u5730'
              '\\u5951\\u7ea6\\u9a8c\\u8bc1\\u901a\\u8fc7"}'},
         ["claim-ladder-backed"])
    # 🚨 codex #5：裸子串扫描 ⇒ 文档里**解释状态枚举**被报成声称（门惩罚正确产物）。
    case("正例 文档解释状态枚举（反引号内 + 同行有「枚举/含义」）→ 不算声称",
         {"README.md": "状态枚举值包括 `integrated-frozen`，含义见流程规范。\n"},
         [])

    case("正例 声称 integrated-frozen 且 G7.5 落盘 pass=true（不许误伤）",
         {"report.md": "# 交付\n本轮状态：**integrated-frozen**。\n",
          ".product-flow/gates/g75-freeze-gate.py.json":
              '{"gate":"g75-freeze-gate.py","verdict":"PASS","exitCode":0,'
              '"ranAt":"2026-09-09T10:00:00"}'},
         [])

    # ===== 2026-09-09 第五轮独立复核：claim-ladder 三处 =====
    # ⭐⭐ 这条**正例**最贵：判据原来是裸子串 `lvl in text`，于是把本 skill
    #   **自带的** templates/triad-reconciliation.md（写着「…**不是** integrated-frozen」）
    #   抄进空项目就立刻报红 —— 照着 skill 做的人第一天就被判违规。
    # 🚨 2026-09-10 第六轮（F8）：否定词要求**紧邻**命中点 ⇒ 中间隔一个「声称」就漏。
    case("正例 「本文档不会声称 integrated-frozen」→ 不算声称（否定词与命中点之间可隔动词）",
         {"note.md": "本文档不会声称 integrated-frozen，冻结以 G7.5 落盘为准。\n"},
         [])
    # ⛔ 放宽不许变成放行：句中早先出现的否定词**不该**豁免后面的真声称。
    case("反例 「本轮不含新功能，状态：integrated-frozen」→ 仍算声称（前文的否定不豁免）",
         {"note.md": "本轮不含新功能，状态：integrated-frozen。\n"},
         ["claim-ladder-backed"])

    case("正例 否定句「不是 integrated-frozen」→ 不算声称（skill 自带模板就这么写）",
         {"note.md": "冻结结论上限是「本地契约验证通过」，不是 integrated-frozen。\n"},
         [])
    # 🚨 多记录任取一条命中：真记录 FAIL，旁边放一个 .old.json 的 PASS 就判过。
    case("反例 最新记录 FAIL、旧记录 PASS → 仍红（旧记录不许替新结论背书）",
         {"report.md": "本轮状态：**integrated-frozen**。\n",
          ".product-flow/gates/g75-freeze-gate.py.old.json":
              '{"verdict":"PASS","exitCode":0,"ranAt":"2026-09-09T10:00:00"}',
          ".product-flow/gates/g75-freeze-gate.py.json":
              '{"verdict":"FAIL","exitCode":1,"ranAt":"2026-09-09T23:59:00"}'},
         ["claim-ladder-backed"])
    # 🚨 ranAt 原来只测**形状**：形状对但不存在的时间照样当有效证据。
    case("反例 ranAt 是不存在的时间 2026-13-45T99:99 → 仍红（只测形状＝没测）",
         {"report.md": "本轮状态：**integrated-frozen**。\n",
          ".product-flow/gates/g75-freeze-gate.py.json":
              '{"verdict":"PASS","exitCode":0,"ranAt":"2026-13-45T99:99:00"}'},
         ["claim-ladder-backed"])
    case("反例 ranAt 是未来时间 2999-12-31 → 仍红",
         {"report.md": "本轮状态：**integrated-frozen**。\n",
          ".product-flow/gates/g75-freeze-gate.py.json":
              '{"verdict":"PASS","exitCode":0,"ranAt":"2999-12-31T00:00:00"}'},
         ["claim-ladder-backed"])

    # ⭐ 构造空间穷举（语境 × 包裹 × 位置）——说明见 _sweep_lib。
    import tempfile as _tf3, shutil as _sh3
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_claim_recognition, report as _rep3
    _cl = next(r for r in PROJECT_RULES if r["id"] == 'claim-ladder-backed')
    _b3 = _tf3.mkdtemp(prefix='cl-sweep-')
    _n3, _bad3 = sweep_claim_recognition(lambda _d: _cl["fn"](_d)[0], _b3)
    _sh3.rmtree(_b3, ignore_errors=True)
    ok = _rep3('声称 vs 提及识别', _n3, _bad3) and ok
    print("\n%s" % ("✅ 项目模式自证通过" if ok else "❌ 项目模式自证失败：先修它"))
    return 0 if ok else 1



@prule("oversize-disclosed", "被 MAX_BYTES 跳过的文件必须报出来（静默跳过 = 没扫到看起来像没问题）")
def r_oversize(root):
    """⚠️ 2026-09-04 立。`walk_text` 对超大文件是静默 `continue` ——
    一份 2.5MB 的文件被整个跳过，**而依赖它的每条规则照样报绿**。

    ⭐ 判据不是「不许有大文件」（那是另一回事），而是
      **「跳过这件事必须出现在报告里」** —— 否则「没扫到」与「扫过没问题」
      在输出上完全一样，这正是本文件反复在治的那一类。
    ⚠️ 本规则依赖其他规则**先跑过** walk_text 才有数据；它排在最后，
      所以正常顺序下拿得到。拿不到时报 N/A 而不是 PASS。
    """
    if not PROJECT_SCANNED:
        return None, "本轮没有规则扫过文件，无从判断（不当作通过）"
    if not SKIPPED_OVERSIZE:
        return True, "没有文件因超过 %d 字节被跳过" % MAX_BYTES
    return False, ["%s（%.1f MB）超过 MAX_BYTES 被跳过 —— "
                   "依赖它的规则本轮**什么都没扫到**" % (f, n / 1e6)
                   for f, n in sorted(set(SKIPPED_OVERSIZE))]

if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        # ⛔ 此前 --help 会被当成路径参数丢弃、触发 40s+ 的全量检查（Codex 外审实测坐实）。
        #   帮助就是帮助：显示、退出 0，别让求助的人等一次完整审计。
        print(__doc__ or '')
        print("用法: consistency-gate.py [<skill根目录>] [--json] [--self-test] [--project <项目目录>]")
        sys.exit(0)
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = args[0] if args else HERE
    if '--self-test' in sys.argv:
        # 🚨 2026-09-10 自查：`self_test(root) or project_self_test()` 是**短路** ——
        #   E6 的修复让 self_test 在有跳过时返回 2，于是**项目模式整段不再运行**，
        #   它那 15 条用例从计数里消失 ⇒ **用例数又变成状态相关的**
        #   （振荡风险以新形态回来了，833 → 818）。
        #   ⭐ 这正是复核那句「修复把失效模式换了个触发器」在我自己身上的第二次发生。
        #   ⇒ 两段都必须跑完；退出码取「更严重」的那个（1 有发现 > 2 没验成 > 0 通过）。
        _rc1, _rc2 = self_test(root), project_self_test()
        sys.exit(1 if 1 in (_rc1, _rc2) else (2 if 2 in (_rc1, _rc2) else 0))
    if '--project' in sys.argv:
        i = sys.argv.index('--project')
        if i + 1 >= len(sys.argv):
            print("UNABLE: --project 后要跟项目目录", file=sys.stderr); sys.exit(2)
        sys.exit(run_project(sys.argv[i + 1], '--json' in sys.argv))
    sys.exit(run(root, '--json' in sys.argv))
