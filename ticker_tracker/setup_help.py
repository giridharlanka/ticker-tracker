"""Human-readable instructions for setup (CLI and web UI)."""

from __future__ import annotations

# Short titles for CLI section headers
TITLES = {
    "google_sheets_id": "Google Sheets ID",
    "holdings_sheet_name": "Holdings sheet (tab) name",
    "column_mapping": "Column mapping",
    "emails": "Email addresses",
    "finance_sources": "Price data sources",
    "base_currency": "Base currency",
    "fx_source": "FX (exchange rate) source",
    "market_overrides": "Custom market suffix → currency",
    "upload_to_drive": "Upload report to Google Drive",
    "run_on_startup": "Run on startup",
}

HELPS: dict[str, str] = {
    "google_sheets_id": """
Open your portfolio spreadsheet in Google Sheets in a web browser.
Look at the address bar. The Sheet ID is the long random-looking string
between "/d/" and the next "/" (often before "/edit").

Example URL:
  https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit
                                      └──────────── copy this part ────────────┘

Paste only that ID here (letters, numbers, hyphens, underscores—no spaces).
""",
    "holdings_sheet_name": """
This is the tab name at the bottom of the spreadsheet where your holdings
live (for example "Holdings", "Portfolio", or "Positions"). It must match
exactly, including spaces and capitals.
""",
    "column_mapping": """
Each row in your sheet should represent one position. Tell the app which
column letter holds each value (A, B, …, AA, etc.—the letters shown above
the grid).

• ticker — symbol for the instrument (local code if you also set exchange).
• exchange — optional; venue or Yahoo suffix (e.g. SGX, NYSE, .SI) so prices match that listing.
• shares — number of shares or units.
• cost_basis — per-share cost in purchase_currency if mapped, else in base currency.
• purchase_currency — optional ISO code (e.g. SGD) for what you paid in; enables cost→base FX.
• currency_override — optional; forces quote/native currency when the provider is ambiguous.

You can skip optional fields by leaving them blank in the web form.
""",
    "emails": """
Addresses that receive each portfolio report (one Gmail send per address).
Enter one address per line in the web form, or one per prompt in the terminal.
All listed addresses are notified on every successful run.
""",
    "finance_sources": """
Choose one or more price sources. The order you select matters: the app tries
the first source for all tickers, then asks the next source only for symbols
that still have no quote, and so on (merged fallback).

Yahoo needs no API key. Finnhub, Alpha Vantage, and Twelve Data need keys;
those keys are stored in your OS keychain, not in the config file.

Unknown source names are ignored with a log warning; supported ids match
the setup labels (yahoo, finnhub, alpha_vantage, twelve_data).
""",
    "base_currency": """
Your home reporting currency as a three-letter ISO 4217 code (examples:
SGD, USD, EUR, GBP). All totals and reports will be converted toward this
currency using your chosen FX source.

See: https://www.iso.org/iso-4217-currency-codes.html
""",
    "fx_source": """
Frankfurter is free (ECB-based rates) and needs no API key—good default.

Open Exchange Rates, Fixer, and Currencylayer are paid/third-party services;
if you pick one, create an account on their site, copy your API key, and
paste it here. The key is stored only in your OS keychain.
""",
    "market_overrides": """
Some tickers use a suffix to show the exchange (e.g. ".KL" for Malaysia).
The app maps common suffixes to currencies automatically; here you can add
or override mappings.

Format in the web form: one mapping per line like  .KL=MYR
The suffix should start with a dot. Use a valid ISO currency code after "=".
""",
    "upload_to_drive": """
If enabled, each successful run uploads the generated Excel workbook to your
Google Drive (using the same Google account as OAuth). If disabled, the file
is only created locally and attached to the notification email (when email
is configured).
""",
    "run_on_startup": """
If enabled, the app can register itself to launch when you log in to your
computer (exact behaviour depends on your OS and a future launcher feature).
""",
}


def help_block(key: str) -> str:
    """Return trimmed help text for *key* (empty string if unknown)."""
    return HELPS.get(key, "").strip()


def print_section(key: str) -> None:
    """Print a titled help block for the CLI."""
    title = TITLES.get(key, key.replace("_", " ").title())
    body = help_block(key)
    print(f"\n{'─' * 4} {title} {'─' * 4}")
    if body:
        for line in body.splitlines():
            line = line.rstrip()
            print(f"  {line}" if line else "")
    else:
        print("  (No extra instructions.)")
