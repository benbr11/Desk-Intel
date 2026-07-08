"""Pre-call brief builder: everything a salesperson should know before dialling.

Given a client, assemble a one-pager:
  * profile (type, appetite, mandates)
  * holdings summary (size, sector breakdown, top positions)
  * recent trades with the desk
  * overnight P&L moves across their book (so you can open with relevant colour)
  * which of the desk's *current* axes are most relevant to this client
"""

from __future__ import annotations

from dataclasses import dataclass, field

from data.providers import DeskDataProvider
from data.synthetic import Client, Position, Trade
from engine.match import MatchEngine

# Rough modified-duration proxy: a T-year bond moves ~ (T * factor)% per 1% yield.
_DUR_FACTOR = 0.85
# Only surface current axes where this client scores at least this well.
RELEVANT_AXE_THRESHOLD = 40.0


@dataclass
class PositionMove:
    position: Position
    bp_move: float          # overnight yield move (bp)
    pnl_mm: float           # estimated overnight P&L ($mm)


@dataclass
class RelevantAxe:
    axe_label: str
    desk_side: str
    score: float
    reason: str


@dataclass
class Brief:
    client: Client
    sector_breakdown: dict[str, float]      # sector -> $mm
    top_positions: list[Position]
    recent_trades: list[Trade]
    position_moves: list[PositionMove]      # sorted by |pnl|, biggest first
    overnight_pnl_mm: float
    relevant_axes: list[RelevantAxe]

    @property
    def talking_points(self) -> list[str]:
        pts: list[str] = []
        if self.position_moves:
            top = self.position_moves[0]
            direction = "gained" if top.pnl_mm >= 0 else "lost"
            pts.append(
                f"Their {top.position.instrument.issuer} position {direction} "
                f"~${abs(top.pnl_mm):.2f}mm overnight ({top.bp_move:+.1f}bp)."
            )
        if self.relevant_axes:
            a = self.relevant_axes[0]
            pts.append(f"Live axe fit: {a.axe_label} (score {a.score:.0f}).")
        biggest_sector = max(self.sector_breakdown, key=self.sector_breakdown.get, default=None)
        if biggest_sector:
            pts.append(f"Biggest exposure is {biggest_sector} "
                       f"(${self.sector_breakdown[biggest_sector]:.0f}mm).")
        return pts


class BriefBuilder:
    def __init__(self, provider: DeskDataProvider):
        self.provider = provider
        self._matcher = MatchEngine(provider)

    def _overnight_moves(self, client: Client) -> tuple[list[PositionMove], float]:
        moves: list[PositionMove] = []
        for pos in client.holdings:
            bp = self.provider.overnight_move_bp(pos.instrument.id)
            mod_dur = pos.instrument.maturity_years * _DUR_FACTOR
            # price change ~= -mod_dur * (Δyield in %) ; Δyield% = bp/100
            pnl = pos.notional_mm * (-mod_dur * (bp / 100.0) / 100.0)
            moves.append(PositionMove(pos, bp, round(pnl, 3)))
        moves.sort(key=lambda m: abs(m.pnl_mm), reverse=True)
        total = round(sum(m.pnl_mm for m in moves), 3)
        return moves, total

    def _relevant_axes(self, client: Client) -> list[RelevantAxe]:
        out: list[RelevantAxe] = []
        for axe in self.provider.get_axes():
            m = self._matcher.score_client(client, axe)
            if m.score >= RELEVANT_AXE_THRESHOLD:
                out.append(RelevantAxe(axe.label(), axe.desk_side, m.score, m.explanation))
        out.sort(key=lambda r: r.score, reverse=True)
        return out

    def build_brief(self, client: Client) -> Brief:
        sector_breakdown: dict[str, float] = {}
        for p in client.holdings:
            sector_breakdown[p.instrument.sector] = round(
                sector_breakdown.get(p.instrument.sector, 0.0) + p.notional_mm, 1)

        top_positions = sorted(client.holdings, key=lambda p: p.notional_mm, reverse=True)[:5]
        recent_trades = sorted(client.trades, key=lambda t: t.quarters_ago)[:6]
        moves, total = self._overnight_moves(client)

        return Brief(
            client=client,
            sector_breakdown=sector_breakdown,
            top_positions=top_positions,
            recent_trades=recent_trades,
            position_moves=moves,
            overnight_pnl_mm=total,
            relevant_axes=self._relevant_axes(client),
        )
