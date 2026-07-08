# Axurry

**A sales & trading desk assistant that turns desk risk into a ranked call list — and preps every client call in one click.**

*(Repository name: `Desk-Intel`.)*

Axurry opens to a clean landing page with **two boxes**; click one to open that tool full-screen:

| 🎯 Axe Matcher | 📇 Pre-Call Brief |
|---|---|
| The desk has risk to move (an *axe*). Pick it → get a **ranked list of which clients to call**, each with a match score, a plain-English reason *why*, a per-factor score breakdown, and a draft outreach line. | About to call a client? Pick them → get a **one-pager**: their book, recent trades with the desk, overnight P&L moves, and which live axes fit them. |

Each tool shows a rubric box up top explaining exactly how the match rating is calculated.

It runs today on a **manufactured (synthetic) universe** — no real client, portfolio, or trade data
required. A real bank feed later drops in behind the same interface with **zero changes to the engine or UI**.

---

## Why this exists (the desk rationale)

A salesperson sits between two sides:

- **Supply** — the desk's traders hold risk/inventory they need to move (*axes*).
- **Demand** — institutional clients (pensions, insurers, asset managers, hedge funds) who might want it.

The whole job is matching the two. Today that's mostly memory, gut, and a mass "run" email. Axurry
makes the matching explicit: it scores every client against an axe on the same things a good
salesperson weighs — **mandate fit, existing holdings, trading history with the desk, and recent
activity** — then ranks them and drafts the pitch.

This is **decision support, not autopilot.** Relationships and judgment stay with the human; the tool
makes sure the right names surface and nothing gets forgotten — especially valuable for a junior
covering many accounts.

## Quick start

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Run the split-screen app:
python -m streamlit run app/streamlit_app.py

# Or eyeball the engine in the terminal (no UI):
python cli.py

# Run the tests:
pytest -q
```

## How it works

### Data sources — synthetic *or* real (CSV / database / API)

The engine and UI depend **only** on the `DeskDataProvider` interface in `data/providers.py`.
Anything that produces the same objects works unchanged. Three real-data providers ship in
`data/loaders.py`, all selectable from the app's sidebar:

| Source | Provider | How to use |
|---|---|---|
| Synthetic (demo) | `SyntheticProvider` | default — manufactured world, safe to share publicly |
| Spreadsheets | `CsvProvider` | upload `instruments/clients/holdings/trades/axes[/overnight].csv` — templates in `sample_data/` |
| Database | `SqlProvider` | point at a SQLite file (same query pattern → Postgres / MSSQL / Snowflake) |
| Live API | `ApiProvider` | JSON at `/instruments`, `/clients`, `/holdings`, `/trades`, `/axes`, `/overnight` |

All three funnel through one builder (`universe_from_rows`), so wiring a real bank feed only
changes *how rows are fetched* — never the engine. For a bespoke source, write a class that builds
a `Universe` and hand it to `UniverseProvider`; change nothing else.

### Running it privately / inside a bank

Real client, holdings, and trade data is confidential — so the app is built to run private:

- **Password-gate the deployment.** Set `app_password` in Streamlit secrets and the real-data
  modes require it; add `require_login = true` to lock the whole app behind a login. The public
  synthetic demo stays open for sharing.
- **Run it internally.** For live bank data it should run on the firm's own infrastructure
  (internal server / private cloud), behind their SSO — never a public URL. It's a plain
  Python/Streamlit app: `streamlit run app/streamlit_app.py` on an internal host, with
  `SqlProvider`/`ApiProvider` pointed at internal systems.

### The match score (transparent by design)

`match_score` (0–100) = a weighted blend of five factors × a hard **eligibility gate**
(`engine/scoring.py`, `engine/match.py`):

| Factor | Weight | Question it answers |
|---|---|---|
| Mandate fit | 0.24 | Eligible & on-strategy (credit quality, duration band, sector)? |
| Portfolio fit | 0.24 | Does it sit naturally in their book (issuer/sector, rating, tenor)? |
| Directional fit | 0.22 | Right side for the desk? (a buyer with room vs. a holder who can trim) |
| Flow history | 0.18 | Traded this sector with us, on the side we need, and how recently? |
| Size fit | 0.12 | Can they absorb the ticket vs. their typical trade size? |

The **eligibility gate** then multiplies the score down for hard no-gos (e.g. high-yield into an
IG-only mandate ×0.10). Every factor returns a reason, so each ranking comes with an explanation.

### Project layout

```
data/
  universe.py     reference vocab (ratings, sectors, issuers, mandates)
  synthetic.py    seeded generator + the data model (Instrument/Client/Axe/...)
  providers.py    interfaces + UniverseProvider + SyntheticProvider + InMemoryProvider
  loaders.py      real-data providers: CSV / SQLite / REST API (+ sample-data writers)
engine/
  scoring.py      five scoring factors + eligibility gate (pure, unit-tested)
  match.py        combines them -> ranked ClientMatch list + drafted pitch
  brief.py        builds the pre-call one-pager
app/
  streamlit_app.py   split-screen UI + data-source picker + optional login
sample_data/      CSV templates + a ready-to-use SQLite DB (demo the CSV/DB modes)
cli.py            terminal view of the engine
tests/            planted known-answer tests + loader round-trip tests
```

## Testing on invented data — *better*, not worse

Because we generate the world, we **know the right answer**. The tests plant a textbook fit
(an IG pension that already buys healthcare) and a textbook non-fit (an energy high-yield hedge fund),
then assert the engine ranks them correctly. Real data can't do this — nobody hands you a labelled
"correct" call list. See `tests/_scenario.py`.

## Deliberately out of scope (v1)

Live market pricing, asset classes beyond corporate bonds, and production hardening (audit logging,
SSO, deploy pipelines). Real-data connectors (CSV / database / API) and access control now ship —
see above — but a full internal-bank deployment is its own effort.

---

*Built as a demonstration. All data is synthetic and generated locally; nothing here reflects any real
client, portfolio, or trade.*
