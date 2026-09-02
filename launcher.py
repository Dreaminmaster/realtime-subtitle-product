import sys
import os


_MAIN_PASSTHROUGH_FLAGS = {
    "--overlay-only",
    "--diagnostics",
    "--no-permission-check",
}


def _main_cli_args(argv=None):
    """Forward only flags understood by main.py.

    LaunchServices may append private arguments such as ``-psn_*``. Passing
    those through would make argparse reject an otherwise valid app launch.
    """
    values = sys.argv if argv is None else argv
    return [arg for arg in values[1:] if arg in _MAIN_PASSTHROUGH_FLAGS]


def _build_identity():
    try:
        from version import BUILD_VERSION, BUILD_COMMIT, BUILD_TIME
        label = BUILD_VERSION if str(BUILD_VERSION).startswith("v") else f"v{BUILD_VERSION}"
        return label, BUILD_COMMIT, BUILD_TIME
    except ImportError:
        return "dev", "unknown", "unknown"


def _user_venv_python():
    from app_paths import get_venv_python

    return os.fspath(get_venv_python())


def _user_venv_gui_python():
    """Return the console-free interpreter for a normal Windows launch.

    The bootstrapper deliberately keeps ``python.exe`` for setup commands so
    their exit status and output remain observable.  The product window uses
    ``pythonw.exe`` on Windows to avoid flashing a console window.
    """
    python = _user_venv_python()
    if os.name != "nt":
        return python
    pythonw = os.path.join(os.path.dirname(python), "pythonw.exe")
    return pythonw if os.path.isfile(pythonw) else python


def _reexec_in_user_venv_for_asr_smoke():
    """Run dependency-heavy ASR diagnostics in the prepared user venv."""
    import json

    venv_python = _user_venv_python()
    if not os.path.isfile(venv_python):
        print(json.dumps({
            "type": "asr_smoke_fail",
            "error_type": "EnvironmentNotPrepared",
            "message": "Run --bootstrap-test once before --asr-smoke-test.",
        }))
        sys.exit(1)

    try:
        already_in_venv = os.path.samefile(sys.executable, venv_python)
    except OSError:
        already_in_venv = os.path.realpath(sys.executable) == os.path.realpath(venv_python)
    if already_in_venv:
        return

    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["VIRTUAL_ENV"] = os.path.dirname(os.path.dirname(venv_python))
    os.execve(
        venv_python,
        [venv_python, os.path.abspath(__file__), *sys.argv[1:]],
        env,
    )

# Handle CLI flags BEFORE PyQt6 import (avoids unnecessary GUI dependencies)
if "--version" in sys.argv:
    _version, _commit, _ = _build_identity()
    print(f"Realtime Subtitle {_version} (commit {_commit})")
    sys.exit(0)

if "--diagnose" in sys.argv:
    from diagnostic_logger import write_full_report, get_system_info
    info = get_system_info()
    info["app_version"] = _build_identity()[0]
    info["python"] = sys.version.split()[0]
    print(write_full_report())
    sys.exit(0)

