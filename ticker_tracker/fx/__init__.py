"""FX rate adapters and run-scoped conversion."""

from ticker_tracker.fx.base import FXAdapter, FXAdapterError, FXRate
from ticker_tracker.fx.forex_python import ForexPythonAdapter
from ticker_tracker.fx.frankfurter import FrankfurterAdapter
from ticker_tracker.fx.open_exchange_rates import (
    OpenExchangeRatesAdapter,
    clear_oxr_api_key,
    get_oxr_api_key,
    set_oxr_api_key,
)
from ticker_tracker.fx.registry import FXRunRegistry

__all__ = [
    "FXAdapter",
    "FXAdapterError",
    "FXRate",
    "FXRunRegistry",
    "ForexPythonAdapter",
    "FrankfurterAdapter",
    "OpenExchangeRatesAdapter",
    "clear_oxr_api_key",
    "get_oxr_api_key",
    "set_oxr_api_key",
]
