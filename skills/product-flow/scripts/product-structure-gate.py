#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S4A 产品结构出场门 —— product-structure.md 的五条结构性判据。

═══ 它补的洞（终局规格 1-1）═══
S4A 防的是「结构未清就填 PRD 模板」——但它自己此前无门禁，
于是「画了个树」和「结构成立」在产物上长得一模一样。

判据（照 templates/product-structure.md 结构反推）：
  ① 功能架构树含 ≥1 个 F-xx（结构必须落到功能编号，否则 PRD 3.2 接不上）
  ② 每条关键任务流有失败/中断出路（↳ 或「失败」「中断」「回到」——没有出路的流程是理想国）
  ③ 权限矩阵 ≥1 行真实内容
  ④ 状态登记只用①类成员（default/empty/loading/success/error —— 唯一权威源
    `interaction-patterns.md`；Skeleton/Disabled 出现在状态列即红）
  ⑤ 零技术栈词命中（判据=换技术栈答案就变的词；产品结构不写工程决定）

用法: product-structure-gate.py <product-structure.md> [--json] | --self-test
退出码: 0=通过 1=有缺口 2=跑不了
⚠️ 验不了什么：结构合不合理（IA 好不好归 S5 评审与 A 锁）；本门只验「结构完整落地且没越界」。
"""
import io, json, os, re, sys

# 🚨 2026-09-09 二轮独立复核揪出：原来整串套 `\b`，而 **`\b` 在 CJK 之间不成立**
#   （中文字符都是 `\w`，「系统采用微服务架构」里 `微服务` 两侧没有词边界）⇒
#   15 个词里的 4 个中文词 **一次都不可能命中**：微服务/索引/表结构/分库分表 全是死判据。
#   ⭐ 一条中文语境的判据，只在 ASCII 上有效。⇒ 拆两组：ASCII 词保留 `\b`，中文词裸匹配。
# 🚨 2026-09-09 第五轮独立复核：本组**没有 re.I** ⇒ 只有一种拼法守得住 ——
#   `postgresql` / `REDIS` / `MySql` / `Postgres` 实测全部 rc=0。
#   ⭐ 一个大小写就绕过，说明判据锁的是**字面量**不是**概念**。
#   ⇒ 整组改大小写不敏感；`Postgres` 这类常见简写一并纳入。
# ⚠️ 诚实边界（不假装能治的部分）：本判据是**字面量词表**，
#   拆词（`Post greSQL`）、零宽字符、全角（`ＲＥＤＩＳ`）、词表外的新技术名，
#   它一概查不到 —— 这一层归人工评审，输出里已如实声明。
TECH_WORDS_ASCII = (r'\b(PostgreSQL|Postgres|MySQL|Redis|MongoDB|Kafka|REST|GraphQL|gRPC|'
                    r'React|Vue|localStorage|Elasticsearch|Nginx|Docker|Kubernetes|SQLite|'
                    r'ORM|JWT|WebSocket|Spring|Django)\b')
# ⚠️ 2026-09-09 三轮复核：`索引` 裸词过宽 —— 正文写「列表页提供**字母索引页**」
#   （纯 IA 概念，换技术栈答案不变）会被报「出现技术栈词」，直接违反本规则自己的判准
#   （「换技术栈答案就变的才属于技术方案」）。⇒ 只认技术语境里的索引。
TECH_WORDS_CJK = r'(微服务|表结构|分库分表|建(?:立)?索引|加索引|索引优化|数据库索引|联合索引)'
TECH_WORDS = r'(?:%s)|(?:%s)' % (TECH_WORDS_ASCII, TECH_WORDS_CJK)
# ⚠️ 只对 ASCII 组开 re.I（中文没有大小写，开了也不变）；编译成一个对象免得两处漂移。
TECH_WORDS_RE = re.compile(TECH_WORDS, re.I)
STATE_OK = {'default', 'empty', 'loading', 'success', 'error'}


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at, before_section   # noqa: E402  段落定位的唯一正本


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def check(md):
    bad = []
    # 🚨 2026-09-09 第五轮独立复核：`md.split('信息架构')[0]` 按**全文首次出现**切 ——
    #   一行目录（「本文分为：信息架构、任务流、权限矩阵」）就把可搜范围切成了目录之前，
    #   于是一份**完全合规**的文档同时报 ①②③ 三条错，而三样东西全都在。
    #   ⭐ 错误诊断比漏报贵：作者拿到三条明显错的报错，就整体不再信这道门。
    #   ⇒ 改锚定标题（_section）；取不到该节时**退回全文搜**（宁可漏，不可误伤）。
    # 🚨 2026-09-10 codex #10：这里原本 `md[:md.index(_ia)]`，假设 section_at 的返回值是
    #   md 的**连续子串** —— 而「同名节全取并拼接」那次修复改变了这个契约 ⇒
    #   两个非嵌套同名「信息架构」节会让它抛 ValueError **直接崩**。⇒ 改用 before_section。
    _before = before_section(md, '信息架构')
    if not re.search(r'F-\d+', _before or md):
        bad.append('① 功能架构里没有任何 F-xx —— 结构没落到功能编号，PRD 3.2 接不上')
    seg2 = section_at(md, '关键任务流')
    if seg2 is None:
        bad.append('② 没有「关键任务流」段')
    else:
        # 🚨 2026-09-09：分隔符原为未锚定行首的 '## ' —— **行内出现 `## `**
        #   （如「文档里用 ## 表示二级标题」）会把本段提前截断：实测截断处之前那条
        #   合法任务的 ↳ 出路被切掉 ⇒ 报它「没出路」（假阳性），
        #   而截断之后真正无出路的任务整条逃检（漏报）。⛔ 一刀切出两种错。
        #   ⚠️ 2026-09-09 第五轮：连「锚定行首的 `\n## `」也还不够 —— 起点仍是
        #     `md.find('关键任务流')`（全文首次出现）。**终点锚定了，起点没有**，
        #     一句「关键任务流见下」即让本段从那句开始切。⇒ 起止都交给 _section。
        seg = seg2
        flows = re.findall(r'任务[：:].+', seg)
        if not flows:
            bad.append('② 任务流段里没有任何「任务：」条目')
        else:
            # ⛔ 逐条任务判出路 —— 曾经整段一个「失败」字替所有任务背书（Codex 复审抓出）
            blocks = [b for b in re.split(r'\n(?=\s*任务[：:])', seg) if re.search(r'任务[：:]', b)]
            # 🚨 2026-09-09 第五轮：判据是「块内出现关键词」，于是
            #   `任务：处理失败订单` **零出路却判过** —— 任务名里自带一个「失败」字。
            #   ⭐ 出路必须由**任务名之外**的内容给出，不能自己给自己背书。
            #   ⇒ 判之前先把「任务：…」那一行本身剥掉。
            def _body_of(b):
                return re.sub(r'任务[：:][^\n]*', '', b, count=1)
            noexit = [re.search(r'任务[：:](.{0,20})', b).group(1).strip() for b in blocks
                      if not re.search(r'↳|失败|中断|回到', _body_of(b))]
            if noexit:
                bad.append('② 有任务流没有失败/中断出路（逐条判，不共享失败词）：%s' % '、'.join(noexit))
    # ⚠️ 不用固定字符窗口（本仓第 N 次教训：窗口会吃进下一节的表）——切到下个标题
    _seg3 = section_at(md, '权限矩阵')
    rows = ([l for l in _seg3.split('\n') if l.strip().startswith('|')]
            if _seg3 is not None else [])
    # 🚨 2026-09-09 第五轮：判据只验「非空」⇒ 整表 `| TBD | TBD | TBD |` 判过。
    #   ⭐ 与 research-gate 决策域那条**同型**（占位符全算填了），同一天两处各犯一次。
    _PH = re.compile(r'^(?:TBD|TODO|N/?A|-+|—+|/+|\?+|待[定填补]\w{0,3}|待补充|略|空)$', re.I)

    def _row_real(r):
        cells = [c.strip().strip('*`') for c in r.strip().strip('|').split('|')]
        return any(c and not _PH.match(c) for c in cells)

    data = [r for r in rows[2:] if r.replace('|', '').replace('-', '').strip()
            and not re.match(r'^\|\s*<', r.strip()) and _row_real(r)]
    if _seg3 is None:
        bad.append('③ 没有「权限矩阵」段')
    elif not data:
        bad.append('③ 权限矩阵没有一行真实内容')
    # 🚨🚨 2026-09-09 第五轮独立复核抓到的**最严重一处**：起点是
    #   `md.find('状态与异常结构')`，于是正文里一句
    #     > 本文的状态与异常结构一节见文末。
    #   就让判据④ 从那句话开始往后切 —— **四个真违例全在切点之前，整条判据静默失效**，
    #   门打印「✅ S4A 五判据全过」rc=0。节标题改个名（「## 6. 状态设计」）同样整条不查。
    #   ⭐ 自证④ 的 11 条用例没有一条动过节标题或前言 —— 用例只覆盖了作者想到的形状。
    # 🚨 2026-09-10 第六轮（E2）：这里写的是 `if seg4 is not None:` —— **取不到就跳过，
    #   不报缺失**。而 `_section.py` 自己的契约写着「`None` = 没有这一节（**该报缺失**）」。
    #   实测代价：整份文档改成 setext 风格标题（合法 Markdown）时，判据②③ 报「整节缺失」、
    #   判据④ **静默 fail-open** —— 同一个 `None`，三个消费方三种处理。
    #   ⭐ 契约写在模块里，消费方没遵守，而没有任何东西检查这件事。
    seg4 = section_at(md, '状态与异常结构')
    if seg4 is None:
        bad.append('④ 没有「状态与异常结构」段 —— 状态登记缺失，S5 交互设计接不上')
    else:
        # 🚨 2026-09-09：原来是 md[i:i+1200] 固定字符窗口 —— **同一文件上面那段
        #   刚因为这个病改过**（窗口会吃进下一节的表），这里漏了。两个方向都坏：
        #   ①段后还有别的节 → 吃进邻节的表，拿别人的行报本节的错；
        #   ②状态表长于 1200 → **后面的行静默逃过非法状态检测**（实测：把 Skeleton
        #     放在第 1200 字符之后，本门报「五判据全过」）。⛔ 截断不报＝假绿。
        seg = seg4
        # 🚨 2026-09-09 三轮独立复核揪出：抽取器是 `[A-Za-z]+`，把状态格里
        #   **每一个英文单词**都当状态 token，且不跳表头、不区分是不是状态表 ⇒
        #   打开 STATE_OK 白名单后引入四类误伤（实测）：
        #     表头 `| Object | State |` → 报「出现 State」
        #     `N/A（无远程数据）`（本仓自己认的三态之一）→ 报「出现 N」「出现 A」
        #     `empty/loading/error（see UI spec）` → 报「see」「UI」「spec」三条
        #     本节内另一张无关三列表 → 报「出现 Owner」「出现 Alice」
        #   ⭐ **黑名单能容忍抽取噪声，白名单不能** —— 换判据方向时必须同步收紧抽取器。
        # 🚨 2026-09-09 第五轮独立复核，判据④ 三处放行一起修：
        #   ①行正则 `\|(…)\|(…)\|[^|\n]*\|` **要求至少 4 个竖线**（3 格）⇒
        #     两列状态表 `| 列表页 | Skeleton |` **连黑名单都不走**，整行不查。
        #   ②白名单只查含 `/` 的格 ⇒ `| 列表页 | Pending |` 逃逸
        #     （合法状态枚举不一定写成斜杠分隔）。
        #   ③中文黑名单只有 3 个词 ⇒ `骨架`（不带屏）/`加载骨架`/`待定态`/`灰态` 全逃。
        #   ⇒ 改**通用分格**（按 `|` 切，几列都认）+ 状态列**按表头名定位**
        #     （含「状态/state」的列）；定位不到时退回「全行黑名单，不跑白名单」——
        #     ⭐ 黑名单能容忍抽取噪声，白名单不能，所以量程差别对待（这条第四轮已定）。
        _lines = [l.strip() for l in seg.split('\n') if l.strip().startswith('|')]
        _hdr_cells, _state_col = [], None
        if _lines:
            _hdr_cells = [c.strip() for c in _lines[0].strip('|').split('|')]
            _state_col = next((i for i, h in enumerate(_hdr_cells)
                               if '状态' in h or 'state' in h.lower()), None)
        _rows = []
        for _li, _l in enumerate(_lines):
            if _li == 0 or set(_l.strip('|')) <= set('-: |'):
                continue                     # 表头行与分隔行不是数据
            _rows.append(_l)
        for m in _rows:
            # 🚨🚨 2026-09-09 第四轮复核：上一批为消除误伤加的三个豁免**没有边界** ——
            #   「剥掉括号里的说明」把 `(Skeleton)`、`（Skeleton、Pending）` 一起放过；
            #   「N/A 开头就跳过」把 `N/A、Skeleton` 整行放过；
            #   只看第 2 列 ⇒ 状态写第 3 列即隐身；只认 ASCII ⇒ `骨架屏`/`禁用态` 不查。
            #   五种一步编辑距离的变体全部逃逸（实测）。
            #   ⭐ 根因：**我把「消除误伤」做成了「整段不看」**。
            #   ⇒ 分开两件事：
            #     ①**黑名单（已知错词）**——宽容抽取、**全行搜**（含括号内、含中文），
            #       它只认明确写错的词，抽取噪声不会造成误伤；
            #     ②**白名单（①类合法状态）**——只在「看起来像状态列」的格子里查，
            #       噪声容忍度低，所以量程必须窄。
            _WRONG = [('skeleton', 'Skeleton'), ('disabled', 'Disabled'),
                      ('骨架屏', '骨架屏'), ('骨架', '骨架'), ('加载骨架', '加载骨架'),
                      ('禁用态', '禁用态'), ('禁用', '禁用'), ('待定态', '待定态'),
                      ('置灰', '置灰'), ('灰态', '灰态')]
            _whole = m                        # 整行，不剥括号、不限列
            for _key, _show in _WRONG:
                if _key in _whole.lower():
                    bad.append('④ 状态列出现 %s —— Skeleton/骨架屏是 loading 的呈现策略、'
                               'Disabled/禁用态归③类可用性（唯一权威源 '
                               'interaction-patterns.md），不写进①类数据状态表' % _show)
            # ②白名单：只查明确的状态格（含斜杠分隔的状态枚举），剥括号说明后判
            _cells = [c.strip() for c in _whole.strip().strip('|').split('|')]
            for _ci, _c in enumerate(_cells):
                _c2 = re.sub(r'[（(][^）)]*[）)]', '', _c)
                # ⭐ 量程：表头定位得到状态列 ⇒ 只查那一列（不要求斜杠）；
                #   定位不到 ⇒ 退回「只查含斜杠的枚举格」（老行为，噪声容忍度低）。
                if _state_col is not None:
                    if _ci != _state_col:
                        continue
                elif '/' not in _c2:
                    continue                  # 不是状态枚举格
                if re.match(r'^\s*N/?A\b', _c2.strip(), re.I):
                    continue                  # N/A 是合法三态之一
                for tok in re.findall(r'[A-Za-z]{2,}', _c2):
                    if tok.lower() in ('n', 'a', 'see', 'ui', 'spec', 'br'):
                        continue
                    if tok.lower() not in STATE_OK and \
                            tok.lower() not in ('skeleton', 'disabled'):
                        bad.append('④ 状态列出现 %s —— ①类数据/流程状态只有 %s；'
                                   '组件交互态与可用性态归 interaction-patterns 另两类'
                                   % (tok, '/'.join(sorted(STATE_OK))))
    # ⚠️ 用 finditer 取整体匹配：TECH_WORDS 现在是两组的并集，
    #   findall 遇多组会返回元组，'、'.join 会炸（自证当场抓到）。
    # 🚨 2026-09-09 第四轮复核：**项目自己的模板过不了自己的门** ——
    #   `templates/product-structure.md:26` 写「关键字段（业务含义，**非表结构**）」，
    #   那是在**告诉人别写技术细节**，却被判成技术栈词。
    #   ⭐ 与 research-gate 的「禁令句被判成编造」同型：门把自己的教学语句当违例。
    #   ⇒ 紧邻否定语（非/不是/不写/别写/不许/⛔）之后的命中不算。
    # 🚨 2026-09-09 第五轮：这条豁免**可以被反向利用** —— 它只看前 6 个字符，
    #   于是「非 Redis 不可」「⛔MySQL 必须开主从」「禁止 PostgreSQL 以外的方案」
    #   全部 rc=0：**加个否定前缀就能把技术选型正大光明写进产品结构**。
    #   ⭐ 与第四轮那条「我把『消除误伤』做成了『整段不看』」是同一个病，
    #     在同一批修复里换了位置复发 —— 豁免的量程是**文本邻域**而不是**语义**。
    #   ⇒ 收窄：否定词与命中之间不许再有实词（`非表结构` 这类紧贴的教学语句仍豁免），
    #     且**整句里若还出现肯定性要求**（必须/要/得/应）就不算否定语境。
    _NEG_CTX = re.compile(r'(?:非|不是|不写|别写|不许|禁止|⛔)[\s「『"\']{0,2}$')
    def _exempt(m, text=None):
        # ⚠️ 2026-09-10：加归一化那一遍时**忘了让它也走这条豁免** ⇒
        #   教学句「非表结构」在归一文本里被判红，自证当场抓到。
        #   ⭐ 「加一条新路径」必须问：**旧路径上的每条豁免，新路径上有没有**。
        t = md if text is None else text
        if not _NEG_CTX.search(t[max(0, m.start() - 6):m.start()]):
            return False
        # 取命中所在的整句，若句中另有肯定性要求 ⇒ 这不是「别写它」，是「就得用它」
        _lo = max(t.rfind('\n', 0, m.start()), t.rfind('。', 0, m.start())) + 1
        _hi = min([x for x in (t.find('\n', m.end()), t.find('。', m.end()))
                   if x > 0] or [len(t)])
        return not re.search(r'必须|应当|应该|要用|得用|以外|不可', t[_lo:_hi])
    # 🚨🚨 2026-09-10 自查（并行会话回流的教训触发）：本门的边界声明写着
    #   「拆词 / 零宽字符 / **全角**（ＲＥＤＩＳ）一概查不到」——
    #   ⭐ 但**全角与零宽是可以廉价归一的**（NFKC + 剥零宽），那是「**我没做**」，
    #     不是「**做不到**」。⛔ 把「没试过」写进边界声明，等于用「不可能」把它盖住，
    #     而「不可能」最贵的地方是**它让人不再尝试**。
    #   ⇒ 归一后再匹配；边界声明同步收窄到真正难的那部分（拆词 / 词表外新技术名）。
    #   ⚠️ 归一只用于**匹配**，报错仍报原文，免得作者对不上自己写的字。
    import unicodedata as _ud
    _norm = _ud.normalize('NFKC', md).replace('\u200b', '').replace('\u200c', '') \
                                     .replace('\u200d', '').replace('\ufeff', '')
    hits = sorted({m.group(0) for m in TECH_WORDS_RE.finditer(md) if not _exempt(m)})
    _hits_n = {m.group(0) for m in TECH_WORDS_RE.finditer(_norm)
               if not _exempt(m, _norm)}
    hits = sorted(set(hits) | (_hits_n - set(hits)))
    if hits:
        bad.append('⑤ 出现技术栈词（换技术栈答案就变的不属于产品结构）：%s' % '、'.join(hits[:4]))
    return bad


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a:
        die('缺少 product-structure.md 路径；用法见 --help')
    if not os.path.isfile(a[0]):
        die('文件不存在：%s' % a[0])
    bad = check(io.open(a[0], encoding='utf-8').read())
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for b in bad:
            print('  ❌ ' + b)
        print('✅ S4A 五判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        # ⚠️ 诚实边界（boundary-on-green：绿灯上必须说清验不了什么）
        print('⚠️ 判据⑤ 是**字面量词表**：**拆词**（Post greSQL）与**词表之外的新技术名**'
              '查不到 ——')
        print('   （全角与零宽字符已做 NFKC 归一，2026-09-10 起能查到；'
              '此前边界声明把它们也写成「查不到」，那是把「没试过」说成了「不可能」）')
        print('   那一层归人工评审，⛔ 本门不声称覆盖。')
        print('⚠️ 本门验不了结构合不合理 —— IA 好不好归 S5 评审与 A 锁。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import tempfile, subprocess
    t = tempfile.mkdtemp(prefix='ps-')
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        print(('  ✅ ' if c else '  ❌ ') + n + ('' if c else '　' + e))
        ok = ok and c

    GOOD = """# 产品结构
