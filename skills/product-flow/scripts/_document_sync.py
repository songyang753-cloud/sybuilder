"""Shared write guard; uses the existing sync contract, not a second baseline."""
import importlib.util
import json
import re
import hashlib
import uuid
import os
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

_GUARD = None


def _parser():
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise RuntimeError('UNABLE: 缺 markdown-it-py；安装套件 requirements.txt') from exc
    return MarkdownIt('commonmark').enable('table')


class _Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag in ('img', 'image'):
            values = dict(attrs)
            self.images.append((values.get('alt', ''), values.get('path') or values.get('src') or ''))


def media_sources(markdown):
    """All supported Markdown/reference and HTML/XML image forms, in order."""
    return [(alt, ref) for alt, ref, _ in media_contexts(markdown)]


def media_contexts(markdown):
    """Keep each image's actual nearest source heading, not a manifest assertion."""
    images = []
    anchor, in_heading = '', False
    for token in _parser().parse(markdown):
        if token.type == 'heading_open':
            anchor, in_heading = '', True
        elif token.type == 'heading_close':
            in_heading = False
        if in_heading and token.type == 'inline':
            anchor = ''.join(t.content for t in token.children or [] if t.type in ('text', 'code_inline')).strip()
        for item in token.children or [token]:
            if item.type == 'image':
                images.append((item.content, item.attrGet('src') or '', anchor))
            elif item.type in ('html_inline', 'html_block'):
                html = _Images(); html.feed(item.content)
                images.extend((alt, ref, anchor) for alt, ref in html.images)
    return [(alt, ref.lstrip('@'), anchor) for alt, ref, anchor in images]


def content_model(markdown):
    """Ordered block/inline content. Only presentation and media URLs are normalized.

    Images are separately bound through the media manifest. Code, numbers, words,
    links, table cells and negations remain significant. Unsupported rich blocks
    are preserved literally, so we cannot silently certify a lossy conversion.
    """
    result = []
    for token in _parser().parse(markdown):
        if token.type == 'inline':
            parts = []
            for item in token.children or []:
                if item.type == 'image':
                    continue
                if item.type in ('html_inline', 'html_block'):
                    value = re.sub(r'<!--.*?-->|<(?:img|image)\b[^>]*>', '', item.content, flags=re.S | re.I)
                    if value.strip(): parts.append(value)
                elif item.type in ('text', 'code_inline'):
                    parts.append(item.content)
                elif item.type in ('softbreak', 'hardbreak'):
                    parts.append(' ')
                elif item.type == 'link_open':
                    parts.append('[link:' + (item.attrGet('href') or '') + ']')
            content = re.sub(r'\s+', ' ', ''.join(parts)).strip()
            # Known platform artifact: adjacent bold spans around inline code.
            content = content.replace('****', '')
            if content:
                result.append(['inline', content])
        elif token.type in ('html_block',):
            value = re.sub(r'<!--.*?-->|<(?:img|image)\b[^>]*>', '', token.content, flags=re.S | re.I).strip()
            if value: result.append(['html', value])
        elif token.type in ('fence', 'code_block'):
            result.append(['code', token.info, token.content.rstrip('\n')])
        elif token.type not in ('paragraph_open', 'paragraph_close'):
            result.append([token.type, token.tag, token.attrGet('start')])
    return result


def source_hash(source):
    return hashlib.sha256(Path(source).read_bytes()).hexdigest()


