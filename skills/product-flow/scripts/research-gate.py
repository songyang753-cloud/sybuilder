#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S2 行业研究出场门禁。

为什么需要它：
  S2/S3 是**唯一决定「做什么」的两个阶段**，也曾是**唯一零门禁的两个阶段**——
  出场条件全是人勾的 checklist。而本 skill 自己的判词是：
  「模板末尾那份自检清单是人勾的……**清单挡不住任何东西，门禁才挡得住**。」
  这句话对 PRD 成立，对 S2 一样成立。研究不实，后面每一步都建在沙子上。

判据（全部来自 s2-research.md 的交付契约）：
  1. 竞品档案 ≥8 家（research/ 下每家一份 .md，排除 matrix/sources/README）
  2. 每份档案有可回溯来源：URL + 访问日期
  3. 有反面样本（做过同类但失败/砍掉的）——最有价值也最容易被整类漏掉
  4. matrix.md 存在，且**没有空格子**（拿不到要显式标「未获取」，不许留空、不许推测填）
  5. sources.md 存在且每条带日期
  6. 全库不得出现「据我所知 / 一般来说 / 业界一般都这么做」——编造在研究阶段的典型形态
  7. 竞品双轴全景、公共维度矩阵、AI 适用性、关键流程图源齐备
 8. 学习/借鉴/规避/差异化与机会优先级有明确结论
 9. PRD/Figma/HTML 双向覆盖、CLM 主张状态与时效可追溯
10. 深挖对象有 RUN 实测回执；通道、结果标签、授权、证据与阻断语义一致
 11. 原子功能词典字段齐；每个 AF × 正式 COMP 恰好一条事实，状态与证据语义一致
 12. 横向面板复用同一 AF 行集；每个 AF 都有 PRD/Figma/HTML 去向
 13. 每个 RUN 的功能遍历覆盖账可解析；每个界面发现都有 AF/NON-FEATURE/BLOCKED 处置，
     且 FULL/PARTIAL 事实可反查同竞品、同 RUN 的界面发现，防止 AF 全集静默漏项

