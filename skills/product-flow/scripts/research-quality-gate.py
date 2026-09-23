#!/usr/bin/env python3
"""S2 review-record gate. Machine validation is NOT a substitute for judgment.
0=PASS, 1=FAIL, 2=UNABLE. --phase final requires current platform receipt and
page-review evidence; pre-publication review alone cannot close S2.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
from _document_sync import source_hash, media_sources
from _section import _iter_headings


def read_record(path):
    text = Path(path).read_text(encoding='utf-8')
    blocks = re.findall(r'^```json\s*\n(.*?)^```\s*$', text, re.M | re.S)
    if len(blocks) != 1: raise ValueError('review-schema: exactly one JSON record required')
    return json.loads(blocks[0])


def bound_inputs(source, review):
    record = read_record(review)
    base = Path(review).resolve().parent
    files = [str(Path(source).resolve()), str(Path(review).resolve())]
    files += [str((Path(source).parent / ref).resolve()) for _, ref in media_sources(Path(source).read_text())]
    for field in ('pageEvidence',):
        files += [str((base / item['path']).resolve()) for item in record.get(field, [])]
    if record.get('receipt'):
        receipt = (base / record['receipt']).resolve()
        files.append(str(receipt))
        if receipt.is_file():
            payload = json.loads(receipt.read_text())
            for key in ('rawEvidenceRef', 'attemptRef', 'sourceRef'):
                if payload.get(key): files.append(str((receipt.parent / payload[key]).resolve()))
            raw = receipt.parent / payload.get('rawEvidenceRef', '')
            if raw.is_file():
                snapshot = json.loads(raw.read_text())
                files += list((snapshot.get('mediaValidation') or {}).get('files', {}))
    return files


def check(source, review, phase='final'):
    record = read_record(review)
    text = Path(source).read_text(encoding='utf-8')
    issues = []
    expected = {str(Path(source).name): source_hash(source)}
    for _, ref in media_sources(text): expected[ref] = source_hash(Path(source).parent / ref)
    if record.get('inputs') != expected: issues.append('review-stale: 正文/图片版本与评审记录不一致')
    afs = set(re.findall(r'(?<!\w)AF-\d+(?!\d)', text))
    sections = {title for _, _, title in _iter_headings(text)}
    reviews = record.get('reviews', [])
    if {r.get('role') for r in reviews} != {'product', 'ux', 'qa'} or len(reviews) != 3:
        issues.append('review-roles: 需产品/UX/测试三个独立判断')
    for r in reviews:
        if (r.get('actorType') not in ('agent', 'human') or not r.get('reviewer') or
                not r.get('reviewedAt') or r.get('decision') != 'APPROVED' or not r.get('rationale')):
            issues.append('review-decision: 缺主体/时间/明确结论及依据')
        if set(r.get('features', [])) != afs or set(r.get('sections', [])) != sections:
            issues.append('review-coverage: 评审未覆盖所有叶子和章节')
    for finding in record.get('findings', []):
        if finding.get('severity') in ('P0', 'P1') and (finding.get('status') != 'CLOSED' or not finding.get('evidence')):
            issues.append('review-open: P0/P1 未关闭')
    if phase == 'final':
        base = Path(review).parent
        receipt = base / record.get('receipt', '')
        if not receipt.is_file():
            issues.append('review-receipt: 缺当前平台交付回执')
        else:
            import importlib.util
            spec = importlib.util.spec_from_file_location('quality_receipt', Path(__file__).with_name('receipt-check.py'))
            gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
            _, bad = gate.check(str(receipt))
            if bad: issues.append('review-receipt: 回执失效 ' + str(bad))
            payload = json.loads(receipt.read_text())
            if (payload.get('receiptSchema') != '2.0'
                    or payload.get('adapter', {}).get('name') != 'doc-sync-guard.readback'
                    or not payload.get('nativeVersion')):
                issues.append('review-receipt-schema: 必须由当前官方适配器签发同版全文与媒体回执')
            if (payload.get('environment') != 'live' or payload.get('sourceHash') != source_hash(source)
                    or payload.get('artifactRef') != record.get('document')):
                issues.append('review-receipt-scope: 必须是当前源稿/文档的 live 回执')
            if str(record.get('nativeVersion', '')) != str(payload.get('nativeVersion', '')):
                issues.append('review-version: 页面审核与平台回读版本不一致')
        if set(record.get('pageSections', [])) != sections or not record.get('pageEvidence'):
            issues.append('review-pages: 需逐页检查至文末，不是首页抽查')
        from _image import validate_image
        covered = set()
        for item in record.get('pageEvidence', []):
            covered.update(item.get('sections', []))
            if not item.get('sections') or str(item.get('nativeVersion', '')) != str(record.get('nativeVersion', '')):
                issues.append('review-page-version: 每张页面截图须注明本版章节范围')
            path = base / item.get('path', '')
            if not path.is_file() or source_hash(path) != item.get('sha256'):
                issues.append('review-page-evidence: 页面截图缺失或已变化')
            else: validate_image(path)
        if covered != sections:
            issues.append('review-page-coverage: 截图记录未覆盖从开头至文末的全部章节')
        if record.get('visualDecision') != 'APPROVED' or not record.get('visualRationale'):
            issues.append('review-visual: 缺图文邻接/比例/可读性/表格/文末的最终判断')
    return issues


def _boundary():
    print('⚠️ 本门只验记录与产物结构，验不了专业判断的真实性；原生页面效果仍需逐页审核。')


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp); src = root / 'report.md'; review = root / 'review.md'
        src.write_text('# Report\n\n## AF-001 Rename\nDetails.')
        record = {'inputs': {'report.md': source_hash(src)}, 'reviews': [
            {'role': role, 'actorType': 'agent', 'reviewer': 'synthetic-reviewer',
             'reviewedAt': '2026-09-23', 'decision': 'APPROVED', 'rationale': 'Synthetic structural fixture only.',
             'features': ['AF-001'], 'sections': ['Report', 'AF-001 Rename']}
            for role in ('product', 'ux', 'qa')]}
        review.write_text('```json\n' + json.dumps(record) + '\n```\n')
        cases = [('正例：pre-review record', not check(src, review, 'pre')),
                 ('反例：pre is not final', bool(check(src, review, 'final')))]
        src.write_text(src.read_text() + ' changed')
        cases.append(('反例：changed report invalidates review', any('review-stale' in x for x in check(src, review, 'pre'))))
        for name, ok in cases: print(('  ✓ ' if ok else '  ✗ ') + name)
        return 0 if all(ok for _, ok in cases) else 1


def main():
    if '--self-test' in sys.argv: return self_test()
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True); p.add_argument('--review', required=True)
    p.add_argument('--phase', choices=['pre', 'final'], default='final')
    a = p.parse_args()
    issues = check(a.source, a.review, a.phase)
    for item in issues: print('❌ ' + item)
    print('⚠️ 只校验评审记录、范围及版本；不冒充真人批准或自动证明专业判断正确。')
    if not issues: print('✅ research-quality ' + a.phase)
    return 1 if issues else 0


def _main_guarded(fn):
    try:
        _boundary()
        sys.exit(fn())
    except Exception as exc:
        print('UNABLE: ' + str(exc), file=sys.stderr); sys.exit(2)


if __name__ == '__main__':
    _main_guarded(main)
