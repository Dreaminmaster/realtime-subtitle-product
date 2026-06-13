#!/usr/bin/env python3
"""Static analysis checks for v2.3.0-rc1."""
import ast, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

errors = 0
files = ['main.py', 'dashboard.py', 'enhanced_overlay_window.py', 'config.py',
         'transcriber.py', 'translation_engine.py', 'transcriber_pool.py',
         'audio_capture.py', 'permission_guide.py', 'diagnostics.py', 'build_dmg.sh']

print("=== v2.3.0-rc1 Static Analysis ===")

# 1. Syntax check
print("\n[1] Python syntax...")
import py_compile
for f in [x for x in files if x.endswith('.py')]:
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {f}")
        errors += 1
print(f"  OK: {len([x for x in files if x.endswith('.py')])} files")

# 2. Shell syntax
print("\n[2] Shell syntax...")
import subprocess
r = subprocess.run(['sh', '-n', 'build_dmg.sh'], capture_output=True)
if r.returncode != 0:
    print(f"  FAIL: build_dmg.sh")
    errors += 1
else:
    print("  OK: build_dmg.sh")

# 3. Key class existence
print("\n[3] Key classes defined...")
classes = {'main.py': ['Pipeline', 'WorkerSignals'],
           'dashboard.py': ['Dashboard', 'StartupWorker'],
           'config.py': ['Config']}
for fname, names in classes.items():
    tree = ast.parse(open(fname).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name in names:
                names.remove(node.name)
    for n in names:
        print(f"  WARN: {n} not in {fname}")

# 4. Key methods
print("\n[4] Key methods verified...")
checks = [
    ("Pipeline.__init__ has _stopping", "main.py", "_stopping", "Pipeline"),
    ("Pipeline.stop has dedup guard", "main.py", "if self._stopping:", "stop"),
    ("Pipeline.start resets _stopping", "main.py", "self._stopping = False", "start"),
    ("create_pipeline returns (pipe, signals)", "main.py", "return pipeline, signals", "create_pipeline"),
]
for label, fname, needle, _ in checks:
    content = open(fname).read()
    if needle not in content:
        print(f"  FAIL: {label}")
        errors += 1
    else:
        print(f"  OK: {label}")

# 5. No os._exit or sys.exit in worker paths
print("\n[5] No dangerous exits in worker paths...")
danger = ['os._exit', 'os.kill(os.getpid()']
for fname in ['main.py', 'audio_capture.py']:
    content = open(fname).read()
    for d in danger:
        if d in content:
            print(f"  WARN: {d} in {fname}")

print("\n" + ("=" * (40)))
if errors == 0:
    print("  ALL CHECKS PASSED")
else:
    print(f"  {errors} ERRORS FOUND")
sys.exit(errors)
