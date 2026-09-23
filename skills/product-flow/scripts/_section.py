#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按**结构边界**取一节正文 —— 门禁定位段落的唯一正本。

🚨 2026-09-09 第五轮独立复核（三个代理各自独立报到同一处）立此模块。
   起因是全仓 9 处活实例都在用 `md.find('某个词')` 定位段落，两个方向都出事：

   · **静默关掉一条判据**（漏报）。product-structure 判据④ 写
     `i = md.find('状态与异常结构')`，于是正文里提前出现一句无辜人话——
       > 本文的状态与异常结构一节见文末。
     ——判据④ 从那一句开始往后切，**四个真违例全部落在切点之前，整条判据静默失效**，
     门打印「✅ S4A 五判据全过」rc=0。触发它不需要恶意构造，写篇导读就够了。

   · **点名无辜者**（误伤，更贵）。business-map / product-structure 的 ①②③
     都取「全文首次出现」，于是一份**完全合规**的文档只要加一行目录，
     就同时报「没有任何 F-xx」「没有任何任务条目」「权限矩阵没有一行内容」——
     而这三样东西全都在。⭐ 作者拿到三条明显错误的报错，最可能的反应是
     「这门坏了」然后**整体不再信它** —— 本仓纪律：错误诊断比漏报贵。

⭐ 为什么这是 `no-positional-window` 的同一个形状，而那条元规则却报全绿：
   它禁的是 `md[i:i+1200]` 与 `find('## ')`，**没禁 `find('<字面量>')`** ——
   而三者失效模式完全一样（按文本位置切分，正文一句话即错位）。
   规则的**量程**漏掉了正在造成假绿的那一族。本模块落地后，该元规则同步扩量程。

⇒ 本模块只提供一种定位方式：**锚定结构边界**。
   ① 标题行（`^#{1,6}\\s*…kw…$`）—— 切到**同级或更高级**标题为止（子节算本节的）。
   ② 表头行（某张表的表头单元格命中 kw）—— 切到该表结束（空行/非表格行/列数变化）。
   ⛔ 正文中间提到 kw 一律**不算定位**：那是引用，不是这一节。
