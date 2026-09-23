#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 agent 协同门 —— 路径所有权 + **在合并结果上**跑全套门禁。

═══ 它补的洞（2026-09-12 实测，不是理论）═══

Claude 与 Codex 并行改同一个仓，当天实际出了五个问题：

  ① **控制面在单个分支上，对方持有时就写不进去**
     —— 要写 `.proposals/team/decision-log.md` 被 `already checked out` 挡住。
     ⭐ 这是 git worktree 的**硬约束**，不是配合问题：分支独占会让「沟通渠道」
       在最需要的时候不可用。⇒ 控制面必须在 `main`。
  ② **口头声称的「零交叠」不可靠**
     —— 我在同步文档里写「与 WO-001 零交叠」，实测 `comm -12` 出来 **4 个文件重叠**。
  ③ **自动合并成功 ≠ 结果正确**（本门存在的首要理由）
     —— 试合：1 个真冲突 + **3 个文件被 git 自动合并**，其中两个是脚本。
       在合并结果上跑门禁：元门禁 **41 → 39**（2 条变 N/A、1 条红），
       零丢失门禁**变红**（对方改 `flow-tailoring.md` 时删掉了一条判据句）。
     ⭐ **两边分别都绿，合完就红。**「我这边是绿的」不构成合并依据。
  ④ **租约会过期且没人能权威更新** —— `owner.json` 写 writer=Codex，
     用户却直接指派 Claude 做，两边都不敢改那个文件，协议悬空。
  ⑤ **孤儿改动无人认领** —— 75 行 `_browser.mjs` 改动不属于任何提交、不属于任何一方。

═══ 三条判据 ═══

  A **所有权**：改了不属于自己、也不在 `shared` 里的路径 ⇒ 红
  B **孤儿**：改动落在任何一方的所有权之外 ⇒ 红（连清单都没有的东西，没人会认领）
  C **shared 附加条件**：改了 `shared` 路径，`.proposals/` 下必须有对应说明条目

  另有 `--merge-check <ref>`：**造出合并结果**（不提交），在**结果**上跑
  `selftest-all --fresh` · `consistency-gate` · `no-loss-gate` · `adr-check`。

═══ ⚠️ 它防不了什么（说清楚，别拿它当万能）═══

1. **防不了「两边都对但合起来语义矛盾」** —— 比如一边定「阈值不写图上」、
   另一边定「阈值写进 manifest」，各自都合理，合起来就是两套说法。
   那一层只能靠 `.proposals/` 的闭环对话，⛔ 机器查不了。
2. **孤儿检测依赖清单完整** —— 新增的文件若两边都没登记，它会被报成孤儿；
   这是**故意的**（宁可多问一次），但不要因此把清单写成通配全仓。
3. `--merge-check` 只回答「合完还绿不绿」，**不回答「合完对不对」**。
4. 🚨 **合并态下 A/B 两条判据对「对方带进来的改动」是关掉的**（2026-09-13 实测踩到）：
   处在 merge 状态时本门只看「与两个父提交都不同」的路径 —— 这是刻意的
   （⛔ 不把对方的文件算到合并者头上），但后果是**对方分支上的所有权违规，
   一合进来就永久不可见**。那次实测：合并结果上 `--who codex` 报
   「（相对 main 无改动）」+ 退出码 0，而同一批改动在 codex 分支上跑是
   **1 条越权 + 5 个孤儿**。
   ⇒ **合并前必须先在来源分支上单独跑一次**，否则这两条判据对合并流程等于不存在：

       git worktree add --detach /tmp/verify <对方分支>
       cd /tmp/verify/skills/product-flow
       python3 scripts/coordination-gate.py --who <对方> --base $(git merge-base main <对方分支>)

用法:
    coordination-gate.py --who claude|codex            查所有权 + 孤儿 + shared 说明
    coordination-gate.py --who claude --base <ref>     指定对照基线（默认 HEAD）
    ⚠️ 合并前查对方：在**来源分支的 worktree 里**跑 --who <对方> --base <merge-base>
    coordination-gate.py --merge-check <ref>           在合并结果上跑全套门禁
    coordination-gate.py --self-test
