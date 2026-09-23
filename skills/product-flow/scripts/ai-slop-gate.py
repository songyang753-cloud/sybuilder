#!/usr/bin/env python3
"""
反 AI-slop 机械门禁 —— 只查「不需要判断力就能判定」的那一层。

定位（重要）：
  反 slop 分三层，这只是第一层。
    第 1 层 门禁（本脚本）：可正则/结构判定的，硬失败
    第 2 层 评审视角：需要判断力的，出字母分（S5.3 第 10 视角）
    第 3 层 生成期约束：Design Read / memorable-thing / SAFE-RISK 提案（最根本）
  **只跑第 1 层不算做了反 slop。** 本脚本报绿只意味着「没有机械可查的破绽」。

判据来源（均带出处，见 research/）：
  taste §9 AI Tells / §4.1 SERIF 纪律 / §4.2 调色板禁令
  design-review 第 9 类 AI Slop 11 条 + 通用铁律
  impeccable OVERUSED_FONTS + AI 配色色相区间
  design-consultation 字体过度使用名单 + 自羞耻门触发词

用法：ai-slop-gate.py <file.html|dir> [--profile web|zh|desktop] [--json] [--list-rules]
退出码：0=干净  1=有发现  2=跑不了
"""
import argparse, json, os, re, sys, colorsys

def die_unable(m):
    print(f"UNABLE: {m}", file=sys.stderr); sys.exit(2)

# —— 字体黑名单：impeccable 15 + taste 2 + design-consultation 9，去重 ——
# ---------------------------------------------------------------- 规则分层（A/B/C/D）
# ⚠️⚠️ 2026-08-31：分层此前**只写在 design-rulesets.md 里，门禁没读**——
#    于是「合理使用 system-ui 的内部工具」「既有品牌用 Inter 的产品」被判成「不合格」。
#    ⭐ **说明层分了层、执行层没分层，等于没分层。**
# A=无障碍/安全硬门(FAIL) · B=产品类型默认值(WARN，可用 DESIGN.md 覆盖)
# C=品牌与设计方向(只对照项目自己的声明) · D=评审启发式(不进门禁)
# ⛔ 2026-09-07（Codex 外审 P0-5）：此前只有 3 条显式 C、其余**默认 A 硬门** ——
#   「紫色渐变」这类品牌方向被当成无障碍级硬失败。现在**每条规则显式定层**，
#   没登记的规则直接拒跑（响亮地坏，不许静默变成硬门）。
#   A=可机械证明的安全/无障碍/功能破坏（当前 16 条里没有一条够格）
#   B=产品类型惯例与高概率质量风险（WARN，可带理由豁免）
#   C=品牌与设计方向（对照项目 DESIGN.md 声明；未声明只报 INFO 绝不 FAIL）
#   D=审美启发式（只生成人工评审问题，不进退出码）
TIER = {
    "em-dash":            "B",   # 中文排版字符规范
    "blocked-font":       "C",   # 无品牌内部工具用 system-ui 是正确选择
    "purple-gradient":    "C",   # 品牌可以批准紫色 —— 方向问题不是质量问题
    "side-tab":           "D",   # 单边色条是否廉价要看整体语境
    "transition-all":     "B",   # 高概率工艺问题；真造成可测缺陷由具体 A 规则报
    "animate-layout":     "B",   # 同上（layout 重算是性能风险不是必然缺陷）
    "fake-data":          "B",   # 占位内容；交付声明为 production 且未标注时应升 A（挂 manifest 后启用）
    "filler-verb":        "B",
    "scroll-hint":        "D",
    "version-badge":      "D",
    "numbered-eyebrow":   "D",
    "ellipsis":           "B",   # 字符规范
    "pure-black-white":   "C",   # 纯黑底是很多开发者工具/终端的正确选择
    "beige-default":      "C",   # 米色只是一种风格默认
    "three-col-icon-grid":"D",   # 规则自己都写着「需人工确认」
    "emoji-as-ui":        "C",   # 项目可以声明轻松/表情化的方向
}


