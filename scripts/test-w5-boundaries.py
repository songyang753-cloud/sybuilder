"""Adversarial W5 configuration tests. All commands/data are synthetic and local."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'skills/four-node-review/agent-evaluation/run.py'
spec = importlib.util.spec_from_file_location('w5_boundaries', ENTRY)
w5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w5)


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.root.mkdir()
        self.adapter = self.root / 'adapter.py'
        shutil.copyfile(ROOT / 'scripts/test-w5-adapter.py', self.adapter)
        self.suite = self.root / 'suite.json'
        self.suite.write_text(json.dumps({'cases': [{'id': 'C1', 'input': 'synthetic'}]}))
        (self.root / 'baseline.json').write_text(json.dumps({
            'suiteHash': w5.digest(self.suite), 'cases': {'C1': dict.fromkeys(w5.DIMENSIONS, 1)}}))
        self.cfg = {'mode': 'production', 'targetVersion': 'synthetic-only',
                    'productionContract': {'promptRef': 'suite.json', 'toolSchemaRef': 'suite.json',
                                           'adapterRef': 'adapter.py', 'judgeRef': 'adapter.py'},
                    'suiteRef': 'suite.json', 'baselineRef': 'baseline.json',
                    'runner': [sys.executable, 'adapter.py', 'runner'],
                    'judge': [sys.executable, 'adapter.py', 'judge'],
                    'judgeControls': [{'expected': 'PASS', 'input': {'trace': {'knownBad': False}}},
                                      {'expected': 'FAIL', 'input': {'trace': {'knownBad': True}}}]}
        self.index = 0

    def run_config(self, cfg=None, execute=True):
        self.index += 1
        config = self.root / 'config.json'
        config.write_text(json.dumps(self.cfg if cfg is None else cfg))
        out = self.root / ('output-%d' % self.index)
        proc = subprocess.run([sys.executable, '-B', str(ENTRY), '--config', str(config),
            '--output', str(out)] + (['--execute'] if execute else []),
            capture_output=True, text=True, timeout=10)
        report = json.loads((out / 'result.json').read_text()) if (out / 'result.json').is_file() else {}
        return proc, report, out

    def test_valid_and_private_output(self):
        proc, report, out = self.run_config()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['plan']['plannedCalls'], 8)
        if os.name == 'posix':
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            self.assertEqual((out / 'result.json').stat().st_mode & 0o777, 0o600)

    def test_invalid_config_types_have_unable_evidence(self):
        for field, value in [('suiteRef', 7), ('timeoutSeconds', '120'), ('timeoutSeconds', None),
                             ('timeoutSeconds', True), ('timeoutSeconds', 0), ('repeats', True),
                             ('productionContract', []), ('judgeControls', [None]),
                             ('targetVersion', 5), ('maxCalls', 2), ('repeats', 300)]:
            with self.subTest(field=field, value=value):
                cfg = dict(self.cfg, **{field: value})
                proc, report, _ = self.run_config(cfg)
                self.assertEqual(proc.returncode, 3, proc.stderr)
                self.assertEqual(report['status'], 'UNABLE')
                self.assertTrue(report['reason'])
                self.assertEqual(report.get('records', []), [])
        for cfg in [None, [], 7]:
            self.index += 1
            config = self.root / 'invalid.json'; config.write_text(json.dumps(cfg))
            rc = w5.execute(config, self.root / ('invalid-%d' % self.index))
            self.assertEqual(rc, 3)

    def test_bad_stdout_and_score_types(self):
        for value in ['null', '[]', 'not-json']:
            with self.subTest(value=value):
                self.adapter.write_text('print(' + repr(value) + ')\n')
                proc, report, _ = self.run_config()
                self.assertEqual(proc.returncode, 3)
                self.assertTrue(report['reason'])
        for value in [None, [], {}, {'status':'OK', 'scores':[]}]:
            with self.assertRaises(w5.Unable): w5.scores(value)

    def test_ref_escape_and_argv_bypass_rejected_before_calls(self):
        outside = self.root.parent / 'outside.json'; shutil.copyfile(self.suite, outside)
        (self.root / 'link.json').symlink_to(outside)
        for ref in ['../outside.json', str(outside), 'link.json']:
            proc, report, _ = self.run_config(dict(self.cfg, suiteRef=ref))
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(report.get('records', []), [])
        for argv in [[sys.executable, '-c', 'print("null")', 'adapter.py'],
                     ['/bin/sh', '-c', 'true', 'adapter.py'],
                     [sys.executable, '-m', 'json', 'adapter.py']]:
            proc, report, _ = self.run_config(dict(self.cfg, judge=argv))
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(report.get('records', []), [])

    def test_no_execute_and_no_overwrite(self):
        proc, _, out = self.run_config(execute=False)
        self.assertEqual(proc.returncode, 3); self.assertFalse(out.exists())
        proc, _, out = self.run_config()
        before = (out / 'result.json').read_bytes()
        proc = subprocess.run([sys.executable, str(ENTRY), '--config', str(self.root/'config.json'),
                              '--output', str(out), '--execute'], capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 3)
        self.assertEqual((out / 'result.json').read_bytes(), before)

    def test_graded_calibration_does_not_relax_product_safety(self):
        control = self.cfg['judgeControls'][0]
        control['scoreBounds'] = {d: [1, 1] for d in w5.DIMENSIONS}
        control['scoreBounds']['rubric'] = [0.8, 1]
        self.adapter.write_text(self.adapter.read_text().replace('print(json.dumps(response))',
            "if sys.argv[1] == 'judge' and 'repeat' not in request.get('trace', {}) and not request.get('trace', {}).get('knownBad'):\n"
            "    response['scores']['rubric'] = 0.9\nprint(json.dumps(response))"))
        proc, _, _ = self.run_config(); self.assertEqual(proc.returncode, 0)
        run = dict.fromkeys(w5.DIMENSIONS, 1); run['safety'] = 0.9
        self.assertIn('P1:safety', w5.compare([run]*3, run)['issues'])

    @unittest.skipUnless(os.name == 'posix', 'owned process groups require POSIX')
    def test_timeout_and_interrupt_clean_owned_descendants(self):
        # An unrelated control process must survive both cleanup paths.
        control = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(lambda: (control.terminate(), control.wait()))
        self.adapter.write_text(
            'import subprocess,sys,time,os\nfrom pathlib import Path\n'
            'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n'
            'Path("child.pid").write_text(str(p.pid))\n'
            'time.sleep(30)\n')
        for interrupt in (False, True):
            with self.subTest(interrupt=interrupt):
                pidfile = self.root / 'child.pid'
                pidfile.unlink(missing_ok=True)
                self.cfg['timeoutSeconds'] = 10 if interrupt else 0.3
                config = self.root / 'config.json'; config.write_text(json.dumps(self.cfg))
                out = self.root / ('tree-' + str(interrupt))
                process = subprocess.Popen([sys.executable, str(ENTRY), '--config', str(config),
                    '--output', str(out), '--execute'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pidfile.exists())
                if interrupt:
                    process.send_signal(signal.SIGTERM)
                process.communicate(timeout=5)
                self.assertEqual(process.returncode, 3)
                self.assertTrue(json.loads((out / 'result.json').read_text())['reason'])
                pid = int(pidfile.read_text())
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
                    if not status or status.startswith('Z'):
                        break
                    time.sleep(0.03)
                self.assertTrue(not status or status.startswith('Z'), status)
                self.assertIsNone(control.poll())


if __name__ == '__main__':
    unittest.main()
