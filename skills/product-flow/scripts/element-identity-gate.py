#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
元素身份门禁（S6 交互稿出场前 · S7 Figma 定稿后）。

为什么需要它：
  M1 的 ID 链管的是**条目**（需求 / 机会 / 假设），它管不到**界面元素**。
  于是交互规格里的一个按钮、HTML 里的那个 DOM、Figma 里的那个图层、
  用例里的那个选择器——**四处各叫各的名字，谁也对不上谁**。
  改了一个按钮，Figma 里找不到它是哪个，用例里的选择器悄悄失效且不报错。

  取自 Whiteport WDS 的 Area Label：同一标识符原样出现在
  规格 / `id` / Figma 图层名 / 测试选择器四处。
  可访问名不在这条链上：优先可见文字，表单用 label，只有无可见名的图标按钮才用 aria-label。

⚠️ 诚实边界：它查「标识符对不对得上、命名是不是按功能、有没有接回需求」，
   **查不出「这个元素该不该存在」**——那是逻辑解释测试，人来做。

用法: element-identity-gate.py <交互规格.md> [--html <demo.html> | --baseline <baseline.md>] [--json]
      --baseline 用于**已上线产品**：无 DOM 时校验「截图+框选坐标+元素名」三元组。
                 |  --self-test
退出码: 0=通过 1=有缺口 2=跑不了
"""
import io, os, re, sys, json, tempfile, subprocess

# 按内容/外观/位置命名 —— 会随文案、主题、排版变动而失效
BAD_NAME = [
    (r'(?:^|-)(?:welcome|greeting|hello)(?:-|$)', "按文案命名（文案会变）"),
    (r'(?:^|-)(?:blue|red|green|dark|light|gray|grey)(?:-|$)', "按颜色命名（颜色会变，且把令牌钉死在名字里）"),
    (r'(?:^|-)(?:first|second|third|last|top|bottom|left|right)(?:-|$)', "按位置命名（位置不是用途）"),
    (r'(?:^|-)(?:big|small|large|tiny)(?:-|$)', "按尺寸命名（尺寸会变）"),
    (r'(?:^|-)(?:div|span|box\d*|wrapper\d+|el\d+)(?:-|$)', "按实现命名（说不出它干什么）"),
]
IDENT = re.compile(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$')


def rows_from_json(txt):
    """从 `spec/elements.json` 抽标识符，渲染成与 md 表同形的行。

    ⭐ 2026-09-03：此前元素身份有**两个源** —— 交互规格里的 md 表（本门禁读它）
       与 `spec/elements.json`（`spec-sync-gate` 读它）。两处各写一遍必然分叉，
       而分叉那天两道门都还是绿的（它们各看各的那一份）。
       ⇒ 本门禁改为**两种输入都认**，项目只维护其中一份即可。
    """
    try:
        d = json.loads(txt)
    except Exception:
        return None
    els = d.get('elements')
    if not isinstance(els, list):
        return None
    out = []
    for e in els:
        if not isinstance(e, dict) or not e.get('id'):
            continue
        # 与 md 表对齐的列序：标识符 / 类型 / 归属 / 用途 / 触发 / 服务需求 / 成功判据
        out.append(['`%s`' % e['id'], e.get('kind', ''), e.get('parent') or '—',
                    e.get('note') or e.get('name') or '', '', e.get('fr') or '',
                    e.get('success') or ''])
    return out


def rows(md):
    """抽出元素标识表的数据行：识别**首列列名**为「标识符」的表。

    ⚠️ 2026-09-04：此前的触发条件是「行首是 `|` 且**行内含**标识符」，
    于是官方模板里那张「出现在哪 / 形态」映射表的**数据行**
    （`| 本表 | 标识符本体 |`）把它触发了，接着把
    `HTML 交互稿` / `Figma 图层名` / `测试用例的选择器` 三行当成了元素。
    ⭐ 触发条件必须锚在**表头首列**上，并且下一行得是分隔行 ——
      「行内出现某个词」这种判据在 markdown 里几乎必然误触发。
    """
    lines = md.splitlines()
    out, in_tbl = [], False
    for i, ln in enumerate(lines):
        t = ln.strip()
        if t.startswith('|'):
            first = re.sub(r'[`*\s]', '', t.strip('|').split('|')[0])
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
            is_sep = nxt.startswith('|') and set(nxt.strip('|')) <= set('-: |')
            if first == '标识符' and is_sep:
                in_tbl = True
                continue
        if in_tbl:
            if not t.startswith('|'):
                in_tbl = False
                continue
            cells = [c.strip() for c in t.strip('|').split('|')]
            if set(''.join(cells)) <= set('-: '):   # 分隔行
                continue
            out.append(cells)
    return out


def baseline_ids(md):
    """从 baseline.md 取元素身份。

    ⚠️ 补的是一处「声称≠实际」：文档写着「`--html` 换成 `--baseline`」，
    而此前脚本只有 `--html`。⭐ 无 DOM 的原生/桌面端**没有 id 可查**，
    所以判据换成三元组齐不齐：**元素名 + 截图 + 框选坐标**。

    识别表头含「元素名」的表：| 元素名 | 截图 | 坐标 | …
    """
    out, in_tbl, ci = [], False, 0
    for ln in md.splitlines():
        t = ln.strip()
        if not t.startswith('|'):
            in_tbl = False; continue
        cells = [c.strip() for c in t.strip('|').split('|')]
        if set(''.join(cells)) <= set('-: '): continue
        head = ''.join(cells)
        if '元素名' in head:
            in_tbl = True
            ci = next(i for i, c in enumerate(cells) if '元素名' in c)
            continue
        if not in_tbl or len(cells) <= ci: continue
        name = re.sub(r'[`*]', '', cells[ci]).strip()
        if name and not name.startswith('<'):
            out.append((name, cells))
    return out


def check(spec_path, html_path=None, as_json=False, baseline_path=None):
    if not os.path.isfile(spec_path):
        print("跑不了：找不到 %s" % spec_path, file=sys.stderr); return 2
    md = io.open(spec_path, encoding='utf-8', errors='replace').read()
    html, base = "", ""
    if baseline_path:
        if not os.path.isfile(baseline_path):
            print("跑不了：找不到 %s" % baseline_path, file=sys.stderr); return 2
        base = io.open(baseline_path, encoding='utf-8', errors='replace').read()
    if html_path:
        if not os.path.isfile(html_path):
            print("跑不了：找不到 %s" % html_path, file=sys.stderr); return 2
        html = io.open(html_path, encoding='utf-8', errors='replace').read()

    # ⚠️ 2026-09-05：`rows_from_json` 解析失败时返回 None，
    #    而下面直接 `for cells in rs` → **抛原始 TypeError，退出码 1**。
    #    ⛔ 1 在本门禁的语义里是「有缺口」—— 于是**输入格式错误被伪装成业务结论**，
    #      照着它去找「哪个标识符不合规」只会一无所获。
    #    ⭐ 同型第二处（今天 `flows-to-testcases` 刚修过一次）：
    #      **输入错误必须报「跑不了」那一档**，并说清是哪个文件、错在哪。
    if spec_path.endswith('.json'):
        rs = rows_from_json(md)
        if rs is None:
            print("UNABLE: %s 不是合法的 elements.json —— "
                  "要么 JSON 解析失败，要么顶层没有 `elements` 数组。"
                  "（传交互规格 md 也可以，本门禁两种输入都认）" % spec_path, file=sys.stderr)
            return 2
    else:
        rs = rows(md)
    findings = []
    if not rs:
        findings.append(("no-table",
                         "元素标识表读不到 —— 传交互规格 md（表头含「标识符」的表）"
                         "或 `spec/elements.json` 皆可，但两者只维护一份"))
    ids = []
    for cells in rs:
        raw = cells[0]
        m = re.search(r'`([^`]+)`', raw) or re.search(r'([a-z0-9<>{}一-龥-]+)', raw)
        if not m:
            continue
        ident = m.group(1)
        # ⚠️ 回退正则不含大写字母，于是 `Figma` 会被切成 `igma` ——
        #    门禁随后报「`igma` 不是合法标识符」，而**文档里根本没有这个字符串**。
        #    ⭐ 人拿着它去搜，只会一无所获。诊断里必须给出**原始单元格**，
        #      而不是判据自己切出来的碎片。
        shown = ident if ident == raw.strip().strip('`') else '%s（原文：%s）' % (ident, raw.strip()[:30])
        if '<' in ident or '{' in ident:      # 模板占位，跳过
            continue
        ids.append((ident, cells))
        if not IDENT.match(ident):
            findings.append(("shape", "`%s` 不是合法标识符（小写、连字符分段）" % shown))
        for pat, why in BAD_NAME:
            if re.search(pat, ident):
                findings.append(("naming", "`%s` %s" % (ident, why)))
                break
        # 「服务哪条需求/驱动力」栏必须接回一个 ID
        if len(cells) >= 6:
            serves = cells[5]
            if not re.search(r'[A-Z]{2,4}-\d+', serves) and serves not in ('—', '-', ''):
                findings.append(("orphan", "`%s` 的「服务哪条需求」没有接回任何需求 ID：%r" % (ident, serves[:24])))

    if not ids and rs:
        findings.append(("no-table", "元素标识表里没有任何真实标识符（只有模板占位）"))

    if html:
        for ident, _ in ids:
            if not re.search(r'id\s*=\s*["\']%s["\']' % re.escape(ident), html):
                findings.append(("missing-id", "`%s` 在交互稿里没有对应的 id" % ident))
            # ⛔ 2026-08-31 撤掉「必须有 aria-label」这条判据（外部评审揪出）：
            #    给所有节点强塞 aria-label 会盖掉更好的可见名称——一个写着「保存」的按钮
            #    配 aria-label="save-btn"，屏幕阅读器念出的比可见文字更差，这是净损失。
            #    正确判据是「无可见文字的元素才必须有可访问名」，静态正则区分不了
            #    「有没有可见文字」，这一条留给 browser-audit 拿 computed accessible name 去查。
        # 反向：交互稿里有形似标识符的 id，规格里却没登记
        known = set(i for i, _ in ids)
        for hid in set(re.findall(r'id\s*=\s*["\']([a-z][a-z0-9-]+)["\']', html)):
            if IDENT.match(hid) and hid not in known:
                findings.append(("unregistered", "交互稿里的 `%s` 没有登记进元素标识表" % hid))

    if base:
        # ⚠️ 不能叫 rows —— 会在整个 check() 里遮蔽同名的模块级函数 rows()，
        #    让前面的 `rs = rows(md)` 直接 UnboundLocalError。
        brows = baseline_ids(base)
        if not brows:
            findings.append(("no-baseline-table", "baseline.md 里没有「元素名」表——"
                                                  "无 DOM 时这是唯一的身份锚点"))
        known = set(i for i, _ in ids)
        for name, cells in brows:
            if name not in known:
                findings.append(("unregistered", "baseline 里的 `%s` 没有登记进元素标识表" % name))
            # ⚠️ 必须带分隔符拼：`''.join` 会让 `s0.png` 后面直接跟下一格的 `0`，
            #    于是 `\b` 词边界失效、截图判据恒为假。
            #    ⭐ 拼接方式本身能让一条正确的正则失效。
            row = ' | '.join(cells)
            # ⭐ 无 DOM 判据＝三元组齐不齐：元素名（已有）+ 截图 + 框选坐标
            if not re.search(r'\.(png|jpg|jpeg|webp)\b', row, re.I):
                findings.append(("no-shot", "`%s` 没有截图——无 DOM 时截图是它唯一的证据" % name))
            if not re.search(r'\d+\s*[,，]\s*\d+', row):
                findings.append(("no-coords", "`%s` 没有框选坐标（形如 `120,340`）——"
                                              "光有截图定位不到具体元素" % name))
        for ident, _ in ids:
            if ident not in set(n for n, _ in brows):
                findings.append(("missing-in-baseline", "`%s` 在 baseline 里没有对应行" % ident))

    if as_json:
        print(json.dumps({"ok": not findings, "count": len(ids),
                          "findings": [{"rule": a, "msg": b} for a, b in findings]},
                         ensure_ascii=False, indent=2))
    else:
        print("元素身份对账：登记 %d 个标识符\n" % len(ids))
        for a, b in findings:
            print("  ❌ [%s] %s" % (a, b))
        if not findings:
            print("⚠️ 本门只验**身份标识**齐不齐、对不对得上 —— "
                  "**不验那个元素长得对不对、点了以后行为对不对**。"
                  "身份齐备的稿子照样可以是错的。")
        print("\n%s" % ("✅ 通过" if not findings else
                        "❌ %d 处对不上——⚠️ 对不上不会让任何东西报错，"
                        "只会让选择器悄悄失效" % len(findings)))
    return 1 if findings else 0


GOOD_MD = """### 元素标识表

