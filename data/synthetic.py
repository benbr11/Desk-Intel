"""Synthetic universe generator.

This manufactures a realistic-*shaped* desk world: instruments, clients (with
coherent holdings and trade histories), current desk axes, and an overnight move
per instrument. Nothing here is real data -- but every field matches the shape a
real bank feed would have, which is exactly why the engine on top is data-agnostic.

Generation is fully deterministic given SEED, so the demo, screenshots, and tests
are reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from data import universe as U

SEED = 20260708  # change to reshuffle the whole world


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Instrument:
    id: str
    issuer: str
    sector: str
    rating: str
    maturity_years: int
    coupon: float          # %, annual
    asset_class: str = "Corporate Bond"

    @property
    def is_ig(self) -> bool:
        return U.is_investment_grade(self.rating)

    @property
    def duration_bucket(self) -> str:
        return U.duration_bucket(self.maturity_years)

    def label(self) -> str:
        return f"{self.issuer} {self.coupon:.2f}% {self.maturity_years}y ({self.rating})"


@dataclass
class Position:
    instrument: Instrument
    notional_mm: float     # $mm held


@dataclass
class Trade:
    instrument: Instrument
    side: str              # "bought" or "sold" (from the client's perspective)
    notional_mm: float
    quarters_ago: int      # 0 = this quarter, 1 = last quarter, ...


@dataclass
class Client:
    id: str
    name: str
    type: str              # one of U.CLIENT_TYPES
    risk_appetite: str     # low / medium / high
    credit_mandate: list[str]      # e.g. ["IG-credit"]
    duration_mandate: list[str]    # e.g. ["long-duration"]
    sector_tilts: list[str]        # favoured sectors
    holdings: list[Position] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)

    @property
    def aum_mm(self) -> float:
        return round(sum(p.notional_mm for p in self.holdings), 1)


@dataclass
class Axe:
    id: str
    instrument: Instrument
    desk_side: str         # "sell" or "buy" -- what the DESK wants to do
    notional_mm: float
    urgency: str           # low / medium / high

    def label(self) -> str:
        return f"Desk {self.desk_side.upper()} ${self.notional_mm:.0f}mm {self.instrument.label()}"


@dataclass
class Universe:
    instruments: list[Instrument]
    clients: list[Client]
    axes: list[Axe]
    overnight_bp: dict[str, float]   # instrument.id -> overnight yield move in bp


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------
def _pick_rating(rng: random.Random, credit_pref: list[str]) -> str:
    """Pick a rating consistent with a credit appetite."""
    if "high-yield" in credit_pref and "IG-credit" not in credit_pref:
        pool = [r for r in U.RATINGS if not U.is_investment_grade(r)]
    elif "crossover" in credit_pref:
        # crossover straddles the IG/HY line: BBB+ .. BB-
        lo, hi = U.RATINGS.index("BBB+"), U.RATINGS.index("BB-")
        pool = U.RATINGS[lo:hi + 1]
    else:  # IG-credit
        pool = [r for r in U.RATINGS if U.is_investment_grade(r)]
    return rng.choice(pool)


def _pick_maturity(rng: random.Random, duration_pref: list[str]) -> int:
    if "long-duration" in duration_pref:
        return rng.randint(10, 30)
    if "short-duration" in duration_pref:
        return rng.randint(1, 4)
    return rng.randint(4, 9)  # core


def _coupon_for(rng: random.Random, rating: str, maturity: int) -> float:
    """A plausible coupon: worse credit + longer maturity -> higher coupon."""
    base = 3.0 + 0.25 * U.rating_notch(rating) + 0.04 * maturity
    return round(base + rng.uniform(-0.3, 0.3), 2)


def _make_instrument(rng: random.Random, seq: int, sector: str,
                     credit_pref: list[str], duration_pref: list[str]) -> Instrument:
    issuer = rng.choice(U.ISSUERS[sector])
    rating = _pick_rating(rng, credit_pref)
    maturity = _pick_maturity(rng, duration_pref)
    coupon = _coupon_for(rng, rating, maturity)
    return Instrument(
        id=f"B{seq:04d}",
        issuer=issuer,
        sector=sector,
        rating=rating,
        maturity_years=maturity,
        coupon=coupon,
    )


# ---------------------------------------------------------------------------
# Public generator
# ---------------------------------------------------------------------------
def generate_universe(seed: int = SEED,
                      n_clients: int = 24,
                      n_axes: int = 8) -> Universe:
    rng = random.Random(seed)
    seq = 0
    all_instruments: list[Instrument] = []
    clients: list[Client] = []

    # Build clients, each with a coherent book. Instruments are minted per client
    # (with a chance to reuse existing ones so books overlap realistically).
    used_names: dict[str, list[str]] = {t: list(U.CLIENT_NAMES[t]) for t in U.CLIENT_TYPES}

    for i in range(n_clients):
        ctype = U.CLIENT_TYPES[i % len(U.CLIENT_TYPES)]
        prof = U.CLIENT_TYPE_PROFILE[ctype]

        # name (unique per type while pool lasts, else suffixed)
        if used_names[ctype]:
            name = used_names[ctype].pop(rng.randrange(len(used_names[ctype])))
        else:
            name = f"{rng.choice(U.CLIENT_NAMES[ctype])} {i}"

        credit_mandate = list(prof["credit"])
        duration_mandate = list(prof["duration"])
        sector_tilts = rng.sample(U.SECTORS, k=rng.randint(2, 3))

        client = Client(
            id=f"C{i:03d}",
            name=name,
            type=ctype,
            risk_appetite=prof["risk"],
            credit_mandate=credit_mandate,
            duration_mandate=duration_mandate,
            sector_tilts=sector_tilts,
        )

        # Holdings: 5-9 positions, mostly in favoured sectors and consistent
        # with the client's credit/duration appetite.
        n_pos = rng.randint(5, 9)
        for _ in range(n_pos):
            sector = (rng.choice(sector_tilts)
                      if rng.random() < 0.75 else rng.choice(U.SECTORS))
            # 30% chance to reuse an existing instrument -> cross-client overlap
            if all_instruments and rng.random() < 0.30:
                candidates = [ins for ins in all_instruments if ins.sector == sector]
                inst = rng.choice(candidates) if candidates else None
            else:
                inst = None
            if inst is None:
                inst = _make_instrument(rng, seq, sector, credit_mandate, duration_mandate)
                seq += 1
                all_instruments.append(inst)
            client.holdings.append(Position(inst, round(rng.uniform(5, 60), 1)))

        # Trade history: 3-7 recent trades, biased toward buying in tilt sectors
        # (i.e. these clients are natural buyers of what they like).
        n_tr = rng.randint(3, 7)
        for _ in range(n_tr):
            if client.holdings and rng.random() < 0.6:
                inst = rng.choice(client.holdings).instrument
            else:
                sector = rng.choice(sector_tilts)
                inst = _make_instrument(rng, seq, sector, credit_mandate, duration_mandate)
                seq += 1
                all_instruments.append(inst)
            side = "bought" if rng.random() < 0.7 else "sold"
            client.trades.append(
                Trade(inst, side, round(rng.uniform(5, 40), 1), rng.randint(0, 5))
            )

        clients.append(client)

    # Current desk axes: sample instruments that actually exist in the world.
    axes: list[Axe] = []
    axe_instruments = rng.sample(all_instruments, k=min(n_axes, len(all_instruments)))
    for j, inst in enumerate(axe_instruments):
        axes.append(Axe(
            id=f"AX{j:02d}",
            instrument=inst,
            desk_side=rng.choice(["sell", "sell", "buy"]),  # desks are more often axed to sell
            notional_mm=float(rng.choice([10, 15, 20, 25, 30, 40, 50])),
            urgency=rng.choice(["low", "medium", "high"]),
        ))

    # Overnight move per instrument (in bp of yield); used by the pre-call brief.
    overnight_bp = {ins.id: round(rng.uniform(-12, 12), 1) for ins in all_instruments}

    return Universe(all_instruments, clients, axes, overnight_bp)
