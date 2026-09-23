#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9.3 产品经理 GUI 走查与四方验收报告结构门。

判据：
  ① S9.2 同构建 PASS，PRD/Figma/HTML/最终应用四件原物与协作文档回读有锚点；
  ② 产品经理以独立会话从真实 GUI 入口亲自操作，不能复用测试证据冒充；
  ③ 主流程/关键分支/失败恢复/角色权限有真实分母、PM-GUI 行与逐步证据；
  ④ 产品价值、功能规则、信息、交互、视觉、多端、信任、开放探索八维均有结论；
  ⑤ PRD↔应用、HTML↔应用、Figma↔应用分别对账；
  ⑥ 发现、偏差、回流与重新测试规则完整，未批准高影响偏差为 0；
  ⑦ 结论只能 APPROVED/REJECTED/UNABLE，只有 APPROVED 可进 S9.4；
  ⑧ 产品/设计/测试三方批准与协作文档 URL/revision/receipt 非占位。

用法: s9-product-walkthrough-gate.py <S9.3受控源稿.md> [--json] | --self-test
退出码: 0=结构与签核合同齐 1=有缺口 2=跑不了
⚠️ 本门不判断产品经理是否真的操作、体验是否高级或产品决定是否正确；这些必须靠
真实 GUI 证据、原物回读和有授权的产品负责人批准。
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
    required = ('文档控制与入场资格', '走查范围、分母与独立性', '产品经理 GUI 逐流程走查',
                '产品判断与四方一致性', '发现、偏差与回流', '结论、批准与平台回读')
    missing = [name for name in required if not section(md, name)]
    if missing:
        bad.append('① 缺核心章节：%s' % '、'.join(missing))

    control = section(md, '文档控制与入场资格')
    for item in ('S9.2', '协作文档 PRD', 'Figma', 'HTML', '最终应用候选构建'):
        if item not in control:
            bad.append('① 入场缺 %s 原物或版本锚点' % item)
    if not re.search(r'质量结论必须\s*PASS', control) or not re.search(r'(?:commit|构建).*\b[A-Za-z0-9._/-]{2,}', control, re.I | re.S):
        bad.append('① 缺 S9.2 同构建 PASS 硬前置')

    scope = section(md, '走查范围、分母与独立性')
    independence = ('产品经理重新操作当前构建', '不能作为本次已走的证据', '真实浏览器 GUI',
                    '不能代替用户可见步骤')
    if any(x not in scope for x in independence):
        bad.append('② 缺产品经理独立 GUI 会话、真实入口或证据不复用合同')

    walkthrough = section(md, '产品经理 GUI 逐流程走查')
    if not re.search(r'PM-GUI-\d+', scope + walkthrough):
        bad.append('③ 缺真实 PM-GUI 流程行')
    if not re.search(r'亲自实走\s*[`*]*\d+\s*/\s*\d+', scope):
        bad.append('③ 缺走查真实 n/m 分母')
    if any(x not in scope for x in ('主流程', '关键分支', '失败与恢复', '角色/权限')):
        bad.append('③ 缺四类 GUI 覆盖分母')
    if not all(x in walkthrough for x in ('实际 GUI 步骤与逐步反馈', '最终业务状态', '独立证据')):
        bad.append('③ 缺逐步操作、业务终态或独立证据')

    judgment = section(md, '产品判断与四方一致性')
    dimensions = ('用户问题与价值是否真正解决', '功能定义、业务规则与权限是否完整',
                  '信息架构、文案与认知负担', '交互反馈、效率、容错与恢复',
                  '视觉层级、质感与品牌一致性', '多端、无障碍与真实使用情境',
                  '体感性能与信任', '开放探索与产品经验判断')
    missing_dimensions = [x for x in dimensions if x not in judgment]
    if missing_dimensions:
        bad.append('④ 缺产品判断维度：%s' % '、'.join(missing_dimensions))
    for pair in ('PRD↔应用', 'HTML↔应用', 'Figma↔应用'):
        if pair not in judgment:
            bad.append('⑤ 缺独立四方对账：%s' % pair)

    findings = section(md, '发现、偏差与回流')
    if not re.search(r'PM-FIND-\d+', findings) or 'deviation-register.md' not in findings:
        bad.append('⑥ 缺发现行或偏差登记')
    if not all(x in findings for x in ('G7.5', 'S8', 'S9.2', '不得在 S9.3 静默改')):
        bad.append('⑥ 缺产品 delta 回流、冻结失效或新构建重测规则')

    final = section(md, '结论、批准与平台回读')
    if not re.search(r'未批准高影响偏差[^\n|]*\|[^\n|]*\b0\b', final):
        bad.append('⑥ 未批准高影响偏差没有明确为 0')
    if not re.search(r'产品验收结论\s*[：:]\s*(?:APPROVED|REJECTED|UNABLE)', final):
        bad.append('⑦ 缺合法产品验收结论')
    if '只有 `APPROVED` 才可进入 S9.4' not in final or 'CONDITIONAL' not in final:
        bad.append('⑦ 缺 S9.4 放行边界或非法 CONDITIONAL 声明')

    for role in ('产品负责人', '设计负责人', '测试负责人'):
        decisions = {'产品负责人': {'批准'}, '设计负责人': {'四方视觉/交互一致', '批准'},
                     '测试负责人': {'确认同构建 S9.2 PASS 仍有效', '批准'}}
        if not approved_role(final, role, decisions[role]):
            bad.append('⑧ %s 缺非占位批准' % role)
    if not re.search(r'https?://\S+', final) or not re.search(r'revision\s*[:：=]\s*[A-Za-z0-9._-]+', final, re.I) or not re.search(r'receipt\s*[:：=]\s*[A-Za-z0-9._/-]+', final, re.I):
        bad.append('⑧ 缺协作文档 URL、revision 或 receipt 的真实值')
    if not re.search(r'回读结论\s*[：:]\s*(?:READY|PARTIAL|BLOCKED)', final):
        bad.append('⑧ 缺协作文档回读结论')
    return bad


