"""Tests for read-only config display."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ticker_tracker.config import AppConfig, EncryptedConfig
from ticker_tracker.show_config import print_config_cli


@pytest.fixture()
def isolated_keyring(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[tuple[str, str], str]:
    store: dict[tuple[str, str], str] = {}

    def get_password(service_name: str, username: str) -> str | None:
        return store.get((service_name, username))

    def set_password(service_name: str, username: str, password: str) -> None:
        store[(service_name, username)] = password

    monkeypatch.setattr("ticker_tracker.config.keyring.get_password", get_password)
    monkeypatch.setattr("ticker_tracker.config.keyring.set_password", set_password)
    return store


def test_print_config_cli_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    isolated_keyring: dict[tuple[str, str], str],
) -> None:
    path = tmp_path / "config.enc"
    enc = EncryptedConfig(path)
    cfg = AppConfig(
        google_sheets_id="1" * 22,
        email_ids=["u@example.com"],
        finance_sources=["yahoo"],
        upload_to_drive=True,
    )
    enc.save(cfg)

    print_config_cli(config_path=path)
    captured = capsys.readouterr()
    assert "config file:" in captured.err
    data = json.loads(captured.out)
    assert data["google_sheets_id"] == "1" * 22
    assert data["upload_to_drive"] is True
    assert data["fx_api_key"] is None
