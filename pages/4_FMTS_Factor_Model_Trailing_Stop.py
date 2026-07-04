"""
FMTS: Factor Model Trailing Stop
=================================
Live view of the aggressive factor portfolio with trailing stop risk management.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="FMTS: Factor Model Trailing Stop",
    page_icon="🎯",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .stop-badge-stopped {
        background: #ff4b4b22; border: 1px solid #ff4b4b;
        border-radius: 6px; padding: 6px 14px;
        color: #ff4b4b; font-weight: 600; font-size: 14px;
        display: inline-block;
    }
    .stop-badge-active {
        background: #00c89622; border: 1px solid #00c896;
        border-radius: 6px; padding: 6px 14px;
        color: #00c896; font-weight: 600; font-size: 14px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

LEDGER_PATH    = "factor_ledger.csv"
STATE_PATH     = "factor_state.json"
SELECTION_PATH = "factor_selection.json"


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
st.title("🎯 FMTS: Factor Model Trailing Stop")
st.caption(
    "Factor-score-weighted portfolio (Relative Momentum vs SPX, Quality, Value, Low Volatility) "
    "with a 9% portfolio-level trailing stop. Re-entry on volatility collapse (rvol20 < rvol_sma60)."
)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Guard: check files exist ───────────────────────────────────────────────────
if not os.path.exists(LEDGER_PATH):
    st.warning("No factor ledger found. Run `factor_screener.py` then `factor_strategy_engine.py` to seed it.")
    st.stop()

if not os.path.exists(STATE_PATH):
    st.warning("No factor state file found. Run `factor_strategy_engine.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)

selection = {}
if os.path.exists(SELECTION_PATH):
    with open(SELECTION_PATH) as f:
        selection = json.load(f)

st.caption(f"📅 Ledger last advanced: **{state['last_date']}**  ·  "
           f"📊 Selection as of: **{selection.get('as_of', 'N/A')}**  ·  "
           f"Prices delayed ~15 min, refreshed every 5 min")

# ── Compute metrics ────────────────────────────────────────────────────────────
tickers      = list(state["shares"].keys())
live_prices  = fetch_live_prices(tickers)
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

    score_data = selection.get("holdings", {}).get(t, {})
    pos_rows.append({
        "Ticker":              t,
        "Sector":              score_data.get("sector", ""),
        "Shares":              round(shares, 3),
        "Entry Price":         round(entry, 2),
        "Live Price":          round(last, 2),
        "Day Chg (%)":         round(day_chg_pct, 2),
        "Cost Basis ($)":      round(cost_basis, 2),
        "Market Value ($)":    round(market_value, 2),
        "Unrealized P/L ($)":  round(unrealized_usd, 2),
        "Unrealized P/L (%)":  round(unrealized_pct, 2),
        "Score":               round(score_data.get("score_composite", 0), 1),
        "Momentum":            round(score_data.get("score_momentum", 0), 1),
        "Quality":             round(score_data.get("score_quality", 0), 1),
        "Value":               round(score_data.get("score_value", 0), 1),
        "Low Vol":             round(score_data.get("score_low_vol", 0), 1),
        "RS-Ratio":            score_data.get("rs_ratio"),
        "RS-Mom":              score_data.get("rs_momentum"),
    })

pos_df = pd.DataFrame(pos_rows)
if total_market_value > 0:
    pos_df["Weight (%)"] = (pos_df["Market Value ($)"] / total_market_value * 100).round(1)

live_nav       = total_market_value + state.get("cash_dollars", 0.0)
total_return   = (live_nav / first_nav - 1) * 100
total_unrealized = total_market_value - total_cost_basis
total_pnl      = live_nav - first_nav
realized_pnl   = total_pnl - total_unrealized

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
c4.metric("Invested / Cash", f"{state['invested']*100:.0f}% / {(1-state['invested'])*100:.0f}%")
c5.metric("Max Drawdown",    f"{max_dd:.2f}%")
c6.metric("Sharpe-to-date",  f"{sharpe:.2f}" if not np.isnan(sharpe) else "n/a")
c7.metric("Days Live",       f"{days_live}")

# ── Stop status badge ──────────────────────────────────────────────────────────
stopped = state.get("stopped_out", False)
stop_date = state.get("stop_date", "")
peak_nav  = state.get("peak_nav", live_nav)
dd_from_peak = (peak_nav - live_nav) / peak_nav * 100 if peak_nav > 0 else 0.0

if stopped:
    st.markdown(
        f'<div class="stop-badge-stopped">⚠️ TRAILING STOP ACTIVE — 50% invested '
        f'(triggered {stop_date}, peak NAV ${peak_nav:,.2f}, '
        f'current drawdown {dd_from_peak:.1f}%)</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f'<div class="stop-badge-active">✅ FULLY INVESTED — '
        f'Peak NAV ${peak_nav:,.2f} · Current drawdown {dd_from_peak:.1f}%</div>',
        unsafe_allow_html=True
    )

st.divider()

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
st.dataframe(styled, use_container_width=True, hide_index=True)

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

# ── Factor scores table ────────────────────────────────────────────────────────
st.subheader("🧪 Factor Scores")
factor_df = pos_df[["Ticker", "Sector", "Score", "Momentum", "Quality", "Value", "Low Vol",
                     "RS-Ratio", "RS-Mom"]].copy()

def _color_score(val):
    if pd.isna(val):
        return ""
    if val >= 70:
        return "color: #00c896; font-weight: 600"
    if val <= 35:
        return "color: #ff4b4b"
    return ""

styled_f = factor_df.style.map(
    _color_score, subset=["Score", "Momentum", "Quality", "Value", "Low Vol"]
).format({
    "Score":    "{:.1f}",
    "Momentum": "{:.1f}",
    "Quality":  "{:.1f}",
    "Value":    "{:.1f}",
    "Low Vol":  "{:.1f}",
    "RS-Ratio": lambda x: f"{x:.1f}" if x is not None else "N/A",
    "RS-Mom":   lambda x: f"{x:.1f}" if x is not None else "N/A",
}, na_rep="N/A")
st.dataframe(styled_f, use_container_width=True, hide_index=True)
st.caption("Scores are percentile ranks 0–100. RS-Ratio > 100 = outperforming SPX; "
           "RS-Momentum > 100 = acceleration vs SPX (RRG 'Leading' quadrant).")

st.divider()

# ── NAV chart ──────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")

# Mark stop periods in ledger
stop_mask = ledger.get("stopped_out", pd.Series([False]*len(ledger), dtype=bool))

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"],
    mode="lines+markers", line=dict(color="#1565c0", width=2),
    name="Factor Portfolio (at close)",
))
# Mark stop-triggered days
stop_dates = ledger[ledger.get("stopped_out", False) == True]["date"] if "stopped_out" in ledger.columns else []
if len(stop_dates):
    stop_navs = ledger[ledger["stopped_out"] == True]["nav"]
    fig.add_trace(go.Scatter(
        x=stop_dates, y=stop_navs, mode="markers",
        marker=dict(color="#ff4b4b", size=8, symbol="x"),
        name="Stop active",
    ))
fig.add_trace(go.Scatter(
    x=[ledger["date"].iloc[-1]], y=[live_nav], mode="markers",
    marker=dict(color="#00c896", size=10, symbol="star"),
    name="Live (intraday)",
))
# Peak NAV reference line
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
st.plotly_chart(fig, use_container_width=True)

# ── Drawdown chart ──────────────────────────────────────────────────────────────
st.subheader("📉 Drawdown from Peak NAV")
fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(
    x=ledger["date"], y=drawdown, mode="lines", fill="tozeroy",
    line=dict(color="#ff4b4b", width=1.5), fillcolor="rgba(255,75,75,0.15)",
    name="Drawdown",
))
fig_dd.add_hline(y=-9.0, line_dash="dot", line_color="#ff8800",
                  annotation_text="Stop threshold (9%)", annotation_position="bottom right")
fig_dd.update_layout(
    height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
)
st.plotly_chart(fig_dd, use_container_width=True)

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
    "stopped_out": "stop active",
})
log_cols = ["date", "NAV ($)", "invested %", "daily return %", "peak NAV ($)", "stop active"]
log_cols = [c for c in log_cols if c in display_log.columns]
st.dataframe(
    display_log[log_cols].sort_values("date", ascending=False),
    use_container_width=True, hide_index=True,
    column_config={
        "NAV ($)":         st.column_config.NumberColumn("NAV ($)", format="$%,.2f"),
        "peak NAV ($)":    st.column_config.NumberColumn("peak NAV ($)", format="$%,.2f"),
        "invested %":      st.column_config.NumberColumn("invested %", format="%.1f%%"),
        "daily return %":  st.column_config.NumberColumn("daily return %", format="%.3f%%"),
    },
)

st.caption(
    "Strategy: Factor Portfolio — S&P 500 + Russell 1000 universe, "
    "top 18 stocks by 4-factor composite score (Relative Momentum vs SPX / RRG-inspired, "
    "Quality, Value, Low Volatility), factor-score weighted, rebalanced monthly. "
    "Risk control: 9% portfolio trailing stop → 50% invested; "
    "re-entry on realized vol collapse (rvol20 < 60-day SMA)."
)
