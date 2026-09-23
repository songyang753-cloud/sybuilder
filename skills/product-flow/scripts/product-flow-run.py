#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""product-flow 运行器：生成/验证运行计划，恢复活动运行，校验独立模块导入。

用法：
  product-flow-run.py plan --root <项目根> --mode full [--write]
  product-flow-run.py plan --root <项目根> --mode from --from S4A [--write]
  product-flow-run.py plan --root <项目根> --mode only --modules interaction [--write]
  product-flow-run.py plan --root <项目根> --mode bundle --modules prd,design [--write]
  product-flow-run.py plan --root <项目根> --mode reverse [--write]
  product-flow-run.py validate --root <项目根>
  product-flow-run.py resume --root <项目根>
  product-flow-run.py result --root <项目根> --draft <result-draft.json>
  product-flow-run.py import --root <项目根> --result <module-result.json>
  product-flow-run.py --self-test
"""
import argparse
import datetime
import hashlib
import re
import io
import json
import os
import shutil
import sys
import uuid

from _workflow import (WorkflowError, canonical_bytes, claim_min, gate_result_dir,
                       load_active_run, load_registry, required_gates_for_module,
                       resolve_plan, sha256_file,
                       validate_full_contains_modules, validate_manifest)
from _module_contract import issue_result, import_result, verify_result


def _write_json(path, data, no_clobber=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if no_clobber and os.path.exists(path):
        raise WorkflowError('拒绝覆盖已有文件：%s' % path)
    tmp = '%s.tmp.%s' % (path, os.getpid())
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def _sha_value(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _read_json(path, label='JSON'):
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise WorkflowError('%s 读不了：%s' % (label, e))


def _new_run_id():
    return 'PF-%s-%s' % (datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
                         uuid.uuid4().hex[:6])


def _plan(args):
    modules = [x.strip() for x in (args.modules or '').split(',') if x.strip()]
    plan = resolve_plan(args.mode, modules, args.start, args.product_type,
                        args.delivery_intent, args.execution_mode, args.html_profile,
                        args.evidence_capability, research_mode=args.research_mode,
                        document_platform=args.document_platform)
    manifest = dict(plan)
    if args.run_id and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_id):
        raise WorkflowError('runId 只允许字母数字开头及 . _ -；禁止路径越界')
    manifest['runId'] = args.run_id or _new_run_id()
    manifest['createdAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    intake = _read_json(args.intake, 'intake') if args.intake else {}
    for key in ('inputs', 'assumptions', 'openDecisions', 'stopLines', 'requiredBackfills'):
        manifest[key] = intake.get(key) or []
    manifest['inputsHash'] = _sha_value(manifest['inputs'])
    manifest['supersedesRunId'] = ''
    if args.write:
        root = os.path.abspath(args.root)
        rel = os.path.join('runs', manifest['runId'], 'run-manifest.json')
        path = os.path.join(root, '.product-flow', rel)
        if os.path.exists(path):
            raise WorkflowError('runId 已存在：%s' % manifest['runId'])
        _write_json(path, manifest, no_clobber=True)
        pointer = {
            'schemaVersion': '1.0',
            'activeRunId': manifest['runId'],
            'manifestRef': rel,
            'manifestHash': sha256_file(path),
        }
        _write_json(os.path.join(root, '.product-flow', 'run-manifest.json'), pointer)
        print('✅ 已创建并激活 %s\n%s' % (manifest['runId'], path))
    else:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def _validate(args):
    manifest, path = load_active_run(os.path.abspath(args.root), required=True)
    if manifest.get('schemaVersion') != '2.0':
        raise WorkflowError('旧 v1 manifest 只能读取，不能作为可验证运行计划；请重新 plan --write')
    validate_manifest(manifest)
    print('✅ 活动运行有效：%s\nmanifest: %s\nplanHash: %s'
          % (manifest['runId'], path, manifest['planHash']))
    return 0


def _resume(args):
    root = os.path.abspath(args.root)
    manifest, path = load_active_run(root, required=True)
    if not args.write:
        print(json.dumps({
            'runId': manifest.get('runId'),
            'manifest': path,
            'modules': manifest.get('modules'),
            'requiredGates': manifest.get('requiredGates'),
            'claimCeiling': manifest.get('claimCeiling'),
        }, ensure_ascii=False, indent=2))
        return 0
    if manifest.get('schemaVersion') != '2.0':
        raise WorkflowError('续跑要求 v2 活动运行')
    old_imports = []
    old_import_dir = os.path.join(root, '.product-flow', 'runs', manifest['runId'], 'imports')
    if os.path.isdir(old_import_dir):
        for name in sorted(os.listdir(old_import_dir)):
            if name.endswith('.json'):
                old_imports.append(_read_json(os.path.join(old_import_dir, name), 'import receipt'))
    resumed = dict(manifest)
    resumed['runId'] = args.run_id or _new_run_id()
    resumed['createdAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resumed['supersedesRunId'] = manifest['runId']
    rel = os.path.join('runs', resumed['runId'], 'run-manifest.json')
    new_path = os.path.join(root, '.product-flow', rel)
    _write_json(new_path, resumed, no_clobber=True)
    _write_json(os.path.join(root, '.product-flow', 'run-manifest.json'), {
        'schemaVersion': '1.0', 'activeRunId': resumed['runId'],
        'manifestRef': rel, 'manifestHash': sha256_file(new_path),
    })
    inherited, failed = [], []
    for receipt in old_imports:
        ref = receipt.get('sourceResultRef')
        try:
            _, _ = import_result(root, ref)
            inherited.append(receipt.get('resultId'))
        except WorkflowError as e:
            failed.append('%s（%s）' % (receipt.get('resultId'), e))   # ⭐ 不再静默吞:列出失败项,否则「继承N项」无法区分「本就0」与「全作废」
    msg = '✅ 已创建续跑 %s（supersedes %s）；复验并继承导入 %d 项。' % (resumed['runId'], manifest['runId'], len(inherited))
    if failed:
        msg += '\n⚠️ **继承失败 %d 项（未继承，需重新导入）**：%s' % (len(failed), '；'.join(failed))
    print(msg + ' 门禁结果不伪造继承，需重跑。')
    return 0


def _result(args):
    dst = issue_result(args.root, args.draft)
    print('✅ 已签发不可覆盖的模块结果：%s' % dst)
    return 0


def _import(args):
    dst, state = import_result(args.root, args.result)
    print('✅ 已验证并双向登记导入：%s\n有效声明上限：%s'
          % (dst, state['effectiveClaimCeiling']))
    return 0


def _self_test():
    ok = True

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print(('  ✅ ' if cond else '  ❌ ') + name)

    a = resolve_plan('full', product_type='dual', execution_mode='build')
    b = resolve_plan('full', product_type='dual', execution_mode='build')
    chk('完整运行覆盖 S1–S10 且计划哈希确定', a['modules'][0] == 'S1'
        and a['modules'][-1] == 'S10' and a['planHash'] == b['planHash'])
    chk('完整运行强制 core-full', a['htmlProfile'] == 'core-full')
    chk('双端+Build 条件门进入必跑集合', 'platform-parity-gate.mjs' in a['requiredGates']
        and 'selfcheck.sh' in a['requiredGates'])
    teardown = resolve_plan('only', ['S2'], research_mode='teardown')
    full_research = resolve_plan('only', ['S2'], research_mode='full-research')
    chk('teardown 只跑通用研究门，不被迫伪造五线全量研究',
        'report-structure-gate.py' in teardown['requiredGates']
        and 'research-gate.py' not in teardown['requiredGates']
        and 'chain-gate.py.G0' not in teardown['requiredGates'])
    chk('full-research 保留研究总门与 S1→S2 对账',
        'research-gate.py' in full_research['requiredGates']
        and 'chain-gate.py.G0' in full_research['requiredGates'])
    dingtalk = resolve_plan('only', ['S2'], document_platform='dingtalk')
    chk('文档平台只启用所选平台的回读门',
        'dingtalk-delivery-gate.py' in dingtalk['requiredGates']
        and 'feishu-delivery-gate.py' not in dingtalk['requiredGates'])
    web = resolve_plan('only', ['interaction'], product_type='web')
    _dual_rule = next(x for x in web['gatePlan'] if x['ruleId'] == 'R-S6-DUAL')
    chk('条件未命中时写入机器计算的 n-a 与 ruleId',
        _dual_rule['classification'] == 'n-a' and not _dual_rule['required'])
    chk('完整运行由同一模块规则组合而成，不得少于各独立模块并集',
        validate_full_contains_modules())
    c = resolve_plan('from', start='S4A')
    chk('--from 不偷带更早阶段', c['modules'][0] == 'S4A' and 'S3B' not in c['modules'])
    d = resolve_plan('only', ['interaction'])
    chk('--only S6 不伪装运行依赖，依赖变外部输入', d['modules'] == ['S6']
        and d['externalInputs'][0]['dependency'] == 'S5'
        and d['htmlProfile'] == 'standalone-interaction')
    e = resolve_plan('bundle', ['design', 'prd'])
    chk('组合模块按阶段拓扑，不按输入顺序', e['modules'] == ['S4B', 'S7'])
    try:
        resolve_plan('full', html_profile='draft')
        rejected = False
    except WorkflowError:
        rejected = True
    chk('完整运行不能降为 skeleton/draft HTML', rejected)
    tampered = dict(a, runId='PF-test')
    tampered['inputs'] = []
    tampered['inputsHash'] = _sha_value([])
    tampered['requiredGates'] = tampered['requiredGates'][:-1]
    try:
        validate_manifest(tampered)
        rejected = False
    except WorkflowError:
        rejected = True
    chk('删掉一个必跑门会被重算抓住', rejected)

    # 独立结果：不可覆盖、双向导入、哈希与声明级上限。
    import tempfile
    t = tempfile.mkdtemp(prefix='pf-run-')

    def activate(plan, run_id):
        manifest = dict(plan)
        manifest.update({'runId': run_id,
                         'createdAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         'inputs': [], 'inputsHash': _sha_value([]),
                         'assumptions': [], 'openDecisions': [], 'stopLines': [],
                         'requiredBackfills': [], 'supersedesRunId': ''})
        rel = os.path.join('runs', run_id, 'run-manifest.json')
        path = os.path.join(t, '.product-flow', rel)
        _write_json(path, manifest, no_clobber=True)
        _write_json(os.path.join(t, '.product-flow', 'run-manifest.json'), {
            'schemaVersion': '1.0', 'activeRunId': run_id,
            'manifestRef': rel, 'manifestHash': sha256_file(path),
        })
        return manifest

    source = activate(resolve_plan('only', ['S1']), 'PF-source')
    from _workflow import gate_evidence
    output = os.path.join(t, 'definition.md')
    with io.open(output, 'w', encoding='utf-8') as f:
        f.write('需求定义')
    gdir = gate_result_dir(t, source)
    os.makedirs(gdir, exist_ok=True)
    for gate in source['requiredGates']:
        ids = sorted(x['ruleId'] for x in source['gatePlan']
                     if x['gate'] == gate and x['required'])
        _write_json(os.path.join(gdir, gate + '.json'), {
            'verdict': 'PASS', 'runId': source['runId'],
            'planHash': source['planHash'], 'ruleIds': ids,
            'claimEligible': True,
            'evidence': gate_evidence(os.path.join(os.path.dirname(__file__), gate), [output]),
        })
    output = os.path.join(t, 'definition.md')
    with io.open(output, 'w', encoding='utf-8') as f:
        f.write('需求定义')
    draft = os.path.join(t, 'result-draft.json')
    _write_json(draft, {'moduleId': 'S1', 'claimCeiling': 'module-approved',
                        'inputs': [{'ref': 'user'}],
                        'outputs': [{'ref': output, 'authority': 'S1'}],
                        'limitations': ['只验证 S1，不验证下游采用']})
    result_path = issue_result(t, draft)
    chk('独立模块结果可签发且哈希可复验', verify_result(result_path)['moduleId'] == 'S1')
    try:
        issue_result(t, draft)
        rejected = False
    except WorkflowError:
        rejected = True
    chk('同 run+module+inputs 再签发会拒绝覆盖', rejected)
    bad_result = os.path.join(t, 'tampered-result.json')
    bad_data = _read_json(result_path, 'result')
    bad_data['limitations'] = ['被改过']
    _write_json(bad_result, bad_data)
    try:
        verify_result(bad_result)
        rejected = False
    except WorkflowError:
        rejected = True
    chk('module-result 内容变化但哈希未变会被拒绝', rejected)

    consumer = activate(resolve_plan('only', ['S2']), 'PF-consumer')
    import_path, claim_state = import_result(t, result_path)
    chk('导入写入消费 记录并按最低级计算声明上限',
        os.path.isfile(import_path) and claim_state['effectiveClaimCeiling'] == 'module-approved')
    index = _read_json(os.path.join(t, '.product-flow', 'index', 'module-consumers.json'), 'index')
    result_id = _read_json(result_path, 'result')['resultId']
    chk('导入同时建立 source result → consumer run 反向索引',
        index['results'][result_id]['consumers'][0]['runId'] == consumer['runId'])
    try:
        import_result(t, result_path)
        rejected = False
    except WorkflowError:
        rejected = True
    chk('同一 result 再导入会拒绝覆盖', rejected)
    print('\n%s' % ('✅ 自证通过：运行计划不再靠人工抄写' if ok else '❌ 自证失败'))
    return 0 if ok else 1


def parser():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument('--self-test', action='store_true')
    sub = p.add_subparsers(dest='command')
    plan = sub.add_parser('plan')
    plan.add_argument('--root', required=True)
    plan.add_argument('--mode', required=True,
                      choices=['full', 'from', 'only', 'bundle', 'reverse'])
    plan.add_argument('--from', dest='start')
    plan.add_argument('--modules')
    plan.add_argument('--product-type', default='web')
    plan.add_argument('--delivery-intent', default='production')
    plan.add_argument('--execution-mode', default='handoff')
    plan.add_argument('--html-profile')
    plan.add_argument('--evidence-capability', default='native')
    plan.add_argument('--research-mode', default='full-research',
                      choices=['teardown', 'competitive-pack', 'full-research'])
    plan.add_argument('--document-platform', default='feishu', choices=['feishu', 'dingtalk'])
    plan.add_argument('--intake', help='JSON：inputs/assumptions/openDecisions/stopLines/requiredBackfills')
    plan.add_argument('--run-id')
    plan.add_argument('--write', action='store_true')
    validate = sub.add_parser('validate')
    validate.add_argument('--root', required=True)
    resume = sub.add_parser('resume')
    resume.add_argument('--root', required=True)
    resume.add_argument('--write', action='store_true')
    resume.add_argument('--run-id')
    imp = sub.add_parser('import')
    imp.add_argument('--root', required=True)
    imp.add_argument('--result', required=True)
    result = sub.add_parser('result')
    result.add_argument('--root', required=True)
    result.add_argument('--draft', required=True)
    return p


def main():
    args = parser().parse_args()
    if args.self_test:
        return _self_test()
    if not args.command:
        raise WorkflowError('缺少命令：plan/validate/resume/result/import')
    return {'plan': _plan, 'validate': _validate, 'resume': _resume,
            'result': _result, 'import': _import}[args.command](args)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except WorkflowError as e:
        print('UNABLE: %s' % e, file=sys.stderr)
        sys.exit(2)
