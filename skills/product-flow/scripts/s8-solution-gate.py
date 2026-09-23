#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S8 技术、算法与测试方案结构门。

判据：
  ① 技术/算法/测试/联合闭环/实施计划/批准六块齐；
  ② 输入原件含 PRD/Figma/HTML 的版本锚点与回读结论；
  ③ 双向追溯表有真实 ID 行；
  ④ 技术方案含可编辑架构图、模块、接口、数据、存储、性能、质量属性、ADR 与恢复；
  ⑤ 算法明确 APPLICABLE 或 N/A，且有非算法基线、数据、评测与退化；
  ⑥ 测试显式覆盖功能、边界异常恢复、接口契约集成、性能容量稳定性、专项测试，
     并分别规划测试工程师 GUI 实走与产品经理 GUI 独立走查；
  ⑦ 三方案联合对账与产品 delta 处置在案；
  ⑧ coding-standards 有版本锚点、STD 适用映射及 selfcheck 边界；
  ⑨ four-node-review 有版本锚点、风险建议档与 S9.2 执行预案；
  ⑩ 研发/算法/测试三方批准及飞书 URL/revision/receipt 非占位；
  ⑪ 实施任务可验收，无“补测试/完善错误处理/按需调整”等空任务。

用法: s8-solution-gate.py <S8受控源稿.md> [--json] | --self-test
退出码: 0=通过 1=有缺口 2=跑不了
⚠️ 验不了什么：技术选择是否正确、算法是否真的有效、测试是否真能挡住生产缺陷、
以及飞书远端内容是否与本地一致；后三者必须由专业评审、真实执行与 doc-sync 回读证明。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _section import section_at


def die(message):
    print('UNABLE: %s' % message, file=sys.stderr)
    sys.exit(2)


def section(md, heading):
    return section_at(md, heading)


def has_h2(md, heading):
    """核心章必须真的是二级标题，不能被文档总标题里的同名词冒充。"""
    return bool(re.search(r'^ {0,3}##[ \t]+(?:\d+\.[ \t]*)?%s(?:[ \t（(].*)?$' %
                          re.escape(heading), md, re.M))


def check(md):
    bad = []
    required = ('技术方案', '算法方案', '测试方案', '三方案联合闭环', '实施计划', '评审、批准与生效')
    missing = [name for name in required if not has_h2(md, name)]
    if missing:
        bad.append('① 缺核心章节：%s' % '、'.join(missing))

    control = section(md, '文档控制与输入冻结') or ''
    for name in ('飞书 PRD', 'Figma', 'HTML'):
        if name not in control:
            bad.append('② 输入冻结缺 %s 原件' % name)
    if not re.search(r'READY|PARTIAL|BLOCKED', control):
        bad.append('② 输入冻结缺 READY/PARTIAL/BLOCKED 结论')

    trace = section(md, '产品合同到方案的双向追溯') or ''
    if not re.search(r'FR-\d+.*(?:AC-\d+|NFR-\d+).*TECH-\d+.*(?:ALG-\d+|N/A-\d+).*TEST-\d+', trace):
        bad.append('③ 追溯表没有 FR/AC/NFR→TECH→ALG/N-A→TEST 的真实 ID 行')

    tech = section(md, '技术方案') or ''
    tech_terms = ('技术架构图与模块边界', '模块接口方案', '数据方案与存储方案', '性能与容量方案',
                  '可靠性、安全与可观测性', '方案选择与 ADR', '发布、迁移与恢复')
    if any(x not in tech for x in tech_terms):
        bad.append('④ 技术方案未闭合架构图/模块/接口/数据存储/性能容量/质量属性/ADR/恢复')
    if not re.search(r'DIAG-TECH-\d+.*(?:C4|Context|Container|Component|部署|数据流)', tech, re.S):
        bad.append('④ 缺带版本锚点的技术架构图与 C4/部署/数据流语义')
    for prefix in ('MOD', 'API', 'DATA', 'STORE', 'PERF'):
        if not re.search(r'\b%s-\d+' % prefix, tech):
            bad.append('④ 技术方案缺真实 %s-ID' % prefix)

    alg = section(md, '算法方案') or ''
    if not re.search(r'APPLICABLE|N/A', alg):
        bad.append('⑤ 算法适用性未明确 APPLICABLE 或 N/A')
    if any(x not in alg for x in ('非算法基线', '数据合同', '候选路线', '部署、监控与退化')):
        bad.append('⑤ 算法方案未闭合基线/数据/评测/部署退化')

    test = section(md, '测试方案') or ''
    test_terms = ('风险模型、范围与策略', '功能测试与业务规则测试', '边界条件、异常与恢复测试',
                  '接口、契约与集成测试', '性能、容量与稳定性测试',
                  '安全、兼容、无障碍与算法测试', '环境、数据与自动化', '测试可信度、准入与退出',
                  'GUI 全流程测试与产品走查准备')
    if any(x not in test for x in test_terms):
        bad.append('⑥ 测试方案未显式闭合功能/边界恢复/接口集成/性能稳定性/专项/环境/证伪准入/GUI 双角色实走')
    if not all(x in test for x in ('测试工程师 GUI 实走', '产品经理 GUI 独立走查', 'S9.2', 'S9.3')):
        bad.append('⑥ 缺 S9.2 测试工程师与 S9.3 产品经理两次独立 GUI 实走合同')

    joint = section(md, '三方案联合闭环') or ''
    if '接口与判据联合对账' not in joint or not re.search(r'delta|回到 G7\.5', joint, re.I):
        bad.append('⑦ 缺三方案联合对账或产品 delta 回流规则')

    if not all(x in control + tech for x in ('coding-standards', 'selfcheck')) or not re.search(r'\bSTD-\d+', tech):
        bad.append('⑧ coding-standards 缺版本锚点、STD 适用映射或 selfcheck 边界')
    if '不证明代码已遵守' not in tech:
        bad.append('⑧ 未声明 selfcheck 只验规范源、不证明项目代码合规')

    plan = section(md, '实施计划') or ''
    if 'four-node-review' not in control + plan or not re.search(r'风险建议档.*[SABC](?:\s*/\s*[SABC])*', plan, re.S) or 'S9.2' not in plan:
        bad.append('⑨ four-node-review 缺版本锚点、S/A/B/C 风险建议档或 S9.2 执行预案')

    approval = section(md, '评审、批准与生效') or ''
    for role in ('研发总监', '算法负责人', '测试负责人'):
        lines = [line for line in approval.splitlines() if role in line and line.strip().startswith('|')]
        if not lines or not any(re.search(r'批准|N/A批准', line) and not re.search(r'<[^>]+>', line) for line in lines):
            bad.append('⑩ %s 没有非占位批准记录' % role)
    if not re.search(r'https?://\S+', approval) or not re.search(r'revision\s*[:：=]\s*[A-Za-z0-9._-]+', approval, re.I) or not re.search(r'receipt\s*[:：=]\s*[A-Za-z0-9._/-]+', approval, re.I):
        bad.append('⑩ 缺飞书 URL、revision 或 receipt 的真实值')

    if re.search(r'补测试|完善错误处理|按需调整|后续优化', plan):
        bad.append('⑪ 实施计划含不可验收的空任务')
    if not re.search(r'VS-\d+.*(?:FR-\d+|AC-\d+|NFR-\d+|ALG-\d+)', plan):
        bad.append('⑪ 实施计划没有带来源 ID 的真实纵向切片')
    return bad


