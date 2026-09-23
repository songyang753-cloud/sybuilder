#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1 意图捕获出场门 —— input/definition.md 的结构性判据（借鉴 AI-Native SDLC Stage 1）。

═══ 它补的洞 ═══
S1 此前是全流程唯一无门禁的阶段（理由成立：想法对错机器判不了）。
借 playbook 的 intent.md 五要素后，「**捕获的结构**」终于有了可查物 ——
本门只查结构与诚实留白，⛔ 仍然不判想法本身（那是 S3B 拍板的事）。

判据：
  ① 五要素节齐（Problem / Proposed outcome / Affected / Constraints / Open questions）
  ② Problem 有真实内容（占位符不算）
  ③ Open questions 显式（有条目，或明写「无」——⛔ 空着 ≠ 没有疑问）
  ④ Constraints 非空（真没有也要写「无已知约束」——沉默与确认过是两回事）
  ⑤ 发起者认可记录在案（落笔的是发起者的意图，没确认过就只是执行者的解读）

用法: intent-gate.py <definition.md> [--json] | --self-test
退出码: 0=通过 1=有缺口 2=跑不了
⚠️ 验不了什么：想法值不值得做（归 S2 研究与 S3B Go/No-build）；问题是不是真痛（归 S2 一手接触）。
"""
import io, json, os, re, sys

SECTIONS = ['Problem', 'Proposed outcome', 'Affected', 'Constraints', 'Open questions']


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def seg_of(md, kw):
    # ⭐ 锚定到**含关键词的标题行**,而非全文首次出现 —— 否则会取到前置「五要素索引行」或
    #    上一节里的交叉引用,导致真实小节缺失也假绿、或片段只剩一行把齐全内容误报为空。
    m = re.search(r'(?m)^#{1,6}[^\n]*' + re.escape(kw), md)
    if not m:
        return None
    i = m.start()
    # 截断点取下个标题**或**分隔线（末节后面跟着认可记录，不截会把它当节内容兜住）
    ends = [x for x in (md.find('\n## ', i + 1), md.find('\n---', i + 1)) if x > 0]
    return md[i:min(ends) if ends else len(md)]


def real_lines(seg):
    out = []
    for ln in seg.split('\n')[1:]:
        t = ln.strip().lstrip('-| ').strip()
        if t and not (t.startswith('<') and t.endswith('>')) and not set(t) <= set('|-: '):
            out.append(t)
    return out


def check(md):
    bad = []
    for sec in SECTIONS:
        if seg_of(md, sec) is None:
            bad.append('① 缺「%s」节（五要素模板见 templates/intent.md）' % sec)
    p = seg_of(md, 'Problem')
    if p is not None and not real_lines(p):
        bad.append('② Problem 没有真实内容（占位符不算——发起者的痛还没被写下来）')
    q = seg_of(md, 'Open questions')
    if q is not None:
        lines = real_lines(q)
        if not lines:
            bad.append('③ Open questions 空着 —— 显式写条目或写「无」；空着 ≠ 没有疑问')
    c = seg_of(md, 'Constraints')
    if c is not None and not real_lines(c):
        bad.append('④ Constraints 空着 —— 真没有也要写「无已知约束」（沉默与确认过是两回事）')
    if not re.search(r'发起者认可记录[：:].{0,40}于.{0,20}确认', md) or re.search(r'发起者认可记录[：:]\s*<', md):
        bad.append('⑤ 没有发起者认可记录 —— 没确认过的 intent 只是执行者的解读')
    return bad


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a:
        die('缺少 definition.md 路径；用法见 --help')
    if not os.path.isfile(a[0]):
        die('文件不存在：%s' % a[0])
    bad = check(io.open(a[0], encoding='utf-8').read())
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for b in bad:
            print('  ❌ ' + b)
        print('✅ S1 五判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门验不了想法值不值得做 —— 那归 S2 研究与 S3B 拍板。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import tempfile, subprocess
    t = tempfile.mkdtemp(prefix='ig-')
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        print(('  ✅ ' if c else '  ❌ ') + n + ('' if c else '　' + e))
        ok = ok and c

    GOOD = """# 意图
## Problem（问题）
- 摄影师每单要花 3 小时手工挑片（来源：亲历）
## Proposed outcome（想要的结果）
- 挑片从小时级降到分钟级
## Affected users & systems（谁与什么会被影响）
| 谁/什么 | 怎么被影响 |
|---|---|
| 摄影师 | 交付周期缩短 |
## Constraints（硬约束）
- 原片不出本地（合规）
## Open questions（现在答不了的问题）
- 无
---
- 发起者认可记录：产品负责人 于 2026-09-08 确认「这写的是我的意思」
"""

    def run(body):
        p = os.path.join(t, 'i.md')
        io.open(p, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chk('正例：五判据全过 → 0', run(GOOD) == 0)
    chk('反例①：缺 Open questions 节 → 1',
        run(GOOD.replace('## Open questions（现在答不了的问题）\n- 无\n', '')) == 1)
    chk('反例②：Problem 只有占位符 → 1',
        run(GOOD.replace('- 摄影师每单要花 3 小时手工挑片（来源：亲历）', '- <发起者的原话>')) == 1)
    chk('反例③：Open questions 空着（既无条目也没写「无」）→ 1',
        run(GOOD.replace('- 无\n---', '---')) == 1)
    chk('反例④：Constraints 空着 → 1',
        run(GOOD.replace('- 原片不出本地（合规）', '- <约束 + 来源>')) == 1)
    chk('反例⑤：无发起者认可记录 → 1',
        run(GOOD.replace('- 发起者认可记录：产品负责人 于 2026-09-08 确认「这写的是我的意思」', '')) == 1)
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'no.md')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', rc == 2)
    print('\n%s' % ('✅ 自证通过：这道门会出声' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print('UNABLE: 门禁自身异常（不是「有发现」）：%s: %s' % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or ''); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    _main_guarded(_entry)