| 标识符 | 类型 | 归属区块 | 用途 | 触发它的用户动作 | 服务哪条需求 | 怎么算成功 |
|---|---|---|---|---|---|---|
| `home-page` | 容器 | — | 页面外壳 | — | — | — |
| `home-primary-cta` | 交互 | header | 发起注册流程 | 读完价值主张后点击 | FR-003 | 进入第二步 |
| `home-input-email` | 输入 | form | 收邮箱 | 聚焦 | FR-003 | 通过校验 |
"""
GOOD_HTML = """<div id="home-page"><button id="home-primary-cta" aria-label="开始注册">开始</button>
<input id="home-input-email" aria-label="邮箱"></div>"""


def self_test():
    t = tempfile.mkdtemp(prefix="eig-"); me = os.path.abspath(__file__)

    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p

    def run_json(obj):
        """新增能力（吃 elements.json）必须有自己的用例 ——
        否则自证覆盖的是加这个能力之前的那个程序。"""
        pth = w('elements.json', json.dumps(obj, ensure_ascii=False))
        return subprocess.call([sys.executable, os.path.abspath(__file__), pth],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run(md, html=None):
        a = [sys.executable, me, w("s.md", md)]
        if html is not None:
            a += ["--html", w("d.html", html)]
        return subprocess.call(a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cases = [
        ("正例（规格）", GOOD_MD, None, 0),
        # 🚨 2026-09-04：官方模板里有一张「出现在哪 / 形态」映射表，
        #    它的**数据行**含「标识符本体」四字。此前触发条件是「行内含标识符」，
        #    于是那张表的三行被当成元素，报出 `igma`（Figma 被回退正则切碎）
        #    这种**文档里根本不存在**的字符串。
        ("反例 映射表的数据行不许触发元素表识别（首列列名才算）",
         "| 出现在哪 | 形态 |\n|---|---|\n| 本表 | 标识符本体 |\n"
         "| Figma 图层名 | 同名 |\n| 测试用例的选择器 | 同名 |\n" + GOOD_MD, None, 0),
        ("正例（规格+交互稿）", GOOD_MD, GOOD_HTML, 0),
        ("反例 没有元素标识表", "### 组件层级\n\n只有一棵树，没有表。\n", None, 1),
        ("反例 表里只有模板占位", GOOD_MD.replace("home-", "<页面>-"), None, 1),
        ("反例 按文案命名", GOOD_MD.replace("home-primary-cta", "home-welcome-message"), None, 1),
        ("反例 按颜色命名", GOOD_MD.replace("home-primary-cta", "home-blue-button"), None, 1),
        ("反例 按位置命名", GOOD_MD.replace("home-input-email", "home-first-input"), None, 1),
        ("反例 标识符形状不合法", GOOD_MD.replace("`home-primary-cta`", "`HomePrimaryCTA`"), None, 1),
        ("反例 服务的需求没接回 ID", GOOD_MD.replace("| FR-003 | 进入第二步 |", "| 用户需要 | 进入第二步 |"), None, 1),
        ("反例 交互稿里缺 id", GOOD_MD, GOOD_HTML.replace('id="home-input-email" ', ''), 1),
        ("反例 交互稿有未登记的 id", GOOD_MD, GOOD_HTML.replace("</div>", '<a id="home-secret-link"></a></div>'), 1),
    ]
    # ⭐ baseline 路径（无 DOM 的已上线产品）单独造正反例：
    #    文档宣称 `--html` 可换 `--baseline`，而此前脚本根本没有这个参数。
    BASE_OK = """| 元素名 | 截图 | 框选坐标 | 说明 |
