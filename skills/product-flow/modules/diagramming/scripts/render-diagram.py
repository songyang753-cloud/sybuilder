#!/usr/bin/env python3
"""Compile existing D2/Mermaid/PlantUML with installed tools, then validate PNG.
No runtime downloads. 0=PASS, 1=invalid source/output, 2=UNABLE tool/runtime.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
from _document_sync import source_hash


def compile_diagram(source, svg, png, layout='dagre'):
    if svg.suffix != '.svg' or png.suffix != '.png' or len({source.resolve(), svg.resolve(), png.resolve()}) != 3:
        raise ValueError('Source, .svg output and .png output must be distinct paths')
    tool = {'.d2': 'd2', '.mmd': 'mmdc', '.puml': 'plantuml'}.get(source.suffix)
    if not tool or not shutil.which(tool):
        raise RuntimeError('UNABLE: installed compiler required for ' + source.suffix)
    if source.suffix == '.puml' and '!include' in source.read_text().lower():
        raise ValueError('Expand and license-review PlantUML includes locally first; no network include execution')
    # Work in a temporary output directory; a failed build cannot publish a new receipt.
    svg.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sybuilder-compile-') as temp:
        candidate = Path(temp) / 'diagram.svg'
        if tool == 'd2': command = [tool, '--layout=' + layout, str(source), str(candidate)]
        elif tool == 'mmdc': command = [tool, '-i', str(source), '-o', str(candidate), '--quiet']
        else: command = [tool, '-tsvg', '-pipe', '-charset', 'UTF-8']
        result = subprocess.run(command, input=source.read_text() if tool == 'plantuml' else None,
                                capture_output=True, text=True, timeout=120)
        if result.returncode: raise ValueError('compiler failed: ' + (result.stdout + result.stderr)[-800:])
        if tool == 'plantuml': candidate.write_text(result.stdout)
        if not candidate.is_file(): raise ValueError('compiler produced no SVG')
        spec = importlib.util.spec_from_file_location('diagram_renderer', HERE / 'render-svg.py')
        renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
        temporary_png = Path(temp) / 'diagram.png'
        renderer.render(candidate, temporary_png)
        svg.write_bytes(candidate.read_bytes()); png.write_bytes(temporary_png.read_bytes())
        proof = {'schemaVersion': 1, 'compiler': tool, 'layout': layout,
                 'sourceHash': source_hash(source), 'svgHash': source_hash(svg), 'pngHash': source_hash(png),
                 'rendererCodeHash': source_hash(HERE / 'render-svg.py')}
        Path(str(png) + '.render.json').write_text(json.dumps(proof))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path); parser.add_argument('svg', type=Path)
    parser.add_argument('--layout', choices=['dagre', 'elk', 'tala'], default='dagre')
    args = parser.parse_args()
    compile_diagram(args.source.resolve(), args.svg.resolve(), args.svg.with_suffix('.png').resolve(), args.layout)
    print('PASS: source compiled and image decoded; visual/business review remains required')


if __name__ == '__main__':
    try: main()
    except ValueError as exc: print('FAIL: ' + str(exc)); sys.exit(1)
    except Exception as exc: print('UNABLE: ' + str(exc)); sys.exit(2)
