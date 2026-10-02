"""
Momentum Daily: Single-Stock Cross-Sectional Momentum, Daily Exposure Gate
============================================================================
Same stock-picking as the Momentum strategy. The only difference: the SPY
trend gate is checked every trading day instead of once a month, no VIX, no
smoothing. Backtested as the best-performing variant across a multi-script
investigation into OTP1.0-style timing (see momentum_trend_gate_control.py /
momentum_walkforward_fix_verify.py) — full-sample Sharpe 1.419 vs the
monthly-gated version's 0.841 over 2005-2026.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from blotter import render_blotter

st.set_page_config(
    page_title="Momentum Daily",
    page_icon="⏱️",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .strategy-box {
        background: #1a0010;
        border-left: 5px solid #d6618f;
        border-radius: 8px;
        padding: 22px 28px;
        margin-bottom: 24px;
        line-height: 1.8;
        font-size: 16px;
        color: #ffecf3;
    }
    .strategy-box h4 {
        margin-top: 0; margin-bottom: 12px; color: #ffffff;
        font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700;
    }
    .strategy-box b { color: #ffffff; }
    .strategy-box ul { color: #ffecf3; }
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

LEDGER_PATH    = "momentum_daily_ledger.csv"
STATE_PATH     = "momentum_daily_state.json"
SELECTION_PATH = "momentum_daily_selection.json"


@st.cache_data(ttl=300)
def fetch_live_prices(tickers):
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d", interval="1d")
            close = h["Close"].dropna() if not h.empty else pd.Series(dtype=float)
            if close.empty:
                raise ValueError("no data")
            out[t] = {
                "price":      float(close.iloc[-1]),
                "prev_close": float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1]),
            }
        except Exception:
            out[t] = {"price": None, "prev_close": None}
    return out


@st.cache_data(ttl=3600)
def load_sector_fallback():
    path = "sp500_sectors.csv"
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["Symbol"], df["GICS Sector"]))


@st.cache_data(ttl=21600)
def fetch_sector_via_yfinance(tickers):
    out = {}
    for t in tickers:
        try:
            out[t] = str(yf.Ticker(t).info.get("sector") or "")
        except Exception:
            out[t] = ""
    return out


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("⏱️ Momentum Daily: Daily Exposure Gate")

st.markdown("""
<div class="strategy-box">
<h4>Strategy Overview — Momentum Daily</h4>
Identical stock-picking to the <a href="/Momentum" style="color:#ffb3cf;">Momentum</a> strategy.
The only difference is <b>how often the exposure decision is checked</b> — and that difference
alone backtested as the single best result across a whole investigation into whether OTP1.0-style
timing (VIX triggers, gradual reload) could improve on the existing gate. It couldn't; checking
the identical rule more often did.
<br><br>
<b>Stock Selection — Blended Momentum (unchanged):</b> Every S&P 500 name ranked by
<b>blended 6-month + 12-month momentum</b> (each skipping the most recent month), <b>top 20</b>,
<b>equal weight</b>, 40% sector cap, rotated monthly. This half never checks the market trend at
all — it always proposes the top 20, every month, regardless of regime.
<br><br>
<b>Risk Control — Daily SPY Trend Gate:</b> Every trading day (not just at the monthly rotation),
this engine checks the S&P 500 against its <b>10-month (210 trading day) moving average</b>.
Above it → <b>risk-on</b>, 100% invested in the current top-20. Below it → <b>risk-off</b>, 100%
cash, checked and re-evaluated <b>every single day</b>. No smoothing, no confirmation delay, no
gradual reload — deliberately, since every smoothing variant tested backtested worse than this
plain instant version.
<ul style="margin: 8px 0 8px 0; padding-left: 20px;">
  <li><b>Cash is literal cash — 0% return.</b> Unlike every other strategy in this system, cash
  here does NOT earn the T-bill rate. This is a deliberate choice so the numbers aren't flattered
  by a risk-free carry the backtest comparison didn't credit either.</li>
  <li><b>10 bps slippage</b> is charged on every trade — both the monthly stock rotation and
  every daily entry/exit flip. Because this gate can flip more often than a monthly-only check,
  it pays this cost more often too; that's already priced into the backtest result it's based on.</li>
