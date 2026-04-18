"""Tests for portfolio calculator pure functions."""

from __future__ import annotations

import pytest
from ticker_tracker.calculator import (
    cost_basis_base,
    current_value_base,
    format_totals_by_ccy,
    gain_loss_base,
    gain_loss_pct,
    portfolio_summary,
    purchase_amount_lines_by_ccy,
    weight_pct,
)


def test_current_value_base() -> None:
    assert current_value_base(10, 5.0, 1.35) == pytest.approx(67.5)


def test_cost_basis_base_total_row() -> None:
    """Sheet total in base: pass shares=1 and the cell value."""
    assert cost_basis_base(1.0, 1500.0) == pytest.approx(1500.0)


def test_gain_loss_and_pct() -> None:
    assert gain_loss_base(1200.0, 1000.0) == pytest.approx(200.0)
    assert gain_loss_pct(1200.0, 1000.0) == pytest.approx(20.0)
    assert gain_loss_pct(800.0, 0.0) == 0.0


def test_weight_pct() -> None:
    assert weight_pct(250.0, 1000.0) == pytest.approx(25.0)
    assert weight_pct(1.0, 0.0) == 0.0


def test_portfolio_summary() -> None:
    holdings = [
        {
            "ticker": "A",
            "current_value_base": 600.0,
            "cost_basis_base": 500.0,
            "base_currency": "SGD",
            "native_ccy": "USD",
            "market_code": "US",
        },
        {
            "ticker": "B.L",
            "current_value_base": 400.0,
            "cost_basis_base": 450.0,
            "base_currency": "SGD",
            "native_ccy": "GBP",
            "market_code": "L",
        },
    ]
    s = portfolio_summary(holdings)
    assert s["base_currency"] == "SGD"
    assert s["holding_count"] == 2
    assert "totals_purchase_cost_by_ccy" in s
    assert s["total_current_value_base"] == pytest.approx(1000.0)
    assert s["total_cost_basis_base"] == pytest.approx(950.0)
    assert s["total_gain_loss_base"] == pytest.approx(50.0)
    assert "US" in s["markets_covered"] and "L" in s["markets_covered"]
    assert set(s["currencies_in_portfolio"]) == {"USD", "GBP"}
    assert s["assumption_notes"]


def test_portfolio_summary_distinct_ticker_count() -> None:
    row = {
        "ticker": "A",
        "current_value_base": 100.0,
        "cost_basis_base": 100.0,
        "base_currency": "SGD",
        "native_ccy": "USD",
        "market_code": "US",
        "report_ccy": "USD",
        "cost_basis_purchase": 100.0,
        "current_value_purchase": 100.0,
    }
    s = portfolio_summary([row, dict(row)])
    assert s["holding_row_count"] == 2
    assert s["distinct_ticker_count"] == 1
    assert s["holding_count"] == 1


def test_format_totals_by_ccy() -> None:
    assert "SGD" in format_totals_by_ccy({"SGD": 100.0, "USD": 50.0})


def test_purchase_amount_lines_by_ccy_sorted() -> None:
    lines = purchase_amount_lines_by_ccy({"USD": 1.0, "HKD": 2.0})
    assert lines[0].startswith("HKD")
    assert lines[1].startswith("USD")
