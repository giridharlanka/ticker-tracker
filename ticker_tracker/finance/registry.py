"""Post-processing for adapter quotes (sub-unit currencies) and multi-source fallback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult

# Minor units sometimes quoted as pseudo-ISO codes; map to major unit and divisor.
SUB_UNIT_CURRENCIES: dict[str, tuple[str, int]] = {
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
}


def apply_sub_unit_correction(result: PriceResult) -> PriceResult:
    """
    If ``result.currency`` is a known sub-unit (e.g. GBX), convert ``price`` to major units.

    ``raw_price`` and original sub-unit semantics are preserved; ``currency`` becomes the
    major ISO code (e.g. GBP).
    """
    mapped = SUB_UNIT_CURRENCIES.get(result.currency)
    if mapped:
        major, divisor = mapped
        result.price = result.raw_price / divisor
        result.currency = major
    return result


def apply_sub_unit_corrections(results: Mapping[str, PriceResult]) -> dict[str, PriceResult]:
    """Apply :func:`apply_sub_unit_correction` to each value (in place)."""
    for r in results.values():
        apply_sub_unit_correction(r)
    return dict(results)


def get_prices_with_fallback(
    adapters: Sequence[FinanceAdapter],
    tickers: list[str],
) -> dict[str, PriceResult]:
    """
    Try ``adapters`` **in config order**; merge quotes so a later source only fills
    tickers still missing after earlier ones (per-ticker fallback).

    Example: Yahoo returns 20 of 22 symbols → Finnhub is called only for the 2 missing;
    any still missing go to Alpha Vantage, etc. Sub-unit correction runs on the merged map.

    Raises:
        FinanceAdapterError: If no adapter returns any quote, or ``adapters`` is empty.
    """
    if not adapters:
        raise FinanceAdapterError("No finance adapters configured.")
    if not tickers:
        return {}

    ordered: list[str] = []
    for raw in tickers:
        t = str(raw).strip()
        if not t:
            continue
        if t not in ordered:
            ordered.append(t)
    if not ordered:
        return {}

    merged: dict[str, PriceResult] = {}
    pending = list(ordered)
    last_exc: FinanceAdapterError | None = None

    for adapter in adapters:
        if not pending:
            break
        try:
            got = adapter.get_prices(pending)
        except FinanceAdapterError as exc:
            last_exc = exc
            continue
        for sym, pr in got.items():
            if sym in pending and sym not in merged:
                merged[sym] = pr
        pending = [t for t in pending if t not in merged]

    if not merged:
        raise FinanceAdapterError("No price quotes from any configured source.") from last_exc
    return apply_sub_unit_corrections(merged)
