"""Bind structured approvals to current artifacts; does not authenticate signers."""
import json
from datetime import datetime
from pathlib import Path
from _document_sync import source_hash
from _section import table_rows_at
from _image import validate_image


def inputs(context, stage):
    data = json.loads(Path(context).read_text())
    record = data.get('approvalBindings', {}).get(stage)
    if not record: raise ValueError('approval-context: 缺当前阶段批准绑定')
    base = Path(context).parent
    files = [str(Path(context))]
    if not record.get('artifacts') or not any(a.get('kind') == 'frozen-prd' for a in record['artifacts']):
        raise ValueError('approval-artifacts: 必须绑定冻结 PRD 及适用输入原物')
    for item in record.get('artifacts', []):
        path = base / item['path']
        if not path.is_file() or source_hash(path) != item.get('sha256'):
            raise ValueError('approval-stale: 批准依赖的原物缺失或已修改')
        files.append(str(path))
    for key in ('approvalEvidence', 'qualityEvidence', 'qaGuiEvidence', 'pmGuiEvidence'):
        if record.get(key):
            evidence_path = base / record[key]
            files.append(str(evidence_path))
            if key in ('qaGuiEvidence', 'pmGuiEvidence') and evidence_path.is_file():
                evidence = json.loads(evidence_path.read_text())
                files += [str(evidence_path.parent / s['screenshot']['path']) for s in evidence.get('steps', [])]
    return record, files


def gui_record(path, role, record, prd_hash):
    data = json.loads(path.read_text())
    if (data.get('role') != role or data.get('status') != 'PASS' or not data.get('sessionId')
            or not data.get('reviewer') or data.get('build') != record.get('build')
            or data.get('prdHash') != prd_hash or not data.get('steps')):
        raise ValueError('approval-gui: 实走角色/构建/PRD/会话/步骤不完整')
    start, end = (datetime.fromisoformat(data[k].replace('Z', '+00:00')) for k in ('startedAt', 'completedAt'))
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError('approval-order: GUI 时间必须带时区并有正确先后')
    for step in data['steps']:
        if any(not step.get(k) for k in ('action', 'expected', 'actual')) or step.get('status') != 'PASS':
            raise ValueError('approval-gui: 每步要有实际操作、预期与观察结果')
        shot = step.get('screenshot', {})
        image = path.parent / shot.get('path', '')
        if not image.is_file() or source_hash(image) != shot.get('sha256'):
            raise ValueError('approval-gui: 截图缺失或版本变化')
        validate_image(image)
    return data['sessionId'], start, end


def check(source, context, stage):
    try:
        record, _ = inputs(context, stage)
        if source_hash(source) != record.get('sourceHash'):
            return ['approval-stale: 批准不是当前受控源稿']
        rows = table_rows_at(Path(source).read_text(), '角色') or []
        approvals = [r for r in rows if len(r) >= 8 and r[-5].strip() in ('agent', 'human')]
        if not approvals or any(r[-3].strip() != record.get('version') or r[-2].strip() != record.get('scope') for r in approvals):
            return ['approval-version: 表内批准版本/范围与当前绑定不一致']
        base = Path(context).parent
        evidence = json.loads((base / record.get('approvalEvidence', '')).read_text())
        if evidence.get('sourceHash') != record['sourceHash'] or evidence.get('version') != record.get('version'):
            return ['approval-evidence: 审批来源不是当前内容/版本']
        decisions = evidence.get('approvals', [])
        if (evidence.get('scope') != record.get('scope') or len(decisions) != len(approvals)
                or {a.get('role') for a in decisions} != {r[0] for r in approvals}):
            return ['approval-evidence: 审批来源的角色/范围与表格不一致']
        for decision in decisions:
            row = next(r for r in approvals if r[0] == decision['role'])
            if (decision.get('actorType') != row[-5] or not decision.get('reviewer')
                    or not decision.get('authority') or decision.get('authority') != row[-4]
                    or decision.get('decision') != 'APPROVED' or not decision.get('reviewedAt')):
                return ['approval-authority: 缺真实主体、授权依据、时间或明确批准']
        if stage == 'S9.3':
            quality = json.loads((base / record.get('qualityEvidence', '')).read_text())
            qa = base / record.get('qaGuiEvidence', '')
            pm = base / record.get('pmGuiEvidence', '')
            prd = next((a for a in record.get('artifacts', []) if a.get('kind') == 'frozen-prd'), {})
            if (quality.get('status') != 'PASS' or quality.get('build') != record.get('build')
                    or not record.get('build') or not prd
                    or quality.get('prdHash') != prd.get('sha256')):
                return ['approval-order: 必须消费同一构建/冻结 PRD 的 S9.2 PASS']
            if not qa.is_file() or not pm.is_file() or source_hash(qa) == source_hash(pm):
                return ['approval-gui: QA 与 PM 必须各有独立 GUI 实走证据']
            qs, _, qe = gui_record(qa, 'qa', record, prd['sha256'])
            ps, pb, _ = gui_record(pm, 'product', record, prd['sha256'])
            passed = datetime.fromisoformat(quality['completedAt'].replace('Z', '+00:00'))
            if passed.tzinfo is None or qs == ps or not qe <= passed <= pb:
                return ['approval-order: QA 完成且 S9.2 通过后才能开始独立 PM GUI 走查']
        return []
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return ['approval-context: ' + str(exc)]


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        import runpy
        from pathlib import Path
        tests = runpy.run_path(str(Path(__file__).resolve().parents[3] / 'scripts/test-remediation-contracts.py'))
        sys.exit(tests['main']('approval'))
