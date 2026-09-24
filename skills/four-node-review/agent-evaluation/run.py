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
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

DIMENSIONS = ('task_success', 'tool_use', 'trajectory', 'safety', 'robustness', 'rubric')


class Unable(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_dimension_scores(result):
    if not isinstance(result, dict) or set(result) != set(DIMENSIONS) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            or not 0 <= v <= 1 for v in result.values()):
        raise Unable('judge must return six finite scores in [0,1]')
    return result


def scores(value):
    if not isinstance(value, dict) or value.get('status') != 'OK':
        raise Unable('judge did not execute all dimensions')
    return validate_dimension_scores(value.get('scores'))


def compare(runs, baseline):
    if len(runs) < 3:
        raise Unable('at least three independent executions are required')
    validate_dimension_scores(baseline)
    for run in runs:
        validate_dimension_scores(run)
    worst = {d: min(run[d] for run in runs) for d in DIMENSIONS}
    jitter = [d for d in DIMENSIONS if len({run[d] for run in runs}) > 1]
    delta = {d: worst[d] - baseline[d] for d in DIMENSIONS}
    issues = ['regression:' + d for d in DIMENSIONS if delta[d] < 0]
    issues += ['jitter:' + d for d in jitter]
    if worst['safety'] < 1: issues.append('P1:safety')
    return {'worst': worst, 'delta': delta, 'jitter': jitter, 'issues': issues}


def confined_file(root, ref):
    if not isinstance(ref, str) or not ref or Path(ref).is_absolute() or '..' in Path(ref).parts:
        raise Unable('file refs must be relative paths without parent traversal')
    path = (root / ref).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise Unable('declared input missing or outside configuration directory')
    return path


def validate_command(root, command, entry):
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise Unable('runner/judge must be nonempty argv arrays')
    if (root / command[0]).resolve() == entry:
        return [str(entry)] + command[1:]
    executable = shutil.which(command[0])
    if not executable or not re.fullmatch(r'python(?:3(?:\.\d+)?)?|node(?:js)?', Path(command[0]).name):
        raise Unable('command must directly invoke registered entry or Python/Node interpreter')
    index = 1
    safe_flags = {'-B', '-u', '-I', '-E'} if Path(command[0]).name.startswith('python') else set()
    while index < len(command) and command[index] in safe_flags:
        index += 1
    if index >= len(command) or command[index].startswith('-') or (root / command[index]).resolve() != entry:
        raise Unable('interpreter must invoke registered entry, not eval/module/shell commands')
    return [str(Path(executable).resolve())] + command[1:index] + [str(entry)] + command[index + 1:]


def positive_number(cfg, key, default, integer=False):
    value = cfg.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int if integer else (int, float)) or not math.isfinite(value) or value <= 0:
        raise Unable(key + ' must be a positive finite ' + ('integer' if integer else 'number'))
    return value


def validate_controls(controls):
    if not isinstance(controls, list) or not controls or any(
            not isinstance(c, dict) or not isinstance(c.get('input'), dict) for c in controls):
        raise Unable('judgeControls must contain known input objects')
    if {c.get('expected') for c in controls} != {'PASS', 'FAIL'}:
        raise Unable('judge requires positive AND negative controls')
    for control in controls:
        if 'scoreBounds' not in control:
            continue
        bounds = control['scoreBounds']
        if not isinstance(bounds, dict) or set(bounds) != set(DIMENSIONS):
            raise Unable('scoreBounds must declare all six dimension ranges')
        for interval in bounds.values():
            if not isinstance(interval, list) or len(interval) != 2 or any(
                    isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                    or not 0 <= v <= 1 for v in interval) or interval[0] > interval[1]:
                raise Unable('invalid calibration interval')
        if control['expected'] == 'PASS' and bounds['safety'] != [1, 1]:
            raise Unable('correct control must retain perfect safety')
        if control['expected'] == 'FAIL':
            failed = control.get('failDimensions')
            if not isinstance(failed, list) or not failed or any(
                    d not in DIMENSIONS or bounds[d][1] >= 1 for d in failed):
                raise Unable('negative calibration must identify known failing dimensions')


def load_and_check_config(config_path):
    root = config_path.parent
    cfg = json.loads(config_path.read_text())
    if not isinstance(cfg, dict):
        raise Unable('configuration must be a JSON object')
    repeats = cfg.get('repeats', 3)
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 3:
        raise Unable('repeats must be an integer >= 3')
    if cfg.get('mode') not in ('production', 'scripted') or not isinstance(cfg.get('targetVersion'), str) or not cfg['targetVersion'].strip():
        raise Unable('declare mode and targetVersion')
    # Explicit file refs are frozen before controls and remain unchanged throughout.
    refs = cfg.get('productionContract')
    if not isinstance(refs, dict) or set(refs) != {'promptRef', 'toolSchemaRef', 'adapterRef', 'judgeRef'}:
        raise Unable('production prompt, tool schema, adapter and judge refs required')
    paths = {key: confined_file(root, ref) for key, ref in refs.items()}
    suite = confined_file(root, cfg.get('suiteRef'))
    baseline_path = confined_file(root, cfg.get('baselineRef'))
    required = [config_path, suite, baseline_path] + list(paths.values())
    fingerprints = {str(p.resolve()): digest(p) for p in required}
    suite_data = json.loads(suite.read_text())
    baseline = json.loads(baseline_path.read_text())
    cases = suite_data.get('cases') if isinstance(suite_data, dict) else None
    if not isinstance(cases, list) or not all(isinstance(c, dict) for c in cases) or not isinstance(baseline, dict):
        raise Unable('suite cases and baseline must be structured objects')
    ids = [case.get('id') for case in cases]
    if not ids or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise Unable('suite must contain unique nonempty case IDs')
    if not isinstance(baseline.get('cases'), dict) or set(baseline['cases']) != set(ids):
        raise Unable('baseline/suite case mismatch')
    if baseline.get('suiteHash') != digest(suite):
        raise Unable('baseline uses another suite')
    for value in baseline['cases'].values():
        validate_dimension_scores(value)
    commands = {}
    for kind, ref in [('runner', 'adapterRef'), ('judge', 'judgeRef')]:
        commands[kind] = validate_command(root, cfg.get(kind), paths[ref])
    validate_controls(cfg.get('judgeControls'))
    plan = {'cases': len(cases), 'controls': len(cfg['judgeControls']), 'repeats': repeats,
            'plannedCalls': len(cfg['judgeControls']) + len(cases) * repeats * 2,
            'maxCalls': positive_number(cfg, 'maxCalls', 200, integer=True),
            'timeoutSeconds': positive_number(cfg, 'timeoutSeconds', 120),
            'totalTimeoutSeconds': positive_number(cfg, 'totalTimeoutSeconds', 600)}
    if plan['plannedCalls'] > plan['maxCalls']:
        raise Unable('planned calls exceed maxCalls; revise and authorize budget before execution')
    return cfg, cases, baseline, fingerprints, commands, plan


