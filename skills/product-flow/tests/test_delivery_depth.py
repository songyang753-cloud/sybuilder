"""Regression cases: plausible-looking prose must not establish coverage."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import _prd_parse


def script(name):
    return runpy.run_path(str(ROOT / 'scripts' / name))


class DepthRegressions(unittest.TestCase):
    def test_feature_body_keeps_children_but_not_next_feature(self):
        gate = script('prd_completeness_check.py')
        text = '## F-01 查看\n开头\n### 字段\n字段正文\n## F-02 导出\n导出正文\n# 附件 A\n## F-01 不属于功能正文\n'
        sections = gate['ch4_sections'](text)
        self.assertIn('字段正文', sections['F-01'][2])
        self.assertNotIn('导出正文', sections['F-01'][2])
        self.assertEqual(set(sections), {'F-01', 'F-02'})

    def test_fr_ownership_without_ac_is_not_acceptance(self):
        text = '# 附件 A\n## FR-001 所属 F-01 MUST\n相关规则。\n# 附件 B'
        self.assertEqual(_prd_parse.features_with_ac(text), set())

    def test_template_shared_scenario_supports_concrete_ac(self):
        text = '# 附件 A\n## FR-001 所属 F-01\n**Given** 列表关闭\n**When** 点击查看\n**Then** 显示固定列表\n- AC-1 条目名称与本地预置数据相同，数据不变。\n# 附件 B'
        self.assertEqual(_prd_parse.features_with_ac(text), {'F-01'})
        self.assertFalse(_prd_parse.features_with_ac(text.replace('条目名称与本地预置数据相同，数据不变。', '<具体验收条件>')))
        self.assertFalse(_prd_parse.features_with_ac(text.replace('显示固定列表', '<预期结果>')))

    def test_appendix_cross_reference_and_fenced_example_do_not_grant_ac(self):
        text = '正文提到 # 附件 A\n```md\n# 附件 A\n## FR-099 所属 F-99\n- AC-1 Given A When B Then C\n```\n## 附件 A\n## FR-001 所属 F-01\n正文提到 # 附件 B\n- AC-1 Given 列表关闭 When 点击查看 Then 显示列表。\n## 附件 B'
        self.assertEqual(_prd_parse.features_with_ac(text), {'F-01'})

    def test_placeholder_scenario_is_not_executable_ac(self):
        text = '# 附件 A\n## FR-001 所属 F-01\n- AC-1 Given <前提> When <操作> Then <预期>\n'
        self.assertFalse(_prd_parse.features_with_ac(text))

    def test_upstream_feature_cannot_disappear(self):
        gate = script('chain-gate.py')
        definition = gate['DEF'].replace('## 六、成功长什么样',
            '| F-02 | 单独导出所选原片 | 两端 | 否 | M |\n## 六、成功长什么样')
        output = io.StringIO()
        with patch.dict(gate['g0_8'].__globals__, {'read': lambda p: definition if p == 'definition' else gate['PRD']}), contextlib.redirect_stdout(output):
            result = gate['g0_8']('definition', 'prd')
        self.assertNotEqual(result, 0)
        self.assertIn('F-02', output.getvalue())

    def test_appendix_mention_is_not_field_spec(self):
        gate = script('prd_completeness_check.py')
        text = gate['GOOD'].replace('F-01 字段：路径 string 必填。', '本功能不含 F-01 字段定义。')
        with patch.dict(gate['check'].__globals__, {'load': lambda _: text}):
            result = gate['check']('memory', stage='S4')
        self.assertTrue(any('D ' in name for name, _ in result['gaps']), result)

    def test_role_cells_cannot_all_be_empty(self):
        gate = script('product-structure-gate.py')
        # Use a minimal task fixture: no reliance on a particular example's row names.
        text = '''# 产品结构
## 功能架构
F-01 查看照片
## 关键任务流
任务：查看照片
打开列表→查看照片；失败→保留列表并返回。
## 权限矩阵
| 行为 | 访客 | 成员 |
|---|---|---|
| 查看照片 | | |
## 状态与异常结构
| 对象 | 状态 |
|---|---|
| 列表 | empty/success/error |
'''
        self.assertTrue(any('③' in issue for issue in gate['check'](text)))


if __name__ == '__main__':
    unittest.main()