def tier_of(rid):
    if rid not in TIER:
        # 响亮地坏：新规则没定层就拒跑，不许静默吃默认值变成硬门
        die_unable("规则 %s 没有在 TIER 里显式定层（A/B/C/D）—— 先定层再上线" % rid)
    return TIER[rid]


def load_design_decl(path):
    """读项目自己的设计声明（DESIGN.md / design-brief.md），用于 C 层比对。

    没有声明文件时，C 层规则只报 INFO —— ⛔ **绝不 FAIL**：
    ⭐ 一条规则如果换个产品类型就该被推翻，它就不是硬门（铁律 49）。
    """
    for c in (path, os.path.join(os.path.dirname(path or "."), "DESIGN.md"),
              ".product-flow/design-brief.md", "DESIGN.md"):
        if c and os.path.isfile(c):
            try: return open(c, encoding="utf8", errors="replace").read()
            except Exception: pass
    return None


BLOCKED_FONTS = [
    "inter","roboto","open sans","lato","montserrat","arial","helvetica","poppins",
    "fraunces","instrument sans","instrument serif","geist","geist sans","geist mono",
    "mona sans","plus jakarta sans","space grotesk","recoleta","outfit","newsreader",
    "raleway","clash display","papyrus","comic sans","lobster","impact","jokerman",
]
# taste §4.2：高端消费品调色板禁令（作默认时禁用）
BEIGE_BG   = ["#f5f1ea","#f7f5f1","#fbf8f1","#efeae0","#ece6db","#faf7f1","#e8dfcb"]
BEIGE_ACC  = ["#b08947","#b6553a","#9a2436","#9c6e2a","#bc7c3a","#7d5621"]
BEIGE_TEXT = ["#1a1714","#1a1814","#1b1814"]

def hex_hue(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c*2 for c in h)
    if len(h) < 6: return None, None
    r,g,b = (int(h[i:i+2],16)/255 for i in (0,2,4))
    hh,l,s = colorsys.rgb_to_hls(r,g,b)
    return hh*360, s

COMMENT_PATS = [
    (re.compile(r'<!--.*?-->', re.S), "html"),
    (re.compile(r'/\*.*?\*/', re.S), "block"),
]
def strip_comments(t):
    """把注释替换成等长空白，保持行号不变。注释里的内容不渲染，不该判 slop。"""
    for pat,_ in COMMENT_PATS:
        t = pat.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), t)
    return t

def visible_text(t):
    """只保留会被渲染的文本：标签之间的内容 + CSS content 属性。同样保持行号。"""
    t = strip_comments(t)
    out = list(t)
    depth_ranges = []
    for m in re.finditer(r'<(script|style)\b.*?</\1>', t, re.S | re.I):
        depth_ranges.append((m.start(), m.end()))
    for m in re.finditer(r'<[^>]*>', t):
        depth_ranges.append((m.start(), m.end()))
    for a, b in depth_ranges:
        for i in range(a, b):
            if out[i] != '\n': out[i] = ' '
    return ''.join(out)

RULES = []
def rule(rid, desc, profiles=("web","zh","desktop")):
    def deco(fn):
        RULES.append({"id":rid,"desc":desc,"fn":fn,"profiles":profiles}); return fn
    return deco

def hits(pat, text, flags=0, label=None, limit=6):
    """⚠️ 2026-09-04：此前第 6 个匹配就 break，而输出印的是 `len(xs) 处` ——
    于是**一个有 50 处破折号的文件报「6 处」**。判定（FAIL）是对的，
    **数字是错的**，而照着「6 处」去修的人会修完 6 个就以为修完了。
    ⛔ 这是「静默截断」那一族：截断本身合理（证据不必全列），
      **但被截断的事实必须说出来**。
    ⇒ 只截断证据列表，计数照实；超出部分在第一条证据里标明。
    """
    out, total = [], 0
    for m in re.finditer(pat, text, flags):
        total += 1
        if len(out) < limit:
            line = text[:m.start()].count("\n")+1
            out.append({"line":line,"snippet":(label or m.group(0))[:90]})
    if out and total > limit:
        out[0] = dict(out[0], snippet=out[0]["snippet"] +
                      "　（共 %d 处，此处只列前 %d 条）" % (total, limit))
    for h in out:
        h["total"] = total
    return out

