"""Map exchange labels to Yahoo Finance suffixes and typical listing ISO currencies."""

from __future__ import annotations

import re

from ticker_tracker.currency.market_currency import currency_for_ticker

# Keys: normalized alphanumerics (MIC or common short name), uppercased.
_EXCHANGE_TO_YAHOO_SUFFIX: dict[str, str] = {
    "NYSE": "",
    "NASDAQ": "",
    "NASD": "",
    "XNAS": "",
    "XNYS": "",
    "AMEX": "",
    "US": "",
    "USA": "",
    "SGX": ".SI",
    "SG": ".SI",
    "SES": ".SI",
    "SI": ".SI",
    "HKEX": ".HK",
    "HK": ".HK",
    "LSE": ".L",
    "LON": ".L",
    "XLON": ".L",
    "TSE": ".T",
    "TYO": ".T",
    "JPX": ".T",
    "TOKYO": ".T",
    "TSX": ".TO",
    "TSXV": ".V",
    "TSEV": ".V",
    "ASX": ".AX",
    "AU": ".AX",
    "NSE": ".NS",
    "BSE": ".BO",
    "KLSE": ".KL",
    "MY": ".KL",
    "TWSE": ".TW",
    "TW": ".TW",
    "TPE": ".TW",
    "XETRA": ".DE",
    "XETR": ".DE",
    "FRA": ".DE",
    "EURONEXT": ".PA",
    "PAR": ".PA",
    "EPA": ".PA",
}

_EXCHANGE_TO_LISTING_CCY: dict[str, str] = {
    "NYSE": "USD",
    "NASDAQ": "USD",
    "NASD": "USD",
    "XNAS": "USD",
    "XNYS": "USD",
    "AMEX": "USD",
    "US": "USD",
    "USA": "USD",
    "SGX": "SGD",
    "SG": "SGD",
    "SES": "SGD",
    "SI": "SGD",
    "HKEX": "HKD",
    "HK": "HKD",
    "LSE": "GBP",
    "LON": "GBP",
    "XLON": "GBP",
    "TSE": "JPY",
    "TYO": "JPY",
    "JPX": "JPY",
    "TOKYO": "JPY",
    "TSX": "CAD",
    "TSXV": "CAD",
    "TSEV": "CAD",
    "ASX": "AUD",
    "AU": "AUD",
    "NSE": "INR",
    "BSE": "INR",
    "KLSE": "MYR",
    "MY": "MYR",
    "TWSE": "TWD",
    "TW": "TWD",
    "TPE": "TWD",
    "XETRA": "EUR",
    "XETR": "EUR",
    "FRA": "EUR",
    "EURONEXT": "EUR",
    "PAR": "EUR",
    "EPA": "EUR",
}


def _norm_exchange_key(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw.strip().upper())


def yahoo_suffix_for_exchange(exchange: str) -> str | None:
    """Return Yahoo suffix (e.g. ``.SI``) or ``\"\"`` for US; ``None`` if unknown."""
    ex = exchange.strip()
    if not ex:
        return None
    if ex.startswith("."):
        return ex.upper()
    key = _norm_exchange_key(ex)
    return _EXCHANGE_TO_YAHOO_SUFFIX.get(key)


def listing_currency_for_exchange(exchange: str) -> str | None:
    """Typical listing ISO currency for *exchange*, if known."""
    ex = exchange.strip()
    if not ex or ex.startswith("."):
        return None
    key = _norm_exchange_key(ex)
    return _EXCHANGE_TO_LISTING_CCY.get(key)


def build_yahoo_price_symbol(ticker: str, exchange: str) -> str:
    """
    Combine sheet *ticker* and *exchange* into a Yahoo-style symbol.

    If *ticker* already has a recognised Yahoo suffix, return it unchanged.
    Otherwise append the suffix implied by *exchange* when known.
    """
    t = ticker.strip().upper()
    if not t:
        return t
    if currency_for_ticker(t, {}) is not None:
        return t
    suf = yahoo_suffix_for_exchange(exchange)
    if suf is None:
        return t
    return f"{t}{suf}" if suf else t
