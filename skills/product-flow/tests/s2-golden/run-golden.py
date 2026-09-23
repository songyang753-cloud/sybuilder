#!/usr/bin/env python3
"""S2 集成黄金样本 + 破坏性反例回归(Codex 建议书 §12 / 验收 §17.3)。

治的病:各门各自 self-test 只证「这道门单独会红」,证明不了「一份真报告能同时过所有 S2 门」
(门之间可能自相矛盾),也证明不了「把好报告改坏后,是对的那道门在红」。

本 harness:
  ① 黄金 fixture(report + deep-tree + events + evidence + readback)必须**同时**过
     report-structure(teardown)/ traversal-coverage(events)/ feishu-delivery 三门 —— 证互相可满足。
  ② 每个破坏性变异,必须让**指定的那道门**红(不是随便哪道)。

退出码 0=全部符合预期;1=有不符。⛔ 不允许只断言输出含某字符串:断的是退出码 + 是哪道门红。
"""
import json, io, os, subprocess, sys, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, '..', '..', 'scripts')


def _rs(d):   # report-structure teardown
    return subprocess.run([sys.executable, os.path.join(G, 'report-structure-gate.py'),
                           '--mode', 'teardown', os.path.join(d, 'report.md'),
                           '--atomic-ledger', os.path.join(d, 'ledger.md'),
                           '--events', os.path.join(d, 'traversal-events.json'),
                           '--evidence-manifest', os.path.join(d, 'evidence-manifest.json')],
                          capture_output=True, text=True).returncode


def _tc(d):   # traversal-coverage events
    return subprocess.run([sys.executable, os.path.join(G, 'traversal-coverage-gate.py'),
                           '--deep-tree', os.path.join(d, 'deep-tree.json'),
                           '--report', os.path.join(d, 'report.md'),
                           '--events', os.path.join(d, 'traversal-events.json'),
                           '--evidence-manifest', os.path.join(d, 'evidence-manifest.json')],
                          capture_output=True, text=True).returncode


def _fd(d):   # feishu-delivery
    return subprocess.run([sys.executable, os.path.join(G, 'feishu-delivery-gate.py'),
                           '--source', os.path.join(d, 'report.md'),
                           '--readback', os.path.join(d, 'readback.xml'),
                           '--evidence-manifest', os.path.join(d, 'evidence-manifest.json')],
                          capture_output=True, text=True).returncode


GATES = {'report-structure': _rs, 'traversal-coverage': _tc, 'feishu-delivery': _fd}


def _fresh():
    """把黄金 fixture 拷到临时目录(变异在副本上做,不脏化提交的 fixture)。"""
    d = tempfile.mkdtemp(prefix='s2-golden-')
    for f in ('report.md', 'deep-tree.json', 'traversal-events.json',
              'evidence-manifest.json', 'readback.xml', 'shot.png', 'ledger.md'):
        shutil.copy(os.path.join(HERE, f), os.path.join(d, f))
    return d


def _read(d, f):
    return io.open(os.path.join(d, f), encoding='utf-8').read()


def _write(d, f, s):
    io.open(os.path.join(d, f), 'w', encoding='utf-8').write(s)


def _jset(d, f, obj):
    json.dump(obj, io.open(os.path.join(d, f), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def _jget(d, f):
    return json.load(io.open(os.path.join(d, f), encoding='utf-8'))


# 每个破坏性变异:(名字, 变异函数, 应当红的那道门)
def m_drop_index(d):
    s = _read(d, 'report.md')
    _write(d, 'report.md', s[:s.index('## 最细功能正文索引')])          # 删索引表及其后

def m_drop_state_section(d):
    s = _read(d, 'report.md')
    _write(d, 'report.md', s.replace('## 状态、异常与恢复', '## 无关小节'))  # 删状态/异常/恢复必备段

def m_verified_missing_afterstate(d):
    ev = _jget(d, 'traversal-events.json'); ev['events'][0]['afterState'] = ''   # verified 缺后态
    _jset(d, 'traversal-events.json', ev)

def m_unclassified_control(d):
    dt = _jget(d, 'deep-tree.json'); dt['nodes'][0]['els'].append({'txt': '导出'})  # 多一个控件、无事件
    _jset(d, 'deep-tree.json', dt)

def m_evidence_not_in_body(d):
    ev = _jget(d, 'traversal-events.json'); ev['events'][0]['evidenceId'] = 'SHOT-999'  # 正文未投影
    _jset(d, 'traversal-events.json', ev)

def m_remote_empty_token(d):
    _write(d, 'readback.xml', '<title>单品报告</title><heading>功能A SHOT-001</heading><image token=""/>')  # 本地有图远端零

def m_blocked_as_verified(d):
    # 把一个本应 blocked 的处置谎报成 verified 但缺证据字段 → 结论上限/事件完整性红
    ev = _jget(d, 'traversal-events.json')
    ev['events'][0].update({'classification': 'verified', 'evidenceId': '', 'result': ''})
    _jset(d, 'traversal-events.json', ev)


CASES = [
    ('删最细功能正文索引表(只留模块概述)', m_drop_index, 'report-structure'),
    ('删状态/异常/恢复必备小节',           m_drop_state_section, 'report-structure'),
    ('已验证事件缺操作后状态',             m_verified_missing_afterstate, 'traversal-coverage'),
    ('新增未归类控件(看见没操作)',         m_unclassified_control, 'traversal-coverage'),
    ('证据 ID 未投影进正文',               m_evidence_not_in_body, 'traversal-coverage'),
    ('本地有图但飞书远端图片 token 为空',   m_remote_empty_token, 'feishu-delivery'),
    ('权限阻塞谎报为已验证却缺证据',        m_blocked_as_verified, 'traversal-coverage'),
]


def main():
    fails = []
    # ① 黄金:三门必须同时绿
    d = _fresh()
    try:
        for name, fn in GATES.items():
            rc = fn(d)
            ok = rc == 0
            print('  %s 黄金过 %-18s rc=%d' % ('✅' if ok else '❌', name, rc))
            if not ok:
                fails.append('黄金未过 %s' % name)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ② 每个破坏性变异:指定门必须红(其余门不作要求)
    for cname, mut, target in CASES:
        d = _fresh()
        try:
            mut(d)
            rc = GATES[target](d)
            ok = rc == 1  # UNABLE or a crash is not a successfully caught defect.
            print('  %s 反例〔%s〕→ %s 应红  rc=%d' % ('✅' if ok else '❌', cname, target, rc))
            if not ok:
                fails.append('反例「%s」未能让 %s 变红(rc=%d)' % (cname, target, rc))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    if fails:
        print('\n❌ S2 黄金样本回归失败:')
        for f in fails:
            print('   -', f)
        return 1
    print('\n✅ S2 集成黄金样本回归全过(三门互相可满足 + %d 个破坏性反例各触发对的门)' % len(CASES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
