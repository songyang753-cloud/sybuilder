#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流程度量汇算（借鉴 AI-Native SDLC 的 leading/lagging 指标层）—— 只读、只呈现。

═══ 它补的洞 ═══
门禁回答「产物合格吗」，从不回答「流程顺吗」。本工具从两处**既有时间戳**汇算：
  · `.product-flow/gates/*.json` 的 ranAt（gate-run 落盘）
  · git log 里各产物文件的首次提交时间（要求项目在 git 里；不在则该项 UNABLE）

指标（每阶段一对 leading/lagging；口径见 references/flow-metrics.md）：
  捕获时长 · intent 存活（definition-final 是否出现）· v0.9→冻结间隔 ·
  冻结后返工（PRD 在 g75 PASS 之后的提交数）· 各门首过率（gate 记录里 FAIL→PASS 的轮数）

⛔ 三条纪律：
  1. **只进 S10 复盘，不做门禁** —— 速度指标做门会诱导赶工（墙钟教训）；
  2. 算不出的数打 UNABLE，**不编造**；
  3. 共享机器上的绝对时长仅供趋势参考，不做红线。

用法: flow-metrics.py <项目根> [--json] | --self-test
退出码: 0=已汇算（含部分 UNABLE） 2=跑不了
"""
import io, json, os, re, subprocess, sys


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def git_first_ts(root, path):
    """文件在 git 里的首次提交时间戳；不在 git/没提交过 → None。"""
    try:
        out = subprocess.run(['git', 'log', '--follow', '--format=%at', '--', path],
                             cwd=root, capture_output=True, text=True, timeout=30)
        ts = [int(x) for x in out.stdout.split()]
        return min(ts) if ts else None
    except Exception:
        return None


def collect(root):
    m = {'unable': []}
    pf = os.path.join(root, '.product-flow')
    # 产物首现时间
    arts = {'intent': 'input/definition.md', 'definition': 'definition-final.md',
            'prd': 'prd/PRD.md', 'freeze': 'contract-manifest.json'}
    ts = {}
    for k, rel in arts.items():
        for cand in (os.path.join('.product-flow', rel), rel):
            t = git_first_ts(root, cand)
            if t:
                ts[k] = t
                break
        else:
            m['unable'].append('%s（%s）不在 git 历史里 —— 该项时长算不出，不编造' % (k, rel))
    if 'intent' in ts and 'definition' in ts:
        m['capture_to_definition_days'] = round((ts['definition'] - ts['intent']) / 86400, 1)
    m['intent_survival'] = ('yes' if 'definition' in ts else
                            ('no-build' if git_first_ts(root, os.path.join('.product-flow', 'no-build.md')) else 'pending'))
    if 'prd' in ts and 'freeze' in ts:
        m['v09_to_freeze_days'] = round((ts['freeze'] - ts['prd']) / 86400, 1)
    # 门禁首过率：gates/*.json 只有末次记录 —— 诚实声明这个局限
    gd = os.path.join(pf, 'gates')
    if os.path.isdir(gd):
        recs = []
        for f in sorted(os.listdir(gd)):
            if f.endswith('.json'):
                try:
                    recs.append(json.load(io.open(os.path.join(gd, f), encoding='utf-8')))
                except Exception:
                    pass
        m['gates_on_record'] = len(recs)
        m['gates_pass'] = sum(1 for r in recs if r.get('verdict') == 'PASS')
        m['note_gates'] = '落盘只留末次记录，首过率需 git log gates/ 目录才能还原（未做，不冒充）'
    else:
        m['unable'].append('无 .product-flow/gates/ —— 没用 gate-run 落盘，门禁侧指标全缺')
    return m


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a:
        die('缺少项目根；用法见 --help')
    if not os.path.isdir(a[0]):
        die('项目根不存在：%s' % a[0])
    m = collect(a[0])
    if '--json' in sys.argv:
        print(json.dumps(m, ensure_ascii=False, indent=1))
    else:
        print('流程度量（只进 S10 复盘，不做门禁；共享机器时长只看趋势）\n')
        for k, v in m.items():
            if k != 'unable':
                print('  %-28s %s' % (k, v))
        for u in m['unable']:
            print('  ⚠️ UNABLE：' + u)
        print('\n⚠️ 本工具验不了「为什么慢」——数字只指向该看哪里，归因要人做。')
    sys.exit(0)


def _self_test():
    import tempfile, shutil
    t = tempfile.mkdtemp(prefix='fm-')
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        print(('  ✅ ' if c else '  ❌ ') + n + ('' if c else '　' + e))
        ok = ok and c

    def sh(*cmd):
        subprocess.run(cmd, cwd=t, capture_output=True, timeout=30)

    sh('git', 'init', '-q')
    sh('git', 'config', 'user.email', 'x@x')
    sh('git', 'config', 'user.name', 'x')
    os.makedirs(os.path.join(t, '.product-flow', 'input'), exist_ok=True)
    io.open(os.path.join(t, '.product-flow', 'input', 'definition.md'), 'w', encoding='utf-8').write('# i\n')
    sh('git', 'add', '-A')
    sh('git', 'commit', '-qm', 'intent', '--date=2026-09-01T00:00:00')
    io.open(os.path.join(t, '.product-flow', 'definition-final.md'), 'w', encoding='utf-8').write('# d\n')
    sh('git', 'add', '-A')
    sh('git', 'commit', '-qm', 'def', '--date=2026-09-03T00:00:00')
    m = collect(t)
    chk('捕获→定义时长按 git 首提交算出（≈2 天）',
        isinstance(m.get('capture_to_definition_days'), float) and 1.5 <= m['capture_to_definition_days'] <= 2.5,
        str(m.get('capture_to_definition_days')))
    chk('intent 存活判定 yes', m.get('intent_survival') == 'yes')
    chk('缺 gates 目录 → UNABLE 明说不编造', any('gates' in u for u in m['unable']))
    t2 = tempfile.mkdtemp(prefix='fm2-')
    m2 = collect(t2)
    chk('非 git 目录 → 各产物 UNABLE，不崩不编', len(m2['unable']) >= 1)
    r = subprocess.run([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope')],
                       capture_output=True)
    chk('无效输入 → 2', r.returncode == 2)
    shutil.rmtree(t, ignore_errors=True)
    shutil.rmtree(t2, ignore_errors=True)
    print('\n%s' % ('✅ 自证通过：量具在量它声称量的东西' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        print('UNABLE: 工具自身异常：%s: %s' % (type(_e).__name__, _e), file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or ''); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    _main_guarded(_entry)
