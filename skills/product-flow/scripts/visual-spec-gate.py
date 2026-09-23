#!/usr/bin/env python3
"""
视觉规格门禁 —— 执行 references/visual-spec.md 第一至五节的**可量化判据**。

为什么需要它：
  ai-slop-gate 查的是反模式（不该有什么），interaction-gate 查交互反模式。
  而 visual-spec 里的**正面判据**（行长/行高/字阶比/间距阶梯/对比度分级/圆角层级）
  原本没有任何东西执行——写在文档里没人跑，等于没写。

⚠️ 只覆盖第一至五节。第六节（质感·景深·光影）**本脚本不碰**，它不可自动验。
   报告显式区分 PASS / FAIL / N/A，通过率分母只算「通过+失败」。

用法：visual-spec-gate.py <file|dir> [--tokens tokens.json] [--profile web|zh|desktop] [--json]
退出码：0=通过 1=不通过 2=跑不了
"""
import argparse, json, os, re, sys

def die(m):
    print("UNABLE: " + m, file=sys.stderr); sys.exit(2)

SP_SCALE = {4,8,12,16,24,32,48,64,96,128}

def lin(c):
    c /= 255
    return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4

def lum(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(x*2 for x in h)
    if len(h) < 6: return None
    r,g,b = (int(h[i:i+2],16) for i in (0,2,4))
    return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)

def ratio(a,b):
    la,lb = lum(a),lum(b)
    if la is None or lb is None: return None
    hi,lo = max(la,lb),min(la,lb)
    return (hi+.05)/(lo+.05)

