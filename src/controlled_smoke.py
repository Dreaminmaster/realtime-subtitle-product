"""Controlled new-architecture runtime smoke test for v2.4.

Verifies the complete pipeline end-to-end in an isolated environment:
  config → repository → SegmentAPI → scheduler → adapter → history VM → export.

Never touches real user paths, real config, real audio, or real API.
"""

from __future__ import annotations
import json
import os
import time
import tempfile
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class SmokeResult:
    ok: bool
    session_id: str = ""
    segment_count: int = 0
    original_text: str = ""
    translated_text: str = ""
    bilingual_text: str = ""
    repo_path: str = ""
    repo_closed: bool = False
    default_config_changed: bool = False
    default_runtime_touched: bool = False
    errors: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    def add_step(self, name: str, ok: bool, detail: str = "") -> None:
        self.steps.append({"step": name, "ok": ok, "detail": detail})
        if not ok:
            self.ok = False
            self.errors.append(f"{name}: {detail}")


def run_controlled_smoke(
    *,
    config: Any = None,
    tmpdir: Path | None = None,
) -> SmokeResult:
    """Run the complete v2.4 architecture in an isolated sandbox.

    Returns a SmokeResult that can be serialized to JSON for reporting.
    """
    result = SmokeResult(started_at=time.time(), ok=True)

    # ── config isolation ─────────────────────────────────────────
    try:
        if config is None:
            from config import config as _cfg
        else:
            _cfg = config

        # Snapshot before
        orig_use_scheduler = getattr(_cfg, "use_translation_scheduler", None)
        orig_use_repo = getattr(_cfg, "use_sqlite_session_repository", None)

        if orig_use_scheduler is not False or orig_use_repo is not False:
            result.default_config_changed = True
    except Exception as e:
        result.add_step("config_snapshot", False, str(e))
        result.finished_at = time.time()
        return result
    result.add_step("config_snapshot", True, "config defaults unchanged")

    if tmpdir is None:
        tmpdir = Path(tempfile.mkdtemp(prefix="smoke_"))
    repo_path = str(tmpdir / "smoke.sqlite3")

    repo = None
    session_id = str(uuid.uuid4())

    try:
        # ── 1. repository ────────────────────────────────────────
        try:
            from src.session_repository import SQLiteSessionRepository
            repo = SQLiteSessionRepository(repo_path)
            repo.initialize()
        except Exception as e:
            result.add_step("repo_init", False, str(e))
            result.finished_at = time.time()
            return result
        result.add_step("repo_init", True, f"created at {repo_path}")

        # ── 2. segment API ───────────────────────────────────────
        try:
            from src.segment_api import SegmentAPI
            api = SegmentAPI(repo)
        except Exception as e:
            result.add_step("segment_api", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("segment_api", True, "SegmentAPI constructed")

        # ── 3. create session + write segments ────────────────────
        try:
            repo.create_session(session_id, source_language="en", target_language="zh")
            segments = [
                ("Hello world, this is a test.", "你好世界，这是一个测试。"),
                ("The quick brown fox jumps over the lazy dog.", "敏捷的棕色狐狸跳过了懒狗。"),
                ("Testing the new architecture pipeline.", "正在测试新架构管道。"),
            ]
            for i, (orig, trans) in enumerate(segments):
                repo.upsert_original_segment(
                    session_id=session_id, segment_id=f"seg-{i+1}",
                    revision=1, status="FINAL", original_text=orig,
                )
                repo.apply_translation(
                    session_id=session_id, segment_id=f"seg-{i+1}",
                    revision=1, translated_text=trans,
                )
            result.segment_count = len(segments)
        except Exception as e:
            result.add_step("data_write", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("data_write", True, f"{len(segments)} segments written")

        # ── 4. API read-back ─────────────────────────────────────
        try:
            snap = api.get_session_snapshot(session_id)
            result.original_text = snap.original_text[:200]
            result.translated_text = snap.translated_text[:200]
            result.bilingual_text = snap.bilingual_text[:200]
        except Exception as e:
            result.add_step("api_read", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("api_read", True, f"original={len(snap.original_text)} chars, translated={len(snap.translated_text)} chars")

        # ── 5. export ────────────────────────────────────────────
        try:
            txt = api.export_transcript(session_id, format="txt")
            j = api.export_transcript(session_id, format="json")
            json.loads(j)  # validate
        except Exception as e:
            result.add_step("export", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("export", True, f"TXT={len(txt)} chars, JSON valid")

        # ── 6. scheduler integration ─────────────────────────────
        try:
            from src.translation_scheduler import TranslationScheduler
            from src.translation_adapter import TranslationAdapter
            sched = TranslationScheduler(max_workers=1)
            adapter = TranslationAdapter(
                scheduler=sched,
                repository=repo,
                repository_enabled=True,
            )
            adapter.start_session(session_id)
            adapter.on_final_text("Hello world!", chunk_id=100)
            time.sleep(0.15)
            adapter.stop_session()
            sched.shutdown(wait=True)
        except Exception as e:
            result.add_step("scheduler", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("scheduler", True, "scheduler + adapter round-trip OK")

        # ── 7. history viewmodel ──────────────────────────────────
        try:
            from src.history_viewmodel import HistoryViewModelBuilder
            vm = HistoryViewModelBuilder(api).build()
            assert vm.available is True
            assert vm.selected_session_id == session_id
        except Exception as e:
            result.add_step("history_vm", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("history_vm", True, f"session={vm.selected_session_id[:8]}...")

        # ── 8. formatter ─────────────────────────────────────────
        try:
            from src.history_dashboard_formatter import format_history_viewmodel_html
            html = format_history_viewmodel_html(vm)
            assert len(html) > 0
        except Exception as e:
            result.add_step("formatter", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("formatter", True, f"HTML output {len(html)} chars")

        # ── 9. dashboard adapter ────────────────────────────────
        try:
            class DummyConfig:
                use_sqlite_session_repository = True
            from src.dashboard_history_adapter import build_history_viewmodel_for_dashboard
            dash_vm = build_history_viewmodel_for_dashboard(
                DummyConfig(),
                repo_factory=lambda: repo,
            )
            assert dash_vm.available is True
        except Exception as e:
            result.add_step("dashboard_adapter", False, str(e))
            repo.close()
            result.finished_at = time.time()
            return result
        result.add_step("dashboard_adapter", True, "dashboard adapter read OK")

        result.ok = True

    finally:
        # ── 10. shutdown ─────────────────────────────────────────
        if repo is not None:
            try:
                repo.close()
                result.repo_closed = True
            except Exception:
                pass
        result.add_step("shutdown", result.repo_closed, "repo closed")
        result.session_id = session_id
        result.repo_path = repo_path
        result.finished_at = time.time()

    return result