"""
import re

# 🚨 2026-09-10 codex 评审 #9：上一版 `^(#{1,6})[ \t]*(.*)$` 与 CommonMark 有三处出入：
#   ①**最多 3 个前导空格**仍是合法 ATX 标题（`   ## 目标节`）—— 上一版返回 None；
#   ②`##前缀目标节`（`#` 后**没有空格**）**不是**标题 —— 上一版当成了标题；
#   ⇒ 允许 0–3 空格缩进，且要求 `#` 后有空白或行尾。
#   ⛔ 诚实边界：本模块**不是** CommonMark 实现，只覆盖 SOP 产物里实际出现的形态；
#     真要完备得引解析器，那是另一个决定（见 references 的量程声明）。
_HEAD = re.compile(r'^ {0,3}(#{1,6})(?:[ \t]+(.*))?$')
# setext 风格标题：正文行 + 下一行全是 = 或 -（合法 Markdown，渲染出来一模一样）
# ⚠️ 2026-09-10：下划线允许 **0–3 个前导空格**（CommonMark）——首版不许，
#   于是 `   ====` 这种完全合法的写法取不到节。**是构造空间穷举扫出来的**，
#   不是想出来的：我列不出这个用例，但穷举「前导空格 0..5」必然覆盖它。
_SETEXT = re.compile(r'^ {0,3}(=+|-+)\s*$')


def _blank_fenced(md):
    """把 fenced code 块内的行**换成空行**（行数不变，行号不动）。

    🚨🚨 2026-09-10 第六轮独立复核（E1/F1）：`_iter_headings` **逐行匹配、不跳围栏** ⇒
      节内任何一段带 `#` 注释的代码块都会被当成一级标题，`section_at` 在那里截断。
      两个方向同一天在**同一份产物**上复现：
        · 漏：状态节里放一段 ```python\n# 状态流转``` ⇒ 后面的 Skeleton 违例整条逃检，
          门报「✅ 五判据全过」rc=0；而**旧版（字面量定位）抓得到** —— 这是本模块引入的回归。
        · 误伤：任务流中间隔一段 shell 示例 ⇒ 出路行被切走，报「任务没有出路」rc=1；
          旧版 rc=0。
      ⭐ 这正是本模块 docstring 开头列为「立此模块理由」的那个双向失效，**原样复现**，
        只是触发器从「正文提一句节名」换成了「正文里有段代码」。
      ⭐⭐ 教训：**「结构锚定」比「字面量定位」强，但前提是「结构」的定义得完整。**
        漏掉围栏与 setext，等于换了个触发器。
    """
    out, fence = [], None
    for line in md.split('\n'):
        st = line.strip()
        # ⚠️ codex #9：③**4 空格缩进的 ``` 在 Markdown 里是代码不是围栏**；
        #   ④三反引号**关不掉**四反引号开的围栏（关闭符必须 ≥ 开启符长度）。
        #   上一版两条都错，于是「假围栏」会把真标题吞掉、真围栏会被提前关闭。
        _indent = len(line) - len(line.lstrip(' '))
        if fence is None:
            m = re.match(r'^(`{3,}|~{3,})', st) if _indent <= 3 else None
            if m:
                fence = m.group(1)
                out.append('')
                continue
            out.append(line)
        else:
            out.append('')
            _c = re.match(r'^(`{3,}|~{3,})\s*$', st)
            if _c and _c.group(1)[0] == fence[0] and len(_c.group(1)) >= len(fence):
                fence = None
    return '\n'.join(out)


_BQ = re.compile(r'^ {0,3}(?:> ?)+')


def _strip_frontmatter(lines):
    """YAML frontmatter 整块置空（保留行数，行号口径不变）。

    🚨 2026-09-11 差分测试抓到：`SKILL.md` 开头的 `---\nname: …\ndescription: …\n---`
      被当成一个**正文长达一整段 description 的二级 setext 标题** ——
      随后 `section_at` 在里面搜任何关键词都可能命中，而那不是任何一节。
    ⚠️ **这一处两边都错**：CommonMark 不认识 frontmatter，裁判也把它当 setext。
      ⇒ 这是本模块**有意与裁判分歧**的地方（见 `_section_oracle.KNOWN_DIVERGENCE`），
        ⛔ 不是照抄裁判，是按本仓语义判：frontmatter 是元数据，不是内容。
    """
    if not lines or lines[0].strip() != '---':
        return lines
    for i in range(1, min(len(lines), 200)):
        if lines[i].strip() in ('---', '...'):
            return [''] * (i + 1) + lines[i + 1:]
    return lines


def _iter_headings(md):
    """产出 (行号, 级别, 标题文本)。围栏内不算，setext 也认，引用块里的也认。"""
    lines = _strip_frontmatter(_blank_fenced(md).split('\n'))
    for ln, raw in enumerate(lines):
        # 🚨 2026-09-11 差分测试（markdown-it-py 当裁判，77 份真实文档）抓到两处漏识：
        #   `> ## ⭐ 结果落盘：…`（design-quality-gates.md:366）与 s3-definition.md:5 ——
        #   **引用块里的 ATX 标题**。正则要求行首 0-3 空格接 `#`，`> ` 前缀直接不匹配，
        #   于是门禁找不到那一节，而人在渲染后看到的分明是个标题。
        #   ⚠️ 收紧前先量了影响：全仓**只有这 2 处**，都是真章节，不是「引用别人的标题」。
        #     ⛔ 若将来出现「文档里引用他人标题作示例」，这里会误命中 —— 那时再按语境收窄，
        #       不要现在就为假想场景加开关（本仓禁投机性代码）。
        line = _BQ.sub('', raw) if _BQ.match(raw) else raw
        m = _HEAD.match(line)
        if m:
            # 🚨 2026-09-10 codex 二轮 #7：合法的**空 ATX 标题**（`##`）让 group(2) 为 None，
            #   随后 `re.search(pat, None)` 抛 **TypeError** —— 全部 6 个消费方**直接崩**。
            #   ⭐ 这是本轮为支持「# 后为空」引入的**直接回归**：我加了一条分支，
            #     却没想过那条分支下捕获组是 None。
            yield ln, len(m.group(1)), (m.group(2) or '')
            continue
        # setext：本行是非空正文，下一行全是 = 或 -
        # 🚨🚨 2026-09-11 **差分测试**（拿 markdown-it-py 当裁判，跑仓里 77 份真实文档）抓到：
        #   `---` 紧跟 `---`（两条连续分隔线，templates/research-report.md:9、prd-complete.md:600）
        #   被判成「内容 `---` + 下划线 `---`」的二级标题。
        #   ⭐ CommonMark 规定 setext 下划线**上面必须是段落**，而 `---` 本身是主题分隔线，
        #     不是段落 —— 分隔线不能当内容行。
        #   ⚠️ 这条**我那 138 例构造空间穷举一条都没抓到**：穷举只覆盖我想得到的轴，
        #     而「分隔线恰好挨着分隔线」不在我列的轴里。本仓记的
        #     「对照组必须来自流程外」——真解析器不共享我的盲区，这就是它的价值。
        nxt = lines[ln + 1] if ln + 1 < len(lines) else ''
        nxt = _BQ.sub('', nxt) if _BQ.match(nxt) else nxt
        if (line.strip() and ln + 1 < len(lines) and _SETEXT.match(nxt)
                and not line.lstrip().startswith('|')      # 表格分隔行不是标题
                and not _SETEXT.match(line)                # ⛔ 分隔线不能当内容行
                and not _HEAD.match(line)):
            yield ln, (1 if nxt.strip()[0] == '=' else 2), line.strip()


def section_at(md, kw, regex=False):
    """取「标题里含 kw」的那一节正文；找不到返回 None。

    ⚠️ 返回 None 与「返回空字符串」必须由调用方区分对待：
      None = **没有这一节**（该报缺失），'' = 有这一节但**是空的**（该报没填）。
      合并成一个值就会把「缺失」和「空」报成同一句话，诊断又错一次。
    """
    lines = md.split('\n')
    pat = kw if regex else re.escape(kw)
    heads = list(_iter_headings(md))
    hits = [(ln, lvl) for ln, lvl, text in heads if re.search(pat, text)]
    if not hits:
        return None
    # 🚨 2026-09-10 第六轮（E3）：原来取**首个**命中就 break ⇒ 一个
    #   「## 6. 状态与异常结构（概要）\n本节详表见 §9。」的桩节，
    #   就能把后面那个装着真表（和违例）的同名节整个遮住，门报「五判据全过」。
    #   ⇒ 同名节**全部取上并拼接**。⭐ 这个方向在两头都安全：
    #     查违例时看得更全（不会漏），查「填了没有」时内容更多（不会误报缺失）。
    segs, spans = [], []
    for ln, lvl in hits:
        end = len(lines)
        for ln2, lvl2, _ in heads:
            if ln2 > ln and lvl2 <= lvl:
                end = ln2
                break
        # 🚨 2026-09-10 codex 评审 #10 后半：同名节**全取**时，
        #   若一个命中节是另一个命中节的**子节**，父节正文里已经含了它，
        #   再追加一次就是**重复计数** —— 实测 6 个决策域被数成 13 个数据行
        #   （含重复表头），刚好越过 `len(data) >= 12` 的门槛。
        #   ⭐ 「全取」这个方向是对的，但必须去掉嵌套包含，否则修漏报换来假绿。
        if any(a <= ln < b for a, b in spans):
            continue
        spans.append((ln, end))
        segs.append('\n'.join(lines[ln + 1:end]))
    return '\n'.join(segs)


def table_rows_at(md, kw, regex=False):
    """取「表头单元格含 kw」的那张表的数据行；找不到返回 None。

    ⚠️ 表的**结束**也必须锚定结构，不能一路切到 EOF ——
      复核实证：切到 EOF 时，文末一张无关的竞品表会被算进本表的行数，
      「3 个真实域 + 一张 10 行的表」被报成「14 域全部齐备」。
    ⇒ 空行 / 非表格行 / 列数变化，三者任一即视为本表结束。
    """
    # 🚨 2026-09-10 codex 二轮 #8：`_blank_fenced()` 只用在**标题遍历**上，
    #   表格路径完全没用它 ⇒ 围栏里的**示例表**能抢在真表之前被取到。
    #   ⭐ 「围栏内不算结构」这条修复**只修了一半** —— 标题修了，表没修。
    lines = _blank_fenced(md).split('\n')
    for i, line in enumerate(lines):
        st = line.strip()
        if not st.startswith('|'):
            continue
        # ⚠️ codex #9：GFM 里 `\|` 是**转义管道**（单元格内容），不是分隔符。
        #   上一版按裸 `|` 切 ⇒ `| A\|B | 可读 |` 被切成三格，
        #   于是**含转义管道的正确产物**被判成列数不符。⇒ 先保护转义再切。
        def _cells(_row):
            return [c.replace('\x00', '|').strip()
                    for c in _row.replace('\\|', '\x00').strip('|').split('|')]
        heads = _cells(st)
        pat = kw if regex else re.escape(kw)
        if not any(re.search(pat, h) for h in heads):
            continue
        # 🚨 2026-09-10 第六轮（F7）：`set('') <= set('-: |')` 是 **True** ——
        #   **空行被判成分隔行**，于是一个后面跟空行的诱饵表头会劫持整个函数
        #   （`return` 在循环内），真表的表头行与分隔行被当成数据行计入。
        #   ⇒ 分隔行必须非空**且至少含一个 `-`**。
        _sep = lines[i + 1].strip().strip('|') if i + 1 < len(lines) else ''
        if not _sep or '-' not in _sep or not set(_sep) <= set('-: |'):
            continue                      # 下一行不是分隔行 ⇒ 这不是表头
        ncol, out = len(heads), []
        for l2 in lines[i + 2:]:
            s2 = l2.strip()
            if not s2 or not s2.startswith('|'):
                break                     # 空行/非表格行＝本表结束
            cells = _cells(s2)
            if len(cells) != ncol:
                break                     # 列数变了＝换了一张表
            out.append(cells)
        return out
    return None


def approved_role(md, role, decisions):
    """Exact decision cell in a single role row; prose mentions are not approvals.

    This validates a record's structure, not the signer's identity or authority.
    """
    rows = table_rows_at(md or '', '角色') or []
    hits = [r for r in rows if r and r[0].strip('`* ').split('/')[0] == role]
    return (len(hits) == 1 and len(hits[0]) >= 8
            and hits[0][1].strip('`* ') in decisions
            and hits[0][-5].strip() in {'human', 'agent'}
            and all(c.strip().lower() not in {'', '-', '—', 'n/a', 'none'}
                    and not re.search(r'<[^>]+>|待填写|待补充|\b(?:TBD|TODO)\b', c, re.I)
                    for c in hits[0]))


def section_or_table(md, kw, regex=False):
    """先按标题取节，取不到再退回「表头命中」的那张表（转成文本）。

    ⛔ 两条路都锚定结构；**没有第三条按字面量位置切的退路** ——
      留一条那样的退路，等于这个模块白写。
    """
    sec = section_at(md, kw, regex)
    if sec is not None:
        return sec
    rows = table_rows_at(md, kw, regex)
    if rows is None:
        return None
    return '\n'.join(' | '.join(r) for r in rows)


def from_line_containing(md, kw, regex=False):
    """从「含 kw 的那一行」起，取到下一个标题为止；找不到返回 None。

    ⚠️ 用于 kw 是**字段名**而不是节标题的场合（retro-gate 的「新观察期」就是
      表格里的一个字段，没有对应标题，`section_at` 取不到）。
    ⭐ 它仍然锚定结构（**行边界 + 下一个标题**），而不是按字符偏移切 ——
      与 `md.split('新观察期', 1)[1]` 的区别是：后者从**词的中间**切开，
      前者从**行首**切；正文里同一行的前半段不会被丢掉，段落终点也不靠数字。
    """
    lines = md.split('\n')
    pat = kw if regex else re.escape(kw)
    # 🚨 2026-09-10 codex 评审 #11：上一版取「全文第一条含该词的行」——
    #   仍然是「首次提及即劫持」，只是把「词中间切」换成了「行首切」。
    #   实测：前言写「新观察期见下。」，真正的字段在后面的
    #   `**新观察期**：30 天；转停止条件：…` 里 ⇒ 取到的是前言那一句，
    #   真正的停止条件被切走并**误报**。⭐ 又一次「修复只换了触发器」。
    # ⇒ 优先取**像字段定义**的那一行（词后紧跟冒号，或落在表格单元格里）；
    #   都没有才退回首次出现。⛔ 这仍是启发式，量程写在下面。
    # 🚨 2026-09-10 codex 二轮 #10：上一版的「像字段」判据太松 ——
    #   `关于新观察期的说明：见下。` 里冒号也在 6 字内，于是**说明句照样劫持**。
    #   ⭐ 我把「首次提及」换成了「首次**看起来像字段**的提及」，触发器又只挪了一格。
    #   ⇒ 收紧成真正的字段形态：kw 必须在**行首**（可带 `-`/`*`/加粗记号）
    #     或落在表格单元格里，且其后紧跟冒号。⛔ 句中提及一律不算。
    #   ⚠️ 并且候选行要排除**围栏内**的行（上一版这里没走 `_blank_fenced`）。
    _field = re.compile(r'^[\s\-*>]{0,4}(?:\*\*)?' + pat + r'(?:\*\*)?\s{0,2}[：:]'
                        r'|\|[^|\n]*' + pat + r'[^|\n]*\|')
    _vis = _blank_fenced(md).split('\n')
    _cands = [i for i, l in enumerate(lines)
              if re.search(pat, l) and i < len(_vis) and _vis[i].strip()]
    if not _cands:
        return None
    i = next((k for k in _cands if _field.search(lines[k])), _cands[0])
    # 终点也走 `_iter_headings`（围栏内标题不算、setext 也认）——
    #   上一版直接用 `_HEAD`，最近两项修复没覆盖到这里（codex #11 后半）。
    _hl = [ln for ln, _lvl, _t in _iter_headings(md) if ln > i]
    end = _hl[0] if _hl else len(lines)
    return '\n'.join(lines[i:end])


def before_section(md, kw, regex=False):
    """返回「第一个匹配标题**之前**」的正文；没有该标题时返回全文。

    🚨 2026-09-10 codex 评审 #10：调用方原本写 `md[:md.index(section_at(md, kw))]` ——
      它假设 `section_at` 的返回值是 md 的**连续子串**。而「同名节全取并拼接」那次修复
      **改变了这个契约**（返回的是多段拼接，可能根本不是子串），
      于是两个非嵌套同名节会让调用方抛 `ValueError: substring not found` —— **直接崩**。
    ⭐ 教训：**改返回值契约必须同步所有消费方**；只改正本不核消费方，
      读哪一个都合法（本仓「一处正本 N 处照做入口」的第 N 次实证）。
    ⇒ 这个函数把「取该节之前的文本」变成模块提供的能力，调用方不再自己切。
    """
    lines = md.split('\n')
    pat = kw if regex else re.escape(kw)
    for ln, _lvl, text in _iter_headings(md):
        if re.search(pat, text):
            return '\n'.join(lines[:ln])
    return md


def _sweep():
    """按**构造维度穷举**，而不是列举「我想到的用例」。

    🚨🚨 2026-09-10 立。两轮专家评审的共同收口是：
      > 修复把一个已知失效模式换了个触发器，
      > **而验证用例只覆盖了作者想到的那个触发器。**
      本模块被点名 4 次（空 ATX 标题崩溃 / 围栏内的表劫持 / 四空格缩进 / setext），
      每一次我都补一条「那个形状」的用例，然后下一轮再被找到下一个形状。

    ⭐ 这个函数是对那句话的**结构性回答**：不再列举用例，而是**列举轴**，
      让轴的笛卡尔积去覆盖我想不到的组合：
        · ATX ：前导空格 0–5 × `#` 数 1/3/6/7 × `#` 后（空格/制表/紧贴/行尾）
        · 围栏：字符 ` 与 ~ × 开启长度 3/4 × 缩进 0/3/4 × 闭合长度 3/4
        · setext：下划线 = 与 - × 前导空格 0/3/4 × 前一行（正文/表格行/空行）
      期望值由**显式写出的规则**推出，不是我记忆里的答案。

    ⚠️ 它当场扫出一条我列不出来的真缺陷：setext 下划线允许 0–3 空格缩进，
      而首版正则不许 ⇒ `   ====` 这种完全合法的写法取不到节。
    ⚠️ 它也当场纠正了我一个**写错的期望**：缩进 4 的 ``` 不是围栏，
      那么其后未缩进的那行 ``` 反而开了个新围栏 —— 代码是对的，我的期望是错的。
      ⭐ 「期望值写错会让正确行为看起来像缺陷」，这条在本仓已经犯过两次。

    ⛔ 诚实边界：轴是我选的，**轴之外的构造仍然覆盖不到**（列表内的标题、
      HTML 块、链接引用定义…）。穷举把「想得到的用例」换成了「想得到的轴」，
      是一层进步，**不是完备性证明**。
    """
    bad, n = [], 0

    def heads(md):
        return [t for _, _, t in _iter_headings(md)]

    for sp in range(0, 6):
        for k in (1, 3, 6, 7):
            for after in (' 标题', '\t标题', '标题', ''):
                n += 1
                md = ' ' * sp + '#' * k + after + '\n正文\n'
                want = (sp <= 3 and 1 <= k <= 6 and (after == '' or after[0] in ' \t'))
                if bool(heads(md)) != want:
                    bad.append('ATX 缩进%d #%d 后=%r' % (sp, k, after))
    for ch in ('`', '~'):
        for openn in (3, 4):
            for ind in (0, 3, 4):
                for closen in (3, 4):
                    n += 1
                    md = (' ' * ind + ch * openn + '\n# 围栏内\n'
                          + ch * closen + '\n\n# 真标题\n正文\n')
                    if ind <= 3:
                        want = ['真标题'] if closen >= openn else []
                    else:
                        want = ['围栏内']     # 不是围栏；其后未缩进的那行才开围栏
                    if heads(md) != want:
                        bad.append('围栏 %s 开%d 缩进%d 闭%d' % (ch, openn, ind, closen))
    for u in ('=', '-'):
        for sp in (0, 3, 4):
            for prev in ('标题文本', '| 表 | 行 |', ''):
                n += 1
                md = prev + '\n' + ' ' * sp + u * 4 + '\n\n正文\n'
                want = bool(prev) and not prev.startswith('|') and sp <= 3
                if bool(heads(md)) != want:
                    bad.append('setext %s 缩进%d 前行=%r' % (u, sp, prev[:6]))
    return n, bad