def verify_media_delivery(source, manifest, native, document, revision, record=True):
    """Bind each local image to a same-version native image in its actual section.

    `delivery` is produced by the upload adapter, never inferred from image counts.
    Its raw upload evidence must contain the exact source-hash/media-id pair. A CLI
    without that evidence or ordered native blocks is UNABLE, not silently trusted.
    """
    images = media_contexts(Path(source).read_text(encoding='utf-8'))
    if not images:
        return
    payload = json.loads(Path(manifest).read_text(encoding='utf-8'))
    delivery = payload.get('delivery') or {}
    if delivery.get('document') != document or str(delivery.get('nativeVersion')) != str(revision):
        raise RuntimeError('UNABLE: 缺同一文档/原生版本的逐图上传映射')
    upload = Path(manifest).parent / delivery.get('uploadEvidenceRef', '')
    if not upload.is_file() or source_hash(upload) != delivery.get('uploadEvidenceHash'):
        raise RuntimeError('UNABLE: 逐图上传原始证据缺失或已变化')
    raw_upload = json.loads(upload.read_text(encoding='utf-8'))
    pairs = set()
    def walk(value):
        if isinstance(value, dict):
            if value.get('sourceHash') and value.get('mediaId'):
                pairs.add((value['sourceHash'], value['mediaId']))
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(raw_upload)
    # Ordered native block normalization. Unknown layouts cannot prove placement.
    remote = []
    if isinstance(native, str):
        class Native(HTMLParser):
            def __init__(self):
                super().__init__(); self.anchor = ''; self.in_heading = False
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag in ('title', 'heading', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    self.anchor = ''; self.in_heading = True
                if tag in ('image', 'img'):
                    remote.append((attrs.get('token') or attrs.get('file_token') or attrs.get('src'), self.anchor.strip()))
            def handle_endtag(self, tag):
                if tag in ('title', 'heading', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'): self.in_heading = False
            def handle_data(self, data):
                if self.in_heading: self.anchor += data
        Native().feed(native)
    else:
        def blocks(value, anchor=''):
            if isinstance(value, list):
                for item in value:
                    anchor = blocks(item, anchor)
            elif isinstance(value, dict):
                kind = str(value.get('type') or value.get('blockType') or '').lower()
                if kind in ('heading', 'title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    anchor = value.get('text') or value.get('content') or ''
                if kind in ('image', 'picture'):
                    remote.append((value.get('mediaId') or value.get('resourceId') or value.get('fileId'),
                                   value.get('sectionTitle') or anchor))
                for key in ('blocks', 'children', 'data', 'result'):
                    if key in value: anchor = blocks(value[key], anchor)
            return anchor
        blocks(native)
    mappings = delivery.get('images') or []
    if len(mappings) != len(images):
        raise RuntimeError('UNABLE: 逐图上传映射数量与源稿不一致')
    evidence = payload.get('evidence') or []
    expected_remote = []
    for (_, path, anchor), item in zip(images, mappings):
        digest = source_hash(Path(source).parent / path)
        matches = [e for e in evidence if e.get('id') == item.get('evidenceId') and
                   (Path(manifest).parent / e.get('sourcePath', '')).resolve() == (Path(source).parent / path).resolve()]
        if len(matches) != 1 or (digest, item.get('mediaId')) not in pairs or item.get('sourceHash') != digest:
            raise RuntimeError('FAIL: 源图与上传媒体身份无法对应')
        if not anchor or matches[0].get('anchor') != anchor:
            raise RuntimeError('FAIL: 证据清单锚点与源图实际所在章节不一致')
        expected_remote.append((item.get('mediaId'), anchor))
    if expected_remote != remote:
        raise RuntimeError('FAIL: 原生媒体缺失、增多、顺序变化或位于错误章节')
    if not record:
        return
    attempt = json.loads(Path(str(source) + '.attempt.json').read_text())
    indirect = [Path(manifest).parent / e[k] for e in evidence
                for k in ('eventsRef', 'sourceRef', 'svgRef', 'renderReceiptRef') if e.get(k)]
    proof = {'attemptId': attempt['attemptId'], 'sourceHash': source_hash(source),
             'document': document, 'nativeVersion': str(revision),
             'files': {str(p.resolve()): source_hash(p) for p in
                       [Path(manifest), upload] + indirect + [Path(source).parent / p for _, p, _ in images]}}
    Path(str(source) + '.media-validation.json').write_text(json.dumps(proof), encoding='utf-8')


def current_media_validation(source, attempt, document, revision):
    if not media_sources(Path(source).read_text(encoding='utf-8')):
        return None
    try:
        proof = json.loads(Path(source + '.media-validation.json').read_text())
        if (proof['attemptId'] == attempt['attemptId'] and proof['sourceHash'] == source_hash(source)
                and proof['document'] == document and proof['nativeVersion'] == str(revision)
                and proof['files'] and all(source_hash(p) == h for p, h in proof['files'].items())):
            return proof
    except (OSError, ValueError, KeyError):
        pass
    raise RuntimeError('UNABLE: 当前回读缺逐图身份/章节/同版本验证；请用平台适配器完整回读')


def begin_attempt(source):
    record = {'attemptId': uuid.uuid4().hex, 'status': 'RUNNING', 'sourceHash': source_hash(source)}
    Path(source + '.attempt.json').write_text(json.dumps(record), encoding='utf-8')
    return record


def check_export_privacy(source, evidence, manifest):
    """Scan the exact declared export/dependency set, not unrelated local projects."""
    root = Path(source).resolve().parent
    paths = {Path(source).resolve()}
    base = Path(manifest).resolve().parent if manifest else root
    if manifest:
        if not Path(manifest).is_file():
            raise RuntimeError('UNABLE: 声明的外发证据清单不可读取')
        paths.add(Path(manifest).resolve())
    for item in evidence:
        for key in ('sourcePath', 'eventsRef', 'sourceRef', 'svgRef', 'renderReceiptRef'):
            if item.get(key):
                ref = Path(item[key])
                path = (base / ref).resolve()
                if ref.is_absolute() or '..' in ref.parts or not path.is_relative_to(base) or not path.is_file():
                    raise RuntimeError('UNABLE: 外发附件路径越界或不可读取')
                paths.add(path)
    scanner = Path(__file__).resolve().parents[3] / 'scripts/verify-portability.py'
    if not scanner.is_file():
        raise RuntimeError('UNABLE: 缺套件隐私扫描器；请安装完整套件')
    spec = importlib.util.spec_from_file_location('export_privacy', scanner)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    terms = []
    if os.environ.get('SYBUILDER_PRIVATE_DENYLIST'):
        denylist = Path(os.environ['SYBUILDER_PRIVATE_DENYLIST']).resolve()
        if (denylist.is_relative_to(root) or denylist.is_relative_to(base)
                or denylist.is_relative_to(scanner.parents[1])):
            raise RuntimeError('UNABLE: 私有词表必须位于交付目录及发布仓之外')
        terms = [s.strip() for s in denylist.read_text().splitlines() if s.strip() and not s.startswith('#')]
        if not terms:
            raise RuntimeError('UNABLE: 私有词表为空')
    findings = module.scan_files(root, sorted(paths), terms)
    if findings:
        # Even file names may contain private terms: expose only the count here.
        raise RuntimeError('FAIL: 外发集合命中隐私规则（%d 处）；请私下复核并重采，未写入远端' % len(findings))


def preflight(source, manifest, for_write=True, destination=None):
    text = Path(source).read_text(encoding='utf-8')
    if re.search(r'^\s*```mermaid\b', text, re.M):
        raise RuntimeError('UNABLE: 请用实际 Mermaid 编译器渲染该图源，或使用内置结构化 JSON→SVG→PNG；加入证据清单后再交付')
    images = media_sources(text)
    if for_write and not images:
        check_export_privacy(source, [], manifest)
    if images:
        if not manifest or not Path(manifest).is_file():
            raise RuntimeError('UNABLE: 有图片的交付必须提供可读取的证据清单；未执行远端写入')
        evidence = json.loads(Path(manifest).read_text(encoding='utf-8')).get('evidence')
        if not isinstance(evidence, list) or not evidence:
            raise RuntimeError('UNABLE: 有图片但证据清单为空或结构不正确；未执行远端写入')
        known = {str((Path(manifest).parent / e.get('sourcePath', '')).resolve()) for e in evidence}
        for _, ref in images:
            path = Path(source).parent / ref
            if not ref or not path.is_file() or str(path.resolve()) not in known:
                raise RuntimeError('UNABLE: 图片缺真实文件或不在证据清单中；未执行远端写入')
            from _image import validate_image
            validate_image(path)
        if for_write:
            check_export_privacy(source, evidence, manifest)
            for item in evidence:
                review = item.get('privacyReview') or {}
                if (item.get('privacyReviewed') is not True or review.get('result') != 'APPROVED'
                        or review.get('actorType') not in ('human', 'agent')
                        or not all(review.get(k) for k in ('reviewer', 'reviewedAt', 'scope', 'method'))):
                    raise RuntimeError('UNABLE: 图片尚未完成逐张隐私审核；未执行远端写入')
                try:
                    reviewed = datetime.fromisoformat(review['reviewedAt'].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    timely = reviewed.tzinfo is not None and now - timedelta(days=30) <= reviewed <= now + timedelta(minutes=5)
                except (ValueError, TypeError, AttributeError):
                    timely = False
                base = Path(manifest).parent
                bindings = {k: source_hash(base / item[k]) for k in
                            ('sourcePath', 'eventsRef', 'sourceRef', 'svgRef', 'renderReceiptRef') if item.get(k)}
                if (not timely or not destination or review.get('destination') != destination
                        or review.get('evidenceId') != item.get('id')
                        or review.get('scope') != item.get('sourcePath')
                        or review.get('sourceBindings') != bindings):
                    raise RuntimeError('UNABLE: 图片审核已过期或内容/事件/范围/目的地不匹配；需重新审核')
                kind = item.get('kind')
                if kind == 'gui-screenshot':
                    ref = base / item.get('eventsRef', '')
                    if not ref.is_file():
                        raise RuntimeError('UNABLE: GUI 截图缺采集事件源')
                    events = json.loads(ref.read_text()).get('events', [])
                    matches = [e for e in events if e.get('id') == item.get('eventId') and
                               e.get('evidenceId') == item.get('id')]
                    if len(matches) != 1:
                        raise RuntimeError('FAIL: GUI 截图与事件记录不对应')
                elif kind == 'diagram':
                    from _diagram_contract import validate_render, validate_compiled
                    source_ref = base / item.get('sourceRef', '')
                    args = (source_ref, base / item.get('svgRef', ''),
                            base / item.get('sourcePath', ''), base / item.get('renderReceiptRef', ''))
                    if source_ref.suffix in ('.d2', '.mmd', '.puml'):
                        ids = set(re.findall(r'(?<!\w)[MFP]-\d+(?!\d)', source_ref.read_text()))
                        validate_compiled(*args, ids)
                    else:
                        validate_render(*args)
                else:
                    raise RuntimeError('UNABLE: 图片必须区分 gui-screenshot / diagram，不能互相冒充')


def save_readback(source, content, extension):
    path = Path(source + '.remote.' + extension)
    path.write_text(content, encoding='utf-8')
    return str(path)


def delivery_receipt(source, platform, ref, ok, issues):
    attempt_path = Path(source + '.attempt.json')
    attempt = json.loads(attempt_path.read_text()) if attempt_path.exists() else begin_attempt(source)
    attempt['status'] = 'PASS' if ok else 'FAIL'
    attempt_path.write_text(json.dumps(attempt), encoding='utf-8')
    path = Path(source + '.delivery-receipt.json')
    path.write_text(json.dumps({'platform': platform, 'document': ref,
                               'status': 'PASS' if ok else 'FAIL', 'issues': issues,
                               'attemptId': attempt['attemptId'], 'sourceHash': attempt['sourceHash'],
                               'syncReceipt': source + '.receipt.json' if ok else None},
                              ensure_ascii=False, indent=2), encoding='utf-8')


def guard():
    global _GUARD
    if _GUARD is None:
        spec = importlib.util.spec_from_file_location(
            'document_sync_guard', Path(__file__).with_name('doc-sync-guard.py'))
        _GUARD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_GUARD)
    return _GUARD


def before_create(source):
    if Path(source + '.sync.json').exists():
        raise RuntimeError('已有正本登记；先核对并复用远端，不可重复新建')


def before_update(source, platform, ref, allow_overwrite=False):
    if not allow_overwrite:
        raise RuntimeError('UNABLE: 默认只允许定位更新；整篇覆盖需明确授权并传 --allow-overwrite')
    side = Path(source + '.sync.json')
    if not side.exists():
        raise RuntimeError('UNABLE: 先读取并合并已有远端，再 record + readback 建立已验证基线')
    record = json.loads(side.read_text(encoding='utf-8'))
    if record.get('kind') != platform or (record.get('doc_token') or record.get('url')) != ref:
        raise RuntimeError('UNABLE: 文档身份与正本登记不一致')
    if record.get('remote_revision') is None or not record.get('lastReadbackAt') or record.get('validationStatus') != 'PASS':
        raise RuntimeError('UNABLE: 没有成功回读的基线；首次 lease 不能代替远端合并')
    if guard().cmd_lease(source) != 0:
        raise RuntimeError('远端漂移，禁止覆盖；先回读合并')


def register_created(source, platform, ref):
    if guard().cmd_record(source, ref, platform, preserve_attempt=True) != 0:
        raise RuntimeError('远端已创建，但正本登记失败；保留返回标识，禁止盲目重建')


def finish(source, ok, issues, expected_revision=None):
    if not ok:
        return False, issues
    if guard().cmd_readback(source, expected_revision=expected_revision) != 0:
        return False, issues + ['真实回读未通过 doc-sync-guard；不能声明交付完成']
    return True, issues


def self_test():
    import tempfile
    from unittest.mock import patch
    results = []
    def case(name, condition):
        results.append(bool(condition))
        print('  %s %s' % ('✅' if condition else '❌', name))
    def rejects(fn):
        try:
            fn()
        except RuntimeError:
            return True
        return False
    with tempfile.TemporaryDirectory() as temp:
        source = str(Path(temp) / 'report.md')
        Path(source).write_text('# Report', encoding='utf-8')
        before_create(source)
        case('正例：新源稿可进入新建流程', True)
        Path(source + '.sync.json').write_text(json.dumps({
            'url': 'synthetic-ref', 'kind': 'feishu', 'remote_revision': '1',
            'lastReadbackAt': 'synthetic-time', 'validationStatus': 'PASS'}))
        case('反例：已有正本不能重复新建', rejects(lambda: before_create(source)))
        case('反例：没有明确整篇覆盖授权就阻止写入', rejects(
            lambda: before_update(source, 'feishu', 'synthetic-ref')))
        with patch.object(guard(), 'cmd_lease', return_value=1):
            case('反例：远端漂移阻止写入', rejects(
                lambda: before_update(source, 'feishu', 'synthetic-ref', True)))
        with patch.object(guard(), 'cmd_lease', return_value=0):
            before_update(source, 'feishu', 'synthetic-ref', True)
            case('正例：授权与已验证基线齐全且无漂移才允许写', True)
        with patch.object(guard(), 'cmd_readback') as readback:
            case('反例：图片核验失败不能签通过回执',
                 not finish(source, False, ['media failed'])[0] and not readback.called)
    return 0 if all(results) else 1


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        raise SystemExit(self_test())
    print(__doc__)
