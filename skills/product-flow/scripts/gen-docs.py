#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档生成 —— 把 `spec/<stage>.json` 的结构口径**写进参考文档**，并守住它不漂移。

═══ 为什么 ═══
spec 是单一真源，三处消费：门禁判结构 · 脚手架生骨架 · **文档写给人看**。
前两处已经接上；第三处不接，执行者仍然看不见口径 —— 而看不见就只能猜，
猜就会回到「写一版 → 跑门禁 → 看报错 → 再猜」那个循环里去。

⭐ 做法抄 gstack：**文档的这一段由脚本生成，不许手改**。
   它从 spec 抽出「哪个文件 / 哪个小节 / 哪些列 / 什么词表」填进标记区，
   于是**文档与门禁不可能各说各话** —— 因为两边读的是同一份 spec。

═══ 标记区契约 ═══
    <!-- SPEC:BEGIN s2 -->   ← 生成起点
    …（脚本写的内容，⛔ 手改会被 `--check` 判红）
    <!-- SPEC:END s2 -->     ← 生成终点
标记区之外的正文**随便手写**，脚本一个字都不碰。

用法:
  gen-docs.py                 # 重新生成全部标记区
  gen-docs.py --check         # 只检查是否漂移（CI/门禁用），⛔ 不落盘
  gen-docs.py --self-test
