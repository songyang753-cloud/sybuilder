#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上线后复盘门禁（S10 出场）。

为什么需要它：
  S10 的前身此前是全流程里**唯一没有执行契约**的那个（5 行、零 reference、零模板、零门禁），
  于是它最容易退化成一张数据报表——填满实测值，却不产生任何决定。

  ⛔ 一份只有实测值、没有决定的 retro 不算跑过 S10。

⚠️ 诚实边界：它查「有没有决定、四本账有没有结算、样本够不够、
   因果性有没有诚实声明」，**查不出「这个决定对不对」**——那要靠人。

用法: retro-gate.py <retro.md> [--json]  |  --self-test
退出码: 0=通过 1=有缺口 2=跑不了
"""
import io, os, re, sys, json, tempfile, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import from_line_containing   # noqa: E402  段落定位的唯一正本

DECISIONS = ("继续", "扩大", "调整", "停止")


def tables(md):
    """把所有 markdown 表的数据行按表分组返回。"""
    out, cur = [], None
    for ln in md.splitlines():
        t = ln.strip()
        if t.startswith('|'):
            cells = [c.strip() for c in t.strip('|').split('|')]
            if set(''.join(cells)) <= set('-: '):
                continue
            if cur is None:
                cur = {"head": cells, "rows": []}
            else:
                cur["rows"].append(cells)
        else:
            if cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return out


def find_tbl(tbs, *kw):
    for t in tbs:
        h = ''.join(t["head"])
        if all(k in h for k in kw): return t
    return None


def checked(seg, label):
    """判断某个选项是否被勾上（☑ / [x] / **加粗** 都算）。"""
    m = re.search(r'[☑✅]\s*%s|\[x\]\s*%s|\*\*%s\*\*' % (label, label, label), seg)
    return bool(m)


def check(path, as_json=False):
    if not os.path.isfile(path):
        print("跑不了：找不到 %s" % path, file=sys.stderr); return 2
    md = io.open(path, encoding='utf-8', errors='replace').read()
    if '复盘' not in md and 'retro' not in md.lower():
        print("跑不了：这看起来不是一份 retro", file=sys.stderr); return 2
    tbs = tables(md)
    f = []

    # 1 · 必须有一个被勾上的决定
    if not any(checked(md, d) for d in DECISIONS):
        f.append(("no-decision", "没有勾选任何决定（继续/扩大/调整/停止）——"
                                 "只有实测值没有决定的 retro 不算跑过 S10"))
    # 1b · 选「继续」且带新观察期，必须写转停止条件
    if checked(md, "继续") and re.search(r'新观察期', md):
        # 锚到下一个标题，不用 300 字符窗口（同上）
        # 🚨 2026-09-09 第五轮：`split('新观察期', 1)[1]` 从**词的中间**切开 ——
        #   正文里提一次即错位。⇒ 锚定到含该字段的**那一行**，再切到下一个标题。
        seg = from_line_containing(md, '新观察期') or ''
        if not re.search(r'转停止的?条件\s*[:：]?\s*\S{2,}', seg.replace('<>', '')):
            f.append(("open-ended", "选了「继续」并给了新观察期，却没写转停止的条件——"
                                    "那是无限期缓刑，不是决定"))
    # 2 · 观察周期依据
    # ⚠️ 标签两侧可能有 ** 强调符：`**周期依据**：…`。首版没允许它，
    #    于是规则**从来没匹配上任何东西**，恒判缺失。
    #    ⭐⭐ 三个反例照样是红的——但它们红的原因是「规则永远匹配不上」，
    #    不是「规则抓住了缺陷」。**反例红了不等于反例在起作用。**
    #    是正例把它揪出来的：反向测试证明不了规则在按预期的理由工作。
    if not re.search(r'周期依据\**\s*[:：]\s*(?!<>)\S{2,}', md):
        f.append(("no-period-basis", "观察周期没写依据——"
                                     "「上线一个月后」是与产品无关的默认值"))
    # 3 · 样本量与测量可信度
    # 🚨 2026-09-09：判据原来只要求冒号后有**一个**非占位字符 —— 于是
    #   「样本量：0」照样通过。**零样本的复盘支撑不了任何结论**，而它是
    #   最容易出现的那种（埋点没上报、灰度没放量时，诚实填 0 反而被放行）。
    #   ⇒ 要求至少一个**非零数字**；全是 0 的（0 / 0次 / 0 个）判红并点名。
    #   ⚠️ 取值范围有两个坑，两版正则各中一个（都被自证用例当场抓住）：
    #     · 取整行 → 把**邻居字段**的数当本字段的值（「/ **最小可读样本**：2000」）⇒ 0 样本绿
    #     · 用「/」切 → 把**同字段内**的合法写法切断（「0 次崩溃 / 128 个会话」）⇒ 正确产物红
    #   ⇒ 改为显式解析：从「样本量：」取到**下一个带冒号的字段名**为止，逐段可读可验。
    def _field_value(text, name):
        # ⚠️ 2026-09-10 **构造空间穷举**（值形态 × 字段写法 × 邻居字段，72 例）
        #   扫出 6 例失配，全是同一族：字段写成**表格单元格**
        #   （`| 样本量 | 37 个 |`）时取不到值 ⇒ 合法产物被报「没填」。
        #   ⭐ 解析器只认「字段名：值」这**一种**写法，而表格是同样自然的另一种；
        #     报出来的还是「没填」这种**错误诊断**（值明明就在那里）。
        #   ⇒ 先试冒号形态，取不到再试表格行（首列是字段名，取其余单元格）。
        for _ln in text.split('\n'):
            _st = _ln.strip()
            # ⚠️⚠️ 首版写成「以 `|` 开头即当表格行、取其余单元格拼接」——
            #   于是 `| 样本量 | 0 个 |　/ **最小可读样本**：2000` 这种
            #   **表格行后面跟着邻居字段**的写法，把邻居的 2000 也取了进来，
            #   零样本被掩盖 ⇒ 穷举当场从 6 例失配变成 8 例。
            #   ⭐ 这正是本函数上方注释点名的那个病（「取整行 ⇒ 把邻居字段的数
            #     当本字段的值」）**在表格路径上的复发** —— 我一边读着那段注释，
            #     一边在新写的分支里又犯了一次。
            #   ⇒ 必须是**完整表格行**（首尾都有 `|`），且只取第二列。
            if not (_st.startswith('|') and _st.endswith('|')):
                continue
            _cells = [c.strip().strip('*`') for c in _st.strip('|').split('|')]
            if len(_cells) >= 2 and re.fullmatch(name, _cells[0]):
                return _cells[1]
        m0 = re.search(name + r'\**\s*[:：]\s*', text)
        if not m0:
            return None
        rest = text[m0.end():].split('\n')[0]
        # 下一个字段名：**加粗** 或 全角/半角分隔后紧跟 `…：`。
        # ⚠️ 必须先认「**」再认内容——第一版要求字段名 ≥2 个非星号字符，
        #    于是 `**S4 约定的最小可读样本**：2000` 没被认出来（它前面有 `**`），
        #    值一路取到邻居字段，反例里的 0 旁边就有个 2000 ⇒ 反例不红。
        nxt = re.search(r'[　/]\s*\*{2}|[　/]\s*[^\s:：]{2,}\s*[:：]', rest)
        return (rest[:nxt.start()] if nxt else rest).strip(' 　/')
    _val = _field_value(md, r'样本量')
    #   ⚠️ 占位符（`<实际>`、`<>`）算「没填」不算「填了 0」——
    #   两者的诊断完全不同，混在一起会让空模板报出「零样本」这种错误结论
    #   （元规则 gate-reads-template 当场抓到：门必须读得懂自己的空模板）。
    _is_placeholder = bool(_val is not None and re.match(r'^<[^>]*>$', _val.strip()))
    _sm = None if (_val is None or _is_placeholder) else re.match(r'(.+)', _val)
    if not _sm:
        f.append(("no-sample", "没写实际样本量"))
    elif not re.search(r'[1-9]\d*', _sm.group(1)):
        f.append(("zero-sample", "样本量里没有任何非零数字（写的是 %s）——"
                                 "零样本不是「测了但很小」，是**没测到**：结论必须降级为 "
                                 "PENDING/读不出来，⛔ 不许当成「无明显变化」"
                  % _sm.group(1).strip()[:24]))
    if not (checked(md, "埋点已验证上报正常") or checked(md, "未验证")):
        f.append(("no-measure-trust", "没声明埋点是否已验证——"
                                      "验证测量必须在验证效果之前"))
    # 3b · 上线前置回查（2026-09-08 借鉴 SDLC：rollback 是最常演练的路径）
    if not re.search(r'回滚演练记录\**\s*[:：]\s*(?!<)\S{4,}', md):
        f.append(("no-rollback-drill", "没有回滚演练记录（日期+命令+结果）——"
                                       "「有回滚脚本」≠「演练过」，从没跑过的回滚脚本是装饰"))
    # 3b2 · 数据窗口核验（借 gstack stale-base 守卫）：窗口错了，复盘会从零条数据里
    #   编出连贯叙事——零数据不会报错，是最危险的静默形态
    _wc = re.search(r'数据窗口核验\**\s*[:：]\s*(?!<)([^\n]{2,})', md)
    # 判据要的是**非零数据点**（数字+量词），不是「这一行写了字」——
    # 「0条未同步」「abcd」曾双双放行（Codex 复审实测抓出：在场检查冒充语义检查）
    if not _wc or not re.search(r'[1-9]\d*\s*(个|条|次|行|项|篇)', _wc.group(1)):
        f.append(("no-window-check", "数据窗口核验缺失或没有非零数据点（须形如「41 个提交/4210 条埋点」）——"
                                     "零数据的窗口不报错，复盘会从虚空编出连贯叙事"))
    # 3c · 持续监控档启用时，band 触发不许静音
    if re.search(r'持续监控档\**\s*[:：]?\s*(已启用|启用)', md):
        trig = re.findall(r'band 触发', md)
        if trig and not re.search(r'(intent 回流|dismiss\w*\s*[（(:：]|驳回理由)', md):
            f.append(("band-silenced", "启用了持续监控档且有 band 触发记录，"
                                       "却既无 intent 回流也无带理由的 dismissal —— 触发被静音"))
    # 4 · 四本账
    for name, kw, extra in (("目标账", ("目标 ID", "实测值"), None),
                            ("假设账", ("ASM", "结算"), None),
                            ("逃逸账", ("线上问题", "门禁"), None),
                            ("决策质量账", ("S3", "该多问"), None)):
        t = find_tbl(tbs, *kw)
        if t is None:
            f.append(("missing-%s" % name, "缺「%s」这张表" % name))
        elif not [r for r in t["rows"] if ''.join(r).replace('<>', '').strip(' |')]:
            f.append(("empty-%s" % name, "「%s」只有表头没有数据行" % name))
    # 5 · 「无明显变化」是被禁的措辞
    # ⚠️ 2026-09-04：**否定式与肯定式几乎同形**。
    #    一句「第二行写『读不出来』**而不是**『无明显变化』」是在声明自己没这么写，
    #    而 substring 判据把它当成了在这么写 —— **免责声明被当成宣称**。
    #    ⭐ 本 SOP 早就记过这一条（判断「文本有没有做某断言」时的通病），
    #      而这道规则一直没修 —— 记下来不等于治好了。
    #    收窄：紧邻的否定语（不是/而不是/别写/不许/禁止/≠）之后的出现不算。
    #    ⛔ 只认**紧邻**（6 字以内），否则「不是 X，但基本 X」这类会被放过去。
    NEG = r'(?:而?不是|不能写|别写|不许|禁止|避免|≠)[^\n]{0,6}$'
    for bad in ("无明显变化", "没有明显变化", "基本持平但原因不明"):
        hits = [m for m in re.finditer(re.escape(bad), md)
                if not re.search(NEG, md[max(0, m.start() - 24):m.start()])]
        if hits:
            f.append(("vague-nochange", "出现「%s」——样本不足要写「读不出来」，"
                                        "「没有变化」有三种来源不能混" % bad))
            break
    # 6 · 因果性诚实声明
    if not (checked(md, r'有 A/B[^☐]*') or checked(md, r'无 A/B[^☐]*')
            or re.search(r'[☑✅]\s*\*{0,2}(有|无) A/B', md)):
        f.append(("no-causality", "没做因果性诚实声明——"
                                  "没有 A/B 就只能给相关性结论，必须写明"))
    # 7 · 出口回流
    if not re.search(r'[☑✅x]\s*\]?\s*[^\n]*lessons\.md', md):
        f.append(("no-outflow", "逃逸缺陷未确认回流 lessons.md"))
    if not re.search(r'[☑✅x]\s*\]?\s*[^\n]*(下一轮|已知事实)', md):
        f.append(("no-feedforward", "被推翻的假设没有确认写进下一轮 S2/S3 输入——"
                                    "否则下一轮会把它当假设再假设一遍"))
    # ⭐ 2026-09-04 立：决策质量账的每条教训必须有**归宿**。
    #    实测起因：一条教训（「单向门拍板要同时确认前置条件谁来做」）写在了复盘里，
    #    而它指出的缺陷**仍留在被复盘的那份 PRD 里** —— 复盘没有回流到被复盘的文档。
    #    ⛔ `no-outflow` 管逃逸缺陷、`no-feedforward` 管被推翻的假设，
    #      **这一类此前没有任何东西管**。教训没有归宿，就只是一段读起来很对的话。
    dq = find_tbl(tbs, "S3", "该多问")
    if dq:
        header, rows_ = dq["head"], dq["rows"]
        home_i = next((i for i, c in enumerate(header) if re.search(r'写进哪|归宿|落到哪', c)), None)
        if home_i is None:
            f.append(("no-lesson-home", "决策质量账缺「写进哪」列——"
                                        "教训没有归宿就只是一段读起来很对的话"))
        else:
            # ⚠️ 只有**真写了教训**的行才要求归宿：
            #    「这个决定没教训」是合法结论，它不需要归宿。
            #    第一版没分这一层，把一行 `—` 的行也判红了 —— 那会逼人给「没教训」编一个归宿。
            les_i = next((i for i, c in enumerate(header) if '该多问' in c), None)
            def filled(cells, i):
                return i is not None and len(cells) > i and bool(re.sub(r'[<>\s—-]', '', cells[i]))
            blank = [r[0][:16] for r in rows_
                     if filled(r, les_i) and not filled(r, home_i)]
            if blank:
                f.append(("no-lesson-home", "决策质量账有 %d 条教训没写「写进哪」：%s"
                          % (len(blank), "、".join(blank[:3]))))

    if as_json:
        print(json.dumps({"ok": not f, "findings": [{"rule": a, "msg": b} for a, b in f]},
                         ensure_ascii=False, indent=2))
    else:
        for a, b in f: print("  ❌ [%s] %s" % (a, b))
        if not f:
            print("⚠️ 本门只验「有没有产生决定」——**不验那个决定对不对**，"
                  "也不验它有没有被执行。一份全是正确废话的 retro 同样能过。")
        print("\n%s" % ("✅ 通过：这份 retro 产生了决定" if not f else
                        "❌ %d 处缺口——⚠️ S10 不出声不会让任何东西报错，"
                        "只会让下一版重犯同样的错" % len(f)))
    return 1 if f else 0


GOOD = """# 上线后复盘 retro.md　X · v1
回滚演练记录：2026-09-01 `make rollback` 于 staging 演练成功（37s 恢复）
数据窗口核验：窗口内41个提交/4210条埋点，数据源已同步核对（2026-10-01）

