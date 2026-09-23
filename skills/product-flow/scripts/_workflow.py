#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""product-flow 运行模型：注册表读取、计划计算、manifest 验证与活动运行解析。"""
import hashlib
import io
import json
import os
import sys


SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(SKILL_ROOT, 'references', 'workflow-registry.json')
CLAIMS = ['exploration', 'draft', 'review-ready', 'module-approved',
          'integrated-frozen', 'production-validated']


class WorkflowError(ValueError):
    pass


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_registry(path=REGISTRY_PATH):
    with io.open(path, encoding='utf-8') as f:
        data = json.load(f)
    if data.get('schemaVersion') != '1.0' or not data.get('registryVersion'):
        raise WorkflowError('workflow registry schema/version 无效')
    if not isinstance(data.get('modules'), dict) or not data.get('stageOrder'):
        raise WorkflowError('workflow registry 缺 modules/stageOrder')
    unknown = [x for x in data['stageOrder'] if x not in data['modules']]
    if unknown:
        raise WorkflowError('stageOrder 含未登记模块：%s' % ', '.join(unknown))
    rules = data.get('gateRules') or []
    ids = [x.get('id') for x in rules]
    if not rules or None in ids or len(ids) != len(set(ids)):
        raise WorkflowError('gateRules 为空、缺 id 或 id 重复')
    for rule in rules:
        if rule.get('ruleType') not in ('required', 'conditional'):
            raise WorkflowError('gate rule %s 的 ruleType 无效' % rule.get('id'))
        unknown_modules = [m for m in rule.get('modules', [])
                           if m != '*' and m not in data['modules']]
        if not rule.get('gate') or unknown_modules:
            raise WorkflowError('gate rule %s 的 gate/modules 无效' % rule.get('id'))
    if data.get('claimOrder') != CLAIMS:
        raise WorkflowError('claimOrder 与运行器支持的声明阶梯不一致')
    evidence = data.get('evidenceCapabilities')
    expected_evidence = ('native', 'mixed', 'limited', 'unavailable')
    if not isinstance(evidence, dict) or set(evidence) != set(expected_evidence):
        raise WorkflowError('evidenceCapabilities 必须完整登记 native/mixed/limited/unavailable')
    evidence_claims = []
    for name in expected_evidence:
        spec = evidence.get(name)
        if not isinstance(spec, dict) or spec.get('maxClaim') not in CLAIMS:
            raise WorkflowError('evidenceCapabilities.%s.maxClaim 无效' % name)
        evidence_claims.append(CLAIMS.index(spec['maxClaim']))
    if any(left < right for left, right in zip(evidence_claims, evidence_claims[1:])):
        raise WorkflowError('evidenceCapabilities 的证据越弱，maxClaim 不得升高')
    return data, sha256_file(path)


def expand_name(registry, name):
    key = str(name).strip()
    if key in registry['modules']:
        return [key]
    if key in registry.get('aliases', {}):
        return list(registry['aliases'][key])
    raise WorkflowError('未知模块/别名：%s' % key)


def _ordered(registry, selected):
    order = list(registry['stageOrder']) + ['TESTCASES', 'REVERSE']
    return [x for x in order if x in selected]


def _matches(condition, context):
    return all(context.get(k) == v for k, v in (condition or {}).items())


def claim_min(registry, claims):
    """声明级别只可取输入中的最低级；组合与导入均单调不升高。"""
    order = registry['claimOrder']
    values = list(claims)
    if not values or any(x not in order for x in values):
        raise WorkflowError('声明级别不在 claimOrder：%s' % values)
    return min(values, key=order.index)


