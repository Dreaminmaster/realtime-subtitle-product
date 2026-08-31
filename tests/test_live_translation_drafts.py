import threading
import time

from src.live_translation_drafts import LiveTranslationDrafts


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_partial_translation_is_emitted_before_finalization():
    updates = []
    drafts = LiveTranslationDrafts(
        lambda text: f"ZH:{text}",
        lambda *args: updates.append(args),
        interval=0.25,
        min_growth=5,
    )
    drafts.start_session(3)
    assert drafts.submit(3, 8, "hello from a live sentence") is True
    assert _wait_until(lambda: len(updates) == 1)
    assert updates[0] == (
        8,
        "hello from a live sentence",
        "ZH:hello from a live sentence",
    )
    drafts.shutdown(wait=True)


def test_finalization_discards_a_running_draft():
    started = threading.Event()
    release = threading.Event()
    updates = []

    def translate(text):
        started.set()
        assert release.wait(timeout=2.0)
        return f"ZH:{text}"

    drafts = LiveTranslationDrafts(
        translate,
        lambda *args: updates.append(args),
        interval=0.25,
    )
    drafts.start_session(1)
    drafts.submit(1, 2, "sentence still in progress")
    assert started.wait(timeout=1.0)
    drafts.finalize(2)
    release.set()
    time.sleep(0.1)
    assert updates == []
    drafts.shutdown(wait=True)


def test_recent_prefix_translation_uses_latest_original_text():
    started = threading.Event()
    release = threading.Event()
    updates = []

    def translate(text):
        started.set()
        assert release.wait(timeout=2.0)
        return f"ZH:{text}"

    drafts = LiveTranslationDrafts(
        translate,
        lambda *args: updates.append(args),
        interval=0.25,
        min_growth=5,
    )
    drafts.start_session(4)
    drafts.submit(4, 9, "this is the beginning")
    assert started.wait(timeout=1.0)
    drafts.submit(4, 9, "this is the beginning of a longer sentence")
    release.set()
    assert _wait_until(lambda: len(updates) >= 1)
    assert updates[0][1] == "this is the beginning of a longer sentence"
    assert updates[0][2] == "ZH:this is the beginning"
    drafts.shutdown(wait=True)

