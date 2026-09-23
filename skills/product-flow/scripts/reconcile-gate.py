#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨产物对账门 G1 / G2 / G3 —— M4 的机器实现。

为什么需要它：
  M4 被本 skill 称为「最有价值的一道机制」，但四道门里长期只有 G4（需求↔用例）有工具，
  **G1/G2/G3 全靠人工逐条核**，而 G2/G3 恰恰是 SKILL.md 自己列的「最容易出事的三个交接口」里的两个。
  `reconcile-gate.md` 还专门写了一节「对账工具自己也要先自证」—— 而那三道门根本没有工具可自证。

判据永远是**双向**的：
  正向漏＝上游有下游没有（少做了，看得见）
  反向漏＝下游有上游没有（多做了没人要的，**永远不会被测试覆盖，也永远没人负责**）

用法:
  reconcile-gate.py G1 <PRD.md>
  reconcile-gate.py G2 <PRD.md> <demo.html> [--exempt <不演示清单.md>]
  reconcile-gate.py G3 <demo.html> <figma-link.md>
  reconcile-gate.py --self-test
退出码: 0=双向通过 1=有漏 2=跑不了（输入缺失/解析不出，绝不折叠成 0）

═══ 产物必须遵守的锚点契约（本 skill 是 SOP，下游产物照此执行）═══
  PRD    第四章小节标题：`### M: <模块> / F-xx: <名>`
         附件 A 每条：`## FR-### 所属 F-xx`
  demo   每个场景一个容器：<section data-scene="f01-empty" data-fr="FR-011,AC-1">
         不演示的：在 <!--不演示 FR-012 理由:纯后端计时--> 或 --exempt 清单里显式登记
  Figma  图层命名：`F-01/pc/empty`，回灌到 figma-link.md：`F-01 | pc | empty | <链接#node-id>`
         ⛔ 三元键 `功能+端+状态` 逐字对账；**状态段用英文 slug**，中文展示名另写在链接文字里。
  ⚠️ 契约不是建议。**锚点缺失时本门禁报「跑不了(2)」，不报通过** —— 没有锚点的产物无法对账。
