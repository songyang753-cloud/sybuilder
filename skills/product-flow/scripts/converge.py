#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收敛报告 —— 一个阶段离交付还差多远，以及**差的是哪一类**。

═══ 为什么要它（抄 spec-kit 的 `/speckit-converge`）═══
门禁回答的是「合不合格」，一个布尔值。而做事的人需要的是**方向**：
还差几条、差的是结构还是内容、有没有在往前走。
spec-kit 的做法是 `implement ↔ converge` 循环到报告 `Converged`，
⇒ product-flow 有门禁但一直没有这一层。

═══ 它和门禁的分工（⛔ 不许混）═══
- **门禁**：合不合格。退出码 0/1/2，**它才是交付判据**。
- **converge**：还差多远、差哪一类、比上次进步了没有。**它不是判据**，
  ⛔ 收敛报告说「快好了」不等于可以交付 —— 交付仍然只认门禁退出码 0。

═══ 三分类（这是本工具唯一的判断）═══
- **结构红**：骨架不对（缺小节/缺列/小节名不匹配）⇒ 跑 `scaffold.py`，或对着 spec 改结构
- **内容红**：结构对了，值没填或填错（含 `⟨TODO⟩` 残留）⇒ **去做研究/写内容**，没有捷径
- **跑不了（UNABLE）**：环境/依赖缺席 ⇒ ⛔ 既不算合格也不算不合格

用法:
  converge.py --stage s2 --artifact <目录或文件>
  converge.py --stage s2 --artifact <…> --save     # 记一次快照，下次能对比进度
  converge.py --self-test
