"""Salient -- Sales & Trading desk assistant.

Landing page shows two boxes (Axe Matcher | Pre-Call Brief). Click a box to open
that tool full-screen; a Back button returns home. Nothing is shown until you pick
a tool, so the home screen stays clean.

Run:  python -m streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from data.providers import SyntheticProvider
from engine.brief import BriefBuilder
from engine.match import WEIGHTS, MatchEngine

# ---------------------------------------------------------------------------
# Branding -- change APP_NAME here and it updates everywhere.
# ---------------------------------------------------------------------------
APP_NAME = "Salient"
APP_TAGLINE = "Sales & Trading desk assistant"

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📈",
                   initial_sidebar_state="collapsed")


# ---------------------------------------------------------------------------
# Shared setup (provider cached so the world is stable; results cached so
# flipping expanders / sliders doesn't recompute needlessly).
# ---------------------------------------------------------------------------
@st.cache_resource
def get_provider() -> SyntheticProvider:
    return SyntheticProvider()


provider = get_provider()
matcher = MatchEngine(provider)
brief_builder = BriefBuilder(provider)


@st.cache_data(show_spinner=False)
def ranked_for(axe_id: str):
    """All clients ranked for an axe (cached by axe id)."""
    return matcher.rank_clients_for(provider.get_axe(axe_id))


@st.cache_data(show_spinner=False)
def brief_for(client_id: str):
    return brief_builder.build_brief(provider.get_client(client_id))


if "view" not in st.session_state:
    st.session_state.view = "home"


def go(view: str) -> None:
    st.session_state.view = view


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container { max-width: 1200px; padding-top: 2.5rem; }
      .di-hero { text-align:center; margin: 1rem 0 2.6rem 0; }
      .di-hero h1 { font-size: 3rem; margin-bottom: 0.3rem; letter-spacing:-0.5px; }
      .di-hero p  { color:#6b7280; font-size: 1.15rem; margin:0; }
      .di-card { padding: 1.6rem 1.4rem 0.8rem 1.4rem; min-height: 260px; }
      .di-card .ico  { font-size: 3.6rem; }
      .di-card .ttl  { font-size: 1.9rem; font-weight: 700; margin-top:0.6rem; }
      .di-card .sub  { color:#6b7280; font-size: 1.08rem; line-height:1.5;
                       min-height: 4.4em; margin-top:0.6rem; }
      div[data-testid="stButton"] > button { border-radius: 10px; font-weight:600; }
      section.main div[data-testid="column"] div[data-testid="stButton"] > button {
        padding: 0.8rem 0; font-size: 1.05rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def score_badge(score: float) -> str:
    color = "#16a34a" if score >= 65 else "#ca8a04" if score >= 40 else "#9ca3af"
    return (f"<span style='background:{color};color:white;padding:2px 9px;"
            f"border-radius:10px;font-weight:600;font-size:0.85em'>{score:.0f}</span>")


_FACTOR_DESC = {
    "mandate": ("Mandate fit", "Is the bond in the client's mandate — credit quality "
                               "(IG/HY), duration, and sector?"),
    "holdings": ("Holdings overlap", "Do they already own similar bonds — same sector, "
                                     "close rating and duration?"),
    "history": ("Trading history", "Have they traded this sector with the desk before, "
                                   "on the side we now need?"),
    "recency": ("Recency", "How recently they've been active in this sector."),
}
_FACTOR_ORDER = ("mandate", "holdings", "history", "recency")


def rubric_box(context: str) -> None:
    """Explainer shown at the top of each tool: how the match rating is built."""
    with st.expander("ℹ️  How the match rating is calculated", expanded=True):
        st.markdown(
            "**Match rating (0–100)** is a weighted blend of four factors — "
            "the same things a good salesperson weighs by instinct:")
        rows = "\n".join(
            f"| {_FACTOR_DESC[k][0]} | **{int(WEIGHTS[k] * 100)}%** | {_FACTOR_DESC[k][1]} |"
            for k in _FACTOR_ORDER)
        st.markdown("| Factor | Weight | What it measures |\n|---|---|---|\n" + rows)
        st.markdown(
            "**Rating colour:** &nbsp; "
            "<span style='color:#16a34a;font-weight:600'>● 65–100 strong — call first</span> &nbsp;·&nbsp; "
            "<span style='color:#ca8a04;font-weight:600'>● 40–64 worth a look</span> &nbsp;·&nbsp; "
            "<span style='color:#9ca3af;font-weight:600'>● 0–39 low priority</span>",
            unsafe_allow_html=True)
        if context == "brief":
            st.caption(
                "The *Relevant live axes* below are scored with this same rubric. "
                "Overnight P&L ≈ position size × bond duration × overnight yield move.")


def score_breakdown(m) -> None:
    """Show how each factor contributed to a client's match score."""
    for k in _FACTOR_ORDER:
        raw, detail = m.components[k]
        pts = WEIGHTS[k] * raw * 100
        st.markdown(f"**{_FACTOR_DESC[k][0]}** &nbsp;<span style='color:#6b7280'>"
                    f"({int(WEIGHTS[k] * 100)}% weight)</span> &nbsp;→&nbsp; **+{pts:.0f} pts**",
                    unsafe_allow_html=True)
        st.progress(min(1.0, max(0.0, raw)))
        st.caption(detail)


# ===========================================================================
# HOME
# ===========================================================================
def render_home() -> None:
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
    st.button("←  Back", on_click=go, args=("home",), key="back_axe")
    st.markdown("## 🎯 Axe Matcher")
    st.caption("The desk has risk to move. Who do you call?")
    rubric_box("axe")

    axes = provider.get_axes()
    axe = st.selectbox("Select a desk axe", options=axes,
                       format_func=lambda a: f"[{a.urgency.upper()}] {a.label()}")

    inst = axe.instrument
    st.markdown(
        f"**Desk wants to `{axe.desk_side.upper()}` ${axe.notional_mm:.0f}mm** &nbsp;·&nbsp; "
        f"{inst.sector} &nbsp;·&nbsp; {inst.rating} &nbsp;·&nbsp; {inst.maturity_years}y "
        f"&nbsp;·&nbsp; urgency **{axe.urgency}**")

    ranked = ranked_for(axe.id)
    top_n = st.slider("How many clients to show", 3, min(15, len(ranked)), 8)
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
                    f"<span style='color:#6b7280;font-size:0.85em'>{m.client.type} · "
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
    st.button("←  Back", on_click=go, args=("home",), key="back_brief")
    st.markdown("## 📇 Pre-Call Brief")
    st.caption("About to call a client? Here's everything you should know.")
    rubric_box("brief")

    clients = sorted(provider.get_clients(), key=lambda c: c.name)
    client = st.selectbox("Select a client", options=clients,
                          format_func=lambda c: f"{c.name}  ({c.type})")

    brief = brief_for(client.id)

    st.markdown(
        f"**{client.name}** &nbsp;·&nbsp; {client.type} &nbsp;·&nbsp; {client.risk_appetite} risk  \n"
        f"<span style='color:#6b7280;font-size:0.9em'>Mandate: "
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
view = st.session_state.view
if view == "axe":
    render_axe_matcher()
elif view == "brief":
    render_pre_call_brief()
else:
    render_home()