用法: research-gate.py <research 目录> [--json]   |   --self-test
退出码: 0=通过 1=不通过 2=跑不了
"""
import io, os, re, sys, json, glob, tempfile, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at   # noqa: E402  段落定位的唯一正本

FABRICATED = re.compile(r'据我所知|一般来说|业界一般|通常都是这样|应该都有')
DATE = re.compile(r'20\d{2}[-/年]\s?\d{1,2}[-/月]\s?\d{1,2}')
URL = re.compile(r'https?://')
NEG = re.compile(r'反面样本|失败案例|已下线|已砍掉|停止维护|退出市场')
META = {'matrix.md', 'sources.md', 'readme.md', 'index.md', 'lines.md', 'insights.md',
        's2-decision-domains.md', 'decision-domains.md',
        'research-decision-ledger.md', 'scope.md', 'competitor-landscape.md',
        'atomic-feature-ledger.md', 'key-flows.md', 'downstream-coverage.md',
        'conflicts.md', 'prd-isomorphic.md', 'market-landscape.md',
        # 2026-09-15 新契约产出物（⛔ 不是竞品档案，别被当成一家竞品数进分母）
        'design-tokens.md', 'state-coverage.md', 'field-specs.md',
        'innovation-trends.md', 'differentiation.md',
        # 2026-09-17：截图目检记录是**流程元文件**，不是竞品档案。
        # ⛔ 不加进来的话，traceable 会要求它带竞品 URL —— 门在惩罚一份正确的产物。
        'screenshot-masking-audit.md'}

# 五条研究线（2026-08-31 重做 S2 时加）——只做竞品一条线的研究，
# 交给 S3 的是「别人怎么做的」，而不是「该做什么」。
LINES = {"user": "① 用户线", "competitor": "② 竞品线", "market": "③ 市场线",
         "data": "④ 数据线", "tech": "⑤ 技术可能性线"}

# ⭐ UNABLE 哨兵 —— 与 None 严格区分。
#   None  = N/A（这条判据在本产物上不适用，合法放行，不进分母）
#   UNABLE= 没验成（缺输入/认不出结构）⇒ **退 2，不许当通过**（本仓 P6）
UNABLE = 'UNABLE'


def check(d):
    if not os.path.isdir(d):
        print("UNABLE: 不是目录 %s" % d, file=sys.stderr); sys.exit(2)
    # ⚠️ 竞品档案 = 目录里除元文件与**定向报告**之外的 md。
    #    首版忘了排除三份定向报告，于是门禁要求「功能调研报告.md」里也要有竞品 URL —— 正例被判红。
    REPORT_RE = re.compile(r'(功能|设计视觉|设计|交互)[^/]*调研报告')
    files = [p for p in glob.glob(os.path.join(d, '*.md'))
             if os.path.basename(p).lower() not in META
             and not REPORT_RE.search(os.path.basename(p))]
    res, all_text = [], ""
    def add(rid, desc, ok, ev): res.append({"id": rid, "desc": desc, "ok": ok, "ev": ev})
    def read(name):
        p = os.path.join(d, name)
        return io.open(p, encoding='utf-8', errors='replace').read() if os.path.isfile(p) else ''

    # ⚠️ 2026-09-08（终局规格 3-3）：8 是**默认值**不是普适硬门 ——
    #   scope.md 可声明「竞品数下限 N · 理由」（垂直领域全球只有 4 家是常态）；
    #   有声明按声明判（理由必须非空），无声明按默认判。**静默低于默认才是缺陷。**
    floor, floor_src = 8, "默认"
    import glob as _g
    for sc in (_g.glob(os.path.join(d, '..', 'scope.md'))
               + _g.glob(os.path.join(d, '..', '.product-flow', 'scope.md'))
               + _g.glob(os.path.join(d, 'scope.md'))):
        _m = re.search(r'竞品数下限\s*[:：]?\s*(\d+)\s*[·,，]\s*理由\s*[:：]?\s*(\S.{2,})', io.open(sc, encoding='utf-8').read())
        if _m:
            floor, floor_src = int(_m.group(1)), "scope.md 声明（理由：%s）" % _m.group(2)[:30]
            break
    add("count", "竞品档案 ≥ 下限（默认 8；scope.md 可声明调整并给理由）",
        len(files) >= floor, "实得 %d 家，下限 %d（%s）" % (len(files), floor, floor_src))

    # 3-2：下游决策域清单（12 域三态 standing，无空格）—— 「高于下游」的对照物
    dd = None
    for cand in ('s2-decision-domains.md', 'decision-domains.md'):
        cp = os.path.join(d, cand)
        if os.path.isfile(cp): dd = io.open(cp, encoding='utf-8').read(); break
    if dd is None:
        for cand in _g.glob(os.path.join(d, '*.md')):
            _t = io.open(cand, encoding='utf-8').read()
            if '下游决策域清单' in _t: dd = _t; break
    if dd is None:
        add("decision-domains", "下游决策域清单（12 域三态 standing）存在", False,
            "没有 —— 「覆盖并高于下游」没有对照物就只是口号（模板见 s2-research.md 〇之〇）")
    else:
        # 🚨 2026-09-09 三轮复核：`find` 找不到时返回 -1，切片变成「取最后一个字符」 ——
        #   而文件是**按文件名** decision-domains.md 命中的，从不保证正文含这个短语。
        #   实测：文件名正确、12 域全填好，只因标题写作「# 决策域清单」→ 判「只有 0 行」。
        #   ⭐ 两个选择器两套契约，失败方式是**静默量错对象**。⇒ 找不到就从头扫全文。
        # 🚨 2026-09-09 第五轮：起点仍是全文首次出现（且**切到 EOF**）——
        #   复核实测：3 个真域 + 文末一张 10 行竞品表 ⇒ 报「14 域全部 standing」。
        #   ⇒ 锚定标题；取不到再退回全文（保留上面那条「找不到就从头扫」的意图）。
        _sec = section_at(dd, '下游决策域清单')
        rows = [l for l in (dd if _sec is None else _sec).split('\n')
                if l.strip().startswith('|')]
        data = [r for r in rows[2:] if r.replace('|', '').replace('-', '').strip()]
        # 🚨 2026-09-09 修（⚠️ 本注释 09-09 晚经独立复核**订正过一次**，原文把病因
        #   写成「真实产物是两列，这条判据从上线起从未生效」——**那是错的**：
        #   SOP 模板 `s2-research.md` 〇之〇 给的就是三列 `| # | 决策域 | standing |`，
        #   旧判据在三列上确实生效。真实情况是**量程只覆盖三列**：两列（`| 域 | standing |`
        #   两端 strip 后只有 2 段）整条漏检，四列（多一个备注列）则会误伤。
        #   ⭐ 记这一笔是因为**错误的病因注释会变成常驻错误记录**，
        #   下一个读它的人（包括半年后的我）会据此得出错误结论。）
        #   ⚠️ standing 列**按表头名定位**，不按位置。三次教训叠在这一行上：
        #     ①原判据取固定索引 [1]/[2] 且要求 ≥3 段 —— 对两列表格整条失效；
        #     ②改「取最后一列」后，四列表（`| # | 域 | standing | 备注 |`）里
        #       备注列空 ⇒ **完全填对的产物被判红**，且报错点名的是 standing 的值
        #       而不是域名（2026-09-09 独立复核实测揪出）；
        #     ③⭐ 位置型定位无论钉哪一头都只对一种形状成立 —— 认表头才是不变量。
        #   找不到 standing 表头时退回「最后一列」，并在证据里说明是按位置判的。
        _hdr = [re.sub(r'[`*\s]', '', c) for c in rows[0].strip().strip('|').split('|')] \
            if rows else []
        # 🚨 2026-09-09 二轮复核：只认 ASCII 字面量 `standing` ⇒ **本地化表头
        #   （`| # | 决策域 | 状态 | 备注 |`）上原假阳性逐字复现**——12 行全填，
        #   它却点名「域1、域2、域3 空」。⇒ 中英两种写法都认。
        # 🚨 2026-09-09 三轮复核：闭集 {'状态','覆盖状态','结论'} 之外立刻退化回位置型 ——
        #   表头写「当前状态」(完全自然的中文)，原假阳性**逐字复现**，连点名的对象都一样。
        #   ⭐ 我自己的注释写着「认表头才是不变量」，而闭集不是不变量，是另一个字面量表。
        #   ⇒ 改**子串匹配**：含「状态/standing/结论/覆盖」的表头都认。
        _cells0 = [[c.strip() for c in r.strip().strip('|').split('|')] for r in data]
        _si = next((k for k, h in enumerate(_hdr)
                    if 'standing' in h.lower()
                    or any(w in h for w in ('状态', '结论', '覆盖'))), None)
        if _si is None:
            # 🚨 2026-09-09 **自攻**：表头词表扩得再大也永远差一个 ——
            #   「填写状况 / 进展 / 调研结果 / completeness」四种自然写法一步即漏。
            #   ⭐ 词表不是不变量，**列里装的是什么**才是。
            #   ⇒ 退回按内容识别：三态值（有输入/明确未知/N/A）出现最多的那一列就是它。
            # 🚨 2026-09-09 第五轮独立复核：`N/?A` 带 re.I 且**无词边界** ——
            #   它匹配任意英文里的「na」（analysis / signal / Nasdaq / banana）。
            #   实证：备注列写「见 final analysis 报告」就**抢走 standing 列的身份**，
            #   于是 standing 列 12 行全空，门照样打印「12 域全部 standing」。
            #   ⭐ 这是第四轮声称已消除的那个假绿 —— 上次堵的是「按位置退回」，
            #     没堵「按内容认错列」，同一个假绿换条路径逐字复现。
            #   ⇒ 英文缩写加词边界。同一天在 definition-gate 的 DEFER_ANY 上
            #     发现**同一个缺陷**（它把 Professional 判成了「还没答」）。
            _TRI = re.compile(r'有输入|明确未知|未知|不适用|已覆盖|未覆盖|'
                              r'(?<![A-Za-z])N/?A(?![A-Za-z])', re.I)
            _score = {}
            for _c in _cells0:
                for _k, _v in enumerate(_c):
                    if _TRI.search(_v or ''):
                        _score[_k] = _score.get(_k, 0) + 1
            if _score:
                _si = max(_score, key=_score.get)
        # 域名列同理：含「域」即可（决策域/下游域/域）；找不到就取 standing 左边一列
        _ni = next((k for k, h in enumerate(_hdr) if '域' in h), None)
        if _ni is None and _si is not None and _si > 0:
            _ni = _si - 1
        _cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in data]
        def _val(c, idx, fallback):
            return c[idx] if (idx is not None and len(c) > idx) else fallback
        # 🚨 2026-09-09 第五轮独立复核，三处一起修：
        #   ①**占位符全算「填了」**：`-` `TBD` `TODO` `<待填>` `待补充` `延后到 S3`
        #     `/` `见下文` 八种实测全绿。⭐ 更刺眼的是**同一份代码里契约不一致** ——
        #     下面 insight-ledger 那条**检查了** `startswith('<')`，这条没有。
        #   ②**单格行计入 12 却不查空值**：`len(c) >= 2` 把只有一格的行排除在空值检查外，
        #     而它们照样进 `len(data)` ⇒ 12 行 `| 域N |`（根本没有 standing 格）
        #     报「12 域全部 standing」。⛔ 「查不了这一行」被当成了「这一行没问题」。
        #   ③**域名不验**：12 行域名全填 `?`、或 12 行完全复制同一行，照样绿。
        _PLACEHOLD = re.compile(r'^(?:-+|—+|/+|\.+|\?+|TBD|TODO|N/?A\s*$|<[^>]*>|'
                                r'待[定填补]\w{0,3}|待补充|见下文|见上|同上|略|空|'
                                r'延后\w{0,6}|后续\w{0,6})$', re.I)

        def _blank(v):
            v = (v or '').strip().strip('*`')
            return (not v) or bool(_PLACEHOLD.match(v))

        empty = [(_val(c, _ni, c[-2] if len(c) >= 2 else c[0]) or '?')[:16]
                 for c in _cells
                 if len(c) <= _si or _blank(_val(c, _si, ''))]
        # ③域名列：不许全是占位、也不许 12 行同一个名字（复制粘贴凑数）
        _names = [(_val(c, _ni, '') or '').strip() for c in _cells] if _ni is not None else []
        _real_names = [n for n in _names if not _blank(n)]
        _dup = bool(_names) and len(set(_real_names)) < max(1, len(_names) // 2)
        if _dup:
            empty = empty or ['域名列凑数（%d 行只有 %d 个不同的域名）'
                              % (len(_names), len(set(_real_names)))]
        # ⛔ 逐域数满 12，消息报实数 —— 曾经 len>=10 就打印「12 域全部 standing」，
        #   10 行也宣布 12 域全过（Codex 复审抓出的「声称≠实现」，正是本仓母题）
        # ⚠️ 2026-09-09 二轮复核：注释承诺过「找不到 standing 表头时退回最后一列，
        #   **并在证据里说明是按位置判的**」——而**没有任何代码写那句话**，
        #   两种情况的证据串一模一样。⭐ 在一个母题是「声称≠实现」的仓里，
        #   这正是注释比实现多说了一句。⇒ 现在真的说出来。
        # 🚨🚨 2026-09-09 第四轮独立复核揪出的**假绿**（比假阳性危险得多）：
        #   表头认不出（如「进展」）且 standing 列**一格都没填**时，内容识别评分为零，
        #   于是退回「最后一列」，而最后一列（备注）填着「无」⇒
        #   **一份一格没填的清单，门报「12 域全部 standing」**。
        #   ⭐ 「判不出来」被折叠成了「判过了」—— 本仓 P6（UNABLE≠通过）的直接违反。
        #   ⇒ 定位不到 standing 列时**一律 UNABLE**（None），⛔ 不猜、不退回位置。
        if _si is None:
            add("decision-domains", "决策域清单 12 域齐且无空格（三态都算填）", UNABLE,
                "UNABLE：表头里找不到 standing/状态列，列内容也认不出三态值"
                "（有输入/明确未知/N/A）—— **本条没验**。"
                "⛔ 不按位置猜：猜错方向会把「一格没填」报成「全部 standing」。"
                "⇒ 表头写成含「状态/standing/结论/覆盖」之一，或按模板填三态值")
        else:
            add("decision-domains", "决策域清单 12 域齐且无空格（有输入/明确未知/N/A+理由 三态都算填）",
                len(data) >= 12 and not empty,
                ("standing 空格：%s" % "、".join(empty[:3])) if empty else
                ("只有 %d 行（应 12 域）" % len(data) if len(data) < 12
                 else "%d 域全部 standing" % len(data)))

    # 3-1：洞察账本存在且每条 INS 有强度+边界+下游目标
    lg = None
    for cand in (os.path.join(d, 'research-decision-ledger.md'),
                 os.path.join(d, '..', 'research-decision-ledger.md')):
        if os.path.isfile(cand): lg = io.open(cand, encoding='utf-8').read(); break
    if lg is None:
        add("insight-ledger", "洞察账本 research-decision-ledger.md 存在", False,
            "没有 —— 高强度洞察的处置将无从核对（G7.5 会红）")
    else:
        badl = []
        for m2 in re.finditer(r'### (INS-\d+)(.*?)(?=### INS-|\Z)', lg, re.S):
            body = m2.group(2)
            for fld in ('强度', '适用边界', '下游目标'):
                fm = re.search(fld + r'[：:]\s*(\S.*)', body)
                if not fm or fm.group(1).strip().startswith('<'):
                    badl.append('%s 缺 %s' % (m2.group(1), fld))
        add("insight-ledger", "账本每条 INS 有强度/适用边界/下游目标",
            not badl, badl[:4] or "全部齐")

    no_src = []
    for p in files:
        t = io.open(p, encoding='utf-8', errors='replace').read(); all_text += t
        if not (URL.search(t) and DATE.search(t)):
            no_src.append(os.path.basename(p))
    add("traceable", "每份档案有 URL + 访问日期（可回溯）",
        not no_src and bool(files), no_src or "全部可回溯")

    add("negative", "有反面样本（做过同类但失败/砍掉的）",
        bool(NEG.search(all_text)), "找到" if NEG.search(all_text) else
        "未找到——找不到也要写『已检索 X 关键词未找到公开失败案例』，不许整类跳过")

    mp = os.path.join(d, 'matrix.md')
    if not os.path.exists(mp):
        add("matrix", "横向矩阵 matrix.md 存在且无空格子", False, "matrix.md 不存在")
        mt = ''
    else:
        mt = io.open(mp, encoding='utf-8', errors='replace').read()
        empties = []
        for i, ln in enumerate(mt.split('\n'), 1):
            if not ln.strip().startswith('|') or re.match(r'^\s*\|[\s\-:|]+\|\s*$', ln): continue
            cells = [c.strip() for c in ln.strip().strip('|').split('|')]
            if any(c == '' for c in cells[1:]): empties.append("第 %d 行" % i)
        add("matrix", "横向矩阵无空格子（拿不到要显式标『未获取』，不许留空也不许推测填）",
            not empties, empties or "无空格子")

    # ── 竞品双轴全景：竞争关系回答「怎么争」，样本角色回答「为什么研究」──
    landscape = read('competitor-landscape.md')
    if not landscape:
        add("competitive-landscape", "competitor-landscape.md 有竞争关系 × 样本角色双轴", False,
            "缺 competitor-landscape.md")
    else:
        # ⚠️ 只量**表格行**：双轴是登记表的属性。正文里「OpenClaw（COMP-13）是上游而非同层」
        # 这类解释句引用编号完全正当，拿它去查双轴是**量错了对象** —— 判据会逼正文不许提编号。
        # ⛔ 收窄的是量程对象，不是标准：表里每一行照旧逐行查，且一行都没有仍判红（fail-closed）。
        comp_rows = [ln for ln in landscape.splitlines()
                     if ln.lstrip().startswith('|')
                     and re.search(r'(?<![A-Z])COMP-\d+(?!\d)', ln)]
        bad_axis = [ln[:48] for ln in comp_rows
                    if not re.search(r'直接|间接|替代|潜在进入', ln)
                    or not re.search(r'品类头部|直接对手|越级参照|反面样本', ln)]
        relation_classes = ('直接竞品', '间接竞品', '替代方案', '潜在进入者')
        sample_roles = ('品类头部', '直接对手', '越级参照', '反面样本')
        missing_classes = [x for x in relation_classes + sample_roles if x not in landscape]
        ok_landscape = bool(comp_rows) and not bad_axis and not missing_classes
        evidence = []
        if not comp_rows: evidence.append("没有实写 COMP-数字 行（模板 COMP-xx 不算）")
        if bad_axis: evidence.append("双轴未填齐：%s" % "；".join(bad_axis[:2]))
        if missing_classes: evidence.append("类别未交代：%s" % "、".join(missing_classes))
        add("competitive-landscape", "竞品双轴全景齐备（直接/间接/替代/潜在 × 头部/对手/越级/反面）",
            ok_landscape, evidence or "%d 个 COMP 均有双轴；八类均有对象或未发现说明" % len(comp_rows))

    # ── 原子功能账本：功能先拆到最小可独立验收单元，再用同一 AF 全集横向对账 ──
    # 形状采用「词典 + AF×COMP 长表 + 横向面板 + 下游映射」。宽表只是投影，
    # 长表才是事实正本；这样 8–12 家竞品在飞书里拆列时不会静默删功能行。
    atomic = read('atomic-feature-ledger.md')
    _atomic_placeholder = re.compile(
        r'^(?:|[-—/]+|TBD|TODO|<[^>]*>|待\S*|未填|同上|略|\?|\.\.\.)$', re.I)

    def _atomic_blank(value):
        return bool(_atomic_placeholder.match((value or '').strip().strip('*`')))

    def _table_in_section(text, heading, required):
        """返回 heading 小节中第一张命中所需表头的表；认语义表头，不认固定列位。"""
        sec = section_at(text, heading) if text else None
        if sec is None:
            return [], []
        lines = sec.splitlines()
        for i, ln in enumerate(lines):
            if not ln.strip().startswith('|'):
                continue
            headers = [re.sub(r'[`*\s]', '', c).lower()
                       for c in ln.strip().strip('|').split('|')]
            if not all(any(re.search(pat, h, re.I) for h in headers) for pat in required):
                continue
            rows = []
            for row in lines[i + 1:]:
                if not row.strip().startswith('|'):
                    if rows:
                        break
                    continue
                if re.match(r'^\s*\|[\s\-:|]+\|\s*$', row):
                    continue
                cells = [c.strip() for c in row.strip().strip('|').split('|')]
                if len(cells) == len(headers):
                    rows.append(cells)
            return headers, rows
        return [], []

    def _col(headers, *patterns):
        return next((i for i, h in enumerate(headers)
                     if any(re.search(pat, h, re.I) for pat in patterns)), None)

    # 正式比较对象只取同时含竞争关系与样本角色的 COMP 行；计划/回执里提及的 COMP 不扩分母。
    formal_comp_ids = sorted({m.group(0) for ln in landscape.splitlines()
                              if re.search(r'直接|间接|替代|潜在进入', ln)
                              and re.search(r'品类头部|直接对手|越级参照|反面样本', ln)
                              for m in [re.search(r'(?<![A-Z])COMP-\d+(?!\d)', ln)] if m})

    dict_headers, dict_rows = _table_in_section(
        atomic, '功能分解词典',
        (r'^af$', r'功能路径', r'层级深度', r'父节点', r'^l0', r'^l1', r'^l2', r'角色', r'场景|入口|触发', r'对象|输入',
         r'前置|规则', r'单一动作', r'状态变化', r'可观察结果|完成定义', r'独立验收|拆分说明'))
    dict_cols = {
        'af': _col(dict_headers, r'^af$'), 'path': _col(dict_headers, r'功能路径'),
        'depth': _col(dict_headers, r'层级深度'), 'parent': _col(dict_headers, r'父节点'),
        'l0': _col(dict_headers, r'^l0'),
        'l1': _col(dict_headers, r'^l1'), 'l2': _col(dict_headers, r'^l2'),
        'actor': _col(dict_headers, r'角色'), 'trigger': _col(dict_headers, r'场景', r'入口', r'触发'),
        'object': _col(dict_headers, r'对象', r'输入'), 'rule': _col(dict_headers, r'前置', r'规则'),
        'action': _col(dict_headers, r'单一动作'), 'transition': _col(dict_headers, r'状态变化'),
        'result': _col(dict_headers, r'可观察结果', r'完成定义'),
        'split': _col(dict_headers, r'独立验收', r'拆分说明'),
    }
    dict_missing_cols = [k for k, v in dict_cols.items() if v is None]
    bad_dict, af_ids = [], []
    if dict_headers and not dict_missing_cols:
        for cells in dict_rows:
            m_af = re.fullmatch(r'`?AF-\d+`?', cells[dict_cols['af']].strip(), re.I)
            if not m_af:
                continue
            af = re.search(r'AF-\d+', cells[dict_cols['af']], re.I).group(0).upper()
            af_ids.append(af)
            missing = [k for k, idx in dict_cols.items() if _atomic_blank(cells[idx])]
            if missing:
                bad_dict.append('%s 缺 %s' % (af, '/'.join(missing)))
            if not re.search(r'→|->', cells[dict_cols['transition']]):
                bad_dict.append('%s 状态变化缺 from→to' % af)
    dup_af = sorted({x for x in af_ids if af_ids.count(x) > 1})
    if dup_af:
        bad_dict.append('AF 重复：%s' % '、'.join(dup_af))
    add('atomic-dictionary', 'atomic-feature-ledger 有原子词典；每个 AF 的角色/触发/对象/规则/单一动作/状态变化/结果/拆分说明齐备',
        bool(atomic) and bool(af_ids) and not dict_missing_cols and not bad_dict,
        ((['缺表头列：%s' % '、'.join(dict_missing_cols)] if dict_missing_cols else [])
         + bad_dict[:6] or ['%d 个 AF 的原子字段齐备' % len(af_ids)]))

    fact_headers, fact_rows = _table_in_section(
        atomic, '原子功能事实账',
        (r'^af$', r'^comp$', r'状态', r'入口|触发', r'字段|参数|默认值', r'规则|前置',
         r'状态变化', r'结果|反馈|文案', r'失败|恢复', r'权限|端|档位|限额',
         r'质量|效率|用户代价', r'证据标签|日期', r'run|clm', r'差异判读|can.t|won.t'))
    fact_cols = {
        'af': _col(fact_headers, r'^af$'), 'comp': _col(fact_headers, r'^comp$'),
        'state': _col(fact_headers, r'状态'), 'trigger': _col(fact_headers, r'入口', r'触发'),
        'params': _col(fact_headers, r'字段', r'参数', r'默认值'),
        'rule': _col(fact_headers, r'规则', r'前置'), 'transition': _col(fact_headers, r'状态变化'),
        'result': _col(fact_headers, r'结果', r'反馈', r'文案'),
        'recovery': _col(fact_headers, r'失败', r'恢复'),
        'scope': _col(fact_headers, r'权限', r'档位', r'限额'),
        'quality': _col(fact_headers, r'质量', r'效率', r'用户代价'),
        'evidence': _col(fact_headers, r'证据标签', r'日期'),
        'anchor': _col(fact_headers, r'run', r'clm'),
        'judgement': _col(fact_headers, r'差异判读', r'can.t', r'won.t'),
    }
    fact_missing_cols = [k for k, v in fact_cols.items() if v is None]
    fact_pairs, bad_facts, fact_by_pair = [], [], {}
    allowed_states = {'FULL', 'PARTIAL', 'ABSENT', 'UNKNOWN', 'N/A'}
    if fact_headers and not fact_missing_cols:
        for cells in fact_rows:
            ma = re.fullmatch(r'`?AF-\d+`?', cells[fact_cols['af']].strip(), re.I)
            mc = re.fullmatch(r'`?COMP-\d+`?', cells[fact_cols['comp']].strip(), re.I)
            if not (ma and mc):
                continue
            af = re.search(r'AF-\d+', cells[fact_cols['af']], re.I).group(0).upper()
            comp = re.search(r'COMP-\d+', cells[fact_cols['comp']], re.I).group(0).upper()
            pair = (af, comp)
            fact_pairs.append(pair)
            state = cells[fact_cols['state']].strip().strip('*`').upper().replace('／', '/')
            row_text = ' | '.join(cells)
            missing = [k for k, idx in fact_cols.items()
                       if k not in ('af', 'comp', 'state') and _atomic_blank(cells[idx])]
            if missing:
                bad_facts.append('%s×%s 缺 %s' % (af, comp, '/'.join(missing)))
            if state not in allowed_states:
                bad_facts.append('%s×%s 状态非法：%s' % (af, comp, state or '空'))
                continue
            fact_by_pair[pair] = {
                'state': state,
                'anchor': cells[fact_cols['anchor']],
                'evidence': cells[fact_cols['evidence']],
            }
            if not DATE.search(cells[fact_cols['evidence']]):
                bad_facts.append('%s×%s 证据标签缺日期' % (af, comp))
            if not re.search(r'CLM-\d+', cells[fact_cols['anchor']], re.I):
                bad_facts.append('%s×%s 缺 CLM 锚点' % (af, comp))
            if state == 'FULL' and not (re.search(r'实测', cells[fact_cols['evidence']])
                                        and re.search(r'RUN-\d+', cells[fact_cols['anchor']], re.I)):
                bad_facts.append('%s×%s FULL 必须有实测标签+RUN' % (af, comp))
            elif state == 'PARTIAL' and not re.search(r'部分|仅|缺|未覆盖|受限', row_text):
                bad_facts.append('%s×%s PARTIAL 未点明缺失边界' % (af, comp))
            elif state == 'ABSENT' and not (re.search(r'已检索|检索后未发现|范围内未发现', row_text)
                                            and DATE.search(row_text)):
                bad_facts.append('%s×%s ABSENT 缺检索入口/范围/日期' % (af, comp))
            elif state == 'UNKNOWN' and not (re.search(r'阻断|无法判断|未获取', row_text)
                                             and re.search(r'TBD-\d+', row_text, re.I)
                                             and re.search(r'owner|负责人', row_text, re.I)):
                bad_facts.append('%s×%s UNKNOWN 缺阻断+TBD+owner' % (af, comp))
            elif state == 'N/A' and '理由' not in row_text:
                bad_facts.append('%s×%s N/A 缺理由' % (af, comp))

    duplicate_pairs = sorted({x for x in fact_pairs if fact_pairs.count(x) > 1})
    expected_pairs = {(af, comp) for af in set(af_ids) for comp in formal_comp_ids}
    actual_pairs = set(fact_pairs)
    missing_pairs = sorted(expected_pairs - actual_pairs)
    extra_pairs = sorted(actual_pairs - expected_pairs)
    if duplicate_pairs:
        bad_facts.append('重复事实：%s' % '、'.join('%s×%s' % x for x in duplicate_pairs[:4]))
    if missing_pairs:
        bad_facts.append('缺事实：%s' % '、'.join('%s×%s' % x for x in missing_pairs[:6]))
    if extra_pairs:
        bad_facts.append('账本对象不在正式全集：%s' % '、'.join('%s×%s' % x for x in extra_pairs[:4]))
    add('atomic-facts', '每个 AF×正式 COMP 恰好一行；细节、状态、日期、RUN/CLM 与 ABSENT/UNKNOWN 语义一致',
        bool(af_ids) and bool(formal_comp_ids) and not fact_missing_cols and not bad_facts
        and actual_pairs == expected_pairs,
        ((['缺表头列：%s' % '、'.join(fact_missing_cols)] if fact_missing_cols else [])
         + (['没有可识别的正式 COMP 分母'] if not formal_comp_ids else [])
         + bad_facts[:8] or ['%d 个 AF×COMP 事实无遗漏、无重复' % len(actual_pairs)]))

    # 横向面板可拆竞品列，不能拆掉 AF 行；面板清单的竞品并集必须等于正式竞品全集。
    panel_matches = list(re.finditer(r'^###\s+(PANEL-\d+)[^\n]*\n([\s\S]*?)(?=^###\s+PANEL-|^##\s+横向对比面板清单|\Z)',
                                     atomic, re.M | re.I))
    panel_af_sets, panel_comp_sets, bad_panels = {}, {}, []
    for pm in panel_matches:
        pid, block = pm.group(1).upper(), pm.group(2)
        table_lines = [ln for ln in block.splitlines() if ln.strip().startswith('|')]
        if len(table_lines) < 3:
            bad_panels.append('%s 缺横向表' % pid); continue
        headers = [re.sub(r'[`*\s]', '', c).upper()
                   for c in table_lines[0].strip().strip('|').split('|')]
        comps = {re.search(r'COMP-\d+', h).group(0) for h in headers if re.search(r'COMP-\d+', h)}
        rows = [ln for ln in table_lines[2:] if not re.match(r'^\s*\|[\s\-:|]+\|\s*$', ln)]
        ids = [re.search(r'AF-\d+', ln, re.I).group(0).upper()
               for ln in rows if re.search(r'AF-\d+', ln, re.I)]
        panel_af_sets[pid], panel_comp_sets[pid] = set(ids), comps
        if len(ids) != len(set(ids)):
            bad_panels.append('%s 有重复 AF 行' % pid)
        if set(ids) != set(af_ids):
            bad_panels.append('%s AF 行集与词典不一致' % pid)

    manifest_headers, manifest_rows = _table_in_section(
        atomic, '横向对比面板清单', (r'^panel$', r'覆盖竞品', r'af首尾', r'af数量', r'行集一致', r'重复|遗漏'))
    manifest_ids = {re.search(r'PANEL-\d+', row[0], re.I).group(0).upper()
                    for row in manifest_rows if re.search(r'PANEL-\d+', row[0], re.I)}
    if manifest_ids != set(panel_af_sets):
        bad_panels.append('面板清单与实际面板不一致')
    all_panel_comps = set().union(*panel_comp_sets.values()) if panel_comp_sets else set()
    repeated_comps = sorted({c for c in all_panel_comps
                             if sum(c in s for s in panel_comp_sets.values()) > 1})
    if all_panel_comps != set(formal_comp_ids):
        bad_panels.append('面板竞品分母不一致：期望 %s，实得 %s'
                          % ('/'.join(formal_comp_ids), '/'.join(sorted(all_panel_comps))))
    if repeated_comps:
        bad_panels.append('竞品跨面板重复：%s' % '、'.join(repeated_comps))
    matrix_af_ids = {m.group(0).upper() for m in re.finditer(r'(?<![A-Z])AF-\d+(?!\d)', mt, re.I)}
    if set(af_ids) - matrix_af_ids:
        bad_panels.append('matrix.md 缺 AF：%s' % '、'.join(sorted(set(af_ids) - matrix_af_ids)))
    add('atomic-horizontal', '横向面板与 matrix.md 复用完整 AF 行集；面板只拆竞品列且正式竞品无遗漏/重复',
        bool(panel_af_sets) and bool(manifest_headers) and not bad_panels,
        bad_panels[:6] or ['%d 个面板覆盖 %d 个正式竞品与 %d 个 AF'
                           % (len(panel_af_sets), len(all_panel_comps), len(set(af_ids)))])

    # 路径各层也要比较；只做叶子勾叉，回答不了产品模型从哪一层开始分叉。
    path_idx = dict_cols.get('path')
    required_nodes = set()
    if path_idx is not None:
        for cells in dict_rows:
            if path_idx >= len(cells):
                continue
            parts = [x.strip() for x in re.split(r'\s*/\s*', cells[path_idx]) if x.strip()]
            if parts and re.fullmatch(r'AF-\d+', parts[-1], re.I):
                parts = parts[:-1]
            for i in range(1, len(parts) + 1):
                required_nodes.add('/'.join(parts[:i]))
    level_headers, level_rows = _table_in_section(
        atomic, '逐级横向对比',
        (r'节点路径', r'层级深度', r'父节点', r'子\s*af', r'竞品.*覆盖', r'共同模式',
         r'关键差异', r'用户|业务代价', r'下游输入'))
    level_path = _col(level_headers, r'节点路径')
    actual_nodes, bad_levels = [], []
    if level_headers and level_path is not None:
        for cells in level_rows:
            node = re.sub(r'[`*]', '', cells[level_path]).strip().strip('/')
            if not node:
                continue
            actual_nodes.append(node)
            if any(_atomic_blank(v) for v in cells):
                bad_levels.append('%s 有空格/占位' % node)
    if len(actual_nodes) != len(set(actual_nodes)):
        bad_levels.append('逐级对比节点重复')
    if set(actual_nodes) != required_nodes:
        bad_levels.append('节点集合不一致：缺%s 多%s' %
                          (sorted(required_nodes - set(actual_nodes)),
                           sorted(set(actual_nodes) - required_nodes)))
    add('atomic-level-comparison', '按实际功能路径从根到叶父节点逐级横向比较，节点全集无漏项',
        bool(required_nodes) and bool(level_headers) and not bad_levels,
        bad_levels[:5] or ['%d 个中间节点均有横向对比' % len(required_nodes)])

    map_headers, map_rows = _table_in_section(
        atomic, '原子功能下游映射',
        (r'^af$', r'研究结论', r'prd', r'figma', r'html', r'adopt|adapt|reject|defer|watch', r'指标|证伪'))
    map_af, bad_map = [], []
    if map_headers:
        for cells in map_rows:
            ma = re.fullmatch(r'`?AF-\d+`?', cells[0].strip(), re.I)
            if not ma:
                continue
            af = re.search(r'AF-\d+', cells[0], re.I).group(0).upper()
            map_af.append(af)
            if any(_atomic_blank(c) for c in cells):
                bad_map.append('%s 有空/占位字段' % af)
            if not re.search(r'adopt|adapt|reject|defer|watch', ' | '.join(cells), re.I):
                bad_map.append('%s 缺处置' % af)
    if len(map_af) != len(set(map_af)):
        bad_map.append('下游映射有重复 AF')
    if set(map_af) != set(af_ids):
        bad_map.append('下游映射 AF 行集与词典不一致')
    add('atomic-downstream', '每个 AF 都映射 PRD/Figma/HTML 或 WATCH/N/A+理由，并有处置与验证条件',
        bool(map_headers) and bool(map_af) and not bad_map,
        bad_map[:5] or ['%d 个 AF 均有三类下游去向' % len(map_af)])

    # ── 决策框架与样本形成过程：不能只交一个无法解释如何选出的最终名单 ──
    # 合法产物有两种形状：`FIELD：value` 与模板表格的 ``| `FIELD` | value |``。
    # 只认冒号会让执行者严格照模板填写却被门禁误伤；只搜字段名又会把说明文字当产物。
    field_value = r'`?\s*(?:[：:]|\|)'
    frame_need = {
        "DECISION": r'(?<![A-Z])DECISION' + field_value,
        "QUESTION": r'(?<![A-Z])QUESTION' + field_value,
        "CHANGE-MIND": r'CHANGE-MIND' + field_value,
        "POSITIONING-LENS": r'POSITIONING-LENS' + field_value,
        "STRATEGIC-TENSION": r'STRATEGIC-TENSION' + field_value,
    }
    missing_frame = [name for name, pat in frame_need.items()
                     if not re.search(pat, landscape, re.I)]
    add("decision-frame", "研究合同含决定/问题/证伪/定位镜头/战略张力",
        bool(landscape) and not missing_frame,
        missing_frame or "研究从待做决定与用户选择标准出发")

    candidate_rows = [ln for ln in landscape.splitlines()
                      if re.search(r'(?<![A-Z])CAND-\d+(?!\d)', ln)]
    bad_candidates = [ln[:56] for ln in candidate_rows
                      if not re.search(r'纳入|排除|观察', ln)
                      or not re.search(r'高|中|低|未知', ln)
                      or not re.search(r'CLM-\d+', ln)]
    candidate_markers = all(x in landscape for x in ('候选池', '排除理由', '重看触发', '不合成总分'))
    add("candidate-funnel", "候选池有纳入/排除记录，威胁与学习价值分列且不合成总分",
        bool(candidate_rows) and not bad_candidates and candidate_markers,
        ((["缺候选池/排除理由/重看触发/不合成总分说明"] if not candidate_markers else [])
         + (["候选行不完整：%s" % "；".join(bad_candidates[:2])] if bad_candidates else [])
         or ["%d 个候选有形成记录" % len(candidate_rows)]))

    source_plan_need = {
        "SOURCE-PLAN": r'SOURCE-PLAN' + field_value, "首选一手证据": r'首选一手证据',
        "独立复核": r'独立复核', "交互实测": r'交互实测', "降级": r'降级',
    }
    missing_source_plan = [name for name, pat in source_plan_need.items()
                           if not re.search(pat, landscape, re.I)]
    add("source-plan", "取证计划按维度声明一手证据/独立复核/交互实测/降级",
        bool(landscape) and not missing_source_plan,
        missing_source_plan or "取证计划齐备")

    # ── 公共比较维度：先比定位与用户结果，再比功能 ──
    DIMENSIONS = {
        "定位与价值主张": r'定位.{0,8}价值主张|价值主张',
        "目标用户与购买者": r'目标用户.{0,8}购买者|购买者.{0,8}用户',
        "核心场景/JTBD": r'核心场景|JTBD',
        "关键流程": r'关键流程|关键路径',
        "核心能力与覆盖度": r'核心能力.{0,8}覆盖|功能矩阵',
        "版本与迭代节奏": r'版本.{0,8}迭代节奏|迭代节奏',
        "价格与包装": r'价格.{0,8}包装|定价.{0,8}档',
        "商业化与服务": r'商业化.{0,8}服务|商业模式',
        "增长与留存": r'增长.{0,8}留存|获客.{0,8}留存',
        "用户体验": r'用户体验|可学性',
        "视觉与品牌": r'视觉.{0,8}品牌|品牌.{0,8}视觉',
        "技术底层": r'技术底层|技术架构',
        "数据/安全/合规": r'数据.{0,8}(安全|合规)|安全.{0,8}合规',
        # 2026-09-15 首跑实证：3/14 直接竞品未登录态零可见 —— 这是产品决定，必须成为可对比维度。
        "未登录/未付费档可见面": r'未登录.{0,12}可见|未付费.{0,10}(档|可见)',
    }
    missing_dims = [name for name, pat in DIMENSIONS.items()
                    if not re.search(pat, mt, re.I)]
    add("comparison-dimensions", "matrix.md 覆盖公共比较维度（定位→用户→场景→流程→能力→商业→体验→技术）",
        bool(mt) and not missing_dims, missing_dims or "14 个公共维度齐备")

    # ── AI 条件域：不适用也要声明理由；适用就必须比较结果/失败/数据/成本而非模型名 ──
    ai_line = re.search(r'AI-SCOPE\s*[：:]\s*(不适用|适用)[^\n]*理由\s*[：:]?\s*([^\n]+)',
                        mt + '\n' + landscape, re.I)
    if not ai_line:
        add("ai-competitive-scope", "AI 专项适用性已声明；适用时九域齐，不适用时理由非空", False,
            "缺 `AI-SCOPE：适用/不适用 · 理由：...`")
    else:
        ai_state, ai_reason = ai_line.group(1), ai_line.group(2).strip().strip('*`')
        reason_ok = bool(ai_reason) and not re.match(r'^(?:<.*>|TBD|TODO|-+|—+)$', ai_reason, re.I)
        AI_DIMS = {
            "能力角色": r'AI.{0,8}能力角色|核心/辅助/增值',
            "能力矩阵": r'AI.{0,8}能力矩阵',
            "效果质量": r'效果质量|准确.{0,6}召回|幻觉.{0,6}误判',
            "使用门槛与信任": r'使用门槛|学习成本|信任.{0,6}解释',
            "响应/失败/接管": r'响应.{0,8}失败|降级.{0,8}人工接管|超时.{0,8}接管',
            "数据与评测": r'数据.{0,8}评测|标注.{0,8}评测',
            "技术路线与壁垒": r'技术路线.{0,8}壁垒|自研.{0,12}第三方',
            "单位成本与规模": r'单位成本|成本.{0,8}规模',
            "安全与合规": r'AI.{0,12}安全.{0,8}合规|安全.{0,8}合规',
        }
        missing_ai = [] if ai_state == '不适用' else [name for name, pat in AI_DIMS.items()
                                                       if not re.search(pat, mt, re.I)]
        add("ai-competitive-scope", "AI 专项适用性已声明；适用时九域齐，不适用时理由非空",
            reason_ok and not missing_ai,
            ("AI 不适用，理由已写" if ai_state == '不适用' and reason_ok else
             ("AI 适用且九域齐备" if not missing_ai and reason_ok else
              "缺：%s%s" % ("理由" if not reason_ok else '',
                              ("、" if not reason_ok and missing_ai else '') + "、".join(missing_ai)))))

    # ── 关键流程对比：可编辑图源 + 同口径量化 + 失败恢复 ──
    flows = read('key-flows.md')
    flow_need = {
        "FLOW-数字": r'(?<![A-Z])FLOW-\d+(?!\d)',
        "可编辑图源": r'```mermaid|\.(?:mmd|d2)\b',
        "同口径协议": r'同口径|完成定义',
        "步骤/时间": r'步骤.{0,12}(时间|耗时)|时间.{0,12}步骤',
        "失败/恢复": r'失败.{0,12}(恢复|重试|取消|接管)|恢复.{0,12}失败',
        "下游三目标": r'PRD[\s\S]{0,300}Figma[\s\S]{0,300}HTML',
    }
    missing_flow = [name for name, pat in flow_need.items()
                    if not re.search(pat, flows, re.I)]
    add("key-flows", "key-flows.md 有同口径协议、可编辑图源、量化差异、失败恢复与三类下游目标",
        bool(flows) and not missing_flow, missing_flow or "关键流程对比结构齐备")

    # ── 交互式实测回执：不能靠一句「已遍历」冒充真实覆盖 ──
    # 执行事实的唯一正本是 key-flows.md#实测采集回执。landscape 里的表是计划，
    # 单体档案与三份报告只引用 RUN，避免三份授权/版本/日期互相漂移。
    run_comp_by_id, run_channel_by_id, run_surface_af_by_id = {}, {}, {}
    surface_issues = []
    receipt_sec = section_at(flows, '实测采集回执') if flows else None
    if receipt_sec is None:
        add("interactive-access", "深挖对象有 RUN 回执；通道/结果/授权/证据/阻断一致", False,
            "key-flows.md 缺 `## 实测采集回执`，无法证明浏览器或 Computer Use 实际走到哪里")
    else:
        table_lines = [ln for ln in receipt_sec.splitlines() if ln.strip().startswith('|')]
        header_pos = next((i for i, ln in enumerate(table_lines)
                           if re.search(r'\bRUN\b', ln, re.I)
                           and re.search(r'\bCOMP\b', ln, re.I)
                           and '采集通道' in ln), None)
        if header_pos is None:
            add("interactive-access", "深挖对象有 RUN 回执；通道/结果/授权/证据/阻断一致", UNABLE,
                "UNABLE：找到了实测采集回执小节，但认不出包含 RUN/COMP/采集通道的表头")
        else:
            headers = [re.sub(r'[`*\s]', '', c).lower()
                       for c in table_lines[header_pos].strip().strip('|').split('|')]

            def col(*terms):
                return next((i for i, h in enumerate(headers)
                             if any(t.lower() in h for t in terms)), None)

            cols = {
                'run': col('run'), 'comp': col('comp'), 'product': col('产品形态'),
                'channel': col('采集通道'), 'date': col('执行日期'), 'version': col('版本'),
                'source': col('官方来源'), 'auth': col('授权状态'), 'data': col('测试数据'),
                'side_effect': col('外部副作用'), 'coverage': col('功能覆盖账'),
                'label': col('结果标签'), 'evidence': col('证据目录', '截图/录屏目录'),
                'blocker': col('阻断/降级理由', '阻断项'),
            }
            missing_cols = [k for k, v in cols.items() if v is None]
            data_lines = [ln for ln in table_lines[header_pos + 1:]
                          if not re.match(r'^\s*\|[\s\-:|]+\|\s*$', ln)
                          and re.search(r'(?<![A-Z])RUN-\d+(?!\d)', ln)]
            if missing_cols:
                add("interactive-access", "深挖对象有 RUN 回执；通道/结果/授权/证据/阻断一致", False,
                    "实测回执缺列：%s" % "、".join(missing_cols))
            elif not data_lines:
                add("interactive-access", "深挖对象有 RUN 回执；通道/结果/授权/证据/阻断一致", False,
                    "实测回执没有实写 RUN-数字 行（模板 RUN-xx 不算）")
            else:
                placeholder = re.compile(r'^(?:|[-—/]+|TBD|TODO|<[^>]*>|待\S*|未填)$', re.I)

                def blank_cell(v):
                    return bool(placeholder.match((v or '').strip().strip('*`')))

                bad_receipts, run_ids, run_comps = [], [], set()
                allowed = ('web-browser', 'mac-computer-use', 'cdp-direct', 'retrieval-only', 'inaccessible')
                for ln in data_lines:
                    cells = [c.strip() for c in ln.strip().strip('|').split('|')]
                    if len(cells) <= max(cols.values()):
                        bad_receipts.append("回执列数不足：%s" % ln[:48]); continue
                    rid = re.search(r'(?<![A-Z])RUN-\d+(?!\d)', cells[cols['run']])
                    cid = re.search(r'(?<![A-Z])COMP-\d+(?!\d)', cells[cols['comp']])
                    channel = next((x for x in allowed if x in cells[cols['channel']]), None)
                    tag = cells[cols['label']]
                    if not rid or not cid or not channel:
                        bad_receipts.append("RUN/COMP/通道无效：%s" % ln[:48]); continue
                    rid, cid = rid.group(0).upper(), cid.group(0).upper()
                    run_ids.append(rid); run_comps.add(cid)
                    run_comp_by_id[rid], run_channel_by_id[rid] = cid, channel
                    common_missing = [name for name in ('date', 'data', 'side_effect', 'coverage', 'label', 'evidence')
                                      if blank_cell(cells[cols[name]])]
                    if common_missing:
                        bad_receipts.append("%s 缺 %s" % (rid, '/'.join(common_missing)))
                    if not DATE.search(cells[cols['date']]):
                        bad_receipts.append("%s 执行日期无效" % rid)
                    if channel == 'web-browser':
                        if 'web' not in cells[cols['product']].lower():
                            bad_receipts.append("%s web-browser 与产品形态不符" % rid)
                        if blank_cell(cells[cols['version']]):
                            bad_receipts.append("%s Web 回执缺版本/账号/价格档" % rid)
                        if blank_cell(cells[cols['source']]) or not URL.search(cells[cols['source']]):
                            bad_receipts.append("%s Web 回执缺实际访问的官方入口" % rid)
                        if '无需下载授权' not in cells[cols['auth']]:
                            bad_receipts.append("%s Web 回执未写『无需下载授权』" % rid)
                        if (('[实测' in tag and 'web-browser' not in tag)
                                or not re.search(r'实测.*web-browser|仅观察|阻断', tag, re.I)):
                            bad_receipts.append("%s Web 结果标签与通道不符" % rid)
                    elif channel == 'mac-computer-use':
                        auth = cells[cols['auth']]
                        if 'mac' not in cells[cols['product']].lower():
                            bad_receipts.append("%s mac-computer-use 与产品形态不符" % rid)
                        if blank_cell(cells[cols['version']]):
                            bad_receipts.append("%s macOS 回执缺具体版本" % rid)
                        if blank_cell(cells[cols['source']]) or not (
                                URL.search(cells[cols['source']]) or '官方' in cells[cols['source']]
                                or 'Mac App Store' in cells[cols['source']]):
                            bad_receipts.append("%s macOS 回执缺可核的官方来源" % rid)
                        if '未授权' in auth or '授权' not in auth or not DATE.search(auth):
                            bad_receipts.append("%s macOS 回执缺用户明确授权与日期" % rid)
                        if (('[实测' in tag and 'mac-computer-use' not in tag)
                                or not re.search(r'实测.*mac-computer-use|仅观察|阻断', tag, re.I)):
                            bad_receipts.append("%s macOS 结果标签与通道不符" % rid)
                    elif channel == 'cdp-direct':
                        # 2026-09-15 首跑实证新增：Electron/Tauri 壳带调试端口直启，CDP 读 DOM。
                        # 操作的是本机已安装应用 ⇒ 授权要求与 mac-computer-use 同级（授权+日期）。
                        auth = cells[cols['auth']]
                        prod = cells[cols['product']]
                        if not ('electron' in prod.lower() or 'tauri' in prod.lower() or '壳' in prod):
                            bad_receipts.append("%s cdp-direct 与产品形态不符（仅限 Electron/Tauri 壳）" % rid)
                        if blank_cell(cells[cols['version']]):
                            bad_receipts.append("%s CDP 回执缺具体版本" % rid)
                        if blank_cell(cells[cols['source']]) or not (
                                URL.search(cells[cols['source']]) or '官方' in cells[cols['source']]
                                or 'Mac App Store' in cells[cols['source']]):
                            bad_receipts.append("%s CDP 回执缺可核的官方来源" % rid)
                        if '未授权' in auth or '授权' not in auth or not DATE.search(auth):
                            bad_receipts.append("%s CDP 回执缺用户明确授权与日期（直启本机应用同样要授权）" % rid)
                        if (('[实测' in tag and 'cdp-direct' not in tag)
                                or not re.search(r'实测.*cdp-direct|仅观察|阻断', tag, re.I)):
                            bad_receipts.append("%s CDP 结果标签与通道不符" % rid)
                    else:
                        if blank_cell(cells[cols['blocker']]):
                            bad_receipts.append("%s 降级通道缺具体阻断/原因" % rid)
                        if '[实测' in tag or not re.search(r'宣称|公开演示|阻断|未获取', tag):
                            bad_receipts.append("%s 降级通道不得标实测" % rid)

                    # “覆盖账”不是一段自由文本，而是从产品表面发现功能的枚举入口。
                    # 每个 SURF 必须处置为 AF、NON-FEATURE 或 BLOCKED；否则 AF 全集可被静默缩小。
                    coverage = cells[cols['coverage']].strip().strip('`')
                    pointer = re.fullmatch(r'([^#]+\.md)#功能遍历覆盖账', coverage, re.I)
                    if not pointer:
                        surface_issues.append('%s 覆盖账不是 `<文件>.md#功能遍历覆盖账`' % rid)
                    else:
                        relpath = pointer.group(1).strip()
                        target = os.path.realpath(os.path.join(d, relpath))
                        try:
                            in_research = os.path.commonpath([os.path.realpath(d), target]) == os.path.realpath(d)
                        except ValueError:
                            in_research = False
                        if not in_research or not os.path.isfile(target):
                            surface_issues.append('%s 覆盖账文件不存在或越出研究目录：%s' % (rid, relpath))
                        else:
                            profile = io.open(target, encoding='utf-8', errors='replace').read()
                            sh, sr = _table_in_section(
                                profile, '功能遍历覆盖账',
                                (r'^surf$', r'^run$', r'一级模块', r'页面|区域|入口',
                                 r'用户可见动作|结果', r'af归并|处置', r'已打开', r'已实际操作',
                                 r'状态|失败|恢复', r'结果标签', r'证据', r'未覆盖|排除理由'))
                            sc = {
                                'surf': _col(sh, r'^surf$'), 'run': _col(sh, r'^run$'),
                                'module': _col(sh, r'一级模块'), 'surface': _col(sh, r'页面', r'区域', r'入口'),
                                'behavior': _col(sh, r'用户可见动作', r'结果'),
                                'disposition': _col(sh, r'af归并', r'处置'),
                                'opened': _col(sh, r'已打开'), 'operated': _col(sh, r'已实际操作'),
                                'state': _col(sh, r'状态', r'失败', r'恢复'),
                                'label': _col(sh, r'结果标签'), 'evidence': _col(sh, r'证据'),
                                'reason': _col(sh, r'未覆盖', r'排除理由'),
                            }
                            missing_surface_cols = [k for k, v in sc.items() if v is None]
                            if missing_surface_cols:
                                surface_issues.append('%s 覆盖账缺列：%s' %
                                                      (rid, '/'.join(missing_surface_cols)))
                            elif not sr:
                                surface_issues.append('%s 覆盖账没有 SURF-数字 行' % rid)
                            else:
                                observed_af, surf_ids = set(), []
                                for row in sr:
                                    sid = re.fullmatch(r'`?(SURF-\d+)`?', row[sc['surf']].strip(), re.I)
                                    row_run = re.fullmatch(r'`?(RUN-\d+)`?', row[sc['run']].strip(), re.I)
                                    if not sid:
                                        surface_issues.append('%s 有无效 SURF：%s' % (rid, row[sc['surf']]))
                                        continue
                                    sid = sid.group(1).upper(); surf_ids.append(sid)
                                    if not row_run or row_run.group(1).upper() != rid:
                                        surface_issues.append('%s 的 %s 未绑定同一 RUN' % (rid, sid))
                                    mandatory = ('module', 'surface', 'behavior', 'opened', 'operated',
                                                 'state', 'label', 'evidence')
                                    missing = [name for name in mandatory if _atomic_blank(row[sc[name]])]
                                    if missing:
                                        surface_issues.append('%s 缺 %s' % (sid, '/'.join(missing)))
                                    disposition = row[sc['disposition']].upper()
                                    row_af = {x.upper() for x in re.findall(r'AF-\d+', disposition, re.I)}
                                    unknown_af = sorted(row_af - set(af_ids))
                                    if unknown_af:
                                        surface_issues.append('%s 归并到词典外 AF：%s' %
                                                              (sid, '/'.join(unknown_af)))
                                    if row_af:
                                        observed_af.update(row_af & set(af_ids))
                                    elif re.search(r'NON-FEATURE|BLOCKED', disposition, re.I):
                                        if _atomic_blank(row[sc['reason']]):
                                            surface_issues.append('%s 标 NON-FEATURE/BLOCKED 但无理由' % sid)
                                    else:
                                        surface_issues.append('%s 未处置为 AF/NON-FEATURE/BLOCKED' % sid)
                                duplicate_surfs = sorted({x for x in surf_ids if surf_ids.count(x) > 1})
                                if duplicate_surfs:
                                    surface_issues.append('%s 覆盖账 SURF 重复：%s' %
                                                          (rid, '/'.join(duplicate_surfs)))
                                run_surface_af_by_id[rid] = observed_af

                dup_runs = sorted({x for x in run_ids if run_ids.count(x) > 1})
                if dup_runs:
                    bad_receipts.append("RUN 重复：%s" % "、".join(dup_runs))
                deep_comps = {m.group(0) for ln in landscape.splitlines()
                              if '深挖' in ln
                              for m in [re.search(r'(?<![A-Z])COMP-\d+(?!\d)', ln)] if m}
                missing_deep = sorted(deep_comps - run_comps)
                if missing_deep:
                    bad_receipts.append("深挖对象无 RUN：%s" % "、".join(missing_deep))
                add("interactive-access", "深挖对象有 RUN 回执；通道/结果/授权/证据/阻断一致",
                    not bad_receipts, bad_receipts[:6] or "%d 个 RUN 回执语义一致" % len(run_ids))

    # FULL/PARTIAL 不仅要“写了 RUN”，还必须能反查同一竞品、同一 RUN 的界面发现。
    # 这条交叉约束把产品表面穷举、AF 词典和事实长表锁成一条可验证链。
    for (af, comp), fact in fact_by_pair.items():
        if fact['state'] not in ('FULL', 'PARTIAL'):
            continue
        run_refs = {x.upper() for x in re.findall(r'RUN-\d+', fact['anchor'], re.I)}
        matching = [rid for rid in run_refs
                    if run_comp_by_id.get(rid) == comp
                    and run_channel_by_id.get(rid) in ('web-browser', 'mac-computer-use', 'cdp-direct')
                    and af in run_surface_af_by_id.get(rid, set())]
        if not matching:
            surface_issues.append('%s×%s %s 无法反查同竞品实测 RUN 的 SURF→AF' %
                                  (af, comp, fact['state']))
    # ── 2026-09-15 新增两条：用户要求「两种取证方式必须一起用」与「四件套」──
    #   ⛔ 规范写了没人守 = 没写。这两条把新要求变成机器可判的。
    conf = read('conflicts.md')
    if conf is None:
        add('dual-channel-conflict',
            'conflicts.md 存在：实测与深度研究两路都跑过，冲突逐条登记且采信实测',
            False, 'conflicts.md 不存在 —— 两条取证通道必须一起用，'
                   '其结果一致与否本身就是交付物；本轮无冲突也要写「无冲突 + 理由」')
    else:
        _has_row = bool(re.search(r'CONFLICT-\d', conf))
        _has_none = bool(re.search(r'本轮无冲突|无冲突[^\n]{0,20}理由', conf))
        _has_dual = ('codex' in conf.lower()) and bool(re.search(r'同向|不同向', conf))
        _adopt_a = bool(re.search(r'采信[^\n]{0,12}(A|实测)', conf))
        _bad = []
        if not (_has_row or _has_none):
            _bad.append('既没有 CONFLICT-xx 行，也没有「本轮无冲突 + 理由」')
        if not _has_dual:
            _bad.append('缺双路 deep-research 合并记录（要能看出我方与 codex 两份，且标了同向/不同向）')
        if _has_row and not _adopt_a:
            _bad.append('有冲突却没写采信（⛔ 默认以 A 实测为准，必须显式写出来）')
        add('dual-channel-conflict',
            'conflicts.md 存在：实测与深度研究两路都跑过，冲突逐条登记且采信实测',
            not _bad, '；'.join(_bad) or 'conflicts.md 齐备')

    # 四件套：深挖对象要产出与 PRD 4.4/6.1/6.2 同构的产物，否则研究喂不进下游
    _iso_txt = '\n'.join(x for x in (read('prd-isomorphic.md'), read('competitor-landscape.md'),
                                      read('matrix.md'), read('key-flows.md'), conf,
                                      read('atomic-feature-ledger.md')) if x)
    _need = {'核心体验路径': r'core-path|核心体验路径',
             '产品模块图': r'module\.(d2|mmd|puml)|产品模块图',
             '功能架构图': r'feature-tree|功能架构图|功能树',
             '功能清单': r'feature-list|功能清单'}
    _miss = [k for k, pat in _need.items() if not re.search(pat, _iso_txt)]
    _id_ok = bool(re.search(r'CAF-\d', _iso_txt)) and bool(re.search(r'CM-\d', _iso_txt))
    _bad2 = []
    if _miss:
        _bad2.append('深挖档缺四件套：' + '、'.join(_miss))
    if not _id_ok:
        _bad2.append('缺竞品 ID 族（CAF-xxx 原子功能 / CM-xx 模块）—— '
                     '⛔ 不许直接用我们的 F-xx/M-xx 标竞品，混进去两边追溯链永远分不开')
    add('prd-isomorphic',
        '深挖竞品有与 PRD 同构的四件套（核心体验路径/产品模块图/功能架构图/功能清单）且用竞品 ID 族',
        not _bad2, '；'.join(_bad2) or '四件套与 ID 族齐备')

    # ══ 2026-09-15 用户指令三项 ══════════════════════════════════════════════
    #   ①「调研要完全覆盖并高于 PRD 的范围与深度」⇒ 载体级对账（2.3a / 7.1b）
    #   ②「要有创新点、趋势与差异化优势」        ⇒ INNOV / TREND / DIFF（5.2 / 5.3）
    #   ③「缺交互与设计，撑不起 PRD」            ⇒ 设计与交互事实库（3.6）
    #   ④「要用 /deep-research 拿到更多内容」    ⇒ B 通道轮次契约（3.4.2）
    # ⛔ 规范写了没人守 ＝ 没写。以下四条把新契约变成机器可判的。
    _dc = read('downstream-coverage.md')

    # ① PRD 载体对账：载体全集 − 已覆盖 ＝ 差集，差集每格必须有理由
    _CARRIERS = {
        '4.4 用户流程图': r'4\.4|核心体验路径|core-path',
        '5.1 业务流程图': r'5\.1|业务流程图|关键流程图|key-flow',
        '6.1 产品模块图': r'6\.1|产品模块图|module\.(?:d2|mmd|puml)',
        '6.2 功能清单': r'功能清单|feature-list',
        '6.2.1 功能架构图': r'6\.2\.1|功能架构图|功能树|feature-tree',
        '6.3.1 页面关系图': r'6\.3\.1|页面关系图|page-graph',
        '七章 设计交互': r'七章|设计交互|设计令牌|design-tokens',
        '附件 D 字段规格': r'附件\s*D|字段规格|field-specs',
        '附件 E 状态机': r'附件\s*E|状态机|状态覆盖|state-coverage',
    }
    _STATUS_OK = re.compile(r'已覆盖|未获取|N/?A|不适用')
    _STATUS_SOFT = re.compile(r'未获取|N/?A|不适用')
    _carrier_sec = section_at(_dc, 'PRD 载体对账') if _dc else None
    if not _dc:
        add('prd-carrier-coverage',
            'downstream-coverage.md 有 PRD 载体对账，每个载体状态合法且未获取/N-A 带原因',
            False, 'downstream-coverage.md 不存在 —— 载体级缺口无从对账（7.1b）')
    elif _carrier_sec is None:
        add('prd-carrier-coverage',
            'downstream-coverage.md 有 PRD 载体对账，每个载体状态合法且未获取/N-A 带原因',
            False, '缺 `## PRD 载体对账` 小节 —— 7.1 按语义字段对账看不见载体级缺口：'
                   '实跑发生过「功能/状态都写已覆盖，而 6.3.1 页面关系图一张都没有」')
    else:
        _bad3 = []
        _miss_c = [k for k, p in _CARRIERS.items() if not re.search(p, _carrier_sec, re.I)]
        if _miss_c:
            _bad3.append('载体对账缺行：' + '、'.join(_miss_c))
        _crows = [l for l in _carrier_sec.splitlines() if l.strip().startswith('|')
                  and not re.match(r'^\s*\|[\s\-:|]+\|\s*$', l.strip())]
        for ln in _crows[1:]:                       # 跳表头
            cells = [c.strip().strip('*`') for c in ln.strip().strip('|').split('|')]
            if len(cells) < 2:
                continue
            name, st = cells[0][:24], cells[-1]
            if not st or not _STATUS_OK.search(st):
                _bad3.append('「%s」状态留空或非法（只许 已覆盖 / 未获取+原因 / N-A+理由）' % name)
            elif _STATUS_SOFT.search(st) and len(re.sub(r'未获取|N/?A|不适用|[:：，,。.\s]', '', st)) < 2:
                _bad3.append('「%s」写了未获取/N-A 却没写原因 —— 留白与漏了在产物上完全一样' % name)
        add('prd-carrier-coverage',
            'downstream-coverage.md 有 PRD 载体对账，每个载体状态合法且未获取/N-A 带原因',
            not _bad3, _bad3[:6] or '%d 个 PRD 载体逐行有状态' % max(len(_crows) - 1, 0))

    # ② 全员档：每个**可读**的正式竞品都要有四件（⛔ 不是挑几个代表画一下）
    _ALL_TIER = {'核心体验路径': r'core-path|核心体验路径',
                 '产品模块图': r'module\.(?:d2|mmd|puml)|产品模块图',
                 '功能清单': r'feature-list|功能清单',
                 '页面关系图': r'page-graph|页面关系图'}
    _readable = sorted({c for r, c in run_comp_by_id.items()
                        if run_channel_by_id.get(r) in
                        ('web-browser', 'mac-computer-use', 'cdp-direct')})
    if not _readable:
        # ⚠️ 这里是 N/A 不是 UNABLE：可读集合为空 ⇒ 本条**无对象**（不是"我没测成"）。
        #   ⛔ 但它绝不等于"覆盖没问题"——那一档的缺口由 3.3 降级阶梯
        #   与 RUN 回执里的 `[阻断]` 登记承接（interactive-access 判据在守）。
        #   ⭐ 写清楚"谁在守"，否则 N/A 会被读成"这块没事"。
        add('per-comp-artifacts',
            '每个可读的正式竞品都有全员档四件（核心体验路径/产品模块图/功能清单/页面关系图）',
            None, 'N/A：零个可读通道的竞品 —— 本条无对象；'
                  '该档缺口由 interactive-access 的 [阻断] 登记与 3.3 降级阶梯承接')
    else:
        _bad4 = []
        for c in _readable:
            _near = '\n'.join(l for l in _iso_txt.splitlines() if c in l)
            _m = [k for k, p in _ALL_TIER.items() if not re.search(p, _near, re.I)]
            if _m:
                _bad4.append('%s 缺全员档：%s' % (c, '、'.join(_m)))
        add('per-comp-artifacts',
            '每个可读的正式竞品都有全员档四件（核心体验路径/产品模块图/功能清单/页面关系图）',
            not _bad4, _bad4[:5] or '%d 个可读竞品的全员档齐备' % len(_readable))

    # ③ 设计与交互事实库：下游要的是数值与清单，形容词喂不进 S5/S6/S7
    _dt, _sc_txt = read('design-tokens.md'), read('state-coverage.md')
    _bad5 = []
    if not _dt:
        _bad5.append('缺 design-tokens.md —— S5 设计方向 / S7 Figma / PRD 七章没有任何可引用的设计事实（3.6）')
    else:
        for k, p in {'色': r'色|color', '字': r'字号|字阶|font|字重',
                     '距': r'间距|栅格|spacing|padding'}.items():
            if not re.search(p, _dt, re.I):
                _bad5.append('设计令牌表缺「%s」族' % k)
        if not re.search(r'取证|通道|CDP|computed|取色|实测|近似', _dt, re.I):
            _bad5.append('设计令牌表没有取证通道标注 —— ⛔ 无标注的令牌会被 S5 当成实测值直接用')
    if not _sc_txt:
        _bad5.append('缺 state-coverage.md —— PRD 附件 E 与 S6 状态四类没有竞品侧依据（3.6.3）')
    else:
        _ms = [s for s in ('首次', '空', '加载', '成功', '部分失败', '失败',
                           '无权限', '离线', '极值', '恢复') if s not in _sc_txt]
        if _ms:
            _bad5.append('状态覆盖矩阵缺态：' + '、'.join(_ms))
    add('design-interaction-evidence',
        '设计令牌表（带取证通道）与状态覆盖矩阵齐备 —— 撑得起 PRD 七章与 S5/S6/S7',
        not _bad5, _bad5[:6] or '设计令牌与 10 态覆盖矩阵齐备')

    # ④ 创新点 / 趋势 / 差异化：结论不能停在"四问"，要能被挑战
    _it, _df = read('innovation-trends.md'), read('differentiation.md')
    _bad6 = []
    if not re.search(r'INNOV-\d', _it):
        _bad6.append('缺 INNOV-xx 创新点登记（5.2.1）—— 每个正式竞品都要过一遍，没有也要写"未发现"')
    if not re.search(r'TREND-\d', _it):
        _bad6.append('缺 TREND-xx 趋势登记（5.2.2）')
    else:
        if not re.search(r'≥\s*3|3\s*家|样本门槛|个例观察|50%', _it):
            _bad6.append('TREND 没有样本门槛声明 —— 🚨 从一个样本推出行业结论正是本仓老毛病')
        if '反例' not in _it:
            _bad6.append('TREND 没列反例名单 —— 有反例不影响成立，不写出来就是在藏证据')
    # ⭐ WATCH-xx：会过期的判断要单列，且复查触发写**事件**不写日期（5.3.1）
    if not re.search(r'WATCH-\d', _df + _it):
        _bad6.append('缺 WATCH-xx 窗口警报（5.3.1）—— DIFF 的窗口期估的是"我们能维持多久"，'
                     'WATCH 记的是"外部正在发生、发生完就让某条结论作废的事"，两者不是一回事')
    elif not re.search(r'复查触发|触发条件|当[^\n]{0,20}(发布|上线|进入正式版|开放)', _df + _it):
        _bad6.append('WATCH 没写复查触发条件 —— ⭐ 写日期会过期，写事件不会')
    if not re.search(r'DIFF-\d', _df):
        _bad6.append('缺 DIFF-xx 差异化优势论证（5.3）')
    else:
        for k, p in {'未满足结果': r'未满足|给不了|做得差|做得很差',
                     '我们凭什么能做': r'凭什么|我们有|既有|资产|积累|成本结构',
                     '对方为何不容易跟': r'不容易跟|不会跟|结构性|冲突|改不动|激励',
                     '窗口期': r'窗口期|领先期|季度|一年'}.items():
            if not re.search(p, _df):
                _bad6.append('DIFF 四要素缺「%s」' % k)
        # ⚠️ 禁用词要排除**禁令语境**（同本文 FABRICATED 的处理）：
        #   模板里写着「⛔ 不许写『更好用』」是在教人别这么写，把禁令判成违例＝门惩罚正确用法。
        _banned = [l.strip()[:30] for l in _df.splitlines()
                   if re.search(r'更好用|更智能|体验更佳|更懂用户', l)
                   and not re.search(r'禁用|禁止|不许|不要|⛔|避免', l)]
        if _banned:
            _bad6.append('DIFF 出现不可证伪表述：' + '；'.join(_banned[:2]))
    add('innovation-trend-diff',
        'INNOV 创新点 / TREND 趋势（带样本门槛与反例）/ DIFF 差异化四要素齐备',
        not _bad6, _bad6[:6] or 'INNOV/TREND/DIFF 齐备且可被挑战')

    # ⑤ B 通道轮次：deep-research 不是边角料，它是 5.2/5.3 的原料
    _drdir = os.path.join(d, 'deep-research')
    _drf = sorted(glob.glob(os.path.join(_drdir, '*.md'))) if os.path.isdir(_drdir) else []
    _drtxt = '\n'.join(io.open(f, encoding='utf-8', errors='replace').read() for f in _drf)
    _bad7 = []
    if not _drf:
        _bad7.append('deep-research/ 无任何轮次产出 —— B 通道没跑（3.4.2）。'
                     '⛔ 时间轴与失败面拿不到，5.2 趋势与 5.3 差异化就只能靠猜')
    else:
        _names = ' '.join(os.path.basename(f) for f in _drf)
        if 'R-A' not in _names:
            _bad7.append('缺 R-A 竞品单体轮（每个正式竞品各一轮）')
        if 'R-B' not in _names:
            _bad7.append('缺 R-B 行业轮')
        if not DATE.search(_drtxt):
            _bad7.append('deep-research 结论没有日期（发布日 / 访问日）')
        if not URL.search(_drtxt):
            _bad7.append('deep-research 结论没有来源 URL —— 不可核的结论不进报告')
    add('deep-research-rounds',
        'B 通道按 3.4.2 固定提纲跑了 R-A/R-B 轮，结论逐条带来源与日期',
        not _bad7, _bad7[:5] or '%d 份 deep-research 轮次产出齐备' % len(_drf))

    # ══ 2026-09-15 第二批（用户拍板三件 + 手工轮对照补强四条）══════════════
    # ⑥ 视觉证据契约（3.7）：报告要带图给读者看；⛔ 引用的文件必须真的在
    _EV = re.compile(r'(?:raw|evidence)/[\w一-龥\-./]+\.(?:png|jpg|jpeg|webp|gif|mp4|mov)', re.I)

    def _ev_refs(txt):
        return sorted(set(_EV.findall(txt or '')))

    def _ev_ok(ref):
        return os.path.isfile(os.path.join(d, ref))

    _all_md = '\n'.join(io.open(f, encoding='utf-8', errors='replace').read()
                        for f in sorted(glob.glob(os.path.join(d, '*.md'))))
    _bad8, _ghost = [], [r for r in _ev_refs(_all_md) if not _ev_ok(r)]
    if _ghost:
        # ⭐ 写一个不存在的文件名比不写更糟：它让读者以为有据可查。
        _bad8.append('证据文件不存在（引用了却找不到）：' + '、'.join(_ghost[:3]))
    # ⚠️ 2026-09-16 补：此前只查结构物，**不查三份定向报告** —— 而用户的要求原话是
    #   「**在报告中**…要有截图或者动图作为辅助，帮助阅读者理解」。
    #   ⭐ 结构物是给机器与下游对账的，报告才是**给人读的那一份**：它没有图，要求就没落地。
    _rep = [f for f in sorted(glob.glob(os.path.join(d, '*.md')))
            if re.search(r'(功能|设计视觉|交互).*报告', os.path.basename(f))]
    for _f in _rep:
        _rt = io.open(_f, encoding='utf-8', errors='replace').read()
        if not [r for r in _ev_refs(_rt) if _ev_ok(r)]:
            _bad8.append('%s 一张图都没有 —— 功能/设计/交互三类结论都要带图给读者看（3.7.2）'
                         % os.path.basename(_f))
    for _name, _why in (('design-tokens.md', '设计：首屏 + 密集页截图贴在令牌表旁'),
                        ('state-coverage.md', '状态：每态的实际表现要看得见'),
                        ('matrix.md', '功能对比：光看功能名读不出做到什么程度')):
        _t = read(_name)
        if not _t:
            continue                       # 该产物缺失由别的判据报，⛔ 这里不重复计一次
        if not [r for r in _ev_refs(_t) if _ev_ok(r)]:
            _bad8.append('%s 一处截图证据都没挂 —— %s（3.7.2）' % (_name, _why))
    # 动效：关键/创新动效必须有录屏；整轮一个都没有时，必须显式声明"本轮无"
    # ⚠️ 2026-09-15 自证抓到：判据被它要守的那段**声明**喂饱了 ——
    #   「本轮无关键/创新动效：…」这句里就含「关键动效」，于是被当成一条待补录屏的行。
    #   ⭐ 本仓母题「判据被它要守的那段文本喂饱」：注释、禁令语境、声明句都会满足它。⇒ 显式排除声明句。
    _DECL = re.compile(r'本轮无|未发现|无值得|不适用|N/?A')
    _motion_lines = [l for l in _all_md.splitlines()
                     if re.search(r'关键动效|创新动效', l) and not _DECL.search(l)]
    _clips = [r for r in _ev_refs(_all_md) if r.lower().endswith(('.gif', '.mp4', '.mov')) and _ev_ok(r)]
    for l in _motion_lines:
        if not re.search(r'\.(gif|mp4|mov)', l, re.I) and '未获取' not in l:
            _bad8.append('标了关键/创新动效却没挂录屏：%s' % l.strip()[:46])
    if not _clips and not _motion_lines and not re.search(r'本轮无关键\s*/?\s*创新动效|无值得录屏的动效', _all_md):
        _bad8.append('全轮零录屏，也没有「本轮无关键/创新动效 + 理由」的声明 —— '
                     '⛔ 静态图证明不了动效，动效层整层没证据（2.4.1 / 3.7.2）')
    add('visual-evidence',
        '承重表挂了真实存在的截图证据；关键/创新动效有录屏（⛔ 引用不存在的文件比不写更糟）',
        not _bad8, _bad8[:6] or '证据引用全部落地，动效证据齐')

    # ⑦ 结构层横向对比的两种形态**都要做**（2.5，用户 2026-09-15 拍板：⛔ 不是二选一）
    _cmp_txt = '\n'.join(x for x in (_iso_txt, read('matrix.md'), read('insights.md')) if x)
    _bad9 = []
    if not re.search(r'族\s*[×x]\s*竞品|同栏对齐|入口族|对齐表', _cmp_txt):
        _bad9.append('缺「族 × 竞品」同栏对齐表 —— 它一眼看出谁缺了哪一族、'
                     '谁把某族降级成设置项，且归一出的族名可直接当我们 6.1 模块图骨架')
    if not re.search(r'对照图|cross-compare', _cmp_txt):
        _bad9.append('缺跨竞品对照图 —— 层级与连线是表格结构上表达不了的')
    else:
        # ⚠️ 2026-09-16 收紧：此前只搜「对照图」三个字 —— **写上这个词就能过**。
        #   用户要求原话是「这些图要用**专业的 skill** 来做」⇒ 必须有**可解析源**
        #   （`.d2` / `.mmd`）且文件真存在；一张截图或一句话不算图。与 visual-evidence 同型。
        # ⚠️ 量程：只在**跨竞品对照图那一小节内**找源文件。开成全文会扫到全员档里
        #   各竞品自己的 `.d2`（那是 per-comp-artifacts 的量程）⇒ 正例误红。
        #   本仓母题 feedback_scope_too_narrow 的反方向：开太大同样是缺陷。
        _cc = section_at(_cmp_txt, '跨竞品对照图') or section_at(_cmp_txt, '对照图') or ''
        _src = re.findall(r'[\w一-龥\-./]+\.(?:d2|mmd)', _cc)
        if not _src:
            _bad9.append('对照图没有**可解析源**（`.d2` / `.mmd`）—— 用户点名"图要用专业的 '
                         'skill 来做"；只写「对照图」三个字或贴一张位图，下游改不动也对不了账')
        else:
            _miss = [x for x in _src if not os.path.exists(os.path.join(d, x))]
            if _miss:
                _bad9.append('对照图源文件**不存在**（引用了却找不到）：' + '、'.join(_miss[:3]))
    add('cross-compare-both-forms',
        '结构层横向对比两种形态都在：族×竞品同栏对齐表 + 跨竞品对照图',
        not _bad9, _bad9[:3] or '对齐表与对照图都在')

    # ⑧ 取证过程的元发现（3.8）：把"我能不能读到这家"本身判读成产品取舍
    _meta = '\n'.join(x for x in (read('insights.md'), read('competitor-landscape.md'),
                                  read('key-flows.md'), _all_md) if x)
    _bad10 = []
    if not re.search(r'元发现|取证过程.{0,6}发现|通道可达性', _meta):
        _bad10.append('缺「取证过程的元发现」小节（3.8）—— 遍历时遇到的阻力本身是'
                      '厂商的产品/安全取舍，⛔ 把它只当噪声就结构上产不出这类一级发现')
    else:
        if not re.search(r'同一把尺子|同一种量法|同一方法', _meta):
            _bad10.append('元发现没写「同一把尺子」—— 各量各的，那只是一堆失败记录')
        if '[推断]' not in _meta and '推断' not in _meta:
            _bad10.append('元发现未标 [推断] —— 未向厂商求证是否有意为之')
    add('probe-meta-finding',
        '取证过程本身被判读为元发现，且写明同一把尺子并标 [推断]',
        not _bad10, _bad10[:3] or '元发现成立')

    # ⑧-b 通道可达性是**逐竞品必填的一格**（3.8.1，2026-09-16 补）
    #   ⚠️ 上面那条 probe-meta-finding 只要求「有一段元发现」——**一段散文不逼任何人每家都量**。
    #     结果就是只写读得到的那几家，读不到的一句「未获取」带过，光谱自然出不来。
    #     格子才逼人。⇒ 这条与上一条不是重复：那条管**判读**，这条管**覆盖**。
    _REACH = ('敞开', 'AX完整', '剥target', '反调试', '不适用', '未量')
    _rsec = section_at(read('key-flows.md'), '实测采集回执') if read('key-flows.md') else None
    _bad10b, _r_ok, _r_ev = [], None, ''
    if _rsec is None:
        _r_ev = 'N/A：key-flows.md 没有实测采集回执小节 —— 该缺口由 interactive-access 守'
    else:
        _rtl = [ln for ln in _rsec.splitlines() if ln.strip().startswith('|')]
        _rhp = next((i for i, ln in enumerate(_rtl)
                     if re.search(r'\bRUN\b', ln, re.I) and '采集通道' in ln), None)
        if _rhp is None:
            _r_ok, _r_ev = UNABLE, 'UNABLE：认不出 RUN 表头，量不了通道可达性'
        else:
            _rhs = [re.sub(r'[`*\s]', '', c) for c in _rtl[_rhp].strip().strip('|').split('|')]
            _rci = next((i for i, h in enumerate(_rhs) if '可达性' in h), None)
            if _rci is None:
                _bad10b.append('RUN 表缺「通道可达性」列（3.8.1）—— 没有格子就没人被逼着'
                               '每家都量，只写读得到的那几家，厂商安全光谱这条一级发现就出不来')
            else:
                for ln in _rtl[_rhp + 1:]:
                    if re.match(r'^\s*\|[\s\-:|]+\|\s*$', ln): continue
                    if not re.search(r'(?<![A-Z])RUN-\d+(?!\d)', ln): continue
                    _cs = [c.strip() for c in ln.strip().strip('|').split('|')]
                    _who = _cs[0] if _cs else '?'
                    _v = re.sub(r'[`*\s]', '', _cs[_rci]) if _rci < len(_cs) else ''
                    if not _v:
                        _bad10b.append('%s 的通道可达性为空 —— 空着不是「它没有」，是**我没量**' % _who)
                    elif not any(_v.startswith(k) for k in _REACH):
                        _bad10b.append('%s 的通道可达性「%s」不在六档内（3.8.1）：%s'
                                       % (_who, _v, '/'.join(_REACH)))
            _r_ok = not _bad10b
            _r_ev = _bad10b[:3] or '每个 RUN 都有通道可达性取值，且在六档内'
    add('channel-reachability',
        '通道可达性逐竞品必填（3.8.1 六档；⛔「未量」≠「反调试」）', _r_ok, _r_ev)

    # ⑧-c 隐私红线（3.3）：读已登录竞品，读到的是**用户自己的数据**
    #   风险不在"看到了"，在它会顺着 报告→飞书→git 一路外流，而此前这条链上一道门都没有。
    _priv, _bad10c = _all_md, []
    # ⚠️ 自证当场抓到：夹具里的「不改**真实账号**」是一句**承诺不碰**，被我读成了「读了真实账号」——
    #   本仓母题「判据被它要守的那段文本喂饱」。⇒ ① 去掉 `真实账号`（边界声明的常用词，信噪比太低）；
    #   ② 命中前先看前面 8 个字有没有否定词，「⛔ 不读已登录界面」不算取证。
    _NEG = re.compile(r'(不|未|非|禁|⛔|无需|避免|不得)[^。；\n]{0,8}$')
    _LOGGED = any(not _NEG.search(_priv[max(0, mm.start() - 10):mm.start()])
                  for mm in re.finditer(r'已登录|登录态|个人账号', _priv))
    _DECLARED = re.search(r'只取产品骨架|未记录用户内容|不记录.{0,6}内容|已清场|隐私清场', _priv)
    if _LOGGED and not _DECLARED:
        _bad10c.append('语料里出现「已登录/真实账号」取证，却没有隐私清场声明（3.3）—— '
                       '必须写明「只取产品骨架、未记录用户内容」，否则读到的私人内容'
                       '会顺着 报告→飞书→git 外流，且 git 里删不干净')
    # 模式扫描只挑**高信号低误报**的：竞品官网上的客服邮箱是产品事实不是隐私，⛔ 不扫邮箱。
    for _lbl, _re_ in (('手机号', r'(?<!\d)1[3-9]\d{9}(?!\d)'),
                       ('身份证号', r'(?<!\d)\d{17}[\dXx](?!\d)')):
        _hit = re.findall(_re_, _priv)
        if _hit:
            _bad10c.append('语料里出现疑似%s（%d 处，内容不回显）—— 竞品调研里不该有这个'
                           % (_lbl, len(_hit)))
    # ⑧-d 「诚实缺口」不是豁免通道（9.1，2026-09-16）
    #   🚨 起因是一次真实的交付失败：契约与判据全都在，我把没做的事列成一张整齐的表，
    #     加一句"本报告不是完整 S2 交付"，然后照样交货。⇒ 诚实地说明没做 ≠ 做了。
    #   与 `UNABLE ≠ PASS ≠ N/A` 同型，但更隐蔽：**它读起来像美德**。
    _bad10d = []
    # ① 整份产物打折的话术：⛔ 产物只有「过门禁」和「没做完」两种状态
    _DISCOUNT = (r'不是一份?完整.{0,6}交付', r'仅供参考', r'定位是.{0,4}首跑',
                 r'连全员档都不满足', r'不完整但可交付', r'不许拿它当\s*S3')
    for _pat in _DISCOUNT:
        if re.search(_pat, _all_md):
            _bad10d.append('出现给整份产物打折的话术「%s」（9.1）—— ⛔ 产物只有「过门禁」'
                           '和「没做完」两种状态，没有第三种叫"不完整但可交付"'
                           % re.search(_pat, _all_md).group(0))
            break
    # ② 诚实缺口里装了「我没做」而不是「不可能取得」
    _gapsec = section_at(_all_md, '诚实缺口') or section_at(_all_md, '降级声明') or ''
    if _gapsec:
        _NOTDONE = (r'未跑', r'一轮未跑', r'零截图', r'零录屏', r'未做', r'没做',
                    r'整块未做', r'未执行', r'本轮未纳入')
        _BLOCKER = (r'登录墙', r'付费墙', r'会员墙', r'反调试', r'地区限制', r'厂商',
                    r'未获授权', r'不可逆', r'官方未公开', r'拒绝')
        # ⚠️ 自证抓到：表头「| 没做的事 | 影响 |」自己就含「没做」⇒ 正例误红。
        #   本仓母题「判据被它要守的那段文本喂饱」——⇒ 跳过表头（下一行是分隔行的那行）。
        _gl = _gapsec.splitlines()
        for _i, _ln in enumerate(_gl):
            if not _ln.strip() or re.match(r'^\s*\|[\s\-:|]+\|\s*$', _ln): continue
            if _i + 1 < len(_gl) and re.match(r'^\s*\|[\s\-:|]+\|\s*$', _gl[_i + 1]): continue
            if any(re.search(p, _ln) for p in _NOTDONE) and \
               not any(re.search(b, _ln) for b in _BLOCKER):
                _bad10d.append('诚实缺口里这条写的是**我没做**而不是**不可能取得**，'
                               '且没点名外部阻断者（9.1）：%s' % _ln.strip()[:60])
                if len(_bad10d) >= 3: break
    # ⑧-e 脚手架占位未清（2026-09-16，与 scaffold.py 同批）
    #   🚨 脚手架把合规骨架生成出来 ⇒ **结构类判据会立刻变绿**。
    #     如果没有这条，一份「结构全绿、内容全空」的语料就能过门 —— 那比 40 条红危险得多，
    #     因为它看起来是做过的。⇒ 只要还剩一个占位标记，本门就红。
    _TODO_MARK = '⟨TODO⟩'
    # ⚠️ 2026-09-17 复核抓到：只扫 .md 会放过**图的占位桩** ——
    #   脚手架生成的 `.d2` 只有 `A -> B`，而 cross-compare-both-forms 只验「源文件存在」
    #   ⇒ 一张桩图就能让「图要用专业 skill 做」这条需求判绿。**这就是脚手架造假绿的实例。**
    _n_todo = _all_md.count(_TODO_MARK)
    for _dp, _dn, _fn in os.walk(d):
        for _f in _fn:
            if _f.endswith(('.d2', '.mmd')):
                _n_todo += io.open(os.path.join(_dp, _f), encoding='utf-8',
                                   errors='replace').read().count(_TODO_MARK)
    add('no-placeholder-left',
        '脚手架占位标记已全部替换为真内容（⛔ 结构对了不等于研究做了）',
        _n_todo == 0,
        ('语料里还剩 %d 处 `%s` —— 骨架生成了，内容还没填。'
         '⛔ 这不是"快完成了"，是**还没开始**：结构是脚手架给的，不是研究产出的'
         % (_n_todo, _TODO_MARK)) if _n_todo else '无占位残留')

    add('gap-not-excuse',
        '诚实缺口只装「不可能取得」且点名阻断者；⛔ 无整份产物打折话术（9.1）',
        not _bad10d, _bad10d[:3] or '未发现把「没做」写成「如实披露」的用法')

    add('no-private-content',
        '读已登录竞品有隐私清场声明；语料无高信号私人标识（⚠️ 拦不住"这段是不是真人写的"，须人审）',
        not _bad10c, _bad10c[:3] or '无隐私红线命中')

    # ⑧b 截图目检 —— 文本判据扫不了图里的人名。
    # 🚨 2026-09-17 实测：6 张竞品截图里 **3 张带真实身份信息**（头像/真名/账号名），
    #    而流程认为"都已打码"。打码靠注入 CSS 选择器，一家改版就**静默失效**：
    #    不报错、不留痕、截图照常生成 ⇒ **「注入了打码 CSS」≠「打码生效」**。
    # ⇒ 机器能守的只有「有没有人真的逐张看过」：一份记录，每张图一行。
    #    ⛔ 它守不了"看得对不对"——那一层只能靠人，判据说明里必须讲清楚。
    _shots = []
    for _dp, _dn, _fn in os.walk(d):
        for _f in _fn:
            if _f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                _shots.append(os.path.relpath(os.path.join(_dp, _f), d))
    _audit = read('screenshot-masking-audit.md') or ''
    _unaudited = [x for x in _shots if os.path.basename(x) not in _audit and x not in _audit]
    # ⚠️ 自证当场抓到：我把两件事塞进了一条判据 —— 「有没有图」和「图有没有被目检」。
    #   于是**所有不含图的既有夹具全红**（正例红＝判据有问题，不是夹具有问题）。
    #   「必须有截图」由 `📎` 引用那条管，⛔ 不归这里。本条只管：**有图就必须有目检记录**。
    add('screenshot-masking-audited',
        '每张截图外发前有逐张目检记录（⚠️ 只验「看过没有」，验不了「看得对不对」）',
        (not _shots) or (bool(_audit) and not _unaudited),
        ('缺 screenshot-masking-audit.md —— 有 %d 张图却没有任何目检记录。'
         '打码会静默失效，外发前必须人眼逐张看' % len(_shots))
        if (_shots and not _audit) else
        (('这些图没在目检记录里登记：%s' % '、'.join(_unaudited[:3])) if _unaudited else
         ('语料里没有图片文件，本条 N/A（「必须有截图」由 `📎` 引用那条判据管）'
          if not _shots else '%d 张图逐张登记在案' % len(_shots))))

    # ⑨ 版本对账与纠错三段（4.4）：只改数字不写真因，下一个人会同样地再错一次
    _ver = '\n'.join(x for x in (read('competitor-landscape.md'), read('insights.md')) if x)
    _bad11 = []
    if not re.search(r'版本对账|版本\s*\|\s*定位|迭代对账', _ver):
        _bad11.append('缺版本对账表（4.4）—— 迭代到第几版、前几版怎么处置说不清')
    else:
        # ⚠️ 自证抓到：量程开成"全部 md"时，任何一处出现「推翻/修正」都会触发纠错判据
        #   （本仓 feedback_scope_too_narrow 的反方向——量程开太大同样会误红）。
        #   ⇒ 只在**版本对账小节内**判，节外的措辞与它无关。
        _vsec = section_at(_ver, '版本对账') or ''
        if re.search(r'纠错|订正|推翻|修正', _vsec) and not re.search(r'真因|错在哪|原因是', _vsec):
            _bad11.append('登记了纠错却没写**旧结论错在哪（真因）** —— '
                              '⭐ 第三段才是有价值的那段：它纠正的是判断方法，不只是结论')
    add('version-ledger',
        '有版本对账表；有纠错时写全三段（旧结论 / 新结论 / 旧结论错在哪）',
        not _bad11, _bad11[:3] or '版本对账与纠错登记齐备')

    add('atomic-surface-reconcile',
        '每个 RUN 覆盖账逐项处置；FULL/PARTIAL 可反查同竞品、同 RUN 的 SURF→AF',
        bool(run_comp_by_id) and not surface_issues,
        surface_issues[:8] or ['%d 个 RUN 覆盖账与原子事实完成双向对账' % len(run_comp_by_id)])

    sp = os.path.join(d, 'sources.md')
    sources_txt = read('sources.md')
    ok_src = os.path.exists(sp) and DATE.search(sources_txt)
    add("sources", "sources.md 存在且条目带访问日期", bool(ok_src),
        "存在且带日期" if ok_src else "缺失或无日期")

    claim_need = {
        "CLM-数字": r'(?<![A-Z])CLM-\d+(?!\d)',
        "验证状态": r'verified|disputed|unverified|overturned',
        "发布日": r'发布日|发布日期',
        "访问日": r'访问日|访问日期',
        "失效日": r'失效日|复查日期|stale',
    }
    missing_claim = [name for name, pat in claim_need.items()
                     if not re.search(pat, sources_txt, re.I)]
    add("claim-ledger", "sources.md 有 CLM 主张状态、发布日期/访问日与失效日",
        bool(sources_txt) and not missing_claim, missing_claim or "承重主张可追溯且可刷新")

    # ⚠️ 2026-09-09：命中要排除**禁令语境**——模板里写着
    #   「『据我所知』『一般来说』一律禁止」是在**教人别这么写**，
    #   把禁令本身判成违例＝门惩罚正确用法（实测：research-brief 模板因此常红）。
    #   判据：同一行里若出现「禁止/不许/不要/⛔/避免」，该行的命中不算数。
    # 🚨 2026-09-09 第五轮独立复核：豁免的量程是**整行**，于是禁令词写在命中**之后**
    #   也算数 ⇒ `据我所知它们都这么做 —— 不要照抄。` 直接放行。
    #   ⭐ 与 product-structure 的「否定豁免只看前 6 字符」是同一个病：
    #     **豁免按文本邻域给，而不是按语义位置给** —— 补一句话就能关掉判据。
    #   ⇒ 换两个站得住的不变量（满足其一才豁免）：
    #     ①禁令词出现在命中**之前**（那是在说「别写这个词」）；
    #     ②命中**被引号包起来**（引用即提及，不是使用）——模板里正是这么写的。
    _BAN_CTX = re.compile(r'禁止|不许|不得|不要|避免|⛔')
    _QUOTED = ('「」', '『』', '""', "''", '""')

    def _is_mention(m):
        _lo = all_text.rfind('\n', 0, m.start()) + 1
        if _BAN_CTX.search(all_text[_lo:m.start()]):
            return True                     # 禁令在前 ⇒ 在讲「别写它」
        _pre = all_text[max(0, m.start() - 1):m.start()]
        _post = all_text[m.end():m.end() + 1]
        return any(_pre == q[0] and _post == q[1] for q in _QUOTED)

    fab = sorted({m.group(0) for m in FABRICATED.finditer(all_text)
                  if not _is_mention(m)})
    # ── 五条线 ──
    idx = os.path.join(d, 'lines.md')
    idx_txt = io.open(idx, encoding='utf-8', errors='replace').read() if os.path.exists(idx) else all_text
    miss_lines = []
    for key, label in LINES.items():
        # 一条线算「有结论」的两种方式：有同名文件，或在 lines.md/正文里写明结论或「本轮不做」
        has_file = bool(glob.glob(os.path.join(d, '*%s*' % key)))
        declared = re.search(re.escape(label) + r'[^\n]{0,80}(本轮不做|不做|已完成|结论|见)', idx_txt)
        if not (has_file or declared): miss_lines.append(label)
    add("five-lines", "五条研究线各有结论或显式「本轮不做」",
        not miss_lines, miss_lines or "五条线均有交代")

    # ── 市场线独立交付：做了不能只留一句趋势，没做不能只写三个字 ──
    market_line = re.search(r'^.*③\s*市场线[^\n]*$', idx_txt, re.M)
    market_decl = market_line.group(0) if market_line else ''
    market_skipped = bool(re.search(r'本轮不做|不做', market_decl))
    market_path = os.path.join(d, 'market-landscape.md')
    market_txt = read('market-landscape.md')
    market_ev = []
    if not market_line:
        market_ok = False
        market_ev.append("lines.md 缺市场线声明")
    elif market_skipped:
        reason = re.search(r'理由\s*[：:]\s*([^·；\n]+)', market_decl)
        ceiling = re.search(r'声明上限\s*[：:]\s*([^·；\n]+)', market_decl)
        invalid = re.compile(r'^\s*(?:|<.*>|TBD|TODO|待定|[-—]+)\s*$', re.I)
        reason_ok = bool(reason and not invalid.match(reason.group(1)))
        ceiling_ok = bool(ceiling and not invalid.match(ceiling.group(1)))
        market_ok = reason_ok and ceiling_ok
        if not reason_ok: market_ev.append("跳过市场线却没写有效理由")
        if not ceiling_ok: market_ev.append("跳过市场线却没写对产品/PRD/设计/交互的声明上限")
    else:
        market_need = {
            "market-landscape.md": r'.+',
            "DECISION": r'(?<![A-Z])DECISION' + field_value,
            "QUESTION": r'(?<![A-Z])QUESTION' + field_value,
            "CHANGE-MIND": r'CHANGE-MIND' + field_value,
            "SCOPE": r'(?<![A-Z])SCOPE' + field_value,
            "品类定义与边界": r'品类定义.{0,8}边界',
            "规模与增长/N/A": r'规模.{0,8}增长|TAM|SAM|SOM',
            "需求与采用": r'需求.{0,8}采用|采用.{0,8}拒绝',
            "供给与价值链": r'供给.{0,8}价值链|价值链.{0,8}商业',
            "趋势与拐点": r'趋势.{0,8}拐点|领先指标',
            "相邻市场与反模式": r'相邻市场.{0,8}反模式|不可迁移边界',
            "事实→推断→建议": r'事实[\s\S]{0,120}推断[\s\S]{0,120}建议',
            "风险/反证": r'风险|反证|推翻',
            "PRD/Figma/HTML 下游覆盖": r'PRD[\s\S]{0,500}Figma[\s\S]{0,500}HTML',
            "来源与日期": r'来源[\s\S]{0,500}\d{4}-\d{2}-\d{2}',
        }
        missing_market = [name for name, pat in market_need.items()
                          if not re.search(pat, market_txt, re.I)]
        market_ok = os.path.exists(market_path) and not missing_market
        if not os.path.exists(market_path): market_ev.append("市场线宣称已做但缺 market-landscape.md")
        if missing_market: market_ev.append("市场交付缺：%s" % "、".join(missing_market))
    add("market-deliverable", "市场线执行则有独立 market-landscape；跳过则写理由与下游声明上限",
        market_ok, market_ev or ("跳过边界已声明" if market_skipped else "市场线独立交付结构齐备"))

    # ── 洞察链 ──
    ins_p = os.path.join(d, 'insights.md')
    if not os.path.exists(ins_p):
        ins = ''
        add("insights-chain", "有 insights.md，且模式→洞察→机会链完整", False,
            "缺 insights.md —— 原始材料本身不是结论，S3 拿到的会是一堆资料而不是判据")
        add("pattern-evidence", "每个洞察标注 ≥3 处独立出处", None, "无 insights.md")
        add("opportunity-solutions", "每个机会有 ≥3 个解法候选", None, "无 insights.md")
    else:
        ins = io.open(ins_p, encoding='utf-8', errors='replace').read()
        need = [w for w in ("模式", "洞察", "机会") if w not in ins]
        add("insights-chain", "有 insights.md，且模式→洞察→机会链完整",
            not need, ("缺环节：%s" % "/".join(need)) if need else "三段齐备")
        # 每个洞察后面要跟 ≥3 处出处标记
        thin = []
        for m in re.finditer(r'^#{2,4}\s*洞察[^\n]*$', ins, re.M):
            # 🚨 2026-09-09 二轮复核：这里原是 `ins[m.end(): m.end()+900]` 固定字符窗口
            #   —— 与批 O/P/Q 修掉的同一形状，**而且就长在提出这条形状的这个门里**。
            #   新元规则 no-positional-window 没抓到它：判据要求 `:` 两侧是裸变量，
            #   而 `m.end()` 是调用表达式 ⇒ 形状对了、写法没覆盖。⇒ 切到下一个标题。
            _nx = re.search(r'^#{2,4}\s', ins[m.end():], re.M)
            seg = ins[m.end(): m.end() + (_nx.start() if _nx else len(ins))]
            n = len(re.findall(r'\[(?:来源|出处|访谈|工单|评论|数据)[^\]]*\]|https?://', seg))
            if n < 3: thin.append("%s（只有 %d 处出处）" % (m.group(0).strip()[:28], n))
        add("pattern-evidence", "每个洞察标注 ≥3 处独立出处（1 处是轶事不是模式）",
            not thin, thin or "全部洞察出处充足")
        few = []
        for m in re.finditer(r'^#{2,4}\s*机会[^\n]*$', ins, re.M):
            # 「机会优先级」是机会索引，不是一条需要再枚举 3 个解法的机会正文。
            # 不排除它会导致一加优先级表，原本合格的研究反而变红。
            if '优先级' in m.group(0):
                continue
            _nx = re.search(r'^#{2,4}\s', ins[m.end():], re.M)   # 同上：切标题不切字符数
            seg = ins[m.end(): m.end() + (_nx.start() if _nx else len(ins))]
            n = len(re.findall(r'^\s*(?:[-*]|\d+[.、])\s*\S', seg, re.M))
            if n < 3: few.append("%s（只有 %d 个解法候选）" % (m.group(0).strip()[:28], n))
        add("opportunity-solutions", "每个机会有 ≥3 个解法候选（只有 1 个＝从解法倒推的问题）",
            not few, few or "全部机会有多个候选")

    # ── 竞品综合必须有明确处置与优先级，不把「别人有」直接变路线图 ──
    action_missing = [x for x in ('学习', '借鉴', '规避', '差异化') if x not in ins]
    priority_ok = bool(re.search(r'机会.{0,12}优先级|优先级.{0,40}P[012]|P[012].{0,20}理由', ins, re.S))
    add("competitive-actions", "insights.md 有学习/借鉴/规避/差异化四类结论与机会优先级",
        bool(ins) and not action_missing and priority_ok,
        (("缺处置：%s；" % "、".join(action_missing)) if action_missing else "")
        + ("缺机会优先级+理由" if not priority_ok else "优先级已写"))

    # ── 双向覆盖：下游问题不漏，研究发现不蒸发 ──
    downstream = read('downstream-coverage.md')
    down_need = {
        "下游→研究": r'下游\s*(?:→|->)\s*研究',
        "研究→下游": r'研究\s*(?:→|->)\s*下游',
        "PRD": r'\bPRD\b',
        "Figma": r'\bFigma\b',
        "HTML": r'\bHTML\b',
        "研究锚点": r'CLM|INS|OPP|COMP|FLOW',
        "三态或处置": r'已覆盖|明确未知|N/?A|adopted|adapted|rejected|deferred|watch',
    }
    missing_down = [name for name, pat in down_need.items()
                    if not re.search(pat, downstream, re.I)]
    add("downstream-coverage", "downstream-coverage.md 双向覆盖 PRD/Figma/HTML，且未知/未采用有去向",
        bool(downstream) and not missing_down, missing_down or "三类下游双向可追溯")

    # ── 三份定向报告（深度由下游反推）──
    REPORTS = {"功能": "喂 S3 提案表与 PRD 范围/功能清单/功能详细设计/附件 D/E",
               "设计": "喂 S5.1 设计系统与 S7 Figma",
               "交互": "喂 S5.2 交互规格与 S6 demo"}
    miss_rep = []
    names = " ".join(os.path.basename(x) for x in glob.glob(os.path.join(d, '*')))
    for k, why in REPORTS.items():
        if k not in names and not re.search(k + r'[^\n]{0,12}(调研)?报告', idx_txt):
            miss_rep.append("%s调研报告（%s）" % (k, why))
    add("targeted-reports", "三份定向报告齐备（功能 / 设计视觉 / 交互，各自一份）",
        not miss_rep, miss_rep or "三份齐备")

    # ── 需求侧竞品 ──
    demand = re.findall(r'需求侧竞品', all_text + idx_txt)
    add("demand-side", "需求侧竞品 ≥3（用户真正在用来解决这件事的东西，常常不是同品类产品）",
        bool(demand), "已列出" if demand else
        "未见需求侧竞品 —— 只做供给侧会做出「比同行更好但没人换过来」的产品，"
        "因为用户对比的对象是他现在的凑合方案")

    # ── Can't vs Won't ──
    cw = re.findall(r"Can't|Won't|做不到|不愿做", all_text + idx_txt)
    add("cant-wont", "竞品取舍标了 Can't / Won't / TBD（Won't 比 Can't 持久得多）",
        bool(cw), "已标注" if cw else "未见 Can't/Won't 判断 —— 只记「它不做 X」记不到「为什么不做」")

    # ── 竞品有而我们没有（借鉴的唯一来源）──
    gapsec = re.search(r'竞品有而(我们|我)没有|我们没有的', all_text + idx_txt)
    add("gap-list", "有「竞品有而我们没有的」独立一节（借鉴的唯一来源）",
        bool(gapsec), "已列出" if gapsec else
        "缺这一节 —— 只对着自己的功能清单去查竞品，**查到的永远是自己已经想到的东西**")

    # ── 三路调研来源声明 ──
    routes = {"a 检索/爬取": r'deep\s*research|检索|爬取|WebSearch',
              "b GitHub 开源实现": r'开源|GitHub|github',
              "c Codex 外包": r'[Cc]odex'}
    miss_r = [k for k, pat in routes.items() if not re.search(pat, all_text + idx_txt)]
    add("three-routes", "三路调研都有交代（检索 · GitHub 开源实现 · Codex 外包）",
        not miss_r, miss_r or "三路齐备")

    # ── 反谄媚：报告必须表态 ──
    HEDGE = re.compile(r'各有优劣|各有千秋|见仁见智|有多种思路|可以考虑一下|也许可行|都有道理')
    hedges = sorted({m.group(0) for m in HEDGE.finditer(all_text + idx_txt)})
    add("no-hedging", "报告里不出现「各有优劣」这类不表态的句子（分析 ≠ 罗列）",
        not hedges, hedges and ("出现：%s —— 每条对比都要表态，并写明什么证据会推翻它" % "/".join(hedges))
        or "全部表态")

    # ── 一手用户接触 ──
    contact = re.search(r'(一手用户接触|用户访谈|无一手用户|未接触用户)', all_text + idx_txt)
    add("user-contact", "显式声明本轮有无一手用户接触",
        bool(contact), "已声明" if contact else
        "未声明 —— 约不到人是常态不是借口，但**必须写明「本轮无一手用户接触，结论强度下降」**，"
        "不许拿竞品分析冒充用户研究（那两件事回答的不是同一个问题）")

    add("no-fabrication", "无「据我所知 / 一般来说 / 业界一般」——编造在研究阶段的典型形态",
        not fab, fab or "未出现")

    # ⚠️ 2026-09-01 修：原写 `all(x["ok"] for x in res)`，而 **None（不适用）在 all() 里是假值** ——
    #    于是 N/A 被静默算成 FAIL。实测后果：insights.md 缺失时 `pattern-evidence` 记 N/A，
    #    门禁 `pass:false` 却**列不出任何 ok:false 的判据** —— 报了不合格但说不出是哪条。
    #    ⭐ 同一个 skill 里三处各写各的：definition-gate 写对了（排除 None），
    #      research/design-intent 没排除。三态契约必须一致：N/A 不进分母，也不算失败。
    # 🚨 2026-09-09 第五轮独立复核揪出：上面这条注释声称在修「N/A 被算成 FAIL」，
    #   它确实修了 —— **但同时把 UNABLE 也一起折叠成了通过**。
    #   实证：standing 列认不出时本门打印「➖ UNABLE：**本条没验**」，
    #   紧接着打印「✅ S2 出场门禁通过」并 **exit 0**。
    #   ⭐ `None` 一个值背了两个语义：**N/A（不适用，合法放行）** 与
    #     **UNABLE（没验成，本仓 P6 明令不许当通过）**。
    #     P6 的承诺在 `add()` 的显示层实现了，在 `sys.exit()` 上一字未动 ——
    #     又一次「声称≠实际」，而且就在写着「三态契约必须一致」的注释下面三行。
    #   ⇒ 拆成两个值：None=N/A（不进分母、算通过），UNABLE=没验（退 2，不算通过）。
    _failed = [x for x in res if x["ok"] is False]
    _unable = [x for x in res if x["ok"] == UNABLE]
    ok = not _failed and not _unable
    if '--json' in sys.argv:
        print(json.dumps({"pass": ok, "checks": res}, ensure_ascii=False, indent=1))
    else:
        for x in res:
            print("%s [%s] %s" % ({True: "✅", False: "❌", UNABLE: "⚠️"}.get(x["ok"], "➖"),
                                  x["id"], x["desc"]))
            for e in (x["ev"] if isinstance(x["ev"], list) else [x["ev"]]): print("      %s" % e)
        if _unable and not _failed:
            print("\n⚠️ 本门**没验完**：%d 条 UNABLE —— ⛔ 这不是通过，也不是不合格。"
                  % len(_unable))
            print("   补齐输入后重跑；在补齐之前，不许拿本门的绿灯当出场依据。")
        else:
            print("\n%s" % ("✅ S2 出场门禁通过" if ok
                            else "❌ 不许进 S3——研究不实，后面每一步都建在沙子上"))
        print("⚠️ 本门禁只验「有没有、可不可回溯」，**验不了研究得深不深**——")
        print("   深度判据是「能不能回答一个具体交互问题」，那要人读。")
    # 三态退出码（与 gate-run.py 登记的语义一致）：1=有发现，2=没验成，0=通过
    return 1 if _failed else (2 if _unable else 0)

def self_test():
    root = tempfile.mkdtemp(prefix="rg2-")
    def build(n=8, src=True, neg=True, empty=False, fab=False, matrix=True, sources=True,
              lines=True, insights=True, thin_ins=False, few_opp=False, contact=True,
              reports=True, demand=True, cantwont=True, market_mode='skip',
              gaplist=True, routes=True, hedge=False,
              domains=True, domain_gap=False, domain_count=12, two_col=False, four_col=False,
              odd_header=False,
              ledger=True, ledger_thin=False, scope_floor=None,
              landscape=True, landscape_axis=True, dimensions=True, dim_visible=True,
              access_product=None,
              decision_frame=True, contract_table=False,
              candidate_funnel=True, source_plan=True, shot_audit='ok',
              ai_scope='not-applicable', ai_complete=True,
              key_flows=True, flow_source=True,
              conflicts=True, conflicts_mode='full', isomorphic=True,
              # 2026-09-15 新契约旋钮（枚举式：一次只挪一样东西）
              carriers='full',        # full | missing_section | blank_status
              per_comp='full',        # full | gap（某可读竞品缺页面关系图）
              design='full',          # full | no_tokens | no_channel | no_states
              conclusions='full',     # full | no_innov | no_floor | no_counter | no_diff |
                                      # no_window | banned | banned_in_prohibition
              deepres='full',         # full | none | no_rb
              visual='full',          # full | none | no_shot | no_report_shot | ghost | no_clip | clip_missing
              compare_forms='full',   # full | none | no_align | no_chart | no_src | ghost_src
              meta_finding='full',    # full | none | no_ruler | no_infer
              version_ledger='full',  # full | none | no_fix | no_cause
              watch='full',           # full | none | no_trigger
              reach='full',           # full | no_col | empty | bad_value  （3.8.1 通道可达性）
              privacy='clean',        # clean | logged_no_decl | phone      （3.3 隐私红线）
              gap='clean',            # clean | discount | notdone | blocked  （9.1 缺口≠豁免）
              placeholder=False,      # True = 语料里残留脚手架占位（结构全绿内容全空）
              access_mode='web-browser', access_date=True, mac_permission=True,
              access_source=True, access_version=True,
              access_coverage=True, access_reason=True,
              surface_section=True, surface_unmapped=False,
              surface_wrong_run=False, surface_missing_af=False,
              run_comp='COMP-01', deep_comp=False,
              actions=True, priority=True, downstream=True,
              claims=True, atomic=True, atomic_dict_gap=False,
              atomic_fact_gap=False, atomic_duplicate=False,
              atomic_bad_status=False, atomic_absent_weak=False,
              atomic_unknown_weak=False, atomic_panel_gap=False, atomic_level_gap=False,
              atomic_downstream_gap=False, atomic_matrix_gap=False):
        d = tempfile.mkdtemp(dir=root)
        if domains:
            # two_col=True 造**真实产物形状**（两列）；默认三列（带编号列）——
            # 两种形状都必须被同一判据正确处理，见下方两条 two_col 用例的理由。
            if four_col:
                rows = ''.join('| %d | 域%d | %s |  |\n'
                               % (i, i, ('' if (domain_gap and i == 3) else '有输入'))
                               for i in range(1, domain_count + 1))
                head = ('# 下游决策域清单\n| # | 决策域 | %s | 备注 |\n'
                        '|---|---|---|---|\n' % ('填写状况' if odd_header else 'standing'))
            elif two_col:
                rows = ''.join('| 域%d | %s |\n' % (i, ('' if (domain_gap and i == 3) else '有输入'))
                               for i in range(1, domain_count + 1))
                head = '# 下游决策域清单\n| 决策域 | standing |\n|---|---|\n'
            else:
                rows = ''.join('| %d | 域%d | %s |\n' % (i, i, ('' if (domain_gap and i == 3) else '有输入'))
                               for i in range(1, domain_count + 1))
                head = '# 下游决策域清单\n| # | 决策域 | standing |\n|---|---|---|\n'
            io.open(os.path.join(d, 's2-decision-domains.md'), 'w', encoding='utf-8').write(head + rows)
        if ledger:
            io.open(os.path.join(d, 'research-decision-ledger.md'), 'w', encoding='utf-8').write(
                '# 账本\n### INS-001\n- 命题：x\n- 强度：high\n'
                + ('' if ledger_thin else '- 适用边界：桌面端重度用户；反例=轻量手机用户\n- 下游目标：PRD, FIGMA\n')
                + '- 最终处置：\n')
        if scope_floor:
            io.open(os.path.join(d, 'scope.md'), 'w', encoding='utf-8').write(
                '竞品数下限：%d · 理由：垂直领域全球仅此几家\n' % scope_floor)
        if landscape:
            rel = '直接竞品' if landscape_axis else '未分类'
            if ai_scope == 'applicable':
                ai_declaration = 'AI-SCOPE：适用 · 理由：核心流程包含 AI\n'
            elif ai_scope == 'not-applicable':
                ai_declaration = 'AI-SCOPE：不适用 · 理由：本产品没有 AI 能力\n'
            else:
                ai_declaration = ''
            if decision_frame and contract_table:
                frame_text = (
                    '## 研究合同\n| 字段 | 内容 |\n|---|---|\n'
                    '| `DECISION` | 是否进入本品类 |\n'
                    '| `QUESTION` | 哪类用户结果未满足 |\n'
                    '| `CHANGE-MIND` | 同口径结果无改善即改变判断 |\n'
                    '| `POSITIONING-LENS` | 重度桌面用户/可逆操作/不服务轻量浏览 |\n'
                    '| `STRATEGIC-TENSION` | 自动化 ↔ 控制力 |\n'
                    + ('| `SOURCE-PLAN` | 见按维度取证计划 |\n' if source_plan else ''))
            elif decision_frame:
                frame_text = (
                    'DECISION：是否进入本品类\nQUESTION：哪类用户结果未满足\n'
                    'CHANGE-MIND：同口径结果无改善即改变判断\n'
                    'POSITIONING-LENS：重度桌面用户/可逆操作/不服务轻量浏览\n'
                    'STRATEGIC-TENSION：自动化 ↔ 控制力\n')
            else:
                frame_text = ''
            io.open(os.path.join(d, 'competitor-landscape.md'), 'w', encoding='utf-8').write(
                '# 竞品双轴全景\n'
                + frame_text
                + ai_declaration
                + (('' if contract_table else 'SOURCE-PLAN：见按维度取证计划\n')
                   + '## 按维度取证计划\n| 维度 | 首选一手证据 | 独立复核 | 交互实测 | 降级 |\n'
                   '|---|---|---|---|---|\n| 功能 | 产品本体 | 用户证据 | 浏览器 | 未获取+原因 |\n'
                   if source_plan else '')
                + ('## 候选池（威胁与学习价值分列，不合成总分）\n'
                   '| CAND | 威胁价值 | 学习价值 | 纳入/排除/观察 | 排除理由/重看触发 | CLM |\n'
                   '|---|---|---|---|---|---|\n'
                   '| CAND-01 | 高：同用户 | 中：流程可学 | 纳入 | N/A：已纳入；版本变化重看 | CLM-001 |\n'
                   if candidate_funnel else '')
                + '| COMP | 对象 | 竞争关系 | 样本角色 |\n|---|---|---|---|\n'
                + ('| COMP-01 | A | %s | 品类头部 |\n' % rel)
                + ('| COMP-02 | B | 间接竞品 | 直接对手 |\n' if landscape_axis else
                   '| COMP-02 | B | 未分类 | 直接对手 |\n')
                + ('深挖对象：COMP-01\n' if deep_comp else '')
                + '类别覆盖：直接竞品 / 间接竞品 / 替代方案 / 潜在进入者；'
                  '样本角色：品类头部 / 直接对手 / 越级参照 / 反面样本。'
                  '无候选时写检索范围与未发现。\n')
        for i in range(n):
            profile = (("# 竞品%d\n" % i)
                       + ("来源 https://x.com/%d 访问日期 2026-08-30\n" % i if src else "来源：无\n")
                       + ("该产品的智能分组功能已下线。\n" if (neg and i == 0) else "")
                       + ("据我所知它们都这么做。\n" if (fab and i == 0) else ""))
            if i == 0 and surface_section:
                surface_run = 'RUN-02' if surface_wrong_run else 'RUN-01'
                interactive_surface = access_mode in ('web-browser', 'mac-computer-use', 'cdp-direct')
                disposition1 = ('' if surface_unmapped else
                                ('AF-001' if interactive_surface else 'BLOCKED'))
                disposition2 = 'AF-002' if interactive_surface else 'BLOCKED'
                result_label = ('[实测·%s·2026-08-30]' % access_mode
                                if interactive_surface else '[阻断·2026-08-30]')
                reason = ('N/A：已覆盖' if interactive_surface else
                          '账号/通道阻断；TBD-001；owner=Research；2026-09-02 补证')
                profile += (
                    '## 功能遍历覆盖账\n'
                    '| SURF | RUN | 一级模块 | 页面/区域/入口 | 用户可见动作/结果（最小颗粒） | AF 归并/处置 | 已打开 | 已实际操作 | 状态/失败/恢复 | 结果标签 | 截图/录屏/CLM 证据 | 未覆盖/排除理由 |\n'
                    '|---|---|---|---|---|---|---|---|---|---|---|---|\n'
                    '| SURF-001 | %s | 文件管理 | 列表/行菜单/重命名 | 修改单个对象名称；成功后列表显示新名称 | %s | 是 | %s | 冲突时保留原名，可重试/取消 | %s | CLM-001 / raw/a/rename.png | %s |\n'
                    % (surface_run, disposition1, ('是' if interactive_surface else '否'),
                       result_label, reason))
                if not surface_missing_af:
                    profile += (
                        '| SURF-002 | %s | 文件管理 | 成功提示/撤销 | 撤销最近一次重命名；对象恢复原名称 | %s | 是 | %s | 窗口过期后转历史记录恢复 | %s | CLM-002 / raw/a/undo.png | %s |\n'
                        % (surface_run, disposition2, ('是' if interactive_surface else '否'),
                           result_label, reason))
            io.open(os.path.join(d, 'c%d.md' % i), 'w', encoding='utf-8').write(profile)
        if matrix:
            dim_rows = (
                '| 定位与价值主张 | 有 | 未获取 |\n'
                '| 目标用户与购买者 | 有 | 未获取 |\n'
                '| 核心场景/JTBD | 有 | 未获取 |\n'
                '| 关键流程 | 有 | 未获取 |\n'
                '| 核心能力与覆盖度 | 有 | 未获取 |\n'
                '| 版本与迭代节奏 | 有 | 未获取 |\n'
                '| 价格与包装 | 有 | 未获取 |\n'
                '| 商业化与服务 | 有 | 未获取 |\n'
                '| 增长与留存 | 有 | 未获取 |\n'
                '| 用户体验 | 有 | 未获取 |\n'
                '| 视觉与品牌 | 有 | 未获取 |\n'
                '| 技术底层 | 有 | 未获取 |\n'
                + ('| 数据/安全/合规 | 有 | 未获取 |\n' if dimensions else '')
                + ('| 未登录/未付费档可见面 | 全功能可见 | 未登录零可见 |\n' if dim_visible else '')
            )
            ai_rows = (
                'AI 能力角色；AI 能力矩阵；效果质量（准确/召回/幻觉/误判）；'
                '使用门槛与信任解释；响应失败与降级人工接管；数据与评测；'
                '技术路线与壁垒（自研/开源/第三方）；单位成本与规模；AI 安全与合规。\n'
                if ai_complete else 'AI 能力角色；AI 能力矩阵。\n')
            io.open(os.path.join(d, 'matrix.md'), 'w', encoding='utf-8').write(
                ('AI-SCOPE：%s · 理由：%s\n' %
                 (('适用' if ai_scope == 'applicable' else ('缺失' if ai_scope == 'missing' else '不适用')),
                  ('核心流程包含 AI' if ai_scope == 'applicable' else
                   ('本产品没有 AI 能力' if ai_scope != 'missing' else '未声明'))))
                + "## 公共维度矩阵\n| 维度 | A | B |\n|---|---|---|\n" + dim_rows
                + "## 功能矩阵\n| AF | 功能 | A | B |\n|---|---|---|---|\n"
                  "| AF-001 | 用户触发后重命名单个对象 | FULL | %s |\n"
                  "| %s | 用户确认后撤销单次重命名 | FULL | UNKNOWN |\n"
                  % (("" if empty else "未获取"), ("AF-999" if atomic_matrix_gap else "AF-002"))
                + ("## AI 专项矩阵\n" + ai_rows if ai_scope == 'applicable' else
                   "## AI 专项矩阵\nN/A：没有 AI 能力。\n"))
        if atomic:
            dict_object = '' if atomic_dict_gap else '单个文件'
            if access_mode in ('web-browser', 'mac-computer-use', 'cdp-direct'):
                measured_tag = '[实测·%s·2026-08-30]' % access_mode
                fact_rows = (
                '| AF-001 | COMP-01 | %s | 文件列表/选中后触发 | 名称/默认保留扩展名 | 有编辑权限且名称唯一 | 原名称→新名称 | 行内显示新名称并提示已保存 | 冲突时提示并保留原名，可重试或取消 | 编辑者/Web/Free/单文件 | 3 步/5 秒/无需配置 | %s | RUN-01 / CLM-001 | Won\'t：优先单项可逆 |\n'
                '| AF-002 | COMP-01 | FULL | 编辑后 Undo 入口 | N/A：撤销没有输入字段 | 最近一次重命名成功 | 已重命名→原名称 | 恢复原名并提示已撤销 | 超时后入口消失，改由历史记录恢复 | 编辑者/Web/Free/最近一次 | 1 步/2 秒/窗口期成本 | %s | RUN-01 / CLM-002 | Can\'t：仅保留一次历史 |\n'
                '| AF-001 | COMP-02 | ABSENT | 已检索：导航/设置/帮助/定价页 | N/A：范围内未发现 | 已检索 Web/Free/v2 | N/A：范围内未发现 | 范围内未发现，不声称绝对没有 | 新入口出现时重开 | 编辑者/Web/Free/v2 | 未获取：功能未发现 | [检索后未发现·2026-08-30] | CLM-003 | TBD：可能受档位限制 |\n'
                '| AF-002 | COMP-02 | UNKNOWN | Enterprise 付费墙后阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：无法判断 | TBD-002 / owner=Research / 获取企业试用后重开 | 管理员/Web/Enterprise | 未获取：账号阻断 | [阻断·2026-08-30] | CLM-004 | TBD：获取试用后判断 |\n'
                % (('BROKEN' if atomic_bad_status else 'FULL'), measured_tag, measured_tag))
            else:
                fact_rows = (
                '| AF-001 | COMP-01 | %s | 账号/通道阻断，入口无法操作 | 未获取：阻断 | 未获取：阻断 | 未获取：阻断 | 未获取：无法判断 | TBD-001 / owner=Research / 获取测试权限后重开 | 编辑者/Web/Free | 未获取：阻断 | [阻断·2026-08-30] | CLM-001 | TBD：补证后判断 |\n'
                '| AF-002 | COMP-01 | UNKNOWN | 账号/通道阻断，撤销入口无法操作 | 未获取：阻断 | 未获取：阻断 | 未获取：阻断 | 未获取：无法判断 | TBD-002 / owner=Research / 获取测试权限后重开 | 编辑者/Web/Free | 未获取：阻断 | [阻断·2026-08-30] | CLM-002 | TBD：补证后判断 |\n'
                '| AF-001 | COMP-02 | ABSENT | 已检索：导航/设置/帮助/定价页 | N/A：范围内未发现 | 已检索 Web/Free/v2 | N/A：范围内未发现 | 范围内未发现，不声称绝对没有 | 新入口出现时重开 | 编辑者/Web/Free/v2 | 未获取：功能未发现 | [检索后未发现·2026-08-30] | CLM-003 | TBD：可能受档位限制 |\n'
                '| AF-002 | COMP-02 | UNKNOWN | Enterprise 付费墙后阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：无法判断 | TBD-004 / owner=Research / 获取企业试用后重开 | 管理员/Web/Enterprise | 未获取：账号阻断 | [阻断·2026-08-30] | CLM-004 | TBD：获取试用后判断 |\n'
                % ('BROKEN' if atomic_bad_status else 'UNKNOWN'))
            if atomic_fact_gap:
                fact_rows = fact_rows.splitlines()[0] + '\n'
            if atomic_duplicate:
                fact_rows += fact_rows.splitlines()[0] + '\n'
            if atomic_absent_weak:
                fact_rows = fact_rows.replace(
                    '| AF-001 | COMP-02 | ABSENT | 已检索：导航/设置/帮助/定价页 | N/A：范围内未发现 | 已检索 Web/Free/v2 | N/A：范围内未发现 | 范围内未发现，不声称绝对没有 | 新入口出现时重开 | 编辑者/Web/Free/v2 | 未获取：功能未发现 | [检索后未发现·2026-08-30] | CLM-003 | TBD：可能受档位限制 |',
                    '| AF-001 | COMP-02 | ABSENT | 未发现 | N/A：未发现 | Web/Free | N/A：未发现 | 竞品没有 | 无 | Web/Free | 未获取 | [未发现·2026-08-30] | CLM-003 | TBD |')
            if atomic_unknown_weak:
                fact_rows = fact_rows.replace(
                    '| AF-002 | COMP-02 | UNKNOWN | Enterprise 付费墙后阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：账号阻断 | 未获取：无法判断 | TBD-002 / owner=Research / 获取企业试用后重开 | 管理员/Web/Enterprise | 未获取：账号阻断 | [阻断·2026-08-30] | CLM-004 | TBD：获取试用后判断 |',
                    '| AF-002 | COMP-02 | UNKNOWN | 付费墙后 | 未获取 | 未获取 | 未获取 | 未获取 | 未获取 | Enterprise | 未获取 | [阻断·2026-08-30] | CLM-004 | 无法判断 |')
            panel_af2 = '' if atomic_panel_gap else '| AF-002 | 用户确认后撤销单次重命名 | 应支持 | FULL · 见事实账 | UNKNOWN · 见事实账 | 差异在窗口期；更长历史会推翻 |\n'
            level_last = '' if atomic_level_gap else '| 完成文件整理/文件管理/撤销 | 3 | 完成文件整理/文件管理 | AF-002 | COMP-01 FULL/COMP-02 UNKNOWN | 都有反馈 | COMP-02 付费墙阻断 | 误操作风险未知 | PRD AC-2/设计撤销态/技术历史/测试窗口 |\n'
            map_af2 = '' if atomic_downstream_gap else '| AF-002 | 可逆是基线 | FR-002 / AC-2 | FIGMA-02 撤销态 | FLOW-01/SCN-02/STATE-undo/OP-undo | adapt：延长窗口 | 1 步且 10 秒内可撤销 |\n'
            io.open(os.path.join(d, 'atomic-feature-ledger.md'), 'w', encoding='utf-8').write(
                '# 原子功能账本\n'
                '## 功能分解词典\n'
                '| AF | 功能路径 | 层级深度 | 父节点 | L0 用户进展/JTBD | L1 业务域/一级模块 | L2 能力族 | 角色 | 场景/入口/触发 | 对象/输入 | 前置/规则 | 单一动作 | 主要状态变化 | 可观察结果/完成定义 | 独立验收点/拆分说明 |\n'
                '|---|---|---:|---|---|---|---|---|---|---|---|---|---|---|---|\n'
                + ('| AF-001 | 完成文件整理/文件管理/重命名/AF-001 | 4 | 重命名 | 完成文件整理 | 文件管理 | 重命名 | 编辑者 | 文件列表选中一个文件 | %s | 有编辑权限且名称唯一 | 修改名称 | 原名称→新名称 | 单个目标名称更新且列表可见 | 可独立授权、失败和验收；批量另列 |\n' % dict_object)
                + '| AF-002 | 完成文件整理/文件管理/撤销/AF-002 | 4 | 撤销 | 安全完成文件整理 | 文件管理 | 撤销 | 编辑者 | 单次重命名成功后 | 最近一次重命名 | 仍在撤销窗口 | 撤销重命名 | 已重命名→原名称 | 单个目标恢复原名且显示成功反馈 | 可独立失败和验收；历史恢复另列 |\n'
                '## 原子功能事实账\n'
                '| AF | COMP | 状态 | 入口/触发 | 字段/参数/默认值 | 规则/前置 | 状态变化 | 结果/反馈/文案 | 失败/恢复 | 权限/端/档位/限额 | 质量/效率/用户代价 | 证据标签+日期 | RUN/CLM | 差异判读/Can\'t-Won\'t-TBD |\n'
                '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n'
                + fact_rows
                + '## 横向对比面板\n'
                  '### PANEL-01 · COMP-01—COMP-02\n'
                  '| AF | 原子功能定义 | 我们/目标 | COMP-01 | COMP-02 | 横向结论/证伪条件 |\n'
                  '|---|---|---|---|---|---|\n'
                  '| AF-001 | 用户触发后重命名单个对象 | 应支持 | FULL · 见事实账 | ABSENT · 见事实账 | 单项可逆优先；失败率上升会推翻 |\n'
                + panel_af2
                + '## 横向对比面板清单\n'
                  '| PANEL | 覆盖竞品 | AF 首尾 | AF 数量 | 与词典行集一致 | 重复/遗漏 | 校验人/日期 |\n'
                  '|---|---|---|---:|---|---|---|\n'
                  '| PANEL-01 | COMP-01/COMP-02 | AF-001—AF-002 | 2 | 是 | 无 | QA/2026-08-30 |\n'
                  '## 逐级横向对比\n'
                  '| 节点路径 | 层级深度 | 父节点 | 子 AF 全集 | 各竞品覆盖边界 | 共同模式 | 关键差异与原因 | 用户/业务代价 | 对我方下游输入 |\n'
                  '|---|---:|---|---|---|---|---|---|---|\n'
                  '| 完成文件整理 | 1 | N/A：根节点 | AF-001/AF-002 | COMP-01 全部/COMP-02 部分 | 均支持文件整理 | COMP-02 缺撤销 | 误操作恢复代价更高 | PRD/设计/技术/测试均需覆盖 |\n'
                  '| 完成文件整理/文件管理 | 2 | 完成文件整理 | AF-001/AF-002 | COMP-01 全部/COMP-02 部分 | 均从列表进入 | 恢复模型不同 | 多一步确认 | PRD/设计/技术/测试均需覆盖 |\n'
                  '| 完成文件整理/文件管理/重命名 | 3 | 完成文件整理/文件管理 | AF-001 | 两家均可见 | 均支持单项修改 | COMP-02 无撤销联动 | 恢复成本不同 | PRD FR-001/设计编辑态/技术冲突/测试边界 |\n'
                + level_last
                + '## 原子功能下游映射\n'
                  '| AF | 研究结论 | PRD FR/NFR/AC | Figma 画面/组件/状态 | HTML flow/scene/state/operation | adopt/adapt/reject/defer/watch | 验证指标/证伪条件 |\n'
                  '|---|---|---|---|---|---|---|\n'
                  '| AF-001 | 单项重命名是基线 | FR-001 / AC-1 | FIGMA-01 编辑态 | FLOW-01/SCN-01/STATE-edit/OP-rename | adopt：满足基础任务 | 3 步内完成且冲突可恢复 |\n'
                + map_af2)
        if key_flows:
            if access_mode is None:
                access_block = ''
            else:
                product = access_product or (
                    'Web' if access_mode == 'web-browser' else
                    ('macOS 原生' if access_mode == 'mac-computer-use' else
                     ('Electron 壳' if access_mode == 'cdp-direct' else '其他')))
                run_date = '2026-08-30' if access_date else ''
                version = (('v1.2 / 测试账号 / Pro' if access_mode == 'mac-computer-use'
                            else 'Web / 测试账号 / Free') if access_version else '')
                official = 'https://official.example/app' if access_source else ''
                if access_mode == 'mac-computer-use':
                    auth = ('用户已授权具体产品+版本+官方来源 2026-08-30'
                            if mac_permission else '未授权未下载')
                    label = '[实测·mac-computer-use·2026-08-30]'
                elif access_mode == 'cdp-direct':
                    auth = ('已安装且授权操作 2026-08-30'
                            if mac_permission else '未授权未下载')
                    label = '[实测·cdp-direct·2026-08-30]'
                elif access_mode == 'web-browser':
                    auth, label = '无需下载授权', '[实测·web-browser·2026-08-30]'
                else:
                    auth, label = '未授权未下载', '[宣称]'
                coverage = 'c0.md#功能遍历覆盖账' if access_coverage else ''
                blocker = ('付费档阻断，影响高级功能结论' if access_mode in ('retrieval-only', 'inaccessible')
                           and access_reason else ('无阻断' if access_reason else ''))
                access_block = (
                    '## 实测采集回执\n'
                    '| RUN | COMP | 产品形态 | 采集通道 |%s 执行日期 | 版本/账号/价格档 | 官方来源/入口 | 授权状态与日期 | 测试数据 | 外部副作用边界 | 功能覆盖账 | 结果标签 | 证据目录 | 阻断/降级理由 |\n'
                    '|---|---|---|%s---|---|---|---|---|---|---|---|---|---|---|\n'
                    '| RUN-01 | %s | %s | %s |%s %s | %s | %s | %s | 合成数据 | 不付费/不发布/不发送/不删除/不改真实账号/不新增系统权限 | %s | %s | raw/a/2026-08-30/ | %s |\n'
                    % ('' if reach == 'no_col' else ' 通道可达性 |',
                       '' if reach == 'no_col' else '---|',
                       run_comp, product, access_mode,
                       '' if reach == 'no_col' else
                       (' |' if reach == 'empty' else
                        (' 全敞开 |' if reach == 'bad_value' else ' 敞开 |')),
                       run_date, version, official,
                       auth, coverage, label, blocker))
            io.open(os.path.join(d, 'key-flows.md'), 'w', encoding='utf-8').write(
                '# 关键流程对比\n' + access_block
                + '## 同口径协议\nFLOW-01 同一任务与完成定义。\n'
                + ('图源 diagrams/FLOW-01.mmd\n```mermaid\nflowchart LR\nA-->B\n```\n'
                   if flow_source else '只有一张截图\n')
                + '步骤与完成时间对比。失败后可重试/取消并恢复。\n'
                  '下游目标：PRD → Figma → HTML。\n')
        if conflicts:
            _rows = ('| CONFLICT-01 | CAF-007 批量导出 | 仅 Pro 可见 [实测·web-browser·2026-09-15] '
                     '| 官网称全档支持 [官网·2026-08-01·2026-09-15] | 采信 A（实测） | 付费档差异 / 我们没找到入口 '
                     '| PRD 6.2 档位假设 |\n'
                     if conflicts_mode in ('full', 'no_adopt') else '')
            if conflicts_mode == 'no_adopt':
                _rows = _rows.replace('采信 A（实测）', '待定')
            _dual = ('| 问题 | 我方 /deep-research 结论 | codex /deep-research 结论 | 同向 | 置信升级 | 出处独立 |\n'
                     if conflicts_mode != 'no_dual' else '')
            _none = '本轮无冲突 · 理由：两路结论逐条一致\n' if conflicts_mode == 'none_declared' else ''
            io.open(os.path.join(d, 'conflicts.md'), 'w', encoding='utf-8').write(
                '# 冲突账\n'
                '| CONFLICT | 维度 | A 实测 | B 研究 | 采信 | 解释 | 影响 |\n|---|---|---|---|---|---|---|\n'
                + _rows + _none + '\n## 双路 deep-research 合并记录\n' + _dual)
        if isomorphic:
            io.open(os.path.join(d, 'prd-isomorphic.md'), 'w', encoding='utf-8').write(
                '# 载体映射产出（全员档 ①③④⑥ · 深挖档 ①–⑭）\n'
                '- 核心体验路径：COMP-01/core-path.d2（对应 PRD 4.4）\n'
                '- 产品模块图：COMP-01/module.d2（CM-01 列表 / CM-02 设置，对应 PRD 6.1）\n'
                '- 功能架构图：COMP-01/feature-tree.d2（叶子 = CAF-001…，对应 PRD 6.2）\n'
                '- 功能清单：COMP-01/feature-list.md（CAF-001 重命名 [实测·web-browser·2026-09-15]）\n'
                + ('' if per_comp == 'gap' else
                   '- 页面关系图：COMP-01/page-graph.d2（对应 PRD 6.3.1）\n')
                + '- 关键流程图：COMP-01/key-flow-1.d2（含异常边与降级边，对应 PRD 5.1）\n')
        if sources:
            io.open(os.path.join(d, 'sources.md'), 'w', encoding='utf-8').write(
                ("# 来源\n- https://x 2026-08-30\n"
                 + ("| CLM | 主张 | 状态 | 发布日 | 访问日 | 失效日 |\n"
                    "|---|---|---|---|---|---|\n"
                    "| CLM-001 | 能力可用 | verified | 2026-08-29 | 2026-08-30 | 2026-11-30 |\n"
                    if claims else "")))
        if lines:
            if market_mode == 'skip':
                market_line = ('③ 市场线 本轮不做 · 理由：当前决定不依赖市场规模 · '
                               '声明上限：不判断产品/PRD/设计/交互的市场容量与增长\n')
            elif market_mode == 'skip-thin':
                market_line = '③ 市场线 本轮不做\n'
            else:
                market_line = '③ 市场线 已完成 · 结论见 market-landscape.md\n'
            io.open(os.path.join(d, 'lines.md'), 'w', encoding='utf-8').write(
                "① 用户线 结论：见 insights\n② 竞品线 结论：见矩阵\n" + market_line
                + "④ 数据线 结论：漏斗\n⑤ 技术可能性线 本轮不做\n"
                + ("本轮有一手用户接触 5 人\n" if contact else "")
                + ("需求侧竞品：微信收藏 / 系统相册 / 文件夹\n" if demand else "")
                + ("取舍判断：Won't（伤自己商业模式）\n" if cantwont else "")
                + ("## 竞品有而我们没有的\n- 版本历史\n" if gaplist else "")
                + ("三路来源：deep research 已做 / GitHub 开源实现已读 / Codex 外包已回\n" if routes else "")
                + ("两家各有优劣\n" if hedge else ""))
        if market_mode == 'done':
            io.open(os.path.join(d, 'market-landscape.md'), 'w', encoding='utf-8').write(
                '# 市场全景\n'
                '| 字段 | 内容 |\n|---|---|\n'
                '| `DECISION` | 是否进入本品类 |\n| `QUESTION` | 谁会先采用 |\n'
                '| `CHANGE-MIND` | 采购行为无变化 |\n| `SCOPE` | 中国/桌面/2026 |\n'
                '## 品类定义与边界\n宽窄口径与纳入排除。\n'
                '## 规模与增长\nN/A + 理由：本决定不依赖 TAM/SAM/SOM。\n'
                '## 需求、采用与拒绝\n购买触发与迁移阻力。\n'
                '## 供给、价值链与商业结构\n渠道、利润池与锁定。\n'
                '## 趋势、拐点与监管\n领先指标与反向证据。\n'
                '## 相邻市场与反模式\n可迁移机制与不可迁移边界。\n'
                '## 决策摘要：事实 → 推断 → 建议\n风险、反证与什么会推翻建议。\n'
                '## 下游覆盖\nPRD 定位；Figma 只接行为约束；HTML 只接环境约束。\n'
                '## 来源与日期\nCLM-001 https://x 访问日期 2026-08-30。\n')
        if reports:
            for k in ("功能", "设计视觉", "交互"):
                # ⚠️ no_report_shot 只抽掉**报告**的图（结构物照常有）——
                #   反例一次只挪一样东西，否则红的原因不唯一，证明不了新判据在守什么。
                _shot = ('' if visual in ('none', 'no_shot', 'no_report_shot')
                         else '\n📎 raw/comp01/2026-09-15/COMP-01-first-screen.png\n')
                io.open(os.path.join(d, '%s调研报告.md' % k), 'w', encoding='utf-8').write(
                    "# %s调研报告\n" % k + _shot)
        if insights:
            ev = "[来源·访谈1] [来源·访谈2] [来源·工单]" if not thin_ins else "[来源·访谈1]"
            opp = "- 解法A\n- 解法B\n- 解法C\n" if not few_opp else "- 解法A\n"
            io.open(os.path.join(d, 'insights.md'), 'w', encoding='utf-8').write(
                "# 研究综合\n## 模式\n多个用户先导出再手工改\n"
                "## 洞察 不信任批量操作\n%s\n## 机会 让批量失败可逐条撤销\n%s"
                "%s%s" % (ev, opp,
                           ("\n## 学习 / 借鉴 / 规避 / 差异化\n学习基线；借鉴恢复；规避静默失败；差异化逐条撤销。\n"
                            if actions else ""),
                           ("## 机会优先级\nOPP-01：P1；理由：证据中等且可逆。\n"
                            if priority else "")))
        if downstream:
            io.open(os.path.join(d, 'downstream-coverage.md'), 'w', encoding='utf-8').write(
                '# 下游双向覆盖\n## 下游 → 研究\n'
                '| 下游 | 字段 | 锚点 | 状态 |\n|---|---|---|---|\n'
                '| PRD | 功能/状态 | CLM-001/INS-001 | 已覆盖 |\n'
                '| Figma | 组件/全状态 | INS-001 | N/A+理由 |\n'
                '| HTML | flow/scene/state | FLOW-01 | 明确未知 |\n'
                + ('' if carriers == 'missing_section' else (
                    '## PRD 载体对账\n'
                    '| PRD 载体 | 竞品侧产出物 | 全员档 n/N | 深挖档 n/N | 状态 |\n'
                    '|---|---|---|---|---|\n'
                    '| 4.4 用户流程图 | core-path.d2 | 2/2 | 1/1 | 已覆盖 |\n'
                    '| 5.1 业务流程图 | key-flow-1.d2 | — | 1/1 | 已覆盖 |\n'
                    '| 6.1 产品模块图 | module.d2 | 2/2 | 1/1 | 已覆盖 |\n'
                    '| 6.2 功能清单 | feature-list.md | 2/2 | 1/1 | 已覆盖 |\n'
                    '| 6.2.1 功能架构图 | feature-tree.d2 | — | 1/1 | 已覆盖 |\n'
                    '| 6.3.1 页面关系图 | page-graph.d2 | 2/2 | 1/1 | 已覆盖 |\n'
                    '| 七章 设计交互 | design-tokens.md | 简表 2/2 | 1/1 | 已覆盖 |\n'
                    '| 附件 D 字段规格 | field-specs.md | — | 1/1 | %s |\n'
                    '| 附件 E 状态机 | state-coverage.md | — | 1/1 | 已覆盖 |\n'
                    % ('' if carriers == 'blank_status' else '未获取：付费档阻断')))
                + '## 研究 → 下游\nINS-001 → PRD/Figma/HTML：adapted；OPP-01：watch。\n')
        # ── 2026-09-15 新契约的夹具 ──
        if design != 'no_tokens':
            io.open(os.path.join(d, 'design-tokens.md'), 'w', encoding='utf-8').write(
                '# 设计令牌反查表 COMP-01\n'
                '| 令牌族 | 取到的值 | %s |\n|---|---|---|\n'
                '| 色 | 主色 #2B6CF6 / 中性 5 阶 | %s |\n'
                '| 字号 | 12/14/16/20/28，字重 400/500/600 | %s |\n'
                '| 间距 | 基数 8，栅格 12 列 | %s |\n'
                '## 组件清单\n按钮 3 档 2 尺寸，禁用与加载态齐；弹层：模态用于不可逆，内联用于校验。\n'
                '## 交互模式清单\n撤销策略：删除给 5s 撤销；导出二次确认。动效量级：短 100–200ms。\n'
                % (('取证通道' if design != 'no_channel' else '备注'),
                   *(['[实测·CDP computed·2026-09-15]'] * 3 if design != 'no_channel'
                     else ['看着挺协调'] * 3)))
        if design != 'no_states':
            io.open(os.path.join(d, 'state-coverage.md'), 'w', encoding='utf-8').write(
                '# 状态覆盖矩阵 COMP-01\n'
                '| CAF | 首次 | 空 | 加载 | 成功 | 部分失败 | 失败 | 无权限 | 离线 | 极值 | 恢复 |\n'
                '|---|---|---|---|---|---|---|---|---|---|---|\n'
                '| CAF-001 | 有：引导卡 | 有：空态给入口 | 有：骨架 | 有：行内提示 | 有：逐条重试 '
                '| 有：错误文案 | 未获取：无多角色 | 有：离线横幅 | 有：超长截断提示 | 有：可撤销 |\n')
        if conclusions != 'no_innov':
            _floor = ('样本门槛：≥3 家且 ≥50% 可读样本同向；达不到只记个例观察。\n'
                      if conclusions != 'no_floor' else '')
            _counter = '反例名单：COMP-02（仍走旧做法）。\n' if conclusions != 'no_counter' else ''
            io.open(os.path.join(d, 'innovation-trends.md'), 'w', encoding='utf-8').write(
                '# 创新点与趋势\n## 创新点\n'
                '| INNOV | 竞品 | 做了什么别人没做的 | 解决的旧痛点 | 代价 | 证据 |\n|---|---|---|---|---|---|\n'
                '| INNOV-01 | COMP-01 | 把先搜索再筛选改成边说边收敛 | 筛选步骤多 | 可控性下降 | CLM-001 |\n'
                '## 趋势\n'
                '| TREND | 类型 | 内容 | 支持名单 |\n|---|---|---|---|\n'
                '| TREND-01 | 收敛 | 一级导航都收敛为命令面板 | COMP-01/03/04 |\n' + _floor + _counter)
        if conclusions != 'no_diff':
            # ⚠️ no_window 必须**真的把窗口期整列拿掉**（表头 + 值 + 正文）——
            #   只删正文那一句时，表里残留的「窗口期/一年」会让判据照样命中，
            #   反例显示红了但红的不是它声称测的东西（本仓「假绿夹具」母题）。
            _ban = ('我们的优势是更好用。\n' if conclusions == 'banned'
                    else ('⛔ 禁用表述：不许写「更好用」「更智能」。\n'
                          if conclusions == 'banned_in_prohibition' else ''))
            if conclusions == 'no_window':
                _tbl = ('| DIFF | 未满足结果 | 我们凭什么能做 | 对方为何不容易跟 |\n|---|---|---|---|\n'
                        '| DIFF-01 | 跨端续写今天都给不了 | 我们有既有设备侧资产与积累 | '
                        '结构性冲突：会伤它的云订阅 |\n'
                        + '| WATCH-01 | 上游框架已被两家采用为底座 | 会让 DIFF-01 作废 | 复查触发：当它的 cron 进入正式版 | 加速 |\n')
            else:
                _tbl = ('| DIFF | 未满足结果 | 我们凭什么能做 | 对方为何不容易跟 | 窗口期 |\n'
                        '|---|---|---|---|---|\n'
                        '| DIFF-01 | 跨端续写今天都给不了 | 我们有既有设备侧资产与积累 | '
                        '结构性冲突：会伤它的云订阅 | 一年 |\n'
                        '窗口期：约一年，到期靠数据飞轮续。\n'
                        + ('' if watch == 'none' else
                           ('| WATCH-01 | 上游框架已被采用 | 会让 DIFF-01 作废 | 2026 年底前 | 加速 |\n'
                            if watch == 'no_trigger' else
                            '| WATCH-01 | 上游框架已被两家采用为底座 | 会让 DIFF-01 作废 | '
                            '复查触发：当它的 cron 进入正式版 | 加速 |\n')))
            io.open(os.path.join(d, 'differentiation.md'), 'w', encoding='utf-8').write(
                '# 差异化竞争优势\n' + _tbl + _ban)
        # ⚠️ 2026-09-15：既有 SURF 覆盖账夹具一直写着 `raw/a/rename.png`、`raw/a/undo.png`，
        #   却**从没真的创建过它们** —— 新加的 visual-evidence 判据第一跑就抓到。
        #   ⭐ 判据没错，是夹具不诚实：一份合格的研究产物，引用的证据必须真的在。
        _rawa = os.path.join(d, 'raw', 'a'); os.makedirs(_rawa, exist_ok=True)
        for _f in ('rename.png', 'undo.png'):
            io.open(os.path.join(_rawa, _f), 'w', encoding='utf-8').write('x')
        # ── 2026-09-15 第二批夹具：视觉证据 / 对齐表 / 元发现 / 版本对账 ──
        if visual != 'none':
            _raw = os.path.join(d, 'raw', 'comp01', '2026-09-15')
            os.makedirs(_raw, exist_ok=True)
            for _f in ('COMP-01-first-screen.png', 'COMP-01-CAF-001-success.png',
                       'COMP-01-CAF-001-fail.png', 'COMP-01-dense.png',
                       'COMP-01-state-empty.png'):
                io.open(os.path.join(_raw, _f), 'w', encoding='utf-8').write('x')
            if visual not in ('no_clip', 'clip_missing'):
                io.open(os.path.join(_raw, 'COMP-01-import-progress.gif'),
                        'w', encoding='utf-8').write('x')
            _p = 'raw/comp01/2026-09-15/'
            _shot = ('' if visual == 'no_shot' else '📎 %sCOMP-01-first-screen.png\n' % _p)
            io.open(os.path.join(d, 'design-tokens.md'), 'a', encoding='utf-8').write(
                '\n## 视觉证据\n' + _shot
                + ('' if visual == 'no_shot' else '📎 %sCOMP-01-dense.png\n' % _p))
            io.open(os.path.join(d, 'state-coverage.md'), 'a', encoding='utf-8').write(
                '\n📎 %sCOMP-01-state-empty.png\n' % _p)
            _mshot = ('📎 %sCOMP-01-CAF-001-success.png · %sCOMP-01-CAF-001-fail.png\n'
                      % (_p, _p)) if visual != 'ghost' else \
                     ('📎 %s根本不存在的图.png\n' % _p)
            io.open(os.path.join(d, 'matrix.md'), 'a', encoding='utf-8').write(
                '\n## 功能对比的截图证明\n' + _mshot)
            if visual == 'no_clip':
                _clip = '（本轮无关键/创新动效：该品类转场均为平台默认行为）\n'
            elif visual == 'clip_missing':
                _clip = '| 导入进度条 | **关键动效**（承载进度状态） | 待补 |\n'
            else:
                _clip = ('| 导入进度条 | **关键动效**（承载进度状态） | '
                         '📎 %sCOMP-01-import-progress.gif |\n' % _p)
            io.open(os.path.join(d, 'c0.md'), 'a', encoding='utf-8').write(
                '\n## 交互与动效\n| 对象 | 判定 | 证据 |\n|---|---|---|\n' + _clip)
        if compare_forms != 'none':
            io.open(os.path.join(d, 'insights.md'), 'a', encoding='utf-8').write(
                '\n## 结构层横向对比\n'
                + ('' if compare_forms == 'no_align' else
                   '### 入口族 × 竞品 同栏对齐表\n| 入口族 | COMP-01 | COMP-02 |\n|---|---|---|\n'
                   '| 对话/任务 | 新建任务 | 新会话 |\n')
                + ('' if compare_forms == 'no_chart' else
                   ('### 跨竞品对照图\n只做了一张对照图。\n' if compare_forms == 'no_src' else
                    '### 跨竞品对照图\ncross-compare/module-compare.d2\n'))
                + '差异：COMP-02 无编排族 → 原因：它押在单次对话 → 对我们：编排要保留。\n')
        if compare_forms not in ('none', 'no_chart', 'no_src', 'ghost_src'):
            os.makedirs(os.path.join(d, 'cross-compare'), exist_ok=True)
            io.open(os.path.join(d, 'cross-compare', 'module-compare.d2'), 'w',
                    encoding='utf-8').write('COMP-01 -> 对话族\nCOMP-02 -> 对话族\n')
        if compare_forms == 'ghost_src':
            io.open(os.path.join(d, 'insights.md'), 'a', encoding='utf-8').write(
                '\n## 结构层横向对比\n### 入口族 × 竞品 同栏对齐表\n| 入口族 | COMP-01 |\n|---|---|\n'
                '| 对话/任务 | 新建任务 |\n### 跨竞品对照图\ncross-compare/ghost.d2\n'
                '差异：A → 原因：B → 对我们：C。\n')
        if meta_finding != 'none':
            io.open(os.path.join(d, 'insights.md'), 'a', encoding='utf-8').write(
                '\n## 取证过程的元发现\n'
                + ('用同一把尺子（直启带调试端口）量全部竞品，通道可达性分四档。\n'
                   if meta_finding != 'no_ruler' else '各家情况不同，有的能读有的不能。通道可达性有差异。\n')
                + ('⚠️ [推断] 依据=本轮通道实测，未向厂商求证是否有意为之。\n'
                   if meta_finding != 'no_infer' else '这说明它们就是这么设计的。\n'))
        if placeholder:
            io.open(os.path.join(d, 'c0.md'), 'a', encoding='utf-8').write(
                '\n## 待填\n| 项 | 值 |\n|---|---|\n| 定位 | \u27e8TODO\u27e9 |\n')
        if placeholder == 'diagram':
            os.makedirs(os.path.join(d, 'cross-compare'), exist_ok=True)
            io.open(os.path.join(d, 'cross-compare', 'stub.d2'), 'w', encoding='utf-8').write(
                'direction: right\n"\u27e8TODO\u27e9" -> "\u27e8TODO\u27e9"\n')
        if gap != 'clean':
            _gp = {
                'discount': '\n## 诚实缺口\n本报告不是一份完整 S2 交付，仅供参考。\n',
                'notdone': '\n## 诚实缺口\n| 没做的事 | 影响 |\n|---|---|\n'
                           '| B 通道一轮未跑 | 定位/增长类结论一条都没有 |\n',
                'blocked': '\n## 诚实缺口\n| 没做的事 | 影响 |\n|---|---|\n'
                           '| COMP-02 未登录态零可见面 | 被**登录墙**挡住，补证计划：申请测试账号 |\n',
            }[gap]
            io.open(os.path.join(d, 'c0.md'), 'a', encoding='utf-8').write(_gp)
        if privacy != 'clean':
            _pv = {
                # 只读到「已登录」而没有清场声明 —— 这是要红的那一个
                'logged_no_decl': '\n本轮 COMP-01 在**已登录**态取证（CDP 直读侧栏）。\n',
                # 有声明，但语料里混进了高信号私人标识 —— 只挪这一样
                'phone': '\n本轮 COMP-01 在**已登录**态取证。隐私：只取产品骨架，未记录用户内容。\n'
                         '侧栏里看到的联系人：' + '138' + '0' * 8 + '\n',
                # 有声明 ⇒ 放行（证明"声明这条路"真的走得通，不是靠语料里没出现过关键词）
                'logged_declared': '\n本轮 COMP-01 在**已登录**态取证。'
                                   '隐私：只取产品骨架，未记录用户内容。\n',
                # 否定语境 ⇒ 不许误伤（门不能惩罚正确用法）
                'negated': '\n本轮全程未登录态取证，⛔ 不读已登录界面，不碰个人账号。\n',
            }[privacy]
            io.open(os.path.join(d, 'c0.md'), 'a', encoding='utf-8').write(_pv)
        if version_ledger != 'none':
            io.open(os.path.join(d, 'competitor-landscape.md'), 'a', encoding='utf-8').write(
                '\n## 版本对账\n| 版本 | 定位 | 处置 |\n|---|---|---|\n'
                '| v1 | 初版 | 归档，不再引用 |\n| v2 | 当前正本 | — |\n'
                + ('⚠️ v1 纠错：旧结论「它无法被 CDP 读取」→ 新结论「它是 Electron 壳可读」；\n'
                   + ('**真因**：此前读不到是登录墙，不是无法 CDP。\n'
                      if version_ledger != 'no_cause' else '')
                   if version_ledger != 'no_fix' else ''))
        if deepres != 'none':
            _dr = os.path.join(d, 'deep-research'); os.makedirs(_dr, exist_ok=True)
            io.open(os.path.join(_dr, 'R-A-COMP-01.md'), 'w', encoding='utf-8').write(
                '# R-A 竞品单体轮 COMP-01\n定价：Pro 每月 20 美元。\n'
                '版本轨迹：近 12 个月新增命令面板、移除旧侧栏。\n'
                '来源 https://official.example/pricing 发布日 2026-07-01 访问日 2026-09-15\n')
            if deepres != 'no_rb':
                io.open(os.path.join(_dr, 'R-B-行业.md'), 'w', encoding='utf-8').write(
                    '# R-B 行业轮\n品类边界正在从工具向 agent 迁移。\n'
                    '来源 https://analyst.example/report 发布日 2026-08-01 访问日 2026-09-15\n')
        # 截图目检记录：**扫本次真正建出来的图**再登记，⛔ 不硬写文件名
        #   （硬写的话，任何改动夹具图集的人都会让这条静默失配）。
        if shot_audit != 'missing':
            _imgs = []
            for _dp, _dn, _fn in os.walk(d):
                for _f in _fn:
                    if _f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        _imgs.append(_f)
            if shot_audit == 'unlisted' and _imgs:
                _imgs = _imgs[1:]          # 反例：漏登记一张
            io.open(os.path.join(d, 'screenshot-masking-audit.md'), 'w',
                    encoding='utf-8').write(
                '# 截图外发前目检记录\n\n目检人：夹具 ｜ 目检日期：2026-09-15\n\n'
                '| 图 | 目检所见 | 处置 |\n|---|---|---|\n'
                + ''.join('| `%s` | 无可识别身份信息 | 无需处置 |\n' % _f for _f in _imgs))
        return d
    def run(d): return subprocess.call([sys.executable, os.path.abspath(__file__), d],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def build_ban_context():
        """在正例基础上，只加一句**禁令语境**的句子（模板里就是这么写的）。

        ⭐ 隔离原则同 build_lines_missing_one：在正例上只挪动一样东西。
        """
        d = build()
        # ⚠️ 必须写进**竞品档案**：no-fabrication 扫的是 all_text，而 all_text
        #   只累积竞品档案（不含 lines.md）。第一版写进 lines.md ⇒ 旧判据也不红，
        #   反向确认当场暴露「这条用例没复现前置条件」。
        f = sorted(glob.glob(os.path.join(d, '*.md')))
        f = [x for x in f if os.path.basename(x) not in
             ('lines.md', 'insights.md', 'research-decision-ledger.md',
              's2-decision-domains.md', 'scope.md', 'atomic-feature-ledger.md')][0]
        txt = io.open(f, encoding='utf-8').read()
        io.open(f, 'w', encoding='utf-8').write(
            txt + "\n⛔ 「据我所知」「一般来说」「业界一般」一律禁止——编造最像事实的形态。\n")
        return d

    def build_domains(replace):
        """在正例基础上**只改 s2-decision-domains.md 一处** —— 其余判据保持绿。

        ⭐ 隔离原则同 build_lines_missing_one：不重写夹具，只挪一样东西。
        """
        d = build()
        f = os.path.join(d, 's2-decision-domains.md')
        io.open(f, 'w', encoding='utf-8').write(replace)
        return d

    _H2 = '# 下游决策域清单\n\n| 决策域 | standing |\n|---|---|\n'

    def build_unrecognizable_standing():
        """在正例基础上**只让 standing 列认不出来** —— 其余判据全部保持绿。

        ⭐ 隔离原则同上：不重写夹具，只改表头名与列内容。
        ⚠️ 这条用例守的是**退出码**，不是显示层：上一版显示层已经打印
          「➖ UNABLE：本条没验」，而下一行照样打印「✅ S2 出场门禁通过」并 exit 0。
          ⇒ 期望 **2**（没验成），⛔ 不是 0，也不是 1。
        """
        d = build()
        f = os.path.join(d, 's2-decision-domains.md')
        txt = io.open(f, encoding='utf-8').read()
        # 表头改成认不出的名字，列值也换成认不出三态的自由文本
        txt = txt.replace('standing', '备注').replace('有输入', '见 final analysis 报告')
        io.open(f, 'w', encoding='utf-8').write(txt)
        return d

    def build_ban_after():
        """禁令词写在命中**之后** —— 第五轮复核的 B8 绕过。

        ⭐ 与 build_ban_context 成对：一个必须放行（禁令在前＝在讲别写它），
          一个必须判红（句尾补一句「不要照抄」不能把编造洗白）。
        """
        d = build()
        f = sorted(glob.glob(os.path.join(d, '*.md')))
        f = [x for x in f if os.path.basename(x) not in
             ('lines.md', 'insights.md', 'research-decision-ledger.md',
              's2-decision-domains.md', 'scope.md', 'atomic-feature-ledger.md')][0]
        txt = io.open(f, encoding='utf-8').read()
        io.open(f, 'w', encoding='utf-8').write(
            txt + "\n据我所知它们都这么做 —— 不要照抄。\n")
        return d

    def build_lines_missing_one():
        """文件都在、其余标记全保留，**只摘掉第 ③ 条线** —— 让 five-lines 成为唯一的红。

        ⚠️ 第一版把 lines.md 整个重写了，连带删掉了 demand-side / cant-wont /
        gap-list / three-routes 的标记文本，于是同时红 5 条 —— **又不是隔离用例**。
        ⭐ 隔离要靠「在正例基础上只挪走一个东西」，不能靠「重写一份看起来差不多的」。
        """
        d = build()
        f = os.path.join(d, 'lines.md')
        txt = re.sub(r'^.*③\s*市场线[^\n]*\n?', '',
                     io.open(f, encoding='utf-8').read(), flags=re.M)
        io.open(f, 'w', encoding='utf-8').write(txt)
        return d

    cases = [("正例", build(), 0),
             # ⭐ 3.8.1 通道可达性逐竞品必填（2026-09-16）
             ("反例 RUN 表没有「通道可达性」列", build(reach='no_col'), 1),
             ("反例 通道可达性格子空着（空≠它没有，是我没量）", build(reach='empty'), 1),
             ("反例 通道可达性用了六档之外的自创值", build(reach='bad_value'), 1),
             # ⭐ 3.3 隐私红线（2026-09-16）
             ("反例 已登录态取证却无隐私清场声明", build(privacy='logged_no_decl'), 1),
             ("反例 有声明但语料混进手机号", build(privacy='phone'), 1),
             ("正例 已登录取证 + 写了清场声明 → 放行", build(privacy='logged_declared'), 0),
             ("正例 「⛔ 不读已登录界面」是否定语境 → 不许误伤", build(privacy='negated'), 0),
             # ⭐ 9.1 诚实缺口不是豁免通道（2026-09-16）
             ("反例 给整份产物打折「不是完整交付/仅供参考」", build(gap='discount'), 1),
             ("反例 诚实缺口里装「我没做」而非「不可能取得」", build(gap='notdone'), 1),
             ("正例 缺口点名了外部阻断者（登录墙）→ 放行", build(gap='blocked'), 0),
             ("反例 对照图没有可解析源（只写了「对照图」三个字）", build(compare_forms='no_src'), 1),
             ("反例 对照图源文件被引用但不存在", build(compare_forms='ghost_src'), 1),
             # ⭐ 脚手架占位守卫（2026-09-16，与 scaffold.py 同批）
             ("反例 语料里残留脚手架占位（结构全绿内容全空）", build(placeholder=True), 1),
             ("反例 **图**是占位桩（只扫 .md 会放过它）", build(placeholder='diagram'), 1),
             ("正例 研究合同按模板表格填写", build(contract_table=True), 0),
             ("正例 AI 适用且九域齐备", build(ai_scope='applicable'), 0),
             ("正例 市场线执行并独立交付", build(market_mode='done'), 0),
             ("反例 只有 5 家", build(n=5), 1),
             ("反例 档案无来源日期", build(src=False), 1),
             ("反例 无反面样本", build(neg=False), 1),
             ("反例 矩阵有空格子", build(empty=True), 1),
             ("反例 缺原子功能账本", build(atomic=False), 1),
             ("反例 原子词典缺对象/输入", build(atomic_dict_gap=True), 1),
             ("反例 AF×COMP 少一条事实", build(atomic_fact_gap=True), 1),
             ("反例 AF×COMP 重复一条事实", build(atomic_duplicate=True), 1),
             ("反例 原子事实使用非法状态", build(atomic_bad_status=True), 1),
             ("反例 ABSENT 没有检索入口与范围", build(atomic_absent_weak=True), 1),
            # 截图目检：打码靠注入 CSS，改版即静默失效 ⇒ 机器只能守「有没有人逐张看过」
            ("反例 有截图却没有目检记录（打码是否生效无人确认）",
             build(shot_audit='missing'), 1),
            ("反例 目检记录漏登记了一张图（抽查看过≠逐张看过）",
             build(shot_audit='unlisted'), 1),
             ("反例 UNKNOWN 没有阻断、TBD 与 owner", build(atomic_unknown_weak=True), 1),
             ("反例 横向面板漏一个 AF", build(atomic_panel_gap=True), 1),
             ("反例 逐级横向对比漏一个中间节点", build(atomic_level_gap=True), 1),
             ("反例 原子功能漏下游映射", build(atomic_downstream_gap=True), 1),
             ("反例 matrix 投影漏一个 AF", build(atomic_matrix_gap=True), 1),
             ("反例 缺 sources.md", build(sources=False), 1),
             ("反例 出现「据我所知」", build(fab=True), 1),
             # 🚨 2026-09-09：判据原来全文 grep 这些词 ⇒ **模板里教人「一律禁止」的那句话
             #    自己被判成编造**（research-brief 模板因此常红）。门不许惩罚正确用法。
             ("正例 禁令语境里出现这些词不算编造（模板在教人别写它）",
              build_ban_context(), 0),
             ("反例 缺 matrix.md", build(matrix=False), 1),
             ("反例 缺竞品双轴全景", build(landscape=False), 1),
             ("反例 COMP 行缺竞争关系轴", build(landscape_axis=False), 1),
             ("反例 研究合同缺定位镜头与战略张力", build(decision_frame=False), 1),
             ("反例 只交最终名单没有候选池形成记录", build(candidate_funnel=False), 1),
             ("反例 缺按维度取证与降级计划", build(source_plan=False), 1),
             ("反例 公共矩阵缺数据安全合规维度", build(dimensions=False), 1),
             ("反例 公共矩阵缺未登录未付费档可见面维度", build(dim_visible=False), 1),
             ("反例 未声明 AI 适用性", build(ai_scope='missing'), 1),
             ("反例 AI 适用但九域不全", build(ai_scope='applicable', ai_complete=False), 1),
             ("反例 缺关键流程对比", build(key_flows=False), 1),
             ("反例 关键流程没有可编辑图源", build(flow_source=False), 1),
             # 交互式采集回执采用**正例基线只变一个字段**的隔离用例；否则“缺 key-flows”
             # 会同时触发流程与回执两道门，无法证明 interactive-access 自己会拦。
             ("正例 macOS 获授权后 Computer Use 实测", build(access_mode='mac-computer-use'), 0),
             ("正例 Electron 壳 CDP 直读实测", build(access_mode='cdp-direct'), 0),
             # ── 2026-09-15 用户三项指令的新契约（每条反例都配了方向相反的正例）──
             ("反例 downstream 缺 PRD 载体对账小节（载体级缺口无人对账）",
              build(carriers='missing_section'), 1),
             ("反例 某载体状态留空（留白与漏了在产物上一样）",
              build(carriers='blank_status'), 1),
             ("反例 可读竞品缺全员档页面关系图（⛔ 不许挑几个代表画）",
              build(per_comp='gap'), 1),
             ("反例 缺设计令牌表（S5/S7 与 PRD 七章无据可用）", build(design='no_tokens'), 1),
             ("反例 令牌表无取证通道标注（S5 会当实测值用）", build(design='no_channel'), 1),
             ("反例 缺状态覆盖矩阵（PRD 附件 E 与 S6 无依据）", build(design='no_states'), 1),
             ("反例 缺 INNOV/TREND 登记", build(conclusions='no_innov'), 1),
             ("反例 TREND 无样本门槛（一个样本推行业趋势）", build(conclusions='no_floor'), 1),
             ("反例 TREND 没列反例名单（藏证据）", build(conclusions='no_counter'), 1),
             ("反例 DIFF 缺窗口期要素", build(conclusions='no_window'), 1),
             ("反例 DIFF 写不可证伪表述「更好用」", build(conclusions='banned'), 1),
             ("正例 禁用词出现在**禁令语境**里 → 不许误伤（门不能惩罚正确用法）",
              build(conclusions='banned_in_prohibition'), 0),
             ("反例 B 通道一轮没跑（5.2/5.3 只能靠猜）", build(deepres='none'), 1),
             ("反例 B 通道缺 R-B 行业轮", build(deepres='no_rb'), 1),
             # ── 2026-09-15 第二批：用户拍板三件 + 手工轮对照补强四条 ──
             ("反例 承重表一处截图证据都没挂（读者只能读文字）", build(visual='no_shot'), 1),
             ("反例 引用了不存在的证据文件（比不写更糟：让人以为有据可查）",
              build(visual='ghost'), 1),
             ("反例 结构物有图但**三份报告**一张都没有（报告才是给人读的那一份）",
              build(visual='no_report_shot'), 1),
             ("正例 无关键/创新动效但**显式声明**了 → 放行（⛔ 不许因此判红）",
              build(visual='no_clip'), 0),
             ("反例 标了关键动效却没挂录屏（静态图证明不了动效）",
              build(visual='clip_missing'), 1),
             ("反例 只有对齐表没有对照图（层级与连线表达不了）",
              build(compare_forms='no_chart'), 1),
             ("反例 只有对照图没有族×竞品对齐表（用户拍板两种都要）",
              build(compare_forms='no_align'), 1),
             ("反例 缺取证过程的元发现（把阻断只当噪声就产不出这类一级发现）",
              build(meta_finding='none'), 1),
             ("反例 元发现没写「同一把尺子」（各量各的＝一堆失败记录）",
              build(meta_finding='no_ruler'), 1),
             ("反例 元发现未标 [推断]（未向厂商求证却写成事实）",
              build(meta_finding='no_infer'), 1),
             ("反例 缺版本对账表", build(version_ledger='none'), 1),
             ("反例 登记了纠错却没写真因（下一个人会同样地再错一次）",
              build(version_ledger='no_cause'), 1),
             ("正例 没有纠错时不强求真因段（⛔ 收紧不许误伤）",
              build(version_ledger='no_fix'), 0),
             ("反例 缺 WATCH 窗口警报", build(watch='none'), 1),
             ("反例 WATCH 用日期而非事件做复查触发（写日期会过期）",
              build(watch='no_trigger'), 1),
             ("反例 CDP 未获用户授权", build(access_mode='cdp-direct', mac_permission=False), 1),
             ("反例 CDP 与产品形态不符", build(access_mode='cdp-direct', access_product='Web'), 1),
             ("正例 无法交互时降级且写明阻断", build(access_mode='retrieval-only'), 0),
             ("反例 只缺 RUN 实测回执（隔离）", build(access_mode=None), 1),
             ("反例 RUN 采集通道不在允许集合", build(access_mode='manual-browser'), 1),
             ("反例 macOS 未获授权却标 Computer Use 实测",
              build(access_mode='mac-computer-use', mac_permission=False), 1),
             ("反例 macOS 回执缺可核官方来源",
              build(access_mode='mac-computer-use', access_source=False), 1),
             ("反例 Web 回执缺实际访问的官方入口", build(access_source=False), 1),
             ("反例 Web 回执缺版本账号价格档", build(access_version=False), 1),
             ("反例 RUN 缺功能覆盖账", build(access_coverage=False), 1),
             ("反例 RUN 指向的功能遍历覆盖账小节不存在",
              build(surface_section=False), 1),
             ("反例 SURF 没有归并 AF 或登记排除/阻断",
              build(surface_unmapped=True), 1),
             ("反例 SURF 绑定了另一个 RUN",
              build(surface_wrong_run=True), 1),
             ("反例 FULL 原子事实无法反查 SURF",
              build(surface_missing_af=True), 1),
             ("反例 FULL 原子事实引用的 RUN 属于另一竞品",
              build(run_comp='COMP-02'), 1),
             ("反例 降级通道未写阻断原因",
              build(access_mode='retrieval-only', access_reason=False), 1),
             ("反例 深挖对象没有对应 RUN",
              build(deep_comp=True, run_comp='COMP-02'), 1),
             ("反例 RUN 缺执行日期", build(access_date=False), 1),
             ("反例 缺四类行动结论", build(actions=False), 1),
             ("反例 缺机会优先级与理由", build(priority=False), 1),
             ("反例 缺 PRD/Figma/HTML 双向覆盖", build(downstream=False), 1),
             ("反例 缺 CLM 主张账", build(claims=False), 1),
             ("反例 五条线没交代", build(lines=False), 1),
             ("反例 跳过市场线却没有理由与声明上限", build(market_mode='skip-thin'), 1),
             ("反例 市场线宣称完成却缺独立交付", build(market_mode='done-missing'), 1),
             ("反例 缺 insights.md", build(insights=False), 1),
             ("反例 洞察只有 1 处出处", build(thin_ins=True), 1),
             ("反例 机会只有 1 个解法", build(few_opp=True), 1),
             ("反例 未声明用户接触", build(contact=False, insights=False), 1),
             # ⭐ 2026-09-01 变异测试发现：上面那条同时关掉了 insights，于是它**红的不是 user-contact**
             #    —— 强制 user-contact 恒绿，自证照样通过。**用例存在 ≠ 用例在守它。**
             #    补隔离用例：只关 contact，实测此时唯一的红就是 user-contact。
             ("反例 只缺用户接触声明（隔离）", build(contact=False), 1),
             # 同理：build(lines=False) 会同时触发 6 条（demand-side/cant-wont/gap-list/three-routes/user-contact），
             #    所以 five-lines 也从没被单独守住。补一个「文件在、只少一条线」的隔离用例。
             ("反例 五条线缺一条（隔离，文件仍在）", build_lines_missing_one(), 1),
             ("反例 缺三份定向报告", build(reports=False), 1),
             ("反例 无需求侧竞品", build(demand=False), 1),
             ("反例 取舍未标 Can't/Won't", build(cantwont=False), 1),
             ("反例 缺「竞品有而我们没有」", build(gaplist=False), 1),
             ("反例 三路未交代", build(routes=False), 1),
             ("反例 出现「各有优劣」不表态", build(hedge=True), 1),
             ("反例 决策域 standing 有空格", build(domain_gap=True), 1),
             # ⭐ 曾经 len>=10 就打印「12 域全部 standing」—— 10 行冒充 12 域全过
             ("反例 决策域只有 10 行（曾被冒充成 12 域全过）", build(domain_count=10), 1),
             ("反例 缺决策域清单", build(domains=False), 1),
             # 🚨 2026-09-09：上面两条反例用的都是**三列**夹具（`| # | 域 | standing |`），
             #    而真实产物是**两列**（`| 域 | standing |`）——原判据按固定索引取列，
             #    对三列成立、对两列**整条失效**：12 行里两行空 standing 照样报「12 域全部 standing」。
             #    ⭐ 反例年年绿着过，不是因为没反例，是因为反例的形状恰好是判据能处理的那种。
             ("正例 两列表格不许误伤（扩量程后新增的形状）", build(two_col=True), 0),
             ("反例 两列表格 standing 有空格（原固定索引判据在这个形状上失效）",
              build(two_col=True, domain_gap=True), 1),
             # 🚨 2026-09-09 独立复核揪出：改「取最后一列」后，四列表（多一个空的备注列）
             #    里 **完全填对的产物被判红**，且报错点名 standing 的值而不是域名。
             #    ⇒ 现按**表头名**定位 standing/域名列；位置型定位钉哪一头都只对一种形状成立。
             ("正例 四列表·备注列空但 standing 全填 → 不许误伤", build(four_col=True), 0),
             # 🚨 2026-09-09 **自攻**：表头闭集扩得再大也永远差一个 ——
             #   「填写状况/进展/调研结果/completeness」四种自然写法一步即漏。
             #   ⭐ 词表不是不变量，**列里装的是什么**才是。⇒ 退回按三态内容识别。
             ("正例 未知表头（按列内容识别三态）→ 不许误伤", build(odd_header=True), 0),
             ("反例 未知表头且有空 standing → 仍红（放宽不许变哑）",
              build(odd_header=True, domain_gap=True), 1),
             ("反例 四列表·standing 有空格 → 红且点名域名（不是点名值）",
              build(four_col=True, domain_gap=True), 1),
             ("反例 缺洞察账本", build(ledger=False), 1),
             ("反例 账本 INS 缺边界/目标", build(ledger_thin=True), 1),
             ("正例 scope 声明下限 4+理由，5 家合法", build(n=5, scope_floor=4), 0),
             # 🚨 2026-09-09 第五轮独立复核：**UNABLE 在退出码上被折叠成通过**。
             #   本仓 P6 明写「UNABLE≠通过」，而 P6 只落在 add() 的显示层，
             #   `sys.exit()` 一字未动 —— 声称与实际差在最后一行代码上。
             ("反例 standing 列认不出 → 退 2（没验成，⛔ 不是通过也不是不合格）",
              build_unrecognizable_standing(), 2),
             # 🚨 2026-09-09 第五轮独立复核：以下四种**旧版全部放行**（逐条实测）。
             #   ⭐ 占位符那条最刺眼：**同一份代码里契约不一致** —— 下面
             #     insight-ledger 那条判据检查了 `startswith('<')`，这条没有。
             ("反例 standing 全填 TBD → 1（占位符不算填了）",
              build_domains(_H2 + "".join("| 域%d | TBD |\n" % i for i in range(1, 13))), 1),
             ("反例 standing 全填「-」→ 1",
              build_domains(_H2 + "".join("| 域%d | - |\n" % i for i in range(1, 13))), 1),
             # ⛔「查不了这一行」被当成了「这一行没问题」：单格行进了 12 的分母，
             #   却因 len(c)>=2 被排除在空值检查外。
             # ⚠️ 这条我**第一版把期望写成 1，自证当场纠正**：整表只有一列时
             #   根本没有 standing 列可定位 ⇒ 正确结论是 **UNABLE(2)**（没验成），
             #   而不是「不合格」。⭐ 期望值写错会让一个正确行为看起来像缺陷。
             ("反例 12 行单格（连 standing 列都没有）→ 2（没验成，不是不合格）",
              build_domains('# 下游决策域清单\n\n| 决策域 |\n|---|\n'
                            + "".join("| 域%d |\n" % i for i in range(1, 13))), 2),
             # ⭐ 这条才是真正打「单格行」那处修复的：表头两列（standing 定位得到），
             #   但数据行只有一格 ⇒ 旧判据的 `len(c) >= 2` 把它排除在空值检查外，
             #   而它照样进 12 的分母。⛔「查不了这一行」被当成了「这一行没问题」。
             ("反例 表头两列但数据行缺 standing 格 → 1（不许算进 12 域）",
              build_domains(_H2 + "".join("| 域%d |\n" % i for i in range(1, 13))), 1),
             ("反例 12 行复制同一个域名 → 1（域名列凑数）",
              build_domains(_H2 + "| 同一个域 | 有输入 |\n" * 12), 1),
             # 🚨 B8：豁免的量程是**整行** ⇒ 禁令词写在命中之后也算数。
             #   ⭐ 与 product-structure 的「否定豁免只看前 6 字符」同病：
             #     豁免按**文本邻域**给而不是按**语义位置**给，补一句话就能关掉判据。
             ("反例 禁令词写在编造语之后 → 1（「不要照抄」不能把编造洗白）",
              build_ban_after(), 1),
             # ── 2026-09-15 两条新判据的反例 ⛔ 没有反例的判据等于没判据 ──
             ("反例 conflicts.md 缺失（两条取证通道没有一起用的证据）",
              build(conflicts=False), 1),
             ("反例 有冲突却没写采信（⛔ 默认以实测为准，必须显式写出来）",
              build(conflicts_mode='no_adopt'), 1),
             ("反例 缺双路 deep-research 合并记录（只跑了一路）",
              build(conflicts_mode='no_dual'), 1),
             ("正例 本轮无冲突但显式写了理由（⭐ 不许因此判红）",
              build(conflicts_mode='none_declared'), 0),
             ("反例 深挖档缺四件套（喂不进 PRD 4.4/6.1/6.2）",
              build(isomorphic=False), 1)]
    ok = True
    # ⭐ 构造空间穷举（轴 = 表头名 × 列数 × 位置 × 值形态 × 干扰列）——
    #   不列举用例，列举轴，让笛卡尔积覆盖我想不到的组合。说明见 _sweep_lib。
    import tempfile as _tf2, shutil as _sh2, subprocess as _sp2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_standing_column, report as _rep
    _base = _tf2.mkdtemp(prefix='rg-sweep-')

    def _run(_d):
        _o = _sp2.run([sys.executable, os.path.abspath(__file__), _d],
                      capture_output=True, text=True).stdout
        _l = [x for x in _o.split('\n') if 'decision-domains' in x]
        return _l[0][0] if _l else '?'

    _n2, _bad2 = sweep_standing_column(_run, _base)
    _sh2.rmtree(_base, ignore_errors=True)
    _sweep_ok = _rep('standing 列识别', _n2, _bad2)

    print("M8 自证 —— 正例绿 / 每类反例必红 / 无效输入报 2\n")
    for n, d, want in cases:
        got = run(d); g = got == want; ok &= g
        print("  %s %-24s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, got))
    got = run(os.path.join(root, 'nope')); g = got == 2; ok &= g
    print("  %s %-24s 期望 2 实得 %d" % ("✅" if g else "❌", "目录不存在", got))
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败"))
    ok = ok and _sweep_ok      # 穷举结果并入结论（⛔ 不许只打印不影响退出码）
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
                "本门禁用位置参数：research-gate.py <research 目录>")
            a = [x for x in sys.argv[1:] if not x.startswith('--')]
            sys.exit(check(a[0]) if a else (print(__doc__) or 2))
    _main_guarded(_entry)
