#!/usr/bin/env python3
"""feishu supplied-artifact delivery checks. 0=PASS, 1=FAIL, 2=UNABLE.
Offline PASS is not proof that a platform write took place.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path
from _delivery_check import check as shared_check

def check(source_path, readback_path, manifest_path=None, markdown_readback=None):
    return shared_check(source_path, readback_path, manifest_path, markdown_readback, 'feishu')


def _boundary():
    print('⚠️ 本门只验记录与产物结构，验不了专业判断的真实性；原生页面效果仍需逐页审核。')


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        from PIL import Image
        root = Path(tmp)
        Image.new('RGB', (16, 16), 'white').save(root / 'a.png')
        source, readback, manifest = root / 'r.md', root / 'r.native', root / 'e.json'
        source.write_text('# Report\n\n## Feature\n\nUsers may cancel.\n\n![SHOT-001](./a.png)\n')
        manifest.write_text(json.dumps({'evidence': [
            {'id': 'SHOT-001', 'sourcePath': 'a.png', 'anchor': 'Feature'}]}))
        native = '<title>Report</title><heading>Feature</heading><p>Users may cancel.</p><image token="m1"/>'
        readback.write_text(native)
        cases = [('complete body and image', not check(source, readback, manifest)[0])]
        readback.write_text(native.replace('Users may cancel.', 'Users may not cancel.'))
        cases.append(('反例：negation mutation', any('body-mismatch' in x for x in check(source, readback, manifest)[0])))
        readback.write_text(native.replace('m1', ''))
        cases.append(('反例：empty image entity', any('media-count' in x for x in check(source, readback, manifest)[0])))
        readback.write_text(native)
        (root / 'a.png').write_bytes(b'not a real image')
        cases.append(('反例：corrupt local image', any('media-source' in x for x in check(source, readback, manifest)[0])))
        for name, ok in cases: print(('  ✓ ' if ok else '  ✗ ') + name)
        return 0 if all(ok for _, ok in cases) else 1


def main():
    if '--self-test' in sys.argv: return self_test()
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--readback', required=True)
    p.add_argument('--readback-markdown', help='same-version structured Markdown; adapter verifies revision')
    p.add_argument('--evidence-manifest')
    p.add_argument('--receipt')
    a = p.parse_args()
    issues, local, remote = check(a.source, a.readback, a.evidence_manifest, a.readback_markdown)
    for issue in issues: print('❌ ' + issue)
    if a.receipt:
        Path(a.receipt).write_text(json.dumps({'gate': 'feishu-delivery-gate',
            'verificationScope': 'supplied-artifacts-only', 'live': False,
            'source': str(Path(a.source).resolve()), 'readback': str(Path(a.readback).resolve()),
            'localImages': local, 'remoteImages': remote,
            'status': 'FAIL' if issues else 'PASS', 'issues': issues}, ensure_ascii=False))
    print('⚠️ 本门只验传入产物；真实写入/同版本回读由适配器验证，页面图文效果仍须逐页审核。')
    if not issues: print('✅ 正文与图片结构通过')
    return 1 if issues else 0


def _main_guarded(fn):
    try:
        _boundary()
        sys.exit(fn())
    except Exception as exc:
        print('UNABLE: ' + str(exc), file=sys.stderr); sys.exit(2)


if __name__ == '__main__':
    _main_guarded(main)
