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
        self.sm = SetupStateMachine(model_id)
        self._event_cb = event_callback
        self._cancel_requested = False
        self._active_process = None
        self._cancel_event = None  # threading.Event for model download cancel
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
        if self._active_process and self._active_process.poll() is None:
            self._active_process.terminate()
            try:
                self._active_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._active_process.kill()
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
        """Check model is on disk and loadable."""
        try:
            from model_manager import model_manager
            models = model_manager.get_models('whisper')
            return any(m['id'] == self.sm.model_id and m['downloaded'] for m in models)
        except Exception:
            return False

    def _step_check_system(self):
        return True

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
        venv_dir = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv")
        pip = os.path.join(venv_dir, "bin", "pip")
        req = os.path.join(RESOURCES, "requirements-core.txt")
        if not os.path.exists(req):
            return False
        try:
            subprocess.run([pip, "install", "--no-cache-dir", "--upgrade", "pip"],
                           check=True, capture_output=True, timeout=60)
            self._active_process = subprocess.Popen(
                [pip, "install", "--no-cache-dir", "-r", req],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _out, _err = self._active_process.communicate(timeout=300)
            if self._active_process.returncode != 0:
                return False
            for pkg in CORE_PACKAGES:
                subprocess.run([os.path.join(venv_dir, "bin", "python3"),
                                "-c", f"import {pkg}"],
                               check=True, capture_output=True, timeout=15)
            return True
        except subprocess.SubprocessError:
            return False
        finally:
            self._active_process = None

    def _step_download_model(self):
        from model_manager import model_manager
        try:
            model_manager.download_model_sync(self.sm.model_id, "whisper")
            return True
        except Exception:
            return False

    def _step_verify(self):
        venv_dir = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv")
        py = os.path.join(venv_dir, "bin", "python3")
        try:
            subprocess.run([py, "-c", "import " + ", ".join(CORE_PACKAGES)],
                           check=True, capture_output=True, timeout=10)
            return True
        except subprocess.SubprocessError:
            return False

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
