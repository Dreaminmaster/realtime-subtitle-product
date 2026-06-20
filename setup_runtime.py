#!/usr/bin/env python3
"""
setup_runtime.py — invoked by SetupController inside the user's venv.

Handles all model operations that need the venv's dependencies
(huggingface_hub, faster-whisper) available.

Usage:
    prepare-default-model <model_id> --resources-dir <path> --user-data-dir <path>
    verify-model <model_id>         --resources-dir <path> --user-data-dir <path>
    download-model <model_id>       --user-data-dir <path>  (online, optional)
    --help

All output is JSON Lines:
    {"type":"prepare_model_ok"|"prepare_model_fail"|"verify_model_ok"|"verify_model_fail"|"download_model_ok"|"download_model_fail", ...}
"""

import sys, os, json, shutil, argparse

RESOURCES_DIR = None
USER_DATA_DIR = None

def emit(obj):
    """Write one JSON line to stdout, flush immediately."""
    line = json.dumps(obj, default=str, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

def fail(error_type, message, **extra):
    """Emit structured failure and exit 1."""
    obj = {"type": error_type, "message": message}
    obj.update(extra)
    emit(obj)
    sys.exit(1)

def ok(type_name, **extra):
    """Emit structured success and exit 0."""
    obj = {"type": type_name}
    obj.update(extra)
    emit(obj)
    sys.exit(0)

def assert_flags():
    if not RESOURCES_DIR or not USER_DATA_DIR:
        fail("usage_error", "Both --resources-dir and --user-data-dir are required",
             resources_dir=bool(RESOURCES_DIR), user_data_dir=bool(USER_DATA_DIR))

# ── helper: find model_manager ──────────────────────────────────────────
def _get_model_manager():
    """Import model_manager from RESOURCES_DIR (add to sys.path)."""
    if RESOURCES_DIR and RESOURCES_DIR not in sys.path:
        sys.path.insert(0, RESOURCES_DIR)
    try:
        from model_manager import model_manager
        return model_manager
    except ImportError as e:
        fail("import_error", f"Cannot import model_manager from {RESOURCES_DIR}: {e}",
             resources_dir=RESOURCES_DIR, sys_path=sys.path[:5])

# ── prepare-default-model ───────────────────────────────────────────────
def prepare_default_model(model_id="tiny"):
    """
    Copy bundled default model from app Resources into user model directory.
    NO NETWORK. Only local file operations.
    """
    assert_flags()

    bundled_dir = os.path.join(RESOURCES_DIR, "models", "whisper", model_id)
    user_models_base = os.path.join(USER_DATA_DIR, "models")
    user_model_dir = os.path.join(user_models_base, "whisper", model_id)

    emit({"type": "prepare_model_progress", "phase": "start",
          "model_id": model_id, "bundled_dir": bundled_dir,
          "user_model_dir": user_model_dir})

    # 1. Does bundled model exist?
    if not os.path.isdir(bundled_dir):
        fail("bundled_model_missing",
             f"Bundled default model not found at: {bundled_dir}",
             model_id=model_id,
             bundled_dir=bundled_dir, exists=False,
             hint="The app bundle is incomplete. Please re-download the DMG and reinstall.")

    # 2. Check key files
    required = ["config.json", "model.bin", "tokenizer.json"]
    missing = [f for f in required if not os.path.isfile(os.path.join(bundled_dir, f))]
    if missing:
        avail = sorted(os.listdir(bundled_dir)) if os.path.isdir(bundled_dir) else []
        fail("bundled_model_incomplete",
             f"Bundled model at {bundled_dir} is missing: {', '.join(missing)}",
             model_id=model_id, bundled_dir=bundled_dir,
             missing=missing, available_files=avail,
             hint="The app bundle is damaged. Please re-download the DMG.")

    # 3. Check if user already has it
    def _is_valid(dirpath):
        if not os.path.isdir(dirpath):
            return False
        return all(os.path.isfile(os.path.join(dirpath, f)) for f in required)

    if _is_valid(user_model_dir):
        # Already present — just register
        emit({"type": "prepare_model_progress", "phase": "already_present",
              "path": user_model_dir})
        mm = _get_model_manager()
        mm.register_model_path(model_id, user_model_dir, "whisper")
        ok("prepare_model_ok", model_id=model_id, model_source="user_cache",
           path=user_model_dir, network_required=False, action="already_present")

    # 4. Copy bundled model to user model directory
    emit({"type": "prepare_model_progress", "phase": "copying",
          "src": bundled_dir, "dst": user_model_dir})
    try:
        os.makedirs(user_model_dir, exist_ok=True)
        copied = 0
        for fname in sorted(os.listdir(bundled_dir)):
            src = os.path.join(bundled_dir, fname)
            dst = os.path.join(user_model_dir, fname)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                copied += 1
        emit({"type": "prepare_model_progress", "phase": "copied",
              "files": copied})
    except OSError as e:
        fail("model_copy_failed",
             f"Cannot copy model files to {user_model_dir}: {e}",
             model_id=model_id, dst=user_model_dir,
             error_type=type(e).__name__, os_error=str(e)[:200],
             hint="Check disk space and write permissions.")

    # 5. Validate copied model
    if not _is_valid(user_model_dir):
        avail = sorted(os.listdir(user_model_dir)) if os.path.isdir(user_model_dir) else []
        fail("model_copy_failed",
             f"Copied model at {user_model_dir} is incomplete",
             model_id=model_id, dst=user_model_dir,
             available_files=avail, missing=[f for f in required if not os.path.isfile(os.path.join(user_model_dir, f))])

    # 6. Register in cache
    mm = _get_model_manager()
    mm.register_model_path(model_id, user_model_dir, "whisper")

    ok("prepare_model_ok", model_id=model_id, model_source="bundled",
       path=user_model_dir, network_required=False, action="copied_from_bundle",
       files_copied=copied)

# ── verify-model (LOCAL ONLY) ───────────────────────────────────────────
def verify_model(model_id="tiny"):
    """Verify model is present and loadable. NO NETWORK."""
    assert_flags()

    user_model_dir = os.path.join(USER_DATA_DIR, "models", "whisper", model_id)
    emit({"type": "verify_model_progress", "phase": "start",
          "model_id": model_id, "path": user_model_dir})

    # 1. Check directory
    if not os.path.isdir(user_model_dir):
        # Maybe check the bundled fallback?
        bundled_dir = os.path.join(RESOURCES_DIR, "models", "whisper", model_id)
        if os.path.isdir(bundled_dir):
            fail("verify_model_fail",
                 f"Default model not prepared. Please reinstall the app.",
                 model_id=model_id, expected=user_model_dir,
                 bundled_present=True, bundled_dir=bundled_dir,
                 hint="The bundled model exists but was not copied. Reinstall the app.")
        else:
            fail("verify_model_fail",
                 f"Bundled default model is missing or damaged. Please reinstall the app.",
                 model_id=model_id, expected=user_model_dir,
                 bundled_present=False,
                 hint="The DMG may be damaged. Re-download and reinstall.")

    # 2. Check key files
    required = ["config.json", "model.bin", "tokenizer.json"]
    missing = [f for f in required if not os.path.isfile(os.path.join(user_model_dir, f))]
    if missing:
        avail = sorted(os.listdir(user_model_dir))
        fail("verify_model_fail",
             f"Model at {user_model_dir} is missing: {', '.join(missing)}",
             model_id=model_id, path=user_model_dir,
             missing=missing, available_files=avail,
             hint="The model installation is incomplete. Reinstall the app.")

    # 3. Attempt local-only load with faster-whisper
    emit({"type": "verify_model_progress", "phase": "loading_whisper"})
    try:
        import warnings
        warnings.filterwarnings("ignore")
        from faster_whisper import WhisperModel
        model = WhisperModel(str(user_model_dir), device="cpu", compute_type="int8")
        emit({"type": "verify_model_progress", "phase": "whisper_loaded"})
    except Exception as e:
        fail("verify_model_fail",
             f"Cannot load model from {user_model_dir}: {e}",
             model_id=model_id, path=user_model_dir,
             error_type=type(e).__name__, error=str(e)[:300],
             hint="The model files exist but are corrupt. Reinstall the app.")

    ok("verify_model_ok", model_id=model_id, path=user_model_dir,
       network_required=False, local_only=True)

# ── download-model (ONLINE — for additional models only) ─────────────────
def download_model(model_id, backend="whisper"):
    """Download a model from Hugging Face. ONLINE — NOT used for default model."""
    assert_flags()

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        fail("download_model_fail",
             "huggingface_hub not available",
             model_id=model_id,
             hint="The venv may be missing dependencies. Reinstall the app.")

    repo_id = f"Systran/faster-whisper-{model_id}"
    emit({"type": "download_model_progress", "phase": "downloading",
          "repo_id": repo_id})

    try:
        snap = snapshot_download(repo_id)
    except Exception as e:
        fail("download_model_fail",
             str(e),
             model_id=model_id, repo_id=repo_id,
             error_type=type(e).__name__)

    # Register
    mm = _get_model_manager()
    mm.register_model_path(model_id, str(snap), backend)

    ok("download_model_ok", model_id=model_id, repo_id=repo_id,
       snapshot_path=str(snap))

# ── cli ──────────────────────────────────────────────────────────────────
def main():
    global RESOURCES_DIR, USER_DATA_DIR

    parser = argparse.ArgumentParser(description="Realtime Subtitle — model operations")
    parser.add_argument("command", choices=["prepare-default-model", "verify-model", "download-model"])
    parser.add_argument("model_id", nargs="?", default="tiny")
    parser.add_argument("--resources-dir", required=True,
                        help="Path to app Resources directory (contains model_manager.py, models/)")
    parser.add_argument("--user-data-dir", required=True,
                        help="Path to user data directory (~/Library/Application Support/RealtimeSubtitle)")

    args = parser.parse_args()
    RESOURCES_DIR = os.path.abspath(args.resources_dir)
    USER_DATA_DIR = os.path.abspath(args.user_data_dir)

    try:
        if args.command == "prepare-default-model":
            prepare_default_model(args.model_id)
        elif args.command == "verify-model":
            verify_model(args.model_id)
        elif args.command == "download-model":
            download_model(args.model_id)
    except SystemExit:
        raise
    except Exception as e:
        # Catch-all: emit structured error, never raw traceback
        import traceback
        fail("internal_error",
             f"Unexpected error in {args.command}: {e}",
             command=args.command, model_id=args.model_id,
             error_type=type(e).__name__, error=str(e)[:500],
             traceback=traceback.format_exc()[-2000:])

if __name__ == "__main__":
    main()
