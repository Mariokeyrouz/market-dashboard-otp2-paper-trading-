"""
Momentum: Single-Stock Cross-Sectional Momentum
================================================
Live view of the momentum strategy — top-20 S&P 500 names by blended 6&12-month
momentum, equal weight, monthly, with a SPY 10-month trend gate for risk control.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Momentum: Cross-Sectional",
    page_icon="🚀",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .strategy-box {
        background: #14001a;
        border-left: 5px solid #b061d6;
        border-radius: 8px;
        padding: 22px 28px;
        margin-bottom: 24px;
        line-height: 1.8;
        font-size: 16px;
        color: #f6ecff;
    }
    .strategy-box h4 {
        margin-top: 0; margin-bottom: 12px; color: #ffffff;
        font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700;
    }
    .strategy-box b { color: #ffffff; }
    .strategy-box ul { color: #f6ecff; }
    .risk-badge-off {
        background: #ff4b4b22; border: 1px solid #ff4b4b; border-radius: 6px;
        padding: 6px 14px; color: #ff4b4b; font-weight: 600; font-size: 14px; display: inline-block;
    }
    .risk-badge-on {
        background: #00c89622; border: 1px solid #00c896; border-radius: 6px;
        padding: 6px 14px; color: #00c896; font-weight: 600; font-size: 14px; display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

LEDGER_PATH    = "momentum_ledger.csv"
STATE_PATH     = "momentum_state.json"
SELECTION_PATH = "momentum_selection.json"


@st.cache_data(ttl=300)
def fetch_live_prices(tickers):
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d", interval="1d")
            if h.empty:
                raise ValueError("no data")
            out[t] = {
                "price":      float(h["Close"].iloc[-1]),
                "prev_close": float(h["Close"].iloc[-2]) if len(h) > 1 else float(h["Close"].iloc[-1]),
            }
        except Exception:
            out[t] = {"price": None, "prev_close": None}
    return out


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🚀 Momentum: Single-Stock Cross-Sectional")

st.markdown("""
<div class="strategy-box">
<h4>Strategy Overview — Momentum (Cross-Sectional)</h4>
An aggressive, return-seeking strategy that buys the market's strongest trending stocks and
rotates monthly. Validated against 21 years of data (beat SPY in both walk-forward halves and
~+11pp/yr vs an equal-weight hold of the same names, net of costs).
<br><br>
<b>Stock Selection — Blended Momentum:</b> Each month, every S&P 500 name is ranked by
<b>blended 6-month + 12-month momentum</b> — each horizon skips the most recent month (to dodge
short-term reversal) and the two are combined by percentile rank so the signal isn't overfit to
one lookback. The <b>top 20</b> are held <b>equal weight</b> (5% each).
<ul style="margin: 8px 0 8px 0; padding-left: 20px;">
  <li><b>Sector cap:</b> no single GICS sector may exceed 8 of 20 names (40%), so one hot theme
  can't quietly become the whole book.</li>
