#!/usr/bin/env python3
"""traversal-coverage-gate.py — S2 竞品遍历「报告 ⟷ deep-tree 数据」覆盖对账门。

治的问题：deep-walk 实测钻到了 N 个路由屏，报告却只写了 1 个——数据在，报告没用它，
没有门拦。本门把「实测遍历所得」从形容词变成可对账的比率：deep-tree 里每个路由屏、
每个（非内容）功能控件，都必须在报告里有归宿（写了 / 声明折叠 + 理由 / TBD）。

诚实边界（本门验得了 / 验不了）：
- 验得了：路由屏有没有被漏写、截图引用真不真、功能控件覆盖率。
- 验不了：报告写得好不好读、控件描述准不准（那归人审）；feed 屏的用户内容不纳入对账
  （由报告用 `type=feed` 显式声明，避免逼人抄用户帖=过度形式化）。

用法: traversal-coverage-gate.py --deep-tree <deep-tree.json> --report <report.md>
      [--events <traversal-events.json>] [--evidence-manifest <evidence-manifest.json>]
      [--threshold 0.9]
      traversal-coverage-gate.py --self-test        # 门自证(绿/红/UNABLE 三态)
退出码(与全队标准一致 STD): 0=通过; 1=有未覆盖或未披露未走全(红); 2=输入缺失/自身异常(UNABLE，绝不折叠成绿)
"""
import argparse, json, re, sys, os, collections
from urllib.parse import urlsplit

def route_of(node):
    if node.get('routeId'):
        return str(node['routeId'])  # explicit role/state-aware scope key, shared by event/report
    url = urlsplit(node.get('url') or '/')
    base = url.path or '/'
    if url.fragment.startswith('/'):
        return (base.rstrip('/') + url.fragment) + ('?' + url.query if url.query else '')
    return base + ('?' + url.query if url.query else '') + ('#' + url.fragment if url.fragment else '')

def is_usercontent(t):
    if re.search(r'\*{4,}\d{3,}', t): return True     # 掩码手机号
    if re.match(r'^[\d\s:]+$', t): return True         # 纯数字/时间
    return False

def denoise_controls(nodes):
    """从 deep-tree 计算每路由的（非内容）功能控件宇宙——与报告生成用同一套过滤。"""
    routes = collections.defaultdict(set)
    for n in nodes:
        r = route_of(n)
        for e in n.get('els', []):
            t = (e.get('txt') or '').strip()
            if not t or t == '[user-content]' or e.get('userContent'): continue
            routes[r].add(t)
    return routes

MARKER = re.compile(r'<!--\s*screen\s+route=(\S+)\s+shot=(\S+)\s+type=(\S+)\s*-->')

def parse_report(md):
    """按 screen 标记切段：返回 {route: {shot, type, text}}。"""
    screens = {}
    marks = list(MARKER.finditer(md))
    for i, m in enumerate(marks):
        route, shot, rtype = m.group(1), m.group(2), m.group(3)
        end = marks[i+1].start() if i+1 < len(marks) else len(md)
        screens[route] = {'shot': shot, 'type': rtype, 'text': md[m.end():end]}
    # 折叠/TBD 台账：整篇里出现的声明（简单以关键词判定有无台账段）
    ledger = ''
    lm = re.search(r'##\s*折叠与\s*TBD.*', md, re.S)
    if lm: ledger = lm.group(0)
    return screens, ledger


EVENT_CLASSES = {'verified', 'observed', 'blocked', 'side-effect', 'non-feature'}


