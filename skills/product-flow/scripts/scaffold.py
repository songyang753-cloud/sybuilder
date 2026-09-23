#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语料脚手架 —— 读 `spec/<stage>.json` 把**合规骨架**生成出来。

═══ 它要治的病 ═══
门禁强制文档结构，而结构口径只活在判据代码里 ⇒ 执行者只能「写一版 → 跑门禁 → 看报错 → 猜」。
🚨 2026-09-16 实测：从零建一份 S2 语料，门禁开局 **40 条红**，靠猜磨到 24 后不再收敛。

⇒ 参考 spec-kit 的 `specify-cli`：**把工件结构生成出来，而不是让人照着模板抄**。
   骨架一出来，结构类判据就该是绿的；剩下的红全是**内容没填**——那是应该红的。

═══ 🚨 它最大的风险：造假绿 ═══
一个只有结构没有内容的语料，如果门禁看不出「这是占位」，
就会得到一份**结构全绿、内容全空**的合格语料 —— 那比 40 条红危险得多。
⇒ 每一个生成的单元格都带 `⟨TODO⟩`，由 `research-gate` 的 `no-placeholder-left` 判据守着：
   **只要还有一个 ⟨TODO⟩，门禁就红。** 填完必须删标记。

用法:
  scaffold.py --stage s2 --out <目录> [--comps 14] [--afs 20] [--force]
  scaffold.py --self-test
