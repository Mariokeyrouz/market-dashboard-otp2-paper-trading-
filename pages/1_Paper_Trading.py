import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="OTP2.0 v4 - Paper Trading",
    page_icon="📊",
    layout="wide",
)

# ── Access gate ──────────────────────────────────────────────────────────────
required_pw = st.secrets.get("PAPER_TRADING_PASSWORD") if hasattr(st, "secrets") else None
if required_pw:
    if "authed" not in st.session_state:
        st.session_state["authed"] = False
    if not st.session_state["authed"]:
        st.title("📊 OTP2.0 v4 - Paper Trading")
        pw = st.text_input("Access password", type="password")
        if st.button("Enter"):
            if pw == required_pw:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

LEDGER_PATH = "paper_ledger.csv"
STATE_PATH = "paper_state.json"
LIVE_TICKERS = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]

st.title("📊 OTP2.0 v4 - Live Paper Trading")
st.caption("Simulated forward test of the v4 strategy (2026-present 'Live' cohort). "
           "No real capital or broker is involved — this tracks what v4 *would* do "
           "starting from go-live, using the same OT2.0 timing engine as the backtest. "
           "The ledger updates once per weekday after US market close.")

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

if not os.path.exists(LEDGER_PATH):
    st.warning("No paper-trading ledger found yet. Run `paper_trading_engine.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)

st.caption(f"📅 Ledger last updated for trading day: **{state['last_date']}**")

# ── Headline metrics ────────────────────────────────────────────────────────
first_nav = ledger["nav"].iloc[0]
last_nav = ledger["nav"].iloc[-1]
total_return = (last_nav / first_nav - 1) * 100
days_live = (ledger["date"].iloc[-1] - ledger["date"].iloc[0]).days

running_max = ledger["nav"].cummax()
drawdown = (ledger["nav"] - running_max) / running_max * 100
max_dd = drawdown.min()

n = len(ledger)
if n > 2:
    rets = ledger["daily_log_ret"].iloc[1:]
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
else:
    sharpe = float("nan")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Current NAV", f"{last_nav:.2f}", f"{total_return:+.2f}%")
col2.metric("Invested %", f"{state['invested']*100:.1f}%")
col3.metric("Cash %", f"{(1 - state['invested'])*100:.1f}%")
col4.metric("Max Drawdown", f"{max_dd:.2f}%")
col5.metric("Days Live", f"{days_live}")

if not np.isnan(sharpe):
    st.caption(f"Annualized Sharpe-to-date: {sharpe:.3f}  |  Last updated: {state['last_date']}")
else:
    st.caption(f"Last updated: {state['last_date']}  (Sharpe needs more history)")

st.divider()

# ── NAV chart ────────────────────────────────────────────────────────────────
st.subheader("NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"], mode="lines+markers",
    line=dict(color="#1565c0", width=2), name="OTP2.0 v4 (Paper)",
))
fig.update_layout(
    height=380,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="NAV (start = 100)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
)
st.plotly_chart(fig, use_container_width=True)

# ── Drawdown chart ───────────────────────────────────────────────────────────
st.subheader("Drawdown")
fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(
    x=ledger["date"], y=drawdown, mode="lines", fill="tozeroy",
    line=dict(color="#ff4b4b", width=1.5), fillcolor="rgba(255,75,75,0.15)",
    name="Drawdown",
))
fig_dd.update_layout(
    height=260,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
)
st.plotly_chart(fig_dd, use_container_width=True)

st.divider()

# ── Positions ────────────────────────────────────────────────────────────────
st.subheader("Positions")
if "entry_prices" in state and "shares" in state and "last_prices" in state:
    pos_rows = []
    for t in LIVE_TICKERS:
        shares = state["shares"][t]
        entry = state["entry_prices"][t]
        last = state["last_prices"][t]
        cost_basis = shares * entry
        market_value = shares * last
        unrealized_pct = (last / entry - 1) * 100
        pos_rows.append({
            "Ticker": t,
            "Shares": round(shares, 4),
            "Entry Price": round(entry, 2),
            "Last Price": round(last, 2),
            "Cost Basis ($)": round(cost_basis, 2),
            "Market Value ($)": round(market_value, 2),
            "Unrealized G/L (%)": round(unrealized_pct, 2),
        })
    pos_df = pd.DataFrame(pos_rows)
    st.dataframe(pos_df, use_container_width=True, hide_index=True)
    st.caption(f"Cash position: **${state['cash_dollars']:,.2f}**  |  "
               f"Total invested market value: **${pos_df['Market Value ($)'].sum():,.2f}**")
else:
    st.info("Position-level data not available for this ledger (older seed format).")

st.divider()

# ── Current allocation & regime ─────────────────────────────────────────────
col_alloc, col_regime = st.columns(2)
with col_alloc:
    st.subheader("Current Allocation")
    st.write(f"**Invested:** {state['invested']*100:.1f}%  |  **Cash:** {(1-state['invested'])*100:.1f}%")
    st.write("**Holdings (equal-weighted):**")
    for t in LIVE_TICKERS:
        st.write(f"- {t}")

with col_regime:
    st.subheader("Active Regime")
    st.write(f"**Config:** {ledger['regime'].iloc[-1]}")
    st.write(
        "The 2026-present cohort was selected with mean composite score 0.863 "
        "(would qualify for the 'Momentum' tier), but the Shiller CAPE override "
        "(~38.0, top decile of its historical range) forces the Defensive "
        "config — tighter vol target (0.06) and smaller reload steps (0.03) — "
        "regardless of momentum strength."
    )
    st.write("**Next re-selection:** January 2029 (3-year cohort cadence).")

st.divider()

# ── Daily log ────────────────────────────────────────────────────────────────
st.subheader("Daily Log")
display_log = ledger.copy()
display_log["date"] = display_log["date"].dt.date
display_log["nav"] = display_log["nav"].round(3)
display_log["invested_pct"] = display_log["invested_pct"].round(1)
display_log["daily_log_ret"] = (display_log["daily_log_ret"] * 100).round(3)
display_log = display_log.rename(columns={
    "invested_pct": "invested %", "daily_log_ret": "daily return %",
})
st.dataframe(display_log[["date", "nav", "invested %", "daily return %", "regime"]]
             .sort_values("date", ascending=False), use_container_width=True, hide_index=True)

st.caption("Strategy: OTP2.0 v4 (54-stock universe, 3yr cohorts, top-7 selection, "
           "5-factor composite + regime tertile + CAPE froth override, layered on "
           "the OTP1.0 daily timing engine). See OTP2.0_v4_investment_thesis.pdf for "
           "full backtest methodology and results.")
