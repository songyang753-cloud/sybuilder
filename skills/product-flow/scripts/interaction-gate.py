#!/usr/bin/env python3
"""
交互反模式门禁 —— 只查「不需要判断力就能判定」的那一层。

定位：交互质量分三层，这是第 1 层。
  第 1 层 门禁（本脚本）：可 grep 的反模式，硬失败
  第 2 层 走查：键盘走一遍 / 多选走一遍 / 撤销走一遍（人做，见 interaction-desktop.md）
  第 3 层 评审视角：UE 专家的 Trunk Test / Goodwill / Mindless-choice
**只跑第 1 层不算做了交互质量。** 报绿只意味着没有机械可查的反模式。

判据来源：references/interaction-criteria.md
用法：interaction-gate.py <file|dir> [--json] [--list-rules]
退出码：0=干净 1=有发现 2=跑不了
"""
import argparse, json, os, re, sys

def die(m): print(f"UNABLE: {m}", file=sys.stderr); sys.exit(2)

def strip_comments(t):
    for pat in (re.compile(r'<!--.*?-->', re.S), re.compile(r'/\*.*?\*/', re.S)):
        t = pat.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), t)
    return t

RULES = []
def rule(rid, desc, why):
    def deco(fn):
        RULES.append({"id": rid, "desc": desc, "why": why, "fn": fn}); return fn
    return deco

def hits(pat, t, flags=0, label=None, limit=5):
    out = []
    for m in re.finditer(pat, t, flags):
        out.append({"line": t[:m.start()].count("\n") + 1,
                    "snippet": (label or m.group(0))[:100]})
        if len(out) >= limit: break
    return out

@rule("zoom-disabled", "禁用了浏览器缩放", "低视力用户被直接挡在门外")
def r1(t): return hits(r'user-scalable\s*=\s*no|maximum-scale\s*=\s*["\']?1', t, re.I)

@rule("paste-blocked", "拦截了粘贴", "密码管理器、验证码、长文本全废")
def r2(t):
    # 两个坑（都是自证时才暴露的）：
    #   ① onPaste 可以是内联属性 onPaste="e.preventDefault()"，后面根本没有 `{`
    #   ② addEventListener('paste', function(e){...}) 里的 `function(e)` 自带 `)`，
    #      用 [^)] 会在那里就截断，永远匹配不到后面的 preventDefault
    out = []
    pats = [r'on[Pp]aste\s*=\s*["\'][^"\']{0,200}?preventDefault',      # 内联属性
            r'on[Pp]aste[^;{]{0,80}\{[\s\S]{0,300}?preventDefault',       # JSX / 赋值 + 函数体
            r'addEventListener\(\s*["\']paste["\'][\s\S]{0,300}?preventDefault']  # 监听器
    seen = set()
    for pat in pats:
        for m in re.finditer(pat, t):
            ln = t[:m.start()].count("\n") + 1
            if ln in seen: continue
            seen.add(ln)
            out.append({"line": ln, "snippet": "paste 被 preventDefault"})
    return sorted(out, key=lambda x: x["line"])[:5]

@rule("transition-all", "`transition: all`", "所有属性同速，且会动到你没想动的东西")
def r3(t): return hits(r'transition\s*:\s*all\b', t, re.I)

@rule("outline-none", "`outline:none` 且全文没有 :focus-visible 替代", "键盘用户失去焦点位置")
def r4(t):
    if re.search(r':focus-visible', t): return []
    return hits(r'outline\s*:\s*(none|0)\b', t, re.I)

@rule("div-onclick", "`<div>`/`<span>` 挂点击处理器", "不可聚焦、不响应 Enter/Space、读屏读不出是按钮")
def r5(t):
    return hits(r'<(div|span)\b[^>]*\son[Cc]lick[=\s]', t)

@rule("img-no-dim", "`<img>` 缺 width/height", "加载时布局跳动（CLS）")
def r6(t):
    out = []
    for m in re.finditer(r'<img\b[^>]*>', t, re.I):
        tag = m.group(0)
        if not (re.search(r'\bwidth\s*=', tag, re.I) and re.search(r'\bheight\s*=', tag, re.I)) \
           and 'aspect-ratio' not in tag:
            out.append({"line": t[:m.start()].count("\n") + 1, "snippet": tag[:80]})
        if len(out) >= 5: break
    return out

