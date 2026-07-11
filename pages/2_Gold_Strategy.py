import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Gold Strategy - Paper Trading",
    page_icon="🥇",
    layout="wide",
)

st.markdown("""
<style>
    .metric-card { background:#1e1e2e; border-radius:10px; padding:16px; margin:4px; }
    [data-testid="stMetricDelta"] svg { display:none; }
    .signal-on  { background:#0d3d27; color:#00c896; border-radius:6px;
                  padding:4px 14px; font-weight:700; font-size:0.9rem; display:inline-block; }
    .signal-off { background:#2a2a3e; color:#aaa; border-radius:6px;
                  padding:4px 14px; font-weight:700; font-size:0.9rem; display:inline-block; }
    .signal-partial { background:#3d2e00; color:#f0a000; border-radius:6px;
                      padding:4px 14px; font-weight:700; font-size:0.9rem; display:inline-block; }
    .stop-safe   { background:#0d3d27; color:#00c896; border-radius:6px; padding:6px 14px; }
    .stop-warn   { background:#3d2e00; color:#f0a000; border-radius:6px; padding:6px 14px; }
    .stop-active { background:#3d0d0d; color:#ff4b4b; border-radius:6px; padding:6px 14px; }
</style>
""", unsafe_allow_html=True)

# ── Access gate ───────────────────────────────────────────────────────────────
try:
    required_pw = st.secrets.get("PAPER_TRADING_PASSWORD")
except Exception:
    required_pw = None
if required_pw:
    if "authed" not in st.session_state:
        st.session_state["authed"] = False
    if not st.session_state["authed"]:
        st.title("🥇 Gold Strategy - Paper Trading")
        pw = st.text_input("Access password", type="password")
        if st.button("Enter"):
            if pw == required_pw:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

LEDGER_PATH = "gold_ledger.csv"
STATE_PATH  = "gold_state.json"
SLIPPAGE    = 0.001
STOP_PCT    = 0.05
TIPS_WIN    = 60
DXY_WIN     = 150


@st.cache_data(ttl=300)
def fetch_live_gld():
    try:
        h = yf.Ticker("GLD").history(period="5d", interval="1d")
        if h.empty or len(h) < 2:
            return None, None
        return float(h["Close"].iloc[-1]), float(h["Close"].iloc[-2])
    except Exception:
        return None, None


@st.cache_data(ttl=3600)
def fetch_signals_live():
    """Fetch current TIPS and DXY values for the signal panel."""
    try:
        import pandas_datareader.data as web
        from datetime import datetime, timedelta
        end   = datetime.today()
        start = end - timedelta(days=365)
        tips_df = web.DataReader("DFII10", "fred", start, end).iloc[:, 0].dropna()
        tips_sma = tips_df.rolling(TIPS_WIN).mean()
        tips_val  = float(tips_df.iloc[-1])
        tips_sma_val = float(tips_sma.iloc[-1]) if not pd.isna(tips_sma.iloc[-1]) else None
        tips_falling = tips_val < tips_sma_val if tips_sma_val else None
    except Exception:
        tips_val, tips_sma_val, tips_falling = None, None, None

    try:
        dxy = yf.Ticker("DX-Y.NYB").history(period="500d", interval="1d")["Close"].squeeze()
        dxy_sma = dxy.rolling(DXY_WIN).mean()
        dxy_val  = float(dxy.iloc[-1])
        dxy_sma_val = float(dxy_sma.iloc[-1]) if not pd.isna(dxy_sma.iloc[-1]) else None
        dxy_weak = dxy_val < dxy_sma_val if dxy_sma_val else None
    except Exception:
        dxy_val, dxy_sma_val, dxy_weak = None, None, None

    return {
        "tips_val": tips_val, "tips_sma": tips_sma_val, "tips_falling": tips_falling,
        "dxy_val":  dxy_val,  "dxy_sma":  dxy_sma_val,  "dxy_weak":     dxy_weak,
    }


