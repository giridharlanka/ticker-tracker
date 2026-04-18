"""Exchange label → Yahoo suffix helpers."""

from __future__ import annotations

import pytest
from ticker_tracker.exchange_map import (
    build_yahoo_price_symbol,
    listing_currency_for_exchange,
    yahoo_suffix_for_exchange,
)


def test_yahoo_suffix_for_exchange_sg() -> None:
    assert yahoo_suffix_for_exchange("SGX") == ".SI"
    assert yahoo_suffix_for_exchange(".SI") == ".SI"


def test_listing_currency_for_exchange() -> None:
    assert listing_currency_for_exchange("NYSE") == "USD"
    assert listing_currency_for_exchange("SGX") == "SGD"


@pytest.mark.parametrize(
    ("ticker", "exchange", "expected"),
    [
        ("Z74", "SGX", "Z74.SI"),
        ("VOO", "NYSE", "VOO"),
        ("FOO", "UNKNOWN", "FOO"),
    ],
)
def test_build_yahoo_price_symbol(ticker: str, exchange: str, expected: str) -> None:
    assert build_yahoo_price_symbol(ticker, exchange) == expected


def test_build_yahoo_price_symbol_keeps_existing_suffix() -> None:
    assert build_yahoo_price_symbol("D05.SI", "SGX") == "D05.SI"