@rule("em-dash","破折号 — / – 出现在可见文案里（taste §9.G：出现一个即失败）")
def r_dash(t,_): return hits(r'[—–]', visible_text(t))

@rule("blocked-font","禁用/过度使用字体作 font-family")
def r_font(t,_):
    out=[]
    for m in re.finditer(r'font-family\s*:\s*([^;{}\n]+)', t, re.I):
        decl = m.group(1).lower()
        first = decl.split(",")[0].strip().strip('"\'')
        for f in BLOCKED_FONTS:
            if first == f or first.startswith(f+" "):
                out.append({"line":t[:m.start()].count("\n")+1,"snippet":f"首选字体 = {first}"}); break
        if re.match(r'^(system-ui|-apple-system)', first):
            # ⛔ 这是 C 层（品牌方向），不是硬门：
            #    **无品牌的内部工具用 system-ui 是正确选择**（省一次字体加载、跟随系统）。
            out.append({"line":t[:m.start()].count("\n")+1,
                        "snippet":f"{first} 作主字体 —— 若项目 DESIGN.md 未声明用系统字体，复核一次"})
    return out[:6]

@rule("purple-gradient","渐变里含紫/靛（色相 260-310）—— AI 配色头号签名")
def r_grad(t,_):
    out=[]
    for m in re.finditer(r'(linear|radial|conic)-gradient\([^)]{0,300}\)', t, re.I):
        seg = m.group(0)
        for hx in re.findall(r'#[0-9A-Fa-f]{3,6}', seg):
            hue,sat = hex_hue(hx)
            if hue is not None and 260 <= hue <= 310 and sat > 0.25:
                out.append({"line":t[:m.start()].count("\n")+1,
                            "snippet":f"{hx}(色相{hue:.0f}°) in {seg[:60]}"}); break
    return out[:6]

@rule("side-tab","卡片单边彩色粗边框 border-left/right ≥2px —— design-review 第 8 条")
def r_side(t,_):
    out=[]
    for m in re.finditer(r'border-(left|right)\s*:\s*(\d+)px\s+solid\s+(#[0-9A-Fa-f]{3,6}|rgba?\([^)]+\))', t, re.I):
        if int(m.group(2)) >= 2:
            col = m.group(3)
            if col.startswith("#"):
                hue,sat = hex_hue(col)
                if sat is not None and sat < 0.12: continue   # 中性色放行
            out.append({"line":t[:m.start()].count("\n")+1,"snippet":m.group(0)[:80]})
    return out[:6]

@rule("transition-all","`transition: all` —— 所有元素同速，design-review 动效第 5 条")
def r_tall(t,_): return hits(r'transition\s*:\s*all\b', t, re.I)

@rule("animate-layout","过渡了**布局属性**（width/height/top/left/margin/padding —— 会触发 layout 重算）")
def r_anim(t,_):
    out=[]
    for m in re.finditer(r'transition\s*:\s*([^;{}\n]+)', t, re.I):
        d=m.group(1).lower()
        for prop in ("width","height","top","left","right","bottom","margin","padding"):
            if re.search(r'\b'+prop+r'\b', d):
                out.append({"line":t[:m.start()].count("\n")+1,"snippet":f"transition 了 {prop}: {d[:60]}"}); break
    return out[:6]

@rule("fake-data","假数据 / 假人名 / 完美假数字（taste §9.D）")
def r_fake(t,_):
    pat = r'(lorem ipsum|John Doe|Jane Doe|\bAcme\b|\bNexus\b|SmartFlow|Cloudly|99\.99%|1234567|示例文字|你的文字)'
    return hits(pat, t, re.I)

@rule("filler-verb","填充动词 / 通用 hero 文案")
def r_filler(t,_):
    pat = (r'(Elevate\b|Seamless(ly)?\b|Unleash\b|Next-Gen\b|Revolutioniz|'
           r'Welcome to |Unlock the power|all-in-one solution|赋能|一站式|全新升级|极致体验)')
    return hits(pat, t, re.I)