@rule("input-no-label", "表单控件没有 label / aria-label", "读屏读不出这个框是干什么的")
def r7(t):
    out = []
    for m in re.finditer(r'<(input|select|textarea)\b[^>]*>', t, re.I):
        tag = m.group(0)
        if re.search(r'type\s*=\s*["\']?(hidden|submit|button)', tag, re.I): continue
        if re.search(r'aria-label|aria-labelledby', tag, re.I): continue
        # ⚠️ 有 `id=` **不等于**有 label。首版见到 id 就跳过，等于假设「有人用 label for 指过它」——
        #    而 `<input id="q">` 配上不存在的 label，正是这条规则该抓的情形，却被静默放行。
        #    **不许用「存在某个属性」去推断「存在某个关系」，要去查那个关系本身。**
        idm = re.search(r'\bid\s*=\s*["\']?([\w:.-]+)', tag, re.I)
        if idm and re.search(r'<label\b[^>]*\bfor\s*=\s*["\']?' + re.escape(idm.group(1)) + r'["\'\s>]', t, re.I):
            continue
        # 被 <label> 直接包裹的也算有 label
        head = t[max(0, m.start() - 300): m.start()]
        if re.search(r'<label\b[^>]*>(?:(?!</label>).)*$', head, re.I | re.S): continue
        out.append({"line": t[:m.start()].count("\n") + 1, "snippet": tag[:80]})
        if len(out) >= 5: break
    return out

@rule("iconbtn-no-label", "只含图标/符号的按钮没有 aria-label", "读屏读不出这个按钮是干什么的")
def r8(t):
    out = []
    for m in re.finditer(r'<button\b([^>]*)>(.*?)</button>', t, re.S | re.I):
        attrs, inner = m.group(1), re.sub(r'<[^>]*>', '', m.group(2)).strip()
        if re.search(r'aria-label|aria-labelledby|\btitle\s*=', attrs, re.I): continue
        # 内容为空、或只有 1-2 个非中英数字符（图标字形）
        if inner == "" or (len(inner) <= 2 and not re.search(r'[\w一-鿿]', inner)):
            out.append({"line": t[:m.start()].count("\n") + 1,
                        "snippet": f"<button>{inner or '(空)'}</button>"})
        if len(out) >= 5: break
    return out

@rule("autofocus", "用了 autoFocus", "打断键盘用户与读屏的阅读顺序，需明确理由")
def r9(t): return hits(r'\bautoFocus\b|\bautofocus\b', t)

@rule("hover-only", "hover 效果没放进 @media (hover: hover)", "触屏用户会卡在 hover 态出不来")
def r10(t):
    if not re.search(r':hover', t): return []
    if re.search(r'@media[^{]*\(\s*hover\s*:\s*hover', t, re.I): return []
    n = len(re.findall(r':hover', t))
    return [{"line": 0, "snippet": f"全文 {n} 处 :hover，但没有任何 @media (hover: hover) 包裹"}] if n >= 3 else []

@rule("no-reduced-motion", "有动效但没有 prefers-reduced-motion 分支", "前庭敏感用户无处可逃")
def r11(t):
    if not re.search(r'transition\s*:|animation\s*:|@keyframes', t, re.I): return []
    if re.search(r'prefers-reduced-motion', t, re.I): return []
    return [{"line": 0, "snippet": "全文有 transition/animation，但没有 prefers-reduced-motion"}]

@rule("ease-in-on-ui", "UI 过渡用了 ease-in", "起步慢，恰好延迟用户正在盯着的那一刻（block 级）")
def r15(t):
    out = []
    # ⚠️ 必须加换行边界：散文文档里几乎没有 `;{}`，不加的话这个贪婪段会从一处
    #    `transition-duration: 0ms` 一路吞到 190 行外，把正文里「30s 超时」这种
    #    **业务超时**当成 UI 过渡时长报红（实测捕获段 6607 字符、跨 190 行）。
    for m in re.finditer(r"transition[^;{}\n]*:\s*([^;{}\n]+)", t, re.I):
        d = m.group(1)
        if re.search(r"\bease-in\b(?!-out)", d):
            out.append({"line": t[:m.start()].count("\n")+1, "snippet": d.strip()[:70]})
        if len(out) >= 5: break
    return out