def gate_plan_for(registry, selected, context):
    """从唯一 gateRules 表解析 required/conditional/n-a；每项带来源 ruleId。"""
    chosen = set(selected)
    plan = []
    for rule in registry.get('gateRules', []):
        applies_to_module = '*' in rule.get('modules', []) or bool(
            chosen.intersection(rule.get('modules', [])))
        if not applies_to_module:
            continue
        item = {
            'ruleId': rule['id'],
            'gate': rule['gate'],
            'gateKind': rule.get('gateKind', 'machine'),
            'receiptBacked': bool(rule.get('receiptBacked')),
            'compositionOnly': bool(rule.get('compositionOnly')),
        }
        if rule['ruleType'] == 'required':
            item.update({'classification': 'required', 'required': True,
                         'reason': '规则 %s 对所选模块无条件适用' % rule['id']})
        elif _matches(rule.get('when'), context):
            item.update({'classification': 'conditional', 'required': True,
                         'condition': rule.get('when'),
                         'reason': '条件 %s 已满足' % json.dumps(rule.get('when'), ensure_ascii=False, sort_keys=True)})
        else:
            item.update({'classification': 'n-a', 'required': False,
                         'condition': rule.get('when'),
                         'reason': '条件 %s 未满足；由注册表计算，非人工豁免'
                                   % json.dumps(rule.get('when'), ensure_ascii=False, sort_keys=True)})
        plan.append(item)
    return plan


def required_gates_for_module(registry, module_id, context=None):
    context = context or {'productType': 'web', 'deliveryIntent': 'production',
                          'executionMode': 'handoff', 'htmlProfile': 'draft',
                          'evidenceCapability': 'native', 'researchMode': 'full-research'}
    return [x['gate'] for x in gate_plan_for(registry, [module_id], context)
            if x['required'] and not x['compositionOnly']]


def validate_full_contains_modules(registry_path=REGISTRY_PATH):
    """同一上下文下，full 必须覆盖每个成员模块的必跑门；组合专属门只允许多不能少。"""
    registry, _ = load_registry(registry_path)
    full = resolve_plan('full', product_type='dual', execution_mode='build',
                        html_profile='core-full', evidence_capability='native',
                        registry_path=registry_path)
    union = set()
    for module_id in registry['stageOrder']:
        only = resolve_plan('only', [module_id], product_type='dual',
                            execution_mode='build', html_profile='core-full',
                            evidence_capability='native', registry_path=registry_path)
        union.update(only['requiredGates'])
    missing = sorted(union.difference(full['requiredGates']))
    if missing:
        raise WorkflowError('full 缺少独立模块要求的门禁：%s' % ', '.join(missing))
    return True


