#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设计意图门禁 —— 反 slop 三层里**第 3 层**（最根本那层）的机器实现。

为什么需要它：
  铁律 16 说「**只做门禁那层等于没做**」，然后把第 3 层
  （Design Read / memorable-thing / SAFE-RISK）**完全交给自觉**。
  反过来同样成立：**把最有效的那层完全交给自觉，也等于没做。**
  而 RISK 提案的四要素结构是可数的 —— 可数的东西不该靠自觉。
  ⚠️ 2026-09-09 同步：RISK 走**提案制**，零提案合法（须写理由），本门禁查的是
  「提案结构齐不齐 / 零提案有没有理由」，⛔ 不是「够不够 N 条」。

⚠️ 诚实边界：本门禁只查「这三件事**有没有交、结构齐不齐**」，
   **判不了「这个 RISK 是不是真的冒险」** —— 那是 S5.3 UI/UE/视角 10 的事。
   一条写着「RISK：我们大胆地使用了圆角」的提案能过本门禁，但过不了评审。

用法: design-intent-gate.py <design-brief.md> [--json]   |   --self-test
退出码: 0=通过 1=不通过 2=跑不了
"""
import io, os, os, re, sys, json, tempfile, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_or_table   # noqa: E402  段落定位的唯一正本

RISK_ELEMS = [("是什么", r'是什么|什么[:：]'), ("为何成立", r'为何成立|为什么成立|理由'),
              ("得到什么", r'得到|收益|换来'), ("代价", r'代价|成本|风险|失去')]

def check(p):
    if not os.path.exists(p):
        print("UNABLE: 不存在 %s" % p, file=sys.stderr); sys.exit(2)
    # ⚠️ 传目录时原先直接抛 IsADirectoryError，退出码 1 与「有发现」**无法区分** ——
    #    崩溃被当成结论。「跑不了」必须是 2。
    if os.path.isdir(p):
        print("UNABLE: %s 是目录，本门禁要的是单个设计文件（如 design/DESIGN.md）" % p,
              file=sys.stderr); sys.exit(2)
    if not os.path.isfile(p):
        print("UNABLE: 文件不存在：%s" % p, file=sys.stderr); sys.exit(2)
    s = io.open(p, encoding='utf-8').read()
    res = []
    def add(rid, desc, ok, ev): res.append({"id": rid, "desc": desc, "ok": ok, "ev": ev})

    # ⚠️ 必须锚在**同一行**。首版写成 `[^\n]*[\n:：]+\s*(.{10,})`，贪婪匹配吃到行尾后
    #    用换行当分隔符，于是**捕获了下一行**——占位符「<谁> 的 <什么产品>」照样判通过。
    #    自证时才发现：一条能靠读别人内容蒙混过关的规则，等于没有这条规则。
    #    🚨 2026-09-04：那个修正**越过了正确用法**。官方模板写的是
    #         ### 1. Design Read（一句话）
    #         > 我把这个读作：给 **<谁>** 的 **<什么产品>**…
    #       内容在**下一行**，于是同一行判据让**模板自己永远过不了这道门** ——
    #       照着模板写的人，S5 第一道门就红。
    #    ⭐⭐ 修一个过松的判据时最容易犯的错，就是把正确用法一起挡在外面。
    #       两个方向都要测：占位符必须红（原病），模板形态必须绿（新病）。
    #    判据：从 `Design Read` 起向后最多两行内找 `：`，占位符检查保持不变。
    m = re.search(r'Design\s*Read[^\n]{0,20}?[:：]\s*([^\n]{10,})', s, re.I)
    if not m:
        m = re.search(r'Design\s*Read[^\n]{0,20}\n[>\s]*[^\n:：]{0,20}[:：]\s*([^\n]{10,})', s, re.I)
    add("design-read", "Design Read 一句话（给谁的什么产品、什么调性、倾向什么设计系统）",
        bool(m and len(m.group(1).strip()) >= 10 and '<' not in m.group(1)[:8]),
        (m.group(1)[:60] if m else "缺失或仍是模板占位"))

    m = re.search(r'(?:memorable[\s-]*thing|唯一一件事|要他记住)[^\n]{0,20}?[:：]\s*([^\n]{6,})', s, re.I)
    add("memorable-thing", "Memorable-thing 一句话（之后每个设计决策都要回查它）",
        bool(m and len(m.group(1).strip()) >= 6 and '<' not in m.group(1)[:8]),
        (m.group(1)[:60] if m else "缺失或仍是模板占位"))

    safe = re.findall(r'\**SAFE-\d+\**', s)
    add("safe-count", "SAFE 2–3 条（符合品类惯例的，说明为何这里要求稳）",
        2 <= len(safe) <= 4, "实得 %d 条" % len(safe))

    # ⚠️ 必须支持**真实的书写形态**，不是只支持我设想的那一种。
    #    设计简报里 RISK 是一张四列表（是什么/为何成立/得到什么/代价）——
    #    四要素在**表头**、内容在**数据行**。只按分块正文找关键词，会把填好的表判成缺项。
    risk_rows, lines = [], s.split('\n')
    for i, ln in enumerate(lines):
        if ln.strip().startswith('|') and '是什么' in ln and '代价' in ln:
            for ln2 in lines[i + 2:]:
                if not ln2.strip().startswith('|'): break
                cells = [c.strip() for c in ln2.strip().strip('|').split('|')]
                if cells and re.match(r'(?:RISK|R)-?\d+', cells[0]): risk_rows.append(cells)
            break
    risks = [] if risk_rows else re.split(r'(?m)^\s*(?:[-*]\s*)?\**RISK-\d+\**', s)[1:]
    n_risk = len(risk_rows) if risk_rows else len(risks)
    # ⛔ 2026-09-08（终局规格 2-4）：不再机械要求 RISK≥2 ——
    #   金融合规工具选择零突破可能完全正确。0 条合法，但必须写明理由；
    #   **没写理由的零才是模板货**（提案≠配额，批准的才执行）。
    # ⚠️ 2026-09-09：判据原来只认模板那一句「为何没有值得评估的突破：」——
    #   而 SOP 五处只写「零提案合法但必须写理由」，照做的人自然写成
    #   「本轮零 RISK 提案，理由：严格品牌约束…」⇒ **正确产物被判红**（实测坐实）。
    #   ⛔ 门不许惩罚正确用法：两种措辞都认，但**都要求冒号后有实质理由**（≥6 字非占位），
    #   声明零提案却不给理由仍然红 —— 放宽的是措辞，不是「提一句就算数」。
    zero_ok = bool(re.search(
        r'(?:为何没有值得评估的突破|(?:本轮|本项目)?\s*(?:零|无|没有)\s*RISK(?:\s*提案)?)'
        r'[，,]?\s*(?:理由)?\s*[：:]\s*(?!<)[^\n]{6,}', s))
    add("risk-count", "RISK 提案 ≥1 条，或 0 条但写明「为何没有值得评估的突破」",
        n_risk >= 1 or zero_ok,
        "实得 %d 条（%s）%s" % (n_risk, "表格式" if risk_rows else "分块式",
                               "，零突破理由已写" if (n_risk == 0 and zero_ok) else ""))

    # ⭐ 三方向登记表（A 锁）：无既定品牌时 ≥3 方向且四差异维度逐格填；
    #   既定品牌可豁免但必须写被排除方向+理由。换色不算方向 —— 本门只能查
    #   「格子填没填、有没有两方向同格全同」，**像不像三个方向归人工评审**。
    # 🚨 2026-09-09 第五轮：`s.find('三个视觉方向登记表')` 按全文首次出现定位 ——
    #   正文里提一句「三个视觉方向登记表见下」即从那句开始切。⇒ 锚定标题/表头。
    seg = section_or_table(s, '三个视觉方向登记表')
    if seg is None:
        add("direction-table", "A 锁三方向登记表存在（或品牌豁免）", False, "整节缺失")
    else:
        drows = []
        for ln in seg.split('\n'):
            if ln.strip().startswith('|') and re.match(r'^\|\s*方向\s+[A-Z甲乙丙]', ln.strip()):
                drows.append([c.strip() for c in ln.strip().strip('|').split('|')])
        exempt = bool(re.search(r'品牌豁免[^\n]*[：:][^\n]*被排除的方向[^\n]*[^<\s]', seg)
                      and not re.search(r'品牌豁免[^\n]*<__>', seg))
        filled = [r for r in drows if len(r) >= 5 and all(c and not c.startswith('<') for c in r[1:5])]
        dup = len(filled) >= 2 and any(filled[i][1:5] == filled[j][1:5]
                                       for i in range(len(filled)) for j in range(i + 1, len(filled)))
        if exempt:
            add("direction-table", "既定品牌豁免：被排除方向与理由在案", True, "豁免路径")
        else:
            add("direction-table", "≥3 个方向四差异维度逐格填，且无两方向全同",
                len(filled) >= 3 and not dup,
                "填齐 %d 个方向%s" % (len(filled), "；有两方向四格全同（只是换皮）" if dup else ""))
        appr = bool(re.search(r'人工批准记录[^\n]*[：:].*?于.*?批准', seg)
                    and not re.search(r'人工批准记录[^\n]*<谁>', seg))
        add("direction-approval", "A 锁人工批准记录在案（谁/何时/选了哪个方向）", appr,
            "已批准" if appr else "没有批准记录 —— 没被人批准的方向不算锁")

    bad, NAMES = [], ['是什么', '为何成立', '得到什么', '代价']
    if risk_rows:
        for cells in risk_rows:
            if len(cells) < 5:
                bad.append("%s 只有 %d 列，四要素不全" % (cells[0], len(cells))); continue
            empty = [j for j, c in enumerate(cells[1:5], 1) if not c or c.startswith('<')]
            if empty: bad.append("%s 留空：%s" % (cells[0], "/".join(NAMES[j-1] for j in empty)))
    else:
        for i, r in enumerate(risks, 1):
            # 🚨 四轮复核：`r[:600]` 是本仓 no-positional-window 禁止的形状，
            #   四要素写在 600 字符之后即静默漏检 —— 正是那条规则 docstring
            #   自己描述的失效模式。⇒ 整块判，不截断。
            miss = [n for n, pat in RISK_ELEMS if not re.search(pat, r)]
            if miss: bad.append("RISK-%d 缺：%s" % (i, "/".join(miss)))
    add("risk-elements", "每条 RISK 四要素齐（0 条且有零突破理由时本条不适用）",
        (not bad and n_risk > 0) or (n_risk == 0 and zero_ok),
        bad or ("%d 条均四要素齐" % n_risk if n_risk else "0 条（零突破理由在案，本条不适用）"))

    # 口径与 definition-gate / research-gate 对齐：N/A(None) 不算失败（2026-09-01）。
    # 本门禁目前不产出 None，但口径先统一 —— 否则下次有人加一条 N/A 就会静默复发。
    ok = all(x["ok"] is not False for x in res)
    if '--json' in sys.argv:
        print(json.dumps({"pass": ok, "checks": res}, ensure_ascii=False, indent=1))
    else:
        for x in res:
            print("%s [%s] %s" % ({True: "✅", False: "❌"}.get(x["ok"], "➖"), x["id"], x["desc"]))
            ev = x["ev"] if isinstance(x["ev"], list) else [x["ev"]]
            for e in ev: print("      %s" % e)
        print("\n%s" % ("✅ 生成期约束已交齐" if ok else "❌ 第 3 层缺失 —— 只做门禁那层等于没做"))
        print("⚠️ 本门禁只查「交没交、结构齐不齐」，**判不了这个 RISK 是不是真的冒险**——那归 S5.3 评审。")
    return 0 if ok else 1

GOOD = """# 设计简报
**Design Read**：我把这个读作：给重度囤图用户的桌面相册，克制的工具调性，倾向瑞士平面体系。
**Memorable-thing**：这个相册能听懂我要什么，然后自己长出那个功能。

