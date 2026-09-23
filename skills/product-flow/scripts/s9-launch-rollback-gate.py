#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9.4 灰度、正式上线与回滚记录结构门。

判据：
  ① 五章齐：文档控制/灰度梯度/监测口径/回滚方案/上线记录与回读；
  ② 入场：S9.3 产品验收同构建 APPROVED 是硬前置，S9.2 PASS 与上线候选构建有锚点；
  ③ 灰度按放量梯度分档，每档有观察时长、进入条件、停止线，且放量是只允许升档的单向门；
  ④ 监测有 SLI 指标行、SLO 阈值、观察窗与不可伪造的数据源（不是「看着正常」）；
  ⑤ 回滚有触发条件、步骤、RTO 与**演练证据**——未演练即 UNABLE，不得声称可回滚；
  ⑥ 未消除的停止线命中为 0，灰度上线结论只能 PASS/HOLD/ROLLED-BACK；
  ⑦ 研发总监上线批准与测试/产品的仍有效确认非占位；
  ⑧ 协作文档 URL/revision/receipt 与回读结论非占位；
  ⑨ 灰度/监测/演练证据绑定被部署 build 指纹，换构建即作废重跑(借 gstack Review Freshness 的上线态形态)。

用法: s9-launch-rollback-gate.py <S9.4受控源稿.md> [--json] | --self-test
退出码: 0=结构与签核合同齐 1=有缺口 2=跑不了
⚠️ 本门不判断放量是否安全、监测是否真的接上、回滚是否真的能成——这些必须靠真实
灰度数据、可复核的监测数据源、演练证据和有授权的研发总监批准。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at, approved_role


def die(message):
    print('UNABLE: %s' % message, file=sys.stderr)
    sys.exit(2)


def section(md, heading):
    return section_at(md, heading) or ''


def check(md):
    bad = []
    required = ('文档控制与入场资格', '灰度计划与放量梯度', '监测与告警口径',
                '回滚方案与演练', '上线记录、结论与平台回读')
    missing = [name for name in required if not section(md, name)]
    if missing:
        bad.append('① 缺核心章节：%s' % '、'.join(missing))

    control = section(md, '文档控制与入场资格')
    for item in ('S9.3', 'S9.2', '最终上线候选构建'):
        if item not in control:
            bad.append('② 入场缺 %s 原物或版本锚点' % item)
    if not re.search(r'产品验收结论必须\s*APPROVED', control):
        bad.append('② 缺 S9.3 同构建 APPROVED 硬前置')

    gray = section(md, '灰度计划与放量梯度')
    if not re.search(r'G-CANARY-\d+', gray):
        bad.append('③ 缺灰度放量梯度档（G-CANARY-N）')
    for col in ('观察时长', '进入本档的条件', '停止线'):
        if col not in gray:
            bad.append('③ 灰度表缺「%s」列' % col)
    if '只允许升档' not in gray:
        bad.append('③ 缺放量单向门（只允许升档）')

    monitor = section(md, '监测与告警口径')
    if not re.search(r'SLI-\d+', monitor):
        bad.append('④ 缺 SLI 监测指标行')
    for col in ('阈值', '观察窗', '数据源'):
        if col not in monitor:
            bad.append('④ 监测缺「%s」' % col)

    rollback = section(md, '回滚方案与演练')
    for item in ('回滚触发条件', '回滚步骤', 'RTO', '回滚演练证据'):
        if item not in rollback:
            bad.append('⑤ 回滚缺「%s」' % item)
    if '未演练' not in rollback:
        bad.append('⑤ 缺「未演练即 UNABLE」的演练强制')

    final = section(md, '上线记录、结论与平台回读')
    if not re.search(r'未消除的停止线命中[^\n|]*\|[^\n|]*\b0\b', final):
        bad.append('⑥ 未消除停止线命中没有明确为 0')
    if not re.search(r'灰度上线结论\s*[：:]\s*(?:PASS|HOLD|ROLLED-BACK)', final):
        bad.append('⑥ 缺合法灰度上线结论（PASS/HOLD/ROLLED-BACK）')

    for role in ('研发总监', '测试负责人', '产品负责人'):
        decisions = {'研发总监': {'批准上线', '批准回滚'},
                     '测试负责人': {'确认同构建 S9.2 PASS 仍有效'},
                     '产品负责人': {'确认 S9.3 APPROVED 仍有效'}}
        if not approved_role(final, role, decisions[role]):
            bad.append('⑦ %s 缺非占位批准' % role)

    if not re.search(r'https?://\S+', final) or not re.search(r'revision\s*[:：=]\s*[A-Za-z0-9._-]+', final, re.I) or not re.search(r'receipt\s*[:：=]\s*[A-Za-z0-9._/-]+', final, re.I):
        bad.append('⑧ 缺协作文档 URL、revision 或 receipt 的真实值')
    if not re.search(r'回读结论\s*[：:]\s*(?:READY|PARTIAL|BLOCKED)', final):
        bad.append('⑧ 缺协作文档回读结论')
    if '证据构建绑定' not in final or '换构建' not in final:
        bad.append('⑨ 缺灰度/监测/演练证据的 build 指纹绑定与「换构建作废」声明（借 M1 新鲜度）')
    return bad


