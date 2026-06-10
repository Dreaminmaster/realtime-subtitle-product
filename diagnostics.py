#!/usr/bin/env python3
"""
Diagnostics & Logging - System diagnostics and log management.

Provides:
  - App startup status logging
  - ASR/Translation backend status
  - Microphone permission checks
  - Audio input validation
  - Log viewing and export
  - Privacy-safe: never logs full voice content
"""

import os
import sys
import json
import time
import platform
from datetime import datetime
from pathlib import Path


class Logger:
    """Simple file-based logger"""
    
    LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3}
    
    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(
                os.path.expanduser("~"),
                "Library", "Logs", "RealtimeSubtitle"
            )
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        self.level = self.LEVELS.get(
            os.getenv("RT_SUBTITLE_LOG_LEVEL", "INFO").upper(), 1
        )
        
        # Startup log
        self.info(f"=== App Started v1.0 ===")
        self.info(f"Platform: {platform.platform()}")
        self.info(f"Python: {sys.version}")
    
    def _write(self, level: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            print(line, end='')
    
    def debug(self, msg): 
        if self.level <= self.LEVELS["DEBUG"]:
            self._write("DEBUG", msg)
    
    def info(self, msg): 
        if self.level <= self.LEVELS["INFO"]:
            self._write("INFO", msg)
    
    def warn(self, msg): 
        if self.level <= self.LEVELS["WARN"]:
            self._write("WARN", msg)
    
    def error(self, msg): 
        if self.level <= self.LEVELS["ERROR"]:
            self._write("ERROR", msg)
    
    def get_logs(self, lines=100) -> list:
        """Get recent log lines"""
        if not self.log_file.exists():
            return []
        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
            return all_lines[-lines:]
        except Exception:
            return []
    
    def get_all_log_files(self) -> list:
        """List all log files"""
        return sorted(
            [str(f) for f in self.log_dir.glob("app_*.log")],
            reverse=True
        )


class Diagnostics:
    """Run system diagnostics and return results"""
    
    def __init__(self, logger=None):
        self.logger = logger or Logger()
        self.results = {}
    
    def run_all(self) -> dict:
        """Run all diagnostic checks"""
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "platform": {},
            "python": {},
            "audio": {},
            "asr": {},
            "translation": {},
            "permissions": {},
            "models": {},
            "summary": {}
        }
        
        self._check_platform()
        self._check_python()
        self._check_audio()
        self._check_permissions()
        self._check_models()
        
        # Summary
        all_ok = all(
            self.results[cat].get("ok", True)
            for cat in ["platform", "python", "audio", "permissions"]
        )
        self.results["summary"] = {
            "all_ok": all_ok,
            "issues": self._collect_issues()
        }
        
        return self.results
    
    def _check_platform(self):
        is_mac = platform.system() == "Darwin"
        is_arm = platform.machine() == "arm64"
        
        self.results["platform"] = {
            "ok": is_mac,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "is_apple_silicon": is_arm,
            "issues": [] if is_mac else ["macOS required for full functionality"]
        }
        self.logger.info(f"Platform: {platform.platform()}, ARM={is_arm}")
    
    def _check_python(self):
        version = sys.version_info
        ok = version >= (3, 10)
        self.results["python"] = {
            "ok": ok,
            "version": f"{version.major}.{version.minor}.{version.micro}",
            "issues": [] if ok else ["Python 3.10+ required"]
        }
        self.logger.info(f"Python version: {sys.version}")
    
    def _check_audio(self):
        issues = []
        devices = []
        
        try:
            import sounddevice as sd
            sd._initialize()
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            
            if not input_devices:
                issues.append("No input audio devices found")
                
            # Check for BlackHole
            has_blackhole = any(
                'blackhole' in d['name'].lower() and d['max_input_channels'] > 0
                for d in devices
            )
            
            self.results["audio"] = {
                "ok": len(input_devices) > 0,
                "device_count": len(devices),
                "input_device_count": len(input_devices),
                "has_blackhole": has_blackhole,
                "input_devices": [
                    {"name": d['name'], "channels": d['max_input_channels']}
                    for d in input_devices[:5]
                ],
                "issues": issues
            }
            self.logger.info(f"Audio: {len(input_devices)} input devices, BlackHole={has_blackhole}")
        except Exception as e:
            self.results["audio"] = {
                "ok": False,
                "issues": [f"Audio check failed: {e}"]
            }
            self.logger.error(f"Audio check failed: {e}")
    
    def _check_permissions(self):
        issues = []
        mic_ok = None
        
        if platform.system() == "Darwin":
            try:
                import objc
                from AVFoundation import AVCaptureDevice
                status = AVCaptureDevice.authorizationStatusForMediaType_("soun")
                mic_ok = (status == 3)  # AVAuthorizationStatusAuthorized
                if not mic_ok:
                    issues.append("Microphone permission not granted")
            except Exception:
                pass
        
        self.results["permissions"] = {
            "ok": mic_ok is not False,
            "microphone": "granted" if mic_ok else "unknown",
            "issues": issues
        }
        self.logger.info(f"Microphone permission: {mic_ok}")
    
    def _check_models(self):
        try:
            from model_manager import model_manager
            models = model_manager.get_models("whisper")
            downloaded = [m for m in models if m.get("downloaded")]
            disk_usage = model_manager.get_disk_usage()
            
            self.results["models"] = {
                "ok": len(downloaded) > 0,
                "downloaded_count": len(downloaded),
                "total_models": len(models),
                "disk_usage_mb": disk_usage.get("total_mb", 0),
                "downloaded": [m["name"] for m in downloaded],
                "issues": [] if downloaded else ["No ASR models downloaded - download a model first"]
            }
            self.logger.info(f"Models: {len(downloaded)} downloaded, {disk_usage.get('total_mb', 0)}MB")
        except Exception as e:
            self.results["models"] = {
                "ok": False,
                "issues": [f"Model check failed: {e}"]
            }
    
    def _collect_issues(self) -> list:
        seen = set()
        issues = []
        for cat in self.results:
            if isinstance(self.results[cat], dict):
                for issue in self.results[cat].get("issues", []):
                    if issue not in seen:
                        seen.add(issue)
                        issues.append(issue)
        return issues
    
    def get_status_text(self) -> str:
        """Get human-readable status report"""
        if not self.results:
            self.run_all()
        
        lines = [
            "=" * 50,
            "  REALTIME SUBTITLE - DIAGNOSTICS REPORT",
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 50,
            ""
        ]
        
        platform_info = self.results.get("platform", {})
        lines.append(f"Platform: {platform_info.get('system', '?')} {platform_info.get('release', '?')}")
        lines.append(f"Machine: {platform_info.get('machine', '?')} (Apple Silicon: {platform_info.get('is_apple_silicon', '?')})")
        
        python_info = self.results.get("python", {})
        lines.append(f"Python: {python_info.get('version', '?')}")
        
        audio_info = self.results.get("audio", {})
        lines.append(f"\nAudio Devices: {audio_info.get('input_device_count', 0)} input")
        lines.append(f"BlackHole: {'Yes' if audio_info.get('has_blackhole') else 'No'}")
        
        perm_info = self.results.get("permissions", {})
        lines.append(f"\nMicrophone: {perm_info.get('microphone', 'unknown')}")
        
        model_info = self.results.get("models", {})
        lines.append(f"\nModels: {model_info.get('downloaded_count', 0)} downloaded")
        lines.append(f"Disk: {model_info.get('disk_usage_mb', 0)} MB")
        
        issues = self._collect_issues()
        if issues:
            lines.append(f"\n⚠️  Issues found ({len(issues)}):")
            for issue in issues:
                lines.append(f"  - {issue}")
        else:
            lines.append("\n✅ All checks passed!")
        
        return "\n".join(lines)


# Global instances
logger = Logger()
diagnostics = Diagnostics(logger)