@rule("keyframes-on-transient", "瞬态/高频元素用 @keyframes 动画而非 transition",
      "keyframes 从零重启、无法从当前状态重定向 —— 快速连点会看到动画跳回起点")
def r_interrupt(t):
    """⭐ 把「可打断性」变成可查的那一步：**不查「它有没有被打断」（动态、难测），
    查「它用的机制能不能被打断」（静态、确定）**。
    CSS `transition` 从当前计算值重定向；`@keyframes`/`animation` 从 0 重启。
    ⇒ 瞬态或高频触发的元素（toast / tooltip / dropdown / popover / toggle / drawer）
    用 animation 就是不可打断。

    来源：`memi-design/design-skills` 的 review-animations（承自 Emil Kowalski / animations.dev）
    第 6 条：「Rapidly-triggered or gesture-driven motion must be interruptible —
    CSS transitions or springs that retarget from current state, not keyframes that restart from zero.」

    ⚠️ 诚实边界：只看**选择器名**里有没有那几个词。名字里不带 toast 的 toast 查不出来；
    JS 驱动的弹簧动画（本身可打断）也不在扫描范围内 —— 那是漏报，不是误报。
    """
    # 🔴 2026-09-05 修：此前是无边界子串匹配，`#plan-preview-**table**` 里的 `table`
    #    含子串 `tab` ⇒ **误报**（云端办公 Agent 项目实测撞到）。同族误伤还有
    #    `stylesheet`（含 sheet）、`tablet`（含 tab）。
    #    ⭐ 而它的正例里恰好一个这类词都没有 —— **判据只能过自己挑的那个正例**。
    #    现改为 CSS 标识符级的整词匹配：两侧不许是字母数字，尾部允许复数 s/es。
    #    `-tab-` `.tabs` `bottom-sheet` `switches` 仍然命中；`table` `stylesheet` 不再命中。
    TRANSIENT = (r'(?<![a-z0-9])'
                 r'(toast|snackbar|tooltip|dropdown|popover|menu|toggle|switch|drawer|sheet|tab)'
                 r'(e?s)?(?![a-z0-9])')
    out = []
    for m in re.finditer(r'([^{}]*)\{([^{}]*)\}', t):
        sel, body = m.group(1), m.group(2)
        if not re.search(TRANSIENT, sel, re.I): continue
        if not re.search(r'\banimation(-name)?\s*:', body, re.I): continue
        if re.search(r'\banimation(-name)?\s*:\s*none\b', body, re.I): continue
        out.append({"line": t[:m.start()].count("\n")+1, "snippet": (sel.strip()[:40] + " { " + body.strip()[:40])})
        if len(out) >= 5: break
    return out

@rule("scale-from-zero", "动效从 scale(0) 起手", "从零放大像弹出气球；应从 0.9–0.97 + opacity 起")
def r_scale0(t):
    """来源同上，第 5 条：Never animate from `scale(0)` — start from `scale(0.9–0.97)` + opacity。"""
    out = []
    for m in re.finditer(r'scale\(\s*0(?:\.0+)?\s*\)', t, re.I):
        out.append({"line": t[:m.start()].count("\n")+1, "snippet": t[max(0,m.start()-30):m.end()+10].replace("\n"," ")[:70]})
        if len(out) >= 5: break
    return out

