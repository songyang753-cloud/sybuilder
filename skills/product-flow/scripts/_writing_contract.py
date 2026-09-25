"""Shared writing checks. Structural checks do not certify semantic truth.

Business facts stay in Markdown; this module reads them, never rewrites them.
"""
import hashlib
import json
from pathlib import Path
import re
from _section import _blank_fenced, _iter_headings

SPEC = json.loads((Path(__file__).resolve().parents[1] / 'spec/_writing-contract.json').read_text())
BRANCH_TYPES = set(SPEC['branchTypes'])
BEHAVIOR_COLUMNS = tuple(SPEC['behaviorColumns'])
QUESTIONS = SPEC['consumerQuestions']
EMPTY = re.compile(r'^(?:[-—/\s]*|TBD|TODO|待补|待定|同上|略|<[^>]+>|⟨TODO⟩)$', re.I)
GENERIC = re.compile(r'^(?:按(?:页面提示|产品要求|实际情况|常规)(?:处理|操作)?|执行操作|完成任务|支持恢复|相关文案)[。.!！]?$')


def meaningful(value):
    return isinstance(value, str) and not EMPTY.fullmatch(value.strip()) and not GENERIC.fullmatch(value.strip())


def tables(text):
    """Read ordinary Markdown tables, ignoring fenced teaching examples."""
    lines = _blank_fenced(text).splitlines()
    i = 0
    while i + 1 < len(lines):
        if not lines[i].strip().startswith('|') or not re.fullmatch(r'[\s|:\-]+', lines[i + 1]):
            i += 1
            continue
        cells = lambda line: [x.strip().strip('`*') for x in re.split(r'(?<!\\)\|', line.strip().strip('|'))]
        header = cells(lines[i])
        rows = []
        i += 2
        while i < len(lines) and lines[i].strip().startswith('|'):
            values = cells(lines[i])
            if len(values) != len(header):
                raise ValueError('table-shape: table row/column mismatch at line %s' % (i + 1))
            rows.append(dict(zip(header, values)))
            i += 1
        yield header, rows


def feature_ids(text):
    """Feature denominator: the ID/name inventory, never arbitrary mentions."""
    ids = []
    for columns, rows in tables(text):
        if 'ID' in columns and any(x in columns for x in ('功能名称', '功能')):
            ids.extend(row['ID'] for row in rows if re.fullmatch(r'F-\d+', row['ID']))
    if len(ids) != len(set(ids)):
        raise ValueError('feature-duplicate: repeated F in inventories')
    return set(ids)


def section_exact(text, heading):
    lines = text.splitlines()
    heads = list(_iter_headings(text))
    hits = [(ln, lv) for ln, lv, title in heads if title == heading]
    if len(hits) != 1:
        return ''
    start, level = hits[0]
    end = next((ln for ln, lv, _ in heads if ln > start and lv <= level), len(lines))
    return '\n'.join(lines[start:end])


def scope_issues(upstream, downstream):
    """Explicit scope decisions are authoritative in upstream, not self-waived."""
    expected, actual = feature_ids(upstream), feature_ids(downstream)
    issues = []
    if not expected or not actual:
        return ['scope-input: upstream and downstream need a functional inventory']
    resolved_old, resolved_new = set(), set()
    for cols, rows in tables(upstream):
        if not {'原功能', '目标功能', '处置', '理由', '批准依据'}.issubset(cols):
            continue
        for row in rows:
            old = set(re.findall(r'(?<!\w)F-\d+', row['原功能']))
            new = set(re.findall(r'(?<!\w)F-\d+', row['目标功能']))
            disposition = row['处置']
            if (disposition not in ('新增', '删除', '拆分', '合并') or
                    row.get('状态') != 'APPROVED' or
                    not all(meaningful(row[k]) for k in ('理由', '批准依据')) or
                    not old.issubset(expected) or not new.issubset(actual) or
                    (disposition == '新增' and (old or not new)) or
                    (disposition == '删除' and (not old or new)) or
                    (disposition == '拆分' and (len(old) != 1 or len(new) < 2)) or
                    (disposition == '合并' and (len(old) < 2 or len(new) != 1))):
                issues.append('scope-decision: invalid or unapproved feature disposition')
                continue
            resolved_old.update(old)
            resolved_new.update(new)
    for fid in sorted(expected - actual - resolved_old):
        issues.append('scope-missing: ' + fid)
    for fid in sorted(actual - expected - resolved_new):
        issues.append('scope-unrequested: ' + fid)
    return issues


