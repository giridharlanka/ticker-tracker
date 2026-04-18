"""Pure portfolio math in base reporting currency."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def current_value_base(shares: float, price_native: float, fx_rate: float) -> float:
    """
    Current market value in base currency.

    *fx_rate* is the factor that converts a native-currency amount into base
    (same as ``FXRunRegistry.convert(1, native, base)``): multiply ``price_native``
    (per share) by ``fx_rate`` to get price per share in base.
    """
    return float(shares) * float(price_native) * float(fx_rate)


def cost_basis_base(shares: float, cost_per_share_base: float) -> float:
    """
    Total cost in base currency when per-share cost is **already** in base.

    When the sheet maps ``purchase_currency``, the engine converts row cost to
    base before storing ``cost_basis_base`` on each holding; otherwise it uses
    this helper: ``shares × cost_per_share_base``.
    """
    return float(shares) * float(cost_per_share_base)


def gain_loss_base(current_value_base: float, cost_basis_base: float) -> float:
    return float(current_value_base) - float(cost_basis_base)


def gain_loss_pct(current_value_base: float, cost_basis_base: float) -> float:
    if cost_basis_base == 0:
        return 0.0
    cb = abs(float(cost_basis_base))
    return 100.0 * (float(current_value_base) - float(cost_basis_base)) / cb


def weight_pct(holding_value_base: float, total_value_base: float) -> float:
    if total_value_base == 0:
        return 0.0
    return 100.0 * float(holding_value_base) / float(total_value_base)


def format_totals_by_ccy(amounts: dict[str, float]) -> str:
    """Format per-currency totals for summary column (e.g. ``USD 1,200.00 | SGD 500.00``)."""
    if not amounts:
        return "—"
    parts = [f"{ccy} {amt:,.2f}" for ccy, amt in sorted(amounts.items())]
    return " | ".join(parts)


def purchase_amount_lines_by_ccy(amounts: dict[str, float]) -> list[str]:
    """
    One display line per purchase currency (sorted by ISO code).

    Used for summary tables: when several currencies exist, each gets its own row
    in the *Purchased* column under the same metric.
    """
    if not amounts:
        return ["—"]
    return [f"{ccy} {amt:,.2f}" for ccy, amt in sorted(amounts.items())]


def _sum_by_report_ccy(holdings: list[dict[str, Any]], field: str) -> dict[str, float]:
    out: defaultdict[str, float] = defaultdict(float)
    for h in holdings:
        ccy = str(h.get("report_ccy") or "").strip()
        if not ccy:
            continue
        val = h.get(field)
        if isinstance(val, bool) or not isinstance(val, int | float):
            continue
        out[ccy] += float(val)
    return dict(out)


def portfolio_summary(holdings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate metrics for a list of enriched holding dicts (all monetary fields in base).

    Expected keys per holding (best-effort, defaults 0):
    ``current_value_base``, ``cost_basis_base``, optional ``base_currency``,
    ``price_fetch_failed``, ``fx_unavailable``.
    """
    base = ""
    for h in holdings:
        b = str(h.get("base_currency") or "").strip()
        if b:
            base = b
            break

    total_cv = sum(float(h.get("current_value_base") or 0) for h in holdings)
    total_cost = sum(float(h.get("cost_basis_base") or 0) for h in holdings)
    gl = gain_loss_base(total_cv, total_cost)
    gl_pct = gain_loss_pct(total_cv, total_cost)

    cost_by_ccy = _sum_by_report_ccy(holdings, "cost_basis_purchase")
    value_by_ccy = _sum_by_report_ccy(holdings, "current_value_purchase")
    gl_by_ccy: dict[str, float] = {}
    for ccy in sorted(set(cost_by_ccy) | set(value_by_ccy)):
        gl_by_ccy[ccy] = value_by_ccy.get(ccy, 0.0) - cost_by_ccy.get(ccy, 0.0)

    def _tkey(h: dict[str, Any]) -> str:
        return str(h.get("ticker") or "").strip().upper()

    distinct_tickers = len({k for h in holdings if (k := _tkey(h))})

    markets: set[str] = set()
    currencies: set[str] = set()
    for h in holdings:
        m = str(h.get("market_code") or "").strip()
        if m and m != "—":
            markets.add(m)
        c = str(h.get("native_ccy") or "").strip()
        if c:
            currencies.add(c)

    notes = [
        (
            "Quote (native) currency is resolved from optional row override, the price provider, "
            "the sheet exchange hint, then ticker suffix mapping."
        ),
        (
            "Cost per share is in base currency unless the sheet maps purchase_currency; "
            "then total row cost is converted to base via the same FX batch as prices."
        ),
    ]

    return {
        "base_currency": base,
        "holding_count": distinct_tickers,
        "holding_row_count": len(holdings),
        "distinct_ticker_count": distinct_tickers,
        "markets_covered": sorted(markets),
        "currencies_in_portfolio": sorted(currencies),
        "total_current_value_base": total_cv,
        "total_cost_basis_base": total_cost,
        "total_gain_loss_base": gl,
        "total_return_pct": gl_pct,
        "totals_purchase_cost_formatted": format_totals_by_ccy(cost_by_ccy),
        "totals_purchase_value_formatted": format_totals_by_ccy(value_by_ccy),
        "totals_purchase_gl_formatted": format_totals_by_ccy(gl_by_ccy),
        "totals_purchase_cost_by_ccy": dict(cost_by_ccy),
        "totals_purchase_value_by_ccy": dict(value_by_ccy),
        "totals_purchase_gl_by_ccy": dict(gl_by_ccy),
        "assumption_notes": notes,
    }
