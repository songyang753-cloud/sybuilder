#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁结果落盘 —— v2 运行写进 `.product-flow/runs/<runId>/gates/`；无计划时兼容旧目录。
（参数里带 G2/G3/G0.6 这类子门号时进键，如 `reconcile-gate.py.G2.json` —— G2/G3 各留各的记录，
不再共用一条互相覆盖）。

═══ 为什么需要它（OPP-09）═══
本流水线有 46 道门禁（口径＝`_roster.gate_names()`，唯一正本）。
⚠️ 2026-09-10：这里曾长期写着「22 道」——**过期了六道而无人发现**，
   因为 `gate-count` 这条元规则当时**只扫 md，不扫脚本 docstring**。
   ⭐ 不是判据写错了，是**它没往这儿看**。量程已扩（脚本里只认「本流水线共 N 道」这类总数句式）。它们各自都能出声，**而声音落在终端里就没了**。
于是「一道门从来没跑过」与「跑过且通过」在项目里长得一模一样。三个实测实例：

  · sample-project 的 `.product-flow/reconcile/` 是**空目录** —— 那份 PRD 有 355 FR / 431 AC，
    G2/G3 **从未产出过任何结论**，无人察觉
  · `browser-audit` 不带 `--all-routes` 只审首屏：同一份 demo「9 通过 1 失败」
    vs「26 通过 **11 失败**」——那 10 个真实失败项一直都在，只是没人看见
  · `reconcile-gate G2` 的 AC 集合曾恒为空 —— 那道门**报绿而一条 AC 都没对过**

⭐ 三个实例是同一个形态：**缺口不报错，它安静地什么都不查，然后看起来像通过。**

═══ 为什么是封装而不是改每一个门禁脚本 ═══
改 22 处必然分叉，而分叉那天每一处都还是绿的（本 SOP 反复记的那类）。
本脚本**不修改任何门禁**：跑它、抓退出码与 stdout、落盘、**原样透传退出码**。
门禁仍可独立运行，行为一个字节都不变。

═══ ⚠️⚠️ 退出码语义在门禁之间**并不一致** ═══
2026-09-04 普查 22 道门发现：

  20 道：0=通过  1=不通过  2=跑不了
  `prd_completeness_check.py`：0=达标  **2=有缺口**  **3=输入无效**
  `coverage_check.py`：0=通过  1=有漏  2=输入无效  **3=对账通过但有未解决缺口**

⛔ 天真的封装（`2 → UNABLE`）会把 `prd_completeness` 的**真失败标成「跑不了」**——
而「跑不了」正是最容易被耸肩带过的那一档。**把 FAIL 伪装成 UNABLE 是最坏的一种误标。**
⭐ 因此这里有一张**显式语义表**，并由 `consistency-gate` 的 `exit-semantics-declared`
规则守着：**新增门禁没登记语义 → 元门禁红**。不许靠默认值猜。

用法:
  gate-run.py <门禁脚本> [门禁自己的参数...]   # 跑并落盘，透传退出码
  gate-run.py --status [--root <项目根>]        # 有哪些门 / 哪些跑过了 / 各自挂在哪个阶段
  gate-run.py --status --gate                  # 当前计划必跑项缺失或非 PASS 就退出 1
  gate-run.py --self-test
退出码: 透传被跑的那道门；`--status` 恒 0（只呈现）；
        `--status --gate` 在案有 FAIL/**UNABLE**/UNKNOWN 或计划必跑项 NOT-RUN 时退 1；
        2=本脚本自己跑不了

⭐⭐ 为什么要有 `--gate`（来自 peer 会话的 A16）：
   **一道会红但不阻断的门，和一道不存在的门，差别只在于它给了你一个「我看到了」的错觉。**
   自检问句：**这道门红的时候，会有什么动作被真的挡住？** 答不出具体动作 = 它只是建议。
   v2 由 workflow registry 按运行模式与条件计算适用项：**必跑 NOT-RUN 必须挡**。
   没有 v2 计划时只提供旧式诊断，不凭空替项目猜适用性。
