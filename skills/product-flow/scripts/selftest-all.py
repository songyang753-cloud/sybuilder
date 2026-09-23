#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全量自证跑手 —— 跑遍所有门禁的 --self-test，并把**实测数字**落到文件。

为什么要有这个脚本（2026-09-06 实测踩到的）：

  文档里写着「23 道门禁的自证共 358 个用例」。
  这个数字是**一次性 shell 循环**数出来的，跑完就没了。
  我今天给 platform-parity 加了 1 条用例 —— 那一刻文档里的 358 就是错的，
  而元门禁 25 条**全绿**：没有任何东西在守它。
  ⭐ 这正是本轮一直在修的形状：**一个数字写在文档里，没人守**。
  ⇒ 声明式的数字一律改成实测：这里跑一次，写进 .selftest-measured.json，
    元门禁 selftest-count-measured 再拿文档去和它对账。

⚠️ 反例数为什么给两个口径：
  「反例」有两种数法 —— ①标题里带「反例」二字；②期望值是非零退出码。
  两者都不完美（有的正例期望 2「没量到」，有的反例标题不写「反例」）。
  ⛔ 挑一个好看的报出来，就是**自相矛盾的统计**。这里两个都报，
  不一致时明确说「这两个口径本来就不一样」，不假装只有一个真值。

⚠️ 「打印了 ❌/✗ 却退出 0」单独报（disagree）：
  它要么是自证在回显被测场景的输出（该加「│ 」归属前缀，见 gate-run/mutation-sweep），
  要么是真 landmine（判定与退出码脱钩）。两种都必须被看见，不许静默折叠成任何一边。
