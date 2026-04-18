"""Encrypted configuration backed by Fernet and OS keychain material."""

from __future__ import annotations

import base64
import json
import os
import platform
import sys
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import keyring
import keyring.errors
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

KEYRING_SERVICE = "ticker-tracker"
KEYRING_CONFIG_KEY_USER = "config-key"
KEYRING_FX_API_USER = "fx-api-key"
HKDF_INFO = b"ticker-tracker-fernet-v1"


def finance_keyring_username(source: str) -> str:
    """Keychain username for a finance provider API key."""
    return f"finance-api-{source}"


def get_fx_api_key() -> str | None:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_FX_API_USER)


def set_fx_api_key(key: str | None) -> None:
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_FX_API_USER, key)
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_FX_API_USER)
    except keyring.errors.PasswordDeleteError:
        pass


def get_finance_api_key(source: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, finance_keyring_username(source))


def set_finance_api_key(source: str, key: str | None) -> None:
    user = finance_keyring_username(source)
    if key:
        keyring.set_password(KEYRING_SERVICE, user, key)
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, user)
    except keyring.errors.PasswordDeleteError:
        pass


def _machine_fingerprint() -> bytes:
    node = platform.node() or "unknown-host"
    return f"{node}\n{uuid.getnode()}".encode()


def _default_config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ticker-tracker"
        return Path.home() / "AppData" / "Local" / "ticker-tracker"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ticker-tracker"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "ticker-tracker"
    return Path.home() / ".config" / "ticker-tracker"


def default_config_path() -> Path:
    """Filesystem path for the encrypted config blob."""
    return _default_config_dir() / "config.enc"


def application_config_dir() -> Path:
    """Directory for ``config.enc``, ``credentials.json``, and other local app files."""
    return _default_config_dir()


def _get_or_create_keyring_salt() -> bytes:
    """32-byte salt stored in the OS keychain; combined with machine fingerprint for Fernet key."""
    existing = keyring.get_password(KEYRING_SERVICE, KEYRING_CONFIG_KEY_USER)
    if existing:
        return base64.urlsafe_b64decode(existing.encode("ascii"))
    salt = os.urandom(32)
    keyring.set_password(
        KEYRING_SERVICE,
        KEYRING_CONFIG_KEY_USER,
        base64.urlsafe_b64encode(salt).decode("ascii"),
    )
    return salt


def _fernet_from_keychain() -> Fernet:
    salt = _get_or_create_keyring_salt()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=HKDF_INFO,
        backend=default_backend(),
    )
    raw = hkdf.derive(_machine_fingerprint())
    fernet_key = base64.urlsafe_b64encode(raw)
    return Fernet(fernet_key)


@dataclass
class AppConfig:
    """Plain configuration schema (secrets use keyring, not this blob)."""

    email_ids: list[str] = field(default_factory=list)
    finance_sources: list[str] = field(default_factory=list)
    fx_source: str = "frankfurter"
    base_currency: str = "USD"
    run_on_startup: bool = False
    google_sheets_id: str = ""
    holdings_sheet_name: str = "Holdings"
    column_map: dict[str, str] = field(default_factory=dict)
    market_currency_overrides: dict[str, str] = field(default_factory=dict)
    upload_to_drive: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Stored encrypted schema: FX API key lives in OS keychain when needed.
        payload["fx_api_key"] = None
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        return cls(
            email_ids=list(data.get("email_ids") or []),
            finance_sources=list(data.get("finance_sources") or []),
            fx_source=str(data.get("fx_source") or "frankfurter"),
            base_currency=str(data.get("base_currency") or "USD"),
            run_on_startup=bool(data.get("run_on_startup", False)),
            google_sheets_id=str(data.get("google_sheets_id") or ""),
            holdings_sheet_name=str(data.get("holdings_sheet_name") or "Holdings"),
            column_map=dict(data.get("column_map") or {}),
            market_currency_overrides=dict(data.get("market_currency_overrides") or {}),
            upload_to_drive=bool(data.get("upload_to_drive", False)),
        )


class EncryptedConfig:
    """Load and save JSON config encrypted with Fernet (key material from keychain + machine)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.is_file():
            return AppConfig()
        fernet = _fernet_from_keychain()
        raw = self.path.read_bytes()
        try:
            decrypted = fernet.decrypt(raw)
        except InvalidToken as exc:
            raise ValueError(
                "Could not decrypt config.enc (wrong machine, missing keychain entry, "
                "or corrupt file)."
            ) from exc
        payload = json.loads(decrypted.decode("utf-8"))
        return AppConfig.from_dict(payload)

    def save(self, config: AppConfig) -> None:
        fernet = _fernet_from_keychain()
        blob = json.dumps(config.to_dict(), indent=2, sort_keys=True).encode("utf-8")
        token = fernet.encrypt(blob)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(token)