## 1. 功能架构
产品
 ├─ 整理域：F-01 智能挑片 · F-02 相似归组
## 3. 关键任务流
任务：交付一批客片
入口 → 挑片 → 确认 → 完成态
       ↳ 失败：AI 置信度低，回到人工挑片
## 5. 权限矩阵
| 操作 | 摄影师 | 买家 | 未登录 |
|---|---|---|---|
| 删除原片 | ✓ | ✗ | ✗ |
## 6. 状态与异常结构
| 对象/页面 | 适用的数据状态 | 异常后的出路 |
|---|---|---|
| 挑片列表 | empty/loading/error | 重试或人工模式 |
"""

    def run(body):
        p = os.path.join(t, 'ps.md')
        io.open(p, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chk('正例：五判据全过 → 0', run(GOOD) == 0)
    # ⭐ 构造空间穷举（轴 = 表头名 × 列数 × 分隔符 × 状态值）——说明见 _sweep_lib。
    #   「阶段」这个表头不含「状态/state」，专测**定位不到状态列时的退回路径**。
    import tempfile as _tf2, shutil as _sh2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_state_column, report as _rep
    from _section import section_at as _sa
    _sec4 = _sa(GOOD, '状态与异常结构')
    _b2 = _tf2.mkdtemp(prefix='ps-sweep-')
    _n2, _bad2 = sweep_state_column(lambda _p: subprocess.call(
        [sys.executable, os.path.abspath(__file__), _p],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), GOOD, _sec4, _b2)
    _sh2.rmtree(_b2, ignore_errors=True)
    chk('状态列识别 构造空间穷举 %d 例' % _n2, not _bad2)
    for _x in _bad2[:4]:
        print('     · %s' % _x)
    # ⭐ 承重确认现在是**机器检查**（此前是我手工做的，而 _sweep_lib 的 docstring
    #   却写着「已变成机器检查」—— 那句话曾是假的，见该函数说明）。
    #   打断黑名单里的「禁用态」⇒ 穷举必须变红；不变红说明它没在量东西。
    from _sweep_lib import assert_weight_bearing as _awb
    _b3 = _tf2.mkdtemp(prefix='ps-wb-')
    try:
        _wb_ok, _wb_n = _awb(
            os.path.abspath(__file__),
            # ⚠️ 第一版变异选的是删掉 `('禁用态','禁用态')` —— **空操作**：
            #   `_WRONG` 里还有更宽的 `('禁用','禁用')`，`禁用态` 照样命中。
            #   ⭐ 「变异打错了靶子」本会话第三次。而 `assert_weight_bearing` **正确地
            #     报了 0 例变红** —— 它抓的就是这个，函数本身是好的。
            #   ⇒ 换成整条黑名单置空，行为改变不含糊。
            ("for _key, _show in _WRONG:", "for _key, _show in []:"),
            lambda _run: sweep_state_column(_run, GOOD, _sec4, _b3))
    finally:
        _sh2.rmtree(_b3, ignore_errors=True)
    chk('↑ 该穷举**确实在量东西**（打断黑名单后 %d 例变红）' % _wb_n, _wb_ok)
    _EXIT_LINE = '       ↳ 失败：AI 置信度低，回到人工挑片\n'
    assert _EXIT_LINE in GOOD, '出路行文本对不上 —— 夹具改了就要同步这条'
    # ===== 2026-09-10 第六轮独立复核：`_section.py` 引入的**回归**（四条，两个方向）=====
    # ⭐⭐ 这一簇最值得记：新模块用「结构锚定」替掉「字面量定位」，方向是对的，
    #   但**「结构」的定义漏了代码围栏与 setext 标题** ⇒ 该模块 docstring 里
    #   逐字描述的双向失效（漏一条判据 + 报假错）在**同一份产物上原样复现**，
    #   只是触发器从「正文提一句节名」换成了「正文里有段代码」。
    #   **修复把失效模式换了个触发器，而用例只覆盖了作者想到的那个触发器。**
    _FENCE = "\n```python\n# 状态流转\nstate = 'loading'\n```\n"
    _BADST = "| 详情页 | Skeleton | 重试 |\n"
    chk('反例④d：状态节里有带 # 的代码围栏 → 仍 1（围栏内的 # 不是标题）',
        run(GOOD.rstrip('\n') + _FENCE + _BADST) == 1)
    chk('正例：任务流中间隔一段 shell 围栏 → 0（⛔ 不许把出路行切走后报「没有出路」）',
        run(GOOD.replace(_EXIT_LINE,
                         "```bash\n# 跑一次全量\ngate-run --all\n```\n" + _EXIT_LINE)) == 0)
    chk('正例：整篇 setext 风格标题 → 0（合法 Markdown，⛔ 不许报两条不存在的缺失）',
        run(re.sub(r'^## +(.+)$', lambda m: m.group(1) + "\n" + "-" * len(m.group(1)) * 2,
                   GOOD, flags=re.M)) == 0)
    chk('反例④e：同名节的「概要」桩节在前、真节在后 → 仍 1（桩节不许遮住真节）',
        run(GOOD.replace("## 6. 状态与异常结构",
                         "## 6. 状态与异常结构（概要）\n本节详表见 §9。\n\n"
                         "## 9. 状态与异常结构（详表）", 1).rstrip('\n')
            + "\n" + _BADST) == 1)
    # ===== 2026-09-09 第五轮独立复核：判据②③④ 六处放行 =====
    _ST = '## 6. 状态与异常结构\n'
    def _swap_states(tbl):
        """只替换状态节的表，其余保持正例。"""
        return re.sub(r'(?ms)^## 6\. 状态与异常结构\n.*', _ST + tbl, GOOD)
    chk('反例④a：**两列**状态表里的 Skeleton → 1（行正则要 4 个竖线时整行不查）',
        run(_swap_states('| 页面 | 状态 |\n|---|---|\n| 列表页 | Skeleton |\n')) == 1)
    chk('反例④b：状态格不含斜杠的 Pending → 1（白名单量程不该由分隔符决定）',
        run(_swap_states('| 页面 | 状态 | 出路 |\n|---|---|---|\n'
                         '| 列表页 | Pending | 重试 |\n')) == 1)
    for _w in ('加载骨架', '灰态'):
        chk('反例④c：中文变体「%s」→ 1（黑名单只 3 词时全逃）' % _w,
            run(_swap_states('| 页面 | 状态 | 出路 |\n|---|---|---|\n'
                             '| 列表页 | %s/empty | 重试 |\n' % _w)) == 1)
    chk('正例④：合法状态列 empty/loading/error → 0（收紧不许误伤）',
        run(_swap_states('| 页面 | 状态 | 出路 |\n|---|---|---|\n'
                         '| 列表页 | empty/loading/error | 重试 |\n')) == 0)
    # ⭐ 与 research-gate 决策域那条**同型**（占位符全算填了），同一天两处各犯一次。
    chk('反例③：权限矩阵整表 TBD → 1（只验非空＝占位符照过）',
        run(re.sub(r'(?ms)(^## [^\n]*权限矩阵[^\n]*\n)(.*?)(?=^## )',
                   r'\1| 角色 | 读 | 写 |\n|---|---|---|\n| TBD | TBD | TBD |\n', GOOD)) == 1)
    # ⭐ 出路必须由**任务名之外**的内容给出 —— 不能自己给自己背书。
    # ⚠️ 这两条**第一版用错了出路行的文本**（抄了 tests/fixtures 那份，而自证用的是 GOOD）——
    #   替换没命中 ⇒ 夹具其实一个字没改，测的是**没改过的正例**。
    #   ⭐ 「一条永远不会红的反例，和没有这条反例是一回事」（本文件上面早写过同一句），
    #     而这次是自证当场把它拦下来的。⇒ 断言替换真的发生了。
    _NOEXIT = GOOD.replace(_EXIT_LINE, '')
    chk('基线：删掉出路行 → 1',  run(_NOEXIT) == 1)
    chk('反例②：删出路 + 任务名自带「失败」二字 → 仍 1（任务名不算出路）',
        run(re.sub(r'任务[：:][^\n]*', '任务：处理失败订单', _NOEXIT, count=1)) == 1)
    # ===== 2026-09-09 第五轮：判据⑤ 大小写 + 否定豁免被反向利用 =====
    for _t in ('postgresql', 'REDIS', 'MySql', 'Postgres'):
        chk('反例⑤：技术栈词写作 %s → 1（无 re.I 时只有一种拼法守得住）' % _t,
            run(GOOD + '\n技术选型：%s 主库。\n' % _t) == 1)
    chk('反例⑤：否定前缀反向利用「非 Redis 不可」→ 1（豁免不许成为写技术选型的通道）',
        run(GOOD + '\n缓存非 Redis 不可。\n') == 1)
    chk('反例⑤：「⛔MySQL 必须开主从」→ 1（有 ⛔ 但整句是肯定要求）',
        run(GOOD + '\n⛔MySQL 必须开主从。\n') == 1)
    chk('正例⑤：教学句「非表结构」→ 0（模板自己就这么写，不许判红）',
        run(GOOD + '\n关键字段（业务含义，非表结构）。\n') == 0)
    chk('正例⑤：IA 概念「字母索引页」→ 0（换技术栈答案不变，不是技术词）',
        run(GOOD + '\n列表页提供字母索引页。\n') == 0)
    # ===== 2026-09-09 第五轮独立复核：字面量定位段（两个方向都出事）=====
    # ⚠️ 这两条的**前置条件是正文里多一句话**，而此前 11 条 ④ 用例
    #   没有一条动过节标题或前言 —— ⭐ 用例只覆盖了作者想到的形状。
    _XREF = '\n本文的状态与异常结构一节见文末。\n'
    _BAD_STATE = '| 详情页 | 骨架屏/禁用态 | 无 |\n'
    chk('基线：违例写在既有状态节里 → 1',
        run(GOOD.rstrip('\n') + '\n' + _BAD_STATE) == 1)
    chk('反例④x：只多一句交叉引用 → 仍 1（旧实现整条判据静默失效，报「五判据全过」）',
        run(GOOD.replace('# 产品结构', '# 产品结构' + _XREF, 1).rstrip('\n')
            + '\n' + _BAD_STATE) == 1)
    # ⭐⭐ 这条**正例**比上面那条反例更贵：旧实现让一份完全合规的文档
    #   因为一行目录同时报 ①②③ 三条错，而三样东西全都在。
    #   作者拿到三条明显错误的报错，最可能的反应是「这门坏了」然后整体不再信它。
    chk('正例：合规文档 + 一行目录 → 0（⛔ 不许因为目录提到节名就报三条假错）',
        run(GOOD.replace('# 产品结构',
                         '# 产品结构\n\n本文分为：信息架构、关键任务流、权限矩阵三部分。\n',
                         1)) == 0)
    chk('反例①：无 F-xx → 1', run(GOOD.replace('F-01 智能挑片 · F-02 相似归组', '智能挑片')) == 1)
    chk('反例②：任务流无失败出路 → 1', run(GOOD.replace('       ↳ 失败：AI 置信度低，回到人工挑片\n', '')) == 1)
    _EXIT = '       ↳ 失败：AI 置信度低，回到人工挑片\n'
    _T2_NOEXIT = _EXIT + '任务：批量导出成片\n入口 → 选目标 → 导出完成\n'
    _T2_EXIT = _T2_NOEXIT + '       ↳ 中断：断网后可续传\n'
    chk('反例②b：两条任务只有一条有出路 → 1（曾经整段一个失败词替所有任务背书）',
        run(GOOD.replace(_EXIT, _T2_NOEXIT)) == 1)
    chk('正例②c：两条任务各有出路 → 0（逐条判不是过度严判）',
        run(GOOD.replace(_EXIT, _T2_EXIT)) == 0)
    # 🚨 2026-09-09：段分隔符曾是未锚定行首的 '## '，行内出现 `## ` 即提前截断。
    #   ⚠️ 本注释 09-09 晚经独立复核**订正**：原文说旧实现「在下面这份产物上同时犯
    #   假阳性+漏报两个错」——**下面这份夹具只能证明漏报那一半**（标记加在 ↳ 行末尾，
    #   旧实现在它上面 rc=0，什么都没点名）。假阳性要把 `## ` 放在 ↳ **之前**才触发，
    #   那是另一份夹具。⭐ 记这一笔是因为**叙述比夹具能证明的更强，等于在注释里造假**；
    #   用例本身仍承重（回退旧分隔符后 rc 从 1 变 0）。
    _INLINE = _EXIT.replace('\n', '（备注：文档里用 ## 表示二级标题）\n')
    chk('反例②d：段内含行内「## 」且其后有无出路任务 → 1（分隔符必须锚定行首）',
        run(GOOD.replace(_EXIT, _INLINE + '任务：批量导出成片\n入口 → 选目标 → 导出完成\n')) == 1)
    chk('正例②e：段内含行内「## 」但每条任务都有出路 → 0（不许因行内标记误伤）',
        run(GOOD.replace(_EXIT, _INLINE)) == 0)
    chk('反例③：权限矩阵无真实行 → 1', run(GOOD.replace('| 删除原片 | ✓ | ✗ | ✗ |\n', '')) == 1)
    chk('反例④：状态列写 Skeleton → 1', run(GOOD.replace('empty/loading/error', 'Skeleton/loading')) == 1)
    # 🚨 2026-09-09：④ 曾用固定字符窗口 md[i:i+1200] —— 状态表长于窗口时，
    #   后面的行**静默逃过检测**（实测报「五判据全过」）。窗口类判据必须有一条
    #   「靶点落在窗口之外」的反例，否则永远只测到窗口内那一半。
    _LONG = ''.join('| 对象%02d | Empty / Error | 重试 |\n' % k for k in range(1, 46))
    chk('反例④b：状态段超 1200 字符、非法状态落在窗口外 → 1（截断漏检＝假绿）',
        run(GOOD.rstrip() + '\n' + _LONG + '| 对象99 | Skeleton | 无 |\n') == 1)
    chk('正例④c：状态段超 1200 字符但全合法 → 0（放宽窗口不许变成乱报）',
        run(GOOD.rstrip() + '\n' + _LONG) == 0)
    chk('反例⑤：出现技术栈词 → 1', run(GOOD.replace('重试或人工模式', '重试（Redis 缓存失效时）')) == 1)
    # 🚨 2026-09-09 二轮复核：整串套 `\b`，而 `\b` 在 CJK 之间不成立 ⇒
    #   4 个中文技术词一次都不可能命中（唯一的反例用的是 ASCII 的 Redis，
    #   于是这条判据「有反例、反例也红」，守的却只有 ASCII 那一半）。
    chk('反例⑤b：中文技术栈词 → 1（`\\b` 在 CJK 之间不成立，此前整类死判据）',
        run(GOOD.replace('重试或人工模式', '重试（系统采用微服务架构时走降级）')) == 1)
    # STATE_OK 此前是死码：docstring 承诺「状态只用①类」，实现只黑名单 skeleton/disabled
    chk('反例④c：状态列出现 Pending（不在①类白名单里）→ 1',
        run(GOOD.replace('empty/loading/error', 'empty/Pending/error')) == 1)
    # 🚨 2026-09-09 三轮复核：打开白名单后抽取器 `[A-Za-z]+` 引入四类误伤 ——
    #   ⭐ 黑名单能容忍抽取噪声，白名单不能。四条正例把它们钉住：
    chk('正例④d：表头写 | Object | State | → 0（表头不是数据行）',
        run(GOOD.replace('| 对象/页面 |', '| Object | State |', 1)) == 0)
    chk('正例④e：状态格写 N/A（无远程数据）→ 0（N/A 是合法三态之一）',
        run(GOOD.rstrip() + '\n| 设置页 | N/A（无远程数据） | 无 |\n') == 0)
    chk('正例④f：括号里的英文说明不算状态名 → 0',
        run(GOOD.rstrip() + '\n| 详情页 | empty/loading/error（see UI spec） | 重试 |\n') == 0)
    chk('正例⑤c：「字母索引页」是 IA 概念不是技术栈词 → 0',
        run(GOOD.rstrip() + '\n列表页提供字母索引页，便于快速定位。\n') == 0)
    chk('反例⑤d：「建立索引」是技术决定 → 1',
        run(GOOD.rstrip() + '\n为提升查询性能需要建立索引。\n') == 1)
    # 🚨 2026-09-09 第四轮复核：上一批为消除误伤加的三个豁免**没有边界**，
    #   五种一步编辑距离的变体全部逃逸。⭐ 根因是**把「消除误伤」做成了「整段不看」**。
    #   ⇒ 黑名单全行搜（含括号内、含中文）、白名单只查状态枚举格。五种各钉一条：
    chk('反例④g：括号包一层 (Skeleton) → 1',
        run(GOOD.rstrip() + '\n| 列表页 | empty/loading(Skeleton) | 重试 |\n') == 1)
    chk('反例④h：全角括号（Skeleton、Pending）→ 1',
        run(GOOD.rstrip() + '\n| 列表页 | empty（Skeleton、Pending） | 重试 |\n') == 1)
    chk('反例④i：N/A、Skeleton 前缀 → 1（N/A 豁免不许连累整行）',
        run(GOOD.rstrip() + '\n| 列表页 | N/A、Skeleton | 重试 |\n') == 1)
    chk('反例④j：状态写在第 3 列 → 1（不许只看第 2 列）',
        run(GOOD.rstrip() + '\n| 列表页 | 说明 | empty/Skeleton/error |\n') == 1)
    chk('反例④k：中文状态名「骨架屏」→ 1（只认 ASCII 等于半个判据）',
        run(GOOD.rstrip() + '\n| 列表页 | 空态/骨架屏/失败 | 重试 |\n') == 1)
    # 反向：项目自己的模板必须过得了自己的门（除空占位符外）
    chk('正例⑤e：「非表结构」是教学语句不是技术栈词 → 0',
        run(GOOD.rstrip() + '\n| 对象 | 关键字段（业务含义，非表结构） | 谁创建 |\n') == 0)
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'no.md')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', rc == 2)
    print('\n%s' % ('✅ 自证通过：这道门会出声' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print('UNABLE: 门禁自身异常（不是「有发现」）：%s: %s' % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or ''); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    _main_guarded(_entry)
