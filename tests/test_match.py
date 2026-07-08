from data.providers import InMemoryProvider
from engine.match import MatchEngine
from tests._scenario import perfect_client, poor_client, sell_axe


def _engine():
    # Deliberately list the poor client FIRST so ordering can't pass by accident.
    provider = InMemoryProvider(clients=[poor_client(), perfect_client()])
    return MatchEngine(provider), sell_axe()


def test_perfect_fit_outranks_poor_fit():
    engine, axe = _engine()
    ranked = engine.rank_clients_for(axe)
    assert ranked[0].client.id == "C_PERF"
    assert ranked[-1].client.id == "C_POOR"
    assert ranked[0].score > ranked[-1].score


def test_perfect_fit_scores_highly():
    engine, axe = _engine()
    top = engine.rank_clients_for(axe, top_n=1)[0]
    assert top.score >= 50.0


def test_match_produces_explanation_and_pitch():
    engine, axe = _engine()
    top = engine.rank_clients_for(axe, top_n=1)[0]
    assert top.explanation and "no strong signal" not in top.explanation
    assert "Redwood" in top.pitch                 # addressed to the client
    assert "Meridian Health" in top.pitch         # names the actual bond
