"""Unit tests for TranscriptEvent."""
import pytest
import time
import uuid
from src.transcript_event import (
    TranscriptEvent, TranscriptPhase, InvalidTranscriptEvent,
)


SID = str(uuid.uuid4())
SEG = str(uuid.uuid4())


def _event(**overrides) -> TranscriptEvent:
    defaults = dict(
        session_id=SID,
        segment_id=SEG,
        utterance_id=1,
        revision=1,
        phase=TranscriptPhase.PARTIAL,
        seq=0,
        text_raw="hello world",
    )
    defaults.update(overrides)
    return TranscriptEvent(**defaults)


class TestCreate:
    def test_create_partial(self):
        e = _event(phase=TranscriptPhase.PARTIAL)
        assert e.phase == TranscriptPhase.PARTIAL
        assert not e.is_final
        assert e.effective_text == "hello world"

    def test_create_final(self):
        e = _event(phase=TranscriptPhase.FINAL)
        assert e.phase == TranscriptPhase.FINAL
        assert e.is_final
        assert e.is_stale is False

    def test_create_stable(self):
        """STABLE is a valid enum value, no special treatment in Phase 1."""
        e = _event(phase=TranscriptPhase.STABLE, text_raw="still going")
        assert e.phase == TranscriptPhase.STABLE
        assert not e.is_final

    def test_default_revision_is_1(self):
        e = TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0, text_raw="x")
        assert e.revision == 1

    def test_default_seq_is_0(self):
        e = TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0, text_raw="x")
        assert e.seq == 0


class TestIsFinal:
    def test_final_is_final(self):
        assert _event(phase=TranscriptPhase.FINAL).is_final is True

    def test_partial_not_final(self):
        assert _event(phase=TranscriptPhase.PARTIAL).is_final is False

    def test_stable_not_final(self):
        assert _event(phase=TranscriptPhase.STABLE, text_raw="...").is_final is False


class TestEffectiveText:
    def test_edited_has_top_priority(self):
        e = _event(text_raw="raw", text_normalized="norm", text_user_edited="edit")
        assert e.effective_text == "edit"

    def test_normalized_second_priority(self):
        e = _event(text_raw="raw", text_normalized="norm")
        assert e.effective_text == "norm"

    def test_raw_when_nothing_else(self):
        e = _event(text_raw="raw")
        assert e.effective_text == "raw"

    def test_none_user_edited_falls_through(self):
        e = _event(text_raw="a", text_user_edited=None, text_normalized="b")
        assert e.effective_text == "b"


class TestValidation:
    def test_session_id_empty_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="session_id"):
            TranscriptEvent(session_id="", segment_id=SEG, utterance_id=0, text_raw="x")

    def test_segment_id_empty_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="segment_id"):
            TranscriptEvent(session_id=SID, segment_id="", utterance_id=0, text_raw="x")

    def test_revision_lt_1_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="revision"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0, revision=0, text_raw="x")

    def test_seq_lt_0_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="seq"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0, seq=-1, text_raw="x")

    def test_utterance_id_lt_0_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="utterance_id"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=-1, text_raw="x")

    def test_end_lt_start_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="end_time"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0,
                            text_raw="x", start_time=5.0, end_time=3.0)

    def test_text_raw_empty_raises_for_partial(self):
        with pytest.raises(InvalidTranscriptEvent, match="text_raw"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0,
                            phase=TranscriptPhase.PARTIAL, text_raw="")

    def test_text_raw_empty_raises_for_final(self):
        with pytest.raises(InvalidTranscriptEvent, match="text_raw"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0,
                            phase=TranscriptPhase.FINAL, text_raw="")

    def test_invalid_phase_raises(self):
        with pytest.raises(InvalidTranscriptEvent, match="phase"):
            TranscriptEvent(session_id=SID, segment_id=SEG, utterance_id=0,
                            phase="INVALID", text_raw="x")


class TestSerialization:
    def test_to_dict_roundtrip(self):
        e = _event(
            text_raw="test", text_normalized="test",
            source_lang="en", target_lang="zh",
            start_time=1.0, end_time=3.5,
        )
        d = e.to_dict()
        e2 = TranscriptEvent.from_dict(d)
        assert e2.session_id == e.session_id
        assert e2.segment_id == e.segment_id
        assert e2.utterance_id == e.utterance_id
        assert e2.revision == e.revision
        assert e2.phase == e.phase
        assert e2.seq == e.seq
        assert e2.text_raw == e.text_raw
        assert e2.text_normalized == e.text_normalized
        assert e2.text_user_edited == e.text_user_edited
        assert e2.translated_text == e.translated_text
        assert e2.source_lang == e.source_lang
        assert e2.target_lang == e.target_lang
        assert e2.start_time == e.start_time
        assert e2.end_time == e.end_time
        assert abs(e2.created_at - e.created_at) < 0.001
        assert e2.is_stale == e.is_stale

    def test_to_dict_with_none_fields(self):
        e = _event(text_normalized=None, text_user_edited=None, translated_text=None,
                   source_lang=None, target_lang=None, start_time=None, end_time=None)
        d = e.to_dict()
        assert d["text_normalized"] is None
        assert d["source_lang"] is None
        e2 = TranscriptEvent.from_dict(d)
        assert e2.text_normalized is None
        assert e2.source_lang is None

    def test_phase_serialized_as_string(self):
        e = _event(phase=TranscriptPhase.FINAL)
        d = e.to_dict()
        assert d["phase"] == "FINAL"
        e2 = TranscriptEvent.from_dict(d)
        assert e2.phase == TranscriptPhase.FINAL

    def test_created_at_is_float(self):
        e = _event()
        d = e.to_dict()
        assert isinstance(d["created_at"], float)


