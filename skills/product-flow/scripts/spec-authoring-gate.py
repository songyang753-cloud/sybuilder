#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec 作者侧结构红棘轮（§4.2）—— 改 spec 引入结构错，当场抓，别再磨 7 轮。

═══ 它治的病（2026-09-17 实测）═══
07:24 立了 M10「用 spec 保证结构一致」，08–11 就把 spec 本身写错 **17 处**，
v8 corpus 门禁 23→16→13→12→8→6→4→0 **磨了 7 个提交**。
为什么这么慢:spec 错**只在下游 corpus 门上暴露**——改 spec → 跑 corpus → 看报错 → 猜 → 再改。
⇒ 把反馈提前到**作者侧**:改完 spec 立刻对每个阶段「scaffold 生骨架 → converge 数结构红」，
   结构红一旦比基线**增加**，就是你这次 spec 改坏了结构，当场红，不用磨到 corpus。

═══ 棘轮口径 ═══
新鲜骨架的结构红 = 该 spec 结构对不对的直接量（scaffold 契约:骨架一出来结构类判据就该绿）。
- actual > 基线 ⇒ 你引入了结构红 → 改 spec（红）
- actual < 基线 ⇒ 你修好了 → **必须把基线改小**（红，防基线腐烂，同 CI 棘轮 ③④）
- actual = 基线 ⇒ 放行
s0 不在表内:chain-gate 跨工件对账，单骨架 converge 判 UNABLE——如实排除（见基线文件 _excluded）。

═══ 它验不了什么（诚实边界）═══
⛔ 结构红 0 不代表内容对——内容红只能靠做研究（converge 已分开这两类）。
⛔ 也拦不住「改 spec 后我没跑本门」这种时机问题——那层同 serial-orchestration，靠纪律 + CI。
⛔ s2 基线 7 是 B5 遗留的真实结构缺口:本门只保证它**不再涨**，收敛到 0 仍需另работа。

用法: spec-authoring-gate.py [--root <skill 根>] ｜ --self-test
退出码: 0=未超基线 1=结构红涨了/该降基线了 2=跑不了
"""
import io, os, re, sys, json, tempfile, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_FILE = os.path.join('spec', '_structural-red-baseline.json')


def _baseline(root):
    d = json.load(io.open(os.path.join(root, BASELINE_FILE), encoding='utf-8'))
    return {k: v for k, v in d.items() if not k.startswith('_') and isinstance(v, int)}


def measure(stage, root):
    """scaffold 生骨架 → converge 数结构红。返回 int，或 None=UNABLE。"""
    t = tempfile.mkdtemp(prefix='spa-%s-' % stage)
    try:
        out = os.path.join(t, stage)
        sc = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'scaffold.py'),
                             '--stage', stage, '--out', out, '--force'],
                            capture_output=True, text=True)
        if sc.returncode != 0:
            return None
        cv = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'converge.py'),
                             '--stage', stage, '--artifact', out],
                            capture_output=True, text=True)
        if cv.returncode == 2:
            return None
        m = re.search(r'结构红\D+?(\d+)', cv.stdout)
        return int(m.group(1)) if m else None
    finally:
        shutil.rmtree(t, ignore_errors=True)


def check_ratchet(actual: dict, baseline: dict):
    """纯函数:比 actual 与 baseline，列出违规。actual 值为 None=该阶段没测出来。"""
    issues, unable = [], []
    for st, base in sorted(baseline.items()):
        a = actual.get(st)
        if a is None:
            unable.append(st)
        elif a > base:
            issues.append("[%s] 结构红 %d > 基线 %d —— 这次 spec 改动引入了 %d 条结构红，改 spec 别改基线"
                          % (st, a, base, a - base))
        elif a < base:
            issues.append("[%s] 结构红 %d < 基线 %d —— 你修好了 %d 条！**必须把 %s 里的 %s 改成 %d**（防基线腐烂）"
                          % (st, a, base, base - a, BASELINE_FILE, st, a))
    return issues, unable


def main(root=None):
    root = root or ROOT
    try:
        baseline = _baseline(root)
    except Exception as e:
        print("UNABLE: 读不到基线 %s (%s)" % (BASELINE_FILE, e), file=sys.stderr)
        return 2
    actual = {st: measure(st, root) for st in baseline}
    issues, unable = check_ratchet(actual, baseline)
    for st in baseline:
        a = actual.get(st)
        print("  %s %-4s 结构红 %s (基线 %d)"
              % ("⚠️" if a is None else ("✅" if a == baseline[st] else "❌"),
                 st, "UNABLE" if a is None else a, baseline[st]))
    for i in issues:
        print("❌ " + i)
    if unable:
        print("⚠️ 没测出来(UNABLE，非通过非失败):%s —— 补环境或查 scaffold/converge" % ', '.join(unable))
    if not issues:
        print("✅ 各阶段结构红未超基线（新鲜骨架的结构类判据未被 spec 改动弄坏）")
    print("⚠️ 本门只保证结构红不涨——⛔ 结构红 0≠内容对，也拦不住『改完没跑本门』的时机问题。")
    return 1 if issues else 0


def self_test():
    ok = True

    def case(name, got, want):
        nonlocal ok
        g = (got == want); ok &= g
        print("  %s %-50s 期望 %d 实得 %d" % ("✅" if g else "❌", name, want, got))

    base = {'s2': 7, 's3': 0, 's4': 0, 's4a': 0}
    # 正例:全等基线
    iss, un = check_ratchet({'s2': 7, 's3': 0, 's4': 0, 's4a': 0}, base)
    case("正例 全等基线 → 无违规", len(iss), 0)
    # 反例:某阶段结构红涨了
    iss, un = check_ratchet({'s2': 7, 's3': 2, 's4': 0, 's4a': 0}, base)
    case("反例 s3 结构红 0→2 → 抓到", len(iss), 1)
    case("反例 措辞含『引入』", 1 if any('引入' in i for i in iss) else 0, 1)
    # 反例:某阶段结构红降了(该改基线)
    iss, un = check_ratchet({'s2': 4, 's3': 0, 's4': 0, 's4a': 0}, base)
    case("反例 s2 结构红 7→4（修好了）→ 逼降基线", len(iss), 1)
    case("反例 措辞含『改成』", 1 if any('改成' in i for i in iss) else 0, 1)
    # UNABLE:某阶段没测出来 → 记 unable，不算违规
    iss, un = check_ratchet({'s2': 7, 's3': None, 's4': 0, 's4a': 0}, base)
    case("UNABLE s3 没测出 → 不算违规", len(iss), 0)
    case("UNABLE s3 进 unable 名单", 1 if 's3' in un else 0, 1)
    # 反例:涨和降同时
    iss, un = check_ratchet({'s2': 9, 's3': 0, 's4': 0, 's4a': 0}, base)
    case("反例 s2 涨 7→9 → 抓到", len(iss), 1)

    print("\n%s" % ("✅ spec 作者侧棘轮门禁自证通过" if ok else "❌ 自证失败"))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print("UNABLE: 工具自身异常（不是「有发现」）：%s: %s" % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(self_test())

    def _entry():
        sys.exit(main())

    _main_guarded(_entry)
