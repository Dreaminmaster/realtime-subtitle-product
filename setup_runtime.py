#!/usr/bin/env python3
"""User-venv setup worker — runs model download and verify via JSON line protocol."""
import sys, os, json

def emit(event):
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()

def verify_model(model_id="tiny"):
    """Verify model is on disk and loadable via faster-whisper."""
    import glob
    try:
        from model_manager import model_manager
        ckpt = model_manager.get_model_path(model_id, "whisper")
        if not ckpt:
            models = model_manager.get_models("whisper")
            m = next((x for x in models if x["id"] == model_id), None)
            if not m or not m.get("downloaded"):
                emit({"type":"verify_fail","reason":"cache_not_downloaded"})
                return False
            # Fallback: try known paths
            candidates = [
                os.path.join(model_manager.data_dir, "models", "whisper", model_id),
                os.path.join(model_manager.data_dir, model_id),
            ]
            for cand in candidates:
                if os.path.isdir(cand):
                    ckpt = cand
                    break
            if not ckpt:
                emit({"type":"verify_fail","reason":"path_missing"})
                return False
        # Check that at least one model file > 1KB exists (not just .lock/.tmp)
        import glob
        files = glob.glob(os.path.join(ckpt, "**", "*"), recursive=True)
        real_files = [f for f in files if os.path.isfile(f) and os.path.getsize(f) > 1024
                      and not f.endswith((".lock",".tmp",".incomplete",".part"))]
        if not real_files:
            emit({"type":"verify_fail","reason":"no_weight_files"})
            return False
        # Light load via faster_whisper
        from faster_whisper import WhisperModel
        emit({"type":"progress","stage":"verify","message":"Loading model for verification..."})
        model = WhisperModel(ckpt, device="cpu", compute_type="int8")
        emit({"type":"verify_pass","model_id":model_id,"path":ckpt})
        del model
        return True
    except Exception as e:
        emit({"type":"verify_fail","reason":str(type(e).__name__)})
        return False

def download_model(model_id="tiny"):
    """Download model. Returns True on success."""
    try:
        from model_manager import model_manager
        emit({"type":"progress","stage":"download","message":f"Downloading {model_id}..."})
        ok = model_manager.download_model_sync(model_id, "whisper")
        if ok:
            emit({"type":"download_done","model_id":model_id})
            return True
        else:
            emit({"type":"download_fail","reason":"returned False"})
            return False
    except Exception as e:
        emit({"type":"download_fail","reason":str(type(e).__name__)})
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
