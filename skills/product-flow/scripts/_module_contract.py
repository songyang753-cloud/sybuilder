#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立模块结果的不可覆盖签发、验证、双向导入与声明上限计算。"""
import datetime
import hashlib
import io
import json
import os

from _workflow import (WorkflowError, canonical_bytes, claim_min, gate_result_dir,
                       load_active_run, load_registry, sha256_file,
                       validate_manifest)


def _read(path, label='JSON'):
    try:
        with io.open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise WorkflowError('%s 读不了：%s' % (label, e))


def _write(path, data, no_clobber=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if no_clobber and os.path.exists(path):
        raise WorkflowError('拒绝覆盖已有文件：%s' % path)
    tmp = '%s.tmp.%s' % (path, os.getpid())
    with io.open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)


def _sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _reject_fixed_result(root):
    legacy = os.path.join(root, '.product-flow', 'module-result.md')
    if os.path.exists(legacy):
        raise WorkflowError('发现会被覆盖的旧固定结果 .product-flow/module-result.md；'
                            '先迁移到 runs/<runId>/modules/<moduleId>/<resultId>.md')


def _find_result(root, result_id):
    base = os.path.join(root, '.product-flow', 'runs')
    if not os.path.isdir(base):
        return None
    for dirpath, _, files in os.walk(base):
        if result_id + '.json' in files and '%smodules%s' % (os.sep, os.sep) in dirpath:
            return os.path.join(dirpath, result_id + '.json')
    return None


def _rules_for_module(registry, module_id):
    return {r['id'] for r in registry['gateRules']
            if ('*' in r.get('modules', []) or module_id in r.get('modules', []))
            and not r.get('compositionOnly')}


def issue_result(root, draft_path):
    root = os.path.abspath(root)
    _reject_fixed_result(root)
    manifest, manifest_path = load_active_run(root, required=True)
    if manifest.get('schemaVersion') != '2.0':
        raise WorkflowError('签发模块结果要求 v2 活动运行')
    draft = _read(draft_path, 'module result draft')
    module_id = draft.get('moduleId')
    if module_id not in manifest.get('modules', []):
        raise WorkflowError('moduleId=%s 不在当前运行 modules' % module_id)
    registry, registry_hash = load_registry()
    claim = draft.get('claimCeiling', 'draft')
    module_max = registry['modules'][module_id].get('maxClaim', 'draft')
    run_max = manifest.get('claimCeiling', 'draft')
    allowed_max = claim_min(registry, [module_max, run_max])
    if claim not in registry['claimOrder'] or claim_min(registry, [claim, allowed_max]) != claim:
        raise WorkflowError('claimCeiling=%s 超过模块/当前运行上限 %s'
                            % (claim, allowed_max))
    if not draft.get('limitations'):
        raise WorkflowError('limitations 必填，必须声明本模块验不了什么')

    inputs = draft.get('inputs') or []
    inputs_hash = _sha(inputs)
    result_id = draft.get('resultId') or 'MR-%s-%s-%s' % (
        manifest['runId'], module_id.replace('.', ''), inputs_hash[:12])
    module_rules = _rules_for_module(registry, module_id)
    gate_results, seen = [], set()
    for item in manifest.get('gatePlan', []):
        if item['ruleId'] not in module_rules or not item['required'] or item['gate'] in seen:
            continue
        seen.add(item['gate'])
        path = os.path.join(gate_result_dir(root, manifest), item['gate'] + '.json')
        if not os.path.isfile(path):
            verdict = 'NOT-RUN'
        else:
            rec = _read(path, 'gate result')
            expected_ids = sorted(x['ruleId'] for x in manifest['gatePlan']
                                  if x['gate'] == item['gate'] and x['required'])
            valid = (rec.get('runId') == manifest['runId']
                     and rec.get('planHash') == manifest['planHash']
                     and rec.get('claimEligible') is True
                     and sorted(rec.get('ruleIds') or []) == expected_ids)
            verdict = rec.get('verdict') if valid else 'INVALID-BINDING'
        gate_results.append({'gate': item['gate'], 'ruleId': item['ruleId'],
                             'verdict': verdict, 'recordRef': os.path.relpath(path, root)})
    not_pass = sorted(x['gate'] for x in gate_results if x['verdict'] != 'PASS')
    if claim == 'module-approved' and not_pass:
        raise WorkflowError('module-approved 但本模块必跑门未 PASS：%s' % ', '.join(not_pass))

    outputs = []
    for output in draft.get('outputs') or []:
        ref = output.get('ref')
        full = ref if ref and os.path.isabs(ref) else os.path.join(root, ref or '')
        if not ref or not os.path.isfile(full):
            raise WorkflowError('输出文件不存在：%s' % (ref or '空'))
        outputs.append({'ref': os.path.abspath(full), 'sha256': sha256_file(full),
                        'authority': output.get('authority', '')})

    supersedes = draft.get('supersedes') or ''
    if supersedes and not _find_result(root, supersedes):
        raise WorkflowError('supersedes 指向不存在的结果：%s' % supersedes)
    body = {
        'schemaVersion': '1.0', 'resultId': result_id,
        'sourceRunId': manifest['runId'], 'sourceManifestRef': manifest_path,
        'sourceManifestHash': sha256_file(manifest_path), 'moduleId': module_id,
        'inputs': inputs, 'inputsHash': inputs_hash,
        'producedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'registryVersion': manifest['registryVersion'], 'registryHash': registry_hash,
        'supersedes': supersedes, 'claimCeiling': claim,
        'outputs': outputs, 'gateResults': gate_results,
        'assumptions': draft.get('assumptions') or [],
        'stopLines': draft.get('stopLines') or [],
        'unresolvedDependencies': draft.get('unresolvedDependencies') or [],
        'backfills': draft.get('backfills') or [],
        'limitations': draft['limitations'],
    }
    body['moduleResultHash'] = _sha(body)
    dst = os.path.join(root, '.product-flow', 'runs', manifest['runId'],
                       'modules', module_id, result_id + '.json')
    _write(dst, body, no_clobber=True)
    if supersedes:
        index_path = os.path.join(root, '.product-flow', 'index', 'module-consumers.json')
        index = _read(index_path, 'consumer index') if os.path.isfile(index_path) else {'schemaVersion': '1.0', 'results': {}}
        for consumer in (index.get('results', {}).get(supersedes, {}).get('consumers') or []):
            consumer['staleAt'] = body['producedAt']
            consumer['staleReason'] = '源结果已被 %s 取代' % result_id
        _write(index_path, index)
    return dst


