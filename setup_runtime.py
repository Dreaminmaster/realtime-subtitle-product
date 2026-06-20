#!/usr/bin/env python3
"""User-venv setup worker — runs model download and verify via JSON line protocol."""
import sys, os, json

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
                  "message":"Model not found on disk. Please run download-model first.",
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

def download_model(model_id="tiny"):
    """Download model from Hugging Face (network allowed). Returns True on success."""
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
    else:
        emit({"type":"error","reason":f"unknown cmd {cmd}"})
        sys.exit(2)
