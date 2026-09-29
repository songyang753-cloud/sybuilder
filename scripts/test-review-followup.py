"""Third-party-review regressions, using only isolated synthetic local projects."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CS = ROOT / 'skills/coding-standards'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Followup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_reverse_traversal_and_symlinks_never_write_real_source(self):
        skill = self.root / 'skills/coding-standards'
        (skill / 'scripts').mkdir(parents=True)
        (self.root / 'licenses').mkdir()
        (self.root / 'THIRD_PARTY.md').write_text('Synthetic attribution')
        helper = skill / 'scripts/reverse-test.sh'
        shutil.copyfile(CS / 'scripts/reverse-test.sh', helper)
        (skill / 'scripts/selfcheck.sh').write_text('exit 0\n')
        other = self.root / 'skills/four-node-review'
        other.mkdir()
        target = other / 'SKILL.md';target.write_text('synthetic-original')
        (skill / 'escape.md').symlink_to(target)
        for source in (str(skill) + '/../four-node-review/SKILL.md', str(skill / 'escape.md')):
            proc = subprocess.run(['bash',str(helper),source,'synthetic-original','mutated','0'],
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(proc.returncode,4,proc.stdout)
            self.assertEqual(target.read_text(),'synthetic-original')

    def test_missing_external_source_is_unable_not_fail(self):
        proc = subprocess.run(['bash',str(CS/'scripts/selfcheck.sh')],
            env=dict(os.environ,FOUR_NODE_SKILL=str(self.root/'missing.md')),
            capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,3,proc.stdout)
        section=proc.stdout.split('[11]')[1].split('[9]')[0]
        self.assertIn('UNABLE',section)
        self.assertNotIn('FAIL ',section)

    def test_stale_global_marker_does_not_disable_live_anchor_check(self):
        (self.root/'coding-standards-revtest.lock').mkdir()
        proc = subprocess.run(['bash',str(CS/'scripts/selfcheck.sh')],
            env=dict(os.environ,TMPDIR=str(self.root)),capture_output=True,text=True,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stdout)
        self.assertIn('锚点全部唯一命中',proc.stdout)

    def test_python_missing_is_explicit_in_anchor_branch(self):
        source=(CS/'scripts/selfcheck.sh').read_text()
        fragment=source[source.index('if [ "${n_anchor:-0}" -lt 10 ]'):source.index('# ---------- 3.')]
        prefix='n_anchor=90; SRC_OK=1; pass(){ echo PASS; }; fail(){ echo FAIL; }; unable(){ echo UNABLE; };\n'
        proc=subprocess.run(['/bin/bash','-c',prefix+fragment],env={'PATH':str(self.root)},
                            capture_output=True,text=True,timeout=5)
        self.assertIn('UNABLE',proc.stdout)
        self.assertNotIn('integer expression',proc.stderr)
        self.assertNotIn('FAIL',proc.stdout)

    def test_new_fixture_directory_cannot_be_silently_omitted(self):
        skill=self.root/'coding-standards'
        shutil.copytree(CS,skill)
        extra=skill/'tests/fixtures/NEW';extra.mkdir()
        for name in ('violating.sh','compliant.sh'):(extra/name).write_text('exit 0\n')
        proc=subprocess.run(['bash',str(skill/'scripts/rule-fixtures.sh')],capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,3)
        self.assertIn('未登记执行语义',proc.stdout)

    def test_hook_dispatches_both_suite_and_flat_host_layout(self):
        for layout in ('skills/coding-standards','coding-standards'):
            repo=self.root/layout.replace('/','-');repo.mkdir()
            subprocess.run(['git','init','-q',str(repo)],check=True)
            skill=repo/layout;(skill/'scripts/hooks').mkdir(parents=True)
            hook=skill/'scripts/hooks/pre-commit';shutil.copyfile(CS/'scripts/hooks/pre-commit',hook)
            hook.chmod(0o755)
            (skill/'scripts/precommit-guard.sh').write_text('echo synthetic-guard\nexit 3\n')
            (skill/'SKILL.md').write_text('synthetic')
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            installed=repo/'.git/hooks/pre-commit';installed.symlink_to(hook)
            proc=subprocess.run(['sh',str(installed)],cwd=repo,capture_output=True,text=True)
            self.assertEqual(proc.returncode,3,proc.stdout+proc.stderr)
            self.assertIn('synthetic-guard',proc.stdout)
            commit=subprocess.run(['git','-c','user.name=Synthetic Tester',
                '-c','user.email=tester@example.invalid','commit','-m','synthetic hook trial'],
                cwd=repo,capture_output=True,text=True)
            self.assertNotEqual(commit.returncode,0)
            self.assertIn('synthetic-guard',commit.stdout+commit.stderr)
            self.assertNotEqual(subprocess.run(['git','rev-parse','--verify','HEAD'],
                cwd=repo,capture_output=True).returncode,0)

    def test_nested_structured_privacy_and_runtime_ignores(self):
        scanner=load('followup_privacy',ROOT/'scripts/verify-portability.py')
        folder=self.root/'spec';folder.mkdir()
        path=folder/'capture.json'
        path.write_text(json.dumps({'userContent':True,'text':'SYNTHETIC_PRIVATE_TEXT'}))
        self.assertIn('spec/capture.json: user-content-not-withheld',scanner.scan(self.root))
        path.write_text(json.dumps({'userContent':True,'text':'[user-content]'}))
        self.assertEqual(scanner.scan(self.root),[])
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        shutil.copyfile(ROOT/'.gitignore',self.root/'.gitignore')
        for target in ('skills/product-flow/.product-flow/x',
                       'skills/product-flow/references/.selftest-progress.jsonl',
                       'skills/product-flow/.reverse-test.lock'):
            proc=subprocess.run(['git','check-ignore','-q',target],cwd=self.root)
            self.assertEqual(proc.returncode,0,target)

    def test_release_scanners_use_git_export_set_not_ignored_runtime(self):
        scanner=load('followup_publish_scan',ROOT/'scripts/verify-portability.py')
        audit=load('followup_publish_audit',ROOT/'scripts/release-audit.py')
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'.gitignore').write_text('.runtime/\n')
        (self.root/'kept.md').write_text('public synthetic file')
        hidden=self.root/'.runtime';hidden.mkdir()
        (hidden/'private.txt').write_text('/'.join(('', 'Users', 'private-user', 'secret')))
        paths=scanner.publish_paths(self.root)
        self.assertIn(self.root/'kept.md',paths);self.assertNotIn(hidden/'private.txt',paths)
        self.assertEqual(scanner.scan_files(self.root,paths),[])
        self.assertNotIn(hidden/'private.txt',audit.candidate_paths(self.root))

    def test_default_measurement_does_not_rewrite_published_snapshot(self):
        sweep=load('followup_selftest',ROOT/'skills/product-flow/scripts/selftest-all.py')
        skill=self.root/'product-flow';(skill/'scripts').mkdir(parents=True)
        (skill/'references').mkdir();snapshot=skill/'references/.selftest-measured.json'
        snapshot.write_text('original snapshot')
        payload={'scripts':1,'cases':1,'failures':0,'failedScripts':[], 'unableScripts':[],
                 'cachedScripts':[],'disagree':[],'negativesByExpectation':0,'negativesByLabel':0}
        def fake(_scripts,_progress,output,_fresh):
            Path(output).write_text(json.dumps(payload));return payload
        with patch.object(sweep,'SCRIPTS',str(skill/'scripts')),patch.object(sweep,'sweep_dir',fake),patch.object(sys,'argv',['selftest','--fresh']):
            self.assertEqual(sweep.main(),0)
        self.assertEqual(snapshot.read_text(),'original snapshot')
        self.assertTrue((skill/'.product-flow/selftest/measured.json').is_file())

    def test_ci_fragments_block_security_and_pin_actions(self):
        import re
        import yaml
        for name in ('ci-node.yml','ci-go.yml'):
            jobs=yaml.safe_load((CS/'repository-enforcement/templates'/name).read_text())
            for job in jobs.values():
                self.assertEqual(job['permissions'],{'contents':'read'})
                self.assertIn('concurrency',job)
                for step in job['steps']:
                    self.assertFalse(step.get('continue-on-error',False))
                    if 'uses' in step:self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')

    def test_local_links_cover_root_paths_without_exempting_templates(self):
        checker=load('followup_links',ROOT/'scripts/verify-local-links.py')
        folder=self.root/'skills/sample/references';folder.mkdir(parents=True)
        (folder/'test.md').write_text('[notice](../../../NOTICE)\n[escape](../../../../outside.md)')
        (self.root/'NOTICE').write_text('synthetic notice')
        count,errors=checker.check(self.root)
        self.assertEqual(count,2)
        self.assertEqual(len(errors),1)
        (self.root/'NOTICE').unlink()
        self.assertEqual(len(checker.check(self.root)[1]),2)

    def test_distributor_refuses_missing_required_test_before_linking(self):
        checkout=self.root/'suite';shutil.copytree(ROOT,checkout,ignore=shutil.ignore_patterns('.git','.sybuilder','.product-flow','__pycache__'))
        (checkout/'skills/four-node-review/tests/test-w5.py').unlink()
        target=self.root/'host'
        proc=subprocess.run(['bash',str(checkout/'install.sh'),str(target)],capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn('test-w5.py',proc.stderr)
        self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
