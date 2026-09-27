#!/usr/bin/env python3
"""Check concrete local Markdown links in a complete distribution, including root references."""
import argparse
from pathlib import Path
from urllib.parse import unquote, urlsplit
from markdown_it import MarkdownIt


def check(root):
    parser = MarkdownIt()
    errors, total = [], 0
    for source in sorted(root.rglob('*.md')):
        relative = source.relative_to(root)
        if any(part.startswith('.') for part in relative.parts):
            continue  # developer/runtime state is not part of the publish set
        for block in parser.parse(source.read_text(encoding='utf-8')):
            for token in block.children or []:
                if token.type not in ('link_open', 'image'):
                    continue
                ref = token.attrGet('href' if token.type == 'link_open' else 'src') or ''
                url = urlsplit(ref)
                if url.scheme or url.netloc or not url.path:
                    continue
                path = unquote(url.path)
                # Explicit authored placeholders/history, not blanket exemptions for templates.
                placeholders = {
                    ('skills/product-flow/templates/competitor-teardown-report.md','@./evidence/SHOT-001.png'),
                    ('skills/product-flow/references/no-loss-renames.md','@./evidence/xxx.png'),
                }
                if (relative.as_posix(),path) in placeholders:
                    continue
                if path.startswith('@./'):
                    path = path[1:]  # research image-source notation
                # Template parameters are not repository files; concrete ../ links are.
                if any(mark in path for mark in ('<', '>', '{', '}', '…')):
                    continue
                if not Path(path).suffix and not path.startswith(('./', '../')):
                    continue
                total += 1
                target = (source.parent / path).resolve()
                if not target.is_relative_to(root) or not target.exists():
                    errors.append(f'{relative}: {path}')
    return total, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    count, errors = check(Path(args.root).resolve())
    print(f'{"FAIL" if errors else "PASS"}: {count} concrete Markdown file links; {len(errors)} unresolved')
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
