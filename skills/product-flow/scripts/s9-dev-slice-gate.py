#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S9.1 开发与持续验证：纵向切片交付记录结构门。

把 vibecoding 的「代码实现关进实施切片」落成可执行门禁——补 S9.1 长期只有
selfcheck.sh 兜底、无专属出场门的缺口。判据：
  ① 六章齐：文档控制/纵向切片与合同/RED→GREEN/AI 生成记录/算法离线评测/出场结论；
  ② 入场：S8 联合方案同构建 APPROVED，coding-standards 正本路径与 commit 有锚点；
  ③ 切片按合同先行组织：SLICE 行 + 合同先行原则 + 幂等/回滚闭合 + TECH/STD 锚；
  ④ 每切片有为正确原因失败的 RED 与最小 GREEN，绑当前 commit，diff 每行可追溯 FR；
  ⑤ AI 生成记录区分 AI 直出 / 人复核，并激活 coding-standards K 层；
  ⑥ 算法改动过离线评测集，或显式 N/A + 理由；
  ⑦ 出场结论 READY/PARTIAL/BLOCKED，含「selfcheck≠代码合规」诚实边界与偏离回写；
  ⑧ 完成度分级声明(self_reported/tested/independently-verified)——同进程 selfcheck 最高 self_reported(借 gstack /cso)。
  ⑨ 代码评审结论在场：切片交付前过确定性代码评审(open-code-review/ocr)，结论有真实裁决
     (无阻断/无高危/通过/已处置)；安全维度 semgrep + trailofbits 规则集推荐，不设硬依赖。

用法: s9-dev-slice-gate.py <S9.1受控源稿.md> [--json] | --self-test
退出码: 0=结构与合同齐 1=有缺口 2=跑不了
⚠️ 本门不判断代码写得好不好——质量由 S9.2 终审与 coding-standards 逐条实现证据裁定；
selfcheck 绿只证规范正本在场自洽，不证代码合规。
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


def table_body(sec):
    """只取表格数据行（丢掉表头行与分隔行），防止判据 token 藏在表头/说明里造成假绿。"""
    rows = [l for l in sec.splitlines() if l.lstrip().startswith('|')]
    data = [l for l in rows if not re.match(r'^\s*\|[\s:|-]+\|\s*$', l)]
    return '\n'.join(data[1:]) if len(data) > 1 else ''


