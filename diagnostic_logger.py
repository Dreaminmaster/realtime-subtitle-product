#!/usr/bin/env python3
import os, json, time, platform, shutil
from app_paths import get_log_dir

LOG_DIR = os.fspath(get_log_dir())
LOG_FILE = os.path.join(LOG_DIR, "launcher.log")

_diagnostics = []

def ensure_dir():
    os.makedirs(LOG_DIR, exist_ok=True)

def log_diagnostic(stage, message, **extra):
    ensure_dir()
    safe = {}
    for k, v in extra.items():
        if k in ("api_key", "token", "password", "text", "transcript"):
            safe[k] = "***REDACTED***"
        elif isinstance(v, (str, int, float, bool, type(None))):
            safe[k] = v
        else:
            safe[k] = str(v)[:200]
    entry = {
        "stage": str(stage),
        "message": str(message),
        "time": time.strftime("%H:%M:%S"),
        "extra": safe,
    }
    _diagnostics.append(entry)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()

def get_diagnostics():
    return list(_diagnostics)

def get_system_info():
    free = "?"
    try:
        free = shutil.disk_usage(os.path.expanduser("~")).free // (1024 ** 3)
    except Exception:
        pass
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pyhome": os.environ.get("PYTHONHOME", "cleared"),
        "pypath": os.environ.get("PYTHONPATH", "cleared"),
        "home_free_gb": free,
        "log_dir": LOG_DIR,
    }

def write_full_report():
    lines = ["=== Realtime Subtitle Diagnostic Report ==="]
    for k, v in get_system_info().items():
        lines.append(f"  {k}: {v}")
    lines.append("--- Stage Log ---")
    for d in _diagnostics:
        extra = " ".join(f"{k}={v}" for k, v in d.get("extra", {}).items())
        lines.append(f"  [{d['time']}] {d['stage']}: {d['message']} {extra}")
    lines.append("=== End Report ===")
    return "\n".join(lines)