def validate_events(path, manifest_path, data_routes, md):
    """把「点过」升级为可审计事件：每个去噪控件恰好一个分类；verified 必须有前后态与截图。"""
    try:
        raw = json.load(open(path, encoding='utf-8'))
        events = raw.get('events', raw if isinstance(raw, list) else [])
    except Exception as e:
        return [f'[事件账不可读] {e}'], []
    evidence = {}
    errors, lines = [], []
    if manifest_path:
        try:
            mr = json.load(open(manifest_path, encoding='utf-8'))
            for item in mr.get('evidence', []):
                evidence[item.get('id')] = item
        except Exception as e:
            errors.append(f'[证据清单不可读] {e}')
    by_key = collections.defaultdict(list)
    for e in events:
        route, target = str(e.get('route', '')).strip(), str(e.get('target', '')).strip()
        by_key[(route, target)].append(e)
        cls = e.get('classification')
        if cls not in EVENT_CLASSES:
            errors.append(f'[事件分类非法] {e.get("id", "<无ID>")} classification={cls!r}')
            continue
        if cls == 'verified':
            miss = [k for k in ('beforeState', 'action', 'afterState', 'result', 'evidenceId') if not str(e.get(k, '')).strip()]
            if miss:
                errors.append(f'[验证事件不完整] {e.get("id", "<无ID>")} 缺 {miss}')
            evid = e.get('evidenceId')
            if manifest_path and evid not in evidence:
                errors.append(f'[证据悬空] {e.get("id", "<无ID>")} 引用 {evid!r}，证据清单无此 ID')
            if evid and evid not in md:
                errors.append(f'[正文未投影] {e.get("id", "<无ID>")} 的证据 {evid} 未出现在报告正文')
        elif not str(e.get('reason', '')).strip():
            errors.append(f'[非验证事件无理由] {e.get("id", "<无ID>")} classification={cls}')
    universe = {(route, target) for route, controls in data_routes.items() for target in controls}
    for key in sorted(universe):
        n = len(by_key.get(key, []))
        if n == 0:
            errors.append(f'[事件漏记] route={key[0]} target={key[1]}')
        elif n > 1:
            errors.append(f'[事件重复] route={key[0]} target={key[1]} 共 {n} 条，必须恰好一条')
    extra = sorted(set(by_key) - universe)
    for route, target in extra:
        errors.append(f'[事件无来源] route={route} target={target} 不在 deep-tree 去噪控件全集')
    done = sum(1 for key in universe if len(by_key.get(key, [])) == 1)
    verified = sum(1 for key in universe if len(by_key.get(key, [])) == 1
                   and by_key[key][0].get('classification') == 'verified')
    if not universe:
        errors.append('[无可验证范围] 分母为空，不能用 0/0 声称 100%')
    else:
        lines.append(f'  处置有交代 {done}/{len(universe)} = {done / len(universe):.0%}；'
                     f'实测 verified {verified}/{len(universe)} = {verified / len(universe):.0%}')
    return errors, lines

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deep-tree', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--events')
    ap.add_argument('--evidence-manifest')
    ap.add_argument('--threshold', type=float)
    a = ap.parse_args()
    if not os.path.exists(a.deep_tree) or not os.path.exists(a.report):
        print('UNABLE: 输入缺失（deep-tree 或 report 不存在）', file=sys.stderr); return 2
    try:
        _dt = json.load(open(a.deep_tree))
        nodes = _dt['nodes']; coverage = _dt.get('coverage', {})
    except Exception as e:
        print(f'UNABLE: deep-tree 读不了 {e}', file=sys.stderr); return 2
    md = open(a.report, encoding='utf-8').read()

    data_routes = denoise_controls(nodes)
    if not nodes or not any(data_routes.values()):
        print('UNABLE: 未取得可验证的功能范围，0/0 不等于全部通过', file=sys.stderr); return 2
    all_routes = set(route_of(n) for n in nodes)
    all_shots = set(n['shot'] for n in nodes)
    screens, ledger = parse_report(md)

    red = []
    event_lines = []
    threshold = a.threshold if a.threshold is not None else (1.0 if a.events else 0.9)
    if a.events:
        if not os.path.exists(a.events):
            print('UNABLE: --events 文件不存在', file=sys.stderr); return 2
        if a.evidence_manifest and not os.path.exists(a.evidence_manifest):
            print('UNABLE: --evidence-manifest 文件不存在', file=sys.stderr); return 2
        event_errors, event_lines = validate_events(a.events, a.evidence_manifest, data_routes, md)
        red.extend(event_errors)
    # ① 路由覆盖：deep-tree 每个路由屏都要有 screen 标记
    for r in sorted(all_routes):
        if r not in screens:
            red.append(f'[漏屏] 路由 {r} 在 deep-tree 有（实测到过），报告里没有 screen 标记')
    # ② 截图引用真实
    for r, s in screens.items():
        if s['shot'] not in all_shots:
            red.append(f'[假引用] {r} 引用截图 {s["shot"]}，deep-tree 里不存在')
    # ③ 控件覆盖（feed 屏跳过，只查骨架已在路由覆盖里保证）
    cov_report = []
    for r in sorted(all_routes):
        if r not in screens: continue
        # Feed content is excluded only by per-element userContent; real controls stay in scope.
        universe = data_routes.get(r, set())
        if not universe:
            cov_report.append(f'  {r:16} 无功能控件（空屏）✓'); continue
        text = screens[r]['text'] + ledger  # 台账里声明折叠的也算有归宿
        covered = [c for c in universe if c in text]
        ratio = len(covered) / len(universe)
        uncovered = sorted(universe - set(covered))
        flag = '✓' if ratio >= threshold else '✗'
        cov_report.append(f'  {r:16} {len(covered)}/{len(universe)} = {ratio:.0%} {flag}')
        if ratio < threshold:
            red.append(f'[控件漏] {r} 覆盖 {ratio:.0%} < {threshold:.0%}，未写入: {uncovered[:8]}{"…" if len(uncovered)>8 else ""}')
    # ④ 覆盖回执：deep-walk 声明「没走全」时，报告必须写明，否则读者会把「钻到的」当成「全部」
    if coverage.get('complete') is False:
        if not re.search(r'未走全|未走完|未遍历完|遍历.{0,6}未完', md):
            red.append('[未披露] deep-tree 的 coverage.complete=false（遍历未走全），'
                       '报告里没写明「未走全」—— 读者会误把已钻部分当全貌')

    print('== 覆盖对账 ==')
    print(f'deep-tree 路由屏: {len(all_routes)} | 报告 screen 段: {len(screens)}'
          + (f' | coverage.complete={coverage.get("complete")}' if coverage else ''))
    print('\n'.join(cov_report))
    if event_lines:
        print('\n'.join(event_lines))
    print('⚠️ 本门验不了：报告写得准不准、控件描述对不对（归人审）；'
          'feed 屏用户内容刻意不纳入对账。')
    if red:
        print('\n❌ 未覆盖（红）:')
        for x in red: print('  ', x)
        print(f'\n退出码 1：{len(red)} 处未覆盖/未披露，浅报告不予放行。')
        return 1
    print('\n✅ 全部路由屏与功能控件均有归宿；事件模式下每个控件均有唯一可审计处置。')
    return 0

