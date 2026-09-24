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
import argparse, os, re, struct, subprocess, sys, tempfile

FIG_RE = re.compile(r'!\[[^\]]*\]\(<@\./([^>]+?\.png)>\)')
OBJ_HEAD_RE = re.compile(r'^## +2\.(\d+) ', re.M)
EXCERPT_RE = re.compile(r'\w[\w./-]*\.\w{1,4}:\d+')          # file:line 形状
COUNT_RE = re.compile(r'(\d+)\s*(?:个)?\s*(?:框架|家|个开源框架|个对象)')
SECTION_KEYS = ("意图理解", "分发与反馈", "整体流程")


def parse_scope(path):
    if not os.path.isfile(path):
        return None
    cfg = {}
    for line in open(path, encoding="utf-8"):
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
        with open(path, "rb") as f:
            head = f.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        return struct.unpack(">I", head[20:24])[0]
    except OSError:
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
    text = open(report, encoding="utf-8").read()

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
        figs = FIG_RE.findall(seg)
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
    for rel in FIG_RE.findall(text):
        p = os.path.join(rdir, rel)
        if not os.path.isfile(p):
            errs.append(f"图文件缺失: {rel}")
            continue
        h = png_height(p)
        if h is not None and h > max_h:
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
    scope = parse_scope(os.path.join(rdir, "scope.md"))
    if scope is None:
        print("UNABLE: scope.md 不存在", file=sys.stderr)
        return 2
    platform = scope.get("documentPlatform")
    doc = scope.get("delivery_doc")
    if platform != "feishu" or not doc:
        print("UNABLE: --post 目前仅实现 feishu 回读;需 scope 声明 documentPlatform: feishu 与 delivery_doc", file=sys.stderr)
        return 2
    cmd = ["lark-cli", "docs", "+fetch", "--as", "user", "--doc", str(doc), "--doc-format", "markdown"]
    if scope.get("lark_profile"):
        cmd[1:1] = ["--profile", str(scope["lark_profile"])]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"UNABLE: 平台不可达({e})", file=sys.stderr)
        return 2
    body = out.stdout
    missing = [k for k in ("执行摘要", "2.1", "方案收敛") if k not in body]
    if out.returncode != 0 or missing:
        print(f"FAIL --post: 回读 rc={out.returncode}, 关键节缺失={missing}")
        print("⚠️ 边界: 回读只证关键节存在,验不了正文内容与本地稿一致")
        return 1
    print("PASS --post: 正本回读命中关键节")
    print("⚠️ 边界: 回读只证关键节存在,验不了正文内容与本地稿一致、图是否渲染正常——需人工抽验")
    return 0


# ---------------- self-test ----------------

def _mk_fixture(tmp, n_objs=2, break_numbering=False, drop_fig=False, stale_count=False):
    os.makedirs(os.path.join(tmp, "figs"), exist_ok=True)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 100, 200) + b"\x08\x02\x00\x00\x00" + b"\x00" * 16
    for i in range(1, n_objs + 1):
        for kind in ("intent", "dispatch", "overall"):
            open(os.path.join(tmp, "figs", f"o{i}-{kind}.png"), "wb").write(png)
    open(os.path.join(tmp, "scope.md"), "w", encoding="utf-8").write(
        f"object_count: {n_objs}\nreport_file: report.md\ncount_exemptions: []\n")
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
    open(os.path.join(tmp, "report.md"), "w", encoding="utf-8").write("".join(lines))
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