@rule("duration-over-budget", "UI 过渡超 300ms 且无举证", "总则 UI <=300ms；超过是举证责任倒置")
def r16(t):
    out = []
    for m in re.finditer(r"transition[^;{}\n]*:\s*([^;{}\n]+)", t, re.I):
        seg = m.group(1)
        line = t[:m.start()].count("\n")+1
        # 同行或上一行有注释即视为已举证
        ctx = "\n".join(t.split("\n")[max(0,line-2):line])
        if "/*" in ctx or "举证" in ctx: continue
        for dm in re.finditer(r"([\d.]+)(m?s)", seg):
            ms = float(dm.group(1)) * (1 if dm.group(2) == "ms" else 1000)
            if ms > 300:
                out.append({"line": line, "snippet": "%gms in `%s`" % (ms, seg.strip()[:44])})
                break
        if len(out) >= 5: break
    return out

@rule("gif", "用了动图而非压缩视频", "体积与解码开销")
def r12(t): return hits(r'\.gif["\')\s]', t, re.I)

@rule("hardcoded-format", "硬编码日期/数字格式", "应走 Intl.*，否则多语言/多地区必错")
def r13(t):
    if re.search(r'Intl\.', t): return []
    return hits(r'toFixed\(\s*\d\s*\)\s*\+\s*["\']%|toLocaleDateString\(\)\s*$', t)

@rule("nav-not-anchor", "用 onclick 导航而不是 <a>", "⌘/中键点击、右键复制链接全失效")
def r14(t):
    return hits(r'on[Cc]lick\s*=\s*["\'][^"\']*(location\.href|window\.open|history\.push)', t)

def scan(text):
    t = strip_comments(text)
    found = []
    for r in RULES:
        for h in r["fn"](t):
            found.append({"rule": r["id"], "desc": r["desc"], "why": r["why"], **h})
    return found

