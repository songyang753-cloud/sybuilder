#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S3A 业务梳理出场门 —— business-map.md 的四条结构性判据。

═══ 它补的洞（终局规格 1-1）═══
S3A 进了阶段表、有模板，但没有任何门禁 —— 一个新阶段的产出无人守，
「填了模板」和「梳理清了业务」在产物上长得一模一样。

判据（照 templates/business-map.md 结构反推）：
  ① 角色表 ≥1 行真实内容（占位符 <...> 不算）
  ② 现状流程段有「卡在哪」的标注（卡/流失/出错/绕路 至少命中其一 —— AS-IS 没有痛点=没去看）
  ③ 指标树每个指标有现值或显式 TBD-xxx（⛔ 空值不算：编不出来的数就登记待查，不许留白）
  ④ 业务规则每条带违反后果（没有后果的规则是愿望，不是规则）

用法: business-map-gate.py <business-map.md> [--json] | --self-test
退出码: 0=通过 1=有缺口 2=跑不了
⚠️ 验不了什么：业务判断对不对（价值是否成立归 S3B 拍板与评审）；本门只验「梳理是否做了且落了地」。
"""
import io, json, os, re, sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at   # noqa: E402  段落定位的唯一正本（见该模块 docstring）


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def rows_of(md, kw):
    # 🚨 2026-09-09 第五轮：起点是 `md.find(kw)`（全文首次出现）——
    #   **终点锚定了，起点没有**；一行目录即让本节从目录那一行开始切。
    seg = section_at(md, kw)
    if seg is None:
        return None
    rows = [l for l in seg.split('\n') if l.strip().startswith('|')]
    return [r for r in rows[2:] if r.replace('|', '').replace('-', '').strip()]


def real(cell):
    c = cell.strip()
    return bool(c) and not (c.startswith('<') and c.endswith('>'))


def check(md):
    bad = []
    # ① 角色
    rr = rows_of(md, '角色与关系')
    good = [r for r in (rr or []) if sum(real(c) for c in r.strip('|').split('|')) >= 3]
    if not rr:
        bad.append('① 没有「角色与关系」表')
    elif not good:
        bad.append('① 角色表没有一行真实内容（占位符不算填）')
    # ② 现状流程的痛点标注
    # 🚨 2026-09-09：原为 md[i:i+1500] 固定字符窗口 —— 实测在**官方 filled 夹具上
    #   就已经跨过了下一节**（两节间距仅 151 字符）：现状流程段一个痛点都没标，
    #   只要后面任何一节出现「流失/出错/卡在」，本条照样判过。⛔ 拿别人的行给本节背书。
    # 🚨🚨 2026-09-09 第五轮独立复核：**第三轮的修复把窗口从尾部挪到了头部，
    #   同一个假绿换个方向复发**。上一版把 `md[i:i+1500]` 改成
    #   `find('现状业务流程')` + `find('\n## ', i)` —— 终点锚定了，起点没有。
    #   实测：AS-IS 段零痛点的文档 rc=1；只加一段导读
    #     > 本文的现状业务流程一节里，读者常卡在第二步
    #   → **rc=0**。这正是该修复注释自己点名要治的「拿别人的行给本节背书」。
    #   反向也成立：加一行目录会让完好的指标树段被判红。
    #   ⭐ 判断修没修好的标准是「同一个反例族里还剩几个变体能过」，
    #     不是「作者写的那一发反例现在红了吗」。
    seg = section_at(md, '现状业务流程')
    if seg is None:
        bad.append('② 没有「现状业务流程」段')
    elif not re.search(r'卡在|流失|出错|绕路|痛点', seg.replace('在哪一步流失/出错/绕路，标出来', '')):
        bad.append('② 现状流程没有标出卡点/流失/出错 —— AS-IS 里没有痛点，说明还没去看真实流程')
    # ③ 指标树现值
    # 同上：窗口过大吃邻节（假绿），窗口过小让长指标表的后半段静默逃检（也是假绿）。
    seg = section_at(md, '指标树')
    if seg is None:
        bad.append('③ 没有「指标树」段')
    else:
        metric_lines = [l for l in seg.split('\n') if re.search(r'指标|北极星', l) and ('<' in l or '：' in l or ':' in l)]
        vague = [l.strip()[:40] for l in metric_lines
                 if re.search(r'现值', l) and not re.search(r'现值[^：:]*[：:]?\s*([\d.%]+|TBD-\d+|未知 → TBD)', l)]
        if vague:
            bad.append('③ 指标写了「现值」却没有数也没有 TBD-xxx：%s' % vague[0])
        if '现值' not in seg and 'TBD' not in seg:
            bad.append('③ 指标树没有任何现值或 TBD 登记 —— 写不出现值就登记待查，不许留白')
    # ④ 规则后果
    rr = rows_of(md, '业务规则')
    if rr is None:
        bad.append('④ 没有「业务规则」表')
    else:
        for r in rr:
            cells = [c.strip() for c in r.strip('|').split('|')]
            if len(cells) >= 3 and real(cells[0]) and not real(cells[2]):
                bad.append('④ 规则「%s」没写违反后果 —— 没有后果的规则是愿望' % cells[0][:24])
    return bad


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a:
        die('缺少 business-map.md 路径；用法见 --help')
    if not os.path.isfile(a[0]):
        die('文件不存在：%s' % a[0])
    # ⚠️ 2026-09-09（§14.2 故障情境实测）：这里原来不带 errors='replace' ——
    #   同批的 definition-gate / retro-gate 都带。于是同一份含损坏字节的产物，
    #   在别的门上得到**内容判定**，在这道门上变成「门禁自身异常 UNABLE」。
    #   ⭐ 守护层的行为没错（它如实标了 UNABLE 而不是冒充 FAIL），
    #   错的是**同类门对同一种输入给出两种结果语义** —— 读者无从判断产物到底合不合格。
    md = io.open(a[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for b in bad:
            print('  ❌ ' + b)
        print('✅ S3A 四判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门验不了业务判断对不对 —— 价值是否成立归 S3B 拍板与评审。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import tempfile, subprocess
    t = tempfile.mkdtemp(prefix='bm-')
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        print(('  ✅ ' if c else '  ❌ ') + n + ('' if c else '　' + e))
        ok = ok and c

    GOOD = """# 业务梳理