def verify_result(path):
    data = _read(path, 'module-result')
    required = ('schemaVersion', 'resultId', 'sourceRunId', 'sourceManifestRef',
                'sourceManifestHash', 'moduleId', 'inputsHash', 'producedAt',
                'moduleResultHash', 'registryVersion', 'registryHash',
                'claimCeiling', 'outputs', 'gateResults',
                'unresolvedDependencies', 'limitations', 'supersedes')
    missing = [x for x in required if x not in data]
    if missing:
        raise WorkflowError('module-result 缺字段：%s' % ', '.join(missing))
    body = dict(data)
    claimed = body.pop('moduleResultHash')
    if claimed != _sha(body):
        raise WorkflowError('moduleResultHash 不匹配（结果被改过或签发错误）')
    registry, registry_hash = load_registry()
    if data['registryVersion'] != registry['registryVersion'] or data['registryHash'] != registry_hash:
        raise WorkflowError('module-result 使用的流程注册表不是当前版本')
    if data['moduleId'] not in registry['modules']:
        raise WorkflowError('moduleId 未登记：%s' % data['moduleId'])
    if data['inputsHash'] != _sha(data.get('inputs') or []):
        raise WorkflowError('inputsHash 不匹配')
    source_manifest = data['sourceManifestRef']
    if not os.path.isfile(source_manifest) or sha256_file(source_manifest) != data['sourceManifestHash']:
        raise WorkflowError('来源运行 manifest 不存在或哈希已变化')
    context = _read(source_manifest, 'source manifest')
    validate_manifest(context)
    claim = data['claimCeiling']
    module_max = registry['modules'][data['moduleId']].get('maxClaim', 'draft')
    allowed_max = claim_min(registry, [module_max, context.get('claimCeiling', 'draft')])
    if claim not in registry['claimOrder'] or claim_min(registry, [claim, allowed_max]) != claim:
        raise WorkflowError('module-result claimCeiling=%s 超过来源运行上限 %s'
                            % (claim, allowed_max))
    if not data.get('limitations'):
        raise WorkflowError('limitations 必填')
    for output in data['outputs']:
        if not output.get('ref') or not output.get('sha256') \
                or not os.path.isfile(output['ref']) or sha256_file(output['ref']) != output['sha256']:
            raise WorkflowError('输出不存在或哈希不符：%s' % output.get('ref'))
    if data['claimCeiling'] == 'module-approved':
        gate_map = {x.get('gate'): x.get('verdict') for x in data['gateResults']}
        context = _read(source_manifest, 'source manifest')
        required_gates = [x['gate'] for x in context['gatePlan']
                          if x['required'] and x['ruleId'] in _rules_for_module(registry, data['moduleId'])]
        missing_gates = [g for g in required_gates if gate_map.get(g) != 'PASS']
        if missing_gates:
            raise WorkflowError('module-approved 但必跑门未 PASS：%s' % ', '.join(missing_gates))
    return data


