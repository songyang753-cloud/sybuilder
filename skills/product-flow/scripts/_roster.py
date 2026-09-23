#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁名册 —— **唯一正本**。谁是门禁，只由这一个函数说了算。

🚨 2026-09-10 codex 专家评审 #14 立此模块。当时的实测：

    consistency-gate 的 gate_files():  28
    gate-run --status 的口径:          27   （漏 browser-audit.mjs）
    mutation-sweep 的默认口径:         24   （另漏 coverage_check.py / prd_completeness_check.py）

  **三个消费方三个集合**，而每一个都在拿自己的那份当「全部门禁」用：
    · `mutation-sweep` 打印「变异全部被杀死」时，另外 4 道门连 skipped 都不会出现；
    · `gate-run --status` 的「哪些门没跑过」漏掉 browser-audit.mjs（S6 出场必跑）；
    · 而 `single-source` 这条元规则治的正是「同一概念在全仓有两种口径」——
      ⭐ **它自己就发生在门禁名册上，且没有任何东西在守。**

⭐⭐ 这不是「还差几个 glob」。codex 的架构判断是对的：
   三类关键事实（Markdown 结构 / 门禁集合 / 完成声明）都缺可共享的数据模型，
   **最危险的假绿全发生在这些接口缝隙上**。
   `_section.py` 是第一类的正本；本模块是第二类的。

🚨 2026-09-12 实测：`GATE_LIKE_EXEMPT` **对 `*-gate.*` 文件从来不生效** ——
   名册第一趟按通配无条件收录，压根没查豁免表。实测 17 条豁免里 **2 条是死的**
   （`consistency-gate.py` 登记着豁免却一直在名册里，`no-loss-gate.py` 新登记同样无效）。
   ⭐ 修的是**谎话不是行为**：`*-gate.*` 后缀无条件入册**符合**本仓"多守一个"的方向，
     错的是豁免表让人以为登记了就能豁免。⇒ 删掉那两条死登记，
     并加一条自证：**豁免表里不许有死条目**（登记了却仍在名册 = 表在腐烂）。
   ⇒ 想让一个脚本不当门禁，**别用 `-gate` 后缀**；用了就得全套登记。

⚠️ 名册的**默认方向**（2026-09-09 第五轮定，此处继承）：
   scripts/ 下接受 `--self-test` 的**一律当门禁**，不是门禁的必须在
   `GATE_LIKE_EXEMPT` 里**显式登记并写明理由**。
   ⛔ 这个方向的错是「多守一个」（一次性登记成本），
     反方向的错是「一道真门永远没人管」（永久盲区）。两者不对称，所以选前者。