|---|---|---|---|
| `home-page` | s0.png | 0,0 | 外壳 |
| `home-primary-cta` | s1.png | 120,340 | 主按钮 |
| `home-input-email` | s2.png | 120,420 | 邮箱 |
"""
    bcases = [
        ("baseline 正例", GOOD_MD, BASE_OK, 0),
        ("baseline 缺元素名表", GOOD_MD, "# 基线\n没有表\n", 1),
        ("baseline 缺截图", GOOD_MD, BASE_OK.replace("s1.png", "—"), 1),
        ("baseline 缺框选坐标", GOOD_MD, BASE_OK.replace("120,340", "—"), 1),
        ("baseline 有未登记元素", GOOD_MD, BASE_OK + "| `home-secret` | s9.png | 1,2 | 野生 |\n", 1),
        ("baseline 漏了规格里的元素", GOOD_MD,
         BASE_OK.replace("| `home-input-email` | s2.png | 120,420 | 邮箱 |\n", ""), 1),
    ]
    # ⭐ 2026-09-01 变异审计补的一条：`no-baseline-table` 变异后自证仍通过。
    #    根因**不是缺用例** —— 「baseline 没有元素名表」时，规格里每个元素都必然
    #    同时触发 `missing-in-baseline`，两条判据**结构上无法用退出码分离**。
    #    ⭐⭐ **对于必然共现的判据，断言要落在 finding id 上，不能落在退出码上** ——
    #    否则「这条判据被删掉了」和「另一条替它红了」在退出码上完全一样。
    def ids_of(md, bl):
        r = subprocess.run([sys.executable, me, w("i1.md", md), "--baseline", w("i2.md", bl), "--json"],
                           capture_output=True, text=True)
        try:
            return {f["rule"] for f in json.loads(r.stdout).get("findings", [])}
        except Exception:
            return set()

    ok = True
    print("M8 自证 —— 正例绿 / 每类缺口各造一个反例必红 / 无效输入报 2\n")
    _got = ids_of(GOOD_MD, "# 基线\n没有表\n")
    _g = "no-baseline-table" in _got
    ok &= _g
    print("  %s %-30s %s" % ("✅" if _g else "❌", "id 级断言 no-baseline-table",
                             "命中" if _g else "未命中，实得 %s" % sorted(_got)))
    for name, md, html, want in cases:
        got = run(md, html); g = got == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    for name, md, bl, want in bcases:
        p1 = w("bs.md", md); p2 = w("bb.md", bl)
        got = subprocess.call([sys.executable, me, p1, "--baseline", p2],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        g = got == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    # ── 新增输入形态：elements.json（与 md 表二选一，只维护一份）──
    jcases = [
        ("json 正例：合法标识符", {"elements": [
            {"id": "home-page", "kind": "容器"},
            {"id": "home-primary-cta", "kind": "交互", "fr": "FR-003", "success": "进入第二步"}]}, 0),
        ("json 反例：按颜色命名", {"elements": [
            {"id": "home-page", "kind": "容器"}, {"id": "blue-button", "kind": "交互"}]}, 1),
        ("json 反例：非法标识符形态", {"elements": [
            {"id": "home-page", "kind": "容器"}, {"id": "Toast", "kind": "容器"}]}, 1),
        ("json 反例：空列表当没有表", {"elements": []}, 1),
    ]
    for name, obj, want in jcases:
        got = run_json(obj); g = got == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    rc = subprocess.call([sys.executable, me, os.path.join(t, "nope.md")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = rc == 2; ok &= g
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g else "❌", "文件不存在", rc))

    # 🚨 2026-09-05：坏 JSON 此前抛原始 TypeError、退出码 1 ——
    #    而 1 在本门禁语义里是「有缺口」，**输入错误被伪装成业务结论**。
    #    同型第二处（今天 flows-to-testcases 刚修过一次）。
    for nm, body in (("坏 JSON（解析失败）", '{"elements": [broken'),
                     ("顶层没有 elements 数组", '{"nope": 1}')):
        bp = os.path.join(t, nm.replace(' ', '') + ".json")
        io.open(bp, 'w', encoding='utf-8').write(body)
        rc2 = subprocess.call([sys.executable, me, bp],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        g2 = rc2 == 2; ok &= g2
        print("  %s %-30s 期望 2 实得 %d" % ("✅" if g2 else "❌", nm + " → 报 2", rc2))
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
        if '--self-test' in sys.argv: sys.exit(self_test())
        # ⚠️ 未知参数必须报错，⛔ 不许静默丢弃。
        #    2026-09-03 实测：有人整场用 `--spec X --demo Y` 调用本门禁，
        #    而正确写法是 `X --html Y`。旧解析把 `--spec`/`--demo` 当成「以 -- 开头」直接滤掉，
        #    于是 h=None、demo 侧的一半（未登记 id 的反向检查）**从没跑过**，
        #    门禁却一路报「✅ 通过」—— 真实缺口 32 处。
        #    ⭐ 「跑不了」和「跑了没问题」折叠成同一个状态，就是 fail-open。
        KNOWN = {'--help', '--html', '--baseline', '--json', '--self-test', '--list-rules'}
        argv = sys.argv[1:]
        # 提示语里写「用法见 --help」就必须真有这个出口 ——
        # 2026-09-05 实测:三道门都在提示 --help,而三道门都不接受 --help。
        if '--help' in sys.argv:
            print((__doc__ or '').strip() or '本门禁用位置参数,见文件头注释'); sys.exit(0)
        unknown = [x for x in argv if x.startswith('--') and x not in KNOWN]
        if unknown:
            print("UNABLE: 不认识的参数 %s；用法见 --help（本门禁要的是 "
                  "`<交互规格.md> --html <demo.html>`）" % ' '.join(unknown), file=sys.stderr)
            sys.exit(2)
        a = [x for x in argv if not x.startswith('--')]
        h = bl = None
        for flag in ('--html', '--baseline'):
            if flag in argv:
                i = argv.index(flag)
                if i + 1 < len(argv):
                    v = argv[i + 1]; a = [x for x in a if x != v]
                    if flag == '--html': h = v
                    else: bl = v
        if not a: print(__doc__); sys.exit(2)
        if len(a) > 1:
            print("UNABLE: 多余的位置参数 %s —— 交互稿要用 `--html` 传，"
                  "⛔ 直接跟在后面会被忽略而门禁照样报绿" % a[1:], file=sys.stderr)
            sys.exit(2)
        sys.exit(check(a[0], h, '--json' in argv, bl))
    _main_guarded(_entry)
