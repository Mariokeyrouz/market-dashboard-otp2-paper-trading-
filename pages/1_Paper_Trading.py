import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="OTP2.0 v4 - Paper Trading",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        margin: 4px;
    }
    [data-testid="stMetricDelta"] svg { display: none; }
</style>
""", unsafe_allow_html=True)

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


@st.cache_data(ttl=300)
def fetch_live_prices(tickers: list) -> dict:
    """Latest available price + prior close, per ticker."""
    out = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="5d", interval="1d")
            if hist.empty:
                raise ValueError("no data")
            out[t] = {
                "price": float(hist["Close"].iloc[-1]),
                "prev_close": float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Close"].iloc[-1]),
            }
        except Exception:
            out[t] = {"price": None, "prev_close": None}
    return out


# ── Header ───────────────────────────────────────────────────────────────────
st.title("📊 OTP2.0 v4 - Live Paper Trading")
st.caption("Simulated forward test of the v4 strategy (2026-present 'Live' cohort). "
           "No real capital or broker is involved — this tracks what v4 *would* do "
           "starting from go-live, using the same OT2.0 timing engine as the backtest.")

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

st.caption(f"📅 Strategy ledger last advanced for trading day: **{state['last_date']}**  ·  "
           f"💹 Position prices below are live (delayed ~15 min, refreshed every 5 min)")

# ── Headline metrics ────────────────────────────────────────────────────────
first_nav = ledger["nav"].iloc[0]
ledger_last_nav = ledger["nav"].iloc[-1]
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

# ── Live position values (computed once, reused for header + table) ─────────
live_prices = fetch_live_prices(LIVE_TICKERS)
has_positions = "entry_prices" in state and "shares" in state

pos_df = None
total_market_value = 0.0
total_cost_basis = 0.0
total_day_pnl = 0.0
if has_positions:
    pos_rows = []
    for t in LIVE_TICKERS:
        shares = state["shares"][t]
        entry = state["entry_prices"][t]
        live = live_prices.get(t, {})
        last = live["price"] if live.get("price") is not None else state["last_prices"][t]
        prev = live["prev_close"] if live.get("prev_close") is not None else last

        cost_basis = shares * entry
        market_value = shares * last
        unrealized_pct = (last / entry - 1) * 100
        unrealized_usd = market_value - cost_basis
        day_pnl = shares * (last - prev)

        total_market_value += market_value
        total_cost_basis += cost_basis
        total_day_pnl += day_pnl

        pos_rows.append({
            "Ticker": t,
            "Shares": round(shares, 3),
            "Entry Price": round(entry, 2),
            "Live Price": round(last, 2),
            "Day Chg (%)": round((last / prev - 1) * 100, 2) if prev else 0.0,
            "Cost Basis ($)": round(cost_basis, 2),
            "Market Value ($)": round(market_value, 2),
            "Unrealized P/L ($)": round(unrealized_usd, 2),
            "Unrealized P/L (%)": round(unrealized_pct, 2),
        })
    pos_df = pd.DataFrame(pos_rows)
    pos_df["Weight (%)"] = (pos_df["Market Value ($)"] / total_market_value * 100).round(1)

live_nav = total_market_value + state.get("cash_dollars", 0.0)
total_return = (live_nav / first_nav - 1) * 100 if has_positions else (ledger_last_nav / first_nav - 1) * 100
display_nav = live_nav if has_positions else ledger_last_nav

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Portfolio Value", f"${display_nav:,.2f}", f"{total_return:+.2f}% since inception")
c2.metric("Today's P/L", f"${total_day_pnl:+,.2f}" if has_positions else "—")
c3.metric("Invested / Cash", f"{state['invested']*100:.0f}% / {(1-state['invested'])*100:.0f}%")
c4.metric("Max Drawdown", f"{max_dd:.2f}%")
c5.metric("Sharpe-to-date", f"{sharpe:.2f}" if not np.isnan(sharpe) else "n/a")
c6.metric("Days Live", f"{days_live}")

st.divider()

# ── Positions ────────────────────────────────────────────────────────────────
st.subheader("📋 Positions")
if pos_df is not None:
    display_pos = pos_df[[
        "Ticker", "Weight (%)", "Shares", "Entry Price", "Live Price",
        "Day Chg (%)", "Cost Basis ($)", "Market Value ($)",
        "Unrealized P/L ($)", "Unrealized P/L (%)",
    ]].copy()

    def _color_pl(val):
        color = "#00c896" if val >= 0 else "#ff4b4b"
        return f"color: {color}; font-weight: 600"

    styled = display_pos.style.map(
        _color_pl, subset=["Day Chg (%)", "Unrealized P/L ($)", "Unrealized P/L (%)"]
    ).format({
        "Weight (%)": "{:.1f}%",
        "Shares": "{:.3f}",
        "Entry Price": "${:.2f}",
        "Live Price": "${:.2f}",
        "Day Chg (%)": "{:+.2f}%",
        "Cost Basis ($)": "${:,.2f}",
        "Market Value ($)": "${:,.2f}",
        "Unrealized P/L ($)": "${:+,.2f}",
        "Unrealized P/L (%)": "{:+.2f}%",
    })
    st.dataframe(styled, use_container_width=True, hide_index=True)

    cash = state.get("cash_dollars", 0.0)
    total_unrealized = total_market_value - total_cost_basis
    st.caption(
        f"💰 Cash: **${cash:,.2f}**  ·  "
        f"📈 Invested market value: **${total_market_value:,.2f}**  ·  "
        f"📊 Total unrealized P/L: **${total_unrealized:+,.2f}** "
        f"({(total_unrealized/total_cost_basis*100):+.2f}%)  ·  "
        f"💸 Cumulative slippage/fees: **${state.get('trading_cost', 0.0):,.2f}**"
    )
else:
    st.info("Position-level data not available for this ledger (older seed format).")

st.divider()

# ── NAV chart ────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"], mode="lines+markers",
    line=dict(color="#1565c0", width=2), name="OTP2.0 v4 (Paper, as of last close)",
))
if pos_df is not None:
    fig.add_trace(go.Scatter(
        x=[ledger["date"].iloc[-1]], y=[live_nav], mode="markers",
        marker=dict(color="#00c896", size=10, symbol="star"), name="Live (intraday)",
    ))
fig.update_layout(
    height=380,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="NAV ($, start = 10,000)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

# ── Drawdown chart ───────────────────────────────────────────────────────────
st.subheader("📉 Drawdown")
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

# ── Active regime ────────────────────────────────────────────────────────────
st.subheader("⚙️ Active Regime")
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
st.subheader("🗒️ Daily Log")
display_log = ledger.copy()
display_log["date"] = display_log["date"].dt.date
display_log["nav"] = display_log["nav"].round(2)
display_log["invested_pct"] = display_log["invested_pct"].round(1)
display_log["daily_log_ret"] = (display_log["daily_log_ret"] * 100).round(3)
display_log = display_log.rename(columns={
    "nav": "NAV ($)", "invested_pct": "invested %", "daily_log_ret": "daily return %",
})
st.dataframe(display_log[["date", "NAV ($)", "invested %", "daily return %", "regime"]]
             .sort_values("date", ascending=False), use_container_width=True, hide_index=True)

st.caption("Strategy: OTP2.0 v4 (54-stock universe, 3yr cohorts, top-7 selection, "
           "5-factor composite + regime tertile + CAPE froth override, layered on "
           "the OTP1.0 daily timing engine). See OTP2.0_v4_investment_thesis.pdf for "
           "full backtest methodology and results.")
