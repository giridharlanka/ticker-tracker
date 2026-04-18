"""Tests for finance adapters, registry correction, and fallback."""

from __future__ import annotations

import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from ticker_tracker.finance.alphavantage_adapter import AlphaVantageAdapter
from ticker_tracker.finance.base import FinanceAdapter, FinanceAdapterError, PriceResult
from ticker_tracker.finance.finnhub_adapter import FinnhubAdapter
from ticker_tracker.finance.registry import (
    SUB_UNIT_CURRENCIES,
    apply_sub_unit_correction,
    apply_sub_unit_corrections,
    get_prices_with_fallback,
)
from ticker_tracker.finance.twelvedata_adapter import TwelveDataAdapter, _MinuteRateLimiter
from ticker_tracker.finance.yfinance_adapter import YFinanceAdapter


@pytest.mark.parametrize(
    ("currency", "expected_major", "raw", "expected_price"),
    [
        ("GBX", "GBP", 800.0, 8.0),
        ("ILA", "ILS", 500.0, 5.0),
    ],
)
def test_sub_unit_correction_to_major(
    currency: str, expected_major: str, raw: float, expected_price: float
) -> None:
    assert currency in SUB_UNIT_CURRENCIES
    r = PriceResult(price=raw, currency=currency, raw_price=raw, source="test")
    apply_sub_unit_correction(r)
    assert r.currency == expected_major
    assert r.price == expected_price
    assert r.raw_price == raw


def test_usd_passthrough_no_sub_unit_change() -> None:
    r = PriceResult(price=150.25, currency="USD", raw_price=150.25, source="yahoo")
    apply_sub_unit_correction(r)
    assert r.currency == "USD"
    assert r.price == 150.25
    assert r.raw_price == 150.25


def test_apply_sub_unit_corrections_dict() -> None:
    a = PriceResult(800.0, "GBX", 800.0, "x")
    b = PriceResult(10.0, "USD", 10.0, "x")
    out = apply_sub_unit_corrections({"a": a, "b": b})
    assert out["a"].currency == "GBP" and out["a"].price == 8.0
    assert out["b"].currency == "USD" and out["b"].price == 10.0


def test_get_prices_with_fallback_merges_partial_primary() -> None:
    class Partial(FinanceAdapter):
        @property
        def source(self) -> str:
            return "partial"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            return {tickers[0]: PriceResult(1.0, "USD", 1.0, self.source)}

    class Backup(FinanceAdapter):
        @property
        def source(self) -> str:
            return "backup"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            return {t: PriceResult(2.0, "EUR", 2.0, self.source) for t in tickers}

    out = get_prices_with_fallback([Partial(), Backup()], ["AAA", "BBB"])
    assert out["AAA"].source == "partial"
    assert out["AAA"].price == 1.0
    assert out["BBB"].source == "backup"
    assert out["BBB"].currency == "EUR"


def test_get_prices_with_fallback_uses_secondary() -> None:
    class FailingAdapter(FinanceAdapter):
        @property
        def source(self) -> str:
            return "fail"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            raise FinanceAdapterError("primary down")

    class BackupAdapter(FinanceAdapter):
        @property
        def source(self) -> str:
            return "backup"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            return {t: PriceResult(42.0, "USD", 42.0, self.source) for t in tickers}

    out = get_prices_with_fallback([FailingAdapter(), BackupAdapter()], ["QQQ"])
    assert out["QQQ"].price == 42.0
    assert out["QQQ"].currency == "USD"
    assert out["QQQ"].source == "backup"


def test_get_prices_with_fallback_all_fail() -> None:
    class Bad(FinanceAdapter):
        @property
        def source(self) -> str:
            return "bad"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            raise FinanceAdapterError("no")

    with pytest.raises(FinanceAdapterError, match="No price quotes from any configured source"):
        get_prices_with_fallback([Bad(), Bad()], ["X"])


def test_get_prices_with_fallback_empty_tickers() -> None:
    class NeverCalled(FinanceAdapter):
        @property
        def source(self) -> str:
            return "x"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            raise AssertionError("should not be called")

    assert get_prices_with_fallback([NeverCalled()], []) == {}


def test_get_prices_with_fallback_applies_gbx_correction() -> None:
    class GbxSource(FinanceAdapter):
        @property
        def source(self) -> str:
            return "mock"

        def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
            return {t: PriceResult(250.0, "GBX", 250.0, self.source) for t in tickers}

    out = get_prices_with_fallback([GbxSource()], ["HSBA.L"])
    assert out["HSBA.L"].raw_price == 250.0
    assert out["HSBA.L"].currency == "GBP"
    assert out["HSBA.L"].price == 2.5


