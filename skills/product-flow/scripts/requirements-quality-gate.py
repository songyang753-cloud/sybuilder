#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
需求质量门禁 —— 「需求的单元测试」里机器能查的那部分。

定位（判据见 references/requirements-quality.md）：
  本 skill 原本只有两层，中间是断的：
    ① 填没填  → prd_completeness_check.py
    ② **写得好不好** ← 原本是空的，本脚本补这一层
    ③ 对不对  → 11 视角评审
  中间这层的特征是：可以逐条问、答案是「是/否」、而且大部分能机械查。
  下游返工大半出在这一层。

⚠️ 诚实边界（报结果必须连这段一起报）：
  它查得出「有含糊词」，**查不出「这条需求对不对」**；
  更查不出**缺失** —— 「PRD 里压根没有这条需求」没有字面痕迹。
  缺失要靠歧义扫描（人做）与视角评审。

用法: requirements-quality-gate.py <PRD.md> [--json] [--list-rules]  |  --self-test
退出码: 0=通过 1=有问题 2=跑不了
来源：github/spec-kit（★132318，2026-08-31 查证）的 checklist/clarify/analyze 三命令。
"""
import io, os, re, sys, json, difflib, tempfile, subprocess

# 含糊形容词：中英各一批。判据是「附近没有数字/阈值」——形容词本身不是错，没量化才是。
VAGUE = ('快速|很快|流畅|顺畅|稳定|健壮|直观|友好|高效|丰富|海量|极致|良好|优秀|美观|清晰|简洁|大量|少量|较高|较低|适当|合适'
         r'|fast|quick|robust|scalable|secure|intuitive|seamless|efficient|responsive|performant')
NUM_NEAR = re.compile(r'\d')
# ⚠️ `xxx` 必须是**独立 token**：原来会命中「应形如 xxxx.yyyy」这种**格式示例**（实测假阳性）。
PLACEHOLDER = re.compile(r'TODO|TKTK|FIXME|\?\?\?|待定|待补|待确认内容|(?<![\w.])[xX]{3}(?![\w.])'
                         r'|<[^>\n]{0,12}(占位|填写|待)[^>\n]{0,12}>')
UNTESTABLE = re.compile(r'应该|合理(?:的)?|正常情况下|尽量|视情况|酌情|尽可能|大致|基本上')
# 只在验收/需求语境里查无判据词，避免误伤正文叙述
ACC_CTX = re.compile(r'FR-\d+|AC-\d+|NFR|验收|Then|预期')

RULES = [
    ("vague-adjective", "含糊形容词没有量化（附近无数字/阈值）"),
    ("placeholder", "占位符残留（TODO / 待定 / <占位>）"),
    ("untestable", "验收语境里出现无判据词（应该/合理/正常情况下）"),
    ("term-drift", "同一个 F-xx 在文档里有多个名字（术语漂移）"),
    ("duplicate-req", "近重复需求（两条 FR 说的是同一件事）"),
    ("test-name-verbatim", "测试名/DOM 断言原样搬进需求（反向提取型 PRD 的典型形态）"),
    ("traceability", "检查表条目带出处的占比 <80%"),
]


def die(m):
    print("UNABLE: " + m, file=sys.stderr); sys.exit(2)


def strip_code(s):
    """去掉代码块与行内代码——里面的 TODO/fast 不是需求含糊，是代码。"""
    # ⚠️ 必须**等长替换**：原来把行内代码换成两个空格，偏移全乱 ——
    #    行号会漂，而且任何想回到 raw 取原文的判据都会取错位置（实测踩过：
    #    来源标记 `[查证·x.test.js·日期]` 本身就是行内代码，在剥离后的文本里不存在，
    #    想回 raw 找又因为偏移不一致而取错段）。改为用等量空格填充。
    s = re.sub(r'```[\s\S]*?```', lambda m: '\n' * m.group(0).count('\n')
               + ' ' * (len(m.group(0)) - m.group(0).count('\n')), s)
    return re.sub(r'`[^`\n]*`', lambda m: ' ' * len(m.group(0)), s)


def lineno(s, i):
    return s[:i].count('\n') + 1


def check(path):
    if not os.path.isfile(path): die("读不到 %s" % path)
    raw = io.open(path, encoding='utf-8', errors='replace').read()
    s = strip_code(raw)
    hits, notes = [], []

    def add(rid, line, text, why):
        hits.append({"rule": rid, "line": line, "text": text.strip()[:120], "why": why})

    # ⓘ 注记通道：**报出但不阻断**。给「值得人看一眼、但机器判不了对错」的信号用。
    #    ⛔ 不许把猜测写成判定 —— 判不了就别红，红了人就会学会忽略它。
    def note(rid, line, text, why):
        notes.append({"rule": rid, "line": line, "text": text.strip()[:120], "why": why})

    # 1 含糊形容词：附近 ±40 字无数字即报
    # ⚠️ 判「附近有没有数字」之前必须先剔除**编号里的数字**。
    #    `F-01` / `CHK001` / `§4.2` 都含数字，但它们不是量化 ——
    #    首版没剔除，于是「导入速度要快」因为同段有 `F-01` 而被豁免，反例失效。
    # ⚠️ 字母前缀**必须是必需的**。写成 `(?:[A-Z]{1,4}-)?\d+` 会让 `?` 生效于整个前缀，
    # 于是它剥掉的是**所有数字**而不只是编号里的数字 —— 「响应要快，P95 ≤ 300ms」
    # 会因为 300 被剥掉而被判成「没有量化」。**过度剥离＝把合规的判成不合规。**
    #
    ID_NUM = re.compile(r'[A-Z]{1,4}-\d+(?:\.\d+)?|§\S*|第[一二三四五六七八九十]+[章节]|CHK\d+')
    for m in re.finditer(VAGUE, s, re.I):
        # ⚠️ 形容词后紧跟汉字 = **构词**，不是程度描述：
        #    「清晰度」是指标名、「快速氛围」是 UI 选项名 —— 实测都被误报过。
        #    ⭐ 门禁的假阳性比漏报更伤：它让人对告警脱敏，然后连真的一起忽略。
        nxt = s[m.end():m.end() + 1]
        if '\u4e00' <= nxt <= '\u9fff':
            continue
        near = ID_NUM.sub(' ', s[max(0, m.start() - 40): m.end() + 40])
        if NUM_NEAR.search(near): continue
        ln = lineno(s, m.start())
        add("vague-adjective", ln, s.split('\n')[ln - 1],
            "「%s」没有量化 —— 写不出数字说明这条还没想清楚，登记 TBD 带 owner，别用形容词蒙混" % m.group(0))

    # 2 占位符
    for m in PLACEHOLDER.finditer(s):
        ln = lineno(s, m.start())
        add("placeholder", ln, s.split('\n')[ln - 1],
            "占位符残留：它看起来像填了，其实是没想过")

    # 3 验收语境里的无判据词
    for i, line in enumerate(s.split('\n'), 1):
        if not ACC_CTX.search(line): continue
        m = UNTESTABLE.search(line)
        if m:
            add("untestable", i, line,
                "「%s」不可判定 —— 验收标准的检验方法是「另一个人能不能判断通过与否」" % m.group(0))

    # 4 术语漂移：同一个 F-xx 在文档里出现多个名字
    #    判据精确：只看「F-xx 紧跟的名字」，不做模糊词表比对（那会制造大量假阳性）
    # 🚨 2026-09-02 修假阳性：原判据把 `|` 也当名字分隔符，于是**任何表格里
    #    `| F-06 |` 后面那一格都被当成「别名」** —— 指标表的 `TBD`、AI 表的
    #    `检索召回 / 精度`、自检清单的标题，全被报成术语漂移。实测 13 处**全是假的**。
    #    ⭐ 门禁的假阳性比漏报更伤：它让人对告警脱敏，然后连真的也一起忽略。
    #    改为只认两个**权威命名位**：
    #      ① 功能清单表的「ID | 功能名称」两列（第二格才是名字）
    #      ② 第四章小节标题 `### …/ F-xx: <名>`
    names = {}

    def _note(fid, nm, pos):
        nm = nm.strip().rstrip('*# ')
        if nm and not nm.startswith(('<', 'TBD', 'ASM')):
            names.setdefault(fid, {}).setdefault(nm, lineno(s, pos))

    m_hdr = re.search(r'^\s*\|\s*ID\s*\|\s*功能名称[^\n]*$', s, re.M)
    if m_hdr:
        # ⚠️ 从表头**行尾**切分时，第一个片段是空串 —— 直接 break 会让整张表一行都读不到
        #    （自证当场抓住：反例「同一功能两个名字」期望红实得绿）。跳过前导空片段。
        for ln in s[m_hdr.end():].split('\n')[1:]:
            if not ln.strip().startswith('|'):
                break
            cells = [c.strip() for c in ln.strip().strip('|').split('|')]
            if len(cells) >= 2 and re.fullmatch(r'F-\d+', cells[0]):
                _note(cells[0], cells[1], m_hdr.end())
    # ⚠️ 原来上限 20 字：**名字比 20 字长就被截断，截断结果与全名互判成「漂移」**
    #    （F-55「三模式导航（Browse / Discover / Organize）」当场中招）。改成读到行尾。
    for m in re.finditer(r'^###[^\n]*?(F-\d+)\s*[:：]\s*([^\n|]{2,})$', s, re.M):
        _note(m.group(1), m.group(2), m.start())
    for fid, nm in names.items():
        if len(nm) > 1:
            add("term-drift", min(nm.values()), "%s = %s" % (fid, " / ".join(nm)),
                "同一功能多个叫法 —— 下游按哪个生成？术语漂移是 PRD 自相矛盾最常见的入口")

    # 5 近重复需求
    # ⚠️ 原来取「标题后第一行」当需求正文，而表格型需求的第一行是**表头**
    #    `| 项 | 值 | 状态 |` —— 于是任意两条表格型需求都 100% 相似（实测 NFR-003≈NFR-004 假阳性）。
    #    改为取第一行**非表格**的实质文本。
    def _body(seg):
        for ln in seg.split('\n'):
            t = ln.strip()
            if len(t) >= 10 and not t.startswith('|') and not set(t) <= set('-: |'):
                return t
        return ''
    # ⚠️ 别用 `([\s\S]{0,400})` 去截正文：它是**贪婪**的，会把下一条 FR 的标题一起吞掉，
    #    而 finditer 从上一个匹配末尾继续 —— 于是**第二条 FR 永远匹配不到**（自证当场抓住）。
    #    改为先定位所有标题，再按相邻标题切片。
    # ⚠️ 层级必须放宽到 `##`~`####`：模板写 `##`、真 PRD 写 `###`、自证夹具写纯文本。
    #    ⭐ 这是**今天第三次**踩同一个坑（G1 假阳性 100% 的根因就是它）——
    #    锁死任一层级都会把另一种合规写法整片漏掉，而漏掉时它只是安静地什么都不报。
    heads = [(mm.start(), mm.group(1)) for mm in
             re.finditer(r'^#{2,4}\s*((?:N?FR)-[\w-]*\d+)[^\n]*$', s, re.M)]
    frs = []
    for k, (pos, fid) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else min(len(s), pos + 2000)
        b = _body(s[s.index('\n', pos) + 1: end])
        if b: frs.append((lineno(s, pos), fid, b))
    norm = [re.sub(r'\W', '', f[2]) for f in frs]   # ⭐ 预计算一次:原来内层每对都重算 frs[i] 的归一化,O(n²)次 re.sub
    for i in range(len(frs)):
        a = norm[i]
        if not a: continue
        la = len(a)
        for j in range(i + 1, len(frs)):
            b = norm[j]
            if not b: continue
            # O(1) 长度上界预筛:ratio ≤ 2*min/(la+lb),够不到阈值就跳,不对明显不相似的对跑昂贵的 ratio()
            if 2 * min(la, len(b)) < 0.85 * (la + len(b)): continue
            if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
                add("duplicate-req", frs[j][0], "%s ≈ %s" % (frs[i][1], frs[j][1]),
                    "两条需求说的是同一件事 —— 合并，保留表述更清楚的那条")

    # 5b 测试名 / DOM 断言原样搬进需求
    # ⭐ 2026-09-02 实测于一份从 591 条测试反向提取的真 PRD：121 条里 **12 条**是
    #    `exports isAvailable, sign, read` / `index.html contains privacy-intro div`
    #    这种测试函数签名与 DOM 断言 —— 其中「隐私保护」功能的**全部 6 条**都是这种，
    #    等于那个功能没有需求。PRD 模板早写着「**测试名 ≠ 需求**」，而没有任何东西守它。
    # ⚠️ 前提守卫：整篇以中文为主时才判。全英文 PRD 每条都会命中，那是判据不适用，不是缺陷。
    _hpos = [h[0] for h in heads]

    def _end_of(pos):
        nxt = [x for x in _hpos if x > pos]
        return nxt[0] if nxt else min(len(s), pos + 1200)

    doc_cjk = sum(1 for ch in s if '\u4e00' <= ch <= '\u9fff') / max(1, len(s))
    if doc_cjk > 0.15:
        for pos, fid in heads:
            body = _body(s[s.index('\n', pos) + 1: _end_of(pos)])
            b = re.sub(r'\*\*行为\*\*[：:]\s*', '', body).strip()
            if len(b) <= 8:
                continue
            cjk = sum(1 for ch in b if '\u4e00' <= ch <= '\u9fff') / len(b)
            if cjk < 0.15:
                add("test-name-verbatim", lineno(s, pos), "%s %s" % (fid, b),
                    "这是测试名/DOM 断言，不是需求 —— 测试验的是「代码现在这么做」，"
                    "PRD 要写「产品应该这么做」")

    # 5c ⓘ 注记：一个功能的**全部**需求来自同一个来源文件
    #    ⭐ 这是「按测试文件批量挂需求」的指纹。实测那份 PRD 20 个有需求的功能里 7 个如此，
    #    其中「相册管理」的 6 条全来自 `album-engine-stress.test.js`（讲任务调度与并发），
    #    与功能毫无关系 —— 归属是按**文件名**匹配的，不是按内容。
    #    ⛔ 但**不做硬门**：一个功能确实可能只有一个测试文件。判不了对错就只报不判。
    # ⚠️ 必须按**相邻标题**切片：固定窗口会跨进下一条需求，
    #    于是每个功能都被算出多个来源，这条注记永远不触发（安静失效）。
    owner_src = {}
    for k, (pos, fid) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(s)
        # ⚠️ 必须用 **raw**：check() 开头 `s = strip_code(raw)` 把**行内代码剥掉了**，
        #    而来源标记正是行内代码 `` `[查证·xxx.test.js·日期]` `` —— 在 s 里根本不存在。
        #    ⭐ 判据读的是被预处理过的文本，而它要找的东西恰好在预处理里被删了：
        #      它不会报错，只会**永远不触发**。
        own = re.search(r'所属\s*(F-\d+)', s[pos:end])
        # ⭐ 来源标记本身是行内代码，在 strip 后的文本里是空格 —— 必须回 raw 取。
        #    strip_code 已改为等长替换，所以这里的 pos/end 与 raw 对齐。
        src = re.search(r'查证·([^\]·\s]+)', raw[pos:end])
        if own and src:
            owner_src.setdefault(own.group(1), []).append((src.group(1), lineno(s, pos)))
    for fid, lst in sorted(owner_src.items()):
        srcs = {x[0] for x in lst}
        if len(srcs) == 1 and len(lst) >= 4:
            note("single-source-attribution", lst[0][1],
                 "%s 的全部 %d 条需求都来自 %s" % (fid, len(lst), next(iter(srcs))),
                 "「按测试文件批量挂需求」的指纹 —— 逐条复核它们是否真的属于这个功能")

    # 6 可追溯率（只在存在 CHK 条目时才判，否则 N/A）
    chk = re.findall(r'^\s*-\s*\[[ x]\]\s*CHK\d+[^\n]*', s, re.M)
    trace_na = not chk
    if chk:
        # ⚠️ 出处标记可能出现在方括号**中间**（`[Clarity, §4]`），不是只在开头。
        #    首版要求以标记开头，把合规的条目判成了不合规 —— 判据写窄了。
        TRACE = re.compile(r'\[[^\]]*(?:§|Spec\s|Gap|Ambiguity|Conflict|Assumption|附件|第[一二三四五六七八九十]|\d+\.\d+)[^\]]*\]')
        traced = [c for c in chk if TRACE.search(c)]
        rate = len(traced) / len(chk)
        if rate < 0.8:
            add("traceability", 0, "检查表 %d 条，带出处 %d 条（%.0f%%）" % (len(chk), len(traced), rate * 100),
                "带出处 <80% —— 没有出处的条目没人能复核")
    return hits, notes, trace_na, len(chk)


def main():
    if '--list-rules' in sys.argv:
        for r, d in RULES: print("%-18s %s" % (r, d)); return 0
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a: print(__doc__); return 2
    hits, notes, trace_na, nchk = check(a[0])
    if '--json' in sys.argv:
        print(json.dumps({"found": len(hits), "hits": hits, "notes": notes}, ensure_ascii=False, indent=1))
        return 1 if hits else 0
    by = {}
    for h in hits: by.setdefault(h["rule"], []).append(h)
    for rid, desc in RULES:
        g = by.get(rid, [])
        if rid == "traceability" and trace_na and not g:
            print("➖ [%s] %s —— N/A（文档里没有 CHK 检查表条目）" % (rid, desc)); continue
        if not g:
            print("✅ [%s] %s" % (rid, desc)); continue
        print("❌ [%s] %s（%d 处）" % (rid, desc, len(g)))
        for h in g[:8]:
            print("     :%s  %s" % (h["line"], h["text"]))
            print("       → %s" % h["why"])
        if len(g) > 8: print("     …另有 %d 处" % (len(g) - 8))
    for n in notes[:12]:
        print("ⓘ [%s] :%s  %s" % (n["rule"], n["line"], n["text"]))
        print("     → %s" % n["why"])
    print("\n结论：%s%s" % ("发现 %d 处" % len(hits) if hits else "机械层无发现",
                          "（另有 %d 条注记，只报不阻断）" % len(notes) if notes else ""))
    print("⚠️ 它查得出「有含糊词」，**查不出「这条需求对不对」**，更查不出**缺失**——")
    print("   「PRD 里压根没有这条需求」没有字面痕迹，只能靠歧义扫描与 11 视角评审。")
    return 1 if hits else 0


# ------------------------------------------------------------------ M8 自证
GOOD = """# PRD
## 三、概要设计
| ID | 功能名称 | 简介 |
|---|---|---|
| F-01 | 导入 | 批量导入照片 |

