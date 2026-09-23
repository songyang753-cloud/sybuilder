"""Offline content/media verification shared by both platform gates.

This checks supplied artifacts; only adapters can issue a live same-version receipt.
Unknown native structures must be supplied as a same-version Markdown export, never
flattened into text or silently skipped.
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from _document_sync import content_model, media_contexts, preflight, verify_media_delivery


def xml_markdown(raw):
    if re.search(r'<!DOCTYPE|<!ENTITY', raw, re.I):
        raise RuntimeError('UNABLE: native XML contains unsupported declarations')
    try:
        root = ET.fromstring('<document>' + raw + '</document>')
    except ET.ParseError as exc:
        raise RuntimeError('UNABLE: native XML is not parseable') from exc
    def render(e):
        tag = e.tag
        text = (e.text or '') + ''.join(render(c) + (c.tail or '') for c in e)
        if tag in ('document', 'body'): return text
        if tag in ('image', 'img'): return ''
        if tag == 'title': return '# ' + text + '\n\n'
        if tag == 'heading' or re.fullmatch(r'h[1-6]', tag):
            level = e.get('level', '2') if tag == 'heading' else tag[1:]
            if level not in list('123456'): raise RuntimeError('UNABLE: unknown heading level')
            return '#' * int(level) + ' ' + text + '\n\n'
        if tag in ('p', 'paragraph'): return text + '\n\n'
        if tag in ('span', 'text', 'strong', 'b', 'em', 'i'): return text
        if tag == 'br': return '\n'
        if tag == 'a': return '[' + text + '](' + e.get('href', '') + ')'
        raise RuntimeError('UNABLE: unsupported native block ' + tag + '; supply same-version Markdown')
    return render(root)


def _content(value):
    if isinstance(value, dict):
        for key in ('markdown', 'content'):
            if isinstance(value.get(key), str): return value[key]
        for key in ('fetch', 'data', 'result'):
            if key in value:
                got = _content(value[key])
                if got is not None: return got
    return None


def check(source, readback, manifest=None, markdown_readback=None, platform='feishu'):
    src = Path(source).read_text(encoding='utf-8')
    raw = Path(readback).read_text(encoding='utf-8')
    native = json.loads(raw) if platform == 'dingtalk' else raw
    md = (Path(markdown_readback).read_text(encoding='utf-8') if markdown_readback else
          _content(native) if platform == 'dingtalk' else xml_markdown(raw))
    if md is None: raise RuntimeError('UNABLE: native response has no structured body')
    issues = []
    if content_model(src) != content_model(md):
        issues.append('body-mismatch: 正文、标题、表格、链接、代码或顺序与源稿不同')
    images = media_contexts(src)
    if re.search(r'待补图|图片占位|截图占位', src):
        issues.append('placeholder: 图片必须为已渲染实图')
    try:
        preflight(source, manifest, for_write=False)
    except (RuntimeError, ValueError) as exc:
        issues.append('media-source: ' + str(exc))
    remote = []
    if isinstance(native, str):
        from html.parser import HTMLParser
        class Media(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag in ('image', 'img'):
                    a = dict(attrs); remote.append(a.get('token') or a.get('file_token') or a.get('src') or '')
        Media().feed(native)
    else:
        def visit(v):
            if isinstance(v, dict):
                if str(v.get('type') or v.get('blockType') or '').lower() in ('image', 'picture'):
                    remote.append(v.get('mediaId') or v.get('resourceId') or v.get('fileId') or '')
                for c in v.values(): visit(c)
            elif isinstance(v, list):
                for c in v: visit(c)
        # fetch and inspect may duplicate entities: inspect is the ordered media view.
        visit(native.get('inspect', native) if isinstance(native, dict) else native)
    if any(not str(x).strip() for x in remote) or len(remote) != len(images):
        issues.append('media-count: 原生图片实体缺失、空标识或多出图片')
    if manifest:
        payload = json.loads(Path(manifest).read_text(encoding='utf-8'))
        if payload.get('delivery'):
            delivery = payload['delivery']
            try:
                view = native.get('inspect', native) if isinstance(native, dict) else native
                verify_media_delivery(source, manifest, view, delivery.get('document'),
                                      delivery.get('nativeVersion'), record=False)
            except RuntimeError as exc: issues.append('media-binding: ' + str(exc))
        for alt, ref, anchor in images:
            matches = [e for e in payload.get('evidence', []) if
                       (Path(manifest).parent / e.get('sourcePath', '')).resolve() ==
                       (Path(source).parent / ref).resolve() and e.get('anchor') == anchor]
            if len(matches) != 1 or matches[0].get('id', 'missing') not in alt:
                issues.append('media-anchor: 图片没有唯一且相邻的功能证据映射')
    return issues, len(images), len(remote)


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        import runpy
        from pathlib import Path
        tests = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/test-remediation-contracts.py'))
        sys.exit(tests['main']('delivery'))
