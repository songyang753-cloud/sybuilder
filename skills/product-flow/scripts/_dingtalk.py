#!/usr/bin/env python3
"""钉钉在线文档适配器：官方 ``dws`` 写入、回读与图片实体验收。"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))


def _run(args, *, cwd=None, input_text=None):
    if not shutil.which('dws'):
        raise RuntimeError('UNABLE: 本机没有官方钉钉 dws CLI')
    return subprocess.run(['dws'] + args + ['--format', 'json'], cwd=cwd, input=input_text,
                          capture_output=True, text=True, timeout=180)


def _json_output(result, action):
    if result.returncode != 0:
        raise RuntimeError('%s 失败: %s' % (action, result.stderr or result.stdout))
    try:
        data = json.loads(result.stdout)
    except Exception as exc:
        raise RuntimeError('%s 返回非 JSON: %s (%s)' % (action, result.stdout[:500], exc))
    if isinstance(data, dict):
        if data.get('success') is False or data.get('ok') is False or data.get('error'):
            raise RuntimeError('%s 失败: %s' % (action, data.get('error') or data))
        status = str(data.get('status') or '').lower()
        if status in {'partial_success', 'unknown', 'failed', 'failure', 'error'}:
            raise RuntimeError('%s 未形成可宣称成功的终态: %s' % (action, status))
    return data


def _find_value(obj, keys):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and value not in (None, ''):
                return value
        for value in obj.values():
            found = _find_value(value, keys)
            if found not in (None, ''):
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _find_value(value, keys)
            if found not in (None, ''):
                return found
    return None


def _portable_markdown(source_md):
    """Convert SYBuilder's Feishu-capable local image form to standard Markdown."""
    return re.sub(r'\]\(<@\./([^)]+)>\)', r'](./\1)', source_md)


def _source(md_path):
    absolute = os.path.abspath(md_path)
    return absolute, os.path.dirname(absolute), _portable_markdown(
        io.open(absolute, encoding='utf-8').read())


def create(title, md_path):
    from _document_sync import before_create
    before_create(md_path)
    _, workdir, content = _source(md_path)
    data = _json_output(_run(['doc', '+create', '--name', title, '--content', '-'],
                             cwd=workdir, input_text=content), 'dws doc +create')
    ref = _find_value(data, {'documentUrl', 'url', 'nodeId', 'node_id', 'documentId', 'id'})
    if not ref:
        raise RuntimeError('create 成功但找不到文档 URL/nodeId')
    return str(ref)


def update(document_ref, md_path, allow_overwrite=False):
    from _document_sync import before_update
    before_update(md_path, 'dingtalk', document_ref, allow_overwrite)
    _, workdir, content = _source(md_path)
    _json_output(_run(['doc', '+update', '--node', document_ref, '--command', 'overwrite',
                       '--content', '-', '--yes'], cwd=workdir, input_text=content), 'dws doc +update')
    return document_ref


def fetch_data(document_ref):
    return _json_output(_run(['doc', '+fetch', '--node', document_ref]), 'dws doc +fetch')


def fetch(document_ref):
    data = fetch_data(document_ref)
    content = _find_value(data, {'markdown', 'content', 'body', 'text'})
    if not isinstance(content, str):
        raise RuntimeError('fetch 成功但找不到正文；不能冒充完成回读')
    return content, data


def inspect_media(document_ref):
    return _json_output(_run(['doc', '+inspect', '--node', document_ref, '--include-media']),
                        'dws doc +inspect --include-media')


def _verify_text(source_md, readback_md, extra_markers=None):
    from _feishu import verify_readback
    return verify_readback(source_md, readback_md, extra_markers)