退出码: 0=一致/已生成 1=漂移（--check 时） 2=跑不了
"""
import io, os, re, sys, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 哪个 spec 的口径写进哪个文档。⚠️ 新增流程时在这里登记，⛔ 别在别处硬编码。
TARGETS = {
    's2-research.json': 'references/competitive-research.md',
    's3-definition.json': 'references/s3-definition.md',
    's4-prd.json': 'references/prd-structure.md',
    's4a-structure.json': 'references/product-structure-gate.md',
    's0-chain.json': 'references/chain-reconcile.md',
}


def _read(p):
    return io.open(p, encoding='utf-8').read() if os.path.exists(p) else None


def render(spec):
    """把 spec 渲染成给人读的结构口径表。⛔ 只渲染机器能对账的那部分，不编解释。"""
    L = ['> ⚠️ **本段由 `scripts/gen-docs.py` 从 `spec/%s` 生成，⛔ 不要手改** —— '
         '手改会被 `gen-docs.py --check` 判红。要改先改 spec。' % spec.get('_specFile', '<stage>.json'),
         '',
         '**门禁**：`%s` ｜ **形态**：`%s`' % (spec.get('gate', '?'), spec.get('kind', 'corpus')), '']
    if spec.get('gateInvocation'):
        L += ['**怎么跑**：`%s`' % spec['gateInvocation'], '']
    if spec.get('template'):
        L += ['**结构来源**：模板 `%s`' % spec['template'], '']

    tables = spec.get('tables') or []
    if tables:
        L += ['### 必需的表（小节名与列名**逐字**如此，⛔ 差一个字判据就认不出）', '',
              '| 表 | 文件 | 小节 | 列 |', '|---|---|---|---|']
        for t in tables:
            L.append('| %s | `%s` | `%s` | %s |'
                     % (t['id'], t['file'], t['section'],
                        ' · '.join('`%s`' % c for c in (t.get('columns') or []))))
        L.append('')

    secs = spec.get('sections') or []
    if secs:
        key = 'title' if spec.get('kind') == 'single-file' else 'section'
        L += ['### 必需的小节', '', '| 小节 | 文件/位置 | 判据 |', '|---|---|---|']
        for s in secs:
            L.append('| `%s` | `%s` | %s |'
                     % (s.get(key, '?'), s.get('file', spec.get('artifact', '—')),
                        ('`%s`' % s['criterion']) if s.get('criterion') else '—'))
        L.append('')

    pe = spec.get('perEntity')
    if pe:
        L += ['### 逐条重复块', '',
              '- **标题格式**：`%s`' % pe.get('headingFormat', ''),
              '- **每块下限**：表格数据行 ≥ %s · 要点 ≥ %s' % (pe.get('minTableRows'), pe.get('minBullets'))]
        for k in ('note', 'rowsNote', 'bulletsNote', 'designLinkNote'):
            if pe.get(k):
                L.append('- %s' % pe[k])
        L.append('')

    vocab = {}
    for t in tables:
        vocab.update(t.get('valueVocab') or {})
    for s in secs:
        vocab.update(s.get('valueVocab') or {})
    if vocab:
        L += ['### 值词表（⛔ 只许这些）', '']
        for k, vs in vocab.items():
            L.append('- `%s`：%s' % (k, ' / '.join('`%s`' % v for v in vs)))
        L.append('')

    ag = spec.get('audienceGate')
    if ag:
        L += ['### ⭐ 读者分区（交付物给谁看）', '',
              '**%s**' % ag.get('rule', ''), '',
              '- 正文：给**人**（产品总监 / 评审 / 业务方）—— 结论先行、自足，图表证据直接放正文',
              '- 附件：给**人 + AI 编程**（研发按它写代码）—— 字段规格、状态机、ID 映射、内部锚点',
              '- ⛔ **过程日志两边都不进**：门禁条数 / 收敛轨迹 / 第几轮 / 我犯了什么错 '
              '⇒ 去 `.proposals/` 与 commit message',
              '', '**门禁**：`%s`　%s' % (ag.get('invocation', ''), ag.get('note', '')), '']

    h = spec.get('harvested') or {}
    if h.get('formats'):
        L += ['### 格式硬要求（⭐ 这些是**跑门禁才发现**的，光读判据代码看不出来）', '']
        for k, v in h['formats'].items():
            L.append('- **%s**：%s' % (k, v))
        L.append('')
    if h.get('requiredRows'):
        for sec, rows in h['requiredRows'].items():
            L += ['### 「%s」的必需行（⛔ 一行都不能少）' % sec, '',
                  '　' + ' · '.join('`%s`' % r for r in rows), '']
    if h.get('corrections'):
        L += ['### ⚠️ 已知纠错（spec 自己踩过的坑）', '']
        for k, v in h['corrections'].items():
            L.append('- **%s**：%s' % (k, v))
        L.append('')

    L += ['### 怎么用', '',
          '1. `python3 scripts/scaffold.py --stage %s --out <目标>` 生成合规骨架；'
          % spec.get('stage', '').lower(),
          '2. 把每个 `⟨TODO⟩` 换成真内容（⛔ 留着占位＝**还没开始**，不是快完成了）；',
          '3. 跑门禁到退出码 0 —— **那一步就是交付本身**，不是最后检查一下。', '']
    return '\n'.join(L)


# ── taxonomy(跨切面分类真源)生成 ─────────────────────────────────────────
# 与 SPEC 块独立的第二条生成路径:把 spec/_taxonomy.json 的分类表就地生成进各文档的
# `<!-- TAXONOMY:BEGIN <key> -->`/`END` 标记区。⭐ 治的是「八类图/NFR/视角/附件」这类
# 分类此前散落多处手写副本、反复自相矛盾(P0-1 反复修的正是它)。
TAXONOMY_SRC = os.path.join('spec', '_taxonomy.json')


def render_taxonomy_table(entry):
    """把一个 taxonomy 分类项渲染成 markdown 表(intro + 表头 + 数据行)。
    ⛔ cell 逐字来自 JSON,不重构/不规整 —— 保证生成的表与原文字节一致。"""
    L = []
    if entry.get('intro'):
        L += [entry['intro'], '']
    hdr = entry['header']
    L.append('| ' + ' | '.join(hdr) + ' |')
    L.append('|' + '|'.join(['---'] * len(hdr)) + '|')
    for row in entry['rows']:
        L.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(L)


def apply_taxonomy(root, check_only):
    """遍历 _taxonomy.json 的每个分类项,注入其目标文档的 TAXONOMY 标记区。
    _taxonomy.json 不存在(如自证临时目录)时静默跳过 —— 它是可选的第二路径。"""
    tax_path = os.path.join(root, TAXONOMY_SRC)
    if not os.path.exists(tax_path):
        return []
    tax = json.loads(_read(tax_path))
    bad = []
    for key, entry in sorted(tax.items()):
        if key.startswith('_') or key in ('schemaVersion',) or not isinstance(entry, dict):
            continue
        if 'rows' not in entry or 'header' not in entry:
            continue
        doc_rel = entry.get('target')
        if not doc_rel:
            bad.append('taxonomy `%s` 没登记 target 文档 —— 它的口径没有落点' % key); continue
        doc_path = os.path.join(root, doc_rel)
        doc = _read(doc_path)
        if doc is None:
            bad.append('taxonomy `%s` 的目标文档 %s 不存在' % (key, doc_rel)); continue
        b, e = '<!-- TAXONOMY:BEGIN %s -->' % key, '<!-- TAXONOMY:END %s -->' % key
        if b not in doc or e not in doc:
            bad.append('%s 里没有 `TAXONOMY:%s` 标记区 —— 先在表两端加标记,再跑生成器' % (doc_rel, key)); continue
        block = '%s\n\n%s\n%s' % (b, render_taxonomy_table(entry), e)
        new = re.sub(re.escape(b) + r'.*?' + re.escape(e), lambda _: block, doc, flags=re.S)
        if new == doc:
            continue
        if check_only:
            bad.append('%s 的 `TAXONOMY:%s` 标记区与 `spec/_taxonomy.json` **不一致** —— '
                       '有人手改了生成区,或改了 taxonomy 没重跑。⇒ `python3 scripts/gen-docs.py`'
                       % (doc_rel, key))
            continue
        io.open(doc_path, 'w', encoding='utf-8').write(new)
    return bad


def apply_one(spec_path, doc_rel, root, check_only):
    spec = json.loads(_read(spec_path))
    spec['_specFile'] = os.path.basename(spec_path)
    stage = (spec.get('stage') or '').lower()
    doc_path = os.path.join(root, doc_rel)
    doc = _read(doc_path)
    if doc is None:
        return ['文档 %s 不存在 —— spec 的口径没有落点' % doc_rel]
    b, e = '<!-- SPEC:BEGIN %s -->' % stage, '<!-- SPEC:END %s -->' % stage
    body = render(spec)
    block = '%s\n\n%s\n%s' % (b, body, e)
    if b in doc and e in doc:
        new = re.sub(re.escape(b) + r'.*?' + re.escape(e), lambda _: block, doc, flags=re.S)
    else:
        # 首次注入：放在文件末尾，⛔ 不猜该插哪儿（猜错会把正文切开）
        new = doc.rstrip() + '\n\n## 结构口径（由 spec 生成）\n\n' + block + '\n'
    if new == doc:
        return []
    if check_only:
        return ['%s 的 `SPEC:%s` 标记区与 spec **不一致** —— 有人手改了生成区，'
                '或改了 spec 没重跑生成器。⇒ `python3 scripts/gen-docs.py`' % (doc_rel, stage)]
    io.open(doc_path, 'w', encoding='utf-8').write(new)
    return []


def main(root=None, check_only=False):
    root = root or ROOT
    bad, n = [], 0
    for sp in sorted(glob.glob(os.path.join(root, 'spec', '*.json'))):
        name = os.path.basename(sp)
        # 约定：`_` 开头的是**跨阶段共享定义**（如 _audience.json），不是某一阶段的 spec。
        # ⛔ 不跳过的话会被当成「没登记落点」判红，而它本来就没有专属文档。
        if name.startswith('_'):
            continue
        doc = TARGETS.get(name)
        if not doc:
            bad.append('`spec/%s` 没在 gen-docs.py 的 TARGETS 里登记 —— '
                       '它的口径没有任何文档承载，执行者仍然看不见' % name)
            continue
        r = apply_one(sp, doc, root, check_only)
        bad += r
        n += 1
    bad += apply_taxonomy(root, check_only)   # 第二路径:跨切面分类真源
    for b in bad:
        print('❌ %s' % b)
    if not bad:
        print('✅ %d 份 spec 的结构口径%s' % (n, '与文档一致' if check_only else '已写入文档'))
    print('⚠️ 本工具只保证**文档与 spec 一致**，⛔ 保证不了 spec 与门禁一致 —— 那是 `spec-check.py`。')
    return 1 if bad else 0


def self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='gd-')
    os.makedirs(os.path.join(t, 'spec')); os.makedirs(os.path.join(t, 'references'))
    ok = True

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-50s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    sp = {"stage": "S2", "gate": "g.py", "kind": "corpus",
          "tables": [{"id": "T", "file": "a.md", "section": "## S", "columns": ["x", "y"],
                      "valueVocab": {"状态": ["A", "B"]}}]}
    io.open(os.path.join(t, 'spec', 's2-research.json'), 'w', encoding='utf-8').write(
        json.dumps(sp, ensure_ascii=False))
    doc = os.path.join(t, 'references', 'competitive-research.md')
    io.open(doc, 'w', encoding='utf-8').write('# 正文\n\n手写的段落，脚本不许碰。\n')

    case("首次生成 → 0", main(t), 0)
    txt = _read(doc)
    case("正文手写部分**原样保留**", 1 if '手写的段落，脚本不许碰。' in txt else 0, 1)
    case("标记区已注入", 1 if '<!-- SPEC:BEGIN s2 -->' in txt else 0, 1)
    case("列名与词表都写进去了", 1 if ('`x`' in txt and '`A`' in txt) else 0, 1)
    case("再跑 --check → 0（一致）", main(t, check_only=True), 0)

    io.open(doc, 'w', encoding='utf-8').write(txt.replace('`x`', '`被人手改了`'))
    case("反例：有人手改了生成区 → --check 判红", main(t, check_only=True), 1)

    sp['tables'][0]['columns'] = ['x', 'y', 'z']
    io.open(os.path.join(t, 'spec', 's2-research.json'), 'w', encoding='utf-8').write(
        json.dumps(sp, ensure_ascii=False))
    main(t)
    case("改 spec → 重跑生成器 → 文档跟着变", 1 if '`z`' in _read(doc) else 0, 1)

    io.open(os.path.join(t, 'spec', 'sX-unknown.json'), 'w', encoding='utf-8').write('{"stage":"SX"}')
    case("反例：spec 没在 TARGETS 登记（口径没有落点）", main(t), 1)
    os.remove(os.path.join(t, 'spec', 'sX-unknown.json'))   # 清掉,免污染下面的 taxonomy 用例

    # ── taxonomy 第二路径自证 ──
    tdoc = os.path.join(t, 'references', 'tax.md')
    io.open(tdoc, 'w', encoding='utf-8').write(
        '# 图表\n\n<!-- TAXONOMY:BEGIN diagrams -->\n<!-- TAXONOMY:END diagrams -->\n\n后面的手写。\n')
    io.open(os.path.join(t, 'spec', '_taxonomy.json'), 'w', encoding='utf-8').write(json.dumps(
        {"diagrams": {"target": "references/tax.md", "intro": "> 引子。",
                      "header": ["图", "位置"], "rows": [["**用户流程图**", "4.4"], ["状态机图", "附件 E"]]}},
        ensure_ascii=False))
    case("taxonomy 首次生成 → 0", main(t), 0)
    txt2 = _read(tdoc)
    case("taxonomy 表已注入（cell 逐字）", 1 if ('| **用户流程图** | 4.4 |' in txt2 and '| 状态机图 | 附件 E |' in txt2) else 0, 1)
    case("taxonomy 标记外手写保留", 1 if '后面的手写。' in txt2 else 0, 1)
    case("taxonomy 再 --check → 0（一致）", main(t, check_only=True), 0)
    io.open(tdoc, 'w', encoding='utf-8').write(txt2.replace('| 状态机图 | 附件 E |', '| 篡改 | 附件 E |'))
    case("反例：手改 taxonomy 生成区 → --check 判红", main(t, check_only=True), 1)

    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ 文档生成器自证通过" if ok else "❌ 自证失败"))
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
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    _main_guarded(lambda: sys.exit(main(check_only='--check' in sys.argv)))