def resolve_plan(mode, requested=None, start=None, product_type='web',
                 delivery_intent='production', execution_mode='handoff',
                 html_profile=None, evidence_capability='native',
                 registry_path=REGISTRY_PATH, research_mode=None):
    registry, registry_hash = load_registry(registry_path)
    requested = requested or []
    if product_type not in ('web', 'mobile', 'dual', 'other'):
        raise WorkflowError('productType 必须是 web/mobile/dual/other')
    if delivery_intent not in ('exploration', 'review', 'handoff', 'production'):
        raise WorkflowError('deliveryIntent 必须是 exploration/review/handoff/production')
    if execution_mode not in ('handoff', 'build'):
        raise WorkflowError('executionMode 必须是 handoff/build')
    evidence_profiles = registry['evidenceCapabilities']
    if evidence_capability not in evidence_profiles:
        raise WorkflowError('evidenceCapability 必须是 native/mixed/limited/unavailable')
    effective_research_mode = research_mode or 'full-research'
    if effective_research_mode not in ('teardown', 'competitive-pack', 'full-research'):
        raise WorkflowError('researchMode 必须是 teardown/competitive-pack/full-research')

    if mode == 'full':
        selected = list(registry['stageOrder'])
    elif mode == 'from':
        expanded = expand_name(registry, start or '')
        if len(expanded) != 1 or expanded[0] not in registry['stageOrder']:
            raise WorkflowError('--from 必须指向一个顺序阶段')
        selected = registry['stageOrder'][registry['stageOrder'].index(expanded[0]):]
    elif mode in ('only', 'bundle'):
        if not requested:
            raise WorkflowError('%s 模式必须指定模块' % mode)
        expanded = []
        for name in requested:
            expanded += expand_name(registry, name)
        selected = _ordered(registry, set(expanded))
        if mode == 'only' and len(set(expanded)) != 1:
            raise WorkflowError('--only 只能解析为一个模块；多模块请用 --bundle')
    elif mode == 'reverse':
        selected = ['REVERSE']
    else:
        raise WorkflowError('mode 必须是 full/from/only/bundle/reverse')

    if html_profile is None:
        html_profile = ('core-full' if mode in ('full', 'from') or 'G7.5' in selected
                        else 'standalone-interaction' if 'S6' in selected else 'draft')
    profiles = registry.get('htmlProfiles', {})
    if html_profile not in profiles:
        raise WorkflowError('未知 HTML profile：%s' % html_profile)
    if (mode in ('full', 'from') or 'G7.5' in selected) and 'S6' in selected \
            and html_profile != 'core-full':
        raise WorkflowError('完整/三方冻结路径的 S6 必须使用 core-full profile')

    context = {'productType': product_type, 'deliveryIntent': delivery_intent,
               'executionMode': execution_mode, 'htmlProfile': html_profile,
               'evidenceCapability': evidence_capability,
               'researchMode': effective_research_mode}
    outputs, external_inputs = [], []
    chosen = set(selected)
    for module_id in selected:
        module = registry['modules'][module_id]
        for dep in module.get('dependencies', []):
            if dep not in chosen:
                external_inputs.append({
                    'module': module_id,
                    'dependency': dep,
                    'contract': '导入经验证的 %s 产物，或在 Gap 中登记假设/停止线' % dep,
                })
        outputs += [{'module': module_id, 'artifact': x}
                    for x in module.get('outputs', [])]
    gate_plan = gate_plan_for(registry, selected, context)
    gates = []
    for item in gate_plan:
        if item['required'] and item['gate'] not in gates:
            gates.append(item['gate'])

    if mode == 'full':
        claim = 'production-validated'
    elif 'G7.5' in selected:
        claim = 'integrated-frozen'
    else:
        claim = claim_min(registry,
                          (registry['modules'][x].get('maxClaim', 'draft') for x in selected))
    if 'S6' in selected:
        claim = claim_min(registry, [claim, profiles[html_profile]['maxClaim']])
    claim = claim_min(registry, [claim,
                                 evidence_profiles[evidence_capability]['maxClaim']])
    plan = {
        'schemaVersion': '2.0',
        'registryVersion': registry['registryVersion'],
        'registryHash': registry_hash,
        'mode': mode,
        'requested': list(requested),
        'from': start or '',
        'productType': product_type,
        'deliveryIntent': delivery_intent,
        'executionMode': execution_mode,
        'htmlProfile': html_profile,
        'evidenceCapability': evidence_capability,
        'modules': selected,
        'externalInputs': external_inputs,
        'expectedOutputs': outputs,
        'requiredGates': gates,
        'gatePlan': gate_plan,
        'claimCeiling': claim,
    }
    # 旧调用未声明时保持历史 planHash；新运行器总会显式写入，避免破坏既有活动运行。
    if research_mode is not None:
        plan['researchMode'] = effective_research_mode
    plan['planHash'] = hashlib.sha256(canonical_bytes(plan)).hexdigest()
    return plan


def validate_manifest(manifest, registry_path=REGISTRY_PATH):
    required = ('schemaVersion', 'runId', 'registryVersion', 'registryHash', 'mode',
                'productType', 'deliveryIntent', 'executionMode', 'htmlProfile',
                'evidenceCapability', 'modules', 'requiredGates', 'gatePlan',
                'claimCeiling', 'planHash', 'inputs', 'inputsHash')
    missing = [k for k in required if k not in manifest]
    if missing:
        raise WorkflowError('run manifest 缺字段：%s' % ', '.join(missing))
    if manifest.get('inputsHash') != hashlib.sha256(canonical_bytes(manifest.get('inputs'))).hexdigest():
        raise WorkflowError('run manifest 的 inputsHash 与 inputs 不一致')
    expected = resolve_plan(
        manifest['mode'], manifest.get('requested') or [], manifest.get('from') or None,
        manifest['productType'], manifest['deliveryIntent'], manifest['executionMode'],
        manifest['htmlProfile'], manifest['evidenceCapability'], registry_path,
        manifest.get('researchMode'))
    for key in ('registryVersion', 'registryHash', 'modules', 'externalInputs',
                'expectedOutputs', 'requiredGates', 'gatePlan', 'claimCeiling', 'planHash'):
        if manifest.get(key) != expected.get(key):
            raise WorkflowError('run manifest 的 %s 与注册表重算结果不一致' % key)
    return expected


