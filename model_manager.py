"""
Model Manager - Download, delete, and manage ASR models.

Supports:
  - faster-whisper models (tiny, base, small, medium, large-v3, turbo)
  - mlx-whisper models (via huggingface hub)
  - FunASR models (via modelscope)

Models are stored in the platform's per-user application-data directory.
"""

import os
import sys
import json
import shutil
import threading, glob
from pathlib import Path

# Model metadata
WHISPER_MODELS = {
    "tiny": {
        "name": "tiny",
        "size_mb": 75,
        "speed": "Extremely Fast",
        "accuracy": "Low",
        "best_for": "Testing, low-end devices",
        "recommended": False
    },
    "tiny.en": {
        "name": "tiny.en",
        "size_mb": 75,
        "speed": "Extremely Fast",
        "accuracy": "Low (English only)",
        "best_for": "Testing, English only",
        "recommended": False
    },
    "base": {
        "name": "base",
        "size_mb": 145,
        "speed": "Fast",
        "accuracy": "Moderate",
        "best_for": "Simple conversations",
        "recommended": False
    },
    "base.en": {
        "name": "base.en",
        "size_mb": 145,
        "speed": "Fast",
        "accuracy": "Moderate (English only)",
        "best_for": "Simple English conversations",
        "recommended": False
    },
    "small": {
        "name": "small",
        "size_mb": 488,
        "speed": "Moderate",
        "accuracy": "Good",
        "best_for": "Daily use (Recommended)",
        "recommended": True
    },
    "small.en": {
        "name": "small.en",
        "size_mb": 488,
        "speed": "Moderate",
        "accuracy": "Good (English only)",
        "best_for": "Daily English use",
        "recommended": False
    },
    "medium": {
        "name": "medium",
        "size_mb": 1530,
        "speed": "Slower",
        "accuracy": "Better",
        "best_for": "Classrooms, meetings",
        "recommended": False
    },
    "medium.en": {
        "name": "medium.en",
        "size_mb": 1530,
        "speed": "Slower",
        "accuracy": "Better (English only)",
        "best_for": "English meetings",
        "recommended": False
    },
    "large-v3": {
        "name": "large-v3",
        "size_mb": 3100,
        "speed": "Slow",
        "accuracy": "Best",
        "best_for": "Transcription, high-performance devices",
        "recommended": False
    },
    "turbo": {
        "name": "turbo",
        "size_mb": 1620,
        "speed": "Fast-Moderate",
        "accuracy": "Very Good",
        "best_for": "Best balance of speed & accuracy",
        "recommended": True
    }
}

# MLX-specific models (subset)
MLX_MODELS = {
    "mlx-community/whisper-tiny": {
        "name": "mlx-tiny",
        "size_mb": 75,
        "speed": "Extremely Fast (Metal)",
        "accuracy": "Low",
        "best_for": "Testing on Apple Silicon",
        "recommended": False
    },
    "mlx-community/whisper-small": {
        "name": "mlx-small", 
        "size_mb": 488,
        "speed": "Fast (Metal)",
        "accuracy": "Good",
        "best_for": "Daily use on Apple Silicon",
        "recommended": True
    },
    "mlx-community/whisper-medium": {
        "name": "mlx-medium",
        "size_mb": 1530,
        "speed": "Moderate (Metal)",
        "accuracy": "Better",
        "best_for": "Meetings on Apple Silicon",
        "recommended": False
    },
    "mlx-community/whisper-large-v3-mlx": {
        "name": "mlx-large-v3",
        "size_mb": 3100,
        "speed": "Moderate (Metal)",
        "accuracy": "Best",
        "best_for": "Best quality on Apple Silicon",
        "recommended": False
    }
}