"""
import hashlib, io, json, os, re, signal, subprocess, sys, time

from _workflow import (WorkflowError, gate_result_dir, load_active_run,
                       load_registry, resolve_plan, sha256_file, gate_evidence, evidence_current,
                       required_rule_ids)

MAX_STDOUT = 256 * 1024          # PRD 附件 E：单个 stdout 上限
RESULT_DIR = os.path.join('.product-flow', 'gates')

# 退出码 → 结论。**每道门禁都必须在这里登记**，没有默认值。
STD = {0: 'PASS', 1: 'FAIL', 2: 'UNABLE'}
# 外部挂接的门禁：脚本不在本 skill 的 scripts/ 里，正本归别的 skill 所有。
# 元门禁 exit-semantics-declared 对这些键不做「本地脚本存在」核对（但语义仍必须登记在上表）。
EXTERNAL_GATES = {
    'selfcheck.sh': '<resolved-coding-standards>/scripts/selfcheck.sh',
}
EXIT_SEMANTICS = {
    'ai-slop-gate.py': STD, 'audience-gate.py': STD, 'cdp-reuse-gate.py': STD,
    'serial-orchestration-gate.py': STD, 'spec-authoring-gate.py': STD, 'report-structure-gate.py': STD,
    'feishu-delivery-gate.py': STD, 'dingtalk-delivery-gate.py': STD, 'research-quality-gate.py': STD,
    'chain-gate.py': STD, 'consistency-gate.py': STD,
    'no-loss-gate.py': STD,
    'diagram-id-gate.py': STD,
    'coordination-gate.py': STD,
    'definition-gate.py': STD, 'demo-anchor-gate.py': STD, 'design-intent-gate.py': STD,
    'element-identity-gate.py': STD, 'figma-editability-gate.py': STD,
    'interaction-gate.py': STD, 'reconcile-gate.py': STD,
    'requirements-quality-gate.py': STD, 'research-gate.py': STD, 'retro-gate.py': STD,
    'tech-research-gate.py': STD,
    's8-solution-gate.py': STD, 's9-quality-report-gate.py': STD,
    's9-product-walkthrough-gate.py': STD,
    's9-dev-slice-gate.py': STD, 's9-launch-rollback-gate.py': STD,
    'spec-sync-gate.py': STD, 'token-provenance-gate.py': STD, 'visual-spec-gate.py': STD,
    # 🚨 2026-09-09 补登记：`browser-audit.mjs` 是 S6 出场必跑的浏览器档视觉审计，
    #   门禁目录里出现 13 次，却因为**文件名不含 `-gate`** 一直落在 gate_files 量程外
    #   ⇒ 从没登记过退出码语义，落盘时会被标 UNKNOWN。
    #   ⭐ 「命名约定被当成判据」的第二次复发（第一次是那两个 `_check.py`）。
    'browser-audit.mjs': STD,
    # 外部挂接：coding-standards 的自洽门（S9.1 Build 模式出场要求其结论在案）。
    # 它证明「依据的规范正本在场且自洽」，⛔ 证明不了「代码照做了」——那种机器门
    # 对方按其 B4 有意不提供（源码正则两头不承重）。3=没能测、4=门自身坏：都不是通过。
    'selfcheck.sh': {0: 'PASS', 1: 'FAIL', 2: 'UNABLE', 3: 'UNABLE', 4: 'UNABLE'},
    'dead-click-gate.mjs': STD, 'flow-walk-gate.mjs': STD,
    'platform-parity-gate.mjs': STD, 'scenario-matrix-gate.mjs': STD,
    'mock-seam-gate.mjs': STD, 'g75-freeze-gate.py': STD,
    'business-map-gate.py': STD, 'product-structure-gate.py': STD, 'intent-gate.py': STD,
    'traversal-coverage-gate.py': STD,   # S2 报告⟷deep-tree 覆盖对账;0=绿 1=红 2=UNABLE(崩溃/缺输入)
    # ⚠️ 这两道不走标准语义 —— 见文件头
    'prd_completeness_check.py': {0: 'PASS', 2: 'FAIL', 3: 'UNABLE'},
    'coverage_check.py': {0: 'PASS', 1: 'FAIL', 2: 'UNABLE', 3: 'PASS_WITH_GAPS'},
}


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def verdict_of(gate, rc):
    """退出码 → 结论。**登记表里没有的组合一律 UNKNOWN**，不猜。

    ⛔ 猜一个默认值会把「这道门用了我不认识的退出码」变成一个看起来确定的结论 ——
    而那正是本文件要治的病。UNKNOWN 是诚实的，PASS 不是。
    """
    table = EXIT_SEMANTICS.get(gate)
    if table is None:
        return 'UNKNOWN', '门禁 %s 没有登记退出码语义' % gate
    if rc not in table:
        return 'UNKNOWN', '%s 的退出码 %d 不在登记的语义里（登记了 %s）' % (
            gate, rc, '/'.join(str(k) for k in sorted(table)))
    return table[rc], None


# ── 前置顺序（SOP 写了，但此前没有任何东西守）───────────────────────────
# SKILL.md S6 明确写着「demo-anchor-gate **必须排在 G2 之前**：锚点是 G2/G3 的输入，
# 缺了它们只会 UNABLE，而 UNABLE 太容易被当成『跑过了』耸肩带过」。
# ⭐ 这正是本 SOP 反复记的那类：**契约写对了 ≠ 有人守它**。
# ⛔ 但不许硬拒 —— 单独跑一道门调试是合法用法。做法是：
#    把一个可耸肩带过的 UNABLE，变成**一句有指向的话**。
PREREQ = {
    'reconcile-gate.py':   ['demo-anchor-gate.py'],
    'demo-anchor-gate.py': ['scenario-matrix-gate.mjs'],   # 锚点由它 --dump 导出
}


def prereq_state(gate, root, manifest=None):
    """返回 [(前置门, 状态)]，状态取 PASS / 别的结论 / NOT-RUN。"""
    out = []
    for g in PREREQ.get(gate, []):
        f = os.path.join(gate_result_dir(root, manifest), g + '.json')
        if not os.path.exists(f):
            out.append((g, 'NOT-RUN')); continue
        try:
            record = json.load(io.open(f, encoding='utf-8')) or {}
            verdict = record.get('verdict', 'UNKNOWN')
            if verdict == 'PASS' and (not evidence_current(record.get('evidence')) or
                    (manifest and (record.get('runId') != manifest['runId'] or
                                   record.get('planHash') != manifest['planHash']))):
                verdict = 'STALE'
            out.append((g, verdict))
        except Exception:
            out.append((g, 'UNREADABLE'))
    return out


def run_child(cmd, timeout=900):
    """Own a session so timeout cleanup cannot kill another user's browser."""
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=(os.name == 'posix')) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
            return subprocess.CompletedProcess(cmd, child.returncode, stdout, stderr)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                child.kill()
            stdout, stderr = child.communicate()
            return subprocess.CompletedProcess(cmd, 124, stdout,
                stderr + '\nUNABLE: gate timed out after %ss' % timeout)


