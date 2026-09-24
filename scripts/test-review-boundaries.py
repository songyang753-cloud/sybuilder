"""Regression probes from the external review; all data and approvals synthetic.

No platform requests, user profiles, production services or real approval records.
"""
import contextlib
import copy
from datetime import datetime, timezone
import importlib.util
import io
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / 'skills/product-flow/scripts'
sys.path.insert(0, str(S))
from _document_sync import preflight, source_hash
from _mutation_state import recover, save_journal, state_path, locked_targets
from _workflow import resolve_plan, suite_script, WorkflowError


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sybuilder-review-boundaries-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def approved_fixture(self, platform='feishu'):
        gold = S.parent / 'tests/s2-golden'
        for name in ('report.md', 'shot.png', 'evidence-manifest.json', 'traversal-events.json'):
            shutil.copyfile(gold / name, self.root / name)
        dest = {'platform': platform, 'document': 'new:Synthetic approval test only'}
        path = self.root / 'evidence-manifest.json'
        payload = json.loads(path.read_text())
        item = payload['evidence'][0]
        item.update(privacyReviewed=True, privacyReview={
            'actorType': 'agent', 'reviewer': 'synthetic-fixture', 'method': 'schema-only',
            'reviewedAt': datetime.now(timezone.utc).isoformat(), 'result': 'APPROVED',
            'scope': item['sourcePath'], 'evidenceId': item['id'], 'destination': dest,
            'sourceBindings': {k: source_hash(self.root / item[k]) for k in ('sourcePath', 'eventsRef')}})
        path.write_text(json.dumps(payload))
        return self.root / 'report.md', path, payload, dest

    def test_privacy_binding_rejects_wrong_scope_date_bytes_and_destination(self):
        source, path, good, dest = self.approved_fixture()
        preflight(source, path, destination=dest)
        for key, value in [('scope', 'another.png'), ('reviewedAt', '1900-01-01T00:00:00Z'),
                           ('evidenceId', 'SHOT-999'), ('sourceBindings', {}),
                           ('destination', {'platform':'dingtalk', 'document':'another'})]:
            with self.subTest(key=key):
                changed = copy.deepcopy(good); changed['evidence'][0]['privacyReview'][key] = value
                path.write_text(json.dumps(changed))
                with self.assertRaises(RuntimeError): preflight(source, path, destination=dest)
        path.write_text(json.dumps(good))
        from PIL import Image
        Image.new('RGB', (300, 200), 'red').save(self.root / 'shot.png')
        with self.assertRaisesRegex(RuntimeError, '不匹配'): preflight(source, path, destination=dest)

    def test_nested_evidence_privacy_blocks_both_platforms_before_api(self):
        for platform in ('feishu', 'dingtalk'):
            with self.subTest(platform=platform):
                source, path, payload, dest = self.approved_fixture(platform)
                events = self.root / 'traversal-events.json'
                data = json.loads(events.read_text())
                secret = '13' + '800' + '138' + '000'  # synthetic pattern, never a real contact
                data['derived'] = {'nested': [{'value': secret}]}
                events.write_text(json.dumps(data))
                payload['evidence'][0]['privacyReview']['sourceBindings']['eventsRef'] = source_hash(events)
                path.write_text(json.dumps(payload))
                adapter = __import__('_' + platform)
                with patch.object(adapter, 'create') as api:
                    with self.assertRaisesRegex(RuntimeError, '隐私'):
                        adapter._write_and_verify('Synthetic approval test only', str(source), evidence_manifest=str(path))
                    api.assert_not_called()
                self.assertNotIn(secret, str(payload))

    def test_private_denylist_decodes_nested_json_and_allows_public_contact(self):
        source, path, data, dest = self.approved_fixture()
        source.write_text(source.read_text() + '\nPublic help: support@example.test\n')
        preflight(source, path, destination=dest)
        with tempfile.TemporaryDirectory() as private:
            deny = Path(private) / 'terms.txt'; deny.write_text('合成私有标识')
            events = self.root / 'traversal-events.json'
            payload = json.loads(events.read_text()); payload['nested'] = {'x':'合成私有标识'}
            events.write_text(json.dumps(payload, ensure_ascii=True))
            with patch.dict(os.environ, {'SYBUILDER_PRIVATE_DENYLIST': str(deny)}):
                with self.assertRaisesRegex(RuntimeError, '隐私'): preflight(source, path, destination=dest)

    def test_manifest_metadata_is_part_of_outbound_privacy_scan(self):
        for platform in ('feishu','dingtalk'):
            source, path, payload, dest = self.approved_fixture(platform)
            payload['private_note'] = {'nested':['13'+'800'+'138'+'000']}
            path.write_text(json.dumps(payload))
            adapter = __import__('_'+platform)
            with patch.object(adapter,'create') as api:
                with self.assertRaisesRegex(RuntimeError,'隐私'):
                    adapter._write_and_verify('Synthetic approval test only',str(source),evidence_manifest=str(path))
                api.assert_not_called()

    def test_recovery_binding_and_user_changes_never_overwritten(self):
        for mutation in ('target', 'originalHash', 'user-edit', 'symlink'):
            with self.subTest(mutation=mutation):
                target = self.root / (mutation + '.txt'); target.write_text('original')
                journal = state_path('journal', target)
                save_journal(target, 'original', 'mutated')
                target.write_text('mutated')
                other = self.root / (mutation + '-other'); other.write_text('preserve')
                if mutation in ('target', 'originalHash'):
                    record = json.loads(journal.read_text())
                    record[mutation] = str(other) if mutation == 'target' else 'bad-hash'
                    journal.write_text(json.dumps(record))
                elif mutation == 'user-edit':
                    target.write_text('user edit')
                else:
                    journal.unlink(); journal.symlink_to(other)
                before = target.read_bytes()
                with self.assertRaises((RuntimeError, OSError)): recover(target)
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(other.read_text(), 'preserve')
                self.assertTrue(journal.exists())
                journal.unlink()  # only the synthetic recovery evidence from this test
        target = self.root / 'valid.txt'; target.write_text('mutated')
        save_journal(target, 'original', 'mutated')
        recover(target); self.assertEqual(target.read_text(), 'original')

    @unittest.skipUnless(os.name == 'posix', 'POSIX mutation locks')
    def test_shared_tree_lock_serializes_different_targets_and_hard_kill_recovers(self):
        (self.root / 'SKILL.md').write_text('# synthetic')
        target = self.root / 'one.txt'; target.write_text('original')
        other = self.root / 'two.txt'; other.write_text('second')
        signal_file = self.root / 'acquired'
        code = ('import sys;sys.path.insert(0,sys.argv[1]);from _mutation_state import locked_targets;'
                'from pathlib import Path\nwith locked_targets([sys.argv[2]]): Path(sys.argv[3]).touch()')
        with locked_targets([target]):
            proc = subprocess.Popen([sys.executable, '-c', code, str(S), str(other), str(signal_file)])
            time.sleep(.2); self.assertFalse(signal_file.exists())
        proc.wait(timeout=5); self.assertTrue(signal_file.exists())
        ready = self.root / 'ready'
        code = ('import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                'from _mutation_state import locked_targets,save_journal\n'
                'with locked_targets([sys.argv[2]]):\n'
                ' save_journal(sys.argv[2],"original","mutated");Path(sys.argv[2]).write_text("mutated");'
                'Path(sys.argv[3]).touch();time.sleep(30)\n')
        proc = subprocess.Popen([sys.executable, '-c', code, str(S), str(target), str(ready)])
        try:
            until = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < until: time.sleep(.02)
            self.assertTrue(ready.exists())
            proc.kill(); proc.wait(timeout=5)
            with locked_targets([target]): recover(target)
            self.assertEqual(target.read_text(), 'original')
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()

    def test_tech_routes_and_real_image_decoding(self):
        for mode in ('full', 'from', 'only'):
            plan = resolve_plan(mode, ['S2'] if mode == 'only' else [], start='S2', research_mode='tech-approach')
            self.assertIn('tech-research-gate.py', plan['requiredGates'])
            self.assertNotIn('traversal-coverage-gate.py', plan['requiredGates'])
            self.assertNotIn('report-structure-gate.py', plan['requiredGates'])
            self.assertTrue(any(x['artifact']=='research/report.md' for x in plan['expectedOutputs']))
        gate = load('tech_bounds', S / 'tech-research-gate.py')
        gate._mk_fixture(str(self.root), n_objs=1)
        source = self.root / 'report.md'
        source.write_text(source.read_text().replace('## 2.', '### 2.'))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.check_pre(str(self.root)), 0)
            (self.root / 'figs/o1-intent.png').write_text('This is not an image.')
            self.assertEqual(gate.check_pre(str(self.root)), 1)

    @unittest.skipUnless(os.name == 'posix', 'POSIX owned subprocesses')
    def test_reverse_timeout_and_sigterm_restore_without_claiming_mutation_success(self):
        target = self.root/'target.txt'; target.write_text('original')
        ready = self.root/'child-ready'
        command = ('import sys,time;from pathlib import Path\n'
                   'if Path(sys.argv[1]).read_text()=="mutated":\n'
                   ' Path(sys.argv[2]).touch();time.sleep(30)\n')
        args = [sys.executable,str(S/'reverse-test.py'),str(target),'--replace','original','mutated',
                '--',sys.executable,'-c',command,str(target),str(ready)]
        for terminate in (False, True):
            ready.unlink(missing_ok=True)
            env = dict(os.environ, REVTEST_TIMEOUT='10' if terminate else '1')
            proc = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                if terminate:
                    until = time.monotonic()+5
                    while not ready.exists() and time.monotonic()<until: time.sleep(.02)
                    self.assertTrue(ready.exists()); proc.terminate()
                stdout, stderr = proc.communicate(timeout=7)
                self.assertEqual(proc.returncode,2,(stdout,stderr))
                self.assertEqual(target.read_text(),'original')
                self.assertFalse(state_path('journal',target).exists())
                self.assertNotIn('✅ 判据承重',stdout)
            finally:
                if proc.poll() is None: proc.kill(); proc.communicate()

    def test_tech_post_cannot_pass_keyword_only_body_or_missing_media(self):
        gate = load('tech_post_bounds', S / 'tech-research-gate.py')
        gate._mk_fixture(str(self.root), n_objs=1)
        scope = self.root / 'scope.md'
        original = scope.read_text()
        source = (self.root / 'report.md').read_text()
        for platform in ('feishu', 'dingtalk'):
            scope.write_text(original + '\ndocumentPlatform: '+platform+'\ndelivery_doc: synthetic-doc\n')
            adapter = __import__('_' + platform)
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                if platform == 'feishu':
                    call = stack.enter_context(patch.object(adapter, 'fetch_data', side_effect=lambda _, fmt:
                        {'version':'1','content':'执行摘要 2.1 方案收敛' if fmt=='markdown' else '<title>Only title</title>'}))
                else:
                    call = stack.enter_context(patch.object(adapter, 'fetch', return_value=('执行摘要 2.1 方案收敛', {'version':'1'})))
                    stack.enter_context(patch.object(adapter, 'inspect_media', return_value={'version':'1','blocks':[]}))
                self.assertEqual(gate.check_post(str(self.root)), 1)
                if platform == 'feishu':
                    call.side_effect = lambda _, fmt: {'version':'1','content':source if fmt=='markdown' else '<title>Only title</title>'}
                else:
                    call.return_value = (source, {'version':'1'})
                self.assertEqual(gate.check_post(str(self.root)), 2)

    @unittest.skipUnless(os.name == 'posix', 'POSIX cross-tool locks')
    def test_actual_mutation_tools_in_different_checkouts_share_external_target_lock(self):
        shared = self.root/'shared'; shared.mkdir()
        target = shared/'gate.py'; marker = self.root/'snapshot-observed'
        original = ('# original\nfrom pathlib import Path\n'
                    f'Path({str(marker)!r}).write_text("original" if "# original" in Path(__file__).read_text().splitlines()[0] else "mutated")\n'
                    'def check(value):\n bad=[]\n if value<0:\n  bad.append("negative")\n return bad\n'
                    'assert check(-1)\nassert not check(1)\n')
        target.write_text(original)
        checkouts=[]
        for index, script in enumerate(('reverse-test.py','mutation-sweep.py')):
            root = self.root/('checkout-'+str(index)); (root/'scripts').mkdir(parents=True)
            (root/'SKILL.md').write_text('# Synthetic installation')
            for filename in (script,'_mutation_state.py'):
                shutil.copyfile(S/filename,root/'scripts'/filename)
            checkouts.append(root/'scripts'/script)
        ready=self.root/'reverse-running'; entered=self.root/'sweep-started'
        command=('import sys,time;from pathlib import Path\n'
                 'if Path(sys.argv[1]).read_text().splitlines()[0]=="# mutated":\n'
                 ' Path(sys.argv[2]).touch();time.sleep(30)\n')
        reverse=subprocess.Popen([sys.executable,str(checkouts[0]),str(target),'--replace','# original','# mutated',
            '--',sys.executable,'-c',command,str(target),str(ready)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        sweep=None
        try:
            until=time.monotonic()+5
            while not ready.exists() and time.monotonic()<until: time.sleep(.02)
            self.assertTrue(ready.exists())
            runner=('import sys,importlib.util;from pathlib import Path;sys.path.insert(0,str(Path(sys.argv[1]).parent));'
                    's=importlib.util.spec_from_file_location("sweep",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                    'Path(sys.argv[3]).touch();sys.exit(m.sweep([sys.argv[2]]))')
            sweep=subprocess.Popen([sys.executable,'-c',runner,str(checkouts[1]),str(target),str(entered)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            until=time.monotonic()+5
            while not entered.exists() and time.monotonic()<until: time.sleep(.02)
            self.assertTrue(entered.exists()); time.sleep(.2)
            self.assertFalse(marker.exists(),'sweep must not snapshot/run a target held by reverse-test')
            reverse.terminate(); reverse.communicate(timeout=5)
            stdout,stderr=sweep.communicate(timeout=10)
            self.assertEqual(reverse.returncode,2)
            self.assertEqual(sweep.returncode,0,(stdout,stderr))
            self.assertEqual(marker.read_text(),'original')
            self.assertEqual(target.read_text(),original)
        finally:
            for proc in (reverse,sweep):
                if proc is not None and proc.poll() is None: proc.kill();proc.communicate()

    def test_merge_failures_never_reach_gates(self):
        gate = load('coord_bounds', S / 'coordination-gate.py')
        for failed in ('clone', 'checkout', 'rev-parse', 'merge', 'diff'):
            with self.subTest(failed=failed):
                def git(args, **kwargs):
                    return (128, '', 'synthetic failure') if args[0]==failed else (0, '', '')
                with patch.object(gate, '_git', side_effect=git), patch.object(gate.subprocess, 'run') as run:
                    verdict, issues = gate.merge_check('synthetic-ref')
                    self.assertIsNone(verdict); self.assertTrue(issues); run.assert_not_called()

    def test_tech_post_positive_and_wrong_image_fail_on_both_platforms(self):
        from html import escape
        from _document_sync import media_contexts
        gate = load('tech_post_positive', S/'tech-research-gate.py')
        gate._mk_fixture(str(self.root), n_objs=1)
        scope = self.root/'scope.md'; original = scope.read_text()
        source = (self.root/'report.md').read_text()
        evidence, images, blocks = [], [], []
        for i, (_, path, anchor) in enumerate(media_contexts(source)):
            eid, mid, digest = 'FIG-'+str(i), 'synthetic-media-'+str(i), source_hash(self.root/path)
            evidence.append({'id':eid,'sourcePath':path,'anchor':anchor})
            images.append({'evidenceId':eid,'mediaId':mid,'sourceHash':digest})
            blocks += [{'type':'heading','text':anchor}, {'type':'image','mediaId':mid}]
        upload = self.root/'upload.json'; upload.write_text(json.dumps(images))
        (self.root/'evidence-manifest.json').write_text(json.dumps({'evidence':evidence,'delivery':{
            'document':'synthetic-doc','nativeVersion':'1','images':images,
            'uploadEvidenceRef':'upload.json','uploadEvidenceHash':source_hash(upload)}}))
        xml = ''.join('<heading>'+escape(b['text'])+'</heading>' if b['type']=='heading'
                      else '<image token="'+b['mediaId']+'"/>' for b in blocks)
        for platform in ('feishu','dingtalk'):
            scope.write_text(original+'\ndocumentPlatform: '+platform+'\ndelivery_doc: synthetic-doc\n')
            adapter = __import__('_'+platform)
            with contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
                if platform == 'feishu':
                    fetch = stack.enter_context(patch.object(adapter, 'fetch_data', side_effect=lambda _,fmt:
                        {'version':'1','content':source if fmt=='markdown' else xml}))
                else:
                    stack.enter_context(patch.object(adapter,'fetch',return_value=(source,{'version':'1'})))
                    fetch = stack.enter_context(patch.object(adapter,'inspect_media',return_value={'version':'1','blocks':blocks}))
                self.assertEqual(gate.check_post(str(self.root)), 0)
                if platform == 'feishu':
                    fetch.side_effect = lambda _,fmt: {'version':'1','content':source if fmt=='markdown' else xml.replace('synthetic-media-0','wrong')}
                else:
                    wrong = copy.deepcopy(blocks); wrong[1]['mediaId'] = 'wrong'
                    fetch.return_value = {'version':'1','blocks':wrong}
                self.assertEqual(gate.check_post(str(self.root)), 1)

    def test_design_only_does_not_claim_product_execution(self):
        gate = load('coverage_bounds', S / 'coverage_check.py')
        (self.root/'cases').mkdir()
        (self.root/'requirements.md').write_text('FR-001 空名称不创建，显示请输入名称。\n')
        (self.root/'readiness.md').write_text('当前无未解决规格缺口。')
        (self.root/'cases/one.md').write_text('### TC-001-1 所属 FR-001 **未执行**\n**未执行理由**：只交付设计，没有被测实现。\n')
        argv=['coverage', str(self.root/'requirements.md'), str(self.root/'cases'), '--gaps', str(self.root/'readiness.md'), '-o', str(self.root/'result.json')]
        with contextlib.redirect_stdout(io.StringIO()):
            with patch.object(sys, 'argv', argv): self.assertEqual(gate.main(), 3)
            with patch.object(sys, 'argv', argv+['--design-only']): self.assertEqual(gate.main(), 0)
        result=json.loads((self.root/'result.json').read_text())
        self.assertEqual(result['product_execution'], 'NOT_VERIFIED')
        self.assertFalse(result['coverage_means_sufficient'])

    def test_suite_helpers_require_complete_supported_install(self):
        self.assertTrue(suite_script('test-remediation-contracts.py').is_file())
        import _workflow
        with patch.object(_workflow, '__file__', str(self.root/'skills/product-flow/scripts/_workflow.py')):
            with self.assertRaisesRegex(WorkflowError, '完整'): suite_script('test-remediation-contracts.py')

    def test_mode_specific_output_templates_cannot_be_orphaned(self):
        gate = load('output_modes', S/'consistency-gate.py')
        (self.root/'references').mkdir(); (self.root/'templates').mkdir()
        (self.root/'templates/tech.md').write_text('# Technical report')
        module = {'outputs':[], 'maxClaim':'draft', 'outputsByResearchMode':{'tech-approach':['report.md']},
                  'outputKinds':{'report.md':'template'}, 'outputTemplates':{'report.md':'templates/tech.md'}}
        registry = self.root/'references/workflow-registry.json'
        registry.write_text(json.dumps({'modules':{'S2':module}}))
        self.assertTrue(gate.r_output_template(str(self.root))[0])
        (self.root/'templates/tech.md').unlink()
        verdict, issues = gate.r_output_template(str(self.root))
        self.assertFalse(verdict); self.assertIn('不存在', str(issues))


if __name__ == '__main__':
    unittest.main()
