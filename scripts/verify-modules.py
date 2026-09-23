#!/usr/bin/env python3
"""Validate SYBuilder internal modules and external adapter contracts."""

from __future__ import annotations

import argparse
import json
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / 'skills' / 'product-flow'


def require(condition, message, issues):
    if not condition:
        issues.append(message)


def registry_checks(issues):
    require(importlib.util.find_spec('yaml') is not None,
            'UNABLE: 设计令牌生成需要 PyYAML；请在虚拟环境安装 requirements.txt', issues)
    registry_path = ROOT / 'shared' / 'module-registry.json'
    registry = json.loads(registry_path.read_text(encoding='utf-8'))
    modules = registry.get('modules', [])
    adapters = registry.get('adapters', [])
    module_ids = [item.get('id') for item in modules]
    adapter_ids = [item.get('id') for item in adapters]
    require(len(module_ids) == len(set(module_ids)), 'module-registry 有重复 module id', issues)
    require(len(adapter_ids) == len(set(adapter_ids)), 'module-registry 有重复 adapter id', issues)
    require({'research', 'diagramming', 'design-quality', 'prototyping',
             'repository-enforcement'} <= set(module_ids), '核心内置模块登记不全', issues)
    require({'lark', 'dingtalk', 'figma', 'browser'} <= set(adapter_ids),
            '平台适配器登记不全', issues)
    for item in modules + adapters:
        entry = ROOT / str(item.get('entry', ''))
        require(entry.is_file(), '登记入口不存在: %s' % item.get('entry'), issues)
    for item in modules:
        entry = ROOT / item['entry']
        if 'modules/' in item['entry']:
            require(not (entry.parent / 'SKILL.md').exists(),
                    '内部模块不应暴露为可自动触发 Skill: %s' % entry.parent, issues)


def wiring_checks(issues):
    skill = (PRODUCT / 'SKILL.md').read_text(encoding='utf-8')
    for marker in ('modules/research', 'modules/diagramming', 'modules/design-quality',
                   'modules/prototyping', 'adapters/lark', 'adapters/dingtalk',
                   'adapters/figma', 'adapters/browser', 'scripts/_documents.py'):
        require(marker in skill, 'product-flow 入口未声明 %s' % marker, issues)

    active_text = ''
    for suffix in ('*.py', '*.sh', '*.mjs', '*.js'):
        for path in PRODUCT.rglob(suffix):
            active_text += '\n' + path.read_text(encoding='utf-8', errors='replace')
    legacy_exec_patterns = (
        r"(?m)^\s*feishu\s+(?:docx|fetch|wiki|drive)\b",
        r"\b(?:run|Popen|check_call|check_output)\s*\(\s*\[\s*['\"]feishu['\"]",
        r"\b(?:spawn|execFile|execFileSync)\s*\(\s*['\"]feishu['\"]",
    )
    require(not any(re.search(pattern, active_text) for pattern in legacy_exec_patterns),
            '执行代码仍直接调用旧第三方 feishu 命令', issues)
    require("['lark-cli'" in active_text, '没有飞书官方 lark-cli 执行路径', issues)
    require("['dws'" in active_text, '没有钉钉官方 dws 执行路径', issues)

    diagram = PRODUCT / 'modules' / 'diagramming'
    require((diagram / 'LICENSE').is_file(), '内置制图器缺上游许可证', issues)
    require((diagram / 'scripts' / 'chrome-svg-to-png.py').is_file(),
            '内置制图器缺本地 Chrome 渲染后备', issues)


def prototype_smoke(issues):
    bundle = PRODUCT / 'modules' / 'prototyping' / 'scripts' / 'bundle.mjs'
    if not shutil.which('node'):
        issues.append('UNABLE: 原型模块自检需要 Node.js')
        return
    with tempfile.TemporaryDirectory(prefix='sybuilder-proto-') as temp:
        root = Path(temp)
        (root / 'index.html').write_text(
            '<!doctype html><link rel="stylesheet" href="app.css">'
            '<main><img src="dot.png"><h1>SYBuilder</h1></main>'
            '<script src="app.js"></script>', encoding='utf-8')
        (root / 'app.css').write_text('body{color:#123}', encoding='utf-8')
        (root / 'app.js').write_text('document.body.dataset.ready="1";', encoding='utf-8')
        (root / 'dot.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        output = root / 'bundle.html'
        result = subprocess.run(['node', str(bundle), str(root), str(output)],
                                capture_output=True, text=True)
        require(result.returncode == 0, '原型 bundle 自检失败: %s' %
                ((result.stdout or '') + (result.stderr or ''))[-600:], issues)
        if output.is_file():
            bundled = output.read_text(encoding='utf-8')
            require('href="app.css"' not in bundled and 'src="app.js"' not in bundled,
                    '原型 bundle 仍有本地样式或脚本外链', issues)
            require('data:image/png;base64,' in bundled, '原型图片未内联', issues)


def render_smoke(issues):
    diagram = PRODUCT / 'modules' / 'diagramming'
    with tempfile.TemporaryDirectory(prefix='sybuilder-diagram-') as temp:
        svg = Path(temp) / 'architecture.svg'
        payload = json.dumps({
            'title': 'SYBuilder',
            'nodes': [{'id': 'a', 'label': 'Research', 'x': 80, 'y': 100},
                      {'id': 'b', 'label': 'Delivery', 'x': 480, 'y': 100}],
            'arrows': [{'from': 'a', 'to': 'b', 'label': 'evidence'}],
        })
        generated = subprocess.run([
            'python3', str(diagram / 'scripts' / 'generate-from-template.py'),
            'architecture', str(svg), payload,
        ], capture_output=True, text=True)
        require(generated.returncode == 0 and svg.is_file(),
                '制图器模板生成失败: %s' % ((generated.stdout or '') +
                (generated.stderr or ''))[-600:], issues)
        if svg.is_file():
            rendered = subprocess.run([str(diagram / 'scripts' / 'validate-svg.sh'), str(svg)],
                                      capture_output=True, text=True)
            require(rendered.returncode == 0,
                    '制图器渲染闭环失败: %s' % ((rendered.stdout or '') +
                    (rendered.stderr or ''))[-1000:], issues)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true', help='also require real SVG rendering')
    args = parser.parse_args()
    issues = []
    registry_checks(issues)
    wiring_checks(issues)
    prototype_smoke(issues)
    if args.render:
        render_smoke(issues)
    if issues:
        for issue in issues:
            print('❌ ' + issue)
        return 1
    print('✅ 内置模块与平台适配器契约通过' + ('，制图渲染通过' if args.render else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
