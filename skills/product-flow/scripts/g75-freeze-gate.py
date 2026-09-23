#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G7.5 三方冻结门 —— 十四查清单里本地可机器判的那部分，真跑；原生回读部分按证据判。

═══ 它补的是哪个洞（2026-09-08 终局规格 2-1）═══
G7.5 在阶段表与 triad-reconciliation.md 里有整套清单，但 scripts/ 里没有任何执行物 ——
「三方冻结」全靠人肉勾选。**没有执行物的总门，和不存在的总门效果一样。**

本地六查（真跑）：
  ① PRD 的 OPEN 项登记表全部 closed / deferred（deferred 必须带 owner+期限）
  ② prd-backfill.md 无 open 的 DELTA
  ③ deviation-register.md 无 open 的高影响偏差
  ④ 洞察账本（research-decision-ledger）里 high/medium 强度的 INS 全有最终处置
  ⑤ reconcile-gate G2、G3 **各自**在案且 PASS（读 .product-flow/gates/ 的分键记录；NOT-RUN 即红，不是 UNABLE）
  ⑥ 切片登记表（slice-registry）存在且四个覆盖类型全有着落

原生回读三查（按证据字段判，缺= UNABLE 语义写进结论）：
  ⑦ prd.readbackReceipt ⑧ figma.structureReceipt ⑨ html.runReceipt —— **只认 receipt**
  （receipt-check 通过 + environment=live + artifactKind 匹配；裸时间戳=手填自证，不再计数）

用法:
  g75-freeze-gate.py <项目根>  [--json]     # 项目根下应有 .product-flow/ 与文档
  g75-freeze-gate.py --self-test
退出码: 0=本地六查全过（stdout 明示冻结上限） 1=有缺口 2=跑不了

⚠️ 诚实边界：
  - 绿了只说明**本地契约**成立。原生证据（⑦⑧⑨）不齐时，冻结上限是「本地契约验证通过」，
    ⛔ 不得宣 integrated-frozen —— 本门会把上限印在结论里。
  - 第⑤查读的是 gate-run 的**分键**落盘记录（reconcile-gate.py.G2.json / .G3.json）——
    旧共用记录一条 PASS 顶两门的假阳性已修（Codex 复审 P0），旧记录不再作数。
  - 十四查里的人工联合验收（三方对着原件看）本门验不了，永远要人做。
