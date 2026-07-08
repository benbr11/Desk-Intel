"""Axurry -- Sales & Trading desk assistant.

Landing page shows two boxes (Axe Matcher | Pre-Call Brief). Click a box to open
that tool full-screen; a Back button returns home. A ☀️/🌙 toggle (top-left)
switches light/dark mode. Each view has a subtle colour undertone: purple (home),
blue (Axe Matcher), red (Pre-Call Brief).

Run:  python -m streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from data.loaders import ApiProvider, CsvProvider, SqlProvider
from data.providers import SyntheticProvider
from engine.brief import BriefBuilder
from engine.match import WEIGHTS, MatchEngine

# ---------------------------------------------------------------------------
# Branding -- change APP_NAME here and it updates everywhere.
# ---------------------------------------------------------------------------
APP_NAME = "Axurry"
APP_TAGLINE = "Sales & Trading desk assistant"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈",
                   initial_sidebar_state="collapsed")


# ---------------------------------------------------------------------------
# Data source layer -- synthetic (public demo) OR real data via CSV / SQL / API.
# The active provider lives in session_state; the engine is rebuilt from it each
# run (cheap). This is the "plug real data in" seam, made usable from the UI.
# Real-data modes can be locked behind a password so the deployment stays private
# (set `app_password`, and optionally `require_login = true`, in Streamlit secrets).
# ---------------------------------------------------------------------------
@st.cache_resource
def _synthetic_provider() -> SyntheticProvider:
    return SyntheticProvider()


def _secret(key: str, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


def _active_provider():
    return st.session_state.get("provider") or _synthetic_provider()


def _require_login_gate() -> None:
    """Optional full-app lock for a private/internal deployment. Enable by setting
    `require_login = true` and `app_password = "..."` in Streamlit secrets."""
    if not _secret("require_login") or st.session_state.get("authed"):
        return
    st.markdown(f"## 🔒 {APP_NAME}")
    st.caption("This deployment is private. Enter the access password to continue.")
    with st.form("login_gate"):
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            if pw and pw == _secret("app_password"):
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()


def _csv_source_ui() -> None:
    st.caption("Upload CSVs — templates are in the repo's `sample_data/`.")
    files = {}
    for key in ["instruments", "clients", "holdings", "trades", "axes", "overnight"]:
        up = st.file_uploader(f"{key}.csv", type="csv", key=f"up_{key}")
        if up is not None:
            files[key] = up
    if st.button("Load CSVs", key="load_csv", use_container_width=True):
        if {"instruments", "clients", "axes"} <= set(files):
            st.session_state.provider = CsvProvider(files)
            st.session_state.view = "home"
        else:
            st.warning("Need at least instruments.csv, clients.csv and axes.csv.")


def _sql_source_ui() -> None:
    path = st.text_input("SQLite database path", value="sample_data/desk.sqlite", key="sql_path")
    st.caption("Tables: instruments, clients, holdings, trades, axes, overnight. For "
               "Postgres/MSSQL/Snowflake the same query pattern applies — swap the connection "
               "in `load_sqlite()`.")
    if st.button("Connect", key="load_sql", use_container_width=True):
        st.session_state.provider = SqlProvider(path)
        st.session_state.view = "home"


def _api_source_ui() -> None:
    url = st.text_input("API base URL", placeholder="https://desk-api.internal/v1", key="api_url")
    token = st.text_input("Bearer token (optional)", type="password", key="api_token")
    st.caption("Expects JSON arrays at /instruments, /clients, /holdings, /trades, /axes, /overnight.")
    if st.button("Fetch", key="load_api", use_container_width=True) and url:
        st.session_state.provider = ApiProvider(url, token or None)
        st.session_state.view = "home"


def render_data_source() -> None:
    """Sidebar: choose where Axurry reads from. Synthetic is open; real sources can
    be password-gated so the same app is safe to share yet usable on real data."""
    with st.sidebar:
        st.markdown(f"### 🔌 {APP_NAME} data")
        src = st.radio("Data source",
                       ["Synthetic demo", "CSV upload", "Database (SQLite)", "REST API"],
                       key="data_source", label_visibility="collapsed")
        if src == "Synthetic demo":
            st.session_state.provider = None
            st.caption("Manufactured demo data — safe to share publicly.")
            return

        pw = _secret("app_password")
        if pw and not st.session_state.get("authed"):
            with st.form("unlock_data"):
                entered = st.text_input("Access password", type="password")
                if st.form_submit_button("Unlock") and entered == pw:
                    st.session_state.authed = True
                    st.rerun()
            st.info("Real data is password-protected — enter the access password.")
            return

        try:
            if src == "CSV upload":
                _csv_source_ui()
            elif src == "Database (SQLite)":
                _sql_source_ui()
            else:
                _api_source_ui()
        except Exception as exc:  # surface any load error rather than crashing
            st.session_state.provider = None
            st.error(f"Could not load data: {exc}")

        p = st.session_state.get("provider")
        if p is not None:
            st.success(f"Loaded {len(p.get_clients())} clients · {len(p.get_axes())} axes · "
                       f"{len(p.get_instruments())} instruments")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "view" not in st.session_state:
    st.session_state.view = "home"
if "dark" not in st.session_state:
    st.session_state.dark = False


def go(view: str) -> None:
    st.session_state.view = view


def toggle_theme() -> None:
    st.session_state.dark = not st.session_state.dark


# ---------------------------------------------------------------------------
# Theming -- per-view accent + light/dark, injected as CSS each run.
# Undertones are deliberately soft (subtle backgrounds, not bright fills).
# ---------------------------------------------------------------------------
THEME = {
    "home":  dict(accent_l="#7c3aed", accent_d="#a78bfa", bg_l="#f5f2fb", bg_d="#151221", card_d="#1f1b2d"),
    "axe":   dict(accent_l="#2563eb", accent_d="#60a5fa", bg_l="#eef4fd", bg_d="#0f1522", card_d="#161d2f"),
    "brief": dict(accent_l="#dc2626", accent_d="#f87171", bg_l="#fdf2f2", bg_d="#1c1114", card_d="#2a1a1d"),
}

_CSS = """
<style>
  .block-container { max-width: 1200px; padding-top: 3.75rem; }
  .stApp { background-color: %(bg)s; color: %(text)s; }
  /* Force standard text onto the themed colour so it can never end up
     light-on-light or dark-on-dark when switching modes. NB: we deliberately do
     NOT target <span>, so inline-coloured spans (badges, colour keys) keep their
     own colour. */
  [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
  [data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] strong,
  [data-testid="stMarkdownContainer"] em, [data-testid="stMarkdownContainer"] td,
  [data-testid="stMarkdownContainer"] th,
  [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
  [data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4,
  [data-testid="stMarkdownContainer"] h5, [data-testid="stMarkdownContainer"] h6,
  [data-testid="stHeading"], [data-testid="stHeadingContainer"],
  [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
  [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: %(text)s !important; }

  .di-hero { text-align:center; margin: 0.6rem 0 2.4rem 0; }
  .di-hero h1 { font-size: 3rem; margin-bottom: 0.3rem; letter-spacing:-0.5px; color:%(text)s; }
  .di-hero p  { font-size: 1.15rem; margin:0; color:%(muted)s; }
  .di-card { padding: 1.6rem 1.4rem 0.8rem 1.4rem; min-height: 260px; }
  .di-card .ico { font-size: 3.6rem; }
  .di-card .ttl { font-size: 1.9rem; font-weight:700; margin-top:0.6rem; color:%(text)s; }
  .di-card .sub { font-size:1.08rem; line-height:1.5; min-height:4.4em; margin-top:0.6rem; color:%(muted)s; }
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:%(muted)s !important; }

  /* cards / bordered containers -- soft accent-tinted border */
  [data-testid="stVerticalBlockBorderWrapper"] { border-color:%(accent_soft)s !important;
      border-radius:12px; background-color:%(card)s; }
  [data-testid="stVerticalBlockBorderWrapper"] > div { background-color:%(card)s; }

  /* expanders -- header bar + body both follow the card colour */
  [data-testid="stExpander"] { background-color:%(card)s; border:1px solid %(border)s; border-radius:10px; }
  [data-testid="stExpander"] details { background-color:%(card)s !important; }
  [data-testid="stExpander"] summary { background-color:%(card)s !important; }
  [data-testid="stExpanderDetails"] { background-color:%(card)s !important; }
  [data-testid="stExpander"] summary, [data-testid="stExpander"] summary span,
  [data-testid="stExpander"] summary p, [data-testid="stExpander"] summary svg { color:%(text)s !important;
      fill:%(text)s !important; }

  /* buttons */
  div[data-testid="stButton"] > button { border-radius:10px; font-weight:600; }
  button[kind="primary"] { background-color:%(accent)s !important; border-color:%(accent)s !important;
      color:#ffffff !important; padding:0.75rem 0; font-size:1.05rem; }

  /* selectbox / inputs / dropdown -- force every layer onto the themed surface */
  [data-testid="stSelectbox"] div[data-baseweb="select"] div,
  [data-testid="stSelectbox"] div[data-baseweb="base-input"],
  div[data-baseweb="select"] > div { background-color:%(inp)s !important;
      border-color:%(border)s !important; }
  div[data-baseweb="select"] *, [data-testid="stSelectbox"] * { color:%(text)s !important; }
  div[data-baseweb="select"] svg { fill:%(text)s !important; }
  ul[role="listbox"], div[data-baseweb="menu"], div[data-baseweb="popover"] div[role="listbox"] {
      background-color:%(inp)s !important; }
  ul[role="listbox"] li, div[data-baseweb="menu"] li { color:%(text)s !important; }

  /* Back button + rubric popover trigger follow the themed surface */
  .st-key-back_axe button, .st-key-back_brief button,
  [data-testid="stPopover"] button { background-color:%(inp)s !important;
      color:%(text)s !important; border-color:%(border)s !important; }
  /* rubric popover panel */
  [data-testid="stPopoverBody"], div[data-baseweb="popover"] [data-testid="stPopoverBody"] {
      background-color:%(card)s !important; }
  [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color:%(text)s !important; }

  /* theme toggle -- borderless icon button, top-left */
  .st-key-theme_toggle button { border:none !important; background:transparent !important;
      font-size:1.5rem !important; padding:0.1rem 0.4rem !important; box-shadow:none !important; }
  .st-key-theme_toggle button:hover { transform:scale(1.12); }
  %(extra)s
</style>
"""


def inject_theme(view: str) -> None:
    dark = st.session_state.dark
    t = THEME[view]
    axe_t, brief_t = THEME["axe"], THEME["brief"]
    if dark:
        v = dict(bg=t["bg_d"], text="#e5e7eb", muted="#9aa4b2", card=t["card_d"],
                 accent=t["accent_d"], inp="#1f2530", border="rgba(148,163,184,0.20)",
                 blue=axe_t["accent_d"], red=brief_t["accent_d"])
    else:
        v = dict(bg=t["bg_l"], text="#0f172a", muted="#64748b", card="#ffffff",
                 accent=t["accent_l"], inp="#ffffff", border="rgba(15,23,42,0.10)",
                 blue=axe_t["accent_l"], red=brief_t["accent_l"])
    v["accent_soft"] = v["accent"] + "44"
    if view == "home":
        v["extra"] = (
            ".st-key-open_axe button{background-color:%(blue)s!important;border-color:%(blue)s!important;}"
            ".st-key-open_brief button{background-color:%(red)s!important;border-color:%(red)s!important;}"
        ) % v
    else:
        v["extra"] = ""
    st.markdown(_CSS % v, unsafe_allow_html=True)


def render_topbar(view: str) -> None:
    cols = st.columns([0.8, 1.2, 2, 8])
    with cols[0]:
        icon = "🌙" if st.session_state.dark else "☀️"
        st.button(icon, key="theme_toggle", on_click=toggle_theme,
                  help="Switch light / dark mode")
    if view != "home":
        with cols[1]:
            st.button("←  Back", key=f"back_{view}", on_click=go, args=("home",))
        with cols[2]:
            with st.popover("ℹ️  Scoring rubric"):
                rubric_content(view)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def score_badge(score: float) -> str:
    color = "#16a34a" if score >= 65 else "#ca8a04" if score >= 40 else "#9ca3af"
    return (f"<span style='background:{color};color:white;padding:2px 9px;"
            f"border-radius:10px;font-weight:600;font-size:0.85em'>{score:.0f}</span>")


_FACTOR_DESC = {
    "mandate": ("Mandate fit", "Is it eligible and on-strategy — credit quality (IG/HY), "
                               "duration band, and stated sector preference? (graded by distance)"),
    "portfolio": ("Portfolio fit", "Does it sit naturally in their book — same issuer/sector, "
                                   "similar rating and tenor, meaningful weight?"),
    "direction": ("Directional fit", "Are they on the side the desk needs? To sell we want room "
                                     "to buy; to source we want a holder who might trim — so "
                                     "concentration cuts both ways."),
    "flow": ("Flow history", "Have they traded this sector with the desk on the side we now "
                             "need, and how recently? (recency-weighted)"),
    "size": ("Size fit", "Can they absorb the ticket, given their typical trade size and book?"),
}
_FACTOR_ORDER = ("mandate", "portfolio", "direction", "flow", "size")


def rubric_content(context: str) -> None:
    """Rubric explainer -- rendered inside the top-left 'Scoring rubric' popover."""
    st.markdown(
        "**Match score (0–100)** estimates how likely a client is to trade a given axe. "
        "It is a weighted blend of five fit factors, then scaled by a hard **eligibility "
        "gate**:")
    st.markdown(
        "<div style='font-family:monospace;font-size:0.9em'>"
        "score = 100 × Σ(weightᵢ × factorᵢ) × eligibility</div>",
        unsafe_allow_html=True)

    rows = "\n".join(
        f"| {_FACTOR_DESC[k][0]} | **{int(WEIGHTS[k] * 100)}%** | {_FACTOR_DESC[k][1]} |"
        for k in _FACTOR_ORDER)
    st.markdown("| Factor | Weight | What it measures |\n|---|---|---|\n" + rows)

    st.markdown(
        "**Why it's direction-aware (the core idea).** Sales is a matching problem: the desk "
        "has *supply* of risk, clients have latent *demand*. Which client fits depends on the "
        "desk's side:\n"
        "- **Desk SELLS** (offering bonds) → we want a **buyer**: mandate headroom, room to add, "
        "a stated appetite for the sector. Being *over-concentrated* in the name **hurts** — no room.\n"
        "- **Desk SOURCES** (bidding for bonds) → we want a **holder who might trim**: they must "
        "already own it, and being *over-weight* **helps**. You can't source from someone who "
        "doesn't hold it.")

    st.markdown(
        "**Eligibility gate (×).** Some fits are hard no-gos and collapse the score no matter how "
        "good the other signals look — because a salesperson simply wouldn't make that call:\n"
        "- High-yield bond into an **IG-only** mandate → ×0.10 (ineligible)\n"
        "- IG bond into a **HY-only** mandate → ×0.55 (off-strategy)\n"
        "- Deep-HY (B+ or worse) into a **low-risk** account → ×0.40\n"
        "- Maturity far beyond the client's **duration band** → ×0.70")

    st.markdown(
        "**Grading, not buckets.** Credit-quality, rating and duration fit decay smoothly with "
        "distance (e.g. a 7y bond vs a 4–9y band scores full; a 12y bond scores partial).")

    st.markdown(
        "**Score bands:** &nbsp; "
        "<span style='color:#16a34a;font-weight:600'>● 65–100 strong — call first</span> &nbsp;·&nbsp; "
        "<span style='color:#ca8a04;font-weight:600'>● 40–64 worth a look</span> &nbsp;·&nbsp; "
        "<span style='color:#9ca3af;font-weight:600'>● 0–39 low priority</span>",
        unsafe_allow_html=True)

    st.caption(
        "Decision support, not autopilot — relationships and judgement stay with the human. "
        "Weights are deliberately simple and visible so every number is defensible; on real data "
        "they would be tuned/back-tested against realised hit rates.")
    if context == "brief":
        st.caption(
            "The *Relevant live axes* below are scored with this same model. "
            "Overnight P&L ≈ position size × bond duration × overnight yield move.")


def score_breakdown(m) -> None:
    base = 0.0
    for k in _FACTOR_ORDER:
        raw, detail = m.components[k]
        pts = WEIGHTS[k] * raw * 100
        base += pts
        st.markdown(f"**{_FACTOR_DESC[k][0]}** &nbsp;<span style='color:#94a3b8'>"
                    f"({int(WEIGHTS[k] * 100)}% weight)</span> &nbsp;→&nbsp; **+{pts:.0f} pts**",
                    unsafe_allow_html=True)
        st.progress(min(1.0, max(0.0, raw)))
        st.caption(detail)
    mult, note = m.eligibility
    st.divider()
    if mult < 0.999:
        st.markdown(f"**Base {base:.0f}**  ×  **eligibility {mult:.2f}**"
                    + (f" &nbsp;<span style='color:#94a3b8'>({note})</span>" if note else ""),
                    unsafe_allow_html=True)
    st.markdown(f"### Final match score: {m.score:.0f}")


# ===========================================================================
# HOME
# ===========================================================================
def render_home() -> None:
    render_topbar("home")
    st.markdown(
        f"<div class='di-hero'><h1>📈 {APP_NAME}</h1>"
        f"<p>{APP_TAGLINE} — pick a tool to begin.</p></div>",
        unsafe_allow_html=True)

    left, _mid, right = st.columns([1, 0.06, 1], gap="large")

    with left:
        with st.container(border=True):
            st.markdown(
                "<div class='di-card'><div class='ico'>🎯</div>"
                "<div class='ttl'>Axe Matcher</div>"
                "<div class='sub'>The desk has risk to move. Get a ranked list of "
                "which clients to call — with the reason and a draft pitch for each.</div></div>",
                unsafe_allow_html=True)
            st.button("Open Axe Matcher  →", type="primary", use_container_width=True,
                      on_click=go, args=("axe",), key="open_axe")

    with right:
        with st.container(border=True):
            st.markdown(
                "<div class='di-card'><div class='ico'>📇</div>"
                "<div class='ttl'>Pre-Call Brief</div>"
                "<div class='sub'>About to call a client? Get a one-page brief: their "
                "book, recent trades, overnight P&amp;L, and which live axes fit them.</div></div>",
                unsafe_allow_html=True)
            st.button("Open Pre-Call Brief  →", type="primary", use_container_width=True,
                      on_click=go, args=("brief",), key="open_brief")

    st.markdown(
        "<p style='text-align:center;color:#9ca3af;font-size:0.85rem;margin-top:2rem'>"
        "Running on a synthetic universe — a real feed drops in behind the same interface.</p>",
        unsafe_allow_html=True)


# ===========================================================================
# TOOL 1 -- Axe Matcher
# ===========================================================================
def render_axe_matcher() -> None:
    render_topbar("axe")
    st.markdown("## 🎯 Axe Matcher")
    st.caption("The desk has risk to move. Who do you call?  "
               "*(Scoring rubric is in the top-left ℹ️ button.)*")

    axes = provider.get_axes()
    if not axes:
        st.info("No axes in the current data source. Load data that includes axes from the sidebar.")
        return
    axe = st.selectbox("Select a desk axe", options=axes,
                       format_func=lambda a: f"[{a.urgency.upper()}] {a.label()}")

    inst = axe.instrument
    st.markdown(
        f"**Desk wants to `{axe.desk_side.upper()}` ${axe.notional_mm:.0f}mm** &nbsp;·&nbsp; "
        f"{inst.sector} &nbsp;·&nbsp; {inst.rating} &nbsp;·&nbsp; {inst.maturity_years}y "
        f"&nbsp;·&nbsp; urgency **{axe.urgency}**")

    ranked = matcher.rank_clients_for(axe)
    if not ranked:
        st.info("No clients in the current data source.")
        return
    n = len(ranked)
    top_n = st.slider("How many clients to show", 3, min(15, n), min(8, n)) if n > 3 else n
    strong = sum(1 for m in ranked if m.score >= 65)
    st.caption(f"Scored {len(ranked)} clients · {strong} strong fit(s) · "
               f"top match **{ranked[0].client.name}** ({ranked[0].score:.0f}).")
    st.divider()

    st.markdown("#### Ranked clients to call")
    for i, m in enumerate(ranked[:top_n], 1):
        with st.container(border=True):
            c1, c2 = st.columns([0.8, 0.2])
            with c1:
                star = " ⭐" if i == 1 else ""
                st.markdown(
                    f"**{i}. {m.client.name}**{star}  \n"
                    f"<span style='color:#94a3b8;font-size:0.85em'>{m.client.type} · "
                    f"{m.client.risk_appetite} risk</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div style='text-align:right'>Match {score_badge(m.score)}</div>",
                            unsafe_allow_html=True)
            st.markdown(f"<span style='font-size:0.9em'>{m.explanation}</span>",
                        unsafe_allow_html=True)
            bcol, pcol = st.columns(2)
            with bcol:
                with st.expander("Why this score"):
                    score_breakdown(m)
            with pcol:
                with st.expander("Draft outreach"):
                    st.text_area("pitch", m.pitch, height=110, label_visibility="collapsed",
                                 key=f"pitch_{axe.id}_{m.client.id}")

    st.caption("All data is synthetic and generated locally — nothing reflects a real client or trade.")


# ===========================================================================
# TOOL 2 -- Pre-Call Brief
# ===========================================================================
def render_pre_call_brief() -> None:
    render_topbar("brief")
    st.markdown("## 📇 Pre-Call Brief")
    st.caption("About to call a client? Here's everything you should know.  "
               "*(Scoring rubric is in the top-left ℹ️ button.)*")

    clients = sorted(provider.get_clients(), key=lambda c: c.name)
    if not clients:
        st.info("No clients in the current data source. Load data from the sidebar.")
        return
    client = st.selectbox("Select a client", options=clients,
                          format_func=lambda c: f"{c.name}  ({c.type})")

    brief = brief_builder.build_brief(client)

    st.markdown(
        f"**{client.name}** &nbsp;·&nbsp; {client.type} &nbsp;·&nbsp; {client.risk_appetite} risk  \n"
        f"<span style='color:#94a3b8;font-size:0.9em'>Mandate: "
        f"{', '.join(client.credit_mandate + client.duration_mandate)} &nbsp;|&nbsp; "
        f"Tilts: {', '.join(client.sector_tilts)}</span>", unsafe_allow_html=True)

    pnl = brief.overnight_pnl_mm
    m1, m2, m3 = st.columns(3)
    m1.metric("Book size", f"${client.aum_mm:,.0f}mm")
    m2.metric("Overnight P&L", f"${pnl:+.2f}mm", delta=f"{pnl:+.2f}", delta_color="normal")
    m3.metric("Positions", f"{len(client.holdings)}")
    st.divider()

    colA, colB = st.columns([0.5, 0.5], gap="large")
    with colA:
        st.markdown("#### Talking points")
        for tp in brief.talking_points:
            st.markdown(f"- {tp}")
        st.markdown("#### Relevant live axes")
        if brief.relevant_axes:
            for a in brief.relevant_axes:
                st.markdown(
                    f"{score_badge(a.score)} &nbsp; **Desk {a.desk_side.upper()}** — {a.axe_label}",
                    unsafe_allow_html=True)
        else:
            st.caption("No current axes are a strong fit.")

    with colB:
        st.markdown("#### Sector exposure")
        sector_df = (pd.DataFrame({"$mm": brief.sector_breakdown})
                     .sort_values("$mm", ascending=True))
        st.bar_chart(sector_df, height=260, horizontal=True)

    with st.expander("Top positions & overnight movers"):
        st.dataframe(
            [{"Issuer": mv.position.instrument.issuer,
              "Sector": mv.position.instrument.sector,
              "Rating": mv.position.instrument.rating,
              "$mm": mv.position.notional_mm,
              "O/N bp": mv.bp_move,
              "O/N P&L $mm": mv.pnl_mm} for mv in brief.position_moves],
            hide_index=True, use_container_width=True)

    with st.expander("Recent trades with the desk"):
        if brief.recent_trades:
            st.dataframe(
                [{"When": "this q" if t.quarters_ago == 0 else f"{t.quarters_ago}q ago",
                  "Side": t.side, "Issuer": t.instrument.issuer,
                  "Sector": t.instrument.sector, "$mm": t.notional_mm}
                 for t in brief.recent_trades],
                hide_index=True, use_container_width=True)
        else:
            st.caption("No recent trades on file.")

    st.caption("All data is synthetic and generated locally — nothing reflects a real client or trade.")


# ===========================================================================
# Router
# ===========================================================================
_require_login_gate()
render_data_source()
provider = _active_provider()
matcher = MatchEngine(provider)
brief_builder = BriefBuilder(provider)

view = st.session_state.view
inject_theme(view)
if view == "axe":
    render_axe_matcher()
elif view == "brief":
    render_pre_call_brief()
else:
    render_home()
