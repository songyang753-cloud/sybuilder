#!/usr/bin/env python3
"""
tokens.json → CSS 自定义属性。

为什么要有它：令牌若在 demo 里手抄一遍、在 Figma 里再手抄一遍，
两处必然悄悄不一致，而且不会有任何东西报错。
**一份真源，两个下游**：S6 用本脚本生成 CSS，S7 用同一份 JSON 生成 Figma Variables。

用法：tokens-to-css.py <tokens.json> [--mode Light|Dark|both] [--prefix --g]
退出码：0=成功 2=跑不了
"""
import argparse, json, os, re, sys

def die(m): print(f"UNABLE: {m}", file=sys.stderr); sys.exit(2)

def flatten(node, path=""):
    if isinstance(node, dict):
        if "value" in node or "Light" in node:
            yield path, node; return
        for k, v in node.items():
            if k.startswith("_"): continue
            yield from flatten(v, f"{path}.{k}" if path else k)

def cssname(prefix, p):
    return f"{prefix}-" + re.sub(r'[.\/]', '-', p).replace("_", "-").lower()

# 令牌组 → 单位。**必须在生成时带上单位**：
# 让 CSS 写 `var(--x)px` 看起来能用，实际会在某些浏览器/某些属性上静默失效
# （整条声明被判无效并回落到 auto），而画面不会报错，只是尺寸悄悄不对。
UNIT = {"space": "px", "radius": "px", "size": "px", "type": "px"}
def unit_for(path):
    top = path.split(".")[0]
    if top == "motion":
        return "ms" if re.search(r'\bdur', path, re.I) else ""
    return UNIT.get(top, "")

def resolve(v, prefix, path=""):
    if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
        return f"var({cssname(prefix, v.strip('{}'))})"
    if isinstance(v, (int, float)):
        return f"{v}{unit_for(path)}"
    return str(v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tokens"); ap.add_argument("--mode", default="both",
                    choices=["Light", "Dark", "both"]); ap.add_argument("--prefix", default="--g")
    a = ap.parse_args()
    if not os.path.isfile(a.tokens): die(f"文件不存在：{a.tokens}")
    try: d = json.load(open(a.tokens, encoding="utf8"))
    except Exception as e: die(f"不是合法 JSON：{e}")

    toks = list(flatten(d))
    if not toks: die("没解析出令牌")
    single, modal = [], {"Light": [], "Dark": []}
    for p, t in toks:
        n = cssname(a.prefix, p)
        if "value" in t:
            single.append(f"  {n}: {resolve(t['value'], a.prefix, p)};")
        else:
            for m in ("Light", "Dark"):
                if m in t: modal[m].append(f"  {n}: {resolve(t[m], a.prefix, p)};")

    out = ["/* 自动生成，勿手改。真源：%s */" % os.path.basename(a.tokens), ":root {"]
    out += single + modal["Light"] + ["}"]
    if a.mode == "both" and modal["Dark"]:
        out += ["", '[data-theme="dark"] {'] + modal["Dark"] + ["}"]
        out += ["", "@media (prefers-color-scheme: dark) {", '  :root:not([data-theme="light"]) {']
        out += ["  " + l for l in modal["Dark"]] + ["  }", "}"]
    print("\n".join(out))



def _self_test():
    """⭐ 2026-09-01 补。本脚本此前**零测试**，而它出过一个真 bug 并进了产物：

    数值令牌生成时漏了单位，`--g-space-1: 4`（而不是 `4px`）。
    CSS 里 `padding:var(--g-space-1)` 于是整条声明无效并静默回落 ——
    **画面不会报错，只是尺寸悄悄不对**。验证项目 的 `_head.built` 里躺过这个值。
    脚本头部注释早就写着「必须在生成时带上单位」，而没有任何东西守着它。
    """
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(('  ✓ ' if cond else '  ✗ ') + name)
        ok = ok and cond

    tok = {"space": {"1": {"value": 4}}, "radius": {"sm": {"value": 8}},
           "size": {"sidebar": {"value": 200}}, "type": {"body": {"value": 13}},
           "primitive": {"neutral": {"0": {"value": "#FFFFFF"}}},
           "semantic": {"bg/canvas": {"Light": "{primitive.neutral.0}", "Dark": "{primitive.neutral.0}"}},
           "motion": {"durPress": {"value": 120}}}
    css = render(tok, "both", "--g") if "render" in globals() else None
    if css is None:
        import io as _io, json as _json, os as _os, subprocess as _sp, tempfile as _tf
        d = _tf.mkdtemp(); f = _os.path.join(d, "t.json")
        _io.open(f, "w", encoding="utf8").write(_json.dumps(tok, ensure_ascii=False))
        r = _sp.run([sys.executable, _os.path.abspath(__file__), f, "--mode", "both"],
                    capture_output=True, text=True)
        css = r.stdout

    # ⭐ 判据是「带不带单位」——这正是那个真 bug 的形状
    for name, expect in (("space", "--g-space-1: 4px"), ("radius", "--g-radius-sm: 8px"),
                         ("size", "--g-size-sidebar: 200px"), ("type", "--g-type-body: 13px")):
        chk("%s 组必须带 px 单位（%s）" % (name, expect), expect in css)
    chk("反向：不带单位的裸值不得出现（`--g-space-1: 4;` 会让整条 CSS 声明静默失效）",
        "--g-space-1: 4;" not in css)
    chk("语义层走别名 var() 而不是把值拍平", "var(--g-primitive-neutral-0)" in css)
    chk("motion 不加 px（毫秒不是长度）", "--g-motion-durpress: 120px" not in css)
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败"))
    return ok


if __name__ == "__main__":
    # ⚠️ `--self-test` 必须在 argparse **之前**拦截：argparse 要求位置参数 tokens，
    #    放在后面会先被它报 usage 错误退出（第一版就是这么写的，自证根本跑不到）。
    if "--self-test" in sys.argv:
        sys.exit(0 if _self_test() else 1)
    main()
