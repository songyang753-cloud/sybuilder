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
import venv
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
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
        shutil.copyfile(Path(__file__).resolve().parent / 'test-w5-adapter.py', self.adapter)
        self.suite = self.root / 'suite.json'
        self.suite.write_text(json.dumps({'cases': [{'id': 'C1', 'input': 'synthetic'}]}))
        (self.root / 'baseline.json').write_text(json.dumps({
            'suiteHash': w5.digest(self.suite), 'cases': {'C1': dict.fromkeys(w5.DIMENSIONS, 1)}}))
        self.cfg = {'mode': 'production', 'targetVersion': 'synthetic-only',
                    'productionContract': {'promptRef': 'suite.json', 'toolSchemaRef': 'suite.json',
                                           'adapterRef': 'adapter.py', 'judgeRef': 'adapter.py'},
                    'suiteRef': 'suite.json', 'baselineRef': 'baseline.json',
                    # 2026-09-29 评审 M16-1:解释器只允许裸名——夹具同步(原 sys.executable 含 '/')
                    'runner': ['python3', 'adapter.py', 'runner'],
                    'judge': ['python3', 'adapter.py', 'judge'],
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

    def test_interpreter_path_injection_rejected(self):
        # 2026-09-29 评审 M16-1:改名 python3 的任意可执行(含路径的 command[0])不得通过校验。
        for argv in [['../outside/python3', 'adapter.py'],
                     ['../../etc/python3', 'adapter.py']]:
            proc, report, _ = self.run_config(dict(self.cfg, runner=argv))
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(report.get('records', []), [])
            self.assertIn('escapes the project root', str(report.get('reason', '')))
        # 绝对路径但不存在 → 拒;存在但非真解释器(改名的 sh 脚本)→ 自证不过而拒
        proc, report, _ = self.run_config(dict(self.cfg, runner=['/nonexistent-path/python3', 'adapter.py']))
        self.assertEqual(proc.returncode, 3)
        self.assertIn('does not exist', str(report.get('reason', '')))
        fake = self.root / 'python3'
        fake.write_text('#!/bin/sh\necho not-a-python\n')
        fake.chmod(0o755)
        proc, report, _ = self.run_config(dict(self.cfg, runner=[str(fake), 'adapter.py', 'runner']))
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(report.get('records', []), [])
        self.assertIn('self-identification', str(report.get('reason', '')))

    def test_fail_dimensions_type_validated_for_all_fail_controls(self):
        # 2026-09-29 评审 M16 建议:无 scoreBounds 的 FAIL 控制例此前不校验 failDimensions,
        # 字符串形态漏到执行期抛 KeyError、reason 只剩类名。
        proc, report, _ = self.run_config(dict(self.cfg,
            judgeControls=[{'expected': 'PASS', 'input': {'trace': {'knownBad': False}}},
                           {'expected': 'FAIL', 'failDimensions': 'safety',
                            'input': {'trace': {'knownBad': True}}}]))
        self.assertEqual(proc.returncode, 3)
        reason = str(report.get('reason', ''))
        self.assertIn('failDimensions', reason)
        self.assertIn('knownBad', reason)  # 报文指明是哪个控制例
        proc, report, _ = self.run_config(dict(self.cfg,
            judgeControls=[{'expected': 'PASS', 'input': {'trace': {'knownBad': False}}},
                           {'expected': 'FAIL', 'failDimensions': ['not-a-dimension'],
                            'input': {'trace': {'knownBad': True}}}]))
        self.assertEqual(proc.returncode, 3)
        self.assertIn('six dimensions', str(report.get('reason', '')))

    def test_private_writes_are_0600(self):
        # 2026-09-29 评审 M16:私写抽 _private_fd 单源后,权限契约不回退(正常执行后查产物权限)。
        proc, _, out = self.run_config()
        self.assertEqual(proc.returncode, 0)
        for name in ('result.json',):
            self.assertEqual((out / name).stat().st_mode & 0o777, 0o600)

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

    def test_virtual_environment_launcher_is_preserved(self):
        env = self.root / 'venv'
        venv.EnvBuilder(with_pip=False, symlinks=True).create(env)
        launcher = env / 'bin/python3'
        self.adapter.write_text('import sys,json\nprint(json.dumps({"prefix":sys.prefix}))\n')
        command = w5.validate_command(self.root.resolve(), [str(launcher), 'adapter.py'], self.adapter.resolve())
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(Path(json.loads(result.stdout)['prefix']).resolve(), env.resolve())
        self.assertEqual(command[0], str(launcher))
        command = w5.validate_command(self.root.resolve(), ['venv/bin/python3', 'adapter.py'], self.adapter.resolve())
        result = subprocess.run(command,cwd=self.root,capture_output=True,text=True,check=True)
        self.assertEqual(Path(json.loads(result.stdout)['prefix']).resolve(),env.resolve())
        with patch.dict(os.environ,PATH=str(env/'bin')+os.pathsep+os.environ.get('PATH','')):
            command=w5.validate_command(self.root.resolve(),['python3','adapter.py'],self.adapter.resolve())
            result=subprocess.run(command,cwd=self.root,capture_output=True,text=True,check=True)
            self.assertEqual(Path(json.loads(result.stdout)['prefix']).resolve(),env.resolve())

    def test_disk_failure_and_launch_window_still_reap_child(self):
        real_popen=w5.subprocess.Popen
        for failure in ('disk','cancel'):
            folder=self.root/failure;folder.mkdir();children=[]
            def launch(*args,**kwargs):
                child=real_popen(*args,**kwargs);children.append(child)
                if failure=='cancel':w5.INTERRUPTED=True
                return child
            try:
                with patch.object(w5.subprocess,'Popen',side_effect=launch),patch.object(w5.os,'fsync',side_effect=OSError('synthetic disk full')):
                    with self.assertRaises((OSError,w5.Unable)):
                        w5.run_owned([sys.executable,'-c','import time;time.sleep(10)'],self.root,b'{}',1,folder,4096,{'remaining':8192})
                self.assertEqual(len(children),1)
                self.assertIsNotNone(children[0].poll())
            finally:
                w5.INTERRUPTED=False
                for child in children:
                    if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()

    def test_completed_evidence_survives_executor_hard_kill(self):
        self.adapter.write_text(self.adapter.read_text().replace("request = json.load(sys.stdin)",
            "request = json.load(sys.stdin)\nif sys.argv[1]=='runner':\n import time; time.sleep(30)"))
        config=self.root/'config.json';config.write_text(json.dumps(self.cfg))
        out=self.root/'hard-kill'
        process=subprocess.Popen([sys.executable,str(ENTRY),'--config',str(config),'--output',str(out),'--execute'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pid=None
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                for file in (out/'calls').glob('*/process.json'):
                    start=json.loads((file.parent/'started.json').read_text())
                    if start['kind']=='runner':pid=json.loads(file.read_text())['pid']
                if pid:break
                time.sleep(.02)
            self.assertIsNotNone(pid)
            process.kill();process.wait(timeout=3)
            completed=list((out/'calls').glob('*/completed.json'))
            self.assertEqual(len(completed),2)
            self.assertTrue(all(json.loads(f.read_text())['status']=='OK' for f in completed))
            self.assertFalse((out/'result.json').exists())
        finally:
            if process.poll() is None:process.kill();process.wait()
            if pid:
                try:os.killpg(pid,signal.SIGKILL)
                except ProcessLookupError:pass

    def test_git_evidence_protection_states(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'.gitignore').write_text('ignored/\n')
        self.assertEqual(w5.git_evidence_check(self.root/'ignored'),'ignored')
        self.assertEqual(w5.git_evidence_check(self.root/'visible'),'unignored-warning')
        folder=self.root/'ignored';folder.mkdir();(folder/'result.json').write_text('{}')
        subprocess.run(['git','-C',str(self.root),'add','-f','ignored/result.json'],check=True)
        with self.assertRaises(w5.Unable):w5.git_evidence_check(folder)
        with patch.object(w5.subprocess,'run',side_effect=OSError()):
            self.assertEqual(w5.git_evidence_check(self.root/'other'),'check-unavailable')
        outside=Path(self.temp.name)/'outside-evidence'
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(w5.git_evidence_check(Path(folder)/'evidence'),'outside-git')
        fake=subprocess.CompletedProcess([],2,'','fatal: permission denied')
        with patch.object(w5.subprocess,'run',return_value=fake):
            self.assertEqual(w5.git_evidence_check(outside),'check-unavailable')

    def test_overlapping_controls_rejected_before_any_calls(self):
        positive, negative = self.cfg['judgeControls']
        positive['scoreBounds'] = {d: [0, 1] for d in w5.DIMENSIONS}
        positive['scoreBounds']['safety'] = [1, 1]
        negative['scoreBounds'] = {d: [0, 0.99] for d in w5.DIMENSIONS}
        negative['scoreBounds']['safety'] = [1, 1]
        negative['failDimensions'] = ['rubric']
        proc, report, _ = self.run_config()
        self.assertEqual(proc.returncode, 3)
        self.assertIn('overlap', report['reason'])
        self.assertEqual(report['records'], [])

    def test_constant_judge_cannot_pass_mixed_calibration(self):
        positive = self.cfg['judgeControls'][0]
        positive['scoreBounds'] = {d: [0.8, 1] for d in w5.DIMENSIONS}
        positive['scoreBounds']['safety'] = [1, 1]
        self.adapter.write_text('import sys,json\nr=json.load(sys.stdin)\n'
            's=dict.fromkeys(' + repr(w5.DIMENSIONS) + ',0.9); s["safety"]=1\n'
            'print(json.dumps({"status":"OK","executionId":r["executionId"],"scores":s}))\n')
        proc, report, _ = self.run_config()
        self.assertEqual(proc.returncode, 3)
        self.assertIn('distinguish', report['reason'])

    def test_output_limit_and_incremental_private_evidence(self):
        self.adapter.write_text('import sys\nsys.stdout.write("x" * 1000000)\n')
        proc, report, out = self.run_config(dict(self.cfg, maxOutputBytes=4096))
        self.assertEqual(proc.returncode, 3)
        self.assertIn('truncated', report['reason'])
        call = out / report['records'][0]['evidenceRef']
        self.assertLessEqual((call / 'stdout.txt').stat().st_size, 4096)
        self.assertTrue((call / 'started.json').is_file())
        self.assertTrue((call / 'completed.json').is_file())
        self.assertNotIn('stdout', report['records'][0])
        self.assertEqual((call / 'stdout.txt').stat().st_mode & 0o777, 0o600)

    def test_invalid_json_reports_safe_file_context(self):
        self.suite.write_text('{\n broken-private-value')
        proc, report, _ = self.run_config()
        self.assertEqual(proc.returncode, 3)
        self.assertIn('suite.json', report['reason'])
        self.assertIn('line 2', report['reason'])
        self.assertNotIn('broken-private-value', report['reason'])

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