def behavior_issues(text, features, research=False):
    """Check explicit transition records in existing leaf bodies/appendix E.

Branch names start with a type, e.g. failure.network. A next step is END:reason,
WAIT:monitor/cancel policy, or one or more F/AF#branch links. Unknown research
branches stay unknown; they cannot establish a verified normal path.
"""
    from _prd_parse import acceptance_records, appendix
    # PRD behavior belongs to E. A table elsewhere cannot fill an empty E.
    behavior_source = text if research else (appendix(text, '# 附件 E', '# 附件 F') or '')
    rows = []
    for columns, values in tables(behavior_source):
        if '分支' in columns and '前态' in columns:
            if not set(BEHAVIOR_COLUMNS).issubset(columns):
                return ['behavior-columns: ' + '/'.join(BEHAVIOR_COLUMNS)]
            rows.extend(values)
    issues, keys, kinds = [], set(), {fid: set() for fid in features}
    acceptance = {} if research else acceptance_records(text)
    for row in rows:
        fid, branch = row['功能'], row['分支']
        key = fid + '#' + branch
        typ = branch.split('.')[0]
        if fid not in features or typ not in BRANCH_TYPES or key in keys:
            issues.append('behavior-identity: ' + key)
        keys.add(key)
        kinds.setdefault(fid, set()).add(typ)
        na = bool(re.match(r'^N/A[:：]', row['前态']))
        unknown = bool(re.match(r'^UNKNOWN[:：]', row['前态']))
        if na or unknown:
            if (typ == 'normal' or (unknown and not research) or
                    not meaningful(re.split(r'[:：]', row['前态'], maxsplit=1)[1]) or
                    not meaningful(row['依据']) or not meaningful(row['下一步'])):
                issues.append('behavior-disposition: ' + key)
            continue
        for field in BEHAVIOR_COLUMNS[2:]:
            if not meaningful(row[field]):
                issues.append('behavior-content: %s/%s' % (key, field))
        if not research:
            refs = re.findall(r'((?:N?FR)-[\w-]*\d+)\s*/\s*(AC-\d+)', row['依据'])
            if not refs or any(acceptance.get(tuple(ref)) not in (fid, '全局') for ref in refs):
                issues.append('behavior-acceptance: %s needs executable owned FR/AC references' % key)
    for fid in sorted(features):
        missing = BRANCH_TYPES - kinds.get(fid, set())
        if missing:
            issues.append('behavior-coverage: %s missing %s (declare applicable, N/A with reason, or research UNKNOWN)' % (fid, ','.join(sorted(missing))))
    exits, edges = set(), {}
    for row in rows:
        if re.match(r'^(?:N/A|UNKNOWN)[:：]', row['前态']):
            continue
        key = row['功能'] + '#' + row['分支']
        target = row['下一步']
        links = re.findall(r'((?:AF|F)-\d+#[a-z]+(?:\.[\w-]+)*)', target)
        terminal = re.match(r'^(END|WAIT)[:：]\s*(.+)', target)
        edges[key] = set(links)
        if terminal and meaningful(terminal.group(2)):
            exits.add(key)
        if not links and not (terminal and meaningful(terminal.group(2))):
            issues.append('behavior-exit: %s#%s' % (row['功能'], row['分支']))
        for link in links:
            if link not in keys:
                issues.append('behavior-dangling: ' + link)
    # Loops are valid only if a documented exit or managed wait is reachable.
    reachable = set(exits)
    while True:
        expanded = reachable | {key for key, targets in edges.items() if targets & reachable}
        if expanded == reachable:
            break
        reachable = expanded
    for key in sorted(set(edges) - reachable):
        issues.append('behavior-no-exit: ' + key)
    return issues


