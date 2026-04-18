# Multi-currency portfolios

This document explains how **ticker-tracker** resolves listing currency, converts to your **base currency**, and handles edge cases (LSE pence, cross-listings).

## Suffix → market currency (built-in)

These suffixes are recognised on Yahoo-style tickers (**longest match wins**). They match `DEFAULT_EXCHANGE_SUFFIX_TO_CURRENCY` in `ticker_tracker/currency/market_currency.py`. You can **override or extend** them in setup under *market currency overrides* (format `.SUFFIX=ISO`).

| Suffix | Typical market | ISO currency |
|--------|----------------|--------------|
| `.KL`  | Bursa Malaysia | MYR |
| `.L`   | London Stock Exchange (LSE) | GBP (see *Pence* below) |
| `.T`   | Tokyo Stock Exchange | JPY |
| `.HK`  | Hong Kong Exchange | HKD |
| `.SI`  | Singapore Exchange | SGD |
| `.AX`  | Australian Securities Exchange | AUD |
| `.TO`  | Toronto Stock Exchange | CAD |
| `.NS`  | National Stock Exchange of India | INR |
| `.DE`  | Xetra (Germany) | EUR |
| `.PA`  | Euronext Paris | EUR |

Tickers **without** a recognised suffix fall back to **USD** for FX purposes unless you set **currency override** on the row (see [Cost basis vs currency override](#cost-basis-vs-currency-override)).

## LSE “pence” (GBX) correction

Some UK listings return prices in **GBX** (pence) rather than **GBP** (pounds). The finance layer maps **GBX → GBP** by dividing the raw quote by **100** and switching the currency code to **GBP** before FX conversion. This applies to typical `.L` instruments when the upstream source reports GBX.

If a `.L` line still looks wrong, set **currency override** to the ISO code you intend and verify the price source.

## How FX conversion works (step by step)

1. **Load config** — your **base currency** (e.g. SGD) is the reporting currency for totals and the XLSX report.
2. **Read each holding** — ticker, optional **exchange**, shares, **cost basis per share**, optional **purchase_currency**, optional **currency override**.
3. **Price symbol** — if the sheet ticker already has a recognised Yahoo-style suffix, it is used as-is; otherwise the app may append a suffix from **exchange** (see `ticker_tracker/exchange_map.py`).
4. **Native price currency** — from, in order: **currency override** → price provider’s currency → **exchange listing hint** (when known) → **suffix map** on the ticker → **USD** default.
5. **FX batch** — one run-scoped request loads rates **from base → each involved currency** (quote currencies plus any **purchase_currency** values), with an optional **forex-python** fallback.
6. **Per holding** — `fx_rate = convert(1, native, base)`; **current value in base** = `shares × price_native × fx_rate`.
7. **Cost basis** — if **purchase_currency** is set: `convert(shares × cost_basis, purchase_currency, base)`; otherwise `shares × cost_basis` is already in base. Gain/loss compares market value to that total.

See also the [README](../README.md#multi-currency--base-reporting) summary.

## Cost basis and purchase currency

- If **`purchase_currency`** is **blank** (column not mapped or empty cells): **`cost_basis`** is **per share in your base currency** (same as before).
- If **`purchase_currency`** is set (e.g. `SGD`): **`cost_basis`** is **per share in that currency**; the app converts **total** row cost `shares × cost_basis` to base using the same FX batch as quotes. If that conversion fails, cost basis for the row is treated as **0** and the ticker is listed under **`cost_fx_unavailable_tickers`** in run metadata.

## Cost basis vs currency override

- **`currency_override`** affects **which ISO code is used for the live quote** when resolving native currency (before FX to base). It is useful for **cross-listed symbols**, venues not in the built-in exchange map, or odd provider behaviour.
- It does **not** define purchase currency: use **`purchase_currency`** for the currency your **`cost_basis`** cells are expressed in.

## Custom suffix mappings

Run **`ticker-tracker --setup`** (CLI or optional web UI — see [README – Installation](../README.md#installation)) and enter **market currency overrides** as lines `SUFFIX=ISO`, for example:

```text
.SS=CNY
.SZ=CNY
.TW=TWD
```

Suffix keys must start with `.`; values must be valid **ISO 4217** codes. These merge with the built-in table; **your** entries win on key clash. You can also override a default (e.g. `.L=GBP`) if your data source uses a non-standard convention.

## FX rate sources (comparison)

| Source | API key | Base handling | Notes |
|--------|-----------|----------------|-------|
| **Frankfurter** (default) | None | Any ISO base supported by the API | ECB-oriented free JSON; batch `latest`; used with **forex-python** fallback in-app. |
| **Open Exchange Rates** | Yes (`ticker-tracker-oxr` + generic FX slot) | Free tier is **USD**-based; app **cross-rates** when your base is not USD | Paid tier can use other bases via API. |
| **fixer / currencylayer** | In config schema | — | **Not implemented** in the engine yet; choose Frankfurter or OXR. |

Setup links:

- [Frankfurter](https://www.frankfurter.app/) — no signup.
- [Open Exchange Rates](https://openexchangerates.org/signup) — app id for `/latest.json`.
- [Twelve Data](https://twelvedata.com/) — optional **price** source (separate from FX).
- [Alpha Vantage](https://www.alphavantage.co/support/#api-key) — optional **price** source.

## Known limitations

- **Shanghai / Shenzhen (`.SS` / `.SZ`)** and other suffixes are **not** in the default map; add them via **market overrides** or **currency override**, and confirm your price source supports those symbols.
- **Cross-listed instruments** (same company, multiple venues) may need **currency override** so the price row matches the venue you are quoting.
- **Rate limits**: Twelve Data free tier is **8 calls/minute** (in-app limiter). Alpha Vantage and other free tiers can throttle; use fewer finance sources or paid tiers if you hit limits.
- **Yahoo / yfinance** quality depends on Yahoo; no SLA.

For operational troubleshooting (OAuth, quotas), see the main [README – Troubleshooting](../README.md#troubleshooting).
