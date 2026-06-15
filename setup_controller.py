#!/usr/bin/env python3
"""Orchestrator: runs each first-launch step with retry, cancel, and state save."""
import os, json, subprocess, sys
from setup_states import SetupStateMachine, SetupStage

SETUP_FILE = os.path.expanduser("~/Library/Application Support/RealtimeSubtitle/.setup_state.json")
RESOURCES = os.path.dirname(os.path.abspath(__file__))


class SetupController:
    EXECUTION_ORDER = (
        SetupStage.CHECK_SYSTEM,
        SetupStage.CREATE_ENV,
        SetupStage.INSTALL_DEPENDENCIES,
        SetupStage.DOWNLOAD_MODEL,
        SetupStage.VERIFY,
    )

    def __init__(self, model_id="tiny", event_callback=None):
        self.sm = SetupStateMachine(model_id)
        self._event_cb = event_callback
        self._load()
        self._stage_map = {
            SetupStage.CHECK_SYSTEM:    self._step_check_system,
            SetupStage.CREATE_ENV:      self._step_create_env,
            SetupStage.INSTALL_DEPENDENCIES: self._step_install_deps,
            SetupStage.DOWNLOAD_MODEL:  self._step_download_model,
            SetupStage.VERIFY:          self._step_verify,
        }
        self._cancel_requested = False
        self._active_process = None

    EXECUTION_ORDER = (
        SetupStage.CHECK_SYSTEM,
        SetupStage.CREATE_ENV,
        SetupStage.INSTALL_DEPENDENCIES,
        SetupStage.DOWNLOAD_MODEL,
        SetupStage.VERIFY,
    )

    def resume(self):
        """Run all incomplete stages. Returns True if all complete."""
        for stage in self.EXECUTION_ORDER:
            if stage in self.sm.completed:
                continue
            if self._cancel_requested:
                return False
            if not self._run_stage(stage):
                return False
        return True

    def cancel(self):
        self._cancel_requested = True

    def _run_stage(self, stage):
        progress = self._stage_map[stage]()
        if progress:
            self.sm.complete_stage(stage)
            self._save()
            return True
        return False

    def _step_check_system(self) -> bool:
        try:
            sys.executable
            return True
        except Exception:
            return False

    def _step_create_env(self) -> bool:
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

    def _step_install_deps(self) -> bool:
        venv_dir = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv")
        pip = os.path.join(venv_dir, "bin", "pip")
        req = os.path.join(RESOURCES, "requirements-core.txt")
        try:
            subprocess.run([pip, "install", "--no-cache-dir", "--upgrade", "pip"],
                           capture_output=True, timeout=60)
            subprocess.run([pip, "install", "--no-cache-dir", "-r", req],
                           capture_output=True, timeout=300)
            # Quick import check
            subprocess.run([os.path.join(venv_dir, "bin", "python3"),
                            "-c", "import PyQt6; print('ok')"],
                           capture_output=True, timeout=15, check=True)
            return True
        except subprocess.SubprocessError:
            return False

    def _step_download_model(self) -> bool:
        from model_manager import model_manager
        try:
            model_manager.download_model_sync(self.sm.model_id, "whisper")
            return True
        except Exception:
            return False

    def _step_verify(self) -> bool:
        venv_dir = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv")
        py = os.path.join(venv_dir, "bin", "python3")
        try:
            subprocess.run([py, "-c",
                            "import PyQt6, numpy, sounddevice; print('imports ok')"],
                           capture_output=True, timeout=10, check=True)
            return True
        except subprocess.SubprocessError:
            return False

    def _save(self):
        os.makedirs(os.path.dirname(SETUP_FILE), exist_ok=True)
        with open(SETUP_FILE, 'w') as f:
            json.dump({"completed": [s.value for s in self.sm.completed],
                       "model_id": self.sm.model_id}, f)

    def _load(self):
        try:
            with open(SETUP_FILE) as f:
                data = json.load(f)
                for v in data.get("completed", []):
                    self.sm.completed.add(SetupStage(v))
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