@patch("ticker_tracker.finance.yfinance_adapter._fast_info_dict")
@patch("ticker_tracker.finance.yfinance_adapter.yf.download")
def test_yfinance_adapter_batch_close_and_currency(
    mock_download: MagicMock, mock_fast_info: MagicMock
) -> None:
    idx = pd.date_range("2026-04-10", periods=2, freq="D")
    cols = pd.MultiIndex.from_tuples(
        [("Close", "AAPL"), ("Close", "MSFT")],
        names=["Price", "Ticker"],
    )
    df = pd.DataFrame(
        [[100.0, 200.0], [110.0, 210.0]],
        index=idx,
        columns=cols,
    )
    mock_download.return_value = df
    mock_fast_info.side_effect = [
        {"currency": "USD", "lastPrice": 999.0},
        {"currency": "USD", "lastPrice": 888.0},
    ]

    ad = YFinanceAdapter()
    out = ad.get_prices(["AAPL", "MSFT"])
    assert out["AAPL"].raw_price == 110.0
    assert out["MSFT"].raw_price == 210.0
    assert out["AAPL"].currency == "USD"
    mock_download.assert_called_once()


@patch("ticker_tracker.finance.yfinance_adapter._fast_info_dict")
@patch("ticker_tracker.finance.yfinance_adapter.yf.download")
def test_yfinance_adapter_falls_back_price_when_download_empty(
    mock_download: MagicMock, mock_fast_info: MagicMock
) -> None:
    mock_download.return_value = pd.DataFrame()
    mock_fast_info.return_value = {"currency": "EUR", "lastPrice": 55.5}

    ad = YFinanceAdapter()
    out = ad.get_prices(["SAP.DE"])
    assert out["SAP.DE"].raw_price == 55.5
    assert out["SAP.DE"].currency == "EUR"


@patch("ticker_tracker.finance.yfinance_adapter._fast_info_dict")
@patch("ticker_tracker.finance.yfinance_adapter.yf.download")
def test_yfinance_adapter_partial_failure_returns_available_quotes(
    mock_download: MagicMock, mock_fast_info: MagicMock
) -> None:
    mock_download.return_value = pd.DataFrame()
    mock_fast_info.side_effect = [
        {"currency": "USD", "lastPrice": 101.0},
        Exception("not found"),
    ]
    ad = YFinanceAdapter()
    out = ad.get_prices(["AZN", "KLG"])
    assert "AZN" in out
    assert "KLG" not in out


@patch("ticker_tracker.finance.yfinance_adapter._fast_info_dict")
@patch("ticker_tracker.finance.yfinance_adapter.yf.download")
def test_yfinance_adapter_raises_when_all_quotes_invalid(
    mock_download: MagicMock, mock_fast_info: MagicMock
) -> None:
    mock_download.return_value = pd.DataFrame()
    mock_fast_info.side_effect = [Exception("x"), Exception("y")]
    ad = YFinanceAdapter()
    with pytest.raises(FinanceAdapterError, match="No valid yfinance quotes"):
        ad.get_prices(["BAD1", "BAD2"])


def test_alpha_vantage_skips_failed_symbol_in_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ticker_tracker.finance.alphavantage_adapter.get_finance_api_key",
        lambda _src: "dummy-key",
    )
    adapter = AlphaVantageAdapter()

    def fake_request(params: dict[str, str]) -> dict:
        fn = params["function"]
        sym = params.get("symbol", "")
        if fn == "GLOBAL_QUOTE":
            if sym == "BAD":
                return {"Global Quote": {}}
            return {"Global Quote": {"05. price": "10.00"}}
        if fn == "SYMBOL_SEARCH":
            return {"bestMatches": [{"1. symbol": sym.upper(), "8. currency": "USD"}]}
        raise AssertionError(fn)

    monkeypatch.setattr(adapter, "_request_json", fake_request)
    out = adapter.get_prices(["GOOD", "BAD"])
    assert "GOOD" in out and out["GOOD"].raw_price == 10.0
    assert "BAD" not in out


def test_alpha_vantage_symbol_search_currency_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ticker_tracker.finance.alphavantage_adapter.get_finance_api_key",
        lambda _src: "dummy-key",
    )
    adapter = AlphaVantageAdapter()
    calls_by_fn: dict[str, int] = {}

    def fake_request(params: dict[str, str]) -> dict:
        fn = params["function"]
        calls_by_fn[fn] = calls_by_fn.get(fn, 0) + 1
        if fn == "GLOBAL_QUOTE":
            return {"Global Quote": {"05. price": "12.34"}}
        if fn == "SYMBOL_SEARCH":
            return {"bestMatches": [{"1. symbol": "IBM", "8. currency": "USD"}]}
        raise AssertionError(fn)

    monkeypatch.setattr(adapter, "_request_json", fake_request)
    adapter.get_prices(["IBM"])
    adapter.get_prices(["IBM"])
    assert calls_by_fn.get("SYMBOL_SEARCH") == 1
    assert calls_by_fn.get("GLOBAL_QUOTE") == 2


