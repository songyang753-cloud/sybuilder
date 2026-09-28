#!/usr/bin/env python3
"""PRD scope, independent consumer and native delivery review.
0=PASS, 1=FAIL, 2=UNABLE. --phase pre never closes a formal PRD delivery.
"""
import argparse
import importlib.util
from pathlib import Path
import sys
from _writing_contract import behavior_issues, compound_ac_issues, feature_ids, nfr_capacity_issues, scope_issues


def review_gate():
    spec = importlib.util.spec_from_file_location('prd_review', Path(__file__).with_name('research-quality-gate.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bound_inputs(source, review):
    return review_gate().bound_inputs(source, review)


def check(source, review, scope, phase='final'):
    text = Path(source).read_text(encoding='utf-8')
    upstream = Path(scope).read_text(encoding='utf-8')
    features = feature_ids(text)
    if not features:
        raise ValueError('scope-input: PRD functional inventory missing')
    issues = scope_issues(upstream, text)
    issues += behavior_issues(text, features)
    issues += compound_ac_issues(text)
    issues += nfr_capacity_issues(text)
    issues += review_gate().check(source, review, phase, features=features, scope=scope)
    return issues


def _boundary():
    print('⚠️ 本门不认证身份或事实；机械完整不替代独立专业判断与产品负责人批准。')


def self_test():
    import unittest
    tests = Path(__file__).resolve().parents[1] / 'tests'
    suite = unittest.defaultTestLoader.discover(str(tests), pattern='test_writing_contract.py')
    class Result(unittest.TextTestResult):
        def startTest(self, test):
            if not hasattr(self, 'checked_names'):
                self.checked_names = []
            self.checked_names.append(test.id())
            super().startTest(test)
    result = unittest.TextTestRunner(verbosity=0, resultclass=Result).run(suite)
    # selftest-all counts the explicit case records, not unittest's progress.
    failed = {test.id() for test, _ in result.failures + result.errors}
    for name in sorted(getattr(result, 'checked_names', [])):
        positive = name.endswith(('test_readonly_na_is_valid', 'test_explicit_removal_in_upstream'))
        print(('  ✗ ' if name in failed else '  ✓ ') + ('正例：' if positive else '反例/边界：') + name)
    return 0 if result.wasSuccessful() else 1


def main():
    if '--self-test' in sys.argv:
        return self_test()
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--source', required=True)
    parser.add_argument('--scope', required=True, help='approved upstream definition or standalone scope inventory')
    parser.add_argument('--review', required=True)
    parser.add_argument('--phase', choices=('pre', 'final'), default='final')
    args = parser.parse_args()
    issues = check(args.source, args.review, args.scope, args.phase)
    for issue in issues:
        print('❌ ' + issue)
    if not issues:
        print('✅ PRD scope / consumer / delivery review ' + args.phase)
    return 1 if issues else 0


def _main_guarded(fn):
    _boundary()
    try:
        sys.exit(fn())
    except Exception as exc:
        print('UNABLE: ' + str(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    _main_guarded(main)
