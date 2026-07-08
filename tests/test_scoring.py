from engine import scoring
from tests._scenario import HC_BBB_7Y, perfect_client, poor_client


def test_mandate_fit_prefers_ig_client_for_ig_bond():
    perfect = scoring.mandate_fit(perfect_client(), HC_BBB_7Y)[0]
    poor = scoring.mandate_fit(poor_client(), HC_BBB_7Y)[0]
    assert perfect > poor
    assert perfect > 0.5  # IG mandate + sector tilt should score strongly


def test_holdings_overlap_rewards_same_sector_holdings():
    perfect = scoring.holdings_overlap(perfect_client(), HC_BBB_7Y)[0]
    poor = scoring.holdings_overlap(poor_client(), HC_BBB_7Y)[0]
    assert perfect > 0
    assert poor == 0  # no healthcare holdings at all


def test_behavioural_history_rewards_natural_buyer_when_desk_sells():
    # Desk is selling -> we want a client who has BOUGHT this sector.
    perfect = scoring.behavioural_history(perfect_client(), HC_BBB_7Y, "sell")[0]
    poor = scoring.behavioural_history(poor_client(), HC_BBB_7Y, "sell")[0]
    assert perfect > 0
    assert poor == 0


def test_recency_rewards_recent_sector_activity():
    perfect = scoring.recency(perfect_client(), HC_BBB_7Y)[0]
    poor = scoring.recency(poor_client(), HC_BBB_7Y)[0]
    assert perfect > poor
