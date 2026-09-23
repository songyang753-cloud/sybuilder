#!/usr/bin/env python3
"""Fail the release candidate on private identity, tenant URLs, or local absolute paths."""
from __future__ import annotations

import pathlib
import re
import argparse

PATTERNS = {
    "phone-like-personal-data": re.compile(r'(?<![0-9A-Za-z_])(?:\+86[ -]?)?1[3-9](?:[ -]?\d){9}(?![0-9A-Za-z_])'),
    "local-user-path": re.compile('/' + r'(?:Users|home)/[A-Za-z0-9_.-]+/'),
    "personal-document-url": re.compile(r'https?://(?:my|[a-z0-9-]+)\.feishu\.cn/(?:docx|wiki)/[A-Za-z0-9]{15,}'),
    "credential-assignment": re.compile(r'''(?i)(?:app_secret|client_secret|api[_-]?key)\s*[:=]\s*["']([A-Za-z0-9_+/-]{16,})["']'''),
    "private-key": re.compile('-----BEGIN ' + r'(?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}


def scan(root, terms=()):
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
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
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(term.casefold() in line.casefold() for term in terms):
                findings.append(f"{rel}:{line_no}: external-private-denylist")
            for name, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    # One audited synthetic security-test value; other values in
                    # this file still get scanned, including future additions.
                    if (name == 'credential-assignment'
                            and rel.as_posix() == 'skills/product-flow/scripts/sec-scan.py'
                            and match.group(1) == 'sk-live-abcdef123456789'):
                        continue
                    findings.append(f"{rel}:{line_no}: {name}")
    return findings


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
    findings = scan(root, terms)
    if findings:
        print("FAIL: release portability scan found private or non-portable content:")
        print("\n".join(findings))
        return 1
    print('PASS: configured file patterns%s; Git history, image appearance and unknown identities require separate review'
          % (' + external private terms' if terms else ' ONLY (no private denylist supplied)'))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
