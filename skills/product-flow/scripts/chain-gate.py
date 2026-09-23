#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
链路前段对账门 G0 / G0.5 / G0.8 —— 补 M4 缺掉的前三个交接。

为什么需要它（2026-08-31 全链 review 的发现）：
  M4 号称「本流水线最有价值的一道机制」，但它的四道门 **G1 才从 S4→S5 开始**。
  也就是说：**S1→S2、S2→S3、S3→S4 三个交接完全没有对账**——
  而 S3→S4 恰恰是「最贵的决定」流向 PRD 的那一环。
  上游做得再好，下游没接住也白做，而且**没有任何东西会因此报错**。

  另一个不对称：PRD 附件 H.1 是「**下游**产物输入映射」（我喂给谁），
  **没有「上游输入映射」（我吃了谁）**——所以 S3→S4 无从对账。

═══ md 跨阶段传递的三种衰减（本门禁要抓的东西）═══
  ① **丢项**：上游 N 条，下游只承接 M 条，差额无人知道
  ② **改写漂移**：下游用自己的话复述上游，语义悄悄变了
  ③ ⭐ **静默降级**：上游写「必须」下游写成「建议」；上游写数字下游写形容词
     —— 第三种最隐蔽，因为下游读起来完全通顺

用法:
  chain-gate.py G0   <input/definition.md> <research 目录>
  chain-gate.py G0.5 <research/insights.md> <definition-final.md>
  chain-gate.py G0.6 <research-decision-ledger.md> <definition-final.md>
  chain-gate.py G0.8 <definition-final.md> <PRD.md>
  chain-gate.py G0.9 <definition-final.md> <state.md>
  chain-gate.py --self-test