def main():
    p = argparse.ArgumentParser()
    p.add_argument("target", nargs="?")
    p.add_argument("--json", action="store_true")
    p.add_argument("--list-rules", action="store_true")
    a = p.parse_args()
    if a.list_rules:
        for r in RULES: print(f"{r['id']:<20} {r['desc']}")
        sys.exit(0)
    if not a.target: die("缺少扫描目标")
    if not os.path.exists(a.target): die(f"目标不存在：{a.target}")
    files = []
    if os.path.isdir(a.target):
        for root, _, fs in os.walk(a.target):
            if "node_modules" in root or "/." in root: continue
            files += [os.path.join(root, f) for f in fs
                      if f.endswith((".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".css"))]
    else:
        files = [a.target]
    if not files: die(f"{a.target} 下没有可扫描的文件")

    allf = []
    for f in files:
        try: txt = open(f, encoding="utf8", errors="replace").read()
        except Exception as e: die(f"读不了 {f}：{e}")
        for x in scan(txt): allf.append({"file": f, **x})

    if a.json:
        print(json.dumps({"files": len(files), "findings": allf, "clean": not allf},
                         ensure_ascii=False, indent=2))
    else:
        print(f"扫描 {len(files)} 个文件　规则 {len(RULES)} 条\n")
        by = {}
        for x in allf: by.setdefault(x["rule"], []).append(x)
        for rid, xs in by.items():
            print(f"  ❌ {rid}（{len(xs)} 处）— {xs[0]['desc']}")
            print(f"       为什么：{xs[0]['why']}")
            for x in xs[:2]:
                loc = f":{x['line']}" if x['line'] else ""
                print(f"       {os.path.basename(x['file'])}{loc}  {x['snippet']}")
        if not allf: print("  （无机械可查的交互反模式）")
        print(f"\n结论：{'CLEAN' if not allf else 'FOUND ' + str(len(allf))}")
        print("⚠️ 这是交互质量三层里的第 1 层。报绿不代表交互好用——")
        print("   键盘走查、多选走查、撤销走查与 UE 视角评审不可省。")
    sys.exit(0 if not allf else 1)


_ST_EXT = ".html"
_ST_BAD_RC = 2
_GOOD_HTML = """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
@media (hover:hover){ .b:hover{opacity:.9} }
.b{transition:opacity .15s ease-out}
/* ⭐ 假阳性守卫（2026-09-05）：以下三个选择器**含瞬态词的子串但不是瞬态元素** ——
   table 含 tab · stylesheet 含 sheet · tablet 含 tab。它们用 animation 是合法的，
   若 keyframes-on-transient 退回无边界子串匹配，正例会变红。 */
#plan-preview-table{animation:fade .2s ease-out both}
.stylesheet-note{animation:fade .2s ease-out both}
#tablet-view{animation:fade .2s ease-out both}
@keyframes fade{from{opacity:0}to{opacity:1}}
.b:focus-visible{outline:2px solid #1F6F5C;outline-offset:2px}
@media (prefers-reduced-motion: reduce){ .b{transition:none} }
</style></head><body>
<a class="b" href="/next">前往</a>
<label for="q">搜索</label><input id="q" type="text">
<button class="b" aria-label="关闭">×</button>
<img src="a.png" width="80" height="80" alt="图">
</body></html>"""
# ── 两条动效新规则的反例（新增规则必须自带反例，否则等于没测）──
# 瞬态元素用 @keyframes = 不可打断
_BAD_KEYFRAMES = _GOOD_HTML.replace("<style>",
    "<style>@keyframes pop{from{opacity:0}to{opacity:1}} .toast{animation:pop .2s ease-out}")
_BAD_SCALE0 = _GOOD_HTML.replace("transition:opacity .15s ease-out",
    "transition:transform .15s ease-out;transform:scale(0)")
for _n, _s in (('keyframes', _BAD_KEYFRAMES), ('scale0', _BAD_SCALE0)):
    if _s == _GOOD_HTML: raise SystemExit("自证用例坏了：动效反例 %s 是 no-op" % _n)

_ST_CASES = [
    ("正例", _GOOD_HTML, 0),
    ("反例 瞬态元素用 keyframes（不可打断）", _BAD_KEYFRAMES, 1),
    ("反例 从 scale(0) 起手", _BAD_SCALE0, 1),
    # ⭐ 收紧判据必须两向都验：假阳性不再误伤（见正例里的 table/stylesheet/tablet），
    #    而**复数与连字符形式的真缺陷仍要被抓住** —— 只验一向就会把真缺陷一起放过。
    ("反例 复数形式的瞬态元素用 keyframes（.tabs）",
     _GOOD_HTML.replace("#tablet-view{animation", ".tabs{animation:fade .2s ease-out both}\n#tablet-view{animation"), 1),
    ("反例 禁用缩放", _GOOD_HTML.replace("initial-scale=1", "initial-scale=1,user-scalable=no"), 1),
    ("反例 transition-all", _GOOD_HTML.replace("transition:opacity .15s ease-out", "transition:all .3s"), 1),
    ("反例 div onclick", _GOOD_HTML.replace("<a class=\"b\" href=\"/next\">前往</a>", "<div onclick=\"go()\">前往</div>"), 1),
    ("反例 img 缺尺寸", _GOOD_HTML.replace('width="80" height="80" ', ''), 1),
    ("反例 input 无 label", _GOOD_HTML.replace('<label for="q">搜索</label>', ''), 1),
    ("反例 图标按钮无 aria-label", _GOOD_HTML.replace(' aria-label="关闭"', ''), 1),
    ("反例 UI 用 ease-in", _GOOD_HTML.replace("opacity .15s ease-out", "opacity .15s ease-in"), 1),
    # ⭐ 2026-09-01 补：插桩实测 16 条规则里只有 7 条在自证里红过 ——
    #    **从没被反向测过的判据，和不存在的判据效果没区别**。以下逐条补齐。
    ("反例 拦截粘贴（paste-blocked）",
     _GOOD_HTML.replace('<input id="q" type="text">',
                        '<input id="q" type="text" onPaste="e.preventDefault()">'), 1),
    ("反例 outline:none 且无 focus-visible 替代（outline-none）",
     _GOOD_HTML.replace('.b:focus-visible{outline:2px solid #1F6F5C;outline-offset:2px}',
                        '.b{outline:none}'), 1),
    ("反例 autofocus（autofocus）",
     _GOOD_HTML.replace('<input id="q" type="text">', '<input id="q" type="text" autofocus>'), 1),
    # ⚠️ 反例要真的制造出那个缺口：本规则有 **n>=3 的阈值**（1 处 :hover 不算模式），
    #    第一版只放 1 处，红不了 —— 不是规则坏了，是反例没造够。
    ("反例 hover 没包 @media (hover:hover)（hover-only，阈值 n>=3）",
     _GOOD_HTML.replace('@media (hover:hover){ .b:hover{opacity:.9} }',
                        '.b:hover{opacity:.9} .c:hover{opacity:.8} .d:hover{opacity:.7}'), 1),
    ("反例 有动效但无 prefers-reduced-motion（no-reduced-motion）",
     _GOOD_HTML.replace('@media (prefers-reduced-motion: reduce){ .b{transition:none} }', ''), 1),
    ("反例 UI 过渡超 300ms（duration-over-budget）",
     _GOOD_HTML.replace('transition:opacity .15s ease-out', 'transition:opacity .5s ease-out'), 1),
    ("反例 用 gif 而非视频（gif）",
     _GOOD_HTML.replace('src="a.png"', 'src="a.gif"'), 1),
    ("反例 硬编码百分比格式（hardcoded-format）",
     _GOOD_HTML.replace('</body>', '<script>el.textContent=x.toFixed(1)+"%"</script></body>'), 1),
    ("反例 用 onclick 导航而不是 <a>（nav-not-anchor）",
     _GOOD_HTML.replace('<a class="b" href="/next">前往</a>',
                        '<span onclick="location.href=\'/next\'">前往</span>'), 1),
]


# ------------------------------------------------------------------ M8 自证
def _self_test():
    """M8 四步自证：正例绿 / 每类反例红 / 无效输入报错不返绿 / 人工核实每条命中。

    ⚠️ 本函数是 2026-08-31 补的。此前 `design-quality-gates.md` 写着
    「**全部**门禁与扫描均自带 --self-test」，而本脚本并没有 —— 又一例「声称 ≠ 实际」。
    现由 consistency-gate 的 `selftest-claim` 规则常驻守着。
    """
    import os, sys, tempfile, subprocess, io as _io
    t = tempfile.mkdtemp(prefix="st-")
    me = os.path.abspath(__file__)
    def w(n, c):
        p = os.path.join(t, n); _io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(p, *extra):
        return subprocess.call([sys.executable, me, p] + list(extra),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ok = True
    print("M8 自证 —— 正例绿 / 每类反例红 / 无效输入报错不返绿\n")
    for name, body, want in _ST_CASES:
        rc = run(w(name.replace(' ', '_') + _ST_EXT, body))
        g = rc == want; ok &= g
        print("  %s %-34s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, rc))
    rc = run(os.path.join(t, "nope" + _ST_EXT))
    g = rc == _ST_BAD_RC; ok &= g
    print("  %s %-34s 期望 %d 实得 %d" % ("✅" if g else "❌", "输入不存在", _ST_BAD_RC, rc))
    # 🆕 2026-09-05 `--unable` 实测：「读不了 <文件>」这个出口从没被触发过。
    #    ⭐ 这类前提守卫锚点写错时**两头都不出声**：既不报「没跑过」也不报缺陷。
    #    ⚠️ root 身份下 chmod 000 仍可读 —— 那种情况下跳过并明说，不冒充通过。
    _nr = os.path.join(t, "unreadable" + _ST_EXT)
    _io.open(_nr, "w", encoding="utf-8").write("<div>x</div>")
    try:
        os.chmod(_nr, 0)
        _readable = True
        try:
            open(_nr, encoding="utf8").read()
        except Exception:
            _readable = False
        if _readable:
            print("  ⏭️  %-34s 当前身份下 chmod 000 仍可读，跳过（不计入通过）" % "读不了的文件")
        else:
            rc = run(_nr); g = rc == _ST_BAD_RC; ok &= g
            print("  %s %-34s 期望 %d 实得 %d"
                  % ("✅" if g else "❌", "文件读不了 → 报 2", _ST_BAD_RC, rc))
    finally:
        try: os.chmod(_nr, 0o644)
        except Exception: pass
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修门禁"))
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
        import sys
        sys.exit(_self_test() if "--self-test" in sys.argv else main())
    _main_guarded(_entry)
