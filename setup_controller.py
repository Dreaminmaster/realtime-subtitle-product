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


class SetupController:
    EXECUTION_ORDER = (SetupStage.CHECK_SYSTEM, SetupStage.CREATE_ENV,
                       SetupStage.INSTALL_DEPENDENCIES, SetupStage.DOWNLOAD_MODEL,
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
            SetupStage.DOWNLOAD_MODEL: self._step_download_model,
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
                # Drain stderr in background thread to prevent pipe buffer deadlock
                import threading as _threading
                def _drain_stderr():
                    for _line in proc.stderr:
                        pass
                _threading.Thread(target=_drain_stderr, daemon=True).start()
                out_lines = []
                for line in proc.stdout:
                    line_str = line.decode(errors='replace').strip()
                    out_lines.append(line_str)
                    try:
                        event = json.loads(line_str)
                        t = event.get("type", "")
                        if t in ("download_fail", "verify_fail", "error"):
                            last_error = event.get("reason", str(t))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                proc.wait(timeout=timeout)
                stdout_tail = "\n".join(out_lines[-20:])
            else:
                _out, _err = proc.communicate(timeout=timeout)
                stdout_tail = (_out or b"").decode(errors='replace')[-1000:]
                stderr_tail = (_err or b"").decode(errors='replace')[-1000:]
            
            duration = _time.time() - start
            
            if self._cancel_requested:
                return False
            
            ok = proc.returncode == 0
            if not ok:
                # Build specific error from JSON-lines error or stderr
                if last_error:
                    error_msg = last_error
                else:
                    error_msg = f"exit code {proc.returncode}"
                if stderr_tail.strip():
                    error_msg = f"{error_msg}: {stderr_tail.strip()[-300:]}"
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
        req = os.path.join(RESOURCES, "requirements-core.txt")
        if not os.path.exists(req):
            self._last_error = "requirements-core.txt not found in app bundle"
            return False
        
        # Step 1: upgrade pip (use venv python3 -m pip, not bare pip binary)
        if not self._run_process(
            [VENV_PYTHON, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "pip"],
            timeout=60
        ):
            self._last_error = "pip upgrade failed: " + (self._last_error or "unknown error")
            return False
        if self._cancel_requested:
            return False
        
        # Step 2: install dependencies from requirements-core.txt
        if not self._run_process(
            [VENV_PYTHON, "-m", "pip", "install", "--no-cache-dir", "-r", req],
            timeout=600
        ):
            self._last_error = "dependency install failed: " + (self._last_error or "unknown error")
            return False
        if self._cancel_requested:
            return False
        
        self._saved_requirements_hash = _requirements_fingerprint()
        return True

    def _step_download_model(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([VENV_PYTHON,rt,"download-model",self.sm.model_id],600,parse_json=True)

    def _step_verify(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([VENV_PYTHON,rt,"verify-model",self.sm.model_id],120,parse_json=True)

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
            elif stage == SetupStage.DOWNLOAD_MODEL:
                rt = os.path.join(RESOURCES,"setup_runtime.py")
                if os.path.exists(rt) and os.path.exists(VENV_PYTHON):
                    fail = not self._run_process([VENV_PYTHON,rt,"verify-model",self.sm.model_id],30,parse_json=True)
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
