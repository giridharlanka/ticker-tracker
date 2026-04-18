"""Google OAuth2 for installed apps; tokens stored in the OS keychain."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import keyring
import keyring.errors
from google_auth_oauthlib.flow import InstalledAppFlow

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from ticker_tracker.config import application_config_dir

KEYRING_GOOGLE_SERVICE = "ticker-tracker-google"
KEYRING_GOOGLE_OAUTH_USER = "oauth-token"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]

_TOKEN_URI = "https://oauth2.googleapis.com/token"


def google_credentials_json_path() -> Path:
    """Path to OAuth client ``credentials.json`` (under app config dir, not repo root)."""
    return application_config_dir() / "credentials.json"


def _load_client_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "installed" in data:
        return data["installed"]
    if "web" in data:
        return data["web"]
    raise ValueError("credentials.json must contain an 'installed' or 'web' OAuth client block.")


def _credentials_from_installed(
    installed: dict[str, Any],
    token: str | None,
    refresh_token: str | None,
    expiry: datetime | None,
) -> Credentials:
    return Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=_TOKEN_URI,
        client_id=installed["client_id"],
        client_secret=installed["client_secret"],
        scopes=SCOPES,
        expiry=expiry,
    )


def _expiry_to_naive_utc(dt: datetime | None) -> datetime | None:
    """Google auth compares ``expiry`` to a naive ``utcnow()`` — store naive UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def _serialize_tokens(creds: Credentials) -> str:
    exp = _expiry_to_naive_utc(creds.expiry)
    payload = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": exp.isoformat() if exp else None,
    }
    return json.dumps(payload, separators=(",", ":"))


def _deserialize_tokens(raw: str) -> dict[str, Any]:
    return json.loads(raw)


def _parse_expiry(value: object) -> datetime | None:
    if not value:
        return None
    s = str(value).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return _expiry_to_naive_utc(dt)


def _save_oauth_to_keyring(creds: Credentials) -> None:
    keyring.set_password(
        KEYRING_GOOGLE_SERVICE,
        KEYRING_GOOGLE_OAUTH_USER,
        _serialize_tokens(creds),
    )


def clear_stored_google_oauth() -> None:
    """Remove stored OAuth tokens from the keychain (for tests or reset)."""
    try:
        keyring.delete_password(KEYRING_GOOGLE_SERVICE, KEYRING_GOOGLE_OAUTH_USER)
    except keyring.errors.PasswordDeleteError:
        pass


def get_credentials(
    *,
    credentials_path: Path | None = None,
    run_local_server_kwargs: dict[str, Any] | None = None,
) -> Credentials:
    """
    Return valid user :class:`Credentials`, refreshing or running the installed-app flow as needed.

    ``credentials.json`` is read from the application config directory (see
    :func:`google_credentials_json_path`). After the first browser flow, tokens
    are stored in the keychain under service ``ticker-tracker-google``,
    username ``oauth-token`` as JSON (``access_token``, ``refresh_token``, ``expiry``).
    """
    path = credentials_path or google_credentials_json_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing OAuth client file: {path}. Download JSON from Google Cloud Console "
            "(Desktop app) and save it as credentials.json in the app config directory."
        )

    installed = _load_client_config(path)
    run_kwargs = dict(run_local_server_kwargs or {})
    run_kwargs.setdefault("open_browser", True)

    raw = keyring.get_password(KEYRING_GOOGLE_SERVICE, KEYRING_GOOGLE_OAUTH_USER)
    if raw:
        data = _deserialize_tokens(raw)
        access = data.get("access_token") or data.get("token")
        refresh = data.get("refresh_token")
        expiry = _parse_expiry(data.get("expiry"))

        creds = _credentials_from_installed(installed, access, refresh, expiry)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_oauth_to_keyring(creds)
        elif creds.expired and not creds.refresh_token:
            raise ValueError(
                "Stored Google OAuth access token is expired and no refresh_token is available. "
                "Clear the keychain entry for ticker-tracker-google / oauth-token and run again."
            )
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
    creds = flow.run_local_server(**run_kwargs)
    _save_oauth_to_keyring(creds)
    return creds