@rule("scroll-hint","滚动提示（taste：用户知道什么是滚动，全禁）")
def r_scroll(t,_):
    return hits(r'(↓\s*scroll|Scroll to explore|向下滚动|scroll-hint|scroll-indicator)', t, re.I)

@rule("version-badge","版本/内测标签作装饰（V0.6 / BETA / EARLY ACCESS）")
def r_ver(t,_):
    return hits(r'>\s*(v?\d+\.\d+(\.\d+)?(-rc\.\d+)?|BETA|ALPHA|EARLY ACCESS|INVITE[- ]ONLY[^<]{0,20})\s*<', t)

@rule("numbered-eyebrow","章节编号 eyebrow（`00 /`、`001 ·`、`06 · how it works`）")
def r_eyebrow(t,_):
    return hits(r'>\s*0\d{1,2}\s*[/·—-]\s*[A-Za-z一-龥]', t)

@rule("ellipsis","用三个点 `...` 而非 `…`", profiles=("web","desktop"))
def r_ell(t,_):
    # ⚠️ 必须只看**可见正文**。原来扫原始文本，于是 JS 的展开语法
    #    `[...(r||document).querySelectorAll(s)]` / `{...(cur?{}:{})}` 被当成省略号报红
    #    （2026-08-31 在 验证项目 的 demo 上实测两处，全是假阳性）。
    #    这是条**文案**规则，代码不在它的量程里 —— visible_text() 早就有，只是这条没用它。
    return hits(r'\.\.\.(?![.\w/])', visible_text(t))

@rule("pure-black-white","纯黑/纯白作**页面级**底色或正文色（局部组件用白字不算）")
def r_pbw(t,_):
    t = strip_comments(t)
    out=[]
    # 只看 body / html / :root 这三个页面级选择器的规则块
    # 选择器必须**就是** body/html/:root 本身（可带同元素上的类/伪类），
    # 不许含后代组合符——`body.is-glance .wbtn` 说的是浮层里的按钮，不是页面底色
    sel_re = r'(?:^|[},])\s*((?:body|html|:root)(?:[.:#\[][^\s,{>+~]*)*)\s*\{([^}]*)\}'
    for m in re.finditer(sel_re, t, re.I|re.M):
        block=m.group(2)
        for d in re.finditer(r'(background(-color)?|color)\s*:\s*(#000000|#000\b|#ffffff|#fff\b)', block, re.I):
            out.append({"line":t[:m.start(2)+d.start()].count("\n")+1,
                        "snippet":f"{m.group(1).strip()} 上 {d.group(0)}（应用 #171717 / #fafafa）"})
    return out[:6]

@rule("beige-default","taste §4.2 高端消费品米色调色板（作默认即禁）")
def r_beige(t,_):
    out=[]
    for hx in BEIGE_BG+BEIGE_ACC+BEIGE_TEXT:
        for m in re.finditer(re.escape(hx), t, re.I):
            out.append({"line":t[:m.start()].count("\n")+1,"snippet":f"{hx}（taste 禁作默认）"}); break
    return out[:6]

@rule("three-col-icon-grid","三列等宽图标卡网格（design-review：最容易辨认的 AI 布局）")
def r_3col(t,_):
    out=[]
    for m in re.finditer(r'grid-template-columns\s*:\s*(repeat\(\s*3\s*,\s*1fr\s*\)|1fr\s+1fr\s+1fr)', t, re.I):
        out.append({"line":t[:m.start()].count("\n")+1,
                    "snippet":"三等宽列 —— 若每格是「圆形图标+标题+两行字」即为 AI 网格，需人工确认"})
    return out[:4]

@rule("emoji-as-ui","彩色 emoji 用作图标/项目符号/按钮内容（✕✓→⌘ 等 UI 字形不算）")
def r_emoji(t,_):
    # 只认真正的彩色 emoji 区段；Dingbats(2700-27BF)、箭头(2190-21FF)、
    # 技术符号(2300-23FF，含 ⌘⌥⌫⏎) 是 UI 字形，不是 slop
    emo = '[\U0001F300-\U0001FAFF\U0001F900-\U0001F9FF\u2B00-\u2BFF]'
    return hits(r'<(h[1-6]|button|li)[^>]*>[^<]{0,40}'+emo, strip_comments(t))

