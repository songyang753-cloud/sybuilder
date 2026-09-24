"""Versioned single-product inputs for comparative/full reports.

The manifest is an input index, not a second set of research conclusions. Public
comparison rows remain in the report; paths and feature sets remain in ledgers.
"""
import hashlib
import json
from pathlib import Path
import re


def load_inputs(path):
    if not path:
        raise ValueError('package-required: 正式横比必须提供 research-package.json')
    base = Path(path).resolve().parent
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schemaVersion') != 1 or not data.get('competitors'):
        raise ValueError('package-schema: 缺版本或单品包')
    files = [str(Path(path).resolve())]
    ids = set()
    for comp in data['competitors']:
        if not re.fullmatch(r'COMP-\d+', comp.get('id', '')) or comp['id'] in ids:
            raise ValueError('package-comp: COMP 缺失或重复')
        ids.add(comp['id'])
        for key in ('report', 'ledger', 'evidence', 'events'):
            item = comp.get(key, {})
            p = (base / item.get('path', '')).resolve()
            if base not in p.parents or not p.is_file():
                raise ValueError('package-file: 缺文件或路径越界 ' + key)
            if hashlib.sha256(p.read_bytes()).hexdigest() != item.get('sha256'):
                raise ValueError('package-stale: 单品输入已变化 ' + key)
            comp[key + 'Path'] = str(p)
            files.append(str(p))
        # Also bind referenced image files; a hash of the JSON alone is insufficient.
        evidence = json.loads(Path(comp['evidencePath']).read_text(encoding='utf-8'))
        for item in evidence.get('evidence', []):
            image = (Path(comp['evidencePath']).parent / item.get('sourcePath', '')).resolve()
            if base not in image.parents or not image.is_file():
                raise ValueError('package-image: 缺图或路径越界')
            files.append(str(image))
    return data, files


