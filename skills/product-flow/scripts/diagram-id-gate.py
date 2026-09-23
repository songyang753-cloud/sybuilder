#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""图与表的 ID 对账门 —— 图里不许有表里没有的东西，表里的也不许在图上缺席。

═══ 它补的洞 ═══

模板此前只有一句话在守这件事（6.2 的「地图与下表的 F-xx 必须一一对应」），
**只有一处、只是一句话、没人查**。于是「插了张图」和「这张图对得上」
在产物上长得一模一样 —— 而一张对不上的图比没有图更糟：
它让读的人以为结构已经对齐了。

═══ 三组判据 ═══

**A 组 · 双向集合相等**（差集非空即红）

    图上的 M 集合  ==  6.1 模块设计表的 M 集合
    图上的 F 集合  ==  6.2 功能清单表的 F 集合
    图上的 P 集合  ==  6.3 页面表的 P 集合
    5.2 流程投影表的 F  ⊆  七章功能卡的 F

**B 组 · 颗粒度同族**

    单张图内节点 ID 只允许**一种前缀族** —— `F-01` 与 `FR-001` 并排即越级
    （`FR` 属附件 A，比 `F` 细一层）

**C 组 · 跨章逻辑一致**

    功能卡标了「含 AI」的 F  →  附件 B.3 必须有对应行
    附件 C.1 的每项数据      →  C.5 图/表上有落盘点与删除触发

═══ ⚠️ 诚实边界 ═══

1. 本门守的是「**该有的 ID 在不在、对不对得上**」，⛔ **不守「这张图画得对不对」** ——
   业务表达是否正确只能靠人评审。
2. 图源必须是**文本可解析**的（`.mmd` / `.d2` / `.puml`）。⛔ 图若是 PNG 或在线画板链接，
   节点 ID 提不出来，本门**只能报 UNABLE，不会报通过** —— 这是刻意的：
   拿不到证据时装作通过，比没有这道门更糟。
3. ID 是靠**正则从图源里抓**的（`M-\\d+` / `F-\\d+` / `P-\\d+`）。
   图源里写成别的形态（如 `F01`、`功能一`）本门认不出 —— 已在输出里如实说明。

