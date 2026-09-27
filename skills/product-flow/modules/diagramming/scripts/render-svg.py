#!/usr/bin/env python3
"""One validated, atomic render path for export and regression tests."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
from _image import validate_image
from _document_sync import source_hash


sys.path.insert(0, str(HERE))
from _svg_safety import safe_css_resource, validated_svg


def render(source, output, width=1920):
    validated_svg(source, width)
    for check in ('xml', 'markers', 'collisions'):
        checked = subprocess.run([sys.executable, str(HERE / 'validate_svg.py'), str(source), '--check', check],
                                 capture_output=True, text=True, timeout=30)
        if checked.returncode:
            raise ValueError('invalid SVG: ' + checked.stdout + checked.stderr)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sybuilder-render-', dir=output.parent) as folder:
        candidate = Path(folder) / 'candidate.png'
        commands = []
        if importlib.util.find_spec('cairosvg'):
            commands.append([sys.executable, '-c',
                'import sys,cairosvg;cairosvg.svg2png(url=sys.argv[1],write_to=sys.argv[2],output_width=int(sys.argv[3]))',
                str(source), str(candidate), str(width)])
        if shutil.which('rsvg-convert'):
            commands.append(['rsvg-convert', '-w', str(width), str(source), '-o', str(candidate)])
        commands.append([sys.executable, str(HERE / 'chrome-svg-to-png.py'),
                         str(source), str(candidate), '--width', str(width)])
        errors = []
        for command in commands:
            candidate.unlink(missing_ok=True)
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=70)
                if result.returncode:
                    raise RuntimeError((result.stdout + result.stderr)[-500:])
                validate_image(candidate)
                os.replace(candidate, output)
                structured = Path(str(source) + '.source.json')
                if structured.is_file():
                    proof = {'schemaVersion': 1, 'sourceHash': source_hash(structured),
                             'svgHash': source_hash(source), 'pngHash': source_hash(output),
                             'renderer': Path(command[0]).name,
                             'rendererCompletion': result.stdout.strip()[-300:],
                             'rendererCodeHash': source_hash(Path(__file__))}
                    Path(str(output) + '.render.json').write_text(json.dumps(proof), encoding='utf-8')
                return
            except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
                errors.append(str(exc))
        raise RuntimeError('UNABLE: no renderer produced a valid image: ' + '; '.join(errors))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('svg', type=Path)
    parser.add_argument('png', type=Path)
    parser.add_argument('--width', type=int, default=1920)
    args = parser.parse_args()
    try:
        if args.width < 1:
            raise ValueError('width must be positive')
        render(args.svg.resolve(), args.png.resolve(), args.width)
    except (ValueError, ET.ParseError) as exc:
        print('FAIL: ' + str(exc)); sys.exit(1)
    except Exception as exc:
        print('UNABLE: ' + str(exc)); sys.exit(2)
    print('PASS: validated render ' + str(args.png))
