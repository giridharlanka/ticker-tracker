"""Ticker suffix to currency mapping; merge with user overrides from config."""

from __future__ import annotations

from collections.abc import Mapping

# Built-in defaults; extend as adapters mature. User `market_currency_overrides` win on key clash.
DEFAULT_EXCHANGE_SUFFIX_TO_CURRENCY: dict[str, str] = {
    ".KL": "MYR",
    ".L": "GBP",
    ".T": "JPY",
    ".HK": "HKD",
    ".SI": "SGD",
    ".AX": "AUD",
    ".TO": "CAD",
    ".NS": "INR",
    ".DE": "EUR",
    ".PA": "EUR",
}


def merged_suffix_map(user_overrides: Mapping[str, str]) -> dict[str, str]:
    """Return built-in suffix map updated with *user_overrides* (user keys replace defaults)."""
    out = dict(DEFAULT_EXCHANGE_SUFFIX_TO_CURRENCY)
    out.update({k: v for k, v in user_overrides.items()})
    return out


def currency_for_ticker(ticker: str, user_overrides: Mapping[str, str]) -> str | None:
    """Return ISO currency for *ticker* based on longest matching suffix, or None if unknown."""
    m = merged_suffix_map(user_overrides)
    matches = [suf for suf in m if ticker.upper().endswith(suf.upper())]
    if not matches:
        return None
    best = max(matches, key=len)
    return m[best]
