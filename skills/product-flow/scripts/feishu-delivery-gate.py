#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个人飞书调研交付门：本地源稿、真实图片、远端图片实体与锚点必须闭环。

用法: feishu-delivery-gate.py --source report.md --readback readback.xml
      [--evidence-manifest evidence-manifest.json] [--receipt receipt.json]
      feishu-delivery-gate.py --self-test
退出码: 0=通过 1=内容/图片丢失 2=输入缺失或工具异常
"""
import argparse, json, os, re, sys, tempfile

LOCAL_IMAGE = re.compile(r'!\[([^\]]+)\]\(<@\./([^)]+)>\)')
REMOTE_IMAGE = re.compile(r'<(?:image|img)\b[^>]*(?:token|file_token|src)\s*=\s*["\']([^"\']+)["\'][^>]*>', re.I)
EMPTY_REMOTE_IMAGE = re.compile(r'<(?:image|img)\b[^>]*(?:token|file_token|src)\s*=\s*["\']\s*["\'][^>]*>', re.I)
BAD_PLACEHOLDER = re.compile(r'📎|待补图|图片占位|截图占位|见附件')


def check(source_path, readback_path, manifest_path=None):
    src = open(source_path, encoding='utf-8', errors='replace').read()
    rb = open(readback_path, encoding='utf-8', errors='replace').read()
    bad, images, remote = [], list(LOCAL_IMAGE.finditer(src)), REMOTE_IMAGE.findall(rb)
    if BAD_PLACEHOLDER.search(src):
        bad.append('源稿仍含图片占位文字；必须嵌入真实图片')
    for alt, rel in [(m.group(1), m.group(2)) for m in images]:
        path = os.path.join(os.path.dirname(os.path.abspath(source_path)), rel)
        if not os.path.isfile(path):
            bad.append('本地图片不存在:%s (%s)' % (rel, alt))
    if len(remote) < len(images):
        bad.append('图片实体 本地%d → 飞书%d，至少丢%d张' % (len(images), len(remote), len(images)-len(remote)))
    if EMPTY_REMOTE_IMAGE.search(rb):
        bad.append('飞书回读存在空图片 token/src')
    if '<title' not in rb and not re.search(r'<heading|<h[1-6]\b', rb, re.I):
        bad.append('飞书回读缺标题/标题块，疑似正文未完整写入')
    if manifest_path:
        try:
            manifest = json.load(open(manifest_path, encoding='utf-8'))
        except Exception as e:
            return ['证据清单不可读:%s' % e], len(images), len(remote)
        for item in manifest.get('evidence', []):
            eid, rel, anchor = item.get('id', ''), item.get('sourcePath', ''), item.get('anchor', '')
            path = rel if os.path.isabs(rel) else os.path.join(os.path.dirname(os.path.abspath(manifest_path)), rel)
            if not eid or not rel or not anchor:
                bad.append('证据条目缺 id/sourcePath/anchor:%r' % item); continue
            if not os.path.isfile(path):
                bad.append('%s 证据文件不存在:%s' % (eid, rel))
            marker = '<!-- evidence:%s' % eid
            if marker not in src or anchor not in src:
                bad.append('%s 未在源稿中以锚点+邻接标记落位' % eid)
            if eid not in rb and anchor not in rb:
                bad.append('%s 的锚点/标识未出现在飞书回读' % eid)
    if re.search(r'\.\.\.|内容截断|truncated', rb, re.I):
        bad.append('飞书回读疑似截断')
    return bad, len(images), len(remote)


def main(a):
    for p in (a.source, a.readback, a.evidence_manifest):
        if p and not os.path.exists(p):
            print('UNABLE: 输入不存在 %s' % p, file=sys.stderr); return 2
    bad, local_n, remote_n = check(a.source, a.readback, a.evidence_manifest)
    for item in bad:
        print('❌ ' + item)
    receipt = {'gate':'feishu-delivery-gate', 'source':os.path.abspath(a.source),
               'readback':os.path.abspath(a.readback), 'localImages':local_n,
               'remoteImages':remote_n, 'status':'FAIL' if bad else 'PASS', 'issues':bad}
    if a.receipt:
        with open(a.receipt, 'w', encoding='utf-8') as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
    if not bad:
        print('✅ 飞书回读闭环：%d 张本地图均有非空远端图片实体' % local_n)
    print('⚠️ 本门验图片实体与锚点守恒，不判断截图内容是否拍对；最终仍需逐张人审。')
    return 1 if bad else 0


def self_test():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, 'a.png'), 'wb').write(b'png')
        src = os.path.join(d, 'r.md')
        open(src, 'w', encoding='utf-8').write('# 报告\n## 功能A\n<!-- evidence:SHOT-001 -->\n![SHOT-001 功能A](<@./a.png>)\n')
        mf = os.path.join(d, 'e.json')
        json.dump({'evidence':[{'id':'SHOT-001','sourcePath':'a.png','anchor':'功能A'}]}, open(mf,'w'), ensure_ascii=False)
        good = os.path.join(d, 'good.xml'); open(good,'w').write('<title>报告</title><heading>功能A SHOT-001</heading><image token="tok"/>')
        bad = os.path.join(d, 'bad.xml'); open(bad,'w').write('<title>报告</title><heading>功能A</heading><image token=""/>')
        b1, _, _ = check(src, good, mf); b2, _, _ = check(src, bad, mf)
        good_ok, bad_ok = not b1, bool(b2)
        print('  %s 正例 完整图片实体与锚点 → 放行' % ('✅' if good_ok else '❌'))
        print('  %s 反例 空 token 且缺证据标识 → 拦截' % ('✅' if bad_ok else '❌'))
        ok = good_ok and bad_ok
        print(('✅' if ok else '❌') + ' 飞书交付门自证通过' if ok else '❌ 飞书交付门自证失败')
        return 0 if ok else 1


def _entry():
    if '--self-test' in sys.argv:
        return self_test()
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True); ap.add_argument('--readback', required=True)
    ap.add_argument('--evidence-manifest'); ap.add_argument('--receipt')
    return main(ap.parse_args())


def _main_guarded(fn):
    """崩溃 ≠ 交付缺陷：意外异常一律退 2。"""
    try:
        sys.exit(fn())
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print('UNABLE: 门禁自身异常:%s: %s' % (type(e).__name__, e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    _main_guarded(_entry)
