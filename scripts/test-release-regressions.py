#!/usr/bin/env python3
"""Offline regression checks. No account, network, or paid-model access."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
os.environ['PF_RECEIPT_ENV'] = 'test'
SCRIPTS = ROOT / 'skills/product-flow/scripts'
sys.path.insert(0, str(SCRIPTS))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ReleaseRegressionTests(unittest.TestCase):
    def test_privacy_scan_detects_phone_data_without_printing_it(self):
        scanner = load('privacy_phone', ROOT / 'scripts/verify-portability.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Construct synthetic input: never retain a real person's number.
            digits = '139' + '0' * 8
            for value in (digits, '联系人' + digits + '结束',
                          '+86 ' + digits[:3] + ' ' + digits[3:7] + ' ' + digits[7:]):
                (root / 'example.md').write_text('Contact: ' + value)
                findings = scanner.scan(root)
                self.assertEqual(findings, ['example.md:1: phone-like-personal-data'])
                self.assertNotIn(value, '\n'.join(findings))
            (root / 'example.md').write_text('Contact: <PHONE>; hash: a' + digits + 'b')
            self.assertEqual(scanner.scan(root), [])

    def test_project_gate_can_read_its_own_preserved_transcript(self):
        import contextlib
        import io
        gate = load('project_transcript', SCRIPTS / 'consistency-gate.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(gate.run_project(temp), 0)
            transcript = root / 'commands.md'
            transcript.write_text('# Actual tool output\n```text\n' + output.getvalue() + '```\n')
            record = root / '.product-flow/runs/run-1/gates/consistency-gate.py.json'
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({'gate': 'consistency-gate.py', 'exitCode': 0,
                                          'stdout': output.getvalue()}, ensure_ascii=False))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.run_project(temp), 0)
            # Logs are not blanket-excluded: an actual claim beside the transcript still fails.
            transcript.write_text(transcript.read_text() + '\n本轮状态：integrated-frozen。\n')
            self.assertFalse(gate.p_claim_ladder(temp)[0])
            (root / 'built.css').write_text('/* 自动生成，勿手改 */\nbody{}')
            self.assertFalse(gate.p_gen(temp)[0])

    def test_research_index_does_not_collapse_duplicate_or_mismatched_features(self):
        gate = load('report_index', SCRIPTS / 'report-structure-gate.py')
        golden = SCRIPTS.parent / 'tests/s2-golden'
        source = (golden / 'report.md').read_text()
        row = next(x for x in source.splitlines() if x.startswith('| `AF-001`') and 'EVENT-001' in x)
        args = (None, str(golden / 'evidence-manifest.json'), str(golden / 'traversal-events.json'))
        self.assertEqual(gate.check_teardown(source, *args), [])
        cases = [(source.replace(row, row + '\n' + row), 'duplicate-af'),
                 (source.replace(row, row + '\n' + row.replace('`AF-001`', '`AF-002`')), 'shared-feature-body'),
                 (source.replace(row, row.replace('SHOT-001', 'SHOT-002')), 'body-evidence-mismatch')]
        for changed, criterion in cases:
            self.assertIn(criterion, {key for key, _ in gate.check_teardown(changed, *args)})

    def test_readback_preserves_meaning_order_and_code(self):
        from _feishu import verify_readback
        source = '# Report\n\n允许访问。\n\n第一段\n\n第二段\n\n```py\nx = 1\n```\n'
        for other in (source.replace('允许', '禁止'), source.replace('第一段\n\n第二段', '第二段\n\n第一段'),
                      source.replace('x = 1', 'x = 2'), source.replace('第一段\n\n', '')):
            self.assertFalse(verify_readback(source, other)[0])
        self.assertTrue(verify_readback(source, source)[0])

    def test_receipt_becomes_invalid_after_latest_failure_or_reregistration(self):
        import _document_sync as sync
        guard = sync.guard()
        checker = load('receipt_regression', SCRIPTS / 'receipt-check.py')
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'source.md')
            Path(source).write_text('# Report\n\n允许访问。')
            guard.cmd_record(source, 'synthetic-document', 'feishu')
            self.assertEqual(guard.cmd_check(source, None), 2)
            response = {'markdown': Path(source).read_text(), 'revision_id': '7', 'native_revision': True}
            with patch.object(guard, '_platform_read', return_value=(response, None)):
                self.assertEqual(guard.cmd_readback(source), 0)
            self.assertEqual(checker.check(source + '.receipt.json')[1], [])
            response['markdown'] = '# Report\n\n禁止访问。'
            with patch.object(guard, '_platform_read', return_value=(response, None)):
                self.assertEqual(guard.cmd_readback(source), 1)
            self.assertTrue(checker.check(source + '.receipt.json')[1])
            response['markdown'] = Path(source).read_text()
            with patch.object(guard, '_platform_read', return_value=(response, None)):
                self.assertEqual(guard.cmd_readback(source), 0)
            guard.cmd_record(source, 'synthetic-document', 'feishu')
            self.assertTrue(checker.check(source + '.receipt.json')[1])

    def test_final_readback_revision_cannot_race_media(self):
        import _document_sync as sync
        guard = sync.guard()
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'source.md')
            Path(source).write_text('# Report\n\nBody')
            guard.cmd_record(source, 'synthetic-document', 'feishu')
            for native, revision in [(True, '8'), (False, '7')]:
                sync.begin_attempt(source)
                with patch.object(guard, '_platform_read', return_value=(
                        {'markdown': Path(source).read_text(), 'revision_id': revision, 'native_revision': native}, None)):
                    self.assertEqual(guard.cmd_readback(source, expected_revision='7'), 1)
            self.assertFalse(Path(source + '.receipt.json').exists())

    def test_all_supported_images_require_local_evidence_before_write(self):
        import _document_sync as sync
        forms = ['![A](a.png)', '![A](<@./a.png>)', '![A][i]\n\n[i]: a.png',
                 '<img src="a.png" alt="A">', '<image path="a.png"/>']
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'source.md')
            for form in forms:
                Path(source).write_text('# Report\n\n' + form)
                self.assertEqual(len(sync.media_sources(Path(source).read_text())), 1)
                with self.assertRaises(RuntimeError): sync.preflight(source, None)

    def test_media_identity_section_and_version_are_bound(self):
        import _document_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, manifest, upload, picture = (root / p for p in ('r.md', 'e.json', 'upload.json', 'a.png'))
            picture.write_bytes(b'synthetic-image-fixture-not-a-real-screenshot')
            source.write_text('# Report\n## Feature\n![A](a.png)')
            sync.begin_attempt(str(source))
            digest = sync.source_hash(picture)
            upload.write_text(json.dumps({'sourceHash': digest, 'mediaId': 'media-1'}))
            payload = {'evidence': [{'id': 'SHOT-1', 'sourcePath': 'a.png', 'anchor': 'Feature'}],
                       'delivery': {'document': 'doc-1', 'nativeVersion': '7',
                                    'uploadEvidenceRef': 'upload.json', 'uploadEvidenceHash': sync.source_hash(upload),
                                    'images': [{'evidenceId': 'SHOT-1', 'sourceHash': digest, 'mediaId': 'media-1'}]}}
            manifest.write_text(json.dumps(payload))
            for native in ('<heading>Feature</heading><image token="media-1"/>',
                           {'blocks': [{'type': 'heading', 'text': 'Feature'}, {'type': 'image', 'mediaId': 'media-1'}]}):
                sync.verify_media_delivery(str(source), str(manifest), native, 'doc-1', '7')
            for native, revision in [('<heading>Other</heading><image token="media-1"/>', '7'),
                                     ('<heading>Feature</heading><image token="wrong"/>', '7'),
                                     ('<heading>Feature</heading><image token="media-1"/><image token="extra"/>', '7'),
                                     ('<heading>Feature</heading><image token="media-1"/>', '8')]:
                with self.assertRaises(RuntimeError):
                    sync.verify_media_delivery(str(source), str(manifest), native, 'doc-1', revision)
            source.write_text('# Report\n## Other\n![A](a.png)\n## Feature\nText')
            with self.assertRaisesRegex(RuntimeError, '源图实际所在章节'):
                sync.verify_media_delivery(str(source), str(manifest),
                    '<heading>Feature</heading><image token="media-1"/>', 'doc-1', '7')
            source.write_text('# Report\n## Feature\n![A](a.png)')
            picture.write_bytes(b'changed-image')
            attempt = json.loads(Path(str(source) + '.attempt.json').read_text())
            with self.assertRaises(RuntimeError):
                sync.current_media_validation(str(source), attempt, 'doc-1', '7')

    def test_feishu_full_offline_chain_accepts_native_images_and_rejects_loss(self):
        import _feishu as adapter
        import _document_sync as sync
        checker = load('chain_receipt', SCRIPTS / 'receipt-check.py')
        for variant in ('good', 'no-image', 'changed-body'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory(prefix='document path ') as temp:
                root = Path(temp)
                source, manifest, upload, picture = (root / p for p in ('report with spaces.md', 'e.json', 'upload.json', 'a.png'))
                from PIL import Image
                Image.new('RGB', (16, 16), 'white').save(picture)
                body = '# Report\n\n允许访问。\n\n## Feature\n<!-- evidence:SHOT-1 -->\n![SHOT-1](<@./a.png>)\n'
                source.write_text(body)
                digest = sync.source_hash(picture)
                upload.write_text(json.dumps({'sourceHash': digest, 'mediaId': 'media-1'}))
                (root / 'events.json').write_text(json.dumps({'events': [
                    {'id': 'EVENT-1', 'evidenceId': 'SHOT-1', 'classification': 'observed'}]}))
                manifest.write_text(json.dumps({'evidence': [{'id': 'SHOT-1', 'sourcePath': 'a.png', 'anchor': 'Feature',
                    'kind': 'gui-screenshot', 'eventsRef': 'events.json', 'eventId': 'EVENT-1',
                    'privacyReviewed': True, 'privacyReview': {'actorType': 'agent', 'reviewer': 'synthetic-review',
                    'reviewedAt': '2026-09-23', 'scope': 'synthetic blank pixels', 'result': 'APPROVED'}}],
                    'delivery': {'document': 'doc-1', 'nativeVersion': '7', 'uploadEvidenceRef': 'upload.json',
                    'uploadEvidenceHash': sync.source_hash(upload),
                    'images': [{'evidenceId': 'SHOT-1', 'sourceHash': digest, 'mediaId': 'media-1'}]}}))
                remote_md = body.replace('![SHOT-1](<@./a.png>)', '<image token="media-1"/>')
                if variant == 'changed-body': remote_md = remote_md.replace('允许', '禁止')
                native = '<title>Report</title><heading>Feature</heading>'
                if variant != 'no-image': native += '<image token="media-1"/>'
                def command(args, *, cwd=None):
                    if args[0] == 'whoami': data = {'identity': 'user', 'available': True, 'tokenStatus': 'ready'}
                    elif '+create' in args:
                        self.assertEqual(cwd, str(root))
                        self.assertEqual(args[args.index('--content') + 1], '@./report with spaces.md')
                        data = {'document_id': 'doc-1'}
                    elif '+fetch' in args:
                        data = {'content': native if args[-1] == 'xml' else remote_md, 'revision_id': '7'}
                    else: self.fail('unexpected command: ' + repr(args))
                    return subprocess.CompletedProcess(args, 0, json.dumps(data), '')
                with patch.object(adapter, '_run', side_effect=command), patch.object(sync.guard(), '_platform_read',
                        return_value=({'markdown': remote_md, 'revision_id': '7', 'native_revision': True}, None)):
                    _, ok, issues = adapter.create_and_verify('Report', str(source), evidence_manifest=str(manifest))
                self.assertEqual(ok, variant == 'good', issues)
                if ok:
                    self.assertEqual(checker.check(str(source) + '.receipt.json')[1], [])
                else:
                    self.assertFalse(Path(str(source) + '.receipt.json').exists())
                    receipt = json.loads(Path(str(source) + '.delivery-receipt.json').read_text())
                    self.assertEqual(receipt['status'], 'FAIL')

    def test_failed_renderer_preserves_existing_image(self):
        renderer = load('renderer_preservation', SCRIPTS.parent / 'modules/diagramming/scripts/chrome-svg-to-png.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source, target = root / 'a.svg', root / 'a.png'
            source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>')
            target.write_bytes(b'PREVIOUS_SYNTHETIC_IMAGE')
            with patch.object(renderer, 'browser', return_value='synthetic-browser'), patch.object(renderer.subprocess, 'Popen') as start:
                start.return_value.poll.return_value = 1
                start.return_value.communicate.return_value = ('', 'synthetic render failure')
                with self.assertRaisesRegex(RuntimeError, 'render failed'):
                    renderer.render(source, target, 100)
            self.assertEqual(target.read_bytes(), b'PREVIOUS_SYNTHETIC_IMAGE')

    def test_privacy_scan_checks_names_directory_and_broken_links(self):
        scanner = load('privacy_paths', ROOT / 'scripts/verify-portability.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'PRIVATE_SYNTHETIC.txt').write_text('neutral')
            (root / 'outside-link').symlink_to(root.parent, target_is_directory=True)
            (root / 'missing-link').symlink_to(root / 'missing')
            results = scanner.scan(root, ['PRIVATE_SYNTHETIC'])
            self.assertEqual(len(results), 3)

    def test_prd_algorithm_table_has_nine_cells(self):
        from markdown_it import MarkdownIt
        text = (SCRIPTS.parent / 'templates/prd-complete.md').read_text()
        from _section import table_rows_at, section_at
        # Column alignment is a structural property, independent of placeholder values.
        rows = table_rows_at(section_at(text, 'B.2 算法能力边界'), '能力项')
        self.assertTrue(rows)
        self.assertTrue(all(len(row) == 9 for row in rows))

    def test_decisions_must_match_the_role_cell_exactly(self):
        specs = [('s8-solution-plan', 's8-solution-gate', ['研发总监', '算法负责人', '测试负责人']),
                 ('s9-quality-report', 's9-quality-report-gate', ['测试负责人', '研发负责人', '算法负责人']),
                 ('s9-product-walkthrough', 's9-product-walkthrough-gate', ['产品负责人', '设计负责人', '测试负责人']),
                 ('s9-launch-rollback', 's9-launch-rollback-gate', ['研发总监', '测试负责人', '产品负责人'])]
        for fixture, name, roles in specs:
            gate = load(name, SCRIPTS / (name + '.py'))
            text = (SCRIPTS.parent / 'tests/fixtures/filled' / (fixture + '.md')).read_text()
            self.assertEqual(gate.check(text), [])
            for field in ('agent', 'SYNTHETIC-AUTH-001', 'fixture-v1', 'synthetic-scope', 'synthetic-approval.json'):
                with self.subTest(gate=name, missing_approval_field=field):
                    self.assertTrue(gate.check(text.replace(field, '待填写')))
            for role in roles:
                for decision in ('未批准', '待批准', '拒绝', '引用他人批准', '不一致'):
                    lines = text.splitlines()
                    hits = 0
                    for i, line in enumerate(lines):
                        cells = line.split('|')
                        if line.startswith('|') and cells[1].strip().split('/')[0] == role:
                            hits += 1
                            cells[2] = decision
                            lines[i] = '|'.join(cells)
                    self.assertEqual(hits, 1)
                    with self.subTest(gate=name, role=role, decision=decision):
                        self.assertTrue(any(role in error for error in gate.check('\n'.join(lines))))

    def test_gate_evidence_binds_content_and_directory_membership(self):
        from _workflow import gate_evidence, evidence_current, output_was_tested
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rule = root / 'gate.py'; rule.write_text('synthetic rule')
            inputs = root / 'inputs'; inputs.mkdir()
            target = inputs / 'report.md'; target.write_text('before')
            evidence = gate_evidence(str(rule), [str(inputs)])
            self.assertTrue(evidence_current(evidence))
            self.assertTrue(output_was_tested(str(target), evidence))
            target.write_text('after')
            self.assertFalse(evidence_current(evidence))
            target.write_text('before')
            (inputs / 'new.md').write_text('new input')
            self.assertFalse(evidence_current(evidence))
            self.assertFalse(evidence_current(None))

    def test_delivery_receipt_is_not_mistaken_for_a_test_input(self):
        from _workflow import gate_evidence, evidence_current, output_was_tested
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rule = root / 'feishu-delivery-gate.py'; rule.write_text('synthetic rule')
            inputs = root / 'inputs'; inputs.mkdir()
            target, receipt = inputs / 'report.md', inputs / 'receipt.json'
            target.write_text('body'); receipt.write_text('previous receipt')
            for args in ([str(inputs), '--receipt', str(receipt)], [str(inputs), '--receipt=' + str(receipt)]):
                evidence = gate_evidence(str(rule), args)
                receipt.write_text('new receipt')
                self.assertTrue(evidence_current(evidence))
                self.assertTrue(output_was_tested(str(target), evidence))
                self.assertFalse(output_was_tested(str(receipt), evidence))

    def test_bundle_rejects_external_symlinks_for_every_resource_type(self):
        bundle = SCRIPTS.parent / 'modules/prototyping/scripts/bundle.mjs'
        for kind, markup in [('image', '<img src="asset.svg">'),
                             ('css', '<link rel="stylesheet" href="asset.css">'),
                             ('js', '<script src="asset.js"></script>'),
                             ('entry', None), ('directory', '<img src="assets/asset.svg">')]:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                demo, outside = root / 'demo', root / 'outside'
                demo.mkdir(); outside.mkdir()
                suffix = {'css': '.css', 'js': '.js'}.get(kind, '.svg')
                secret = 'SYNTHETIC_OUTSIDE_ASSET'
                asset = outside / ('asset' + suffix)
                asset.write_text(secret)
                if kind == 'entry':
                    (demo / 'index.html').symlink_to(asset)
                else:
                    (demo / 'index.html').write_text(markup)
                    if kind == 'directory':
                        (demo / 'assets').symlink_to(outside, target_is_directory=True)
                    else:
                        (demo / asset.name).symlink_to(asset)
                output = root / 'output.html'
                result = subprocess.run(['node', str(bundle), str(demo), str(output)],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                if output.exists():
                    import base64
                    self.assertNotIn(secret, output.read_text())
                    self.assertNotIn(base64.b64encode(secret.encode()).decode(), output.read_text())

    def test_platform_update_calls_guard_before_any_write(self):
        import _feishu
        import _dingtalk
        import _document_sync as sync
        for adapter in (_feishu, _dingtalk):
            with patch.object(sync, 'before_update', side_effect=RuntimeError('blocked')) as gate, \
                 patch.object(adapter, '_run') as command, \
                 patch.object(_feishu, 'verify_user_identity'):
                with self.assertRaises(RuntimeError):
                    adapter.update('synthetic-ref', 'synthetic.md', True)
                gate.assert_called_once()
                command.assert_not_called()

    def test_unrecognized_image_syntax_cannot_count_as_zero(self):
        gate = load('feishu_media', SCRIPTS / 'feishu-delivery-gate.py')
        with tempfile.TemporaryDirectory() as temp:
            source, remote = Path(temp) / 'report.md', Path(temp) / 'remote.xml'
            source.write_text('# Report\n![real image](./local.png)')
            remote.write_text('<title>Report</title>')
            self.assertTrue(gate.check(str(source), str(remote))[0])

    def test_empty_evidence_manifest_blocks_before_write(self):
        import _document_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            source, manifest = Path(temp) / 'report.md', Path(temp) / 'evidence.json'
            source.write_text('# Report\n![image](<@./local.png>)')
            manifest.write_text('{"evidence": []}')
            with self.assertRaises(RuntimeError):
                sync.preflight(str(source), str(manifest))

    def test_license_alone_does_not_clear_publication_blockers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('product-flow', 'coding-standards', 'four-node-review'):
                path = root / 'skills' / name / 'SKILL.md'
                path.parent.mkdir(parents=True)
                path.write_text('# Synthetic skill')
            (root / 'LICENSE').write_text('Synthetic test fixture; not a license grant.')
            (root / 'RELEASE_BLOCKERS.md').write_text('- [ ] Unresolved rights')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/release-audit.py'),
                                     '--publish', str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('unresolved items', result.stdout)

    def test_public_preview_does_not_imply_stable_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.preview_fixture(Path(temp))
            result = self.audit_preview(root)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('not stable-release approval', result.stdout)
            stable = subprocess.run([sys.executable, str(ROOT / 'scripts/release-audit.py'),
                                     '--publish', str(root)], capture_output=True, text=True)
            self.assertEqual(stable.returncode, 1)
            self.assertIn('unresolved items', stable.stdout)

    def test_public_preview_requires_complete_publication_checklist(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.preview_fixture(Path(temp))
            checklist = root / 'PUBLICATION_CHECKLIST.md'
            for body in ('', '- [x] PUB-1 Only one item', '- [ ] PUB-1 Not reviewed'):
                checklist.write_text(body)
                result = self.audit_preview(root)
                self.assertEqual(result.returncode, 1)
                self.assertIn('publication checklist', result.stdout)

    def test_public_preview_requires_notices_and_bounded_license_paths(self):
        for problem in ('missing-notice', 'missing-license', 'outside-path', 'missing-destination'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as temp:
                root = self.preview_fixture(Path(temp))
                manifest = root / 'licenses/sources.json'
                data = json.loads(manifest.read_text())
                if problem == 'missing-notice': (root / 'NOTICE').unlink()
                elif problem == 'missing-license': (root / 'licenses/upstream.txt').unlink()
                elif problem == 'outside-path': data['entries'][0]['licenseFile'] = '../outside.txt'
                else: data['entries'][0]['localPaths'] = ['missing.md']
                manifest.write_text(json.dumps(data))
                result = self.audit_preview(root)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertTrue('NOTICE' in result.stdout or 'source manifest' in result.stdout)

    def preview_fixture(self, root):
        for name in ('product-flow', 'coding-standards', 'four-node-review'):
            path = root / 'skills' / name / 'SKILL.md'
            path.parent.mkdir(parents=True)
            path.write_text('# Synthetic skill')
        for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY.md'):
            (root / name).write_text('Synthetic audit fixture, not a legal grant.')
        (root / 'PUBLICATION_CHECKLIST.md').write_text('\n'.join(
            '- [x] PUB-%d Synthetic reviewed item' % i for i in range(1, 6)))
        (root / 'RELEASE_BLOCKERS.md').write_text('- [ ] Real-platform validation missing')
        (root / 'licenses').mkdir()
        (root / 'licenses/upstream.txt').write_text('Synthetic license fixture.')
        (root / 'licenses/sources.json').write_text(json.dumps({'entries': [{
            'source': 'synthetic/upstream', 'revision': 'a' * 40, 'license': 'MIT',
            'licenseFile': 'licenses/upstream.txt', 'localPaths': ['skills/product-flow/SKILL.md'],
            'kind': 'synthetic adaptation', 'changes': 'test fixture'}]}))
        return root

    def audit_preview(self, root):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/release-audit.py'),
                               '--public-preview', str(root)], capture_output=True, text=True)

    def test_readback_rejects_column_loss_and_heading_loss(self):
        import _feishu
        source = '# Report\n\n' + 'body ' * 100 + '\n|a|b|c|d|\n|---|---|---|---|\n|1|2|3|4|\n## Details\ntext'
        collapsed = source.replace('|a|b|c|d|\n|---|---|---|---|\n|1|2|3|4|', '|a|b|\n|---|---|\n|1|2|')
        self.assertFalse(_feishu.verify_readback(source, collapsed)[0])
        self.assertFalse(_feishu.verify_readback(source, source.replace('## Details', 'Details'))[0])
        self.assertTrue(_feishu.verify_readback(source, source)[0])

    def test_media_requires_images_and_deduplicates_fetch_inspect(self):
        gate = load('media_gate', SCRIPTS / 'dingtalk-delivery-gate.py')
        image = {'type': 'image', 'mediaId': 'synthetic-image-id'}
        self.assertEqual(gate._media_entities({'fetch': [image], 'inspect': [image]}), 1)
        self.assertEqual(gate._media_entities({'type': 'media', 'mediaId': 'synthetic-audio-id'}), 0)
        self.assertEqual(gate._media_entities({'type': 'image', 'fileName': 'missing.png'}), 0)

    def test_privacy_scan_includes_scanners_extensionless_and_binary(self):
        scanner = load('privacy', ROOT / 'scripts/verify-portability.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'scripts').mkdir()
            term = 'SYNTHETIC_PRIVATE_SENTINEL'
            for name in ('scripts/verify-portability.py', 'NOTICE', 'image.svg', 'asset.bin'):
                (root / name).write_bytes(term.encode())
            self.assertEqual(len(scanner.scan(root, [term])), 4)
            self.assertEqual(scanner.scan(root, ['OTHER_SENTINEL']), [])

    def test_synthetic_exception_does_not_hide_second_credential(self):
        scanner = load('privacy_exception', ROOT / 'scripts/verify-portability.py')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'skills/product-flow/scripts/sec-scan.py'
            path.parent.mkdir(parents=True)
            assignment = 'api' + '_key = '
            path.write_text(assignment + repr('sk-live-abcdef123456789') + '; ' +
                            assignment + repr('SYNTHETIC_SECRET_SENTINEL_1234'))
            self.assertEqual(len(scanner.scan(root)), 1)

    def test_new_document_cannot_duplicate_recorded_canonical(self):
        import _document_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'report.md')
            Path(source).write_text('# Report')
            Path(source + '.sync.json').write_text(json.dumps({'url': 'synthetic-ref'}))
            with self.assertRaises(RuntimeError):
                sync.before_create(source)

    def test_update_requires_verified_baseline_and_explicit_overwrite(self):
        import _document_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'report.md')
            Path(source).write_text('# Report')
            with self.assertRaises(RuntimeError):
                sync.before_update(source, 'feishu', 'synthetic-ref', False)
            Path(source + '.sync.json').write_text(json.dumps({
                'kind': 'feishu', 'url': 'synthetic-ref', 'remote_revision': '1'}))
            with patch.object(sync.guard(), 'cmd_lease') as lease:
                with self.assertRaises(RuntimeError):
                    sync.before_update(source, 'feishu', 'synthetic-ref', True)
                lease.assert_not_called()

    def test_drift_blocks_write_and_failed_verification_cannot_issue_receipt(self):
        import _document_sync as sync
        with tempfile.TemporaryDirectory() as temp:
            source = str(Path(temp) / 'report.md')
            Path(source).write_text('# Report')
            Path(source + '.sync.json').write_text(json.dumps({
                'kind': 'feishu', 'url': 'synthetic-ref', 'remote_revision': '1',
                'lastReadbackAt': 'synthetic-time', 'validationStatus': 'PASS'}))
            with patch.object(sync.guard(), 'cmd_lease', return_value=1):
                with self.assertRaises(RuntimeError):
                    sync.before_update(source, 'feishu', 'synthetic-ref', True)
            with patch.object(sync.guard(), 'cmd_readback') as readback:
                self.assertFalse(sync.finish(source, False, ['bad media'])[0])
                readback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
