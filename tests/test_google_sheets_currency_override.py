"""Optional currency_override column in read_holdings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ticker_tracker.google.sheets import read_holdings


@patch("ticker_tracker.google.sheets.build")
def test_read_holdings_includes_currency_override(mock_build: MagicMock) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_ret = mock_service.spreadsheets.return_value.values.return_value.get.return_value
    get_ret.execute.return_value = {"values": [["AAPL", "10", "1500.00", "USD"]]}
    fake_creds = MagicMock(name="creds")

    rows = read_holdings(
        "spreadsheet-id-12345678901234567890",
        "Holdings",
        {"ticker": "A", "shares": "B", "cost_basis": "C", "currency_override": "D"},
        credentials=fake_creds,
    )

    assert rows == [
        {"ticker": "AAPL", "shares": "10", "cost_basis": "1500.00", "currency_override": "USD"},
    ]
    inner = mock_service.spreadsheets.return_value.values.return_value.get
    inner.assert_called_once_with(
        spreadsheetId="spreadsheet-id-12345678901234567890",
        range="'Holdings'!A2:D",
    )
