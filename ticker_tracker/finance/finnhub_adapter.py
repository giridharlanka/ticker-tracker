"""Finnhub stock quote API (per-symbol quote + profile for ISO currency)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from ticker_tracker.config import get_finance_api_key
from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult

# Primary host matches finnhub-python Client.API_URL; fallback matches common REST docs.
_API_BASES = (
    "https://api.finnhub.io/api/v1",
    "https://finnhub.io/api/v1",
)
_REQUEST_TIMEOUT_SEC = 15.0
_MAX_ATTEMPTS_PER_BASE = 3
_BACKOFF_SEC = 0.55
_RETRIABLE_HTTP = frozenset({429, 502, 503, 504})


class _FinnhubRetry(Exception):
    """Internal: caller should retry same or alternate base after backoff."""

    __slots__ = ()


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode(errors="replace")
    except Exception:
        return ""


def _payload_error_message(data: object) -> str | None:
    if not isinstance(data, dict):
        return None
    err = data.get("error")
    if err is None and "Error Message" in data:
        err = data.get("Error Message")
    if err is None:
        return None
    return str(err).strip()


def _rate_limit_hint(text: str) -> bool:
    t = text.lower()
    return any(s in t for s in ("limit", "rate", "too many", "frequency"))


class FinnhubAdapter(FinanceAdapter):
    """https://finnhub.io/docs/api/quote — ``source`` id ``finnhub``."""

    def __init__(self) -> None:
        self._currency_cache: dict[str, str] = {}

    @property
    def source(self) -> str:
        return "finnhub"

    def _request_json(self, path: str, params: dict[str, str]) -> dict[str, object]:
        key = get_finance_api_key("finnhub")
        if not key:
            raise FinanceAdapterError("Missing Finnhub API key in keychain.")
        q = urllib.parse.urlencode({**params, "token": key})

        last_err: FinanceAdapterError | None = None
        for base in _API_BASES:
            url = f"{base}{path}?{q}"
            for attempt in range(_MAX_ATTEMPTS_PER_BASE):
                try:
                    return self._request_json_once(url)
                except _FinnhubRetry:
                    if attempt + 1 < _MAX_ATTEMPTS_PER_BASE:
                        time.sleep(_BACKOFF_SEC * (2**attempt))
                        continue
                    last_err = FinanceAdapterError(
                        "Finnhub transient failure after "
                        f"{_MAX_ATTEMPTS_PER_BASE} attempts ({base})."
                    )
                    break
                except FinanceAdapterError as exc:
                    last_err = exc
                    break
            continue

        if last_err is not None:
            raise last_err
        raise FinanceAdapterError("Finnhub request failed.")

    def _request_json_once(self, url: str) -> dict[str, object]:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ticker-tracker/0.1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SEC) as resp:
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            body = _read_http_error_body(exc)
            if exc.code in _RETRIABLE_HTTP:
                raise _FinnhubRetry from exc
            if exc.code in (401, 403):
                raise FinanceAdapterError(
                    f"Finnhub rejected the request (HTTP {exc.code}); check the API key."
                ) from exc
            msg = f"HTTP {exc.code}"
            if body:
                try:
                    parsed = json.loads(body)
                    pe = _payload_error_message(parsed)
                    if pe:
                        msg = pe
                    elif isinstance(parsed, dict):
                        msg = f"{msg}: {body[:300]}"
                    else:
                        msg = f"{msg}: {body[:300]}"
                except json.JSONDecodeError:
                    msg = f"{msg}: {body[:300]}"
            raise FinanceAdapterError(f"Finnhub {msg}") from exc
        except urllib.error.URLError as exc:
            raise _FinnhubRetry from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FinanceAdapterError(f"Finnhub invalid JSON: {exc!s}") from exc

        if isinstance(data, dict):
            pe = _payload_error_message(data)
            if pe:
                if _rate_limit_hint(pe):
                    raise _FinnhubRetry from None
                raise FinanceAdapterError(f"Finnhub API: {pe}")
        if not isinstance(data, dict):
            raise FinanceAdapterError("Finnhub returned a non-object JSON value.")
        return data

    def _quote_price(self, symbol: str) -> float:
        data = self._request_json("/quote", {"symbol": symbol})
        keys_order = ("c", "pc", "o", "h", "l")
        for key in keys_order:
            candidate = data.get(key)
            if candidate is None or isinstance(candidate, bool):
                continue
            if not isinstance(candidate, str | int | float):
                continue
            try:
                v = float(candidate)
            except (TypeError, ValueError):
                continue
            if v > 0:
                return v
        raise FinanceAdapterError(f"No Finnhub price for {symbol!r}")

    def _profile_currency(self, symbol: str) -> str:
        sym_u = symbol.upper()
        if sym_u in self._currency_cache:
            return self._currency_cache[sym_u]
        data = self._request_json("/stock/profile2", {"symbol": symbol})
        cur = data.get("currency")
        if cur:
            ccy = str(cur).strip().upper()
            self._currency_cache[sym_u] = ccy
            return ccy
        try:
            etf = self._request_json("/etf/profile", {"symbol": symbol})
            cur2 = etf.get("currency") if isinstance(etf, dict) else None
            if cur2:
                ccy = str(cur2).strip().upper()
                self._currency_cache[sym_u] = ccy
                return ccy
        except FinanceAdapterError:
            pass
        self._currency_cache[sym_u] = "USD"
        return "USD"

    def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
        if not tickers:
            return {}

        ordered: list[str] = []
        for raw in tickers:
            t = raw.strip()
            if not t:
                raise FinanceAdapterError("Empty ticker in request.")
            if t not in ordered:
                ordered.append(t)

        out: dict[str, PriceResult] = {}
        for t in ordered:
            try:
                raw_price = self._quote_price(t)
            except FinanceAdapterError:
                continue
            try:
                currency = self._profile_currency(t)
            except FinanceAdapterError:
                currency = "USD"
            out[t] = PriceResult(
                price=float(raw_price),
                currency=currency,
                raw_price=float(raw_price),
                source=self.source,
            )
        if not out:
            raise FinanceAdapterError("No Finnhub quotes for requested tickers.")
        return out