退出码: 0=双向通过 1=有漏/有降级 2=跑不了（绝不折叠成 0）
"""
import io, os, re, sys, tempfile, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at   # noqa: E402  段落定位唯一正本

# S3 定义必须覆盖、且必须落进 PRD 的项（与 s3-definition.md 第二节一致）
DEF_ITEMS = [
    ("一句话定位", r'一句话定位|产品定位', r'摘要|定位'),
    ("目标用户", r'目标用户', r'目标用户'),
    ("不服务谁", r'不服务', r'不服务'),
    ("核心价值", r'核心价值', r'核心价值|价值'),
    ("明确不做", r'明确不做', r'明确不做'),
    ("功能集合", r'功能集合|功能清单', r'功能清单'),
    ("载体", r'载体', r'载体'),
    ("AI 判定", r'AI\?', r'AI\?'),
    ("成本量级", r'成本', r'成本'),
    ("成功指标", r'成功长什么样|成功指标', r'目标'),
    ("护栏指标", r'护栏', r'护栏'),
    ("关键路径", r'关键路径', r'核心体验路径|关键路径'),
    ("数据边界", r'数据边界|状态与数据', r'数据清单|附件 C'),
    ("产品调性", r'产品调性|情绪基调', r'情绪基调|调性|附件 K'),
    ("硬约束", r'硬约束', r'约束|依赖'),
    ("单向门", r'单向门', r'单向门'),
    ("失败路径", r'失败路径', r'风险|失败路径'),
]
NUM = re.compile(r'\d')
# ⚠️ 字母前缀**必须是必需的**。写成 `(?:[A-Z]{1,4}-)?\d+` 会让 `?` 生效于整个前缀，
# 于是它剥掉的是**所有数字**而不只是编号里的数字 —— 「响应要快，P95 ≤ 300ms」
# 会因为 300 被剥掉而被判成「没有量化」。**过度剥离＝把合规的判成不合规。**
ID_NUM = re.compile(r'[A-Z]{1,4}-\d+(?:\.\d+)?|§\S*|第[一二三四五六七八九十]+[章节]|CHK\d+')
DOWNGRADE = [("必须→建议", r'必须|MUST|不许|绝不', r'建议|SHOULD|尽量|可以考虑')]


def die(m):
    print("UNABLE: " + m, file=sys.stderr); sys.exit(2)


def read(p):
    if not os.path.exists(p): die("读不到 %s" % p)
    if os.path.isdir(p):
        out = []
        for r, _, fs in os.walk(p):
            for f in fs:
                if f.endswith('.md'):
                    out.append(io.open(os.path.join(r, f), encoding='utf-8', errors='replace').read())
        if not out: die("目录里没有 md：%s" % p)
        return "\n".join(out)
    return io.open(p, encoding='utf-8', errors='replace').read()


def sect(s, pat, span=1200):
    """取某一节的正文。**按标题层级切**：父节包含它的子节。

    ⚠️ 2026-09-04 全链实跑发现：原实现在**任意层级**的下一个标题处截断，
    于是 `## 五、背景与目标` 这种父标题（官方 PRD 模板就是这个结构）
    会被紧随其后的 `### 5.1 …` 立刻截断成**空正文** ——
    而 G0.8 的降级判据是「定义里有数字、PRD 对应位置没有数字」，
    正文为空自然没有数字 → **一份写对了的 PRD 被报出六条「量化降级」**。
    ⭐⭐ 假阳性比漏报更贵：六条一起出现时，看的人只会认为这道门坏了，
    然后连真的那两条正向漏也一起忽略掉。
    """
    #    🚨 第一版的修法是「父节包含子节」—— 自证反例当场抓住了它：
    #      那样 `## 五、目标` 会把 `### 护栏指标` 的数字一起吃进来，
    #      **子节的数字掩盖父节的含糊**，降级判据就废了。
    #    ⭐ 正确判据不是「切多宽」，而是**匹配到哪个标题**：
    #      在所有匹配的标题里取**第一个自身正文非空的**。
    #      `## 五、背景与目标` 自身正文是空的（紧跟 `### 5.1`）→ 跳过，
    #      落到 `### 5.2 目标` 上，正是作者真正写内容的那一节。
    ms = list(re.finditer(r'^(#{1,4})[^\n]*?(?:%s)[^\n]*$' % pat, s, re.M))
    if not ms: return None
    fallback = None
    for m in ms:
        rest = s[m.end():]
        nxt = re.search(r'^#{1,4}\s', rest, re.M)
        own = rest[:nxt.start()] if nxt else rest[:span]
        if fallback is None: fallback = own
        if own.strip(): return own
    return fallback


def emit(title, fwd, rev, extra=None, notes=None):
    """`extra` = 衰减（**计入退出码**）· `notes` = 纯信息（**不计入**）。

    ⚠️ 2026-09-04 实跑发现：此前只有 `extra` 一个通道，
    于是「已把 S1 排除出调研语料」这种**纯说明**也被塞进去 ——
    印成「🟠 衰减」并且**让这道门退出 1**。
    ⭐ 也就是说这道门**没有「不失败地说句话」的通道**：它一开口就等于报缺陷。
    后果有两面：真发生自覆盖时把说明误报成缺陷；
    而写门的人为了不误报，就会倾向于**什么都不说** —— 信息因此消失。
    """
    print("# 链路对账 %s" % title)
    for x in fwd: print("  🔴 正向漏 %s" % x)
    for x in rev: print("  🔴 反向漏 %s" % x)
    for x in (extra or []): print("  🟠 衰减 %s" % x)
    for x in (notes or []): print("  ℹ️ %s" % x)
    if not fwd and not rev and not extra: print("  ✅ 双向通过，无衰减")
    print("\n⚠️ 上游做得再好，下游没接住也白做——**而没有任何东西会因此报错**。")
    return 1 if (fwd or rev or extra) else 0


# ---------------------------------------------------------------- G0
def read_corpus(d, exclude=None):
    """目录语料 —— **排除掉 exclude 指向的那个文件**。

    ⚠️⚠️ 2026-08-31 实测的一个洞：G0 拿 `.product-flow/` 当调研目录时报「✅ 双向通过」，
    而 `design-brief.md`（同时被当作 S1 输入）就在那个目录里 ——
    **S1 的关键词用自己覆盖了自己**，这道门无条件通过。
    ⭐ 自覆盖比误报更危险：它长得和「调研做得好」一模一样。
    排除之后若一份 md 都不剩，那不是「通过」，是 UNABLE。"""
    if not os.path.isdir(d):
        return read(d), 0
    ex = os.path.realpath(exclude) if exclude else None
    out, skipped = [], 0
    for r, _, fs in os.walk(d):
        for f in sorted(fs):
            if not f.endswith('.md'):
                continue
            full = os.path.join(r, f)
            if ex and os.path.realpath(full) == ex:
                skipped += 1
                continue
            out.append(io.open(full, encoding='utf-8', errors='replace').read())
    if not out:
        die("调研目录里除了 S1 定义文件本身没有别的 md：%s —— 那不是调研语料" % d)
    return "\n".join(out), skipped


# S1 的方向清单**优先从一个明确的产出位读**，读不到才退回扫「」。
# ⚠️ 2026-09-04 实测发现的坑：原实现把 S1 里**每一处**「」都当成「点名的方向」，
#    而中文里「」既用于命名也用于强调 —— 于是
#    **S1 写得越清楚（强调越多），G0 报的假漏越多**。
#    实跑一份真 S1 时它报了两条漏，两条都是强调引号（「一道门从来没跑过」）。
#    ⛔ 更糟的是：**这个约定在全仓零处文档**，而 SKILL.md 自己用了 296 次「」，
#    绝大多数是强调。也就是说这道门要求的写法，本 SOP 自己从不遵守。
#    ⭐ 一道会把正确产物判红的门，最后一定会被人加豁免绕过去 —— 所以修它而不是放宽它。
#    ⭐⭐ 正确解法与「展示名给人看 / slug 给对账用」是同一条：
#    **对账用的键必须是明确的产出位，不能从散文的标点里刮。**
DIRECTIONS_SEC = re.compile(r'^#{1,4}\s*(?:粗颗粒功能|方向清单|点名的方向)[^\n]*$', re.M)


def s1_directions(s1):
    """返回 (方向集合, 取自哪种模式)。模式必须报出来 —— 不同模式的严格度不同。"""
    # ⚠️⚠️ 2026-09-10 **构造空间穷举**（标题写法 × 列表记号 × 命名标记 × 行内强调，80 例）
    #   扫出 **10 例失配**，全是一个形状：**3 空格缩进的标题**（合法 ATX）认不出 ⇒
    #   静默降级到 `quotes` 兜底模式，**一个方向都取不到，S1→S2 对账整条失效**。
    #   ⭐ 降级是「静默」的这一点最要命：输出里看不出「我没找到那一节」，
    #     只看到「没有方向」——与「真的没写方向」长得一模一样。
    #   ⇒ 交给 `_section`（缩进 0–3 / `#` 后空白 / 级别 / 围栏 / setext 它都处理过）。
    #     ⛔ 不在这里再手写一遍标题匹配 —— 那正是「多套手写解析器」这个根因本身。
    seg = section_at(s1, r'粗颗粒功能|方向清单|点名的方向', regex=True)
    if seg is not None:
        # ⭐ 小节里**只认加粗**。第一版把加粗和「」都收，结果强调引号照样漏进来 ——
        #    那等于把小节模式又变回了扫标点。**命名与强调必须只有一个标记。**
        #    整节一处加粗都没有时才退回「」，但那属于降级路径。
        rows = [ln.strip() for ln in seg.splitlines()
                if ln.strip().startswith(('-', '*', '|')) or re.match(r'^\d+[.、]', ln.strip())]
        # 只取**每项开头那个**加粗：行内还会有强调用的加粗
        #    （实例：`3. **缺口高亮**：**从没跑过**的门…`）——
        #    同一个「命名与强调混用」的问题下沉一层，必须在这里截住。
        LEAD = re.compile(r'^[-*\s]*(?:\d+[.、])?\s*\|?\s*\*\*([^*\n]{2,20})\*\*')
        items = set()
        for ln in rows:
            m2 = LEAD.match(ln)
            if m2 and m2.group(1).strip():
                items.add(m2.group(1).strip())
        if items:
            return items, 'section'
        items = {v.strip() for ln in rows
                 for v in re.findall(r'[「【]([^」】\n]{2,20})[」】]', ln) if v.strip()}
        if items:
            return items, 'section-quotes'
    return set(re.findall(r'[「【]([^」】\n]{2,14})[」】]', s1)), 'quotes'


def g0(s1_path, research_dir):
    s1 = read(s1_path)
    rs, self_excluded = read_corpus(research_dir, exclude=s1_path)
    kws, mode = s1_directions(s1)
    if not kws: return emit("G0 · S1→S2（需求 → 调研覆盖）", [], [],
                            ["S1 里既没有「粗颗粒功能」小节、也没有「」标出的关键点，"
                             "无法机械对账（人工核）—— 这不是通过"])
    fwd = ["S1 点名的「%s」在调研里没出现" % k for k in sorted(kws) if k not in rs]
    notes = []
    if mode == 'section':
        notes.append("方向取自 S1 的「粗颗粒功能」小节的**加粗项**共 %d 项（强调引号不参与对账）" % len(kws))
    elif mode == 'section-quotes':
        notes.append("⚠️ 小节里一处加粗都没有，退回扫该节的「」共 %d 项 —— "
                     "**强调引号会被当成方向**，建议把方向写成加粗" % len(kws))
    else:
        notes.append("⚠️ S1 里没有「粗颗粒功能」小节，退回扫全文「」共 %d 项 —— "
                     "**这种模式下强调引号会被当成方向，可能报出假漏**，"
                     "正确做法是在 S1 里列一节「粗颗粒功能」" % len(kws))
    if self_excluded:
        notes.append("已把 S1 定义文件本身排除出调研语料（避免自覆盖）")
    return emit("G0 · S1→S2（需求 → 调研覆盖）", fwd, [], None, notes)


# ---------------------------------------------------------------- G0.9
def g0_9(def_path, state_path):
    """S3 → state.md：**证据停止线必须原样抄进 state.md，否则它拦不住任何阶段。**

    ⚠️⚠️ 此前停止线只写在 `definition-final.md`，**没有任何东西检查它有没有被抄过去**——
    而 S7/S8 的入场条件读的是 `state.md`。
    ⭐⭐ **一条约束如果产出在 A、执行在 B，而没人检查 A→B 的搬运，
    那它的强制力等于零** —— 记录了不等于执行了（铁律 48）。
    """
    dfn, st = read(def_path), read(state_path)
    rows = []
    in_tbl = False
    for ln in dfn.splitlines():
        t = ln.strip()
        if not t.startswith('|'):
            in_tbl = False; continue
        cells = [c.strip() for c in t.strip('|').split('|')]
        if set(''.join(cells)) <= set('-: '): continue
        head = ''.join(cells)
        if '等级' in head and ('结论' in head or '证据' in head):
            in_tbl = True; continue
        if in_tbl and len(cells) >= 2 and cells[0] and not cells[0].startswith('<'):
            rows.append(cells)
    if not rows:
        print("UNABLE: 定义里没有证据等级表 —— 先跑 definition-gate", file=sys.stderr); sys.exit(2)

    low = [r for r in rows if re.search(r'\bE[01]\b', r[1] if len(r) > 1 else '')]
    fwd, rev = [], []
    for r in low:
        key = r[0].strip('`*<> ')
        if key and key not in st:
            fwd.append("E0/E1 结论「%s」的停止线没有抄进 state.md —— **它拦不住任何阶段**" % key[:22])
    # ③ ⭐⭐ 状态一致性：抄过去了 ≠ 它还拦得住。
    #    🔴 2026-09-04 变异实测：把 state.md 里「⛔ E1 停止线**未解除**」原地改成
    #    「✅ E1 停止线**已解除**」，**这道门照样双向通过、退出码 0**。
    #    ⛔ 它查的是 key 有没有被抄过去，而停止线的全部意义在**状态**。
    #    ⭐ 一道门若对「约束仍然成立」与「约束已被撤掉」给出同样的结果，
    #      它对这条约束就是 N/A —— 而它一直在报 PASS。
    #    解除是合法的，但按铁律 48 必须留下**谁、哪天**：没有署名的解除一律判红。
    #    ⚠️ 判据只查**自相矛盾**，不查「有没有署名」：
    #      铁律 48 有**两条**合法解除路径 —— 证据补足（E1→E3）**或**用户拍板。
    #      第一版只认「用户/日期」，把一条靠证据升级解除的合法记录判成了缺陷。
    #      ⭐ 门禁不许惩罚正确实现，而**一条规则的合法路径有几条，判据就得认几条**。
    #      改成查同一行里「已解除」与「前提仍未满足」并存 —— 那是纯粹的自相矛盾，
    #      也正是「把未解除原地改成已解除」留下的指纹（解释文字没跟着改）。
    STILL_UNMET = r'未验证|未豁免|仍未|从未|尚未'
    for m in re.finditer(r'[^\n]*停止线[^\n]*已解除[^\n]*', st):
        ln = m.group(0)
        if re.search(STILL_UNMET, ln):
            rev.append("state.md 同一行既说「停止线已解除」又说前提仍未满足：「%s」 —— "
                       "⛔ 自相矛盾；解除是合法的，但前提没变就不该解除" % ln.strip()[:46])

    # 反向：state.md 的**停止线表**里登记了「未解除」的行，定义里要找得到出处。
    # ⚠️ 2026-09-04：此前判据是「任何含『未解除』的表行」，
    #    于是**阶段进度表**里那行「S7 Figma | ⛔ 不进（停止线 SL-1/SL-2 未解除）」
    #    被当成了一条停止线，报出「『S7 Figma』在定义里找不到出处」。
    #    ⭐ 这是今天第三次撞上同一形态：**行内出现某个词就触发**
    #      （G0 的「」· element-identity 的「标识符」· 本处的「未解除」）。
    #      判据必须锚在**那张表**上：表头要同时像停止线表（含「停止」或「解除了吗」）。
    in_stop_tbl = False
    for i, ln in enumerate(st.splitlines()):
        s_ = ln.strip()
        if not s_.startswith('|'):
            in_stop_tbl = False
            continue
        cells = [x.strip() for x in s_.strip('|').split('|')]
        if set(''.join(cells)) <= set('-: '):
            continue
        head = ''.join(cells)
        if re.search(r'停止在哪|解除了吗', head):
            in_stop_tbl = True
            continue
        if not in_stop_tbl or '未解除' not in s_:
            continue
        k = cells[0].strip('`*<> ') if cells else ''
        if k and k not in dfn and not k.startswith('<'):
            rev.append("state.md 里的未解除停止线「%s」在定义里找不到出处" % k[:22])
    return emit("G0.9 · S3→state（证据停止线的搬运）", fwd, rev)


# ---------------------------------------------------------------- G0.6
def g0_6(ledger_path, def_path):
    """高强度洞察在产品定义里必须有承接或显式拒绝（终局规格 3-4）。

    与 G0.5（机会 OPP）互补：机会有归宿了，**洞察**仍可能沉默消失 ——
    而「研究没被采用不是错误，沉默消失才是错误」此前只是账本模板里的一句话。
    判据按 ID：定义正文出现 `INS-xxx` 即承接（引用/拒绝都算——拒绝也是处置）。
    只查 high 强度：medium 的处置由 G7.5 第④查兜（那里查的是账本自身的处置字段）。"""
    lg, dfn = read(ledger_path), read(def_path)
    highs = []
    # 🚨 2026-09-09：切块前瞻原来只认「下一条 INS」或文件尾（\Z）——
    #   于是**最后一条 INS 的 body 会吞掉它后面的所有小节**（账本模板末尾就有一节）。
    #   实测：最后一条 INS 自己漏写强度时，它会捡后面小节里的「强度：high」，
    #   被判成 high 继而报「沉默消失」——**假阳性，且报的是一条无辜记录**。
    #   ⇒ 前瞻同时认「下一条 INS」与「下一个 ## / ### 小节」，两者取先到的那个。
    for m in re.finditer(r'### (INS-\d+)(.*?)(?=\n#{2,3} |\Z)', lg, re.S):
        st = re.search(r'强度[：:]\s*(high|medium|low|unknown)', m.group(2))
        if st and st.group(1) == 'high':
            highs.append(m.group(1))
    if not highs:
        print("UNABLE: 账本里没有任何 high 强度的 INS —— 没得对账（不是通过）", file=sys.stderr)
        sys.exit(2)
    fwd = [("%s（high）在定义里既无引用也无显式拒绝 —— 沉默消失" % i, '')
           for i in highs if i not in dfn]
    fwd = [x[0] for x in fwd]
    return emit("G0.6 · S2→S3B（高强度洞察的承接）", fwd, [])


# ---------------------------------------------------------------- G0.5
def g0_5(ins_path, def_path):
    ins, dfn = read(ins_path), read(def_path)
    # ⚠️ **按 ID 对账，不按文本相似度。**
    #    首版用「机会文本的前 8 个字是否出现在定义里」做匹配 —— 「让批量失败可逐条撤销」与
    #    定义里的「批量失败可逐条撤销」只差一个「让」字就漏判。
    #    **模糊文本匹配在对账门里是不可接受的**：它既会漏也会误，而且漏的时候悄无声息。
    #    改为 M1 的 ID 贯穿链：机会必须带 `OPP-xx` 编号，定义必须逐个给出归宿。
    # ⚠️ 2026-09-04 全链实跑发现：本判据只认**标题**形态，
    #    而 9 条机会写成一张表是完全自然的写法（也是我实跑时写的）。
    #    ⛔ 更根本的问题：`references/s2-research.md` 有 400+ 行讲怎么产出机会，
    #    **从头到尾没说过要编号** —— 也就是说这道门要求的格式，
    #    产出它的那份文档从来没有写下来过。
    #    ⭐⭐ 这与「契约写对了没人守」不同，是更隐蔽的一种：
    #    **契约从来没被写下来，只被强制执行。** 照着 SOP 认真做的人必然在这里 UNABLE，
    #    而 UNABLE 太容易被当成「跑过了」耸肩带过。
    #    两边都修：这里容忍表格形态，s2-research.md 里补上编号要求。
    opps = re.findall(r'^#{2,4}\s*机会\s*(OPP-\d+)[：: ]?\s*(.{0,40})$', ins, re.M)
    if not opps:
        # 退回：表格形态 —— 某一行的单元格里出现 OPP-xx，取同行下一个非空单元格当描述
        for ln in ins.splitlines():
            ln = ln.strip()
            if not ln.startswith('|'):
                continue
            cells = [c.strip() for c in ln.strip('|').split('|')]
            for i, c in enumerate(cells):
                m2 = re.match(r'^[`*\s]*(OPP-\d+)[`*\s]*$', c)
                if m2:
                    rest = next((x for x in cells[i+1:] if x), '')
                    opps.append((m2.group(1), re.sub(r'[`*]', '', rest)[:40]))
                    break
    if not opps:
        die("insights.md 里解析不到「## 机会 OPP-xx …」——\n"
            "       机会必须带 OPP 编号才能对账（M1 ID 贯穿链）。无编号即无法判断它有没有被处置。")
    fwd = []
    for oid, otext in opps:
        if oid not in dfn:
            fwd.append("机会 %s「%s」在定义里没有出现 —— 采纳/拒绝/推迟都行，**沉默地丢掉不行**"
                       % (oid, otext.strip()[:22]))
    return emit("G0.5 · S2→S3（机会 → 定义）", fwd, [],
                ["⚠️ 机会的合法结局有三种：采纳 / 显式拒绝 / 显式推迟。**沉默地丢掉不是结局。**"]
                if fwd else [])


# ---------------------------------------------------------------- G0.8
def g0_8(def_path, prd_path):
    dfn, prd = read(def_path), read(prd_path)
    fwd, decay = [], []
    for name, dpat, ppat in DEF_ITEMS:
        in_def = re.search(dpat, dfn)
        if not in_def: continue                      # 定义里就没有 → 归 definition-gate 管
        if not re.search(ppat, prd):
            fwd.append("定义有「%s」，PRD 里没有承接位" % name)
            continue
        # ③ 静默降级：定义里带数字的项，PRD 对应位置也应带数字
        dbody = sect(dfn, dpat) or ""
        praw = sect(prd, ppat)
        pbody = praw or ""
        # ⚠️ 「没有这一节」与「有这一节但没数字」是**两种不同的病**，
        #    此前共用一句诊断「变成了没有数字的描述」——
        #    而 PRD 里其实连这一节都不存在（只是正文里提了一嘴，所以上面的
        #    `re.search(ppat, prd)` 通过了）。
        #    ⭐ 一句错误的诊断会让人去找一个不存在的问题；本轮这是第二次。
        if NUM.search(ID_NUM.sub(' ', dbody)):
            if praw is None:
                decay.append("「%s」定义里是量化的，而 PRD 里**只在正文提了一嘴、没有独立小节**"
                             " —— 没有承接位就没人维护它" % name)
            elif not NUM.search(ID_NUM.sub(' ', pbody)):
                decay.append("「%s」在定义里是量化的，到 PRD 变成了没有数字的描述" % name)
        # 约束级别降级
        for lbl, up, down in DOWNGRADE:
            if re.search(up, dbody) and re.search(down, pbody) and not re.search(up, pbody):
                decay.append("「%s」的约束级别被降级（%s）" % (name, lbl))

    # ③b ⭐ 逐项核「首版不做」——按节比词太粗（一节里硬词软词并存是常态），
    #    而这一条是**按项**核的，假阳性低：
    #    定义写「首版不做：A · B · C」，PRD 里每一项都必须仍是**硬边界**
    #    （落在「明确不做」这类表里）。只出现在「非目标 / 不追求」里 = 被降级。
    #    🔴 2026-09-04 实录：definition 同一行三项 ——「多 Agent 编排 · 行业套件 ·
    #    完整移动端能力」，后两项进了 PRD 的「明确不做」表，
    #    **只有「多 Agent 编排」被软化成 5.3 非目标「不追求多 Agent 编排的复杂度」**。
    #    ⛔ 「首版不做 X」是硬边界，「不追求 X 的复杂度」允许做个简版 —— 级别变了，
    #    而两句话各自读起来都通顺，上面按节比词的规则两边的词一个都不认识。
    m = re.search(r'\*{0,2}首版不做\*{0,2}\s*[：:]\s*([^\n]+)', dfn)
    if m:
        hard = sect(prd, r'明确不做') or ''
        soft = sect(prd, r'非目标') or ''
        for item in re.split(r'[·、,，]', re.sub(r'[。\s]*$', '', m.group(1))):
            item = item.strip(' *。')
            if len(item) < 2: continue
            if item in hard: continue                       # 仍是硬边界，OK
            if item in soft or re.search(r'不追求[^\n]{0,12}' + re.escape(item[:6]), prd):
                decay.append("定义写「首版不做：%s」，PRD 里它只出现在非目标/不追求，"
                             "没进「明确不做」表 —— 硬边界被降成软倾向" % item)
    return emit("G0.8 · S3→S4（定义 → PRD）", fwd, [], decay)


# ---------------------------------------------------------------- M8 自证
INS = "# 综合\n## 机会 OPP-01 让批量失败可逐条撤销\n- 解法A\n## 机会 OPP-02 让导入可后台运行\n- 解法B\n"
DEF = """# 定义
## 一句话定位
给重度用户的桌面相册。
## 二、目标用户
### 不服务谁
不服务轻度用户。
## 三、核心价值
一句话。
## 四、明确不做
| a | b |
|---|---|
| 云同步 | 冲突 |
**首版不做**：多端同步 · 云备份。
## 五、功能集合
| ID | 功能 | 载体 | AI? | 成本 |
|---|---|---|---|---|
| F-01 | 批量失败可逐条撤销 | 两端 | 否 | M |
## 六、成功长什么样
检索成功率从 41% 提到 70%，上线后 3 个月。
### 护栏指标
首屏必须不超过 800ms。
## 七、关键路径
打开→检索→导出。
## 八、数据边界
本地存储。
## 九、产品调性
情绪基调 Professional。
## 十、硬约束
不联网。
## 十一、单向门
只做桌面端。
## 十二、失败路径
检索不准导致弃用。
## 机会归宿
OPP-01 采纳（见 F-01）。OPP-02 本轮不做，理由：算力不足。
## 补充 让导入可后台运行 本轮不做，理由：算力不足
"""
PRD = """# PRD
## 一、摘要
定位：给重度用户的桌面相册。
## 三、概要设计
### 功能清单
| ID | 功能 | 载体 | AI? | 成本 |
|---|---|---|---|---|
| F-01 | 批量失败可逐条撤销 | 两端 | 否 | M |
#### 明确不做
| 云同步 | 冲突 |
| 多端同步 | 成本 |
| 云备份 | 成本 |
## 五、目标
检索成功率 41% → 70%，上线后 3 个月。
### 护栏指标
首屏必须不超过 800ms。
## 六、目标用户
不服务轻度用户。核心价值一句话。
### 核心体验路径
打开→检索→导出。
## 附件 C · 数据清单
本地存储。
## 附件 K
情绪基调 Professional。
## 约束与依赖
不联网。
## 单向门
只做桌面端。
## 风险
检索不准导致弃用。
"""


def _run_sweep():
    """S1 方向抽取的构造空间穷举（说明见 _sweep_lib.sweep_s1_directions）。"""
    from _sweep_lib import sweep_s1_directions, report as _rep
    _n, _bad = sweep_s1_directions(s1_directions)
    return _rep('S1 方向抽取', _n, _bad)


def self_test():
    t = tempfile.mkdtemp(prefix="cg-"); me = os.path.abspath(__file__)
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(*a):
        return subprocess.call([sys.executable, me] + list(a),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ins, dfn, prd = w("ins.md", INS), w("def.md", DEF), w("prd.md", PRD)
    ok = True
    def case(n, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-42s 期望 %d 实得 %d" % ("✅" if g else "❌", n, want, got))

    case("G0.5 正例（机会都有归宿）", run('G0.5', ins, dfn), 0)
    case("G0.5 反例（机会被沉默丢掉）",
         run('G0.5', ins, w("d2.md", DEF.replace("OPP-02 本轮不做，理由：算力不足。", ""))), 1)
    LG = "# 账本\n### INS-001\n- 命题：x\n- 强度：high\n### INS-002\n- 命题：y\n- 强度：medium\n"
    lgp = w("ledger.md", LG)
    case("G0.6 正例（high 洞察在定义里有承接）",
         run('G0.6', lgp, w("d6.md", "# 定义\n依据 INS-001 判断桌面优先。\n")), 0)
    case("G0.6 反例（high 洞察沉默消失）",
         run('G0.6', lgp, w("d6b.md", "# 定义\n没提任何洞察。\n")), 1)
    case("G0.6 正例（显式拒绝也算处置）",
         run('G0.6', lgp, w("d6c.md", "# 定义\nINS-001 经评审拒绝：样本偏差。\n")), 0)
    case("G0.6 无 high 洞察 → 报 2（没得对账不是通过）",
         run('G0.6', w("lg2.md", "# 账本\n### INS-003\n- 强度：low\n"), w("d6d.md", "# 定义\n")), 2)
    # 🚨 2026-09-09：切块前瞻原来只认「下一条 INS / 文件尾」⇒ **最后一条 INS 会吞掉
    #   它后面的所有小节**（账本模板末尾本来就有一节）。最后一条自己漏写强度时，
    #   它会捡尾节里的「强度：high」被判成 high ⇒ 报一条无辜记录「沉默消失」。
    _TAIL = "\n## 附：被否决的洞察\n早期判断 AI 分类 强度：high，已复核否决。\n"
    case("G0.6 正例 尾节含「强度：high」不许渗进最后一条 INS",
         run('G0.6', w("lg3.md", "# 账本\n### INS-001\n- 强度：high\n### INS-004\n- 命题：无强度字段\n" + _TAIL),
             w("d6e.md", "# 定义\n依据 INS-001 判断。\n")), 0)
    case("G0.6 反例 最后一条 INS 段内真写 high 且没被承接（修渗透不许把门修哑）",
         run('G0.6', w("lg4.md", "# 账本\n### INS-001\n- 强度：high\n### INS-004\n- 强度：high\n" + _TAIL),
             w("d6f.md", "# 定义\n依据 INS-001 判断。\n")), 1)
    case("G0.8 正例（18 项都有承接）", run('G0.8', dfn, prd), 0)
    case("G0.8 反例（PRD 缺单向门承接位）",
         run('G0.8', dfn, w("p2.md", PRD.replace("## 单向门\n只做桌面端.\n", "").replace("## 单向门\n只做桌面端。\n", ""))), 1)
    case("G0.8 反例（量化被降级成形容词）",
         run('G0.8', dfn, w("p3.md", PRD.replace("检索成功率 41% → 70%，上线后 3 个月。", "检索成功率显著提升。"))), 1)
    case("G0.8 反例（约束级别被降级）",
         run('G0.8', dfn, w("p4.md", PRD.replace("首屏必须不超过 800ms", "首屏建议尽量快"))), 1)
    # 🔴 2026-09-04 补：上面那条按**节**比词，认得「必须→建议」；
    #    而最常见的一种降级是把「首版不做 X」挪进「非目标：不追求 X…」——
    #    两边的词它一个都不认识。这条按**项**核，专治这一种。
    case("G0.8 反例（「首版不做」的项被挪进非目标 = 硬边界降成软倾向）",
         run('G0.8', dfn, w("p5.md", PRD.replace("| 多端同步 | 成本 |\n", "")
                                        .replace("### 护栏指标", "### 非目标\n- 不追求多端同步的完整度\n### 护栏指标"))), 1)
    # ⚠️⚠️ 2026-08-31 自审：首版这条把**临时目录本身**当调研目录传进去，
    #    而 s1.md 就在那个目录里 —— 关键词当然找得到，**正例是自满足的**，
    #    而且 G0 **压根没有反例**。⭐⭐ 一道只有自满足正例、没有反例的门，
    #    等于没被测过：它永远绿，不管代码是对是错。
    rdir_ok = os.path.join(t, "rdir_ok"); os.makedirs(rdir_ok, exist_ok=True)
    io.open(os.path.join(rdir_ok, "r1.md"), "w", encoding="utf-8").write(
        "竞品都做了批量撤销；后台导入是标配。")
    rdir_bad = os.path.join(t, "rdir_bad"); os.makedirs(rdir_bad, exist_ok=True)
    io.open(os.path.join(rdir_bad, "r1.md"), "w", encoding="utf-8").write(
        "竞品都做了批量撤销。")          # 缺「后台导入」
    s1p = w("s1.md", "我们要做「批量撤销」和「后台导入」。")
    case("G0 正例（S1 点名的都被调研覆盖）", run('G0', s1p, rdir_ok), 0)
    case("G0 反例（S1 点名的没进调研）", run('G0', s1p, rdir_bad), 1)
    case("G0 无「」关键词 → 只能人工核（不许当通过）",
         run('G0', w("s1b.md", "我们要做批量撤销。"), rdir_ok), 1)
    # ⭐ 2026-09-04 实跑一份真 S1 时，G0 把两处**强调引号**当成了「点名的方向」报漏。
    #    中文里「」既命名也强调 → **S1 写得越清楚，假漏越多**；
    #    而这个约定全仓零处文档，SKILL.md 自己用了 296 次「」。
    #    修法不是放宽匹配，而是让方向清单成为**明确的产出位**。
    S1_SEC = ("## 粗颗粒功能\n\n1. **批量撤销**：说明里出现「一道门从来没跑过」这种强调\n"
              "2. **后台导入**：以及「另一处强调」\n\n"
              "## 边界\n不做「历史趋势」。\n")
    case("G0 有「粗颗粒功能」小节时，只对账该节的方向（强调引号不算）",
         run('G0', w("s1c.md", S1_SEC), rdir_ok), 0)
    # 🚨 反例必须真的制造出那个缺口：把小节里的一项换成调研没覆盖的词，必须红。
    case("G0 该节里的方向没进调研 → 必须红",
         run('G0', w("s1d.md", S1_SEC.replace('后台导入', '离线归档')), rdir_ok), 1)
    # 🚨 反向测试②：若判据退回扫全文「」，上面那条正例会被强调引号判红 —— 用它证明分流真的生效。
    case("G0 反向：同样内容但没有小节标题 → 强调引号会把它判红（证明小节模式确实在起作用）",
         run('G0', w("s1e.md", S1_SEC.replace('## 粗颗粒功能', '## 功能想法')), rdir_ok), 1)
    # ⭐ emit 此前只有「衰减」一个通道 → 纯说明也会让门退出 1。
    #    自覆盖说明是最常触发的一条：S1 文件就在调研目录里时必然出现。
    rdir_self = os.path.join(t, "rdir_self"); os.makedirs(rdir_self, exist_ok=True)
    io.open(os.path.join(rdir_self, "r1.md"), "w", encoding="utf-8").write(
        "竞品都做了批量撤销；后台导入是标配。")
    s1_inside = os.path.join(rdir_self, "s1.md")
    io.open(s1_inside, "w", encoding="utf-8").write("我们要做「批量撤销」和「后台导入」。")
    case("S1 就在调研目录里：排除自覆盖的**说明**不许让这道门变红（此前会）",
         run('G0', s1_inside, rdir_self), 0)
    # ⭐ G0.9：停止线的搬运——**产出在 A、执行在 B，没人检查搬运 = 强制力为零**
    DEF_EV = ("## 证据等级\n| 结论 | 等级 | 证据 | 相关性 | 怎么补 | 停止线 |\n|---|---|---|---|---|---|\n"
              "| 用户为检索头疼 | E2 | 访谈 | 直接 | — | — |\n"
              "| 愿意换工具 | E0 | 推演 | 直接 | 假门 | 只做到 S6 |\n")
    ST_OK = "# 状态\n| 结论 | 等级 | 停止在哪 | 怎么补 | 解除了吗 |\n|---|---|---|---|---|\n" \
            "| 愿意换工具 | E0 | 只做到 S6 | 假门 | ☐ 未解除 |\n"
    case("G0.9 正例（停止线已抄进 state）",
         run('G0.9', w("d9.md", DEF_EV), w("s9.md", ST_OK)), 0)
    case("G0.9 反例（E0 停止线没抄过去）",
         run('G0.9', w("d9b.md", DEF_EV), w("s9b.md", "# 状态\n没有停止线表\n")), 1)
    case("G0.9 反向（state 有未解除但定义里没出处）",
         run('G0.9', w("d9c.md", DEF_EV),
             w("s9c.md", ST_OK + "| 凭空冒出来的结论 | E0 | 只做到 S6 | — | ☐ 未解除 |\n")), 1)
    # ⭐ 2026-09-04：反向判据此前是「任何含『未解除』的表行」，
    #    于是**阶段进度表**里那行「S7 Figma | ⛔ 不进（停止线 SL-1/SL-2 未解除）」
    #    被当成一条停止线，报出「『S7 Figma』在定义里找不到出处」。
    #    ⛔ 今天第三次撞上「行内出现某个词就触发」（G0 的「」· 元素表的「标识符」· 本处）。
    case("G0.9 正例：别的表里提到「未解除」不算停止线（阶段进度表就会这么写）",
         run('G0.9', w("d9d.md", DEF_EV),
             w("s9d.md", ST_OK +
               "\n## 阶段进度\n| 阶段 | 状态 |\n|---|---|\n"
               "| S7 Figma | ⛔ 不进（停止线未解除） |\n")), 0)
    # 🔴 2026-09-04 变异实测：把「停止线未解除」原地改成「已解除」而解释文字没跟着改，
    #    这道门**照样双向通过、退出码 0** —— 它查的是 key 有没有被抄过去，
    #    ⭐ 而停止线的全部意义在**状态**。一道门若对「约束仍成立」与「约束已被撤掉」
    #      给出同样结果，它对这条约束就是 N/A，而它一直在报 PASS。
    case("G0.9 反例（停止线被翻成已解除，而前提仍未满足）",
         run('G0.9', w("d9e.md", DEF_EV),
             w("s9e.md", ST_OK + "\n⛔ 「愿意换工具」的停止线已解除：该前提**从未**被真实用户验证。\n")), 1)
    # ⚠️ 正例这一条守的是「不许惩罚正确实现」：铁律 48 有**两条**合法解除路径
    #    （证据补足 / 用户拍板），第一版判据只认「用户+日期」，
    #    把一条靠 E1→E3 证据升级解除的**真实合法记录**判成了缺陷。
    case("G0.9 正例反向（靠证据升级合法解除，不许判红）",
         run('G0.9', w("d9f.md", DEF_EV),
             w("s9f.md", ST_OK + "\n🟢 「愿意换工具」的停止线已解除：证据 E0 → E3，假门落地页实测转化 12%。\n")), 0)
    case("G0.9 无证据表 → 报 2", run('G0.9', w("d9d.md", "# 定义\n没有表\n"), w("s9d.md", ST_OK)), 2)
    case("输入不存在 → 报 2 不报 0", run('G0.8', os.path.join(t, "nope.md"), prd), 2)
    case("insights 无机会 → 报 2", run('G0.5', w("empty.md", "# 空\n"), dfn), 2)
    print("\n%s" % ("✅ 前三道链路门都会出声" if ok else "❌ 自证失败"))

    # 🆕 2026-09-05 `unexecuted-check --unable` 实测：本门 7 个「跑不了」出口
    #    有 2 个从没被触发过 —— 都是「目录里读不到语料」这一类。
    #    ⭐ 这类守卫锚点写错时会**两头都不出声**：既不报「没跑过」也不报缺陷。
    _empty = os.path.join(t, 'emptydir'); os.makedirs(_empty, exist_ok=True)
    # ⛔ 参数顺序是 g0(s1_path, research_dir) —— 定义在前、调研目录在后。
    #    第一版我传反了，于是把目录当成 S1 文件、把文件当成调研目录，测的不是那条出口。
    case("G0 传的调研目录里一个 md 都没有 → 报 2", run('G0', dfn, _empty), 2)
    # ⛔ 「S1 定义文件」是按 **realpath 相等**认的，不是按文件名 ——
    #    所以那份定义必须**就是**传给 G0 的那一个、且位于调研目录内。
    #    第一版我在目录里另写了一个同名文件，realpath 不同 ⇒ 它被当成语料 ⇒ 返回 1 不是 2。
    _only = os.path.join(t, 'onlydef'); os.makedirs(_only, exist_ok=True)
    _dfn_in = os.path.join(_only, 'definition-final.md')
    io.open(_dfn_in, 'w', encoding='utf-8').write(DEF)
    case("G0 调研目录里只有 S1 定义文件本身 → 报 2", run('G0', _dfn_in, _only), 2)
    # L70 在**另一个函数**里（读单个路径的 read），不是 read_corpus ——
    # 要触发它得让**第一个参数**（S1 位置）是个空目录。
    # ⭐ 「目录里没有 md」在两处各有一份实现，用例必须分别打到各自那一份。
    case("G0 的 S1 位置是个空目录 → 报 2", run('G0', _empty, _only), 2)

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
    def _entry():
            if '--self-test' in sys.argv: sys.exit(self_test())
            # ⚠️ 未知参数必须报错，⛔ 不许静默丢弃。
            #    2026-09-03 实测：同一个 skill 的 element-identity-gate 因为这一行
            #    `[x for x in argv if not x.startswith('--')]`，把误写的 `--spec/--demo`
            #    当成「以 -- 开头」滤掉，于是半个门禁从没跑过而一路报绿。
            #    本门禁的位置参数恰好和常见误写的取值顺序一致 —— **那是碰巧对了，不是没有风险**：
            #    顺序一换（`--demo X --prd Y`）就会把 demo 当 PRD 解析。
            KNOWN = {'--help', '--json', '--self-test', '--list-rules'}
            # 提示语里写「用法见 --help」就必须真有这个出口 ——
            # 2026-09-05 实测:三道门都在提示 --help,而三道门都不接受 --help。
            if '--help' in sys.argv:
                print((__doc__ or '').strip() or '本门禁用位置参数,见文件头注释'); sys.exit(0)
            unknown = [x for x in sys.argv[1:] if x.startswith('--') and x not in KNOWN]
            if unknown:
                print("UNABLE: 不认识的参数 %s；本门禁用**位置参数**，用法见 --help"
                      % ' '.join(unknown), file=sys.stderr)
                sys.exit(2)
            a = [x for x in sys.argv[1:] if not x.startswith('--')]
            if len(a) == 3:
                g = a[0].upper().replace('G0.5', 'G0.5').replace('G0.8', 'G0.8')
                if g == 'G0': sys.exit(g0(a[1], a[2]))
                if a[0] == 'G0.5': sys.exit(g0_5(a[1], a[2]))
                if a[0] == 'G0.6': sys.exit(g0_6(a[1], a[2]))
                if a[0] == 'G0.8': sys.exit(g0_8(a[1], a[2]))
                if a[0] == 'G0.9': sys.exit(g0_9(a[1], a[2]))
            print(__doc__); sys.exit(2)
    _main_guarded(_entry)