"""
import hashlib, json, os, re, subprocess, sys, tempfile, time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
# ⚠️ **量具本身错了**（2026-09-06 当场抓到）：第一版只认 `✅/❌`，
#   而 7 个脚本的自证用 `✓/✗`（_argv / _prd_parse / _scene_parse / tokens-to-css /
#   _argv.mjs / _page-helpers.mjs / _browser.mjs）。
#   于是它们全被数成「用例 0 · 失败 0 · 退出码 0」——
#   ⛔ **「自证没跑」和「自证全过」在统计里长得一模一样**，
#   而我差点把这个系统性偏低的数字写进文档当权威值。
#   ⭐ 要求前导空格：门禁**报告正文**里的 ✅/❌ 顶格打印，不能算成自证用例。
#   ⭐ 嵌套回显（自证里转印被测场景的输出）约定加「│ 」前缀 —— 前缀挡在
#     空白与记号之间，天然不匹配本正则。谁在报红，和有没有红一样重要。
# ⚠️ 解析口径一变（比如 ✗ 开始计入失败），按 mtime 复用的旧记录就是**旧口径的数字**——
#   加版本号：口径变了，缓存全部作废重测。mtime 只知道被测物变没变，不知道量具变没变。
PARSER = 3   # 3：失败改按记号位判定（此前行内 grep，绿用例标题含 ✗ 字样会被数成失败）
CASE = re.compile(r'^\s+(✅|❌|✓|✗|⊘)\s')  # ⊘ = 跳过（可见但不算失败）
EXPECT_NONZERO = re.compile(r'期望\s*[1-9]')


def sha_of(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def has_selftest(path):
    try:
        with open(path, encoding='utf-8') as f:
            return '--self-test' in f.read()
    except Exception:
        return False


def _tree_diff(root):
    """本次测量所在的树与 HEAD 的差异路径（**仓库根**相对，git 自己的口径）。

    ⚠️ 2026-09-11 自查：这行原来写「相对 skill 根」—— 实测返回的是
      `skills/product-flow/scripts/x.py` 这种仓库根相对路径。**昨天刚写的代码里的文档谎话**，
      而它出现在一个专治「声称 vs 实际」的模块里。

    ⚠️ 诚实边界：拿不到 git（不是仓库 / 没装 git / 超时）时返回 **None** —— 
      ⛔ 不返回 `[]`：那等于宣称「树是干净的」，是一句没有依据的话。
      消费方必须把 None 当「不知道」，不当「干净」。
    """
    try:
        out = subprocess.run(['git', 'status', '--porcelain', '--', '.'],
                             cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=20)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return sorted(ln[3:].strip() for ln in
                  out.stdout.decode('utf-8', 'replace').splitlines() if ln[3:].strip())


def _head_sha(root):
    """测量时的 HEAD。

    ⚠️ 2026-09-11：treeDiff 单独存在时**说不清跟哪个 HEAD 比的** —— 落盘后一次提交，
      「与 HEAD 有 5 处差异」里的 HEAD 就已经不是同一个了，读的人会以为那些文件还脏着。
      ⭐ 本仓早有这条：**差集判据必须锚 commit**。拿不到返回 None（不编）。
    """
    try:
        out = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=root,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
    except Exception:
        return None
    return out.stdout.decode().strip() if out.returncode == 0 else None


def sweep_dir(scripts_dir, prog_path, out_path, fresh):
    """⚠️ 2026-09-06：这个跑手连续两次**跑到一半被杀**（本机常年 8-11 个 claude 会话并行，
    别的会话「起跑时清上一轮」会按进程名误杀）。头一次还因为 `| tail` 的管道缓冲，
    30 分钟的输出**一个字都没留下**。
    ⇒ 逐门禁落盘 + 可续跑。⛔ 续跑必须校验**内容哈希**：
      内容变过就重跑那道 —— 否则「续跑」就是拿旧数字充数，
      正是本仓一直在修的「声称的≠实际的」。
    """
    done = {}
    if not fresh and os.path.exists(prog_path):
        for ln in open(prog_path, encoding='utf-8'):
            try:
                r = json.loads(ln)
                done[r['file']] = r
            except Exception:
                pass
    elif fresh and os.path.exists(prog_path):
        # 🚨 2026-09-12 实测踩到：上一轮报了 4 个用例失败，我跑 --fresh 复现 —— 全绿，
        #   **而那 4 个失败是哪几条已经无从查起**：--fresh 把唯一的记录删掉了。
        #   ⭐ 「复现不了」和「本来就没发生」在这里代码上无法区分，
        #     偏偏复现不了的失败才是最需要留证的那种。
        #   ⇒ 不删，改名归档。留最近 5 份，够回溯又不会无限堆。
        import time as _t, glob as _g
        os.rename(prog_path, prog_path + '.' + _t.strftime('%Y%m%d-%H%M%S'))
        old_archives = sorted(_g.glob(prog_path + '.2*'))
        for _a in old_archives[:-5]:
            os.remove(_a)
    files = sorted(f for f in os.listdir(scripts_dir)
                   if (f.endswith('.py') or f.endswith('.mjs'))
                   and has_selftest(os.path.join(scripts_dir, f)))
    results = []
    for f in files:
        p = os.path.join(scripts_dir, f)
        # ⚠️ 缓存键锚**内容哈希**不锚 mtime：mutation-sweep / reverse-test 的复原
        #   是重写文件 —— 内容一个字没变、mtime 变了。锚 mtime 会把「复原过」
        #   误读成「改过」，天天逼人白测；反过来内容变了 mtime 相同倒是几乎不会发生。
        h = sha_of(p)
        prev = done.get(f)
        # ⚠️ 只复用**绿的**记录：失败可能是环境性的（本机清场会杀掉 chrome 子进程、
        #   sweep 中途依赖文件还是旧格式）—— 缓存失败等于把一次事故钉成永久结论。
        #   成功才缓存；失败的每次续跑都重试，代价只有失败集那几个。
        if (prev and prev.get('sha') == h and prev.get('parser') == PARSER
                and prev.get('rc') == 0 and not prev.get('failures')):
            results.append(dict(prev, cached=True))
            continue                      # 已测、内容没变、且是绿的 —— 可以复用
        cmd = ([sys.executable, p] if f.endswith('.py') else ['node', p]) + ['--self-test']
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=scripts_dir, timeout=900)
        except subprocess.TimeoutExpired as e:   # 单个自证挂死不拖住整轮
            r = subprocess.CompletedProcess(cmd, 124, e.stdout or '', (e.stderr or '') + '\n⏱️ 自证超时 900s 被杀')
        out = (r.stdout or '') + (r.stderr or '')
        # ⚠️ 失败看**记号位**（正则捕获组），不是行内 grep ——
        #   「✅ 标题里提到 ✗ 的正例」曾被数成失败（被咬的正是本脚本自己的自证标题）。
        matched = [(CASE.match(ln).group(1), ln) for ln in out.splitlines() if CASE.match(ln)]
        cases = [ln for _, ln in matched]
        bad = [ln for mark, ln in matched if mark in ('❌', '✗')]
        # ⚠️ ⊘ 是**跳过**不是失败：变异打在基线就红的规则上，证明不了任何事。
        #   ⛔ 但也不许无声 —— 单独计数并打印，否则「跳过」和「跑过」在产物上一样。
        skipped = [ln for mark, ln in matched if mark == '⊘']
        rec = {'file': f, 'sha': h, 'parser': PARSER, 'rc': r.returncode, 'cases': len(cases),
               'failures': len(bad), 'skipped': len(skipped),
               'negNumeric': sum(1 for ln in cases if EXPECT_NONZERO.search(ln)),
               'negLabel': sum(1 for ln in cases if '反例' in ln)}
        results.append(rec)
        with open(prog_path, 'a', encoding='utf-8') as fh:   # 逐条落盘：被杀只丢当前这一道
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
            fh.flush()
        mark = '⚠️' if (r.returncode == 2 and not bad) else ('❌' if (r.returncode != 0 or bad) else '✅')
        print('  %s %s（退出码 %d · 用例 %d · 失败 %d）'
              % (mark, f, r.returncode, len(cases), len(bad)), flush=True)
        for ln in bad[:3]:
            print('     ' + ln.strip(), flush=True)
        if skipped:
            print('     ⊘ 跳过 %d 条（基线就红的规则，变异证明不了任何事）' % len(skipped),
                  flush=True)
        if r.returncode == 0 and bad:
            print('     ⚠️ 打印了红却退出 0 —— 要么是回显没加「│ 」归属前缀，'
                  '要么判定与退出码脱钩（landmine），去看这道门', flush=True)

    # rc=2 是「跑不了」（环境/依赖缺席），不是「测出失败」—— 混在一起会把浏览器缺席
    # 数成几十个失败（Codex 隔离环境实测 45 个「失败」全是环境码）。UNABLE 单列，不折进 failed 也不算绿。
    # 🚨🚨 2026-09-10 实测揪出的第二类 UNABLE：**脚本崩溃时未必退 2**。
    #   本机磁盘满（可用一度仅 39Mi）那次，套件跑到一半被资源掐断 ⇒
    #   14 个脚本在**字母序上连续的尾部**集体「失败」，而它们**单跑全部 rc=0**。
    #   ⭐ 它们退的是 1 或别的码、且**一个用例都没产出** —— 那意味着
    #     **自证根本没跑起来**，不是「测出了失败」。旧判据只认 rc==2，于是
    #     把一次环境事故报成了 14 个内容缺陷。
    #   ⭐⭐ 与我此前报给并行会话的 .mjs flaky **是同一形状**（「跑不了」被记成
    #     「测出失败」），只是触发源从端口换成了磁盘 —— 同一个病在两处各犯一次。
    #   ⇒ 判据加一条：**非零退出 + 零用例 + 零红标记 ⇒ UNABLE**。
    #     ⛔ 仍不折成通过：UNABLE 单列，套件整体退 2。
    #   ⚠️ 量程：产出了用例又崩的（跑了一半崩）仍归 failed —— 那时至少有真实测量在场，
    #     把它当 UNABLE 会掩盖真失败。**宁可把「半截」算失败，不可把失败算「没测」。**
    def _no_evidence(r):
        return r['rc'] != 0 and r['cases'] == 0 and not r['failures']

    unable = [r['file'] for r in results
              if (r['rc'] == 2 and not r['failures']) or _no_evidence(r)]
    failed = [r['file'] for r in results if (r['rc'] != 0 or r['failures']) and r['file'] not in unable]
    disagree = [r['file'] for r in results if r['rc'] == 0 and r['failures']]

    # 🚨 2026-09-10（并行会话把它照出来了）：**这个数字量的是「工作树」，
    #   而 design-quality-gates.md 声称的是「clone 下来会得到的数」——两个总体。**
    #   实测：对方一个未提交的 `templates/evidence-receipt.json` 让 doc-sync-guard
    #   多出 1 个用例，一个未提交的 `receipt-check.py` 多出 9 个 ⇒ 工作树 879 / clone 869。
    #   而 `selftest-count-measured` 把这 10 的差额报成了「文档数字过期」。
    #   ⭐ 判决没错（数字确实对不上），**诊断错了** —— 而本仓的记录是
    #     「错误诊断比漏报贵」：照着它去改文档，会把 clone 口径的正确数字改成错的。
    #   ⇒ 落盘时把**总体**一起记下来：测量发生在与 HEAD 有哪些差异的树上。
    #   ⛔ 只记录、不改判决：树脏不是豁免（那会让真的文档漂移躲在脏树后面）。
    _root_for_git = os.path.dirname(os.path.dirname(os.path.abspath(out_path)))
    data_tree = _tree_diff(_root_for_git)
    data_head = _head_sha(_root_for_git)
    data = {
        'measuredAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'scripts': len(results),
        'cases': sum(r['cases'] for r in results),
        'failures': sum(r['failures'] for r in results),
        'failedScripts': failed,
        'unableScripts': unable,
        'cachedScripts': sorted(r['file'] for r in results if r.get('cached')),
        'disagree': disagree,
        'shas': {r['file']: r.get('sha') for r in results},
        # 🚨 2026-09-11：逐门数字必须进这份**一次性写完**的快照。
        #   `gate-has-negative` 第一版读的是 `.selftest-progress.jsonl` ——
        #   那是**边跑边追加**的，而它自己就在这次运行里被调用：跑到 consistency-gate 时
        #   后面的门还没测，规则就报「名册里的门没被测过」。⭐ 自指回路，
        #   与当年 810↔747 振荡同源：**判据消费的文件，正由调用它的那次运行生产**。
        #   ⇒ 消费方一律改读本快照（写在全部跑完之后，天然完整）。
        'perGate': {r['file']: {'cases': r['cases'],
                                'negNumeric': r['negNumeric'],
                                'negLabel': r['negLabel']} for r in results},
        'negativesByExpectation': sum(r['negNumeric'] for r in results),
        'negativesByLabel': sum(r['negLabel'] for r in results),
        'command': 'python3 scripts/selftest-all.py',
        'treeDiff': data_tree,   # None＝问不到 git；[]＝与 HEAD 一致
        'headAt': data_head,     # 上面那个 diff 是**跟这个 commit** 比的
    }
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    return data


def main():
    fresh = '--fresh' in sys.argv
    prog_path = os.path.join(os.path.dirname(SCRIPTS), 'references', '.selftest-progress.jsonl')
    out_path = os.path.join(os.path.dirname(SCRIPTS), 'references', '.selftest-measured.json')
    data = sweep_dir(SCRIPTS, prog_path, out_path, fresh)
    print('\n脚本 %d 个 · 用例 %d 个 · 失败 %d 个' % (data['scripts'], data['cases'], data['failures']))
    print('反例：按期望非零 %d 个 / 按标题带「反例」 %d 个%s'
          % (data['negativesByExpectation'], data['negativesByLabel'],
             '　（两个口径本来就不一样，不是矛盾）'
             if data['negativesByExpectation'] != data['negativesByLabel'] else ''))
    if data['disagree']:
        print('⚠️ 打印了红却退出 0（回显缺归属前缀，或判定与退出码脱钩）：'
              + '、'.join(data['disagree']))
    if data['unableScripts']:
        print('⚠️ 跑不了（rc=2，环境/依赖缺席 —— 是 UNABLE，不是失败，也**不是通过**）：'
              + '、'.join(data['unableScripts']))
    _cached = data.get('cachedScripts') or []
    print('本轮真跑 %d / 缓存复用 %d（发布证据要求全 fresh：--fresh）'
          % (data['scripts'] - len(_cached), len(_cached)))
    print('已写入 references/.selftest-measured.json')
    # 失败 → 1；只有环境性 UNABLE → 2（不许显示成全绿）；全过 → 0
    return 1 if data['failedScripts'] else (2 if data['unableScripts'] else 0)


def self_test():
    """量具自己的自证 —— 它数错过一次（✓/✗ 全漏），不能再靠肉眼信它。

    夹具是五个已知答案的假脚本：
      a  三条用例一条 ❌、退出 1        → cases 3 / failures 1 / 进 failedScripts
      b  两条 ✓、退出 0                → ✓ 口径被数到（就是那次数错的形状）
      c  嵌套「│ ❌」+ 顶格 ❌ + 真用例×2（一条标题含 ✗❌ 字样）→ 只数真用例，失败看记号位
      d  打印 ❌ 却退出 0（landmine）   → 算失败 + 进 disagree（不许静默折叠）
      f  一条 ✗、退出 1                → ✗ 也算失败（首版只认 ❌，✗ 的失败会漏数）
    """
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        print(('  ✅ ' if cond else '  ❌ ') + name + ('' if cond else '　' + extra))
        ok = ok and cond

    d = tempfile.mkdtemp(prefix='sta-')
    fx = {
        'a.py': ('# --self-test\n'
                 'print("  ✅ 正例 甲")\n'
                 'print("  ✅ 反例：坏输入必须红　期望 1 实得 1")\n'
                 'print("  ❌ 反例：漏网　期望 1 实得 0")\n'
                 'raise SystemExit(1)\n'),
        'b.py': ('# --self-test\n'
                 'print("  ✓ 短记号 正例")\n'
                 'print("  ✓ 短记号 反例 期望 2")\n'),
        'c.py': ('# --self-test\n'
                 'print("  │ ❌ 嵌套回显的红（被测场景的预期产物）")\n'
                 'print("❌ 顶格的报告正文")\n'
                 'print("  ✅ 真用例")\n'
                 'print("  ✅ 标题里提到 ✗ 与 ❌ 字样的正例（失败看记号位不看行内）")\n'),
        'd.py': ('# --self-test\n'
                 'print("  ❌ 判定说失败")\n'),           # 却退出 0：landmine
        'f.py': ('# --self-test\n'
                 'print("  ✗ 短记号的失败")\n'
                 'raise SystemExit(1)\n'),
        'g.py': ('# --self-test\n'
                 'print("UNABLE: 环境里没有浏览器")\n'
                 'raise SystemExit(2)\n'),          # 环境性 UNABLE：单列，不算失败不算绿
        # 🚨 2026-09-10：**崩溃时未必退 2** —— 磁盘满那次，脚本退 1 且一个用例都没产出。
        #   旧判据只认 rc==2 ⇒ 把一次环境事故报成 14 个内容缺陷。
        'h.py': ('# --self-test\n'
                 'import sys; sys.stderr.write("OSError: No space left on device\\n")\n'
                 'raise SystemExit(1)\n'),          # 非零退出 + **零用例** ⇒ 也是 UNABLE
        # ⛔ 对照组：跑了一半崩（有用例、也有红）仍必须算 failed ——
        #   那时至少有真实测量在场，把它当 UNABLE 会掩盖真失败。
        'i.py': ('# --self-test\n'
                 'print("  ✅ 正例")\n'
                 'print("  ❌ 反例：真失败")\n'
                 'raise SystemExit(1)\n'),
        # 🚨 2026-09-12 查清的悬案：consistency-gate 用 ✗ 同时表示「变异没被杀死」（真失败）
        #   和「基线就红所以跳过」（证明不了任何事）—— **一个记号两个含义、严重性相反**。
        #   于是 4 个跳过被数成 4 个失败，而我上一轮还查不出是哪 4 个。
        #   ⇒ 跳过改用 ⊘。这一对用例锁住两个方向：⊘ 不算失败，✗ 仍算失败。
        'j.py': ('# --self-test\n'
                 'print("  ✅ 正例")\n'
                 'print("  ⊘ 跳过：基线就红，这发变异证明不了任何事")\n'
                 'print("  ⊘ 跳过：同上")\n'),
    }
    for name, src in fx.items():
        open(os.path.join(d, name), 'w', encoding='utf-8').write(src)
    import io as _io, contextlib as _ctx
    buf = _io.StringIO()
    with _ctx.redirect_stdout(buf):
        data = sweep_dir(d, os.path.join(d, 'prog.jsonl'), os.path.join(d, 'out.json'), True)
    for _ln in buf.getvalue().splitlines():
        print('  │ ' + _ln)
    rec = {r['file']: r for r in
           (json.loads(x) for x in open(os.path.join(d, 'prog.jsonl'), encoding='utf-8'))}

    chk('九个夹具全被发现', data['scripts'] == 9, '实得 %d' % data['scripts'])
    # 🚨 2026-09-12：⊘ 的两个方向。
    chk('j：⊘ 跳过**不算失败**（基线就红的变异证明不了任何事）',
        rec['j.py']['failures'] == 0, '实得 %s' % rec['j.py'].get('failures'))
    chk('j：⊘ 跳过仍**被计为用例并单独计数**（⛔ 跳过不许无声）',
        rec['j.py']['cases'] == 3 and rec['j.py'].get('skipped') == 2,
        '实得 cases=%s skipped=%s' % (rec['j.py']['cases'], rec['j.py'].get('skipped')))
    chk('对照：f 的 ✗ **仍算失败**（改的是跳过的记号，不是把 ✗ 放开）',
        rec['f.py']['failures'] == 1, '实得 %s' % rec['f.py'].get('failures'))
    # 🚨 2026-09-10 新增的一对：治「崩溃时未必退 2」。
    chk('h：非零退出 + **零用例** ⇒ UNABLE（跑不起来 ≠ 测出失败）',
        'h.py' in data['unableScripts'] and 'h.py' not in data['failedScripts'],
        '实得 unable=%s failed=%s' % (data['unableScripts'], data['failedScripts']))
    chk('i：跑了一半崩（有用例有红）⇒ 仍算 failed（⛔ 不许把真失败当「没测」）',
        'i.py' in data['failedScripts'] and 'i.py' not in data['unableScripts'],
        '实得 unable=%s failed=%s' % (data['unableScripts'], data['failedScripts']))
    chk('g：rc=2 进 unableScripts，不进 failedScripts（环境缺席≠测出失败）',
        'g.py' in data['unableScripts'] and 'g.py' not in data['failedScripts'],
        '实得 unable=%s failed=%s' % (data['unableScripts'], data['failedScripts']))
    chk('a：用例 3 · 失败 1', (rec['a.py']['cases'], rec['a.py']['failures']) == (3, 1),
        '实得 %s' % [(rec['a.py']['cases'], rec['a.py']['failures'])])
    chk('b：✓ 口径被数到（用例 2 · 失败 0）',
        (rec['b.py']['cases'], rec['b.py']['failures']) == (2, 0))
    chk('c：嵌套「│」/顶格不算；标题含 ✗❌ 字样的绿用例不算失败（用例 2 · 失败 0）',
        (rec['c.py']['cases'], rec['c.py']['failures']) == (2, 0),
        '实得 %s' % [(rec['c.py']['cases'], rec['c.py']['failures'])])
    chk('d：打印红却退出 0 → 算失败且进 disagree',
        rec['d.py']['failures'] == 1 and 'd.py' in data['disagree']
        and 'd.py' in data['failedScripts'])
    chk('f：✗ 的失败也被数到（首版只认 ❌ 会漏）', rec['f.py']['failures'] == 1)
    chk('总数对得上（3+2+2+1+1+2+3=14 用例 · 4 失败；h 零用例不计入、j 的 ⊘ 不计失败）',
        (data['cases'], data['failures']) == (14, 4),
        '实得 %s' % [(data['cases'], data['failures'])])
    # a 贡献 2/2；b 那行「反例 期望 2」两个口径同时命中，贡献 1/1
    chk('反例口径各自独立（期望非零 3 · 标题带「反例」4）',
        (data['negativesByExpectation'], data['negativesByLabel']) == (3, 4),
        '实得 %s' % [(data['negativesByExpectation'], data['negativesByLabel'])])
    # 续跑缓存三条语义：绿的复用 / 失败的重试 / 量具口径变了全体作废。
    # 夹具里 a、d、f、i 是失败的（4 个），g、h 是 UNABLE（2 个）—— 六个每轮都重试，固定 +6；
    #   b、c、j 是绿的（3 个），复用。初始 9 条记录。
    #   ⭐ j 绿说明 ⊘ 没被当成失败 —— 否则它会跟着每轮重试，这几个数字全变。
    buf2 = _io.StringIO()
    with _ctx.redirect_stdout(buf2):
        sweep_dir(d, os.path.join(d, 'prog.jsonl'), os.path.join(d, 'out.json'), False)
    n2 = sum(1 for _ in open(os.path.join(d, 'prog.jsonl'), encoding='utf-8'))
    chk('续跑：绿的复用，失败/UNABLE 的重试（+6）—— 失败可能是环境性的，缓存失败=把事故钉成结论',
        n2 == 15, '实得 %d' % n2)
    # 复原式重写：内容没变、mtime 变了的**绿**记录 → 仍复用（mutation-sweep/reverse-test 天天这么干）
    os.utime(os.path.join(d, 'b.py'), None)
    with _ctx.redirect_stdout(_io.StringIO()):
        sweep_dir(d, os.path.join(d, 'prog.jsonl'), os.path.join(d, 'out.json'), False)
    n3 = sum(1 for _ in open(os.path.join(d, 'prog.jsonl'), encoding='utf-8'))
    chk('只动 mtime（复原式重写）→ 绿记录仍复用，不把「复原过」误读成「改过」（仍只 +6）',
        n3 == 21, '实得 %d' % n3)
    with open(os.path.join(d, 'b.py'), 'a', encoding='utf-8') as fh:
        fh.write('# 内容真的变了\n')
    with _ctx.redirect_stdout(_io.StringIO()):
        sweep_dir(d, os.path.join(d, 'prog.jsonl'), os.path.join(d, 'out.json'), False)
    n4 = sum(1 for _ in open(os.path.join(d, 'prog.jsonl'), encoding='utf-8'))
    chk('绿记录的内容变了 → 必须重测（+6 重试 +1 b）', n4 == 28, '实得 %d' % n4)
    # ⚠️ 口径升降必须放最后：升上去那轮的记录 parser 不同，降回来会全体重测，
    #   放在中间会污染后续所有计数（第一版就是这么写错的）。
    global PARSER
    _old = PARSER
    try:
        PARSER = _old + 1
        buf3 = _io.StringIO()
        with _ctx.redirect_stdout(buf3):
            sweep_dir(d, os.path.join(d, 'prog.jsonl'), os.path.join(d, 'out.json'), False)
    finally:
        PARSER = _old
    n5 = sum(1 for _ in open(os.path.join(d, 'prog.jsonl'), encoding='utf-8'))
    chk('解析口径变了 → 缓存作废全部重测（旧口径数字不许被当新结果复用）',
        n5 == 37, '实得 %d' % n5)
    print('\n%s' % ('✅ 自证通过：量具在量它声称量的东西' if ok else '❌ 自证失败：先修量具'))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or ''); print('用法: selftest-all.py [--fresh] [--self-test]'); sys.exit(0)
    sys.exit(self_test() if '--self-test' in sys.argv else main())
