"""Shared setup validation, persistence, and apply logic (CLI + web)."""

from __future__ import annotations

import re
from typing import Any

from ticker_tracker.config import (
    AppConfig,
    EncryptedConfig,
    set_finance_api_key,
    set_fx_api_key,
)
from ticker_tracker.currency import is_valid_iso4217, normalize_iso4217
from ticker_tracker.finance.twelvedata_adapter import (
    clear_twelvedata_api_key,
    set_twelvedata_api_key,
)
from ticker_tracker.fx.open_exchange_rates import clear_oxr_api_key, set_oxr_api_key

KNOWN_FINANCE_SOURCES = (
    "yahoo",
    "alpha_vantage",
    "twelve_data",
    "finnhub",
    "polygon",
)

FX_SOURCES = (
    "frankfurter",
    "open_exchange_rates",
    "fixer",
    "currencylayer",
)

FREE_FX_SOURCES = frozenset({"frankfurter"})

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

RECOMMENDED_COLUMNS = (
    ("ticker", "Ticker symbol (local code if you use exchange)"),
    ("exchange", "Listing exchange (e.g. NYSE, SGX, LSE, or Yahoo suffix like .SI)"),
    ("shares", "Share quantity"),
    ("cost_basis", "Cost per share (in purchase currency if set, else base currency)"),
    ("purchase_currency", "Optional ISO 4217 currency you paid in (e.g. SGD, USD)"),
    ("currency_override", "Optional: force quote / native currency for that row"),
)

DEFAULT_COLUMN_LETTERS = {
    "ticker": "A",
    "exchange": "B",
    "shares": "C",
    "cost_basis": "D",
    "purchase_currency": "E",
    "currency_override": "F",
}

# Columns that may be omitted in setup forms (blank = not mapped).
OPTIONAL_COLUMN_FIELDS = frozenset({"exchange", "purchase_currency", "currency_override"})


def _validate_google_sheet_id(sheet_id: str) -> list[str]:
    errors: list[str] = []
    if len(sheet_id) < 20:
        errors.append("Google Sheets ID looks too short.")
    if " " in sheet_id or "/" in sheet_id:
        errors.append("Google Sheets ID should not contain spaces or slashes.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", sheet_id):
        errors.append("Google Sheets ID should be alphanumeric (with _ or -).")
    return errors


def _validate_emails(emails: list[str]) -> list[str]:
    bad = [e for e in emails if not EMAIL_RE.fullmatch(e)]
    if not emails:
        return ["At least one email is required."]
    if bad:
        return [f"Invalid email format: {', '.join(bad)}"]
    return []


