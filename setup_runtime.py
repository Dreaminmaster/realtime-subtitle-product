#!/usr/bin/env python3
"""User-venv setup worker — runs model preparation and verify via JSON line protocol."""
import sys, os, json

RESOURCES = os.path.dirname(os.path.abspath(__file__))

def emit(event):
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()

def _friendly_error(e):
    """Convert exception to a human-readable message."""
    t = type(e).__name__
    msg = str(e)
    if t == "LocalEntryNotFoundError":
        return ("Model download failed. The model was not found in local cache "
                "and could not be downloaded from Hugging Face. "
                "Please check your network connection and try again.")
    if "timeout" in t.lower() or "timeout" in msg.lower():
        return ("Model download timed out. "
                "Please check your network connection and try again.")
    if "Connection" in t or "HTTPError" in t or "ConnectError" in t:
        return f"Network error during model download: {msg[:300]}"
    if "OSError" in t and "Disk" in msg:
        return f"Not enough disk space for model download: {msg[:200]}"
    return f"Model download failed ({t}): {msg[:300]}"

def verify_model(model_id="tiny"):
    """Verify model is on disk and loadable via faster-whisper. Uses ModelManager for path.
    local_files_only only — no network."""
    try:
        from model_manager import model_manager
        ckpt = model_manager.get_model_path(model_id, "whisper")
        if not ckpt or not os.path.isdir(ckpt):
            emit({"type":"verify_fail","model_id":model_id,
                  "message":"Model not found on disk. Please run prepare-default-model first.",
                  "error_type":"path_missing"})
            return False
        # Check that at least one model file > 1KB exists (not just .lock/.tmp)
        import glob
        files = glob.glob(os.path.join(ckpt, "**", "*"), recursive=True)
        real_files = [f for f in files if os.path.isfile(f) and os.path.getsize(f) > 1024
                      and not f.endswith((".lock",".tmp",".incomplete",".part"))]
        if not real_files:
            emit({"type":"verify_fail","model_id":model_id,
                  "message":"Model directory exists but contains no weight files.",
                  "error_type":"no_weight_files"})
            return False
        # Light load via faster_whisper
        from faster_whisper import WhisperModel
        emit({"type":"progress","stage":"verify","message":"Loading model for verification..."})
        model = WhisperModel(ckpt, device="cpu", compute_type="int8")
        emit({"type":"verify_pass","model_id":model_id,"path":ckpt})
        del model
        return True
    except Exception as e:
        emit({"type":"verify_fail","model_id":model_id,
              "error_type":type(e).__name__,
              "message":_friendly_error(e)})
        return False

def prepare_default_model(model_id="tiny"):
    """Copy bundled model from Resources into user model directory.
    
    No network access. The model is expected to be at Resources/models/whisper/tiny/.
    If missing, fail with a clear message.
    """
    import shutil
    from model_manager import model_manager
    
    BACKEND = "whisper"
    
    emit({"type":"progress","stage":"prepare_model",
          "message":"Preparing default model…",
          "model_source":"bundled","network_required":False,
          "model_id":model_id})
    
    # 1. Check if user already has valid model
    data_dir = model_manager._get_app_data_dir()
    user_model_dir = os.path.join(data_dir, "models", BACKEND, model_id)
    
    if os.path.isdir(user_model_dir) and model_manager._is_valid_whisper_dir(user_model_dir):
        emit({"type":"progress","stage":"prepare_model",
              "message":f"Already present: {model_id}",
              "model_source":"user_cache","network_required":False})
        model_manager.register_model_path(model_id, user_model_dir, BACKEND)
        return True
    
    # 2. Find bundled model
    bundled_model = os.path.join(RESOURCES, "models", BACKEND, model_id)
    if not os.path.isdir(bundled_model):
        emit({"type":"prepare_fail","model_id":model_id,
              "message":"Bundled default model is missing. "
                        "This app bundle is incomplete. Please re-download the DMG.",
              "error_type":"bundled_missing"})
        return False
    
    # Verify key files exist in bundle
    required = ["config.json", "model.bin", "tokenizer.json"]
    for fname in required:
        if not os.path.exists(os.path.join(bundled_model, fname)):
            emit({"type":"prepare_fail","model_id":model_id,
                  "message":f"Bundled default model is damaged (missing {fname}). "
                             "Please re-download the DMG.",
                  "error_type":"bundled_damaged","missing":fname})
            return False
    
    # 3. Copy bundled model into user directory
    emit({"type":"progress","stage":"prepare_model",
          "message":f"Copying bundled {model_id} model…"})
    try:
        os.makedirs(user_model_dir, exist_ok=True)
        for fname in os.listdir(bundled_model):
            src = os.path.join(bundled_model, fname)
            dst = os.path.join(user_model_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
    except OSError as e:
        emit({"type":"prepare_fail","model_id":model_id,
              "message":"Could not copy bundled model. Check disk space and permissions.",
              "error_type":"copy_failed","detail":str(e)[:200]})
        return False
    
    # 4. Validate copied model
    if not model_manager._is_valid_whisper_dir(user_model_dir):
        emit({"type":"prepare_fail","model_id":model_id,
              "message":"Copied model is incomplete. App bundle may be damaged.",
              "error_type":"invalid_copy"})
        return False
    
    # 5. Register path
    model_manager.register_model_path(model_id, user_model_dir, BACKEND)
    
    emit({"type":"prepare_pass","model_id":model_id,"path":user_model_dir,
          "model_source":"bundled","network_required":False})
    return True

def download_model(model_id="tiny"):
    """Download model from Hugging Face (network allowed). Returns True on success.
    
    NOTE: This is NOT called during normal bootstrap. It is an optional online
    path for downloading additional models (e.g. base, small, medium) after the
    app is already running with the bundled tiny model.
    """
    try:
        from model_manager import model_manager
        emit({"type":"progress","stage":"download","message":f"Downloading {model_id}..."})
        ok = model_manager.download_model_sync(model_id, "whisper")
        if ok:
            ckpt = model_manager.get_model_path(model_id, "whisper")
            emit({"type":"download_done","model_id":model_id,"path":ckpt or ""})
            return True
        else:
            emit({"type":"download_fail","model_id":model_id,
                  "message":"Model download returned False with no specific error."})
            return False
    except Exception as e:
        emit({"type":"download_fail","model_id":model_id,
              "error_type":type(e).__name__,
              "message":_friendly_error(e)})
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        emit({"type":"error","reason":"usage"})
        sys.exit(2)
    cmd = sys.argv[1]
    mid = sys.argv[2] if len(sys.argv) > 2 else "tiny"
    if cmd == "download-model":
        ok = download_model(mid)
        sys.exit(0 if ok else 1)
    elif cmd == "verify-model":
        ok = verify_model(mid)
        sys.exit(0 if ok else 1)
    elif cmd == "prepare-default-model":
        ok = prepare_default_model(mid)
        sys.exit(0 if ok else 1)
    else:
        emit({"type":"error","reason":f"unknown cmd {cmd}"})
        sys.exit(2)