def _entry():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        die('缺少 S9.3 受控源稿路径；用法见 --help')
    if not os.path.isfile(args[0]):
        die('文件不存在：%s' % args[0])
    md = io.open(args[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--context' in sys.argv:
        from _approval import check as check_approval
        bad += check_approval(args[0], sys.argv[sys.argv.index('--context') + 1], 'S9.3')
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ S9.3 八判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门只验报告合同；真实 GUI 体验和产品判断仍须人工实走与批准。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import subprocess
    import tempfile
    root = tempfile.mkdtemp(prefix='s9pm-')
    ok = True

    def run(body):
        path = os.path.join(root, 'walkthrough.md')
        io.open(path, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """# 产品经理 GUI 走查与四方验收报告
## 0. 文档控制与入场资格
产品/版本/构建/commit：App 1.0 build-17 commit abc123。
| 入场依据 | 版本 | 原物 | 结论 |
|---|---|---|---|
| S9.2 协作文档报告 | r9 | 是 | 质量结论必须 PASS；receipt s92.json |
| 冻结协作文档 PRD | r1 | 是 | receipt p.json |
| Figma | v2 | 是 | receipt f.json |
| HTML | h3 | 是 | receipt h.json |
| 最终应用候选构建 | build-17 | 是 | receipt a.json |
## 1. 走查范围、分母与独立性
产品经理重新操作当前构建；测试录像不能作为本次已走的证据。Web 使用真实浏览器 GUI；API/DOM 不能代替用户可见步骤。
| PM-GUI-ID | 来源 | 任务 | 主流程 | 关键分支与失败与恢复 | 状态 |
|---|---|---|---|---|---|
| PM-GUI-001 | FLOW-01/FR-001 | 完成导入 | 登录导入 | 越界后恢复 | RUN |
真实分母：2 条；亲自实走 2/2；主流程 1/1、关键分支 1/1、失败与恢复 1/1、角色/权限 1/1。
## 2. 产品经理 GUI 逐流程走查
| PM-GUI-ID | 构建 | 实际 GUI 步骤与逐步反馈 | 最终业务状态 | 结果 | 独立证据 |
|---|---|---|---|---|---|
| PM-GUI-001 | build-17/web/admin/2026-09-13 | 登录、导入、错误反馈、重试 | 数据已保存 | PASS | pm.mp4 |
## 3. 产品判断与四方一致性
用户问题与价值是否真正解决：PASS。
功能定义、业务规则与权限是否完整：PASS。
信息架构、文案与认知负担：PASS。
交互反馈、效率、容错与恢复：PASS。
视觉层级、质感与品牌一致性：PASS。
多端、无障碍与真实使用情境：PASS。
体感性能与信任：PASS。
开放探索与产品经验判断：PASS。
PRD↔应用、HTML↔应用、Figma↔应用分别 PASS，不能互相顶替。
## 4. 发现、偏差与回流
| ID | 类型 | 证据 | 处置 |
|---|---|---|---|
| PM-FIND-001 | 低机会 | pm.png | 下一版本 |
用户可感知偏差登记 deviation-register.md。产品 delta 回 G7.5；影响方案回 S8；实现变化回 S9.2 重测。不得在 S9.3 静默改原物。
## 5. 结论、批准与平台回读
| 汇总项 | 结果 | 证据 |
|---|---|---|
| 未批准高影响偏差 | 0 | deviations.md |
产品验收结论：APPROVED。只有 `APPROVED` 才可进入 S9.4；CONDITIONAL 不是合法结论。
| 角色 | 结论 | 人/时间 | 证据 | 主体类型 | 授权依据 | 产物版本 | 适用范围 | 审批证据来源 |
|---|---|---|---| --- | --- | --- | --- | --- |
| 产品负责人 | 批准 | 张三/2026-09-13 | p.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
| 设计负责人 | 四方视觉/交互一致 | 李四/2026-09-13 | d.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
| 测试负责人 | 确认同构建 S9.2 PASS 仍有效 | 王五/2026-09-13 | q.json | agent | SYNTHETIC-AUTH-001 | fixture-v1 | synthetic-scope | synthetic-approval.json |
协作文档：https://docs.example.com/product-walkthrough
revision: r3
receipt: receipts/pm.json
回读结论：READY
"""
    chk('正例：八判据全过 → 0', run(good) == 0)
    mutations = [
        ('反例①：S9.2 非 PASS', good.replace('质量结论必须 PASS', '质量结论 CONDITIONAL'), '①'),
        ('反例②：复用测试证据', good.replace('不能作为本次已走的证据', '可作为本次证据'), '②'),
        ('反例③：无真实分母', good.replace('亲自实走 2/2', '走查已完成'), '③'),
        ('反例④：无开放探索', good.replace('开放探索与产品经验判断', '按脚本检查'), '④'),
        ('反例⑤：缺 Figma 对账', good.replace('Figma↔应用', '视觉已看'), '⑤'),
        ('反例⑥：偏差不清零', good.replace('| 未批准高影响偏差 | 0 |', '| 未批准高影响偏差 | 1 |'), '⑥'),
        ('反例⑦：有条件放行', good.replace('产品验收结论：APPROVED', '产品验收结论：CONDITIONAL'), '⑦'),
        ('反例⑧：无产品批准', good.replace('| 产品负责人 | 批准 |', '| 产品负责人 | 待定 |'), '⑧'),
    ]
    for name, body, prefix in mutations:
        findings = check(body)
        chk('%s → 1 且命中本判据' % name,
            run(body) == 1 and any(x.startswith(prefix) for x in findings))
    missing = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'missing.md')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', missing == 2)
    print('\n%s' % ('✅ 自证通过：S9.3 产品走查门会出声' if ok else '❌ 自证失败'))
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