if "--bootstrap-test" in sys.argv:
    """Run full bootstrap in CLI mode (no GUI). Prints JSON Lines.
    
    Usage: launcher.py --bootstrap-test [model_id]
    Exits 0 if READY, 1 if any stage fails.
    """
    from diagnostic_logger import write_full_report, get_system_info
    model_id = sys.argv[sys.argv.index("--bootstrap-test") + 1] \
        if len(sys.argv) > sys.argv.index("--bootstrap-test") + 1 \
           and not sys.argv[sys.argv.index("--bootstrap-test") + 1].startswith("--") \
        else "tiny"
    
    import json as _json
    
    class _CLIEventSink:
        def __call__(self, event):
            stage = getattr(event, 'stage', '?')
            msg = getattr(event, 'message', '')
            pct = getattr(event, 'percent', None)
            obj = {"type": "stage_event", "stage": str(stage), "message": msg}
            if pct is not None:
                obj["percent"] = pct
            print(_json.dumps(obj))
            sys.stdout.flush()
    
    from setup_controller import SetupController
    ctrl = SetupController(model_id, event_callback=_CLIEventSink())
    ok = ctrl.resume()
    
    # Gather bootstrap evidence from subprocess JSON events
    evidence = ctrl.evidence_summary()
    
    # Print final state
    info = get_system_info()
    model_source = evidence.get("model_source", "unknown")
    if model_source == "unknown":
        from app_paths import get_app_support_dir
        prepared_model = os.fspath(
            get_app_support_dir() / "models" / "whisper" / model_id
        )
        required_model_files = ("config.json", "model.bin", "tokenizer.json")
        if all(os.path.isfile(os.path.join(prepared_model, f)) for f in required_model_files):
            model_source = "user_cache"

    result = {
        "type": "bootstrap_complete",
        "success": ok,
        "ready": ok,
        "model_id": model_id,
        "app_version": _build_identity()[0],
        "python": sys.version.split()[0],
        "dependency_source": evidence.get("dependency_source", "wheelhouse"),
        "network_required": evidence.get("network_required", False),
        "model_source": model_source,
    }
    # Also include error info if present
    if "error_type" in evidence:
        result["error_type"] = evidence["error_type"]
        result["error_message"] = evidence.get("message", "")
    if ok:
        result["status"] = "READY"
    else:
        result["status"] = "FAILED"
        result["error"] = ctrl._last_error or "unknown error"
    print(_json.dumps(result))
    
    # Also write full diagnostic
    diag = write_full_report()
    from app_paths import get_log_dir
    diag_file = os.fspath(get_log_dir() / "bootstrap_test.log")
    os.makedirs(os.path.dirname(diag_file), exist_ok=True)
    with open(diag_file, "w") as f:
        f.write(diag)
    print(_json.dumps({"type": "diagnostic_log", "path": diag_file}))
    
    sys.exit(0 if ok else 1)

if "--asr-smoke-test" in sys.argv:
    """Verify ASR model loads locally offline (no GUI). Prints JSON Lines.
    
    Usage: launcher.py --asr-smoke-test [model_id]
    Requires HF_HUB_OFFLINE=1 for a real offline test.
    Exits 0 if ASR_MODEL_READY, 1 if transcriber fails to initialize.
    """
    import json as _json
    import os as _os

    _reexec_in_user_venv_for_asr_smoke()
    
    model_id = sys.argv[sys.argv.index("--asr-smoke-test") + 1] \
        if len(sys.argv) > sys.argv.index("--asr-smoke-test") + 1 \
           and not sys.argv[sys.argv.index("--asr-smoke-test") + 1].startswith("--") \
        else "tiny"
    
    print(_json.dumps({"type": "asr_smoke_start", "model_id": model_id,
                       "HF_HUB_OFFLINE": _os.environ.get("HF_HUB_OFFLINE", "not set")}))
    
    # Ensure offline
    _os.environ.setdefault("HF_HUB_OFFLINE", "1")
    _os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    
    try:
        # Resolve model path
        from model_manager import model_manager as _mm
        model_path = _mm.get_model_path(model_id, "whisper")
        if model_path:
            print(_json.dumps({"type": "asr_model_path", "path": model_path,
                               "model_source": "local"}))
            if _os.path.isdir(model_path):
                files = sorted(_os.listdir(model_path))
                print(_json.dumps({"type": "asr_model_files", "count": len(files),
                                   "files": files}))
        else:
            print(_json.dumps({"type": "asr_model_path", "path": None,
                               "model_source": "unknown", "warning": "no local path resolved"}))
            model_path = model_id
        
        # Initialize transcriber — this is the real WhisperModel load
        # Override the module-level singleton config for the test model
        import config as _cfgmod
        _original_whisper_model = _cfgmod.config.whisper_model
        _cfgmod.config.whisper_model = model_id
        
        from transcriber_pool import get_or_create_transcriber
        t = get_or_create_transcriber()
        if t is None:
            print(_json.dumps({"type": "asr_smoke_fail", "error": "get_or_create_transcriber returned None"}))
            sys.exit(1)
        
        print(_json.dumps({"type": "asr_model_ready", "asr_model_path": model_path,
                           "model_id": model_id,
                           "network_required": False,
                           "model_source": "bundled" if model_path else "unknown"}))
        print("ASR_MODEL_READY")
        
    except Exception as e:
        import traceback as _tb
        print(_json.dumps({"type": "asr_smoke_fail", "error_type": type(e).__name__,
                           "message": str(e)}))
        _tb.print_exc()
        sys.exit(1)
    
    sys.exit(0)