退出码: 0=通过 1=有违规/合并结果不绿 2=跑不了
"""
import fnmatch
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
MANIFEST = os.path.join(SKILL, 'references', 'path-ownership.json')


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def _git(args, cwd=None):
    r = subprocess.run(['git'] + args, cwd=cwd or REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


def load_manifest(path=None):
    p = path or MANIFEST
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding='utf-8'))


def _match(path, pats):
    for pat in pats:
        if fnmatch.fnmatch(path, pat):
            return True
        # `dir/**` 也应匹配 `dir/a/b`；fnmatch 的 * 会跨 /，但补一条前缀匹配更稳
        if pat.endswith('/**') and path.startswith(pat[:-2]):
            return True
    return False


def classify(paths, man):
    """把改动路径分成 己方 / 他方 / shared / 孤儿。"""
    owners = man['owners']
    out = {'own': [], 'others': [], 'shared': [], 'orphan': []}
    return owners, out


def check_ownership(who, changed, man, root=None):
    owners = man['owners']
    if who not in owners:
        return None, ['未知 agent：%s（清单里有 %s）' % (who, '、'.join(k for k in owners if k != 'shared'))]
    mine = owners[who]
    shared = owners.get('shared', [])
    theirs = {k: v for k, v in owners.items() if k not in (who, 'shared')}
    bad, touched_shared = [], []
    for p in changed:
        if _match(p, mine):
            continue
        if _match(p, shared):
            touched_shared.append(p)
            continue
        owner = next((k for k, v in theirs.items() if _match(p, v)), None)
        if owner:
            bad.append('A 所有权：%s 属于 **%s**，你（%s）不该改它 —— '
                       '要改就先在 .proposals/ 提出来并等回应' % (p, owner, who))
        else:
            bad.append('B 孤儿：%s **不属于任何一方** —— 连清单都没有的东西没人会认领；'
                       '把它登记进 path-ownership.json，或说明它为什么该存在' % p)
    if touched_shared and man.get('sharedRequiresNote'):
        note_dirs = man.get('noteDirs') or []
        notes = [p for p in changed if any(p.startswith(d) for d in note_dirs)]
        if not notes:
            bad.append('C shared 附加条件：改了 %s（shared），但 %s 下没有任何说明条目 —— '
                       '⛔ 这些文件双方都会改，没有说明就无从判断合并时该保留谁的'
                       % ('、'.join(touched_shared[:3]), '/'.join(note_dirs)))
        else:
            # ⭐ 2026-09-15 收紧：说明条目必须**点名**改了哪个 shared 路径。
            #
            # 🚨 它补的洞：原条件只要求「change set 里有任意一个 .proposals 文件」。
            #   于是随手带一份无关说明，就能改任何 shared 路径 —— 包括
            #   `no-loss-baseline.json`（零丢失保证的锚点本身）与 `coordination-gate.py`（本门自己）。
            #   而清单上还写着「主责保留」，读清单的人会得出与门禁相反的结论。
            #
            # ⚠️ **为什么不用「非 owner 不许有删除行」那个方案**（2026-09-15 实测否决）：
            #   拿最近 30 个提交回放，那条判据会误杀 **11 个合法提交** ——
            #   零丢失基线本来就是**重新生成**的（+13827/−8502）、一行改名是 +2/−2、
            #   用户要求的结构调整是 +401/−143。⛔ 判据一旦比现实还严，
            #   真实结果是大家绕开它，而不是遵守它（见 feedback_tightening_blocks_correct_usage）。
            #   ⇒ 改为「点名」：成本极低、几乎不可能误伤，却真的逼人说清楚动了哪个承重件。
            _note_txt = ''
            for _n in notes:
                _fp = os.path.join(root or REPO, _n)
                if os.path.exists(_fp):
                    try:
                        _note_txt += io.open(_fp, encoding='utf-8', errors='replace').read()
                    except Exception:
                        pass
            # ⚠️ 说明文件**自己**也在 shared 清单里（.proposals/**），
            #   ⛔ 不能要求它点名自己 —— 那是自指的假阳性。
            #   ⭐ 这是仓里既有的正例「收紧不许误伤正确用法」当场抓到的，
            #     不是我事后想到的：新判据必须在**正例**上先自证不误伤。
            _unnamed = [p for p in touched_shared
                        if p not in notes
                        and p not in _note_txt and os.path.basename(p) not in _note_txt]
            if _unnamed:
                bad.append('C2 shared 说明未点名：改了 %s（shared），但 %s 里**没有提到它** —— '
                           '⛔ 带一份无关说明不等于说明；承重件（零丢失基线、协同门自己）'
                           '被改了却没人说得出为什么，合并时无从判断该保留谁的'
                           % ('、'.join(_unnamed[:3]), '、'.join(notes[:2])))
    return (not bad), bad


def check_tombstones(man, root=None):
    """清单里的非通配条目：要么文件真实存在，要么在 tombstones 里显式登记。

    🚨 2026-09-15 加：此前清单里有 5 条指向**已不存在的文件**（阶段重编号后的旧路径）。
      意图是「旧路径墓碑」，合理 —— 但**没有任何东西区分「有意的墓碑」和「改完忘删的垃圾」**，
      一年后没人敢动它们。⭐ 同本仓母题：**约定写对了，没人守**。
    ⛔ 本规则只判「登记没登记」，不判墓碑该不该存在（那是人的判断）。
    """
    root = root or REPO
    owners = (man or {}).get('owners') or {}
    tombs = {t.get('path') for t in ((man or {}).get('tombstones') or [])}
    bad = []
    for who, pats in owners.items():
        for pat in pats:
            if '*' in pat:
                continue
            if os.path.exists(os.path.join(root, pat)):
                continue
            if pat in tombs:
                continue
            bad.append('D 幽灵条目：%s（属 %s）指向**不存在的文件**，且不在 tombstones 里 —— '
                       '要么它已退场（登记进 tombstones，写 since/replacedBy/why），'
                       '要么是路径写错了' % (pat, who))
    # 反方向同样要守：登记成墓碑的文件又回来了，说明登记过期
    for t in ((man or {}).get('tombstones') or []):
        _p = t.get('path')
        if _p and os.path.exists(os.path.join(root, _p)):
            bad.append('D 墓碑复活：%s 已登记为墓碑，但文件现在**真实存在** —— '
                       '⛔ 过期的墓碑登记会让人以为它已退场' % _p)
    return (not bad), bad


INVENTORY_BASELINE = 'skills/product-flow/references/ownership-inventory-baseline.json'
INVENTORY_GLOBS = ('skills/product-flow/scripts/*.py', 'skills/product-flow/scripts/*.mjs',
                   'skills/product-flow/references/*.md', 'skills/product-flow/templates/*.md')


def check_inventory(man, root=None, baseline_path=None, globs=None):
    """全量归属对账（棘轮式）：承重文件要么有主，要么在基线里显式挂账。

    🚨 2026-09-15 实测暴露的结构盲区：孤儿规则（B）只对**本次改动过的文件**查归属，
      于是 `coverage_check.py` 这种**从没被改过**的承重件在清单外躺了很久没人发现 ——
      它不是漏登记被放过，而是**结构上没人会去看它**。
      ⭐ 同本仓母题：量程没盖到，和「查过了没问题」在产物上完全一样。

    ⛔ 为什么走棘轮而不是直接硬门：立规则那天存量 63 个未登记。
      一道**必然红**的门会被 `|| true` 绕过或直接删掉（CI 棘轮那轮的实测教训）。
      ⇒ 基线只许减不许增，三个方向都判：

        E1 新增未登记   —— 不在 owners/tombstones 也不在基线 ⇒ 红（棘轮不许变松）
        E2 基线条目已登记 —— 已经有主了却还挂在基线 ⇒ 红（逼你划掉，防清单腐烂）
        E3 基线条目已消失 —— 文件都没了还挂着 ⇒ 红（同上）

    ⭐ E2/E3 是这条棘轮的牙：只有 E1 的话，基线会变成一张永远没人清理的垃圾场。
    """
    import fnmatch as _fn
    import glob as _glob
    root = root or REPO
    baseline_path = baseline_path or INVENTORY_BASELINE
    globs = globs or INVENTORY_GLOBS
    owners = (man or {}).get('owners') or {}
    pats = [p for v in owners.values() for p in v]
    pats += [t.get('path') for t in ((man or {}).get('tombstones') or []) if t.get('path')]

    bp = os.path.join(root, baseline_path)
    if not os.path.exists(bp):
        return None, ['E 基线 %s 不存在 —— 本条**没验**：先生成基线。⛔ 不是「通过」' % baseline_path]
    try:
        base = set(json.load(io.open(bp, encoding='utf-8')).get('unregistered') or [])
    except Exception as _e:
        return None, ['E 基线读不了（%s）—— 本条没验，⛔ 不是通过' % _e]

    def _owned(p):
        return any(p == q or _fn.fnmatch(p, q) for q in pats)

    present, bad = set(), []
    for g in globs:
        for f in sorted(_glob.glob(os.path.join(root, g))):
            rel = os.path.relpath(f, root)
            present.add(rel)
            if _owned(rel) or rel in base:
                continue
            bad.append('E1 新增未登记：%s **不属于任何一方**，也不在归属基线里 —— '
                       '棘轮只许减不许增：把它登记进 path-ownership.json' % rel)
    for rel in sorted(base):
        if _owned(rel):
            bad.append('E2 基线该瘦身：%s 已经登记到 owners 了，却还挂在归属基线里 —— '
                       '⛔ 划掉它（基线不清理就会变成没人看的垃圾场）' % rel)
        elif rel not in present:
            bad.append('E3 基线有幽灵：%s 已经不存在了，却还挂在归属基线里 —— ⛔ 划掉它' % rel)
    return (not bad), bad


def in_merge():
    """正在合并中？（存在 MERGE_HEAD）"""
    return os.path.exists(os.path.join(REPO, '.git', 'MERGE_HEAD'))


def merge_authored_paths():
    """🚨 2026-09-12 在**真实合并**上发现的设计缺陷：

    `--who` 检查的是「我改了什么」，而**合并必然带进对方的文件** —— 那不是我改的。
    第一次拿真合并跑，它把对方的 `workflow-registry.json` 报成「你不该改它」，
    把对方改过、清单里没有的 `delivery-pipeline.md` 报成孤儿。
    ⭐ **判据量错了对象**：合并态下我只对**自己解决的冲突**负责。

    ⇒ 合并时只取「与**两个父提交都不同**」的路径 —— 那才是我真正写下的东西。
    """
    rc, out, _ = _git(['diff', '--name-only', 'HEAD'])          # 相对我方父提交
    if rc != 0:
        return None
    mine = {l.strip() for l in out.splitlines() if l.strip()}
    rc2, out2, _ = _git(['diff', '--name-only', 'MERGE_HEAD'])  # 相对对方父提交
    if rc2 != 0:
        return None
    theirs = {l.strip() for l in out2.splitlines() if l.strip()}
    # ⚠️ 2026-09-12 当场再修一处：`git diff` **看不见未跟踪文件**，
    #   而合并时**新建的文件也是我写的**（例：本次的合并说明 .proposals/merge-*.md）。
    #   ⭐ 少算了它，规则 C 就会说「没有说明条目」，而说明其实已经写好躺在那儿。
    rc3, out3, _ = _git(['ls-files', '--others', '--exclude-standard'])
    untracked = {l.strip() for l in out3.splitlines() if l.strip()} if rc3 == 0 else set()
    # ⛔ `.codex/` 是第三方工具的本地配置目录，不属于本仓治理范围（与 changed_paths 同一口径）
    return sorted(p for p in ((mine & theirs) | untracked) if not p.startswith('.codex'))


def changed_paths(base='HEAD'):
    rc, out, err = _git(['status', '--porcelain'])
    if rc != 0:
        return None
    paths = [l[3:].strip() for l in out.splitlines() if l[3:].strip()]
    rc2, out2, _ = _git(['diff', '--name-only', base])
    if rc2 == 0:
        paths += [l.strip() for l in out2.splitlines() if l.strip()]
    return sorted(set(p for p in paths if not p.startswith('.codex')))


GATES = [
    ('selftest-all', ['python3', 'scripts/selftest-all.py', '--fresh'], 'skill'),
    ('consistency-gate', ['python3', 'scripts/consistency-gate.py'], 'skill'),
    ('no-loss-gate', ['python3', 'scripts/no-loss-gate.py'], 'skill'),
    ('adr-check', ['python3', 'docs/adr/adr-check.py'], 'repo'),
]


def merge_check(ref):
    """⭐ 造出合并结果，在**结果**上跑全套门禁。⛔ 不在任何一侧跑。"""
    import tempfile
    import shutil
    d = tempfile.mkdtemp(prefix='coord-merge-')
    r = os.path.join(d, 'r')
    try:
        rc, _o, e = _git(['clone', '-q', REPO, r], cwd=d)
        if rc != 0:
            return None, ['克隆不了本仓：%s' % e.strip()[:120]]
        _git(['checkout', '-q', 'main'], cwd=r)
        rc, o, e = _git(['merge', '--no-commit', '--no-ff', ref], cwd=r)
        rc2, conf, _ = _git(['diff', '--name-only', '--diff-filter=U'], cwd=r)
        conflicts = [x for x in conf.splitlines() if x.strip()]
        bad = []
        if conflicts:
            bad.append('合并有 %d 个**真冲突**，先人工解决：%s'
                       % (len(conflicts), '、'.join(conflicts[:4])))
            return False, bad
        auto = [l.split()[-1] for l in o.splitlines() if l.startswith('Auto-merging')]
        results = []
        for name, cmd, where in GATES:
            cwd = os.path.join(r, 'skills', 'product-flow') if where == 'skill' else r
            if not os.path.exists(os.path.join(cwd, cmd[1])):
                results.append((name, None, '脚本不存在'))
                continue
            p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=3000)
            tail = p.stdout.decode('utf-8', 'replace').strip().splitlines()
            results.append((name, p.returncode, tail[-1][:110] if tail else ''))
        for name, code, tail in results:
            if code is None:
                bad.append('%s：%s —— 本条**没验**' % (name, tail))
            elif code != 0:
                bad.append('%s 在**合并结果**上不绿（退出码 %s）：%s' % (name, code, tail))
        if auto:
            print('  ℹ️ git **自动合并**了 %d 个文件：%s' % (len(auto), '、'.join(auto[:6])))
            print('     ⭐ 自动合并成功 ≠ 结果正确 —— 这正是本门在**合并结果**上跑门禁的理由。')
        return (not bad), bad
    finally:
        shutil.rmtree(d, True)


def _print_boundary():
    """⚠️ 绿时也要说清验不了什么。必须定义在 _self_test 之前。"""
    print('⚠️ 本门**验不了**：两边都对但合起来**语义矛盾**（例：一边定「阈值不写图上」、'
          '另一边定「阈值写进 manifest」，各自合理、合起来两套说法）——'
          '⛔ 那一层只能靠 .proposals/ 的闭环对话。`--merge-check` 只回答「合完还绿不绿」，'
          '**不回答「合完对不对」**。')


def _self_test():
    import tempfile
    import shutil
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        ok = ok and bool(c)
        print('  %s %s%s' % ('✅' if c else '❌', n, '' if c else '　' + e))

    man = load_manifest()
    chk('清单读得到且三方齐全', man is not None and
        set(man['owners']) >= {'claude', 'codex', 'shared'})

    v, bad = check_ownership('claude', ['skills/product-flow/templates/prd-complete.md'], man)
    chk('正例：改自己的路径 → 绿', v is True, '实得 %s' % (bad[:1],))

    v, bad = check_ownership('claude', ['skills/product-flow/scripts/_workflow.py'], man)
    chk('反例 A：改对方的路径 → 红且点名归谁',
        v is False and any('属于 **codex**' in b for b in bad), '实得 %s' % (bad[:1],))

    v, bad = check_ownership('codex', ['skills/product-flow/scripts/diagram-id-gate.py'], man)
    chk('反例 A2：反方向同样拦（codex 改 claude 独占路径）',
        v is False and any('属于 **claude**' in b for b in bad))

    # ── 2026-09-15 C2「说明必须点名」的自证 ──
    #   ⚠️ 这条要在**真实仓库**上验：它会去读 .proposals 文件的内容。
    # ⚠️ 要挑一个**只在 shared、不在 claude 自己名下**的路径：
    #   check_ownership 先查 mine 再查 shared，落在自己名下的根本走不到 C2。
    #   （no-loss-baseline.json 同时在两个清单里，用它测不到这条 —— 第一版就踩了。）
    _SH = 'skills/product-flow/SKILL.md'   # 只在 shared
    _NOTE_NAMED = 'skills/product-flow/.proposals/WIP-claude-2026-09-15-autorun.md'
    v, bad = check_ownership('claude', [_SH, 'skills/product-flow/.proposals/不相干说明.md'], man)
    chk('反例 C2：改了 shared 承重件，带的说明**没点名**它 → 红',
        v is False and any('C2' in b for b in bad), '实得 %s' % (bad[:1],))
    import os as _os2
    if _os2.path.exists(_os2.path.join(REPO, _NOTE_NAMED)):
        _txt = io.open(_os2.path.join(REPO, _NOTE_NAMED), encoding='utf-8').read()
        _named = 'skills/product-flow/references/path-ownership.json'
        if _named in _txt or _os2.path.basename(_named) in _txt:
            v, bad = check_ownership('claude', [_named, _NOTE_NAMED], man)
            chk('正例 C2：说明里点名了该 shared 路径 → 放行（⛔ 不许因此还红）',
                v is True, '实得 %s' % (bad[:1],))

    # ── 2026-09-15 墓碑判据的自证（⛔ 没有反例的判据等于没判据）──
    _ok_t, _bad_t = check_tombstones(man)
    chk('正例 A：真实清单里没有幽灵条目，也没有复活的墓碑', _ok_t, '实得 %s' % (_bad_t[:1],))

    import tempfile as _tf, json as _json, os as _os
    _sand = _tf.mkdtemp(prefix='cg-tomb-')
    _os.makedirs(_os.path.join(_sand, 'a'), exist_ok=True)
    io.open(_os.path.join(_sand, 'a', 'real.md'), 'w', encoding='utf-8').write('x')
    _m_ghost = {'owners': {'claude': ['a/real.md', 'a/gone.md']}, 'tombstones': []}
    _v, _b = check_tombstones(_m_ghost, root=_sand)
    chk('反例 D1：条目指向不存在的文件且没登记墓碑 → 红',
        _v is False and any('幽灵条目' in x for x in _b), '实得 %s' % (_b[:1],))
    _m_ok = {'owners': {'claude': ['a/real.md', 'a/gone.md']},
             'tombstones': [{'path': 'a/gone.md', 'since': '2026-09-15',
                             'replacedBy': 'a/real.md', 'why': '退场'}]}
    _v, _b = check_tombstones(_m_ok, root=_sand)
    chk('正例 B：同一条目登记进 tombstones 后放行（⛔ 不许因此还红）', _v is True, '实得 %s' % (_b[:1],))
    _m_zombie = {'owners': {'claude': ['a/real.md']},
                 'tombstones': [{'path': 'a/real.md', 'since': '2026-09-15', 'why': '退场'}]}
    _v, _b = check_tombstones(_m_zombie, root=_sand)
    chk('反例 D2：登记为墓碑的文件又回来了 → 红（过期登记会骗人）',
        _v is False and any('墓碑复活' in x for x in _b), '实得 %s' % (_b[:1],))

    # ── E 全量归属对账（棘轮）2026-09-15 ──
    #   ⭐ 正例先跑真实仓库：它证明棘轮**当下是绿的**，否则下面三个反例红了也说明不了什么
    #     （基线本来就红的话，反例的红分不清是判据抓到的还是存量带的）。
    _ok_i, _bad_i = check_inventory(man)
    chk('正例 E：真实仓库的归属棘轮当前是绿的（基线与清单一致）',
        _ok_i is True, '实得 %s' % (_bad_i[:1],))

    _sandi = _tf.mkdtemp(prefix='cg-inv-')
    _os.makedirs(_os.path.join(_sandi, 'pkg'), exist_ok=True)
    for _f in ('owned.py', 'baselined.py', 'brandnew.py'):
        io.open(_os.path.join(_sandi, 'pkg', _f), 'w', encoding='utf-8').write('x')
    _man_i = {'owners': {'claude': ['pkg/owned.py']}, 'tombstones': []}

    def _mkbase(items, name='base.json'):
        _bp = _os.path.join(_sandi, name)
        io.open(_bp, 'w', encoding='utf-8').write(
            _json.dumps({'unregistered': items}, ensure_ascii=False))
        return name

    _G = ('pkg/*.py',)
    _v, _b = check_inventory(_man_i, root=_sandi, globs=_G,
                             baseline_path=_mkbase(['pkg/baselined.py', 'pkg/brandnew.py']))
    chk('正例 E0：有主的 + 挂在基线的，全都放行（⛔ 棘轮不许惩罚现状）',
        _v is True, '实得 %s' % (_b[:1],))
    _v, _b = check_inventory(_man_i, root=_sandi, globs=_G,
                             baseline_path=_mkbase(['pkg/baselined.py'], 'b2.json'))
    chk('反例 E1：新增一个既没主、也不在基线的文件 → 红（棘轮不许变松）',
        _v is False and any('E1' in x for x in _b), '实得 %s' % (_b[:1],))
    _v, _b = check_inventory(_man_i, root=_sandi, globs=_G,
                             baseline_path=_mkbase(
                                 ['pkg/owned.py', 'pkg/baselined.py', 'pkg/brandnew.py'], 'b3.json'))
    chk('反例 E2：已经登记到 owners 了却还挂在基线 → 红（逼你划掉，防清单腐烂）',
        _v is False and any('E2' in x for x in _b), '实得 %s' % (_b[:1],))
    _v, _b = check_inventory(_man_i, root=_sandi, globs=_G,
                             baseline_path=_mkbase(
                                 ['pkg/baselined.py', 'pkg/brandnew.py', 'pkg/早没了.py'], 'b4.json'))
    chk('反例 E3：基线里挂着一个已经不存在的文件 → 红',
        _v is False and any('E3' in x for x in _b), '实得 %s' % (_b[:1],))
    _v, _b = check_inventory(_man_i, root=_sandi, globs=_G, baseline_path='不存在的基线.json')
    chk('反例 E4：基线文件缺失 → UNABLE（没验成，⛔ 不是通过）',
        _v is None, '实得 %s / %s' % (_v, _b[:1]))

    v, bad = check_ownership('claude', ['skills/product-flow/scripts/某个没登记的.py'], man)
    chk('反例 B：孤儿路径 → 红（连清单都没有的东西没人会认领）',
        v is False and any(b.startswith('B 孤儿') for b in bad))

    v, bad = check_ownership('claude', ['skills/product-flow/SKILL.md'], man)
    chk('反例 C：改 shared 但没有说明条目 → 红',
        v is False and any(b.startswith('C shared') for b in bad), '实得 %s' % (bad[:1],))

    # A distributable regression must not depend on private historical notes.
    with tempfile.TemporaryDirectory(prefix='coord-note-') as note_root:
        note = 'skills/product-flow/.proposals/synthetic-review.md'
        note_path = os.path.join(note_root, note)
        os.makedirs(os.path.dirname(note_path), exist_ok=True)
        with io.open(note_path, 'w', encoding='utf-8') as stream:
            stream.write('Reviewed change: skills/product-flow/SKILL.md. Synthetic test only.')
        v, bad = check_ownership('claude', ['skills/product-flow/SKILL.md', note], man, root=note_root)
    chk('正例：改 shared **且**有说明条目 → 绿（⛔ 收紧不许误伤正确用法）',
        v is True, '实得 %s' % (bad[:1],))

    v, bad = check_ownership('someone-else', ['a'], man)
    chk('反例 D：未知 agent → 红（⛔ 不许静默放行）', v is None and bad)

    d2 = tempfile.mkdtemp(prefix='coord-nm-')
    io.open(os.path.join(d2, 'x.json'), 'w', encoding='utf-8').write('{}')
    chk('清单不存在 → 返回 None（调用方须判 UNABLE，⛔ 不当通过）',
        load_manifest(os.path.join(d2, 'nope.json')) is None)
    shutil.rmtree(d2, True)

    # 通配符语义：`dir/**` 要能匹配深层
    chk('`templates/diagrams/**` 能匹配深层文件',
        _match('skills/product-flow/templates/diagrams/a/b.d2',
               ['skills/product-flow/templates/diagrams/**']))

    print('\n%s' % ('✅ 自证通过：越界改动与孤儿会被抓住' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    """⛔ 本门自身崩溃必须退 2，不许和「有违规」共用退出码 1。"""
    try:
        return fn()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback
        print('UNABLE: 工具自身异常：%s: %s' % (type(_e).__name__, _e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv:
        print((__doc__ or '').strip()); sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())

    man = load_manifest()
    if man is None:
        die('找不到 %s —— 本门**没验**，⛔ 不是通过' % os.path.relpath(MANIFEST, REPO))

    _res = []
    if '--merge-check' in sys.argv:
        i = sys.argv.index('--merge-check')
        if i + 1 >= len(sys.argv):
            die('--merge-check 要跟一个 ref')
        ref = sys.argv[i + 1]

        def _run_m():
            _res.append(merge_check(ref))
        _main_guarded(_run_m)
        v, bad = _res[0]
    elif '--who' in sys.argv:
        i = sys.argv.index('--who')
        if i + 1 >= len(sys.argv):
            die('--who 要跟 agent 名')
        who = sys.argv[i + 1]
        base = 'HEAD'
        if '--base' in sys.argv:
            bi = sys.argv.index('--base')
            if bi + 1 >= len(sys.argv):
                die('--base 要跟 ref')       # 缺值守卫:否则 IndexError→裸traceback→退1,被gate-run记成FAIL(与真违规同码)
            base = sys.argv[bi + 1]
        if in_merge():
            changed = merge_authored_paths()
            print('ℹ️ **合并态**：只检查你实际解决的冲突（与两个父提交都不同的路径），'
                  '⛔ 不把对方带进来的文件算到你头上。')
        else:
            changed = changed_paths(base)
        if changed is None:
            die('不是 git 仓库或 git 不可用')
        if not changed:
            print('（相对 %s 无改动）' % base)
            _print_boundary()
            sys.exit(0)

        def _run_w():
            _ok, _bad = check_ownership(who, changed, man)
            # ⭐ 幽灵/复活条目与「谁改了什么」无关，任何一次 --who 都该顺手守住 ——
            #   它守的是清单**自己**的健康度，而清单是本门的全部判据来源。
            _tok, _tbad = check_tombstones(man)
            _iok, _ibad = check_inventory(man)      # 2026-09-15 全量归属棘轮
            _all = _bad + _tbad + _ibad
            if _ok is None or _iok is None:
                _res.append((None, _all))
            else:
                _res.append((bool(_ok) and _tok and _iok, _all))
        _main_guarded(_run_w)
        v, bad = _res[0]
    else:
        die('要给 --who <agent> 或 --merge-check <ref>；用法见 --help')

    _print_boundary()
    for b in bad or []:
        print('  ❌ ' + b)
    if v is True:
        print('✅ 协同检查通过')
    sys.exit(0 if v is True else (2 if v is None else 1))