def review_files(record, base):
    """Only declared evidence within the review package; no machine-wide probing."""
    base = Path(base).resolve()
    result = []
    for item in record.get('reviews', []):
        trace = item.get('trace', {})
        if not isinstance(trace, dict) or not isinstance(trace.get('path'), str):
            raise ValueError('consumer-trace: review requires a trace path/hash')
        path = Path(trace['path'])
        target = (base / path).resolve()
        if path.is_absolute() or base not in target.parents or not target.is_file():
            raise ValueError('consumer-trace: evidence must be a file within the review package')
        result.append(str(target))
    return result


def consumer_issues(text, record, features, base):
    """Bind independent consumer answers to exact passages; not an AI judge."""
    issues = []
    author = record.get('authorSession')
    if not meaningful(author):
        issues.append('consumer-author: missing writer session')
    sessions = set()
    traces = review_files(record, base)
    for review, trace in zip(record.get('reviews', []), traces):
        role = review.get('role')
        session = review.get('sessionId')
        if not meaningful(session) or session == author or session in sessions:
            issues.append('consumer-independent: distinct actual review sessions required')
        sessions.add(session)
        raw = Path(trace).read_bytes()
        if not raw or hashlib.sha256(raw).hexdigest() != review['trace'].get('sha256'):
            issues.append('consumer-trace-stale: missing or changed independent review trace')
        answers = review.get('consumption', [])
        if not isinstance(answers, list):
            raise ValueError('consumer-schema: consumption must be an array')
        got = [(a.get('feature'), a.get('question')) for a in answers if isinstance(a, dict)]
        expected = {(fid, q) for fid in features for q in QUESTIONS.get(role, ())}
        if len(got) != len(set(got)) or set(got) != expected:
            issues.append('consumer-coverage: %s answers must cover each leaf/question exactly once' % role)
        for answer in answers:
            if not isinstance(answer, dict):
                raise ValueError('consumer-schema: answer must be an object')
            excerpt = answer.get('quote', '')
            paragraph = section_exact(text, answer.get('section', ''))
            fid = answer.get('feature', '')
            owns_section = isinstance(fid, str) and re.search(r'(?<![\w-])' + re.escape(fid) + r'(?![\w-])', answer.get('section', ''))
            if (not owns_section or not meaningful(answer.get('answer')) or answer.get('decision') != 'PASS' or
                    not meaningful(excerpt) or not paragraph or excerpt not in paragraph):
                issues.append('consumer-evidence: %s/%s needs an answer and exact body citation' % (answer.get('feature'), answer.get('question')))
    batches = record.get('batches', [])
    if not isinstance(batches, list):
        raise ValueError('batch-schema: batches must be an array')
    covered = []
    batch_ids = set()
    for index, batch in enumerate(batches):
        if not isinstance(batch, dict):
            raise ValueError('batch-schema: batch must be an object')
        units = batch.get('units', [])
        if not isinstance(units, list) or any(not isinstance(u, dict) for u in units):
            raise ValueError('batch-schema: units must be an array of objects')
        if not meaningful(batch.get('id')) or batch.get('id') in batch_ids:
            issues.append('batch-identity: unique batch ID required')
        batch_ids.add(batch.get('id'))
        if (not units or batch.get('status') != 'APPROVED' or
                (index == 0 and batch.get('kind') != 'sample') or
                (index > 0 and batch.get('calibratedBy') != batches[0].get('id')) or
                batch.get('reviewSessions') != [r.get('sessionId') for r in record.get('reviews', [])]):
            issues.append('batch-approval: sample first; each batch needs actual review evidence')
        for unit in units:
            body = section_exact(text, unit.get('section', ''))
            covered.append(unit.get('feature'))
            digest = hashlib.sha256(body.encode()).hexdigest()
            fid = unit.get('feature', '')
            owns_section = isinstance(fid, str) and re.search(r'(?<![\w-])' + re.escape(fid) + r'(?![\w-])', unit.get('section', ''))
            if not owns_section or not body or digest != unit.get('sha256'):
                issues.append('batch-stale: accepted body changed or was compressed: ' + str(unit.get('feature')))
    if set(covered) != features or len(covered) != len(set(covered)):
        issues.append('batch-coverage: accepted batches must cover every leaf once')
    return issues


if __name__ == '__main__':
    import runpy
    import sys
    if '--self-test' in sys.argv:
        gate = runpy.run_path(str(Path(__file__).with_name('prd-quality-gate.py')))
        sys.exit(gate['self_test']())
