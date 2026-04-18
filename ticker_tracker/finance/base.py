"""Shared types and abstract finance price adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class FinanceAdapterError(RuntimeError):
    """Raised when a finance adapter cannot return prices for the requested tickers."""


@dataclass
class PriceResult:
    """Spot quote from a single finance source (before registry sub-unit correction)."""

    price: float  # price after sub-unit correction (adapters set equal to raw_price)
    currency: str  # ISO 4217 native currency code
    raw_price: float  # price as returned by the source
    source: str  # adapter name


class FinanceAdapter(ABC):
    """Abstract price lookup for one upstream source."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Short adapter identifier stored on ``PriceResult.source``."""

    @abstractmethod
    def get_prices(self, tickers: list[str]) -> dict[str, PriceResult]:
        """
        Return one ``PriceResult`` per requested ticker.

        Adapters set ``price`` equal to ``raw_price``; the registry applies
        sub-unit correction (e.g. GBX → GBP).

        Raises:
            FinanceAdapterError: Total failure (missing data, HTTP errors, etc.).
        """