</ul>
<b>What this page shows:</b> A live forward simulation, no survivorship bias (trades today's
actual index going forward). Backtest reference: full-sample Sharpe 1.419 vs the monthly-gated
version's 0.841 over 2005-2026 (same universe, same survivorship-bias caveat on absolute levels —
read the relative gap, not the CAGR level).
</div>
""", unsafe_allow_html=True)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── Guard: files exist ─────────────────────────────────────────────────────────
if not os.path.exists(LEDGER_PATH):
    st.warning("No Momentum Daily ledger found. Run `momentum_daily_screener.py` then "
               "`momentum_daily_strategy_engine.py` to seed it.")
    st.stop()
if not os.path.exists(STATE_PATH):
    st.warning("No Momentum Daily state file found. Run `momentum_daily_strategy_engine.py` to seed it.")
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
tickers        = list(state["shares"].keys())
live_prices    = fetch_live_prices(tickers) if tickers else {}
sector_fallback = load_sector_fallback()
holdings_meta  = selection.get("holdings", {})
_unresolved    = [t for t in tickers
                  if not (holdings_meta.get(t, {}).get("sector") or sector_fallback.get(t))]
yf_sector_fallback = fetch_sector_via_yfinance(tuple(sorted(_unresolved))) if _unresolved else {}
first_nav      = ledger["nav"].iloc[0]

total_market_value = 0.0
total_cost_basis   = 0.0
total_day_pnl      = 0.0
pos_rows = []

for t in tickers:
    shares    = state["shares"][t]
    entry     = state["entry_prices"][t]
    lp        = live_prices.get(t, {})
    last = lp.get("price")
    if last is None or pd.isna(last):
        last = state.get("last_prices", {}).get(t)
    if last is None or pd.isna(last):
        last = entry
    prev = lp.get("prev_close")
    if prev is None or pd.isna(prev):
        prev = last

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
        "Sector":              sd.get("sector") or sector_fallback.get(t) or yf_sector_fallback.get(t, ""),
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
_wt_denom = total_market_value if (total_market_value and total_market_value > 0) else float("nan")
pos_df["Weight (%)"] = (pos_df["Market Value ($)"] / _wt_denom * 100).round(1)

live_nav         = total_market_value + state.get("cash_dollars", 0.0)
total_return     = (live_nav / first_nav - 1) * 100
total_unrealized = total_market_value - total_cost_basis
total_pnl        = live_nav - first_nav
realized_pnl     = total_pnl - total_unrealized

running_max = ledger["nav"].cummax()
drawdown    = (ledger["nav"] - running_max) / running_max * 100
max_dd      = drawdown.min()

n_flips_total = int((ledger["risk_on"].astype(bool).diff().fillna(False)).sum()) if "risk_on" in ledger.columns else 0

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
c7.metric("Exposure Flips",  f"{n_flips_total}")

# ── Trend-gate badge ───────────────────────────────────────────────────────────
if risk_on:
    st.markdown(
        f'<div class="risk-badge-on">✅ RISK-ON — fully invested in the top-20 '
        f'(SPY above its 210-day SMA, checked today)</div>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f'<div class="risk-badge-off">⚠️ RISK-OFF — in cash (literal, 0% return) '
        f'(SPY below its 210-day SMA, checked today); re-checked every trading day</div>',
        unsafe_allow_html=True
    )

st.divider()

# ── Risk-off / cash short-circuit ──────────────────────────────────────────────
if not tickers:
    st.subheader("💵 Currently in cash")
    st.info("The daily SPY trend gate is risk-off, so the strategy holds 100% cash — literal "
            "cash, earning nothing — until the S&P 500 closes back above its 210-day average. "
            "Re-checked every trading day, not just at the monthly rotation.")
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
    f"💰 Cash (literal, 0%): **${cash:,.2f}**  ·  "
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
           "trending name in the S&P 500. Selection is unconditional — computed the same way "
           "whether the strategy is currently risk-on or risk-off.")

st.divider()

# ── NAV chart ──────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"],
    mode="lines+markers", line=dict(color="#d6618f", width=2),
    name="Momentum Daily Portfolio (at close)",
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
    "cap. Risk control: SPY 210-day trend gate, checked DAILY (not monthly) → 100% literal cash "
    "(0% return) when the index is below its 210-day average. Backtest absolute returns were "
    "survivorship-inflated upper bounds; this live forward test is bias-free."
)

render_blotter("Momentum Daily")