def refresh_claim_state(root, manifest):
    registry, _ = load_registry()
    # ⭐ stale 标记由 issue_result 写在消费索引的 consumer 条目上(不在 receipt 上),读取方必须读这里
    _cidx_path = os.path.join(root, '.product-flow', 'index', 'module-consumers.json')
    _cidx = _read(_cidx_path, 'consumer index') if os.path.isfile(_cidx_path) else {'results': {}}
    imports_dir = os.path.join(root, '.product-flow', 'runs', manifest['runId'], 'imports')
    receipts = []
    if os.path.isdir(imports_dir):
        receipts = [_read(os.path.join(imports_dir, x), 'import receipt')
                    for x in sorted(os.listdir(imports_dir)) if x.endswith('.json')]
    imported_modules = {x.get('moduleId') for x in receipts}
    expected = {x['dependency'] for x in manifest.get('externalInputs', [])}
    reasons, claims = [], [manifest['claimCeiling']]
    for missing in sorted(expected - imported_modules):
        reasons.append('外部依赖 %s 尚未导入' % missing)
        claims.append('draft')
    for receipt in receipts:
        ref = receipt.get('sourceResultRef')
        if not ref or not os.path.isfile(ref) or sha256_file(ref) != receipt.get('sourceResultHash'):
            reasons.append('导入 %s 的源结果已变化或不可读' % receipt.get('resultId'))
            claims.append('draft')
            continue
        result = verify_result(ref)
        claims.append(result['claimCeiling'])
        if result.get('unresolvedDependencies'):
            reasons.append('%s 仍有未关闭依赖' % result['resultId'])
            claims.append('review-ready')
        _cons = (_cidx.get('results', {}).get(receipt.get('resultId'), {}).get('consumers') or [])
        if any(c.get('runId') == manifest['runId'] and c.get('staleAt') for c in _cons):
            reasons.append('%s 已被来源标记过期' % result['resultId'])
            claims.append('draft')
    state = {'schemaVersion': '1.0', 'runId': manifest['runId'],
             'computedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'effectiveClaimCeiling': claim_min(registry, claims), 'reasons': reasons}
    _write(os.path.join(root, '.product-flow', 'runs', manifest['runId'], 'claim-state.json'), state)
    return state


def import_result(root, result_path):
    root = os.path.abspath(root)
    _reject_fixed_result(root)
    manifest, _ = load_active_run(root, required=True)
    if manifest.get('schemaVersion') != '2.0':
        raise WorkflowError('导入要求 v2 活动运行')
    result_path = os.path.abspath(result_path)
    result = verify_result(result_path)
    expected = {x['dependency'] for x in manifest.get('externalInputs', [])}
    if result['moduleId'] not in expected:
        raise WorkflowError('%s 不是当前计划声明的外部依赖：%s'
                            % (result['moduleId'], ', '.join(sorted(expected)) or '无'))
    receipt = {
        'schemaVersion': '1.0', 'resultId': result['resultId'],
        'moduleId': result['moduleId'], 'sourceRunId': result['sourceRunId'],
        'sourceResultRef': result_path, 'sourceResultHash': sha256_file(result_path),
        'consumerRunId': manifest['runId'], 'consumerPlanHash': manifest['planHash'],
        'importedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    dst = os.path.join(root, '.product-flow', 'runs', manifest['runId'],
                       'imports', result['resultId'] + '.json')
    _write(dst, receipt, no_clobber=True)
    index_path = os.path.join(root, '.product-flow', 'index', 'module-consumers.json')
    index = _read(index_path, 'consumer index') if os.path.isfile(index_path) else {'schemaVersion': '1.0', 'results': {}}
    item = index['results'].setdefault(result['resultId'],
                                       {'sourceResultRef': result_path, 'consumers': []})
    item['consumers'].append({'runId': manifest['runId'], 'importReceiptRef': dst})
    _write(index_path, index)
    return dst, refresh_claim_state(root, manifest)


def _self_test():
    """模块结果签发与复验的最小承重自证。"""
    import shutil
    import tempfile
    from _workflow import resolve_plan

    ok = True

    def chk(name, condition, detail=''):
        nonlocal ok
        passed = bool(condition)
        ok = ok and passed
        print(('  ✅ ' if passed else '  ❌ ') + name
              + ('' if passed or not detail else '　' + detail))

    root = tempfile.mkdtemp(prefix='module-contract-selftest-')
    run_id = 'PF-module-contract-selftest'
    manifest = dict(resolve_plan('only', ['S1']))
    manifest.update({
        'runId': run_id,
        'createdAt': '2026-09-12T00:00:00+00:00',
        'inputs': [],
        'inputsHash': _sha([]),
        'assumptions': [],
        'openDecisions': [],
        'stopLines': [],
        'requiredBackfills': [],
        'supersedesRunId': '',
    })
    manifest_rel = os.path.join('runs', run_id, 'run-manifest.json')
    manifest_path = os.path.join(root, '.product-flow', manifest_rel)
    _write(manifest_path, manifest)
    _write(os.path.join(root, '.product-flow', 'run-manifest.json'), {
        'schemaVersion': '1.0',
        'activeRunId': run_id,
        'manifestRef': manifest_rel,
        'manifestHash': sha256_file(manifest_path),
    })
    gates = gate_result_dir(root, manifest)
    for gate in manifest['requiredGates']:
        rule_ids = sorted(item['ruleId'] for item in manifest['gatePlan']
                          if item['gate'] == gate and item['required'])
        _write(os.path.join(gates, gate + '.json'), {
            'verdict': 'PASS',
            'runId': run_id,
            'planHash': manifest['planHash'],
            'ruleIds': rule_ids,
            'claimEligible': True,
        })
    output_path = os.path.join(root, 'definition.md')
    with io.open(output_path, 'w', encoding='utf-8') as f:
        f.write('已确认的需求定义')
    draft_path = os.path.join(root, 'draft.json')
    _write(draft_path, {
        'moduleId': 'S1',
        'claimCeiling': 'module-approved',
        'inputs': [{'ref': 'user-confirmed-intent'}],
        'outputs': [{'ref': output_path, 'authority': 'S1'}],
        'limitations': ['只验证 S1，不验证下游采用'],
    })
    result_path = issue_result(root, draft_path)
    verified = verify_result(result_path)
    chk('正例：模块结果可签发、不可变哈希可复验',
        verified['moduleId'] == 'S1' and verified['claimCeiling'] == 'module-approved')

    tampered_path = os.path.join(root, 'tampered.json')
    tampered = _read(result_path, 'module result')
    tampered['limitations'] = ['篡改后的限制']
    _write(tampered_path, tampered)
    try:
        verify_result(tampered_path)
        caught, message = False, ''
    except WorkflowError as e:
        caught, message = True, str(e)
    chk('反例：篡改签发结果必须拒绝（锚定 moduleResultHash 判据）',
        caught and 'moduleResultHash 不匹配' in message,
        '实得 %s' % (message or '未拒绝'))

    try:
        issue_result(root, draft_path)
        caught, message = False, ''
    except WorkflowError as e:
        caught, message = True, str(e)
    chk('反例：重复签发不得覆盖既有结果（锚定拒绝覆盖判据）',
        caught and '拒绝覆盖已有文件' in message,
        '实得 %s' % (message or '未拒绝'))

    restricted = dict(resolve_plan('only', ['S1'], evidence_capability='unavailable'))
    restricted.update({
        'runId': 'PF-module-contract-unavailable',
        'createdAt': '2026-09-12T00:00:00+00:00',
        'inputs': [],
        'inputsHash': _sha([]),
        'assumptions': [],
        'openDecisions': [],
        'stopLines': [],
        'requiredBackfills': [],
        'supersedesRunId': '',
    })
    restricted_rel = os.path.join('runs', restricted['runId'], 'run-manifest.json')
    restricted_path = os.path.join(root, '.product-flow', restricted_rel)
    _write(restricted_path, restricted)
    _write(os.path.join(root, '.product-flow', 'run-manifest.json'), {
        'schemaVersion': '1.0',
        'activeRunId': restricted['runId'],
        'manifestRef': restricted_rel,
        'manifestHash': sha256_file(restricted_path),
    })
    overclaim_path = os.path.join(root, 'overclaim.json')
    _write(overclaim_path, {
        'moduleId': 'S1',
        'claimCeiling': 'module-approved',
        'inputs': [{'ref': 'evidence-unavailable'}],
        'outputs': [{'ref': output_path, 'authority': 'S1'}],
        'limitations': ['原生证据不可得'],
    })
    try:
        issue_result(root, overclaim_path)
        caught, message = False, ''
    except WorkflowError as e:
        caught, message = True, str(e)
    chk('反例：证据不可得时不得签发越级结果（锚定当前运行 claimCeiling）',
        caught and '当前运行上限 draft' in message,
        '实得 %s' % (message or '未拒绝'))
    shutil.rmtree(root, ignore_errors=True)

    print('\n%s' % ('✅ 自证通过：模块签发与复验判据可信' if ok
                     else '❌ 自证失败：模块签发或复验判据失真'))
    return 0 if ok else 1


if __name__ == '__main__':
    import sys
    if '--help' in sys.argv:
        print(__doc__ or '')
        print('用法: _module_contract.py --self-test')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    print('UNABLE: 本模块只提供共享判据；请使用 --self-test', file=sys.stderr)
    sys.exit(2)