class ModelManager:
    """Manage ASR model downloads and storage"""
    
    def __init__(self, data_dir=None):
        if data_dir is None:
            from app_paths import get_app_support_dir

            data_dir = get_app_support_dir() / "models"
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache file
        self.cache_file = self.data_dir / "model_cache.json"
        self._cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            print(f"[ModelManager] Failed to save cache: {e}")
    
    def register_model_path(self, model_id: str, path: str, backend: str = "whisper") -> None:
        """Explicitly register a model path in cache without network access.
        
        Used by setup to register models bundled in the app DMG.
        """
        self._cache[model_id] = {
            "backend": backend,
            "downloaded_at": str(__import__('datetime').datetime.now()),
            "repo_id": f"Systran/faster-whisper-{model_id}" if backend == "whisper" else model_id,
            "snapshot_path": path,
            "source": "bundled",
        }
        self._save_cache()
    
    def _user_model_dir(self, model_id: str, backend: str = "whisper") -> str:
        """Path to user model directory under data dir.
        
        Example: <app-data>/RealtimeSubtitle/models/whisper/tiny
        (self.data_dir already ends in 'models/', so we append backend/model_id directly.)
        """
        return os.path.join(str(self.data_dir), backend, model_id)

    @staticmethod
    def _bundled_model_dir(model_id: str, backend: str = "whisper",
                           resources_dir: str = None) -> str:
        """Path to the bundled model inside the app's Resources directory.
        
        Example: /Applications/RealtimeSubtitle.app/Contents/Resources/models/whisper/tiny
        
        This is the model shipped inside the DMG — ready-only, never modified.
        """
        if resources_dir is None:
            from platform_support import bundled_resources_dir

            resources_dir = os.fspath(bundled_resources_dir())
        return os.path.join(resources_dir, "models", backend, model_id)
    
    def get_model_path(self, model_id, backend="whisper"):
        """Return the real locally-cached snapshot path, or None.
        Checks cache first, then resolves via huggingface_hub local_files_only."""
        if backend == "whisper":
            # Fast path: cached snapshot_path from a previous download
            cached = self._cache.get(model_id, {})
            cached_path = cached.get("snapshot_path")
            if cached_path and os.path.isdir(cached_path) and self._is_valid_whisper_dir(cached_path):
                return cached_path
            
            repo_id = model_id if "/" in model_id else f"Systran/faster-whisper-{model_id}"
            try:
                from public_model_download import public_snapshot_download
                path = public_snapshot_download(
                    repo_id=repo_id,
                    local_files_only=True,
                )
                if path and self._is_valid_whisper_dir(path):
                    return path
            except Exception:
                pass
            # Check app-specific model directory (bundled/copied models)
            app_dir = self._user_model_dir(model_id)
            if self._is_valid_whisper_dir(app_dir):
                return app_dir
            # Fallback: manual HF cache resolution
            from pathlib import Path
            cache_slug = repo_id.replace("/", "--")
            cache_base = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{cache_slug}"
            if cache_base.exists():
                snaps = cache_base / "snapshots"
                if snaps.is_dir():
                    for snap in sorted(snaps.iterdir(), reverse=True):
                        if self._is_valid_whisper_dir(str(snap)):
                            return str(snap)
        return None

    @staticmethod
    def _is_valid_whisper_dir(path):
        """Check that path contains at least config.json + model weights."""
        import os
        p = os.path
        if not p.isdir(path):
            return False
        has_config = p.exists(p.join(path, "config.json"))
        # Weight files: model.bin, *.safetensors, pytorch_model.bin
        import glob
        weights = glob.glob(p.join(path, "*.safetensors")) or \
                  glob.glob(p.join(path, "model.bin")) or \
                  glob.glob(p.join(path, "pytorch_model.bin"))
        has_weights = any(os.path.getsize(w) > 10000 for w in weights)  # >10KB
        has_vocab = p.exists(p.join(path, "vocabulary.json")) or \
                    p.exists(p.join(path, "vocabulary.txt")) or \
                    p.exists(p.join(path, "tokenizer.json"))
        return has_config and has_weights and has_vocab

    def get_models(self, backend="whisper") -> list:
        """Get list of available models for a backend"""
        if backend == "mlx":
            model_dict = MLX_MODELS
        else:
            model_dict = WHISPER_MODELS
        
        models = []
        for model_id, info in model_dict.items():
            downloaded = self.is_downloaded(model_id, backend)
            installed_size = self.get_installed_size(model_id, backend)
            
            models.append({
                "id": model_id,
                "name": info["name"],
                "size_mb": info["size_mb"],
                "speed": info["speed"],
                "accuracy": info["accuracy"],
                "best_for": info["best_for"],
                "recommended": info["recommended"],
                "downloaded": downloaded,
                "installed_size_mb": installed_size,
                "backend": backend
            })
        for model_id, cached in self._cache.items():
            if cached.get("backend", "whisper") != backend or model_id in model_dict:
                continue
            installed_size = self.get_installed_size(model_id, backend)
            models.append({
                "id": model_id,
                "name": model_id,
                "size_mb": installed_size or "—",
                "speed": "Community model",
                "accuracy": "Varies",
                "best_for": "Installed from Hugging Face",
                "recommended": False,
                "downloaded": self.is_downloaded(model_id, backend),
                "installed_size_mb": installed_size,
                "backend": backend,
            })
        
        return models
    
    def is_downloaded(self, model_id: str, backend="whisper") -> bool:
        """Check if a model is downloaded"""
        if backend == "mlx":
            return self._is_mlx_model_downloaded(model_id)
        else:
            return self._is_whisper_model_downloaded(model_id)
    
    def _is_whisper_model_downloaded(self, model_id: str) -> bool:
        """Report installed only when a loadable faster-whisper snapshot exists.

        A Hugging Face cache folder or lock file can exist while a download is
        incomplete.  OpenAI Whisper ``.pt`` files are also not loadable by the
        faster-whisper runtime used here.  ``get_model_path`` is therefore the
        single source of truth for both the UI and model factory.
        """
        return self.get_model_path(model_id, "whisper") is not None
    
    def _is_mlx_model_downloaded(self, model_id: str) -> bool:
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        model_dir = model_id.replace("/", "--")
        full_path = os.path.join(cache_dir, f"models--{model_dir}")
        return os.path.exists(full_path) or model_id in self._cache
    
    def get_installed_size(self, model_id: str, backend="whisper") -> float:
        """Get installed size in MB"""
        if backend == "mlx":
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_dir = model_id.replace("/", "--")
            full_path = os.path.join(cache_dir, f"models--{model_dir}")
        else:
            cached_path = self._cache.get(model_id, {}).get("snapshot_path")
            if cached_path and os.path.exists(cached_path):
                full_path = cached_path
            else:
                cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
                repo_id = model_id if "/" in model_id else f"Systran/faster-whisper-{model_id}"
                full_path = os.path.join(cache_dir, f"models--{repo_id.replace('/', '--')}")
            if not os.path.exists(full_path):
                whisper_cache = os.path.expanduser("~/.cache/whisper")
                full_path = os.path.join(whisper_cache, f"{model_id}.pt")
        
        if not os.path.exists(full_path):
            return 0.0
        
        total = 0
        for dirpath, dirnames, filenames in os.walk(full_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
        
        return round(total / (1024 * 1024), 1)
    
    def download_model_sync(self, model_id: str, backend="whisper",
                            progress_callback=None, cancel_event=None):
        """Synchronous download — blocks until complete. Returns True on success, raises on failure."""
        if progress_callback:
            progress_callback("starting", 0)
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled")
        snapshot_path = None
        repo_id = None
        if backend == "mlx":
            self._download_mlx_model(model_id, progress_callback)
            repo_id = model_id
        elif backend == "funasr":
            self._download_funasr_model(model_id, progress_callback)
            repo_id = model_id
        else:
            snapshot_path, repo_id = self._download_whisper_model(model_id, progress_callback)
        self._cache[model_id] = {
            "backend": backend,
            "downloaded_at": str(__import__('datetime').datetime.now()),
            "repo_id": repo_id,
            "snapshot_path": snapshot_path,
        }
        self._save_cache()
        if progress_callback:
            progress_callback("completed", 100)
        return True

    def download_model(self, model_id: str, backend="whisper", 
                      progress_callback=None, done_callback=None):
        """Legacy async wrapper. Prefer download_model_sync in DownloadTask workers."""
        
        def _download():
            try:
                self.download_model_sync(model_id, backend, progress_callback)
                if done_callback:
                    done_callback(True, None)
            except Exception as e:
                if progress_callback:
                    progress_callback("error", 0)
                if done_callback:
                    done_callback(False, str(e))
        
        thread = threading.Thread(target=_download, daemon=True)
        thread.start()
        return thread
    
    def _download_whisper_model(self, model_id, progress_callback=None):
        """Download faster-whisper model via explicit snapshot_download.
        Returns (snapshot_path, repo_id) on success."""
        if "/" in model_id:
            from model_catalog import validate_faster_whisper_repo
            repo_id = validate_faster_whisper_repo(model_id)
        else:
            repo_id = f"Systran/faster-whisper-{model_id}"
        if progress_callback:
            progress_callback("downloading", 10)
        
        from public_model_download import public_snapshot_download
        
        if progress_callback:
            progress_callback("resolving", 30)
        
        snapshot_path = public_snapshot_download(
            repo_id=repo_id,
            local_files_only=False,
        )
        
        if progress_callback:
            progress_callback("completed", 100)
        
        return snapshot_path, repo_id
    
    def _download_mlx_model(self, model_id, progress_callback=None):
        """Download MLX whisper model from HuggingFace"""
        if progress_callback:
            progress_callback("downloading", 10)
        
        from public_model_download import public_snapshot_download
        
        public_snapshot_download(
            repo_id=model_id,
            cache_dir=os.path.expanduser("~/.cache/huggingface/hub")
        )
        
        if progress_callback:
            progress_callback("completed", 100)
    
    def _download_funasr_model(self, model_id, progress_callback=None):
        """Download FunASR model from modelscope"""
        if progress_callback:
            progress_callback("downloading", 10)
        
        from modelscope import snapshot_download
        
        snapshot_download(model_id)
        
        if progress_callback:
            progress_callback("completed", 100)
    
    def delete_model(self, model_id: str, backend="whisper") -> bool:
        """Delete a downloaded model"""
        try:
            if backend == "mlx":
                cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
                model_dir = model_id.replace("/", "--")
                full_path = os.path.join(cache_dir, f"models--{model_dir}")
                if os.path.exists(full_path):
                    shutil.rmtree(full_path)
            else:
                cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
                repo_id = model_id if "/" in model_id else f"Systran/faster-whisper-{model_id}"
                full_path = os.path.join(cache_dir, f"models--{repo_id.replace('/', '--')}")
                if os.path.exists(full_path):
                    shutil.rmtree(full_path)
                
                # Also check whisper cache
                whisper_cache = os.path.expanduser("~/.cache/whisper")
                model_file = os.path.join(whisper_cache, f"{model_id}.pt")
                if os.path.exists(model_file):
                    os.remove(model_file)
            
            # Update cache
            if model_id in self._cache:
                del self._cache[model_id]
                self._save_cache()
            
            return True
        except Exception as e:
            print(f"[ModelManager] Error deleting model {model_id}: {e}")
            return False
    
    def get_disk_usage(self) -> dict:
        """Get total disk usage of all models"""
        total = 0
        models_used = []
        
        # Check all backends
        for backend in ["whisper", "mlx"]:
            for model_id in self.get_models(backend):
                size = model_id.get("installed_size_mb", 0) if isinstance(model_id, dict) else 0
                if size > 0:
                    total += size
                    models_used.append(model_id["name"] if isinstance(model_id, dict) else str(model_id))
        
        return {
            "total_mb": round(total, 1),
            "total_gb": round(total / 1024, 2),
            "model_count": len(models_used),
            "models": models_used
        }
    
    def clear_all_models(self) -> bool:
        """Delete all downloaded models"""
        try:
            for model_id in list(self._cache.keys()):
                backend = self._cache[model_id].get("backend", "whisper")
                self.delete_model(model_id, backend)
            self._cache = {}
            self._save_cache()
            return True
        except Exception as e:
            print(f"[ModelManager] Error clearing models: {e}")
            return False


# Global singleton
model_manager = ModelManager()