## 三个视觉方向登记表
| 方向 | 构图与阅读路径 | 字形气质与层级 | 色彩/材质/光影 | 关键操作与反馈的视觉表达 |
|---|---|---|---|---|
| 方向 A 暗房 | 满屏瀑布流，Z 型扫读 | 无衬线细字重，层级靠字号 | 近黑底，照片自发光 | 悬浮工具条淡入 |
| 方向 B 图书馆 | 左栏索引+右侧大图 | 衬线标题混排 | 暖白纸感，投影分层 | 固定操作列常显 |
| 方向 C 工作台 | 网格+可拖拽分区 | 等宽数字信息密 | 中性灰，色只给状态 | 操作即时内联反馈 |
- **品牌豁免**（仅既定品牌时填）：被排除的方向 <__> · 理由 <__>
- **人工批准记录**：产品负责人 于 2026-09-08 批准 方向 A 作为视觉命题

| SAFE-1 | 沿用网格缩略图 | 品类惯例，用户肌肉记忆在这 |
| SAFE-2 | 左侧栏常驻导航 | 桌面工具的 table stakes |

**RISK-1**
是什么：全产品只有一个信号色，且只用于自生长。
为何成立：照片本身是唯一该有颜色的东西。
得到什么：功能入口在满屏照片里仍然一眼可见。
代价：一旦泛用整条逻辑崩塌，且不会有人报警。

