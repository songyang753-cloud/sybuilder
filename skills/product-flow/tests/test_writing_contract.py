"""Positive/negative contract tests, including actual CLI verdicts."""
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from _writing_contract import behavior_issues, consumer_issues, scope_issues
from writing_fixtures import text_fixture, record_fixture, save_record


class WritingContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.text = text_fixture()
        self.record = record_fixture(self.root, self.text)

    def consumer(self, record=None, text=None):
        return consumer_issues(text or self.text, record or self.record, {'F-01'}, self.root)

    def test_readonly_na_is_valid(self):
        self.assertEqual(behavior_issues(self.text, {'F-01'}), [])
        self.assertEqual(self.consumer(), [])

    def test_missing_function_has_no_coverage(self):
        self.assertTrue(any('F-02' in i for i in behavior_issues(self.text, {'F-01', 'F-02'})))
        # A table in another chapter must not fill an empty authoritative E.
        misplaced = self.text.replace('# 附件 E', '# 附件 Z')
        self.assertTrue(any('behavior-coverage' in i for i in behavior_issues(misplaced, {'F-01'})))

    def test_cycle_without_exit_is_not_closed(self):
        text = self.text.replace('END:关闭列表返回首页，不改变数据', 'F-01#normal')
        self.assertTrue(any('behavior-no-exit' in i for i in behavior_issues(text, {'F-01'})))

    def test_managed_wait_is_a_valid_exit(self):
        text = self.text.replace('END:关闭列表返回首页，不改变数据', 'WAIT:保留列表；可关闭返回首页')
        self.assertEqual(behavior_issues(text, {'F-01'}), [])

    def test_chinese_colons_are_not_missing_behavior(self):
        text = self.text.replace('N/A:', 'N/A：').replace('END:', 'END：')
        self.assertEqual(behavior_issues(text, {'F-01'}), [])
        unknown = text.replace('N/A：', 'UNKNOWN：')
        self.assertEqual(behavior_issues(unknown, {'F-01'}, research=True), [])
        self.assertTrue(behavior_issues(unknown, {'F-01'}))
        wait = text.replace('END：', 'WAIT：')
        self.assertEqual(behavior_issues(wait, {'F-01'}), [])

    def test_missing_acceptance_reference_is_rejected(self):
        text = self.text.replace('FR-001/AC-1', 'FR-001/AC-99')
        self.assertTrue(any('behavior-acceptance' in i for i in behavior_issues(text, {'F-01'})))

    def test_acceptance_of_another_function_cannot_be_borrowed(self):
        text = self.text.replace('FR-001 所属 F-01', 'FR-001 所属 F-02')
        self.assertTrue(any('behavior-acceptance' in i for i in behavior_issues(text, {'F-01'})))

    def test_citation_of_summary_is_not_leaf_consumption(self):
        self.record['reviews'][0]['consumption'][0]['section'] = '测试文档'
        self.assertTrue(any('consumer-evidence' in i for i in self.consumer()))

    def test_scope_approved_split(self):
        scope = '| ID | 功能名称 |\n|---|---|\n| F-01 | 管理 |\n'
        scope += '\n| 原功能 | 目标功能 | 处置 | 理由 | 批准依据 | 状态 |\n|---|---|---|---|---|---|\n| F-01 | F-02 F-03 | 拆分 | 创建删除结果不同 | DEC-01 范围批准 | APPROVED |\n'
        target = '| ID | 功能名称 |\n|---|---|\n| F-02 | 创建 |\n| F-03 | 删除 |\n'
        self.assertEqual(scope_issues(scope, target), [])

    def test_scope_unapproved_split(self):
        scope = '| ID | 功能名称 |\n|---|---|\n| F-01 | 管理 |\n'
        scope += '\n| 原功能 | 目标功能 | 处置 | 理由 | 批准依据 | 状态 |\n|---|---|---|---|---|---|\n| F-01 | F-02 F-03 | 拆分 | 创建删除结果不同 | TBD | APPROVED |\n'
        target = '| ID | 功能名称 |\n|---|---|\n| F-02 | 创建 |\n| F-03 | 删除 |\n'
        self.assertTrue(any('scope-decision' in i for i in scope_issues(scope, target)))
        pending = scope.replace('TBD', '等待产品负责人批准').replace('APPROVED', 'UNREVIEWED')
        self.assertTrue(any('scope-decision' in i for i in scope_issues(pending, target)))

    def test_filler_cannot_replace_data_rule(self):
        text = self.text.replace('只读，条目数量和值不变', '执行操作')
        self.assertTrue(any('behavior-content' in i for i in behavior_issues(text, {'F-01'})))

    def test_unresolved_exit(self):
        text = self.text.replace('END:关闭列表返回首页，不改变数据', '支持恢复')
        self.assertTrue(any('behavior-exit' in i for i in behavior_issues(text, {'F-01'})))

    def test_cross_feature_link_must_exist(self):
        text = self.text.replace('END:关闭列表返回首页，不改变数据', 'F-02#normal')
        self.assertTrue(any('behavior-dangling' in i for i in behavior_issues(text, {'F-01'})))
        # A separate reachable END must not hide a link to a nonexistent action.
        inactive = self.text.replace('END:关闭列表返回首页，不改变数据', 'END:可关闭；或 F-01#permission')
        self.assertTrue(any('behavior-inactive-target' in i for i in behavior_issues(inactive, {'F-01'})))

    def test_missing_branch_type(self):
        text = '\n'.join(x for x in self.text.splitlines() if '| interruption |' not in x)
        self.assertTrue(any('interruption' in i for i in behavior_issues(text, {'F-01'})))

    def test_normal_cannot_be_na(self):
        text = self.text.replace('| 列表关闭 |', '| N/A:不想测试 |')
        self.assertTrue(any('behavior-disposition' in i for i in behavior_issues(text, {'F-01'})))

    def test_unknown_research_not_invented_as_product_rule(self):
        text = self.text.replace('N/A:本测试只读', 'UNKNOWN:无权限验证，本测试只读')
        self.assertFalse(behavior_issues(text, {'F-01'}, research=True))
        self.assertTrue(behavior_issues(text, {'F-01'}))

    def test_reviewer_is_not_writer(self):
        self.record['reviews'][0]['sessionId'] = self.record['authorSession']
        self.assertTrue(any('consumer-independent' in i for i in self.consumer()))

    def test_empty_answers_do_not_mean_reviewed(self):
        for answer in ('符合要求', '内容完整。', '完整', '检查通过', '未发现问题', '按需处理'):
            self.record['reviews'][0]['consumption'][0]['answer'] = answer
            self.assertTrue(any('consumer-evidence' in i for i in self.consumer()), answer)
        self.record['reviews'][0]['consumption'] = []
        self.assertTrue(any('consumer-coverage' in i for i in self.consumer()))

    def test_fabricated_citation_rejected(self):
        self.record['reviews'][0]['consumption'][0]['quote'] = '不存在的权限与恢复规则'
        self.assertTrue(any('consumer-evidence' in i for i in self.consumer()))

    def test_body_compression_invalidates_accepted_batch(self):
        text = self.text.replace('数据不变。', '完成任务。')
        self.assertTrue(any('batch-stale' in i for i in self.consumer(text=text)))

    def test_changed_trace_is_rejected(self):
        (self.root / 'product-trace.txt').write_text('changed')
        self.assertTrue(any('consumer-trace-stale' in i for i in self.consumer()))

    def test_trace_path_cannot_escape_package(self):
        self.record['reviews'][0]['trace']['path'] = '../outside.txt'
        with self.assertRaisesRegex(ValueError, 'consumer-trace'):
            self.consumer()

    def test_scope_missing_feature(self):
        scope = self.text.replace('| F-01 | 查看列表 |', '| F-01 | 查看列表 |\n| F-02 | 导出 |')
        self.assertEqual(scope_issues(scope, self.text), ['scope-missing: F-02'])

    def test_explicit_removal_in_upstream(self):
        scope = self.text.replace('| F-01 | 查看列表 |', '| F-01 | 查看列表 |\n| F-02 | 导出 |')
        scope += '\n| 原功能 | 目标功能 | 处置 | 理由 | 批准依据 | 状态 |\n|---|---|---|---|---|---|\n| F-02 | — | 删除 | 首版仅查看，不对外导出 | DEC-01 用户范围决定 | APPROVED |\n'
        self.assertEqual(scope_issues(scope, self.text), [])

    def test_scope_unrequested_feature(self):
        target = self.text.replace('| F-01 | 查看列表 |', '| F-01 | 查看列表 |\n| F-02 | 导出 |')
        self.assertEqual(scope_issues(self.text, target), ['scope-unrequested: F-02'])

    def test_prd_pre_is_not_native_final(self):
        source, review, scope = (self.root / n for n in ('report.md', 'review.md', 'scope.md'))
        source.write_text(self.text)
        scope.write_text(self.text)
        import hashlib
        self.record['inputs']['@scope'] = hashlib.sha256(scope.read_bytes()).hexdigest()
        save_record(review, self.record)
        gate = runpy.run_path(str(ROOT / 'scripts/prd-quality-gate.py'))
        self.assertEqual(gate['check'](source, review, scope, 'pre'), [])
        self.assertTrue(any('review-receipt' in i for i in gate['check'](source, review, scope, 'final')))

    def test_compound_ac_is_flagged(self):
        # R2：复合 AC 让 FR 级引用变成假覆盖 —— 三个断言可能只测了一个。
        from _writing_contract import compound_ac_issues
        text = self.text.replace('- AC-1 Given',
                                 '- AC-2 支持拖拽排序，同时结果跟随账号保存\n- AC-1 Given')
        self.assertTrue(any('ac-compound' in i and 'AC-2' in i for i in compound_ac_issues(text)))

    def test_atomic_marker_is_not_punished(self):
        # 门不许惩罚正确用法：确属单一行为的连接词，标了 [原子:理由] 就放行。
        from _writing_contract import compound_ac_issues
        text = self.text.replace('- AC-1 Given',
                                 '- AC-2 字段标红且给出具体原因 [原子:同一次反馈的两个侧面]\n- AC-1 Given')
        self.assertEqual(compound_ac_issues(text), [])

    def test_nfr_perf_number_needs_capacity_anchor(self):
        # R1：没有量级的性能数字不可测 —— P95≤2s 在 100 条和 10 万条下结论相反。
        from _writing_contract import nfr_capacity_issues
        text = self.text.replace('# 附件 E',
                                 '## NFR-001 所属 全局\nP95 响应时间 ≤ 500ms\n\n# 附件 E')
        self.assertTrue(any('nfr-capacity' in i for i in nfr_capacity_issues(text)))
        anchored = text.replace('P95 响应时间 ≤ 500ms',
                                'P95 响应时间 ≤ 500ms\n**适用量级**：D.0 条目当前 1 万，按 1 万验收')
        self.assertEqual(nfr_capacity_issues(anchored), [])

    def test_invalid_json_returns_unable_not_crash(self):
        source, review, scope = (self.root / n for n in ('report.md', 'review.md', 'scope.md'))
        source.write_text(self.text)
        scope.write_text(self.text)
        review.write_text('```json\nnull\n```')
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts/prd-quality-gate.py'),
            '--source', str(source), '--review', str(review), '--scope', str(scope), '--phase', 'pre'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn('UNABLE:', proc.stderr)


if __name__ == '__main__':
    unittest.main()
