#!/usr/bin/env python3
"""Orchestrator: runs each first-launch step with retry, cancel, events, and state save."""
import os, json, subprocess, sys, tempfile, time
from setup_states import SetupStateMachine, SetupStage

SETUP_FILE = os.path.expanduser(
    "~/Library/Application Support/RealtimeSubtitle/.setup_state.json")
RESOURCES = os.path.dirname(os.path.abspath(__file__))

CORE_PACKAGES = ("PyQt6", "numpy", "sounddevice", "faster_whisper", "httpx", "openai")


class SetupController:
    EXECUTION_ORDER = (SetupStage.CHECK_SYSTEM, SetupStage.CREATE_ENV,
                       SetupStage.INSTALL_DEPENDENCIES, SetupStage.DOWNLOAD_MODEL,
                       SetupStage.VERIFY)

    def __init__(self, model_id="tiny", event_callback=None):
        import threading
        self.sm = SetupStateMachine(model_id)
        self._event_cb = event_callback
        self._cancel_requested = False
        self._active_process = None
        self._cancel_event = threading.Event()  # for model download cancel
        self._stage_map = {
            SetupStage.CHECK_SYSTEM:          self._step_check_system,
            SetupStage.CREATE_ENV:            self._step_create_env,
            SetupStage.INSTALL_DEPENDENCIES:  self._step_install_deps,
            SetupStage.DOWNLOAD_MODEL:        self._step_download_model,
            SetupStage.VERIFY:                self._step_verify,
        }
        assert SetupStage.READY not in self._stage_map, "READY must not be in stage_map"
        self._load()

    # ---- public API ----

    def resume(self):
        """Run all incomplete stages. Returns True if all complete, emits READY."""
        passed, removed = self._pre_verify_completed()
        for stage in self.EXECUTION_ORDER:
            if stage in self.sm.completed:
                continue
            if self._cancel_requested:
                return False
            self._emit(self.sm.begin_stage(stage))
            ok = self._stage_map[stage]()
            if ok:
                self._emit(self.sm.complete_stage(stage))
                self.sm.completed.add(stage)
                self._save()
            else:
                self._emit(self.sm.fail_stage("Stage failed"))
                return False
        self._emit(self.sm.ready())
        return True

    def cancel(self):
        self._cancel_requested = True
        self._cancel_event.set()
        if self._active_process and self._active_process.poll() is None:
            self._active_process.terminate()
            try: self._active_process.wait(timeout=5)
            except subprocess.TimeoutExpired: self._active_process.kill()
        self._active_process = None
        self._emit(self.sm.cancel())

    # ---- internal ----

    def _emit(self, event):
        if self._event_cb:
            self._event_cb(event)

    def _pre_verify_completed(self):
        """Re-validate completed stages. Cascade: failing one clears all downstream."""
        removed = []
        stage_order = list(self.EXECUTION_ORDER)
        for i, stage in enumerate(stage_order):
            if stage not in self.sm.completed:
                continue
            verifier = {
                SetupStage.CREATE_ENV: self._verify_env_exists,
                SetupStage.INSTALL_DEPENDENCIES: self._verify_deps_importable,
                SetupStage.DOWNLOAD_MODEL: self._verify_model_on_disk,
            }.get(stage)
            if verifier and not verifier():
                # Cascade: clear this stage and all subsequent
                for j in range(i, len(stage_order)):
                    s = stage_order[j]
                    if s in self.sm.completed:
                        self.sm.completed.discard(s)
                        removed.append(s)
                break
        return len(self.sm.completed), removed

    def _verify_env_exists(self):
        venv = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle/venv")
        return os.path.exists(os.path.join(venv, "bin", "python3"))

    def _verify_deps_importable(self):
        venv = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle/venv")
        py = os.path.join(venv, "bin", "python3")
        try:
            subprocess.run([py, "-c", "import " + ", ".join(CORE_PACKAGES)],
                           capture_output=True, timeout=15, check=True)
            return True
        except subprocess.SubprocessError:
            return False

    def _verify_model_on_disk(self):
        """Check model dir exists, has key files, and is loadable."""
        try:
            from model_manager import model_manager
            models = model_manager.get_models('whisper')
            m = next((x for x in models if x['id'] == self.sm.model_id), None)
            if not m or not m.get('downloaded'):
                return False
            ckpt = model_manager.get_model_path(self.sm.model_id, 'whisper')
            if not ckpt or not os.path.isdir(ckpt):
                return False
            for _root, _dirs, files in os.walk(ckpt):
                if files: return True
            return False
        except Exception:
            return False

    def _step_check_system(self):
        """Verify minimum system requirements."""
        import platform, shutil
        try:
            assert platform.system() == "Darwin", "macOS required"
            assert platform.machine() in ("arm64","aarch64"), "Apple Silicon required"
            bundled_py = os.path.join(RESOURCES, "python", "bin", "python3")
            assert os.access(bundled_py, os.X_OK), f"Bundled Python not executable: {bundled_py}"
            req_file = os.path.join(RESOURCES, "requirements-core.txt")
            assert os.path.isfile(req_file), f"requirements-core.txt missing: {req_file}"
            app_support = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle")
            os.makedirs(app_support, exist_ok=True)
            assert os.access(app_support, os.W_OK), f"Application Support not writable: {app_support}"
            free_gb = shutil.disk_usage(app_support).free / (1024**3)
            assert free_gb > 1.0, f"Low disk space: {free_gb:.1f} GB free"
            return True
        except AssertionError as e:
            self._emit(self.sm.fail_stage(str(e)))
            return False

    def _step_create_env(self):
        venv_dir = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv")
        python_bin = os.path.join(RESOURCES, "python", "bin", "python3")
        if not os.path.exists(python_bin):
            python_bin = sys.executable
        if os.path.exists(os.path.join(venv_dir, "bin", "python3")):
            return True
        try:
            subprocess.run([python_bin, "-m", "venv", "--copies", venv_dir],
                           check=True, capture_output=True, timeout=120)
            return True
        except subprocess.SubprocessError:
            return False

    def _step_install_deps(self):
        pip = os.path.join(VENV_DIR, "bin", "pip")
        req = os.path.join(RESOURCES, "requirements-core.txt")
        if not os.path.exists(req):
            return False
        if not self._run_process([pip, "install", "--no-cache-dir", "--upgrade", "pip"], timeout=60):
            return False
        if self._cancel_requested:
            return False
        if not self._run_process([pip, "install", "--no-cache-dir", "-r", req], timeout=600):
            return False
        for pkg in CORE_PACKAGES:
            if not self._run_process([VENV_PYTHON, "-c", f"import {pkg}"], timeout=15):
                return False
            if self._cancel_requested:
                return False
        return True

    def _step_download_model(self):
        runtime = os.path.join(RESOURCES, "setup_runtime.py")
        if not os.path.exists(runtime) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process(
            [VENV_PYTHON, runtime, "download-model", self.sm.model_id], timeout=600)

    def _step_verify(self):
        runtime = os.path.join(RESOURCES, "setup_runtime.py")
        if not os.path.exists(runtime) or not os.path.exists(VENV_PYTHON):
            return False
        return self._run_process(
            [VENV_PYTHON, runtime, "verify-model", self.sm.model_id], timeout=120)

    def _save(self):
        data = {"schema_version": 1,
                "completed": [s.value for s in self.sm.completed],
                "model_id": self.sm.model_id,
                "updated_at": int(time.time())}
        tmp_path = SETUP_FILE + ".tmp"
        os.makedirs(os.path.dirname(SETUP_FILE), exist_ok=True)
        with open(tmp_path, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, SETUP_FILE)

    def _load(self):
        try:
            with open(SETUP_FILE) as f:
                data = json.load(f)
                for v in data.get("completed", []):
                    self.sm.completed.add(SetupStage(v))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