def _validate_finance(sources: list[str], keys: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for s in sources:
        if s == "yahoo":
            continue
        key = keys.get(s, "")
        if len(key) < 8:
            errors.append(f"API key for '{s}' is missing or too short (min 8 characters).")
    return errors


def _validate_column_map(column_map: dict[str, str]) -> list[str]:
    if not column_map:
        return ["Column map is empty; add at least one mapping."]
    return []


def _validate_base_currency(code: str) -> list[str]:
    if not is_valid_iso4217(code):
        return [f"Unknown or invalid ISO 4217 currency code: {code!r}."]
    return []


def _validate_fx_source(fx_source: str) -> list[str]:
    if fx_source not in FX_SOURCES:
        return [f"Unknown FX source {fx_source!r}. Choose one of: {', '.join(FX_SOURCES)}."]
    return []


def _validate_fx_api_key(fx_source: str, fx_api_key: str | None) -> list[str]:
    if fx_source in FREE_FX_SOURCES:
        return []
    if not fx_api_key or len(fx_api_key) < 8:
        return [f"FX API key is required for source {fx_source!r} (min 8 characters)."]
    return []


def _validate_market_overrides(overrides: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for suffix, cur in overrides.items():
        if not suffix.startswith("."):
            errors.append(f"Suffix {suffix!r} should start with '.'")
        if not is_valid_iso4217(cur):
            errors.append(f"Override {suffix!r} → {cur!r} has invalid currency code.")
    return errors


def verify_setup(
    config: AppConfig,
    *,
    finance_api_keys: dict[str, str],
    fx_api_key: str | None,
) -> list[str]:
    """Return human-readable issues; empty means OK."""
    issues: list[str] = []
    issues.extend(_validate_google_sheet_id(config.google_sheets_id))
    issues.extend(_validate_column_map(config.column_map))
    issues.extend(_validate_emails(config.email_ids))
    issues.extend(_validate_finance(config.finance_sources, finance_api_keys))
    issues.extend(_validate_base_currency(config.base_currency))
    issues.extend(_validate_fx_source(config.fx_source))
    issues.extend(_validate_fx_api_key(config.fx_source, fx_api_key))
    issues.extend(_validate_market_overrides(config.market_currency_overrides))
    issues.extend(_remote_verify_finance_keys(config))
    return issues


def _remote_verify_finance_keys(config: AppConfig) -> list[str]:
    """Placeholder for live API checks; extend when finance adapters exist."""
    return []


def persist_api_keys(
    finance_sources: list[str],
    finance_api_keys: dict[str, str],
    fx_source: str,
    fx_api_key: str | None,
) -> None:
    for src in KNOWN_FINANCE_SOURCES:
        if src not in finance_sources and src != "yahoo":
            set_finance_api_key(src, None)
            if src == "twelve_data":
                clear_twelvedata_api_key()
    for src in finance_sources:
        if src == "yahoo":
            continue
        key = finance_api_keys.get(src)
        set_finance_api_key(src, key)
        if src == "twelve_data" and key:
            set_twelvedata_api_key(key)

    if fx_source in FREE_FX_SOURCES:
        set_fx_api_key(None)
    else:
        set_fx_api_key(fx_api_key)

    if fx_source == "open_exchange_rates" and fx_api_key:
        set_oxr_api_key(fx_api_key)
    else:
        clear_oxr_api_key()


def apply_setup(
    *,
    google_sheets_id: str,
    holdings_sheet_name: str,
    column_map: dict[str, str],
    email_ids: list[str],
    finance_sources: list[str],
    finance_api_keys: dict[str, str],
    base_currency: str,
    fx_source: str,
    fx_api_key: str | None,
    market_currency_overrides: dict[str, str],
    run_on_startup: bool,
    upload_to_drive: bool,
    encrypted_config: EncryptedConfig,
) -> tuple[AppConfig | None, list[str]]:
    """
    Validate, then write ``config.enc`` and keychain entries.

    Returns ``(config, [])`` on success, or ``(None, issues)`` on validation failure.
    """
    cfg = AppConfig(
        google_sheets_id=google_sheets_id.strip(),
        holdings_sheet_name=(holdings_sheet_name.strip() or "Holdings"),
        column_map=column_map,
        email_ids=email_ids,
        finance_sources=finance_sources,
        fx_source=fx_source.strip().lower(),
        base_currency=normalize_iso4217(base_currency),
        market_currency_overrides=market_currency_overrides,
        run_on_startup=run_on_startup,
        upload_to_drive=upload_to_drive,
    )
    issues = verify_setup(
        cfg,
        finance_api_keys=finance_api_keys,
        fx_api_key=fx_api_key,
    )
    if issues:
        return None, issues

    encrypted_config.save(cfg)
    persist_api_keys(finance_sources, finance_api_keys, cfg.fx_source, fx_api_key)
    return cfg, []


def parse_emails_blob(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_market_overrides_blob(text: str) -> dict[str, str]:
    """Parse lines like '.KL=MYR' or '.KL = MYR'."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        suf = left.strip()
        cur = normalize_iso4217(right.strip())
        if suf:
            out[suf] = cur
    return out


def build_column_map_from_recommended_form(form: dict[str, Any]) -> dict[str, str]:
    """Build column_map from web-style keys col_ticker, col_shares, …"""
    mapping: dict[str, str] = {}
    for field, _desc in RECOMMENDED_COLUMNS:
        key = f"col_{field}"
        raw = (form.get(key) or "").strip().upper()
        if field in OPTIONAL_COLUMN_FIELDS and not raw:
            continue
        if raw:
            if not raw.isalpha():
                continue
            mapping[field] = raw
    return mapping