def scan_text(text, profile):
    findings=[]
    for r in RULES:
        if profile not in r["profiles"]: continue
        for h in r["fn"](text, profile):
            findings.append({"rule":r["id"],"desc":r["desc"], **h})
    return findings

def main():
    p=argparse.ArgumentParser()
    p.add_argument("target",nargs="?"); p.add_argument("--profile",default="web",choices=["web","zh","desktop"])
    p.add_argument("--json",action="store_true"); p.add_argument("--list-rules",action="store_true")
    a=p.parse_args()
    if a.list_rules:
        for r in RULES: print(f"{r['id']:<22} {r['desc']}")
        sys.exit(0)
    if not a.target: die_unable("缺少扫描目标")
    if not os.path.exists(a.target): die_unable(f"目标不存在：{a.target}")
    # ⚠️ 2026-09-04：目录模式按扩展名过滤，**而显式传单文件时不过滤** ——
    #    于是显式传一个 `DESIGN.md` 进来，会用「可见文案」那套规则去扫
    #    设计理由散文与 YAML 里的推导说明，报出 6 个「A 层硬门」失败。
    #    ⛔ 这类假红最贵的不是那一次误判，是它教会人忽略这道门。
    #    ⭐ 同一道门对同一个文件，走目录进来会被跳过、显式传进来却会被扫 ——
    #      **两条路径判据不一致，本身就是缺陷**。
    SCANNABLE = (".html", ".htm", ".css", ".jsx", ".tsx", ".vue", ".svelte")
    files=[]
    if os.path.isdir(a.target):
        for root,_,fs in os.walk(a.target):
            if "node_modules" in root or "/." in root: continue
            files += [os.path.join(root,f) for f in fs if f.endswith(SCANNABLE)]
    elif a.target.endswith(SCANNABLE):
        files=[a.target]
    else:
        die_unable(f"{a.target} 不是可扫描的类型 —— 本门禁查的是**可见文案与视觉实现**，"
                   f"只认 {'/'.join(x.lstrip('.') for x in SCANNABLE)}。"
                   f"设计文档（.md）里的理由散文不是 UI 文案，用它的规则去扫必然假红")
    if not files: die_unable(f"{a.target} 下没有可扫描的文件（html/css/jsx/tsx/vue/svelte）")

    # C 层对照项目声明（此前 load_design_decl 定义了却从没被调用 —— Codex 外审抓出的假能力）
    _base = a.target if os.path.isdir(a.target) else (os.path.dirname(a.target) or ".")
    decl = load_design_decl(os.path.join(_base, "DESIGN.md"))
    DECL_KEYS = {"blocked-font": None, "purple-gradient": ("紫", "purple", "violet"),
                 "pure-black-white": ("纯黑", "黑白", "black", "monochrome"),
                 "beige-default": ("米色", "奶油", "beige", "cream"),
                 "emoji-as-ui": ("emoji", "表情")}

    def declared(x):
        """项目声明里是否批准了这条 C 层发现的方向。⚠️ 字符串级比对，只认显式提到。"""
        if not decl: return False
        keys = DECL_KEYS.get(x["rule"])
        if keys is None and x["rule"] == "blocked-font":
            first = x.get("snippet", "").split("=")[-1].strip().lower()
            return bool(first) and first.split()[0].strip("\"'") in decl.lower()
        return any(k.lower() in decl.lower() for k in (keys or ()))

    allf=[]
    for f in files:
        try: text=open(f,encoding="utf8",errors="replace").read()
        except Exception as e: die_unable(f"读不了 {f}：{e}")
        for x in scan_text(text,a.profile): allf.append({"file":f, **x})
    for x in allf:
        if tier_of(x["rule"]) == "C":
            x["declared"] = declared(x)

    hardf=[x for x in allf if tier_of(x["rule"])=="A"]
    if a.json:
        print(json.dumps({"profile":a.profile,"files":len(files),"findings":allf,
                          "hard":len(hardf),"clean":not hardf,
                          "tiers":{x["rule"]:tier_of(x["rule"]) for x in allf}},
                         ensure_ascii=False,indent=2))
    else:
        print(f"扫描 {len(files)} 个文件　档位={a.profile}　规则 {len([r for r in RULES if a.profile in r['profiles']])} 条\n")
        by={}
        for x in allf: by.setdefault(x["rule"],[]).append(x)
        ICON={"A":"❌","B":"⚠️","C":"ℹ️","D":"💡"}
        for rid,xs in by.items():
            tg=tier_of(rid)
            _n = xs[0].get('total') or len(xs)   # 证据可截断，计数不许
            print(f"  {ICON[tg]} [{tg}] {rid}（{_n} 处）— {xs[0]['desc']}")
            for x in xs[:3]: print(f"       {os.path.basename(x['file'])}:{x['line']}  {x['snippet']}")
        if not allf: print("  （无机械可查的 slop 破绽）")
        hard=[x for x in allf if tier_of(x["rule"])=="A"]
        soft=[x for x in allf if tier_of(x["rule"])!="A"]
        # ⚠️ 汇总也不许用证据条数当计数 —— `hits` 的证据列表按 limit 截断过。
        #    逐条那一行已经改成印真计数，汇总这一行第一版还在印 len(hard)，
        #    于是同一次运行里**两个数字互相打架**（逐条 20 处，汇总 6 处）。
        #    ⭐ 截断合理，但**被截断的事实必须在每一处出现计数的地方都说出来**。
        # 🚨 第一版写成 `sum(每条证据的 total)` —— 6 条证据各带 total=20 → 报 120。
        #    ⭐ 计数要**按 (文件, 规则) 去重**取一次真值，不是按证据求和。
        #      这是同一个错误的第三种形态：先是少报（截断），再是多报（重复计）。
        def _cnt(xs):
            seen, n = set(), 0
            for x in xs:
                k = (x.get('file'), x.get('rule'))
                if k in seen:
                    continue
                seen.add(k)
                n += x.get('total') or 1
            return n
        _h, _s = _cnt(hard), _cnt(soft)
        print(f"\n结论：{'CLEAN' if not hard else 'FOUND ' + str(_h)}"
              f"（A 层硬门 {_h} 处{'；B/C 层提示 %d 处，不阻断' % _s if soft else ''}）")
        if soft and not hard:
            print("⚠️ B/C 层是产品类型默认值与品牌方向 —— **与默认风格不同 ≠ 质量不合格**（铁律 49）。")
        print("⚠️ 这只是反 slop 三层里的第 1 层。报绿不代表设计不像 AI 生成的。")
    # ⛔ 退出码只看 A 层：B/C/D 不阻断（铁律 49）。
    #    ⭐ 此前 C 层的字体/配色直接返 1，把「与默认风格不同」判成「质量不合格」。
    sys.exit(0 if not hardf else 1)


