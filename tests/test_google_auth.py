"""Tests for Google OAuth (mocked keychain / refresh)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ticker_tracker.google.auth import (
    KEYRING_GOOGLE_OAUTH_USER,
    KEYRING_GOOGLE_SERVICE,
    get_credentials,
    google_credentials_json_path,
)


def _installed_client(tmp_path: Path) -> Path:
    p = tmp_path / "credentials.json"
    p.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "test-client-id",
                    "client_secret": "test-client-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )
    return p


def test_get_credentials_loads_from_keychain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    creds_path = _installed_client(tmp_path)
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    blob = json.dumps(
        {"access_token": "access-xyz", "refresh_token": "refresh-abc", "expiry": future}
    )
    store: dict[tuple[str, str], str] = {}

    def get_password(service: str, user: str) -> str | None:
        if service == KEYRING_GOOGLE_SERVICE and user == KEYRING_GOOGLE_OAUTH_USER:
            return blob
        return None

    def set_password(service: str, user: str, password: str) -> None:
        store[(service, user)] = password

    monkeypatch.setattr("ticker_tracker.google.auth.keyring.get_password", get_password)
    monkeypatch.setattr("ticker_tracker.google.auth.keyring.set_password", set_password)

    creds = get_credentials(credentials_path=creds_path, run_local_server_kwargs={})
    assert creds.token == "access-xyz"
    assert creds.refresh_token == "refresh-abc"
    assert store == {}


def test_get_credentials_refresh_updates_keychain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    creds_path = _installed_client(tmp_path)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    blob = json.dumps({"access_token": "expired", "refresh_token": "refresh-abc", "expiry": past})
    saved: list[str] = []

    def get_password(service: str, user: str) -> str | None:
        if service == KEYRING_GOOGLE_SERVICE and user == KEYRING_GOOGLE_OAUTH_USER:
            return blob
        return None

    def set_password(service: str, user: str, password: str) -> None:
        saved.append(password)

    monkeypatch.setattr("ticker_tracker.google.auth.keyring.get_password", get_password)
    monkeypatch.setattr("ticker_tracker.google.auth.keyring.set_password", set_password)

    def fake_refresh(self, request):  # noqa: ANN001
        self.token = "fresh-token"
        self.expiry = datetime.now(UTC) + timedelta(hours=1)

    monkeypatch.setattr(
        "ticker_tracker.google.auth.Credentials.refresh",
        fake_refresh,
    )

    creds = get_credentials(credentials_path=creds_path, run_local_server_kwargs={})
    assert creds.token == "fresh-token"
    assert len(saved) == 1
    data = json.loads(saved[0])
    assert data["access_token"] == "fresh-token"
    assert data["refresh_token"] == "refresh-abc"


def test_google_credentials_json_path_under_config_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ticker_tracker.google.auth.application_config_dir", lambda: tmp_path)
    assert google_credentials_json_path() == tmp_path / "credentials.json"
