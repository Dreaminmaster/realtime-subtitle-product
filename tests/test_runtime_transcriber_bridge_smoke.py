"""Runtime bridge smoke: raw FINAL → pipeline bridge hook → repository → SegmentAPI."""
import pytest
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path


def _smoke(tmp_path, raw_output):
    from src.session_repository import SQLiteSessionRepository
    from src.segment_api import SegmentAPI
    from src.translation_scheduler import TranslationScheduler
    from src.translation_adapter import TranslationAdapter
    from src.runtime_settings_guard import RuntimeSettingsDecision
    from src.runtime_transcriber_bridge_adapter import build_transcriber_output_bridge_for_runtime

    repo_path = str(tmp_path / "bridge_smoke.sqlite3")
    repo = SQLiteSessionRepository(repo_path)
    repo.initialize()
    session_id = str(uuid.uuid4())

    class FakeTranslator:
        def translate(self, text, lang=None):
            return f"ZH:{text}"

    scheduler = TranslationScheduler(translator=FakeTranslator().translate, max_queue=10, max_workers=1)
    adapter = TranslationAdapter(scheduler=scheduler, repository=repo, repository_enabled=True)
    adapter.start_session(session_id)

    decision = RuntimeSettingsDecision(
        ok=True, mode="scheduler_repository", effective_settings={},
        issues=[], recommended_changes={},
        allow_translation_scheduler=True,
        allow_sqlite_repository=True,
        allow_transcriber_output_bridge=True,
    )
    bridge = build_transcriber_output_bridge_for_runtime(decision, session_id=session_id, translation_adapter=adapter)

    result = bridge.handle_raw_output(raw_output)
    time.sleep(0.3)
    adapter.stop_session()
    scheduler.shutdown(wait=True)

    api = SegmentAPI(repo)
    segs = api.list_segments(session_id)
    snap = api.get_session_snapshot(session_id)
    repo.close()

    return {"ok": result.ok, "forwarded": result.forwarded, "segments": len(segs),
            "original": snap.original_text[:200] if snap else "",
            "translated": snap.translated_text[:200] if snap else "",
            "bilingual": snap.bilingual_text[:200] if snap else "",
            "closed": True}


# ── 15. FINAL writes repository ─────────────────────────────────
class TestFinalWritesRepo:
    def test_writes(self, tmp_path):
        r = _smoke(tmp_path, {"text": "hello world", "status": "final"})
        assert r["ok"] is True
        assert r["forwarded"] is True
        assert r["segments"] >= 1
        assert "hello world" in r["original"]
        assert "ZH:" in r["translated"]


# ── 16. partial/stable no translation ───────────────────────────
class TestPartialStableNoTranslation:
    def test_partial(self, tmp_path):
        r = _smoke(tmp_path, {"text": "hel", "status": "partial"})
        assert r["ok"] is True
        assert r["forwarded"] is False
        assert r["segments"] == 0

    def test_stable(self, tmp_path):
        r = _smoke(tmp_path, {"text": "hello", "status": "stable"})
        assert r["ok"] is True
        assert r["forwarded"] is False
        assert r["segments"] == 0


# ── 17. invalid raw controlled ──────────────────────────────────
class TestInvalidSafe:
    def test_none(self, tmp_path):
        r = _smoke(tmp_path, None)
        assert r["ok"] is False
        assert r["forwarded"] is False

    def test_empty(self, tmp_path):
        r = _smoke(tmp_path, {"text": "", "status": "final"})
        assert r["ok"] is False
        assert r["forwarded"] is False


# ── 18. smoke serializable ──────────────────────────────────────
class TestSerializable:
    def test_json(self, tmp_path):
        r = _smoke(tmp_path, {"text": "hello", "status": "final"})
        j = json.dumps(r, default=str)
        assert len(j) > 0
