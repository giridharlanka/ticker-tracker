"""Alpha Vantage GLOBAL_QUOTE plus SYMBOL_SEARCH for native currency."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from ticker_tracker.config import get_finance_api_key
from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult

ALPHA_URL = "https://www.alphavantage.co/query"


class AlphaVantageAdapter(FinanceAdapter):
    def __init__(self) -> None:
        self._currency_cache: dict[str, str] = {}

    @property
    def source(self) -> str:
        return "alpha_vantage"

    def _request_json(self, params: dict[str, str]) -> dict[str, object]:
        q = urllib.parse.urlencode(params)
        url = f"{ALPHA_URL}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": "ticker-tracker/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise FinanceAdapterError(f"Alpha Vantage HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise FinanceAdapterError(f"Alpha Vantage network error: {exc}") from exc

    def _global_quote_price(self, symbol: str, api_key: str) -> float:
        data = self._request_json({"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key})
        if "Note" in data or "Information" in data:
            raise FinanceAdapterError("Alpha Vantage rate limit or usage notice.")
        if "Error Message" in data:
            raise FinanceAdapterError(str(data["Error Message"]))
        gq = data.get("Global Quote")
        if not isinstance(gq, dict):
            raise FinanceAdapterError(f"No GLOBAL_QUOTE for {symbol!r}")
        price_s = gq.get("05. price")
        if not price_s:
            raise FinanceAdapterError(f"No price in GLOBAL_QUOTE for {symbol!r}")
        return float(str(price_s).strip())

    def _symbol_search_currency(self, symbol: str, api_key: str) -> str:
        sym_u = symbol.upper()
        if sym_u in self._currency_cache:
            return self._currency_cache[sym_u]

        data = self._request_json(
            {"function": "SYMBOL_SEARCH", "keywords": symbol, "apikey": api_key}
        )
        if "Note" in data or "Information" in data:
            raise FinanceAdapterError("Alpha Vantage rate limit on SYMBOL_SEARCH.")
        if "Error Message" in data:
            raise FinanceAdapterError(str(data["Error Message"]))
        matches = data.get("bestMatches")
        if not isinstance(matches, list) or not matches:
            raise FinanceAdapterError(f"No SYMBOL_SEARCH matches for {symbol!r}")

        currency: str | None = None
        for m in matches:
            if not isinstance(m, dict):
                continue
            if str(m.get("1. symbol", "")).upper() == sym_u:
                c = m.get("8. currency")
                if c:
                    currency = str(c).strip().upper()
                    break
        if not currency:
            first = matches[0]
            if isinstance(first, dict):
                c = first.get("8. currency")
                if c:
                    currency = str(c).strip().upper()
        if not currency:
            raise FinanceAdapterError(f"No currency in SYMBOL_SEARCH for {symbol!r}")

        self._currency_cache[sym_u] = currency
        return currency

    def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
        if not tickers:
            return {}

        api_key = get_finance_api_key("alpha_vantage")
        if not api_key:
            raise FinanceAdapterError("Missing Alpha Vantage API key in keychain.")

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
                raw_price = self._global_quote_price(t, api_key)
                currency = self._symbol_search_currency(t, api_key)
            except FinanceAdapterError:
                continue
            out[t] = PriceResult(
                price=raw_price,
                currency=currency,
                raw_price=raw_price,
                source=self.source,
            )
        if not out:
            raise FinanceAdapterError("No Alpha Vantage quotes for requested tickers.")
        return out