def run(argv, root, adhoc=False):
    try:
        manifest, _ = load_active_run(root, required=False)
    except Exception as e:
        die('活动运行无效，拒绝把新结果写进不明运行：%s' % e)
    if not manifest and not adhoc:
        die('没有 v2 活动运行；先用 product-flow-run.py plan --write 建计划。'
            '只做不计入声明的调试请显式加 --adhoc')
    gate_path = argv[0]
    if not os.path.isfile(gate_path):
        die('门禁脚本不存在：%s' % gate_path)
    gate = os.path.basename(gate_path)
    # 落盘键 = 脚本名[+子门号]。G2/G3 曾共用 reconcile-gate.py.json 互相覆盖 ——
    # 一条 PASS 顶两门（Codex 复审定为 P0 假阳性）。子门号进键，各留各的记录。
    sub = next((a for a in argv[1:] if re.match(r'^G\d[\d.]*$', a)), None)
    key = gate + ('.' + sub if sub else '')
    if manifest and manifest.get('schemaVersion') == '2.0':
        planned = {x.get('gate') for x in manifest.get('gatePlan', [])}
        if key not in planned and not adhoc:
            die('门禁 %s 不在当前运行 gatePlan；调试请显式加 --adhoc' % key)
        def option(name, default=None):
            for i, arg in enumerate(argv[1:], 1):
                if arg == name: return argv[i + 1] if i + 1 < len(argv) else None
                if arg.startswith(name + '='): return arg.split('=', 1)[1]
            return default
        if not adhoc and gate == 'report-structure-gate.py' and option('--mode') != manifest.get('researchMode'):
            die('报告 mode 必须与当前计划 researchMode 一致；不能用旧摘要门代替正式深拆')
        if not adhoc and gate == 'research-quality-gate.py' and option('--phase', 'final') != 'final':
            die('发布前 pre 评审不能充当 S2 最终页面验收；调试请用 --adhoc')
        if not adhoc and gate == 'tech-research-gate.py' and not option('--post'):
            die('技术调研正式记录须 --post（内含 --pre 与全文/媒体回读）；本地检查请用 --adhoc')
        if not adhoc and gate == 'coverage_check.py' and '--design-only' in argv:
            if any(m.startswith('S9') for m in manifest.get('modules', [])):
                die('设计对账不能代替 S9 实际测试；请另签 TESTCASES 设计模块结果')
        if not adhoc and gate == 'diagram-id-gate.py' and '--formal' not in argv:
            die('正式图交付需要 --formal，旧图源诊断不能抵消图位/渲染验收')
        if not adhoc and gate in {'s8-solution-gate.py', 's9-quality-report-gate.py',
                                  's9-product-walkthrough-gate.py', 's9-launch-rollback-gate.py'} and not option('--context'):
            die('正式批准门需要 --context contract-manifest.json，绑定当前产物与批准版本')
    runner = ('node' if gate.endswith('.mjs')
              else 'bash' if gate.endswith('.sh')
              else sys.executable)
    cmd = [runner, gate_path] + argv[1:]
    try:
        evidence = gate_evidence(gate_path, argv[1:])
    except (OSError, WorkflowError) as e:
        die('无法绑定被测输入：%s' % e)
    t0 = time.time()
    p = run_child(cmd)
    out = (p.stdout or '') + (p.stderr or '')
    truncated = len(out) > MAX_STDOUT
    if truncated:
        out = out[:MAX_STDOUT]
    v, why = verdict_of(gate, p.returncode)
    if p.returncode == 124:
        v, why = 'UNABLE', '执行超时，未完成验证'
    stable = evidence_current(evidence)
    if not stable:
        v, why = 'UNABLE', '测量期间输入或规则变化；本次结果不可用于批准'
    # ⭐ UNABLE + 前置没跑 = 十有八九是顺序问题，而不是环境问题。
    #    不改退出码（那会挡住合法的单独调试），只把话说清楚。
    unmet = [(g, s) for g, s in prereq_state(gate, root, manifest) if s != 'PASS']
    if v == 'UNABLE' and unmet:
        hint = ('这道门报 UNABLE，而它的前置尚未通过：'
                + '、'.join('%s（%s）' % (g, s) for g, s in unmet)
                + ' —— **十有八九是顺序问题，不是环境问题**。'
                  '先把前置跑通再回来，别把 UNABLE 当成「跑过了」。')
        why = (why + '；' if why else '') + hint
    # 被测产物：门禁参数里第一个真实存在的文件/目录
    target = next((a for a in argv[1:] if not a.startswith('-') and os.path.exists(a)), None)
    rec = {
        'gate': gate,
        'subGate': sub,
        'verdict': v,
        'exitCode': p.returncode,
        'ranAt': time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime(t0)),
        'durationMs': int((time.time() - t0) * 1000),
        'target': target,
        'cmd': ' '.join(cmd),
        'stdout': out,
        'stdoutTruncated': truncated,
        'claimEligible': not adhoc and stable,
        'evidence': evidence,
    }
    if manifest and manifest.get('schemaVersion') == '2.0':
        rec.update({'runId': manifest['runId'], 'planHash': manifest['planHash'],
                    'registryVersion': manifest['registryVersion'],
                    'registryHash': manifest['registryHash'],
                    'ruleIds': required_rule_ids(manifest, key)})
    if why:
        rec['warning'] = why
    if PREREQ.get(gate):
        rec['prereq'] = [{'gate': g, 'verdict': s}
                         for g, s in prereq_state(gate, root, manifest)]
    d = gate_result_dir(root, manifest)
    if adhoc and manifest:
        d = os.path.join(d, 'adhoc')
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, key + '.json'), 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    sys.stdout.write(p.stdout or '')
    sys.stderr.write(p.stderr or '')
    print('\n→ 已落盘 %s　结论 %s（退出码 %d）'
          % (os.path.join(d, key + '.json'), v, p.returncode), file=sys.stderr)
    if why:
        print('⚠️ %s' % why, file=sys.stderr)
    return p.returncode if stable else 2


