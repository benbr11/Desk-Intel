# Salient

**A sales & trading desk assistant that turns desk risk into a ranked call list — and preps every client call in one click.**

*(Repository name: `Desk-Intel`.)*

Salient opens to a clean landing page with **two boxes**; click one to open that tool full-screen:

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

The whole job is matching the two. Today that's mostly memory, gut, and a mass "run" email. Salient
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

### The adapter seam (the important design idea)

The engine and UI depend **only** on abstract interfaces in `data/providers.py`
(`ClientProvider`, `AxeProvider`, `MarketProvider`). Today those are backed by
`SyntheticProvider`, which manufactures a coherent fake world. To go live:

```python
# Today:
provider = SyntheticProvider()
# At a bank — write one class that reads real feeds, change one line:
provider = CitiProvider()          # implements the same interfaces
```

Nothing in `engine/` or `app/` changes. No proprietary data is ever needed to build, test, or demo.

### The match score (transparent by design)

`match_score` (0–100) is a weighted blend of four components (`engine/scoring.py`):

| Component | Weight | Question it answers |
|---|---|---|
| Mandate fit | 0.35 | Is this even in-mandate (credit quality, duration, sector)? |
| Holdings overlap | 0.30 | Do they already own this kind of risk? |
| Behavioural history | 0.25 | Have they traded it with us, on the side we now need? |
| Recency | 0.10 | Are they active in this sector right now? |

Each component also returns a short reason, which is why every ranking comes with an explanation.

### Project layout

```
data/
  universe.py     reference vocab (ratings, sectors, issuers, mandates)
  synthetic.py    seeded generator + the data model (Instrument/Client/Axe/...)
  providers.py    the adapter interfaces + SyntheticProvider + InMemoryProvider
engine/
  scoring.py      the four scoring components (pure, unit-tested)
  match.py        combines them -> ranked ClientMatch list + drafted pitch
  brief.py        builds the pre-call one-pager
app/
  streamlit_app.py   the split-screen UI
cli.py            terminal view of the engine
tests/            planted known-answer tests (we control the truth)
```

## Testing on invented data — *better*, not worse

Because we generate the world, we **know the right answer**. The tests plant a textbook fit
(an IG pension that already buys healthcare) and a textbook non-fit (an energy high-yield hedge fund),
then assert the engine ranks them correctly. Real data can't do this — nobody hands you a labelled
"correct" call list. See `tests/_scenario.py`.

## Deliberately out of scope (v1)

Real market/bank data, authentication, live pricing, and asset classes beyond corporate bonds.
These are exactly the "plug in later" items the adapter seam is designed for.

---

*Built as a demonstration. All data is synthetic and generated locally; nothing here reflects any real
client, portfolio, or trade.*
