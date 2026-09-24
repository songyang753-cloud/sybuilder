"""Real planner/writer/consumer integration. Synthetic execution is explicitly isolated."""
import contextlib
from datetime import datetime, timedelta
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / 'skills/product-flow/scripts'
sys.path.insert(0, str(S))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

planner = load('binding_planner', S/'product-flow-run.py')
gate = load('binding_writer', S/'gate-run.py')
from _workflow import load_active_run, gate_result_dir, required_rule_ids
from _module_contract import issue_result

class BindingTests(unittest.TestCase):
    def activate(self, root, mode='only', research='full-research'):
        opts = ['plan', '--root', str(root), '--mode', mode, '--run-id', 'BINDING',
                '--research-mode', research, '--write']
        if mode == 'only': opts += ['--modules', 'research']
        if mode == 'from': opts += ['--from', 'research']
        planner._plan(planner.parser().parse_args(opts))
        return load_active_run(str(root), required=True)[0]

    def verdict(self, root, record_gate, n):
        draft = root/'.product-flow/draft.json'
        draft.write_text(json.dumps({'moduleId':'S2', 'claimCeiling':'draft',
            'resultId':'CASE-'+str(n), 'limitations':['Synthetic local contract test, not approval']}))
        issued = json.loads(Path(issue_result(str(root), str(draft))).read_text())
        return next(r['verdict'] for r in issued['gateResults'] if r['gate']==record_gate)

    def test_conditional_bindings_use_the_real_writer_and_consumer(self):
        for mode in ('full', 'from', 'only'):
            for research in ('full-research', 'competitive-pack'):
                with self.subTest(mode=mode, research=research), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        manifest = self.activate(root, mode, research)
                        with patch.object(gate, 'run_child', return_value=subprocess.CompletedProcess([],0,'synthetic gate body','')):
                            gate.run([str(S/'research-gate.py'), str(root)], str(root))
                        p = Path(gate_result_dir(str(root), manifest))/'research-gate.py.json'
                        rec = json.loads(p.read_text())
                        self.assertEqual(rec['ruleIds'], required_rule_ids(manifest, 'research-gate.py'))
                        self.assertEqual(self.verdict(root, 'research-gate.py', 1), 'PASS')
                        # Other results are explicitly synthetic to isolate status binding.
                        # The research record above still comes from the real writer.
                        for required in manifest['requiredGates']:
                            if required == 'research-gate.py': continue
                            fixture = dict(rec, ruleIds=required_rule_ids(manifest, required))
                            fixture['ranAt'] = (datetime.now().astimezone()+timedelta(seconds=2)).isoformat()
                            (p.parent/(required+'.json')).write_text(json.dumps(fixture))
                        status_output = io.StringIO()
                        with contextlib.redirect_stdout(status_output):
                            code = gate.status(str(root), str(S.parent), blocking=True)
                        self.assertEqual(code, 0, status_output.getvalue())
                        rec['ruleIds'].append('R-FOREIGN'); p.write_text(json.dumps(rec))
                        self.assertEqual(self.verdict(root, 'research-gate.py', 2), 'INVALID-BINDING')
                        self.assertEqual(gate.status(str(root), str(S.parent), blocking=True), 1)

    def test_tech_plan_requires_post_not_pre_for_formal_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                manifest = self.activate(root, research='tech-approach')
                with patch.object(gate, 'run_child') as child:
                    with self.assertRaises(SystemExit) as exc:
                        gate.run([str(S/'tech-research-gate.py'), '--pre', str(root)], str(root))
                    self.assertEqual(exc.exception.code, 2); child.assert_not_called()
                # A mocked post body tests admission only, not remote acceptance.
                with patch.object(gate, 'run_child', return_value=subprocess.CompletedProcess([],2,'','synthetic UNABLE')):
                    self.assertEqual(gate.run([str(S/'tech-research-gate.py'), '--post', str(root)], str(root)), 2)
                self.assertEqual(self.verdict(root, 'tech-research-gate.py', 1), 'UNABLE')

    def test_real_report_gate_rejects_missing_body_after_valid_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for src in (S.parent/'tests/s2-golden').iterdir():
                if src.is_file(): shutil.copyfile(src, root/src.name)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.activate(root, research='teardown')
                args = [str(S/'report-structure-gate.py'), '--mode', 'teardown', str(root/'report.md'),
                    '--atomic-ledger', str(root/'ledger.md'), '--events', str(root/'traversal-events.json'),
                    '--evidence-manifest', str(root/'evidence-manifest.json')]
                self.assertEqual(gate.run(args, str(root)), 0)
                self.assertEqual(self.verdict(root, 'report-structure-gate.py', 1), 'PASS')
                (root/'report.md').write_text('# Incomplete report\n')
                self.assertEqual(self.verdict(root, 'report-structure-gate.py', 2), 'INVALID-BINDING')
                self.assertNotEqual(gate.run(args, str(root)), 0)
                self.assertEqual(self.verdict(root, 'report-structure-gate.py', 3), 'FAIL')

if __name__ == '__main__': unittest.main()
