#!/usr/bin/env python3
"""Synthetic subprocess fixture ONLY. Never use as a production adapter/judge."""
import json
import sys

request = json.load(sys.stdin)
mode = sys.argv[2] if len(sys.argv) > 2 else 'good'
response = {'executionId': request['executionId'], 'status': 'OK'}
if sys.argv[1] == 'runner':
    response['trajectory'] = [{'synthetic': True, 'result': request['case']['input']}]
    response['repeat'] = request['repeat']
else:
    value = 0 if request.get('trace', {}).get('knownBad') else 1
    if mode == 'always-green': value = 1
    if 'repeat' in request.get('trace', {}):
        if mode == 'regression': value = 0
        if mode == 'jitter': value = request['trace']['repeat'] % 2
        if mode == 'unable': response['status'] = 'ENV-NOT-READY'
    response['scores'] = {d: value for d in
                          ('task_success', 'tool_use', 'trajectory', 'safety', 'robustness', 'rubric')}
print(json.dumps(response))
