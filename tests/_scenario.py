"""A hand-built, known-answer scenario.

Because we construct this world ourselves, we KNOW the right answer: the pension
is a textbook buyer of the healthcare IG bond the desk is trying to sell, and the
energy hedge fund is a textbook non-fit. The tests assert the engine agrees.
This is the payoff of synthetic data -- we control the truth.
"""

from __future__ import annotations

from data.synthetic import Axe, Client, Instrument, Position, Trade

# --- Instruments ---------------------------------------------------------------
HC_BBB_7Y = Instrument("B001", "Meridian Health", "Healthcare", "BBB", 7, 4.50)   # the axe
HC_A_10Y = Instrument("B002", "Cascade Pharma", "Healthcare", "A", 10, 4.20)      # similar
HC_BBB_5Y = Instrument("B003", "Vantage Medical", "Healthcare", "BBB", 5, 4.10)   # similar
EN_B_3Y = Instrument("B004", "Delta Petroleum", "Energy", "B", 3, 7.00)           # junk energy


def perfect_client() -> Client:
    """Pension: IG mandate, healthcare tilt, already owns similar names, buys them."""
    c = Client(
        id="C_PERF", name="Redwood Pension", type="Pension Fund", risk_appetite="low",
        credit_mandate=["IG-credit"], duration_mandate=["core-duration", "long-duration"],
        sector_tilts=["Healthcare", "Utilities"],
    )
    c.holdings = [Position(HC_A_10Y, 40.0), Position(HC_BBB_5Y, 25.0)]
    c.trades = [
        Trade(HC_A_10Y, "bought", 20.0, 0),
        Trade(HC_BBB_5Y, "bought", 15.0, 1),
    ]
    return c


def poor_client() -> Client:
    """Energy HY hedge fund: wrong credit, wrong sector, no history in healthcare."""
    c = Client(
        id="C_POOR", name="Delta Macro", type="Hedge Fund", risk_appetite="high",
        credit_mandate=["high-yield"], duration_mandate=["short-duration"],
        sector_tilts=["Energy"],
    )
    c.holdings = [Position(EN_B_3Y, 30.0)]
    c.trades = [Trade(EN_B_3Y, "bought", 10.0, 2)]
    return c


def sell_axe() -> Axe:
    """The desk wants to sell the healthcare IG bond."""
    return Axe("AX_TEST", HC_BBB_7Y, "sell", 50.0, "high")
