"""Google Sheets API helpers (holdings rows)."""

from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build

from google.oauth2.credentials import Credentials
from ticker_tracker.google.auth import get_credentials

_REQUIRED_FIELDS = ("ticker", "shares", "cost_basis")

# Read order; optional keys are skipped if absent from column_map.
_ROW_FIELD_ORDER = (
    "ticker",
    "exchange",
    "shares",
    "cost_basis",
    "purchase_currency",
    "currency_override",
)


def column_letter_to_index(col: str) -> int:
    """0-based column index from Excel-style letters (A, B, …, AA)."""
    col = col.strip().upper()
    if not col or not col.isalpha():
        raise ValueError(f"Invalid column letter: {col!r}")
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def index_to_column_letter(idx: int) -> str:
    """Excel-style column letters from 0-based index."""
    if idx < 0:
        raise ValueError("Column index must be non-negative")
    idx += 1
    letters = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def _escape_sheet_title(name: str) -> str:
    return name.replace("'", "''")


def _row_fields(column_map: dict[str, str]) -> list[str]:
    for field in _REQUIRED_FIELDS:
        if field not in column_map:
            raise KeyError(f"column_map must include '{field}'")
    return [f for f in _ROW_FIELD_ORDER if f in column_map]


def _a1_range(sheet_name: str, column_map: dict[str, str]) -> str:
    fields = _row_fields(column_map)
    letters = [column_map[f].strip().upper() for f in fields]
    indices = [column_letter_to_index(letter) for letter in letters]
    lo, hi = min(indices), max(indices)
    lo_letter = index_to_column_letter(lo)
    hi_letter = index_to_column_letter(hi)
    quoted = _escape_sheet_title(sheet_name)
    return f"'{quoted}'!{lo_letter}2:{hi_letter}"


def read_holdings(
    spreadsheet_id: str,
    sheet_name: str,
    column_map: dict[str, str],
    *,
    credentials: Credentials | None = None,
) -> list[dict[str, Any]]:
    """
    Read data rows from a sheet tab (row 1 treated as header, skipped via ``A2:`` range).

    *column_map* maps logical names to column letters, e.g.
    ``{'ticker': 'A', 'shares': 'B', 'cost_basis': 'C'}``, optionally
    ``exchange`` (venue for price lookup), ``purchase_currency`` (ISO code for
    cost per share), or ``currency_override`` (force quote currency). Returns
    rows with string values as returned by the API.
    """
    fields = _row_fields(column_map)

    creds = credentials or get_credentials()
    service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    range_a1 = _a1_range(sheet_name, column_map)

    result = (
        service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_a1).execute()
    )
    rows = result.get("values") or []

    letters = [column_map[f].strip().upper() for f in fields]
    indices = [column_letter_to_index(letter) for letter in letters]
    base = min(indices)

    out: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {}
        for field, letter in zip(fields, letters, strict=True):
            idx = column_letter_to_index(letter) - base
            if idx < len(row):
                entry[field] = row[idx]
            else:
                entry[field] = ""
        if any(str(entry[k]).strip() for k in _REQUIRED_FIELDS):
            out.append(entry)
    return out
