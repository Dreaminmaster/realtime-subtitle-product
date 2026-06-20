#!/usr/bin/env python3
"""CI test — verify bundled model: register, validate, local WhisperModel load."""
import sys, os

RESOURCES = os.environ.get("RESOURCES", "")
MODEL_DST = os.environ.get("MODEL_DST", "")

assert RESOURCES, "RESOURCES not set"
assert MODEL_DST, "MODEL_DST not set"

sys.path.insert(0, RESOURCES)

from model_manager import model_manager

model_manager.register_model_path("tiny", MODEL_DST, "whisper")
print("  ✅ model registered")

path = model_manager.get_model_path("tiny", "whisper")
assert path, "model path not found"
print(f"  ✅ get_model_path(tiny) -> {path}")
assert os.path.isdir(path), f"not a dir: {path}"

for f in ["config.json", "model.bin", "tokenizer.json"]:
    assert os.path.isfile(os.path.join(path, f)), f"missing {f}"
print("  ✅ all model files present")

from faster_whisper import WhisperModel
import warnings
warnings.filterwarnings("ignore")
model = WhisperModel(str(path), device="cpu", compute_type="int8")
print("  ✅ WhisperModel loaded (local-only)")