def check(md):
    bad = []
    required = ('文档控制与入场资格', '纵向切片与合同锚定', 'RED→GREEN 证据',
                'AI 生成记录', '算法切片离线评测门', '出场结论与偏差回写')
    missing = [name for name in required if not section(md, name)]
    if missing:
        bad.append('① 缺核心章节：%s' % '、'.join(missing))

    control = section(md, '文档控制与入场资格')
    if 'S8' not in control:
        bad.append('② 入场缺 S8 联合方案锚点')
    if not re.search(r'方案结论必须\s*APPROVED', control):
        bad.append('② 缺 S8 同构建 APPROVED 硬前置')
    if 'coding-standards' not in control:
        bad.append('② 缺 coding-standards 正本路径')
    if 'commit' not in control:
        bad.append('② 缺当前构建 commit 锚点')

    slices = section(md, '纵向切片与合同锚定')
    if not re.search(r'SLICE-\d+', slices):
        bad.append('③ 缺纵向切片行（SLICE-N）')
    if '合同先行' not in slices:
        bad.append('③ 缺合同先行原则')
    slice_rows = table_body(slices)
    for kw in ('幂等', '回滚'):
        if kw not in slice_rows:
            bad.append('③ 合同状态缺「%s」闭合（数据行）' % kw)
    if not re.search(r'(?:TECH|STD)-\w', slices):
        bad.append('③ 缺 TECH/STD 追溯锚')

    rg = section(md, 'RED→GREEN 证据')
    if not re.search(r'SLICE-\d+', rg):
        bad.append('④ 缺切片 RED→GREEN 行')
    if 'RED' not in rg or 'GREEN' not in rg:
        bad.append('④ 缺 RED 或 GREEN 证据')
    if 'commit' not in rg:
        bad.append('④ RED/GREEN 未绑 commit')
    if '可追溯' not in rg:
        bad.append('④ 缺 diff 每行可追溯 FR')

    ai = section(md, 'AI 生成记录')
    if 'AI 直出' not in ai or '人复核' not in ai:
        bad.append('⑤ 缺 AI 直出 / 人复核 区分')
    if 'K 层' not in ai:
        bad.append('⑤ 缺 coding-standards K 层激活')

    algo = section(md, '算法切片离线评测门')
    if '评测集' not in algo:
        bad.append('⑥ 缺算法离线评测门')
    if not re.search(r'N/A|回归|通过|无改动', table_body(algo)):
        bad.append('⑥ 算法改动未过评测集也无 N/A 理由（数据行）')

    final = section(md, '出场结论与偏差回写')
    if not re.search(r'开发切片出场结论\s*[：:]\s*(?:READY|PARTIAL|BLOCKED)', final):
        bad.append('⑦ 缺合法开发切片出场结论')
    if 'selfcheck' not in final or '不证代码合规' not in final:
        bad.append('⑦ 缺 selfcheck≠代码合规 的诚实边界')
    if '回写' not in final:
        bad.append('⑦ 缺偏离 S8 的同 commit 回写')
    if not re.search(r'完成度分级[^\n]*(?:self_reported|tested|independently-verified)', final):
        bad.append('⑧ 缺完成度分级声明（self_reported/tested/independently-verified；同进程 selfcheck 最高 self_reported）')

    review = section(md, '代码评审结论')
    if not review:
        bad.append('⑨ 缺「代码评审结论」章节（切片交付前须过确定性代码评审 open-code-review/ocr）')
    else:
        if not re.search(r'ocr|open-code-review', review, re.I):
            bad.append('⑨ 代码评审未锚定确定性评审工具（open-code-review / ocr）')
        if not re.search(r'无阻断|无高危|通过|已处置', table_body(review)):
            bad.append('⑨ 代码评审缺真实裁决（无阻断/无高危/通过/已处置；只扫数据行防假绿）')
    return bad


def _entry():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    if not args:
        die('缺少 S9.1 受控源稿路径；用法见 --help')
    if not os.path.isfile(args[0]):
        die('文件不存在：%s' % args[0])
    md = io.open(args[0], encoding='utf-8', errors='replace').read()
    bad = check(md)
    if '--json' in sys.argv:
        print(json.dumps({'bad': bad}, ensure_ascii=False))
    else:
        for item in bad:
            print('  ❌ ' + item)
        print('✅ S9.1 九判据全过' if not bad else '❌ %d 处缺口' % len(bad))
        print('⚠️ 本门只验切片交付合同；代码质量仍须 S9.2 终审与逐条实现证据。')
    sys.exit(0 if not bad else 1)