def _self_test():
    """门自证(子进程真跑,复用 tests/traversal-coverage/fixtures/):
      ① 满报告→绿(0) ② 浅报告→红(1) ③ 缺输入→UNABLE(2)
      ④ coverage.complete=false 且报告未披露→红(1) ⑤ 已披露「未走全」→绿(0)
    ④⑤ 用同一份 nodes(路由/控件覆盖不变),只切换 complete + 是否披露 ⇒ 单独锚定 complete 判据。"""
    import subprocess, tempfile
    here = os.path.dirname(os.path.abspath(__file__))
    fx = os.path.join(here, '..', 'tests', 'traversal-coverage', 'fixtures')
    G = os.path.abspath(__file__)
    dt = os.path.join(fx, 'deep-tree.mini.json')
    full_md = os.path.join(fx, 'report-full.mini.md')
    def rc(args):
        return subprocess.run([sys.executable, G] + args, capture_output=True, text=True).returncode
    tmp = tempfile.mkdtemp(prefix='trav-st-')
    d = json.load(open(dt)); d['coverage'] = {'complete': False}
    dtf = os.path.join(tmp, 'dt-incomplete.json'); json.dump(d, open(dtf, 'w'))
    full = open(full_md, encoding='utf-8').read()
    nodis = os.path.join(tmp, 'r-nodisc.md'); io_write(nodis, full)
    dis = os.path.join(tmp, 'r-disc.md'); io_write(dis, full + '\n\n> ⚠️ 遍历未走全：撞上限，前沿仍有未探索节点。\n')
    events_ok = os.path.join(tmp, 'events-ok.json')
    events_bad = os.path.join(tmp, 'events-bad.json')
    manifest = os.path.join(tmp, 'evidence.json')
    controls = denoise_controls(d['nodes'])
    evs = []
    for i, (route, target) in enumerate((x for r, cs in controls.items() for x in [(r, c) for c in cs]), 1):
        evs.append({'id': f'EVENT-{i:03d}', 'route': route, 'target': target,
                    'classification': 'verified', 'beforeState': '初始', 'action': f'点击{target}',
                    'afterState': '完成', 'result': target, 'evidenceId': 'SHOT-001'})
    json.dump({'events': evs}, open(events_ok, 'w'), ensure_ascii=False)
    json.dump({'events': evs[:-1]}, open(events_bad, 'w'), ensure_ascii=False)
    json.dump({'evidence': [{'id': 'SHOT-001', 'sourcePath': 'shot.png', 'anchor': 'SHOT-001'}]}, open(manifest, 'w'), ensure_ascii=False)
    with open(full_md, encoding='utf-8') as f: full_with_shot = f.read() + '\nSHOT-001\n'
    full_event_md = os.path.join(tmp, 'r-event.md'); io_write(full_event_md, full_with_shot)
    cases = [
        ('正例：满报告→绿(0)',                    rc(['--deep-tree', dt,  '--report', full_md]) == 0),
        ('反例：浅报告必红　期望 1',               rc(['--deep-tree', dt,  '--report', os.path.join(fx, 'report-shallow.mini.md')]) == 1),
        ('反例：缺输入必 UNABLE　期望 2',          rc(['--deep-tree', '/nope.json', '--report', full_md]) == 2),
        ('反例：complete=false 未披露必红　期望 1', rc(['--deep-tree', dtf, '--report', nodis]) == 1),
        ('正例：complete=false 已披露→绿(0)',     rc(['--deep-tree', dtf, '--report', dis]) == 0),
        ('正例：事件账逐控件唯一且证据闭环→绿(0)', rc(['--deep-tree', dt, '--report', full_event_md, '--events', events_ok, '--evidence-manifest', manifest]) == 0),
        ('反例：事件账漏一个控件必红→1',          rc(['--deep-tree', dt, '--report', full_event_md, '--events', events_bad, '--evidence-manifest', manifest]) == 1),
    ]
    for n, ok in cases: print(('  ✓ ' if ok else '  ✗ ') + n)
    bad = [n for n, ok in cases if not ok]
    if bad:
        print('❌ 门自证失败: ' + '、'.join(bad)); return 1
    print('✅ 门自证全过(7 例：旧兼容三态 + 未走全披露 + 事件唯一覆盖)'); return 0


def io_write(path, s):
    open(path, 'w', encoding='utf-8').write(s)


# ⛔ `except Exception` 不捕获 `SystemExit`，门禁自己的 exit(0/1/2) 不受影响；
#    未预料异常 → 2(UNABLE)，绝不折叠成 0/1（不许把崩溃伪装成「通过」或「有发现」）。
def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 门禁自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)
    def _entry():
        if '--self-test' in sys.argv:
            sys.exit(_self_test())
        sys.exit(main())
    _main_guarded(_entry)