## 1. 角色与关系
| 角色 | 是谁 | 要什么 | 付出什么 | 关系 |
|---|---|---|---|---|
| 摄影师 | 自由职业者 | 快速交片 | 月费 | 服务买家 |
## 2. 现状业务流程
拍摄 → 手动挑片（**卡在这里：3 小时/单**）→ 修图 → 交付
## 5. 指标树
北极星：交片周期（现值 5 天）
 ├─ 挑片时长（现值 3h）
 └─ 返修率（现值未知 → TBD-001）
## 4. 业务规则
| 规则 | 为什么存在 | 违反后果 | 来源 |
|---|---|---|---|
| 原片 30 天后删除 | 存储成本 | 用户丢片投诉 | INS-003 |
"""

    def run(body):
        p = os.path.join(t, 'bm.md')
        io.open(p, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chk('正例：四判据全过 → 0', run(GOOD) == 0)
    # ⭐ 构造空间穷举（轴 = 痛点词 × 位置 × 邻节诱饵）——说明见 _sweep_lib。
    #   诱饵那一轴专放「附注：早期版本有用户流失」，它在第四、五轮各制造过一次假绿。
    import tempfile as _tf2, shutil as _sh2, subprocess as _sp2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _sweep_lib import sweep_pain_detection
    from _section import section_at as _sa
    _sec = _sa(GOOD, '现状业务流程')
    _b2 = _tf2.mkdtemp(prefix='bm-sweep-')

    def _missed(_p):
        _o = _sp2.run([sys.executable, os.path.abspath(__file__), _p],
                      capture_output=True, text=True).stdout
        return '② 现状流程没有标出' in _o

    _n2, _bad2 = sweep_pain_detection(_missed, GOOD, _sec, _b2)
    _sh2.rmtree(_b2, ignore_errors=True)
    chk('痛点识别 构造空间穷举 %d 例' % _n2, not _bad2)
    for _x in _bad2[:4]:
        print('     · %s' % _x)
    chk('反例①：角色表全占位 → 1',
        run(GOOD.replace('| 摄影师 | 自由职业者 | 快速交片 | 月费 | 服务买家 |',
                         '| <用户> | <是谁> | <要什么> | <付出> | <关系> |')) == 1)
    chk('反例②：现状流程无卡点 → 1', run(GOOD.replace('（**卡在这里：3 小时/单**）', '')) == 1)
    # 🚨 2026-09-09：② 曾用 md[i:i+1500] 固定窗口，而**官方夹具两节间距仅 151 字符**
    #   ⇒ 窗口早就跨进了后面的节：本段一个痛点没标，只要别处出现「流失」就判过。
    #   ⛔ 拿别人的行给本节背书。窗口类判据必须有「邻节诱饵」反例。
    chk('反例②b：本段无痛点、邻节有「流失」诱饵 → 1（窗口不许吃邻节的行）',
        run(GOOD.replace('（**卡在这里：3 小时/单**）', '')
            + '\n\n## 附注\n历史包袱：早期版本有用户流失，已修。\n') == 1)
    chk('正例②c：本段有痛点、邻节也有痛点词 → 0（修窗口不许变成漏判本段）',
        run(GOOD + '\n\n## 附注\n历史包袱：早期版本有用户流失，已修。\n') == 0)
    # 🚨🚨 2026-09-09 第五轮独立复核：上面那次修复（②b/②c）把窗口从**尾部**挪到了
    #   **头部** —— `find('现状业务流程')` + `find('\n## ', i)`：终点锚定了，起点没有。
    #   于是同一个假绿换个方向复发：正文前面加一段**提到本节名字的导读**，
    #   本节就从那句话开始切，导读里的「卡在」替真正没痛点的 AS-IS 段背书。
    #   ⭐ 这正是 ②b 注释自己点名要治的「拿别人的行给本节背书」。
    chk('反例②d：本段无痛点、**前言**提到本节名并含痛点词 → 1（起点也必须锚定）',
        run(('# 业务地图\n\n本文的现状业务流程一节里，读者常卡在第二步。\n'
             + GOOD.split('\n', 1)[1]).replace('（**卡在这里：3 小时/单**）', '')) == 1)
    chk('反例③：指标无现值无 TBD → 1',
        run(GOOD.replace('（现值 5 天）', '').replace('（现值 3h）', '').replace('（现值未知 → TBD-001）', '')) == 1)
    chk('正例：现值编不出但登记了 TBD → 0（诚实待查不算缺口）',
        run(GOOD.replace('（现值 5 天）', '（现值未知 → TBD-002）')) == 0)
    chk('反例④：规则无后果 → 1', run(GOOD.replace('| 用户丢片投诉 |', '|  |')) == 1)
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope.md')],
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
