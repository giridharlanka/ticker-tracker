"""Smoke tests for the local setup web UI."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("flask")

from ticker_tracker.config import EncryptedConfig
from ticker_tracker.web.setup_server import create_app


def test_setup_page_renders(tmp_path: Path) -> None:
    enc = EncryptedConfig(tmp_path / "config.enc")
    app = create_app(enc)
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Google Sheets" in resp.data
    assert b"Frankfurter" in resp.data
