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

with st.expander("ℹ️ How this strategy works, and why — read me", expanded=True):
    st.markdown("""
**The core idea:** none of these four signals is individually strong enough to trade on its
own — three of the four (SectorEW, FMTS, and even Gold on some measures) don't clearly beat
just holding SPY by themselves. But portfolio theory doesn't require every ingredient to be
good alone — it requires them to not move together. If four assets have low correlation, a
combined book can end up with a *better* risk-adjusted return than any single one of them,
because each one's bad days get cancelled out by the others' good days more often than not.
That's the bet this strategy is making, and it's the one thing in this session's research that
actually held up under scrutiny: **equal-weighting all four beat every individual pillar and
beat SPY on Sharpe by a wide margin, backtested 2009–2026** (204 months, Newey-West t = 6.73 —
comfortably past the ≥3 bar this project holds every result to).

**The four pillars, and why each one is built the way it is:**

- **🥇 Gold** — long GLD when TIPS 10-year real yield is falling (below its own 60-day average)
  *and* the Dollar Index is weak (below its 150-day average), sized at 50% or 100% depending on
  how weak the dollar signal is, with a 5% trailing stop. This is the single strongest validated
  signal in the whole research program (backtested Sharpe 1.165 on its own, 2003–2026). **Note:**
  this is a different, more nuanced construction than the standalone "Gold Strategy" page
  elsewhere in this app, which uses a simpler on/off signal — the two will not track each other.
- **📈 SectorEW** — ranks the 9 core S&P sector ETFs by 12-month relative momentum vs SPY (skipping
  the most recent month), holds the top 3 — but via the *real* equal-weight sector ETFs (RSPT,
  RSPF, RSPG, …), not the more common cap-weighted ones (XLK, XLF, …). That distinction matters: a
  parallel research script found that holding these sectors through individual stocks looked great
  in a backtest but the "edge" was entirely a survivorship-bias artifact of the stock price history
  used — it evaporated once tested against the real, unbiased equal-weight ETFs. This sleeve exists
  because the *real* equal-weight ETFs still showed a modest, genuine edge over cap-weighted ones
  once that bias was stripped out, even though it's not enough to beat SPY by itself.
- **🎯 FMTS** — ranks stocks by a Momentum + Low-Volatility composite (equal blend of the two),
  holds the top 18, with a 9% portfolio-level trailing stop. **Note:** the live "FMTS" page
  elsewhere in this app uses a fuller four-factor version that also scores Value and Quality —
  those two factors can't be backtested honestly here (this project has no historical fundamentals
  data, only today's snapshot), so this sleeve deliberately uses only the two factors that
  actually have a real backtested track record. It doesn't beat SPY alone, but it's the least
  correlated of the three equity sleeves with OTP2.0 (see the correlation table below), which is
  where its value in the combination comes from.
- **📊 OTP2.0** — the same regime-based, fixed 7-stock (GE, GS, GOOGL, AVGO, IBM, JPM, JNJ) timing
  engine as the standalone OTP2.0 page, run exactly as-is (not the AMA variant — a separate test
  found AMA's extra rules make no measurable difference over 17 years, so there was no reason to
  duplicate it here). The single best-performing pillar on its own over the common backtest window.

**How the sleeves are weighted together — correlation is the whole point:**
    """)

    corr_df = pd.DataFrame(
        {"Gold": [1.00, 0.05, 0.11, 0.01], "SectorEW": [0.05, 1.00, 0.58, 0.37],
         "FMTS": [0.11, 0.58, 1.00, 0.22], "OTP2.0": [0.01, 0.37, 0.22, 1.00]},
        index=["Gold", "SectorEW", "FMTS", "OTP2.0"],
    )
    cc1, cc2 = st.columns([1, 1])
    with cc1:
        _corr_fig = go.Figure(data=go.Heatmap(
            z=corr_df.values, x=list(corr_df.columns), y=list(corr_df.index),
            zmin=-1, zmax=1, colorscale="RdBu_r",
            text=corr_df.round(2).values.astype(str), texttemplate="%{text}", hoverongaps=False,
            colorbar=dict(title="ρ"),
        ))
        _corr_fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(_corr_fig, width='stretch')
        st.caption("Monthly return correlation, 2009–2026 backtest window.")
    with cc2:
        st.markdown("""
Gold is the standout diversifier — essentially uncorrelated with all three others (0.01–0.11).
SectorEW and FMTS are the most alike (0.58, both equity-momentum-flavored), which is why the
combination's benefit comes mostly from Gold and OTP2.0 pulling against the other two, not from
all four being independent of each other. Backtested, adding pillars one at a time raised the
median Sharpe of every possible combination monotonically: **0.78 (1 pillar) → 0.98 (2) → 1.09
(3) → 1.14 (all 4)** — the textbook signature of real diversification, not a fluke of one lucky
combination.
        """)

    st.markdown("""
**Why rebalance on a drift band instead of a fixed schedule?** Checking weights and resetting to
25/25/25/25 every single month sounds simple, but it means trading (and paying costs) even when
nothing has meaningfully changed. Backtested, only rebalancing when a sleeve's weight drifts more
than 5 percentage points from its 25% target cut trading from 203 months down to just 6 — a 97%
reduction — for essentially the same risk-adjusted return (Sharpe 1.109 vs 1.121 always-rebalancing).
It's not a source of extra return by itself; it's a way to get the same result with far less
unnecessary turnover.

**What this doesn't claim:** this is a ~17-year backtest on 4 assets, not a law of nature — treat it
as strong evidence, not a guarantee. Two of the four pillars (SectorEW, FMTS) still trail SPY on
their own; they're in this book for what they do to the *combination's* risk, not for their own
returns. And the combined book traded a bit of raw return for a much smoother ride versus SPY over
the same backtest window (CAGR 12.55% vs SPY's 14.61%, but Sharpe 1.14 vs SPY's 0.82, and max
drawdown -9.1% vs SPY's -23.9%) — it is not designed to outrun the index in a straight line, it's
designed to lose far less when things go wrong.
    """)

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
