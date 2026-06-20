import sys
import os

# Handle CLI flags BEFORE PyQt6 import (avoids unnecessary GUI dependencies)
if "--version" in sys.argv:
    try:
        from version import BUILD_VERSION, BUILD_COMMIT
        print(f"Realtime Subtitle v{BUILD_VERSION} (commit {BUILD_COMMIT})")
    except ImportError:
        print("Realtime Subtitle (dev build)")
    sys.exit(0)

if "--diagnose" in sys.argv:
    from diagnostic_logger import write_full_report, get_system_info
    info = get_system_info()
    info["app_version"] = "v2.3.1-rc14"
    info["python"] = sys.version.split()[0]
    print(write_full_report())
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
        self.setWindowTitle("Real-Time Translator - Launcher")
        self.setFixedSize(400, 200)
        
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
        log_dir = os.path.expanduser("~/Library/Logs/RealtimeSubtitle")
        import subprocess
        subprocess.Popen(["open", log_dir])

    def _btn_style(self, color):
        return (f"QPushButton {{ background: {color}; color: #1e1e2e; "
                f"padding: 6px 14px; border-radius: 4px; font-weight: bold; }}")

    def _launch_dashboard(self):
        QApplication.quit()
        venv_py = os.path.expanduser(
            "~/Library/Application Support/RealtimeSubtitle/venv/bin/python3")
        resources = os.path.dirname(os.path.abspath(__file__))
        main_py = os.path.join(resources, "main.py")
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["VIRTUAL_ENV"] = os.path.dirname(os.path.dirname(venv_py))
        os.execve(venv_py, [venv_py, main_py], env)
    
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
    app.setStyle("Fusion")
    launcher = LauncherWindow()
    launcher.show()
    sys.exit(app.exec())
