#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRD 完备度门禁 —— 验「填没填」，不验「填得对不对」。

用法:
  python3 prd_completeness_check.py <PRD.md> [--stage S4|S5|S7|v0.9|v1.0] [--json] [--min-rows N] [--min-bullets N]
     ⚠️ `--stage` 真实存在却一直没写进本用法说明（2026-09-03 补）——
        S4 允许「设计稿」列全空，S5/S7 不允许；不传 stage 时按最严判。
  python3 prd_completeness_check.py --self-test          # M8 自证：正例绿 / 每类反例红 / 无效输入不返绿

退出码:
  0 = 全部达标
  2 = 有缺口（详情见报告）
  3 = 输入无效（文件不存在 / 解析不出功能清单 / 结构残缺）

四类结论（不是两类）：
  PASS / FAIL / N/A（前置条件不成立，本条对该对象无意义）/ UNABLE（跑不了）
  判据：一条规则如果对「正确实现」和「错误实现」给出同样的结果，它对该对象就是 N/A，不是 PASS。
  ⚠️ 通过率的分母只算 PASS+FAIL。

⚠️ 这道门禁只回答「每个 F-xx 在各附件里有没有对应内容、第四章够不够细」。
   它**不能**判断内容是否正确、是否可实现 —— 那是评审的事。
   报覆盖率时必须连这句话一起报，只贴百分比等同谎报。

⚠️ 判据方向（2026-08-30 改）：语义判断交给人，门禁只查「填没填」。
   例：AI 功能不再靠关键词猜（实测「智能推荐/一键美化/人脸相册」三个全部漏报），
   改为功能清单表增设 `AI?` 列由人填，门禁只核该列非空 + 为「是」的行在附件 B.2 出现。
