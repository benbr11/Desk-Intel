"""Data provider interfaces -- the seam between the engine and the data source.

The engine and UI depend ONLY on these abstract interfaces, never on where the
data comes from. Today the data comes from `SyntheticProvider` (a manufactured
world). To go live at a bank, you write e.g. `CitiProvider(DeskDataProvider)`
that reads real feeds and returns the same objects -- and nothing else changes.

That is the whole architectural point: no proprietary data is needed to build,
test, or demo the product.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from data.synthetic import Axe, Client, Instrument, Universe, generate_universe


class ClientProvider(ABC):
    @abstractmethod
    def get_clients(self) -> list[Client]: ...

    def get_client(self, client_id: str) -> Client | None:
        return next((c for c in self.get_clients() if c.id == client_id), None)


class AxeProvider(ABC):
    @abstractmethod
    def get_axes(self) -> list[Axe]: ...

    def get_axe(self, axe_id: str) -> Axe | None:
        return next((a for a in self.get_axes() if a.id == axe_id), None)


class MarketProvider(ABC):
    @abstractmethod
    def overnight_move_bp(self, instrument_id: str) -> float:
        """Overnight change in yield (bp) for an instrument. +ve = yields up."""
        ...


class DeskDataProvider(ClientProvider, AxeProvider, MarketProvider, ABC):
    """The full interface the engine/UI wire against."""
    @abstractmethod
    def get_instruments(self) -> list[Instrument]: ...


# ---------------------------------------------------------------------------
# The default provider used today: a manufactured world.
# ---------------------------------------------------------------------------
class SyntheticProvider(DeskDataProvider):
    def __init__(self, universe: Universe | None = None, **gen_kwargs):
        self._u = universe or generate_universe(**gen_kwargs)

    @property
    def universe(self) -> Universe:
        return self._u

    def get_clients(self) -> list[Client]:
        return self._u.clients

    def get_axes(self) -> list[Axe]:
        return self._u.axes

    def get_instruments(self) -> list[Instrument]:
        return self._u.instruments

    def overnight_move_bp(self, instrument_id: str) -> float:
        return self._u.overnight_bp.get(instrument_id, 0.0)


# ---------------------------------------------------------------------------
# A tiny hand-fed provider, handy for tests and one-off scenarios.
# ---------------------------------------------------------------------------
class InMemoryProvider(DeskDataProvider):
    def __init__(self, clients=None, axes=None, instruments=None, overnight_bp=None):
        self._clients = clients or []
        self._axes = axes or []
        self._instruments = instruments or []
        self._overnight = overnight_bp or {}

    def get_clients(self) -> list[Client]:
        return self._clients

    def get_axes(self) -> list[Axe]:
        return self._axes

    def get_instruments(self) -> list[Instrument]:
        return self._instruments

    def overnight_move_bp(self, instrument_id: str) -> float:
        return self._overnight.get(instrument_id, 0.0)
