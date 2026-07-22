from permission_guide import should_show_permission_guide
from main import should_open_permission_guide


def test_permission_guide_shows_before_marker(monkeypatch, tmp_path):
    monkeypatch.setenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR", str(tmp_path))
    monkeypatch.setattr("permission_guide._check_microphone_raw", lambda: True)
    assert should_show_permission_guide() is True


def test_permission_guide_stays_hidden_after_marker(monkeypatch, tmp_path):
    monkeypatch.setenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR", str(tmp_path))
    (tmp_path / ".permission_guide_seen").touch()
    monkeypatch.setattr("permission_guide._check_microphone_raw", lambda: True)
    assert should_show_permission_guide() is False


def test_denied_microphone_reopens_guide(monkeypatch, tmp_path):
    monkeypatch.setenv("REALTIME_SUBTITLE_APP_SUPPORT_DIR", str(tmp_path))
    (tmp_path / ".permission_guide_seen").touch()
    monkeypatch.setattr("permission_guide._check_microphone_raw", lambda: False)
    assert should_show_permission_guide() is True


def test_main_skips_permission_guide_after_success(monkeypatch):
    monkeypatch.setattr(
        "permission_guide.should_show_permission_guide",
        lambda: False,
    )
    assert should_open_permission_guide() is False


def test_no_permission_check_short_circuits_state_probe(monkeypatch):
    def unexpected_probe():
        raise AssertionError("permission state should not be queried")

    monkeypatch.setattr(
        "permission_guide.should_show_permission_guide",
        unexpected_probe,
    )
    assert should_open_permission_guide(no_permission_check=True) is False