"""
import io, os, re, sys, tempfile, subprocess
import _prd_parse
import _scene_parse
# 场景解析统一走 _scene_parse（2026-09-01 抽出，与 demo-anchor-gate 共用，不再各写一份）
scenes = _scene_parse.scenes
baseline_scenes = _scene_parse.baseline_scenes
load_scenes = _scene_parse.load_scenes

# 「实现行为型」FR 的指纹：验收标准指向一个测试，而不是描述用户能看到什么。
# 反向提取型 PRD（产品已上线、需求从测试反推）整份都是这种。
IMPL_FR = re.compile(r'可由\s*[`\s]*[\w./-]*test[\w./-]*[`\s]*\s*验证')

def read(p):
    try: return io.open(p, encoding='utf-8').read()
    except Exception as e:
        print("UNABLE: 读不到 %s (%s)" % (p, e), file=sys.stderr); sys.exit(2)

def feats(prd):
    m = re.search(r'^\s*\|\s*ID\s*\|.*功能名称.*$', prd, re.M)
    if not m: return []
    out, lines = [], prd[m.end():].split('\n')
    for ln in lines[1:]:
        if not ln.strip().startswith('|'): break
        c = re.match(r'^\s*\|\s*(F-\d+)\s*\|', ln)
        if c: out.append(c.group(1))
    return out

def ch4(prd):
    return dict((m.group(1), m.group(0)) for m in re.finditer(r'(?m)^### M: .*?/ (F-\d+): .*$', prd))

def frs(prd):
    """附件 A 的 FR/NFR → 所属 F-xx；顺带收 AC 编号。

    ⚠️ 2026-08-31：本函数原先自带一份 `^##\\s*(N?FR)` 的正则，**只认二级标题**，
    在真 PRD（FR 写在 `###`）上把 25 个功能全判成「无验收标准」——假阳性 100%，
    而同一个 skill 的 prd_completeness_check 同时判「25/25 齐全」。
    两处各写各的解析器 = 两个互相矛盾的结论。现统一委托 `_prd_parse`。"""
    seg = _prd_parse.appendix(prd) or ''
    return _prd_parse.fr_owners(prd, seg), _prd_parse.ac_ids(prd, seg)

def exempt(html, extra):
    """收「不演示」登记。支持两种粒度：
       `不演示 NFR-002`        → 整条豁免
       `不演示 NFR-002/AC-1`   → **只豁免那一条验收标准**
    ⚠️ 原实现的 `[\w-]*\d+` 不含 `/`，`NFR-002/AC-1` 会被**静默截成 `NFR-002`**，
       于是「只豁免 AC-1」写出来等于「整条全豁免」—— 而写的人以为自己收窄了。
    """
    PAT = r'((?:N?FR)-[\w-]*\d+(?:\s*/\s*AC-\d+)?|AC-\d+)'
    ids = set(re.findall(r'不演示\s*' + PAT, html))
    if extra: ids |= set(re.findall(PAT, read(extra)))
    return {re.sub(r'\s*', '', x) for x in ids}

def figma_layers(txt):
    return set(re.findall(r'(F-\d+)\s*[/|｜]\s*([^\s|｜]+)\s*[/|｜]\s*([^\s|｜]+)', txt))

def emit(title, fwd, rev, extra=None):
    print("# 对账 %s" % title)
    print("正向漏 %d · 反向漏 %d%s" % (len(fwd), len(rev), (" · " + extra) if extra else ""))
    for x in fwd: print("  🔴 正向漏 %s" % x)
    for x in rev: print("  🔴 反向漏 %s  ← 无需求依据，永远不会被测试覆盖" % x)
    if not fwd and not rev: print("  ✅ 双向对账通过")
    print("\n⚠️ 逐条核过，分母是真核过的数量；「不演示/不实现」是合法结论但必须显式登记。")
    return 1 if (fwd or rev) else 0

def g1(prd_path):
    prd = read(prd_path); F = feats(prd); C = ch4(prd); FR, _ = frs(prd)
    if not F: print("UNABLE: 解析不出功能清单表", file=sys.stderr); sys.exit(2)
    if not C: print("UNABLE: 解析不出第四章小节（契约：### M: <模块> / F-xx: <名>）", file=sys.stderr); sys.exit(2)
    owned = {v for v in FR.values() if v}
    fwd  = ["%s 无第四章小节" % f for f in F if f not in C]
    fwd += ["%s 无附件 A 验收标准（下游生成不出用例）" % f for f in F if f not in owned]
    rev  = ["第四章有 %s，功能清单里没有" % f for f in C if f not in F]
    rev += ["附件 A 的 %s 所属 %s，功能清单里没有" % (k, v) for k, v in FR.items() if v and v not in F and v != '全局']
    return emit("G1 · S4→S5（功能 → 交互/验收）", fwd, rev)

def g2(prd_path, demo_path, ex=None):
    prd, html = read(prd_path), read(demo_path)
    FR, ACS = frs(prd); S = load_scenes(demo_path)
    kind = "demo" if demo_path.lower().endswith(('.html', '.htm')) else "baseline"
    if not FR: print("UNABLE: 附件 A 解析不出 FR", file=sys.stderr); sys.exit(2)
    if not S:
        # ⭐ 先判**这份 PRD 适不适用 G2**，再报「没锚点」。
        # 2026-09-01 实测 验证项目：附件 A 的 121 条里 115 条是「实现行为型」
        # （AC 写成「该行为可由 test/xxx.test.js 验证」），因为这份 PRD 是从已上线代码
        # 反向提取的。而 demo 的场景是 UI 状态 —— **两者不在一个平面上**，
        # 逐条映射只会造出「制造出来的合格」。
        # 此前这种情况只报一句通用的「没有场景锚点」，读的人会以为补个属性就行。
        n_impl = len(IMPL_FR.findall(prd))
        if FR and n_impl >= 0.7 * len(FR):
            print("UNABLE: 附件 A 的 %d/%d 条 FR 是**实现行为型**（AC = 某个测试验证），"
                  "不是用户可见需求 —— 这是**反向提取型 PRD**，G2 的契约"
                  "（每个 FR 都要有 demo 场景）对它不成立。\n"
                  "        出路二选一：① 已上线产品走 baseline 路径 —— "
                  "锁 `.product-flow/baseline.md` 后跑 `G2 <prd.md> <baseline.md>`；"
                  "② 确要用 demo，则这些 FR 必须逐条登记「不演示·理由」。\n"
                  "        ⛔ 不要为了让本门变绿而给场景硬凑 data-fr。"
                  % (n_impl, len(FR)), file=sys.stderr)
            sys.exit(2)
        print("UNABLE: %s 里没有场景锚点（demo 要 data-scene / baseline 要「场景×需求」表）"
              " —— 无锚点无法对账，不是「通过」" % kind, file=sys.stderr); sys.exit(2)
    EX = exempt(html, ex)
    covered = set()
    for _, ids in S: covered |= set(ids)
    # ⭐ AC 必须**带归属**再对账。只比全局 `AC-n` 集合时，任意一个场景标了 `AC-3`，
    #    所有 FR 的 AC-3 就都算覆盖了 —— 实测本 skill 此前正是如此，
    #    而且 `ac_ids` 的正则还认不出 `- **AC-1**`，返回空列表，
    #    于是这道名为「验收标准 → demo」的门**从来没有对过一条验收标准**。
    PAIRS = _prd_parse.ac_pairs(prd)
    # 场景内就近归属：一个场景里列出的 AC，归属于同一场景里列出的 FR
    # ⭐ 两种声明方式，**显式优先**：
    #    ① `data-fr="FR-031/AC-2"`  —— 带归属，明确说了是哪条 FR 的哪条 AC
    #    ② `data-fr="FR-031,AC-2"`  —— 就近归属，靠场景内配对推断
    #    ⚠️ ② 在一个场景列了 **多个 FR** 时会产生**笛卡尔积**：
    #    实测某项目 159 条 AC 里有 23 条只由 5 个多-FR 场景的叉乘「覆盖」，
    #    其中 5 条还同时登记着「不演示」—— 一边说没演，一边被算成演了。
    covered_pairs, declared_pairs, inferred_pairs = set(), set(), set()
    for _, ids in S:
        for i in ids:
            if '/' in i and i.split('/')[1].startswith('AC-'):
                declared_pairs.add(i)
        frs_here = [i for i in ids if i.startswith(('FR-', 'NFR-')) and '/' not in i]
        acs_here = [i for i in ids if i.startswith('AC-')]
        for f in frs_here:
            for a in acs_here: inferred_pairs.add(f + '/' + a)
    covered_pairs = declared_pairs | inferred_pairs
    # ⛔ 显式的「不演示」与推断出来的「已覆盖」冲突时，报矛盾 —— 不许静默当成通过。
    #    显式声明（无论哪一边）都比推断有力：一边写着没演，一边靠叉乘算成演了，两者必有一错。
    conflict = sorted((inferred_pairs - declared_pairs) & EX)
    def ac_ok(f, a):
        return (f + '/' + a) in covered_pairs or f in EX or (f + '/' + a) in EX
    by_fr = {}
    for f, a in PAIRS: by_fr.setdefault(f, []).append(a)
    # ⭐ FR 本身不必再单独要一个场景：它的每条 AC 都已覆盖或豁免时，它就落地了。
    #    否则会逼人给场景加一个纯为过门禁的 FR 标签（那正是「为了变绿而凑锚点」）。
    fwd = ["%s 无 demo 场景，也未登记「不演示·理由」" % k
           for k in list(FR)
           if k not in covered and k not in EX
           and not (by_fr.get(k) and all(ac_ok(k, a) for a in by_fr[k]))]
    fwd += ["%s/%s 无 demo 场景，也未登记「不演示·理由」" % (f, a)
            for f, a in PAIRS if not ac_ok(f, a)]
    fwd += ["%s 既登记了「不演示」，又被场景叉乘算成已覆盖 —— 两者必有一错" % x
            for x in conflict]
    # ⚠️ 反向检查也要认**带归属**的写法：`FR-011/AC-1` 里的 FR 部分同样是可反查的需求。
    #    只比裸 id 的话，一个场景全用带归属写法反而会被判成「无需求依据」。
    def traceable(ids):
        if set(ids) & (set(FR) | set(ACS)): return True
        return any('/' in i and i.split('/')[0] in FR for i in ids)
    rev = ["场景 %s 没有反查得到的需求（demo 看 data-fr / baseline 看需求列）" % sid
           for sid, ids in S if not ids or not traceable(ids)]
    extra = "显式豁免 %d" % len(EX) if EX else ""
    if PAIRS:
        # ⭐ 把「声明的」与「推断的」分开报：推断出来的覆盖比声明出来的弱，
        #    数字混在一起会让人以为每一条都被明确说过。
        nd = len(declared_pairs & {f + '/' + a for f, a in PAIRS})
        ni = len((inferred_pairs - declared_pairs) & {f + '/' + a for f, a in PAIRS})
        extra += ("%sAC 覆盖：声明 %d · 推断 %d" % (" · " if extra else "", nd, ni))
    return emit("G2 · S5→S6（验收标准 → demo）", fwd, rev, extra or None)

def g3(demo_path, figma_path):
    """S6→S7 逐**场景**对账。

    ⚠️⚠️ 2026-08-31 修（外部评审揪出）：此前只把场景 ID 里的 `f01` 提出来，
    和 Figma 的 `F-01` 比 —— 判的是「F-01 有没有**至少一张**画面」。
    ⭐⭐ **于是 F-01 有空态/加载/错误/无权限十个场景，而 Figma 只有一张
    `F-01|PC|空态`，它照样通过** —— 承诺的「每个场景都有对应画面和状态」
    退化成了功能级对账，**而状态恰恰是最容易在交接时丢掉的东西**。

    现在按 `f01-empty` → `(F-01, empty)` 逐场景比对图层的第三段（状态）。
    """
    fg = read(figma_path)
    S = load_scenes(demo_path); L = figma_layers(fg)
    if not S: print("UNABLE: 输入里无场景锚点（demo 要 data-scene / baseline 要场景表）",
                    file=sys.stderr); sys.exit(2)
    if not L:
        print("UNABLE: figma-link 里解析不出 `F-xx | 端 | 状态` 三段图层名 —— 无命名即无法对账",
              file=sys.stderr); sys.exit(2)

    def split(sid):
        """`f01-pc-empty` / `f01-empty` → (功能, 端, 状态)。

        ⚠️⚠️ 2026-08-31 二修（外部评审）：上一版的键是 **(功能, 状态)**，
        **把「端」丢了** —— 于是 PC 与移动端同一功能同一状态，
        **只要有一张稿就通过**，而双端产品恰恰最需要分别设计。
        ⭐ 端缺省时按 `*` 处理：`*` 与任何端都匹配（单端产品不必写端）。
        """
        m = re.match(r'[Ff]-?(\d+)[-_](pc|web|desktop|mobile|m|h5)[-_](.+)$', sid.strip(), re.I)
        if m:
            return ("F-%02d" % int(m.group(1)), m.group(2).lower(), m.group(3).lower())
        m = re.match(r'[Ff]-?(\d+)[-_](.+)$', sid.strip())
        return ("F-%02d" % int(m.group(1)), "*", m.group(2).lower()) if m else None

    bad_id = [sid for sid, _ in S if not split(sid)]
    if bad_id:
        print("UNABLE: 场景 ID 不符 `fNN[-端]-<状态>` 命名，无法逐场景对账：%s"
              % "、".join(sorted(bad_id)[:6]), file=sys.stderr); sys.exit(2)

    def norm_end(e):
        e = (e or "").strip().lower()
        return {"pc": "pc", "web": "pc", "desktop": "pc",
                "移动端": "mobile", "手机": "mobile", "m": "mobile", "h5": "mobile"}.get(e, e)

    scene = {split(sid) for sid, _ in S}
    layer = {(f, norm_end(e), st.strip().lower()) for f, e, st in L}

    def covered(f, e, st):
        return any(lf == f and lst == st and (e == "*" or le == "*" or le == e)
                   for lf, le, lst in layer)

    fwd = ["场景 %s/%s/%s 在 Figma 里没有对应图层（**状态在交接时丢掉，研发到时会自己编**）"
           % (f, e, st) for f, e, st in sorted(scene) if not covered(f, e, st)]
    # ⭐ 反向也走**同一把三元键**：此前只比功能，于是 Figma 多出一个状态不会报错。
    rev = ["Figma 有 %s/%s/%s 图层，输入里没有对应场景（**稿子里多出来的状态没人验收**）"
           % (f, e, st) for f, e, st in sorted(layer)
           if not any(sf == f and sst == st and (se == "*" or e == "*" or se == e)
                      for sf, se, sst in scene)]
    return emit("G3 · S6→S7（逐场景 → 设计稿状态）", fwd, rev)


# ------------------------------------------------------------------ M8 自证
PRD_OK = """| ID | 功能名称 | 简介 | 优先级 | 载体 | AI? | 成本/规模 |
|---|---|---|---|---|---|---|
| F-01 | 导入 | x | P0 | 两端 | 否 | M |

