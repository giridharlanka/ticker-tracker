# ticker-tracker

**ticker-tracker** reads your holdings from **Google Sheets**, fetches live prices (**Yahoo Finance** plus optional **Finnhub**, **Alpha Vantage**, **Twelve Data**), converts everything to your chosen **base currency** using **ECB-based FX** (Frankfurter) or **Open Exchange Rates**, and produces an **Excel report** e‑mailed through **Gmail** (optional **Google Drive** upload is configured in setup). Configuration and API keys stay on your machine: **encrypted config** plus the **OS keychain**.

---

## Prerequisites

- **Python 3.11+** (3.11 or newer recommended; matches CI and type checking).
- A **Google account** you can use for Cloud billing (no charge for the APIs used at typical personal volumes) and OAuth.
- Optional: API keys for paid finance or FX providers if you enable those sources.

---

## Google Cloud setup (step by step)

1. Open [Google Cloud Console](https://console.cloud.google.com/) and **Create project** (any name, e.g. `ticker-tracker`).
2. **APIs & Services → Library** — enable each API:
   - **Google Sheets API** (read your portfolio tab).
   - **Google Drive API** (upload the generated `.xlsx`).
   - **Gmail API** (send the report as an attachment).
3. **APIs & Services → OAuth consent screen**
   - User type: **External** (or Internal if Workspace-only).
   - Add scopes (or rely on defaults when the app requests them): the app requests  
     `spreadsheets.readonly`, `drive.file`, `gmail.send` (see `ticker_tracker/google/auth.py`).
   - Add yourself as a **test user** while the app is in *Testing* mode.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Desktop app** (recommended for the installed flow).
   - Download the JSON and save it as **`credentials.json`** in the app config directory  
     (`~/Library/Application Support/ticker-tracker/` on macOS, or see `ticker_tracker.config.application_config_dir`).
5. First run of Sheets/Drive/Gmail will open a **browser OAuth** window; approve access. Tokens are stored in the **OS keychain**, not in `credentials.json`.

---

## Installation

```bash
git clone https://github.com/<your-org>/ticker-tracker.git
cd ticker-tracker
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install "."
# optional: local Flask setup UI + pytest/ruff/mypy (contributors)
pip install -e ".[dev,web]"
```

Use `pip install -e .` instead of `pip install .` if you want an editable checkout while iterating.

Run the **setup wizard** (stores encrypted `config.enc` and keychain entries):

```bash
python main.py --setup
# or
ticker-tracker --setup
# or (same as ticker-tracker-setup)
ticker-tracker-setup
```

**Daily use:** run `ticker-tracker` or `python main.py` for the **Tk** popup (`Run` / `Skip`). Headless: `ticker-tracker --run` or `python -m ticker_tracker --run`.

**Email notifications:** every address you save in setup is sent the report on each successful run (the GUI shows the full list; it no longer limits sends to a single “profile”).

**Review saved settings** (read-only; same fields as `config.enc`, not keychain secrets):

```bash
ticker-tracker --show-config
ticker-tracker --show-config --web
# optional bind (default 127.0.0.1:8767):
ticker-tracker --show-config --web --show-config-host 127.0.0.1 --show-config-port 8768
```

The web view needs `pip install 'ticker-tracker[web]'` (Flask).

---

## Google Sheets format

Row **1** is treated as a **header** (ignored for data). Data starts at row **2**.

| Column (logical name) | Required | Example | Description |
|----------------------|----------|---------|-------------|
| **ticker** | Yes | `AAPL` or `D05` | Symbol for the instrument. If you use **exchange**, you can use the local code (e.g. `D05` on SGX); otherwise use the full symbol your price source expects (see [Ticker format](#ticker-format--suffix-guide)). |
| **exchange** | No | `SGX` or `NYSE` | Listing venue (common names or MIC-style codes). Used to build the **price** symbol (e.g. `D05` + SGX → `D05.SI` for Yahoo) and, when the price API does not return a currency, to guess **quote currency**. |
| **shares** | Yes | `10` | Number of shares or units. |
| **cost_basis** | Yes | `150` | **Cost per share** in **purchase_currency** if that column is mapped, otherwise in your **base currency**. Total row cost is `shares × cost_basis`, then converted to base when `purchase_currency` is set. |
| **purchase_currency** | No | `SGD` | ISO 4217 code for the currency you paid in for that row’s cost. Leave blank to treat `cost_basis` as already in base currency. |
| **currency_override** | No | `HKD` | If set, forces **listing / quote** currency for that row when the suffix, exchange hint, or provider is ambiguous. See [multi-currency doc](docs/multi_currency.md#cost-basis-vs-currency-override). |

**Sample rows** (base currency e.g. **SGD**; first row uses cost in SGD via `purchase_currency`):

| ticker | exchange | shares | cost_basis | purchase_currency | currency_override |
|--------|----------|--------|------------|-------------------|---------------------|
| AAPL   |          | 5      | 240        | USD               |                     |
| D05    | SGX      | 2000   | 9.25       | SGD               |                     |
| 0005   | HKEX     | 400    | 800        | HKD               |                     |
| SHEL   | LSE      | 150    | 15         | GBP               |                     |

**Example mixed portfolio (listing currencies):**

| Ticker   | Listing CCY | Notes |
|----------|---------------|--------|
| **AAPL** | USD | US listing. |
| **D05.SI** | SGD | Singapore listing (DBS). |
| **0005.HK** | HKD | Hong Kong listing (HSBC). |
| **SHEL.L** | GBP | London listing; see **LSE pence** note below. |

---

## Finance sources

| Config id | Description | API key | Get started |
|-----------|-------------|---------|-------------|
| **yahoo** | Yahoo Finance (via `yfinance`) | No | [yfinance](https://github.com/ranaroussi/yfinance) |
| **finnhub** | [Finnhub](https://finnhub.io/) quote + profile (currency); **ETF profile** if company profile omits currency | Yes (keychain `finance-api-finnhub`) | Per-symbol fallback when Yahoo omits a ticker; see **Finnhub client behaviour** below. |
| **alpha_vantage** | Alpha Vantage GLOBAL_QUOTE + symbol search | Yes (keychain `finance-api-alpha_vantage`) | [Alpha Vantage](https://www.alphavantage.co/support/#api-key) |
| **twelve_data** | Twelve Data `/quote` | Yes (keychain `ticker-tracker-twelvedata`) | [Twelve Data](https://twelvedata.com/) |
| **polygon** | — | — | Reserved in setup; not implemented yet. |

**Source order (`finance_sources` in config):** list ids **top to bottom** — that is try-first → try-last. The engine **merges** prices: each source is asked only for symbols still missing; e.g. Yahoo fills most rows, then Finnhub is called for the remainder, then Alpha Vantage for any still missing. Each holding’s `PriceResult.source` records which provider supplied that quote.

**Batch behaviour:** **Finnhub**, **Alpha Vantage**, and **Twelve Data** resolve **each symbol independently** — one unknown or failing ticker does not prevent the rest of that batch from returning quotes.

**Finnhub client behaviour:** Matches the official [finnhub-python](https://github.com/Finnhub-Stock-API/finnhub-python) base URL order: **`api.finnhub.io`** first, then **`finnhub.io`**. Retries with backoff on transient errors (**429**, **502–504**, network). Quote uses **current / prior close / open / high / low** (first positive value). If the profile request fails after a good quote, the row still gets a price with **USD** as currency unless another source filled it earlier in the merge.

**One ticker shows “—” for price while others work:** the sheet symbol often does not match what APIs expect (e.g. iShares **CSPX** on the London Stock Exchange is usually quoted as **`CSPX.L`** on Yahoo / many feeds, not bare `CSPX`). Set **exchange** (e.g. LSE) or put the **full symbol** your provider uses in **ticker**. Backup sources only help when they recognise the same symbol string.

---

## FX rate sources

| Config id | API key | Default? | Notes |
|-----------|---------|----------|--------|
| **frankfurter** | No | **Yes** | ECB-oriented rates from [Frankfurter](https://www.frankfurter.app/); batch fetch per run. |
| **open_exchange_rates** | Yes (`ticker-tracker-oxr` + main FX slot) | No | [Open Exchange Rates](https://openexchangerates.org/signup); free tier is USD-based; app cross-rates to your base. |
| **fixer** / **currencylayer** | Would use main FX slot | — | Shown in setup; **adapters not implemented** — use Frankfurter or OXR. |

Details: [docs/multi_currency.md](docs/multi_currency.md#fx-rate-sources-comparison).

---

## Multi-currency & base reporting

Your **base currency** (e.g. **SGD**) is the currency of **totals**, **cost basis** (as entered), and the **Excel** report headers. Each holding’s **native** price currency comes from the provider or suffix rules; the engine **converts** native amounts to base using the FX source you picked.

Full walkthrough: **[docs/multi_currency.md](docs/multi_currency.md)**.

---

## Ticker format & suffix guide

Suffixes match **longest** pattern on the ticker (case-insensitive). Built-in defaults (overridable in setup):

| Suffix | Exchange (typical) | CCY | Example tickers |
|--------|---------------------|-----|-------------------|
| `.SI` | Singapore (SGX) | SGD | `D05.SI`, `O39.SI` |
| `.L` | London (LSE) | GBP | `SHEL.L`, `VOD.L` |
| `.HK` | Hong Kong (HKEX) | HKD | `0005.HK`, `0700.HK` |
| `.AX` | Australia (ASX) | AUD | `BHP.AX` |
| `.T` | Japan (TSE) | JPY | `7203.T` |
| `.TO` | Canada (TSX) | CAD | `SHOP.TO` |
| `.NS` | India (NSE) | INR | `RELIANCE.NS` |
| `.KL` | Malaysia (Bursa) | MYR | `MAYBANK.KL` |
| `.DE` | Xetra | EUR | `SAP.DE` |
| `.PA` | Euronext Paris | EUR | `OR.PA` |

### LSE pence (GBX) correction

Some UK feeds quote in **GBX** (pence). The app normalises **GBX → GBP** (÷100) before FX so totals stay in major pounds. If something still looks off for a `.L` line, set **currency override** and verify the symbol on your price source.

---

## Startup configuration

In the setup wizard, choose **Upload report to Google Drive** (Yes/No). When **No**, the workbook is still built and attached to the notification email only.

Enable **Run on startup** to register a **headless** run at login:

- **macOS:** `~/Library/LaunchAgents/com.ticker-tracker.portfolio.plist` + `launchctl bootstrap`.
- **Windows:** `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `TickerTracker`.
- **Linux:** `~/.config/systemd/user/ticker-tracker.service` + `systemctl --user enable`.

The command is **`python -m ticker_tracker --run`** (same interpreter you used to install). Override with env **`TICKER_TRACKER_STARTUP_CMD`** (shell-split) if you need a specific venv path.

---

## Troubleshooting

### OAuth / Google

| Symptom | What to do |
|---------|------------|
| **`redirect_uri_mismatch`** | Desktop client should use **loopback** redirect; use the installed-app flow from this project. Recreate OAuth client as **Desktop**. |
| **`access_blocked` / “app not verified”** | On *Testing* consent screen, add your Google account as a **test user**, or publish the app (stricter verification for sensitive scopes). |
| **`invalid_client`** | `credentials.json` must match the OAuth client; re-download from Cloud Console. |
| **Sheets “not found”** | Check spreadsheet ID and that the account you OAuth’d has access. |

### Rates / providers

| Symptom | What to do |
|---------|------------|
| **Alpha Vantage “Thank you for using…”** | Free tier rate limit; wait or add a paid key / another finance source. |
| **Finnhub 429 / 5xx** | The client **retries** a few times with backoff and may switch host; if it persists, wait or upgrade the Finnhub plan. |
| **Finnhub “rejected” / HTTP 401–403** | Bad or missing API key — re-enter the key in setup (keychain `finance-api-finnhub`). |
| **Twelve Data 429 / errors** | Free tier ~**8 req/min**; reduce symbols or upgrade. |
| **Frankfurter / FX errors offline** | Check network; **forex-python** fallback may also hit the network. |
| **FX source `fixer` / `currencylayer`** | Not implemented — switch to **frankfurter** or **open_exchange_rates** in setup. |

### Config / keychain

| Symptom | What to do |
|---------|------------|
| **Cannot decrypt `config.enc`** | Wrong machine, missing keychain salt (`config-key`), or corrupt file — see [SECURITY.md](SECURITY.md). |

---

## Project layout (short)

| Path | Role |
|------|------|
| `ticker_tracker/main.py` | CLI / GUI entry (`ticker-tracker`). |
| `ticker_tracker/engine.py` | Sheets → FX → prices → XLSX → optional Drive → Gmail. |
| `ticker_tracker/finance/`, `ticker_tracker/fx/` | Price and FX adapters + registries. |
| `ticker_tracker/ui/popup.py` | Tk “Portfolio Tracker” window. |
| `ticker_tracker/ui/startup_registration.py` | OS login registration. |
| `docs/multi_currency.md` | Deep dive on currencies and FX. |

---

## Development

```bash
make install    # venv + editable install with dev + web extras
make setup      # ticker-tracker --setup (CLI wizard)
make run        # ticker-tracker (Tk popup)
make test       # pytest + coverage
make lint       # ruff check + format check
make clean      # caches + coverage artifacts
make typecheck  # mypy (same as CI typecheck job)
```

CI (GitHub Actions): **Ruff**, **mypy**, **pytest** with coverage, and **TruffleHog** secret scanning on `push` / `pull_request` to **`main`**.

---

## Security & disclosure

See **[SECURITY.md](SECURITY.md)** for where secrets live, what is on disk, how to revoke OAuth, rotate API keys, and **responsible disclosure**.

---

## License

Specify your license in `LICENSE` (e.g. MIT) when you publish the repo.
