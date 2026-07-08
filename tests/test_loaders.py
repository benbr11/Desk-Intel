"""Tests for the real-data loaders (CSV / SQLite / row-builder).

These prove the "plug real data in" seam works: data loaded from an external
source rebuilds the same object universe the engine already knows how to score.
"""

from data.loaders import (SqlProvider, build_sqlite, load_csv, load_sqlite,
                          universe_from_rows, write_csvs)
from data.synthetic import generate_universe
from engine.match import MatchEngine


def test_universe_from_rows_parses_lists_refs_and_types():
    u = universe_from_rows(
        instruments=[dict(id="B1", issuer="Acme", sector="Technology", rating="BBB",
                          maturity_years="7", coupon="4.5")],
        clients=[dict(id="C1", name="Fund A", type="Asset Manager", risk_appetite="Medium",
                      credit_mandate="IG-credit|crossover", duration_mandate="core-duration",
                      sector_tilts="Technology;Healthcare")],
        holdings=[dict(client_id="C1", instrument_id="B1", notional_mm="10")],
        trades=[dict(client_id="C1", instrument_id="B1", side="Bought", notional_mm="5",
                     quarters_ago="1")],
        axes=[dict(id="AX1", instrument_id="B1", desk_side="Sell", notional_mm="20", urgency="high")],
        overnight=[dict(instrument_id="B1", bp="3.5")])
    assert (len(u.clients), len(u.axes), len(u.instruments)) == (1, 1, 1)
    c = u.clients[0]
    assert c.credit_mandate == ["IG-credit", "crossover"]      # pipe-split
    assert c.sector_tilts == ["Technology", "Healthcare"]      # semicolon-split
    assert c.risk_appetite == "medium"                         # lower-cased
    assert len(c.holdings) == 1 and c.trades[0].side == "bought"
    assert u.axes[0].desk_side == "sell"
    assert u.overnight_bp["B1"] == 3.5


def test_csv_round_trip_preserves_universe(tmp_path):
    u = generate_universe()
    d = tmp_path / "csv"
    write_csvs(str(d), u)
    src = {k: str(d / f"{k}.csv")
           for k in ["instruments", "clients", "holdings", "trades", "axes", "overnight"]}
    u2 = load_csv(src)
    assert len(u2.clients) == len(u.clients)
    assert len(u2.axes) == len(u.axes)
    assert len(u2.instruments) == len(u.instruments)
    # holdings survive the round trip
    assert sum(len(c.holdings) for c in u2.clients) == sum(len(c.holdings) for c in u.clients)


def test_sqlite_round_trip_preserves_universe(tmp_path):
    u = generate_universe()
    db = str(tmp_path / "desk.sqlite")
    build_sqlite(db, u)
    u2 = load_sqlite(db)
    assert len(u2.clients) == len(u.clients)
    assert len(u2.axes) == len(u.axes)
    assert len(u2.instruments) == len(u.instruments)


def test_loaded_provider_drives_the_engine_unchanged(tmp_path):
    u = generate_universe()
    db = str(tmp_path / "d.sqlite")
    build_sqlite(db, u)
    prov = SqlProvider(db)                       # real-data provider
    ranked = MatchEngine(prov).rank_clients_for(prov.get_axes()[0])
    assert ranked
    assert 0 <= ranked[0].score <= 100
    assert ranked[0].score >= ranked[-1].score   # still ranked
