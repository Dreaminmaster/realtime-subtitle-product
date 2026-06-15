#!/usr/bin/env python3
"""Orchestrator with Popen pip, subprocess model, clean env, real cancel."""
import os, json, subprocess, sys, time, threading
from setup_states import SetupStateMachine, SetupStage

SETUP_FILE = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle/.setup_state.json")
RESOURCES = os.path.dirname(os.path.abspath(__file__))
APP_SUPPORT = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle")
VENV_DIR = os.path.join(APP_SUPPORT, "venv")
VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python3")
CORE_PACKAGES = ("PyQt6","numpy","sounddevice","faster_whisper","httpx","openai")

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
            self._emit(self.sm.begin_stage(stage))
            ok = self._stage_map[stage]()
            if self._cancel_requested or self._cancel_event.is_set():
                return False
            if not ok:
                self._emit(self.sm.fail_stage("Stage failed"))
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

    def _run_process(self, cmd, timeout=300):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=_child_env())
        with self._process_lock:
            self._active_process = proc
        try:
            try:
                _out, _err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._kill_process(proc)
                return False
            if self._cancel_requested:
                return False
            return proc.returncode == 0
        except OSError:
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
        pip = os.path.join(VENV_DIR,"bin","pip")
        req = os.path.join(RESOURCES,"requirements-core.txt")
        if not os.path.exists(req):
            return False
        if not self._run_process([pip,"install","--no-cache-dir","--upgrade","pip"],60):
            return False
        if self._cancel_requested: return False
        if not self._run_process([pip,"install","--no-cache-dir","-r",req],600):
            return False
        for pkg in CORE_PACKAGES:
            if not self._run_process([VENV_PYTHON,"-c",f"import {pkg}"],15):
                return False
            if self._cancel_requested: return False
        self._saved_requirements_hash = _requirements_fingerprint()
        return True

    def _step_download_model(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([VENV_PYTHON,rt,"download-model",self.sm.model_id],600)

    def _step_verify(self):
        rt = os.path.join(RESOURCES,"setup_runtime.py")
        if not os.path.exists(rt) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process([VENV_PYTHON,rt,"verify-model",self.sm.model_id],120)

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
                    fail = not self._run_process([VENV_PYTHON,rt,"verify-model",self.sm.model_id],30)
            if fail:
                for j in range(i,len(order)):
                    s = order[j]
                    if s in self.sm.completed:
                        self.sm.completed.discard(s)
                        removed.append(s)
                break
        return len(self.sm.completed), removed

    def _emit(self, event):
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
