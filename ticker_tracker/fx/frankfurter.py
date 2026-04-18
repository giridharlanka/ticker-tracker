"""Frankfurter (ECB) FX API — free, no API key, batch latest rates."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from ticker_tracker.currency import normalize_iso4217
from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate

FRANKFURTER_LATEST = "https://api.frankfurter.app/latest"


class FrankfurterAdapter(FXAdapter):
    @property
    def source(self) -> str:
        return "frankfurter"

    def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
        fc = normalize_iso4217(from_currency)
        tc = normalize_iso4217(to_currency)
        if fc == tc:
            return FXRate(fc, tc, 1.0, datetime.now(UTC), self.source)
        out = self.get_rates(fc, [tc])
        if tc not in out:
            raise FXAdapterError(f"No Frankfurter rate {fc} -> {tc}")
        return out[tc]

    def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
        base = normalize_iso4217(from_currency)
        targets: list[str] = []
        seen: set[str] = set()
        for raw in to_currencies:
            t = normalize_iso4217(raw)
            if t == base or t in seen:
                continue
            seen.add(t)
            targets.append(t)
        if not targets:
            return {}

        q = urllib.parse.urlencode({"from": base, "to": ",".join(targets)})
        url = f"{FRANKFURTER_LATEST}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": "ticker-tracker/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise FXAdapterError(f"Frankfurter HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise FXAdapterError(f"Frankfurter network error: {exc}") from exc

        if not isinstance(payload, dict):
            raise FXAdapterError("Frankfurter invalid JSON")
        rates = payload.get("rates")
        if not isinstance(rates, dict):
            raise FXAdapterError("Frankfurter response missing rates")
        date_s = str(payload.get("date") or "")
        try:
            fetched = datetime.fromisoformat(date_s).replace(tzinfo=UTC)
        except ValueError:
            fetched = datetime.now(UTC)

        out: dict[str, FXRate] = {}
        for t in targets:
            raw_v = rates.get(t)
            if raw_v is None:
                raise FXAdapterError(f"Frankfurter missing rate for {base} -> {t}")
            try:
                rate = float(raw_v)
            except (TypeError, ValueError) as exc:
                raise FXAdapterError(f"Frankfurter bad rate for {t!r}") from exc
            out[t] = FXRate(base, t, rate, fetched, self.source)
        return out