def load_active_run(root, required=False, registry_path=REGISTRY_PATH):
    pointer = os.path.join(root, '.product-flow', 'run-manifest.json')
    if not os.path.isfile(pointer):
        if required:
            raise WorkflowError('缺 .product-flow/run-manifest.json 活动运行指针')
        return None, None
    with io.open(pointer, encoding='utf-8') as f:
        data = json.load(f)
    if data.get('activeRunId') and data.get('manifestRef'):
        ref = data['manifestRef']
        path = ref if os.path.isabs(ref) else os.path.join(root, '.product-flow', ref)
        with io.open(path, encoding='utf-8') as f:
            manifest = json.load(f)
        if manifest.get('runId') != data.get('activeRunId'):
            raise WorkflowError('活动运行指针与 manifest.runId 不一致')
        validate_manifest(manifest, registry_path)
        if data.get('manifestHash') != sha256_file(path):
            raise WorkflowError('活动运行 manifestHash 与文件不一致')
        return manifest, path
    # v1 兼容只用于读取旧项目；它没有机器计算的必跑集合。
    if data.get('runId') or 'applicableGates' in data:
        return data, pointer
    raise WorkflowError('run-manifest.json 既不是 v2 指针也不是可识别的 v1 manifest')


def gate_result_dir(root, manifest=None):
    if manifest and manifest.get('schemaVersion') == '2.0' and manifest.get('runId'):
        return os.path.join(root, '.product-flow', 'runs', manifest['runId'], 'gates')
    return os.path.join(root, '.product-flow', 'gates')


def _self_test():
    """注册表与计划计算的最小承重自证。"""
    import shutil
    import tempfile

    ok = True

    def chk(name, condition, detail=''):
        nonlocal ok
        passed = bool(condition)
        ok = ok and passed
        print(('  ✅ ' if passed else '  ❌ ') + name
              + ('' if passed or not detail else '　' + detail))

    registry, _ = load_registry()
    expected = {
        # native 只是不再额外降级；完整运行仍受 core-full 的 integrated-frozen 上限约束。
        'native': 'integrated-frozen',
        'mixed': 'module-approved',
        'limited': 'review-ready',
        'unavailable': 'draft',
    }
    actual = {name: resolve_plan('full', product_type='dual', execution_mode='build',
                                 evidence_capability=name)['claimCeiling']
              for name in expected}
    for name in expected:
        chk('正例：evidenceCapability=%s 的 claimCeiling=%s' % (name, expected[name]),
            actual[name] == expected[name], '实得 %s' % actual[name])
    chk('正例：证据能力下降时声明上限严格单调不升高',
        all(CLAIMS.index(actual[left]) > CLAIMS.index(actual[right])
            for left, right in zip(('native', 'mixed', 'limited'),
                                   ('mixed', 'limited', 'unavailable'))))

    temp_dir = tempfile.mkdtemp(prefix='workflow-selftest-')
    bad_path = os.path.join(temp_dir, 'registry.json')
    bad = json.loads(json.dumps(registry, ensure_ascii=False))
    bad['evidenceCapabilities']['limited']['maxClaim'] = 'production-validated'
    with io.open(bad_path, 'w', encoding='utf-8') as f:
        json.dump(bad, f, ensure_ascii=False)
    try:
        load_registry(bad_path)
        caught, message = False, ''
    except WorkflowError as e:
        caught, message = True, str(e)
    chk('反例：较弱证据档不得反向抬高声明上限（锚定 evidenceCapabilities 单调判据）',
        caught and 'evidenceCapabilities' in message and '不得升高' in message,
        '实得 %s' % (message or '未拒绝'))
    shutil.rmtree(temp_dir, ignore_errors=True)

    print('\n%s' % ('✅ 自证通过：流程注册表与声明上限接线可信' if ok
                     else '❌ 自证失败：流程注册表或声明上限失真'))
    return 0 if ok else 1


if __name__ == '__main__':
    if '--help' in sys.argv:
        print(__doc__ or '')
        print('用法: _workflow.py --self-test')
        sys.exit(0)
    if '--self-test' in sys.argv:
        sys.exit(_self_test())
    print('UNABLE: 本模块只提供共享判据；请使用 --self-test', file=sys.stderr)
    sys.exit(2)
