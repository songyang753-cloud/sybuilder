#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构造空间穷举的公共骨架 —— 多处判据共用一份。

🚨 2026-09-10 立。两轮 codex 评审 + 六轮独立复核的共同收口：
   > 修复把一个已知失效模式换了个触发器，
   > **而验证用例只覆盖了作者想到的那个触发器。**

⭐ 穷举法是对那句话的结构性回答：**不列举用例，列举轴**，
  让笛卡尔积覆盖作者想不到的组合。
  ⚠️ 2026-09-10 订正：这里曾写「**已在三处验证**」，而当时已是 8 个 sweep、接入 11 个脚本 ——
    ⭐ **硬编码的计数会安静过期**，而它就写在治「声称≠实际」的模块里。
    ⇒ 不再写死数量；实时清单 = 本文件里的 `sweep_*` 函数。以下是几处代表性结果：
    · `_section._sweep()`            138 例 → 扫出 setext 缩进（我列不出来）
    · `definition-gate._sweep_answer_state()` 2940 例 → 扫出 **160 例**归一化组合
    · `research-gate` / `product-structure-gate` 的列识别 → 各自零失配（诚实的负面结果）

⚠️⚠️ **零发现的量具最可疑。** 本仓有一条教训叫「坏夹具会伪造出一个发现」，
   它反过来同样成立：一个什么都测不到的穷举也会报「零失配」。
   ⇒ `assert_weight_bearing()` 把这件事变成机器检查：
     故意打断被测判据，穷举**必须**变红；不变红就说明它没在量东西。
   ⚠️⚠️ 2026-09-10 订正：**这句话曾经是假的** —— 从本模块第一版起它就写在这儿，
     而那个函数**根本不存在**，承重确认全是手工做的（手动打断→观察→还原）。
     ⭐ **我在为了治「声称≠实际」而写的模块里，犯了「声称≠实际」。**
     是 codex 第三轮跑到一半的一次 grep 照出来的：全仓搜这个名字只有本行命中、零定义。
     现在它是真的（见文件末尾的实现），并已接进 product-structure 的自证。
   ⚠️ 覆盖度（⛔ 不许说成「已全部机器化」）：目前**只接了一处**
     （product-structure 的状态列穷举，实测打断黑名单后 180 例中 108 例变红）。
     其余几处仍是手工确认过的 —— 那是「未试」不是「做不到」，
     只需把 sweep 的签名统一成接受 `run_gate` 回调即可。

⛔ 诚实边界：**轴是我选的**。轴之外的构造仍然覆盖不到。
  穷举把「想得到的用例」换成「想得到的轴」——是一层进步，**不是完备性证明**。
  这句话必须跟着每一处穷举一起出现，⛔ 不许简化成「已穷举」。