"""
import io, json, os, re, sys, hashlib, subprocess


def _deadline_of(status):
    """从 deferred 状态里解出一个**真实且未过期**的期限。返回 (日期或 None, 说明)。

    ⚠️ 取状态里**最晚**的那个日期（区间写法「2026-01-01 至 2026-03-31」该按结束日算）。
    ⚠️ 容差 0 天：期限是「到这天为止」，过了就是过了。⛔ 不给宽限 ——
      给了宽限就等于「再拖一点点」也算带期限，那正是本判据要拦的东西。
    """
    import datetime as _dt
    found, invalid = [], False
    for y, mo, d in re.findall(r'(\d{4})-(\d{2})-(\d{2})', status or ''):
        try:
            found.append(_dt.date(int(y), int(mo), int(d)))
        except ValueError:
            invalid = True
    if not found:
        return None, ('期限 %r 不是真实日期（只测形状等于没测）' % status[:24]
                      if invalid else '缺期限（状态里要写明到哪天为止）')
    due = max(found)
    if due < _dt.date.today():
        return None, ('期限 %s **已经过了** —— 过期的期限就是永久延期，只是穿了件日期的外衣'
                      % due.isoformat())
    return due, ''


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def read(p):
    try:
        return io.open(p, encoding='utf-8').read()
    except Exception:
        return None


def find_doc(root, names):
    """在项目根与 .product-flow/ 常见位置找文档，返回首个存在的路径或 None。"""
    cands = []
    for n in names:
        cands += [os.path.join(root, n),
                  os.path.join(root, '.product-flow', n),
                  os.path.join(root, '.product-flow', 'prd', n),
                  os.path.join(root, 'docs', n)]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def table_rows(md, head_kw):
    """取包含 head_kw 的小节里第一张表的数据行（切到下个标题为止）。"""
    i = md.find(head_kw)
    if i < 0:
        return None
    seg = md[i:]
    j = re.search(r'\n#{1,3} ', seg[1:])
    if j:
        seg = seg[:j.start() + 1]
    rows = [l for l in seg.split('\n') if l.strip().startswith('|')]
    return [r for r in rows[2:] if r.replace('|', '').replace('-', '').strip()]


def check(root):
    bad, info = [], []
    pf = os.path.join(root, '.product-flow')

    # ① OPEN 项
    prd = find_doc(root, ('PRD.md', 'prd.md'))
    if not prd:
        bad.append('① 找不到 PRD.md —— v1.0 冻结的对象都不在')
    else:
        md = read(prd) or ''
        rows = table_rows(md, 'OPEN 项登记表')
        if rows is None:
            bad.append('① PRD 没有「OPEN 项登记表」—— v0.9 模板必带（空表也要有，写「无 OPEN 项」）')
        else:
            for r in rows:
                cells = [c.strip() for c in r.strip().strip('|').split('|')]
                if len(cells) < 6 or cells[0].startswith('OPEN-001') and '<示例' in r:
                    continue
                if '无 OPEN 项' in r:
                    continue
                st = cells[-1]
                if st.startswith('closed'):
                    continue
                if st.startswith('deferred'):
                    # deferred 必须带 owner（第 3 列）与期限（状态里带日期）
                    # 🚨🚨 2026-09-11 系统扫「只测形状」这一类时抓到，本条**三种写法都能绕过**，
                    #   而它的原话就是「无主延期=永久方案」：
                    #     · `deferred 至以后再说` —— 旧正则的 `|至` 分支让**任何含「至」字的状态**
                    #       免于带日期。这个分支本意是认「2026-01 至 2026-03」这种区间写法，
                    #       实际成了一张万能通行证。
                    #     · `deferred 9999-99-99` —— 只测形状，**不存在的日期**照样算期限。
                    #     · `deferred 2020-01-01` —— 形状对、日期真，但**已经过期**。
                    #       ⭐ 一个过期的期限就是永久延期，只是穿了件日期的外衣 ——
                    #         这条正是判据要拦的东西，而判据放它过去了。
                    #   ⇒ 改成解析出**真实且未过期**的日期。⛔ 不再接受「含某个字」这种代理指标。
                    _owner_ok = len(cells) >= 3 and cells[2] and not cells[2].startswith('<')
                    _due, _why = _deadline_of(st)
                    if _owner_ok and _due:
                        continue
                    bad.append('① OPEN 项 %s deferred 但%s —— 无主延期=永久方案'
                               % (cells[0], '缺 owner' if not _owner_ok else _why))
                    continue
                bad.append('① OPEN 项 %s 状态「%s」—— 冻结前只许 closed/deferred(带主带期)' % (cells[0], st or '空'))

    # ② prd-backfill
    bf = find_doc(root, ('prd-backfill.md',))
    if not bf:
        bad.append('② 没有 prd-backfill.md —— 若确无设计/交互 delta，也要建一份写「无」（沉默≠没有）')
    else:
        opens = [r for r in (table_rows(read(bf) or '', 'DELTA') or [])
                 if re.search(r'\|\s*open\s*\|?\s*$', r) and 'DELTA-001' not in r]
        if opens:
            bad.append('② prd-backfill 有 %d 条 open 的 DELTA —— 回灌完才能冻结' % len(opens))

    # ③ deviation-register
    dv = find_doc(root, ('deviation-register.md',))
    if dv:
        opens = [r for r in (table_rows(read(dv) or '', '偏差登记') or [])
                 if re.search(r'\|\s*open\s*\|?\s*$', r) and 'DEV-001' not in r]
        if opens:
            bad.append('③ deviation-register 有 %d 条 open 偏差' % len(opens))
    else:
        info.append('③ 无 deviation-register.md（S9.3 前建；G7.5 阶段可无）')

    # ④ 洞察账本
    lg = find_doc(root, ('research-decision-ledger.md',))
    if not lg:
        bad.append('④ 没有洞察账本 research-decision-ledger.md —— 高强度洞察的处置无从核对')
    else:
        md = read(lg) or ''
        for m in re.finditer(r'### (INS-\d+)(.*?)(?=### INS-|\Z)', md, re.S):
            ins, body = m.group(1), m.group(2)
            st = re.search(r'强度[：:]\s*(high|medium|low|unknown)', body)
            dp = re.search(r'最终处置[：:]\s*(adopted|adapted|rejected|deferred|watch)', body)
            if st and st.group(1) in ('high', 'medium') and not dp:
                bad.append('④ %s 强度 %s 但没有最终处置 —— 沉默消失才是错误' % (ins, st.group(1)))

    # ⑤ reconcile 在案：G2、G3 **各自**要有记录且 PASS（gate-run 已按子门号分键落盘）。
    #   ⛔ 旧共用记录 reconcile-gate.py.json 不再作数 —— 一条 PASS 顶两门是 Codex 复审定的 P0 假阳性。
    legacy = os.path.isfile(os.path.join(pf, 'gates', 'reconcile-gate.py.json'))
    missing, notpass = [], []
    for tag in ('G2', 'G3'):
        p5 = os.path.join(pf, 'gates', 'reconcile-gate.py.%s.json' % tag)
        if not os.path.isfile(p5):
            missing.append(tag)
            continue
        try:
            v = json.load(io.open(p5, encoding='utf-8')).get('verdict')
        except Exception:
            v = 'UNREADABLE'
        if v != 'PASS':
            notpass.append('%s=%s' % (tag, v))
    if missing:
        bad.append('⑤ reconcile-gate %s 结论不在案（NOT-RUN）—— 用 gate-run.py 分别跑 G2/G3 落盘；没跑≠通过%s'
                   % ('、'.join(missing),
                      '（发现旧共用记录 reconcile-gate.py.json —— 它只能证明最近一次运行，不认）' if legacy else ''))
    elif notpass:
        bad.append('⑤ reconcile-gate 在案结论非 PASS：%s' % '、'.join(notpass))
    else:
        info.append('⑤ reconcile G2/G3 各自在案且 PASS')

    # ⑥ 切片登记
    sl = find_doc(root, ('slice-registry.md',))
    if not sl:
        bad.append('⑥ 没有 slice-registry.md —— B 锁的四覆盖类型无从核对')
    else:
        rows = table_rows(read(sl) or '', '覆盖类型对账') or []
        empty = [r.strip().strip('|').split('|')[0].strip() for r in rows
                 if len(r.strip().strip('|').split('|')) >= 2
                 and not r.strip().strip('|').split('|')[1].strip()]
        if empty:
            bad.append('⑥ 切片覆盖类型有空缺：%s' % '、'.join(empty))

    # ⑦⑧⑨ 原生证据
    cm = find_doc(root, ('contract-manifest.json',))
    native_ok = 0
    if cm:
        try:
            d = json.load(io.open(cm, encoding='utf-8'))
        except Exception:
            d = {}
        # ⛔ 只认 receipt（receipt-check 通过 + environment=live + artifactKind 匹配）。
        # 裸时间戳不再计数：三个任意 'T' 曾把冻结上限抬到 integrated-frozen（Codex 三审 P0-4）。
        # receipt 的第一位真签发方=doc-sync-guard readback（飞书实弹）；figma/html 适配器分期，
        # 但 receipt-check ④ 要求 rawEvidenceRef 真实存在——伪造成本从「填一个 T」抬到「编一整套凭据」。
        _rcheck = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receipt-check.py')
        _legacy_key = {'prd': 'lastReadbackAt', 'figma': 'structureReadbackAt', 'html': 'lastRunAt'}
        for k, rkey, kind, path, label in (('prd', 'readbackReceipt', 'feishu-prd', '⑦', '飞书回读'),
                                           ('figma', 'structureReceipt', 'figma', '⑧', 'Figma 结构回读'),
                                           ('html', 'runReceipt', 'html', '⑨', 'HTML 浏览器运行')):
            sec = d.get(k) or {}
            rp = str(sec.get(rkey) or '')
            if not rp or rp.startswith('<'):
                info.append('%s %s 无 receipt（%s.%s 为空%s）'
                            % (path, label, k, rkey,
                               '；有裸时间戳但**手填自证不算**——用适配器签发 receipt（如 doc-sync-guard readback）'
                               if sec.get(_legacy_key[k]) else ''))
                continue
            rf = rp if os.path.isfile(rp) else os.path.join(root, rp)
            if not os.path.isfile(rf):
                bad.append('%s %s 声称有 receipt 但文件不存在：%s —— 声称≠实际' % (path, label, rp))
                continue
            pr = subprocess.run([sys.executable, _rcheck, rf, '--json'], capture_output=True, text=True)
            try:
                res = json.loads(pr.stdout.strip().splitlines()[-1])
            except Exception:
                res = {'bad': ['receipt-check 输出解析失败']}
            if pr.returncode != 0:
                bad.append('%s %s 的 receipt 无效：%s' % (path, label, (res.get('bad') or ['?'])[0]))
            elif res.get('artifactKind') != kind:
                bad.append('%s receipt 的 artifactKind=%s 与 %s 不符 —— 拿别家的凭据顶数不行'
                           % (path, res.get('artifactKind'), kind))
            elif res.get('environment') != 'live':
                info.append('%s %s receipt 是 test 环境 —— 只证契约，不解真实上限' % (path, label))
            else:
                native_ok += 1
        # 本地哈希对账：manifest.spec 里登记的文件与磁盘一致
        for fn, h in (d.get('spec') or {}).items():
            fp = find_doc(root, (os.path.join('spec', fn), fn))
            if fp and h and not h.startswith('<'):
                real = hashlib.sha1(io.open(fp, 'rb').read()).hexdigest()
                if real != h:
                    bad.append('manifest.spec 里 %s 的哈希与磁盘不一致 —— 投影过期（改了没回账）' % fn)
    else:
        info.append('⑦⑧⑨ 无 contract-manifest.json —— 三类原生证据全部缺席')

    if cm and native_ok == 3:
        try:
            _t = json.load(io.open(cm, encoding='utf-8')).get('triad') or {}
            if not _t.get('reverseLinkWritten'):
                info.append('反向锚未写（triad.reverseLinkWritten=false）—— 飞书/Figma 侧还不知道'
                            '自己对应哪个冻结版本（Linkage 最低标准是两边互记）')
        except Exception:
            pass
    ceiling = ('integrated-frozen 可宣（三类原生证据齐）' if native_ok == 3 else
               '⛔ 冻结上限=**本地契约验证通过**（原生证据 %d/3 —— 缺的那几类是 UNABLE 不是通过）' % native_ok)
    return bad, info, ceiling


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    unknown = [x for x in sys.argv[1:] if x.startswith('--') and x not in ('--json', '--self-test')]
    if unknown:
        die('不认识的参数 %s；用法见 --help' % unknown[0])
    if not a:
        die('缺少项目根目录；用法见 --help')
    root = a[0]
    if not os.path.isdir(root):
        die('项目根不存在：%s' % root)
    bad, info, ceiling = check(root)
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad, 'info': info, 'ceiling': ceiling}, ensure_ascii=False, indent=1))
    else:
        print('G7.5 三方冻结门 —— 本地六查 + 原生证据三查\n')
        for b in bad:
            print('  ❌ ' + b)
        for i in info:
            print('  ℹ️ ' + i)
        print('\n%s' % ('✅ 本地六查全过' if not bad else '❌ %d 处缺口，不能冻结' % len(bad)))
        print(ceiling)
        print('⚠️ 本门验不了：人工三方联合验收（对着飞书原文/Figma 原图/可运行 HTML 看）——那一步永远要人做。')
    sys.exit(0 if not bad else 1)


# ------------------------------------------------------------------ M8 自证
def _self_test():
    import tempfile, shutil, subprocess
    t = tempfile.mkdtemp(prefix='g75-')
    ok = True

    def chk(name, cond, extra=''):
        nonlocal ok
        print(('  ✅ ' if cond else '  ❌ ') + name + ('' if cond else '　' + extra))
        ok = ok and cond

    def mk(root, **over):
        """造一套可冻结的最小项目，over 里给的文件内容覆盖默认。"""
        shutil.rmtree(root, ignore_errors=True)
        os.makedirs(os.path.join(root, '.product-flow', 'gates'), exist_ok=True)
        files = {
            'PRD.md': ('# X PRD\n### OPEN 项登记表\n\n| ID | 内容 | owner | 决策阶段 | 回灌位置 | 状态 |\n'
                       '|---|---|---|---|---|---|\n| OPEN-002 | 空态插画 | 张三 | S5 | 四章 | closed |\n'),
            'prd-backfill.md': ('# 回灌\n## DELTA\n| DELTA-ID | 来源 | 原值 | 新值 | 影响域 | 处置 | 回灌位置 | 状态 |\n'
                                '|---|---|---|---|---|---|---|---|\n| DELTA-002 | figma | a | b | 文案 | 回灌 | 四章 | closed |\n'),
            'research-decision-ledger.md': ('# 账本\n### INS-001\n- 命题：x\n- 强度：high\n- 最终处置：adopted\n'),
            'slice-registry.md': ('# 切片\n## 覆盖类型对账\n| 覆盖类型 | 由哪个切片覆盖 |\n|---|---|\n'
                                  '| 最核心的完成路径 | 切片1 |\n| 最难一屏 | 切片1 |\n'
                                  '| 异常恢复 | 切片2 |\n| 端差异 | N/A 单端 |\n'),
            '.product-flow/gates/reconcile-gate.py.G2.json': json.dumps({'verdict': 'PASS'}),
            '.product-flow/gates/reconcile-gate.py.G3.json': json.dumps({'verdict': 'PASS'}),
        }
        files.update(over)
        for rel, c in files.items():
            if c is None:
                continue
            p = os.path.join(root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, 'w', encoding='utf-8').write(c)
        return root

    def run(root):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), root],
                           capture_output=True, text=True)
        return r.returncode, r.stdout

    d = os.path.join(t, 'p')
    rc, out = run(mk(d))
    chk('正例：六查全过 → 0，且明示冻结上限', rc == 0 and '冻结上限' in out, '实得 %d' % rc)

    rc, _ = run(mk(d, **{'PRD.md': '# X PRD\n没有那张表\n'}))
    chk('反例①a：PRD 无 OPEN 表 → 1', rc == 1, '实得 %d' % rc)
    rc, _ = run(mk(d, **{'PRD.md': ('# X\n### OPEN 项登记表\n| ID | 内容 | owner | 阶段 | 回灌 | 状态 |\n'
                                    '|---|---|---|---|---|---|\n| OPEN-2 | x | 李 | S5 | 四 | open |\n')}))
    chk('反例①b：有 open 的 OPEN 项 → 1', rc == 1)
    # ⚠️ 期限一律用**相对今天**算，⛔ 不硬编码：
    #   原来这条写死 `deferred(至2026-10-01)`，本意是测「无 owner」——
    #   可一过那天，它会**因为另一个原因红**（期限过期），夹具就不再测它声称测的东西了。
    #   同一个坑我今天刚在 adr-check 的夹具里修过一次。
    import datetime as _dt
    _future = (_dt.date.today() + _dt.timedelta(days=365)).isoformat()
    _past = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

    def _openrow(owner, status):
        return ('# X\n### OPEN 项登记表\n| ID | 内容 | owner | 阶段 | 回灌 | 状态 |\n'
                '|---|---|---|---|---|---|\n| OPEN-2 | x | %s | S5 | 四 | %s |\n'
                % (owner, status))

    rc, out_c = run(mk(d, **{'PRD.md': _openrow('', 'deferred(至%s)' % _future)}))
    chk('反例①c：deferred 无 owner → 1（无主延期=永久方案）',
        rc == 1 and '缺 owner' in out_c, '实得 rc=%d out=%r' % (rc, out_c[:100]))
    # ===== 2026-09-11 系统扫「只测形状」抓到的三种绕过，全部配反例 =====
    # ⚠️ 反例一律**锚定判据**：只断言 rc==1 只能证明「门红了」，不能证明
    #   「为**这条**理由红」。今天两次被这个坑（夹具因另一个原因红，就不再测它声称测的东西）。
    rc, out_d = run(mk(d, **{'PRD.md': _openrow('张三', 'deferred 至以后再说')}))
    chk('反例①d：deferred「至以后再说」→ 1（旧正则的 `|至` 分支是张万能通行证）',
        rc == 1 and '缺期限' in out_d, '实得 rc=%d out=%r' % (rc, out_d[:100]))
    rc, out_e = run(mk(d, **{'PRD.md': _openrow('张三', 'deferred 9999-99-99')}))
    chk('反例①e：deferred 期限是**不存在的日期** → 1（只测形状等于没测）',
        rc == 1 and '不是真实日期' in out_e, '实得 rc=%d out=%r' % (rc, out_e[:100]))
    rc, out_g = run(mk(d, **{'PRD.md': _openrow('张三', 'deferred 至 %s' % _past)}))
    chk('反例①f：deferred 期限**已经过了** → 1'
        '（过期的期限就是永久延期，只是穿了件日期的外衣）',
        rc == 1 and '已经过了' in out_g, '实得 rc=%d out=%r' % (rc, out_g[:100]))
    # 🚨 第一版这条写成 `'① OPEN 项' not in _[0] if isinstance(_, tuple) else True` ——
    #   `_` 是输出字符串不是元组 ⇒ 条件**恒为 True**，这条用例什么都不测。
    #   ⭐ 今天第三个「恒绿判据」（前两个：adr-check 的 superseded、receipt-check 的去重）。
    rc, out_p = run(mk(d, **{'PRD.md': _openrow('张三', 'deferred 至 %s' % _future)}))
    chk('正例：deferred 带 owner + 未过期的真实期限 → 不因①红（⛔ 收紧不许误伤正确写法）',
        '① OPEN 项' not in out_p, '实得 %r' % out_p[:120])
    rc, out_f = run(mk(d, **{'PRD.md': _openrow('张三',
                             'deferred 从 %s 至 %s' % (_past, _future))}))
    chk('正例：区间写法按**结束日**算 → 不因①红（起始日在过去不影响）',
        '① OPEN 项' not in out_f)
    rc, _ = run(mk(d, **{'prd-backfill.md': ('# 回灌\n## DELTA\n| DELTA-ID | a | b | c | d | e | f | 状态 |\n'
                                             '|---|---|---|---|---|---|---|---|\n| DELTA-2 | | | | | | | open |\n')}))
    chk('反例②：backfill 有 open DELTA → 1', rc == 1)
    rc, _ = run(mk(d, **{'research-decision-ledger.md': '# 账本\n### INS-001\n- 命题：x\n- 强度：high\n- 最终处置：\n'}))
    chk('反例④：high 强度 INS 无处置 → 1', rc == 1)
    rc, _ = run(mk(d, **{'.product-flow/gates/reconcile-gate.py.G2.json': None}))
    chk('反例⑤a：reconcile G2 NOT-RUN → 1（没跑≠通过，不折叠成 UNABLE）', rc == 1)
    rc, _ = run(mk(d, **{'.product-flow/gates/reconcile-gate.py.G3.json': json.dumps({'verdict': 'UNABLE'})}))
    chk('反例⑤b：reconcile G3 在案 UNABLE → 1（跑了但没结论≠通过）', rc == 1)
    rc, _ = run(mk(d, **{'.product-flow/gates/reconcile-gate.py.G2.json': None,
                         '.product-flow/gates/reconcile-gate.py.G3.json': None,
                         '.product-flow/gates/reconcile-gate.py.json': json.dumps({'verdict': 'PASS'})}))
    chk('反例⑤c：只有旧共用记录 → 1（一条 PASS 不许顶 G2/G3 两门）', rc == 1)
    rc, _ = run(mk(d, **{'slice-registry.md': ('# 切片\n## 覆盖类型对账\n| 覆盖类型 | 由哪个切片覆盖 |\n'
                                               '|---|---|\n| 最核心的完成路径 |  |\n')}))
    chk('反例⑥：切片覆盖类型空缺 → 1', rc == 1)
    # 原生证据 receipt 化（Codex 三审 P0-4）：裸 'T' 不再解上限，三张有效 live receipt 才可宣
    mk(d, **{'contract-manifest.json': json.dumps({
        'prd': {'lastReadbackAt': 'T'}, 'figma': {'structureReadbackAt': 'T'},
        'html': {'lastRunAt': 'T'}, 'spec': {}})})
    rc, out = run(d)
    chk("反例：三个裸 'T' 时间戳 → 上限只到本地契约（曾被它抬到 integrated-frozen）",
        rc == 0 and 'integrated-frozen 可宣' not in out and '手填自证不算' in out)

    def _mk_receipts(env='live', prd_kind='feishu-prd', break_prd=None):
        mk(d, **{'contract-manifest.json': json.dumps({
            'prd': {'readbackReceipt': 'ER-p.json'},
            'figma': {'structureReceipt': 'ER-f.json'},
            'html': {'runReceipt': 'ER-h.json'},
            'triad': {'reverseLinkWritten': True}, 'spec': {}})})
        io.open(os.path.join(d, 'raw-ev.json'), 'w', encoding='utf-8').write('{}')
        for rid, kind in (('ER-p', prd_kind), ('ER-f', 'figma'), ('ER-h', 'html')):
            r = {'receiptSchema': '1.0', 'receiptId': rid, 'artifactKind': kind,
                 'artifactRef': 'x', 'nativeVersion': '4', 'capabilitiesExercised': ['readback'],
                 'observedAt': '2026-09-08T23:40:51', 'adapter': {'name': 't', 'version': '1'},
                 'rawEvidenceRef': os.path.join(d, 'raw-ev.json'), 'environment': env}
            if rid == 'ER-p' and break_prd:
                r.update(break_prd)
            io.open(os.path.join(d, rid + '.json'), 'w', encoding='utf-8').write(json.dumps(r))

    _mk_receipts()
    rc, out = run(d)
    chk('正例：三张有效 live receipt → integrated-frozen 可宣', rc == 0 and 'integrated-frozen 可宣' in out)
    _mk_receipts(env='test')
    rc, out = run(d)
    chk('反例：test 环境 receipt → 不解真实上限（只证契约）',
        rc == 0 and 'integrated-frozen 可宣' not in out and 'test 环境' in out)
    _mk_receipts(break_prd={'observedAt': 'T'})
    rc, out = run(d)
    chk("反例：receipt 里 observedAt='T' → 1（无效 receipt 是红，不是没证据）", rc == 1)
    _mk_receipts(prd_kind='figma')
    rc, _ = run(d)
    chk('反例：artifactKind 不匹配（拿 figma 凭据顶飞书）→ 1', rc == 1)
    _mk_receipts()
    os.remove(os.path.join(d, 'ER-p.json'))
    rc, _ = run(d)
    chk('反例：manifest 声称有 receipt 但文件不存在 → 1（声称≠实际）', rc == 1)
    spec_dir = os.path.join(d, 'spec')
    os.makedirs(spec_dir, exist_ok=True)
    io.open(os.path.join(spec_dir, 'copy.json'), 'w', encoding='utf-8').write('{"a":1}')
    io.open(os.path.join(d, 'contract-manifest.json'), 'w', encoding='utf-8').write(json.dumps({
        'prd': {}, 'figma': {}, 'html': {}, 'spec': {'copy.json': '0' * 40}}))
    rc, _ = run(d)
    chk('反例：manifest 里 spec 哈希与磁盘不一致 → 1（投影过期）', rc == 1)
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入：项目根不存在 → 2', rc == 2, '实得 %d' % rc)

    shutil.rmtree(t, ignore_errors=True)
    print('\n%s' % ('✅ 自证通过：这道门会出声' if ok else '❌ 自证失败：先修门禁'))
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
