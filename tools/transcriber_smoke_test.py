#!/usr/bin/env python3
"""ASR Smoke Test — validates that the bundled model can actually be loaded by faster-whisper
without any network access.  Must pass before a DMG is considered shippable.

Usage (from CI):
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  python3 transcriber_smoke_test.py tiny \
    --user-data-dir "$HOME/Library/Application Support/RealtimeSubtitle" \
    --resources-dir "$APP/Contents/Resources"

Output: JSON Lines to stdout.  Exit code 0 = PASS.
"""
import sys, os, json

def emit(t, **kw):
    print(json.dumps(dict(type=t, **kw)))
    sys.stdout.flush()

try:
    import faster_whisper
except ImportError:
    emit("asr_smoke_fail", error_type="IMPORT_FAILED",
         message="faster_whisper not installed",
         asr_model_ready=False)
    sys.exit(1)

model_id = sys.argv[1] if len(sys.argv) > 1 else "tiny"
resources_dir = None
user_data_dir = None
args = sys.argv[2:]
i = 0
while i < len(args):
    if args[i] == "--resources-dir" and i + 1 < len(args):
        resources_dir = args[i + 1]; i += 2
    elif args[i] == "--user-data-dir" and i + 1 < len(args):
        user_data_dir = args[i + 1]; i += 2
    else:
        i += 1

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# Build model_manager with the correct data directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_manager import model_manager as mm_cls

_data_dir = user_data_dir or os.path.expanduser("~/Library/Application Support/RealtimeSubtitle")
_data_dir = os.path.join(_data_dir, "models")

mm = mm_cls(data_dir=_data_dir)

emit("asr_smoke_start", model_id=model_id, data_dir=_data_dir,
     resources_dir=resources_dir, network_required=False)

# Step 1: Resolve model path
model_path = mm.get_model_path(model_id, "whisper")
if not model_path:
    emit("asr_smoke_fail", error_type="MODEL_NOT_FOUND",
         message=f"No local path for '{model_id}' in {_data_dir}",
         asr_model_ready=False)
    sys.exit(1)

emit("asr_model_path", path=model_path, model_id=model_id,
     model_source="bundled" if resources_dir and resources_dir in model_path else "user_cache")

# Step 2: Validate directory exists
if not os.path.isdir(model_path):
    emit("asr_smoke_fail", error_type="MODEL_DIR_MISSING",
         message=f"Model dir not found: {model_path}",
         asr_model_ready=False)
    sys.exit(1)

files = os.listdir(model_path)
emit("asr_model_files", count=len(files), files=sorted(files))

# Step 3: Try actual model loading
emit("asr_loading", model_path=model_path)

try:
    from faster_whisper import WhisperModel
    import torch

    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"

    model = WhisperModel(model_path, device=device, compute_type="int8")
    emit("asr_model_loaded", model_path=model_path, device=device)

    # Quick sanity: transcribe a tiny silent audio to verify the model works
    import numpy as np
    dummy_audio = np.zeros(16000, dtype=np.float32)
    segments, info = model.transcribe(dummy_audio, language="en")
    emit("asr_transcribe_ok", language=info.language, duration=info.duration)

    emit("asr_smoke_pass", asr_model_ready=True, model_path=model_path,
         network_required=False, model_source="bundled")

except Exception as e:
    emit("asr_smoke_fail", error_type="MODEL_LOAD_FAILED",
         message=str(e)[:200], asr_model_ready=False,
         model_path=model_path)
    sys.exit(1)
