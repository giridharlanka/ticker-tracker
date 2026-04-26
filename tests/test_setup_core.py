"""Tests for shared setup parsing helpers."""

from __future__ import annotations

from pathlib import Path

from ticker_tracker.config import EncryptedConfig
from ticker_tracker.setup_core import (
    apply_setup,
    parse_emails_blob,
    parse_market_overrides_blob,
    resolve_local_report_dir,
)


def test_parse_emails_blob() -> None:
    assert parse_emails_blob("a@b.co\n\nc@d.co\n") == ["a@b.co", "c@d.co"]


def test_parse_market_overrides_blob() -> None:
    raw = "# comment\n.KL=MYR\n.NS = INR\n"
    assert parse_market_overrides_blob(raw) == {".KL": "MYR", ".NS": "INR"}


def test_apply_setup_allows_local_source_without_emails(tmp_path) -> None:
    enc = EncryptedConfig(tmp_path / "config.enc")
    cfg, issues = apply_setup(
        holdings_source="local_file",
        google_sheets_id="",
        holdings_sheet_name="Holdings",
        local_holdings_path="holdings.csv",
        local_holdings_sheet_name="Holdings",
        column_map={"ticker": "ticker", "shares": "shares", "cost_basis": "cost_basis"},
        email_ids=[],
        finance_sources=["yahoo"],
        finance_api_keys={},
        base_currency="SGD",
        fx_source="frankfurter",
        fx_api_key=None,
        market_currency_overrides={},
        run_on_startup=False,
        upload_to_drive=False,
        output_formats=["html"],
        local_report_dir="",
        encrypted_config=enc,
    )
    assert cfg is not None
    assert issues == []


def test_resolve_local_report_dir_blank_uses_temp() -> None:
    import tempfile

    p = resolve_local_report_dir("")
    assert p == Path(tempfile.gettempdir())


def test_apply_setup_rejects_non_dir_local_report(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_dir"
    bad.write_text("x", encoding="utf-8")
    enc = EncryptedConfig(tmp_path / "config.enc")
    _cfg, issues = apply_setup(
        holdings_source="google_sheets",
        google_sheets_id="1" * 22,
        holdings_sheet_name="Holdings",
        local_holdings_path="",
        local_holdings_sheet_name="Holdings",
        column_map={"ticker": "A", "shares": "B", "cost_basis": "C"},
        email_ids=["a@b.co"],
        finance_sources=["yahoo"],
        finance_api_keys={},
        base_currency="SGD",
        fx_source="frankfurter",
        fx_api_key=None,
        market_currency_overrides={},
        run_on_startup=False,
        upload_to_drive=False,
        output_formats=["xlsx"],
        local_report_dir=str(bad),
        encrypted_config=enc,
    )
    assert issues
    assert any("directory" in msg.lower() for msg in issues)
