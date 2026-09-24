#!/usr/bin/env python3
"""Offline remediation regressions; synthetic receipts never certify live delivery."""
import copy
import hashlib
import importlib.util
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
GOLD = S.parent / 'tests/s2-golden'
sys.path.insert(0, str(S))
from _document_sync import source_hash


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sybuilder-contracts-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def golden(self):
        for name in ('report.md', 'ledger.md', 'evidence-manifest.json', 'traversal-events.json', 'shot.png', 'readback.xml'):
            shutil.copy(GOLD / name, self.root / name)
        return self.root

    def test_writing_example_evidence_is_bound_to_source_and_decodable_images(self):
        from _image import validate_image
        example=S.parent/'templates/examples/report-writing'
        evidence=json.loads((example/'evidence/evidence.json').read_text())
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(evidence['sourceSha256'],digest(example/evidence['source']))
        shots=[e for e in evidence['events'] if 'image' in e]
        self.assertTrue(shots)
        self.assertEqual(len({e['id'] for e in evidence['events']}),len(evidence['events']))
        self.assertEqual(len({e['sha256'] for e in shots}),len(shots))
        for event in shots:
            path=example/'evidence'/event['image']
            self.assertEqual(event['sha256'],digest(path))
            self.assertEqual(validate_image(path),(evidence['viewport']['width'],evidence['viewport']['height']))

    def test_writing_example_images_are_real_local_report_links(self):
        import re
        example=S.parent/'templates/examples/report-writing'
        shots={e['image'] for e in json.loads((example/'evidence/evidence.json').read_text())['events'] if 'image' in e}
        links=re.findall(r'!\[[^\]]*\]\(evidence/([^\)]+)\)',(example/'research-domain.md').read_text())
        self.assertEqual(set(links),shots)
        for link in links:self.assertTrue((example/'evidence'/link).is_file())

    def test_writing_capture_refuses_existing_evidence_directory(self):
        sentinel=self.root/'preserve.txt';sentinel.write_text('existing evidence')
        script=S.parent/'templates/examples/report-writing/capture.cjs'
        result=subprocess.run(['node',str(script),'--out',str(self.root)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,1)
        self.assertIn('existing evidence is never overwritten',result.stderr)
        self.assertEqual(sentinel.read_text(),'existing evidence')

    def test_template_routing_accepts_remaining_route_but_rejects_orphan(self):
        gate=load('remediation_template_routes',S/'consistency-gate.py')
        (self.root/'templates').mkdir();(self.root/'references').mkdir()
        (self.root/'templates/intent.md').write_text('# Intent\n')
        skill=self.root/'SKILL.md';ref=self.root/'references/research.md'
        skill.write_text('Use templates/intent.md');ref.write_text('Read intent.md')
        self.assertTrue(gate.r_artifact_wired(str(self.root))[0])
        mutation=next(mut for rid,_,mut in gate.MUTATIONS if rid=='stage-artifact-wired')
        skill.write_text(mutation(skill.read_text()))
        self.assertTrue(gate.r_artifact_wired(str(self.root))[0])
        ref.write_text(mutation(ref.read_text()))
        passed,issues=gate.r_artifact_wired(str(self.root))
        self.assertFalse(passed);self.assertIn('templates/intent.md',issues[0])

    def test_public_report_routes_use_bundled_modules_and_selected_platform(self):
        template = (S.parent / 'templates/research-report.md').read_text()
        self.assertIn('scripts/_documents.py --platform feishu', template)
        self.assertIn('`dingtalk`', template)
        self.assertIn('modules/diagramming', template)
        self.assertIn('不能替代详细正文', template)
        self.assertNotIn('import _feishu', template)
        self.assertNotIn('交付件 = 飞书文档', template)
        module = (S.parent / 'modules/diagramming/MODULE.md').read_text()
        self.assertIn('diagram-id-gate.py --formal', module)
        self.assertIn('不能单独调用某个后端绕开安全检查', module)

    def test_image_valid_decode(self):
        from _image import validate_image
        w, h = validate_image(GOLD / 'shot.png')
        self.assertGreater(w, 100); self.assertGreater(h, 100)

    def test_image_header_only_rejected(self):
        from _image import validate_image
        path = self.root / 'fake.png'; path.write_bytes(b'\x89PNG\r\n\x1a\n')
        with self.assertRaisesRegex(ValueError, 'invalid evidence image'): validate_image(path)

    def test_gate_timeout_reaps_owned_session(self):
        import os
        gate=load('remediation_gate_run',S/'gate-run.py')
        command=[sys.executable,'-c','import time;print("started",flush=True);time.sleep(10)']
        result=gate.run_child(command,timeout=0.2)
        self.assertEqual(result.returncode,124)
        self.assertIn('started',result.stdout)
        self.assertIn('UNABLE: gate timed out',result.stderr)
        self.assertEqual(gate.run_child([sys.executable,'-c','print("ok")']).returncode,0)

    def test_diagram_failed_renderer_uses_fresh_fallback(self):
        import subprocess
        renderer=load('remediation_fallback',S.parent/'modules/diagramming/scripts/render-svg.py')
        svg=self.root/'simple.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200"><text x="20" y="40">Diagram</text></svg>')
        png=self.root/'out.png';png.write_bytes(b'old output')
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            if 'validate_svg.py' in command[1]:
                return subprocess.CompletedProcess(command,0,'','')
            candidate=Path(command[4] if command[1]=='-c' else command[3])
            if command[1]=='-c':
                candidate.write_bytes(b'invalid image')
                return subprocess.CompletedProcess(command,1,'','renderer error')
            self.assertFalse(candidate.exists())
            shutil.copy(GOLD/'shot.png',candidate)
            return subprocess.CompletedProcess(command,0,'fallback completed','')
        with patch.object(renderer.importlib.util,'find_spec',return_value=object()),patch.object(renderer.shutil,'which',return_value=None),patch.object(renderer.subprocess,'run',side_effect=run):
            renderer.render(svg,png)
        self.assertEqual(png.read_bytes(),(GOLD/'shot.png').read_bytes())
        self.assertEqual(len(calls),5)
        def unavailable(command,**kwargs):
            return subprocess.CompletedProcess(command,0 if 'validate_svg.py' in command[1] else 2,'','unavailable')
        with patch.object(renderer.importlib.util,'find_spec',return_value=None),patch.object(renderer.shutil,'which',return_value=None),patch.object(renderer.subprocess,'run',side_effect=unavailable):
            with self.assertRaisesRegex(RuntimeError,'UNABLE'):renderer.render(svg,png)
        self.assertEqual(png.read_bytes(),(GOLD/'shot.png').read_bytes())

    def test_diagram_chrome_nonzero_never_publishes(self):
        chrome=load('remediation_chrome',S.parent/'modules/diagramming/scripts/chrome-svg-to-png.py')
        svg=self.root/'a.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>')
        png=self.root/'a.png';png.write_bytes(b'previous')
        with patch.object(chrome,'browser',return_value='synthetic-browser'),patch.object(chrome.subprocess,'Popen') as start:
            start.return_value.poll.return_value=1
            with self.assertRaisesRegex(RuntimeError,'Chrome render failed'):chrome.render(svg,png,100)
        self.assertEqual(png.read_bytes(),b'previous')

    def test_diagram_escaped_css_cannot_bypass_resource_check(self):
        renderer=load('remediation_css',S.parent/'modules/diagramming/scripts/render-svg.py')
        svg=self.root/'external.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><style>@'+chr(92)+'69mport "https://example.invalid/a.css";</style></svg>')
        with self.assertRaisesRegex(ValueError,'escaped SVG CSS'):renderer.render(svg,self.root/'out.png')

    def test_quality_final_requires_bound_pages_and_current_receipt(self):
        gate=load('remediation_quality',S/'research-quality-gate.py')
        source=self.root/'report.md';source.write_text('# Report\n## AF-001 Create\nDetailed behavior')
        sections=['Report','AF-001 Create']
        shutil.copy(GOLD/'shot.png',self.root/'page.png')
        receipt={'receiptSchema':'2.0','adapter':{'name':'doc-sync-guard.readback'},'environment':'live',
                 'nativeVersion':'v1','sourceHash':source_hash(source),'artifactRef':'synthetic-doc'}
        receipt_path=self.root/'receipt.json';receipt_path.write_text(json.dumps(receipt))
        record={'inputs':{'report.md':source_hash(source)},'reviews':[
            {'role':role,'actorType':'agent','reviewer':'synthetic-'+role,'reviewedAt':'2026-09-23',
             'decision':'APPROVED','rationale':'Synthetic schema test, not live approval',
             'features':['AF-001'],'sections':sections} for role in ('product','ux','qa')],
            'receipt':'receipt.json','document':'synthetic-doc','nativeVersion':'v1',
            'pageSections':sections,'pageEvidence':[{'path':'page.png','sha256':source_hash(self.root/'page.png'),'nativeVersion':'v1','sections':sections}],
            'visualDecision':'APPROVED','visualRationale':'Synthetic record only'}
        review=self.root/'review.md'
        def save():review.write_text('```json\n'+json.dumps(record)+'\n```\n')
        # Isolate page/version checks; real receipt authenticity is covered by receipt-check.
        with patch('importlib.util.module_from_spec') as create:
            from types import SimpleNamespace
            fake=SimpleNamespace(check=lambda _: ([],[]))
            create.return_value=fake
            with patch('importlib.util.spec_from_file_location') as spec:
                spec.return_value.loader.exec_module=lambda _:None
                save();self.assertEqual(gate.check(source,review),[])
                record['pageEvidence'][0]['sections']=['Report'];save()
                self.assertTrue(any('review-page-coverage' in x for x in gate.check(source,review)))
                record['pageEvidence'][0]['nativeVersion']='v0';save()
                self.assertTrue(any('review-page-version' in x for x in gate.check(source,review)))
                receipt['receiptSchema']='1.0';receipt_path.write_text(json.dumps(receipt))
                self.assertTrue(any('review-receipt-schema' in x for x in gate.check(source,review)))

    def test_delivery_full_body(self):
        from _delivery_check import check
        d = self.golden()
        self.assertEqual(check(d/'report.md', d/'readback.xml', d/'evidence-manifest.json')[0], [])
        raw=(d/'readback.xml').read_text()
        for changed in (raw.replace('无需登录', '需要登录'), '<title>单品报告</title><image token="synthetic"/>'):
            (d/'readback.xml').write_text(changed)
            self.assertTrue(any('body-mismatch' in e for e in check(d/'report.md', d/'readback.xml', d/'evidence-manifest.json')[0]))

    def test_delivery_moved_or_empty_image(self):
        from _delivery_check import check
        d=self.golden(); original=(d/'readback.xml').read_text()
        (d/'readback.xml').write_text(original.replace('synthetic-offline-media-001', ''))
        self.assertTrue(any('media-count' in e for e in check(d/'report.md',d/'readback.xml',d/'evidence-manifest.json')[0]))
        (d/'readback.xml').write_text(original)
        payload=json.loads((d/'evidence-manifest.json').read_text());payload['evidence'][0]['anchor']='Wrong feature'
        (d/'evidence-manifest.json').write_text(json.dumps(payload))
        self.assertTrue(any('media-anchor' in e for e in check(d/'report.md',d/'readback.xml',d/'evidence-manifest.json')[0]))

    def test_delivery_unknown_xml_is_unable(self):
        from _delivery_check import xml_markdown
        with self.assertRaisesRegex(RuntimeError, 'unsupported native block'):
            xml_markdown('<unknown-table>lost cells</unknown-table>')

    def diagram(self):
        generator=load('remediation_generator', S.parent/'modules/diagramming/scripts/generate-from-template.py')
        data={'schemaVersion':1,'diagramId':'DIA-1','diagramType':'functional-architecture','targetSection':'6.2',
              'style':1,'width':1200,'height':800,'title':'Synthetic graph',
              'nodes':[{'id':'F-01','label':'F-01 Start','x':100,'y':200,'width':250,'height':90},
                       {'id':'F-02','label':'F-02 Finish','x':700,'y':200,'width':250,'height':90}],
              'arrows':[{'source':'F-01','target':'F-02','label':'continue'}]}
        svg=self.root/'graph.svg';svg.write_text(generator.build_svg('flowchart',data))
        source=self.root/'graph.svg.source.json';source.write_text(json.dumps(data))
        png=self.root/'graph.png';shutil.copy(GOLD/'shot.png',png)
        # This fixture validates identity only; real rendering is checked separately.
        proof=self.root/'graph.png.render.json'
        def refresh():proof.write_text(json.dumps({k:source_hash(p) for k,p in [('sourceHash',source),('svgHash',svg),('pngHash',png)]}))
        refresh();return source,svg,png,proof,refresh

    def test_diagram_rebuild_preserves_full_svg(self):
        from _diagram_contract import validate_render
        source,svg,png,proof,refresh=self.diagram()
        self.assertEqual(validate_render(source,svg,png,proof),{'F-01','F-02'})
        original=svg.read_text()
        for mutation in [original.replace('data-node-id="F-01"','display="none" data-node-id="F-01"'),
                         original.replace('data-node-id="F-01"','transform="translate(10000,0)" data-node-id="F-01"'),
                         original.replace('<svg ', '<svg style="display:none" ',1)]:
            svg.write_text(mutation);refresh()
            with self.assertRaisesRegex(ValueError,'diagram-render-source'):validate_render(source,svg,png,proof)

    def test_diagram_unknown_edges_and_invisible_lines(self):
        from _diagram_contract import validate_source
        source,*_=self.diagram();good=json.loads(source.read_text())
        self.assertEqual(validate_source(good),{'F-01','F-02'})
        for changed,criterion in [({'target':'F-99'},'diagram-edge'),({'opacity':0},'diagram-visible'),({'stroke_width':0},'diagram-visible')]:
            data=copy.deepcopy(good);data['arrows'][0].update(changed)
            with self.assertRaisesRegex(ValueError,criterion):validate_source(data)

    def test_diagram_font_data_is_not_an_external_url(self):
        import base64
        renderer=load('remediation_render',S.parent/'modules/diagramming/scripts/render-svg.py')
        url='data:application/font-woff;base64,'+base64.b64encode(b'wOFF'+bytes(20)).decode()
        self.assertTrue(renderer.safe_css_resource(url))
        for bad in ('https://example.invalid/a.woff', 'data:font/woff;base64,AAAA', 'data:text/html;base64,d09GRg=='):
            self.assertFalse(renderer.safe_css_resource(bad))

    def test_diagram_legacy_source_without_images_cannot_pass_formal(self):
        gate=load('remediation_diagram_gate',S/'diagram-id-gate.py')
        (self.root/'PRD.md').write_text('## 模块设计\nM-01\n## 功能清单\nF-01\n## 页面结构\nP-01\n')
        folder=self.root/'diagrams';folder.mkdir();(folder/'all.mmd').write_text('graph LR\nM-01 --> F-01 --> P-01')
        manifest=json.loads((S.parent/'templates/diagram-manifest.json').read_text())
        for row in manifest['diagrams']:row.update(applicable=True,rationale='Synthetic formal test',source='diagrams/all.mmd')
        (folder/'manifest.json').write_text(json.dumps(manifest))
        ok,issues=gate.check(str(self.root),formal=True)
        self.assertFalse(ok);self.assertTrue(any('真实编译产物' in issue for issue in issues))

    def package(self):
        d=self.golden()
        comp={'id':'COMP-01','featureMap':{'AF-001':['AF-001']}}
        for key,name in [('report','report.md'),('ledger','ledger.md'),('evidence','evidence-manifest.json'),('events','traversal-events.json')]:
            comp[key]={'path':name,'sha256':source_hash(d/name)}
        data={'schemaVersion':1,'competitors':[comp], 'comparisonNodes':[
            {'id':'work','parent':None,'features':['AF-001']}, {'id':'create','parent':'work','features':['AF-001']},
            {'id':'leaf','parent':'create','features':['AF-001']}]}
        p=d/'package.json';p.write_text(json.dumps(data))
        report='## 逐节点逐竞品对比\n| 节点 | COMP | 状态 | 原生路径 | 依据 | 影响 |\n|---|---|---|---|---|---|\n'
        report+='\n'.join('| '+n+' | COMP-01 | FULL | 工作/创建/功能A | EVENT-001 SHOT-001 | 需定义持久化 |' for n in ('work','create','leaf'))
        return p,report

    def test_research_package_valid_then_stale(self):
        from _research_package import check_package
        gate=load('remediation_report',S/'report-structure-gate.py')
        path,report=self.package()
        self.assertEqual(check_package(report,path,gate.check_teardown),[])
        (self.root/'ledger.md').write_text('changed')
        issues=check_package(report,path,gate.check_teardown)
        self.assertTrue(any('package-stale' in why for _,why in issues))

    def test_comparison_cannot_omit_native_leaf_from_denominator(self):
        from _research_package import check_package
        gate = load('denominator_report', S/'report-structure-gate.py')
        path, comparison = self.package()
        text = (self.root/'report.md').read_text()
        start, end = text.index('### 4.1.1 AF-001'), text.index('## 最细功能正文索引')
        def second(value):
            return value.replace('AF-001','AF-002').replace('SHOT-001','SHOT-002').replace('EVENT-001','EVENT-002').replace('功能A','功能B').replace('4.1.1','4.1.2')
        text = text[:end] + second(text[start:end]) + text[end:]
        row = next(x for x in text.splitlines() if x.startswith('| `AF-001`') and 'EVENT-001' in x)
        (self.root/'report.md').write_text(text.replace(row, row+'\n'+second(row)))
        ledger = (self.root/'ledger.md').read_text()
        row = next(x for x in ledger.splitlines() if 'AF-001' in x and x.lstrip().startswith('|'))
        (self.root/'ledger.md').write_text(ledger+'\n'+second(row)+'\n')
        for name, key in [('evidence-manifest.json','evidence'), ('traversal-events.json','events')]:
            p = self.root/name; data = json.loads(p.read_text())
            data[key].append(json.loads(second(json.dumps(data[key][0], ensure_ascii=False))))
            p.write_text(json.dumps(data))
        package = json.loads(path.read_text()); comp = package['competitors'][0]
        for key in ('report','ledger','evidence','events'):
            comp[key]['sha256'] = source_hash(self.root/comp[key]['path'])
        path.write_text(json.dumps(package))
        # Genuine, structurally valid two-leaf report; only the comparison omits one.
        self.assertEqual(gate.check_teardown((self.root/'report.md').read_text(),
            str(self.root/'ledger.md'), str(self.root/'evidence-manifest.json'), str(self.root/'traversal-events.json')), [])
        self.assertIn('package-native-denominator', {k for k,_ in check_package(comparison,path,gate.check_teardown)})
        comp['featureMap']['AF-002'] = ['AF-002']
        package['comparisonNodes'].append({'id':'leaf2','parent':'create','features':['AF-002']})
        for n in package['comparisonNodes'][:2]: n['features'].append('AF-002')
        path.write_text(json.dumps(package))
        comparison = '\n'.join(line.replace('EVENT-001 SHOT-001', 'EVENT-001 SHOT-001 EVENT-002 SHOT-002')
            if line.startswith(('| work |', '| create |')) else line for line in comparison.splitlines())
        comparison += '\n| leaf2 | COMP-01 | FULL | 工作/创建/功能B | EVENT-002 SHOT-002 | 需定义持久化 |'
        self.assertEqual(check_package(comparison,path,gate.check_teardown), [])

    def test_research_package_missing_rows_and_unknown_absence(self):
        from _research_package import check_package
        gate=load('remediation_report_rows',S/'report-structure-gate.py')
        path,report=self.package()
        issues=check_package(report.rsplit('\n',1)[0],path,gate.check_teardown)
        self.assertIn('comparison-set',{k for k,_ in issues})
        report=report.replace('FULL','ABSENT').replace('EVENT-001 SHOT-001','登录墙')
        self.assertIn('absence-not-proven',{k for k,_ in check_package(report,path,gate.check_teardown)})

    def test_research_exact_body_and_file(self):
        gate=load('remediation_report_body',S/'report-structure-gate.py');d=self.golden()
        source=(d/'report.md').read_text()
        args=(str(d/'ledger.md'),str(d/'evidence-manifest.json'),str(d/'traversal-events.json'))
        self.assertEqual(gate.check_teardown(source,*args),[])
        bad=source.replace('| AF-001 功能A |','| AF-001 |')
        self.assertIn('missing-feature-body',{k for k,_ in gate.check_teardown(bad,*args)})
        bad=source.replace('@./shot.png','@./wrong.png')
        self.assertIn('body-image-path',{k for k,_ in gate.check_teardown(bad,*args)})

    def test_research_comparison_cannot_borrow_or_drop_evidence(self):
        from _research_package import check_package
        gate=load('remediation_report_evidence',S/'report-structure-gate.py');path,report=self.package()
        bad=report.replace('EVENT-001 SHOT-001','EVENT-999 SHOT-999')
        self.assertIn('comparison-evidence',{k for k,_ in check_package(bad,path,gate.check_teardown)})
        self.assertIn('comparison-row',{k for k,_ in check_package(report+'\n| broken | row |',path,gate.check_teardown)})
        # A genuine event/image elsewhere in the same product is not proof of this node.
        data=json.loads(path.read_text());comp=data['competitors'][0]
        src=self.root/'report.md';src.write_text(src.read_text()+'\n## 补充截图\n<!-- evidence:SHOT-002 -->\n![SHOT-002 补充](<@./shot.png>)\n')
        ep=self.root/'evidence-manifest.json';ev=json.loads(ep.read_text())
        item=copy.deepcopy(ev['evidence'][0]);item.update(id='SHOT-002',anchor='补充截图');ev['evidence'].append(item);ep.write_text(json.dumps(ev))
        tp=self.root/'traversal-events.json';events=json.loads(tp.read_text())
        event=copy.deepcopy(events['events'][0]);event.update(id='EVENT-002',evidenceId='SHOT-002');events['events'].append(event);tp.write_text(json.dumps(events))
        for key in ('report','evidence','events'):comp[key]['sha256']=source_hash(self.root/comp[key]['path'])
        path.write_text(json.dumps(data))
        self.assertEqual(check_package(report,path,gate.check_teardown),[])
        bad=report.replace('EVENT-001 SHOT-001','EVENT-002 SHOT-002')
        self.assertIn('comparison-node-evidence',{k for k,_ in check_package(bad,path,gate.check_teardown)})

    def approval(self):
        source=self.root/'solution.md'
        source.write_text('| 角色 | 结论 | 依据 | 风险 | 主体类型 | 主体 | 批准版本 | 批准范围 | 来源 |\n|---|---|---|---|---|---|---|---|---|\n| 技术 | APPROVED | evaluated | none | agent | synthetic | v1 | solution | evidence.json |\n')
        prd=self.root/'prd.md';prd.write_text('# Frozen PRD\nA')
        record={'sourceHash':source_hash(source),'version':'v1','scope':'solution','approvalEvidence':'evidence.json',
                'artifacts':[{'kind':'frozen-prd','path':'prd.md','sha256':source_hash(prd)}]}
        (self.root/'evidence.json').write_text(json.dumps({'sourceHash':source_hash(source),'version':'v1','scope':'solution',
            'approvals':[{'role':'技术','actorType':'agent','reviewer':'synthetic','authority':'synthetic',
                          'decision':'APPROVED','reviewedAt':'2026-09-23T00:00:00Z'}]}))
        context=self.root/'contract.json';context.write_text(json.dumps({'approvalBindings':{'S8':record}}))
        return source,context,record

    def test_approval_valid_and_stale_source(self):
        from _approval import check
        source,context,_=self.approval();self.assertEqual(check(source,context,'S8'),[])
        source.write_text(source.read_text()+'changed')
        self.assertTrue(any('approval-stale' in x for x in check(source,context,'S8')))

    def test_approval_changed_prd_and_false_scope(self):
        from _approval import check
        source,context,record=self.approval()
        record['scope']='different';context.write_text(json.dumps({'approvalBindings':{'S8':record}}))
        self.assertTrue(any('approval-version' in x for x in check(source,context,'S8')))
        (self.root/'prd.md').write_text('new requirements')
        self.assertTrue(any('approval-stale' in x for x in check(source,context,'S8')))

    def test_approval_missing_artifacts_and_authority(self):
        from _approval import check
        source,context,record=self.approval()
        payload=json.loads((self.root/'evidence.json').read_text());payload['approvals'][0]['authority']=''
        (self.root/'evidence.json').write_text(json.dumps(payload))
        self.assertTrue(any('approval-authority' in x for x in check(source,context,'S8')))
        record['artifacts']=[];context.write_text(json.dumps({'approvalBindings':{'S8':record}}))
        self.assertTrue(any('approval-artifacts' in x for x in check(source,context,'S8')))

    def test_approval_gui_order_and_same_build(self):
        from _approval import check
        source,context,record=self.approval();record.update(build='build-1',qualityEvidence='quality.json',qaGuiEvidence='qa.json',pmGuiEvidence='pm.json')
        prd_hash=record['artifacts'][0]['sha256'];shutil.copy(GOLD/'shot.png',self.root/'shot.png')
        for role,file,start,end in [('qa','qa.json','01','02'),('product','pm.json','04','05')]:
            value={'role':role,'status':'PASS','sessionId':role+'-session','reviewer':'synthetic','build':'build-1','prdHash':prd_hash,
                   'startedAt':'2026-09-23T00:'+start+':00Z','completedAt':'2026-09-23T00:'+end+':00Z',
                   'steps':[{'action':'create','expected':'created','actual':'created','status':'PASS','screenshot':{'path':'shot.png','sha256':source_hash(self.root/'shot.png')}}]}
            (self.root/file).write_text(json.dumps(value))
        quality={'status':'PASS','build':'build-1','prdHash':prd_hash,'completedAt':'2026-09-23T00:03:00Z'}
        (self.root/'quality.json').write_text(json.dumps(quality))
        context.write_text(json.dumps({'approvalBindings':{'S9.3':record}}))
        self.assertEqual(check(source,context,'S9.3'),[])
        quality['completedAt']='2026-09-23T00:06:00Z';(self.root/'quality.json').write_text(json.dumps(quality))
        self.assertTrue(any('approval-order' in x for x in check(source,context,'S9.3')))
        pm=json.loads((self.root/'pm.json').read_text());pm['build']='another';(self.root/'pm.json').write_text(json.dumps(pm))
        self.assertTrue(any('approval-gui' in x for x in check(source,context,'S9.3')))


class Results(unittest.TextTestResult):
    def addSuccess(self,test):
        super().addSuccess(test);print('  ✅ '+test._testMethodName+('（含反例）' if test._testMethodName != 'test_image_valid_decode' else ''),flush=True)


def main(group=None):
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    if group:suite=unittest.TestSuite(test for test in suite if test._testMethodName.startswith('test_'+group+'_'))
    result=unittest.TextTestRunner(verbosity=0,resultclass=Results).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':sys.exit(main())