退出码: 0=Converged（门禁绿） 1=NotConverged 2=跑不了
"""
import io, os, re, sys, json, time, argparse, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODO = '⟨TODO⟩'
SNAP = '.converge-history.json'

# 判「这条红是结构问题还是内容问题」的证据特征。
# ⚠️ 只在**证据文本**上判，⛔ 不猜判据意图 —— 猜错会把人指去改错的东西。
# ⭐ 分界只有一条：**脚手架能不能生成它**。
#   能生成（缺小节/缺行/缺列/缺字面/格式不对）⇒ 结构红，跑 scaffold 或改 spec；
#   不能生成（值是占位/日期无效/数量为 0/证据不存在）⇒ 内容红，只能去做研究。
#   ⚠️ 顺序要紧：**内容特征先判** —— 「缺日期」是值没填（内容），不是缺一列（结构）。
_CONTENT = (re.escape(TODO), r'留空', r'非法', r'无效', r'没有日期', r'缺日期',
            r'缺失或无日期', r'一张图都没有', r'^0 个', r'\b0 个', r'未声明',
            r'不在六档内', r'不存在', r'找不到）', r'未填', r'空壳')
_STRUCT = (r'缺表头列', r'缺.{0,6}列', r'找不到这个小节', r'缺\s*`?##', r'缺小节',
           r'认不出', r'解析不出', r'分母不一致', r'行集与词典不一致', r'缺这一节',
           r'^缺[：:]', r'^缺\s', r'缺.{0,8}族', r'缺.{0,10}-xx', r'缺.{0,8}声明',
           r'缺.{0,10}登记', r'缺.{0,8}ID 族', r'不是\s*`', r'未填齐', r'缺环节',
           r'缺处置')
# ⛔ 这里曾有一条「短中文串一律当结构红」的兜底，已删：它让「未分类」几乎不可达。
#   一个**从不说「不知道」**的分类器是在撒谎 —— 而误导比不分类贵。
#   证据只有一个裸字面时（如 `下游三目标` / `c09.md`），形状上与「没见过的说法」
#   不可区分 ⇒ 老实归 `unknown`，让人看证据原文自己判。


def classify(ev):
    """一条红是结构问题还是内容问题。⚠️ 两者都不匹配时归 `未分类`，⛔ 不硬塞。"""
    t = ev if isinstance(ev, str) else ' '.join(map(str, ev or []))
    if any(re.search(p, t) for p in _CONTENT):
        return 'content'
    if any(re.search(p, t) for p in _STRUCT):
        return 'structure'
    return 'unknown'


GATES = {
    's2': ('scripts/research-gate.py', True),
    's3': ('scripts/definition-gate.py', False),
    's4': ('scripts/prd_completeness_check.py', False),
    's4a': ('scripts/product-structure-gate.py', False),
}


def run_gate(stage, artifact, root=None):
    root = root or ROOT
    if stage not in GATES:
        print("UNABLE: 不认识的阶段 %s（有：%s）" % (stage, '/'.join(GATES)), file=sys.stderr)
        sys.exit(2)
    rel, _ = GATES[stage]
    gate = os.path.join(root, rel)
    if not os.path.exists(gate):
        print("UNABLE: 门禁 %s 不存在" % rel, file=sys.stderr); sys.exit(2)
    r = subprocess.run([sys.executable, gate, artifact], capture_output=True, text=True)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def parse(out):
    """从门禁输出里抽出 (判据 id, 证据)。⚠️ 认两种排版：`❌ [id] 描述` 与 `· 描述`。"""
    reds, lines = [], out.splitlines()
    for i, l in enumerate(lines):
        m = re.match(r'^❌\s*\[([^\]]+)\]\s*(.*)$', l)
        if m:
            ev = lines[i + 1].strip() if i + 1 < len(lines) else ''
            reds.append((m.group(1), ev or m.group(2)))
        elif l.startswith('  · '):
            reds.append(('gap', l[4:].strip()))
    unable = len(re.findall(r'^⚠️.*UNABLE|^UNABLE', out, re.M))
    return reds, unable


def report(stage, artifact, save=False, root=None):
    root = root or ROOT
    rc, out = run_gate(stage, artifact, root)
    reds, unable = parse(out)
    n_todo = 0
    if os.path.isdir(artifact):
        for f in os.listdir(artifact):
            if f.endswith('.md'):
                n_todo += io.open(os.path.join(artifact, f), encoding='utf-8',
                                  errors='replace').read().count(TODO)
    elif os.path.exists(artifact):
        n_todo = io.open(artifact, encoding='utf-8', errors='replace').read().count(TODO)

    buckets = {'structure': [], 'content': [], 'unknown': []}
    for cid, ev in reds:
        buckets[classify(ev)].append((cid, ev))

    hist_path = os.path.join(artifact if os.path.isdir(artifact)
                             else os.path.dirname(artifact) or '.', SNAP)
    prev = None
    if os.path.exists(hist_path):
        try:
            h = json.loads(io.open(hist_path, encoding='utf-8').read())
            prev = (h.get('runs') or [])[-1] if h.get('runs') else None
        except Exception:
            prev = None

    print("# 收敛报告 · %s · %s" % (stage.upper(), artifact))
    print()
    if rc == 0:
        print("## ✅ **Converged** —— 门禁退出码 0")
        print("⚠️ 门禁只验「有没有、可不可回溯」，⛔ 验不了研究得深不深 —— 那要人读。")
    else:
        print("## ❌ **NotConverged** —— 门禁退出码 %d，%d 条红" % (rc, len(reds)))
    print()
    print("| 类别 | 条数 | 该怎么办 |")
    print("|---|---|---|")
    print("| **结构红** | %d | 跑 `scaffold.py --stage %s`，或对着 `spec/` 改小节名与列名 |"
          % (len(buckets['structure']), stage))
    print("| **内容红** | %d | **去做研究/写内容** —— 没有捷径，脚手架帮不了 |"
          % len(buckets['content']))
    print("| 未分类 | %d | 看证据原文自己判（⛔ 本工具不硬猜） |" % len(buckets['unknown']))
    print("| 跑不了 UNABLE | %d | 补环境 —— ⛔ 既不算合格也不算不合格 |" % unable)
    print("| 占位残留 `%s` | %d | 骨架生成了内容还没填 ⇒ **还没开始**，不是快完成了 |"
          % (TODO, n_todo))
    print()
    if prev:
        d = len(reds) - prev.get('reds', 0)
        arrow = '↘ 少了 %d 条' % -d if d < 0 else ('↗ **多了 %d 条**' % d if d > 0 else '→ 持平')
        print("**与上次对比**：%d → %d（%s）·上次 %s" % (prev.get('reds', 0), len(reds), arrow,
                                                    prev.get('at', '?')))
        if d >= 0:
            print("⚠️ 没有减少 —— 如果连续两轮如此，**说明在原地打转**，换个打法（本仓母题）。")
        print()
    for k, title in (('structure', '结构红'), ('content', '内容红'), ('unknown', '未分类')):
        if buckets[k]:
            print("### %s" % title)
            for cid, ev in buckets[k][:12]:
                print("- `%s` —— %s" % (cid, ev[:96]))
            print()
    print("⛔ **收敛报告不是交付判据**：说「快好了」不等于可以交付，交付只认门禁退出码 0。")

    if save:
        runs = []
        if os.path.exists(hist_path):
            try:
                runs = (json.loads(io.open(hist_path, encoding='utf-8').read()).get('runs') or [])
            except Exception:
                runs = []
        runs.append({'at': time.strftime('%Y-%m-%d %H:%M:%S'), 'stage': stage, 'rc': rc,
                     'reds': len(reds), 'structure': len(buckets['structure']),
                     'content': len(buckets['content']), 'todo': n_todo})
        io.open(hist_path, 'w', encoding='utf-8').write(
            json.dumps({'runs': runs[-20:]}, ensure_ascii=False, indent=1))
        print("\n📌 已记快照 %s（留最近 20 次）" % SNAP)
    return 0 if rc == 0 else 1


def self_test():
    ok = True

    def case(name, got, want):
        nonlocal ok
        g = got == want; ok &= g
        print("  %s %-52s 期望 %s 实得 %s" % ("✅" if g else "❌", name, want, got))

    case("结构红：缺表头列", classify('缺表头列：af、l0'), 'structure')
    case("结构红：找不到小节", classify('spec 说小节是 `## X`，但门禁源码里找不到这个小节名'), 'structure')
    case("内容红：占位残留", classify('还剩 42 处 `%s`' % TODO), 'content')
    case("内容红：值非法", classify('「4.4」状态留空或非法'), 'content')
    case("内容红：0 个", classify('0 个 RUN 覆盖账完成双向对账'), 'content')
    case("⛔ 两者都不像 → 未分类（不硬塞）", classify('某种没见过的说法'), 'unknown')
    # ⚠️ 顺序要紧：内容特征优先 —— 「缺 X 列的值是 ⟨TODO⟩」是内容问题不是结构问题
    case("内容优先于结构（缺列但原因是占位）",
         classify('缺表头列的值是 %s' % TODO), 'content')
    # ⭐ 覆盖率本身要被守：未分类多 = 把判断推回给人，工具就白做了
    case("结构红：缺一个令牌族", classify('设计令牌表缺「字」族'), 'structure')
    case("结构红：缺一类登记块", classify('缺 DIFF-xx 差异化优势论证（5.3）'), 'structure')
    case("结构红：缺九个域名（整块没生成）",
         classify('缺：能力角色、能力矩阵、效果质量、安全与合规'), 'structure')
    case("结构红：格式不对（引用写法）",
         classify('RUN-01 覆盖账不是 `<文件>.md#功能遍历覆盖账`'), 'structure')
    case("⛔ 裸字面无法凭形状分类 → unknown（不硬猜）", classify('下游三目标'), 'unknown')
    case("结构红：竞品 ID 族没用对", classify('缺竞品 ID 族（CAF-xxx / CM-xx）'), 'structure')
    case("⚠️ 内容优先：缺日期是值没填，不是缺一列",
         classify('AF-001×COMP-01 证据标签缺日期'), 'content')
    case("⛔ 只报文件名同样无法凭形状分类 → unknown", classify('c09.md'), 'unknown')
    r, u = parse("❌ [a-crit] 描述\n      证据行\n  · 某个 gap\n")
    case("能解析两种排版（判据式 + gap 式）", len(r), 2)
    case("判据 id 解析正确", r[0][0], 'a-crit')
    case("gap 式归到 gap", r[1][0], 'gap')
    print("\n%s" % ("✅ 收敛报告自证通过" if ok else "❌ 自证失败"))
    return 0 if ok else 1


def _main_guarded(fn):
    """崩溃 ≠ 有发现：意外异常一律退 2。"""
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 工具自身异常（不是「有发现」）：%s: %s" % (type(_e).__name__, _e),
              file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--stage', required=True)
    ap.add_argument('--artifact', required=True)
    ap.add_argument('--save', action='store_true')
    a = ap.parse_args()
    _main_guarded(lambda: sys.exit(report(a.stage, a.artifact, a.save)))
