"""Quick terminal view of the engine -- no UI needed.

Usage:
    python cli.py            # show top matches for the first axe + a sample brief
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from data.providers import SyntheticProvider
from engine.brief import BriefBuilder
from engine.match import MatchEngine


def main() -> None:
    provider = SyntheticProvider()
    matcher = MatchEngine(provider)

    axe = provider.get_axes()[0]
    print("=" * 78)
    print(f"AXE: {axe.label()}   urgency={axe.urgency}")
    print("=" * 78)
    print(f"{'#':>2}  {'Client':<26} {'Type':<15} {'Score':>6}   Why")
    print("-" * 78)
    for i, m in enumerate(matcher.rank_clients_for(axe, top_n=8), 1):
        print(f"{i:>2}. {m.client.name:<26} {m.client.type:<15} {m.score:>6.1f}   {m.explanation}")

    top = matcher.rank_clients_for(axe, top_n=1)[0]
    print("\nDraft pitch to top match:")
    print(f"  {top.pitch}\n")

    # Sample pre-call brief.
    client = top.client
    brief = BriefBuilder(provider).build_brief(client)
    print("=" * 78)
    print(f"PRE-CALL BRIEF: {client.name}  ({client.type}, {client.risk_appetite} risk)")
    print(f"  Mandate: {', '.join(client.credit_mandate + client.duration_mandate)}")
    print(f"  Tilts:   {', '.join(client.sector_tilts)}")
    print("=" * 78)
    print(f"  AUM (book): ${client.aum_mm:.0f}mm | Overnight P&L: ${brief.overnight_pnl_mm:+.2f}mm")
    print("  Sector breakdown:")
    for sector, mm in sorted(brief.sector_breakdown.items(), key=lambda kv: -kv[1]):
        print(f"    {sector:<14} ${mm:>7.1f}mm")
    print("  Talking points:")
    for tp in brief.talking_points:
        print(f"    - {tp}")
    print("  Relevant live axes:")
    for a in brief.relevant_axes:
        print(f"    - [{a.score:>5.1f}] {a.axe_label}")


if __name__ == "__main__":
    main()