用法: diagram-id-gate.py <项目目录> [--json] | --self-test
退出码: 0=对得上 1=对不上 2=跑不了（缺 PRD / 缺图源）
"""
import glob
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at    # noqa: E402

ID_PATS = {'M': re.compile(r'\bM-\d+\b'), 'F': re.compile(r'\bF-\d+\b'), 'P': re.compile(r'\bP-\d+\b')}
# ⚠️ 越级族：`FR-001` 比 `F-01` 细一层，属附件 A。两者并排即颗粒度混族。
FINER = re.compile(r'\b(FR|AC|NFR|ASM|TBD|OPEN|DELTA|CHG|OBJ|SEC)-\d+\b')

DIAG_DIRS = ('.product-flow/diagrams', 'diagrams', 'docs/diagrams')
DIAG_EXT = ('.mmd', '.d2', '.puml')


def die(msg):
    print('UNABLE: %s' % msg, file=sys.stderr)
    sys.exit(2)


def find_prd(root):
    for pat in ('PRD*.md', 'prd*.md', '**/PRD*.md', '**/prd*.md'):
        hits = sorted(glob.glob(os.path.join(root, pat), recursive=True))
        if hits:
            return hits[0]
    return None


def diagram_sources(root):
    """图源文件。⛔ 找不到就 UNABLE，不报通过。"""
    out = []
    for d in DIAG_DIRS:
        for e in DIAG_EXT:
            out += sorted(glob.glob(os.path.join(root, d, '**', '*' + e), recursive=True))
    return out


# ⛔ 注释符：d2/mermaid/plantuml 三种图源的注释起始。
_COMMENT_STARTS = ('#', '%%', "'", '//')


def strip_comments(text):
    """🚨 2026-09-12 拿**我自己刚画的六张示例图**跑本门时揪出来的：
    `functional-architecture.example.d2` 被判「混了 F-01 与 FR-001，颗粒度越级」——
    而 `FR-001` 全文只出现在**一行注释**里，那行注释恰恰是在**警告别混族**。

    ⭐ 这是「数『提到』≠『用了』」的又一个实例：注释里的 ID 是**引用**，不是节点。
      ⛔ 而按原来的判据，一份图源只要在注释里解释自己为什么不该混族，就会被判混族 ——
        **门在惩罚正确的写法**，还专门惩罚写了说明的那一份。

    ⇒ 抽 ID 前先剥注释行。⚠️ 只剥**整行注释**，不剥行尾注释 ——
      `A -> B # 见 F-03` 这种行尾写法在三种图源里的转义规则各不相同，
      按行首判定是**确定性**的，按行尾要猜。宁可少剥，不可剥错。
    """
    keep = []
    for line in (text or '').split('\n'):
        t = line.lstrip()
        if t and any(t.startswith(c) for c in _COMMENT_STARTS):
            continue
        keep.append(line)
    return '\n'.join(keep)


def ids_in(text, kind):
    return set(ID_PATS[kind].findall(text or ''))


def table_ids(md, heading_kw, kind):
    """从 PRD 某一节的表格里抓 ID。"""
    seg = section_at(md, heading_kw)
    if seg is None:
        return None
    return ids_in(seg, kind)


def check(root):
    prd = find_prd(root)
    if not prd:
        return None, ['找不到 PRD（%s 下没有 PRD*.md）—— 本门**没验**，⛔ 不是通过' % root]
    md = io.open(prd, encoding='utf-8', errors='replace').read()
    srcs = diagram_sources(root)
    if not srcs:
        return None, ['找不到任何图源（%s 下的 %s）—— 图若只是 PNG，ID 提不出来，'
                      '本门**没验**。⛔ 拿不到证据时装作通过，比没有这道门更糟'
                      % ('、'.join(DIAG_DIRS), '/'.join(DIAG_EXT))]
    bad = []
    # ⭐ 在**唯一的读入处**剥注释：A 组（图上的 M/F/P 集合）与 B 组（混族）一起受益。
    #   注释里提到 `M-99` 不等于这张图有 M-99 这个节点 —— 两组是同一个判断。
    src_text = {p: strip_comments(io.open(p, encoding='utf-8', errors='replace').read())
                for p in srcs}

    # ── A 组：双向集合相等 ──
    for kind, kw, where in (('M', '模块设计', '6.1'), ('F', '功能清单', '6.2'), ('P', '页面结构', '6.3')):
        tab = table_ids(md, kw, kind)
        if tab is None:
            bad.append('A〔%s〕PRD 里找不到「%s」这一节 —— 图对不了账' % (where, kw))
            continue
        dia = set()
        for p, t in src_text.items():
            dia |= ids_in(t, kind)
        if not dia and not tab:
            continue
        only_dia, only_tab = sorted(dia - tab), sorted(tab - dia)
        if only_dia:
            bad.append('A〔%s〕图上有、%s 表里没有：%s —— 图里不许出现表里没有的东西'
                       % (where, where, '、'.join(only_dia)))
        if only_tab:
            bad.append('A〔%s〕%s 表里有、图上没有：%s —— 表里的东西不许在该出现的图上缺席'
                       % (where, where, '、'.join(only_tab)))

    # 5.2 流程投影表的 F ⊆ 七章功能卡的 F
    proj = section_at(md, '流程与功能的对应')
    cards = section_at(md, '详细设计')
    if proj is not None and cards is not None:
        extra = sorted(ids_in(proj, 'F') - ids_in(cards, 'F'))
        if extra:
            bad.append('A〔5.2〕流程投影表里的 %s 在七章功能卡里没有对应的卡' % '、'.join(extra))

    # ── B 组：颗粒度同族 ──
    for p, t in src_text.items():
        finer = sorted(set(m.group(0) for m in FINER.finditer(t)))
        coarse = sorted(ids_in(t, 'M') | ids_in(t, 'F') | ids_in(t, 'P'))
        if finer and coarse:
            bad.append('B〔%s〕同一张图里混了两族 ID：%s 与 %s —— 颗粒度越级'
                       % (os.path.basename(p), '、'.join(coarse[:3]), '、'.join(finer[:3])))

    # ── C 组：跨章逻辑一致 ──
    ai_cards = set()
    if cards is not None:
        for blk in re.split(r'(?m)^###\s', cards):
            if 'AI 能力' in blk or 'AI能力' in blk:
                ai_cards |= ids_in(blk, 'F')
    b3 = section_at(md, '算法与模型需求')
    if ai_cards and b3 is None:
        bad.append('C〔B.3〕功能卡里有含 AI 的功能（%s），但附件 B.3 算法与模型需求整节缺失'
                   % '、'.join(sorted(ai_cards)))

    c1, c5 = section_at(md, '数据清单'), section_at(md, '数据生命周期')
    if c1 is not None and c5 is None and c1.strip():
        bad.append('C〔C.5〕附件 C.1 有数据清单，但 C.5 数据生命周期整节缺失 —— '
                   '删除链路没人画，合规上答不了「删到哪」')

    return (not bad), bad


def _print_boundary():
    """⚠️ 绿的时候也要说清验不了什么。"""
    print('⚠️ 本门**验不了**：图画得对不对（业务表达是否正确只能靠人评审）；'
          '⛔ 图源若不是文本（PNG／在线画板），ID 提不出来，本门报 UNABLE 而**不报通过**；'
          'ID 靠正则抓（`F-\\d+` 等），写成 `F01`／「功能一」本门认不出。')


def _self_test():
    import tempfile
    import shutil
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        ok = ok and bool(c)
        print('  %s %s%s' % ('✅' if c else '❌', n, '' if c else '　' + e))

    GOOD_PRD = """# X PRD
