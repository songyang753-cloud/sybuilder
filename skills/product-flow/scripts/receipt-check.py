#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原生证据 receipt 校验 —— 「manifest 里那个时间戳是谁写的」终于有了答案。

═══ 它补的洞（Codex 三审 P0-4 的本地半场）═══
G7.5 的原生三查此前只看 manifest 字段**非空**：三个任意字符串 'T' 就能把冻结上限
抬到 integrated-frozen。根因是**时间戳由执行者手填自证**——没有签发方、没有原始
证据指向、没有 live/test 之分。本工具校验的 receipt 由适配器在真实动作后签发
（如 `doc-sync-guard.py readback` 写盘的回读凭据），执行者只能引用，不能编造。

判据（模板 `templates/evidence-receipt.json`）：
  ① 必填字段齐：receiptId/artifactKind/artifactRef/nativeVersion/observedAt/adapter.name/rawEvidenceRef/environment
  ② artifactKind ∈ {feishu-prd, dingtalk-prd, figma, html, app}；environment ∈ {live, test}
  ③ observedAt 是可解析的时间（RFC3339 形），⛔ 任意字符串 'T' 不算
  ④ rawEvidenceRef 指向的本地文件**真实存在**（没有原始证据的 receipt 不算 receipt）
  ⑤ 占位符（<...>）未清零 = 模板没填完，不算签发

用法: receipt-check.py <receipt.json> [--json] | --self-test
退出码: 0=有效 1=无效 2=跑不了
⚠️ 验不了什么：签发方是否诚实（receipt 可以被伪造——防伪造靠 rawEvidenceRef 可追查 +
  adapter 侧的实弹验证，本工具只把「手填一个 T」的成本抬高成「伪造一整套带原始证据的凭据」）；
  environment=test 的 receipt 即使有效也只证契约，不解除真实声明上限——消费方（g75）负责区分。
