#!/usr/bin/env python3
"""tech-research-gate.py — S2 researchMode=tech-approach 出场门禁。

用法:
  python3 tech-research-gate.py --pre  <research_dir>   # 交付前:本地结构机检
  python3 tech-research-gate.py --post <research_dir>   # 推送后:正本平台回读验真
  python3 tech-research-gate.py --self-test             # 门自证:正例必须绿、三类反例必须红

退出码:0=通过 1=不通过 2=UNABLE(前置缺失/平台不可达,如实报告不装绿)。

<research_dir> 约定:
  scope.md    含声明行:object_count: N / report_file: xxx.md /(可选)
              count_exemptions: [n1, n2] / max_fig_height: 2600 /
              documentPlatform: feishu / delivery_doc: <document_id>
  报告 md     由 report_file 指定(默认 report.md),图引用 ![alt](<@./rel/path.png>)

判据正本:references/s2-tech-approach-runbook.md(本脚本只机检 ★ 项,不判内容对错)。
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys, tempfile
from pathlib import Path
from _document_sync import media_sources, verify_media_delivery

OBJ_HEAD_RE = re.compile(r'^#{2,3} +2\.(\d+) ', re.M)
EXCERPT_RE = re.compile(r'\w[\w./-]*\.\w{1,4}:\d+')          # file:line 形状
COUNT_RE = re.compile(r'(\d+)\s*(?:个)?\s*(?:框架|家|个开源框架|个对象)')
SECTION_KEYS = ("意图理解", "分发与反馈", "整体流程")


def parse_scope(path):
    if not os.path.isfile(path):
        return None
    cfg = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        m = re.match(r'^(\w+)\s*:\s*(.+?)\s*$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if k == "count_exemptions":
            cfg[k] = [int(x) for x in re.findall(r'\d+', v)]
        elif v.isdigit():
            cfg[k] = int(v)
        else:
            cfg[k] = v
    return cfg


def png_height(path):
    try:
        from _image import validate_image
        return validate_image(path)[1]
    except (OSError, ValueError):
        return None


def check_pre(rdir):
    errs = []
    scope = parse_scope(os.path.join(rdir, "scope.md"))
    if scope is None:
        print("UNABLE: scope.md 不存在", file=sys.stderr)
        return 2
    n = scope.get("object_count")
    if not isinstance(n, int) or n < 1:
        errs.append("scope.md 未声明合法 object_count")
        n = 0
    report = os.path.join(rdir, str(scope.get("report_file", "report.md")))
    if not os.path.isfile(report):
        print(f"UNABLE: 报告文件不存在 {report}", file=sys.stderr)
        return 2
    text = Path(report).read_text(encoding='utf-8')

    # 1) 对象编号连续 2.1..2.N(2.0 总览存在)
    nums = sorted({int(m.group(1)) for m in OBJ_HEAD_RE.finditer(text)})
    if 0 not in nums:
        errs.append("缺 2.0 总览节")
    body_nums = [x for x in nums if x > 0]
    if n and body_nums != list(range(1, n + 1)):
        errs.append(f"对象编号不连续或数量不符: 期望 2.1..2.{n}, 实得 {body_nums}")

    # 2) 逐对象:三小节关键词 + 3 图 + ≥3 段 file:line 摘录
    spans = [(m.start(), int(m.group(1))) for m in OBJ_HEAD_RE.finditer(text)]
    spans.append((len(text), -1))
    for (start, num), (end, _nx) in zip(spans, spans[1:]):
        if num <= 0:
            continue
        seg = text[start:end]
        for key in SECTION_KEYS:
            if key not in seg:
                errs.append(f"2.{num} 缺小节关键词「{key}」")
        figs = media_sources(seg)
        if len(figs) < 3:
            errs.append(f"2.{num} 图引用不足 3(实得 {len(figs)})")
        fences = seg.count("```") // 2
        anchors = len(EXCERPT_RE.findall(seg))
        if fences < 3 or anchors < 3:
            errs.append(f"2.{num} 代码/prompt 摘录不足(fence 对={fences}, file:line 锚={anchors},均须 ≥3)")

    # 3) 口径:文中对象计数 ∈ 声明∪豁免
    allowed = {n} | set(scope.get("count_exemptions", []))
    for m in COUNT_RE.finditer(text):
        v = int(m.group(1))
        if v not in allowed:
            errs.append(f"口径疑残留: 「{m.group(0)}」不在声明值{n}∪豁免{sorted(allowed - {n})}中")

    # 4) 图文件存在 + 高度红线
    max_h = int(scope.get("max_fig_height", 2600))
    for _, rel in media_sources(text):
        p = os.path.join(rdir, rel)
        if not Path(p).resolve().is_relative_to(Path(rdir).resolve()):
            errs.append("图路径越出研究目录")
            continue
        if not os.path.isfile(p):
            errs.append(f"图文件缺失: {rel}")
            continue
        h = png_height(p)
        if h is None:
            errs.append(f"图不能完整解码: {rel}")
        elif h > max_h:
            errs.append(f"图超高度红线: {rel} 高 {h}px > {max_h}px")

    if errs:
        for e in errs:
            print("FAIL:", e)
        print("⚠️ 边界: 本门只验结构与口径,验不了结论对不对、摘录是否真实取自源码")
        return 1
    print(f"PASS --pre: 2.0..2.{n} 结构/摘录/口径/图 全部达标")
    print("⚠️ 边界: 本门只验结构与口径,验不了结论对不对、摘录是否真实取自源码、方案能否落地——那靠承重结论独立复核与语义终审")
    return 0


def check_post(rdir):
    pre = check_pre(rdir)
    if pre != 0:
        return pre
    scope = parse_scope(os.path.join(rdir, "scope.md"))
    if scope is None:
        print("UNABLE: scope.md 不存在", file=sys.stderr)
        return 2
    platform = scope.get("documentPlatform")
    doc = scope.get("delivery_doc")
    if platform not in ("feishu", "dingtalk") or not doc:
        print("UNABLE: 需 scope 声明 documentPlatform: feishu/dingtalk 与 delivery_doc", file=sys.stderr)
        return 2
    source = Path(rdir) / str(scope.get('report_file', 'report.md'))
    manifest = Path(rdir) / str(scope.get('evidence_manifest', 'evidence-manifest.json'))
    try:
        from _feishu import _find_value, verify_readback
        if platform == 'feishu':
            import _feishu as adapter
            data = adapter.fetch_data(str(doc), 'markdown')
            native_data = adapter.fetch_data(str(doc), 'xml')
            body = _find_value(data, {'content', 'markdown', 'body'})
            native = _find_value(native_data, {'content', 'xml', 'body'})
        else:
            import _dingtalk as adapter
            body, data = adapter.fetch(str(doc))
            native_data = adapter.inspect_media(str(doc))
            native = native_data
        keys = {'revision_id', 'revisionId', 'version', 'revision'}
        version, media_version = _find_value(data, keys), _find_value(native_data, keys)
        if version is None or str(version) != str(media_version):
            raise RuntimeError('UNABLE: 正文与原生图片回读缺同版标识')
        ok, issues = verify_readback(source.read_text(), body)
        if not ok:
            print('FAIL --post: 全文回读不一致')
            return 1
        verify_media_delivery(source, manifest, native, str(doc), version, record=False)
    except (OSError, ValueError, RuntimeError, TypeError, subprocess.TimeoutExpired) as e:
        if isinstance(e, RuntimeError) and str(e).startswith('FAIL:'):
            print('FAIL --post: 逐图身份或章节位置不一致', file=sys.stderr)
            return 1
        print('UNABLE --post: 全文/逐图回读无法验证: ' + type(e).__name__, file=sys.stderr)
        return 2
    print("PASS --post: 本地结构、全文与同版本逐图身份/章节一致")
    print("⚠️ 不等于内容正确或视觉已验；还须最终 research-quality 评审与逐页走查")
    return 0


# ---------------- self-test ----------------

def _mk_fixture(tmp, n_objs=2, break_numbering=False, drop_fig=False, stale_count=False):
    os.makedirs(os.path.join(tmp, "figs"), exist_ok=True)
    from PIL import Image, ImageDraw
    for i in range(1, n_objs + 1):
        for kind in ("intent", "dispatch", "overall"):
            image = Image.new('RGB', (400, 200), 'white')
            ImageDraw.Draw(image).text((20, 30), f'Synthetic object {i}: {kind}', fill='black')
            image.save(os.path.join(tmp, "figs", f"o{i}-{kind}.png"))
    Path(tmp, 'scope.md').write_text(
        f"object_count: {n_objs}\nreport_file: report.md\ncount_exemptions: []\n", encoding='utf-8')
    lines = ["# 报告\n", "## 2.0 总览\n"]
    for i in range(1, n_objs + 1):
        num = i + 1 if (break_numbering and i == 2) else i     # 反例1: 2.2→2.3
        lines.append(f"## 2.{num} 对象{i}\n")
        for j, key in enumerate(SECTION_KEYS):
            lines.append(f"### {key}:机制、策略与方案\n")
            lines.append(f"```python\n# src/mod{j}.py:{10+j}\nx = {j}\n```\n")
            if not (drop_fig and i == 1 and j == 2):           # 反例2: 对象1只 2 图
                lines.append(f"![图](<@./figs/o{i}-{('intent','dispatch','overall')[j]}.png>)\n")
    if stale_count:
        lines.append(f"\n本次共调研 {n_objs + 3} 个框架。\n")   # 反例3: 旧口径
    else:
        lines.append(f"\n本次共调研 {n_objs} 个框架。\n")
    Path(tmp, 'report.md').write_text(''.join(lines), encoding='utf-8')
    return tmp


def self_test():
    cases = [("正例", {}, 0),
             ("反例-漏编号", {"break_numbering": True}, 1),
             ("反例-缺图", {"drop_fig": True}, 1),
             ("反例-旧口径", {"stale_count": True}, 1)]
    ok = True
    for name, kw, want in cases:
        with tempfile.TemporaryDirectory() as tmp:
            _mk_fixture(tmp, **kw)
            got = check_pre(tmp)
        mark = "✓" if got == want else "✗"
        if got != want:
            ok = False
        print(f"  {mark} {name}: 期望 {want} 实得 {got}")
    print("[self-test]", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pre", metavar="DIR")
    g.add_argument("--post", metavar="DIR")
    g.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    sys.exit(check_pre(a.pre) if a.pre else check_post(a.post))


def _main_guarded(fn):
    """崩溃 ≠ 有发现:意外异常一律退 2,⛔ 不许和「有发现」共用退出码 1。"""
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 工具自身异常(不是「有发现」): %s: %s" % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    _main_guarded(main)
