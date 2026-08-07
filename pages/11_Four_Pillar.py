"""
Four-Pillar Strategy — Live Paper Trading
============================================
Gold (R-dir+DXY+5%stop) + SectorEW (top-3 sector momentum, real equal-weight
ETFs) + FMTS (Momentum+Low-Vol 2-factor, 9% stop) + OTP2.0 (base), 25% each,
drift-band rebalanced (±5%). Validated in four_pillar_combination_backtest.py
(Sharpe 1.139, MaxDD -9.1%, 2009-2026) and four_pillar_band_rebalance_backtest.py.
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Four-Pillar Strategy - Paper Trading", page_icon="🧩", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .sleeve-card { background:#1e1e2e; border-radius:10px; padding:14px; margin:4px; }
    .band-ok   { background:#0d3d27; color:#00c896; border-radius:6px; padding:6px 14px; display:inline-block; }
    .band-near { background:#3d2e00; color:#f0a000; border-radius:6px; padding:6px 14px; display:inline-block; }
</style>
""", unsafe_allow_html=True)

LEDGER_PATH = "four_pillar_ledger.csv"
STATE_PATH = "four_pillar_state.json"
BAND = 0.05
TARGET_W = 0.25
SLEEVE_COLOR = {"Gold": "#c9a227", "SectorEW": "#1565c0", "FMTS": "#e65100", "OTP2.0": "#6a1b9a"}

st.title("🧩 Four-Pillar Strategy — Live Paper Trading")
st.caption(
    "25% each: Gold (R-dir+DXY signal, 5% stop) · SectorEW (top-3 sector momentum, real "
    "equal-weight ETFs) · FMTS (Momentum+Low-Vol 2-factor, 9% stop) · OTP2.0 (base engine). "
    "Rebalanced only when a sleeve drifts beyond ±5% of its 25% target — not on a fixed calendar. "
    "Backtested Sharpe 1.139 · MaxDD -9.1% (2009-2026, common window) — see "
    "four_pillar_combination_backtest.py and four_pillar_band_rebalance_backtest.py."
)

col_refresh, _ = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh"):
        st.rerun()

if not os.path.exists(LEDGER_PATH) or not os.path.exists(STATE_PATH):
    st.warning("No Four-Pillar ledger found. Run `four_pillar_engine.py` to seed it.")
    st.stop()

ledger = pd.read_csv(LEDGER_PATH, parse_dates=["date"])
with open(STATE_PATH) as f:
    state = json.load(f)
sleeves = state.get("sleeves", {})

nav = state.get("nav", ledger["nav"].iloc[-1])
first_nav = ledger["nav"].iloc[0]
total_ret = (nav / first_nav - 1) * 100
running_max = ledger["nav"].cummax()
drawdown = (ledger["nav"] - running_max) / running_max * 100
max_dd = drawdown.min()
days_live = (pd.Timestamp.today().normalize() - ledger["date"].iloc[0]).days
n_rebal = state.get("n_rebalances", 0)

# ── Headline metrics ──────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Portfolio Value", f"${nav:,.2f}", f"{total_ret:+.2f}% since inception")
c2.metric("Days Live", str(days_live))
c3.metric("Max Drawdown", f"{max_dd:.2f}%")
c4.metric("Rebalances", str(n_rebal))
c5.metric("Last Updated", state.get("last_date", "—"))

st.divider()

# ── Sleeve breakdown ────────────────────────────────────────────────────────────
st.subheader("🧱 Sleeve Breakdown")

rows = []
for name, sub in sleeves.items():
    sv = float(sub.get("nav", 0.0))
    w = (sv / nav * 100) if nav else float("nan")
    drift = w - TARGET_W * 100
    holdings = sub.get("shares", {})
    n_hold = sum(1 for v in holdings.values() if v)
    if name == "Gold":
        detail = "In GLD" if sub.get("invested", 0) > 0.01 else ("Stop-wait" if sub.get("stop_active") else "Cash")
        if sub.get("invested", 0) > 0.01:
            detail += f" ({sub['invested']*100:.0f}%)"
    elif name == "FMTS":
        detail = f"{n_hold} holdings" + (" ⚠ stopped (50%)" if sub.get("stopped_out") else "")
    elif name == "SectorEW":
        detail = ", ".join(t for t in holdings if holdings.get(t)) or "—"
    else:
        detail = f"{sub.get('invested', 0)*100:.0f}% invested, {n_hold} names"
    rows.append({"Sleeve": name, "Value ($)": sv, "Weight %": w, "Drift from 25%": drift, "Status": detail})

