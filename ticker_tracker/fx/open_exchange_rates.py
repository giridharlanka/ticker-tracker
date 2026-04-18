"""Open Exchange Rates — API key in OS keychain (``ticker-tracker-oxr``)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

import keyring
import keyring.errors

from ticker_tracker.currency import normalize_iso4217
from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate

OXR_KEYRING_SERVICE = "ticker-tracker-oxr"
OXR_KEYRING_USERNAME = "api-key"
OXR_LATEST = "https://openexchangerates.org/api/latest.json"


def get_oxr_api_key() -> str | None:
    return keyring.get_password(OXR_KEYRING_SERVICE, OXR_KEYRING_USERNAME)


def set_oxr_api_key(key: str | None) -> None:
    if key:
        keyring.set_password(OXR_KEYRING_SERVICE, OXR_KEYRING_USERNAME, key)
        return
    try:
        keyring.delete_password(OXR_KEYRING_SERVICE, OXR_KEYRING_USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass


def clear_oxr_api_key() -> None:
    set_oxr_api_key(None)


class OpenExchangeRatesAdapter(FXAdapter):
    """
    OXR latest.json.

    * ``usd_base_only=True`` (free tier): responses are USD-based; non-USD *from* uses
      cross-rates ``rate(to)/rate(from)`` where each rate is units of that currency per 1 USD.
    * ``usd_base_only=False`` (paid): passes ``base=<from_currency>`` and requested symbols.
    """

    def __init__(self, *, usd_base_only: bool = True) -> None:
        self._usd_base_only = usd_base_only

    @property
    def source(self) -> str:
        return "open_exchange_rates"

    def _fetch_usd_rates(
        self, symbols: set[str], api_key: str
    ) -> tuple[dict[str, float], datetime]:
        sym_arg = ",".join(sorted(s for s in symbols if s != "USD"))
        params: dict[str, str] = {"app_id": api_key}
        if sym_arg:
            params["symbols"] = sym_arg
        q = urllib.parse.urlencode(params)
        url = f"{OXR_LATEST}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": "ticker-tracker/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            raise FXAdapterError(f"Open Exchange Rates HTTP error: {exc}") from exc
        except urllib.error.URLError as exc:
            raise FXAdapterError(f"Open Exchange Rates network error: {exc}") from exc

        if not isinstance(payload, dict):
            raise FXAdapterError("Open Exchange Rates invalid JSON")
        rates = payload.get("rates")
        if not isinstance(rates, dict):
            raise FXAdapterError("Open Exchange Rates response missing rates")
        ts = payload.get("timestamp")
        if isinstance(ts, int | float):
            fetched = datetime.fromtimestamp(int(ts), tz=UTC)
        else:
            fetched = datetime.now(UTC)

        out: dict[str, float] = {"USD": 1.0}
        for k, v in rates.items():
            if isinstance(k, str):
                try:
                    out[normalize_iso4217(k)] = float(v)
                except (TypeError, ValueError):
                    continue
        return out, fetched

    def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
        fc = normalize_iso4217(from_currency)
        tc = normalize_iso4217(to_currency)
        if fc == tc:
            return FXRate(fc, tc, 1.0, datetime.now(UTC), self.source)
        got = self.get_rates(fc, [tc])
        if tc not in got:
            raise FXAdapterError(f"No Open Exchange Rates quote {fc} -> {tc}")
        return got[tc]

    def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
        api_key = get_oxr_api_key()
        if not api_key:
            raise FXAdapterError("Missing Open Exchange Rates API key in keychain.")

        fc = normalize_iso4217(from_currency)
        targets: list[str] = []
        seen: set[str] = set()
        for raw in to_currencies:
            t = normalize_iso4217(raw)
            if t == fc or t in seen:
                continue
            seen.add(t)
            targets.append(t)
        if not targets:
            return {}

        if not self._usd_base_only:
            q = urllib.parse.urlencode(
                {
                    "app_id": api_key,
                    "base": fc,
                    "symbols": ",".join(targets),
                }
            )
            url = f"{OXR_LATEST}?{q}"
            req = urllib.request.Request(url, headers={"User-Agent": "ticker-tracker/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                raise FXAdapterError(f"Open Exchange Rates HTTP error: {exc}") from exc
            except urllib.error.URLError as exc:
                raise FXAdapterError(f"Open Exchange Rates network error: {exc}") from exc
            rates = payload.get("rates") if isinstance(payload, dict) else None
            if not isinstance(rates, dict):
                raise FXAdapterError("Open Exchange Rates response missing rates")
            ts = payload.get("timestamp") if isinstance(payload, dict) else None
            if isinstance(ts, int | float):
                fetched = datetime.fromtimestamp(int(ts), tz=UTC)
            else:
                fetched = datetime.now(UTC)
            out: dict[str, FXRate] = {}
            for t in targets:
                raw_v = rates.get(t)
                if raw_v is None:
                    raise FXAdapterError(f"Open Exchange Rates missing {fc} -> {t}")
                out[t] = FXRate(
                    fc,
                    t,
                    float(raw_v),
                    fetched,
                    self.source,
                )
            return out

        # Free tier: USD base — cross via USD-quoted amounts per currency.
        need = set(targets) | {fc}
        need.discard("USD")
        usd_map, fetched = self._fetch_usd_rates(need, api_key)

        def per_usd(code: str) -> float:
            c = normalize_iso4217(code)
            if c == "USD":
                return 1.0
            if c not in usd_map:
                raise FXAdapterError(f"Open Exchange Rates missing USD->{c}")
            return usd_map[c]

        r_from = per_usd(fc)
        cross_rates: dict[str, FXRate] = {}
        for t in targets:
            r_to = per_usd(t)
            # units of ``t`` per 1 ``fc``: (t per USD) / (fc per USD)
            cross = r_to / r_from
            cross_rates[t] = FXRate(fc, t, cross, fetched, self.source)
        return cross_rates