# ── Load data ─────────────────────────────────────────────────────────────────
st.title("🥇 Gold Strategy — Live Paper Trading")
st.caption(
    "TIPS direction × DXY filter + 5% trailing stop on GLD ETF.  "
    "Backtested Sharpe 1.165 · Sortino 1.075 · MaxDD −9.78% (2003–2026, 32 stop events)."
)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

if not os.path.exists(LEDGER_PATH) or not os.path.exists(STATE_PATH):
    st.warning("No gold strategy ledger found. Run `gold_strategy_engine.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)

st.caption(
    f"📅 Ledger last updated: **{state['last_date']}**  ·  "
    f"💹 Live GLD price refreshed every 5 min"
)

# ── Live price ────────────────────────────────────────────────────────────────
live_price, prev_close = fetch_live_gld()
gld_price = live_price or state["last_gld_price"]
prev_price = prev_close or state["last_gld_price"]

in_pos     = state["in_position"]
stop_act   = state["stop_active"]
gld_shares = state.get("gld_shares", 0.0)
entry_price = state.get("entry_price")
hwm         = state.get("hwm")
cash        = state.get("cash_dollars", START_NAV := 10000.0)

market_value = gld_shares * gld_price if in_pos else 0.0
live_nav     = market_value + cash
day_pnl      = gld_shares * (gld_price - prev_price) if in_pos else 0.0
first_nav    = ledger["nav"].iloc[0]
total_ret    = (live_nav / first_nav - 1) * 100

running_max = ledger["nav"].cummax()
drawdown    = (ledger["nav"] - running_max) / running_max * 100
max_dd      = drawdown.min()
days_live   = (ledger["date"].iloc[-1] - ledger["date"].iloc[0]).days

# ── Headline metrics ──────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Portfolio Value",  f"${live_nav:,.2f}", f"{total_ret:+.2f}% since inception")
c2.metric("Today's P/L",      f"${day_pnl:+,.2f}" if in_pos else "—")
c3.metric("Position",         "In GLD" if in_pos else ("Stop-Wait" if stop_act else "Cash"))
c4.metric("Stop Level",       f"${hwm*(1-0.05):,.2f}" if hwm else "—",
          f"HWM ${hwm:,.2f}" if hwm else None)
c5.metric("Max Drawdown",     f"{max_dd:.2f}%")
c6.metric("Days Live",        str(days_live))

st.divider()

# ── Position card ─────────────────────────────────────────────────────────────
st.subheader("📋 Current Position")
if in_pos and entry_price:
    cost_basis    = gld_shares * entry_price
    unreal_usd    = market_value - cost_basis
    unreal_pct    = (gld_price / entry_price - 1) * 100
    day_chg_pct   = (gld_price / prev_price - 1) * 100 if prev_price else 0.0

    pos_data = pd.DataFrame([{
        "Ticker":             "GLD",
        "Shares":             round(gld_shares, 4),
        "Entry Price":        round(entry_price, 2),
        "Live Price":         round(gld_price, 2),
        "Day Chg (%)":        round(day_chg_pct, 2),
        "Cost Basis ($)":     round(cost_basis, 2),
        "Market Value ($)":   round(market_value, 2),
        "Unrealized P/L ($)": round(unreal_usd, 2),
        "Unrealized P/L (%)": round(unreal_pct, 2),
    }])

    def _color(val):
        return f"color:{'#00c896' if val >= 0 else '#ff4b4b'};font-weight:600"

    styled = pos_data.style.map(
        _color, subset=["Day Chg (%)", "Unrealized P/L ($)", "Unrealized P/L (%)"]
    ).format({
        "Shares":             "{:.4f}",
        "Entry Price":        "${:.2f}",
        "Live Price":         "${:.2f}",
        "Day Chg (%)":        "{:+.2f}%",
        "Cost Basis ($)":     "${:,.2f}",
        "Market Value ($)":   "${:,.2f}",
        "Unrealized P/L ($)": "${:+,.2f}",
        "Unrealized P/L (%)": "{:+.2f}%",
    })
    st.dataframe(styled, width='stretch', hide_index=True)
    st.caption(
        f"Cash: **$0.00** (fully invested)  ·  "
        f"Entry date: **{state.get('entry_date', '—')}**  ·  "
        f"Cumulative slippage/fees: **${state.get('trading_cost', 0):,.2f}**"
    )
else:
    st.info(
        f"Not invested in GLD.  "
        f"Cash: **${cash:,.2f}**  ·  "
        f"Cumulative slippage/fees: **${state.get('trading_cost', 0):,.2f}**"
    )

# ── Stop-loss status banner ───────────────────────────────────────────────────
st.subheader("🛡️ Trailing Stop Status")
if stop_act:
    st.markdown(
        "<div class='stop-active'>🔴 <b>Stop Active</b> — exited GLD after stop triggered. "
        "Waiting for TIPS + DXY signals to reset before re-entry.</div>",
        unsafe_allow_html=True,
    )
elif in_pos and hwm:
    distance_pct = (gld_price / hwm - 1) * 100
    stop_price   = hwm * (1 - STOP_PCT)
    gap_to_stop  = (gld_price / stop_price - 1) * 100
    if gap_to_stop <= 2.0:
        cls = "stop-warn"
        icon = "🟡"
        msg = f"<b>Within {gap_to_stop:.1f}% of stop</b> — HWM ${hwm:,.2f} · Stop at ${stop_price:,.2f}"
    else:
        cls = "stop-safe"
        icon = "🟢"
        msg = (f"<b>No stop risk</b> — GLD is {distance_pct:.1f}% below HWM "
               f"({distance_pct + STOP_PCT*100:.1f}% cushion to stop at ${stop_price:,.2f})")
    st.markdown(f"<div class='{cls}'>{icon} {msg}</div>", unsafe_allow_html=True)
else:
    st.markdown(
        "<div class='signal-off'>⚪ Not in position — stop not applicable</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Signal panel ──────────────────────────────────────────────────────────────
st.subheader("📡 Live Signal Status")
sig = fetch_signals_live()
sc1, sc2, sc3 = st.columns(3)

with sc1:
    st.markdown("**TIPS 10Y Real Yield**")
    if sig["tips_val"] is not None:
        arrow = "↓ Falling" if sig["tips_falling"] else "↑ Rising"
        color = "#00c896" if sig["tips_falling"] else "#ff4b4b"
        st.markdown(
            f"Current: **{sig['tips_val']:.2f}%**  ·  "
            f"SMA-60: **{sig['tips_sma']:.2f}%**  ·  "
            f"<span style='color:{color};font-weight:700'>{arrow}</span>",
            unsafe_allow_html=True,
        )
        label = "signal-on" if sig["tips_falling"] else "signal-off"
        txt   = "TIPS Tailwind ✓" if sig["tips_falling"] else "TIPS Headwind ✗"
        st.markdown(f"<div class='{label}'>{txt}</div>", unsafe_allow_html=True)
    else:
        st.caption("TIPS data unavailable (FRED)")

with sc2:
    st.markdown("**DXY Dollar Index**")
    if sig["dxy_val"] is not None:
        arrow = "↓ Weak" if sig["dxy_weak"] else "↑ Strong"
        color = "#00c896" if sig["dxy_weak"] else "#ff4b4b"
        st.markdown(
            f"Current: **{sig['dxy_val']:.2f}**  ·  "
            f"SMA-150: **{sig['dxy_sma']:.2f}**  ·  "
            f"<span style='color:{color};font-weight:700'>{arrow}</span>",
            unsafe_allow_html=True,
        )
        label = "signal-on" if sig["dxy_weak"] else "signal-off"
        txt   = "DXY Tailwind ✓" if sig["dxy_weak"] else "DXY Headwind ✗"
        st.markdown(f"<div class='{label}'>{txt}</div>", unsafe_allow_html=True)
    else:
        st.caption("DXY data unavailable")

with sc3:
    st.markdown("**Combined Regime**")
    tips_ok = sig.get("tips_falling")
    dxy_ok  = sig.get("dxy_weak")
    if tips_ok is None or dxy_ok is None:
        st.caption("Signal data unavailable")
    elif tips_ok and dxy_ok:
        st.markdown("<div class='signal-on'>🟢 REGIME ON — Both signals active</div>",
                    unsafe_allow_html=True)
        st.caption("Entry criteria met. If not in GLD, next close triggers buy.")
    elif tips_ok or dxy_ok:
        active = "TIPS" if tips_ok else "DXY"
        st.markdown(f"<div class='signal-partial'>🟡 PARTIAL — Only {active} signal active</div>",
                    unsafe_allow_html=True)
        st.caption("Both signals must agree to enter. Staying in cash.")
    else:
        st.markdown("<div class='signal-off'>🔴 REGIME OFF — No signals active</div>",
                    unsafe_allow_html=True)
        st.caption("Both signals inactive. Cash position.")

st.divider()

# ── NAV chart ─────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"],
    mode="lines+markers",
    line=dict(color="#f0a000", width=2),
    name="Gold Strategy (paper, as of last close)",
))
fig.add_trace(go.Scatter(
    x=[ledger["date"].iloc[-1]], y=[live_nav],
    mode="markers",
    marker=dict(color="#00c896", size=10, symbol="star"),
    name="Live (intraday)",
))
fig.update_layout(
    height=360,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="NAV ($, start = 10,000)", gridcolor="#2a2a3e", tickformat=","),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width='stretch')