### M: 素材 / F-01: 导入
| 页面 | 设计稿 | 逻辑 |
|---|---|---|
| a | b | - c |

# 附件 A · 验收标准
## FR-011 所属 F-01 MUST
- AC-1 条件
# 附件 B · 假设
"""
BASELINE_OK = '''# 真实程序基线清单

**版本** v1.2.0 · **构建号** 4417 · **抓取日期** 2026-08-31

| 场景ID | 对应需求 | 进入路径 | 截图 | 抓取版本 |
|---|---|---|---|---|
| f01-empty | FR-011, AC-1 | 菜单>导入 | s0.png | v1.2.0 |
| f01-loading | FR-011, AC-1 | 菜单>导入 | s1.png | v1.2.0 |
'''

DEMO_OK = ('<section data-scene="f01-empty" data-fr="FR-011,AC-1"></section>'
           '<section data-scene="f01-loading" data-fr="FR-011,AC-1"></section>')
FIG_OK = ("F-01 | PC | empty | https://figma.com/x#node-id=1\n"
          "F-01 | PC | loading | https://figma.com/x#node-id=2\n")
# ⚠️ 状态段此前写「空态」而场景 ID 是 `f01-empty` —— 旧 G3 只比功能族所以看不出来。
#    改成逐场景后立刻暴露：**图层名的状态段必须和场景 ID 的状态段用同一个字符串。**

def _msg_has(*a, **kw):
    """跑一次并检查 stderr 里有没有指定措辞 —— 判「理由对不对」，不只判退出码。"""
    needle = kw.pop('needle')
    r = subprocess.run([sys.executable, os.path.abspath(__file__)] + list(a),
                       capture_output=True, text=True)
    return needle in (r.stderr or '')


def self_test():
    t = tempfile.mkdtemp(prefix="rg-")
    def w(n, c):
        p = os.path.join(t, n); io.open(p, 'w', encoding='utf-8').write(c); return p
    def run(*a):
        return subprocess.call([sys.executable, os.path.abspath(__file__)] + list(a),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases = [
        ("G1 正例",            lambda: run('G1', w('a.md', PRD_OK)), 0),
        # ⚠️ 反例要造对：把唯一的第四章小节删掉 → 门禁应报「跑不了(2)」而不是「有漏(1)」，
        #    因为整章缺失时无法区分「漏了」和「这份文档还没写到第四章」。
        #    真正的正向漏，是**有功能但那一个功能没有小节** —— 所以反例要加第二个功能。
        ("G1 正向漏(某功能缺小节)", lambda: run('G1', w('b.md', PRD_OK.replace(
            "| F-01 | 导入 | x | P0 | 两端 | 否 | M |",
            "| F-01 | 导入 | x | P0 | 两端 | 否 | M |\n| F-02 | 编辑 | y | P1 | 两端 | 否 | S |"))), 1),
        ("G1 整章缺失 → 报 2 不报 1", lambda: run('G1', w('b2.md', PRD_OK.replace('### M: 素材 / F-01: 导入', '### 别的标题'))), 2),
        ("G1 反向漏(第四章多出)", lambda: run('G1', w('c.md', PRD_OK.replace('### M: 素材 / F-01: 导入',
                                  '### M: 素材 / F-01: 导入\n### M: 素材 / F-99: 野生功能'))), 1),
        ("G2 正例",            lambda: run('G2', w('d.md', PRD_OK), w('d.html', DEMO_OK)), 0),
        ("G2 正向漏(FR 没场景)", lambda: run('G2', w('e.md', PRD_OK), w('e.html', '<section data-scene="x" data-fr="AC-1"></section>')), 1),
        ("G2 反向漏(场景无来源)", lambda: run('G2', w('f.md', PRD_OK), w('f.html', DEMO_OK + '<section data-scene="ghost" data-fr=""></section>')), 1),
        ("G2 豁免登记后转绿",    lambda: run('G2', w('g.md', PRD_OK),
                                  w('g.html', '<!--不演示 FR-011 理由:纯后端--><section data-scene="x" data-fr="AC-1"></section>')), 0),
        ("G3 正例",            lambda: run('G3', w('h.html', DEMO_OK), w('h.md', FIG_OK)), 0),
        ("G3 正向漏(稿缺状态)",  lambda: run('G3', w('i.html', DEMO_OK), w('i.md', "F-99 | pc | empty | x\n")), 1),
        ("无锚点必须报 2 不报 0", lambda: run('G2', w('j.md', PRD_OK), w('j.html', '<div>没有锚点</div>')), 2),
        # ⭐ 反向提取型 PRD：同样是 2，但**理由必须不同** —— 泛泛一句「没有锚点」会让人
        #    以为补个属性就行，实际是 G2 对这类 PRD 根本不适用（2026-09-01 验证项目 实测 115/121）。
        ("反向提取型 PRD 要给专门的理由，不能只说没锚点",
         lambda: 0 if _msg_has('G2', w('k.md', PRD_OK.replace(
             '## FR-011 所属 F-01 MUST\n- AC-1 条件',
             '## FR-011 所属 F-01 MUST\n- AC-1 该行为可由 `test/x.test.js` 验证\n'
             '## FR-012 所属 F-01 MUST\n- AC-1 该行为可由 `test/y.test.js` 验证')),
             w('k.html', '<div>没有锚点</div>'), needle='反向提取型') else 1, 0),
        ("普通 PRD 无锚点时**不得**误报成反向提取型",
         lambda: 0 if _msg_has('G2', w('l.md', PRD_OK), w('l.html', '<div>没有锚点</div>'),
                               needle='没有场景锚点') else 1, 0),
        ("文件不存在必须报 2",    lambda: run('G1', os.path.join(t, 'nope.md')), 2),
        # ⭐ baseline 路径（已上线产品）必须单独造正反例：
        #    文档从一开始就宣称「G2/G3 可换 baseline.md」，而脚本里一行 baseline 代码都没有。
        #    ⚠️ 只跑 demo 用例的话，**这条路径全绿而它根本不存在** —— 声称≠实际。
        ("G2 baseline 正例",     lambda: run('G2', w('k.md', PRD_OK), w('k2.md', BASELINE_OK)), 0),
        # ⚠️ 首版这条造错了：只删掉第二行，而第一行仍然覆盖着 FR-011 —— 于是「什么都没漏」。
        #    ⭐ 反例必须真的制造出那个缺口，删掉一行不等于删掉一条覆盖。
        ("G2 baseline 正向漏",   lambda: run('G2', w('l.md', PRD_OK), w('l2.md',
            BASELINE_OK.replace("FR-011, AC-1", "AC-1"))), 1),
        ("G2 baseline 反向漏",   lambda: run('G2', w('m.md', PRD_OK), w('m2.md', BASELINE_OK +
            "| f09-ghost |  | 某处 | s9.png | v1.2.0 |\n")), 1),
        ("G2 baseline 无场景表报 2", lambda: run('G2', w('n.md', PRD_OK),
            w('n2.md', "# 基线清单\n版本 v1.2.0\n没有表。\n")), 2),
        ("G3 baseline 正例",     lambda: run('G3', w('o2.md', BASELINE_OK), w('o3.md', FIG_OK)), 0),
        # ⭐⭐ 这条是本次修复的核心反例：**功能有画面，但少一个状态**。
        #    旧 G3 只比功能族 → F-01 有 empty 一张就通过，loading 丢了没人知道。
        #    ⚠️ **状态恰恰是最容易在 S6→S7 交接时丢掉的东西。**
        ("G3 功能有画面但状态缺（旧版会放过）",
         lambda: run('G3', w('p5.md', BASELINE_OK),
                     w('p6.md', "F-01 | PC | empty | https://figma.com/x#node-id=1\n")), 1),
        # ⭐⭐ 端维度：上一版的键是 (功能,状态)，**把端丢了** —— 双端产品只要有一张稿就通过。
        ("G3 双端只给了一端的稿（旧版会放过）",
         lambda: run('G3',
                     w('q1.html', '<section data-scene="f01-pc-empty" data-fr="FR-011"></section>'
                                  '<section data-scene="f01-mobile-empty" data-fr="FR-011"></section>'),
                     w('q2.md', "F-01 | pc | empty | https://figma.com/x#node-id=1\n")), 1),
        ("G3 双端两张稿都在",
         lambda: run('G3',
                     w('q3.html', '<section data-scene="f01-pc-empty" data-fr="FR-011"></section>'
                                  '<section data-scene="f01-mobile-empty" data-fr="FR-011"></section>'),
                     w('q4.md', "F-01 | pc | empty | https://figma.com/x#node-id=1\n"
                                "F-01 | mobile | empty | https://figma.com/x#node-id=2\n")), 0),
        ("G3 反向：稿里多出一个状态（旧版会放过）",
         lambda: run('G3', w('q5.html', DEMO_OK.replace(
             '<section data-scene="f01-loading" data-fr="FR-011,AC-1"></section>', '')),
                     w('q6.md', FIG_OK)), 1),
        # 🆕 2026-09-05 `--unable` 实测：「figma-link 里解析不出三段图层名」这个出口
        #    从没被触发过 —— 自证的 figma-link 永远是合法的。
        ("G3 figma-link 里一条三段图层名都没有 → 报 2",
         lambda: run('G3', w('p8.md', BASELINE_OK),
                     w('fl_bad.md', "# 图层清单\n随便写点东西，没有 F-xx | 端 | 状态\n")), 2),
        ("G3 场景 ID 不合 fNN- 命名 → 报 2 不报 0",
         lambda: run('G3', w('p7.md', BASELINE_OK.replace("f01-loading", "随便起的名字")),
                     w('p8.md', FIG_OK)), 2),
    ]
    ok = True
    print("M8 自证 —— 正例绿 / 每类漏各造一个反例必红 / 无锚点与缺输入必须报 2 不报 0\n")
    for name, fn, want in cases:
        got = fn(); good = got == want; ok &= good
        print("  %s %-24s 期望 %d 实得 %d" % ("✅" if good else "❌", name, want, got))
    print("\n%s" % ("✅ 三道对账门都会出声" if ok else "❌ 自证失败，先修门禁"))
    return 0 if ok else 1


# ── 意外异常必须报「跑不了」，不许和「有发现」共用退出码 ────────────────
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
        #    2026-09-03 实测：同一个 skill 的 element-identity-gate 因为这一行
        #    `[x for x in argv if not x.startswith('--')]`，把误写的 `--spec/--demo`
        #    当成「以 -- 开头」滤掉，于是半个门禁从没跑过而一路报绿。
        #    本门禁的位置参数恰好和常见误写的取值顺序一致 —— **那是碰巧对了，不是没有风险**：
        #    顺序一换（`--demo X --prd Y`）就会把 demo 当 PRD 解析。
        KNOWN = {'--help', '--exempt', '--json', '--self-test', '--list-rules'}
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
        ei = sys.argv.index('--exempt') if '--exempt' in sys.argv else -1
        ex = sys.argv[ei + 1] if ei > -1 and len(sys.argv) > ei + 1 else None
        if ex and ex in a: a.remove(ex)   # ⭐ 否则 --exempt 的值留在位置参数里,len(a)==4≠G2要的3,豁免通道必 UNABLE(照 spec-sync-gate.py:509)
        if not a: print(__doc__); sys.exit(2)
        g = a[0].upper()
        try:
            if g == 'G1' and len(a) == 2: sys.exit(g1(a[1]))
            if g == 'G2' and len(a) == 3: sys.exit(g2(a[1], a[2], ex))
            if g == 'G3' and len(a) == 3: sys.exit(g3(a[1], a[2]))
        except SystemExit: raise
        except Exception as e:
            print("UNABLE: %s" % e, file=sys.stderr); sys.exit(2)
        print(__doc__); sys.exit(2)
    _main_guarded(_entry)