</ul>
<b>Risk Control — SPY Trend Gate:</b> At each monthly rebalance the strategy checks the S&P 500
against its <b>10-month moving average</b>. Above it → <b>risk-on</b>, fully invested in the top-20.
Below it → <b>risk-off</b>, the entire book moves to <b>cash</b> (earning the T-bill rate). This one
overlay cut the backtest's worst drawdown roughly in half.
<br><br>
<b>What this page shows:</b> A live forward simulation seeded on 2026-07-21. Because it trades
today's index going forward, it carries <b>no survivorship bias</b> — the honest test the historical
backtest couldn't give (that universe was today's winners, so its absolute returns were an upper bound).
</div>
""", unsafe_allow_html=True)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Guard: files exist ─────────────────────────────────────────────────────────
if not os.path.exists(LEDGER_PATH):
    st.warning("No momentum ledger found. Run `momentum_screener.py` then `momentum_strategy_engine.py` to seed it.")
    st.stop()
if not os.path.exists(STATE_PATH):
    st.warning("No momentum state file found. Run `momentum_strategy_engine.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)

selection = {}
if os.path.exists(SELECTION_PATH):
    with open(SELECTION_PATH) as f:
        selection = json.load(f)

risk_on = bool(state.get("risk_on", True))

st.caption(f"📅 Ledger last advanced: **{state['last_date']}**  ·  "
           f"📊 Selection as of: **{selection.get('as_of', 'N/A')}**  ·  "
           f"Prices delayed ~15 min, refreshed every 5 min")

# ── Compute metrics ────────────────────────────────────────────────────────────
tickers      = list(state["shares"].keys())
live_prices  = fetch_live_prices(tickers) if tickers else {}
first_nav    = ledger["nav"].iloc[0]

total_market_value = 0.0
total_cost_basis   = 0.0
total_day_pnl      = 0.0
pos_rows = []

for t in tickers:
    shares    = state["shares"][t]
    entry     = state["entry_prices"][t]
    lp        = live_prices.get(t, {})
    last      = lp["price"]      if lp.get("price")      is not None else state.get("last_prices", {}).get(t, entry)
    prev      = lp["prev_close"] if lp.get("prev_close") is not None else last

    cost_basis   = shares * entry
    market_value = shares * last
    unrealized_usd = market_value - cost_basis
    unrealized_pct = (last / entry - 1) * 100
    day_pnl      = shares * (last - prev)
    day_chg_pct  = (last / prev - 1) * 100 if prev else 0.0

    total_market_value += market_value
    total_cost_basis   += cost_basis
    total_day_pnl      += day_pnl

    sd = selection.get("holdings", {}).get(t, {})
    pos_rows.append({
        "Ticker":              t,
        "Sector":              sd.get("sector", ""),
        "Shares":              round(shares, 3),
        "Entry Price":         round(entry, 2),
        "Live Price":          round(last, 2),
        "Day Chg (%)":         round(day_chg_pct, 2),
        "Cost Basis ($)":      round(cost_basis, 2),
        "Market Value ($)":    round(market_value, 2),
        "Unrealized P/L ($)":  round(unrealized_usd, 2),
        "Unrealized P/L (%)":  round(unrealized_pct, 2),
        "Momentum Score":      round(sd.get("score_momentum", 0), 1),
        "6M Return (%)":       sd.get("ret_6m"),
        "12M Return (%)":      sd.get("ret_12m"),
    })

pos_df = pd.DataFrame(pos_rows)
if total_market_value > 0:
    pos_df["Weight (%)"] = (pos_df["Market Value ($)"] / total_market_value * 100).round(1)

live_nav         = total_market_value + state.get("cash_dollars", 0.0)
total_return     = (live_nav / first_nav - 1) * 100
total_unrealized = total_market_value - total_cost_basis
total_pnl        = live_nav - first_nav
realized_pnl     = total_pnl - total_unrealized

running_max = ledger["nav"].cummax()
drawdown    = (ledger["nav"] - running_max) / running_max * 100
max_dd      = drawdown.min()

n = len(ledger)
if n > 2:
    rets   = ledger["daily_log_ret"].iloc[1:]
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
else:
    sharpe = float("nan")

days_live = (ledger["date"].iloc[-1] - ledger["date"].iloc[0]).days

# ── Headline metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Portfolio Value",  f"${live_nav:,.2f}",    f"{total_return:+.2f}% since inception")
c2.metric("Today's P/L",     f"${total_day_pnl:+,.2f}")
c3.metric("Realized P/L",    f"${realized_pnl:+,.2f}")
c4.metric("Invested / Cash", f"{state.get('invested', 0)*100:.0f}% / {(1-state.get('invested', 0))*100:.0f}%")
c5.metric("Max Drawdown",    f"{max_dd:.2f}%")
c6.metric("Sharpe-to-date",  f"{sharpe:.2f}" if not np.isnan(sharpe) else "n/a")
c7.metric("Days Live",       f"{days_live}")

# ── Trend-gate badge ───────────────────────────────────────────────────────────
trend_note = selection.get("trend_note", "SPY vs 10-month SMA")
if risk_on:
    st.markdown(
        f'<div class="risk-badge-on">✅ RISK-ON — fully invested in the top-20 '
        f'({trend_note})</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f'<div class="risk-badge-off">⚠️ RISK-OFF — in cash '
        f'({trend_note}); waiting for the trend to turn back up</div>',
        unsafe_allow_html=True
    )

st.divider()

# ── Risk-off / cash short-circuit ──────────────────────────────────────────────
if not tickers:
    st.subheader("💵 Currently in cash")
    st.info("The SPY trend gate is risk-off, so the strategy holds 100% cash (earning the "
            "T-bill rate) until the S&P 500 climbs back above its 10-month average. No open "
            "positions this month.")
    st.stop()

# ── Positions table ────────────────────────────────────────────────────────────
st.subheader("📋 Positions")
display_pos = pos_df[[
    "Ticker", "Sector", "Weight (%)", "Shares", "Entry Price", "Live Price",
    "Day Chg (%)", "Cost Basis ($)", "Market Value ($)",
    "Unrealized P/L ($)", "Unrealized P/L (%)",
]].copy()

def _color_pl(val):
    return f"color: {'#00c896' if val >= 0 else '#ff4b4b'}; font-weight: 600"

styled = display_pos.style.map(
    _color_pl, subset=["Day Chg (%)", "Unrealized P/L ($)", "Unrealized P/L (%)"]
).format({
    "Weight (%)":         "{:.1f}%",
    "Shares":             "{:.3f}",
    "Entry Price":        "${:.2f}",
    "Live Price":         "${:.2f}",
    "Day Chg (%)":        "{:+.2f}%",
    "Cost Basis ($)":     "${:,.2f}",
    "Market Value ($)":   "${:,.2f}",
    "Unrealized P/L ($)": "${:+,.2f}",
    "Unrealized P/L (%)": "{:+.2f}%",
})
st.dataframe(styled, width='stretch', hide_index=True)

cash = state.get("cash_dollars", 0.0)
st.caption(
    f"💰 Cash: **${cash:,.2f}**  ·  "
    f"📈 Invested: **${total_market_value:,.2f}**  ·  "
    f"📊 Unrealized P/L: **${total_unrealized:+,.2f}** "
    f"({(total_unrealized/total_cost_basis*100):+.2f}%)  ·  "
    f"🔒 Realized P/L: **${realized_pnl:+,.2f}**  ·  "
    f"💸 Cumulative slippage: **${state.get('trading_cost', 0.0):,.2f}**"
)

st.divider()

# ── Momentum scores table ──────────────────────────────────────────────────────
st.subheader("🚀 Momentum Scores")
mom_df = pos_df[["Ticker", "Sector", "Momentum Score", "6M Return (%)", "12M Return (%)"]].copy()

def _color_score(val):
    if pd.isna(val):
        return ""
    if val >= 90:
        return "color: #00c896; font-weight: 600"
    if val <= 50:
        return "color: #ff4b4b"
    return ""

styled_m = mom_df.style.map(_color_score, subset=["Momentum Score"]).format({
    "Momentum Score": "{:.1f}",
    "6M Return (%)":  lambda x: f"{x:+.1f}%" if x is not None else "N/A",
    "12M Return (%)": lambda x: f"{x:+.1f}%" if x is not None else "N/A",
}, na_rep="N/A")
st.dataframe(styled_m, width='stretch', hide_index=True)
st.caption("Momentum Score is the blended 6&12-month percentile rank (0–100); 100 = strongest "
           "trending name in the S&P 500. Returns are trailing total returns as of the last rebalance.")

st.divider()

# ── NAV chart ──────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"],
    mode="lines+markers", line=dict(color="#8e24aa", width=2),
    name="Momentum Portfolio (at close)",
))
fig.add_trace(go.Scatter(
    x=[ledger["date"].iloc[-1]], y=[live_nav], mode="markers",
    marker=dict(color="#00c896", size=10, symbol="star"),
    name="Live (intraday)",
))
if "peak_nav" in ledger.columns:
    fig.add_trace(go.Scatter(
        x=ledger["date"], y=ledger["peak_nav"],
        mode="lines", line=dict(color="#a0a0a0", width=1, dash="dot"),
        name="Peak NAV",
    ))
fig.update_layout(
    height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="NAV ($, start = $10,000)", gridcolor="#2a2a3e", tickformat=","),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width='stretch')

# ── Drawdown chart ──────────────────────────────────────────────────────────────
st.subheader("📉 Drawdown from Peak NAV")
fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(
    x=ledger["date"], y=drawdown, mode="lines", fill="tozeroy",
    line=dict(color="#ff4b4b", width=1.5), fillcolor="rgba(255,75,75,0.15)",
    name="Drawdown",
))
fig_dd.update_layout(
    height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
)
st.plotly_chart(fig_dd, width='stretch')

st.divider()

# ── Daily log ──────────────────────────────────────────────────────────────────
st.subheader("🗒️ Daily Log")
display_log = ledger.copy()
display_log["date"]          = display_log["date"].dt.date
display_log["nav"]           = display_log["nav"].round(2)
display_log["invested_pct"]  = display_log["invested_pct"].round(1)
display_log["daily_log_ret"] = (display_log["daily_log_ret"] * 100).round(3)
if "peak_nav" in display_log.columns:
    display_log["peak_nav"] = display_log["peak_nav"].round(2)
display_log = display_log.rename(columns={
    "nav": "NAV ($)", "invested_pct": "invested %",
    "daily_log_ret": "daily return %", "peak_nav": "peak NAV ($)",
    "risk_on": "risk-on",
})
log_cols = ["date", "NAV ($)", "invested %", "daily return %", "peak NAV ($)", "risk-on"]
log_cols = [c for c in log_cols if c in display_log.columns]
st.dataframe(
    display_log[log_cols].sort_values("date", ascending=False),
    width='stretch', hide_index=True,
    column_config={
        "NAV ($)":         st.column_config.NumberColumn("NAV ($)", format="$%,.2f"),
        "peak NAV ($)":    st.column_config.NumberColumn("peak NAV ($)", format="$%,.2f"),
        "invested %":      st.column_config.NumberColumn("invested %", format="%.1f%%"),
        "daily return %":  st.column_config.NumberColumn("daily return %", format="%.3f%%"),
    },
)

st.caption(
    "Strategy: Single-stock cross-sectional momentum — S&P 500 universe, top 20 by blended "
    "6&12-month momentum (skip most recent month), equal weight, monthly rebalance, 40% sector "
    "cap. Risk control: SPY 10-month trend gate → 100% cash when the index is below its "
    "10-month average. Backtest absolute returns were survivorship-inflated upper bounds; this "
    "live forward test is bias-free."
)
