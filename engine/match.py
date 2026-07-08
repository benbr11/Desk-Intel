"""Match engine: given an axe, rank which clients to call.

Combines the four scoring components into a single 0-100 match score, builds a
plain-English explanation of *why* each client ranked, and drafts a first-pass
outreach line the salesperson can edit and send.
"""

from __future__ import annotations

from dataclasses import dataclass

from data.providers import ClientProvider
from data.synthetic import Axe, Client
from engine import scoring

# Weights for the four components. They sum to 1.0.
WEIGHTS = {
    "mandate": 0.35,     # is it even in-mandate?  (strongest signal)
    "holdings": 0.30,    # do they already own this kind of risk?
    "history": 0.25,     # have they traded it with us, on the side we need?
    "recency": 0.10,     # are they active right now?
}


@dataclass
class ClientMatch:
    client: Client
    score: float                       # 0-100
    components: dict[str, tuple[float, str]]   # name -> (raw 0..1 score, detail)
    explanation: str
    pitch: str


def _explain(components: dict[str, tuple[float, str]]) -> str:
    """Join the details of the highest-contributing components into one sentence."""
    ranked = sorted(
        components.items(),
        key=lambda kv: kv[1][0] * WEIGHTS[kv[0]],
        reverse=True,
    )
    parts = [detail for name, (raw, detail) in ranked if raw > 0][:3]
    return "; ".join(parts) if parts else "no strong signal — low priority"


def _draft_pitch(client: Client, axe: Axe, lead_reason: str) -> str:
    who = client.name.split()[0]
    inst = axe.instrument
    if axe.desk_side == "sell":
        return (f"Hi {who} - showing ${axe.notional_mm:.0f}mm of {inst.issuer} "
                f"{inst.coupon:.2f}% {inst.maturity_years}y ({inst.rating}) at [level]. "
                f"Thought of you first: {lead_reason.lower()}. Size is live now.")
    else:  # desk wants to buy -> approach natural holders/sellers
        return (f"Hi {who} - we're strong buyers of {inst.sector} {inst.rating} paper and "
                f"can take up to ${axe.notional_mm:.0f}mm of {inst.issuer} "
                f"{inst.coupon:.2f}% {inst.maturity_years}y. "
                f"Given {lead_reason.lower()}, wanted to check if you're looking to lighten up.")


class MatchEngine:
    def __init__(self, provider: ClientProvider):
        self.provider = provider

    def score_client(self, client: Client, axe: Axe) -> ClientMatch:
        instr = axe.instrument
        components = {
            "mandate": scoring.mandate_fit(client, instr),
            "holdings": scoring.holdings_overlap(client, instr),
            "history": scoring.behavioural_history(client, instr, axe.desk_side),
            "recency": scoring.recency(client, instr),
        }
        total = sum(WEIGHTS[name] * raw for name, (raw, _) in components.items())
        score = round(100 * total, 1)
        explanation = _explain(components)
        lead_reason = explanation.split(";")[0].strip()
        pitch = _draft_pitch(client, axe, lead_reason)
        return ClientMatch(client, score, components, explanation, pitch)

    def rank_clients_for(self, axe: Axe, top_n: int | None = None) -> list[ClientMatch]:
        matches = [self.score_client(c, axe) for c in self.provider.get_clients()]
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_n] if top_n else matches
