#!/usr/bin/env python3
"""
Figma 可编辑性门禁 —— 判断一份 Figma 稿是不是「研发能直接用」的高精度可编辑稿。

为什么需要它：
  人工三问自检（能改字吗/能改色吗/尺寸是量的吗）会对「堆矩形」的稿子全绿，
  因为堆矩形也是真图层。三问检验的是「不是贴图」，不是「能维护、能交接」。

判据（四个可计算比率，全部要过）：
  1. 组件实例化率  INSTANCE / (INSTANCE + 裸 RECT + 裸 ELLIPSE)   ≥ 阈值
  2. 变量绑定率    有 boundVariables 的节点 / 有视觉属性的节点     ≥ 阈值
  3. 硬编码填充数  既没绑变量也没绑样式的 SOLID 填充                ≤ 阈值
  4. AutoLayout    用了 AutoLayout 的容器 / 全部容器                ≥ 阈值

数据来源：Figma REST API（读操作，**不消耗 MCP 写入配额**）
用法：
  figma-editability-gate.py <fileKey> [--token-env FIGMA_PAT | --keychain <service>]
                            [--json] [--strict]
退出码：0=通过  1=不通过  2=跑不了（环境/网络/权限）—— 三者绝不折叠
"""
import argparse, json, os, subprocess, sys, urllib.request, urllib.error, collections

# 阈值：默认值面向「基座库已建成」的稿子。--strict 用更严的一档。
THRESHOLDS = {
    "default": {"instance_rate": 0.60, "var_bind_rate": 0.50, "max_hardcoded": 60,  "autolayout_rate": 0.80},
    "strict":  {"instance_rate": 0.80, "var_bind_rate": 0.75, "max_hardcoded": 10,  "autolayout_rate": 0.90},
}
VISUAL_KEYS = ("fills", "strokes", "effects", "cornerRadius", "itemSpacing",
               "paddingLeft", "paddingRight", "paddingTop", "paddingBottom")


def die_unable(msg):
    """环境问题 → 退出码 2。绝不返回 0，'跑不了' 不等于 '跑了没问题'。"""
    print(f"UNABLE: {msg}", file=sys.stderr)
    sys.exit(2)


def get_token(args):
    if args.token_env:
        t = os.environ.get(args.token_env)
        if not t:
            die_unable(f"环境变量 {args.token_env} 为空")
        return t
    try:
        t = subprocess.run(["security", "find-generic-password", "-s", args.keychain, "-w"],
                           capture_output=True, text=True, timeout=15)
    except Exception as e:
        die_unable(f"读 Keychain 失败：{e}")
    if t.returncode != 0 or not t.stdout.strip():
        die_unable(f"Keychain 里没有 service={args.keychain} 的条目")
    return t.stdout.strip()


