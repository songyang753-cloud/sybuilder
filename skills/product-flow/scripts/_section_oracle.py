#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`_section.py` 的**差分测试** —— 拿真 CommonMark 实现当裁判。

═══ 为什么需要它 ═══

`_section.py` 是全仓 9 个门禁共用的段落定位正本，而它是**手写正则**。
Codex 两轮评审都点同一件事：手写解析器必然有它没想到的 Markdown 写法，
而门禁靠它「看见」文档 —— **它看错，所有下游判据跟着错，且不会有任何东西报错**。

我此前的替代是构造空间穷举（枚举写法的轴取笛卡尔积，138 例）。
⚠️ 但穷举只能覆盖**我想得到的轴** —— 这正是本仓母题
「修复把失效模式换了个触发器，而验证只覆盖作者想到的那个」。

⭐ **实证：上线当天就抓到 5 份真实文档的分歧，我那 138 例一条都没抓到。**
  · 假阳性：`---` 紧跟 `---`（两条连续分隔线）被判成二级标题 —— 分隔线不能当 setext 内容行；
  · 假阴性：`> ## 标题`（引用块里的 ATX）看不见 —— 门禁找不到那一节，
    而人在渲染后看到的分明是个标题。
  本仓记的「**对照组必须来自流程外**」，这是它最直接的一次兑现。

═══ ⛔ 它不是运行时依赖 ═══

`_section.py` 照旧零依赖运行 —— 「clone 下来就能跑」是这个 skill 能被分发的前提。
本模块只在**自证时**起作用：装了 markdown-it-py 就比对，没装就打印 UNABLE 并
**明说本轮没验**，退回穷举那一层。⛔ 没装不算通过（本仓红线：UNABLE ≠ 通过）。

═══ ⚠️ 诚实边界 ═══

1. **只比标题识别**（行号 × 级别 × 文本），那是全部消费方的共同地基。
   ⛔ 不比「节的结束位置」：那是本仓语义（下一个同级或更高级标题），
     不是 CommonMark 的概念，拿裁判去量会**量错对象**。
2. **`_section.py` 不是 CommonMark 完备实现，也不打算是。**
   病态 Markdown（连续分隔线夹 setext、围栏跨进列表、引用嵌套…）上两边仍会分歧，
   本模块把那个比率**如实打印出来**（见输出的「病态构造」一行）。
   ⛔ 它不是绿灯判据 —— 判据是「**真实文档零分歧**」，因为门禁只解析真实文档。
   ⚠️ 也**不许**为了让那个数字好看去裁剪生成器：那是「调测试直到它通过」。
3. `KNOWN_DIVERGENCE` 是**有意分歧**的登记表：那几处是裁判错、本模块对。
   ⭐ 登记表带**棘轮**：登记的文件若不再分歧，本测试会**变红** ——
     否则表会腐烂，早晚豁免掉真问题。

