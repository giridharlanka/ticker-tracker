"""Tests for Sheets holdings reader (mocked API)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ticker_tracker.google.sheets import (
    column_letter_to_index,
    index_to_column_letter,
    read_holdings,
)


@pytest.mark.parametrize(
    ("letter", "idx"),
    [("A", 0), ("B", 1), ("Z", 25), ("AA", 26), ("AB", 27)],
)
def test_column_letter_round_trip(letter: str, idx: int) -> None:
    assert column_letter_to_index(letter) == idx
    assert index_to_column_letter(idx) == letter


@patch("ticker_tracker.google.sheets.build")
def test_read_holdings_maps_columns(mock_build: MagicMock) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_ret = mock_service.spreadsheets.return_value.values.return_value.get.return_value
    get_ret.execute.return_value = {
        "values": [
            ["AAPL", "10", "1500.00"],
            ["MSFT", "2", "800"],
        ]
    }
    fake_creds = MagicMock(name="creds")

    rows = read_holdings(
        "spreadsheet-id-12345678901234567890",
        "Holdings",
        {"ticker": "A", "shares": "B", "cost_basis": "C"},
        credentials=fake_creds,
    )

    assert rows == [
        {"ticker": "AAPL", "shares": "10", "cost_basis": "1500.00"},
        {"ticker": "MSFT", "shares": "2", "cost_basis": "800"},
    ]
    mock_build.assert_called_once_with(
        "sheets", "v4", credentials=fake_creds, cache_discovery=False
    )
    inner = mock_service.spreadsheets.return_value.values.return_value.get
    inner.assert_called_once_with(
        spreadsheetId="spreadsheet-id-12345678901234567890",
        range="'Holdings'!A2:C",
    )


@patch("ticker_tracker.google.sheets.build")
def test_read_holdings_non_contiguous_columns(mock_build: MagicMock) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_ret = mock_service.spreadsheets.return_value.values.return_value.get.return_value
    get_ret.execute.return_value = {"values": [["MSFT", "", "5", "", "1000"]]}
    fake_creds = MagicMock()
    # B, D, F -> slice covers B through F; indices 1,3,5 relative to B (base 1)
    rows = read_holdings(
        "id",
        "Tab1",
        {"ticker": "B", "shares": "D", "cost_basis": "F"},
        credentials=fake_creds,
    )
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["shares"] == "5"
    assert rows[0]["cost_basis"] == "1000"
    inner = mock_service.spreadsheets.return_value.values.return_value.get
    inner.assert_called_once_with(spreadsheetId="id", range="'Tab1'!B2:F")


@patch("ticker_tracker.google.sheets.build")
def test_read_holdings_exchange_and_purchase_currency(mock_build: MagicMock) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_ret = mock_service.spreadsheets.return_value.values.return_value.get.return_value
    get_ret.execute.return_value = {"values": [["Z74", "SGX", "100", "1.5", "SGD"]]}
    fake_creds = MagicMock()

    rows = read_holdings(
        "id",
        "Holdings",
        {
            "ticker": "A",
            "exchange": "B",
            "shares": "C",
            "cost_basis": "D",
            "purchase_currency": "E",
        },
        credentials=fake_creds,
    )
    assert rows[0] == {
        "ticker": "Z74",
        "exchange": "SGX",
        "shares": "100",
        "cost_basis": "1.5",
        "purchase_currency": "SGD",
    }
