"""Structured diagram source and rendered identity validation."""
import json
import copy
import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from _document_sync import source_hash
from _image import validate_image

SLOT_TYPES = ('user-flow', 'business-flow', 'product-module', 'functional-architecture',
              'information-architecture', 'page-relation', 'state-machine', 'data-lifecycle')


def validate_source(data, formal=True):
    if formal and (data.get('schemaVersion') != 1 or not data.get('diagramId') or
                   not data.get('diagramType') or not data.get('targetSection')):
        raise ValueError('diagram-contract: 缺 schemaVersion/diagramId/diagramType/targetSection')
    nodes = data.get('nodes', [])
    ids = [n.get('id') for n in nodes]
    if not nodes or any(not isinstance(i, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', i) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('diagram-nodes: 节点必须有唯一 ID')
    for arrow in data.get('arrows', []):
        if float(arrow.get('stroke_width', 1)) <= 0 or float(arrow.get('opacity', 1)) <= 0:
            raise ValueError('diagram-visible: 连线必须可见')
        if str(arrow.get('color', '')).lower() in ('none', 'transparent'):
            raise ValueError('diagram-visible: 连线不可透明')
        # Legacy free-coordinate diagrams remain supported, not formal ID evidence.
        if not formal and not arrow.get('source') and not arrow.get('target') and 'start' in arrow and 'end' in arrow:
            continue
        if arrow.get('source') not in ids or arrow.get('target') not in ids:
            raise ValueError('diagram-edge: 连线起点/终点不存在')
    return set(ids)


def validate_render(source, svg, png, receipt):
    data = json.loads(Path(source).read_text())
    ids = validate_source(data)
    actual = Path(svg).read_text()
    # Formal local delivery is deterministic: metadata alone cannot prove visibility
    # or preserve arrows. Rebuild the full SVG, including edges, from the same source.
    generator = Path(__file__).resolve().parents[1] / 'modules/diagramming/scripts/generate-from-template.py'
    spec = importlib.util.spec_from_file_location('_diagram_generator', generator)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if not data.get('templateType') or actual != module.build_svg(data['templateType'], copy.deepcopy(data)):
        raise ValueError('diagram-render-source: SVG 不是当前结构源的完整生成物（含节点、连线与布局）')
    xml = ET.fromstring(actual)
    groups = [e for e in xml.iter() if e.get('data-node-id')]
    if {e.get('data-node-id') for e in groups} != ids or len(groups) != len(ids):
        raise ValueError('diagram-render-ids: 渲染节点与源不一致')
    _, _, width, height = map(float, xml.get('viewBox', '').split())
    for g in groups:
        if not list(g) or not ''.join(g.itertext()).strip():
            raise ValueError('diagram-visible: 节点没有可见图形/文字')
        for e in g.iter():
            if re.search(r'display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:;|$)', e.get('style', '')) or e.get('opacity') == '0':
                raise ValueError('diagram-visible: 隐藏节点不能对账')
        x, y, right, bottom = map(float, g.get('data-bounds', '').split(','))
        if right <= x or bottom <= y or x < 0 or y < 0 or right > width or bottom > height:
            raise ValueError('diagram-visible: 节点在画布外')
    validate_image(png)
    proof = json.loads(Path(receipt).read_text())
    for key, path in [('sourceHash', source), ('svgHash', svg), ('pngHash', png)]:
        if proof.get(key) != source_hash(path):
            raise ValueError('diagram-stale: 图源/SVG/PNG/渲染记录版本不一致')
    return ids


def validate_compiled(source, svg, png, receipt, ids):
    """Legacy compiler evidence; semantic layout/edge review remains a human task."""
    compiler = {'.d2': 'd2', '.mmd': 'mmdc', '.puml': 'plantuml'}.get(Path(source).suffix)
    proof = json.loads(Path(receipt).read_text())
    if not compiler or proof.get('compiler') != compiler:
        raise ValueError('diagram-compiler: 缺对应真实编译器回执')
    for key, path in [('sourceHash', source), ('svgHash', svg), ('pngHash', png)]:
        if proof.get(key) != source_hash(path): raise ValueError('diagram-stale: 编译源/产物版本不一致')
    xml = ET.fromstring(Path(svg).read_text())
    visible_text = []
    def visit(element, hidden=False):
        hidden = hidden or element.get('display') == 'none' or element.get('visibility') == 'hidden' or element.get('opacity') == '0'
        hidden = hidden or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:;|$)', element.get('style', '')))
        if not hidden and element.tag.split('}')[-1] in ('text', 'tspan'):
            visible_text.append(''.join(element.itertext()))
        for child in element: visit(child, hidden)
    visit(xml)
    text = ' '.join(visible_text)
    if any(not re.search(r'(?<!\w)' + re.escape(i) + r'(?!\w)', text) for i in ids):
        raise ValueError('diagram-render-ids: 编译图中缺可见 ID 标签')
    validate_image(png)


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
        sys.exit(tests['main']('diagram'))