_ST_EXT = ".html"
_ST_BAD_RC = 2
_GOOD_HTML = """<!doctype html><html><head><style>
body{font-family:Charter,Georgia,serif;background:#fafafa;color:#171717}
.c{border-radius:8px;transition:opacity .15s ease-out}
</style></head><body><h1>标题</h1><p>正文内容，用弯引号“像这样”，省略号用…</p></body></html>"""
_ST_CASES = [
    # (名字, 夹具, 期望退出码, 期望命中的规则 id；"!xx"=必须不命中)
    # ⛔ 2026-09-07 重定层后 16 条规则里没有 A 层 —— 退出码恒 0。
    #    于是退出码不再能区分「报出」与「没报」，断言一律落在 finding id 上
    #    （本仓教训：对必然共现/同码的判据，断言落 id 不落退出码）。
    ("正例", _GOOD_HTML, 0, None),
    ("反例 破折号（B 层报出）", _GOOD_HTML.replace("正文内容", "正文内容 — 带破折号"), 0, "em-dash"),
    ("正例 首选字体 system-ui（C 层提示）",
     _GOOD_HTML.replace("font-family:Charter,Georgia,serif",
                        "font-family:system-ui,-apple-system,sans-serif"), 0, "blocked-font"),
    ("反例 禁用字体（C 层报出不阻断）",
     _GOOD_HTML.replace("Charter,Georgia,serif", "Inter,sans-serif"), 0, "blocked-font"),
    ("反例 transition-all（B）", _GOOD_HTML.replace("transition:opacity .15s ease-out", "transition:all .3s"), 0, "transition-all"),
    ("反例 三点省略号（B）", _GOOD_HTML.replace("用…", "用..."), 0, "ellipsis"),
    ("防假阳 JS 展开语法不算省略号",
     _GOOD_HTML.replace("</body>", "<script>const f=(...a)=>[...a];</script></body>"), 0, "!ellipsis"),
    ("反例 单边彩色粗边框（D）",
     _GOOD_HTML.replace("border-radius:8px", "border-left:4px solid #7C3AED;border-radius:8px"), 0, "side-tab"),
    ("反例 过渡布局属性（B）",
     _GOOD_HTML.replace("transition:opacity .15s ease-out", "transition:width .2s ease-out"), 0, "animate-layout"),
    ("反例 假数据（B）", _GOOD_HTML.replace("正文内容", "Lorem ipsum dolor"), 0, "fake-data"),
    ("反例 填充动词（B）", _GOOD_HTML.replace("正文内容", "赋能每一位创作者"), 0, "filler-verb"),
    ("反例 滚动提示（D）", _GOOD_HTML.replace("<h1>标题</h1>", "<h1>标题</h1><div>向下滚动</div>"), 0, "scroll-hint"),
    ("反例 版本徽章（D）", _GOOD_HTML.replace("<h1>标题</h1>", "<h1>标题</h1><span>BETA</span>"), 0, "version-badge"),
    ("反例 章节编号 eyebrow（D）",
     _GOOD_HTML.replace("<h1>标题</h1>", "<span>01 · 开始</span><h1>标题</h1>"), 0, "numbered-eyebrow"),
    ("反例 米色默认（C）",
     _GOOD_HTML.replace("background:#fafafa", "background:#f5f1ea"), 0, "beige-default"),
    ("反例 三列图标网格（D）",
     _GOOD_HTML.replace(".c{", ".g{grid-template-columns:repeat(3,1fr)}\n.c{"), 0, "three-col-icon-grid"),
    ("反例 emoji 当图标（C）",
     _GOOD_HTML.replace("<h1>标题</h1>", "<h1>🚀 标题</h1>"), 0, "emoji-as-ui"),
    ("反例 页面级纯白（C）",
     _GOOD_HTML.replace("background:#fafafa", "background:#FFFFFF"), 0, "pure-black-white"),
    ("反例 紫渐变（C）", _GOOD_HTML.replace("<h1>", "<div style='background:linear-gradient(90deg,#7C3AED,#4F46E5)'></div><h1>"), 0, "purple-gradient"),
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
    import json as _json
    def run_json(p):
        r = subprocess.run([sys.executable, me, p, "--json"], capture_output=True, text=True)
        try: return r.returncode, _json.loads(r.stdout)
        except Exception: return r.returncode, {"findings": []}
    for name, body, want, wrule in _ST_CASES:
        rc, d = run_json(w(name.replace(' ', '_') + _ST_EXT, body))
        rules_hit = {x["rule"] for x in d.get("findings", [])}
        if wrule is None:
            g = rc == want and not rules_hit
        elif wrule.startswith('!'):
            g = rc == want and wrule[1:] not in rules_hit
        else:
            g = rc == want and wrule in rules_hit
        ok &= g
        print("  %s %-34s 期望 rc=%d%s 实得 rc=%d 命中=%s"
              % ("✅" if g else "❌", name, want,
                 ('' if wrule is None else ' ' + wrule), rc, sorted(rules_hit) or '无'))
    rc = run(os.path.join(t, "nope" + _ST_EXT))
    g = rc == _ST_BAD_RC; ok &= g
    print("  %s %-34s 期望 %d 实得 %d" % ("✅" if g else "❌", "输入不存在", _ST_BAD_RC, rc))
    # ⭐ 2026-09-04：目录模式按扩展名过滤，而显式传单文件时不过滤 ——
    #    显式传 DESIGN.md 进来会用「可见文案」的规则扫设计理由散文，报出 6 个 A 层失败。
    #    ⛔ 两条路径判据不一致本身就是缺陷；且这类假红会教会人忽略这道门。
    md = w("design_doc.md", "# 设计说明\n\n中性灰 —— 必须与红绿互不相同 —— 这是理由散文。\n")
    rc = run(md)
    g = rc == 2; ok &= g
    print("  %s %-34s 期望 %d 实得 %d" % ("✅" if g else "❌", "显式传 .md → 报 2 不扫", 2, rc))
    # 🚨 反向：可扫描类型仍必须被扫（过滤不许变成「什么都不扫」）
    htm = w("still_scans.html", "<p>正文 —— 带破折号</p>")
    _rc2, _d2 = run_json(htm)
    g = _rc2 == 0 and any(x["rule"] == "em-dash" for x in _d2.get("findings", [])); ok &= g
    print("  %s %-34s 期望 rc=0 且命中 em-dash 实得 rc=%d" % ("✅" if g else "❌", "反向 .html 仍会被扫出破折号", _rc2))
    # ⭐ 每条规则必须显式定层：TIER 漏一条即坏（响亮地坏，不许静默吃默认值）
    _missing = sorted({r["id"] for r in RULES} - set(TIER))
    g = not _missing; ok &= g
    print("  %s %-34s %s" % ("✅" if g else "❌", "全部规则显式定层（无默认 A）", _missing or "16 条全登记"))
    # ⭐ C 层对照项目声明：DESIGN.md 声明了紫色 → declared 标 True
    _dd = os.path.join(t, "declproj"); os.makedirs(_dd, exist_ok=True)
    _io.open(os.path.join(_dd, "DESIGN.md"), "w", encoding="utf-8").write("# 方向\n主色是紫色系。\n")
    _io.open(os.path.join(_dd, "p.html"), "w", encoding="utf-8").write(
        _GOOD_HTML.replace("<h1>", "<div style='background:linear-gradient(90deg,#7C3AED,#4F46E5)'></div><h1>"))
    _rc3, _d3 = run_json(os.path.join(_dd, "p.html"))
    _pg = [x for x in _d3.get("findings", []) if x["rule"] == "purple-gradient"]
    g = bool(_pg) and _pg[0].get("declared") is True; ok &= g
    print("  %s %-34s %s" % ("✅" if g else "❌", "C 层对照声明（声明紫色→declared）",
          "declared=True" if g else _pg))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：先修门禁"))
    # ⭐⭐ 「不阻断」不许退化成「不检查」：C 层规则必须**仍然出现在 findings 里**。
    #    ⚠️ 只断言退出码 0 是不够的 —— 把规则删掉退出码也是 0。
    import subprocess as _sp, json as _js, tempfile as _tf, os as _os
    _t = _tf.mkdtemp(prefix="slop-c-")
    _f = _os.path.join(_t, "c.html")
    open(_f, "w", encoding="utf8").write(
        _GOOD_HTML.replace("Charter,Georgia,serif", "Inter,sans-serif"))
    _o = _sp.run([sys.executable, _os.path.abspath(__file__), _f, "--json"],
                 capture_output=True, text=True).stdout
    try:
        _d = _js.loads(_o)
        _hit = any(x["rule"] == "blocked-font" for x in _d.get("findings", []))
        _tier = _d.get("tiers", {}).get("blocked-font")
        _g = _hit and _tier == "C"
    except Exception:
        _g = False
    ok &= _g
    print("  %s %-40s %s" % ("✅" if _g else "❌",
          "C 层规则仍然报出（不阻断 ≠ 不检查）",
          "findings 里有 blocked-font 且标 C" if _g else "**规则消失了或层级不对**"))

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