def is_neutral(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(x*2 for x in h)
    if len(h) < 6: return True
    r,g,b = (int(h[i:i+2],16) for i in (0,2,4))
    return (max(r,g,b) - min(r,g,b)) < 30

def visible_text(t):
    """只保留会被渲染的文案：剥掉 <script>/<style>/注释/标签。保持行号不变。
    ⚠️ 必须剥——JS 的展开运算符 `...c` 和文案里的省略号 `...` 长得一样，
    不剥就会把正确的代码判成排印错误。这类假阳性比漏报更伤。"""
    out = list(t)
    spans = []
    for m in re.finditer(r"<(script|style)\b.*?</\1>", t, re.S | re.I): spans.append(m.span())
    for m in re.finditer(r"<!--.*?-->", t, re.S): spans.append(m.span())
    for m in re.finditer(r"<[^>]*>", t): spans.append(m.span())
    for a, b in spans:
        for i in range(a, b):
            if out[i] != "\n": out[i] = " "
    return "".join(out)

CHECKS = []
# 传了 --tokens 时，字阶比例改由**令牌层**判 —— 见 c_scale 里的说明。
TOKENS_GIVEN = False


def check(cid, sec, desc):
    def deco(fn):
        CHECKS.append({"id":cid,"sec":sec,"desc":desc,"fn":fn}); return fn
    return deco

@check("type-count","1.2","字号总数 <=7")
def c1(css, prof):
    sizes = sorted({float(m) for m in re.findall(r"font-size\s*:\s*([\d.]+)px", css)})
    if not sizes: return None, "未发现字面字号声明（可能全走令牌）"
    return len(sizes) <= 7, "%d 个：%s" % (len(sizes), sizes)

@check("type-ratio","1.2","字号最大/最小比 >=2.0（低于即字阶扁平）")
def c2(css, prof):
    sizes = sorted({float(m) for m in re.findall(r"font-size\s*:\s*([\d.]+)px", css)})
    if len(sizes) < 2: return None, "字面字号不足 2 个"
    r = sizes[-1]/sizes[0]
    return r >= 2.0, "最大 %s / 最小 %s = %.2f" % (sizes[-1], sizes[0], r)

@check("type-min","1.1","字号不低于硬下限 11px")
def c3(css, prof):
    floor = {"web":14,"zh":13,"desktop":13}[prof]
    sizes = [float(m) for m in re.findall(r"font-size\s*:\s*([\d.]+)px", css)]
    if not sizes: return None, "未发现字面字号"
    small = sorted({s for s in sizes if s < floor})
    bad = [s for s in small if s < 11]
    return not bad, "低于 %dpx 的：%s；低于 11px（硬下限）的：%s" % (floor, small or "无", bad or "无")

@check("line-height","1.3","行高按**角色**分档达标（标题可紧，正文要松）")
def c4(css, prof):
    """两个坑，都是拿 fixture 跑出来才发现的：
      ① 首版一刀切要求所有 line-height >= 1.6 —— 把 h1 28px/1.25 误判为不合格。
         标题本来就该比正文紧，必须在**同一规则块内配对 font-size** 再判。
      ② 只看字号仍然分不出角色：20px 既可能是正文也可能是小标题，档位边界必然误判。
         → 改为**先从选择器判角色**（h1-h6 / 名字含 title|heading|display 即标题），
           判不出角色的**单列为「角色不明」，不计入通过也不计入失败**——
           不许猜，也不许当通过。
      推论：**语义命名是这条判据能工作的前提。** 把类名写成 .t / .b，门禁就只能弃权。"""
    HEAD_RE = re.compile(r"(^|[\s,>+~])(h[1-6])\b|title|heading|headline|display|\bhd\b", re.I)
    def band(fs, is_head):
        if is_head:
            if fs >= 48: return (1.1, "大展示字")
            if fs >= 24: return (1.2, "标题")
            return (1.3, "小标题")
        base = 1.5 if fs >= 16 else 1.6
        # ⚠️ 浮点：1.6 + 0.1 == 1.7000000000000002，会把恰好 1.7 的正确实现判红。
        #    门禁的假阳性比漏报更伤——它会让人对告警脱敏。一律 round 到 2 位。
        return (round(base + (0.1 if prof == "zh" else 0), 2), "正文")
    bad, unknown, ok = [], [], 0
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        sel, blk = m.group(1).strip().split("\n")[-1], m.group(2)
        if sel.startswith("@"): continue
        fm = re.search(r"font-size\s*:\s*([\d.]+)px", blk)
        lm = re.search(r"line-height\s*:\s*([\d.]+)\s*[;}]?", blk)
        if fm and lm:
            fs, lh = float(fm.group(1)), float(lm.group(1))
        else:
            # ⭐ `font: 13px/1.5 sans` 简写同样声明了行高。原实现只认 `font-size:`，
            #    在大量用简写的工程里这条规则**一条都验不到**却照报「通过」
            #    —— M8 的第四类失效：覆盖静默缩水。
            sh = re.search(r"(?:^|[;{\s])font\s*:[^;{}]*?([\d.]+)px\s*/\s*([\d.]+)", blk)
            if not sh: continue
            fs, lh = float(sh.group(1)), float(sh.group(2))
        if not (0.8 < lh < 3): continue
        # ⭐ 第三种角色：**定尺寸盒子里居中的字形**（图标 / 徽标 / 序号圆点）。
        #    那里 line-height 不控制文本流，`line-height:1` 正是正确写法。
        #    原实现只有「标题 / 正文」两档，凡不是标题一律按正文要求 >=1.6，
        #    于是把正确的图标实现判红 —— 这与本规则自己写的「不许猜」矛盾。
        boxed = (re.search(r"\bwidth\s*:\s*[\d.]+px", blk)
                 and re.search(r"\bheight\s*:\s*[\d.]+px", blk)
                 and re.search(r"place-items\s*:\s*center|align-items\s*:\s*center", blk))
        # ⭐ 第四种角色：**单行控件标签**（按钮 / 输入框 / 标签页 / 徽标 / 列表行）。
        #    它们只有一行，行高 1~1.4 是正确做法，按正文档要求 >=1.6 会把对的判成错的。
        CTRL_RE = re.compile(r"(^|[\s,>+~.#])(button|input|select|textarea|option|"
                             r"btn|chip|tab|badge|trow|pill|toolbar)\b", re.I)
        if CTRL_RE.search(sel):
            unknown.append("%s（%gpx/%g · 单行控件标签，不按正文行高判）" % (sel[:28], fs, lh))
            continue
        if boxed:
            unknown.append("%s（%gpx/%g · 定尺寸居中字形，行高不参与排版）" % (sel[:28], fs, lh))
            continue
        is_head = bool(HEAD_RE.search(sel))
        # 字号 >=24 时即便选择器无语义也可安全判为标题
        if not is_head and fs >= 24: is_head = True
        if not is_head and 20 <= fs < 24 and not re.search(r"body|\bp\b|text|desc|para", sel, re.I):
            unknown.append("%s（%gpx/%g）" % (sel[:28], fs, lh)); continue
        need, role = band(fs, is_head)
        if round(lh, 3) < need: bad.append("%s %gpx/%g（%s档需 >=%g）" % (sel[:24], fs, lh, role, need))
        else: ok += 1
    if not (ok or bad or unknown):
        return None, "没有规则块同时声明 font-size 与 line-height —— 无法配对判定"
    detail = "达标 %d；不达标：%s" % (ok, bad or "无")
    if unknown:
        detail += "；⚠️ 角色不明（选择器无语义，门禁弃权）：%s" % unknown
    return not bad, detail

@check("font-family","1.5","首选字体族 <=3（2 核心 + 1 mono）")
def c5(css, prof):
    fams = set()
    for m in re.finditer(r"font-family\s*:\s*([^;{}]+)", css):
        first = m.group(1).split(",")[0].strip().strip("\"'").lower()
        if first and not first.startswith("var("): fams.add(first)
    if not fams: return None, "未发现 font-family"
    return len(fams) <= 3, "%d 个：%s" % (len(fams), sorted(fams))

@check("space-scale","2.1","间距值落在 4/8/12/16/24/32/48/64/96/128 阶梯上")
def c6(css, prof):
    # ⚠️ 属性名必须**顶在边界上**：原正则用 `[^:;{}]*` 可以跨过整段 HTML，
    #    于是 `class="gap"` 后面隔着几百字的 `font-size:13px` 被当成间距值报离群。
    # ⚠️ 简写要取**每一个**值：`padding:8px 13px` 只抓第一个的话，
    #    第二个数永远查不到（原实现就是如此）。
    vals = [int(v) for decl in re.findall(r"(?:^|[;{\"'\s])(?:padding|margin|gap|row-gap|column-gap)(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?\s*:\s*([^;{}\"']+)", css)
            for v in re.findall(r"(\d+)px", decl)]
    if not vals: return None, "未发现字面间距值（全走令牌是好事）"
    off = sorted({v for v in vals if v not in SP_SCALE and v > 2})
    return not off, "离群值：%s（共 %d 个唯一值）" % (off or "无", len(set(vals)))

@check("space-variety","2.4","间距唯一值数量合理（既不单调也不无规律）")
def c7(css, prof):
    vals = [int(v) for decl in re.findall(r"(?:^|[;{\"'\s])(?:padding|margin|gap|row-gap|column-gap)(?:-(?:top|right|bottom|left|block|inline)(?:-(?:start|end))?)?\s*:\s*([^;{}\"']+)", css)
            for v in re.findall(r"(\d+)px", decl)]
    u = {v for v in vals if v > 2}
    if len(vals) < 10: return None, "字面间距样本不足（%d 个）" % len(vals)
    if len(u) <= 3: return False, "只有 %d 个唯一值 -> 单调" % len(u)
    if len(u) > 10: return False, "%d 个唯一值且无规律 -> 太乱：%s" % (len(u), sorted(u))
    return True, "%d 个唯一值：%s" % (len(u), sorted(u))

@check("palette-size","3.2","非灰色数 <=12")
def c8(css, prof):
    hexes = {m.lower() for m in re.findall(r"#[0-9A-Fa-f]{6}\b", css)}
    chroma = {h for h in hexes if not is_neutral(h)}
    if not hexes: return None, "未发现字面色值"
    s = sorted(chroma)
    return len(chroma) <= 12, "%d 个非灰色：%s%s" % (len(chroma), s[:8], "…" if len(s) > 8 else "")

@check("no-pure-bw","3.3","页面级不用纯黑纯白")
def c9(css, prof):
    sel = r"(?:^|[},])\s*((?:body|html|:root)(?:[.:#\[][^\s,{>+~]*)*)\s*\{([^}]*)\}"
    bad = []
    for m in re.finditer(sel, css, re.I | re.M):
        for d in re.finditer(r"(background(-color)?|color)\s*:\s*(#000000|#000\b|#ffffff|#fff\b)", m.group(2), re.I):
            bad.append(m.group(1).strip() + ": " + d.group(0))
    return not bad, str(bad or "无")

@check("radius-levels","4","圆角值集合 <=4（要有层级）")
def c10(css, prof):
    vals = sorted({int(m) for m in re.findall(r"border-radius\s*:\s*(\d+)px", css) if int(m) < 500})
    if not vals: return None, "未发现字面圆角（可能全走令牌）"
    return len(vals) <= 4, "%d 个：%s" % (len(vals), vals)

@check("token-bypass","5","令牌绕过率：视觉值应引用令牌而非硬编码")
def c11(css, prof):
    """⭐ 这条查的不是「有没有定义令牌」，而是「**有没有人不用令牌**」。
    真实教训：令牌文件干净（7 阶间距全是 4 的倍数）、来源门禁全绿，
    而 demo 的 CSS 里照样手写 padding:5px 10px / 3px 9px —— 11 个唯一值含 7 个离群。
    **令牌干净 != 使用干净。** 只查令牌本身的门禁看不见这一整类问题。"""
    props = r"(?:padding|margin|gap|row-gap|column-gap|border-radius|font-size|color|background(?:-color)?)"
    lit = tokref = 0
    off = []
    for m in re.finditer(props + r"[^:;{}]*:\s*([^;{}]+)", css):
        val = m.group(1)
        if "var(" in val: tokref += 1
        elif re.search(r"\d+px|#[0-9A-Fa-f]{3,8}|rgba?\(", val):
            lit += 1
            if len(off) < 8: off.append(val.strip()[:34])
    total = lit + tokref
    if total < 10: return None, "视觉声明样本不足（%d 条）" % total
    rate = tokref / total
    return rate >= 0.80, "令牌引用 %d / 硬编码 %d = 引用率 %.0f%%（要求 >=80%%）；硬编码样例：%s" % (
        tokref, lit, rate * 100, off)

@check("body-text-contrast", "3.1", "正文色对其所在背景的对比度 ≥4.5:1（WCAG AA）")
def c12(css, prof):
    """⚠️⚠️ 2026-08-31 重写。原判据是「颜色不得浅于 #525252」，两个问题：

    ① **按错误前提标定**：注释写「#666 在白底上只有 3.8:1，不到 4.5」——
       实测 #666666 对白是 **5.74:1**。而门槛色 #525252 本身要求 **7.81:1**，
       比它援引的 AA 标准（4.5:1）严了近一倍。于是它把合规颜色判成不合规：
       验证项目 的 #6B6B73 实测 5.28:1（对其真实画布 #F8F8FA 是 4.98:1）照样被红。
    ② **不看背景**：`color:#FFFFFF` 用在反色底按钮上是正确做法，它一律判红。

    ⭐ 无障碍硬门的判据是**对比度**，不是「颜色够不够深」——
       用明度代理去近似一个本来就能精确计算的量，只会两头都错。

    现在：逐条 `color:` 声明，取**同一规则块**里的背景（没有就取页面背景，
    再没有就按白底），算真实对比度，低于 4.5:1 才红。
    ⚠️ 诚实边界：看同块背景 → 后代回溯到声明过背景的**祖先选择器** → 页面背景。
       判不了运行时才确定的背景（内联 style / JS 改的 / 多重继承链）。
    """
    AA = 4.5
    page_bg = "#FFFFFF"
    m = re.search(r'(?:^|[},])\s*(?:body|html|:root)[^{}]*\{([^{}]*)\}', css)
    if m:
        b = re.search(r'background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{3,6})', m.group(1))
        if b: page_bg = b.group(1)

    # ⭐ 先把「哪个选择器声明了背景」记下来，供后代块回溯。
    #    ⚠️ 不做这一步就会**假阳性**：`.s-failed .ic{color:…}` 自己没有背景，
    #    背景在父选择器 `.s-failed` 上，落到页面白底就会算出 1.10:1 并报红。
    #    M8：假阳性会让人对门禁脱敏，最后所有告警都被无视。
    sel_bg = {}
    for blk in re.finditer(r'(?:^|[}\n;])\s*([^{}@]+?)\s*\{([^{}]*)\}', css):
        b = re.search(r'background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{3,6})', blk.group(2))
        if not b: continue
        for one in blk.group(1).split(','):
            one = one.strip()
            if one: sel_bg[one] = b.group(1)

    def ancestor_bg(sel):
        """`.a .b .c` → 逐级去掉末段，找最近一个声明过背景的祖先选择器。"""
        for one in sel.split(','):
            parts = one.strip().split()
            while len(parts) > 1:
                parts.pop()
                hit = sel_bg.get(' '.join(parts))
                if hit: return hit
        return None

    bad, checked = [], 0
    for blk in re.finditer(r'(?:^|[}\n;])\s*([^{}@]+?)\s*\{([^{}]*)\}', css):
        sel, body = blk.group(1), blk.group(2)
        own = re.search(r'background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{3,6})', body)
        bg = own.group(1) if own else (ancestor_bg(sel) or page_bg)
        for cm in re.finditer(r'(?<!-)\bcolor\s*:\s*(#[0-9A-Fa-f]{3,6})\b', body):
            fg = cm.group(1)
            r = ratio(fg, bg)
            if r is None:
                continue
            checked += 1
            if r < AA:
                bad.append("%s on %s = %.2f:1（<%.1f）" % (fg, bg, r, AA))
    if not checked:
        return None, "未发现字面文字色（走令牌时由 contrast-tier 判）"
    # ⚠️ 必须回字符串：打印器做 `"       " + why`，回 list 会让本规则
    #    **只要真发现东西就崩溃** —— 于是它至今只「通过」过，从没报出过一次。
    return not bad, "；".join(sorted(set(bad))) or "%d 处正文色全部 ≥%.1f:1" % (checked, AA)

@check("font-weight-gap","1.5","字重相邻档差值 >=200（Weber：差值不足看不出层级）")
def c13(css, prof):
    ws = set()
    for m in re.finditer(r"font-weight\s*:\s*(\d{3})", css):
        ws.add(int(m.group(1)))
    for m in re.finditer(r"font\s*:\s*(\d{3})\s", css):
        ws.add(int(m.group(1)))
    ws = sorted(ws)
    if len(ws) < 2: return None, "字重不足 2 档：%s" % (ws or "未发现")
    gaps = [(ws[i+1]-ws[i], "%d→%d" % (ws[i], ws[i+1])) for i in range(len(ws)-1)]
    bad = [g[1] for g in gaps if g[0] < 200]
    return not bad, "字重 %s；相邻差值不足 200 的：%s" % (ws, bad or "无")

@check("modular-scale","1.2","字阶步进不出现「挤在一起」或「断层」两头")
def c14(css, prof):
    """⚠️ 这条刻意只判两头，不判中间。
    真实设计的字阶可以跳级（12 和 13 可能各有用途），
    拿「相邻比必须等于某个模数」去判会大量误报——
    而门禁的假阳性比漏报更伤，它让人对告警脱敏。
    只判两种明确错的：相邻两档几乎无差别（<1.05，肉眼分不出层级）、
    或断层过大（>2.0，中间缺档）。"""
    sizes = sorted({float(m) for m in re.findall(r"font-size\s*:\s*([\d.]+)px", css)})
    if len(sizes) < 3: return None, "字号不足 3 档，无法判步进"
    tight, gap = [], []
    for i in range(len(sizes)-1):
        r = sizes[i+1]/sizes[i]
        if r < 1.05: tight.append("%g→%g(×%.3f)" % (sizes[i], sizes[i+1], r))
        elif r > 2.0: gap.append("%g→%g(×%.2f)" % (sizes[i], sizes[i+1], r))
    bad = []
    if tight: bad.append("挤在一起、分不出层级：%s" % tight)
    if gap: bad.append("断层、中间缺档：%s" % gap)
    return not bad, "字阶 %s；%s" % (sizes, bad or "两头都正常")

@check("typographic-detail","1.6","排印细节：用 … 不用 ...，标题有 text-wrap:balance")
def c15(css, prof):
    issues = []
    vis = visible_text(css)
    if re.search(r"\.{3}(?![.\w/])", vis):
        sample = re.search(r".{0,20}\.{3}.{0,12}", vis)
        issues.append("可见文案里出现三个点 ...（应为 …）：%s" % (sample.group(0).strip() if sample else ""))
    if re.search(r"<h[1-6]", css) and "text-wrap" not in css:
        issues.append("有标题但没有 text-wrap: balance")
    if re.search(r"tabular-nums", css) is None and re.search(r"<t(able|d)\b", css):
        issues.append("有表格但没有 font-variant-numeric: tabular-nums")
    return not issues, str(issues or "无")

@check("transition-matrix","5.4","过渡时长符合矩阵（颜色/背景/透明度 ~150ms，transform/阴影 ~200ms）")
def c16(css, prof):
    EXP = {"color":150, "background":150, "background-color":150, "opacity":150,
           "transform":200, "box-shadow":200}
    bad = []
    for m in re.finditer(r"transition\s*:\s*([^;{}]+)", css):
        for part in m.group(1).split(","):
            pm = re.match(r"\s*([a-z-]+)\s+([\d.]+)(m?s)", part.strip())
            if not pm: continue
            prop, val, unit = pm.group(1), float(pm.group(2)), pm.group(3)
            ms = val if unit == "ms" else val*1000
            if prop in EXP and abs(ms - EXP[prop]) > 80:
                bad.append("%s %gms（矩阵值 %dms）" % (prop, ms, EXP[prop]))
    bad = sorted(set(bad))
    if not re.search(r"transition\s*:", css): return None, "未发现 transition 声明"
    return not bad, str(bad or "无")


@check("type-scale-ratio","craft 1.2","字阶步进比只用一个模块化比例（混用会让层级说不上哪里怪）")
def c_scale(css, prof):
    """⚠️ 2026-09-01：判的对象错了一半。

    本条说的是「**字阶**是不是单一模块化比例」—— 那是**令牌层**的属性。
    而这里量的是 CSS 里**实际用到**的字号：demo 少用一档（如 bodyStrong），
    相邻比就会跳（实测 验证项目：令牌字阶跨度 0.068 合格，而 demo 跳过 16px 后
    量出 1.538 的假跳档，报「混用了多个比例」）。
    ⭐ **跳档是覆盖问题，混比是比例问题**，混在一个判据里，报出来的话就是错的。
    传了 `--tokens` 就让位给令牌层判据；没传才退回 CSS 视角（聊胜于无）。
    """
    if TOKENS_GIVEN:
        return None, "字阶比例由令牌层判（craft 1.2t）—— CSS 只反映用到的档，跳档会造出假跳比"
    sizes = sorted({float(m) for m in re.findall(r"font-size\s*:\s*([\d.]+)px", css)})
    if len(sizes) < 4: return None, "字面字号不足 4 个，判不出比例"
    ratios = [sizes[i+1]/sizes[i] for i in range(len(sizes)-1) if sizes[i] > 0]
    ratios = [r for r in ratios if 1.02 < r < 2.2]
    if len(ratios) < 3: return None, "相邻字号比例样本不足"
    lo, hi = min(ratios), max(ratios)
    return (hi - lo) <= 0.18, "步进比 %.3f–%.3f（跨度 %.3f，>0.18 即混用了多个比例）" % (lo, hi, hi - lo)

@check("typographic-craft","craft 2","长文排印工艺（悬挂标点/字偶距/孤行寡行/pretty 折行）")
def c_craft(css, prof):
    # 前置条件：有长文才谈得上这些。没有就是 N/A，不是 PASS。
    if not re.search(r"max-width\s*:\s*\d+(ch|em|rem)", css) and "line-height" not in css:
        return None, "没有长文排版迹象，本条不适用"
    want = {"hanging-punctuation": "悬挂标点（引号挂到文本块外，左边缘才是齐的）",
            "font-kerning": "字偶距",
            "text-wrap": "折行控制（标题 balance / 正文 pretty）",
            "orphans": "孤行寡行控制"}
    miss = [v for k, v in want.items() if k not in css]
    return (len(miss) <= 2), ("缺 %d 项：%s" % (len(miss), " · ".join(miss)) if miss else "四项齐备")

@check("nested-radius","4","嵌套圆角：内圆角应 = 外圆角 - 间隙")
def c17(css, prof):
    """只能给出「值得人看一眼」的提示，无法完全自动判定嵌套关系。
    因此命中时报 N/A 级提示而不是 FAIL —— 不许把猜测写成判定。"""
    radii = sorted({int(m) for m in re.findall(r"border-radius\s*:\s*(\d+)px", css) if int(m) < 500})
    if len(radii) < 2: return None, "圆角不足 2 档，无法判嵌套关系"
    return None, "圆角档位 %s —— 嵌套关系需人工核（内=外-间隙），门禁无法确定哪两个是嵌套的" % radii

def token_checks(tok):
    out = []
    # ── craft 1.2t：字阶比例（判**定义的字阶**，不判 CSS 用到了哪几档）──
    ty = tok.get("type", {})
    sz = sorted({v.get("value") if isinstance(v, dict) else v
                 for k, v in ty.items() if not k.startswith("_")
                 and isinstance((v.get("value") if isinstance(v, dict) else v), (int, float))})
    if len(sz) >= 4:
        rs = [sz[i + 1] / sz[i] for i in range(len(sz) - 1) if sz[i] > 0]
        rs = [r for r in rs if 1.02 < r < 2.2]
        if len(rs) >= 3:
            lo, hi = min(rs), max(rs)
            out.append(("type-scale-ratio-token", "craft 1.2t",
                        "令牌字阶只用一个模块化比例", (hi - lo) <= 0.18,
                        "步进比 %.3f–%.3f（跨度 %.3f，>0.18 即混用）" % (lo, hi, hi - lo)))
    prim = tok.get("primitive", {}); sem = tok.get("semantic", {})
    def resolve(v):
        if isinstance(v, str) and v.startswith("{"):
            n = prim
            for k in v.strip("{}").replace("primitive.", "").split("."):
                n = n.get(k, {}) if isinstance(n, dict) else {}
            return n.get("value") if isinstance(n, dict) else None
        return v
    bg = {m: resolve(sem.get("bg/canvas", {}).get(m)) for m in ("Light", "Dark")}
    pairs = [("text/primary",4.5),("text/secondary",4.5),("text/tertiary",4.5),
             ("signal/grow",4.5),("border/interactive",3.0),("border/focus",3.0)]
    bad = []
    for name, need in pairs:
        if name not in sem: continue
        for mode in ("Light", "Dark"):
            fg = resolve(sem[name].get(mode)); b = bg.get(mode)
            if not fg or not b: continue
            r = ratio(fg, b)
            if r and r < need: bad.append("%s@%s=%.2f(需%s)" % (name, mode, r, need))
    out.append(("contrast-tier","3.1","对比度分级：正文 >=4.5:1，承载信息的边框 >=3:1",
                not bad, str(bad or "全部达标")))
    ty = tok.get("type", {})
    sizes = sorted(v.get("value") for v in ty.values()
                   if isinstance(v, dict) and isinstance(v.get("value"), (int, float)))
    if len(sizes) >= 2:
        out.append(("token-type-ratio","1.2","令牌字阶最大/最小比 >=2.0",
                    sizes[-1]/sizes[0] >= 2.0, "%s/%s=%.2f" % (sizes[-1], sizes[0], sizes[-1]/sizes[0])))
    sp = sorted(v.get("value") for v in tok.get("space", {}).values() if isinstance(v, dict))
    if sp:
        off = [v for v in sp if v % 4 != 0]
        out.append(("token-space","2.1","令牌间距全为 4 的倍数", not off, "%s，离群 %s" % (sp, off or "无")))
    rd = sorted(v.get("value") for v in tok.get("radius", {}).values()
                if isinstance(v, dict) and isinstance(v.get("value"), (int, float)) and v.get("value") < 500)
    if rd:
        out.append(("token-radius","4","令牌圆角有层级（3-6 档）", 3 <= len(rd) <= 6, str(rd)))
    return out


DARK_SEL = re.compile(r'(?:\[data-theme\s*=\s*"?dark"?\]|prefers-color-scheme\s*:\s*dark)')


def _strip_dark_scopes(css):
    """删掉深色作用域的整块（含 @media 的嵌套花括号），只留浅色定义。

    逐字符配对花括号，不能用正则 —— `@media(...){ :root{...} }` 是嵌套的，
    非贪婪正则会在第一个 `}` 就断开，把 `:root{...}` 的一半留下来。
    """
    out, i, n = [], 0, len(css)
    while i < n:
        m = DARK_SEL.search(css, i)
        if not m:
            out.append(css[i:]); break
        # 回退到这条规则/at-rule 的起点
        start = css.rfind('}', i, m.start()) + 1
        if start <= 0:
            start = i
        brace = css.find('{', m.end())
        if brace < 0:
            out.append(css[i:]); break
        depth, j = 1, brace + 1
        while j < n and depth:
            if css[j] == '{': depth += 1
            elif css[j] == '}': depth -= 1
            j += 1
        out.append(css[i:start])
        i = j
    return ''.join(out)


def resolve_vars(css, rounds=5):
    """把 `var(--x)` 展开成它的字面值再判。

    ⚠️⚠️ **这是本门禁最严重的一个盲区，2026-08-31 自证时才发现。**
    所有数值判据都读字面量（`font-size:\s*([\d.]+)px`）。
    而本 SOP 恰恰要求项目把一切令牌化 —— 于是 CSS 里全是 `var(--fs-4)`，
    门禁一个值都读不到，**全部判 PASS**。
    也就是说：**项目越是照 SOP 做对，这道门就越瞎**，而它还报绿。
    典型的「覆盖静默缩水」——报绿不是因为好，是因为它看不见。

    修法：先从 `:root` 之类的声明里收集 `--name: value`，
    再把 `var(--name[, fallback])` 就地展开（迭代若干轮，因为令牌可以引用令牌）。
    ⚠️ 展开只用于**数值判据**；`token-bypass` 必须看**原始 CSS**，
    否则它会以为所有值都是硬编码的 —— 那是反过来的假阳性。
    """
    # ⚠️⚠️ 第二个盲区（2026-08-31 拿真项目实跑才发现，与上面那个方向相反）：
    #    原来 `dict(findall(...))` 把**全文**的 `--x: v` 收成一张平表，而 `dict` 保留**最后一个**。
    #    带深色模式的项目里 `[data-theme="dark"]` / `@media(prefers-color-scheme:dark)`
    #    排在 `:root` 之后 → 每个令牌都被解析成**深色值**，
    #    于是 3.1「白底正文不得浅于 #525252」拿深色模式的文字色去判白底 → 必然假阳性。
    #    ⭐ 上一个盲区是「项目越照 SOP 令牌化，它越瞎」；这个是
    #      「项目越正确实现深色模式，它误报越多」—— 同一个函数，两个反向的坑。
    #    修法：建表时只收**非深色作用域**的定义（浅色是判据的默认前提）。
    #    ⚠️ 诚实边界：因此本门禁**不判深色模式**下的取值，那需要按主题各判一遍。
    defs = dict(re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', _strip_dark_scopes(css)))
    out = css
    for _ in range(rounds):
        new = re.sub(r'var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*?))?\)',
                     lambda m: (defs.get(m.group(1)) or m.group(2) or m.group(0)).strip(), out)
        if new == out: break
        out = new
    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("target", nargs="?")
    p.add_argument("--tokens")
    p.add_argument("--profile", default="web", choices=["web","zh","desktop"])
    p.add_argument("--json", action="store_true")
    a = p.parse_args()
    if not a.target: die("缺少扫描目标")
    if not os.path.exists(a.target): die("目标不存在：" + a.target)
    if os.path.isfile(a.target):
        files = [a.target]
    else:
        files = [os.path.join(r,f) for r,_,fs in os.walk(a.target) for f in fs
                 if f.endswith((".html",".css")) and "node_modules" not in r]
    if not files: die("没有可扫描的 html/css")
    global TOKENS_GIVEN
    TOKENS_GIVEN = bool(a.tokens)
    css_raw = "\n".join(open(f, encoding="utf8", errors="replace").read() for f in files)
    css = resolve_vars(css_raw)

    rows = []
    for c in CHECKS:
        # token-bypass 查的是「有没有人不用令牌」，必须看原始 CSS；其余判据看展开后的值
        r = c["fn"](css_raw if c["id"] == "token-bypass" else css, a.profile)
        if r is None or r[0] is None:
            rows.append((c["id"], c["sec"], c["desc"], "N/A", r[1] if r else "前置条件不成立"))
        else:
            rows.append((c["id"], c["sec"], c["desc"], "PASS" if r[0] else "FAIL", r[1]))
    if a.tokens:
        if not os.path.isfile(a.tokens): die("tokens 文件不存在：" + a.tokens)
        try:
            tok = json.load(open(a.tokens, encoding="utf8"))
        except Exception as e:
            die("tokens 不是合法 JSON：%s" % e)
        for cid, sec, desc, ok, why in token_checks(tok):
            rows.append((cid, sec, desc, "PASS" if ok else "FAIL", why))

    npass = sum(1 for r in rows if r[3] == "PASS")
    nfail = sum(1 for r in rows if r[3] == "FAIL")
    nna   = sum(1 for r in rows if r[3] == "N/A")
    if a.json:
        print(json.dumps({"rows":[{"id":r[0],"sec":r[1],"desc":r[2],"result":r[3],"detail":r[4]} for r in rows],
                          "pass":npass,"fail":nfail,"na":nna}, ensure_ascii=False, indent=2))
    else:
        print("扫描 %d 个文件　档位=%s\n" % (len(files), a.profile))
        icons = {"PASS":"✅","FAIL":"❌","N/A":"➖"}
        for cid, sec, desc, res, why in rows:
            print("  %s [%s] %s" % (icons[res], sec, desc))
            # 兜底：某条规则回了非字符串也不许让整个门禁崩掉
            print("       " + (why if isinstance(why, str) else "；".join(map(str, why))))
        print("\n通过 %d · 失败 %d · 不适用 %d" % (npass, nfail, nna))
        if npass + nfail:
            print("通过率分母只算「通过+失败」= %d/%d" % (npass, npass + nfail))
        print("\n⚠️ 本门禁只覆盖 visual-spec 第一至五节。")
        print("   第六节（质感·景深·光影）不可自动验，必须人工按 6.1-6.10 走查，")
        print("   报告写「已走查，发现 N 处」，不许写「质感 ✅」。")
    sys.exit(0 if nfail == 0 else 1)



# ------------------------------------------------------------------ M8 自证
_GOOD = """<!doctype html><html><head><style>
:root{--fg:#171717;--bg:#fafafa;--sp-2:8px;--sp-4:16px;--sp-6:32px;
      --fs-1:32px;--fs-2:24px;--fs-3:20px;--fs-4:16px;--fs-5:13px;
      --r-sm:8px;--r-md:12px}
body{background:var(--bg);color:var(--fg);font-family:Charter,Georgia,serif;
     font-size:var(--fs-4);line-height:1.7;font-kerning:normal;
     hanging-punctuation:first last;orphans:2;widows:2;text-wrap:pretty}
main{max-width:65ch;margin:0 auto;padding:var(--sp-6)}
h1{font-size:var(--fs-1);line-height:1.25;text-wrap:balance;margin:0 0 var(--sp-4)}
h2{font-size:var(--fs-2);line-height:1.3}
h3{font-size:var(--fs-3);line-height:1.4}
p{font-size:var(--fs-4);margin:0 0 var(--sp-4)}
small{font-size:var(--fs-5)}
.b{border-radius:var(--r-sm);transition:color 150ms ease-in-out;padding:var(--sp-2) var(--sp-4)}
.card{border-radius:var(--r-md);padding:var(--sp-4)}
</style></head><body><main><h1>标题</h1><p>正文用弯引号“像这样”，省略号用…</p></main></body></html>"""

_DARKMODE = """<!doctype html><html><head><style>
:root{--fg:#171717;--bg:#fafafa}
:root[data-theme="dark"]{--fg:#FBFBFD;--bg:#141418}
@media (prefers-color-scheme: dark){:root{--fg:#B4B4BC}}
body{background:var(--bg);color:var(--fg)}
</style></head><body><p>正文</p></body></html>"""


_CONTRAST_CASES = [
    ("正例 深灰正文 #171717 on #fafafa", "body{background:#fafafa;color:#171717}", False),
    ("反例 #999999 on 白底（3.0:1，不到 AA）", "body{background:#fff;color:#999999}", True),
    ("防假阳 反色底上的白字（旧判据一律判红）", "body{background:#fff}.btn{background:#222222;color:#FFFFFF}", False),
    ("防假阳 #6B6B73 on 白底（5.28:1 合规，旧判据因 <#525252 判红）",
     "body{background:#FFFFFF;color:#6B6B73}", False),
]


def _contrast_cases():
    """3.1 重写后的正反例。旧判据在后两条上都会误报 —— 那正是它被重写的理由。"""
    bad = 0
    for name, css, want_fail in _CONTRAST_CASES:
        fn = next(c["fn"] for c in CHECKS if c["id"] == "body-text-contrast")
        ok, ev = fn(resolve_vars(css), "web")
        got_fail = (ok is False)
        good = (got_fail == want_fail)
        print(("  ✅ " if good else "  ❌ ") + name + ("" if good else "　期望红=%s 实得=%s %s" % (want_fail, got_fail, ev)))
        bad += 0 if good else 1
    return 1 if bad else 0



# ⭐ 2026-09-01：插桩实测 19 条判据只有 6 条在自证里红过 ——
# **从没被反向测过的判据，和不存在的判据效果没区别**。以下逐条造反例。
# ⚠️ `nested-radius` 刻意不在此列：它命中时返回 N/A 提示而**从不 FAIL**（设计如此，
#    不许把猜测写成判定），所以它没有「红」这个状态可测，不是覆盖缺口。
_NEG_CASES = [
    # ⚠️ 锚点写错过一次：`--fs-5:13px}` 在原文里不存在（右花括号在 --r-md:12px 之后），
    #    replace 静默空转 → 夹具等于正例 → 期望红实得绿。**空转的 replace 会被这个构造自动抓住。**
    ("type-count 字号超 7 档",
     _GOOD.replace("--r-sm:8px;--r-md:12px}", "--r-sm:8px;--r-md:12px;--fs-6:11px;--fs-7:10px;--fs-8:9px}")
          .replace("small{font-size:var(--fs-5)}",
                   "small{font-size:var(--fs-5)}\n.a{font-size:var(--fs-6)}\n.b2{font-size:var(--fs-7)}\n.c2{font-size:var(--fs-8)}")),
    ("type-ratio 字阶扁平（最大/最小 < 2.0）",
     _GOOD.replace("--fs-1:32px", "--fs-1:18px").replace("--fs-2:24px", "--fs-2:17px")),
    ("line-height 正文行高过紧",
     _GOOD.replace("line-height:1.7", "line-height:1.1")),
    ("font-family 首选字体族超 3",
     _GOOD.replace("font-family:Charter,Georgia,serif;",
                   "font-family:Charter,serif;}\n.f2{font-family:Inter,sans-serif}\n.f3{font-family:Menlo,monospace}\n.f4{font-family:Georgia,serif}\n.f5{font-family:Verdana,sans-serif;")),
    ("space-scale 间距不在阶梯上",
     _GOOD.replace("--sp-2:8px", "--sp-2:7px").replace("--sp-4:16px", "--sp-4:19px")),
    ("space-variety 间距只有一个值（单调）",
     _GOOD.replace("--sp-2:8px;--sp-4:16px;--sp-6:32px", "--sp-2:8px;--sp-4:8px;--sp-6:8px")
          + "<style>.x1{padding:8px}.x2{margin:8px}.x3{gap:8px}.x4{padding:8px}.x5{margin:8px}"
            ".x6{gap:8px}.x7{padding:8px}.x8{margin:8px}.x9{gap:8px}.xa{padding:8px}</style>"),
    ("palette-size 非灰色超 12",
     _GOOD.replace("</style>", "".join(".p%d{color:#%02x33aa}" % (i, i * 17) for i in range(14)) + "</style>")),
    ("radius-levels 圆角档位超 4",
     _GOOD.replace("--r-md:12px}", "--r-md:12px;--r-a:2px;--r-b:5px;--r-c:17px;--r-d:23px}")
          .replace(".card{border-radius:var(--r-md)",
                   ".ra{border-radius:var(--r-a)}.rb{border-radius:var(--r-b)}"
                   ".rc{border-radius:var(--r-c)}.rd{border-radius:var(--r-d)}\n.card{border-radius:var(--r-md)")),
    ("font-weight-gap 相邻字重差不足 200",
     _GOOD.replace("</style>", ".w1{font-weight:400}.w2{font-weight:500}</style>")),
    ("modular-scale 相邻两档几乎无差别",
     _GOOD.replace("--fs-3:20px", "--fs-3:23.5px")),
    ("transition-matrix 颜色过渡时长离谱",
     _GOOD.replace("transition:color 150ms", "transition:color 900ms")),
    ("typographic-detail 可见文案用三个点而非 …",
     _GOOD.replace("省略号用…", "省略号用...")),
    ("typographic-craft 缺长文排印工艺",
     _GOOD.replace("font-kerning:normal;\n     hanging-punctuation:first last;orphans:2;widows:2;text-wrap:pretty", "")),
]


def _neg_cases():
    """每条反例必须**恰好**让它针对的那条判据红（不看退出码，看是哪条红）。"""
    ok = True
    for cid_desc, css_raw in _NEG_CASES:
        cid = cid_desc.split()[0]
        css = resolve_vars(css_raw)
        fn = next((c["fn"] for c in CHECKS if c["id"] == cid), None)
        if fn is None:
            print("  ❌ 找不到判据 " + cid); ok = False; continue
        try:
            got, why = fn(css, "web")
        except Exception as e:
            print("  ❌ %s 调用出错：%s" % (cid_desc, e)); ok = False; continue
        good = (got is False)
        print(("  ✅ " if good else "  ❌ ") + cid_desc + ("" if good else "　期望红，实得 %r（%s）" % (got, why)))
        ok = ok and good
    return 0 if ok else 1

def _token_scale_cases():
    """craft 1.2t 的正反例。⚠️ 必须验它**会红** —— 只有正例的判据永远绿。"""
    good = {"type": {"caption": {"value": 11}, "body": {"value": 13},
                     "bodyStrong": {"value": 16}, "title": {"value": 20}, "display": {"value": 25}}}
    bad = {"type": {"caption": {"value": 11}, "label": {"value": 12}, "body": {"value": 13},
                    "bodyStrong": {"value": 15}, "title": {"value": 20}, "display": {"value": 28}}}
    def verdict(tok):
        for cid, sec, desc, ok, why in token_checks(tok):
            if cid == "type-scale-ratio-token":
                return ok
        return None
    # ⚠️⚠️ 2026-09-05 `unexecuted-check` 实测：令牌夹具**只有 `type`** ⇒
    #    `token-space`（间距是否 4 的倍数）与 `token-radius`（圆角是否 3-6 档）
    #    这两条判据**一次都没被评估过**。变异扫描看不出来 —— 它们从没执行，
    #    置真与否毫无差别。⭐ 「被前提挡住的断言」与「跑了且通过的断言」输出一样。
    def one(tok, cid):
        for c, sec, desc, ok, why in token_checks(tok):
            if c == cid: return ok
        return None
    SP_OK = {"space": {"a": {"value": 4}, "b": {"value": 8}, "c": {"value": 16}}}
    SP_BAD = {"space": {"a": {"value": 4}, "b": {"value": 6}, "c": {"value": 16}}}
    RD_OK = {"radius": {"s": {"value": 4}, "m": {"value": 8}, "l": {"value": 12}}}
    RD_BAD = {"radius": {"a": {"value": 2}, "b": {"value": 4}, "c": {"value": 6},
                         "d": {"value": 8}, "e": {"value": 10}, "f": {"value": 12},
                         "g": {"value": 16}}}
    cases = [("craft1.2t 正例 单一比例 11/13/16/20/25", verdict(good) is True),
             ("craft1.2t 反例 混比 11/12/13/15/20/28（三档挤在 2px 内）", verdict(bad) is False),
             ("token-space 正例 4/8/16 全是 4 的倍数", one(SP_OK, "token-space") is True),
             ("token-space 反例 混入 6（不是 4 的倍数）", one(SP_BAD, "token-space") is False),
             ("token-radius 正例 3 档（4/8/12）", one(RD_OK, "token-radius") is True),
             ("token-radius 反例 7 档（层级过多）", one(RD_BAD, "token-radius") is False)]
    bad_n = 0
    for name, ok in cases:
        print(("  ✅ " if ok else "  ❌ ") + name)
        bad_n += 0 if ok else 1
    return 1 if bad_n else 0


def _dark_scope_case():
    """反向用例：浅色 #171717 合规、深色 #FBFBFD/#B4B4BC 只在深色底上用。
    修复前 `dict()` 让深色值覆盖浅色，3.1 会把 #FBFBFD 当「白底正文」报红。"""
    import tempfile
    d = tempfile.mkdtemp(); f = os.path.join(d, 'x.html')
    open(f, 'w', encoding='utf8').write(_DARKMODE)
    css = resolve_vars(open(f, encoding='utf8').read())
    # ⚠️ 断言必须看**展开后的声明**，不能看「文件里有没有这个串」——
    #    深色定义那几行本来就还在文本里，第一版断言 `'#FBFBFD' not in css` 因此必然失败。
    #    第三次犯同一个错：判据的量程要对准被判的东西。
    decl = re.findall(r'(?<!-)\bcolor\s*:\s*(#[0-9A-Fa-f]{3,6})', css)
    ok = ('#171717' in decl) and ('#FBFBFD' not in decl) and ('#B4B4BC' not in decl)
    print(("  ✅ " if ok else "  ❌ ") + "深色作用域的令牌不得覆盖浅色定义（3.1 判的是白底）")
    return 0 if ok else 1


def _self_test():
    """M8 自证。⚠️ 2026-08-31 补 —— 此前文档声称「全部门禁均自带 --self-test」而本脚本没有。"""
    import os, sys, tempfile, subprocess, io as _io
    t = tempfile.mkdtemp(prefix="vsg-")
    me = os.path.abspath(__file__)
    def w(n, c):
        p = os.path.join(t, n); _io.open(p, "w", encoding="utf-8").write(c); return p
    def run(p):
        return subprocess.call([sys.executable, me, p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases = [
        ("正例", _GOOD, 0),
        ("反例 字号过小", _GOOD.replace("--fs-5:13px", "--fs-5:9px"), 1),
        ("反例 白底正文过浅", _GOOD.replace("--fg:#171717", "--fg:#999999"), 1),
        ("反例 页面级纯白", _GOOD.replace("--bg:#fafafa", "--bg:#ffffff"), 1),
                # ⚠️ 反例要造在**使用处**，不是只加令牌定义 —— 没被用到的令牌不构成圆角层级，
        #    门禁不算它是对的。首版这条变异因此成了 no-op。
        ("反例 圆角层级过多", _GOOD.replace(".card{border-radius:var(--r-md);padding:var(--sp-4)}",
            ".card{border-radius:var(--r-md);padding:var(--sp-4)}"
            ".a{border-radius:3px}.c{border-radius:17px}.d{border-radius:21px}.e{border-radius:29px}"), 1),
        ("反例 三点省略号", _GOOD.replace("用…", "用..."), 1),
        # ⚠️⚠️ 2026-09-05 变异扫描实测：typographic-detail 里的**后两条判据从没有反例**
        #    —— 把它们整条删掉，自证照样全绿。以下补上，并且各自隔离：
        #    · text-wrap：craft 判据容忍缺 ≤2 项，所以**只**去掉 text-wrap 时 craft 仍绿，
        #      红的只会是这一条（否则就是被 craft 兜住，反例守的是另一条规则）。
        #    · tabular-nums：原夹具**根本没有 <table>**，这条判据连正例都从没走到过。
        ("反例 有标题却没有 text-wrap（craft 只缺 1 项仍绿，红的必须是这一条）",
         _GOOD.replace("text-wrap:balance;", "").replace("text-wrap:pretty", ""), 1),
        ("反例 有表格却没有 tabular-nums",
         _GOOD.replace("<p>正文", "<table><td>1234</td></table><p>正文"), 1),
        ("正例 表格带了 tabular-nums → 不许误伤",
         _GOOD.replace("<p>正文", "<table style=\"font-variant-numeric:tabular-nums\"><td>1234</td></table><p>正文"), 0),
        ("反例 混用多个字阶比例", _GOOD.replace("--fs-2:24px", "--fs-2:29px")
                                    .replace("--fs-3:20px", "--fs-3:20.5px"), 1),
        ("反例 排印工艺缺项", _GOOD.replace("font-kerning:normal;", "")
                                .replace("hanging-punctuation:first last;", "")
                                .replace("orphans:2;widows:2;", ""), 1),
    ]
    ok = True
    print("M8 自证 —— 正例绿 / 每类反例红 / 无效输入报错不返绿\n")
    for n, body, want in cases:
        rc = run(w(n.replace(" ", "_") + ".html", body))
        g = rc == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, rc))
    rc = run(os.path.join(t, "nope.html"))
    g = rc == 2; ok &= g
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g else "❌", "输入不存在", rc))
    # 🆕 2026-09-05 `--unable` 实测：`--tokens` 的两个「跑不了」出口从没被触发过。
    #    ⭐ 这类前提守卫锚点写错时**两头都不出声**：既不报「没跑过」也不报缺陷。
    import subprocess as _sp
    _good = w("tok_good.html", _GOOD)
    for _n, _tokarg, _want in [
        ("--tokens 文件不存在 → 报 2", os.path.join(t, "no_such_tokens.json"), 2),
        ("--tokens 不是合法 JSON → 报 2", w("bad_tokens.json", "{ not json"), 2),
    ]:
        _rc = _sp.call([sys.executable, me, _good, "--tokens", _tokarg],
                       stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        _g = _rc == _want; ok &= _g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if _g else "❌", _n, _want, _rc))
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
        if "--self-test" in sys.argv: sys.exit(_self_test() or _dark_scope_case() or _contrast_cases() or _token_scale_cases() or _neg_cases())
        main()
    _main_guarded(_entry)
