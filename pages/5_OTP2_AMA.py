"""
OTP2.0 AMA — AlphaMind Adjusted
================================
Streamlit dashboard for the OTP2.0 AMA paper-trading engine.
State: paper_state_AMA.json | Ledger: paper_ledger_AMA.csv
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="OTP2.0 AMA — AlphaMind Adjusted",
    page_icon="🧠",
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
    .strategy-box {
        background: #0d2137;
        border-left: 5px solid #42a5f5;
        border-radius: 8px;
        padding: 22px 28px;
        margin-bottom: 24px;
        line-height: 1.8;
        font-size: 16px;
        color: #e8f0fe;
    }
    .strategy-box h4 {
        margin-top: 0;
        margin-bottom: 12px;
        color: #ffffff;
        font-size: 13px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 700;
    }
    .strategy-box b { color: #ffffff; }
    .strategy-box ul { color: #e8f0fe; }
    .ama-tag {
        display: inline-block;
        background: #1a3a5c;
        border: 1px solid #42a5f5;
        border-radius: 4px;
        padding: 2px 10px;
        font-size: 12px;
        font-weight: 700;
        color: #90caf9;
        letter-spacing: 0.08em;
        margin-left: 10px;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)


LEDGER_PATH  = "paper_ledger_AMA.csv"
STATE_PATH   = "paper_state_AMA.json"
LIVE_TICKERS = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]


@st.cache_data(ttl=300)
def fetch_live_prices(tickers: list) -> dict:
    out = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="5d", interval="1d")
            if hist.empty:
                raise ValueError("no data")
            out[t] = {
                "price":      float(hist["Close"].iloc[-1]),
                "prev_close": float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Close"].iloc[-1]),
            }
        except Exception:
            out[t] = {"price": None, "prev_close": None}
    return out


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🧠 OTP2.0 AMA — AlphaMind Adjusted")

st.markdown("""
<div class="strategy-box">
<h4>Strategy Overview — OTP2.0 AMA <span class="ama-tag">ALPHAMIND ADJUSTED</span></h4>
OTP2.0 AMA runs the same two-pillar architecture as OTP2.0 (Out-Timing + Out-Pacing) with two
targeted additions to the timing engine, recommended by AlphaMind after an independent review
of regime behaviour during the 2022 market cycle.
<br><br>
<b>What's the same:</b> The stock selection model (7 stocks, 5-factor composite, 3-year cohort,
Defensive CAPE override), the trim thresholds, the vol-targeting logic, and all reload parameters
are identical to the original OTP2.0 engine. The AMA modifications are purely reload filters.
<br><br>
<b>Addition 1 — VIX Term Structure Filter:</b> The VIX3M/VIX ratio measures the shape of the
volatility term structure. When short-dated fear (VIX) exceeds 3-month volatility (VIX3M), the
ratio falls below 1.0, signalling an inverted vol surface — the market is pricing acute near-term
stress above longer-run uncertainty. During such episodes, reloading into equity is premature.
The AMA engine blocks all reloads when the 3-day smoothed VIX3M/VIX ratio is below 1.0. This
filter would have prevented the costly July 2022 re-entry into a bear market false recovery.
<br><br>
<b>Addition 2 — Minimum Dwell Time (20 days):</b> After a trim fires, the AMA engine requires at
least 20 calendar days to elapse before any reload is permitted. The original 3-day cooldown debounces
same-week signal noise; the 20-day dwell gate enforces regime persistence — confirming the market
has genuinely recovered rather than bounced briefly. Both gates run in parallel from the trim date;
both must be satisfied before reloading begins.
<br><br>
<b>What this page shows:</b> A forward simulation tracking the AMA variant in real market conditions
from the same start date as OTP2.0. Compare directly to the OTP2.0 page to measure the impact of
the two additions.
</div>
""", unsafe_allow_html=True)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

if not os.path.exists(LEDGER_PATH):
    st.warning("No AMA paper-trading ledger found. Run `paper_trading_engine_AMA.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)

st.caption(f"📅 Strategy ledger last advanced: **{state['last_date']}**  ·  "
           f"💹 Position prices below are live (delayed ~15 min, refreshed every 5 min)")

# ── Headline metrics ──────────────────────────────────────────────────────────
first_nav       = ledger["nav"].iloc[0]
ledger_last_nav = ledger["nav"].iloc[-1]
days_live       = (ledger["date"].iloc[-1] - ledger["date"].iloc[0]).days

running_max = ledger["nav"].cummax()
drawdown    = (ledger["nav"] - running_max) / running_max * 100
max_dd      = drawdown.min()

n = len(ledger)
if n > 2:
    rets   = ledger["daily_log_ret"].iloc[1:]
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
else:
    sharpe = float("nan")

live_prices = fetch_live_prices(LIVE_TICKERS)
has_positions = "entry_prices" in state and "shares" in state

pos_df = None
total_market_value = 0.0
total_cost_basis   = 0.0
total_day_pnl      = 0.0

if has_positions:
    pos_rows = []
    for t in LIVE_TICKERS:
        shares = state["shares"][t]
        entry  = state["entry_prices"][t]
        live   = live_prices.get(t, {})
        last   = live["price"]      if live.get("price")      is not None else state["last_prices"][t]
        prev   = live["prev_close"] if live.get("prev_close") is not None else last

        cost_basis    = shares * entry
        market_value  = shares * last
        unrealized_pct = (last / entry - 1) * 100
        unrealized_usd = market_value - cost_basis
        day_pnl       = shares * (last - prev)

        total_market_value += market_value
        total_cost_basis   += cost_basis
        total_day_pnl      += day_pnl

        pos_rows.append({
            "Ticker":              t,
            "Shares":              round(shares, 3),
            "Entry Price":         round(entry, 2),
            "Live Price":          round(last, 2),
            "Day Chg (%)":         round((last / prev - 1) * 100, 2) if prev else 0.0,
            "Cost Basis ($)":      round(cost_basis, 2),
            "Market Value ($)":    round(market_value, 2),
            "Unrealized P/L ($)":  round(unrealized_usd, 2),
            "Unrealized P/L (%)":  round(unrealized_pct, 2),
        })
    pos_df = pd.DataFrame(pos_rows)
    pos_df["Weight (%)"] = (pos_df["Market Value ($)"] / total_market_value * 100).round(1)

live_nav     = total_market_value + state.get("cash_dollars", 0.0)
total_return = (live_nav / first_nav - 1) * 100 if has_positions else (ledger_last_nav / first_nav - 1) * 100
display_nav  = live_nav if has_positions else ledger_last_nav

total_unrealized = total_market_value - total_cost_basis
total_pnl        = display_nav - first_nav
realized_pnl     = total_pnl - total_unrealized

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Portfolio Value", f"${display_nav:,.2f}", f"{total_return:+.2f}% since inception")
c2.metric("Today's P/L",    f"${total_day_pnl:+,.2f}" if has_positions else "—")
c3.metric("Realized P/L",   f"${realized_pnl:+,.2f}")
c4.metric("Invested / Cash", f"{state['invested']*100:.0f}% / {(1-state['invested'])*100:.0f}%")
c5.metric("Max Drawdown",   f"{max_dd:.2f}%")
c6.metric("Sharpe-to-date", f"{sharpe:.2f}" if not np.isnan(sharpe) else "n/a")
c7.metric("Days Live",      f"{days_live}")

# ── AMA-specific state indicators ─────────────────────────────────────────────
trim_date  = state.get("trim_date")
cooldown   = state.get("cooldown_days", 0)
dwell_ok   = True
if trim_date:
    days_since = (pd.Timestamp.today() - pd.Timestamp(trim_date)).days
    dwell_ok   = days_since >= 20

col_g1, col_g2, col_g3 = st.columns(3)
col_g1.metric("Dwell Gate",
              "Open" if dwell_ok else f"Blocked ({(pd.Timestamp.today() - pd.Timestamp(trim_date)).days if trim_date else 0}d / 20d)",
              help="Reload blocked for 20 days after a trim fires")
col_g2.metric("Cooldown",
              f"{cooldown}d remaining" if cooldown > 0 else "Clear",
              help="3-day same-week debounce, independent of dwell")
col_g3.metric("Trim Date",
              trim_date if trim_date else "None",
              help="Date of last trim (both gates restart from here)")

st.divider()

# ── Positions ─────────────────────────────────────────────────────────────────
st.subheader("📋 Positions")
if pos_df is not None:
    display_pos = pos_df[[
        "Ticker", "Weight (%)", "Shares", "Entry Price", "Live Price",
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
else:
    st.info("Position-level data not available (older seed format).")

st.divider()

# ── NAV chart ─────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"], mode="lines+markers",
    line=dict(color="#1565c0", width=2), name="OTP2.0 AMA (as of last close)",
))
if pos_df is not None:
    fig.add_trace(go.Scatter(
        x=[ledger["date"].iloc[-1]], y=[live_nav], mode="markers",
        marker=dict(color="#00c896", size=10, symbol="star"), name="Live (intraday)",
    ))
fig.update_layout(
    height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="NAV ($, start = 10,000)", gridcolor="#2a2a3e", tickformat=","),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

# ── Drawdown chart ────────────────────────────────────────────────────────────
st.subheader("📉 Drawdown")
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
st.plotly_chart(fig_dd, use_container_width=True)

st.divider()

# ── Active regime ─────────────────────────────────────────────────────────────
st.subheader("⚙️ Active Regime")
st.write(f"**Config:** {ledger['regime'].iloc[-1]}" if 'regime' in ledger.columns else "**Config:** DEFENSIVE_OT2")
st.write(
    "Defensive regime active (Shiller CAPE ~38, top decile override). "
    "AMA filters add two reload gates on top of the base engine — both must clear before any reload step executes."
)

st.divider()

# ── Daily log ─────────────────────────────────────────────────────────────────
st.subheader("🗒️ Daily Log")
display_log = ledger.copy()
display_log["date"]          = display_log["date"].dt.date
display_log["nav"]           = display_log["nav"].round(2)
display_log["invested_pct"]  = display_log["invested_pct"].round(1)
display_log["daily_log_ret"] = (display_log["daily_log_ret"] * 100).round(3)
display_log = display_log.rename(columns={
    "nav": "NAV ($)", "invested_pct": "invested %", "daily_log_ret": "daily return %",
})

base_cols  = ["date", "NAV ($)", "invested %", "daily return %"]
extra_cols = [c for c in ["regime", "stopped_dwell", "stopped_term"] if c in display_log.columns]
show_cols  = base_cols + extra_cols
st.dataframe(
    display_log[show_cols].sort_values("date", ascending=False),
    use_container_width=True, hide_index=True,
    column_config={
        "NAV ($)":        st.column_config.NumberColumn("NAV ($)", format="$%,.2f"),
        "invested %":     st.column_config.NumberColumn("invested %", format="%.1f%%"),
        "daily return %": st.column_config.NumberColumn("daily return %", format="%.3f%%"),
    },
)

st.caption(
    "Strategy: OTP2.0 AMA — same 7-stock portfolio and timing engine as OTP2.0, "
    "plus two AlphaMind-recommended reload gates: VIX3M/VIX term structure filter (ratio >= 1.0) "
    "and 20-day post-trim dwell time."
)
