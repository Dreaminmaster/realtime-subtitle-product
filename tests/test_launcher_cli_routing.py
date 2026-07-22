import os
from unittest.mock import patch

import pytest

import launcher


def test_main_cli_args_only_forwards_supported_flags():
    assert launcher._main_cli_args([
        "launcher.py",
        "-psn_0_12345",
        "--auto-launch",
        "--overlay-only",
        "--no-permission-check",
        "--unknown",
    ]) == ["--overlay-only", "--no-permission-check"]


def test_asr_smoke_reports_unprepared_environment(monkeypatch, capsys, tmp_path):
    missing = tmp_path / "missing-python"
    monkeypatch.setattr(launcher, "_user_venv_python", lambda: str(missing))
    with pytest.raises(SystemExit) as exc:
        launcher._reexec_in_user_venv_for_asr_smoke()
    assert exc.value.code == 1
    assert "EnvironmentNotPrepared" in capsys.readouterr().out


def test_asr_smoke_does_not_reexec_inside_user_venv(monkeypatch, tmp_path):
    venv_python = tmp_path / "python3"
    venv_python.touch()
    monkeypatch.setattr(launcher, "_user_venv_python", lambda: str(venv_python))
    monkeypatch.setattr(os.path, "samefile", lambda left, right: True)
    with patch("os.execve") as execve:
        launcher._reexec_in_user_venv_for_asr_smoke()
    execve.assert_not_called()