## 四、详细设计
### M: 素材 / F-01: 导入
单次最多 500 张，超出提示。

# 附件 A · 验收标准
## FR-011 所属 F-01 MUST
Given 已选 500 张 When 点击导入 Then 全部入库且 P95 ≤ 3000ms

## FR-012 所属 F-01 MUST
Given 磁盘不足 When 点击导入 Then 阻止并提示剩余空间不足

## 检查表
- [ ] CHK001 是否定义了导入失败的错误文案？[Gap]
- [ ] CHK002 「批量」是否量化为具体条数？[Clarity, §4]
"""

CASES = [
    ("正例", GOOD, 0),
    ("反例 含糊形容词无量化", GOOD.replace("单次最多 500 张，超出提示。", "导入速度要快，界面要流畅。"), 1),
    ("反例 占位符残留", GOOD.replace("批量导入照片", "批量导入照片 TODO"), 1),
    ("反例 验收里出现无判据词", GOOD.replace("Then 全部入库且 P95 ≤ 3000ms", "Then 应该正常入库"), 1),
    ("反例 同一功能两个名字", GOOD.replace("### M: 素材 / F-01: 导入", "### M: 素材 / F-01: 素材导入"), 1),
    # ⭐ 2026-09-02 防假阳性用例：拿真 PRD 跑时这三类**全是误报**（18/18），
    #    而门禁的假阳性比漏报更伤 —— 它让人对告警脱敏，然后连真的一起忽略。
    ("防假阳 指标名里的形容词（清晰度/快速氛围）不算含糊",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n清晰度以 blur.json 为主；快速氛围是一个选项名。\n\n"
     "# 附件 A · 验收标准\n## FR-011 所属 F-01 MUST\nGiven 已选 500 张 When 导入 Then 全部入库且 P95 ≤ 3000ms\n", 0),
    ("防假阳 格式示例 xxxx.yyyy 不算占位符",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n授权码应形如 xxxx.yyyy，格式不对要报错。\n\n"
     "# 附件 A · 验收标准\n## FR-011 所属 F-01 MUST\nGiven 码不合法 When 激活 Then 提示格式错误并给出 1 个示例\n", 0),
    ("防假阳 两条表格型需求不算近重复（表头相同不是内容相同）",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n## FR-011 所属 F-01 MUST\nGiven 已选 500 张 When 导入 Then 全部入库且 P95 ≤ 3000ms\n\n"
     "## NFR-003 所属 全局 MUST（并发）\n| 项 | 值 | 状态 |\n|---|---|---|\n| 解码并发上限 | 有上限，数值 TBD-23 | 待答 |\n\n"
     "## NFR-004 所属 全局 SHOULD（存储）\n| 项 | 值 | 状态 |\n|---|---|---|\n| 存储方式 | Referenced 或 Managed，只问一次 | 已定 |\n", 0),
    # ⭐ 2026-09-02 新判据的正反例（来自一份真 PRD 的实测：121 条里 12 条是测试名直搬）
    ("反例 测试名直搬进需求（test-name-verbatim）",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n"
     "### FR-011　所属 F-01　MUST\n**行为**：exports isAvailable, sign, read\n"
     "- AC-1 该行为可由 `test/x.test.js` 验证\n", 1),
    ("反例 DOM 断言直搬（test-name-verbatim）",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n"
     "### FR-011　所属 F-01　MUST\n**行为**：index.html contains privacy-intro div\n", 1),
    ("防假阳 中文需求不算测试名直搬",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n"
     "### FR-011　所属 F-01　MUST\n**行为**：单次导入超过 500 张时提示并停止，不静默截断\n", 0),
    ("防假阳 需求里带英文标识符但主体是中文",
     "# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n"
     "### FR-011　所属 F-01　MUST\n**行为**：`isAvailable` 返回 false 时，界面显示「该能力不可用」而不是空白\n", 0),
    ("反例 两条 FR 近重复", GOOD.replace(
        "Given 磁盘不足 When 点击导入 Then 阻止并提示剩余空间不足",
        "Given 已选 500 张 When 点击导入 Then 全部入库且 P95 ≤ 3000ms"), 1),
    ("反例 检查表可追溯率不足", GOOD.replace("[Gap]", "").replace("[Clarity, §4]", ""), 1),
    ("正例 含糊词但已量化（不许误判）", GOOD.replace("单次最多 500 张，超出提示。",
                                              "响应要快：P95 ≤ 300ms，超时提示。"), 0),
    ("正例 代码块里的 TODO 不算", GOOD + "\n```js\n// TODO: refactor\nconst fast = 1\n```\n", 0),
]


def self_test():
    t = tempfile.mkdtemp(prefix="rq-")
    ok = True
    print("M8 自证 —— 正例绿 / 每条规则各造一个反例必红 / 无效输入报 2\n")
    for name, body, want in CASES:
        p = os.path.join(t, re.sub(r'\W+', '_', name) + ".md")
        io.open(p, 'w', encoding='utf-8').write(body)
        rc = subprocess.call([sys.executable, os.path.abspath(__file__), p],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        g = rc == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, rc))
    # ⭐ 注记是**不阻断**的 —— 退出码测不出它。必须落在 finding id 上断言。
    #    （同一课今天在 element-identity-gate 上学过：判据被删掉与另一条替它红，
    #      在退出码上完全一样。）
    _note_md = ("# PRD\n## 三、概要设计\n| ID | 功能名称 | 简介 |\n|---|---|---|\n| F-01 | 导入 | 批量导入 |\n\n"
     "## 四、详细设计\n### M: 素材 / F-01: 导入\n单次最多 500 张。\n\n"
     "# 附件 A · 验收标准\n"
        + "### FR-011　所属 F-01　MUST\n**行为**：导入超过 500 张要提示\n- 来源：`[查证·a.test.js·2026-01-01]`\n"
        + "### FR-012　所属 F-01　MUST\n**行为**：磁盘不足要阻止\n- 来源：`[查证·a.test.js·2026-01-01]`\n"
        + "### FR-013　所属 F-01　MUST\n**行为**：重复文件要跳过\n- 来源：`[查证·a.test.js·2026-01-01]`\n"
        + "### FR-014　所属 F-01　MUST\n**行为**：取消后要能重来\n- 来源：`[查证·a.test.js·2026-01-01]`\n")
    _p = os.path.join(t, "note.md"); io.open(_p, 'w', encoding='utf-8').write(_note_md)
    _r = subprocess.run([sys.executable, os.path.abspath(__file__), _p, "--json"],
                        capture_output=True, text=True)
    try:
        _ids = {n["rule"] for n in json.loads(_r.stdout).get("notes", [])}
    except Exception:
        _ids = set()
    g = "single-source-attribution" in _ids and _r.returncode == 0
    ok &= g
    print("  %s %-30s %s" % ("✅" if g else "❌", "注记 single-source（且不阻断）",
                             "命中且退出码 0" if g else "实得 ids=%s rc=%s" % (sorted(_ids), _r.returncode)))

    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope.md')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = rc == 2; ok &= g
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g else "❌", "文件不存在", rc))
    print("\n%s" % ("✅ 自证通过" if ok else "❌ 自证失败"))
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
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    def _entry():
        sys.exit(self_test() if '--self-test' in sys.argv else main())
    _main_guarded(_entry)