def _self_test():
    import subprocess
    import tempfile
    root = tempfile.mkdtemp(prefix='s9dev-')
    ok = True

    def run(body):
        path = os.path.join(root, 'devslice.md')
        io.open(path, 'w', encoding='utf-8').write(body)
        return subprocess.call([sys.executable, os.path.abspath(__file__), path],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def chk(name, value):
        nonlocal ok
        print(('  ✅ ' if value else '  ❌ ') + name)
        ok = ok and value

    good = """# 开发与持续验证：纵向切片交付记录
## 0. 文档控制与入场资格
| 项 | 内容 |
|---|---|
| S8 联合方案 | https://x r3；方案结论必须 APPROVED；receipt s8.json |
| coding-standards 正本 | /path cs commit c1；selfcheck receipt cs.json |
| 当前构建 / commit | build-9 commit abc123 |
| 模式 | Build |
| 研发 / 复核 | 张三 |
## 1. 纵向切片与合同锚定（合同先行）
合同先行：接口/schema/错误/幂等/回滚先闭合再排任务。
| SLICE-ID | 对应 FR/AC | TECH/STD 锚 | 精确文件 | 合同状态 | 状态 |
|---|---|---|---|---|---|
| SLICE-001 | FR-011/AC-1 | TECH-03/STD-07 | src/import.ts:parse | 接口/幂等/回滚已闭合 | DONE |
## 2. RED→GREEN 证据（每切片）
diff 每行可追溯 FR。
| SLICE-ID | RED 证据 | 最小 GREEN | 绑定 commit | 可追溯 FR | 越界 |
|---|---|---|---|---|---|
| SLICE-001 | RED 先红 assert 原因对 | GREEN 通过 | abc123 | 是 | 无 |
## 3. AI 生成记录与协作层（附件 H.4）
| SLICE-ID | AI 直出/人复核 | K 层条款 | 复核人/证据 |
|---|---|---|---|
| SLICE-001 | AI 直出→人复核 | 幻觉API/写完≠验过 | 张三/pr1 |
## 4. 算法切片离线评测门
| 算法改动 | 评测集/指标 | 过门结果 | 或 N/A |
|---|---|---|---|
| 无 | 评测集 recall@10 | — | N/A：本切片无算法改动 |
## 5. 出场结论与偏差回写
| 汇总项 | 结果 | 证据 |
|---|---|---|
| selfcheck receipt | 在案 不证代码合规 | cs.json |
| STD-ID 实现证据 | 齐 | link |
| 偏离 S8 方案 | 无偏离/已同 commit 回写 | link |
| 完成度分级 | self_reported（同进程 selfcheck） | 逐条 STD 证据升 tested 见 link |
开发切片出场结论：READY。selfcheck 绿 ≠ 代码合规。
## 6. 代码评审结论（切片交付前必过）
| 评审维度 | 工具/方式 | 结论 | 处置 |
|---|---|---|---|
| 功能/质量 | open-code-review (ocr) 确定性规则 | 无阻断项 | — |
| 安全 | semgrep + trailofbits 规则集（推荐） | 无高危项 | — |
| 人工复核 | reviewer 张三 | 复核通过 | pr1 |
评审正本：ocr（Apache-2.0，确定性×Agent 混合）；安全维度 semgrep 可选，不阻断 fresh clone。
"""
    chk('正例：九判据全过 → 0', run(good) == 0)
    mutations = [
        ('反例①：缺算法评测章节', good.replace('## 4. 算法切片离线评测门', '## 4. 算法（占位）'), '①'),
        ('反例②：S8 非 APPROVED', good.replace('方案结论必须 APPROVED', '方案结论 CONDITIONAL'), '②'),
        ('反例③：无合同先行', good.replace('合同先行：', '按需：'), '③'),
        ('反例④：无可追溯', good.replace('可追溯', '已看'), '④'),
        ('反例⑤：无 K 层', good.replace('K 层条款', '规范条款'), '⑤'),
        ('反例⑥：算法无评测也无 N/A', good.replace('N/A：本切片无算法改动', '待补'), '⑥'),
        ('反例⑦：无合法出场结论', good.replace('开发切片出场结论：READY', '开发切片出场结论：待定'), '⑦'),
        ('反例⑧：无完成度分级', good.replace('| 完成度分级 | self_reported（同进程 selfcheck） | 逐条 STD 证据升 tested 见 link |\n', ''), '⑧'),
        ('反例⑨：代码评审无真实裁决', good.replace('无阻断项', '待补').replace('无高危项', '待补').replace('复核通过', '复核待定'), '⑨'),
    ]
    for name, body, prefix in mutations:
        findings = check(body)
        chk('%s → 1 且命中本判据' % name,
            run(body) == 1 and any(x.startswith(prefix) for x in findings))
    missing = subprocess.call([sys.executable, os.path.abspath(__file__), os.path.join(root, 'missing.md')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chk('无效输入 → 2', missing == 2)
    print('\n%s' % ('✅ 自证通过：S9.1 开发切片门会出声' if ok else '❌ 自证失败'))
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