def fetch(file_key, token):
    req = urllib.request.Request(f"https://api.figma.com/v1/files/{file_key}",
                                 headers={"X-Figma-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        die_unable(f"Figma API HTTP {e.code}：{e.read()[:200].decode('utf8','replace')}")
    except Exception as e:
        die_unable(f"取文件失败：{e}")


def analyze(doc, page_filter=None):
    m = collections.Counter()
    types = collections.Counter()
    hardcoded_samples = []

    def has_visual(n):
        return any(k in n for k in VISUAL_KEYS)

    def walk(n, in_instance=False, page=None):
        t = n.get("type")
        if t == "CANVAS":
            page = n.get("name")
            if page_filter and page_filter not in page:
                return
        types[t] += 1
        m["total"] += 1

        # 主组件内部不计入实例化率的分母——组件本来就是用图元搭的
        inside_master = in_instance or t in ("COMPONENT", "COMPONENT_SET")

        if t == "INSTANCE":
            m["instance"] += 1
        elif t in ("RECTANGLE", "ELLIPSE", "VECTOR", "LINE", "POLYGON", "STAR") and not inside_master:
            m["bare_shape"] += 1

        if t in ("FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"):
            m["container"] += 1
            if n.get("layoutMode", "NONE") != "NONE":
                m["autolayout"] += 1

        if has_visual(n):
            m["visual_nodes"] += 1
            bv = n.get("boundVariables") or {}
            st = n.get("styles") or {}
            if bv or st:
                m["bound_nodes"] += 1
            fills = n.get("fills") or []
            solid_visible = [f for f in fills
                             if f.get("type") == "SOLID" and f.get("visible", True)]
            if solid_visible and not bv.get("fills") and not st.get("fill") and not inside_master:
                m["hardcoded_fill"] += 1
                if len(hardcoded_samples) < 12:
                    c = solid_visible[0].get("color", {})
                    hexv = "#%02X%02X%02X" % (round(c.get("r", 0) * 255),
                                              round(c.get("g", 0) * 255),
                                              round(c.get("b", 0) * 255))
                    hardcoded_samples.append(f"{page or '?'} / {n.get('name','?')} → {hexv}")

        for c in n.get("children") or []:
            walk(c, inside_master, page)

    walk(doc)
    return m, types, hardcoded_samples


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file_key")
    p.add_argument("--keychain", default="figma-rest-pat")
    p.add_argument("--token-env")
    p.add_argument("--page", help="只看名字含此串的 Page")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--from-file", help="改从本地 JSON 读（离线复核 / 门禁自证用），跳过网络")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    th = THRESHOLDS["strict" if a.strict else "default"]
    if a.from_file:
        try:
            data = json.load(open(a.from_file))
        except Exception as e:
            die_unable(f"读本地文件失败：{e}")
        if "document" not in data:
            die_unable(f"{a.from_file} 不是 Figma 文件 JSON（没有 document 字段）")
    else:
        data = fetch(a.file_key, get_token(a))
    m, types, samples = analyze(data["document"], a.page)

    if m["total"] <= 1:
        die_unable("文件里没有可分析的节点（Page 过滤是不是写错了？）")

    inst_denom = m["instance"] + m["bare_shape"]
    r = {
        "instance_rate":   m["instance"] / inst_denom if inst_denom else 0.0,
        "var_bind_rate":   m["bound_nodes"] / m["visual_nodes"] if m["visual_nodes"] else 0.0,
        "hardcoded_fill":  m["hardcoded_fill"],
        "autolayout_rate": m["autolayout"] / m["container"] if m["container"] else 0.0,
    }
    checks = [
        ("组件实例化率", f"{r['instance_rate']*100:.1f}%", f"≥{th['instance_rate']*100:.0f}%",
         r["instance_rate"] >= th["instance_rate"]),
        ("变量/样式绑定率", f"{r['var_bind_rate']*100:.1f}%", f"≥{th['var_bind_rate']*100:.0f}%",
         r["var_bind_rate"] >= th["var_bind_rate"]),
        ("硬编码填充数", str(r["hardcoded_fill"]), f"≤{th['max_hardcoded']}",
         r["hardcoded_fill"] <= th["max_hardcoded"]),
        ("AutoLayout 覆盖率", f"{r['autolayout_rate']*100:.1f}%", f"≥{th['autolayout_rate']*100:.0f}%",
         r["autolayout_rate"] >= th["autolayout_rate"]),
    ]
    passed = all(c[3] for c in checks)

    if a.json:
        print(json.dumps({"file": data.get("name"), "lastModified": data.get("lastModified"),
                          "mode": "strict" if a.strict else "default",
                          "metrics": r, "raw": dict(m), "types": dict(types),
                          "checks": [{"name": c[0], "actual": c[1], "required": c[2], "pass": c[3]}
                                     for c in checks],
                          "passed": passed}, ensure_ascii=False, indent=2))
    else:
        print(f"文件：{data.get('name')}　最后修改：{data.get('lastModified')}")
        print(f"档位：{'strict' if a.strict else 'default'}　节点总数：{m['total']}")
        print(f"类型分布：{dict(types.most_common(8))}\n")
        w = max(len(c[0]) for c in checks)
        for name, actual, req, ok in checks:
            print(f"  {'✅' if ok else '❌'} {name:<{w}}  实测 {actual:<10} 要求 {req}")
        if samples:
            print(f"\n  硬编码填充样例（前 {len(samples)} 条）：")
            for s in samples:
                print(f"    · {s}")
        print(f"\n结论：{'PASS' if passed else 'FAIL'}")
        if not passed:
            print("⚠️ 不可编辑意味着**设计师拿到的是一张图，不是一份可维护的稿** —— "
                  "改一个圆角要重画，而改动不会回流到令牌，下一轮实现又会对不上。")
    sys.exit(0 if passed else 1)




# ------------------------------------------------------------------ M8 自证
def _self_test():
    """走 --from-file 离线自证，不碰网络、不消耗配额。
    ⚠️ 2026-08-31 补 —— 此前文档声称「全部门禁均自带 --self-test」而本脚本没有。"""
    import os, sys, json as _j, tempfile, subprocess, io as _io
    t = tempfile.mkdtemp(prefix="feg-"); me = os.path.abspath(__file__)
    def node(n, ty, **kw):
        d = {"id": "1:%d" % (abs(hash(n)) % 9999), "name": n, "type": ty}; d.update(kw); return d
    def doc(instances, rects, bound, autolayout):
        kids = []
        for i in range(instances):
            kids.append(node("Btn%d" % i, "INSTANCE", fills=[{"type": "SOLID"}],
                             boundVariables=({"fills": {}} if i < bound else {}),
                             layoutMode=("VERTICAL" if i < autolayout else "NONE")))
        for i in range(rects):
            kids.append(node("Rect%d" % i, "RECTANGLE", fills=[{"type": "SOLID", "visible": True}]))
        return {"document": {"id": "0:0", "name": "Doc", "type": "DOCUMENT",
                             "children": [{"id": "0:1", "name": "Page", "type": "CANVAS", "children": kids}]}}
    def wrap(kids):
        return {"document": {"id": "0:0", "name": "Doc", "type": "DOCUMENT",
                             "children": [{"id": "0:1", "name": "Page", "type": "CANVAS",
                                           "children": kids}]}}

    def iso_instance():
        """只让**实例化率**不合格。
        分母 = INSTANCE + 裸图元，所以必须用 RECTANGLE 稀释；
        但给它们 `boundVariables.fills` —— 这样既不算硬编码填充、绑定率也仍是 100%。
        AutoLayout 分母只数容器（FRAME/COMPONENT/INSTANCE），裸图元不进，故不受影响。"""
        kids = [node("Btn%d" % i, "INSTANCE", fills=[],
                     boundVariables={"fills": {}}, layoutMode="VERTICAL") for i in range(2)]
        kids += [node("R%d" % i, "RECTANGLE",
                      fills=[{"type": "SOLID", "visible": True}],
                      boundVariables={"fills": {}}) for i in range(20)]
        return wrap(kids)

    def iso_hardcoded():
        """只让**硬编码填充数**不合格（默认阈值 ≤60，所以要 >60 个）。
        全部是 INSTANCE：实例化率 100%、AutoLayout 100%；
        给 `boundVariables.strokes` 让绑定率 100%，但 fills 未绑 → 计入硬编码。"""
        kids = [node("Btn%d" % i, "INSTANCE",
                     fills=[{"type": "SOLID", "visible": True, "color": {"r": 0, "g": 0, "b": 0}}],
                     boundVariables={"strokes": {}}, layoutMode="VERTICAL") for i in range(70)]
        return wrap(kids)

    def w(n, obj):
        p = os.path.join(t, n); _io.open(p, "w", encoding="utf-8").write(_j.dumps(obj)); return p
    def run(f, *x):
        return subprocess.call([sys.executable, me, "FAKEKEY", "--from-file", f] + list(x),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # ⚠️ 2026-08-31 自审补：本门判**四个**比率，而此前只有**两个**有反例——
    #    硬编码填充数与 AutoLayout 两条**从没被验过会不会红**。
    #    ⭐⭐ 一条从没被反向测过的判据，和一条不存在的判据，在效果上没有区别。
    cases = [("正例 组件化+绑定齐全", doc(20, 1, 20, 20), 0),
             ("反例 堆矩形(实例化率低)", doc(2, 20, 2, 2), 1),
             ("反例 零变量绑定", doc(20, 1, 0, 20), 1),
             ("反例 零 AutoLayout", doc(20, 1, 20, 0), 1),
             ("反例 硬编码填充超标", doc(20, 30, 20, 20), 1),
             # ⭐ 2026-09-02 变异审计补：上面「堆矩形」与「硬编码超标」两条**同时触发多个比率**，
             #    强制其中任一条恒真，自证照样全绿 —— 它们各自从没被单独守住。
             #    ⚠️ 隔离要靠「只挪走一样东西」：下面两条用**无填充的 FRAME** 当分母，
             #    这样只动实例化率而不碰硬编码/绑定/AutoLayout。
             ("反例 只有实例化率低（隔离）", iso_instance(), 1),
             ("反例 只有硬编码超标（隔离）", iso_hardcoded(), 1)]
    ok = True
    print("M8 自证（离线 --from-file，不消耗 MCP 配额）\n")
    for n, obj, want in cases:
        rc = run(w(n.replace(" ", "_") + ".json", obj)); g = rc == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, rc))
    rc = run(os.path.join(t, "nope.json")); g = rc == 2; ok &= g
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g else "❌", "输入不存在", rc))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败"))
    return 0 if ok else 1


# ── 意外异常必须报「跑不了」，不许和「有发现」共用退出码 ────────────────
# 🚨 2026-09-05：本门原有针对**特定读操作**的 `except`，但意外异常出现在别处仍会 rc=1
#    —— **与「有发现」同码**。后果：① 报告里长成「有发现」，把人送去查不存在的缺陷；
#    ② 自证里只看退出码的反例，**崩溃会被读成「反例红了」**。
# ⛔ `except Exception` 不捕获 `SystemExit`，门禁自己的 exit(0/1/2) 不受影响。
def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb, sys as _sys
        print("UNABLE: 门禁自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=_sys.stderr)
        _tb.print_exc(file=_sys.stderr)
        _sys.exit(2)


if __name__ == '__main__':
    def _entry():
        if "--self-test" in sys.argv:
            import sys as _s; _s.exit(_self_test())
        main()
    _main_guarded(_entry)
