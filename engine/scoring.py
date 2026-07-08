"""Scoring components for client<->axe matching.

Each component is a small, pure function returning `(score, detail)`:
  * score  -- a 0..1 float (higher = better fit)
  * detail -- a short human sentence explaining the score (drives the "why")

Transparency is intentional. In an interview you want to be able to justify every
number: this is decision support, not a black box. The four components are combined
with fixed weights in `engine/match.py`.
"""

from __future__ import annotations

from data import universe as U
from data.synthetic import Client, Instrument

# Instruments count as "similar" if within this many rating notches.
NEAR_RATING_NOTCHES = 2


# ---------------------------------------------------------------------------
# 1. Holdings overlap -- does the client already own this kind of risk?
# ---------------------------------------------------------------------------
def holdings_overlap(client: Client, instr: Instrument) -> tuple[float, str]:
    same_sector = [p for p in client.holdings if p.instrument.sector == instr.sector]
    if not same_sector:
        return 0.0, f"no existing {instr.sector} holdings"

    near, tgt_notch = [], U.rating_notch(instr.rating)
    for p in same_sector:
        close_rating = abs(U.rating_notch(p.instrument.rating) - tgt_notch) <= NEAR_RATING_NOTCHES
        close_dur = p.instrument.duration_bucket == instr.duration_bucket
        if close_rating or close_dur:
            near.append(p)

    # Score: 3+ closely-similar names in the sector is a strong overlap.
    score = min(1.0, 0.35 * len(same_sector) + 0.25 * len(near))
    detail = f"holds {len(same_sector)} {instr.sector} name(s)"
    if near:
        detail += f", {len(near)} at similar rating/duration"
    return round(score, 3), detail


# ---------------------------------------------------------------------------
# 2. Mandate fit -- is this instrument even in-mandate for the client?
# ---------------------------------------------------------------------------
def mandate_fit(client: Client, instr: Instrument) -> tuple[float, str]:
    reasons: list[str] = []
    score = 0.0

    # Credit-quality appetite (the strongest signal / near-filter).
    if instr.is_ig:
        if "IG-credit" in client.credit_mandate:
            score += 0.5; reasons.append("IG mandate matches IG bond")
        elif "crossover" in client.credit_mandate:
            score += 0.3; reasons.append("crossover mandate accepts IG")
        else:
            reasons.append("IG bond vs HY-only mandate (weak)")
    else:  # high yield
        if "high-yield" in client.credit_mandate:
            score += 0.5; reasons.append("HY mandate matches HY bond")
        elif "crossover" in client.credit_mandate:
            score += 0.3; reasons.append("crossover mandate accepts HY")
        else:
            reasons.append("HY bond vs IG-only mandate (out of mandate)")

    # Duration appetite.
    bucket = instr.duration_bucket
    dur_ok = (
        ("long-duration" in client.duration_mandate and bucket in ("long", "ultra-long")) or
        ("short-duration" in client.duration_mandate and bucket == "short") or
        ("core-duration" in client.duration_mandate and bucket == "medium")
    )
    if dur_ok:
        score += 0.3; reasons.append(f"{bucket} duration fits mandate")

    # Sector tilt.
    if instr.sector in client.sector_tilts:
        score += 0.2; reasons.append(f"favours {instr.sector}")

    return round(min(1.0, score), 3), "; ".join(reasons)


# ---------------------------------------------------------------------------
# 3. Behavioural history -- has the client traded this kind of thing with us,
#    and on the side we now need?
# ---------------------------------------------------------------------------
def behavioural_history(client: Client, instr: Instrument, desk_side: str) -> tuple[float, str]:
    # If the desk wants to SELL, we want a natural BUYER (client bought before).
    natural_side = "bought" if desk_side == "sell" else "sold"
    verbing = "buying" if natural_side == "bought" else "selling"
    relevant = [t for t in client.trades
                if t.instrument.sector == instr.sector and t.side == natural_side]
    if not relevant:
        return 0.0, f"no history {verbing} {instr.sector} with desk"

    # Recent activity counts more; cap the contribution.
    weight = sum(1.0 / (1 + t.quarters_ago) for t in relevant)
    score = min(1.0, 0.5 * weight)
    flow = "bought" if natural_side == "bought" else "sold"
    prep = "from" if natural_side == "bought" else "to"
    detail = f"{flow} {instr.sector} {prep} desk {len(relevant)}x recently"
    return round(score, 3), detail


# ---------------------------------------------------------------------------
# 4. Recency -- how recently has the client been active in this sector at all?
# ---------------------------------------------------------------------------
def recency(client: Client, instr: Instrument) -> tuple[float, str]:
    sector_trades = [t for t in client.trades if t.instrument.sector == instr.sector]
    if not sector_trades:
        return 0.0, f"quiet in {instr.sector}"
    most_recent = min(t.quarters_ago for t in sector_trades)
    score = max(0.0, 1.0 - most_recent / 5.0)   # 0 quarters ago -> 1.0; 5+ -> ~0
    when = "this quarter" if most_recent == 0 else f"{most_recent}q ago"
    return round(score, 3), f"last active in {instr.sector} {when}"
