"""Scoring components for client<->axe matching -- the analytical core.

Given an axe (a bond the *desk* wants to move) and a client, we score fit across
five weighted dimensions and one hard eligibility gate. Every number is transparent
and defensible: this is decision support, not a black box.

What makes the model 'correct' rather than generic:

  * Direction-aware. The desk's side flips the logic. To SELL, the desk needs a
    client with *room and appetite to buy*; to SOURCE (desk buys), it needs a
    *holder who might trim*. Concentration therefore cuts both ways -- being full
    in a name helps you sell it back to the desk but hurts your ability to buy more.

  * Eligibility gate. A portfolio-ineligible bond (e.g. high-yield shown to an
    IG-only pension) is near-disqualified regardless of every other signal -- a
    real salesperson would never make that call. The gate multiplies the score.

  * Graded, not binary. Credit-quality, rating and duration fit decay smoothly with
    distance instead of matching on a coarse bucket.

Each component returns `(score, detail)` where score is 0..1 and detail is a short
human sentence that drives the "why". Weights live in `engine/match.py`.
"""

from __future__ import annotations

from statistics import median

from data import universe as U
from data.synthetic import Axe, Client, Instrument

# Duration mandate -> preferred maturity band (years).
_DURATION_BANDS = {
    "short-duration": (1, 4),
    "core-duration": (4, 9),
    "long-duration": (10, 30),
}
# 'Deep' high yield = B+ or worse (a low-risk account should not touch it).
_DEEP_HY_NOTCH = U.rating_notch("B+")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _book_stats(client: Client, instr: Instrument) -> dict:
    aum = client.aum_mm or 1.0
    sector_pos = [p for p in client.holdings if p.instrument.sector == instr.sector]
    issuer_pos = [p for p in client.holdings if p.instrument.issuer == instr.issuer]
    return {
        "aum": aum,
        "sector_pos": sector_pos,
        "issuer_pos": issuer_pos,
        "sector_share": sum(p.notional_mm for p in sector_pos) / aum,
        "issuer_share": sum(p.notional_mm for p in issuer_pos) / aum,
    }


def _target_band(client: Client) -> tuple[int, int]:
    bands = [_DURATION_BANDS[d] for d in client.duration_mandate if d in _DURATION_BANDS]
    if not bands:
        return (1, 30)
    return (min(b[0] for b in bands), max(b[1] for b in bands))


# ---------------------------------------------------------------------------
# 1. Mandate fit -- is it on-strategy? (credit quality, duration band, sector)
# ---------------------------------------------------------------------------
def mandate_fit(client: Client, instr: Instrument) -> tuple[float, str]:
    if instr.is_ig:
        if "IG-credit" in client.credit_mandate:
            credit, cnote = 1.0, "IG bond fits IG mandate"
        elif "crossover" in client.credit_mandate:
            credit, cnote = 0.80, "crossover mandate accepts IG"
        else:
            credit, cnote = 0.20, "IG bond is off-strategy for a HY mandate"
    else:
        near_line = U.rating_notch(instr.rating) <= U.rating_notch("BB-")
        if "high-yield" in client.credit_mandate:
            credit, cnote = 1.0, "HY bond fits HY mandate"
        elif "crossover" in client.credit_mandate:
            credit = 0.75 if near_line else 0.40
            cnote = "crossover mandate accepts near-line HY"
        else:
            credit, cnote = 0.05, "HY bond breaches IG-only mandate"

    lo, hi = _target_band(client)
    m = instr.maturity_years
    if lo <= m <= hi:
        dur, dnote = 1.0, ""
    else:
        gap = (lo - m) if m < lo else (m - hi)
        dur, dnote = _clamp(1 - gap / 8.0), f"{gap}y outside duration band"

    sect = 1.0 if instr.sector in client.sector_tilts else 0.0

    score = 0.55 * credit + 0.30 * dur + 0.15 * sect
    parts = [cnote]
    if sect:
        parts.append(f"favours {instr.sector}")
    if dnote and dur < 0.7:
        parts.append(dnote)
    return round(score, 3), "; ".join(parts)


# ---------------------------------------------------------------------------
# 2. Portfolio fit -- does it sit naturally in their existing book?
# ---------------------------------------------------------------------------
def portfolio_fit(client: Client, instr: Instrument) -> tuple[float, str]:
    bs = _book_stats(client, instr)
    if not bs["sector_pos"] and not bs["issuer_pos"]:
        return 0.0, f"no existing {instr.sector} exposure"

    score, notes = 0.0, []
    if bs["issuer_pos"]:
        score += 0.45
        notes.append(f"already holds {instr.issuer}")

    score += 0.30 * _clamp(bs["sector_share"] / 0.20)
    n = len(bs["sector_pos"])
    if n:
        notes.append(f"{n} {instr.sector} name(s), ~{bs['sector_share'] * 100:.0f}% of book")
        tgt = U.rating_notch(instr.rating)
        avg_notch = sum(U.rating_notch(p.instrument.rating) for p in bs["sector_pos"]) / n
        avg_mat = sum(p.instrument.maturity_years for p in bs["sector_pos"]) / n
        rating_close = _clamp(1 - abs(avg_notch - tgt) / 6.0)
        dur_close = _clamp(1 - abs(avg_mat - instr.maturity_years) / 10.0)
        score += 0.15 * rating_close + 0.10 * dur_close
        if rating_close > 0.6 and dur_close > 0.6:
            notes.append("similar rating & tenor")

    return round(_clamp(score), 3), "; ".join(notes)