def _entry():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        die('缺少 S8 受控源稿路径；用法见 --help')
    if not os.path.isfile(args[0]):
        die('文件不存在：%s' % args[0])
    md = io.open(args[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ S8 十一判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门只验结构；专业正确性、真实执行与飞书远端一致性须另证。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import subprocess
    import tempfile
    root = tempfile.mkdtemp(prefix='s8g-')
    ok = True

    def run(body):
        path = os.path.join(root, 's8.md')
        io.open(path, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """# S8 技术、算法与测试方案
## 0. 文档控制与输入冻结
| 输入 | 版本 | receipt | 回读 |
|---|---|---|---|
| 飞书 PRD | r1 | p.json | 是 |
| Figma | v2 | f.json | 是 |
| HTML | b3 | h.json | 是 |
| coding-standards | /rules@c1 | std.json | 是 |
| four-node-review | /review@c2 | review.json | 是 |
输入结论：READY
## 1. 决策摘要、范围与追溯
### 1.2 产品合同到方案的双向追溯
| 产品 | 技术 | 算法 | 测试 |
|---|---|---|---|
| FR-001 AC-1 NFR-001 | TECH-001 | ALG-001 | TEST-001 |
## 2. 技术方案
#### 2.1.1 研发规范适用档案
coding-standards /rules@c1；selfcheck: receipts/std.json。selfcheck 只证明规范源在场且自洽，不证明代码已遵守。
| STD-ID | 场景 | 规则 | 落点 | 结论 |
|---|---|---|---|---|
| STD-001 | 接口 | A/K | API-001/TEST-001 | 适用 |
### 2.2 技术架构图与模块边界
| DIAG-ID | 图 | 图源 | 决策 |
|---|---|---|---|
| DIAG-TECH-01 | C4 Context/Container/Component 与部署数据流 | arch.d2@v1 | 边界 |
| MOD-ID | 职责 | 依赖 | 预算 |
|---|---|---|---|
| MOD-001 | 导入 | API-001 | P99 |
### 2.3 模块接口方案
| API-ID | 边界 | 契约 | 约束 |
|---|---|---|---|
| API-001 | MOD-001 到服务 | openapi@v1 | 鉴权错误码超时幂等重试版本 |
### 2.4 数据方案与存储方案
| DATA-ID | 来源 | 生命周期 | 约束 |
|---|---|---|---|
| DATA-001 | 事实源 | 采集到删除 | 隐私留存 |
| STORE-ID | 介质 | 模型 | 演进 |
|---|---|---|---|
| STORE-001 | SQL | schema/index/partition | RPO/RTO/备份恢复 |
### 2.5 性能与容量方案
| PERF-ID | 负载 | 目标 | 验证 |
|---|---|---|---|
| PERF-001 | 100 QPS | P99 200ms | load/stress/soak/scale |
### 2.6 可靠性、安全与可观测性
均有阈值与恢复动作。
### 2.7 方案选择与 ADR
ADR-001 记录替代方案与后果。
### 2.8 发布、迁移与恢复
可演练。
## 3. 算法方案
### 3.1 适用性与非算法基线
APPLICABLE；非算法基线已实测。
### 3.3 数据合同
数据版本、切分与泄漏检查。
### 3.4 候选路线
候选路线与基线同口径评测。
### 3.5 部署、监控与退化
低置信度降级并回滚。
## 4. 测试方案
### 4.1 风险模型、范围与策略
风险优先。
### 4.2 功能测试与业务规则测试
TEST-001 覆盖导入成功。
### 4.3 边界条件、异常与恢复测试
含空值、越界、错误、恢复与并发。
### 4.4 接口、契约与集成测试
覆盖 API-001 的鉴权、错误与兼容。
### 4.5 性能、容量与稳定性测试
PERF-001 覆盖 load/stress/soak/scale。
### 4.6 安全、兼容、无障碍与算法测试
安全与兼容必测，算法按适用性。
### 4.7 环境、数据与自动化
数据脱敏。
### 4.8 测试可信度、准入与退出
RED 为正确原因失败，退出阈值可判定。
### 4.9 GUI 全流程测试与产品走查准备
GUI-001：S9.2 测试工程师 GUI 实走真实入口、主流程、分支、失败与恢复；S9.3 产品经理 GUI 独立走查，只在质量 PASS 后按冻结 PRD 亲自操作，两次证据互不替代。
## 5. 三方案联合闭环
### 5.1 接口与判据联合对账
schema、阈值、降级、回滚已对账。
影响产品合同的 delta 回到 G7.5 批准。
## 6. 实施计划
four-node-review /review@c2；风险建议档：A；S9.2 由测试负责人定档并执行 entry/gates/security/review/qa/bench。
| VS | 结果 | 文件 | 验证 | 来源 |
|---|---|---|---|---|
| VS-01 | 用户可完成导入 | src/a.py | RED/GREEN | FR-001 AC-1 |
## 7. 评审、批准与生效
| 角色 | 结论 | 证据 |
|---|---|---|
| 研发总监 | 批准 | 张三 2026-09-13 |
| 算法负责人 | 批准 | 李四 2026-09-13 |
| 测试负责人 | 批准 | 王五 2026-09-13 |
飞书：https://example.feishu.cn/docx/abc
revision: r17
receipt: receipts/s8.json
"""
    chk('正例：十一判据全过 → 0', run(good) == 0)
    mutations = [
        ('反例①：删测试章节', good.replace('## 4. 测试方案', '## 4. 验证计划', 1), '①'),
        ('反例②：输入结论缺失', good.replace('输入结论：READY', '输入尚未结论'), '②'),
        ('反例③：追溯缺 TEST', good.replace('TEST-001', '待填', 1), '③'),
        ('反例④：技术无接口', good.replace('### 2.3 模块接口方案', '### 2.3 接口说明', 1), '④'),
        ('反例⑤：算法适用性空白', good.replace('APPLICABLE；', '待决定；'), '⑤'),
        ('反例⑥：测试无接口类', good.replace('### 4.4 接口、契约与集成测试', '### 4.4 其他测试', 1), '⑥'),
        ('反例⑦：产品 delta 无回流', good.replace('影响产品合同的 delta 回到 G7.5 批准。', '需求变化在本方案直接决定。'), '⑦'),
        ('反例⑧：无 STD 映射', good.replace('STD-001', 'RULE-001', 1), '⑧'),
        ('反例⑨：无四节点风险档', good.replace('风险建议档：A', '风险建议待定'), '⑨'),
        ('反例⑩：测试批准占位', good.replace('| 测试负责人 | 批准 | 王五 2026-09-13 |', '| 测试负责人 | <结论> | <证据> |'), '⑩'),
        ('反例⑪：空任务', good.replace('用户可完成导入', '完善错误处理'), '⑪'),
    ]
    for name, body, prefix in mutations:
        findings = check(body)
        chk('%s → 1 且命中本判据' % name, run(body) == 1 and any(x.startswith(prefix) for x in findings))
    missing = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'missing.md')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', missing == 2)
    print('\n%s' % ('✅ 自证通过：S8 十一判据门会出声' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def _main_guarded(fn):
    try:
        fn()
    except SystemExit:
        raise
    except Exception as exc:
        import traceback
        print('UNABLE: 门禁自身异常（不是「有发现」）：%s: %s' % (type(exc).__name__, exc), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__ or '')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    _main_guarded(_entry)