class TestMarkStale:
    def test_mark_stale_returns_stale_event(self):
        e = _event()
        e2 = e.mark_stale()
        assert e2.is_stale is True

    def test_mark_stale_does_not_mutate_original(self):
        e = _event()
        _ = e.mark_stale()
        assert e.is_stale is False  # original unchanged

    def test_mark_stale_preserves_fields(self):
        e = _event(text_raw="keep me", utterance_id=42)
        e2 = e.mark_stale()
        assert e2.text_raw == "keep me"
        assert e2.utterance_id == 42


class TestWithRevision:
    def test_creates_new_revision(self):
        e = _event(revision=1)
        e2 = e.with_revision(2, "edited text")
        assert e2.revision == 2
        assert e2.text_user_edited == "edited text"
        assert e.revision == 1  # original unchanged
        assert e.text_user_edited is None  # original unchanged

    def test_new_revision_not_stale(self):
        e = _event(revision=1)
        e2 = e.with_revision(2)
        assert e2.is_stale is False

    def test_new_revision_created_at_updated(self):
        e = _event()
        time.sleep(0.01)
        e2 = e.with_revision(2)
        assert e2.created_at > e.created_at

    def test_with_revision_no_text_change(self):
        e = _event(text_raw="a", text_user_edited="b")
        e2 = e.with_revision(2)  # no new_text
        assert e2.text_user_edited == "b"  # preserved from original


class TestWithTranslation:
    def test_sets_translated_text(self):
        e = _event()
        e2 = e.with_translation("你好世界")
        assert e2.translated_text == "你好世界"
        assert e.translated_text is None  # original unchanged

    def test_sets_target_lang(self):
        e = _event()
        e2 = e.with_translation("bonjour", target_lang="fr")
        assert e2.target_lang == "fr"

    def test_does_not_change_other_fields(self):
        e = _event(text_raw="raw", utterance_id=5)
        e2 = e.with_translation("trans")
        assert e2.text_raw == "raw"
        assert e2.utterance_id == 5


class TestRevisionIsolation:
    def test_old_revision_not_overwritten_by_new(self):
        """Old and new revisions are separate objects, no cross-contamination."""
        old = _event(revision=1, text_raw="old")
        new = old.with_revision(2, "new text")
        assert old.text_raw == "old"
        assert old.text_user_edited is None
        assert old.revision == 1

        assert new.text_raw == "old"  # text_raw still from original
        assert new.text_user_edited == "new text"
        assert new.revision == 2

    def test_stale_old_new_still_valid(self):
        old = _event(revision=1)
        stale = old.mark_stale()
        new = old.with_revision(2)
        assert stale.is_stale is True
        assert new.is_stale is False
        assert old.is_stale is False  # stale was returned, not mutated

    def test_translation_on_wrong_revision_detectable(self):
        """Translation must be bound to (session_id, segment_id, revision)."""
        r1 = _event(session_id="S1", segment_id="SEG1", revision=1)
        r2 = r1.with_revision(2)
        assert r1.revision == 1
        assert r2.revision == 2
        # A translation result for r1 should NOT apply to r2
        r1t = r1.with_translation("译1")
        assert r1t.translated_text == "译1"
        assert r2.translated_text is None


class TestFactoryCreate:
    def test_create_auto_generates_segment_id(self):
        e = TranscriptEvent.create(
            session_id=SID, utterance_id=1, text_raw="hello"
        )
        assert len(e.segment_id) == 36  # uuid4

    def test_create_respects_explicit_segment_id(self):
        e = TranscriptEvent.create(
            session_id=SID, utterance_id=1, text_raw="hello",
            segment_id="my-custom-id",
        )
        assert e.segment_id == "my-custom-id"

    def test_create_sets_phase(self):
        e = TranscriptEvent.create(
            session_id=SID, utterance_id=1, text_raw="x",
            phase=TranscriptPhase.FINAL,
        )
        assert e.phase == TranscriptPhase.FINAL

    def test_create_default_phase_is_partial(self):
        e = TranscriptEvent.create(
            session_id=SID, utterance_id=1, text_raw="x",
        )
        assert e.phase == TranscriptPhase.PARTIAL
