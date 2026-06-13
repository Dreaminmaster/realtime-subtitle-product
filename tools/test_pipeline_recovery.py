#!/usr/bin/env python3
"""Test pipeline recovery signal chain via static analysis."""
import sys

errors = 0
with open('main.py') as f:
    code = f.read()

checks = [
    ('pipeline_failed signal', 'pipeline_failed = pyqtSignal'),
    ('cleanup_finished signal', 'pipeline_cleanup_finished = pyqtSignal'),
    ('_stopping init', 'self._stopping = False'),
    ('_stopping guard', 'self._stopping:'),
    ('_stopping reset in start', 'self._stopping = False'),
    ('pipeline_failed emit', 'self.signals.pipeline_failed.emit'),
    ('cleanup_finished emit', 'signals.pipeline_cleanup_finished.emit'),
    ('_failed flag', 'self._failed = True'),
    ('_cleanup_in_progress', 'self._cleanup_in_progress = True'),
]
for name, pattern in checks:
    if pattern in code:
        print(f"  OK: {name}")
    else:
        print(f"  FAIL: {name}")
        errors += 1

with open('dashboard.py') as f:
    dcode = f.read()
dchecks = [
    ('_on_pipeline_failed', '_on_pipeline_failed'),
    ('cleanup handler', '_on_pipeline_cleanup_finished'),
    ('pipeline_failed connect', 'pipeline_failed.connect'),
    ('cleanup connect', 'pipeline_cleanup_finished.connect'),
]
for name, pattern in dchecks:
    if pattern in dcode:
        print(f"  OK: {name}")
    else:
        print(f"  FAIL: {name}")
        errors += 1

print(f"=== {'PASSED' if errors == 0 else 'FAILED ' + str(errors) + ' errors'} ===")
sys.exit(errors)