@patch("ticker_tracker.finance.twelvedata_adapter.urllib.request.urlopen")
def test_twelvedata_adapter_quote(mock_urlopen: MagicMock) -> None:
    import json

    body = {
        "symbol": "AAPL",
        "close": "150.00",
        "currency": "USD",
    }

    class _Resp:
        def read(self) -> bytes:
            return json.dumps(body).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    mock_urlopen.return_value = _Resp()

    with patch(
        "ticker_tracker.finance.twelvedata_adapter.get_twelvedata_api_key",
        return_value="k",
    ):
        ad = TwelveDataAdapter()
        out = ad.get_prices(["AAPL"])
    assert out["AAPL"].raw_price == 150.0
    assert out["AAPL"].currency == "USD"
    assert out["AAPL"].source == "twelve_data"


@patch("ticker_tracker.finance.finnhub_adapter.urllib.request.urlopen")
def test_finnhub_adapter_quote_and_profile(mock_urlopen: MagicMock) -> None:
    import json

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    mock_urlopen.side_effect = [
        _Resp({"c": 10.5, "pc": 10.0}),
        _Resp({"currency": "USD"}),
    ]

    with patch(
        "ticker_tracker.finance.finnhub_adapter.get_finance_api_key",
        return_value="test-token-12345678",
    ):
        ad = FinnhubAdapter()
        out = ad.get_prices(["IBM"])
    assert out["IBM"].raw_price == 10.5
    assert out["IBM"].currency == "USD"
    assert out["IBM"].source == "finnhub"
    assert mock_urlopen.call_count == 2


@patch("ticker_tracker.finance.finnhub_adapter.urllib.request.urlopen")
def test_finnhub_quote_uses_open_when_current_and_prior_close_zero(mock_urlopen: MagicMock) -> None:
    import json

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    mock_urlopen.side_effect = [
        _Resp({"c": 0, "pc": 0, "o": 50.0, "h": 51.0, "l": 49.0}),
        _Resp({"currency": "USD"}),
    ]
    with patch(
        "ticker_tracker.finance.finnhub_adapter.get_finance_api_key",
        return_value="test-token-12345678",
    ):
        ad = FinnhubAdapter()
        out = ad.get_prices(["X"])
    assert out["X"].raw_price == 50.0


@patch("ticker_tracker.finance.finnhub_adapter.urllib.request.urlopen")
def test_finnhub_keeps_quote_when_profile_http_fails(mock_urlopen: MagicMock) -> None:
    import json

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    def _side_effect(*args: object, **kwargs: object) -> object:
        req = args[0]
        assert isinstance(req, urllib.request.Request)
        if "/quote" in req.full_url:
            return _Resp({"c": 2.0, "pc": 1.0})
        err = urllib.error.HTTPError(req.full_url, 500, "Internal Error", {}, BytesIO(b"{}"))
        raise err

    mock_urlopen.side_effect = _side_effect
    with patch(
        "ticker_tracker.finance.finnhub_adapter.get_finance_api_key",
        return_value="test-token-12345678",
    ):
        ad = FinnhubAdapter()
        out = ad.get_prices(["IBM"])
    assert out["IBM"].raw_price == 2.0
    assert out["IBM"].currency == "USD"


@patch("ticker_tracker.finance.finnhub_adapter.urllib.request.urlopen")
def test_finnhub_retries_on_429_then_succeeds(mock_urlopen: MagicMock) -> None:
    import json

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return json.dumps(self._payload).encode()

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *a: object) -> bool:
            return False

    err429 = urllib.error.HTTPError(
        "https://api.finnhub.io/api/v1/quote?x=1",
        429,
        "Too Many",
        {},
        BytesIO(b"{}"),
    )
    # Quote: three 429s on api.finnhub.io, then success on finnhub.io; profile: OK on api first try.
    mock_urlopen.side_effect = [
        err429,
        err429,
        err429,
        _Resp({"c": 3.0, "pc": 2.0}),
        _Resp({"currency": "EUR"}),
    ]
    with patch(
        "ticker_tracker.finance.finnhub_adapter.get_finance_api_key",
        return_value="test-token-12345678",
    ):
        ad = FinnhubAdapter()
        out = ad.get_prices(["IBM"])
    assert out["IBM"].raw_price == 3.0
    assert out["IBM"].currency == "EUR"
    assert mock_urlopen.call_count == 5


def test_minute_rate_limiter_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "ticker_tracker.finance.twelvedata_adapter.time.sleep",
        lambda s: sleeps.append(float(s)),
    )
    # Two monotonic() calls per acquire without throttle; 9th acquire hits the window cap.
    seq = [0.0] * 16 + [0.0, 60.1, 60.1]
    it = iter(seq)

    def mono() -> float:
        return next(it)

    monkeypatch.setattr("ticker_tracker.finance.twelvedata_adapter.time.monotonic", mono)

    lim = _MinuteRateLimiter(8, 60.0)
    for _ in range(8):
        lim.acquire()
    lim.acquire()
    assert sleeps, "expected a throttle sleep on the 9th call"
