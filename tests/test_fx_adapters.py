"""Tests for FX adapters, run registry cache, and Open Exchange Rates cross-rates."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate
from ticker_tracker.fx.forex_python import ForexPythonAdapter
from ticker_tracker.fx.frankfurter import FrankfurterAdapter
from ticker_tracker.fx.open_exchange_rates import OpenExchangeRatesAdapter
from ticker_tracker.fx.registry import FXRunRegistry


def _frankfurt_json() -> bytes:
    return json.dumps(
        {
            "amount": 1.0,
            "base": "USD",
            "date": "2026-01-15",
            "rates": {"SGD": 1.35, "EUR": 0.9, "GBP": 0.8},
        }
    ).encode()


class _UrlResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _UrlResp:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_frankfurt_registry_batches_one_http_per_run(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls = {"n": 0}

    def fake_urlopen(req: object, timeout: object = None) -> _UrlResp:
        calls["n"] += 1
        return _UrlResp(_frankfurt_json())

    monkeypatch.setattr("ticker_tracker.fx.frankfurter.urllib.request.urlopen", fake_urlopen)

    reg = FXRunRegistry(FrankfurterAdapter(), "USD", {"USD", "SGD", "EUR"})
    with caplog.at_level(logging.INFO):
        assert reg.convert(100, "USD", "SGD") == pytest.approx(135.0)
        assert reg.convert(10, "EUR", "USD") == pytest.approx(10 / 0.9)
        # 1 USD = 0.9 EUR and 1 USD = 1.35 SGD ⇒ 1 EUR = 1.35/0.9 SGD
        assert reg.convert(1, "EUR", "SGD") == pytest.approx(1.35 / 0.9)
    assert calls["n"] == 1
    assert "FX rates fetched for run" in caplog.text


def test_convert_same_currency_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("should not fetch")

    monkeypatch.setattr("ticker_tracker.fx.frankfurter.urllib.request.urlopen", boom)
    reg = FXRunRegistry(FrankfurterAdapter(), "USD", {"SGD"})
    assert reg.convert(42.5, "SGD", "SGD") == 42.5


def test_oxr_free_tier_cross_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """SGD->GBP via USD base: (GBP per USD) / (SGD per USD)."""
    oxr_body = json.dumps(
        {
            "disclaimer": "x",
            "license": "y",
            "timestamp": 1700000000,
            "base": "USD",
            "rates": {"SGD": 1.36, "GBP": 0.79},
        }
    ).encode()

    monkeypatch.setattr(
        "ticker_tracker.fx.open_exchange_rates.get_oxr_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "ticker_tracker.fx.open_exchange_rates.urllib.request.urlopen",
        lambda *a, **k: _UrlResp(oxr_body),
    )

    ad = OpenExchangeRatesAdapter(usd_base_only=True)
    out = ad.get_rates("SGD", ["GBP"])
    assert out["GBP"].from_currency == "SGD"
    assert out["GBP"].to_currency == "GBP"
    expected = 0.79 / 1.36
    assert out["GBP"].rate == pytest.approx(expected)


def test_oxr_paid_tier_direct_base(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {
            "timestamp": 1700000001,
            "base": "EUR",
            "rates": {"GBP": 0.85},
        }
    ).encode()
    monkeypatch.setattr(
        "ticker_tracker.fx.open_exchange_rates.get_oxr_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "ticker_tracker.fx.open_exchange_rates.urllib.request.urlopen",
        lambda *a, **k: _UrlResp(body),
    )
    ad = OpenExchangeRatesAdapter(usd_base_only=False)
    out = ad.get_rates("EUR", ["GBP"])
    assert out["GBP"].rate == pytest.approx(0.85)


def test_convert_raises_when_rate_not_cached() -> None:
    class PartialStub(FXAdapter):
        @property
        def source(self) -> str:
            return "stub"

        def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
            raise NotImplementedError

        def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
            return {
                "SGD": FXRate(
                    "USD",
                    "SGD",
                    1.35,
                    datetime.now(UTC),
                    self.source,
                )
            }

    reg = FXRunRegistry(PartialStub(), "USD", {"USD", "SGD"})
    with pytest.raises(FXAdapterError, match="No FX rate cached"):
        reg.convert(1, "EUR", "SGD")


def test_registry_fallback_when_primary_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom(FXAdapter):
        @property
        def source(self) -> str:
            return "boom"

        def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
            raise FXAdapterError("no")

        def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
            raise FXAdapterError("no")

    class Stub(FXAdapter):
        @property
        def source(self) -> str:
            return "stub"

        def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
            raise NotImplementedError

        def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
            fc, base = from_currency, "USD"
            assert fc == base
            return {t: FXRate(base, t, 2.0, datetime.now(UTC), self.source) for t in to_currencies}

    reg = FXRunRegistry(Boom(), "USD", {"USD", "EUR"}, fallback_adapter=Stub())
    assert reg.convert(5, "USD", "EUR") == pytest.approx(10.0)


@patch.object(ForexPythonAdapter, "_client")
def test_forex_python_adapter_delegates(mock_client: MagicMock) -> None:
    cr = MagicMock()
    cr.get_rate.return_value = 1.25
    mock_client.return_value = cr
    ad = ForexPythonAdapter()
    r = ad.get_rate("USD", "EUR")
    assert r.rate == pytest.approx(1.25)
    cr.get_rate.assert_called_once()