def check_package(report, path, check_teardown):
    try:
        data, _ = load_inputs(path)
    except (ValueError, OSError) as exc:
        return [('package-input', str(exc))]
    bad, all_af, records = [], set(), {}
    from _section import table_rows_at, section_at
    competitors = {c['id'] for c in data['competitors']}
    for comp in data['competitors']:
        records[comp['id']] = comp
        src = Path(comp['reportPath']).read_text(encoding='utf-8')
        bad += [(key, comp['id'] + ': ' + why) for key, why in
                check_teardown(src, comp['ledgerPath'], comp['evidencePath'], comp['eventsPath'])]
        mapping = comp.get('featureMap', {})
        if not mapping: bad.append(('package-feature-map', comp['id'] + ' 缺公共 AF→原生 AF 对应'))
        ledger = Path(comp['ledgerPath']).read_text(encoding='utf-8')
        # Use the same full dictionary denominator as the single-product gate.
        # A blank line can split a Markdown table; it must not hide later leaves.
        native_ids = set(re.findall(r'(?<!\w)AF-\d+(?!\d)', section_at(ledger, '功能分解词典') or ''))
        mapped_ids = {n for values in mapping.values() if isinstance(values, list) for n in values if isinstance(n, str)}
        if not native_ids or mapped_ids != native_ids:
            bad.append(('package-native-denominator', comp['id'] + ' 原生最细功能全集未完整映射；范围变化须先更新并重新验收单品账本，不能在横比中删叶子'))
        comp['eventRecords'] = {e.get('id'): e for e in json.loads(Path(comp['eventsPath']).read_text()).get('events', [])}
        comp['shotIds'] = {e.get('id') for e in json.loads(Path(comp['evidencePath']).read_text()).get('evidence', [])}
        comp['featureShots'] = {}
        for af, native in mapping.items():
            all_af.add(af)
            if not re.fullmatch(r'AF-\d+', af) or not isinstance(native, list) or any(not isinstance(n, str) for n in native):
                bad.append(('package-feature-map', comp['id'] + ' 功能映射非法')); continue
            if any(not re.search(r'(?<!\w)' + re.escape(n) + r'(?!\d)', ledger) for n in native):
                bad.append(('package-feature-map', comp['id'] + ' 原生功能不在账本'))
            for n in native:
                body = section_at(src, r'(?<!\w)' + re.escape(n) + r'(?!\d)', regex=True) or ''
                comp['featureShots'][n] = set(re.findall(r'\bSHOT-\d+\b', body))
    nodes = data.get('comparisonNodes', [])
    byid = {n.get('id'): n for n in nodes}
    if not nodes or len(byid) != len(nodes):
        bad.append(('comparison-nodes', '横比范围缺节点或重复'))
    leaf_union = set()
    for comp in data['competitors']:
        if set(comp.get('featureMap', {})) != all_af:
            bad.append(('package-denominator', comp['id'] + ' 必须对全部公共 AF 显式映射；未知/缺席也不能删行'))
    for n in nodes:
        afs = set(n.get('features', []))
        children = [c for c in nodes if c.get('parent') == n.get('id')]
        if children:
            if set().union(*(set(c.get('features', [])) for c in children)) != afs:
                bad.append(('comparison-tree', '父节点必须由子节点完整覆盖，不能隐藏叶子'))
        else:
            leaf_union |= afs
            if len(afs) != 1:
                bad.append(('comparison-leaves', '末级节点必须是单一原子功能，不能用组合功能提前停止下钻'))
        parent = n.get('parent')
        if not afs or not afs <= all_af or (parent and parent not in byid):
            bad.append(('comparison-tree', '层级/父节点/叶子集合不完整'))
        seen = {n.get('id')}; current = parent
        while current in byid:
            if current in seen:
                bad.append(('comparison-cycle', '横比节点存在循环')); break
            seen.add(current); current = byid[current].get('parent')
        if parent in byid and not afs <= set(byid[parent].get('features', [])):
            bad.append(('comparison-tree', '子节点叶子不属于父节点'))
    if leaf_union != all_af or any(not any(set(n.get('features', [])) == {af} for n in nodes) for af in all_af):
        bad.append(('comparison-leaves', '必须逐层比到每个公共 AF，不能只比模块'))
    # Explicit long-form matrix handles products with different native trees.
    section = section_at(report, '逐节点逐竞品对比') or ''
    rows = table_rows_at(section, '节点') or []
    for line in section.splitlines():
        if line.strip().startswith('|') and len(re.split(r'(?<!\\)\|', line.strip().strip('|'))) != 6:
            bad.append(('comparison-row', '比较表含列数错误；不能把损坏尾行静默忽略'))
    pairs = set()
    for row in rows[1:] if rows and '节点' in rows[0][0] else rows:
        if len(row) != 6:
            bad.append(('comparison-row', '需六列：节点/COMP/状态/原生路径/依据/影响')); continue
        node, comp, status, native, evidence, impact = [x.strip(' `') for x in row]
        if (node, comp) in pairs: bad.append(('comparison-duplicate', '重复比较行'))
        pairs.add((node, comp))
        if status not in ('FULL', 'PARTIAL', 'ABSENT', 'UNKNOWN', 'N/A') or not all((native, evidence, impact)):
            bad.append(('comparison-status', '比较状态/路径/依据/影响缺失'))
        if status == 'ABSENT' and (not re.search(r'已检索|范围内未发现', evidence) or
                                   re.search(r'阻断|未授权|未获授权|登录墙|未知', evidence)):
            bad.append(('absence-not-proven', '未知/阻断不等于不存在'))
        if node not in byid or comp not in competitors: bad.append(('comparison-scope', '范围外比较项'))
        elif status in ('FULL', 'PARTIAL'):
            item = records[comp]
            events = re.findall(r'EVENT-\d+', evidence)
            shots = set(re.findall(r'SHOT-\d+', evidence))
            if (not events or not shots or not shots <= item['shotIds']
                    or any(e not in item['eventRecords'] or item['eventRecords'][e].get('classification') != 'verified' for e in events)
                    or not any(item['eventRecords'].get(e, {}).get('evidenceId') in shots for e in events)):
                bad.append(('comparison-evidence', '支持性结论必须引用本竞品真实验证且成对的 EVENT/SHOT；观察或未知不能冒充支持'))
            if status == 'FULL' and any(not item['featureMap'].get(af) for af in byid[node].get('features', [])):
                bad.append(('comparison-evidence', 'FULL 节点下每个 AF 都必须有原生功能映射'))
            native_features = {n for af in byid[node].get('features', []) for n in item['featureMap'].get(af, [])}
            node_shots = set().union(*(item['featureShots'].get(n, set()) for n in native_features))
            if not shots or not shots <= node_shots:
                bad.append(('comparison-node-evidence', '证据必须属于当前节点的原生功能正文，不能借同竞品的其他功能或附图'))
            if status == 'FULL' and any(not shots.intersection(item['featureShots'].get(n, set())) for n in native_features):
                bad.append(('comparison-node-evidence', 'FULL 必须覆盖当前节点下每个原生功能的证据'))
    expected = {(n, c) for n in byid for c in competitors}
    if pairs != expected: bad.append(('comparison-set', '逐级节点×全部竞品行集不完整或多出'))
    return bad


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        import runpy
        from pathlib import Path
        from _workflow import suite_script
        try:
            test_path = suite_script('test-remediation-contracts.py')
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(2)
        tests = runpy.run_path(str(test_path))
        sys.exit(tests['main']('research'))
