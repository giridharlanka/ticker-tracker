"""Shared FX types and abstract adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


class FXAdapterError(RuntimeError):
    """Raised when an FX adapter cannot supply the requested rate(s)."""


@dataclass
class FXRate:
    from_currency: str
    to_currency: str
    rate: float
    fetched_at: datetime
    source: str


class FXAdapter(ABC):
    """One upstream FX rate provider."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Identifier stored on ``FXRate.source``."""

    @abstractmethod
    def get_rate(self, from_currency: str, to_currency: str) -> FXRate:
        """Spot rate to multiply an amount in *from_currency* into *to_currency*."""

    @abstractmethod
    def get_rates(self, from_currency: str, to_currencies: list[str]) -> dict[str, FXRate]:
        """
        Batch rates from *from_currency* into each distinct code in *to_currencies*.

        Keys in the returned mapping are normalized ``to`` currency codes.
        """
