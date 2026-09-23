#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零丢失门禁 —— 大改造后，旧的语义单元一条都不许消失。

═══ 为什么需要它 ═══

这个仓已经丢过两次内容，两次都**没有任何东西报错**：

  · 2026-09-10 15:50:14 全仓 `git checkout .` 冲掉 9 个文件的未提交 WIP + README 31 行；
  · 飞书模板分段推送**静默吞掉** `<owner>`、`<AC>`×2 与 C.3 的一整条 ——
    而当时的验收结论写的是「附件 A-M、评审前检查均已通过 CLI 回读」。

⭐ 两次的共同形状：**验的是「在不在」，不是「全不全」**。
  而「全不全」只有拿改动前的基线做差集才判得了。

═══ 判据 ═══

    旧集合 ⊆ 新集合                差集非空 ⇒ 红
    差集里的每一条，要么在改名映射表里有登记，要么就是丢失

⛔ **不登记就算丢失**。否则「改名」会变成「丢失」的万能挡箭牌 ——
  本仓治的正是这类形状。

═══ 抽什么（抽承重的，不抽全文）═══

  Markdown：章节标题 · **表头（列的契约）** · 每行第一列（行的身份）· 判据句（含 ⛔⚠️必须/不得/至少/一律/禁止）
  Python  ：规则 id（@rule/@prule）· 自证用例名（chk 首参）· MUTATIONS 的 rid

⚠️ **诚实边界**：
  1. 它守的是「语义单元没消失」，**不守「内容没被改坏」** ——
     一行判据句被改成相反的意思，字面还在，本门看不出来。那一层靠评审与变异测试。
  2. 正文散文（非判据句）**不在量程内**。全量比对会被换行、重排、措辞微调淹没，
     产出一个没人看的差集 —— 本仓记过：**量错对象比量不到更危险**。
  3. 只认 `.md` 与 `.py`；`.mjs` 无可用 AST（不引依赖，见 ADR-0008）。

用法:
    no-loss-gate.py --snapshot            把当前树抽成基线，写到 references/no-loss-baseline.json
    no-loss-gate.py                       拿当前树与基线做差集
    no-loss-gate.py --self-test           自证（含承重确认：删一条已知内容必须报红）
退出码: 0=零丢失 1=有丢失 2=跑不了（没有基线等）
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import _iter_headings   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join('references', 'no-loss-baseline.json')
RENAMES = os.path.join('references', 'no-loss-renames.md')

# 判据句：带这些记号/词的行是**承重**的，措辞可以润色，但不许整条消失
_VERDICT = re.compile(r'⛔|⚠️|必须|不得|不许|至少|一律|禁止|只许|仅当')


def _norm(s):
    """归一：去空白、去 markdown 强调与反引号。⛔ 不做同义改写。"""
    s = re.sub(r'^\s*>\s*', '', (s or '').strip())
    s = re.sub(r'^#{1,6}\s*', '', s)
    s = re.sub(r'^[-*]\s*\[[ xX]?\]\s*|^[-*]\s+|^\d+[.)]\s+', '', s)
    return re.sub(r'\s+', '', s.replace('**', '').replace('`', '').replace('　', ''))