def _entry():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        die('缺少 S9.4 受控源稿路径；用法见 --help')
    if not os.path.isfile(args[0]):
        die('文件不存在：%s' % args[0])
    md = io.open(args[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--context' in sys.argv:
        from _approval import check as check_approval
        bad += check_approval(args[0], sys.argv[sys.argv.index('--context') + 1], 'S9.4')
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ S9.4 九判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门只验上线合同；放量安全、监测接线与回滚可行仍须真实数据、演练与研发总监批准。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import subprocess
    import tempfile
    root = tempfile.mkdtemp(prefix='s9launch-')
    ok = True

    def run(body):
        path = os.path.join(root, 'launch.md')
        io.open(path, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """# 灰度、正式上线与回滚记录
## 0. 文档控制与入场资格
产品/版本/构建/commit：App 1.0 build-20 commit def456。
| 入场依据 | 版本 | 原物 | 结论 |
|---|---|---|---|
| S9.3 协作文档报告 | r9 | 是 | 产品验收结论必须 APPROVED；receipt s93.json |
| S9.2 同构建 | r8 | 是 | PASS；receipt s92.json |
| 最终上线候选构建 | build-20 commit def456 | 是 | receipt build.json |
## 1. 灰度计划与放量梯度
| 灰度档 | 放量比例 | 观察时长 | 进入本档的条件 | 停止线 | 状态 |
|---|---|---|---|---|---|
| G-CANARY-1 | 1% | ≥2 小时 | 关键 SLI 达标 | 错误率>1% | RUN |
放量单向门：只允许升档；命中停止线只暂停或回滚。
## 2. 监测与告警口径（SLI/SLO）
每个指标绑真实数据源。
| SLI-ID | 指标 | SLO 阈值 | 观察窗 | 数据源 | 告警 | 实测 |
|---|---|---|---|---|---|---|
| SLI-001 | 错误率 | 1% | 5min | 监控看板 grafana/x | oncall | 0.2% |
## 3. 回滚方案与演练
| 项 | 内容 |
|---|---|
| 回滚触发条件 | 命中任一停止线 |
| 回滚步骤 | 关灰度开关→切回 build-19 |
| RTO | 5 分钟 |
| 回滚演练证据 | 2026-09-17 预发演练通过 receipt drill.json；未演练即 UNABLE |
## 4. 上线记录、结论与平台回读
| 汇总项 | 结果 | 证据 |
|---|---|---|
| 未消除的停止线命中 | 0 | dash.png |
| 回滚演练 | 已演练 | drill.json |
| 证据构建绑定 | 灰度/监测/演练证据均绑定 build-20/def456；换构建即作废重跑 | dash.png |
灰度上线结论：PASS。只有 `PASS` 才算完成上线。
| 角色 | 结论 | 人/时间 | 证据 | 主体类型 | 授权依据 | 产物版本 | 适用范围 | 审批证据来源 |
|---|---|---|---| --- | --- | --- | --- | --- |
| 研发总监 | 批准上线 | 张三/2026-09-18 | r.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
| 测试负责人 | 确认同构建 S9.2 PASS 仍有效 | 王五/2026-09-18 | q.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
| 产品负责人 | 确认 S9.3 APPROVED 仍有效 | 李四/2026-09-18 | p.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
协作文档：https://docs.example.com/launch
revision: r5
receipt: receipts/launch.json
回读结论：READY
"""
    chk('正例：九判据全过 → 0', run(good) == 0)
    mutations = [
        ('反例①：缺回滚章节', good.replace('## 3. 回滚方案与演练', '## 3. 回滚（占位）'), '①'),
        ('反例②：S9.3 非 APPROVED', good.replace('产品验收结论必须 APPROVED', '产品验收结论 CONDITIONAL'), '②'),
        ('反例③：无单向门', good.replace('只允许升档', '按需放量'), '③'),
        ('反例④：监测无数据源', good.replace('数据源', '来源'), '④'),
        ('反例⑤：回滚未演练', good.replace('未演练即 UNABLE', '默认可回滚'), '⑤'),
        ('反例⑥：停止线不清零', good.replace('| 未消除的停止线命中 | 0 |', '| 未消除的停止线命中 | 2 |'), '⑥'),
        ('反例⑦：无研发总监批准', good.replace('| 研发总监 | 批准上线 |', '| 研发总监 | 待定 |'), '⑦'),
        ('反例⑧：无回读结论', good.replace('回读结论：READY', '回读结论：待写'), '⑧'),
        ('反例⑨：证据未绑构建', good.replace('| 证据构建绑定 | 灰度/监测/演练证据均绑定 build-20/def456；换构建即作废重跑 | dash.png |\n', ''), '⑨'),
    ]
    for name, body, prefix in mutations:
        findings = check(body)
        chk('%s → 1 且命中本判据' % name,
            run(body) == 1 and any(x.startswith(prefix) for x in findings))
    missing = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'missing.md')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', missing == 2)
    print('\n%s' % ('✅ 自证通过：S9.4 灰度上线回滚门会出声' if ok else '❌ 自证失败'))
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
