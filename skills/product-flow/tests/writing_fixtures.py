"""Synthetic records for checker tests. NOT real reviews or product evidence."""
import hashlib
import json
from pathlib import Path
from _writing_contract import BEHAVIOR_COLUMNS, BRANCH_TYPES, QUESTIONS, section_exact


def behavior_table(fid='F-01'):
    header = '| ' + ' | '.join(BEHAVIOR_COLUMNS) + ' |\n'
    header += '|' + '|'.join('---' for _ in BEHAVIOR_COLUMNS) + '|\n'
    header += '| %s | normal | 列表关闭 | 点击查看已存在条目 | 列表打开 | 只读，条目数量和值不变 | 展示条目名称 | END:关闭列表返回首页，不改变数据 | FR-001/AC-1 |\n' % fid
    for kind in sorted(BRANCH_TYPES - {'normal'}):
        header += '| %s | %s | N/A:本测试只读本地固定列表，无输入、账号、请求或异步工作 | — | — | — | — | 不生成写入与恢复步骤 | 本测试样本的固定只读范围 |\n' % (fid, kind)
    return header


def text_fixture(fid='F-01'):
    return ('# 测试文档\n| ID | 功能名称 |\n|---|---|\n| %s | 查看列表 |\n'
            '## %s 查看列表\n用户从首页点击查看；展示固定列表，数据不变。关闭返回首页。\n' % (fid, fid)) + behavior_table(fid) + (
                '# 附件 A\n## FR-001 所属 %s\n- AC-1 Given 列表关闭 When 点击查看 Then 显示固定条目，关闭返回首页，数据不变。\n' % fid)


def record_fixture(root, text, fid='F-01', name='report.md'):
    root = Path(root)
    heading = fid + ' 查看列表'
    record = {'authorSession': 'synthetic-author',
              'inputs': {name: hashlib.sha256(text.encode()).hexdigest()},
              'reviews': [], 'findings': []}
    for role, questions in QUESTIONS.items():
        trace = root / (role + '-trace.txt')
        trace.write_text('SYNTHETIC CHECKER FIXTURE, not an actual professional review: ' + role)
        record['reviews'].append({
            'role': role, 'actorType': 'agent', 'reviewer': 'synthetic-' + role,
            'sessionId': 'synthetic-session-' + role, 'reviewedAt': '2026-09-25T10:00:00+08:00',
            'decision': 'APPROVED', 'rationale': 'Synthetic parser fixture only; no real approval.',
            'trace': {'path': trace.name, 'sha256': hashlib.sha256(trace.read_bytes()).hexdigest()},
            'features': [fid], 'sections': ['测试文档', heading, '附件 A', 'FR-001 所属 ' + fid],
            'consumption': [{'feature': fid, 'question': question,
                'answer': '此样本只读已有列表，关闭返回首页，不产生任何写入。',
                'section': heading, 'quote': '用户从首页点击查看；展示固定列表，数据不变。关闭返回首页。',
                'decision': 'PASS'} for question in questions]})
    record['batches'] = [{'id': 'sample-1', 'kind': 'sample', 'status': 'APPROVED',
        'reviewSessions': [item['sessionId'] for item in record['reviews']],
        'units': [{'feature': fid, 'section': heading,
                   'sha256': hashlib.sha256(section_exact(text, heading).encode()).hexdigest()}]}]
    return record


def save_record(path, record):
    Path(path).write_text('```json\n' + json.dumps(record, ensure_ascii=False, indent=2) + '\n```\n')
