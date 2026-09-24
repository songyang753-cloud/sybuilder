#!/usr/bin/env python3
"""Real subprocess contract regressions with synthetic adapters, not model evals."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('w5', ROOT / 'skills/four-node-review/agent-evaluation/run.py')
w5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w5)


class EvaluationTests(unittest.TestCase):
    def test_three_repeats_negative_controls_regressions_and_unable(self):
        for mode, expected in [('good', 0), ('regression', 1), ('jitter', 1),
                               ('unable', 3), ('always-green', 3)]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                suite = root / 'suite.json'
                suite.write_text(json.dumps({'cases': [{'id': 'C1', 'input': 'synthetic'}]}))
                baseline = root / 'baseline.json'
                baseline.write_text(json.dumps({'suiteHash': w5.digest(suite),
                                                'cases': {'C1': dict.fromkeys(w5.DIMENSIONS, 1)}}))
                adapter = 'adapter.py'
                (root / adapter).write_bytes((ROOT / 'scripts/test-w5-adapter.py').read_bytes())
                cfg = {'mode': 'production', 'targetVersion': 'synthetic-test-only',
                       'productionContract': dict.fromkeys(('promptRef', 'toolSchemaRef'), 'suite.json'),
                       'runner': [sys.executable, adapter, 'runner'],
                       'judge': [sys.executable, adapter, 'judge', mode],
                       'suiteRef': 'suite.json', 'baselineRef': 'baseline.json',
                       'judgeControls': [{'expected': 'PASS', 'input': {'trace': {'knownBad': False}}},
                                         {'expected': 'FAIL', 'input': {'trace': {'knownBad': True}}}]}
                cfg['productionContract'].update(adapterRef=adapter, judgeRef=adapter)
                path = root / 'config.json'; path.write_text(json.dumps(cfg))
                self.assertEqual(w5.execute(path, root / 'output'), expected)
                report = json.loads((root / 'output/result.json').read_text())
                ids = [r['executionId'] for r in report['records']]
                self.assertEqual(len(ids), len(set(ids)))
                if mode == 'good':
                    self.assertEqual(report['cases']['C1']['worst'], dict.fromkeys(w5.DIMENSIONS, 1))
                    cfg['mode'] = 'scripted'; path.write_text(json.dumps(cfg))
                    self.assertEqual(w5.execute(path, root / 'scripted'), 3)
                self.assertEqual(w5.digest(baseline), report['fingerprints'][str(baseline.resolve())])

    def test_missing_dimensions_or_repeats_never_pass(self):
        with self.assertRaises(w5.Unable): w5.scores({'status': 'OK', 'scores': {'safety': 1}})
        with self.assertRaises(w5.Unable): w5.compare([dict.fromkeys(w5.DIMENSIONS, 1)], dict.fromkeys(w5.DIMENSIONS, 1))


if __name__ == '__main__':
    unittest.main()