**观察周期**：8/1—9/30　**周期依据**：月度产品，取两个完整使用周期
**样本量**：4210　/　**S4 约定的最小可读样本**：2000
**测量可信度**：☑ 埋点已验证上报正常

## 一、决定
**本次决定**：☑ 调整
**一句话理由**：目标未达成但定位到是第二步流失

## 二、目标账
| 目标 ID | 目标值 | 实测值 | 判定 | 依据 |
|---|---|---|---|---|
| GOAL-01 | 30% | 18% | 未达成 | 看板A |

## 三、假设账
| ASM | 内容 | 当初的证据等级 | 结算 | 凭什么这么结算 |
|---|---|---|---|---|
| ASM-01 | 用户愿意换 | E0 | 推翻 | 留存3% |

## 四、逃逸账
| 线上问题 | 严重度 | 本该被哪一道门禁拦住 | 那道门为什么没拦住 | 回流动作 |
|---|---|---|---|---|
| 导入超时 | 高 | 性能NFR | 门在但判据不覆盖大文件 | 加判据 |

## 五、决策质量账
| S3 当时的定义 | 现实怎么说的 | 下次在 S3 该多问一句什么 | 写进哪 |
|---|---|---|---|
| 认为用户会换工具 | 留存3% | 他现在用什么，换过来成本多少 | definition-final 模板的目标用户小节 |
| 认为 A 方案更快 | 确实更快 | — | — |

