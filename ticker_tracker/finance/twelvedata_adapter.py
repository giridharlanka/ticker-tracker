"""Twelve Data quote endpoint with free-tier rate limiting."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import keyring
import keyring.errors

from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult

TWELVEDATA_KEYRING_SERVICE = "ticker-tracker-twelvedata"
TWELVEDATA_KEYRING_USERNAME = "api-key"
TWELVEDATA_QUOTE_URL = "https://api.twelvedata.com/quote"


def get_twelvedata_api_key() -> str | None:
    try:
        return keyring.get_password(TWELVEDATA_KEYRING_SERVICE, TWELVEDATA_KEYRING_USERNAME)
    except keyring.errors.KeyringError:
        return None


def set_twelvedata_api_key(key: str | None) -> None:
    try:
        if key:
            keyring.set_password(TWELVEDATA_KEYRING_SERVICE, TWELVEDATA_KEYRING_USERNAME, key)
            return
        keyring.delete_password(TWELVEDATA_KEYRING_SERVICE, TWELVEDATA_KEYRING_USERNAME)
    except keyring.errors.KeyringError:
        pass


def clear_twelvedata_api_key() -> None:
    set_twelvedata_api_key(None)


class _MinuteRateLimiter:
    """At most *max_calls* acquisitions per *window_sec* (sliding window)."""

    def __init__(self, max_calls: int, window_sec: float) -> None:
        self._max = max_calls
        self._window = window_sec
        self._lock = threading.Lock()
        self._times: list[float] = []

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._window
            self._times = [t for t in self._times if t > cutoff]
            if len(self._times) >= self._max:
                wait = self._window - (now - self._times[0]) + 0.05
                if wait > 0:
                    time.sleep(wait)
                now = time.monotonic()
                cutoff = now - self._window
                self._times = [t for t in self._times if t > cutoff]
            self._times.append(time.monotonic())


class TwelveDataAdapter(FinanceAdapter):
    """
    Real-time / end-of-day quote from `Twelve Data <https://twelvedata.com/>`_.

    API key is read from the OS keychain (service ``ticker-tracker-twelvedata``).
    """

    _limiter = _MinuteRateLimiter(8, 60.0)

    @property
    def source(self) -> str:
        return "twelve_data"

    def _fetch_quote(self, symbol: str, api_key: str) -> dict[str, object]:
        self._limiter.acquire()
        q = urllib.parse.urlencode({"symbol": symbol, "apikey": api_key})
        url = f"{TWELVEDATA_QUOTE_URL}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": "ticker-tracker/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise FinanceAdapterError(f"Twelve Data HTTP error for {symbol!r}") from exc
        except urllib.error.URLError as exc:
            raise FinanceAdapterError(f"Twelve Data network error for {symbol!r}") from exc
        if not isinstance(payload, dict):
            raise FinanceAdapterError(f"Twelve Data invalid JSON for {symbol!r}")
        if payload.get("status") == "error":
            msg = payload.get("message", payload)
            raise FinanceAdapterError(f"Twelve Data error for {symbol!r}: {msg}")
        return payload

    def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
        if not tickers:
            return {}

        api_key = get_twelvedata_api_key()
        if not api_key:
            raise FinanceAdapterError("Missing Twelve Data API key in keychain.")

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
                data = self._fetch_quote(t, api_key)
                close = data.get("close")
                currency = data.get("currency")
                if close is None or not currency:
                    raise FinanceAdapterError(f"Incomplete Twelve Data quote for {t!r}")
                raw_price = float(str(close))
            except (FinanceAdapterError, TypeError, ValueError):
                continue
            cur = str(currency).strip().upper()
            out[t] = PriceResult(
                price=raw_price,
                currency=cur,
                raw_price=raw_price,
                source=self.source,
            )
        if not out:
            raise FinanceAdapterError("No Twelve Data quotes for requested tickers.")
        return out
