#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9.2 工程测试与 four-node-review 终审报告结构门。

判据：
  ① 版本对象、S8/coding-standards/four-node-review 与飞书回读均有锚点；
  ② 人工风险档、覆盖合同真实分母和 Entry 证据齐；
  ③ 七类测试显式执行，测试工程师从真实 GUI 入口完整实走，SKIPPED/UNABLE 不得静默；
  ④ coding-standards 有 STD 逐项证据，selfcheck 边界写明；
  ⑤ four-node 各节点按包覆盖，有轮次、三态与独立新证据；
  ⑥ finding 有修复、预期原因证伪与复验；
  ⑦ 需求/代码/变异覆盖分报，最终 fresh 回归在案；
  ⑧ 风险档与 Open Item 放行规则未被降级；
  ⑨ 工程结论不冒充 S9.3 四方产品验收，三专业批准及飞书 receipt 齐。

用法: s9-quality-report-gate.py <S9.2受控源稿.md> [--json] | --self-test
退出码: 0=通过 1=有缺口 2=跑不了
⚠️ 本门只验报告结构和显式证据指针；测试是否真实、发现是否正确、质量是否足以放行，
仍须由真实运行、独立复验和有授权的人批准。
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
    return section_at(md, heading) or ''


def check(md):
    bad = []
    required = ('文档控制、对象与依据', '风险定档、覆盖合同与入场门', '显式测试执行结果',
                '`coding-standards` 执行与偏离', '`four-node-review` 终审执行',
                '最终回归、缺口与质量结论', '批准、写入与回读')
    missing = [x for x in required if not section(md, x)]
    if missing:
        bad.append('① 缺核心章节：%s' % '、'.join(missing))

    control = section(md, '文档控制、对象与依据')
    for name in ('S8', 'coding-standards', 'four-node-review'):
        if name not in control:
            bad.append('① 缺 %s 的版本锚点' % name)
    if not re.search(r'(?:commit|revision|hash).*\b[A-Za-z0-9._/-]{2,}', control, re.I | re.S):
        bad.append('① 缺可复现版本/构建锚点')
    if not re.search(r'https?://\S+', md) or not re.search(r'receipt\s*[:：=]\s*[A-Za-z0-9._/-]+', md, re.I):
        bad.append('① 缺飞书 URL 或真实 receipt')

    entry = section(md, '风险定档、覆盖合同与入场门')
    if not re.search(r'最终风险档\s*[：:]\s*[SABC]\b', entry):
        bad.append('② 缺人工最终风险档 S/A/B/C')
    if not re.search(r'PKG-\d+', entry) or not re.search(r'覆盖\s*[`*]*\d+\s*/\s*\d+', entry):
        bad.append('② 缺覆盖包或真实 n/m 分母')
    if 'Entry' not in entry or not re.search(r'PASS|FAIL|UNABLE', entry):
        bad.append('② 缺 Entry 三态证据')

    tests = section(md, '显式测试执行结果')
    test_domains = ('功能与业务规则', '边界、异常、并发与恢复', '接口、契约与集成',
                    '性能、容量与稳定性', '安全与隐私', '兼容、无障碍与交互工程质量',
                    '算法评测与退化')
    missing_domains = [x for x in test_domains if x not in tests]
    if missing_domains:
        bad.append('③ 缺测试域：%s' % '、'.join(missing_domains))
    if 'SKIPPED/UNABLE' not in tests or not all(x in tests for x in ('原因', '影响', 'owner', '解除条件')):
        bad.append('③ SKIPPED/UNABLE 缺四字段处置规则')
    gui_terms = ('测试工程师 GUI 全流程实走', '真实入口', '主流程', '关键分支', '失败与恢复',
                 '构建', '环境', '角色', '时间', '不能替代 GUI')
    if not re.search(r'GUI-S92-\d+', tests) or any(x not in tests for x in gui_terms):
        bad.append('③ 缺测试工程师 GUI 全流程实走、四类覆盖或当前构建逐步证据合同')
    if not re.search(r'GUI\s*结论\s*[：:]\s*(?:PASS|FAIL|UNABLE)', tests):
        bad.append('③ 缺 GUI PASS/FAIL/UNABLE 独立结论')

    standards = section(md, '`coding-standards` 执行与偏离')
    if not re.search(r'STD-\d+', standards) or '如何证明遵守' not in standards:
        bad.append('④ 缺 STD 逐项遵守证据')
    if 'selfcheck' not in md or '不证明本次代码已遵守' not in md:
        bad.append('④ 未写明 selfcheck 的能力边界')

    review = section(md, '`four-node-review` 终审执行')
    for node in ('entry', 'gates', 'security', 'review', 'qa', 'bench'):
        if not re.search(r'^\|\s*%s\s*\|' % node, review, re.M):
            bad.append('⑤ four-node 缺节点：%s' % node)
    if not all(x in review for x in ('覆盖包 n/m', '独立新证据', 'CLEAN/DIRTY/UNABLE')):
        bad.append('⑤ 节点缺轮次/覆盖/三态/独立新证据合同')

    if not re.search(r'FIND-\d+.*(?:commit|N/A).*预期.*(?:CLEAN|DIRTY|UNABLE)', review, re.S):
        bad.append('⑥ finding 缺修复、预期原因证伪或复验')
    if not re.search(r'precision\s*=\s*\d+\s*/\s*\d+', review, re.I):
        bad.append('⑥ 缺候选发现精度 N/C')

    final = section(md, '最终回归、缺口与质量结论')
    if not all(x in final for x in ('需求覆盖', '代码行/分支/变异覆盖', '全量回归与构建')):
        bad.append('⑦ 缺分离覆盖报告或全量 fresh 回归')
    if not re.search(r'质量结论\s*[：:]\s*(?:PASS|CONDITIONAL|FAIL|UNABLE)', final):
        bad.append('⑦ 缺合法质量结论')
    if 'S 档：不得有 Open Item' not in final or 'UNABLE' not in final or '永不等于 PASS' not in final:
        bad.append('⑧ 风险档/Open Item/UNABLE 放行规则不完整')

    approval = section(md, '批准、写入与回读')
    for role in ('测试负责人', '研发负责人', '算法负责人'):
        if not re.search(r'^\|[^\n]*%s[^\n]*\|[^\n]*(?:批准|已知悉|N-A批准)[^\n]*\|' % role,
                         approval, re.M):
            bad.append('⑨ %s 缺非占位批准' % role)
    if '不得声称 PRD/Figma/HTML/最终应用已一致' not in final:
        bad.append('⑨ 缺 S9.2 不替代 S9.3 的声明边界')
    if not re.search(r'回读结论\s*[：:]\s*(?:READY|PARTIAL|BLOCKED)', approval):
        bad.append('⑨ 缺飞书回读结论')
    return bad


