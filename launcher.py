import sys
import os
import subprocess
import configparser
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QProgressBar, QMessageBox, QPushButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

class SetupWorker(QThread):
    """Runs SetupController.resume() in background. Emits stage events."""
    stage_event = pyqtSignal(object)
    finished = pyqtSignal(bool)

    def __init__(self, model_id="tiny", parent=None):
        super().__init__(parent)
        self._model_id = model_id

    def run(self):
        from setup_controller import SetupController
        self.ctrl = SetupController(self._model_id, event_callback=self._on_event)
        ok = self.ctrl.resume()
        self.finished.emit(ok)

    def _on_event(self, event):
        self.stage_event.emit(event)


class DependencyInstaller(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool)

    def run(self):
        self.progress.emit("Checking dependencies...")
        
        required_packages = []
        try:
            with open("requirements.txt", "r") as f:
                required_packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            self.progress.emit("requirements.txt not found. Skipping check.")
            self.finished.emit(True)
            return

        missing = []
        for pkg in required_packages:
            # Simple check: try to import the package name usually maps to the install name
            # But some don't (e.g. pyqt6 -> PyQt6).
            # So we rely on pip freeze or just try to install everything?
            # Better approach: Just run pip install and let it skip existing.
            pass
            
        # We will just run pip install -r requirements.txt
        # This is safer than guessing import names.
        
        self.progress.emit("Installing/Verifying dependencies via pip...")
        
        try:
            # Using subprocess to run pip
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.progress.emit(output.strip())
            
            rc = process.poll()
            if rc == 0:
                self.progress.emit("Dependencies installed successfully.")
                self.finished.emit(True)
            else:
                stderr = process.stderr.read()
                self.progress.emit(f"Error: {stderr}")
                self.finished.emit(False)
                
        except Exception as e:
            self.progress.emit(f"Failed to run pip: {e}")
            self.finished.emit(False)

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
        
        # Start Button (Hidden initially)
        self.start_btn = QPushButton("Launch Application")
        self.start_btn.setStyleSheet("""
            background-color: #3498db; color: white; padding: 10px; font-weight: bold; border-radius: 5px;
        """)
        self.start_btn.clicked.connect(self.launch_main_app)
        self.start_btn.hide()
        self.layout.addWidget(self.start_btn)

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
        self.layout.addLayout(btn_layout)
        # Launch Application button (shown on success)
        self.launch_btn = QPushButton("Launch Application")
        self.launch_btn.clicked.connect(self._launch_dashboard)
        self.launch_btn.setEnabled(False)
        self.layout.addWidget(self.launch_btn)
        
        self._setup_ctrl = None
        self.installer = SetupWorker("tiny")
        self.installer.stage_event.connect(self._on_stage_event)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()

    def _on_stage_event(self, event):
        self.log_label.setText(f"{event.stage}: {event.message}")
        if event.percent is not None:
            self.progress_bar.setValue(int(event.percent))
        else:
            self.progress_bar.setRange(0, 0)
        # Enable retry on failure
        if event.can_retry:
            self.retry_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
        if event.can_cancel:
            self.cancel_btn.setEnabled(True)
            self.retry_btn.setEnabled(False)
    
    def _retry_setup(self):
        self.retry_btn.setEnabled(False)
        self.installer = SetupWorker(self._setup_ctrl.sm.model_id if self._setup_ctrl else "tiny")
        self.installer.stage_event.connect(self._on_stage_event)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()
    
    def _cancel_setup(self):
        if self._setup_ctrl:
            self._setup_ctrl.cancel()
        self.cancel_btn.setEnabled(False)
    
    def _launch_dashboard(self):
        QApplication.quit()
        os.execv(sys.executable, [sys.executable, "main.py"])
    
    def update_log(self, message):
        self.log_label.setText(message)

    def on_install_finished(self, success):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._setup_ctrl = getattr(self.installer, 'ctrl', None)
        if success:
            self.log_label.setText("Ready to launch!")
            self.start_btn.show()
            self.label.setText("Initialization Complete")
            QTimer.singleShot(800, self.launch_main_app)
        else:
            self.label.setText("Initialization Failed")
            self.log_label.setStyleSheet("color: red;")
            self.retry_btn.setEnabled(True)

    def launch_main_app(self):
        self.close()
        # Launch Dashboard
        try:
            import dashboard
            self.dash = dashboard.Dashboard()
            self.dash.show()
        except Exception as e:
            import traceback
            error_msg = f"Failed to launch dashboard:\n{str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            QMessageBox.critical(self, "Error", error_msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Modern Styling for Launcher
    app.setStyle("Fusion")
    
    launcher = LauncherWindow()
    launcher.show()
    
    sys.exit(app.exec())
