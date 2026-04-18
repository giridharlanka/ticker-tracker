"""Tests for shared setup parsing helpers."""

from __future__ import annotations

from ticker_tracker.setup_core import parse_emails_blob, parse_market_overrides_blob


def test_parse_emails_blob() -> None:
    assert parse_emails_blob("a@b.co\n\nc@d.co\n") == ["a@b.co", "c@d.co"]


def test_parse_market_overrides_blob() -> None:
    raw = "# comment\n.KL=MYR\n.NS = INR\n"
    assert parse_market_overrides_blob(raw) == {".KL": "MYR", ".NS": "INR"}