def status(root, skill_root, blocking=False):
    """呈现门禁状态；v2 计划的 requiredGates 是阻断集合。"""
    try:
        manifest, manifest_path = load_active_run(root, required=False)
    except Exception as e:
        print('❌ 活动运行无效：%s' % e)
        return 1 if blocking else 2
    # 🚨 2026-09-10 codex #14：这里原本自己 glob 一套 ⇒ 漏掉 `browser-audit.mjs`
    #   （S6 出场必跑），于是「哪些门没跑过」这份清单**天生看不见它**。
    #   ⭐ 三个消费方三个集合，而每个都在拿自己那份当「全部门禁」用。⇒ 统一走正本。
    sys.path.insert(0, os.path.join(skill_root, 'scripts'))
    from _roster import gate_names         # noqa: E402  门禁名册唯一正本
    gates = gate_names(skill_root)
    rdir = gate_result_dir(root, manifest)
    got = {}
    if os.path.isdir(rdir):
        for f in sorted(os.listdir(rdir)):
            if not f.endswith('.json'):
                continue
            try:
                got[f[:-5]] = json.load(io.open(os.path.join(rdir, f), encoding='utf-8'))
            except Exception as e:
                got[f[:-5]] = {'verdict': 'UNREADABLE', 'exitCode': None,
                               'ranAt': None, 'warning': str(e)[:60]}
            # 子门记录（如 reconcile-gate.py.G2）也让主脚本算「有结果」——不然分键后主脚本永远显示没跑过
            _mm = re.match(r'^(.+?\.(?:py|mjs))\.G[\d.]+$', f[:-5])
            if _mm:
                got.setdefault(_mm.group(1), got[f[:-5]])
    # 阶段映射由同一注册表给出，不再从 Markdown 文案反向猜。
    stage = {}
    try:
        registry, _ = load_registry()
        for rule in registry.get('gateRules', []):
            label = '/'.join(x for x in rule.get('modules', []) if x != '*') or '全局'
            stage.setdefault(rule.get('gate'), label)
    except Exception:
        registry = {}
    notrun = [g for g in gates if g not in got]
    print('门禁名册 %d 道　·　当前结果 %d　·　名册中从来没跑过 %d'
          % (len(gates), len(got), len(notrun)))
    # ⭐ 2026-09-08（终局规格 1-4）：若项目建了 run-manifest，就按它**分栏呈现**——
    #   仍不替人判断「该跑什么」，只是把**使用者自己声明过的**适用/不适用摆出来。
    #   ⚠️ manifest 坏了不吞也不崩：提示后按无 manifest 呈现（呈现层不许把环境问题变结论）。
    declared, na_reason = None, {}
    if manifest and manifest.get('schemaVersion') == '2.0':
        declared = set(manifest.get('requiredGates') or [])
        print('活动运行 %s　·　计划必跑 %d　·　profile=%s\nmanifest: %s'
              % (manifest.get('runId'), len(declared), manifest.get('htmlProfile'), manifest_path))
    elif manifest:
        declared = {x.get('gate') for x in (manifest.get('applicableGates') or []) if x.get('gate')}
        na_reason = {x.get('item'): x.get('reason', '')
                     for x in (manifest.get('nonApplicable') or [])}
    required_notrun = sorted(g for g in (declared or set()) if g not in got)
    if required_notrun:
        print('\n⛔ 当前计划必跑但 NOT-RUN：')
        for g in required_notrun:
            print('   ·  %-32s [%s]' % (g, stage.get(g, '未挂阶段')))
    if manifest and manifest.get('schemaVersion') != '2.0' and notrun:
        d_na = [g for g in notrun if g in na_reason]
        d_und = [g for g in notrun if g not in (declared or set()) and g not in na_reason]
        if d_na:
            print('\nⓘ 旧 manifest 声明不适用：')
            for g in d_na:
                print('   ·  %-32s 理由：%s' % (g, na_reason.get(g) or '（空理由无效）'))
        if d_und:
            print('\n？旧 manifest 未表态：')
            for g in d_und:
                print('   ·  %-32s [%s]' % (g, stage.get(g, '未挂阶段')))
    elif not manifest and notrun:
        print('\nⓘ 无 v2 计划，以下只作诊断，不推断适用性：')
        for g in notrun:
            print('   ·  %-32s [%s]' % (g, stage.get(g, '未挂阶段')))
    if got:
        print('\n已有结果：')
        order = {'FAIL': 0, 'UNKNOWN': 1, 'UNABLE': 2, 'UNREADABLE': 2,
                 'PASS_WITH_GAPS': 3, 'PASS': 4}
        for g, r in sorted(got.items(), key=lambda kv: (order.get(kv[1].get('verdict'), 9), kv[0])):
            mark = {'PASS': '✅', 'FAIL': '❌', 'UNABLE': '⚠️', 'PASS_WITH_GAPS': '🟠',
                    'UNKNOWN': '❓', 'UNREADABLE': '❓'}.get(r.get('verdict'), '❓')
            stale = ''
            tgt = r.get('target')
            if tgt and os.path.exists(tgt) and r.get('ranAt'):
                try:
                    if os.path.getmtime(tgt) > time.mktime(time.strptime(
                            r['ranAt'][:19], '%Y-%m-%dT%H:%M:%S')):
                        stale = '　⚠️ 结论已过期（产物比它新）'
                except Exception:
                    pass
            print('   %s %-30s %-14s %s%s'
                  % (mark, g, r.get('verdict'), (r.get('ranAt') or '')[:19], stale))
    print('\n⚠️ 门禁结论来自门禁；适用集合来自已验证的 workflow registry 计划。')
    if not blocking:
        print('⭐ 加 `--gate`：计划必跑项 NOT-RUN 或非 PASS 都会阻断。')
        return 0
    # ── --gate：把「呈现」变成「阻断」 ────────────────────────────────
    # ⭐⭐ 自检问句（来自 peer 会话的 A16）：**这道门红的时候，会有什么动作被真的挡住？**
    #    答不出具体动作 = 它只是一条建议。
    #    ⛔ 「一道会红但不阻断的门，和一道不存在的门，差别只在于它给了你
    #      一个『我看到了』的错觉。」
    #    🚨 第一版把 UNABLE 排除在阻断之外 —— **反向测试当场证伪**：
    #      拿一个空文件跑 definition-gate 得到 UNABLE，而 `--gate` 放行了。
    #    ⭐⭐ 「跑了但查不了」与「没跑」是两回事，必须分开：
    #      `NOT-RUN` = 你**没跑**它（可能不适用）→ 不挡，要人判断
    #      `UNABLE`  = 你**跑了**，它说「我查不了」→ **必须挡**
    #                  你以为有信息的地方其实是空的
    #    ⛔ 这正是本会话反复栽的那一点：**UNABLE 是最容易被耸肩带过的一档**
    #      （G2 的 AC 集合恒空时报 UNABLE，而「UNABLE」与「通过」在我眼里没有区别）。
    #    ⚠️ 「本轮不适用」的正确表达是**不跑它**（NOT-RUN），不是跑了拿一个 UNABLE。
    # ── 元门禁不许被「只跑我改的那一道」绕过（结构，不是纪律）──────────
    # ⭐ 形状由并行会话 fm-agent 提出：**改完一道门只跑那一道，等于把元门禁关掉，
    #   且不留任何痕迹** —— 没有跳过记录，没有 UNABLE，什么都没有。
    #   它那边的做法是「`--filter` 时强制把元门禁加回来」；我这边没有编排器，
    #   等价位置是这里：**任何门禁文件比最近一次元门禁记录新 ⇒ 挡住**。
    # ⛔ 写成铁律没用 —— 纪律正是刚刚失效的那个东西。要让它**必须被主动绕过**才失效。
    meta_stale = []
    meta_rec = got.get('consistency-gate.py')
    newest = None
    for g in gates:
        gp = os.path.join(skill_root, 'scripts', g)
        if os.path.exists(gp):
            mt = os.path.getmtime(gp)
            if newest is None or mt > newest[0]: newest = (mt, g)
    if newest:
        if not meta_rec:
            meta_stale.append('元门禁 consistency-gate 在本项目里**一次都没跑过**')
        else:
            try:
                ran = time.mktime(time.strptime(meta_rec['ranAt'][:19], '%Y-%m-%dT%H:%M:%S'))
                if newest[0] > ran:
                    meta_stale.append(
                        '门禁 %s 比最近一次元门禁记录还新（%s）—— '
                        '改过门禁却没重跑元门禁' % (newest[1], meta_rec['ranAt'][:19]))
            except Exception:
                meta_stale.append('元门禁记录里的 ranAt 读不出来')

    v2 = bool(manifest and manifest.get('schemaVersion') == '2.0')
    if blocking and not v2:
        print('\n❌ --gate：缺少有效 v2 活动运行，无法知道哪些门必跑；先 plan --write。')
        return 1
    binding_bad = []
    if v2:
        for g in sorted(declared):
            if g not in got:
                continue
            r = got[g]
            expected_rules = required_rule_ids(manifest, g)
            if (r.get('runId') != manifest.get('runId')
                    or r.get('planHash') != manifest.get('planHash')
                    or sorted(r.get('ruleIds') or []) != expected_rules
                    or not r.get('claimEligible')
                    or not evidence_current(r.get('evidence'))):
                binding_bad.append(g)
        blockers = [(g, got[g]) for g in sorted(declared) if g in got
                    and got[g].get('verdict') != 'PASS']
    else:
        blockers = [(g, r) for g, r in sorted(got.items())
                    if r.get('verdict') in ('FAIL', 'UNABLE', 'UNKNOWN', 'UNREADABLE')]
    if required_notrun:
        print('\n❌ --gate：%d 道计划必跑门仍是 NOT-RUN，不许往下走。' % len(required_notrun))
        return 1
    if binding_bad:
        print('\n❌ --gate：运行/计划/规则不匹配或被测输入已过期：%s' % '、'.join(binding_bad))
        return 1
    if meta_stale:
        print('\n❌ --gate：元门禁没跟上门禁的改动，不许往下走：')
        for m in meta_stale: print('   · ' + m)
        print('   ⇒ 跑 `gate-run.py scripts/consistency-gate.py` 之后再来。')
        return 1
    if not blockers:
        print('\n✅ --gate：当前计划所有必跑门均在案、绑定当前运行且为 PASS')
        return 0
    print('\n❌ --gate：有 %d 道门的结论在案且为红，不许往下走：' % len(blockers))
    for g, r in blockers:
        print('   · %-30s %s（退出码 %s）%s'
              % (g, r.get('verdict'), r.get('exitCode'),
                 '　' + r['warning'][:40] if r.get('warning') else ''))
    return 1


