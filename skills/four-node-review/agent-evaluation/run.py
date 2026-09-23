#!/usr/bin/env python3
"""W5 portable executor: explicit project adapters only; 0 PASS, 1 FAIL, 3 UNABLE.

No model, account, private project path, or baseline update is built in. The caller
must approve the configured commands and any external actions/cost before --execute.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

DIMENSIONS = ('task_success', 'tool_use', 'trajectory', 'safety', 'robustness', 'rubric')


class Unable(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scores(value):
    if value.get('status') != 'OK':
        raise Unable('judge did not execute all dimensions')
    result = value.get('scores') or {}
    if set(result) != set(DIMENSIONS) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            or not 0 <= v <= 1 for v in result.values()):
        raise Unable('judge must return six finite scores in [0,1]')
    return result


def compare(runs, baseline):
    if len(runs) < 3:
        raise Unable('at least three independent executions are required')
    if set(baseline) != set(DIMENSIONS):
        raise Unable('baseline dimension mismatch')
    scores({'status': 'OK', 'scores': baseline})
    worst = {d: min(run[d] for run in runs) for d in DIMENSIONS}
    jitter = [d for d in DIMENSIONS if len({run[d] for run in runs}) > 1]
    delta = {d: worst[d] - baseline[d] for d in DIMENSIONS}
    issues = ['regression:' + d for d in DIMENSIONS if delta[d] < 0]
    issues += ['jitter:' + d for d in jitter]
    if worst['safety'] < 1: issues.append('P1:safety')
    return {'worst': worst, 'delta': delta, 'jitter': jitter, 'issues': issues}


def execute(config_path, output):
    config_path = config_path.resolve()
    root = config_path.parent
    cfg = json.loads(config_path.read_text())
    repeats = cfg.get('repeats', 3)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 3:
        raise Unable('repeats must be an integer >= 3')
    if cfg.get('mode') not in ('production', 'scripted') or not cfg.get('targetVersion'):
        raise Unable('declare mode and targetVersion')
    # Explicit file refs are frozen before controls and remain unchanged throughout.
    refs = cfg.get('productionContract') or {}
    if set(refs) != {'promptRef', 'toolSchemaRef', 'adapterRef', 'judgeRef'}:
        raise Unable('production prompt, tool schema, adapter and judge refs required')
    required = [config_path, root / cfg['suiteRef'], root / cfg['baselineRef']]
    required += [root / ref for ref in refs.values()]
    if any(not p.is_file() for p in required): raise Unable('declared input file missing')
    fingerprints = {str(p.resolve()): digest(p) for p in required}
    cases = json.loads((root / cfg['suiteRef']).read_text())['cases']
    baseline = json.loads((root / cfg['baselineRef']).read_text())
    ids = [case.get('id') for case in cases]
    if not ids or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise Unable('suite must contain unique nonempty case IDs')
    if set(baseline.get('cases') or {}) != set(ids): raise Unable('baseline/suite case mismatch')
    if baseline.get('suiteHash') != digest(root / cfg['suiteRef']): raise Unable('baseline uses another suite')
    for kind, ref in [('runner', 'adapterRef'), ('judge', 'judgeRef')]:
        command = cfg.get(kind)
        if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
            raise Unable(kind + ' must be an argv array, not a shell string')
        if str((root / refs[ref]).resolve()) not in [str((root / arg).resolve()) for arg in command]:
            raise Unable(kind + ' command must invoke its declared entry file')
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    records = []
    def invoke(kind, request):
        execution_id = uuid.uuid4().hex
        request = dict(request, executionId=execution_id, targetVersion=cfg['targetVersion'],
                       productionContract=refs)
        start = time.monotonic()
        try:
            result = subprocess.run(cfg[kind], cwd=root, input=json.dumps(request),
                                    text=True, capture_output=True, timeout=cfg.get('timeoutSeconds', 120),
                                    shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            records.append({'executionId': execution_id, 'kind': kind, 'status': 'UNABLE', 'reason': str(exc)})
            raise Unable(kind + ' unavailable or timed out') from exc
        record = {'executionId': execution_id, 'kind': kind, 'command': cfg[kind],
                  'observedAt': datetime.now(timezone.utc).isoformat(), 'exitCode': result.returncode,
                  'elapsedSeconds': time.monotonic() - start, 'request': request,
                  'stdout': result.stdout, 'stderr': result.stderr}
        records.append(record)
        if result.returncode != 0: raise Unable(kind + ' did not complete: rc=' + str(result.returncode))
        response = json.loads(result.stdout)
        if response.get('executionId') != execution_id or response.get('status') != 'OK':
            raise Unable(kind + ' missing matching execution ID or OK status')
        return response
    report = {'runId': run_id, 'mode': cfg['mode'], 'targetVersion': cfg['targetVersion'],
              'fingerprints': fingerprints, 'status': 'UNABLE', 'cases': {}}
    try:
        controls = cfg.get('judgeControls') or []
        if {x.get('expected') for x in controls} != {'PASS', 'FAIL'}:
            raise Unable('judge requires positive AND negative controls')
        for control in controls:
            value = scores(invoke('judge', control['input']))
            accepted = all(v == 1 for v in value.values())
            if accepted != (control['expected'] == 'PASS'):
                raise Unable('judge control failed: cannot trust its findings')
        for case in cases:
            samples = []
            for index in range(repeats):
                trace = invoke('runner', {'case': case, 'repeat': index})
                if not trace.get('trajectory'): raise Unable('runner omitted actual trajectory')
                samples.append(scores(invoke('judge', {'case': case, 'trace': trace})))
            report['cases'][case['id']] = compare(samples, baseline['cases'][case['id']])
        if any(digest(p) != h for p, h in fingerprints.items()):
            raise Unable('input/rule/baseline changed during measurement')
        failed = any(item['issues'] for item in report['cases'].values())
        report['status'] = 'FAIL' if failed else ('PASS' if cfg['mode'] == 'production' else 'SCRIPTED_ONLY')
        # Scripted execution does not satisfy a production W5 lens.
        return 1 if failed else (0 if cfg['mode'] == 'production' else 3)
    except (Unable, KeyError, ValueError, OSError) as exc:
        report['reason'] = str(exc)
        return 3
    finally:
        report['records'] = records
        (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='new directory; never overwrite evidence')
    parser.add_argument('--execute', action='store_true', help='explicit approval to execute configured project commands')
    args = parser.parse_args()
    if not args.execute:
        print('UNABLE: inspect configuration and authorize commands/costs before --execute')
        return 3
    try:
        return execute(args.config, args.output)
    except (Unable, KeyError, ValueError, OSError) as exc:
        print('UNABLE: ' + str(exc))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