"""
import io, os, re, sys, json, tempfile, subprocess
import _prd_parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import (section_at, section_or_table,   # noqa: E402  段落定位唯一正本
                      _iter_headings)

EXIT_OK, EXIT_GAP, EXIT_BAD = 0, 2, 3


def load(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception as e:
        print("ERR 读不到文件: %s (%s)" % (p, e)); sys.exit(EXIT_BAD)


# ---------------------------------------------------------------- 功能清单表
def parse_feature_table(s):
    """按**列**解析功能清单表，返回 (columns, rows[dict])。

    为什么必须按列解析：旧版用 `优先级.*?ASM-\\d+` 全文正则，而 markdown 表里
    「优先级」只在表头行、`[ASM-003]` 在数据行，`.` 不跨行 —— 该规则实测永不触发。
    """
    lines = s.split('\n')
    for i, ln in enumerate(lines):
        if re.match(r'^\s*\|\s*ID\s*\|', ln) and '功能名称' in ln:
            cols = [c.strip() for c in ln.strip().strip('|').split('|')]
            rows = []
            for ln2 in lines[i + 2:]:                      # +2 跳过分隔行
                if not ln2.strip().startswith('|'):
                    break
                if re.match(r'^\s*\|[\s\-:|]+\|\s*$', ln2):
                    continue
                cells = [c.strip() for c in ln2.strip().strip('|').split('|')]
                if not cells or not re.match(r'^F-\d+', cells[0]):
                    continue
                rows.append(dict(zip(cols, cells + [''] * (len(cols) - len(cells)))))
            return cols, rows
    return [], []


def col_of(cols, *names):
    """找列名（容忍「AI?」「是否 AI」「载体」「成本/规模」这类写法差异）"""
    for c in cols:
        flat = c.replace(' ', '').replace('*', '')
        for n in names:
            if n in flat:
                return c
    return None


# ---------------------------------------------------------------- 第四章
def ch4_sections(s):
    """第四章逐功能：表格数据行数 + 逻辑列要点条数 + 原文（供三选一检查）"""
    out = {}
    parts = re.split(r'(?m)^### M: .*?/ (F-\d+): (.*)$', s)
    for i in range(1, len(parts), 3):
        fid, body = parts[i], parts[i + 2]
        # ⚠️ 2026-09-10 复核这一处：它**不是**「全文定位一节」那一族 ——
        #   `body` 已经是 `re.split(r'^### M: …/ (F-\d+):')` 切出来的**功能块**，
        #   这里只是把块尾多余的部分掐掉。⭐ 但 `'\n## '` 这种写法仍认不出
        #   缩进标题与 setext ⇒ 缩进写法下会**多吃**下一块的内容。
        #   ⇒ 用正本的标题识别来找块内第一个标题行，边界语义不变。
        _bl = body.split('\n')
        _cut = next((ln for ln, _lv, _t in _iter_headings(body) if ln > 0), None)
        body = '\n'.join(_bl[:_cut]) if _cut is not None else body
        rows = [l for l in body.split('\n')
                if l.startswith('|') and not re.match(r'^\|[\s\-:|]+\|$', l) and '| 页面 |' not in l]
        bullets = sum(l.count('<br>-') + (1 if re.search(r'\|\s*-\s', l) else 0) for l in rows)
        out[fid] = (len(rows), bullets, body)
    return out


def appendix(s, start, end=None):
    """取 [start, end) 之间的一段 —— **两端都锚定行首**。

    🚨 2026-09-09 第五轮独立复核：原实现是 `s[s.index(start):s.index(end)]`，
      按**全文首次出现**定位。传进来的 `start/end`（`# 附件 A`、`## B.2`）虽然长得像标题，
      但 `index` 不区分「这是一行标题」还是「正文里提了一句」——
      一句「详见 # 附件 C 的说明」就能把段落起点或终点挪到别处：
      起点前移 ⇒ 吃进不属于本附件的内容；终点前移 ⇒ 本附件后半段**静默逃检**。
    ⭐ 这是 `no-positional-window` 那一族的**间接形态**（字面量先进变量再 index），
      元规则查不到它 —— 我上一批因此在注释里把它登记成「查不到的量程边界」。
      ⛔ 但「查不到」不等于「不用修」：能修的就修，边界声明只留给真修不了的。
    ⚠️ 这道门守的是 **G7.5 冻结**，全流程风险最高的一处。
    """
    # ⚠️⚠️ 2026-09-10 **构造空间穷举**（标题写法 × 缩进 × 交叉引用干扰 × 内容形态，24 例）
    #   扫出 **9 例失配**，三种形态全是**合规产物被报缺陷**：
    #     `#  附件 C`（`#` 后两个空格）· `## 附件 C`（二级标题）· `   # 附件 C`（合法缩进）
    #   ⭐ 上一轮我把 `s.index()` 改成 `^` 锚定行首，只修了「位置」那一半 ——
    #     **字面量本身仍是精确匹配**，于是同一个附件换个合法写法就找不到了。
    #   ⇒ 交给 `_section`（它已经处理过缩进 0–3、`#` 后空白、级别、围栏、setext）。
    #     ⛔ 别在这里再手写一遍标题解析 —— 那正是「多套手写解析器」这个根因本身。
    import re as _re
    _kw = _re.sub(r'^[#\s]+', '', start).strip()
    _lines = s.split('\n')
    _heads = list(_iter_headings(s))
    _hit = next(((ln, lv) for ln, lv, tx in _heads if _kw in tx), None)
    if _hit is None:
        return None
    _ln, _lv = _hit
    # ⚠️ 穷举第二轮：只按「同级或更高级标题」切，会在**附件标题本身是 `##`**、
    #   而其子节 `## C.1` 同级时**提前截断** ⇒ 合规附件被报「空壳」。
    #   ⭐ 调用方本来就传了明确的终点标记（`# 附件 D`），用它做边界比猜层级准。
    #   ⇒ 终点优先取「标题里含 end 关键词」的那一行；没有 end 才退回按层级切。
    _end_ln = None
    if end:
        _ekw = _re.sub(r'^[#\s]+', '', end).strip()
        _end_ln = next((ln for ln, _l, tx in _heads if ln > _ln and _ekw in tx), None)
    if _end_ln is None:
        _end_ln = next((ln for ln, lv, _t in _heads if ln > _ln and lv <= _lv), len(_lines))
    return '\n'.join(_lines[_ln:_end_ln])


def appendix_feats(s, start, end):
    seg = appendix(s, start, end)
    return None if seg is None else set(re.findall(r'F-\d+', seg))


THREE_WAY = ("两端同一套交互", "降级版", "只在一端存在")


# ---------------------------------------------------------------- 主检查
def check(path, min_rows=4, min_bullets=12, stage=None):
    s = load(path)
    cols, rows = parse_feature_table(s)
    if not rows:
        print("ERR 解析不出功能清单表（3.2 的 | ID | 功能名称 | … 表）"); sys.exit(EXIT_BAD)

    feats = [r['ID'] for r in rows]
    r = {"total": len(feats), "gaps": [], "stats": {}, "na": []}

    # 0 · 设计稿列（**阶段感知**）
    #     ⚠️ 这一列此前完全没人查：模板一边写「每一行必须有链接不许留空」，
    #     一边写「S7 才回灌」——两条在 S4 那一刻同时成立就是矛盾。
    #     于是 `--only S4` 会稳定产出一份设计稿列全空的 PRD，S4–S6 之间无人拦截。
    #     ⭐ 判据必须带阶段：不带阶段就只能二选一，而两个选择都是错的。
    #     ⚠️ 首版用 `](http` 判「有链接」——**正例里的 `[稿](x#node-id=1)` 会被判成空**。
    #        判据要判的是「这一格填了没有」，不是「链接是不是 http」。
    ch4 = ch4_sections(s)          # ⚠️ 本块在颗粒度检查之前，ch4 要先算出来
    if stage:
        # 2026-09-08（终局规格 2-2）：两次冻结的语义别名 —— v0.9=产品基线（等价 S4 档），
        # v1.0=三方回灌后（设计稿列必须全满 + OPEN 表无 open + 附件 M 回灌协议已填）。
        _raw = str(stage).upper()
        v10 = _raw in ('V1.0', '1.0')
        if _raw in ('V0.9', '0.9'):
            _raw = 'S4'
        if v10:
            _raw = 'S7'
        st = _raw.lstrip('SV').lstrip('S')
        PLACEHOLDER = re.compile(r'^\s*(|-|—|待补|TBD|<[^>]*>)\s*$')
        links, blanks = 0, set()
        for f in feats:
            seg = ch4.get(f, (0, 0, ''))[2] if f in ch4 else ''
            for ln in seg.splitlines():
                t = ln.strip()
                if not t.startswith('|'): continue
                cells = [c.strip() for c in t.strip('|').split('|')]
                if len(cells) < 3 or set(''.join(cells)) <= set('-: '): continue
                if cells[0] in ('页面', '页面/场景'): continue      # 表头
                cell = cells[1]
                if re.search(r'\]\(\s*[^)\s]+\)', cell): links += 1
                elif PLACEHOLDER.match(cell): blanks.add(f)
                else: blanks.add(f)
        if st in ('7', '8', '9') and blanks:
            # ⚠️ gaps 存的是 (类别名, 条目列表) 二元组，不是字符串。
            #    首版 append 了字符串，report() 解包时直接崩——**而自证当时报的是「实得 1」，
            #    那是 Python 的异常退出码，不是判定结果。** ⭐ 退出码 1 在本门禁的语义里
            #    根本不存在（只有 0/2/3），出现它就说明门自己炸了，不是它抓到了东西。
            r["gaps"].append(("设计稿列未回灌（S%s 必须全部有链接）" % st, sorted(blanks)))
        if v10:
            # v1.0 附加判据①：OPEN 表无 open（示例行与「无 OPEN 项」不算）
            # 🚨 2026-09-09 第五轮：这道门守的是 **G7.5 冻结**，全流程风险最高的一处，
            #   而它用 `s.find('OPEN 项登记表')` 按全文首次出现定位 —— 正文里一句
            #   「OPEN 项登记表见附件」就让它从那句往后切，未关闭的 OPEN 项静默逃检。
            oseg = section_or_table(s, 'OPEN 项登记表')
            if oseg is None:
                r["gaps"].append(("v1.0 缺「OPEN 项登记表」（v0.9 模板必带）", []))
            else:
                oopen = [ln.strip().strip('|').split('|')[0].strip()
                         for ln in oseg.splitlines()
                         if ln.strip().startswith('|') and re.search(r'\|\s*open\s*\|?\s*$', ln)
                         and '<示例' not in ln]
                if oopen:
                    r["gaps"].append(("v1.0 有未关闭的 OPEN 项（冻结前只许 closed/deferred 带主带期）", oopen))
            # v1.0 附加判据②：附件 M 回灌协议已填（十项清单至少有已填落点，且不再是纯模板）
            mseg = section_at(s, '附件 M')
            if mseg is None:
                r["gaps"].append(("v1.0 缺「附件 M · v1.0 三方回灌协议」", []))
            else:
                filled_rows = 0
                for ln in mseg.splitlines():
                    t = ln.strip()
                    if not t.startswith('|'):
                        continue
                    cells = [c.strip() for c in t.strip('|').split('|')]
                    if len(cells) >= 3 and cells[0].isdigit() and cells[2] and not cells[2].startswith('<'):
                        filled_rows += 1
                if filled_rows == 0:
                    r["gaps"].append(("v1.0 附件 M 回灌清单一行落点都没填（回灌协议还是空模板）", []))
        elif st in ('4', '5', '6') and links == 0:
            r["na"].append("设计稿列全空 —— S%s 合法，但**本 PRD 不可直接交研发**，"
                           "报告里必须写明「设计稿列未回灌」" % st)

    # 1 · 第四章颗粒度
    ch4 = ch4_sections(s)
    thin = [f for f in feats if ch4.get(f, (0, 0, ''))[0] < min_rows or ch4.get(f, (0, 0, ''))[1] < min_bullets]
    missing4 = [f for f in feats if f not in ch4]
    thin = [f for f in thin if f not in missing4]
    r["stats"]["ch4_ok"] = len(feats) - len(set(thin) | set(missing4))
    if missing4: r["gaps"].append(("第四章缺整节", missing4))
    if thin:     r["gaps"].append(("第四章颗粒度不足(<%d行或<%d要点)" % (min_rows, min_bullets), thin))

    # 2-5 · 附件 A/D/E/F 逐功能覆盖
    APX = [("A 验收标准", '# 附件 A', '# 附件 B'), ("D 字段规格", '# 附件 D', '# 附件 E'),
           ("E 状态机边界", '# 附件 E', '# 附件 F'), ("F 文案规格", '# 附件 F', '# 附件 G')]
    for label, a, b in APX:
        if re.search(r'附件\s*%s[^\n]{0,40}本次不涉及' % label[0], s):
            r["na"].append("附件 %s（索引标注「本次不涉及」）" % label); continue
        # ⚠️ 附件 A 用**归属判据**而不是「文中提到 F-xx」：后者太松 ——
        #    「本条与 F-20 无关」这样一句也会被算成 F-20 有验收标准。
        #    与 reconcile-gate G1 共用 `_prd_parse`，两道门禁不再各写各的（2026-08-31）。
        if label.startswith('A'):
            seg = _prd_parse.appendix(s, a, b)
            cov = None if seg is None else _prd_parse.features_with_ac(s, seg)
        else:
            cov = appendix_feats(s, a, b)
        if cov is None:
            r["gaps"].append(("附件 %s 整节缺失" % label, ["<整节>"])); continue
        miss = [f for f in feats if f not in cov]
        r["stats"]["附件" + label[0]] = len(feats) - len(miss)
        if miss: r["gaps"].append(("附件 %s 未覆盖" % label, miss))

    # 6 · AI 功能 —— 靠人填的 AI? 列，不靠关键词猜
    ai_col = col_of(cols, 'AI', '是否AI')
    if ai_col is None:
        r["gaps"].append(("功能清单表缺 `AI?` 列（模板已更新；关键词识别实测漏报 100%%，不再回退）", ["<表头>"]))
        ai = []
    else:
        blank = [x['ID'] for x in rows if not x.get(ai_col, '').strip()]
        if blank: r["gaps"].append(("`AI?` 列留空（是/否，二选一）", blank))
        ai = [x['ID'] for x in rows if x.get(ai_col, '').strip().startswith(('是', 'Y', 'y'))]
    r["stats"]["ai_features"] = len(ai)
    if ai:
        # ⚠️ 2026-09-01 收窄量程：原来扫**整个附件 B**，于是 B.1 的假设表里随口提一句
        #    「F-02」也算 B.2 登记了 —— 与附件 A 上修过的「提一句就算数」同型。
        #    现在只认 B.2 小节；B.2 不存在时回退到整段并在证据里说明（不静默）。
        b2_seg = appendix(s, '## B.2', '# 附件 C')
        b2 = (set(re.findall(r'F-\d+', b2_seg)) if b2_seg is not None
              else (appendix_feats(s, '# 附件 B', '# 附件 C') or set()))
        ai_miss = [f for f in ai if f not in b2]
        if ai_miss: r["gaps"].append(("AI 功能缺附件 B.2 算法能力边界", ai_miss))
        if not re.search(r'NFR-AI', s):
            r["gaps"].append(("AI 功能缺 NFR-AI 效果验收", ["<全部>"]))

    # 7 · 全局 NFR 最小集（含无障碍 —— 与安全同型的第二个结构漏洞，2026-08-30 补）
    need = {"性能": r"P9\d|首屏|ms|帧率|fps", "并发": r"并发|QPS|排队",
            "存储": r"存储上限|磁盘|容量", "兼容": r"兼容|最低版本|macOS \d|iOS \d|Chrome \d",
            "无障碍": r"无障碍|NFR-A11Y|WCAG|对比度|键盘可达|读屏",
            # ⚠️ 2026-08-31 联合评审补：S2 的歧义扫描把「可观测性」列为非功能质量的一项，
            #    而 PRD 的 NFR 最小集里没有它 —— **上游扫了，下游没有落点**。
            "可观测性": r"可观测|NFR-OBS|traceId|链路追踪|结构化日志|告警阈值"}
    nfr_seg = appendix(s, '# 附件 A', '# 附件 B') or s
    nfr_miss = [k for k, p in need.items() if not re.search(p, nfr_seg)]
    if nfr_miss: r["gaps"].append(("全局 NFR 缺类别", nfr_miss))

    # 8 · 优先级仍挂 ASM（按列取值，不再全文正则）
    p_col = col_of(cols, '优先级')
    if p_col is None:
        r["gaps"].append(("功能清单表缺「优先级」列", ["<表头>"]))
    else:
        asm = [x['ID'] for x in rows if re.search(r'ASM-\d+|待定|TBD', x.get(p_col, ''))]
        blank = [x['ID'] for x in rows if not x.get(p_col, '').strip()]
        if asm:   r["gaps"].append(("优先级仍挂 ASM/TBD 未拍板（不得进评审）", asm))
        if blank: r["gaps"].append(("优先级列留空", blank))

    # 9 · 附件 C 安全与合规 —— 唯一「不许省略」的附件，此前无门禁
    c_seg = appendix(s, '# 附件 C', '# 附件 D')
    if c_seg is None:
        r["gaps"].append(("附件 C 安全与合规整节缺失（唯一不许省略的附件）", ["<整节>"]))
    else:
        body = re.sub(r'^#.*$', '', c_seg, flags=re.M).strip()
        if len(body) < 80:
            r["gaps"].append(("附件 C 安全与合规为空壳（不适用也要写「不适用 + 理由」）", ["<整节>"]))
        elif not re.search(r'C\.2|权限矩阵', c_seg):
            r["gaps"].append(("附件 C 缺 C.2 角色与权限矩阵（每个 ❌ 是越权测试的唯一依据）", ["<C.2>"]))

    # 9b · 附件 P（非目标 / 路径规划）与附件 Q（依赖 / 风险）—— 2026-09-15 新增
    #
    # 🚨 为什么必须加：这三样此前在正文三章，2026-09-15 按用户指令外移到附件。
    #   外移那一刻我在模板里写了一句「prd_completeness_check 照查」—— **那是假的**，
    #   这道门当时对「非目标/依赖/风险」一个字都没查过。
    #   ⭐ 本仓母题「声称 vs 实际」：在 SOP 里谎称某道门在守，比不写更糟 ——
    #     读者会因此停止自查，而根本没有人在查。
    #   ⇒ 要么把那句话删掉，要么把门补上。这里选择补门：
    #     正文里的东西至少还会被评审的眼睛扫到，挪进附件后若再无机器检查，**必然静默消失**。
    for _letter, _next, _label, _subs in (
            ('P', 'Q', 'P 范围边界与路径规划', (('P.1', '非目标'), ('P.2', '路径规划'))),
            ('Q', 'R', 'Q 依赖与风险',       (('Q.1', '依赖'),   ('Q.2', '风险'))),
    ):
        # ⚠️ **诚实边界**（写反例时实测出来的，⛔ 不要照直觉改）：
        #   `appendix()` 会把锚点的 `#` 与空白**剥掉后做子串匹配**，
        #   所以 `# 附件 PP · 别的东西` 会被当成 `# 附件 P` ——
        #   给锚点加尾随空格**没有用**（我先写了这个「修法」并在注释里声称它有效，
        #   是反例把这句话证伪的）。⭐ 这不是本判据独有：`附件 C` 同样会匹配 `附件 CC`。
        #   ⇒ 现状可接受：附件字母由模板固定为 A–R 单字母，现实里不会出现 `附件 PP`。
        #     ⛔ 若哪天附件编号改成多字母，这里和附件 C 那条**一起**要改 `appendix()` 的匹配。
        _seg = appendix(s, '# 附件 %s' % _letter, '# 附件 %s' % _next)
        if _seg is None:
            r["gaps"].append(("附件 %s 整节缺失（外移不等于变可选，仍必填）" % _label, ["<整节>"]))
            continue
        _body = re.sub(r'^#.*$', '', _seg, flags=re.M).strip()
        if len(_body) < 40:
            r["gaps"].append(("附件 %s 为空壳（只有标题没有内容）" % _label, ["<整节>"]))
            continue
        # 🚨 2026-09-15 独立评审揪出：这里原本判的是 `_seg`，而 `appendix()` **返回含标题行**，
        #   「附件 P · 范围边界与**路径规划**」「附件 Q · **依赖**与**风险**」的标题里
        #   恰好含判据关键词 ⇒ P.2 / Q.1 / Q.2 **三条判据恒为真**，只有 P.1 是活的。
        #   ⭐ 而模板里当时正写着「门禁实际守到哪一层（说准，别夸大）」声称四条都查 ——
        #     我警告的那种错，当场犯在自己新加的判据上。
        #   ⇒ 判 `_body`（已剥掉所有标题行），不判 `_seg`。
        # ⚠️ 只能剥**附件标题那一行**，⛔ 不能用 _body（它把所有标题行都剥了，
        #   而小节常常就写成标题 `## P.1 非目标` ⇒ 会把合规产物误判为缺小节）。
        #   ⭐ 两个方向都踩过：判 _seg 是标题混进来导致**恒为真**，
        #     判 _body 是小节标题被剥掉导致**恒为假**。正确的是「去掉首行的 _seg」。
        _seg_body = '\n'.join(_seg.split('\n')[1:])
        _miss = [n for n, kw in _subs if not re.search(re.escape(n) + r'|' + kw, _seg_body)]
        if _miss:
            r["gaps"].append(("附件 %s 缺小节" % _label, _miss))

    # 10 · 载体列 + 双端三选一（视角 9 自认复发率最高的返工，此前无门禁）
    car = col_of(cols, '载体')
    if car is None:
        r["gaps"].append(("功能清单表缺「载体」列", ["<表头>"]))
    else:
        blank = [x['ID'] for x in rows if not x.get(car, '').strip()]
        if blank: r["gaps"].append(("载体列留空（两端/仅 web/仅移动端）", blank))
        both = [x['ID'] for x in rows if '两端' in x.get(car, '')]
        if not both:
            r["na"].append("双端三选一（本次无「两端」功能）")
        else:
            # ⚠️ 2026-09-04：判据必须**先剥 markdown 强调**再比。
            #    作者自然会写 `两端**同一套交互**`（把关键词加粗），
            #    而字面量 `两端同一套交互` 在那串里**不存在** → 一份写对了的 PRD 被判红。
            #    ⭐ 与 09-03 修的 `- **AC-1**` 是同一族：**判据读字面量，作者写带装饰的字面量。**
            #    ⛔ 凡是「必须出现某个短语」的判据，都要先剥 `*` `_` 反引号。
            strip_md = lambda x: re.sub(r'[*_`]', '', x)
            no3 = [f for f in both
                   if not any(k in strip_md(ch4.get(f, (0, 0, ''))[2]) for k in THREE_WAY)]
            if no3:
                r["gaps"].append(("双端功能未在第四章回答三选一（两端同一套交互/降级版/只在一端存在）", no3))

    # 11 · 成本/规模列（S3/S4 拍板的依据，此前整条流水线没有承载位）
    cost = col_of(cols, '成本', '规模')
    if cost is None:
        r["gaps"].append(("功能清单表缺「成本/规模」列（优先级没有成本就是拍脑袋）", ["<表头>"]))
    else:
        blank = [x['ID'] for x in rows if not x.get(cost, '').strip()]
        if blank: r["gaps"].append(("成本/规模列留空（S/M/L）", blank))

    # 12 · 小节编号不许重号 · 「见 x.y」必须指向存在的小节
    #    🔴 2026-09-04 实录：一份 PRD 里**两个小节都叫 7.1.1**（「口径」是 ####，
    #    「护栏指标」是 ###）—— 层级还不同，所以通读发现不了。
    #    全文 6 处引用 7.1.1，其中「护栏见 7.1.1」把读者带到了口径表。
    #    ⭐ **引用完好、指向错误**，与 Figma node-id 失效是同一种病：
    #      M9 已经为外链立了双锚，而**正文自己的编号从来没人守**。
    heads = {}
    for m in re.finditer(r'^(#{2,6})\s*(\d+(?:\.\d+)+)\s', s, re.M):
        heads.setdefault(m.group(2), []).append(len(m.group(1)))
    dup = ["%s（出现 %d 次，层级 %s）" % (n, len(v), '/'.join('#' * x for x in v))
           for n, v in sorted(heads.items()) if len(v) > 1]
    if dup:
        r["gaps"].append(("小节编号重号 —— 引用它的地方指向哪一个？", dup))
    dead = sorted({m.group(1) for m in re.finditer(r'见\s*(\d+\.\d+(?:\.\d+)?)', s)
                   if m.group(1) not in heads})
    if dead:
        r["gaps"].append(("正文写「见 x.y」而没有这个编号的小节（引用完好、指向不存在）", dead))

    return r


def report(r, as_json=False):
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=1)); return EXIT_GAP if r["gaps"] else EXIT_OK
    print("功能总数: %d" % r["total"])
    print("覆盖统计: " + " · ".join("%s=%s/%s" % (k, v, r["total"])
                                for k, v in r["stats"].items() if k != "ai_features"))
    print("AI 功能数: %s" % r["stats"].get("ai_features", 0))
    if r.get("na"):
        print("N/A（不适用，不进分母）: " + " · ".join(r["na"]))
    if not r["gaps"]:
        print("\n✅ 完备度门禁通过")
        print("⚠️ 本门禁只验「填没填」，不验「填得对不对」——内容是否正确、可实现，仍需人评审。")
        return EXIT_OK
    print("\n❌ 发现 %d 类缺口:" % len(r["gaps"]))
    for name, items in r["gaps"]:
        show = " ".join(items[:12]) + (" …共%d个" % len(items) if len(items) > 12 else "")
        print("  · %-46s %s" % (name, show))
    print("\n⚠️ 覆盖率只说明「填没填」，不代表内容正确。报覆盖率必须连本行一起报。")
    return EXIT_GAP


# ---------------------------------------------------------------- M8 自证
GOOD = """## 三、概要设计
| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 | 上线时间 |
|---|---|---|---|---|---|---|---|
| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | M | 9月 |

