#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S2 调研报告结构门禁。

兼容旧综合报告检查；`--mode teardown` 额外验证：每个最细功能都有可执行正文、状态/异常/恢复、
真实证据锚点和下游输入，并可与 atomic-feature-ledger、evidence-manifest 做集合对账。

用法:
  report-structure-gate.py <报告.md>
  report-structure-gate.py <报告.md> --mode teardown [--atomic-ledger FILE] [--evidence-manifest FILE]
  report-structure-gate.py --self-test
退出码: 0=通过 1=缺结构/缺正文 2=跑不了
"""
import argparse, io, json, os, re, sys, tempfile
from _section import _iter_headings, before_section

LEGACY_REQUIRED = [
    ('执行摘要(BLUF)', ['摘要', 'BLUF', '决策摘要']),
    ('竞品全景/选择理由', ['全景', '竞品选择', '竞品清单', '选择理由']),
    ('横向对比(差异/特点)', ['横向', '对比矩阵', '对比']),
    ('创新点/趋势', ['创新', '趋势', 'INNOV', 'TREND']),
    ('差异化/机会', ['差异化', '机会', 'DIFF', '白空间']),
    ('表态/建议/需求启发', ['表态', '建议', '需求', '决策', '启发']),
    ('方法与来源(单列)', ['方法', '来源', 'methodolog']),
]
TEARDOWN_REQUIRED = [
    ('执行摘要', ['执行摘要', '决策摘要', 'BLUF']),
    ('范围与诚实边界', ['范围与诚实边界', '研究范围', '研究对象、范围与结论上限']),
    ('定位与用户', ['定位与目标用户', '定位与用户', '产品定位、目标用户与核心任务']),
    ('产品全景与旅程', ['产品全景', '用户旅程']),
    ('功能全景与逐功能正文', ['功能全景', '逐功能正文']),
    ('最细功能正文索引', ['最细功能正文索引']),
    ('设计与交互', ['设计与交互']),
    ('状态异常与恢复', ['状态、异常与恢复', '状态异常与恢复']),
    ('反向规格与下游输入', ['反向规格', '下游输入', '反向产品规格']),
    ('方法与来源', ['方法与来源', '方法、证据范围与诚实缺口']),
]
INDEX_HEADERS = [
    'AF', '功能路径', '用户目标', '入口与前置', '一个动作', '规则/字段', '状态与反馈',
    '失败恢复', '证据', '正文小节', 'PRD/设计/技术/测试输入', '证据等级'
]
PLACEHOLDER = re.compile(r'<[^>]+>|待补|TBD|TODO|示例|xxx|—\s*$|^-$', re.I)


def _read(path):
    try:
        return io.open(path, encoding='utf-8', errors='replace').read()
    except Exception as e:
        raise RuntimeError('读不到 %s (%s)' % (path, e))


def _head_text(src):
    return '\n'.join(ln for ln in src.splitlines() if ln.lstrip().startswith('#'))


def _table_after(src, heading):
    m = re.search(r'^#{2,4}\s*.*%s.*$' % re.escape(heading), src, re.M)
    if not m:
        return [], []
    lines, table, started = src[m.end():].splitlines(), [], False
    for line in lines:
        if line.strip().startswith('|'):
            table.append(line.strip()); started = True
        elif started and line.strip():
            break
    if len(table) < 2:
        return [], []
    cells = lambda line: [c.strip() for c in line.strip('|').split('|')]
    headers = cells(table[0])
    rows = [dict(zip(headers, cells(line))) if len(cells(line)) == len(headers)
            else {'__malformed__': line} for line in table[2:]]
    return headers, rows


def _atomic_ids(src):
    _h, rows = _table_after(src, '功能分解词典')
    return {r.get('AF', '').strip('` ') for r in rows if re.fullmatch(r'AF-\d+', r.get('AF', '').strip('` '))}


def _evidence_manifest(path):
    raw = json.loads(_read(path))
    return {e.get('id'): e for e in raw.get('evidence', []) if e.get('id')}


def _body_section_for_af(src, af, anchor=''):
    """Locate the actual heading, not an earlier summary/TOC mention of AF."""
    text = before_section(src, '最细功能正文索引')
    lines, heads = text.splitlines(), list(_iter_headings(text))
    wanted = anchor.strip('# `')
    normalized = lambda title: re.sub(r'^\d+(?:\.\d+)*\s+', '', title).strip()
    hits = [(line, level) for line, level, title in heads if level >= 3
            and (wanted == normalized(title) if wanted else re.search(r'(?<!\w)' + re.escape(af) + r'(?!\d)', title))]
    if len(hits) != 1:
        return ''
    start, level = hits[0]
    end = next((line for line, lvl, _ in heads if line > start and lvl <= level), len(lines))
    return '\n'.join(lines[start:end])


def check_legacy(src):
    bad, htext = [], _head_text(src)
    for name, kws in LEGACY_REQUIRED:
        if not any(k in htext for k in kws):
            bad.append(('missing-section', '缺必备小节:%s' % name))
    if not re.search(r'```mermaid|<image\b|!\[[^\]]*\]\(', src):
        bad.append(('no-inline-diagram', '正文无内联图'))
    if '[实测' not in src:
        bad.append(('no-channel-a', '缺 `[实测·…]` 标签'))
    if '[案头' not in src:
        bad.append(('no-channel-b', '缺 `[案头·…]` 标签'))
    return bad


def check_competitive(src):
    bad = check_legacy(src)
    headers, rows = _table_after(src, '横向对比矩阵')
    need = ('节点路径', '层级', '子 AF', '产品模型', '共同模式', '关键差异', '含义')
    for wanted in need:
        if not any(wanted.lower() in h.lower() for h in headers):
            bad.append(('level-compare-header', '逐级横向对比缺列:%s' % wanted))
    if not rows or any(any(PLACEHOLDER.search(v) for v in r.values()) for r in rows):
        bad.append(('level-compare-empty', '逐级横向对比没有实写数据，或仍含占位'))
    return bad


def check_teardown(src, ledger_path=None, manifest_path=None, events_path=None):
    bad, htext = [], _head_text(src)
    for name, kws in TEARDOWN_REQUIRED:
        if not any(k in htext for k in kws):
            bad.append(('missing-section', '缺单品拆解小节:%s' % name))
    headers, rows = _table_after(src, '最细功能正文索引')
    for wanted in INDEX_HEADERS:
        if not any(wanted in h for h in headers):
            bad.append(('index-header', '最细功能正文索引缺列:%s' % wanted))
    report_ids, body_anchors = set(), set()
    for i, row in enumerate(rows, 1):
        af = row.get('AF', '').strip('` ')
        if not re.fullmatch(r'AF-\d+', af):
            bad.append(('index-af', '索引第%d行 AF 非法:%r' % (i, af))); continue
        if af in report_ids:
            bad.append(('duplicate-af', '索引重复声明同一功能:%s' % af))
        report_ids.add(af)
        for h in INDEX_HEADERS[1:]:
            val = next((v for k, v in row.items() if h in k), '')
            if not val or PLACEHOLDER.search(val):
                bad.append(('index-cell', '%s 的「%s」为空或占位' % (af, h)))
        state = next((v for k, v in row.items() if '状态与反馈' in k), '')
        grade = row.get('证据等级', 'verified')
        if grade not in ('verified', 'observed', 'reported', 'blocked'):
            bad.append(('evidence-state', '%s 的证据等级非法' % af))
        if grade == 'verified' and not re.search(r'→|->|业务状态不变.*(?:视图|反馈)', state):
            bad.append(('state-transition', '%s 未写 before→after 与反馈' % af))
        evid = row.get('证据', '')
        if grade == 'verified' and (not re.search(r'EVENT-\d+', evid) or not re.search(r'SHOT-\d+', evid)):
            bad.append(('evidence-pair', '%s 证据必须同时含 EVENT 与 SHOT' % af))
        if grade != 'verified' and not re.search(r'未知|阻断|未实测|仅观察|宣称', row.get('失败恢复', '') + evid):
            bad.append(('honest-boundary', '%s 非实测项必须解释未知/阻断，不得虚构成功' % af))
        section = next((v for k, v in row.items() if '正文小节' in k), '')
        if section in body_anchors:
            bad.append(('shared-feature-body', '%s 复用了其他索引行的正文锚点' % af))
        body_anchors.add(section)
        if section and section.strip('# `') not in src:
            bad.append(('body-anchor', '%s 的正文小节锚点不存在:%s' % (af, section)))
        body = _body_section_for_af(src, af, section)
        if not body:
            bad.append(('missing-feature-body', '%s 只在索引出现，正文没有独立功能段' % af))
        else:
            if not set(re.findall(r'\bSHOT-\d+\b', evid)).issubset(set(re.findall(r'\bSHOT-\d+\b', body))):
                bad.append(('body-evidence-mismatch', '%s 索引证据与该功能正文配图不一致' % af))
            required_body = [
                ('角色/入口/前置', r'角色|入口|前置'), ('对象/字段/规则', r'对象|字段|规则|默认值|校验'),
                ('一个动作', r'动作'), ('状态变化', r'状态变化|before\s*→\s*after'),
                ('结果与反馈', r'结果|反馈'), ('失败与恢复', r'失败|异常|恢复|重试|回退|取消'),
                ('下游输入', r'PRD|设计|交互|技术|算法|测试'),
            ]
            for name, pat in required_body:
                if not re.search(pat, body, re.I):
                    bad.append(('feature-body-field', '%s 正文缺「%s」' % (af, name)))
            if grade == 'verified' and (not re.search(r'<!--\s*evidence:SHOT-\d+', body) or not re.search(r'!\[[^\]]*SHOT-\d+', body)):
                bad.append(('feature-body-shot', '%s 正文没有邻接真实截图及机器锚点' % af))
            prose = re.sub(r'[`#|<>!*_\-\s\d.:/]+', '', body)
            if len(prose) < 100:
                bad.append(('feature-body-thin', '%s 正文有效文字过薄（%d字符）；索引值不能冒充说明' % (af, len(prose))))
    if not rows:
        bad.append(('no-body-index', '缺最细功能正文索引数据行；树图/清单不能替代正文'))
    for _line, _level, title in _iter_headings(before_section(src, '最细功能正文索引')):
        ids = set(re.findall(r'(?<!\w)AF-\d+(?!\d)', title))
        if len(ids) > 1:
            bad.append(('combined-leaf-body', '多个独立 AF 不能合用一个正文标题'))
    if ledger_path:
        ledger_ids = _atomic_ids(_read(ledger_path))
        if ledger_ids != report_ids:
            bad.append(('af-set-mismatch', '词典与正文索引 AF 集合不一致:缺%s 多%s' %
                        (sorted(ledger_ids - report_ids), sorted(report_ids - ledger_ids))))
    if manifest_path:
        manifest = _evidence_manifest(manifest_path)
        if len(manifest) != len(json.loads(_read(manifest_path)).get('evidence', [])):
            bad.append(('duplicate-shot', '证据清单有重复或缺失的图片 ID'))
        referenced = set(re.findall(r'\bSHOT-\d+\b', src))
        for eid in sorted(referenced - set(manifest)):
            bad.append(('dangling-shot', '正文引用 %s，证据清单中不存在' % eid))
        base = os.path.dirname(os.path.abspath(manifest_path))
        from _document_sync import media_sources
        for eid, item in manifest.items():
            source = item.get('sourcePath', '')
            anchor = item.get('anchor', '')
            resolved = source if os.path.isabs(source) else os.path.join(base, source)
            if not source or not os.path.isfile(resolved):
                bad.append(('missing-evidence-file', '%s 的真实文件不存在:%s' % (eid, source)))
            else:
                from _image import validate_image
                try: validate_image(resolved)
                except ValueError as exc: bad.append(('invalid-image', str(exc)))
            if eid not in src or (anchor and anchor not in src):
                bad.append(('evidence-not-inline', '%s/锚点未出现在对应正文' % eid))
            if ('<!-- evidence:%s' % eid) not in src:
                bad.append(('evidence-marker', '%s 缺邻接标记 <!-- evidence:%s -->' % (eid, eid)))
            for row in rows:
                if eid not in re.findall(r'\bSHOT-\d+\b', row.get('证据', '')):
                    continue
                body = _body_section_for_af(src, row.get('AF', '').strip('` '), row.get('正文小节', ''))
                actual = [ref for alt, ref in media_sources(body) if eid in alt]
                if len(actual) != 1 or os.path.realpath(os.path.join(base, actual[0])) != os.path.realpath(resolved):
                    bad.append(('body-image-path', '%s 必须在所属功能正文引用清单内同一张真实图' % eid))
    else:
        bad.append(('evidence-manifest-required', '单品交付必须提供 evidence-manifest，不以 ID 形状代替真实证据'))
    if events_path:
        event_items = json.loads(_read(events_path)).get('events', [])
        events = {e.get('id'): e for e in event_items}
        if len(events) != len(event_items):
            bad.append(('duplicate-event', '事件账有重复 ID'))
        for row in rows:
            ids = set(re.findall(r'\bEVENT-\d+\b', row.get('证据', '')))
            shots = set(re.findall(r'\bSHOT-\d+\b', row.get('证据', '')))
            for eid in ids:
                event = events.get(eid)
                if not event or event.get('evidenceId') not in shots:
                    bad.append(('dangling-event', '%s 不存在或未指向该功能证据' % eid))
                elif event.get('classification') == 'verified' and not all(event.get(k) for k in
                        ('beforeState', 'action', 'afterState', 'result', 'evidenceId')):
                    bad.append(('incomplete-event', '%s 缺真实操作前后态' % eid))
                elif row.get('证据等级', 'verified') == 'verified' and event.get('classification') != 'verified':
                    bad.append(('evidence-overclaim', '%s 的仅观察/阻断事件不能当成功实测' % eid))
    else:
        bad.append(('events-required', '单品交付必须提供 traversal-events，不以 EVENT 字串代替操作账'))
    if not re.search(r'主路径', src) or not re.search(r'失败|异常', src) or not re.search(r'恢复|重试|回退|取消', src):
        bad.append(('journey-branches', '旅程必须同时写主路径、失败/异常路径与恢复动作'))
    if any(r.get('证据等级', 'verified') == 'verified' for r in rows) and not re.search(r'!\[[^\]]*SHOT-\d+[^\]]*\]\([^)]*\)', src):
        bad.append(('no-real-inline-shot', '缺官方 lark-cli 可上传的真实内联截图语法'))
    return bad


def main(report, mode=None, ledger=None, manifest=None, events=None, package=None):
    if not report or not os.path.exists(report):
        print('UNABLE: 报告不存在 %s' % report, file=sys.stderr); return 2
    try:
        src = _read(report)
        if mode == 'teardown':
            bad = check_teardown(src, ledger, manifest, events)
            if not ledger:
                bad.append(('ledger-required', '正式深拆必须提供最细功能账本'))
        elif mode in ('competitive-pack', 'full-research'):
            bad = check_competitive(src)
            from _research_package import check_package
            bad += check_package(src, package, check_teardown)
        else:
            bad = check_legacy(src)
    except Exception as e:
        print('UNABLE: %s' % e, file=sys.stderr); return 2
    for key, why in bad:
        print('❌ [%s] %s' % (key, why))
    if not bad:
        print('✅ 报告结构与逐功能正文契约通过' if mode == 'teardown' else '✅ 报告结构齐')
    print('⚠️ 本门验结构、集合与证据存在性；结论真伪和截图是否拍对仍需人审。')
    return 1 if bad else 0


def self_test():
    ok = True
    def case(name, got, want):
        nonlocal ok
        hit = got == want; ok &= hit
        print(('  ✓ ' if hit else '  ✗ ') + '%s 期望%d 实得%d' % (name, want, got))
    with tempfile.TemporaryDirectory() as d:
        from PIL import Image
        shot = os.path.join(d, 'shot.png'); Image.new('RGB', (16, 16), 'white').save(shot)
        manifest = os.path.join(d, 'evidence.json')
        events = os.path.join(d, 'events.json')
        io.open(events, 'w').write(json.dumps({'events': [{'id': 'EVENT-001', 'classification': 'verified',
            'evidenceId': 'SHOT-001', 'beforeState': 'idle', 'action': 'create', 'afterState': 'done', 'result': 'created'}]}))
        io.open(manifest, 'w').write(json.dumps({'evidence':[{'id':'SHOT-001','sourcePath':'shot.png','anchor':'功能A'}]}, ensure_ascii=False))
        ledger = os.path.join(d, 'ledger.md')
        io.open(ledger, 'w').write('## 功能分解词典\n| AF | 名称 |\n|---|---|\n| `AF-001` | 功能A |\n')
        good = '''# 单品报告
## 执行摘要
## 范围与诚实边界
## 定位与目标用户
## 产品全景与用户旅程
主路径；失败/异常路径；重试恢复。
## 功能全景与逐功能正文
### 4.1.1 AF-001 功能A
AF-001 的角色、入口与前置：编辑者从首页进入功能A，在账号已登录并有编辑权限时处理目标对象。
对象、字段、默认值与校验规则均在此说明；用户执行一个创建动作，状态变化是空闲→完成，结果与反馈为成功提示。
若发生失败或异常，用户可以重试、取消或回退恢复；这会形成 PRD、设计交互、技术和测试的下游输入。
这一段继续解释边界、为什么拆到这里，以及相邻能力为何属于另一个独立功能，确保不是只有索引表格的空壳正文。<!-- evidence:SHOT-001 -->
![SHOT-001｜功能A成功态](<@./shot.png>)
## 最细功能正文索引
| AF | 功能路径 | 用户目标 | 入口与前置 | 一个动作 | 规则/字段 | 状态与反馈 | 失败恢复 | 证据 | 正文小节 | PRD/设计/技术/测试输入 | 证据等级 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `AF-001` | 工作/创建/功能A | 完成A | 首页且已登录 | 点击创建 | 名称必填 | 空闲→完成，显示成功 | 失败可重试 | EVENT-001 / SHOT-001 | AF-001 功能A | FR-1 / UI-1 / TECH-1 / TEST-1 | verified |
## 设计与交互
## 状态、异常与恢复
## 反向规格与下游输入
## 方法与来源
'''
        report = os.path.join(d, 'good.md'); io.open(report, 'w').write(good)
        case('完整单品正文通过', main(report, 'teardown', ledger, manifest, events), 0)
        shallow = os.path.join(d, 'shallow.md'); io.open(shallow, 'w').write('\n'.join('# '+x[0] for x in TEARDOWN_REQUIRED) + '\n![SHOT-001](<@./shot.png>)')
        case('只有标题+一张图必须红', main(shallow, 'teardown'), 1)
        bad_ledger = os.path.join(d, 'ledger-extra.md')
        io.open(bad_ledger, 'w').write(_read(ledger) + '| `AF-002` | 功能B |\n')
        case('词典多一个 AF 必须红', main(report, 'teardown', bad_ledger, manifest, events), 1)
        legacy = '''# 综合报告
## 执行摘要
## 竞品全景与选择理由
## 横向对比
## 创新点与趋势
## 差异化机会
## 表态与需求启发
## 方法与来源
```mermaid
graph LR
A-->B
```
[实测·GUI·2026-09-21] [案头·官网·2026-09-21]
'''
        legacy_path = os.path.join(d, 'legacy.md'); io.open(legacy_path, 'w').write(legacy)
        case('旧综合报告兼容通过', main(legacy_path), 0)
        case('正例三段式全+内联图+双通道→放行', main(legacy_path), 0)
        no_diagram = os.path.join(d, 'legacy-no-diagram.md')
        io.open(no_diagram, 'w').write(legacy.replace('```mermaid\ngraph LR\nA-->B\n```', ''))
        case('反例无内联图(去mermaid)→判红', main(no_diagram), 1)
        no_diff = os.path.join(d, 'legacy-no-diff.md')
        io.open(no_diff, 'w').write(legacy.replace('## 差异化机会\n', ''))
        case('反例缺『差异化』小节→判红', main(no_diff), 1)
        no_a = os.path.join(d, 'legacy-no-a.md')
        io.open(no_a, 'w').write(legacy.replace('[实测·GUI·2026-09-21]', ''))
        case('反例缺通道A实测标签→判红', main(no_a), 1)
        no_b = os.path.join(d, 'legacy-no-b.md')
        io.open(no_b, 'w').write(legacy.replace('[案头·官网·2026-09-21]', ''))
        case('反例缺通道B案头标签→判红', main(no_b), 1)
        comp = legacy.replace('## 横向对比\n', '''## 五 横向对比矩阵
| 节点路径 | 层级 | 子 AF 全集 | A 的产品模型/边界 | B 的产品模型/边界 | 共同模式 | 关键差异与原因 | 对我们的含义 |
|---|---:|---|---|---|---|---|---|
| 工作/任务 | 2 | AF-001/AF-002 | 列表式 | 对话式 | 均可创建 | 入口与恢复不同 | 采用双入口 |
''')
        comp_path = os.path.join(d, 'comp.md'); io.open(comp_path, 'w').write(comp)
        case('多竞品只填表但无单品包必须红', main(comp_path, 'competitive-pack'), 1)
        comp_empty = os.path.join(d, 'comp-empty.md'); io.open(comp_empty, 'w').write(legacy)
        case('多竞品缺逐级横比数据必红', main(comp_empty, 'competitive-pack'), 1)
    print('✅ 报告门自证通过' if ok else '❌ 报告门自证失败')
    return 0 if ok else 1


def _entry():
    if '--self-test' in sys.argv:
        return self_test()
    ap = argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--mode', choices=['teardown', 'competitive-pack', 'full-research'])
    ap.add_argument('--atomic-ledger')
    ap.add_argument('--evidence-manifest')
    ap.add_argument('--events')
    ap.add_argument('--package-manifest')
    a = ap.parse_args()
    return main(a.report, a.mode, a.atomic_ledger, a.evidence_manifest, a.events, a.package_manifest)


def _main_guarded(fn):
    """崩溃 ≠ 内容缺陷：意外异常一律退 2。"""
    try:
        sys.exit(fn())
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print('UNABLE: 门禁自身异常:%s: %s' % (type(e).__name__, e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    _main_guarded(_entry)
