"""Yahoo Finance prices via yfinance (batch download + per-ticker metadata)."""

from __future__ import annotations

import contextlib
import logging
import warnings
from collections.abc import Iterator
from typing import Any

import pandas as pd
import yfinance as yf

from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_yfinance_pandas_utcnoise() -> Iterator[None]:
    """
    yfinance still calls pandas ``Timestamp.utcnow()`` internally; recent pandas
    emits a deprecation warning on every call, so one portfolio run can print
    hundreds of identical lines. Filter those only for our Yahoo fetch scope.
    """
    with warnings.catch_warnings():
        for _cat in (FutureWarning, DeprecationWarning):
            warnings.filterwarnings("ignore", message=".*utcnow.*", category=_cat)
        p4 = getattr(pd.errors, "Pandas4Warning", None)
        if p4 is not None:
            warnings.filterwarnings("ignore", message=".*utcnow.*", category=p4)
        yield


def _fast_info_dict(ticker: str) -> dict[str, Any]:
    return dict(yf.Ticker(ticker).fast_info)


def _fi_last_price(fi: dict[str, Any]) -> float | None:
    v = fi.get("lastPrice", fi.get("last_price"))
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fi_currency(fi: dict[str, Any]) -> str | None:
    c = fi.get("currency")
    if not c:
        return None
    return str(c).strip().upper()


def _latest_close_from_download(df: pd.DataFrame, ticker: str) -> float | None:
    if df is None or df.empty:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            ser = df["Close"][ticker].dropna()
        else:
            ser = df["Close"].dropna()
        if ser.empty:
            return None
        return float(ser.iloc[-1])
    except (KeyError, TypeError, ValueError):
        return None


class YFinanceAdapter(FinanceAdapter):
    """Prices from Yahoo Finance; ``source`` is ``\"yahoo\"`` to match config."""

    @property
    def source(self) -> str:
        return "yahoo"

    def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
        if not tickers:
            return {}

        ordered: list[str] = []
        for raw in tickers:
            t = raw.strip()
            if not t:
                raise FinanceAdapterError("Empty ticker in request.")
            if t not in ordered:
                ordered.append(t)

        with _suppress_yfinance_pandas_utcnoise():
            df: pd.DataFrame | None = None
            try:
                # threads=False avoids duplicate parallel yfinance work (and stderr spam).
                df = yf.download(
                    tickers=ordered,
                    period="10d",
                    interval="1d",
                    progress=False,
                    threads=False,
                    auto_adjust=False,
                )
            except Exception:
                logger.exception("yfinance.download failed; using per-ticker prices only")
                df = None

            out: dict[str, PriceResult] = {}
            for t in ordered:
                close = _latest_close_from_download(df, t) if df is not None else None
                try:
                    fi = _fast_info_dict(t)
                except Exception as exc:
                    logger.info("yfinance skipped %r (no usable metadata/quote): %s", t, exc)
                    continue
                currency = _fi_currency(fi)
                raw_price = close if close is not None else _fi_last_price(fi)
                if raw_price is None or not currency:
                    logger.info("Incomplete yfinance quote for %r", t)
                    continue
                rp = float(raw_price)
                out[t] = PriceResult(price=rp, currency=currency, raw_price=rp, source=self.source)

            if not out:
                raise FinanceAdapterError("No valid yfinance quotes for requested tickers.")
            return out
