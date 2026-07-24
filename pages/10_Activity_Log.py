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
