#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec 自证 —— 规格声明的结构口径，必须与门禁真正要的一致。

═══ 为什么需要它 ═══
`spec/<stage>.json` 是**单一真源**：门禁读它判结构、脚手架读它生骨架、文档生成器读它写作业清单。
一旦它与门禁实际要求不一致，**三处会一起错**，而且错得整整齐齐、看不出来。

🚨 前车之鉴（2026-09-16）：我先做过一版从判据源码**静态反推**规格的工具，
自证 6 对 / 2 错，且其中一条错得带「高」置信 —— 会把人送去错的文件找错的小节。
⇒ 作废。改成**人工写 spec + 机器验 spec**：人负责理解，机器负责对账。

═══ 它验什么 / 不验什么 ═══
验：spec 里写的小节名与列正则，在门禁源码里**逐字存在**。
⛔ 不验：spec 写的「note」对不对、词表全不全 —— 那要人读。
⛔ 不验：spec 覆盖了门禁的**全部**判据 —— 只验「写下来的那些是对的」。
   覆盖率由 `--coverage` 单独报告，**它低不算失败**，算「还有多少没被写下来」。

用法:
  spec-check.py                 # 验 spec/ 下全部
  spec-check.py --coverage      # 额外报告覆盖率
  spec-check.py --self-test