def _entry():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        die('缺少 S9.2 受控源稿路径；用法见 --help')
    if not os.path.isfile(args[0]):
        die('文件不存在：%s' % args[0])
    md = io.open(args[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ S9.2 九判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门只验报告合同；真实质量仍须运行与有授权的人批准。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import subprocess
    import tempfile
    root = tempfile.mkdtemp(prefix='s9q-')
    ok = True

    def run(body):
        path = os.path.join(root, 'report.md')
        io.open(path, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """# 工程测试与四节点终审报告
## 0. 文档控制、对象与依据
commit abc123；revision r9；hash h8。S8 / coding-standards / four-node-review 均锚定。
coding-standards 的 selfcheck 只证明规范源在场且自洽，不证明本次代码已遵守。
飞书：https://example.feishu.cn/docx/q
receipt: receipts/q.json
## 1. 风险定档、覆盖合同与入场门
最终风险档：A；决策人：张三；理由：接口迁移。
| 包 | 文件 | 来源 | 风险 | 状态 |
|---|---|---|---|---|
| PKG-001 | src/a.py | FR-001/API-001 | 接口 | RUN |
真实分母：共 1 包；覆盖 1/1；来自 git diff。
### 1.3 入场门（Entry）
版本一致 PASS；RED/GREEN PASS；环境 PASS，证据 receipts/e.json。
## 2. 显式测试执行结果
| 测试域 | ID | 范围 | 结果 | 证据/失败原因 |
|---|---|---|---|---|
| 功能与业务规则 | TEST-001 | 正向 | PASS | f.json |
| 边界、异常、并发与恢复 | TEST-002 | 越界恢复 | PASS | b.json |
| 接口、契约与集成 | API-001 | schema/授权 | PASS | a.json |
| 性能、容量与稳定性 | PERF-001 | load/soak | PASS | p.json |
| 安全与隐私 | SEC-001 | 扫描+人工 | PASS | s.json |
| 兼容、无障碍与交互工程质量 | TEST-006 | 键盘读屏 | PASS | c.json |
| 算法评测与退化 | N/A-001 | 不适用 | PASS | n.json |
SKIPPED/UNABLE 必须写原因、影响、owner、解除条件。
### 2.1 测试工程师 GUI 全流程实走
从真实入口操作当前构建；主流程、关键分支、失败与恢复、角色权限全部覆盖。API/DOM 只能辅助定位，不能替代 GUI。证据绑定构建、环境、角色、时间。
| GUI-ID | 来源 | 操作 | 结果 | 证据 |
|---|---|---|---|---|
| GUI-S92-001 | FLOW-01/FR-001 | 登录、导入、失败后恢复 | PASS | gui.mp4 |
GUI 结论：PASS。
## 3. `coding-standards` 执行与偏离
| STD-ID | 范围 | 如何证明遵守 | 结论 | 豁免 |
|---|---|---|---|---|
| STD-001 | src/a.py | 测试与人工复核 | PASS | N/A |
## 4. `four-node-review` 终审执行
| 节点 | 轮次 | 覆盖包 n/m | 已用镜头/本轮新增镜头 | 结论 | 独立新证据 |
|---|---:|---:|---|---|---|
| entry | 1 | 1/1 | 入口 | CLEAN | e.json |
| gates | 2 | 1/1 | 变异 | CLEAN | g.json |
| security | 2 | 1/1 | 权限 | CLEAN | s.json |
| review | 2 | 1/1 | 并发 | CLEAN | r.json |
| qa | 2 | 1/1 | 边界 | CLEAN | q.json |
| bench | 1 | 1/1 | 性能 | CLEAN | b.json |
CLEAN/DIRTY/UNABLE；每轮有独立新证据。
| Finding | 节点 | 严重度 | 证据 | 根因 | 修复 commit | 反例预期原因 | 复验 |
|---|---|---|---|---|---|---|---|
| FIND-001 | qa | HIGH | q1 | 边界 | commit def456 | 预期断言变红 | CLEAN |
precision=1/1。
## 5. 最终回归、缺口与质量结论
需求覆盖 1/1；代码行/分支/变异覆盖分别 90/85/70；全量回归与构建 fresh PASS。
质量结论：PASS。
S 档：不得有 Open Item；UNABLE 永不等于 PASS。
移交 S9.3 仅说明工程质量，不得声称 PRD/Figma/HTML/最终应用已一致。
## 6. 批准、写入与回读
| 角色 | 结论 | 人/时间 | 证据 |
|---|---|---|---|
| 测试负责人 | 批准 | 王五 | t.json |
| 研发负责人 | 已知悉并接受修复 | 张三 | d.json |
| 算法负责人/N-A复核人 | N-A批准 | 李四 | a.json |
回读结论：READY
"""
    chk('正例：九判据全过 → 0', run(good) == 0)
    mutations = [
        ('反例①：无 four-node 锚点', good.replace('four-node-review 均锚定', '终审规范待定'), '①'),
        ('反例②：无风险档', good.replace('最终风险档：A', '风险待定'), '②'),
        ('反例③：缺接口测试域', good.replace('接口、契约与集成', '其他测试', 1), '③'),
        ('反例③b：缺 GUI 实走', good.replace('GUI-S92-001', 'GUI-TODO'), '③'),
        ('反例④：无 STD', good.replace('STD-001', 'RULE-001'), '④'),
        ('反例⑤：缺 security 节点', good.replace('| security |', '| threat |'), '⑤'),
        ('反例⑥：无精度', good.replace('precision=1/1。', '候选均已看过。'), '⑥'),
        ('反例⑦：无 fresh 回归', good.replace('全量回归与构建 fresh PASS', '局部回归通过'), '⑦'),
        ('反例⑧：UNABLE 可过', good.replace('UNABLE 永不等于 PASS', 'UNABLE 可酌情通过'), '⑧'),
        ('反例⑨：冒充产品验收', good.replace('不得声称 PRD/Figma/HTML/最终应用已一致', '已经证明四方一致'), '⑨'),
    ]
    for name, body, prefix in mutations:
        findings = check(body)
        chk('%s → 1 且命中本判据' % name,
            run(body) == 1 and any(x.startswith(prefix) for x in findings))
    missing = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'missing.md')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', missing == 2)
    print('\n%s' % ('✅ 自证通过：S9.2 终审门会出声' if ok else '❌ 自证失败'))
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