"""
import io, json, os, re, sys
import hashlib

KINDS = {'feishu-prd', 'dingtalk-prd', 'figma', 'html', 'app'}
ENVS = {'live', 'test'}
REQUIRED = ['receiptId', 'artifactKind', 'artifactRef', 'nativeVersion',
            'observedAt', 'adapter', 'rawEvidenceRef', 'environment']
TS = re.compile(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?')


def _real_past_time(ts):
    """observedAt 必须是**真实存在且已经发生**的时间。

    🚨 2026-09-11 合入时的对抗探针抓到两处，都是本仓记录过的教训在新文件上原样复发：
      · `2026-13-45T99:99` 形状合法、日期不存在 ⇒ 旧判据放行。**只测形状＝没测**，
        `claim-ladder-backed` 当初正是被同一个形状骗的，那条已经修过一次。
      · `2999-12-31` 是未来 ⇒ 旧判据放行。观察记录不可能来自未来；
        允许它等于允许「先签 receipt 再补动作」。
    ⚠️ 容差 1 天：跨时区签发的 receipt 可能比本机时钟稍前，⛔ 不给更多
      （给多了就等于给伪造留窗口）。
    """
    import datetime as _dt
    m = TS.match(ts)
    if not m:
        return False, '不是可解析时间 —— 任意字符串冒充不了时间戳'
    y, mo, d, hh, mm = (int(x) for x in m.group(1, 2, 3, 4, 5))
    ss = int(m.group(6) or 0)
    try:
        t = _dt.datetime(y, mo, d, hh, mm, ss)
    except ValueError:
        return False, '是个**不存在的时间** —— 只测形状等于没测'
    if t > _dt.datetime.now() + _dt.timedelta(days=1):
        return False, '在**未来** —— 观察记录不可能来自未来'
    return True, ''


def _placeholders(v, path=''):
    """递归找没填完的模板占位符。

    🚨 旧判据只看**顶层字符串**，于是 `adapter.name = '<adapter-name>'` 一路绿灯 ——
      而本工具判据⑤原话就是「占位≠签发」，**签发方自己填占位符时它看不见**。
    """
    out = []
    if isinstance(v, str):
        if v.startswith('<') and v.endswith('>'):
            out.append(path or '(顶层)')
    elif isinstance(v, dict):
        for k, sub in v.items():
            out += _placeholders(sub, '%s.%s' % (path, k) if path else k)
    elif isinstance(v, list):
        for i, sub in enumerate(v):
            out += _placeholders(sub, '%s[%d]' % (path, i))
    return out


def die(m):
    print('UNABLE: %s' % m, file=sys.stderr)
    sys.exit(2)


def check(path):
    try:
        d = json.load(io.open(path, encoding='utf-8'))
    except Exception as e:
        return None, ['receipt 不是合法 JSON：%s' % str(e)[:60]]
    bad = []
    for k in REQUIRED:
        v = d.get(k)
        if v in (None, '', []):
            bad.append('① 缺必填字段 %s' % k)
        elif isinstance(v, str) and v.startswith('<') and not v.endswith('>'):
            # ⚠️ 闭合的 `<x>` 交给 _placeholders 递归统一报（否则同一处报两遍）；
            #   这里只兜**没闭合**的半截占位符（`<未填`），那种 _placeholders 认不出。
            bad.append('⑤ 字段 %s 是半截占位符 %r —— 没填完不算签发' % (k, v[:20]))
    # ⚠️ 2026-09-11 自查：第一版的去重写成 `b.split(' ')[1]`，取到的是「字段」两个字
    #   而不是字段名 ⇒ **去重从来没生效**，顶层占位符被报两遍。
    #   ⭐ 代码声称去重、实际没有 —— 本仓母题在一个刚合入的文件里又出现一次。
    #   ⇒ 顶层那一遍改由本函数统一出，不再分两处报。
    for _ph in _placeholders(d):
        bad.append('⑤ %s 还是模板占位符 —— 没填完不算签发（占位符可以藏在嵌套字段里）' % _ph)
    if d.get('artifactKind') not in KINDS and not str(d.get('artifactKind', '')).startswith('<'):
        bad.append('② artifactKind=%r 不在 %s' % (d.get('artifactKind'), sorted(KINDS)))
    if d.get('environment') not in ENVS and not str(d.get('environment', '')).startswith('<'):
        bad.append('② environment=%r 不在 {live, test}' % d.get('environment'))
    ts = str(d.get('observedAt', ''))
    if ts and not ts.startswith('<'):
        _ok, _why = _real_past_time(ts)
        if not _ok:
            bad.append("③ observedAt=%r %s" % (ts[:24], _why))
    if not (d.get('adapter') or {}).get('name'):
        bad.append('① adapter.name 缺失 —— 没有签发方的 receipt 是手填自证')
    ref = str(d.get('rawEvidenceRef', ''))
    if ref and not ref.startswith('<') and not os.path.exists(
            os.path.join(os.path.dirname(os.path.abspath(path)), ref)) and not os.path.exists(ref):
        bad.append('④ rawEvidenceRef=%s 指向的文件不存在 —— 没有原始证据的 receipt 不算 receipt' % ref[:60])
    if (d.get('adapter') or {}).get('name') == 'doc-sync-guard.readback':
        try:
            base = os.path.dirname(os.path.abspath(path))
            raw = os.path.join(base, d['rawEvidenceRef'])
            attempt = json.load(io.open(os.path.join(base, d['attemptRef']), encoding='utf-8'))
            snapshot = json.load(io.open(raw, encoding='utf-8'))
            if (d.get('receiptSchema') != '2.0' or attempt.get('attemptId') != d.get('attemptId')
                    or attempt.get('status') != 'PASS' or snapshot.get('validationStatus') != 'PASS'
                    or snapshot.get('attemptId') != d.get('attemptId')
                    or str(snapshot.get('remote_revision')) != d.get('nativeVersion')
                    or (snapshot.get('doc_token') or snapshot.get('url')) != d.get('artifactRef')
                    or hashlib.sha256(open(raw, 'rb').read()).hexdigest() != d.get('rawEvidenceHash')
                    or hashlib.sha256(open(d['sourceRef'], 'rb').read()).hexdigest() != d.get('sourceHash')):
                bad.append('⑥ 当前尝试失败/已变更，或源稿与回读证据不再匹配；历史成功不可复用')
            for media_path, digest in (snapshot.get('mediaValidation') or {}).get('files', {}).items():
                if hashlib.sha256(open(media_path, 'rb').read()).hexdigest() != digest:
                    bad.append('⑥ 媒体源/映射/上传证据变化，须重新验收')
        except (OSError, KeyError, TypeError, ValueError):
            bad.append('⑥ 缺当前代次/内容绑定，旧回执只能作为历史证据，须重新回读')
    return d, bad


def _entry():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not a:
        die('缺少 receipt 路径；用法见 --help')
    if not os.path.isfile(a[0]):
        die('文件不存在：%s' % a[0])
    d, bad = check(a[0])
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad, 'environment': (d or {}).get('environment'),
                          'artifactKind': (d or {}).get('artifactKind')}, ensure_ascii=False))
    else:
        for b in bad:
            print('  ❌ ' + b)
        if not bad:
            print('✅ receipt 有效（environment=%s%s）'
                  % (d.get('environment'), '——test 只证契约，不解真实上限' if d.get('environment') == 'test' else ''))
        else:
            print('❌ %d 处缺口' % len(bad))
    sys.exit(0 if not bad else 1)


def _self_test():
    import tempfile, subprocess
    t = tempfile.mkdtemp(prefix='rc-')
    raw = os.path.join(t, 'raw.sync.json')
    io.open(raw, 'w', encoding='utf-8').write('{}')
    GOOD = {'receiptSchema': '1.0', 'receiptId': 'ER-001', 'artifactKind': 'feishu-prd',
            'artifactRef': 'PROEdoc', 'nativeVersion': '4',
            'capabilitiesExercised': ['readback'], 'observedAt': '2026-09-08T23:40:51',
            'adapter': {'name': 'synthetic-adapter', 'version': '1'},
            'rawEvidenceRef': raw, 'environment': 'live'}
    ok = True

    def chk(n, c, e=''):
        nonlocal ok
        print(('  ✅ ' if c else '  ❌ ') + n + ('' if c else '　' + e))
        ok = ok and c

    def run(d):
        p = os.path.join(t, 'r.json')
        io.open(p, 'w', encoding='utf-8').write(json.dumps(d))
        return subprocess.call([sys.executable, os.path.abspath(__file__), p],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chk('正例：完整 live receipt → 0', run(GOOD) == 0)
    chk('正例：test receipt 也有效（只证契约）→ 0', run(dict(GOOD, environment='test')) == 0)
    chk("反例①：observedAt='T' → 1（任意字符串冒充不了时间戳——G7.5 曾被它骗）",
        run(dict(GOOD, observedAt='T')) == 1)
    chk('反例②：缺 adapter.name → 1（没有签发方=手填自证）',
        run(dict(GOOD, adapter={})) == 1)
    chk('反例③：rawEvidenceRef 指向不存在的文件 → 1（没有原始证据不算 receipt）',
        run(dict(GOOD, rawEvidenceRef=os.path.join(t, 'nope.json'))) == 1)
    chk('反例④：environment 乱写 → 1（live/test 必须二选一）',
        run(dict(GOOD, environment='prod')) == 1)
    chk('反例⑤：模板占位符没填完 → 1（占位≠签发）',
        run(dict(GOOD, nativeVersion='<revision>')) == 1)
    # ===== 2026-09-11 合入前的对抗探针抓到的三处，全是本仓记录过的教训原样复发 =====
    chk('反例⑦：observedAt=2026-13-45T99:99 → 1（形状合法但**日期不存在**；只测形状＝没测）',
        run(dict(GOOD, observedAt='2026-13-45T99:99')) == 1)
    chk('反例⑧：observedAt=2999-12-31 → 1（观察记录不可能来自**未来**）',
        run(dict(GOOD, observedAt='2999-12-31T00:00')) == 1)
    chk('反例⑨：adapter.name=<adapter-name> → 1（占位符藏在**嵌套字段**里，'
        '判据⑤原话就是「占位≠签发」，而签发方自己填占位符时它看不见）',
        run(dict(GOOD, adapter={'name': '<adapter-name>', 'version': '1'})) == 1)
    chk('反例⑩：半截占位符 nativeVersion="<未填"（没闭合）→ 1'
        '（闭合的交给递归查，半截的递归认不出，两条路都要有人守）',
        run(dict(GOOD, nativeVersion='<未填')) == 1)
    chk('反例⑪：占位符藏在**列表**里 capabilitiesExercised=["<能力>"] → 1',
        run(dict(GOOD, capabilitiesExercised=['<能力>'])) == 1)
    chk('正例：昨天签发的 receipt 仍有效（⛔ 收紧不许误伤正常时间）',
        run(dict(GOOD, observedAt=(__import__('datetime').datetime.now()
                                   - __import__('datetime').timedelta(days=1)
                                   ).strftime('%Y-%m-%dT%H:%M:%S'))) == 0)
    chk('反例⑥：坏 JSON → 1',
        (io.open(os.path.join(t, 'b.json'), 'w', encoding='utf-8').write('{'),
         subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'b.json')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))[1] == 1)
    rc = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(t, 'nope.json')],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', rc == 2)
    print('\n%s' % ('✅ 自证通过：手填一个 T 的时代结束了' if ok else '❌ 自证失败'))
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
