"""Launcher CLI routing (no Tk mainloop)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticker_tracker.main import main


@patch("ticker_tracker.ui.popup.show_popup")
def test_launcher_default_opens_popup(mock_popup: MagicMock) -> None:
    main([])
    mock_popup.assert_called_once()


@patch("ticker_tracker.setup_wizard.main")
def test_launcher_setup_flag(mock_setup: MagicMock) -> None:
    main(["--setup"])
    mock_setup.assert_called_once()


@patch("ticker_tracker.engine.run_once")
def test_launcher_run_flag(mock_run: MagicMock) -> None:
    main(["--run"])
    mock_run.assert_called_once()


@patch("ticker_tracker.show_config.print_config_cli")
def test_launcher_show_config_cli(mock_show: MagicMock) -> None:
    main(["--show-config"])
    mock_show.assert_called_once_with()


@patch("ticker_tracker.show_config.run_show_config_web")
def test_launcher_show_config_web(mock_web: MagicMock) -> None:
    main(["--show-config", "--web", "--show-config-port", "9999"])
    mock_web.assert_called_once_with(host="127.0.0.1", port=9999)


def test_launcher_web_requires_show_config() -> None:
    import pytest

    with pytest.raises(SystemExit):
        main(["--web"])