def _md_units(path, rel):
    """一份 Markdown 的语义单元。"""
    out = []
    src = io.open(path, encoding='utf-8', errors='replace').read()
    lines = src.split('\n')
    for i, line in enumerate(lines):          # 表头 = 下一行是分隔行的那一行
        st = line.strip()
        if not st.startswith('|') or i + 1 >= len(lines):
            continue
        nxt = lines[i + 1].strip()
        if nxt.startswith('|') and re.match(r'^[\s:\-|]+$', nxt.strip('|')):
            out.append(('header', rel, _norm(st)))
    seen_header = {}
    for _ln, _lv, text in _iter_headings(src):
        if text.strip():
            out.append(('heading', rel, _norm(text)))
    for line in src.split('\n'):
        s = line.strip()
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if not cells or re.match(r'^[\s:\-|]+$', s.strip('|')):
                continue          # 表格分隔行
            # 🚨 2026-09-12 立完当场改：第一版把**整行**当语义单元（2086 条），
            #   结果改任何一个单元格整行就「消失」—— 本仓母题「量错对象比量不到更危险」：
            #   它量的是「内容变没变」，而要防的是**结构性丢失**（行没了、列没了、章节没了）。
            #   实测代价：我自己把「28 道门禁」改成 29，整行报丢失，
            #   逼我把一行 300 字的表格原文抄进改名表 —— 那张表会立刻变成垃圾场。
            #   ⇒ 首列＝行的**身份**（行没了才丢）；表头＝**列的契约**（删列才丢）。
            if cells[0]:
                out.append(('cell0', rel, _norm(cells[0])))
            if len(cells) > 1 and all(cells) and not seen_header.get(rel + str(id(out))):
                pass
            continue
        if s and _VERDICT.search(s):
            out.append(('verdict', rel, _norm(s)))
    return out


