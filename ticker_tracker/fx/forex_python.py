"""forex-python CurrencyRates — per-pair calls, suitable as a fallback."""

from __future__ import annotations

from datetime import UTC, datetime

from forex_python.converter import CurrencyRates

from ticker_tracker.currency import normalize_iso4217
from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate


class ForexPythonAdapter(FXAdapter):
    @property
    def source(self) -> str:
        return "forex_python"

    def _client(self) -> CurrencyRates:
        return CurrencyRates()

    def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
        fc = normalize_iso4217(from_currency)
        tc = normalize_iso4217(to_currency)
        if fc == tc:
            return FXRate(fc, tc, 1.0, datetime.now(UTC), self.source)
        try:
            r = float(self._client().get_rate(fc, tc))
        except Exception as exc:
            raise FXAdapterError(f"forex_python rate {fc} -> {tc}: {exc}") from exc
        return FXRate(fc, tc, r, datetime.now(UTC), self.source)

    def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
        fc = normalize_iso4217(from_currency)
        out: dict[str, FXRate] = {}
        seen: set[str] = set()
        for raw in to_currencies:
            tc = normalize_iso4217(raw)
            if tc == fc or tc in seen:
                continue
            seen.add(tc)
            out[tc] = self.get_rate(fc, tc)
        return out