### 7.1 数据分析设计
埋点见 7.1.1。
#### 7.1.1 口径
分子分母写清。

## 四、详细设计
### M: 素材 / F-01: 导入
| 页面 | 设计稿 | 逻辑 |
|---|---|---|
| 导入页 | [稿](x#node-id=1) | - 支持拖拽；<br>- 上限 500 张；<br>- 失败重试 3 次；<br>- 空态引导 |
| 进行中 | [稿](x#node-id=2) | - 进度条；<br>- 可后台；<br>- 可取消；<br>- 部分失败可展开 |
| 完成 | [稿](x#node-id=3) | - Toast；<br>- 跳转库；<br>- 计数；<br>- 撤销 5s |
| 失败 | [稿](x#node-id=4) | - 原因分类；<br>- 只重试失败项；<br>- 日志入口；<br>- 反馈入口 |
两端同一套交互。

# 附件 A · 验收标准
FR-011 所属 F-01。NFR-001 P95 ≤500ms 首屏 200ms 60fps。并发 100 QPS 排队。
存储上限 20GB 磁盘。兼容 macOS 13 / Chrome 120 最低版本。
NFR-A11Y-001 无障碍：全部交互键盘可达，对比度 ≥4.5:1，读屏可读。\nNFR-OBS-001 可观测性：关键路径结构化日志含 traceId，告警阈值已定。

# 附件 B · 假设
B.2 略。

# 附件 C · 安全与合规
C.1 数据清单：照片路径、设备号。C.2 角色与权限矩阵：普通成员不可导出他人数据（❌）。
C.3 合规约束：不上传云端。C.4 个人信息自评：不涉及敏感个人信息。

# 附件 D · 字段规格
F-01 字段：路径 string 必填。

# 附件 E · 状态机
F-01 空/加载/成功/失败/无权限/极值。

# 附件 F · 文案规格
F-01 Toast ≤18 字。

# 附件 G · 接口契约
略。

# 附件 P · 范围边界与路径规划
P.1 非目标：本次不做批量导出，用户只能单张操作。
P.2 路径规划：当前版本先做浏览；未来可能支持批量与自定义封面。

# 附件 Q · 依赖与风险
Q.1 依赖：D-01 平台组先上线 Auth v2，阻塞 F-01，未确认，后果是整功能上不了线。
Q.2 风险：R-01 转码成本可能超预算，影响 ROI，概率中，预案是先限分辨率。

# 附件 R · 竞品对照
略。
"""

CASES = [
    # 🔴 2026-09-04 补：规则 12（小节重号 / 死引用）此前**夹具里连一个编号小节都没有**，
    #    于是它在正例上也是空转 —— 与本文件下方那条注释记的是同一种病：
    #    「新判据一次都没被跑过而自证照样全绿」。
    ("反例 小节编号重号（两个 7.1.1）",
     # ⚠️ 本门禁的退出码是 0/2/3（2=有缺口、3=跑不了），**不是**通用的 0/1/2 ——
     #    我第一版按通用约定写了 1，两个反例双双「实得 2 期望 1」，
     #    ⭐ 那看起来像规则没生效，实际规则抓到了、只是我读错了这道门的语义。
     GOOD.replace("#### 7.1.1 口径", "### 7.1.1 口径\n补一节\n#### 7.1.1 护栏指标"), EXIT_GAP),
    ("反例 「见 x.y」指向不存在的小节", GOOD.replace("埋点见 7.1.1。", "埋点见 7.9.9。"), EXIT_GAP),

    ("正例", GOOD, EXIT_OK),
    ("反例1 优先级挂 ASM（旧版实测永不触发）", GOOD.replace("| P0 | 两端", "| P0 [ASM-003] | 两端"), EXIT_GAP),
    # ⚠️ 下面这条同时触发 B.2 与 NFR-AI 两条判据 —— 两条都没被单独守住。补两个隔离用例。
    # ⚠️ 这条第一版把 NFR-AI 那句写进了**附件 B 段内**，而 B.2 的判据是
    #    「附件 B 段里 grep 到 F-\d+ 就算登记」——那句话里含「F-01」，于是 B.2 反而被判通过。
    #    ⭐ 与今天早上修过的附件 A 同型的「提一句就算数」；这里先绕开它（NFR-AI 放到文末），
    #      判据本身的松紧留待单独处置，不在补测试这一轮里顺手改语义。
    # ⭐ 量程反例：B.1 里提一句 F-01 **不算** B.2 登记（收窄前它会算，与附件 A 同型的松判据）。
    ("反例2d B.1 提到功能但 B.2 没登记（量程反例）",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 |", "| F-01 | 导入 | 导入照片 | P0 | 两端 | 是 |")
         .replace("# 附件 B · 假设\nB.2 略。",
                  "# 附件 B · 假设\nB.1 假设：F-01 的导入路径沿用旧实现。\n\n## B.2 算法能力边界\n（本轮未填）")
     + "\n\n# 附件 D · 其它\nNFR-AI-001：效果验收 —— 识别准确率 ≥90%。\n", EXIT_GAP),
    ("反例2b 只缺 B.2（NFR-AI 已登记，隔离）",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 |", "| F-01 | 导入 | 导入照片 | P0 | 两端 | 是 |")
     + "\n\n# 附件 D · 其它\nNFR-AI-001：效果验收 —— 识别准确率 ≥90%。\n", EXIT_GAP),
    ("反例2c 只缺 NFR-AI（B.2 已登记，隔离）",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 |", "| F-01 | 导入 | 导入照片 | P0 | 两端 | 是 |")
         .replace("B.2 略。", "B.2 算法能力边界：F-01 使用端侧模型，弱光场景召回下降。"), EXIT_GAP),
    ("反例2 AI 功能未在 B.2 登记", GOOD.replace("| 否 | M |", "| 是 | M |"), EXIT_GAP),
    ("反例3 附件 C 空壳", re.sub(r'# 附件 C · 安全与合规\n[\s\S]*?(?=\n# 附件 D)', '# 附件 C · 安全与合规\n', GOOD), EXIT_GAP),
    ("反例4 载体=两端但第四章无三选一", GOOD.replace("两端同一套交互。", ""), EXIT_GAP),
    # ⭐ 2026-09-04：作者把关键词加粗是自然写法，判据必须先剥装饰再比。
    #    此前 `两端**同一套交互**` 会被判成「没回答三选一」—— 写对了却报红。
    ("正例 三选一写成 `两端**同一套交互**`（加粗装饰不许让判据失效）",
     GOOD.replace("两端同一套交互。", "两端**同一套交互**。"), EXIT_OK),
    # 🚨 反向：剥装饰不许变成放行 —— 压根没写三选一的，仍必须红
    ("反例4b 只写了「双端」二字而没回答三选一（剥装饰不许变成放行）",
     GOOD.replace("两端同一套交互。", "**双端**。"), EXIT_GAP),
    ("反例5 缺无障碍 NFR", GOOD.replace("NFR-A11Y-001 无障碍：全部交互键盘可达，对比度 ≥4.5:1，读屏可读。\nNFR-OBS-001 可观测性：关键路径结构化日志含 traceId，告警阈值已定。", ""), EXIT_GAP),
    ("反例6 成本/规模列留空", GOOD.replace("| 否 | M |", "| 否 |  |"), EXIT_GAP),
    ("反例7 第四章颗粒度不足", re.sub(r'\| 失败 \|.*\n', '', GOOD), EXIT_GAP),
    # ⭐ 2026-09-01 变异审计：20 条判据里 **12 条变异存活** —— 其中 10 条**根本没有用例**，
    #    另 2 条（B.2 / NFR-AI）被同一个用例同时触发，谁都没被单独守住。
    #    ⚠️ 表格列的反例要连表头 + 分隔行 + 数据行一起改，只改表头会让解析器直接失配。
    ("反例9 功能清单缺「优先级」列",
     GOOD.replace("| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 | 上线时间 |",
                  "| ID | 功能名称 | 简介 | 载体 | AI? | 成本/规模 | 上线时间 |")
         .replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|")
         .replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | M | 9月 |",
                  "| F-01 | 导入 | 导入照片 | 两端 | 否 | M | 9月 |"), EXIT_GAP),
    ("反例10 优先级列留空",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 |", "| F-01 | 导入 | 导入照片 |  |"), EXIT_GAP),
    ("反例11 功能清单缺「载体」列",
     GOOD.replace("| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 | 上线时间 |",
                  "| ID | 功能名称 | 简介 | 优先级 | AI? | 成本/规模 | 上线时间 |")
         .replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|")
         .replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | M | 9月 |",
                  "| F-01 | 导入 | 导入照片 | P0 | 否 | M | 9月 |"), EXIT_GAP),
    ("反例12 载体列留空",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 |", "| F-01 | 导入 | 导入照片 | P0 |  |"), EXIT_GAP),
    ("反例13 功能清单缺 `AI?` 列",
     GOOD.replace("| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 | 上线时间 |",
                  "| ID | 功能名称 | 简介 | 优先级 | 载体 | 成本/规模 | 上线时间 |")
         .replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|")
         .replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | M | 9月 |",
                  "| F-01 | 导入 | 导入照片 | P0 | 两端 | M | 9月 |"), EXIT_GAP),
    ("反例14 `AI?` 列留空",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 |",
                  "| F-01 | 导入 | 导入照片 | P0 | 两端 |  |"), EXIT_GAP),
    ("反例15 功能清单缺「成本/规模」列",
     GOOD.replace("| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 | 上线时间 |",
                  "| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 上线时间 |")
         .replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|")
         .replace("| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | M | 9月 |",
                  "| F-01 | 导入 | 导入照片 | P0 | 两端 | 否 | 9月 |"), EXIT_GAP),
    # ⚠️ 同上：直接删小节会连带触发「双端功能未回答三选一」。
    #    先把载体从「两端」改成「仅 web」让三选一判据不适用，再删小节 —— 才是隔离。
    ("反例16 第四章缺整节（隔离）",
     GOOD.replace("| F-01 | 导入 | 导入照片 | P0 | 两端 |", "| F-01 | 导入 | 导入照片 | P0 | 仅 web |")
         .replace("### M: 素材 / F-01: 导入", "### 别的标题"), EXIT_GAP),
    ("反例17 附件 C 整节缺失", GOOD.replace("# 附件 C · 安全与合规", "# 附件 Z · 其它"), EXIT_GAP),
    # ⭐ 2026-09-15 新判据（附件 P/Q）的三条反例 —— ⛔ 没有反例的判据等于没判据。
    #   ⚠️ 反例①用「改标题」而不是「删整段」：删段会把 P 的内容并进 Q，
    #     那样测的是「Q 里多了东西」，不是「P 不见了」—— 量错对象。
    ("反例21 附件 P 整节缺失（非目标/路径规划连位置都没了）",
     GOOD.replace("# 附件 P · 范围边界与路径规划", "# 别的一节 · 与范围无关"), EXIT_GAP),
    ("反例22 附件 Q 空壳（只剩标题，依赖与风险都没写）",
     re.sub(r'# 附件 Q · 依赖与风险\n[\s\S]*?(?=\n# 附件 R)', '# 附件 Q · 依赖与风险\n', GOOD), EXIT_GAP),
    # 🚨 2026-09-15 独立评审揪出：下面三条**必须把同附件的另一小节正文加长**，
    #   否则删掉一小节后整段不足 40 字符，走的是上面「空壳」那条分支 ——
    #   用例会绿，但绿的不是它声称测的那条判据。⭐「反例红了 ≠ 规则在守真实形状」。
    ("反例23 附件 P 缺 P.2 路径规划小节（⭐ 正文够长，必须绕开空壳分支）",
     GOOD.replace("P.1 非目标：本次不做批量导出，用户只能单张操作。",
                  "P.1 非目标：本次不做批量导出；不做跨设备同步；不做自动清理。边界写清楚以免评审被问为什么不顺便做。")
         .replace("P.2 路径规划：当前版本先做浏览；未来可能支持批量与自定义封面。", ""), EXIT_GAP),
    ("反例24 附件 Q 缺 Q.1 依赖小节（正文够长）",
     GOOD.replace("Q.1 依赖：D-01 平台组先上线 Auth v2，阻塞 F-01，未确认，后果是整功能上不了线。", ""), EXIT_GAP),
    ("反例25 附件 Q 缺 Q.2 风险小节（正文够长）",
     GOOD.replace("Q.1 依赖：D-01 平台组先上线 Auth v2，阻塞 F-01，未确认，后果是整功能上不了线。",
                  "Q.1 依赖：D-01 平台组先上线 Auth v2，阻塞 F-01，未确认，后果是整功能上不了线，降级为只读模式。")
         .replace("Q.2 风险：R-01 转码成本可能超预算，影响 ROI，概率中，预案是先限分辨率。", ""), EXIT_GAP),
    # 🚨🚨 2026-09-09 第五轮：`appendix()` 用 `s.index(end)` 按**全文首次出现**找终点 ⇒
    #   附件 C 正文里提一句「与 # 附件 D 的口径一致」，C 段就在那句话处**提前截断**，
    #   后半段（含 C.2 权限矩阵）整段逃检，而门报的是「**附件 C 为空壳**」——
    #   ⭐ 一份**完全合规**的 PRD 被凭空指控，而且发生在守 **G7.5 冻结**这道门上。
    #   ⚠️ 这正是我上一批在注释里登记成「元规则查不到的量程边界」的那个间接形态 ——
    #     「查不到」不等于「不用修」。⇒ 两端都锚定行首。
    ("正例 附件 C 正文提到「# 附件 D」→ 0（一句交叉引用不许把本节判成空壳）",
     GOOD.replace("## C.1 数据清单",
                  "## C.1 数据清单\n\n> 留存策略与 # 附件 D 的口径一致。\n", 1), 0),
    # ⚠️ 这条第一版造错了：把 C.2 整句删成「（略）」，附件 C 就成了空壳 ——
    #    实测红的是「附件 C 为空壳」而不是「缺 C.2」。**反例要恰好制造那一个缺口。**
    #    正确做法：C.1 保留足够实质内容，只把 C.2 那半句拿掉。
    ("反例18 附件 C 有实质内容但缺 C.2 权限矩阵（隔离）",
     GOOD.replace("C.1 数据清单：照片路径、设备号。C.2 角色与权限矩阵：普通成员不可导出他人数据（❌）。",
                  "C.1 数据清单：照片路径、设备号、EXIF 位置、人脸特征向量；留存 30 天，删除即物理删除。"),
     EXIT_GAP),
    ("反例8 附件 A 整节缺失", GOOD.replace("# 附件 A · 验收标准", "# 附件 A · 验收标准 本次不涉及X").replace("# 附件 A · 验收标准 本次不涉及X", "## 挪走"), EXIT_GAP),
    ("无效输入 解析不出功能清单", "# 一份没有功能清单表的文档\n正文若干。", EXIT_BAD),
]


def _run_sweep():
    """附件解析的构造空间穷举（说明见 _sweep_lib.sweep_appendix_parsing）。"""
    import tempfile as _tf, shutil as _sh, subprocess as _sp, io as _io
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_appendix_parsing, report as _rep
    _fx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'tests', 'fixtures', 'filled', 'PRD.md')
    if not os.path.exists(_fx):
        print("  ➖ 附件解析穷举：找不到官方夹具 —— **本条没验**（不是通过）")
        return True
    _b = _tf.mkdtemp(prefix='prd-sweep-')

    def _flag(_p):
        _o = _sp.run([sys.executable, os.path.abspath(__file__), _p],
                     capture_output=True, text=True).stdout
        return '附件 C' in _o

    _n, _bad = sweep_appendix_parsing(_flag, _io.open(_fx, encoding='utf-8').read(), _b)
    _sh.rmtree(_b, ignore_errors=True)
    return _rep('附件解析', _n, _bad)


def self_test():
    ok = True
    tmp = tempfile.mkdtemp(prefix="prdgate-")
    print("M8 自证 —— 正例必须绿、每类反例必须红、无效输入必须报错不返绿\n")
    for name, body, want in CASES:
        p = os.path.join(tmp, re.sub(r'\W+', '_', name) + ".md")
        io.open(p, 'w', encoding='utf-8').write(body)
        rc = subprocess.call([sys.executable, os.path.abspath(__file__), p],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        good = (rc == want)
        ok &= good
        print("  %s %-46s 期望 %d 实得 %d" % ("✅" if good else "❌", name, want, rc))
    p = os.path.join(tmp, "不存在的目录", "x.md")
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), p],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    good = (rc == EXIT_BAD); ok &= good
    print("  %s %-46s 期望 %d 实得 %d" % ("✅" if good else "❌", "无效输入 文件不存在", EXIT_BAD, rc))
    # ⭐ --stage 判据必须单独造正反例：不传 --stage 时它整段不执行，
    #    此前所有自证用例都没传，于是**新判据一次都没被跑过而自证照样全绿**。
    def run_stage(body, st):
        p = os.path.join(tmp, "st.md"); io.open(p, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), p, "--stage", st],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    V10_TAIL = """

### OPEN 项登记表
| ID | 内容 | owner | 决策阶段 | 回灌位置 | 状态 |
|---|---|---|---|---|---|
| OPEN-002 | 空态插画 | 张三 | S5 | 四章 | closed |

# 附件 M · v1.0 三方回灌协议
| # | 回灌什么 | 落点 | 状态 |
|---|---|---|---|
| 1 | 最终信息架构 | 三、概要设计 | 已回灌 |
"""
    EMPTY = GOOD
    for i in range(1, 5):
        EMPTY = EMPTY.replace("[稿](x#node-id=%d)" % i, " ")
    for name, body, st, want in (
            ("stage S7 设计稿齐全", GOOD, "S7", 0),
            ("stage S7 设计稿全空必红", EMPTY, "S7", EXIT_GAP),
            ("stage S4 设计稿全空合法", EMPTY, "S4", 0),
            ("stage S7 缺一行也要红", GOOD.replace("[稿](x#node-id=3)", " "), "S7", EXIT_GAP),
            # v1.0 = 设计稿全满 + OPEN 无 open + 附件 M 已填（终局规格 2-2）
            ("stage v1.0 正例（三条件齐）", GOOD + V10_TAIL, "v1.0", 0),
            ("stage v1.0 有未关闭 OPEN 项必红",
             GOOD + V10_TAIL.replace("| OPEN-002 | 空态插画 | 张三 | S5 | 四章 | closed |",
                                     "| OPEN-002 | 空态插画 | 张三 | S5 | 四章 | open |"), "v1.0", EXIT_GAP),
            ("stage v1.0 缺附件 M 必红", GOOD + V10_TAIL.split("# 附件 M")[0], "v1.0", EXIT_GAP),
            ("stage v1.0 附件 M 全空模板必红",
             GOOD + V10_TAIL.replace("| 1 | 最终信息架构 | 三、概要设计 |", "| 1 | 最终信息架构 | <落点> |"), "v1.0", EXIT_GAP),
            ("stage v0.9 别名＝基线档（设计稿空合法）", EMPTY + V10_TAIL, "v0.9", 0)):
        src = run_stage(body, st); g = src == want; ok &= g
        print("  %s %-46s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, src))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败：这道门不可信，先修它"))
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
            if '--self-test' in sys.argv:
                sys.exit(self_test())
            argv = sys.argv[1:]
            mr, mb, stage, files = 4, 12, None, []
            i = 0
            while i < len(argv):
                a = argv[i]
                if a.startswith('--min-rows'):
                    mr = int(a.split('=')[1]) if '=' in a else int(argv[i + 1]); i += 1 if '=' in a else 2; continue
                if a.startswith('--min-bullets'):
                    mb = int(a.split('=')[1]) if '=' in a else int(argv[i + 1]); i += 1 if '=' in a else 2; continue
                if a.startswith('--stage'):
                    stage = a.split('=')[1] if '=' in a else argv[i + 1]; i += 1 if '=' in a else 2; continue
                if a.startswith('--'):
                    i += 1; continue
                files.append(a); i += 1
            if not files:
                print(__doc__); sys.exit(EXIT_BAD)
            sys.exit(report(check(files[0], mr, mb, stage), '--json' in sys.argv))
    _main_guarded(_entry)