退出码: 0=生成成功 1=拒绝生成（目标非空且没给 --force） 2=跑不了
"""
import io, os, re, sys, json, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODO = '⟨TODO⟩'


def _load(stage, root=None):
    p = os.path.join(root or ROOT, 'spec', '%s-research.json' % stage
                     if stage == 's2' else '%s-definition.json' % stage
                     if stage == 's3' else '%s-prd.json' % stage
                     if stage == 's4' else '%s.json' % stage)
    if not os.path.exists(p):
        # 允许 spec/<stage>*.json 任一匹配
        import glob as _g
        c = _g.glob(os.path.join(root or ROOT, 'spec', '%s*.json' % stage))
        if not c:
            print("UNABLE: 找不到 %s 的规格（spec/%s*.json）" % (stage, stage), file=sys.stderr)
            sys.exit(2)
        p = c[0]
    return json.loads(io.open(p, encoding='utf-8').read())


def _table_md(t, rows, seeds=None):
    """按 spec 的列名生成表头 + n 行占位。列名用 `columns`（人读的），
    ⚠️ 不用 `columnPatterns`（那是给门禁匹配的正则，写进文档会很难看且可能不匹配）。"""
    cols = t.get('columns') or []
    out = ['| ' + ' | '.join(cols) + ' |', '|' + '---|' * len(cols)]
    for r in rows:
        cells = []
        for i, c in enumerate(cols):
            if i < len(r) and r[i]:
                cells.append(r[i]); continue
            # ⭐ 结构性空格填**合法值**（形状对了门禁才认），内容性空格留 ⟨TODO⟩
            seed = next((v for k, v in (seeds or {}).items() if k and k in c), None)
            cells.append(seed or TODO)
        out.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(out)


def _vocab_note(t):
    v = t.get('valueVocab') or {}
    if not v:
        return ''
    lines = ['', '> **值词表（⛔ 只许这些）**：']
    for k, vals in v.items():
        lines.append('> - `%s`：%s' % (k, ' / '.join('`%s`' % x for x in vals)))
    return '\n'.join(lines) + '\n'


def _build_single_file(spec, out, root, force):
    """单文件形态（如 S3 定义）：骨架＝模板的标题集 + spec 点名的表与词表。
    ⚠️ 与语料形态的区别在**结构从哪来**：那边从门禁源码，这边从模板。"""
    art = spec.get('artifact') or 'artifact.md'
    p = out if out.endswith('.md') else os.path.join(out, art)
    if os.path.isdir(os.path.dirname(p) or '.'):
        pass
    else:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p) and not force:
        print("拒绝生成：%s 已存在。⛔ 脚手架不覆盖已有产物。要覆盖加 --force。" % p, file=sys.stderr)
        return 1
    seeds = (spec.get('seeds') or {}).get('cells') or {}
    lines = ['# %s · %s\n' % (TODO, spec.get('stage', '')),
             '> ⚠️ 骨架由 scaffold.py 生成，每个 %s 都要替换成真内容。' % TODO,
             '> ⛔ `no-placeholder-left` 同型纪律：留着占位就是**还没开始**。\n']
    for sec in spec.get('sections', []):
        lines.append('## %s\n' % sec['title'])
        if sec.get('note'):
            lines.append('> %s\n' % sec['note'])
        if sec.get('columns'):
            cols = sec['columns']
            lines.append('| ' + ' | '.join(cols) + ' |')
            lines.append('|' + '---|' * len(cols))
            row = [seeds.get(c, TODO) for c in cols]
            lines.append('| ' + ' | '.join(row) + ' |\n')
        else:
            lines.append('%s\n' % TODO)
        for sub in sec.get('sub', []):
            lines.append('### %s\n\n%s\n' % (sub, TODO))
    # ── perEntity：清单表 + 每条一个重复块（S4 PRD 的形状）──
    pe = spec.get('perEntity')
    et = spec.get('entryTable')
    if et:
        cols = et.get('requiredColumns', []) + ['优先级', '说明']
        lines.append('\n### 6.2 功能清单（⚠️ %s）\n' % et.get('note', '')[:60])
        lines.append('| ' + ' | '.join(cols) + ' |')
        lines.append('|' + '---|' * len(cols))
        for i in range(1, 4):
            lines.append('| F-%03d | %s | P0 | %s |' % (i, TODO, TODO))
        lines.append('')
    if pe:
        nrow = pe.get('minTableRows', 4); nbul = pe.get('minBullets', 12)
        lines.append('\n> 🚨 **功能块标题逐字如此**：`%s`。%s\n' %
                     (pe.get('headingFormat', ''), pe.get('note', '')[:80]))
        for i in range(1, 4):
            lines.append('### M: %s / F-%03d: %s\n' % (TODO, i, TODO))
            lines.append('| 页面 | 设计稿 | 设计交互逻辑 |')
            lines.append('|---|---|---|')
            # ⚠️ 要点写在**逻辑列单元格内**（`<br>-`），⛔ 表外的 `- ` 列表门禁一条都不算
            per = max(1, -(-nbul // nrow))
            for j in range(nrow):
                pts = ''.join('<br>- %s' % TODO for _ in range(per))
                lines.append('| %s | [%s](%s) | %s%s |'
                             % (TODO, TODO, 'https://figma.example/n%d' % j, TODO, pts))
            lines.append('')
    for name, why in (spec.get('attachments') or {}).items():
        lines.append('\n## %s\n\n> %s\n\n%s\n' % (name, why, TODO))

    for tok in ((spec.get('harvested') or {}).get('requiredTokens') or {}).get(art, []):
        lines.append('<!-- 门禁点名要的字面：%s -->' % tok)
    for k, v in seeds.items():
        if k not in ('等级',):
            lines.append('\n**%s**：%s' % (k, v))
    fmts = ((spec.get('harvested') or {}).get('formats') or {})
    if fmts:
        lines.append('\n> **格式硬要求**：\n' +
                     '\n'.join('> - `%s`：%s' % (a, b) for a, b in fmts.items()))
    io.open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    n = '\n'.join(lines).count(TODO)
    print("✅ 已生成 %s（%d 个小节）" % (p, len(spec.get('sections', []))))
    print("   %d 处 %s —— **门禁会因此红，这是对的**：结构有了，内容还没有。" % (n, TODO))
    return 0


def build(stage, out, comps=14, afs=20, root=None, force=False):
    spec = _load(stage, root)
    if spec.get('kind') == 'single-file':
        return _build_single_file(spec, out, root, force)
    if os.path.isdir(out) and os.listdir(out) and not force:
        print("拒绝生成：%s 非空。⛔ 脚手架不覆盖已有语料（那会静默删掉别人的工作）。"
              "确认要覆盖就加 --force。" % out, file=sys.stderr)
        return 1
    os.makedirs(out, exist_ok=True)
    for sub in ('raw', 'cross-compare', 'deep-research'):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    seed_cells = (spec.get('seeds') or {}).get('cells') or {}
    comp_ids = ['COMP-%02d' % i for i in range(1, comps + 1)]
    af_ids = ['AF-%03d' % i for i in range(1, afs + 1)]
    buf = {}                                    # 文件名 -> [段落]

    def put(fn, text):
        buf.setdefault(fn, []).append(text)

    # ── 元文件的头 ──
    for fn, meta in spec.get('files', {}).items():
        if not meta.get('isMeta'):
            continue
        put(fn, '# %s\n\n> %s\n' % (meta.get('role', fn), meta.get('note', '')
                                    or '⚠️ 骨架由 scaffold.py 生成，每个 %s 都要替换成真内容。' % TODO))

    # ── 表 ──
    for t in spec.get('tables', []):
        fn = t['file']
        if fn == 'c<NN>.md':
            continue                            # 竞品档案里的表在下面逐家生成
        if t['id'] == '原子功能事实账':
            rows = [[a, c] for a in af_ids for c in comp_ids]
        elif t['id'] == '功能分解词典':
            rows = [[a] for a in af_ids]
        elif t['id'] == '实测采集回执':
            rows = [['RUN-%02d' % i, comp_ids[i - 1]] for i in range(1, comps + 1)]
        elif t['id'] == '横向对比面板清单':
            rows = [['面板 A'], ['面板 B']]
        elif t['id'] == '原子功能下游映射':
            rows = [[a] for a in af_ids]
        else:
            rows = [[]]
        put(fn, '%s\n\n%s%s\n%s\n' % (t['section'],
                                      ('> %s\n' % t['note']) if t.get('note') else '',
                                      _vocab_note(t), _table_md(t, rows, seed_cells)))

    # ── 非表小节 ──
    for s in spec.get('sections', []):
        fn, sec = s['file'], s['section']
        if fn == '*.md':
            fn = '功能调研报告.md'
        if sec.startswith('（') or '…' in sec:   # 关键词式：给一句提示，不造假标题
            put(fn, '<!-- ⚠️ %s：%s -->\n\n%s\n' % (s['criterion'], s.get('note', ''), TODO))
            continue
        body = _vocab_note(s)
        put(fn, '%s\n\n%s%s\n%s\n' % (sec, ('> %s\n' % s['note']) if s.get('note') else '',
                                      body, TODO))

    # ── 竞品档案 ──
    surf = next((t for t in spec.get('tables', []) if t['file'] == 'c<NN>.md'), None)
    for i, cid in enumerate(comp_ids, 1):
        fn = 'c%02d.md' % i
        s = ['# %s · %s（竞品档案）\n' % (cid, TODO),
             '| 项 | 内容 |', '|---|---|',
             '| 官方 URL | https://%s |' % TODO,
             '| 访问日期 | %s |' % TODO,
             '| 通道可达性 | %s |' % TODO, '']
        if surf:
            s.append('%s\n\n%s\n' % (surf['section'], _table_md(surf, [['SURF-001', 'RUN-%02d' % i]], seed_cells)))
        for blk in ('核心体验路径（全员档①）', '产品模块图（全员档③·`CM-xx`）',
                    '功能清单（全员档④·`CAF-xxx`）', '页面关系图（全员档⑥）',
                    "Can't vs Won't"):
            s.append('## %s\n\n%s\n' % (blk, TODO))
        buf[fn] = ['\n'.join(s)]

    # ── 跨切面声明：**必须落在竞品档案语料里**（判据读的是非元文件拼接文本）──
    cc = spec.get('crossCutting', {})
    s = ['# 研究方法与跨切面声明（非竞品；本轮研究自身的档案）\n',
         '| 项 | 内容 |', '|---|---|',
         '| 方法正本 URL | https://github.com/example-org/evidence-driven-product-flow |',
         '| 访问日期 | %s |' % TODO, '',
         '> 🚨 %s\n' % cc.get('_note', '')]
    for it in cc.get('items', []):
        s.append('## %s\n\n> 判据 `%s`' % (it['need'], it['criterion']))
        if it.get('tokens'):
            s.append('> 必须出现这些字样：%s' % '、'.join('`%s`' % x for x in it['tokens']))
        s.append('\n%s\n' % TODO)
    buf['c00-研究方法与跨切面声明.md'] = ['\n'.join(s)]

    # ── harvested：门禁在骨架上报出来的**精确要求**，逐条生成（见 spec.harvested）──
    h = spec.get('harvested', {})
    for secname, rows in (h.get('requiredRows') or {}).items():
        tgt = next((x['file'] for x in spec.get('sections', [])
                    if x['section'].lstrip('# ').strip() == secname), None)
        if not tgt:
            continue
        put(tgt, '\n> ⚠️ 下面这些行是**门禁点名要的**，⛔ 一行都不能少：\n\n'
                 '| 载体 | 调研这边拿什么喂它 | 状态 |\n|---|---|---|\n'
            + '\n'.join('| %s | %s | %s |' % (r, TODO, TODO) for r in rows) + '\n')
    for fn, toks in (h.get('requiredTokens') or {}).items():
        if fn == 'cross-comp':
            fn = 'c00-研究方法与跨切面声明.md'
        put(fn, '\n## ⚠️ 门禁点名要的字面（⛔ 少一个就红）\n\n'
            + '\n'.join('- `%s` → %s' % (t, TODO) for t in toks) + '\n')
    for path, why in (h.get('requiredFiles') or {}).items():
        if path.endswith('/'):
            os.makedirs(os.path.join(out, path), exist_ok=True)
            io.open(os.path.join(out, path, 'R-A.md'), 'w', encoding='utf-8').write(
                '# R-A 竞品单体轮\n\n> %s\n\n%s\n' % (why, TODO))
            io.open(os.path.join(out, path, 'R-B.md'), 'w', encoding='utf-8').write(
                '# R-B 行业轮\n\n> %s\n\n%s\n' % (why, TODO))
        elif path.endswith('.d2'):
            os.makedirs(os.path.join(out, 'cross-compare'), exist_ok=True)
            io.open(os.path.join(out, 'cross-compare', 'entry-families.d2'), 'w',
                    encoding='utf-8').write(
                        '# %s\n# ⚠️ 这是占位桩，%s —— 真图要用 fireworks-tech-graph 出\n'
                        'direction: right\n"%s" -> "%s"\n' % (why, TODO, TODO, TODO))
        else:
            for rn in ('功能调研报告.md', '设计调研报告.md', '交互调研报告.md'):
                buf.setdefault(rn, ['# %s\n\n> %s\n\n📎 `raw/<slug>/<date>/<图>.png`\n\n%s\n'
                                    % (rn[:-3], why, TODO)])
    # ── seeds.blocks：门禁点名要的**结构块**，逐文件生成（内容仍是 ⟨TODO⟩）──
    sb = (spec.get('seeds') or {}).get('blocks') or {}
    def blk(fn, title, body):
        put(fn, '\n## %s\n\n%s\n' % (title, body))
    if 'competitor-landscape.md' in sb:
        rows = '\n'.join('| `%s` | %s | 直接 | 品类头部 | %s | 该产品发版或定位变更即重看 | 中 | 中 |'
                         % (c, TODO, TODO) for c in comp_ids)
        blk('competitor-landscape.md', '竞品集合（双轴 + 候选池形成记录）',
            '| COMP | 竞品 | 竞争关系轴 | 样本角色轴 | 纳入/排除理由 | 重看触发 | 威胁价值 | 学习价值 |\n'
            '|---|---|---|---|---|---|---|---|\n' + rows +
            '\n\n⛔ **威胁价值与学习价值分列，不合成总分**。')
        blk('competitor-landscape.md', '〇 研究合同',
            '\n'.join('| `%s` | %s |' % (k, TODO) for k in
                      ('DECISION','QUESTION','CHANGE-MIND','POSITIONING-LENS','STRATEGIC-TENSION','SOURCE-PLAN'))
            .join(['| 项 | 必填内容 |\n|---|---|\n','']) +
            '\n\n`AI-SCOPE：适用 · 理由：%s`\n' % TODO)
        blk('matrix.md', '公共比较维度（⚠️ 判据读 matrix.md，不是 landscape）',
            '| 维度 | 结论 |\n|---|---|\n' + '\n'.join('| %s | %s |' % (d, TODO) for d in
            ('定位与价值主张','目标用户与购买者','场景','流程','能力','商业','体验','技术')))
        blk('competitor-landscape.md', '取证计划 SOURCE-PLAN',
            '| 维度 | **首选一手证据** | 独立复核 | 能否交互实测 | 降级方式 |\n|---|---|---|---|---|\n'
            + '\n'.join('| %s | %s | %s | %s | %s |' % (d, TODO, TODO, TODO, TODO)
                        for d in ('功能清单','设计令牌','交互模式','定位/增长/口碑')))
        blk('competitor-landscape.md', '版本对账',
            '| 版本 | 定位 | 处置 |\n|---|---|---|\n| v1 | %s | %s |\n\n'
            '纠错三段：旧结论 %s / 新结论 %s / **旧结论错在哪（真因）** %s' % (TODO, TODO, TODO, TODO, TODO))
    if 'design-tokens.md' in sb:
        blk('design-tokens.md', '设计令牌反查表',
            '| 令牌族 | 取到的值 | 取证通道 | 📎 截图证据 |\n|---|---|---|---|\n'
            + '\n'.join('| %s族 | %s | `cdp-direct` | `raw/<slug>/<date>/<图>.png` |' % (f, TODO)
                        for f in ('字','色','距')))
    if 'innovation-trends.md' in sb:
        blk('innovation-trends.md', '创新点 INNOV',
            '| ID | 创新点 | 谁做的 | 新在哪 | 证据 |\n|---|---|---|---|---|\n'
            + '\n'.join('| `INNOV-%02d` | %s | `%s` | %s | %s |' % (i, TODO, c, TODO, TODO)
                        for i, c in enumerate(comp_ids, 1)))
        blk('innovation-trends.md', '趋势 TREND（带样本门槛与反例）',
            '| ID | 趋势 | 样本 | 反例 | 判定 |\n|---|---|---|---|---|\n| `TREND-01` | %s | %s | %s | %s |'
            % (TODO, TODO, TODO, TODO))
        blk('innovation-trends.md', 'WATCH（写事件不写日期）',
            '| ID | 盯什么 | 触发条件（事件） |\n|---|---|---|\n| `WATCH-01` | %s | %s |' % (TODO, TODO))
    if 'matrix.md' in sb:
        blk('matrix.md', '横向对比面板 A',
            '| AF | ' + ' | '.join(comp_ids) + ' |\n|---|' + '---|' * len(comp_ids) + '\n'
            + '\n'.join('| `%s` | ' % a + ' | '.join(['UNKNOWN'] * len(comp_ids)) + ' |' for a in af_ids))
        blk('matrix.md', '频次分层', '| 层 | 阈值 | 落在这一层的 AF |\n|---|---|---|\n| 原语 | ≥70%% | %s |' % TODO)
    if 'insights.md' in sb:
        blk('insights.md', '跨竞品对照图', '`cross-compare/entry-families.d2`（可解析源）\n\n差异 %s → 原因 %s → 对我们 %s' % (TODO, TODO, TODO))
        blk('insights.md', '四类行动结论',
            '| 类 | 结论 |\n|---|---|\n' + '\n'.join('| %s | %s |' % (k, TODO)
            for k in ('学习','借鉴','规避','差异化')))
        blk('insights.md', '主题分析（含**模式**环节）', '编码 → **模式** → 主题 → 洞察 → 机会：%s' % TODO)
        blk('insights.md', '机会 OPP（每个 ≥3 解法候选 + 优先级理由）',
            '| OPP | 机会 | 解法A | 解法B | 解法C | 机会优先级 + 理由 |\n|---|---|---|---|---|---|\n'
            '| `OPP-01` | %s | %s | %s | %s | **P0**：%s |' % (TODO, TODO, TODO, TODO, TODO))
    if 'key-flows.md' in sb:
        blk('key-flows.md', '同口径协议',
            '`FLOW-01` 同一任务与**完成定义**：%s\n\n**可编辑图源**：`cross-compare/entry-families.d2`\n\n'
            '| FLOW | 竞品 | 步骤数 | 耗时 | 回退 | 错误 | 恢复 |\n|---|---|---|---|---|---|---|\n'
            '| `FLOW-01` | `COMP-01` | %s | %s | %s | %s | %s |\n\n'
            '**三类下游目标**：① S5.2 交互规格 ② S6 HTML demo ③ PRD 七章' % ((TODO,) * 6))
    if 'sources.md' in sb:
        blk('sources.md', '承重主张账 CLM',
            '| CLM | 主张 | 来源 | 验证状态 | 发布日期 | 访问日 | 失效日 |\n|---|---|---|---|---|---|---|\n'
            '| `CLM-001` | %s | %s | %s | %s | %s | %s |' % ((TODO,)*6))
    if 'lines.md' in sb:
        blk('lines.md', '五条研究线',
            '| 线 | 结论或显式「本轮不做」 |\n|---|---|\n'
            + '\n'.join('| %s | 本轮不做：%s |' % (l, TODO) for l in
                        ('① 用户线','② 竞品线','③ 市场/品类线','④ 数据线','⑤ 技术可能性线')))
        blk('lines.md', '市场线声明', '本轮市场线：%s。独立交付 `market-landscape.md`。下游声明上限：%s' % (TODO, TODO))
    if 'conflicts.md' in sb:
        blk('conflicts.md', '双路 deep-research 合并记录',
            '| 轮 | 我方 | codex | 同向/不同向 |\n|---|---|---|---|\n| R-A | %s | %s | %s |' % ((TODO,)*3))
        blk('conflicts.md', '冲突条目',
            '| ID | 主张 | A 通道实测 | B 通道宣称 | 采信 |\n|---|---|---|---|---|\n'
            '| `CONFLICT-01` | %s | %s | %s | **以 A 实测为准**：%s |' % ((TODO,)*4))
    if 'downstream-coverage.md' in sb:
        blk('downstream-coverage.md', '下游→研究 反向追溯',
            '| 下游承重问题 | 反查到的研究条目 | 未知/未采用的去向 |\n|---|---|---|\n| %s | %s | %s |\n\n'
            '（另一半：研究→下游 见 PRD 载体对账）' % ((TODO,)*3))
    if (h.get('formats') or {}):
        put('atomic-feature-ledger.md', '\n> **格式硬要求**：\n'
            + '\n'.join('> - `%s`：%s' % (k, v) for k, v in h['formats'].items()) + '\n')

    for fn, parts in buf.items():
        io.open(os.path.join(out, fn), 'w', encoding='utf-8').write('\n'.join(parts) + '\n')

    n_todo = sum(io.open(os.path.join(out, f), encoding='utf-8').read().count(TODO)
                 for f in os.listdir(out) if f.endswith('.md'))
    print("✅ 已生成 %d 个文件到 %s" % (len(buf), out))
    print("   %d 处 %s —— **门禁会因此全红，这是对的**：结构有了，内容还没有。" % (n_todo, TODO))
    print("⛔ 填完必须删掉 %s 标记；`no-placeholder-left` 判据守着这件事。" % TODO)
    print("⚠️ 脚手架只保证**结构**对得上门禁，⛔ 保证不了内容对不对——那是研究本身。")
    return 0


def self_test():
    import tempfile, shutil
    ok = True

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-46s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    t = tempfile.mkdtemp(prefix='scaf-')
    d = os.path.join(t, 'r')
    case("正例：空目录生成成功", build('s2', d, comps=3, afs=2), 0)
    txt = {f: io.open(os.path.join(d, f), encoding='utf-8').read() for f in os.listdir(d)
           if f.endswith('.md')}
    allmd = '\n'.join(txt.values())
    case("生成物带 ⟨TODO⟩（不许悄悄产出看似完整的语料）", 1 if TODO in allmd else 0, 1)
    case("功能分解词典的列名齐", 1 if '| af | l0 | l1 | l2 |' in allmd.replace('  ', ' ') or
         ('af' in allmd and '拆分说明' in allmd) else 0, 1)
    case("事实账是 AF×COMP 全笛卡尔（2×3=6 行）",
         len(re.findall(r'\| `?AF-\d+`? \| `?COMP-\d+`? \|', allmd)) >= 6 and 1 or 0, 1)
    case("竞品档案数 = comps", len([f for f in txt if re.match(r'^c\d\d\.md$', f)]), 3)
    case("跨切面声明落在**竞品档案**里（非元文件）",
         1 if any(f.startswith('c00') for f in txt) else 0, 1)
    case("反例：目标非空且无 --force → 拒绝生成（不覆盖别人的工作）",
         build('s2', d, comps=3, afs=2), 1)
    case("正例：带 --force 可覆盖", build('s2', d, comps=3, afs=2, force=True), 0)
    shutil.rmtree(t, ignore_errors=True)
    print("\n%s" % ("✅ 脚手架自证通过" if ok else "❌ 脚手架自证失败"))
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
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--stage', default='s2')
    ap.add_argument('--out', required=True)
    ap.add_argument('--comps', type=int, default=14)
    ap.add_argument('--afs', type=int, default=20)
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    _main_guarded(lambda: sys.exit(build(a.stage, a.out, a.comps, a.afs, force=a.force)))
