"""Real-data loaders: build a Universe from CSV files, a SQLite database, or a REST
API. Each returns objects identical to the synthetic world, so the engine and UI are
completely source-agnostic — the whole point of the provider seam.

Shared schema (same field names across all three sources):
  instruments: id, issuer, sector, rating, maturity_years, coupon[, asset_class]
  clients:     id, name, type, risk_appetite, credit_mandate, duration_mandate, sector_tilts
               (the mandate/tilt fields are lists; in CSV/SQL separate with '|')
  holdings:    client_id, instrument_id, notional_mm
  trades:      client_id, instrument_id, side("bought"/"sold"), notional_mm, quarters_ago
  axes:        id, instrument_id, desk_side("buy"/"sell"), notional_mm, urgency
  overnight:   instrument_id, bp            (optional — overnight yield move in bp)

To point at a real bank system, you only change *how the rows are fetched*
(a different DB connection or API base URL); `universe_from_rows` and everything
above it stay the same.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import urllib.request

from data.providers import UniverseProvider
from data.synthetic import Axe, Client, Instrument, Position, Trade, Universe


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _aslist(v) -> list[str]:
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    if v is None:
        return []
    return [p.strip() for p in str(v).replace(";", "|").replace(",", "|").split("|") if p.strip()]


def _num(v, cast=float, default=0):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# The one builder everything funnels through: rows (dicts) -> Universe
# ---------------------------------------------------------------------------
def universe_from_rows(instruments, clients, holdings, trades, axes, overnight=None) -> Universe:
    insts: dict[str, Instrument] = {}
    for r in instruments:
        iid = str(r["id"])
        insts[iid] = Instrument(
            id=iid, issuer=r["issuer"], sector=r["sector"], rating=r["rating"],
            maturity_years=_num(r["maturity_years"], int), coupon=_num(r["coupon"], float),
            asset_class=(r.get("asset_class") or "Corporate Bond"))

    hold_by_client: dict[str, list[Position]] = {}
    for r in holdings:
        inst = insts.get(str(r["instrument_id"]))
        if inst:
            hold_by_client.setdefault(str(r["client_id"]), []).append(
                Position(inst, _num(r["notional_mm"], float)))

    trade_by_client: dict[str, list[Trade]] = {}
    for r in trades:
        inst = insts.get(str(r["instrument_id"]))
        if inst:
            trade_by_client.setdefault(str(r["client_id"]), []).append(
                Trade(inst, str(r["side"]).strip().lower(),
                      _num(r["notional_mm"], float), _num(r.get("quarters_ago", 0), int)))

    clients_out: list[Client] = []
    for r in clients:
        cid = str(r["id"])
        c = Client(
            id=cid, name=r["name"], type=r["type"],
            risk_appetite=str(r.get("risk_appetite", "medium")).strip().lower(),
            credit_mandate=_aslist(r.get("credit_mandate")),
            duration_mandate=_aslist(r.get("duration_mandate")),
            sector_tilts=_aslist(r.get("sector_tilts")))
        c.holdings = hold_by_client.get(cid, [])
        c.trades = trade_by_client.get(cid, [])
        clients_out.append(c)

    axes_out: list[Axe] = []
    for r in axes:
        inst = insts.get(str(r["instrument_id"]))
        if inst:
            axes_out.append(Axe(
                id=str(r["id"]), instrument=inst, desk_side=str(r["desk_side"]).strip().lower(),
                notional_mm=_num(r["notional_mm"], float),
                urgency=str(r.get("urgency", "medium")).strip().lower()))

    overnight_bp = {str(r["instrument_id"]): _num(r.get("bp", 0), float) for r in (overnight or [])}
    return Universe(list(insts.values()), clients_out, axes_out, overnight_bp)


# ---------------------------------------------------------------------------
# 1. CSV
# ---------------------------------------------------------------------------
def _read_csv(fileobj) -> list[dict]:
    raw = fileobj.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw)))


def load_csv(sources: dict) -> Universe:
    """`sources` maps each table name to a file path OR a file-like object
    (e.g. a Streamlit UploadedFile). Missing optional tables are simply empty."""
    def rows(key):
        s = sources.get(key)
        if s is None:
            return []
        if hasattr(s, "read"):
            s.seek(0) if hasattr(s, "seek") else None
            return _read_csv(s)
        with open(s, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    return universe_from_rows(rows("instruments"), rows("clients"), rows("holdings"),
                              rows("trades"), rows("axes"), rows("overnight"))


# ---------------------------------------------------------------------------
# 2. SQLite (reference DB implementation; same query pattern generalises to
#    Postgres/MSSQL/Snowflake — swap the connection).
# ---------------------------------------------------------------------------
def load_sqlite(db_path: str) -> Universe:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        def q(table):
            try:
                return [dict(r) for r in con.execute(f"SELECT * FROM {table}")]
            except sqlite3.Error:
                return []
        return universe_from_rows(q("instruments"), q("clients"), q("holdings"),
                                  q("trades"), q("axes"), q("overnight"))
    finally:
        con.close()


# ---------------------------------------------------------------------------
# 3. REST API (JSON arrays at /instruments, /clients, /holdings, /trades,
#    /axes, /overnight). Bearer token optional.
# ---------------------------------------------------------------------------
def load_api(base_url: str, token: str | None = None) -> Universe:
    base = base_url.rstrip("/")

    def get(path):
        req = urllib.request.Request(f"{base}/{path}")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, list) else data.get(path, [])

    return universe_from_rows(get("instruments"), get("clients"), get("holdings"),
                              get("trades"), get("axes"), get("overnight"))


# ---------------------------------------------------------------------------
# Providers (thin wrappers — build a Universe, hand it to UniverseProvider)
# ---------------------------------------------------------------------------
class CsvProvider(UniverseProvider):
    def __init__(self, sources: dict):
        super().__init__(load_csv(sources))


class SqlProvider(UniverseProvider):
    def __init__(self, db_path: str):
        super().__init__(load_sqlite(db_path))


class ApiProvider(UniverseProvider):
    def __init__(self, base_url: str, token: str | None = None):
        super().__init__(load_api(base_url, token))


# ---------------------------------------------------------------------------
# Export helpers — turn any Universe into CSV templates or a sample SQLite DB
# (used to generate sample_data/ so CSV & DB modes are demoable out of the box).
# ---------------------------------------------------------------------------
def universe_to_tables(u: Universe) -> dict[str, list[dict]]:
    instruments = [dict(id=i.id, issuer=i.issuer, sector=i.sector, rating=i.rating,
                        maturity_years=i.maturity_years, coupon=i.coupon,
                        asset_class=i.asset_class) for i in u.instruments]
    clients, holdings, trades = [], [], []
    for c in u.clients:
        clients.append(dict(id=c.id, name=c.name, type=c.type, risk_appetite=c.risk_appetite,
                            credit_mandate="|".join(c.credit_mandate),
                            duration_mandate="|".join(c.duration_mandate),
                            sector_tilts="|".join(c.sector_tilts)))
        for p in c.holdings:
            holdings.append(dict(client_id=c.id, instrument_id=p.instrument.id, notional_mm=p.notional_mm))
        for t in c.trades:
            trades.append(dict(client_id=c.id, instrument_id=t.instrument.id, side=t.side,
                               notional_mm=t.notional_mm, quarters_ago=t.quarters_ago))
    axes = [dict(id=a.id, instrument_id=a.instrument.id, desk_side=a.desk_side,
                 notional_mm=a.notional_mm, urgency=a.urgency) for a in u.axes]
    overnight = [dict(instrument_id=iid, bp=bp) for iid, bp in u.overnight_bp.items()]
    return dict(instruments=instruments, clients=clients, holdings=holdings,
                trades=trades, axes=axes, overnight=overnight)


def write_csvs(out_dir, universe: Universe) -> None:
    import os
    os.makedirs(out_dir, exist_ok=True)
    for name, rows in universe_to_tables(universe).items():
        if not rows:
            continue
        with open(os.path.join(out_dir, f"{name}.csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def build_sqlite(db_path: str, universe: Universe) -> None:
    con = sqlite3.connect(db_path)
    try:
        for name, rows in universe_to_tables(universe).items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            con.execute(f"DROP TABLE IF EXISTS {name}")
            con.execute(f"CREATE TABLE {name} ({', '.join(c + ' TEXT' for c in cols)})")
            con.executemany(
                f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [[r[c] for c in cols] for r in rows])
        con.commit()
    finally:
        con.close()
