"""
Trade Blotter — persistent per-fill record for the strategy suite
===================================================================
An append-only record (trades.csv) of every actual share fill each engine
makes — one row per (ticker, day) where shares changed by more than dust.
Complements event_log.py: events.jsonl records the *decision* ("rotated 5
out / 5 in"), trades.csv records the *fills* that decision produced (ticker,
side, shares, price, realized P&L).

Engines call record_fills() once per rebalance point, passing the share
dict before and after. The diff between the two is the fill list — this
mirrors exactly what the ledger's own NAV/cost bookkeeping already computes,
so blotter rows tie out to the ledger's trading_cost.

Historical fills before this file existed cannot be recovered (the ledgers
only ever stored NAV + a holdings string, never shares) — trades.csv starts
from whenever each engine was wired to call record_fills(), and rows carry
source="engine" for that. A future reconstruction pass, if built, must use
source="reconstructed" so an estimate is never mistaken for a real fill.
"""

import csv
import os

import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
BLOTTER_PATH = os.path.join(REPO, "trades.csv")

COLUMNS = ["date", "strategy", "ticker", "side", "shares", "price", "gross",
           "slippage", "avg_cost", "realized_pnl", "reason", "source"]

# Fills smaller than this (in dollars) are float/rounding dust from daily
# mark-to-target rebalancing, not real trading decisions — skip them.
MIN_NOTIONAL = 1.0


def record_fills(strategy, date, prev_shares, new_shares, prices,
                  entry_prices_before, slippage_rate, reason, source="engine"):
    """
    Diff prev_shares -> new_shares and append one row per non-dust fill.

      strategy             display name, matches event_log.STRATS
      date                 'YYYY-MM-DD' the fill happened
      prev_shares          {ticker: shares} before this rebalance
      new_shares           {ticker: shares} after this rebalance
      prices               {ticker: fill price} for today (buys should use
                            the slippage-marked-up entry price where the
                            engine already computes one; sells the day's mark)
      entry_prices_before  {ticker: avg cost} as of BEFORE this fill — used
                            to compute realized P&L on the sold portion
      slippage_rate        fraction, used to back out per-fill slippage $
      reason               'seed' | 'rebalance' | 'stop' | 'reentry' |
                            'vol-target' | 'risk-off' | 'risk-on' |
                            'entry' | 'exit'

    Returns the number of rows written.
    """
    rows = []
    for t in set(prev_shares) | set(new_shares):
        if t not in prices:
            continue
        old_sh = prev_shares.get(t, 0.0)
        new_sh = new_shares.get(t, 0.0)
        delta = new_sh - old_sh
        px = prices[t]
        gross = abs(delta) * px
        if gross < MIN_NOTIONAL:
            continue
        side = "buy" if delta > 0 else "sell"
        avg_cost = entry_prices_before.get(t)
        realized_pnl = round(abs(delta) * (px - avg_cost), 2) if side == "sell" and avg_cost is not None else None
        rows.append({
            "date": date, "strategy": strategy, "ticker": t, "side": side,
            "shares": round(abs(delta), 6), "price": round(px, 4),
            "gross": round(gross, 2), "slippage": round(gross * slippage_rate, 2),
            "avg_cost": round(avg_cost, 4) if avg_cost is not None else "",
            "realized_pnl": realized_pnl if realized_pnl is not None else "",
            "reason": reason, "source": source,
        })

    if not rows:
        return 0

    write_header = not os.path.exists(BLOTTER_PATH)
    with open(BLOTTER_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def load_trades(strategy=None):
    """Load trades.csv, optionally filtered to one strategy. Empty frame if
    no fills have been recorded yet (e.g. before an engine's first run since
    being wired to record_fills)."""
    if not os.path.exists(BLOTTER_PATH):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(BLOTTER_PATH, parse_dates=["date"])
    if strategy:
        df = df[df["strategy"] == strategy]
    return df.sort_values("date").reset_index(drop=True)


def render_blotter(strategy, note=None, n=15):
    """Streamlit expander with recent fills for one strategy — the shared
    widget every strategy page embeds so a per-strategy blotter doesn't need
    duplicating eight times. Imports streamlit lazily so this module stays
    usable from the (non-Streamlit) daily engine scripts."""
    import streamlit as st

    df = load_trades(strategy)
    with st.expander(f"🧾 Trade Blotter — {strategy}", expanded=False):
        if note:
            st.caption(note)
        if df.empty:
            st.caption(
                "No fills recorded yet. The blotter records real per-ticker fills "
                "going forward from when this engine's rebalance logic was "
                "instrumented — it does not backfill history from before that."
            )
            return

        total_gross = df["gross"].sum()
        total_slip = df["slippage"].sum()
        realized = df["realized_pnl"].dropna()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Fills", f"{len(df):,}")
        c2.metric("Gross Traded", f"${total_gross:,.0f}")
        c3.metric("Slippage Paid", f"${total_slip:,.0f}")
        c4.metric("Realized P&L", f"${realized.sum():+,.0f}" if len(realized) else "—")

        show = df.sort_values("date", ascending=False).head(n).copy()
        show["date"] = show["date"].dt.date
        show["side"] = show["side"].str.capitalize()
        show = show.rename(columns={
            "date": "Date", "ticker": "Ticker", "side": "Side", "shares": "Shares",
            "price": "Price", "gross": "Gross", "slippage": "Slippage",
            "realized_pnl": "Realized P&L", "reason": "Reason",
        })
        cols = ["Date", "Ticker", "Side", "Shares", "Price", "Gross", "Slippage",
                "Realized P&L", "Reason"]
        st.dataframe(
            show[cols], width='stretch', hide_index=True,
            height=min(38 + 35 * len(show) + 10, 38 + 35 * n + 10),
            column_config={
                "Shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "Gross": st.column_config.NumberColumn("Gross", format="$%,.0f"),
                "Slippage": st.column_config.NumberColumn("Slippage", format="$%.2f"),
                "Realized P&L": st.column_config.NumberColumn("Realized P&L", format="$%+,.2f"),
            },
        )
        if len(df) > n:
            st.caption(f"Showing the {n} most recent of {len(df):,} fills. "
                       "Full history on the Trade Blotter page.")