# ── Drawdown chart ────────────────────────────────────────────────────────────
st.subheader("📉 Drawdown")
fig_dd = go.Figure()
fig_dd.add_trace(go.Scatter(
    x=ledger["date"], y=drawdown,
    mode="lines", fill="tozeroy",
    line=dict(color="#ff4b4b", width=1.5),
    fillcolor="rgba(255,75,75,0.12)",
))
fig_dd.update_layout(
    height=220,
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
)
st.plotly_chart(fig_dd, width='stretch')

st.divider()

# ── Daily log ─────────────────────────────────────────────────────────────────
st.subheader("🗒️ Daily Log")
log = ledger.copy()
log["date"]          = log["date"].dt.date
log["nav"]           = log["nav"].round(2)
log["gld_price"]     = log["gld_price"].round(2)
log["daily_log_ret"] = (log["daily_log_ret"] * 100).round(3)
log = log.rename(columns={
    "nav": "NAV ($)", "gld_price": "GLD Price",
    "daily_log_ret": "Daily Ret %",
    "in_position": "In GLD", "signal": "Signal",
    "stop_fired": "Stop Fired",
})
st.dataframe(
    log[["date", "NAV ($)", "In GLD", "GLD Price", "Daily Ret %", "Signal", "Stop Fired"]]
        .sort_values("date", ascending=False),
    width='stretch', hide_index=True,
    column_config={
        "NAV ($)":    st.column_config.NumberColumn("NAV ($)", format="$%,.2f"),
        "GLD Price":  st.column_config.NumberColumn("GLD Price", format="$%.2f"),
        "Daily Ret %": st.column_config.NumberColumn("Daily Ret %", format="%.3f%%"),
    },
)

st.caption(
    "Strategy: TIPS 10Y real yield falling (< 60-day SMA) × DXY below SMA-150 + 5% trailing stop.  "
    "Instrument: GLD ETF (SPDR Gold Shares). 10 bps slippage/fee on each entry/exit.  "
    "Backtested on GC=F (gold futures) 2003–2026 — see dxy_gold_stopcheck_triggers.csv for full stop log."
)