def _py_units(path, rel):
    """一个脚本的语义单元：规则 id、自证用例名、变异靶 rid。"""
    import ast
    out = []
    src = io.open(path, encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
    except Exception:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in ('rule', 'prule') and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(('rule', rel, a.value))
            if n.func.id in ('chk', 'case', 'check') and n.args:
                a = n.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(('case', rel, _norm(a.value)))
    m = re.search(r'(?m)^MUTATIONS\s*=\s*\[', src)
    if m:
        for rid in re.findall(r'\(\s*"([^"]+)",\s*"', src[m.start():]):
            out.append(('mutation', rel, rid))
    return out


def snapshot(root=None):
    root = root or ROOT
    units = []
    pats = ('SKILL.md', 'references/*.md', 'templates/*.md', 'templates/**/*.md')
    for p in pats:
        for f in glob.glob(os.path.join(root, p), recursive=True):
            rel = os.path.relpath(f, root)
            # 🚨 本门自己的两个控制文件不进量程 —— 基线与改名表是**门的零件**，不是被守的内容。
            #   实测：自证沙箱会覆写改名表，于是那份表自己的标题「消失」⇒ 正例误红。
            #   ⭐ 本仓母题「规则扫到自己的夹具」，这次发生在零丢失门禁上。
            if rel.startswith('.proposals') or os.path.basename(rel).startswith('no-loss-'):
                continue
            units += _md_units(f, rel)
    for f in glob.glob(os.path.join(root, 'scripts', '*.py')):
        units += _py_units(f, os.path.relpath(f, root))
    # 去重但保留出处：同一句话在两个文件里各算一条
    return sorted({(k, r, v) for k, r, v in units if v})


def _load_renames(root):
    """改名映射表。两种写法都认：`旧 → 新` 行，或 `| 旧 | 新 | 理由 |` 表格行。

    🚨 2026-09-12 立完当场踩：我把表写成 markdown 表格，而解析器只认 `→` ——
      **格式对不上，登记等于没登记**，门禁照样红，而登记表看起来是填了的。
      ⭐ 本仓母题「声称 vs 实际」，这次发生在豁免通道自己身上。

    ⛔ 表格写法**必须带理由**（第三列 ≥4 字）：没理由的登记不算登记 ——
      与 `_roster.GATE_LIKE_EXEMPT` 同一纪律，豁免必须写明为什么。
    """
    p = os.path.join(root, RENAMES)
    out = {}
    if not os.path.exists(p):
        return out
    for line in io.open(p, encoding='utf-8'):
        t = line.strip()
        if t.startswith('#'):
            continue
        # 🚨 2026-09-12：判定顺序必须是「先箭头、后表格」——
        #   表格单元里的**值本身可能以 `|` 开头**（例：表头单元 `|事件名|...|`），
        #   先判表格会把一条合法的 `→` 登记切成一堆碎片 ⇒ 登记静默失效。
        #   ⇒ 含**带空格的 ` → `** 即按箭头格式解析，其余以 `|` 开头的才是表格行。
        if ' → ' in t:
            o, _, n = t.partition(' → ')
            if _norm(o):
                out[_norm(o)] = _norm(n)
            continue
        if t.startswith('|'):
            cells = [c.strip() for c in t.strip('|').split('|')]
            if len(cells) < 3 or re.match(r'^[\s:\-|]+$', t.strip('|')):
                continue
            o, n, why = cells[0], cells[1], cells[2]
            if len(why.strip()) < 4:
                continue                  # ⛔ 没写理由 = 不算登记
            if _norm(o):
                out[_norm(o)] = _norm(n)
            continue
    return out


def compare(root=None):
    root = root or ROOT
    bp = os.path.join(root, BASELINE)
    if not os.path.exists(bp):
        return None, ['没有基线 %s —— 本条**没验**：先跑 `--snapshot`。⛔ 不是「通过」' % BASELINE]
    try:
        base = [tuple(x) for x in json.load(io.open(bp, encoding='utf-8'))['units']]
    except Exception as e:
        return False, ['基线读不了（%s）' % e]
    now = snapshot(root)
    # 🚨 按**（类型，值）**比，不按值比：`gate-count` 同时是规则 id 和变异靶 rid，
    #   只按值去重时，改掉规则 id 而靶的 rid 还在 ⇒ 值层面看不出丢失，**承重确认当场变红**。
    #   ⭐ 同一个字符串在不同类型里是**不同的契约** —— 规则 id 没了就是没了，
    #     哪怕别处还有个同名的字符串。
    now_keys = {(k, v) for k, _r, v in now}
    # 改名登记在读取时会经过 `_norm`；当前值也必须同口径归一，否则脚本里的
    # `31 道…` → `34 道…` 会因空格差异被误报成“新名也不在”。
    now_vals = {_norm(v) for _k, _r, v in now}  # 改名目标只按值找（换类型也算落地）
    renames = _load_renames(root)
    lost = []
    for kind, rel, val in base:
        if (kind, val) in now_keys:
            continue
        # 基线里的 Python 变异靶保留原始空格，而登记表键已经 `_norm`；查询也要同口径。
        mapped = renames.get(_norm(val))
        if mapped and mapped in now_vals:
            continue              # 已登记的改名，且新名确实在
        if mapped:
            lost.append('%s〔%s〕登记改名为「%s」但新名**也不在** —— %s' % (kind, rel, mapped, val[:48]))
        else:
            lost.append('%s〔%s〕消失且**未登记改名**：%s' % (kind, rel, val[:56]))
    return (not lost), lost


def _print_boundary():
    """⚠️ 绿的时候也要说清验不了什么 —— 一道不说边界的绿会被当成比它更强的保证。

    ⚠️ 必须定义在 `_self_test` **之前**：`boundary-on-green` 规则剥自证段时
      是从 `def _self_test` 一刀切到文件尾，写在 `__main__` 里会被整段切掉（实测）。
    """
    print('⚠️ 本门**验不了**：内容有没有被改坏（判据句被改成相反的意思、字面还在，本门看不出来）；'
          '也不覆盖正文散文。⛔ 那两层靠评审与变异测试，不要拿本门的绿去替它们背书。')


def _self_test():
    import tempfile
    import shutil
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        ok = ok and bool(c)
        print('  %s %s%s' % ('✅' if c else '❌', n, '' if c else '　' + e))

    units = snapshot()
    chk('能从本 skill 抽出语义单元（>500 条）', len(units) > 500, '实得 %d' % len(units))
    kinds = {k for k, _r, _v in units}
    for need in ('heading', 'cell0', 'verdict', 'rule', 'case'):
        chk('抽到了 %s 类单元' % need, need in kinds)

    def sandbox(mutate):
        d = tempfile.mkdtemp(prefix='noloss-')
        r = os.path.join(d, 'pf')
        shutil.copytree(ROOT, r, ignore=shutil.ignore_patterns('.proposals', '__pycache__'))
        os.makedirs(os.path.join(r, 'references'), exist_ok=True)
        json.dump({'units': [list(u) for u in units]},
                  io.open(os.path.join(r, BASELINE), 'w', encoding='utf-8'), ensure_ascii=False)
        mutate(r)
        res = compare(r)
        shutil.rmtree(d, True)
        return res

    chk('正例：树没动 → 零丢失', sandbox(lambda r: None)[0] is True,
        '实得 %s' % (sandbox(lambda r: None)[1][:2],))

    # ⭐ 承重确认：本仓记过「零发现的量具最可疑」。删一条已知内容，必须报红。
    def _del_heading(r):
        p = os.path.join(r, 'references', 'iron-rules.md')
        s = io.open(p, encoding='utf-8').read()
        h = next(t for _l, _v, t in _iter_headings(s) if t.strip())
        io.open(p, 'w', encoding='utf-8').write(s.replace('# ' + h, '# 换了个完全不同的标题', 1))
    v, bad = sandbox(_del_heading)
    chk('反例①：删掉一个章节标题 → 红（承重确认）',
        v is False and any('未登记改名' in b for b in bad), '实得 %s' % (bad[:2],))

    def _del_verdict(r):
        p = os.path.join(r, 'SKILL.md')
        s = io.open(p, encoding='utf-8').read()
        line = next(l for l in s.split('\n') if _VERDICT.search(l) and len(l.strip()) > 12)
        io.open(p, 'w', encoding='utf-8').write(s.replace(line, '', 1))
    v, bad = sandbox(_del_verdict)
    chk('反例②：删掉一条判据句 → 红', v is False and bad)

    def _del_rule(r):
        p = os.path.join(r, 'scripts', 'consistency-gate.py')
        s = io.open(p, encoding='utf-8').read()
        io.open(p, 'w', encoding='utf-8').write(
            s.replace('@rule("gate-count"', '@rule("gate-count-RENAMED"', 1))
    v, bad = sandbox(_del_rule)
    chk('反例③：改掉一条规则 id → 红（规则 id 是契约，不许静默改名）',
        v is False and any('gate-count' in b for b in bad))

    # 改名登记后应放行 —— ⛔ 但收紧不许误伤：登记了就必须真的放行
    def _rename_with_registry(r):
        _del_rule(r)
        io.open(os.path.join(r, RENAMES), 'w', encoding='utf-8').write(
            '# 改名映射表\ngate-count → gate-count-RENAMED\n')
    v, bad = sandbox(_rename_with_registry)
    chk('正例：改名**已登记** → 放行（⛔ 登记表必须真的起作用）', v is True, '实得 %s' % (bad[:2],))

    # ⛔ 登记了但新名不存在 = 假登记，必须仍红
    def _fake_registry(r):
        p = os.path.join(r, 'scripts', 'consistency-gate.py')
        s = io.open(p, encoding='utf-8').read()
        io.open(p, 'w', encoding='utf-8').write(s.replace('@rule("gate-count"', '@rule("gone"', 1))
        io.open(os.path.join(r, RENAMES), 'w', encoding='utf-8').write(
            'gate-count → 一个根本不存在的新名字\n')
    v, bad = sandbox(_fake_registry)
    chk('反例④：登记了改名但**新名也不在** → 仍红（假登记挡不住）',
        v is False and any('也不在' in b for b in bad))

    def _registry_no_reason(r):
        _del_rule(r)
        io.open(os.path.join(r, RENAMES), 'w', encoding='utf-8').write(
            '| gate-count | gate-count-RENAMED |  |\n')
    v, bad = sandbox(_registry_no_reason)
    chk('反例⑥：登记了改名但**没写理由** → 仍红（⛔ 豁免必须写明为什么）',
        v is False and bad, '实得 %s' % (bad[:1],))

    def _registry_table(r):
        _del_rule(r)
        io.open(os.path.join(r, RENAMES), 'w', encoding='utf-8').write(
            '| 旧 | 新 | 理由 |\n|---|---|---|\n'
            '| gate-count | gate-count-RENAMED | 规则改名，理由充分 |\n')
    v, bad = sandbox(_registry_table)
    chk('正例：**表格写法**且带理由 → 放行（⛔ 两种写法都要认）', v is True, '实得 %s' % (bad[:1],))

    def _pipe_value(r):
        # 值本身以 | 开头（表头单元）——只能用 → 格式登记
        p2 = os.path.join(r, 'SKILL.md')
        t2 = io.open(p2, encoding='utf-8').read()
        # ⚠️ 夹具第一版改的是**行首的 `|`** —— 那会让整行不再被识别为表格行，
        #   等于**删除**而不是改名，用例测的不是它声称测的东西。⇒ 改行内的词。
        lines2 = t2.split('\n')
        hdr = next(lines2[i].strip() for i in range(len(lines2) - 1)
                   if lines2[i].strip().startswith('|')
                   and re.match(r'^[\s:\-|]+$', lines2[i + 1].strip().strip('|') or 'x'))
        w = [c.strip() for c in hdr.strip('|').split('|') if c.strip()][0]
        hdr2 = hdr.replace(w, w + '改名', 1)
        io.open(p2, 'w', encoding='utf-8').write(t2.replace(hdr, hdr2, 1))
        # ⚠️ 改一个词会同时改**表头**与**首列**两个单元 —— 两条都要登记。
        #   门禁报出第二条时，说明它真的在按单元粒度查，而不是按行。
        io.open(os.path.join(r, RENAMES), 'w', encoding='utf-8').write(
            '%s → %s\n%s → %s\n' % (_norm(hdr), _norm(hdr2), _norm(w), _norm(w + '改名')))
    v, bad = sandbox(_pipe_value)
    chk('正例：值以 `|` 开头时用 `→` 格式登记 → 放行（⛔ 先判表格会把它切碎）',
        v is True, '实得 %s' % (bad[:1],))

    d2 = tempfile.mkdtemp(prefix='noloss-nb-')
    os.makedirs(os.path.join(d2, 'references'), exist_ok=True)
    v2, b2 = compare(d2)
    shutil.rmtree(d2, True)
    chk('反例⑤：没有基线 → UNABLE（⛔ 不折成通过）', v2 is None and any('没验' in x for x in b2))

    print('\n%s' % ('✅ 自证通过：旧内容消失会被抓住' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    """⛔ 本门自身崩溃必须退 2，不许和「有丢失」共用退出码 1 —— 本仓红线。"""
    try:
        return fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback
        print('UNABLE: 工具自身异常：%s: %s' % (type(_e).__name__, _e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv:
        print((__doc__ or '').strip()); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    if '--snapshot' in sys.argv:
        u = snapshot()
        os.makedirs(os.path.join(ROOT, 'references'), exist_ok=True)
        io.open(os.path.join(ROOT, BASELINE), 'w', encoding='utf-8').write(
            json.dumps({'units': [list(x) for x in u]}, ensure_ascii=False, indent=1) + '\n')
        import collections
        print('基线已写入 %s' % BASELINE)
        print('语义单元 %d 条：%s' % (len(u), dict(collections.Counter(k for k, _r, _v in u))))
        sys.exit(0)
    _res = []

    def _run():
        _res.append(compare())
    _main_guarded(_run)
    v, bad = _res[0]
    _print_boundary()
    for b in bad[:40]:
        print('  ❌ ' + b)
    if len(bad) > 40:
        print('  ❌ …另有 %d 条' % (len(bad) - 40))
    if v is True:
        print('✅ 零丢失：基线里的语义单元一条都没消失')
    sys.exit(0 if v is True else (2 if v is None else 1))