# ------------------------------------------------------------------ M8 自证
def _self_test():
    """正例绿 / 每类反例红 / 无效输入报错不返绿。

    ⭐ 本脚本最要紧的判据是**退出码不许被误标**：
      `prd_completeness_check` 的 2 是「有缺口」不是「跑不了」，
      把 FAIL 标成 UNABLE 是最坏的一种误标（UNABLE 最容易被耸肩带过）。
    """
    import tempfile, shutil
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        print(('  ✅ ' if cond else '  ❌ ') + name + ('' if cond else '　' + extra))
        ok = ok and cond

    # ⚠️ 自证里回显的 status() 报表带 ❌ 行（模拟的红门），与真实用例行长得一样 ——
    #   selftest-all.py 曾把它们数成「gate-run 自证失败 2 条」。
    #   嵌套输出一律加「│ 」归属前缀：谁在报红，和有没有红一样重要。
    def _nested(fn, *a, **kw):
        import io as _io, contextlib as _ctx
        buf = _io.StringIO()
        with _ctx.redirect_stdout(buf):
            rc = fn(*a, **kw)
        for ln in buf.getvalue().splitlines():
            print('  │ ' + ln)
        return rc

    # ① 语义表：两道非标门禁必须被正确解读
    chk('prd_completeness 的 2 判为 FAIL（不是 UNABLE）',
        verdict_of('prd_completeness_check.py', 2)[0] == 'FAIL',
        '实得 %s' % verdict_of('prd_completeness_check.py', 2)[0])
    chk('标准门禁的 2 判为 UNABLE',
        verdict_of('definition-gate.py', 2)[0] == 'UNABLE')
    chk('coverage_check 的 3 判为 PASS_WITH_GAPS',
        verdict_of('coverage_check.py', 3)[0] == 'PASS_WITH_GAPS')
    # 🚨 没登记的门禁 / 没登记的退出码，一律 UNKNOWN —— **不许猜成 PASS**
    chk('没登记语义的门禁 → UNKNOWN（不许猜）',
        verdict_of('brand-new-gate.py', 0)[0] == 'UNKNOWN')
    chk('登记了但退出码不在表里 → UNKNOWN（不许猜）',
        verdict_of('definition-gate.py', 7)[0] == 'UNKNOWN')

    # ② 前置顺序：SOP 写了「demo-anchor 必须排在 G2 之前」，此前无人守
    _pd = tempfile.mkdtemp(prefix='gr-pre-')
    chk('前置一次都没跑过 → NOT-RUN（不许当成通过）',
        prereq_state('reconcile-gate.py', _pd) == [('demo-anchor-gate.py', 'NOT-RUN')],
        '实得 %s' % prereq_state('reconcile-gate.py', _pd))
    os.makedirs(os.path.join(_pd, RESULT_DIR), exist_ok=True)
    for _v in ('UNABLE', 'PASS'):
        json.dump({'verdict': _v, 'evidence': gate_evidence(__file__, [])},
                  io.open(os.path.join(_pd, RESULT_DIR, 'demo-anchor-gate.py.json'),
                          'w', encoding='utf-8'))
        chk('前置结论 %s 时读得出来' % _v,
            prereq_state('reconcile-gate.py', _pd) == [('demo-anchor-gate.py', _v)])
    # 🚨 反例：前置**只有 PASS 才算满足** —— UNABLE 不许被当成满足
    json.dump({'verdict': 'UNABLE'},
              io.open(os.path.join(_pd, RESULT_DIR, 'demo-anchor-gate.py.json'),
                      'w', encoding='utf-8'))
    chk('前置是 UNABLE 时算「未满足」（这正是它要挡的那种耸肩）',
        [s for _, s in prereq_state('reconcile-gate.py', _pd) if s != 'PASS'] == ['UNABLE'])
    chk('没有前置要求的门禁 → 空列表（不许无中生有）',
        prereq_state('definition-gate.py', _pd) == [])

    d = tempfile.mkdtemp(prefix='gr-')
    try:
        g_ok = os.path.join(d, 'fake-gate.py')
        io.open(g_ok, 'w', encoding='utf-8').write(
            'import sys\nprint("我跑过了")\nsys.exit(int(sys.argv[1]))\n')
        EXIT_SEMANTICS['fake-gate.py'] = STD
        cwd = os.getcwd()
        os.chdir(d)
        try:
            # ② 透传退出码：封装不许改变门禁的结论
            rc0 = run([g_ok, '0'], d, adhoc=True)
            rc1 = run([g_ok, '1'], d, adhoc=True)
            chk('退出码原样透传（0）', rc0 == 0, '实得 %s' % rc0)
            chk('退出码原样透传（1）', rc1 == 1, '实得 %s' % rc1)
            # ③ 落盘内容
            f = os.path.join(d, RESULT_DIR, 'fake-gate.py.json')
            chk('结果文件写出来了', os.path.isfile(f))
            rec = json.load(io.open(f, encoding='utf-8'))
            chk('结论按语义表标成 FAIL', rec['verdict'] == 'FAIL', '实得 %s' % rec.get('verdict'))
            chk('stdout 被记下来（不是只记退出码）', '我跑过了' in rec['stdout'])
            chk('记了时间戳', bool(rec.get('ranAt')))
            # ⑤ 子门号分键：G2/G3 各留各的记录（曾共用一条互相覆盖——一条 PASS 顶两门）
            g_sub = os.path.join(d, 'fake-sub-gate.py')
            io.open(g_sub, 'w', encoding='utf-8').write('import sys\nsys.exit(0)\n')
            EXIT_SEMANTICS['fake-sub-gate.py'] = STD
            run([g_sub, 'G2'], d, adhoc=True)
            run([g_sub, 'G3'], d, adhoc=True)
            chk('子门号进落盘键：G2/G3 各一条记录',
                os.path.isfile(os.path.join(d, RESULT_DIR, 'fake-sub-gate.py.G2.json'))
                and os.path.isfile(os.path.join(d, RESULT_DIR, 'fake-sub-gate.py.G3.json')))
            chk('反例：带子门号时不再写主键文件（写了=还是那条会被覆盖的旧记录）',
                not os.path.isfile(os.path.join(d, RESULT_DIR, 'fake-sub-gate.py.json')))
            # ⑥ .sh 门禁（coding-standards 挂接）：走 bash、退出码透传、3 判 UNABLE
            g_sh = os.path.join(d, 'fake-shell-gate.sh')
            io.open(g_sh, 'w', encoding='utf-8').write('#!/bin/sh\necho shell-ran\nexit 3\n')
            EXIT_SEMANTICS['fake-shell-gate.sh'] = {0: 'PASS', 1: 'FAIL', 3: 'UNABLE'}
            rc3 = run([g_sh], d, adhoc=True)
            chk('.sh 门禁走 bash 且退出码原样透传（3）', rc3 == 3, '实得 %s' % rc3)
            _r3 = json.load(io.open(os.path.join(d, RESULT_DIR, 'fake-shell-gate.sh.json'),
                                    encoding='utf-8'))
            chk('.sh 的 3 按登记语义判 UNABLE（没能测≠不合格≠通过）', _r3['verdict'] == 'UNABLE',
                '实得 %s' % _r3.get('verdict'))
            # ④ status：没跑过的必须被点名
            print('  —— status 输出 ——')
            SK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _nested(status, d, SK)
            # ⭐ 新判据：元门禁记录陈旧 ⇒ 阻断（结构，不是纪律）。
            #    自证用**记录的时间戳**造两种情形，不碰任何真实文件。
            def _meta(ts):
                os.makedirs(os.path.join(d, RESULT_DIR), exist_ok=True)
                json.dump({'gate': 'consistency-gate.py', 'verdict': 'PASS',
                           'exitCode': 0, 'ranAt': ts},
                          io.open(os.path.join(d, RESULT_DIR,
                                               'consistency-gate.py.json'),
                                  'w', encoding='utf-8'), ensure_ascii=False)
            # ⛔ 必须先清空其它结论 —— 否则上一步 fake-gate 的 FAIL 会让它照样红，
            #    **用例就没有隔离新判据**（反向测当场证伪：拆掉判据自证仍绿）。
            import shutil as _sh0
            _sh0.rmtree(os.path.join(d, RESULT_DIR), ignore_errors=True)
            _meta('2000-01-01T00:00:00')          # 比任何门禁文件都旧
            rc_ms = _nested(status, d, SK, blocking=True)
            chk('⭐ 元门禁记录比门禁文件旧 → 阻断（改了门禁没重跑元门禁）',
                rc_ms == 1, '实得 %s' % rc_ms)
            _meta(time.strftime('%Y-%m-%dT%H:%M:%S'))   # 刚跑过
            run([g_ok, '1'], d, adhoc=True)             # 把 FAIL 记录造回来
            # ⑤ ⭐ --gate 必须**真的挡住**：刚才那次 fake-gate 是 FAIL
            #    自检问句（peer 会话 A16）：这道门红的时候，会有什么动作被真的挡住？
            rc_gate = _nested(status, d, SK, blocking=True)
            chk('--gate 在案有 FAIL 时退出 1（真阻断，不只是呈现）',
                rc_gate == 1, '实得 %s' % rc_gate)
            # 🚨 UNABLE 也必须挡 —— 第一版放行了它，反向测试当场证伪。
            #    「跑了但查不了」≠「没跑」：前者是你以为有信息的地方其实是空的。
            run([g_ok, '2'], d, adhoc=True)           # 退出码 2 → UNABLE
            rc_u = _nested(status, d, SK, blocking=True)
            chk('--gate 在案有 UNABLE 时也退出 1（跑了但查不了 ≠ 没跑）',
                rc_u == 1, '实得 %s' % rc_u)
            # 反向：清干净后必须放行（恒红的门和不存在的门一样没用）
            import shutil as _sh
            _sh.rmtree(os.path.join(d, RESULT_DIR), ignore_errors=True)
            _meta(time.strftime('%Y-%m-%dT%H:%M:%S'))
            rc_clean = _nested(status, d, SK, blocking=True)
            chk('无 v2 活动运行即使在案没有红也阻断（无计划不能宣称完成）',
                rc_clean == 1, '实得 %s' % rc_clean)
        finally:
            os.chdir(cwd)
            EXIT_SEMANTICS.pop('fake-gate.py', None)
            # ⑥ manifest 分栏（终局规格 1-4）：呈现层读使用者自己的声明，仍不替人判断
        _md2 = tempfile.mkdtemp(prefix='gr-mf-')
        os.makedirs(os.path.join(_md2, '.product-flow'), exist_ok=True)
        import io as _io2, contextlib as _ctx2
        def _cap(root):
            b = _io2.StringIO()
            with _ctx2.redirect_stdout(b): status(root, SK)
            return b.getvalue()
        json.dump({'applicableGates': [{'gate': 'definition-gate.py'}],
                   'nonApplicable': [{'item': 'figma-editability-gate.py', 'reason': '本项目无 Figma'}]},
                  io.open(os.path.join(_md2, '.product-flow', 'run-manifest.json'), 'w', encoding='utf-8'))
        _out = _cap(_md2)
        chk('旧 manifest：声明适用的未跑门单独列出',
            '当前计划必跑但 NOT-RUN' in _out and 'definition-gate.py' in _out)
        chk('manifest 分栏：声明不适用带理由不算欠账', '本项目无 Figma' in _out)
        chk('旧 manifest：未表态的单独一栏', '旧 manifest 未表态' in _out)
        io.open(os.path.join(_md2, '.product-flow', 'run-manifest.json'), 'w', encoding='utf-8').write('{bad json')
        _out2 = _cap(_md2)
        chk('manifest 坏 JSON：明确报活动运行无效（不吞不猜）',
            '活动运行无效' in _out2)

        # ⑦ v2 计划：必跑 NOT-RUN 真阻断；每条记录必须绑定 run/plan/rule。
        _v2 = tempfile.mkdtemp(prefix='gr-v2-')
        _plan = resolve_plan('only', ['definition'])
        _plan['runId'] = 'PF-gate-selftest'
        _plan['inputs'] = []
        _plan['inputsHash'] = hashlib.sha256(b'[]').hexdigest()
        _mp = os.path.join(_v2, '.product-flow', 'runs', _plan['runId'], 'run-manifest.json')
        os.makedirs(os.path.dirname(_mp), exist_ok=True)
        json.dump(_plan, io.open(_mp, 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump({'schemaVersion': '1.0', 'activeRunId': _plan['runId'],
                   'manifestRef': os.path.relpath(_mp, os.path.join(_v2, '.product-flow')),
                   'manifestHash': sha256_file(_mp)},
                  io.open(os.path.join(_v2, '.product-flow', 'run-manifest.json'),
                          'w', encoding='utf-8'), ensure_ascii=False)
        chk('v2：计划必跑项一个未跑即阻断',
            _nested(status, _v2, SK, blocking=True) == 1)
        _gdir = gate_result_dir(_v2, _plan)
        os.makedirs(_gdir, exist_ok=True)
        _future = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() + 60))
        for _gate in _plan['requiredGates']:
            _rules = sorted(x['ruleId'] for x in _plan['gatePlan']
                            if x['gate'] == _gate and x['required'])
            json.dump({'gate': _gate.split('.G')[0], 'verdict': 'PASS', 'exitCode': 0,
                       'ranAt': _future, 'runId': _plan['runId'],
                       'planHash': _plan['planHash'], 'ruleIds': _rules,
                       'claimEligible': True,
                       'evidence': gate_evidence(os.path.join(SK, 'scripts', _gate.split('.G')[0]), [])},
                      io.open(os.path.join(_gdir, _gate + '.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False)
        chk('v2：全部必跑门绑定当前 run/plan/rule 且 PASS 才放行',
            _nested(status, _v2, SK, blocking=True) == 0)
        _victim = _plan['requiredGates'][-1]
        _vr = os.path.join(_gdir, _victim + '.json')
        _badrec = json.load(io.open(_vr, encoding='utf-8'))
        _badrec['ruleIds'] = ['R-FOREIGN']
        json.dump(_badrec, io.open(_vr, 'w', encoding='utf-8'), ensure_ascii=False)
        chk('v2：复制来的 PASS 若 ruleId 不属于当前计划仍阻断',
            _nested(status, _v2, SK, blocking=True) == 1)

        # 手改 manifest 后即使重算 pointer hash，也必须被 registry 重算抓住。
        _tampered = dict(_plan)
        _tampered['requiredGates'] = _tampered['requiredGates'][:-1]
        json.dump(_tampered, io.open(_mp, 'w', encoding='utf-8'), ensure_ascii=False)
        _pointer = {'schemaVersion': '1.0', 'activeRunId': _plan['runId'],
                    'manifestRef': os.path.relpath(_mp, os.path.join(_v2, '.product-flow')),
                    'manifestHash': sha256_file(_mp)}
        json.dump(_pointer, io.open(os.path.join(_v2, '.product-flow', 'run-manifest.json'),
                                    'w', encoding='utf-8'), ensure_ascii=False)
        chk('v2：手删必跑门并重算 pointer hash 仍被计划重算拒绝',
            _nested(status, _v2, SK, blocking=True) == 1)

    # ⑤ 门禁不存在 → 报 2
        rc = subprocess.call([sys.executable, os.path.abspath(__file__),
                              os.path.join(d, 'nope.py')],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        chk('门禁脚本不存在 → 报 2（不许折叠成 0）', rc == 2, '实得 %s' % rc)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print('\n%s' % ('✅ 自证通过：这道门会出声' if ok else '❌ 自证失败：先修它'))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '(用法见文件头)'); sys.exit(0)   # 登记册#1：帮助就是帮助，退 0
    a = sys.argv[1:]
    if '--self-test' in a:
        sys.exit(_self_test())
    SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ri = a.index('--root') if '--root' in a else -1
    root = a[ri + 1] if ri >= 0 else os.getcwd()
    if ri >= 0:
        a = a[:ri] + a[ri + 2:]
    if '--status' in a:
        sys.exit(status(root, SKILL, blocking='--gate' in a))
    adhoc = '--adhoc' in a
    if adhoc:
        a.remove('--adhoc')
    if not a:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(a, root, adhoc=adhoc))
