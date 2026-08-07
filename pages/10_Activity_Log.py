"""
Activity Log — system-wide timeline of strategy actions
=======================================================
A dedicated, persistent, filterable feed of what every strategy has done
(seeds, rebalances, stops, risk-flips, trims). Reads events.jsonl, which the
daily job keeps current from the ledgers; engine-logged events also carry
realized P&L where available.
"""

import pandas as pd
import streamlit as st

from event_log import STRATS, load_events

st.set_page_config(page_title="Activity Log", page_icon="🧾", layout="wide")

ICON = {name: icon for name, _, icon in STRATS}
TYPE_LABEL = {
    "seed": "🌱 Seed", "rebalance": "🔄 Rebalance", "stop": "⛔ Stop",
    "reentry": "↩️ Re-entry", "risk-off": "🛑 Risk-off", "risk-on": "✅ Risk-on",
    "trim": "✂️ Trim", "reload": "➕ Reload", "entry": "🟢 Entry", "exit": "🚪 Exit",
}

st.title("🧾 Activity Log")
st.caption(
    "A system-wide, persistent timeline of what each strategy has *done* — seeds, "
    "rebalances, stop triggers, risk-flips and trims. Reconstructed from ledger "
    "history and refreshed by the daily job. (Realized P&L per event is populated "
    "for engine-logged events going forward.)"
)

with st.expander("ℹ️ What this log tracks — read me", expanded=False):
    st.markdown("""
This is a permanent, growing record of every **action** each strategy takes — not day-to-day
price drift (that's the charts and metrics table), but the **decisions** it makes and the money
they lock in.

**Events captured**

| Event | Fires when… | Strategies | Realized P&L? |
|---|---|---|---|
| 🌱 **Seed** | A strategy is first launched | all | — |
| 🔄 **Rebalance** | Monthly re-selection changes the holdings | Momentum, FMTS, FMTS AMA, RRG | ✅ + tickers |
| 🟢 **Entry** | Macro signals align → buys GLD | Gold | — |
| 🚪 **Exit** | Gold's signal turns off → sells GLD | Gold | ✅ |
| ⛔ **Stop** | 9% trailing stop (FMTS) / 5% (Gold) fires | FMTS, FMTS AMA, Gold | ✅ (Gold) |
| ↩️ **Re-entry** | FMTS re-enters after a stop calms | FMTS, FMTS AMA | — |
| 🛑 **Risk-off** / ✅ **Risk-on** | S&P 500 crosses its 10-month average → cash / back in | Momentum | — |
| ✂️ **Trim** / ➕ **Reload** | A big (>8pp) exposure change in a day | OTP2.0, OTP2.0 AMA | — (cumulative on their page) |
| 🔄 **Rebalance** | A sleeve drifts >5% from its 25% target, or SectorEW/FMTS rotate monthly | 🧩 FourPillar | — |

**What each row records:** date · strategy · event · a plain-English detail. Instrumented trades
(Momentum / FMTS / FMTS AMA rebalances and Gold exits) also carry the **realized P&L** — sale
proceeds − cost basis, net of slippage — and the **tickers traded**.

**What it does *not* track:** daily NAV / unrealized gains (see the charts), OTP2.0's tiny daily
vol-target tweaks (only >8pp moves are logged), or individual fills — a rebalance reads
"rotated 5 out / 5 in" with the realized total, not every share's price. It's an audit trail of
*decisions*, not a full trade blotter.

**Two sources:** *backfill* reconstructs actions from the ledgers on every daily run (retroactive,
no realized P&L); *engine-logged* events are the richer live ones with realized P&L, and take
precedence so nothing double-counts.

**🔄 RRG is a research book, not a funded strategy.** Its events are logged the same way, but the
signal failed its pre-registered validation (1/9 criteria — walk-forward turned \$1 into \$0.98
with a 50% drawdown, and it added nothing over plain 12-1 relative momentum). It is tracked here
to build genuine out-of-sample evidence. Read its rows as an experiment, not as performance.

**When it fills in:** the realized-P&L column lights up the first time an instrumented strategy
acts — the monthly rebalance (Momentum / FMTS, ~early each month) or a Gold exit.
""")

events = load_events()
if not events:
    st.info("No events recorded yet. Run the strategy engines / daily job to populate the log.")
    st.stop()

df = pd.DataFrame(events)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date", ascending=False).reset_index(drop=True)

# ── Filters ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
all_strats = sorted(df["strategy"].unique())
all_types = sorted(df["type"].unique())
sel_s = c1.multiselect("Strategy", all_strats, default=all_strats)
sel_t = c2.multiselect("Event type", all_types, default=all_types)
f = df[df["strategy"].isin(sel_s) & df["type"].isin(sel_t)]

# ── Summary chips ──────────────────────────────────────────────────────────────
counts = f["type"].value_counts().to_dict()
summary = "  ·  ".join(f"{TYPE_LABEL.get(t, t)} {counts[t]}" for t in sorted(counts))
st.caption(f"**{len(f)} events** across {f['strategy'].nunique()} strategies  ·  {summary}")

# ── Table ──────────────────────────────────────────────────────────────────────
show = pd.DataFrame({
    "Date": f["date"].dt.date,
    "Strategy": f["strategy"].map(lambda s: f"{ICON.get(s, '')} {s}"),
    "Event": f["type"].map(lambda t: TYPE_LABEL.get(t, t)),
    "Detail": f["detail"],
})
if "realized_pnl" in f.columns and f["realized_pnl"].notna().any():
    show["Realized P&L"] = f["realized_pnl"]
if "tickers" in f.columns and f["tickers"].notna().any():
    show["Tickers"] = f["tickers"].map(lambda x: ", ".join(x) if isinstance(x, list) else "")

col_cfg = {}
if "Realized P&L" in show.columns:
    col_cfg["Realized P&L"] = st.column_config.NumberColumn("Realized P&L", format="$%+,.0f")

st.dataframe(show, width='stretch', hide_index=True,
             height=min(640, 60 + 34 * len(show)), column_config=col_cfg)

st.caption(
    "Event types: seed (inception) · rebalance (holdings changed) · stop / re-entry "
    "(trailing-stop) · risk-off / risk-on (momentum trend gate) · trim / reload "
    "(exposure scaled). Source: reconstructed from ledgers + live engine events."
)