df_sleeves = pd.DataFrame(rows)
st.dataframe(
    df_sleeves.style.format({"Value ($)": "${:,.2f}", "Weight %": "{:.1f}%", "Drift from 25%": "{:+.1f}pp"})
        .map(lambda v: "color:#ff4b4b;font-weight:600" if isinstance(v, float) and abs(v) > BAND * 100 * 0.8 else "",
             subset=["Drift from 25%"]),
    width='stretch', hide_index=True,
)

max_drift = df_sleeves["Drift from 25%"].abs().max() if len(df_sleeves) else 0.0
if max_drift > BAND * 100 * 0.8:
    st.markdown(f"<div class='band-near'>🟡 Largest drift {max_drift:.1f}pp — approaching the "
                f"±{BAND*100:.0f}% rebalance band</div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div class='band-ok'>🟢 Largest drift {max_drift:.1f}pp — well within the "
                f"±{BAND*100:.0f}% rebalance band</div>", unsafe_allow_html=True)

# Sleeve weight pie
fig_pie = go.Figure(data=[go.Pie(
    labels=df_sleeves["Sleeve"], values=df_sleeves["Value ($)"],
    marker=dict(colors=[SLEEVE_COLOR.get(s, "#888") for s in df_sleeves["Sleeve"]]),
    hole=0.45, textinfo="label+percent",
)])
fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
                       paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig_pie, width='stretch')

st.divider()

# ── NAV chart ─────────────────────────────────────────────────────────────────
st.subheader("📈 NAV Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=ledger["date"], y=ledger["nav"], mode="lines+markers",
    line=dict(color="#8e44ad", width=2), name="Four-Pillar (paper)",
))
rebal_rows = ledger[ledger.get("rebalanced", False) == True]
if len(rebal_rows):
    fig.add_trace(go.Scatter(
        x=rebal_rows["date"], y=rebal_rows["nav"], mode="markers",
        marker=dict(color="#f0a000", size=10, symbol="diamond"), name="Band rebalance",
    ))
fig.update_layout(
    height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
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
    x=ledger["date"], y=drawdown, mode="lines", fill="tozeroy",
    line=dict(color="#ff4b4b", width=1.5), fillcolor="rgba(255,75,75,0.12)",
))
fig_dd.update_layout(
    height=220, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=20, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"), xaxis=dict(title="Date"),
)
st.plotly_chart(fig_dd, width='stretch')

st.divider()

# ── Daily log ─────────────────────────────────────────────────────────────────
st.subheader("🗒️ Daily Log")
log = ledger.copy()
log["date"] = log["date"].dt.date
log["nav"] = log["nav"].round(2)
log["daily_log_ret"] = (log["daily_log_ret"] * 100).round(3)
log = log.rename(columns={"nav": "NAV ($)", "daily_log_ret": "Daily Ret %",
                          "holdings": "Sleeve Weights", "rebalanced": "Rebalanced"})
st.dataframe(
    log[["date", "NAV ($)", "Daily Ret %", "Sleeve Weights", "Rebalanced"]]
        .sort_values("date", ascending=False),
    width='stretch', hide_index=True,
    column_config={
        "NAV ($)": st.column_config.NumberColumn("NAV ($)", format="$%,.2f"),
        "Daily Ret %": st.column_config.NumberColumn("Daily Ret %", format="%.3f%%"),
    },
)

st.caption(
    "Each sleeve replicates exactly what four_pillar_combination_backtest.py tested — Gold and "
    "FMTS/OTP2.0 use the SAME construction as their backtests, not the live standalone Gold/OTP2.0 "
    "AMA/full-FMTS strategies elsewhere in this app, which differ. 10 bps slippage per trade. "
    "PAPER TRADING ONLY — not a recommendation to trade real money."
)
