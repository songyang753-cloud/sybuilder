#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""降门槛监测门 —— 扫 git diff，抓「悄悄降低质量门槛来换绿」的形态。

借 addyosmani/agent-skills `constraint-driven-development`：把质量条写成契约，
并**盯着 diff 不让 agent 偷偷降它**。本门扫 diff 的**新增/删除行**，命中即
默认阻断(exit 1)，须走豁免(理由/风险/owner/到期)，不许静默合入。

五类(与 `references/s9-quality-gates.md §2.0.6` 对齐)：
  ① 抑制注释：新增 @ts-ignore / eslint-disable / # noqa / # type: ignore / //nolint / pragma no cover / istanbul ignore
  ② 测试削弱：新增 .skip / xit / .only / fdescribe / @pytest.mark.skip / t.Skip；或删掉 test 定义
  ③ 断言削弱：删掉 assert/expect 行；或新增永真断言(assert True / expect(true))
  ④ 阈值改小：成对的 (删A行 / 加B行) 同含阈值关键字，且新数字 < 旧数字
  ⑤ 假实现占位：新增 NotImplementedError / pragma no cover / 只有 pass 的函数体冒充完成

用法: bar-weakening-scan.py [<diff文件>] [--json] | --self-test
  不给 diff 文件时读 `git diff HEAD`(当前工作树 vs HEAD)。
