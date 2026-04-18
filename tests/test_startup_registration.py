"""Startup registration paths (mocked OS commands)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ticker_tracker.ui import startup_registration as su


def test_run_command_args_uses_module_invocation() -> None:
    args = su._run_command_args()
    assert args[0] == __import__("sys").executable
    assert "-m" in args and "ticker_tracker" in args and args[-1] == "--run"


@patch.object(su, "_run_command_args", return_value=["/bin/python", "/tmp/main.py", "--run"])
@patch("subprocess.run")
@patch.object(Path, "write_text")
def test_register_macos_writes_plist_and_bootstraps(
    mock_write: MagicMock,
    mock_run: MagicMock,
    _mock_args: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_run.return_value = subprocess.CompletedProcess([], returncode=0)
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("os.getuid", lambda: 501)
    su.register_startup()
    mock_write.assert_called()
    assert any("bootstrap" in str(c) for c in mock_run.call_args_list)


@patch.object(su, "_deregister_macos")
def test_deregister_macos_called(mock_dm: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    su.deregister_startup()
    mock_dm.assert_called_once()
