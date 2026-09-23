#!/usr/bin/env python3
"""Audit the clean SYBuilder candidate before a public release."""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


ALLOWED_SKILLS = {
    "skills/product-flow/SKILL.md",
    "skills/coding-standards/SKILL.md",
    "skills/four-node-review/SKILL.md",
}
FORBIDDEN_PARTS = {".DS_Store", "__pycache__", ".four-node-review"}
SENSITIVE_NAMES = re.compile(r"(?i)(?:\.env(?:\..*)?|id_rsa|oauth|credential|token\.json)$")
OLD_FEISHU_COMMAND = re.compile(r"(?m)^\s*feishu\s+(?:docx|fetch|wiki|drive)\b")
TEXT_SUFFIXES = {".md", ".json", ".py", ".mjs", ".js", ".sh", ".yaml", ".yml", ".tsv"}


def publication_errors(root: pathlib.Path) -> list[str]:
    errors = []
    for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY.md'):
        if not (root / name).is_file() or not (root / name).read_text().strip():
            errors.append('public distribution requires ' + name)
    checklist = root / 'PUBLICATION_CHECKLIST.md'
    body = checklist.read_text() if checklist.is_file() else ''
    checked = set(re.findall(r'^- \[x\] (PUB-[1-5])\b', body, re.M))
    if checked != {'PUB-%d' % i for i in range(1, 6)} or re.search(r'^- \[ \]', body, re.M):
        errors.append('publication checklist is incomplete or has unresolved items')
    try:
        entries = json.loads((root / 'licenses/sources.json').read_text())['entries']
        if not isinstance(entries, list) or not entries:
            raise ValueError('entries must be a nonempty list')
        for entry in entries:
            if not all(isinstance(entry.get(k), str) and entry[k].strip()
                       for k in ('source', 'revision', 'license', 'licenseFile', 'kind', 'changes')):
                raise ValueError('missing source, revision, license or scope')
            if not re.fullmatch(r'[0-9a-f]{40}', entry['revision']):
                raise ValueError('revision must pin a full commit')
            paths = entry.get('localPaths')
            if not isinstance(paths, list) or not paths:
                raise ValueError('missing destination paths')
            for name in [entry['licenseFile'], *paths]:
                if not isinstance(name, str):
                    raise ValueError('path must be text')
                path = (root / name).resolve()
                if root not in path.parents or not path.is_file() or not path.stat().st_size:
                    raise ValueError('missing, empty or external path: ' + name)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append('source manifest is invalid: ' + str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true", help="stable release: require publication checks and closure of every release blocker")
    mode.add_argument("--public-preview", action="store_true", help="public source preview: require rights/privacy checklist and third-party notices, not stable quality approval")
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    errors: list[str] = []

    skills = {str(path.relative_to(root)) for path in root.rglob("SKILL.md")}
    if skills != ALLOWED_SKILLS:
        errors.append("discoverable Skills differ: expected %s, found %s" %
                      (sorted(ALLOWED_SKILLS), sorted(skills)))

    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if ".git" in rel.parts:
            continue
        if any(part in FORBIDDEN_PARTS for part in rel.parts):
            errors.append("forbidden generated/private path: %s" % rel)
            continue
        if ".product-flow" in rel.parts and "fixtures" not in rel.parts:
            errors.append("forbidden generated/private path: %s" % rel)
            continue
        # Development proposals are needed by the coordination gate, but are
        # ignored by Git and must never enter a publishable archive.
        if ".proposals" in rel.parts:
            if args.publish or args.public_preview:
                errors.append("private proposal path in publish tree: %s" % rel)
            continue
        if path.is_file() and path.stat().st_size > 5 * 1024 * 1024:
            errors.append("file exceeds 5 MiB: %s" % rel)
        if path.is_file() and SENSITIVE_NAMES.search(path.name):
            errors.append("credential-like filename: %s" % rel)
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if (str(rel) not in {"skills/product-flow/references/no-loss-baseline.json",
                                 "skills/product-flow/references/no-loss-renames.md"}
                    and OLD_FEISHU_COMMAND.search(text)):
                errors.append("deprecated third-party feishu command: %s" % rel)

    if args.publish or args.public_preview:
        errors.extend(publication_errors(root))
    if args.publish:
        checklist = root / 'RELEASE_BLOCKERS.md'
        if not checklist.is_file():
            errors.append('public release requires a reviewed release-blocker checklist')
        elif re.search(r'^- \[ \]', checklist.read_text(encoding='utf-8'), re.M):
            errors.append('public release has unresolved items in RELEASE_BLOCKERS.md')
    if errors:
        print("FAIL: release audit")
        for item in errors:
            print("- " + item)
        return 1
    status = "stable release" if args.publish else "public preview" if args.public_preview else "candidate"
    print("PASS: %s packaging checks; exactly three Skills and configured path/command rules (not a complete privacy audit)" % status)
    if args.public_preview:
        print('Public source preview only; not stable-release approval. See RELEASE_BLOCKERS.md.')
    if not args.publish and not (root / "LICENSE").is_file():
        print("BLOCKED FOR PUBLICATION: project LICENSE is intentionally unresolved; see RELEASE_BLOCKERS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
