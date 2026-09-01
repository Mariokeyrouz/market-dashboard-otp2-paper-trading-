"""
Trade Blotter — system-wide fill-level record
===============================================
Every real per-ticker fill each engine has made — one row per (ticker, day)
where shares changed by more than dust. Complements the Activity Log: that
page records the *decision* ("rotated 5 out / 5 in"), this page records the
*fills* that decision produced (ticker, side, shares, price, realized P&L).
Reads trades.csv, appended to by the engines and kept current by the daily job.
"""

import pandas as pd
import streamlit as st

from event_log import STRATS
from blotter import load_trades

st.set_page_config(page_title="Trade Blotter", page_icon="💵", layout="wide")

ICON = {name: icon for name, _, icon in STRATS}
REASON_LABEL = {
    "seed": "🌱 Seed", "rebalance": "🔄 Rebalance", "stop": "⛔ Stop",
    "reentry": "↩️ Re-entry", "vol-target": "⚖️ Vol-target", "entry": "🟢 Entry",
    "exit": "🚪 Exit",
}

st.title("💵 Trade Blotter")
st.caption(
    "The system-wide, per-fill record of what each strategy has actually traded — "
    "ticker, side, shares, price and realized P&L for every real rebalance. The "
    "[Activity Log](/Activity_Log) records the *decision* (\"rotated 5 out / 5 "
    "in\"); this page records the individual **fills** that decision produced."
)

with st.expander("ℹ️ What this tracks — read me", expanded=False):
    st.markdown("""
Every ledger in this system stores daily NAV and a holdings string — never shares or fill
prices. This page is built from a separate append-only record, `trades.csv`, that each engine
writes to directly at the moment its share count changes.

**Row = one ticker, one day, one non-dust fill** (fills under \\$1 notional — float noise from
daily mark-to-target rebalancing — are dropped). A single rebalance can produce several rows,
one per ticker traded.

**Reason codes**

| Reason | Fires when… |
|---|---|
| 🌱 **Seed** | The engine's first-ever buy |
| 🔄 **Rebalance** | Monthly re-selection changes holdings (FMTS, FMTS AMA, Momentum, RRG) |
| ⛔ **Stop** | Trailing stop scales the book down (FMTS, FMTS AMA, Gold) |
| ↩️ **Re-entry** | Stop clears and the book scales back up (FMTS, FMTS AMA) |
| 🟢 **Entry** / 🚪 **Exit** | Gold's signal turns on / off |
| ⚖️ **Vol-target** | Daily invested-% tweak from trim/reload/vol-targeting (OTP2.0, OTP2.0 AMA, FMTS, FMTS AMA) |

**What it does *not* cover:** history from before each engine was wired to write here — the
underlying ledgers never stored shares, so there is nothing to reconstruct. Rows start
accumulating from each engine's next run onward. **🧩 FourPillar** only logs fills for its
OTP2.0 sleeve today — its Gold, SectorEW and FMTS sleeves rebalance through separate,
not-yet-instrumented code paths, so its rows undercount that book's real turnover.

**🔄 RRG** is a research book, not funded capital — see the Activity Log for the validation
context. Its fills are recorded the same way for completeness.
""")

df = load_trades()
if df.empty:
    st.info(
        "No fills recorded yet. Each engine now writes here on every rebalance, "
        "but the file starts empty — it will fill in from the next daily update "
        "onward. Nothing to reconstruct from older ledgers (they never stored shares)."
    )
    st.stop()

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date", ascending=False).reset_index(drop=True)

# ── Filters ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
all_strats = sorted(df["strategy"].unique())
all_reasons = sorted(df["reason"].unique())
sel_s = c1.multiselect("Strategy", all_strats, default=all_strats)
sel_r = c2.multiselect("Reason", all_reasons, default=all_reasons)
f = df[df["strategy"].isin(sel_s) & df["reason"].isin(sel_r)]

# ── Summary ────────────────────────────────────────────────────────────────────
realized = f["realized_pnl"].dropna()
sc1, sc2, sc3, sc4 = st.columns(4)
sc1.metric("Fills", f"{len(f):,}")
sc2.metric("Gross Traded", f"${f['gross'].sum():,.0f}")
sc3.metric("Slippage Paid", f"${f['slippage'].sum():,.0f}")
sc4.metric("Realized P&L", f"${realized.sum():+,.0f}" if len(realized) else "—")

by_strat = f.groupby("strategy").agg(
    Fills=("ticker", "count"), Gross_Traded=("gross", "sum"),
    Slippage=("slippage", "sum"), Realized_PnL=("realized_pnl", "sum"),
).rename(columns={"Gross_Traded": "Gross Traded", "Realized_PnL": "Realized P&L"})
by_strat.index = [f"{ICON.get(s, '')} {s}" for s in by_strat.index]
by_strat = by_strat.sort_values("Gross Traded", ascending=False)

st.dataframe(
    by_strat, width='stretch',
    height=min(38 + 35 * len(by_strat) + 10, 400),
    column_config={
        "Fills": st.column_config.NumberColumn("Fills", format="%d"),
        "Gross Traded": st.column_config.NumberColumn("Gross Traded", format="$%,.0f"),
        "Slippage": st.column_config.NumberColumn("Slippage", format="$%,.2f"),
        "Realized P&L": st.column_config.NumberColumn("Realized P&L", format="$%+,.2f"),
    },
)

# ── Full fill table ────────────────────────────────────────────────────────────
show = pd.DataFrame({
    "Date": f["date"].dt.date,
    "Strategy": f["strategy"].map(lambda s: f"{ICON.get(s, '')} {s}"),
    "Ticker": f["ticker"],
    "Side": f["side"].str.capitalize(),
    "Shares": f["shares"],
    "Price": f["price"],
    "Gross": f["gross"],
    "Slippage": f["slippage"],
    "Realized P&L": f["realized_pnl"],
    "Reason": f["reason"].map(lambda r: REASON_LABEL.get(r, r)),
    "Source": f["source"],
})

st.dataframe(
    show, width='stretch', hide_index=True,
    height=min(38 + 35 * len(show) + 10, 900),
    column_config={
        "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
        "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "Gross": st.column_config.NumberColumn("Gross", format="$%,.0f"),
        "Slippage": st.column_config.NumberColumn("Slippage", format="$%.2f"),
        "Realized P&L": st.column_config.NumberColumn("Realized P&L", format="$%+,.2f"),
    },
)

st.caption(
    "Source: engine (live, written the moment a fill happens). A future reconstruction "
    "pass, if built, would carry source=reconstructed so an estimate is never mistaken "
    "for a real fill."
)
