# -*- coding: utf-8 -*-
"""场景锚点解析 —— `reconcile-gate`（G2/G3）与 `demo-anchor-gate`（S6 出场）**共用**。

═══ 为什么必须共用 ═══
2026-09-01：`demo-anchor-gate` 刚建起来时只认 HTML demo 的 `data-scene`，
而**已上线产品走的是 `baseline.md` 路径**（S6 跳过、真实程序即 demo，锁基线清单代替）。
于是那条路径的 S6 出场契约**没有任何机器检查** —— 又一处「特例路径断在机器契约上，
不会报错，只会安静地什么都不查」。

补的时候本可以在新门禁里再写一份 baseline 表解析 ——
那正是今天刚在附件 A 解析上治掉的病（两处各写各的、给出互相矛盾的结论）。
所以搬家而不是复制：判据只有这一份，两个门禁都读它。
"""
import io, os, re


def read(p):
    return io.open(p, encoding='utf-8', errors='replace').read()


def scenes(html):
    """从 demo（HTML）里取场景。"""
    return [(m.group(1), [x.strip() for x in (m.group(2) or '').split(',') if x.strip()])
            for m in re.finditer(r'data-scene\s*=\s*"([^"]+)"(?:[^>]*?data-fr\s*=\s*"([^"]*)")?', html)]


def baseline_scenes(md):
    """从 `.product-flow/baseline.md` 里取场景（已上线产品的替代输入）。

    ⚠️⚠️ 这个函数补的是一处**「声称≠实际」**：文档从 2026-08-31 起就写着
    「G2/G3 的输入可以从 demo.html 换成 baseline.md」，而**脚本里一行 baseline 代码都没有**，
    真跑必然 UNABLE。⭐ 这是本 SOP 自己反复批判的那类缺陷在自己身上的第三次复发。

    识别的表形态（表头含「场景」与「FR」/「需求」）：
      | 场景ID | 对应需求 | 进入路径 | 截图 | 版本 |
    """
    out, in_tbl, cid, cfr = [], False, 0, 1
    for ln in md.splitlines():
        t = ln.strip()
        if not t.startswith('|'):
            in_tbl = False
            continue
        cells = [c.strip() for c in t.strip('|').split('|')]
        if set(''.join(cells)) <= set('-: '):
            continue
        head = ''.join(cells)
        if ('场景' in head) and re.search(r'FR|需求', head):
            in_tbl = True
            cid = next(i for i, c in enumerate(cells) if '场景' in c)
            cfr = next(i for i, c in enumerate(cells) if re.search(r'FR|需求', c))
            continue
        if not in_tbl or len(cells) <= max(cid, cfr):
            continue
        sid = re.sub(r'[`*]', '', cells[cid]).strip()
        if not sid or sid.startswith('<'):
            continue
        ids = re.findall(r'(?:N?FR|AC)-[\w-]*\d+', cells[cfr])
        out.append((sid, ids))
    return out


def measured_scenes(txt):
    """从 `scenario-matrix-gate --dump` 的实测锚点里取场景（可运行原型的输入）。

    ⚠️ 2026-09-04 补的是一处**模型变更把下游门禁的输入假设打断**：
    S6 从「场景稿」（一屏一个 `<section data-scene>`，静态可扫）改成
    **可运行原型**（状态由数据推导、锚点运行时写到 `body` 上）之后，
    静态扫 HTML **一个场景都取不到** —— G2/G3 只会 UNABLE。
    ⭐ 我当初为「G2/G3 的输入照旧成立」专门做了运行时锚点生成，
      却**从没在能工作的 G2 下验过**（那时 G2 的 AC 集合恒空，看不出区别）——
      **「我为它做了准备」不等于「它真的接得上」，中间那一步只能真跑一次。**

    ⭐⭐ 为什么不让原型自己写一张静态场景表：那张表会与实现漂移，
      而这份 dump 是**走到了才记下**的实测结果，它就是实现吐出来的。
      走不到的场景不会出现在这里 —— 「没走到」在下游表现为「没有这个场景」，
      而不是被一张手写表补成「有」。
    """
    import json
    d = json.loads(txt)
    return [(r['scene'], [x.strip() for x in (r.get('fr') or '').split(',') if x.strip()])
            for r in d.get('scenes', [])]


def load_scenes(path):
    """按扩展名自动选适配器：.html → demo；.json → 实测锚点；.md → baseline。判据本身不变。"""
    txt = read(path)
    if path.lower().endswith(('.html', '.htm')):
        return scenes(txt)
    if path.lower().endswith('.json'):
        return measured_scenes(txt)
    return baseline_scenes(txt)


