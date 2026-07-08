"""DeskIntel -- split-screen Sales & Trading desk assistant.

Left half  : AXE MATCHER   -- pick an axe the desk wants to move, get the ranked
                             call list with a reason and a draft pitch per client.
Right half : PRE-CALL BRIEF -- pick a client, get a one-pager to prep the call.

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
from engine.match import MatchEngine

st.set_page_config(page_title="DeskIntel", layout="wide", page_icon="📈")


@st.cache_resource
def get_provider() -> SyntheticProvider:
    # Cached so the synthetic world is stable across reruns/clicks.
    return SyntheticProvider()


provider = get_provider()
matcher = MatchEngine(provider)
brief_builder = BriefBuilder(provider)

# --- Header --------------------------------------------------------------------
st.markdown(
    "## 📈 DeskIntel &nbsp;·&nbsp; Sales & Trading desk assistant",
)
st.caption(
    "Turns desk risk into a ranked call list, and preps every client call in one click. "
    "Running on a **synthetic** universe — a real feed drops in behind the same interface."
)

left, right = st.columns(2, gap="large")


def score_badge(score: float) -> str:
    color = "#16a34a" if score >= 65 else "#ca8a04" if score >= 40 else "#9ca3af"
    return (f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:10px;font-weight:600;font-size:0.85em'>{score:.0f}</span>")


# ============================ LEFT: AXE MATCHER ================================
with left:
    st.subheader("① Axe Matcher")
    st.caption("The desk has risk to move. Who do you call?")

    axes = provider.get_axes()
    axe = st.selectbox(
        "Select a desk axe",
        options=axes,
        format_func=lambda a: f"[{a.urgency.upper()}] {a.label()}",
    )

    inst = axe.instrument
    st.markdown(
        f"**Desk wants to `{axe.desk_side.upper()}` ${axe.notional_mm:.0f}mm** &nbsp;·&nbsp; "
        f"{inst.sector} &nbsp;·&nbsp; {inst.rating} &nbsp;·&nbsp; {inst.maturity_years}y "
        f"&nbsp;·&nbsp; urgency **{axe.urgency}**"
    )

    st.markdown("**Ranked clients to call**")
    ranked = matcher.rank_clients_for(axe, top_n=8)
    for i, m in enumerate(ranked, 1):
        with st.container(border=True):
            c1, c2 = st.columns([0.78, 0.22])
            with c1:
                st.markdown(f"**{i}. {m.client.name}**  \n"
                            f"<span style='color:#6b7280;font-size:0.85em'>{m.client.type} · "
                            f"{m.client.risk_appetite} risk</span>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"Match&nbsp;{score_badge(m.score)}", unsafe_allow_html=True)
            st.markdown(f"<span style='font-size:0.9em'>{m.explanation}</span>",
                        unsafe_allow_html=True)
            with st.expander("Draft outreach"):
                st.text_area("pitch", m.pitch, height=90, key=f"pitch_{axe.id}_{m.client.id}",
                             label_visibility="collapsed")


# ============================ RIGHT: PRE-CALL BRIEF ===========================
with right:
    st.subheader("② Pre-Call Brief")
    st.caption("About to call a client? Here's everything you should know.")

    clients = sorted(provider.get_clients(), key=lambda c: c.name)
    client = st.selectbox(
        "Select a client",
        options=clients,
        format_func=lambda c: f"{c.name}  ({c.type})",
    )

    brief = brief_builder.build_brief(client)

    st.markdown(
        f"**{client.name}** &nbsp;·&nbsp; {client.type} &nbsp;·&nbsp; {client.risk_appetite} risk  \n"
        f"<span style='color:#6b7280;font-size:0.9em'>Mandate: "
        f"{', '.join(client.credit_mandate + client.duration_mandate)} &nbsp;|&nbsp; "
        f"Tilts: {', '.join(client.sector_tilts)}</span>",
        unsafe_allow_html=True,
    )

    m1, m2 = st.columns(2)
    m1.metric("Book size", f"${client.aum_mm:,.0f}mm")
    m2.metric("Overnight P&L", f"${brief.overnight_pnl_mm:+.2f}mm")

    st.markdown("**Talking points**")
    for tp in brief.talking_points:
        st.markdown(f"- {tp}")

    st.markdown("**Sector exposure**")
    sector_df = (pd.DataFrame({"$mm": brief.sector_breakdown})
                 .sort_values("$mm", ascending=True))
    st.bar_chart(sector_df, height=220, horizontal=True)

    with st.expander("Top positions & overnight movers", expanded=False):
        st.dataframe(
            [{"Issuer": mv.position.instrument.issuer,
              "Sector": mv.position.instrument.sector,
              "Rating": mv.position.instrument.rating,
              "$mm": mv.position.notional_mm,
              "O/N bp": mv.bp_move,
              "O/N P&L $mm": mv.pnl_mm} for mv in brief.position_moves],
            hide_index=True, use_container_width=True,
        )

    with st.expander("Recent trades with the desk"):
        if brief.recent_trades:
            st.dataframe(
                [{"When": "this q" if t.quarters_ago == 0 else f"{t.quarters_ago}q ago",
                  "Side": t.side,
                  "Issuer": t.instrument.issuer,
                  "Sector": t.instrument.sector,
                  "$mm": t.notional_mm} for t in brief.recent_trades],
                hide_index=True, use_container_width=True,
            )
        else:
            st.caption("No recent trades on file.")

    st.markdown("**Relevant live axes for this client**")
    if brief.relevant_axes:
        for a in brief.relevant_axes:
            st.markdown(
                f"{score_badge(a.score)} &nbsp; **Desk {a.desk_side.upper()}** — {a.axe_label}",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No current axes are a strong fit.")
