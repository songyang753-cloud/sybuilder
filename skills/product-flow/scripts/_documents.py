#!/usr/bin/env python3
"""SYBuilder 协作文档统一入口（飞书 / 钉钉）。"""

from __future__ import annotations

import argparse
import json
import os
import sys


def push_deliverable(platform, title, md_path, extra_markers=None,
                     document_ref=None, evidence_manifest=None, allow_overwrite=False):
    if platform == 'feishu':
        import _feishu
        return _feishu.push_deliverable(
            title, md_path, extra_markers, doc_token=document_ref,
            evidence_manifest=evidence_manifest, allow_overwrite=allow_overwrite)
    if platform == 'dingtalk':
        import _dingtalk
        return _dingtalk.push_deliverable(
            title, md_path, extra_markers, document_ref=document_ref,
            evidence_manifest=evidence_manifest, allow_overwrite=allow_overwrite)
    raise ValueError('platform 必须是 feishu 或 dingtalk')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', required=True, choices=('feishu', 'dingtalk'))
    parser.add_argument('--title', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--document', help='已有文档 token、nodeId 或 URL；传入则原地更新')
    parser.add_argument('--allow-overwrite', action='store_true', help='仅在用户明确授权整篇重建后使用；仍强制检查远端漂移')
    parser.add_argument('--evidence-manifest')
    parser.add_argument('--marker', action='append', default=[])
    args = parser.parse_args()
    ref, ok, issues = push_deliverable(
        args.platform, args.title, os.path.abspath(args.source), args.marker,
        document_ref=args.document,
        evidence_manifest=(os.path.abspath(args.evidence_manifest)
                           if args.evidence_manifest else None), allow_overwrite=args.allow_overwrite)
    print(json.dumps({'platform': args.platform, 'document': ref,
                      'verified': ok, 'issues': issues}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print('UNABLE: %s' % exc, file=sys.stderr)
        raise SystemExit(2)