def self_test():
    """共用解析器同样要自证：它的判据一旦错，**每个下游门禁看到的东西都跟着错**，
    而且不会有任何东西报错。今天 G1 假阳性 100% 的根因就是一个解析器正则。"""
    ok = True

    def chk(name, cond):
        nonlocal ok
        print(('  ✓ ' if cond else '  ✗ ') + name)
        ok = ok and cond

    chk("demo：data-scene + data-fr 都取得到",
        scenes('<section data-scene="f01-empty" data-fr="FR-1,AC-2">') == [('f01-empty', ['FR-1', 'AC-2'])])
    chk("demo：只有 data-scene 没有 data-fr 时，需求列表为空而不是丢掉这个场景",
        scenes('<section data-scene="f01-empty">') == [('f01-empty', [])])
    chk("baseline：认「场景×需求」表",
        baseline_scenes("| 场景ID | 对应需求 |\n|---|---|\n| f01-empty | FR-1, AC-2 |")
        == [('f01-empty', ['FR-1', 'AC-2'])])
    chk("baseline：表头列序换了也要认（按表头找列，不按位置）",
        baseline_scenes("| 对应需求 | 场景ID |\n|---|---|\n| FR-1 | f01-empty |")
        == [('f01-empty', ['FR-1'])])
    chk("baseline：没有那张表时返回空，而不是把随便一张表当成场景表",
        baseline_scenes("| 版本 | 日期 |\n|---|---|\n| v1 | 2026-09-01 |") == [])
    chk("baseline：占位行 `<场景ID>` 不算真场景",
        baseline_scenes("| 场景ID | 对应需求 |\n|---|---|\n| <场景ID> | <FR> |") == [])
    # 🚨 这条第一版我写成了 `chk(..., True)` —— **恒真断言，删掉实现照样绿**。
    #    自造装饰性判据是本 SOP 反复记的老毛病，写完必须问一句：把实现改坏，它会红吗？
    import tempfile
    d = tempfile.mkdtemp()
    md = os.path.join(d, 'baseline.md')
    io.open(md, 'w', encoding='utf-8').write("| 场景ID | 对应需求 |\n|---|---|\n| f01-empty | FR-1 |")
    html = os.path.join(d, 'demo.html')
    io.open(html, 'w', encoding='utf-8').write('<section data-scene="f02-grid" data-fr="FR-2">')
    chk("load_scenes 按扩展名选适配器：.md 走 baseline",
        load_scenes(md) == [('f01-empty', ['FR-1'])])
    chk("load_scenes 按扩展名选适配器：.html 走 demo",
        load_scenes(html) == [('f02-grid', ['FR-2'])])
    # 反向：把 .md 当 HTML 扫必然一个场景都取不到 —— 证明适配器真的在分流
    chk("反向：baseline 内容用 demo 适配器扫会取不到（说明分流真的生效）",
        scenes(io.open(md, encoding='utf-8').read()) == [])

    # ⭐ 2026-09-04 补：可运行原型走实测锚点这条路。
    dump = os.path.join(d, 'anchors.json')
    io.open(dump, 'w', encoding='utf-8').write(
        '{"measuredBy":"scenario-matrix-gate","scenes":['
        '{"scene":"f01-pc-empty","fr":"FR-011,AC-1"},{"scene":"f01-pc-loading","fr":""}]}')
    chk("实测锚点：scene + fr 取得到，fr 为空时场景仍在（≠ 丢掉这个场景）",
        load_scenes(dump) == [('f01-pc-empty', ['FR-011', 'AC-1']), ('f01-pc-loading', [])])
    # 🚨 反向：可运行原型的 HTML 静态扫必须取不到 —— 这正是本适配器存在的理由。
    #    若这条变绿，说明有人往原型里手贴了静态 data-scene，
    #    那就退回场景稿了：**静态贴的锚点不保证那一屏真的到得了**。
    proto = os.path.join(d, 'proto.html')
    io.open(proto, 'w', encoding='utf-8').write(
        "<body></body><script>document.body.setAttribute('data-scene','f01-pc-empty')</script>")
    chk("反向：运行时才写锚点的原型，静态扫取不到（所以才需要 --dump 这条路）",
        load_scenes(proto) == [])
    return ok


if __name__ == '__main__':
    import sys
    # 统一接受 `--self-test`：元门禁 selftest-claim 按这个字面量识别，
    # 无参也跑自证（这个模块除了自证没有别的 CLI 用途）。
    if len(sys.argv) > 1 and sys.argv[1] not in ('--self-test',):
        print(__doc__); sys.exit(2)
    sys.exit(0 if self_test() else 1)