## 六、概要设计
### 6.1 模块设计
| 模块 ID | 名称 |
|---|---|
| M-01 | 甲 |
### 6.2 功能清单
| ID | 功能名称 |
|---|---|
| F-01 | 乙 |
### 6.3 页面结构
| 页面 ID | 名称 |
|---|---|
| P-01 | 丙 |
## 五、业务流程
### 5.2 流程与功能的对应
| 流程节点 | 实现它的 F-xx |
|---|---|
| 甲 | F-01 |
## 七、详细设计
### M: 甲 / F-01: 乙
| AI 能力项 | 内容 |
|---|---|
| 能力类型 | 识别 |
## 附件 B
### B.3 算法与模型需求
| 项 | 内容 |
|---|---|
| 模型选型及理由 | x |
## 附件 C
### C.1 数据清单
| 数据项 | 用途 |
|---|---|
| 甲 | x |
### C.5 数据生命周期图
| 数据项 | 删除触发 |
|---|---|
| 甲 | y |
"""
    GOOD_DIAG = 'flowchart TD\n  M-01 --> F-01\n  F-01 --> P-01\n'

    def sandbox(prd=None, diag=None, no_diag=False):
        d = tempfile.mkdtemp(prefix='dig-')
        io.open(os.path.join(d, 'PRD.md'), 'w', encoding='utf-8').write(prd or GOOD_PRD)
        if not no_diag:
            os.makedirs(os.path.join(d, '.product-flow', 'diagrams'))
            io.open(os.path.join(d, '.product-flow', 'diagrams', 'a.mmd'),
                    'w', encoding='utf-8').write(diag or GOOD_DIAG)
        r = check(d)
        shutil.rmtree(d, True)
        return r

    v, bad = sandbox()
    chk('正例：图与三张表双向相等 → 绿', v is True, '实得 %s' % (bad[:2],))

    v, bad = sandbox(diag=GOOD_DIAG + '  F-99 --> P-01\n')
    chk('反例 A1：图上有 F-99、表里没有 → 红', v is False and any('图上有' in b for b in bad))

    v, bad = sandbox(prd=GOOD_PRD.replace('| F-01 | 乙 |', '| F-01 | 乙 |\n| F-02 | 丁 |'))
    chk('反例 A2：表里有 F-02、图上没有 → 红（缺席也是对不上）',
        v is False and any('图上没有' in b for b in bad))

    v, bad = sandbox(diag=GOOD_DIAG + '  F-01 --> FR-001\n')
    chk('反例 B：同一张图里混了 F-01 与 FR-001 → 红（颗粒度越级）',
        v is False and any(b.startswith('B〔') for b in bad))

    # 🚨 2026-09-12 拿**我自己刚画的六张示例图**跑本门时揪出来的真缺陷：
    #   注释里提到 FR-001 被当成图上有 FR-001。⛔ 门在惩罚**写了说明**的那一份图源。
    #   ⭐ 新能力必配新正例：只加「注释不算数」的正例，
    #     反例 B（节点里真的混族）必须继续红 —— 否则就是把门放开而不是修对。
    v, bad = sandbox(diag='%% 注释：⛔ 不许混进 FR-001（附件 A 的细一层）\n' + GOOD_DIAG)
    chk('正例：ID 只出现在注释里 → 不算图上有（数「提到」≠「用了」）',
        v is True, '实得 %s' % (bad[:2],))

    v, bad = sandbox(diag='# 注释里提到 M-99\n' + GOOD_DIAG)
    chk('正例：注释里提到表外的 M-99 → 不该判「图上有表里没有的」',
        v is True, '实得 %s' % (bad[:2],))

    # ⚠️ 反向断言：剥注释**不能**把真节点一起剥掉。
    v, bad = sandbox(diag=GOOD_DIAG + '  F-01 --> FR-001\n%% 这行注释不影响上面那条真的混族\n')
    chk('反例 B2：节点真混族 + 另有注释 → 仍然红（剥注释没放过真缺陷）',
        v is False and any(b.startswith('B〔') for b in bad))

    # ⭐ 端到端正例：**真的七张示例图** + 真的夹具 PRD 一起跑，必须全绿。
    #   上面所有用例的图源都是沙箱里现编的字符串 —— 那证明不了
    #   「仓库里实际交付的那六张图能过本门」。2026-09-12 第一次真跑就揪出一个缺陷。
    # ⚠️ 改了任何一张示例图或夹具，这条会红 —— 那是它的用途。
    _tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'templates', 'diagrams')
    _fix = os.path.join(_tpl, 'fixture-prd.example.md')
    _exs = sorted(glob.glob(os.path.join(_tpl, '*.example.d2')))
    if not os.path.exists(_fix) or len(_exs) < 7:
        # ⛔ 依赖缺失是 UNABLE 不是静默跳过 —— 少了就必须说出来。
        chk('端到端正例：仓库里的七张示例图 + 夹具 PRD → 全绿',
            False, 'UNABLE：夹具或示例图缺失（找到 %d 张，夹具存在=%s）'
                   % (len(_exs), os.path.exists(_fix)))
    else:
        _d = tempfile.mkdtemp(prefix='dig-e2e-')
        os.makedirs(os.path.join(_d, '.product-flow', 'diagrams'))
        shutil.copy(_fix, os.path.join(_d, 'PRD-fixture.md'))
        for _e in _exs:
            shutil.copy(_e, os.path.join(_d, '.product-flow', 'diagrams'))
        _v, _bad = check(_d)
        shutil.rmtree(_d, True)
        chk('端到端正例：仓库里的 %d 张示例图 + 夹具 PRD → 全绿' % len(_exs),
            _v is True, '实得 %s' % (_bad[:3],))

    v, bad = sandbox(prd=GOOD_PRD.replace("""### B.3 算法与模型需求