**RISK-2**
是什么：界面有两个音量——静默态与显形态。
为何成立：浏览时界面该消失，操作时该出现。
得到什么：照片保真与功能可见性同时成立。
代价：每个组件要定义两套音量，工作量近翻倍。
"""

def _run_sweep():
    """三方向登记表的构造空间穷举（说明见 _sweep_lib.sweep_direction_table）。"""
    import tempfile as _tf, shutil as _sh, subprocess as _sp, io as _io, re as _re
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_direction_table, report as _rep
    _fx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'tests', 'fixtures', 'filled', 'design-brief.md')
    if not os.path.exists(_fx):
        print("  ➖ 三方向表穷举：找不到官方夹具 —— **本条没验**（不是通过）")
        return True
    _b = _tf.mkdtemp(prefix='di-sweep-')

    def _flag(_p):
        _o = _sp.run([sys.executable, os.path.abspath(__file__), _p],
                     capture_output=True, text=True).stdout
        return bool(_re.search(r'❌ \[direction-table\]', _o))

    _n, _bad = sweep_direction_table(_flag, _io.open(_fx, encoding='utf-8').read(), _b)
    _sh.rmtree(_b, ignore_errors=True)
    return _rep('三方向登记表', _n, _bad)


def self_test():
    t = tempfile.mkdtemp(prefix="dig-")
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(p): return subprocess.call([sys.executable, os.path.abspath(__file__), p],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    TG = GOOD.split('**RISK-1**')[0] + """
| # | 是什么 | 为何成立 | 得到什么 | **代价是什么** |
|---|---|---|---|---|
| RISK-1 | 全产品一个信号色 | 照片是唯一该有颜色的东西 | 入口在满屏照片里可见 | 泛用即崩且无人报警 |
| RISK-2 | 界面两个音量 | 浏览时消失操作时出现 | 保真与可见同时成立 | 每组件两套音量，工作量近翻倍 |
"""
    # ⭐ 另一种合法写法：RISK 用表格写。夹具此前只有散文式。
    GOOD_TABLE = GOOD.replace('**RISK-1**\n是什么：全产品只有一个信号色，且只用于自生长。\n为何成立：照片本身是唯一该有颜色的东西。\n得到什么：功能入口在满屏照片里仍然一眼可见。\n代价：一旦泛用整条逻辑崩塌，且不会有人报警。\n\n**RISK-2**\n是什么：界面有两个音量——静默态与显形态。\n为何成立：浏览时界面该消失，操作时该出现。\n得到什么：照片保真与功能可见性同时成立。\n代价：每个组件要定义两套音量，工作量近翻倍。', '| ID | 是什么 | 为何成立 | 得到什么 | 代价 |\n|---|---|---|---|---|\n| RISK-1 | 全产品一个信号色 | 照片是唯一该有颜色的东西 | 入口在满屏照片里仍一眼可见 | 泛用即崩且无人报警 |\n| RISK-2 | 界面有两个音量 | 浏览时界面该消失，操作时该出现 | 保真与可见性同时成立 | 每个组件要定义两套音量 |')
    assert GOOD_TABLE != GOOD, '夹具替换没生效 —— 反例会与正例逐字相同'
    cases = [
        ("正例（分块式）", GOOD, 0),
        ("正例（表格式·真实写法）", TG, 0),
        ("反例 表格填了但格子留空", TG.replace("泛用即崩且无人报警", ""), 1),
        ("反例 表格仍是 <占位>", TG.replace("全产品一个信号色", "<是什么>"), 1),
        ("反例 缺 Design Read", re.sub(r'\*\*Design Read\*\*.*\n', '', GOOD), 1),
        # ⭐ 2026-09-04：官方模板把 Design Read 的内容放在**下一行**
        #    （`### 1. Design Read（一句话）` / `> 我把这个读作：…`），
        #    而同一行判据让**模板自己永远过不了这道门**。两个方向都要测：
        ("正例 Design Read 内容在下一行（官方模板就是这个形状）",
         re.sub(r'\*\*Design Read\*\*[^\n]*', 
                "### 1. Design Read（一句话）\n> 我把这个读作：给工程师的本地只读诊断面板，克制，倾向开发者工具那一路。",
                GOOD, count=1), 0),
        # 🚨 反向：下一行**仍是占位符**时必须红 —— 放宽不许把原病放回来
        ("反例 下一行仍是 <占位>（放宽不许把原病放回来）",
         re.sub(r'\*\*Design Read\*\*[^\n]*',
                "### 1. Design Read（一句话）\n> 我把这个读作：给 <谁> 的 <什么产品>，<什么调性>。",
                GOOD, count=1), 1),
        ("反例 缺 memorable-thing", re.sub(r'\*\*Memorable-thing\*\*.*\n', '', GOOD), 1),
        ("正例 只有 1 条 RISK 提案（提案≠配额，1 条合法）", GOOD.split('**RISK-2**')[0], 0),
        ("反例 0 RISK 且没写零突破理由", GOOD.split('**RISK-1**')[0], 1),
        ("正例 0 RISK 但写明理由（合规工具零突破合法）",
         GOOD.split('**RISK-1**')[0] + "\n为何没有值得评估的突破：金融合规工具，可用性与信任压倒差异化。\n", 0),
        # 🚨 2026-09-09 实测坐实的假阳性：SOP 五处只说「零提案须写理由」，
        #    照做的人写的是下面这种自然措辞，而判据只认模板那一句 ⇒ 正确产物被判红。
        ("正例 0 RISK·自然措辞理由（SOP 只说「写理由」，门不许只认一种说法）",
         GOOD.split('**RISK-1**')[0] + "\n本轮零 RISK 提案，理由：严格品牌约束，集团 VI 已锁定主色与字体。\n", 0),
        ("反例 0 RISK·自然措辞但理由是空的（放宽措辞≠提一句就算数）",
         GOOD.split('**RISK-1**')[0] + "\n本轮零 RISK 提案，理由：\n", 1),
        ("反例 0 RISK·自然措辞但理由是占位符",
         GOOD.split('**RISK-1**')[0] + "\n本轮零 RISK 提案，理由：<写清为什么>\n", 1),
        ("反例 缺三方向登记表（也无品牌豁免）",
         GOOD.replace(GOOD[GOOD.index('## 三个视觉方向登记表'):GOOD.index('- **人工批准记录**')], ''), 1),
        ("反例 两方向四格全同（只是换皮不算方向）",
         GOOD.replace('| 方向 B 图书馆 | 左栏索引+右侧大图 | 衬线标题混排 | 暖白纸感，投影分层 | 固定操作列常显 |',
                      '| 方向 B 图书馆 | 满屏瀑布流，Z 型扫读 | 无衬线细字重，层级靠字号 | 近黑底，照片自发光 | 悬浮工具条淡入 |'), 1),
        ("反例 无人工批准记录（没被批准的方向不算锁）",
         GOOD.replace('- **人工批准记录**：产品负责人 于 2026-09-08 批准 方向 A 作为视觉命题', ''), 1),
        ("正例 既定品牌豁免路径",
         GOOD.replace(GOOD[GOOD.index('| 方向 A'):GOOD.index('- **品牌豁免**')], '')
             .replace('- **品牌豁免**（仅既定品牌时填）：被排除的方向 <__> · 理由 <__>',
                      '- **品牌豁免**：被排除的方向 暗房系 · 理由 集团 VI 强约束，仅允许官方蓝白体系'), 0),
        ("反例 RISK 缺「代价」", GOOD.replace('代价：一旦泛用整条逻辑崩塌，且不会有人报警。', ''), 1),
        # 🆕🆕 2026-09-05：本门支持 RISK 的**两种合法写法**（散文式 / 表格式），
        #    而夹具**只有散文式** —— `if risk_rows:` 整个分支（含「列数不足」那条判据）
        #    **一次都没执行过**。变异扫描说这道门「五条判据全有反例守着」，
        #    因为它按**规则**置真；而这是规则内部的分支，从没被走到。
        #    ⭐ **补的不是反例，是另一种合法写法的正例** —— 缺了它，
        #    「只支持其中一种」不会被任何东西发现。
        ("正例 RISK 用表格式写（另一种合法写法）", GOOD_TABLE, 0),
        ("反例 表格式里某行列数不足（四要素不全）",
         GOOD_TABLE.replace(
             '| RISK-1 | 全产品一个信号色 | 照片是唯一该有颜色的东西 | 入口在满屏照片里仍一眼可见 | 泛用即崩且无人报警 |',
             '| RISK-1 | 全产品一个信号色 | 照片是唯一该有颜色的东西 |'), 1),
        ("反例 SAFE 只有 1 条", GOOD.replace('| SAFE-2 | 左侧栏常驻导航 | 桌面工具的 table stakes |', ''), 1),
        ("反例 仍是模板占位", GOOD.replace('我把这个读作：给重度囤图用户的桌面相册，克制的工具调性，倾向瑞士平面体系。', '<谁> 的 <什么产品>'), 1),
    ]
    ok = True
    print("M8 自证 —— 正例绿 / 每类缺失各造一个反例必红 / 无效输入报 2\n")
    for n, body, want in cases:
        got = run(w(re.sub(r'\W+', '_', n) + '.md', body)); g = got == want; ok &= g
        print("  %s %-26s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, got))
    got = run(os.path.join(t, 'nope.md')); g = got == 2; ok &= g
    print("  %s %-26s 期望 2 实得 %d" % ("✅" if g else "❌", "文件不存在", got))
    # 🆕 2026-09-05 `unexecuted-check --unable` 实测：本门有三个「跑不了」出口，
    #    而自证只触发过第一个（不存在）。另两个**从没被证明会出声**：
    #    ⭐ 「读不到就报 UNABLE」这类守卫锚点写错时会**两头都不出声** ——
    #    既不报「没跑过」也不报缺陷，比漏判更隐蔽。（形状由并行会话 peer-agent-c0 提出。）
    _d = os.path.join(t, 'adir'); os.makedirs(_d, exist_ok=True)
    got = run(_d); g = got == 2; ok &= g
    print("  %s %-26s 期望 2 实得 %d" % ("✅" if g else "❌", "传的是目录 → 报 2", got))
    # `not isfile` 那条守的是「存在、不是目录、也不是普通文件」—— fifo/设备文件。
    # 不是死代码，只是罕见；`os.mkfifo` 能真的把它测出来。
    _f = os.path.join(t, 'afifo')
    try:
        os.mkfifo(_f)
        got = run(_f); g = got == 2; ok &= g
        print("  %s %-26s 期望 2 实得 %d" % ("✅" if g else "❌", "传的是 fifo → 报 2", got))
    except (OSError, AttributeError):
        print("  ⏭️  %-26s 本平台建不了 fifo，跳过（不计入通过）" % "fifo 出口")
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败"))
    ok = _run_sweep() and ok      # 穷举结果并入结论
    return 0 if ok else 1


# ── 意外异常必须报「跑不了」，不许和「有发现」共用退出码 ────────────────
# 🚨 2026-09-05 实测：喂一个坏 JSON 给本门，得到 **rc=1 + Traceback** ——
#    **崩溃与「发现缺陷」在退出码上完全一样**。后果有两层：
#    ① 报告里它长成「有发现」，把人送去查一个不存在的缺陷；
#    ② 自证里只看退出码的反例，**崩溃会被读成「反例红了」**。
#    （形状由并行会话 peer-agent-c0 提出，它那边是「反例对象被别的判据消费 ⇒ KeyError」。）
# ⛔ `except Exception` 不捕获 `SystemExit`，所以门禁自己的 exit(0/1/2) 不受影响。
def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 门禁自身异常（不是「有发现」）：%s: %s"
              % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    def _entry():
            if '--self-test' in sys.argv: sys.exit(self_test())
            # ⚠️ 未知 `--flag` 必须报错：静默丢弃会让门禁只跑一半而照样报绿（见 _argv.py）
            import os as _os, sys as _sys
            _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
            from _argv import reject_unknown
            reject_unknown({'--json', '--self-test'},
                "本门禁用位置参数：design-intent-gate.py <文件或目录>")
            a = [x for x in sys.argv[1:] if not x.startswith('--')]
            sys.exit(check(a[0]) if a else (print(__doc__) or 2))
    _main_guarded(_entry)