"""


# ⚠️⚠️ 2026-09-10「变异覆盖审计」的三次量具失效 —— 记在这里，因为下次做同类枚举必会重走：
#   问题：「42 条元规则里，哪几条既没有变异靶、也没有项目模式用例？」
#   ①非贪婪 `MUTATIONS = \[(.*?)\n\]` 在**内层 `]`** 就截断 ⇒ 只抓到表头几条，报「32 条无靶」；
#   ②改括号配平，但起点用 `src.index('MUTATIONS = [')` —— 它命中的是
#     `no-positional-window` 里那个**字符串字面量**（跳过靶区用的），不是表定义 ⇒ 报「0 条目」；
#   ③写靶时变异串 `('definition-gate.py',` **在配对表里根本不存在**（表里是双引号）⇒ **空操作靶**。
#   ⭐⭐ 三次同族：**匹配到「提及」而非「定义」** —— 而这正是本仓修得最多的那类缺陷，
#     它在**调查工具**上又犯了三遍。
#   ⭐ 真正的教训不是「小心正则」，是：**第一个数字出来时先问「它可信吗」**。
#     若我不核对「32 条无靶」，就会去给 30 条**不需要靶**的规则补靶，白干一整轮。
#   ⇒ 做法：定义类锚点一律**锚行首**（`^MUTATIONS = \[`）；结构提取用括号配平不用正则；
#     变异串写完先断言它在目标里**恰好出现一次**（`assert_weight_bearing` 已内置这条断言）。


def report(name, n, bad, limit=5):
    """统一的穷举结果呈现。返回是否全过。"""
    print("  %s %s 构造空间穷举 %d 例" % ('✅' if not bad else '❌', name, n))
    for b in bad[:limit]:
        print("     · %s" % b)
    if len(bad) > limit:
        print("     · …另有 %d 例（同族）" % (len(bad) - limit))
    return not bad


def sweep_standing_column(run_gate, tmpdir):
    """research-gate 的 standing 列识别 —— 轴：表头名 × 列数 × 位置 × 值形态 × 干扰列。

    干扰列那一轴专门放「见 final analysis 报告」——历史上正是它靠
    `N/?A` 无词边界抢走了 standing 列的身份（第五轮实证）。
    """
    import itertools, os, io
    HDRS = ['standing', '状态', '当前状态', '填写状况', '进展', '结论', '覆盖情况']
    VALS = [('有输入', 'FILL'), ('', 'EMPTY'), ('TBD', 'EMPTY'), ('-', 'EMPTY')]
    NOISE = ['', '见 final analysis 报告']
    bad, n = [], 0
    for hdr, nc, pos, (val, kind), noise in itertools.product(
            HDRS, (2, 3, 4), ('末', '中'), VALS, NOISE):
        if nc == 2 and pos == '中':
            continue
        n += 1
        cols = (['决策域'] + ['备注'] * (nc - 2) + [hdr]) if pos == '末' \
            else (['决策域', hdr] + ['备注'] * (nc - 2))
        si = len(cols) - 1 if pos == '末' else 1
        rows = []
        for i in range(1, 13):
            c = ['域%d' % i] + [''] * (nc - 1)
            c[si] = val
            for k in range(1, nc):
                if k != si and noise:
                    c[k] = noise
            rows.append('| ' + ' | '.join(c) + ' |')
        md = ('# 下游决策域清单\n\n| ' + ' | '.join(cols) + ' |\n|'
              + '---|' * nc + '\n' + '\n'.join(rows) + '\n')
        d = os.path.join(tmpdir, 'rg%d' % n)
        os.makedirs(d, exist_ok=True)
        io.open(os.path.join(d, 's2-decision-domains.md'), 'w',
                encoding='utf-8').write(md)
        mark = run_gate(d)
        if kind == 'EMPTY' and mark == '✅':
            bad.append('空值却判过：表头=%s 列数=%d 位置=%s 值=%r 干扰=%r'
                       % (hdr, nc, pos, val, noise))
        if kind == 'FILL' and mark == '❌':
            bad.append('填好了却判红：表头=%s 列数=%d 位置=%s 干扰=%r' % (hdr, nc, pos, noise))
    return n, bad


def sweep_state_column(run_gate, base_md, sec4, tmpdir):
    """product-structure 判据④ —— 轴：表头名 × 列数 × 分隔符 × 状态值。

    表头轴里的「阶段」不含「状态/state」，专测**定位不到状态列时的退回路径**。
    """
    import itertools, os, io
    HDR = ['状态', '适用的数据状态', 'State', '阶段']
    VAL = [('empty%sloading', 'OK'), ('default%serror', 'OK'),
           ('empty%sSkeleton', 'BAD'), ('empty%s骨架屏', 'BAD'),
           ('empty%s禁用态', 'BAD')]
    bad, n = [], 0
    for hdr, nc, sep, (tpl, kind) in itertools.product(
            HDR, (2, 3, 4), ('/', '、', '，'), VAL):
        n += 1
        val = tpl % sep
        cols = ['页面', hdr] + ['出路'] * (nc - 2)
        row = ['列表页', val] + ['重试'] * (nc - 2)
        tbl = ('| ' + ' | '.join(cols) + ' |\n|' + '---|' * nc
               + '\n| ' + ' | '.join(row) + ' |\n')
        p = os.path.join(tmpdir, 'ps%d.md' % n)
        io.open(p, 'w', encoding='utf-8').write(base_md.replace(sec4, '\n' + tbl))
        rc = run_gate(p)
        if kind == 'BAD' and rc == 0:
            bad.append('违例被放行：表头=%s 列数=%d 分隔=%r 值=%r' % (hdr, nc, sep, val))
        if kind == 'OK' and rc != 0:
            bad.append('合法被判红：表头=%s 列数=%d 分隔=%r 值=%r' % (hdr, nc, sep, val))
    return n, bad


def sweep_claim_recognition(run_rule, tmpdir):
    """claim-ladder 的「声称 vs 提及」识别 —— 轴：语境 × 包裹 × 位置。

    🚨 首次运行扫出 **12 例失配**，全是同一族：**加了反引号的真实声称被当成提及**。
      `本轮状态：`integrated-frozen`。` 是再正常不过的写法（人们习惯给状态值加代码格式）。
      ⭐ 那条「反引号内＝提及」的启发式是为消除一处误伤顺手加的**代理指标**，
        而真正的区分从来不在**包裹**，在**这句话在主张什么**。⇒ 已撤掉。
    """
    import itertools, os, io
    LVL = 'integrated-frozen'
    CTX = [('本轮状态：%s。', 'CLAIM'),
           ('本文档不会声称 %s。', 'MENTION'),
           ('冻结结论不是 %s。', 'MENTION'),
           ('状态枚举值包括 %s，含义见流程规范。', 'MENTION'),
           ('取值范围：%s、local-verified。', 'MENTION'),
           ('**状态说明**：%s', 'CLAIM'),
           ('本轮不含新功能，状态：%s。', 'CLAIM')]
    WRAP = [('', ''), ('`', '`'), ('**', '**')]
    POS = ['%s', '前缀文本 %s', '| 甲 | %s |', '## %s']
    bad, n = [], 0
    for (tpl, kind), (a, b), pos in itertools.product(CTX, WRAP, POS):
        n += 1
        body = pos % (tpl % (a + LVL + b))
        d = os.path.join(tmpdir, 'cl%d' % n)
        os.makedirs(d, exist_ok=True)
        io.open(os.path.join(d, 'doc.md'), 'w', encoding='utf-8').write('# 文档\n\n' + body + '\n')
        st = run_rule(d)
        if kind == 'CLAIM' and st is not False:
            bad.append('声称却没要证据：%r 包裹=%r 位置=%r' % (tpl, a, pos))
        if kind == 'MENTION' and st is False:
            bad.append('提及被当成声称：%r 包裹=%r 位置=%r' % (tpl, a, pos))
    return n, bad


def sweep_pain_detection(run_gate, base_md, sec, tmpdir):
    """business-map 判据② 痛点识别 —— 轴：痛点词 × 位置 × 邻节诱饵。

    邻节诱饵那一轴专放「附注：早期版本有用户流失」——历史上正是它
    靠固定字符窗口/未锚定起点替**零痛点的 AS-IS 段**背书（第四、五轮各实证一次）。
    """
    import itertools, os, io
    PAIN = [('卡在', 'HAS'), ('流失', 'HAS'), ('出错', 'HAS'),
            ('痛点', 'HAS'), ('', 'NONE')]
    POS = ['行内 %s 这里', '**%s**', '> %s', '| 步骤 | %s |']
    DECOY = ['', '\n\n## 附注\n历史包袱：早期版本有用户流失，已修。\n']
    bad, n = [], 0
    for (w, kind), pos, decoy in itertools.product(PAIN, POS, DECOY):
        n += 1
        body = (pos % w) if w else '流程照常推进。'
        p = os.path.join(tmpdir, 'bm%d.md' % n)
        io.open(p, 'w', encoding='utf-8').write(
            base_md.replace(sec, '\n' + body + '\n') + decoy)
        missed = run_gate(p)          # True 表示门报「没有标出痛点」
        if kind == 'HAS' and missed:
            bad.append('有痛点却报没有：词=%r 位置=%r 诱饵=%s' % (w, pos, bool(decoy)))
        if kind == 'NONE' and not missed:
            bad.append('没痛点却判过：位置=%r 诱饵=%s' % (pos, bool(decoy)))
    return n, bad


def sweep_retro_sample(run_gate, base_md, old_line, tmpdir):
    """retro-gate 的样本量解析 —— 轴：值形态 × 字段写法 × 邻居字段。

    🚨 首次运行扫出 6 例失配：字段写成**表格单元格**（`| 样本量 | 37 个 |`）时
      取不到值 ⇒ 合法产物被报「没填」。解析器只认「字段名：值」这一种写法。

    ⚠️⚠️ **修的过程比结果更值得记，两条：**
      ① 我补表格分支时写成「以 `|` 开头即当表格行、取其余单元格拼接」，
         于是把行尾跟着的邻居字段也取了进来，零样本被邻居的 2000 掩盖
         —— ⭐ 这正是本函数上方注释点名的那个病（「取整行 ⇒ 把邻居字段的数
         当本字段的值」）**在新分支上的复发**：我一边读着那段注释，一边又犯一次。
         ⇒ 必须是完整表格行（首尾都有 `|`）且只取第二列。
      ② 收紧后仍剩 4 例「失配」，但**那不是缺陷** ——
         `| 样本量 | 37 个 |　/ 覆盖率：85%` 在 Markdown 里根本不是合法表格行，
         是我的**笛卡尔积造出了现实中不存在的组合**（邻居字段只对行内形态有意义）。
         ⭐⭐ **穷举法的陷阱：轴的笛卡尔积会造出不现实的组合，
           把它们当失配，会逼你去「修」一个没问题的地方** —— 而我差点就那么做了，
           上一条那个 bug 正是这样被引入的。⇒ 轴之间的**互斥约束必须显式写出来**。
    """
    import itertools, os, io
    VAL = [('37 个', 'OK'), ('0 个', 'ZERO'), ('0', 'ZERO'),
           ('<实际>', 'PLACEHOLDER'), ('0 次崩溃 / 128 个会话', 'OK'), ('三次', 'NONNUM')]
    INLINE = ['**实际样本量**：%s', '实际样本量：%s', '**样本量**：%s']
    TABLE = ['| 样本量 | %s |']
    NEIGH = ['', '　/ **最小可读样本**：2000', '　/ 覆盖率：85%']
    bad, n = [], 0
    combos = ([(f, nb) for f in INLINE for nb in NEIGH]     # 行内形态才有邻居字段
              + [(f, '') for f in TABLE])                   # ⛔ 表格行后面不跟行内字段
    for (v, kind), (f, nb) in itertools.product(VAL, combos):
        n += 1
        p = os.path.join(tmpdir, 'rt%d.md' % n)
        io.open(p, 'w', encoding='utf-8').write(base_md.replace(old_line, (f % v) + nb))
        flagged = run_gate(p)
        if kind == 'OK' and flagged:
            bad.append('合法样本量被判红：值=%r 写法=%r 邻居=%r' % (v, f, nb))
        if kind in ('ZERO', 'PLACEHOLDER', 'NONNUM') and not flagged:
            bad.append('%s 却没报：值=%r 写法=%r 邻居=%r' % (kind, v, f, nb))
    return n, bad


def sweep_appendix_parsing(run_gate, base_md, tmpdir):
    """prd_completeness 的附件解析 —— 轴：标题写法 × 缩进 × 交叉引用干扰 × 内容形态。

    🚨 首次运行扫出 **9 例失配**，三种形态全是**合规产物被报缺陷**：
      `#  附件 C`（`#` 后两个空格）· `## 附件 C`（二级标题）· `   # 附件 C`（合法缩进）。
      ⭐ 上一轮把 `s.index()` 改成 `^` 锚定行首，**只修了「位置」那一半** ——
        字面量本身仍是精确匹配，同一个附件换个合法写法就找不到了。
      ⇒ 交给 `_section`（缩进 0–3 / `#` 后空白 / 级别 / 围栏 / setext 它都处理过）。
        ⛔ 别在这里再手写一遍标题解析 —— 那正是「多套手写解析器」这个根因本身。

    ⚠️ 第二轮仍剩 3 例：附件标题写成 `##` 时，其子节 `## C.1` **同级** ⇒ 提前截断、
      合规附件被报「空壳」。⇒ 终点改用调用方本来就传了的 `end` 标记（比猜层级准）。

    ⚠️⚠️ 反向确认时**第一次打断是空操作**：我把 `_kw in tx` 换成 `tx.startswith(_kw)`，
      而 `附件 C · 安全与合规` 本来就以 `附件 C` 开头 —— 行为一点没变，穷举当然全绿，
      差点被读成「这个穷举没在量东西」。⭐ **「变异打错了靶子」在反向确认自身上复发。**
      换成真打断（退回精确字面量行首匹配）后：8 例中 4 例变红，承重性才算证实。
    """
    import itertools, os, io
    HDR = ['# 附件 C · 安全与合规', '#  附件 C · 安全与合规',
           '## 附件 C · 安全与合规', '   # 附件 C · 安全与合规']
    XREF = ['', '\n> 留存策略与 # 附件 D 的口径一致。\n', '\n> 详见 # 附件 C。\n']
    CONTENT = [('KEEP', 'OK'), ('EMPTY', 'BAD')]
    orig = '# 附件 C · 安全与合规'
    if orig not in base_md or '# 附件 D' not in base_md:
        return 0, ['夹具里没有附件 C/D —— **本条没验**']
    i = base_md.index(orig)
    j = base_md.index('# 附件 D')
    cbody = base_md[i:j]
    bad, n = [], 0
    for hdr, xref, (mode, kind) in itertools.product(HDR, XREF, CONTENT):
        n += 1
        newc = (hdr + cbody[len(orig):]) if mode == 'KEEP' \
            else (hdr + '\n\n（本轮不适用）\n\n')
        if xref and mode == 'KEEP':
            newc = newc.replace('## C.1 数据清单', '## C.1 数据清单\n' + xref, 1)
        p = os.path.join(tmpdir, 'prd%d.md' % n)
        io.open(p, 'w', encoding='utf-8').write(base_md[:i] + newc + base_md[j:])
        flagged = run_gate(p)
        if kind == 'OK' and flagged:
            bad.append('合规附件 C 被报缺陷：标题=%r 干扰=%r' % (hdr, xref[:12]))
        if kind == 'BAD' and not flagged:
            bad.append('空壳附件 C 没报：标题=%r' % hdr)
    return n, bad


def sweep_direction_table(run_gate, base_md, tmpdir):
    """design-intent 的三方向登记表 —— 轴：方向行数 × 空格位置 × 两方向全同 × 标题写法。

    ⚠️⚠️ **第一版这个穷举是坏的，值得单独记一笔**：
      我声明了 `ROWS` / `CELL` 两个轴却**从没把它们接到夹具上**，
      只有标题写法在变 ⇒ 报「24 例」，实际只测了 **4 个不同输入**（各重复 6 次）。
      ⭐ 这是本仓「坏夹具会伪造出一个发现」的**镜像**：
        坏夹具会伪造发现，**坏穷举会伪造覆盖** —— 报的数字比真实覆盖大 6 倍，
        而输出看起来完全正常。
      ⇒ 轴必须**真的接到被测输入上**；写完先自查「改这个轴，输入变了吗」。

    ⚠️ 反向确认用的打断也必须真会改行为（上一处栽过）：
      这里打断的是「四格填齐」判据（`filled` 不再要求非空）⇒ 4 例中 1 例变红。
    """
    import itertools, os, io, re
    rows = [l for l in base_md.split('\n')
            if re.match(r'^\|\s*方向\s+[A-Z甲乙丙]', l.strip())]
    m = re.search(r'^#{1,4}[^\n]*三个视觉方向登记表[^\n]*$', base_md, re.M)
    if not rows or not m:
        return 0, ['夹具里没有三方向登记表 —— **本条没验**']
    orig_hdr = m.group(0)
    NROW = [(3, 'OK'), (2, 'FEW'), (1, 'FEW')]
    BLANK = [('none', 'OK'), ('c2', 'BAD'), ('c4', 'BAD')]
    DUP = [(False, 'OK'), (True, 'BAD')]
    HDR = ['## 三个视觉方向登记表', '### 三个视觉方向登记表', '   ## 三个视觉方向登记表']
    bad, n = [], 0
    for (nr, rk), (bl, bk), (dp, dk), hdr in itertools.product(NROW, BLANK, DUP, HDR):
        n += 1
        cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows[:nr]]
        if bl == 'c2' and cells:
            cells[0][2] = ''
        if bl == 'c4' and cells and len(cells[0]) > 4:
            cells[0][4] = ''
        if dp and len(cells) >= 2:
            cells[1][1:5] = cells[0][1:5]
        newrows = ['| ' + ' | '.join(c) + ' |' for c in cells]
        md = base_md
        for i, r in enumerate(rows):
            md = md.replace(r + '\n', (newrows[i] + '\n') if i < len(newrows) else '', 1)
        md = md.replace(orig_hdr, hdr, 1)
        p = os.path.join(tmpdir, 'di%d.md' % n)
        io.open(p, 'w', encoding='utf-8').write(md)
        flagged = run_gate(p)
        want = (rk != 'OK') or (bk != 'OK') or (dk != 'OK')
        if flagged != want:
            bad.append('%s：行数=%d 空格=%s 全同=%s 标题=%r'
                       % ('该红没红' if want else '合规被判红', nr, bl, dp, hdr))
    return n, bad


def sweep_s1_directions(extract, tmpdir=None):
    """chain-gate 的 S1 方向抽取 —— 轴：标题写法 × 列表记号 × 命名标记 × 行内强调。

    🚨 首次运行扫出 **10 例失配**，全是一个形状：**3 空格缩进的标题**（合法 ATX）
      认不出 ⇒ **静默降级到 `quotes` 兜底模式**，一个方向都取不到，
      S1→S2 对账整条失效。
      ⭐ 「静默降级」这一点最要命：输出里看不出「我没找到那一节」，
        只看到「没有方向」——**与「真的没写方向」长得一模一样**。
      ⇒ 交给 `_section`。⛔ 不在门禁里再手写一遍标题匹配。

    ⚠️ 行内强调那一轴（`**方向1**：这里有**强调**的加粗`）守的是既有教训
      「命名与强调必须只有一个标记」——它在这一轮仍然全绿。
    """
    import itertools
    HDR = ['## 粗颗粒功能', '### 粗颗粒功能', '##  粗颗粒功能', '   ## 粗颗粒功能']
    BULLET = ['- ', '* ', '1. ', '1、', '| ']
    NAME = ['**{}**', '「{}」']
    INLINE = ['', '：这里有**强调**的加粗']
    bad, n = [], 0
    for hdr, b, nm, inl in itertools.product(HDR, BULLET, NAME, INLINE):
        n += 1
        body = '\n'.join(b + nm.format('方向%d' % i) + inl for i in (1, 2, 3))
        items, mode = extract('# S1\n\n' + hdr + '\n' + body + '\n\n## 其它\n正文\n')
        if items != {'方向1', '方向2', '方向3'}:
            bad.append('标题=%r 记号=%r 命名=%r 强调=%s → 取到 %s（模式=%s）'
                       % (hdr, b, nm, bool(inl), sorted(items)[:3], mode))
    return n, bad


def assert_weight_bearing(gate_path, mutation, sweep_fn, expect_min=1):
    """把「这个穷举真的在量东西」从**手工步骤**变成**机器检查**。

    🚨🚨 2026-09-10：本模块的 docstring 从第一版起就写着
      「⇒ `assert_weight_bearing()` 把这件事变成机器检查」——
      **而这个函数当时根本不存在**。承重确认全是我手工做的
      （手动打断判据 → 看穷举变红 → 还原），
      ⭐ **我在为了治「声称≠实际」而写的模块里，犯了「声称≠实际」。**
      是 codex 第三轮跑到一半（额度用尽前）的一次 grep 把它照出来的：
      全仓搜 `assert_weight_bearing` 只有 docstring 那一处命中，零定义。
      ⇒ 现在它是真的。

    做法：把门禁脚本复制到临时目录、施加一处**文本变异**（`mutation` = (旧串, 新串)），
    让 `sweep_fn` 针对**变异后的副本**跑一遍，断言它至少报出 `expect_min` 条失配。
    ⛔ 不变红 ⇒ 这个穷举没在量它声称量的东西，直接判失败。

    ⚠️ 量程（诚实边界，⛔ 不许简化成「已机器化」）：
      · 只覆盖「sweep 通过 `run_gate` 回调跑子进程」这一类（本模块六个 sweep 里的多数）；
        直接调函数的那种（如 `sweep_s1_directions` 传的是 `s1_directions` 本身）**用不了**，
        那几处仍是手工确认 —— **这是「未试」不是「做不到」**，可以做，只是要改签名。
      · 变异串写错（不匹配）时**必须报错而不是静默通过** —— 见下方 assert。
    """
    import shutil, tempfile, os, subprocess, sys, io as _io
    old, new = mutation
    src = _io.open(gate_path, encoding='utf-8').read()
    if old not in src:
        raise AssertionError('承重确认的变异串没命中 —— 这次什么都没测：%r' % old[:60])
    d = tempfile.mkdtemp(prefix='wb-')
    dst_dir = os.path.join(d, 'scripts')
    shutil.copytree(os.path.dirname(gate_path), dst_dir)
    dst = os.path.join(dst_dir, os.path.basename(gate_path))
    _io.open(dst, 'w', encoding='utf-8').write(src.replace(old, new, 1))

    def _run(p):
        return subprocess.call([sys.executable, dst, p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        _n, bad = sweep_fn(_run)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return len(bad) >= expect_min, len(bad)


def _self_test():
    """共用穷举骨架必须能同时识别全匹配与系统性失配。"""
    import re

    ok = True

    def chk(name, condition, detail=''):
        nonlocal ok
        passed = bool(condition)
        ok = ok and passed
        print(('  ✅ ' if passed else '  ❌ ') + name
              + ('' if passed or not detail else '　' + detail))

    def good_extract(md):
        return set(re.findall(r'方向[123]', md)), 'self-test'

    total, mismatches = sweep_s1_directions(good_extract)
    chk('正例：S1 方向构造空间的每个合法组合均被正确识别',
        total == 80 and not mismatches,
        '实得 total=%d mismatches=%d' % (total, len(mismatches)))
    bad_total, bad_mismatches = sweep_s1_directions(lambda _md: (set(), 'broken'))
    chk('反例：打断方向抽取后全部组合必须报失配（锚定 sweep 失配判据）',
        bad_total == 80 and len(bad_mismatches) == 80
        and '取到' in bad_mismatches[0],
        '实得 total=%d mismatches=%d' % (bad_total, len(bad_mismatches)))

    print('\n%s' % ('✅ 自证通过：共用构造空间穷举会识别失配' if ok
                     else '❌ 自证失败：共用构造空间穷举失真'))
    return 0 if ok else 1


if __name__ == '__main__':
    import sys
    if '--help' in sys.argv:
        print(__doc__ or '')
        print('用法: _sweep_lib.py --self-test')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    print('UNABLE: 本模块只提供共享穷举判据；请使用 --self-test', file=sys.stderr)
    sys.exit(2)
