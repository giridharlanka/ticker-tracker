"""Run-scoped FX cache, conversion, and optional primary/fallback adapters."""

from __future__ import annotations

import logging
from collections.abc import Collection

from ticker_tracker.currency import normalize_iso4217
from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate

logger = logging.getLogger(__name__)


class FXRunRegistry:
    """
    Prime once per run: batch-fetch ``base_currency`` → each involved currency, then convert.

    Rates are stored as returned by the adapter (units of *to* per one *from* for the
    ``base_currency`` → *X* leg used internally).
    """

    def __init__(
        self,
        adapter: FXAdapter,
        base_currency: str,
        involved_currencies: Collection[str],
        *,
        fallback_adapter: FXAdapter | None = None,
    ) -> None:
        self._adapter = adapter
        self._fallback = fallback_adapter
        self._base = normalize_iso4217(base_currency)
        self._involved = {normalize_iso4217(c) for c in involved_currencies} | {self._base}
        # target currency -> FXRate for (base -> target)
        self._base_to: dict[str, FXRate] = {}
        self._primed = False

    @property
    def base_currency(self) -> str:
        return self._base

    def cached_fx_rates(self) -> list[FXRate]:
        """All ``base → target`` legs cached after prime (sorted by target code)."""
        self._prime()
        return [self._base_to[k] for k in sorted(self._base_to)]

    def _prime(self) -> None:
        if self._primed:
            return

        targets = sorted(c for c in self._involved if c != self._base)
        if not targets:
            logger.info("FX run primed: base %s only; no cross rates fetched.", self._base)
            self._primed = True
            return

        last_err: FXAdapterError | None = None
        chosen: FXAdapter | None = None
        for ad in (self._adapter, self._fallback):
            if ad is None:
                continue
            try:
                batch = ad.get_rates(self._base, targets)
                if targets and not batch:
                    raise FXAdapterError("Empty FX batch from adapter.")
                self._base_to = batch
                chosen = ad
                break
            except FXAdapterError as exc:
                last_err = exc
                continue
        else:
            raise FXAdapterError("All FX adapters failed for run prime.") from last_err

        snapshot = {k: round(v.rate, 8) for k, v in sorted(self._base_to.items())}
        logger.info(
            "FX rates fetched for run (source=%s, base=%s): %s",
            chosen.source if chosen else self._adapter.source,
            self._base,
            snapshot,
        )
        self._primed = True

    def _units_per_base(self, currency: str) -> float:
        c = normalize_iso4217(currency)
        if c == self._base:
            return 1.0
        self._prime()
        if c not in self._base_to:
            raise FXAdapterError(f"No FX rate cached for {self._base} -> {c}")
        return self._base_to[c].rate

    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        """Convert *amount* using primed rates (identity if currencies match)."""
        fc = normalize_iso4217(from_currency)
        tc = normalize_iso4217(to_currency)
        if fc == tc:
            return amount
        # amount in fc -> tc: multiply by (units tc per base) / (units fc per base)
        return amount * (self._units_per_base(tc) / self._units_per_base(fc))