def _self_test():
    """本模块此前**一条自证都没有** —— 而**9 个脚本**依赖它（写下这句时是 6 个 —— ⭐ 硬编码的计数会安静过期，
      这一条本身就是实例；下次改用 `grep -l 'from _section import' scripts/*.py` 现数）。

    ⭐ 它是 `_` 前缀的辅助模块，于是长期落在「谁需要自证」的量程之外；
      而它恰恰是全仓最承重的一处解析器。⛔ 承重不看文件名前缀。
    """
    ok = True

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print('  %s %s' % ('✅' if cond else '❌', name))

    n, bad = _sweep()
    # ⚠️ 这行原来不带名字，汇总十处穷举时打印成「✅ 构造空间穷举 138 例」——
    #   证据不署名就对不上账。
    chk('节定位 构造空间穷举 %d 例全部符合显式规则' % n, not bad)
    for b in bad[:6]:
        print('     · %s' % b)
    chk('空 ATX 标题 `##` 不崩（group(2) 为 None）',
        section_at('##\n\n## 目标节\n正文\n', '目标节') is not None)
    chk('围栏内的**表**不劫持真表（修复不许只修一半）',
        table_rows_at('```\n| 目标表 | 值 |\n|---|---|\n| 假 | 假 |\n```\n\n'
                      '| 目标表 | 值 |\n|---|---|\n| 真 | 真 |\n', '目标表')
        == [['真', '真']])
    chk('GFM 转义管道不切格（含 `\\|` 的正确产物不许判列数不符）',
        table_rows_at('| 域 | 说明 |\n|---|---|\n| A\\|B | 可读 |\n', '域')
        == [['A|B', '可读']])
    chk('嵌套同名节不重复计数（父节已含子节）',
        len([l for l in (section_at(
            '## 清单\n### 清单（明细）\n| 域 | 状态 |\n|---|---|\n| 域1 | 有 |\n',
            '清单') or '').split('\n') if l.strip().startswith('|')]) == 3)
    chk('None 与空字符串分得开（缺失 vs 空节）',
        section_at('# A\n正文\n', '不存在') is None
        and section_at('## 空节\n\n## 下一节\n', '空节') is not None)
    chk('from_line_containing 取字段行而非说明句',
        '转停止条件' in (from_line_containing(
            '关于新观察期的说明：见下。\n## 正文\n**新观察期**：30 天；转停止条件：X\n',
            '新观察期') or ''))
    print('\n' + ('✅ 自证通过：段落定位正本可信' if ok else '❌ 自证失败：先修正本'))
    return 0 if ok else 1


if __name__ == '__main__':
    import sys
    if '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    print(__doc__.strip())