# ---------------------------------------------------------------------------
# 3. Directional fit -- are they on the side the desk needs?
# ---------------------------------------------------------------------------
def directional_fit(client: Client, instr: Instrument, desk_side: str) -> tuple[float, str]:
    bs = _book_stats(client, instr)
    tilt = instr.sector in client.sector_tilts

    if desk_side == "sell":
        # Desk offers bonds -> want a natural BUYER: appetite AND room to add.
        appetite = 1.0 if tilt else 0.35
        room = 1 - _clamp(bs["sector_share"] / 0.35)
        issuer_room = 1 - _clamp(bs["issuer_share"] / 0.12)
        score = appetite * (0.6 * room + 0.4 * issuer_room)
        if bs["issuer_share"] > 0.12:
            note = f"little room — already heavy in {instr.issuer}"
        elif tilt and room > 0.3:
            note = f"natural buyer: wants {instr.sector}, has room to add"
        elif tilt:
            note = f"wants {instr.sector} but book fairly full"
        else:
            note = f"no stated {instr.sector} appetite"
        return round(_clamp(score), 3), note

    # Desk sources bonds -> want a HOLDER who might trim (can't sell what they lack).
    if not bs["sector_pos"]:
        return 0.0, f"doesn't hold {instr.sector} — can't source from them"
    holds_issuer = 1.0 if bs["issuer_pos"] else 0.0
    overweight = _clamp(bs["sector_share"] / 0.30)
    score = 0.5 * holds_issuer + 0.3 * overweight + 0.2 * (1.0 if tilt else 0.5)
    note = (f"holds {instr.issuer} — natural to lift from"
            if bs["issuer_pos"] else f"overweight {instr.sector} — possible trimmer")
    return round(_clamp(score), 3), note


# ---------------------------------------------------------------------------
# 4. Flow history -- have they traded this sector with us, on the side we need?
# ---------------------------------------------------------------------------
def flow_history(client: Client, instr: Instrument, desk_side: str) -> tuple[float, str]:
    natural = "bought" if desk_side == "sell" else "sold"
    rel = [t for t in client.trades
           if t.instrument.sector == instr.sector and t.side == natural]
    if not rel:
        verb = "buying" if natural == "bought" else "selling"
        return 0.0, f"no history {verb} {instr.sector} with the desk"
    # Recent activity counts more (1/(1+quarters_ago)); cap the contribution.
    weight = sum(1.0 / (1 + t.quarters_ago) for t in rel)
    prep = "from" if natural == "bought" else "to"
    return round(_clamp(0.6 * weight), 3), f"{natural} {instr.sector} {prep} desk {len(rel)}x recently"


# ---------------------------------------------------------------------------
# 5. Size fit -- can they absorb the ticket, given their typical trade size?
# ---------------------------------------------------------------------------
def size_fit(client: Client, axe: Axe) -> tuple[float, str]:
    tickets = [t.notional_mm for t in client.trades] or [p.notional_mm for p in client.holdings]
    typical = median(tickets) if tickets else max(1.0, client.aum_mm * 0.02)
    capacity = max(typical * 2.5, client.aum_mm * 0.06, 1.0)
    ratio = axe.notional_mm / capacity
    if ratio <= 1:
        return 1.0, f"${axe.notional_mm:.0f}mm fits their typical ticket"
    return round(_clamp(1.0 / ratio), 3), (
        f"${axe.notional_mm:.0f}mm is large vs their ~${typical:.0f}mm tickets")


# ---------------------------------------------------------------------------
# Eligibility gate -- a multiplier (0..1). Hard breaches near-disqualify.
# ---------------------------------------------------------------------------
def eligibility(client: Client, instr: Instrument) -> tuple[float, str]:
    mult, reasons = 1.0, []
    has_ig = "IG-credit" in client.credit_mandate
    has_hy = "high-yield" in client.credit_mandate
    has_xo = "crossover" in client.credit_mandate

    if not instr.is_ig and has_ig and not has_hy and not has_xo:
        mult *= 0.10
        reasons.append("HY bond ineligible for an IG-only mandate")
    if instr.is_ig and has_hy and not has_ig and not has_xo:
        mult *= 0.55
        reasons.append("IG bond off-strategy for a HY mandate")
    if client.risk_appetite == "low" and U.rating_notch(instr.rating) >= _DEEP_HY_NOTCH:
        mult *= 0.40
        reasons.append("deep-HY vs low risk appetite")
    _, hi = _target_band(client)
    if instr.maturity_years > hi + 10:
        mult *= 0.70
        reasons.append("well beyond their duration band")

    return round(mult, 3), "; ".join(reasons)