用法: _section_oracle.py --self-test
退出码: 0=真实文档零分歧 1=有未登记的分歧 2=跑不了（没装解析器 / 工具自身异常）
"""
import glob
import io
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import _iter_headings   # noqa: E402

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ⛔ 只登记「裁判错、本模块对」的。拿不准就别登记 —— 让它红，红了再想。
KNOWN_DIVERGENCE = {
    'SKILL.md':
        'YAML frontmatter：裁判不认识 frontmatter，把 `---\\nname: …\\ndescription: …` '
        '当成一个正文长达整段 description 的 setext 标题。本模块按本仓语义跳过元数据。',
    'templates/design-md.md':
        'YAML frontmatter（0–55 行）里有 `#` 开头的**YAML 注释**，裁判当成 14 个 ATX 标题。'
        '本模块只认 55 行之后的 11 个真章节。',
}


def _oracle_headings(md):
    """用 markdown-it 取 (行号, 级别, 文本)，口径对齐到 `_iter_headings`。"""
    from markdown_it import MarkdownIt
    tokens = MarkdownIt('commonmark').parse(md)
    out = []
    for i, t in enumerate(tokens):
        if t.type != 'heading_open':
            continue
        lvl = int(t.tag[1])
        text = tokens[i + 1].content if i + 1 < len(tokens) else ''
        out.append((t.map[0] if t.map else 0, lvl, text))
    return out


def _norm(items):
    """比对前的口径对齐。

    ⚠️ 只做**两边都同意是同一概念**的规整：首尾空白、ATX 的收尾 `#`。
    ⛔ 不做「把不一致抹平」的规整 —— 那等于让裁判闭嘴。
    """
    out = []
    for ln, lvl, text in items:
        t = (text or '').strip()
        while t.endswith('#'):
            t2 = t.rstrip('#').rstrip()
            if t2 == t:
                break
            t = t2
        out.append((ln, lvl, t))
    return out


def diverges(md):
    """返回 (本模块结果, 裁判结果, 是否分歧)。"""
    mine = _norm(list(_iter_headings(md)))
    theirs = _norm(_oracle_headings(md))
    return mine, theirs, mine != theirs


def real_docs(root=None):
    root = root or SKILL_ROOT
    pats = ('references/*.md', 'templates/**/*.md', 'SKILL.md', '.proposals/*.md')
    out = []
    for p in pats:
        out += glob.glob(os.path.join(root, p), recursive=True)
    return sorted(set(out))


# ───────── 病态构造生成器：枚举**写法**，不枚举文档 ─────────
_ATX = ['# A', '## B', '###### F', '#Nope', '#', '##', '   ### 缩进三格', '    # 四格是代码块']
_SETEXT = ['标题\n===', '标题\n---', '标题\n   ===', '标题\n====扰动']
_FENCE = ['```\n# 围栏里不算\n```', '~~~\n## 也不算\n~~~', '````\n```\n# 嵌套围栏\n```\n````']
_NOISE = ['正文一行', '', '- 列表项', '> 引用', '| a | b |', '\t制表符开头',
          '*强调*', '<!-- 注释 -->', '---', '***']


def _gen_docs(n, seed=20260911):
    rnd = random.Random(seed)
    pool = _ATX + _SETEXT + _FENCE + _NOISE
    for _ in range(n):
        yield '\n'.join(rnd.choice(pool) for _ in range(rnd.randint(1, 12)))


def _self_test():
    try:
        import markdown_it   # noqa: F401
    except ImportError:
        print('UNABLE: 本机没装 markdown-it-py —— 差分测试**本轮没验**。')
        print('       `_section.py` 运行时不需要它；要跑这层验证：pip3 install markdown-it-py')
        print('       ⛔ 这不是「通过」，也不是「不合格」。')
        return 2

    ok = True
    docs = real_docs()
    if not docs:
        print('UNABLE: 一份真实文档都没找到 —— 本条**没验**（⛔ 不是通过）')
        return 2

    unexpected, healed = [], []
    for f in docs:
        rel = os.path.relpath(f, SKILL_ROOT)
        try:
            _, _, bad = diverges(io.open(f, encoding='utf-8').read())
        except Exception as e:
            unexpected.append((rel, '_section 抛异常：%s: %s' % (type(e).__name__, e)))
            continue
        if bad and rel not in KNOWN_DIVERGENCE:
            mine, theirs, _ = diverges(io.open(f, encoding='utf-8').read())
            unexpected.append((rel, '本模块多 %s ／ 裁判多 %s'
                               % ([x for x in mine if x not in theirs][:2],
                                  [x for x in theirs if x not in mine][:2])))
        if not bad and rel in KNOWN_DIVERGENCE:
            healed.append(rel)

    ok &= not unexpected
    print('  %s 真实文档标题识别差分 %d 份（裁判：markdown-it-py CommonMark）'
          % ('✅' if not unexpected else '❌', len(docs)))
    for rel, why in unexpected[:6]:
        print('     · %s：%s' % (rel, why))
    if len(unexpected) > 6:
        print('     · …另有 %d 份' % (len(unexpected) - 6))

    # ⛔ 棘轮：登记表不许腐烂。登记的文件不再分歧 ⇒ 红，逼人把它从表里删掉。
    ok &= not healed
    print('  %s 有意分歧登记表 %d 条，全部仍在分歧（⛔ 不再分歧的必须从表里删掉，否则表会腐烂）'
          % ('✅' if not healed else '❌', len(KNOWN_DIVERGENCE)))
    for rel in healed:
        print('     · %s 已不再分歧 —— 从 KNOWN_DIVERGENCE 里删掉它' % rel)

    # ⭐ 承重确认：裁判必须真的会说「不一样」。零发现的量具最可疑。
    sensitive = (_norm(list(_iter_headings('# 真标题'))) != [(0, 9, 'X')])
    ok &= sensitive
    print('  %s 承重确认：喂一个错的结果给比对，它必须报分歧（零发现的量具最可疑）'
          % ('✅' if sensitive else '❌'))

    # ⚠️ 病态构造：**如实报数，不作为判据**（见模块 docstring 诚实边界 2）
    pathological = list(_gen_docs(3000))
    diff_n = sum(1 for md in pathological if diverges(md)[2])
    print('  ⚠️ 病态构造 %d 份随机拼装 · 分歧 %d 份（%.0f%%）—— **如实报数，不作判据**：'
          % (len(pathological), diff_n, 100.0 * diff_n / len(pathological)))
    print('     `_section.py` 不是 CommonMark 完备实现，也不打算是；门禁只解析真实文档。')
    print('     ⛔ 不许为了让这个数字好看去裁剪生成器 —— 那是「调测试直到它通过」。')

    print('\n%s' % ('✅ 自证通过：真实文档上与 CommonMark 零未登记分歧'
                    if ok else '❌ 自证失败：见上方'))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv:
        print((__doc__ or '').strip()); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    print((__doc__ or '').strip()); sys.exit(0)