## 七、出口
- [x] 逃逸缺陷与门禁缺口已回流 lessons.md
- [x] 被推翻的假设已作为已知事实写进下一轮 S2/S3 的输入
- 因果性诚实声明：☑ 无 A/B，本文全部结论只是相关性
"""


def _run_sweep():
    """样本量解析的构造空间穷举（说明见 _sweep_lib.sweep_retro_sample）。"""
    import tempfile as _tf, shutil as _sh, subprocess as _sp, io as _io
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_retro_sample, report as _rep
    _fx = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'tests', 'fixtures', 'filled', 'retro.md')
    if not os.path.exists(_fx):
        print("  ➖ 样本量解析穷举：找不到官方夹具 —— **本条没验**（不是通过）")
        return True
    _g = _io.open(_fx, encoding='utf-8').read()
    _ol = [l for l in _g.split('\n') if '实际样本量' in l]
    if not _ol:
        print("  ➖ 样本量解析穷举：夹具里没有「实际样本量」行 —— **本条没验**")
        return True
    _b = _tf.mkdtemp(prefix='rt-sweep-')

    def _flag(_p):
        _o = _sp.run([sys.executable, os.path.abspath(__file__), _p],
                     capture_output=True, text=True).stdout
        return '样本量' in _o and '❌' in _o

    _n, _bad = sweep_retro_sample(_flag, _g, _ol[0], _b)
    _sh.rmtree(_b, ignore_errors=True)
    return _rep('样本量解析', _n, _bad)


def self_test():
    t = tempfile.mkdtemp(prefix="rg-"); me = os.path.abspath(__file__)
    def run(c):
        p = os.path.join(t, "r.md"); io.open(p, 'w', encoding='utf-8').write(c)
        return subprocess.call([sys.executable, me, p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases = [
        ("正例", GOOD, 0),
        ("反例 没有决定", GOOD.replace("☑ 调整", "☐ 调整"), 1),
        ("反例 周期无依据", GOOD.replace("**周期依据**：月度产品，取两个完整使用周期", "**周期依据**：<>"), 1),
        ("反例 没写样本量", GOOD.replace("**样本量**：4210", "**样本量**：<>"), 1),
        # 🚨 2026-09-09：原判据只要求冒号后有一个非占位字符 ⇒「样本量：0」照样通过。
        #   零样本的复盘支撑不了任何结论，而它恰恰是最容易发生的那种
        #   （埋点没上报 / 灰度没放量时诚实填 0，反被放行）。规格 §14.2 点名「空样本必须 FAIL」。
        ("反例 样本量为 0（零样本＝没测到，不是「测了但很小」）",
         GOOD.replace("**样本量**：4210", "**样本量**：0"), 1),
        ("正例 样本量含非零数字即可（不许因为出现 0 就误伤）",
         GOOD.replace("**样本量**：4210", "**样本量**：0 次崩溃 / 128 个会话"), 0),
        ("反例 没声明测量可信度", GOOD.replace("☑ 埋点已验证上报正常", "☐ 埋点已验证上报正常"), 1),
        ("反例 缺目标账", GOOD.replace("| 目标 ID | 目标值 | 实测值 | 判定 | 依据 |", "| A | B | C | D | E |"), 1),
        ("反例 假设账空表", GOOD.replace("| ASM-01 | 用户愿意换 | E0 | 推翻 | 留存3% |", ""), 1),
        ("反例 缺决策质量账", GOOD.replace("| S3 当时的定义 | 现实怎么说的 | 下次在 S3 该多问一句什么 | 写进哪 |", "| a | b | c | d |"), 1),
        # ⭐ 2026-09-04：决策质量账的教训必须有**归宿**。实测起因：一条教训写在复盘里，
        #    而它指出的缺陷仍留在被复盘的那份 PRD 里 ——
        #    `no-outflow` 管逃逸缺陷、`no-feedforward` 管被推翻的假设，**这一类此前无人管**。
        ("反例 决策质量账写了教训却不写「写进哪」",
         GOOD.replace("| 认为用户会换工具 | 留存3% | 他现在用什么，换过来成本多少 | definition-final 模板的目标用户小节 |",
                      "| 认为用户会换工具 | 留存3% | 他现在用什么，换过来成本多少 |  |"), 1),
        # 🚨 反向：没写教训的行（`—`）不许被要求归宿 —— 否则会逼人给「没教训」编一个归宿。
        #    正例 GOOD 里第二行就是这种，它必须绿。
        ("正例 没教训的行不要求归宿（判据不许逼人编归宿）", GOOD, 0),
        ("反例 写了「无明显变化」", GOOD.replace("| GOAL-01 | 30% | 18% | 未达成 | 看板A |",
                                          "| GOAL-01 | 30% | 19% | 无明显变化 | 看板A |"), 1),
        # ⭐ 2026-09-04：**否定式与肯定式几乎同形**。
        #    「写『读不出来』而不是『无明显变化』」是在声明自己没这么写，
        #    而 substring 判据把免责声明当成了宣称。
        ("正例 只是**提到**这个被禁措辞（免责声明不算宣称）",
         GOOD + "\n⚠️ 这里要写「读不出来」而不是「无明显变化」。\n", 0),
        # 🚨 反向：收窄不许变成放行 —— 先否定再照写的，仍必须红
        ("反例 先说「不是无明显变化」再照写一遍（收窄不许变成放行）",
         GOOD.replace("| GOAL-01 | 30% | 18% | 未达成 | 看板A |",
                      "| GOAL-01 | 30% | 19% | 无明显变化 | 看板A |")
             + "\n（这不是无明显变化。）\n", 1),
        ("反例 无因果性声明", GOOD.replace("☑ 无 A/B，本文全部结论只是相关性", "待定"), 1),
        ("反例 未回流 lessons", GOOD.replace("- [x] 逃逸缺陷与门禁缺口已回流 lessons.md", "- [ ] 待办"), 1),
        ("反例 无下一轮输入", GOOD.replace("- [x] 被推翻的假设已作为已知事实写进下一轮 S2/S3 的输入", "- [ ] 待办"), 1),
        ("反例 继续但无转停止条件", GOOD.replace("☑ 调整", "☑ 继续") +
                              "\n**新观察期**：观察留存 · 到 10/31 · 转停止的条件 <>\n", 1),
        ("反例 数据窗口核验写「0条未同步」→ 1（零数据点不算核验过）",
         GOOD.replace("数据窗口核验：窗口内41个提交/4210条埋点，数据源已同步核对（2026-10-01）",
                      "数据窗口核验：0条未同步"), 1),
        ("反例 数据窗口核验写一串没有数字的话 → 1（在场≠核验）",
         GOOD.replace("数据窗口核验：窗口内41个提交/4210条埋点，数据源已同步核对（2026-10-01）",
                      "数据窗口核验：窗口没问题一切正常"), 1),
        ("反例 无数据窗口核验（零数据窗口会让复盘凭空编叙事）",
         GOOD.replace("数据窗口核验：窗口内41个提交/4210条埋点，数据源已同步核对（2026-10-01）\n",
                      ""), 1),
        ("反例 无回滚演练记录（有脚本≠演练过）",
         GOOD.replace("回滚演练记录：2026-09-01 `make rollback` 于 staging 演练成功（37s 恢复）",
                      "回滚脚本：scripts/rollback.sh 已就绪"), 1),
        ("反例 持续档 band 触发被静音",
         GOOD + "\n持续监控档：已启用\nband 触发：2026-09-02 CI 失败率破 2σ\n", 1),
        ("正例 band 触发带 dismissal 理由不算静音",
         GOOD + "\n持续监控档：已启用\nband 触发：2026-09-02 破 2σ\ndismiss（理由：依赖服务窗口抖动，band 窗口已调大）\n", 0),
    ]
    ok = True
    print("M8 自证 —— 正例绿 / 每类缺口各造一个反例必红 / 无效输入报 2\n")
    for name, body, want in cases:
        got = run(body); g = got == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    for name, body, want in (("非 retro 文件", "# 随便一份文档\n内容\n", 2),):
        got = run(body); g = got == want; ok &= g
        print("  %s %-30s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))
    rc = subprocess.call([sys.executable, me, os.path.join(t, "nope.md")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    g = rc == 2; ok &= g
    print("  %s %-30s 期望 2 实得 %d" % ("✅" if g else "❌", "文件不存在", rc))
    print("\n%s" % ("✅ 自证通过：这道门会出声" if ok else "❌ 自证失败"))
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
                "本门禁用位置参数：retro-gate.py <retro.md>")
            a = [x for x in sys.argv[1:] if not x.startswith('--')]
            if not a: print(__doc__); sys.exit(2)
            sys.exit(check(a[0], '--json' in sys.argv))
    _main_guarded(_entry)
