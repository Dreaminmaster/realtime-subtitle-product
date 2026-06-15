"""
Model Manager - Download, delete, and manage ASR models.

Supports:
  - faster-whisper models (tiny, base, small, medium, large-v3, turbo)
  - mlx-whisper models (via huggingface hub)
  - FunASR models (via modelscope)

Models are stored in ~/Library/Application Support/RealtimeSubtitle/models/
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
            data_dir = os.path.join(
                os.path.expanduser("~"),
                "Library",
                "Application Support",
                "RealtimeSubtitle",
                "models"
            )
        
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
    
    def get_model_path(self, model_id, backend="whisper"):
        """Return the real locally-cached snapshot path, or None.
        Uses huggingface_hub local_files_only to resolve without network."""
        if backend == "whisper":
            repo_id = f"Systran/faster-whisper-{model_id}"
            try:
                from huggingface_hub import snapshot_download
                path = snapshot_download(
                    repo_id=repo_id,
                    local_files_only=True,
                )
                if path and self._is_valid_whisper_dir(path):
                    return path
            except Exception:
                pass
            # Fallback: manual HF cache resolution
            from pathlib import Path
            cache_base = Path.home() / ".cache" / "huggingface" / "hub" / \
                         f"models--Systran--faster-whisper-{model_id}"
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
        
        return models
    
    def is_downloaded(self, model_id: str, backend="whisper") -> bool:
        """Check if a model is downloaded"""
        if backend == "mlx":
            return self._is_mlx_model_downloaded(model_id)
        else:
            return self._is_whisper_model_downloaded(model_id)
    
    def _is_whisper_model_downloaded(self, model_id: str) -> bool:
        """Check if faster-whisper model is cached"""
        # faster-whisper caches models in its own directory
        cache_dir = os.path.expanduser(f"~/.cache/huggingface/hub")
        import glob
        # Look for model files
        model_dir = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_id}")
        if os.path.exists(model_dir):
            return True
        
        # Also check whisper cache
        whisper_cache = os.path.expanduser("~/.cache/whisper")
        if os.path.exists(os.path.join(whisper_cache, f"{model_id}.pt")):
            return True
        
        return model_id in self._cache
    
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
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            full_path = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_id}")
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
        if backend == "mlx":
            self._download_mlx_model(model_id, progress_callback)
        elif backend == "funasr":
            self._download_funasr_model(model_id, progress_callback)
        else:
            self._download_whisper_model(model_id, progress_callback)
        self._cache[model_id] = {
            "backend": backend,
            "downloaded_at": str(__import__('datetime').datetime.now())
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
        """Download faster-whisper model"""
        if progress_callback:
            progress_callback("downloading", 10)
        
        from faster_whisper import WhisperModel
        
        if progress_callback:
            progress_callback("loading", 50)
        
        # Simply initializing downloads the model
        model = WhisperModel(model_id, device="cpu", compute_type="int8")
        
        if progress_callback:
            progress_callback("completed", 100)
    
    def _download_mlx_model(self, model_id, progress_callback=None):
        """Download MLX whisper model from HuggingFace"""
        if progress_callback:
            progress_callback("downloading", 10)
        
        from huggingface_hub import snapshot_download
        
        snapshot_download(
            model_id,
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
                full_path = os.path.join(cache_dir, f"models--Systran--faster-whisper-{model_id}")
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