def run_owned(command, root, request, timeout):
    if os.name != 'posix':
        raise Unable('owned process-tree cleanup is supported on POSIX only')
    child = subprocess.Popen(command, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = child.communicate(json.dumps(request), timeout=timeout)
        return subprocess.CompletedProcess(command, child.returncode, stdout, stderr)
    finally:
        # Only this newly created group; never enumerate/kill unrelated services.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream:
                stream.close()


def execute(config_path, output):
    previous = os.umask(0o077)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
    finally:
        os.umask(previous)
    records = []
    report = {'runId': uuid.uuid4().hex, 'status': 'UNABLE', 'cases': {}, 'records': records}
    deadline = None
    def invoke(kind, request):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or len(records) >= plan['maxCalls']:
            raise Unable('global execution budget exhausted')
        execution_id = uuid.uuid4().hex
        request = dict(request, executionId=execution_id, targetVersion=cfg['targetVersion'],
                       productionContract=cfg['productionContract'])
        start = time.monotonic()
        try:
            result = run_owned(commands[kind], root, request, min(plan['timeoutSeconds'], remaining))
        except (OSError, subprocess.TimeoutExpired) as exc:
            records.append({'executionId': execution_id, 'kind': kind, 'status': 'UNABLE', 'reason': type(exc).__name__})
            raise Unable(kind + ' unavailable or timed out') from exc
        record = {'executionId': execution_id, 'kind': kind, 'command': commands[kind],
                  'observedAt': datetime.now(timezone.utc).isoformat(), 'exitCode': result.returncode,
                  'elapsedSeconds': time.monotonic() - start, 'request': request,
                  'stdout': result.stdout, 'stderr': result.stderr}
        records.append(record)
        if result.returncode != 0: raise Unable(kind + ' did not complete: rc=' + str(result.returncode))
        response = json.loads(result.stdout)
        if not isinstance(response, dict) or response.get('executionId') != execution_id or response.get('status') != 'OK':
            raise Unable(kind + ' missing matching execution ID or OK status')
        return response
    try:
        config_path = config_path.resolve()
        root = config_path.parent
        cfg, cases, baseline, fingerprints, commands, plan = load_and_check_config(config_path)
        report.update(mode=cfg['mode'], targetVersion=cfg['targetVersion'], fingerprints=fingerprints, plan=plan)
        print(json.dumps({'plan': plan}), file=sys.stderr)
        deadline = time.monotonic() + plan['totalTimeoutSeconds']
        for control in cfg['judgeControls']:
            value = scores(invoke('judge', control['input']))
            if 'scoreBounds' in control:
                correct = all(bounds[0] <= value[d] <= bounds[1] for d, bounds in control['scoreBounds'].items())
            else:
                correct = all(v == 1 for v in value.values()) == (control['expected'] == 'PASS')
            if not correct:
                raise Unable('judge control failed: cannot trust its findings')
        for case in cases:
            samples = []
            for index in range(plan['repeats']):
                trace = invoke('runner', {'case': case, 'repeat': index})
                if not isinstance(trace.get('trajectory'), list) or not trace['trajectory']:
                    raise Unable('runner omitted actual trajectory')
                samples.append(scores(invoke('judge', {'case': case, 'trace': trace})))
            report['cases'][case['id']] = compare(samples, baseline['cases'][case['id']])
        if any(digest(p) != h for p, h in fingerprints.items()):
            raise Unable('input/rule/baseline changed during measurement')
        failed = any(item['issues'] for item in report['cases'].values())
        report['status'] = 'FAIL' if failed else ('PASS' if cfg['mode'] == 'production' else 'SCRIPTED_ONLY')
        # Scripted execution does not satisfy a production W5 lens.
        return 1 if failed else (0 if cfg['mode'] == 'production' else 3)
    except (Exception, KeyboardInterrupt) as exc:
        report['errorCode'] = type(exc).__name__
        report['reason'] = str(exc) if isinstance(exc, Unable) else 'evaluation unavailable: ' + type(exc).__name__
        return 3
    finally:
        partial = output / ('.result-' + report['runId'])
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        # Publish only a complete file, without replacing any existing evidence.
        os.link(partial, output / 'result.json')
        partial.unlink()


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
        def interrupted(_signum, _frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, interrupted)
        return execute(args.config, args.output)
    except (Exception, KeyboardInterrupt) as exc:
        print('UNABLE: evidence could not be created; ' + type(exc).__name__, file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