import subprocess
import configparser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QProgressBar, QMessageBox,
                             QPushButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

class SetupWorker(QThread):
    """Runs SetupController.resume() in background. Emits stage events."""
    stage_event = pyqtSignal(object)
    finished = pyqtSignal(bool)

    def __init__(self, model_id="tiny", parent=None):
        super().__init__(parent)
        self._model_id = model_id
        self.ctrl = None
        self._cancel_pending = False

    def run(self):
        from setup_controller import SetupController
        self.ctrl = SetupController(self._model_id, event_callback=self._on_event)
        if self._cancel_pending:
            self.ctrl.cancel()
        ok = self.ctrl.resume()
        self.finished.emit(ok)

    def cancel(self):
        if self.ctrl:
            self.ctrl.cancel()
        else:
            self._cancel_pending = True

    def _on_event(self, event):
        self.stage_event.emit(event)


# Clear PYTHONHOME inherited from shell launcher (would overrides user-venv pyvenv.cfg)
os.environ.pop("PYTHONHOME", None)
os.environ.pop("PYTHONPATH", None)


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Realtime Subtitle")
        self.setFixedSize(460, 230)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)
        
        # Title
        self.label = QLabel("Initializing Real-Time Translator...")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(self.label)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.layout.addWidget(self.progress_bar)
        
        # Log Label
        self.log_label = QLabel("Checking environment...")
        self.log_label.setStyleSheet("color: #666; font-size: 12px;")
        self.log_label.setWordWrap(True)
        self.layout.addWidget(self.log_label)
        
        # Launch button (shown on success)
        self.launch_btn = QPushButton("Launch Application")
        self.launch_btn.setStyleSheet("""
            background-color: #a6e3a1; color: #1e1e2e;
            padding: 8px 16px; border-radius: 4px; font-weight: bold;
        """)
        self.launch_btn.clicked.connect(self._launch_dashboard)
        self.launch_btn.hide()
        self.layout.addWidget(self.launch_btn)

        self._launch_started = False
        self._dashboard_process = None
        self._dashboard_log_handle = None
        self._dashboard_log_offset = 0

        # Auto-run dependency check
        QTimer.singleShot(500, self.start_check)

    def start_check(self):
        # Retry / Cancel buttons
        btn_layout = QHBoxLayout()
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.clicked.connect(self._retry_setup)
        self.retry_btn.setEnabled(False)
        btn_layout.addWidget(self.retry_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_setup)
        btn_layout.addWidget(self.cancel_btn)
        self.diag_btn = QPushButton("Copy Diagnostics")
        self.diag_btn.setStyleSheet(self._btn_style("#f9e2af"))
        self.diag_btn.clicked.connect(self._copy_diagnostics)
        self.diag_btn.hide()
        btn_layout.addWidget(self.diag_btn)
        self.log_btn = QPushButton("Open Logs")
        self.log_btn.clicked.connect(self._open_logs)
        self.log_btn.hide()
        btn_layout.addWidget(self.log_btn)
        self.layout.addLayout(btn_layout)
        
        self._setup_ctrl = None
        self.installer = SetupWorker("tiny")
        self.installer.stage_event.connect(self._on_stage_event)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()

    def _on_stage_event(self, event):
        # Diagnostic logging is handled by SetupController._emit — do not double-log
        self._last_event = event
        self.log_label.setText(f"{getattr(event,'stage','')}: {getattr(event,'message','')}")
        if getattr(event,'percent',None) is not None:
            self.progress_bar.setRange(0,100); self.progress_bar.setValue(int(event.percent))
        else:
            self.progress_bar.setRange(0,0)
        if getattr(event,'can_retry',False):
            self.retry_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.diag_btn.show()
        if getattr(event,'can_cancel',False):
            self.cancel_btn.setEnabled(True); self.retry_btn.setEnabled(False); self.diag_btn.hide()
    
    def _retry_setup(self):
        self.retry_btn.setEnabled(False)
        self.installer = SetupWorker(self._setup_ctrl.sm.model_id if self._setup_ctrl else "tiny")
        self.installer.stage_event.connect(self._on_stage_event)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()
    
    def _cancel_setup(self):
        self.installer.cancel()
        self.cancel_btn.setEnabled(False)
    
    def _copy_diagnostics(self):
        from diagnostic_logger import write_full_report
        QApplication.clipboard().setText(write_full_report())
        self.diag_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.diag_btn.setText("Copy Diagnostics"))

    def _open_logs(self):
        from app_paths import get_log_dir
        log_dir = os.fspath(get_log_dir())
        import subprocess
        if os.name == "nt":
            os.startfile(log_dir)
        else:
            subprocess.Popen(["open", log_dir])

    def _btn_style(self, color):
        return (f"QPushButton {{ background: {color}; color: #1e1e2e; "
                f"padding: 6px 14px; border-radius: 4px; font-weight: bold; }}")

    def _launch_dashboard(self):
        if self._launch_started:
            return
        self._launch_started = True
        self.launch_btn.setEnabled(False)
        self.retry_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.label.setText("Opening Realtime Subtitle…")
        self.log_label.setText("Starting the main window…")
        self.progress_bar.setRange(0, 0)

        venv_py = _user_venv_gui_python()
        resources = os.path.dirname(os.path.abspath(__file__))
        main_py = os.path.join(resources, "main.py")
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["VIRTUAL_ENV"] = os.path.dirname(os.path.dirname(venv_py))
        from app_paths import get_log_dir
        from diagnostic_logger import log_diagnostic

        log_dir = os.fspath(get_log_dir())
        os.makedirs(log_dir, exist_ok=True)
        startup_log = os.path.join(log_dir, "app-startup.log")
        command = [venv_py, main_py, *_main_cli_args()]
        log_diagnostic(
            "Launch application",
            "Starting dashboard process",
            interpreter=os.path.basename(venv_py),
            resources=resources,
        )

        try:
            self._dashboard_log_handle = open(
                startup_log, "a", encoding="utf-8", buffering=1
            )
            self._dashboard_log_handle.write("\n=== Dashboard launch ===\n")
            self._dashboard_log_offset = self._dashboard_log_handle.tell()
            kwargs = {
                "cwd": resources,
                "env": env,
                "stdout": self._dashboard_log_handle,
                "stderr": subprocess.STDOUT,
            }
            if os.name == "nt":
                kwargs["creationflags"] = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                )
            else:
                kwargs["start_new_session"] = True
            self._dashboard_process = subprocess.Popen(command, **kwargs)
        except Exception as exc:
            log_diagnostic(
                "Launch application",
                "Could not start dashboard process",
                error_type=type(exc).__name__,
                detail=str(exc)[:300],
            )
            self._show_launch_failure(str(exc), startup_log)
            return

        # Do not close the bootstrap window until the new process has survived
        # its import and first-window construction.  This turns previously
        # invisible pythonw.exe failures into an actionable in-product error.
        QTimer.singleShot(2200, lambda: self._confirm_dashboard_started(startup_log))

    def _confirm_dashboard_started(self, startup_log):
        from diagnostic_logger import log_diagnostic

        process = self._dashboard_process
        if process is None:
            self._show_launch_failure("The dashboard process was not created.", startup_log)
            return
        returncode = process.poll()
        if returncode is None:
            log_diagnostic(
                "Launch application",
                "Dashboard process is running",
                pid=process.pid,
            )
            self._close_dashboard_log()
            QApplication.quit()
            return

        output = self._read_dashboard_launch_output(startup_log)
        if returncode == 0 and "Existing Realtime Subtitle instance notified" in output:
            log_diagnostic(
                "Launch application",
                "Existing dashboard instance was notified",
            )
            self._close_dashboard_log()
            QApplication.quit()
            return

        log_diagnostic(
            "Launch application",
            "Dashboard process exited during startup",
            returncode=returncode,
            detail=output[-500:],
        )
        detail = output.strip()[-1200:] or f"The process exited with code {returncode}."
        self._show_launch_failure(detail, startup_log)

    def _read_dashboard_launch_output(self, startup_log):
        self._close_dashboard_log()
        try:
            with open(startup_log, "r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self._dashboard_log_offset)
                return handle.read()
        except OSError:
            return ""

    def _close_dashboard_log(self):
        handle = self._dashboard_log_handle
        self._dashboard_log_handle = None
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass

    def _show_launch_failure(self, detail, startup_log):
        self._close_dashboard_log()
        self._launch_started = False
        self._dashboard_process = None
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.label.setText("Realtime Subtitle could not open")
        self.log_label.setText(
            "The setup is complete, but the main window could not start. "
            "Open Logs and send app-startup.log when requesting help."
        )
        self.log_label.setStyleSheet("color: #f38ba8; font-size: 12px;")
        self.launch_btn.setText("Try Opening Again")
        self.launch_btn.setEnabled(True)
        self.launch_btn.show()
        self.log_btn.show()
        self.diag_btn.show()
        QMessageBox.critical(
            self,
            "Realtime Subtitle — Startup Failed",
            "The environment and speech model are ready, but the main window "
            "closed during startup.\n\n"
            f"Log: {startup_log}\n\n"
            f"Details:\n{str(detail)[:1200]}",
        )
    
    def update_log(self, message):
        self.log_label.setText(message)

    def on_install_finished(self, success):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._setup_ctrl = getattr(self.installer, 'ctrl', None)
        if success:
            self.log_label.setText("Ready to launch!")
            self.label.setText("Initialization Complete")
            self.launch_btn.show()
            self.retry_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            # A desktop app should open its product directly. The setup window
            # remains visible only long enough to communicate readiness.
            QTimer.singleShot(250, self._launch_dashboard)
        elif getattr(self.installer, 'ctrl', None) and self.installer.ctrl._cancel_requested:
            self.label.setText("Initialization Cancelled")
            self.log_label.setStyleSheet("color: #fab387;")
            self.retry_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.label.setText("Initialization Failed")
            self.log_label.setStyleSheet("color: red;")
            self.retry_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.diag_btn.show()
            self.log_btn.show()

if __name__ == "__main__":
    from diagnostic_logger import log_diagnostic
    log_diagnostic("launcher", "Bootstrap started")
    app = QApplication(sys.argv)
    from single_instance import SingleInstance
    # The setup window and the product window are separate processes during
    # handoff.  A dedicated lock prevents the launcher from accidentally
    # making the newly spawned dashboard believe another dashboard is alive.
    instance = SingleInstance(name="com.realtimesubtitle.launcher", parent=app)
    if not instance.is_primary:
        sys.exit(0)
    app.setStyle("Fusion")
    try:
        from PyQt6.QtGui import QIcon
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets", "icon", "realtime-subtitle-icon.png",
        )
        if os.path.isfile(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    launcher = LauncherWindow()
    launcher._single_instance = instance
    instance.message_received.connect(
        lambda _message: (launcher.showNormal(), launcher.raise_(), launcher.activateWindow())
    )
    launcher.show()
    sys.exit(app.exec())
