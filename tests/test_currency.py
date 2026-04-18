"""Tests for currency / ISO 4217 validation."""

from __future__ import annotations

import pytest
from ticker_tracker.currency import is_valid_iso4217, normalize_iso4217


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("SGD", True),
        ("usd", True),
        (" EUR ", True),
        ("XXX", False),
        ("US", False),
        ("USDD", False),
        ("", False),
        ("12X", False),
    ],
)
def test_is_valid_iso4217(code: str, expected: bool) -> None:
    assert is_valid_iso4217(code) is expected


def test_normalize_iso4217() -> None:
    assert normalize_iso4217("  sgd  ") == "SGD"
