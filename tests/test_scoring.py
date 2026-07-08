"""Known-answer tests for the scoring components.

We construct the world ourselves, so we KNOW the right answer: the IG pension is a
textbook fit for the healthcare IG bond; the energy HY hedge fund is a textbook
non-fit. The tests assert the engine agrees — the payoff of synthetic data.
"""

from engine import scoring
from tests._scenario import EN_B_3Y, HC_BBB_7Y, perfect_client, poor_client, sell_axe


def test_mandate_fit_prefers_ig_client_for_ig_bond():
    perfect = scoring.mandate_fit(perfect_client(), HC_BBB_7Y)[0]
    poor = scoring.mandate_fit(poor_client(), HC_BBB_7Y)[0]
    assert perfect > poor
    assert perfect > 0.5          # IG mandate + in-band duration + sector tilt


def test_portfolio_fit_rewards_existing_sector_book():
    assert scoring.portfolio_fit(perfect_client(), HC_BBB_7Y)[0] > 0
    assert scoring.portfolio_fit(poor_client(), HC_BBB_7Y)[0] == 0   # no healthcare at all


def test_flow_history_rewards_natural_buyer_when_desk_sells():
    # Desk sells -> we want a client who has BOUGHT this sector from us.
    assert scoring.flow_history(perfect_client(), HC_BBB_7Y, "sell")[0] > 0
    assert scoring.flow_history(poor_client(), HC_BBB_7Y, "sell")[0] == 0


def test_directional_fit_can_only_source_from_a_holder():
    # Desk BUYS energy junk -> only a client who HOLDS it can be a source.
    assert scoring.directional_fit(poor_client(), EN_B_3Y, "buy")[0] > 0     # holds it
    assert scoring.directional_fit(perfect_client(), EN_B_3Y, "buy")[0] == 0  # holds no energy


def test_eligibility_gate_blocks_hy_bond_for_ig_only_mandate():
    blocked = scoring.eligibility(perfect_client(), EN_B_3Y)[0]   # IG-only pension, junk bond
    ok = scoring.eligibility(perfect_client(), HC_BBB_7Y)[0]      # IG bond, IG mandate
    assert blocked <= 0.15        # near-disqualified
    assert ok == 1.0


def test_size_fit_penalises_oversized_ticket():
    score = scoring.size_fit(poor_client(), sell_axe())[0]   # $50mm vs a small book
    assert 0 < score < 1
