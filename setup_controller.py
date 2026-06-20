#!/usr/bin/env python3
"""Orchestrator with Popen pip, subprocess model, clean env, real cancel."""
import os, json, subprocess, sys, time, threading
from setup_states import SetupStateMachine, SetupStage

SETUP_FILE = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle/.setup_state.json")
RESOURCES = os.path.dirname(os.path.abspath(__file__))
APP_SUPPORT = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle")
VENV_DIR = os.path.join(APP_SUPPORT, "venv")
VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python3")

def _child_env():
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["VIRTUAL_ENV"] = VENV_DIR
    return env

def _requirements_fingerprint():
    try:
        import hashlib
        with open(os.path.join(RESOURCES,"requirements-core.txt"),"rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception:
        return "unknown"


def _get_local_pip_version(venv_python):
    """Return (major, minor) tuple or None."""
    try:
        proc = subprocess.run(
            [venv_python, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=15,
            env=_child_env()
        )
        if proc.returncode == 0:
            # "pip 24.0 from ..." — extract version
            parts = proc.stdout.strip().split()
            if len(parts) >= 2:
                ver = parts[1].split(".")
                return tuple(int(v) for v in ver[:2])
    except Exception:
        pass
    return None


class SetupController:
    EXECUTION_ORDER = (SetupStage.CHECK_SYSTEM, SetupStage.CREATE_ENV,
                       SetupStage.INSTALL_DEPENDENCIES, SetupStage.PREPARE_DEFAULT_MODEL,
                       SetupStage.VERIFY)

    def __init__(self, model_id="tiny", event_callback=None):
        self.sm = SetupStateMachine(model_id)
        self._event_cb = event_callback
        self._cancel_requested = False
        self._active_process = None
        self._process_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._saved_requirements_hash = None
        self._last_error = None
        self._stage_map = {
            SetupStage.CHECK_SYSTEM: self._step_check_system,
            SetupStage.CREATE_ENV: self._step_create_env,
            SetupStage.INSTALL_DEPENDENCIES: self._step_install_deps,
            SetupStage.PREPARE_DEFAULT_MODEL: self._step_prepare_default_model,
            SetupStage.VERIFY: self._step_verify,
        }
        self._load()

    def resume(self):
        passed, _ = self._pre_verify_completed()
        for stage in self.EXECUTION_ORDER:
            if stage in self.sm.completed:
                continue
            if self._cancel_requested:
                return False
            self._last_error = None
            self._emit(self.sm.begin_stage(stage))
            ok = self._stage_map[stage]()
            if self._cancel_requested or self._cancel_event.is_set():
                return False
            if not ok:
                msg = self._last_error or f"{STAGE_LABELS.get(stage, stage)} failed"
                self._emit(self.sm.fail_stage(msg))
                return False
            self._emit(self.sm.complete_stage(stage))
            self.sm.completed.add(stage)
            self._save()
        self._emit(self.sm.ready())
        return True

    def cancel(self):
        self._cancel_requested = True
        self._cancel_event.set()
        self._kill_active_process()
        self._emit(self.sm.cancel())

    def _run_process(self, cmd, timeout=300, parse_json=False):
        """Execute via Popen with clean env. Captures stdout/stderr tail on failure.
        Sets self._last_error on failure with returncode + stderr info.
        Logs detailed spawn/completion/failure/timeout to diagnostic log.
        Never emits stage events — caller (resume) handles that once."""
        import time as _time
        start = _time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=_child_env())
        from diagnostic_logger import log_diagnostic
        log_diagnostic("process", "spawned", command=" ".join(cmd), timeout=timeout)
        with self._process_lock:
            self._active_process = proc
        
        last_error = ""
        stdout_tail = ""
        stderr_tail = ""
        
        try:
            if parse_json:
                # Collect stderr in background thread (don't discard!)
                import threading as _threading
                stderr_lines = []  # mutable list for thread-safe-ish capture
                def _collect_stderr():
                    try:
                        for line in proc.stderr:
                            stderr_lines.append(line.decode(errors='replace').rstrip())
                    except Exception:
                        pass
                _threading.Thread(target=_collect_stderr, daemon=True).start()
                out_lines = []
                for line in proc.stdout:
                    line_str = line.decode(errors='replace').strip()
                    if not line_str:
                        continue
                    out_lines.append(line_str)
                    try:
                        event = json.loads(line_str)
                        t = event.get("type", "")
                        # All known failure types from setup_runtime.py
                        if t.endswith("_fail") or t in ("error", "internal_error",
                            "usage_error", "import_error"):
                            last_error = event.get("message") or t
                            # Save the full error event for display
                            self._last_json_error = event
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # Non-JSON line — keep it in stdout_tail for diagnostics
                        pass
                proc.wait(timeout=timeout)
                stdout_tail = "\n".join(out_lines[-30:])
                # Wait briefly for stderr thread to finish
                _time.sleep(0.05)
                if stderr_lines:
                    stderr_tail = "\n".join(stderr_lines[-40:])
            else:
                _out, _err = proc.communicate(timeout=timeout)
                stdout_tail = (_out or b"").decode(errors='replace')[-1000:]
                stderr_tail = (_err or b"").decode(errors='replace')[-1000:]
            
            duration = _time.time() - start
            
            if self._cancel_requested:
                return False
            
            ok = proc.returncode == 0
            if not ok:
                # Build the best error message available
                if last_error:
                    error_msg = last_error
                else:
                    error_msg = f"exit code {proc.returncode}"

                # Append stderr if we have it (tracebacks, etc.)
                if stderr_tail.strip():
                    stderr_preview = stderr_tail.strip()[-500:]
                    error_msg = f"{error_msg}\n--- stderr ---\n{stderr_preview}"
                elif stdout_tail.strip() and not parse_json:
                    error_msg = f"{error_msg}: {stdout_tail.strip()[-300:]}"

                self._last_error = error_msg
                log_diagnostic("process", "failed",
                               returncode=proc.returncode,
                               error=error_msg[:500],
                               duration_ms=int(duration * 1000))
            else:
                log_diagnostic("process", "completed",
                               returncode=0,
                               duration_ms=int(duration * 1000))
            return ok
            
        except subprocess.TimeoutExpired:
            self._kill_process(proc)
            duration = _time.time() - start
            self._last_error = f"timed out after {timeout}s"
            log_diagnostic("process", "timeout",
                           timeout=timeout,
                           duration_ms=int(duration * 1000))
            return False
        except OSError as e:
            self._last_error = f"OS error: {e}"
            log_diagnostic("process", "os_error", error=str(e)[:300])
            return False
        finally:
            with self._process_lock:
                if self._active_process is proc:
                    self._active_process = None

    def _kill_active_process(self):
        with self._process_lock:
            proc = self._active_process
        self._kill_process(proc)
        with self._process_lock:
            self._active_process = None

    @staticmethod
    def _kill_process(proc):
        if proc and proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: pass

    def _step_check_system(self):
        import platform, shutil
        try:
            assert platform.system()=="Darwin"
            assert platform.machine() in ("arm64","aarch64")
            assert os.access(os.path.join(RESOURCES,"python","bin","python3"),os.X_OK)
            assert os.path.isfile(os.path.join(RESOURCES,"requirements-core.txt"))
            os.makedirs(APP_SUPPORT,exist_ok=True)
            assert os.access(APP_SUPPORT,os.W_OK)
            free_gb = shutil.disk_usage(APP_SUPPORT).free/(1024**3)
            assert free_gb>1.5
            return True
        except AssertionError:
            return False

    def _step_create_env(self):
        if os.path.exists(VENV_PYTHON):
            return True
        bundled = os.path.join(RESOURCES,"python","bin","python3")
        return self._run_process([bundled,"-m","venv","--copies",VENV_DIR],timeout=120)

    def _step_install_deps(self):
        """Install pip dependencies in 4 sub-steps.
        pip upgrade failure is non-blocking (warning, continue)."""
        stage_label = "Install dependencies"
        req = os.path.join(RESOURCES, "requirements-core.txt")
        if not os.path.exists(req):
            self._last_error = "requirements-core.txt not found in app bundle"
            return False

        # 1. Check pip — blocking
        self._emit_progress(stage_label, "Check pip…")
        self._last_error = None
        if not self._run_process(
            [VENV_PYTHON, "-m", "pip", "--version"],
            timeout=30
        ):
            self._last_error = "pip not available: " + (self._last_error or "unknown error")
            return False
        self._emit_progress(stage_label, "Check pip ✓")
        if self._cancel_requested:
            return False

        # 2. Optional pip upgrade — non-blocking, warn on failure.
        # Check if pip is already recent enough to skip the lengthy upgrade.
        self._emit_progress(stage_label, "Optional pip upgrade…")
        local_pip_ver = _get_local_pip_version(VENV_PYTHON)
        if local_pip_ver is not None and local_pip_ver >= (24, 0):
            self._emit_progress(stage_label, "Optional pip upgrade ✓ (pip already recent)")
        else:
            if local_pip_ver is not None:
                self._emit_progress(stage_label,
                    f"Optional pip upgrade… (pip {local_pip_ver[0]}.{local_pip_ver[1]}, upgrading to latest)")
            upgrade_ok = self._run_process(
                [VENV_PYTHON, "-m", "pip", "install",
                 "--disable-pip-version-check", "--no-input",
                 "--upgrade", "pip"],
                timeout=180
            )
            if not upgrade_ok:
                warning = "pip upgrade failed: " + (self._last_error or "unknown error") + \
                          ", continuing with existing pip"
                self._emit_progress(stage_label, "⚠ " + warning)
                self._last_error = None  # clear, don't propagate
            else:
                self._emit_progress(stage_label, "Optional pip upgrade ✓")
        if self._cancel_requested:
            return False

        # 3. Install requirements-core.txt from bundled wheelhouse — blocking (offline)
        wheelhouse = os.path.join(RESOURCES, "wheelhouse")
        self._emit_progress(stage_label, "Install requirements-core.txt…")

        if os.path.isdir(wheelhouse) and os.listdir(wheelhouse):
            whl_count = len([f for f in os.listdir(wheelhouse) if f.endswith(".whl")])
            from diagnostic_logger import log_diagnostic
            log_diagnostic("Install dependencies", "Install requirements-core.txt",
                           dependency_source="wheelhouse", network_required=False,
                           wheelhouse_path=wheelhouse, wheel_count=whl_count)
        else:
            self._last_error = (
                "Bundled dependency packages are missing. "
                "This app bundle is incomplete. Please re-download the DMG."
            )
            from diagnostic_logger import log_diagnostic
            log_diagnostic("Install dependencies", "Install requirements-core.txt",
                           dependency_source="wheelhouse", network_required=False,
                           error="wheelhouse_missing")
            return False

        self._last_error = None
        if not self._run_process(
            [VENV_PYTHON, "-m", "pip", "install",
             "--no-index",
             "--find-links", wheelhouse,
             "--disable-pip-version-check", "--no-input",
             "-r", req],
            timeout=120
        ):
            pip_error = self._last_error or "unknown"
            self._last_error = (
                "Could not install bundled dependencies. "
                "The app bundle may be corrupted. Please re-download the DMG."
            )
            from diagnostic_logger import log_diagnostic
            log_diagnostic("Install dependencies", "Install requirements-core.txt",
                           dependency_source="wheelhouse", network_required=False,
                           error="wheelhouse_install_failed",
                           detail=str(pip_error)[:300])
            return False
        self._emit_progress(stage_label, "Install requirements-core.txt ✓")
        if self._cancel_requested:
            return False

        # 4. Verify critical imports — blocking
        self._emit_progress(stage_label, "Verify imports…")
        self._last_error = None
        if not self._run_process(
            [VENV_PYTHON, "-c",
             "for m in ['faster_whisper','PyQt6','numpy','httpx']: __import__(m); print('OK')"],
            timeout=60
        ):
            self._last_error = "import verification failed: " + (self._last_error or "critical modules not importable")
            return False
        self._emit_progress(stage_label, "Verify imports ✓")

        self._saved_requirements_hash = _requirements_fingerprint()
        return True

    def _step_prepare_default_model(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([
            VENV_PYTHON, rt,
            "prepare-default-model", self.sm.model_id,
            "--resources-dir", RESOURCES,
            "--user-data-dir", APP_SUPPORT,
        ], 120, parse_json=True)

    def _step_verify(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([
            VENV_PYTHON, rt,
            "verify-model", self.sm.model_id,
            "--resources-dir", RESOURCES,
            "--user-data-dir", APP_SUPPORT,
        ], 120, parse_json=True)

    def _pre_verify_completed(self):
        removed = []
        order = list(self.EXECUTION_ORDER)
        for i, stage in enumerate(order):
            if stage not in self.sm.completed:
                continue
            fail = False
            if stage == SetupStage.CREATE_ENV and not os.path.exists(VENV_PYTHON):
                fail = True
            elif stage == SetupStage.INSTALL_DEPENDENCIES:
                if self._saved_requirements_hash and \
                   self._saved_requirements_hash != _requirements_fingerprint():
                    fail = True
            elif stage == SetupStage.PREPARE_DEFAULT_MODEL:
                rt = os.path.join(RESOURCES,"setup_runtime.py")
                if os.path.exists(rt) and os.path.exists(VENV_PYTHON):
                    fail = not self._run_process([VENV_PYTHON,rt,"verify-model",self.sm.model_id,"--resources-dir",RESOURCES,"--user-data-dir",APP_SUPPORT],30,parse_json=True)
            if fail:
                for j in range(i,len(order)):
                    s = order[j]
                    if s in self.sm.completed:
                        self.sm.completed.discard(s)
                        removed.append(s)
                break
        return len(self.sm.completed), removed

    def _emit(self, event):
        from diagnostic_logger import log_diagnostic
        stage_name = str(getattr(event, 'stage', 'event'))
        msg = str(getattr(event, 'message', ''))
        log_diagnostic(stage_name, msg)
        if self._event_cb:
            self._event_cb(event)

    def _emit_progress(self, stage_label, message):
        """Emit a sub-step progress event within the current stage."""
        from progress_events import ProgressEvent
        from setup_states import TOTAL_STAGES
        idx = SetupStage.INSTALL_DEPENDENCIES.value
        event = ProgressEvent(
            task_id="setup",
            stage=stage_label,
            message=message,
            stage_index=idx,
            total_stages=TOTAL_STAGES,
            can_cancel=True
        )
        self._emit(event)

    def _save(self):
        data = {"schema_version":1,
                "completed":[s.value for s in self.sm.completed],
                "model_id":self.sm.model_id,
                "requirements_hash":_requirements_fingerprint(),
                "updated_at":int(time.time())}
        tmp = SETUP_FILE+".tmp"
        os.makedirs(os.path.dirname(SETUP_FILE),exist_ok=True)
        with open(tmp,"w") as f:
            json.dump(data,f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,SETUP_FILE)

    def _load(self):
        try:
            with open(SETUP_FILE) as f:
                data = json.load(f)
                for v in data.get("completed",[]):
                    self.sm.completed.add(SetupStage(v))
                self._saved_requirements_hash = data.get("requirements_hash")
        except (FileNotFoundError,json.JSONDecodeError,KeyError):
            pass