退出码: 0=一致 1=不一致 2=跑不了
"""
import io, os, re, sys, json, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import _iter_headings   # 标题解析唯一正本

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr)
        sys.exit(2)


def check_one(spec_path, root=None):
    root = root or ROOT
    spec = json.loads(_read(spec_path))
    gate_rel = spec.get('gate')
    if not gate_rel:
        return ["%s 没写 `gate` —— 规格不指向任何门禁，无从对账" % os.path.basename(spec_path)], 0, 0
    gate_path = os.path.join(root, gate_rel)
    if not os.path.exists(gate_path):
        return ["%s 指向的门禁 %s **不存在**" % (os.path.basename(spec_path), gate_rel)], 0, 0
    src = _read(gate_path)
    bad, n_sec, n_col = [], 0, 0

    # ⭐ 两种门禁形态，校验口径不同（2026-09-17 接入 S3 时才发现，此前 schema 只表达得了一种）：
    #   corpus      —— 吃一个语料目录；小节名硬编码在**门禁源码**里 ⇒ 对着源码校验
    #   single-file —— 吃一个文件；结构来自**模板** ⇒ 对着模板校验
    #   ⛔ 用错口径会得出「小节不存在」这种假红，把人送去改对的东西。
    if spec.get('kind') == 'single-file':
        tpl_rel = spec.get('template')
        if not tpl_rel:
            return ["%s 声明 kind=single-file 却没写 `template` —— 结构从哪来说不清"
                    % os.path.basename(spec_path)], 0, 0
        tpl_path = os.path.join(root, tpl_rel)
        if not os.path.exists(tpl_path):
            return ["%s 指向的模板 %s **不存在**" % (os.path.basename(spec_path), tpl_rel)], 0, 0
        tpl = _read(tpl_path)
        # ⛔ 不手写标题解析 —— 仓里只许有一个正本（围栏内不算、setext 也认、引用块里的也认，
        #    这些坑 `_section.py` 都踩过并修过；手写一份就多一份要单独修的量程）。
        heads = {t for _ln, _lv, t in _iter_headings(tpl)}
        for sec in spec.get('sections', []):
            n_sec += 1
            t = sec['title']
            if t not in heads:
                bad.append("小节「%s」：spec 说模板里有它，但 %s 的标题集里找不到 —— "
                           "⛔ 照 spec 建的骨架与模板对不上" % (t, tpl_rel))
            for sub in sec.get('sub', []):
                n_sec += 1
                if sub not in heads:
                    bad.append("子小节「%s」（属「%s」）在模板标题集里找不到" % (sub, t))
            for c in sec.get('columns', []):
                n_col += 1
        ids = set(re.findall(r"""add\(\s*["']([a-z0-9][a-z0-9-]*)["']""", src))
        for cid in (spec.get('criteria') or {}):
            if cid not in ids:
                bad.append("`%s` 不是 %s 里的判据 id —— spec 指着一个不存在的判据"
                           % (cid, os.path.basename(gate_rel)))
        for sec in spec.get('sections', []):
            cid = sec.get('criterion')
            if cid and cid not in ids:
                bad.append("小节「%s」挂的判据 `%s` 不存在" % (sec['title'], cid))
        return bad, n_sec, n_col

    for t in spec.get('tables', []):
        sec = t['section'].lstrip('# ').strip()
        n_sec += 1
        # 小节名必须在门禁源码里逐字出现（_table_in_section 的第二个参数）
        if sec.startswith('（') or '…' in sec:
            continue                      # 关键词式判据：spec 里显式标注，不做逐字小节对账
        if not (re.search(r"_table_in_section\([^)]*?'%s'" % re.escape(sec), src, re.S)
                or re.search(r"section_at\([^,]+,\s*'%s'" % re.escape(sec), src)):
            bad.append("表「%s」：spec 说小节是 `## %s`，但门禁源码里找不到这个小节名 —— "
                       "⛔ 照 spec 建的骨架门禁会认不出来" % (t['id'], sec))
        for p in t.get('columnPatterns', []):
            n_col += 1
            if p not in src:
                bad.append("表「%s」：spec 写的列正则 `%s` 在门禁源码里不存在 —— "
                           "列名对不上，整表判缺" % (t['id'], p))

    for s in spec.get('sections', []):
        sec = s['section'].lstrip('# ').strip()
        n_sec += 1
        if sec.startswith('（') or '…' in sec:
            continue                      # 同上：关键词式，不逐字对账
        if not re.search(r"section_at\([^,]+,\s*'%s'" % re.escape(sec), src) and \
           ("'%s'" % sec) not in src:
            bad.append("小节「%s」：spec 说门禁读它，但门禁源码里找不到这个小节名" % sec)

    # 判据 id 必须真的是门禁里的一条判据
    ids = set(re.findall(r"""add\(\s*["']([a-z0-9][a-z0-9-]*)["']""", src))
    for grp in ('tables', 'sections'):
        for x in spec.get(grp, []):
            cid = x.get('criterion')
            if cid and cid not in ids:
                bad.append("`%s` 不是门禁里的判据 id —— spec 指着一个不存在的判据" % cid)
    for x in spec.get('crossCutting', {}).get('items', []):
        if x.get('criterion') and x['criterion'] not in ids:
            bad.append("`%s` 不是门禁里的判据 id" % x['criterion'])
    return bad, n_sec, n_col


def orphan_sections(spec_path, root=None):
    """⭐ 反向对账：门禁里**硬编码的小节名**，必须在 spec 里有登记。

    ⚠️ `check_one` 守的是「spec 写的门禁认」；这条守的是**反方向**——
      「门禁认的 spec 都写了」。少了这一向，新增一个硬编码小节就会**静默逃出规格**，
      于是文档与脚手架都不知道它存在，执行者又回到猜的状态。
    ⛔ 这是 B3「门禁改读 spec」的最小可行形态：不改门禁的读取方式（那是大手术），
      而是**让两边的集合必须相等**，且新增硬编码会被立刻拦下。
    """
    root = root or ROOT
    spec = json.loads(_read(spec_path))
    if spec.get('kind') in ('single-file', 'cross-artifact'):
        return set()                      # 结构来自模板/配对，门禁里本就没有硬编码小节
    gp = os.path.join(root, spec.get('gate') or '')
    if not os.path.exists(gp):
        return set()                      # 门禁不存在由 check_one 报，⛔ 这里别再 sys.exit(2)
    src = _read(gp)
    hard = set(re.findall(r"_table_in_section\(\s*\n?\s*\w+,\s*'([^']+)'", src))
    hard |= set(re.findall(r"section_at\([^,]+,\s*'([^']+)'", src))
    got = {t['section'].lstrip('# ').strip() for t in spec.get('tables', [])}
    got |= {x['section'].lstrip('# ').strip() for x in spec.get('sections', [])}
    return hard - got


def coverage(spec_path, root=None):
    """spec 覆盖了门禁多少条判据。⚠️ 低不算失败，算『还有多少没被写下来』。"""
    root = root or ROOT
    spec = json.loads(_read(spec_path))
    src = _read(os.path.join(root, spec['gate']))
    ids = set(re.findall(r"""add\(\s*["']([a-z0-9][a-z0-9-]*)["']""", src))
    covered = {x['criterion'] for grp in ('tables', 'sections') for x in spec.get(grp, []) if x.get('criterion')}
    covered |= {x['criterion'] for x in spec.get('crossCutting', {}).get('items', []) if x.get('criterion')}
    return covered & ids, ids - covered


def main(root=None):
    root = root or ROOT
    # 约定：`_` 开头＝跨阶段共享定义（_audience.json 之类），没有自己的门禁与产物。
    # ⛔ 不排除的话，`spec.get('gate')` 取空 → 拼出目录路径 → 报「读不到目录」这种假错。
    specs = sorted(p for p in glob.glob(os.path.join(root, 'spec', '*.json'))
                   if not os.path.basename(p).startswith('_'))
    if not specs:
        print("UNABLE: spec/ 下没有规格文件", file=sys.stderr)
        return 2
    rc = 0
    for sp in specs:
        bad, n_sec, n_col = check_one(sp, root)
        for miss in sorted(orphan_sections(sp, root)):
            bad.append("门禁里硬编码了小节「%s」，但 spec 里没登记 —— "
                       "它对文档与脚手架**不可见**，执行者只能靠猜（B3 反向对账）" % miss)
        name = os.path.basename(sp)
        if bad:
            rc = 1
            print("❌ %s" % name)
            for b in bad[:12]:
                print("      %s" % b)
        else:
            print("✅ %s（%d 个小节 · %d 个列正则，与门禁逐字一致）" % (name, n_sec, n_col))
        if '--coverage' in sys.argv:
            cov, miss = coverage(sp, root)
            print("      覆盖 %d / %d 条判据；**未写进 spec 的 %d 条**：%s"
                  % (len(cov), len(cov) + len(miss), len(miss), '、'.join(sorted(miss)[:10])))
            print("      ⚠️ 覆盖率低不算失败 —— 它说的是「还有多少结构口径没被写下来」")
    print("\n%s" % ("✅ spec 与门禁一致" if rc == 0 else
                    "❌ spec 与门禁不一致 —— ⛔ 照它建的骨架会白做"))
    print("⚠️ 本检查只验「写下来的是对的」，⛔ 验不了「写下来的够不够」，也验不了 note 写得对不对。")
    return rc


def self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='spec-')
    os.makedirs(os.path.join(t, 'spec')); os.makedirs(os.path.join(t, 'scripts'))
    gate = os.path.join(t, 'scripts', 'g.py')
    io.open(gate, 'w', encoding='utf-8').write(
        "h, r = _table_in_section(atomic, '真小节', (r'^af$', r'角色'))\n"
        "add('good-one', 'x')\nadd('sec-one', 'y')\nsection_at(x, '真的二级小节')\n")
    ok = True

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-44s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    def w(obj):
        io.open(os.path.join(t, 'spec', 's.json'), 'w', encoding='utf-8').write(
            json.dumps(obj, ensure_ascii=False))
        return main(t)

    base = {"gate": "scripts/g.py",
            "tables": [{"id": "T", "section": "## 真小节", "criterion": "good-one",
                        "columnPatterns": ["^af$", "角色"]}],
            "sections": [{"section": "## 真的二级小节", "criterion": "sec-one"}]}
    case("正例：spec 与门禁逐字一致", w(base), 0)

    import copy
    b2 = copy.deepcopy(base); b2['tables'][0]['section'] = '## 假小节'
    case("反例：小节名门禁里不存在（骨架会白做）", w(b2), 1)

    b3 = copy.deepcopy(base); b3['tables'][0]['columnPatterns'] = ["^af$", "不存在的列"]
    case("反例：列正则门禁里不存在", w(b3), 1)

    b4 = copy.deepcopy(base); b4['tables'][0]['criterion'] = 'no-such-criterion'
    case("反例：指着一个不存在的判据 id", w(b4), 1)

    b5 = copy.deepcopy(base); b5['gate'] = 'scripts/missing.py'
    case("反例：指向的门禁文件不存在", w(b5), 1)

    # ── B3 反向对账：门禁认的，spec 必须都写了 ──
    # ⚠️ 只**追加**一个新硬编码小节（一次只挪一样东西）；
    #   重写整个门禁会连原有小节一起丢，红的就不是我声称测的那件事。
    io.open(gate, 'a', encoding='utf-8').write("section_at(y, '没登记进 spec 的小节')\n")
    case("反例：门禁硬编码了小节而 spec 没登记（静默逃出规格）", w(base), 1)
    b6 = copy.deepcopy(base)
    b6['sections'].append({"section": "## 没登记进 spec 的小节", "criterion": "sec-one"})
    case("正例：补登记后两边集合相等", w(b6), 0)

    # ── single-file 形态（2026-09-17 接入 S3 时新增的分支）──
    os.makedirs(os.path.join(t, 'templates'), exist_ok=True)
    io.open(os.path.join(t, 'templates', 'tpl.md'), 'w', encoding='utf-8').write(
        "# 标题\n## 真小节 A\n### 真子节\n## 真小节 B\n")
    sf = {"gate": "scripts/g.py", "kind": "single-file", "template": "templates/tpl.md",
          "sections": [{"title": "真小节 A", "sub": ["真子节"], "criterion": "good-one"},
                       {"title": "真小节 B"}],
          "criteria": {"sec-one": "x"}}
    case("正例：single-file 的小节在模板里逐字存在", w(sf), 0)

    s2 = copy.deepcopy(sf); s2['sections'][0]['title'] = '假小节'
    case("反例：single-file 小节模板里没有", w(s2), 1)

    s3 = copy.deepcopy(sf); s3['sections'][0]['sub'] = ['假子节']
    case("反例：single-file 子小节模板里没有", w(s3), 1)

    s4 = copy.deepcopy(sf); s4['criteria'] = {'no-such': 'x'}
    case("反例：single-file 指着不存在的判据 id", w(s4), 1)

    s5 = copy.deepcopy(sf); del s5['template']
    case("反例：声明 single-file 却没写 template（结构从哪来说不清）", w(s5), 1)

    s6 = copy.deepcopy(sf); s6['template'] = 'templates/missing.md'
    case("反例：single-file 指向的模板不存在", w(s6), 1)

    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ spec 自证通过" if ok else "❌ spec 自证失败"))
    return 0 if ok else 1


def _main_guarded(fn):
    """崩溃 ≠ 有发现：意外异常一律退 2，⛔ 不许和「有发现」共用退出码 1。"""
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 工具自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__); sys.exit(0)
    _main_guarded(lambda: sys.exit(self_test() if '--self-test' in sys.argv else main()))
