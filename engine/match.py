"""Match engine: given an axe, rank which clients to call.

Combines five weighted fit factors into a base score, then applies a hard
eligibility gate (a multiplier) so portfolio-ineligible bonds never rank high:

    score = 100 * Σ(weightᵢ · factorᵢ) * eligibility

It also builds a plain-English "why", flags any eligibility limitation, and drafts
a first-pass outreach line the salesperson can edit and send.
"""

from __future__ import annotations

from dataclasses import dataclass

from data.providers import ClientProvider
from data.synthetic import Axe, Client
from engine import scoring

# Weights for the five fit factors. They sum to 1.0.
WEIGHTS = {
    "mandate": 0.24,     # is it eligible and on-strategy?
    "portfolio": 0.24,   # does it sit naturally in their book?
    "direction": 0.22,   # are they on the side the desk needs?
    "flow": 0.18,        # have they traded it with us, on that side?
    "size": 0.12,        # can they absorb the ticket?
}


@dataclass
class ClientMatch:
    client: Client
    score: float                              # 0-100 (after eligibility gate)
    components: dict[str, tuple[float, str]]  # factor -> (raw 0..1, detail)
    eligibility: tuple[float, str]            # (multiplier 0..1, reason if <1)
    explanation: str
    pitch: str


def _explain(components: dict[str, tuple[float, str]],
             eligibility: tuple[float, str]) -> str:
    """Top few contributing factors, plus an eligibility caveat if one applies."""
    ranked = sorted(components.items(),
                    key=lambda kv: kv[1][0] * WEIGHTS[kv[0]], reverse=True)
    parts = [detail for _, (raw, detail) in ranked if raw > 0 and detail][:3]
    mult, note = eligibility
    if mult < 0.85 and note:
        parts.append(f"⚠ {note}")
    return "; ".join(parts) if parts else "no strong signal — low priority"


def _draft_pitch(client: Client, axe: Axe, lead_reason: str) -> str:
    who = client.name.split()[0]
    inst = axe.instrument
    if axe.desk_side == "sell":
        return (f"Hi {who} - showing ${axe.notional_mm:.0f}mm of {inst.issuer} "
                f"{inst.coupon:.2f}% {inst.maturity_years}y ({inst.rating}) at [level]. "
                f"Thought of you first: {lead_reason.lower()}. Size is live now.")
    return (f"Hi {who} - we're strong buyers of {inst.sector} {inst.rating} paper and "
            f"can take up to ${axe.notional_mm:.0f}mm of {inst.issuer} "
            f"{inst.coupon:.2f}% {inst.maturity_years}y. "
            f"Given {lead_reason.lower()}, wanted to see if you're looking to lighten up.")


class MatchEngine:
    def __init__(self, provider: ClientProvider):
        self.provider = provider

    def score_client(self, client: Client, axe: Axe) -> ClientMatch:
        instr = axe.instrument
        components = {
            "mandate": scoring.mandate_fit(client, instr),
            "portfolio": scoring.portfolio_fit(client, instr),
            "direction": scoring.directional_fit(client, instr, axe.desk_side),
            "flow": scoring.flow_history(client, instr, axe.desk_side),
            "size": scoring.size_fit(client, axe),
        }
        elig = scoring.eligibility(client, instr)
        base = sum(WEIGHTS[name] * raw for name, (raw, _) in components.items())
        score = round(100 * base * elig[0], 1)
        explanation = _explain(components, elig)
        lead_reason = explanation.split(";")[0].strip().lstrip("⚠ ").strip()
        pitch = _draft_pitch(client, axe, lead_reason)
        return ClientMatch(client, score, components, elig, explanation, pitch)

    def rank_clients_for(self, axe: Axe, top_n: int | None = None) -> list[ClientMatch]:
        matches = [self.score_client(c, axe) for c in self.provider.get_clients()]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_n] if top_n else matches