退出码: 0=无降门槛形态 1=有(须豁免) 2=跑不了
⚠️ 本门只抓机械可见的削弱形态；命中不等于错(可能有正当理由)，但**必须显式豁免**，
不许静默。它抓不到语义级的偷工(逻辑改错但断言没删),那仍靠评审。
"""
import io
import os
import re
import subprocess
import sys

SUPPRESS = re.compile(r'@ts-ignore|@ts-expect-error|eslint-disable|#\s*noqa|#\s*type:\s*ignore|//\s*nolint|#\s*pragma:\s*no\s*cover|istanbul\s+ignore|#\s*NOSONAR', re.I)
TEST_SKIP = re.compile(r'\.skip\(|\bxit\(|\bxdescribe\(|\.only\(|\bfdescribe\(|\bfit\(|@pytest\.mark\.skip|@unittest\.skip|\bt\.Skip\(|@Ignore\b|@Disabled\b', re.I)
TRIVIAL_ASSERT = re.compile(r'\bassert\s+(?:True|1|true)\b|\bassert\(\s*true\s*\)|expect\(\s*true\s*\)|assertTrue\(\s*True\s*\)', re.I)
REAL_ASSERT = re.compile(r'\bassert\b|\bexpect\(|\bassert(?:Equal|True|That|Contains)\(|\brequire\.', re.I)
TEST_DEF = re.compile(r'\bdef\s+test_|\bit\(|\btest\(|\bTest\w+\s*\(|func\s+Test[A-Z]', re.I)
STUB = re.compile(r'NotImplementedError|raise\s+NotImplemented\b|#\s*pragma:\s*no\s*cover|throw\s+new\s+Error\(["\']not\s+implemented', re.I)
THRESH_KEY = re.compile(r'cov-fail-under|fail_under|min-coverage|min_coverage|--min\b|threshold|--max-dead|max-dead-pct|coverage.*?(\d{2,3})', re.I)
NUM = re.compile(r'(\d+(?:\.\d+)?)')


def die(message):
    print('UNABLE: %s' % message, file=sys.stderr)
    sys.exit(2)


def parse_diff(text):
    """返回 (added, removed)：各是 [(file, text)] 列表(去掉 +/- 前缀)。"""
    added, removed = [], []
    cur = '?'
    for line in text.splitlines():
        if line.startswith('+++ '):
            cur = line[4:].lstrip('b/').strip()
            continue
        if line.startswith('--- '):
            continue
        if line.startswith('diff --git'):
            m = re.search(r' b/(\S+)', line)
            if m:
                cur = m.group(1)
            continue
        if line.startswith('+') and not line.startswith('+++'):
            added.append((cur, line[1:]))
        elif line.startswith('-') and not line.startswith('---'):
            removed.append((cur, line[1:]))
    return added, removed


def _num_after_key(s):
    m = NUM.search(s)
    return float(m.group(1)) if m else None


def check(diff_text):
    bad = []
    added, removed = parse_diff(diff_text)

    for f, t in added:
        if SUPPRESS.search(t):
            bad.append('① 抑制注释新增：%s :: %s' % (f, t.strip()[:60]))
        if TEST_SKIP.search(t):
            bad.append('② 测试被跳过/聚焦：%s :: %s' % (f, t.strip()[:60]))
        if TRIVIAL_ASSERT.search(t):
            bad.append('③ 新增永真断言(=剥断言)：%s :: %s' % (f, t.strip()[:60]))
        if STUB.search(t):
            bad.append('⑤ 假实现占位：%s :: %s' % (f, t.strip()[:60]))

    # ② 删掉 test 定义；③ 删掉真实断言(且没在新增里补回同类)
    added_txt = '\n'.join(t for _, t in added)
    for f, t in removed:
        if TEST_DEF.search(t):
            bad.append('② 测试定义被删：%s :: %s' % (f, t.strip()[:60]))
        if REAL_ASSERT.search(t) and not TRIVIAL_ASSERT.search(t):
            # 若同一断言文本在新增里出现(只是挪位)则不算削弱
            if t.strip() not in added_txt:
                bad.append('③ 真实断言被删：%s :: %s' % (f, t.strip()[:60]))

    # ④ 阈值改小：删A行/加B行成对、同含阈值关键字、新数字更小
    rem_thresh = [(f, t, _num_after_key(t)) for f, t in removed if THRESH_KEY.search(t)]
    add_thresh = [(f, t, _num_after_key(t)) for f, t in added if THRESH_KEY.search(t)]
    for rf, rt, rn in rem_thresh:
        if rn is None:
            continue
        for af, at, an in add_thresh:
            if an is not None and af == rf and an < rn:
                bad.append('④ 阈值被改小：%s :: %s → %s' % (rf, str(rn), str(an)))
                break
    return bad


def _read_diff(args):
    files = [a for a in args if not a.startswith('--')]
    if files:
        if not os.path.isfile(files[0]):
            die('diff 文件不存在：%s' % files[0])
        return io.open(files[0], encoding='utf-8', errors='replace').read()
    try:
        out = subprocess.run(['git', 'diff', 'HEAD'], capture_output=True, text=True, timeout=60)
    except Exception as exc:
        die('无法跑 git diff：%s' % exc)
    if out.returncode != 0:
        die('git diff 失败(非 git 仓或无 HEAD)：%s' % out.stderr.strip()[:80])
    return out.stdout


def _entry():
    diff_text = _read_diff(sys.argv[1:])
    bad = check(diff_text)
    if '--json' in sys.argv:
        import json
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ 无降门槛形态' if not bad else '❌ %d 处降门槛形态(须显式豁免,不许静默合入)' % len(bad))
        print('⚠️ 只抓机械可见的削弱;语义级偷工仍靠评审。命中不等于错,但必须有理由/风险/owner/到期。')
    sys.exit(0 if not bad else 1)


def _self_test():
    ok = True

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,3 +1,5 @@
 def compute(v):
-    return v
+    return v + 1
+
+def test_compute():
+    assert compute(1) == 2
"""
    chk('正例：干净 diff → 0 处', check(good) == [])
    mutations = [
        ('反例①：新增 # type: ignore', good + '+    y = risky()  # type: ignore\n', '①'),
        ('反例②：新增 @pytest.mark.skip', good + '+@pytest.mark.skip\n', '②'),
        ('反例③：新增永真断言', good + '+    assert True\n', '③'),
        ('反例③b：真实断言被删', good + '-    assert compute(2) == 3\n', '③'),
        ('反例⑤：假实现占位', good + '+    raise NotImplementedError\n', '⑤'),
        ('反例④：阈值改小', good + '-    "--cov-fail-under=80",\n+    "--cov-fail-under=60",\n', '④'),
    ]
    for name, body, prefix in mutations:
        found = check(body)
        chk('%s → 命中本类且非空' % name, bool(found) and any(x.startswith(prefix) for x in found))

    # 无效输入(不存在的 diff 文件)→ 2
    import tempfile
    root = tempfile.mkdtemp(prefix='barweak-')
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'nope.diff')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入(缺文件) → 2', rc == 2)
    # 正例经子进程 → 0
    gp = os.path.join(root, 'good.diff')
    io.open(gp, 'w', encoding='utf-8').write(good)
    rc0 = subprocess.call([sys.executable, os.path.abspath(__file__), gp],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('正例文件经子进程 → 0', rc0 == 0)
    print('\n%s' % ('✅ 自证通过：降门槛监测门会出声' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        print('UNABLE: 门禁自身异常（不是「有发现」）：%s: %s' %
              (type(exc).__name__, exc), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    _main_guarded(_entry)