def _write_and_verify(title, md_path, extra_markers=None, document_ref=None,
                      evidence_manifest=None, allow_overwrite=False):
    source_md = io.open(md_path, encoding='utf-8').read()
    from _document_sync import preflight, save_readback, delivery_receipt
    preflight(md_path, evidence_manifest)
    ref = update(document_ref, md_path, allow_overwrite) if document_ref else create(title, md_path)
    if not document_ref:
        from _document_sync import register_created
        register_created(md_path, 'dingtalk', ref)
    readback_md, fetch_result = fetch(ref)
    revision = _find_value(fetch_result, {'revision_id', 'revisionId', 'version', 'revision'})
    if revision is None:
        raise RuntimeError('UNABLE: 钉钉未返回原生版本，不能签发交付通过')
    ok, issues = _verify_text(source_md, readback_md, extra_markers)
    try:
        media_result = inspect_media(ref)
        media_revision = _find_value(media_result, {'revision_id', 'revisionId', 'version', 'revision'})
        if str(media_revision) != str(revision):
            raise RuntimeError('文本与媒体回读版本不同或缺版本')
    except Exception as exc:
        ok = False
        issues.append('钉钉媒体回读 UNABLE: %s' % exc)
        media_result = {'mediaReadback': 'UNABLE', 'reason': str(exc)}

    readback_path = save_readback(md_path, json.dumps(
        {'fetch': fetch_result, 'inspect': media_result}, ensure_ascii=False, indent=2), 'json')
    gate = subprocess.run([
        sys.executable, os.path.join(_HERE, 'dingtalk-delivery-gate.py'),
        '--source', os.path.abspath(md_path), '--readback', readback_path,
    ] + (['--evidence-manifest', os.path.abspath(evidence_manifest)] if evidence_manifest else []),
        capture_output=True, text=True, timeout=180)
    if gate.returncode != 0:
        ok = False
        issues.append('钉钉图片交付门未通过:\n' + (gate.stdout or '') + (gate.stderr or ''))
    from _document_sync import finish
    if ok:
        from _document_sync import verify_media_delivery
        verify_media_delivery(md_path, evidence_manifest, media_result, ref, revision)
    ok, issues = finish(md_path, ok, issues, expected_revision=revision)
    delivery_receipt(md_path, 'dingtalk', ref, ok, issues)
    return ref, ok, issues


def create_and_verify(title, md_path, extra_markers=None, document_ref=None,
                      evidence_manifest=None, allow_overwrite=False):
    from _document_sync import begin_attempt, delivery_receipt
    begin_attempt(md_path)
    try:
        return _write_and_verify(title, md_path, extra_markers, document_ref,
                                 evidence_manifest, allow_overwrite)
    except Exception as exc:
        delivery_receipt(md_path, 'dingtalk', document_ref, False, [str(exc)])
        raise


def audience_ok(md_path):
    result = subprocess.run([sys.executable, os.path.join(_HERE, 'audience-gate.py'), md_path],
                            capture_output=True, text=True)
    return result.returncode == 0, (result.stdout or '') + (result.stderr or '')


def push_deliverable(title, md_path, extra_markers=None, document_ref=None,
                     evidence_manifest=None, allow_overwrite=False):
    ok, output = audience_ok(md_path)
    if not ok:
        raise RuntimeError('⛔ 拒绝推送：audience-gate 未通过\n' + output)
    return create_and_verify(title, md_path, extra_markers, document_ref,
                             evidence_manifest=evidence_manifest, allow_overwrite=allow_overwrite)


def _self_test():
    converted = _portable_markdown('![证据](<@./evidence/a.png>)')
    positive = converted == '![证据](./evidence/a.png)'
    negative = _find_value({'result': {'status': 'ok'}}, {'url', 'nodeId'}) is None
    print('  %s 正例：飞书本地图片语法可无损转换为标准 Markdown' % ('✅' if positive else '❌'))
    print('  %s 反例：响应没有文档标识时不会猜造 nodeId' % ('✅' if negative else '❌'))
    print('⚠️ 本自证不访问钉钉，也不证明真实账号权限、网络、文档写入或媒体回读可用。')
    return 0 if positive and negative else 1


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        raise SystemExit(_self_test())
    print(__doc__)