| 项 | 内容 |
|---|---|
| 模型选型及理由 | x |
""", ""))
    chk('反例 C1：功能卡含 AI 但 B.3 缺失 → 红',
        v is False and any('B.3' in b for b in bad), '实得 %s' % (bad[:2],))

    v, bad = sandbox(prd=GOOD_PRD.replace("""### C.5 数据生命周期图
| 数据项 | 删除触发 |
|---|---|
| 甲 | y |
""", ""))
    chk('反例 C2：有 C.1 数据清单但 C.5 缺失 → 红（删除链路没人画）',
        v is False and any('C.5' in b for b in bad), '实得 %s' % (bad[:2],))

    v, bad = sandbox(no_diag=True)
    chk('反例 D：只有 PNG 没有文本图源 → **UNABLE**（⛔ 不报通过——拿不到证据时装作通过比没有门更糟）',
        v is None and any('没验' in b for b in bad))

    d3 = tempfile.mkdtemp(prefix='dig-noprd-')
    v3, b3 = check(d3)
    shutil.rmtree(d3, True)
    chk('反例 E：找不到 PRD → UNABLE（⛔ 不是通过）', v3 is None and any('没验' in x for x in b3))

    print('\n%s' % ('✅ 自证通过：图与表对不上会被抓住' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    """⛔ 本门自身崩溃必须退 2，不许和「有缺口」共用退出码 1。"""
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
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        die('缺少项目目录；用法见 --help')
    if not os.path.isdir(args[0]):
        die('不是目录：%s' % args[0])
    _res = []

    def _run():
        _res.append(check(args[0]))
    _main_guarded(_run)
    v, bad = _res[0]
    if '--json' in sys.argv:
        print(json.dumps({'ok': v, 'bad': bad}, ensure_ascii=False))
    else:
        _print_boundary()
        for b in bad:
            print('  ❌ ' + b)
        if v is True:
            print('✅ 图与表 ID 对得上：三组判据（双向集合相等 / 颗粒度同族 / 跨章逻辑一致）全过')
    sys.exit(0 if v is True else (2 if v is None else 1))
