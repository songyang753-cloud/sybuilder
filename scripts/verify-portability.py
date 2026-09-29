#!/usr/bin/env python3
"""Fail the release candidate on private identity, tenant URLs, or local absolute paths."""
from __future__ import annotations

import pathlib
import re
import argparse
import json
import subprocess

PATTERNS = {
    "phone-like-personal-data": re.compile(r'(?<![0-9A-Za-z_])(?:\+86[ -]?)?1[3-9](?:[ -]?\d){9}(?![0-9A-Za-z_])'),
    "local-user-path": re.compile('/' + r'(?:Users|home)/[A-Za-z0-9_.-]+/'),
    "personal-document-url": re.compile(r'https?://(?:my|[a-z0-9-]+)\.feishu\.cn/(?:docx|wiki)/[A-Za-z0-9]{15,}'),
    "credential-assignment": re.compile(r'''(?i)(?:app_secret|client_secret|api[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_+/-]{16,})["']'''),
    "private-key": re.compile('-----BEGIN ' + r'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}


def private_structured_content(value):
    """Known user-content containers may retain shape/counts, never labels or IDs."""
    if isinstance(value, dict):
        if value.get('userContent') is True:
            for key in ('text', 'txt', 'title', 'label', 'id', 'plugin', 'view'):
                if value.get(key) not in (None, '', '[user-content]', '[unavailable]'):
                    return True
        return any(private_structured_content(v) for v in value.values())
    if isinstance(value, list):
        return any(private_structured_content(v) for v in value)
    return False


def scan(root, terms=()):
    return scan_files(root, sorted(root.rglob('*')), terms)


def scan_files(root, paths, terms=()):
    """Scan an explicit export set; diagnostics never echo matching values."""
    findings: list[str] = []
    for path in paths:
        rel = path.relative_to(root) if path.is_relative_to(root) else pathlib.Path(path.name)
        if ".git" in rel.parts:
            continue
        name_text = rel.as_posix()
        if any(term.casefold() in name_text.casefold() for term in terms):
            findings.append(f"{rel}: private-path-name")
        if path.is_symlink():
            findings.append(f"{rel}: symlink requires target review")
            continue
        if not path.is_file():
            continue
        # Scan extensionless and binary files too; no scanner-file exemption.
        text = path.read_bytes().decode('utf-8', errors='replace')
        if path.suffix.lower() in ('.json', '.jsonl'):
            try:
                data = ([json.loads(line) for line in text.splitlines() if line.strip()]
                        if path.suffix.lower() == '.jsonl' else json.loads(text))
                if private_structured_content(data):
                    findings.append(f'{rel}: user-content-not-withheld')
                text = json.dumps(data, ensure_ascii=False)
            except ValueError:
                findings.append(f'{rel}: invalid-json-export')
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(term.casefold() in line.casefold() for term in terms):
                findings.append(f"{rel}:{line_no}: external-private-denylist")
            # ⭐ 2026-09-29 真机投递实测：d2 渲染的 SVG 里，贝塞尔 path 坐标
            #   （多段浮点坐标用空格相连）恰好构成手机号模式——
            #   图形坐标不是个人数据。对 svg 的 path data 属性先剥离再扫电话规则；
            #   ⛔ 其余规则与其余文件不受影响，SVG 文本节点里的真手机号仍会红。
            if path.suffix.lower() == '.svg':
                scan_line = re.sub(r'd="[^"]*"', 'd=""', line)
            else:
                scan_line = line
            for name, pattern in PATTERNS.items():
                for match in pattern.finditer(scan_line if name == 'phone-like-personal-data' else line):
                    # One audited synthetic security-test value; other values in
                    # this file still get scanned, including future additions.
                    if (name == 'credential-assignment'
                            and rel.as_posix() == 'skills/product-flow/scripts/sec-scan.py'
                            and match.group(1) == 'sk-live-abcdef123456789'):
                        continue
                    findings.append(f"{rel}:{line_no}: {name}")
    return findings


def publish_paths(root):
    """Return the actual Git export set; a copied candidate falls back to all files."""
    try:
        proc = subprocess.run(
            ['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
            capture_output=True, timeout=10, check=False)
        if proc.returncode == 0:
            return sorted(root / item.decode('utf-8') for item in proc.stdout.split(b'\0') if item)
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        pass
    return sorted(root.rglob('*'))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', default='.')
    parser.add_argument('--denylist', type=pathlib.Path,
                        help='PRIVATE external UTF-8 file; one personal/employer term per line')
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    terms = []
    if args.denylist:
        denylist = args.denylist.resolve()
        if denylist == root or root in denylist.parents:
            parser.error('the private denylist must stay outside the release tree')
        terms = [s.strip() for s in denylist.read_text(encoding='utf-8').splitlines()
                 if s.strip() and not s.startswith('#')]
        if not terms:
            parser.error('the private denylist is empty')
    findings = scan_files(root, publish_paths(root), terms)
    if findings:
        print("FAIL: release portability scan found private or non-portable content:")
        print("\n".join(findings))
        return 1
    print('PASS: configured file patterns%s; Git history, image appearance and unknown identities require separate review'
          % (' + external private terms' if terms else ' ONLY (no private denylist supplied)'))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