"""
import glob
import io
import os
import re

# 名字不含 `-gate` 但确实是门禁的（历史命名，改名会断外部引用）
NAMED_GATES = ("prd_completeness_check.py", "coverage_check.py", "browser-audit.mjs")

# ⛔ 豁免只给「职责本身不是判产物」的东西；拿不准就让它进门禁集合（宁可多守）。
GATE_LIKE_EXEMPT = {
    'selftest-all.py', 'mutation-sweep.py', 'reverse-test.py', 'unexecuted-check.py',
    'gate-run.py',              # 跑手：它跑别的门，自己不判内容
    'spec-to-js.py', 'flows-to-testcases.py', 'design-to-tokens.py', 'tokens-to-css.py',
    'taste-memory.py', 'flow-metrics.py', 'capture-live-ui.js',
    'scaffold.py',              # 脚手架：**生成**骨架，不判任何产物 —— 它的产物由 research-gate 等判
    'gen-docs.py',              # 文档生成器：把 spec 口径写进文档；漂移由 consistency-gate 的 spec-doc-in-sync 判
    'converge.py',              # 收敛报告：读**门禁的输出**做分类，自己不判任何产物；⛔ 它不是交付判据
    'spec-check.py',            # 验的是**规格**与门禁一致，不判任何产物（产物归各流程的门禁）
    'doc-sync-guard.py',        # 格式边界守卫（外发协议，不判产物内容）
    'sec-scan.py',              # 专项扫描（目录里单列为「专项扫描」）
    'bar-weakening-scan.py',    # 专项扫描：扫 git diff 抓降门槛形态，非结构报告门（借 addyosmani constraint-driven-development）
    'receipt-check.py',         # 原生证据 receipt 校验门（manifest 时间戳归属校验）
    'competitor-walk.mjs',      # 竞品遍历器(CDP computer-use)：需真实 Electron app 才能跑，无纯逻辑通过/失败判据可自证；产物由 research-gate 判
    'competitor-sweep.mjs',     # 竞品串行编排器：只是逐个调 walk（串行防爆内存），不判任何产物；串行行为由 serial-orchestration-gate 判
}


def gate_files(skill_root):
    """scripts/ 下的全部门禁（绝对路径，已排序）。**含 .mjs** —— 门禁是不是门禁跟语言无关。

    ⚠️ 2026-09-04：此前只按 `*-gate.*` 通配，于是 `prd_completeness_check.py`（S4 出场门）
      与 `coverage_check.py`（S8 对账门）在计数里消失了，而 `gate-wired` 又把它俩单独加回来
      ⇒ 两条元规则对「有几道门禁」口径不一致。⭐ 根因：**命名约定被当成了判据**。
    """
    sd = os.path.join(skill_root, 'scripts')
    out = []
    for pat in ('*-gate.py', '*-gate.mjs'):
        out += glob.glob(os.path.join(sd, pat))
    out += [os.path.join(sd, g) for g in NAMED_GATES if os.path.exists(os.path.join(sd, g))]
    known = {os.path.basename(p) for p in out}
    for p in sorted(glob.glob(os.path.join(sd, '*.py')) + glob.glob(os.path.join(sd, '*.mjs'))):
        b = os.path.basename(p)
        if b in known or b.startswith('_') or b in GATE_LIKE_EXEMPT:
            continue
        try:
            src = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        # 🚨 2026-09-10 codex 二轮 #3：`'--self-test' in src` 是**裸子串** ⇒
        #   ①只在注释里提一句「does not accept --self-test」的帮助脚本被**收成门禁**；
        #   ②真正处理自测但用 `"--self" + "-test"` 拼参数的**不入册**。
        #   ⭐ docstring 说的是「**接受** --self-test」，代码做的是「**提到** --self-test」——
        #     本仓母题「提到≠用了」在名册正本上又犯一次。
        #   ⇒ 剥掉行注释后要求它出现在代码里，且该文件真的读命令行（argv 语境）。
        #   ⚠️ 诚实边界：拼接构造的参数（`"--self" + "-test"`）本函数**认不出**，
        #     它靠 argv 语境这一条兜住一半（读 argv 的脚本会入册，由 selftest-claim 再查）。
        code = re.sub(r'(?m)^\s*(?:#|//).*$', '', src)
        if not re.search(r'argv|process\.argv', code):
            continue                      # 从不看命令行 ⇒ 不是一道能被跑的门
        if '--self-test' not in code:
            continue
        out.append(p)
    return sorted(set(out))


def gate_names(skill_root):
    """同上，只要文件名。"""
    return sorted({os.path.basename(p) for p in gate_files(skill_root)})


def sweepable(skill_root):
    """变异扫描的默认名册 —— 门禁全集减去「扫它没意义」的。

    ⚠️ 元门禁自己不进（它的变异由 `consistency-gate --self-test` 的 MUTATIONS 表负责，
      两套机制打同一个文件会互相干扰）。⛔ 其余一律进：
      此前 `mutation-sweep` 只 glob `*-gate.*`，于是三道具名门禁
      **连「跳过」都不会出现在输出里**，而结论行照样写「变异全部被杀死」。
    """
    return [p for p in gate_files(skill_root)
            if os.path.basename(p) != 'consistency-gate.py']


def _self_test():
    """本模块的自证：名册非空、含具名门禁、豁免真的被排除、方向反转仍在。"""
    import tempfile
    ok = True

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("  %s %s" % ('✅' if cond else '❌', name))

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    names = gate_names(root)
    chk('名册非空', len(names) > 10)
    for g in ('prd_completeness_check.py', 'coverage_check.py', 'browser-audit.mjs'):
        if os.path.exists(os.path.join(root, 'scripts', g)):
            chk('具名门禁在册：%s' % g, g in names)
    chk('元门禁自己不在变异名册里',
        'consistency-gate.py' not in {os.path.basename(p) for p in sweepable(root)})
    chk('显式豁免真的被排除（gate-run.py）', 'gate-run.py' not in names)
    # 🚨 2026-09-12：这条守的是**豁免表本身别腐烂**。此前 2 条死登记无人发现。
    _dead = [e for e in GATE_LIKE_EXEMPT if e in set(names)]
    chk('豁免表里没有**死条目**（登记了却仍在名册 ⇒ 登记是假的）：%s' % (_dead or '无'), not _dead)

    d = tempfile.mkdtemp(prefix='roster-')
    os.makedirs(os.path.join(d, 'scripts'))
    io.open(os.path.join(d, 'scripts', 'stealth-check.py'), 'w', encoding='utf-8').write(
        "import sys\n# 措辞避开全部关键词\nif '--self-test' in sys.argv:\n    sys.exit(0)\n")
    chk('措辞避开全部关键词的门禁仍被收进量程（默认方向＝除非登记否则就是）',
        'stealth-check.py' in gate_names(d))
    io.open(os.path.join(d, 'scripts', 'gen-only.py'), 'w', encoding='utf-8').write(
        "# 没有自测的生成器\nprint('x')\n")
    chk('没有 --self-test 的东西不进名册（那一层归 selftest-claim 用更宽的名册查）',
        'gen-only.py' not in gate_names(d))
    print("\n" + ("✅ 自证通过：名册正本可信" if ok else "❌ 自证失败：先修名册"))
    return 0 if ok else 1


if __name__ == '__main__':
    import sys
    if '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    for _p in gate_files(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        print(os.path.basename(_p))
