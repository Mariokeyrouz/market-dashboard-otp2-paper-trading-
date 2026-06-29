"""
Paper Trading Engine — OTP2.0 v4 (Live Cohort)
================================================
Advances the v4 "2026-present (Live)" cohort by one (or more) trading days
and appends to paper_ledger.csv. Designed to be run daily (e.g. via a
scheduled task) after US market close.

Live cohort (from v4_cohort_regimes.csv, "2026-present (Live)" row):
  Selected stocks: GE, GS, GOOGL, AVGO, IBM, JPM, JNJ  (equal-weighted)
  Regime config:   Defensive (CAPE frothy, 38.0)  -> DEFENSIVE_OT2_CONFIG
  Next re-selection: 2029-01 (3yr cohort cadence) — not implemented here
                      since it's years away; engine will need updating then.

State is persisted in paper_state.json (carries OT2.0 invested%, cooldown,
consecutive-fall counters, dollar split across invested/cash). Each run
catches up from the last recorded date to the latest available trading day.

Usage:
  python paper_trading_engine.py
"""

import json
import os
import time
import numpy as np
import pandas as pd

from strategy_deep_test import download, download_tbill, build_market_features
from strategy_selection_v2 import DEFENSIVE_OT2_CONFIG

LIVE_TICKERS = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]
CFG = DEFENSIVE_OT2_CONFIG
LEDGER_PATH = "paper_ledger.csv"
STATE_PATH = "paper_state.json"
START_NAV = 10000.0
# Round-trip slippage + commission cost, applied to dollar amount traded
# whenever the invested/cash split rebalances (e.g. 0.1% = 10 bps).
SLIPPAGE_FEE_RATE = 0.001


def _step(row, prev, state, cfg, lr, cash_ret, px_today, cash_ret_simple):
    """One-day OT2.0 state advance. Mutates and returns `state` dict.

    `px_today`        : dict {ticker: close price today} — used for real
                        per-stock mark-to-market and share-level rebalancing.
    `cash_ret_simple` : simple (non-log) daily cash return for the cash bucket.

    The invested sleeve is held as actual shares per ticker. On any change in
    target invested %, every holding is scaled proportionally (preserving
    relative weights) and `shares` / `entry_prices` / cash are updated so that
    NAV == sum(shares*price) + cash exactly. The page reconciles by construction.
    """
    c = cfg
    inv = state["invested"]
    cooldown = state["cooldown"]
    consec_vix_fall = state["consec_vix_fall"]
    consec_rvol_fall = state["consec_rvol_fall"]

    rvol = max(row["rvol20"], 1e-6)
    vol_target_inv = min(0.95, c["vol_target"] / rvol)
    rvol_long = max(row["rvol252"], 1e-6)
    vol_scale = min(2.5, rvol / rvol_long)

    above_sma = row["close"] > row["sma200"]
    pos_mom = row["momentum"] > 0
    if not above_sma and not pos_mom:
        trend_scale = 1.5
    elif above_sma and pos_mom:
        trend_scale = 0.7
    else:
        trend_scale = 1.0

    bs = row["breadth_score"]
    vix_l2_thresh = c["vix_l2"]
    if bs <= -2:
        vix_l1_thresh = c["vix_l1"] - 2
        vix_l2_thresh = c["vix_l2"] - 2
        breadth_trim_mul = 1.4
    elif bs >= 2:
        vix_l1_thresh = c["vix_l1"] + 3
        breadth_trim_mul = 0.6
    else:
        vix_l1_thresh = c["vix_l1"]
        breadth_trim_mul = 1.0

    vix_above_ma = row["vix"] > row["vix_ma5"]
    vix_l1_signal = row["vix"] > vix_l1_thresh and vix_above_ma
    vix_l2_signal = row["vix"] > vix_l2_thresh and vix_above_ma

    trim = 0.0
    if cooldown == 0:
        scale = vol_scale * trend_scale * breadth_trim_mul
        if vix_l2_signal:
            trim = c["trim_l2_base"] * scale
        elif vix_l1_signal:
            trim = c["trim_l1_base"] * scale

    if trim > 0:
        inv = max(c["floor"], inv - trim)
        cooldown = c["cooldown_days"]

    consec_vix_fall = consec_vix_fall + 1 if row["vix"] < prev["vix"] else 0
    consec_rvol_fall = consec_rvol_fall + 1 if row["rvol20"] < prev["rvol20"] else 0

    above_sma50 = row["close"] > row["sma50"]
    speed_needed = c["reload_min_days"] if above_sma50 else c["reload_min_days"] + 2
    vix_ma20_ok = row["vix"] <= row["vix_ma20"] * 1.02
    above_sma200 = row["close"] > row["sma200"]

    base_signal = (
        consec_vix_fall >= speed_needed and
        consec_rvol_fall >= speed_needed and
        vix_ma20_ok and
        above_sma200 and
        inv < 0.90 and
        cooldown == 0
    )

    if base_signal:
        inv = min(0.95, inv + c["reload_size"])

    if trim == 0 and not base_signal:
        if abs(inv - vol_target_inv) > 0.03:
            inv = 0.6 * inv + 0.4 * vol_target_inv
        inv = max(c["floor"], inv)

    if cooldown > 0:
        cooldown -= 1

    # ── Real per-stock bookkeeping ──────────────────────────────────────────
    shares = state["shares"]
    entry_prices = state["entry_prices"]

    # 1. Mark holdings + cash to today's close (positions move by own prices).
    stock_value_pre = sum(shares[t] * px_today[t] for t in shares)
    cash_dollars = state["cash_dollars"] * (1.0 + cash_ret_simple)
    total_pre = stock_value_pre + cash_dollars

    # 2. Determine target invested dollars and the trade needed to get there.
    target_stock = inv * total_pre
    traded_dollars = abs(target_stock - stock_value_pre)
    cost = traded_dollars * SLIPPAGE_FEE_RATE
    total = total_pre - cost
    target_stock = inv * total           # re-apply target after netting cost

    # 3. Scale every holding by the same factor (preserve relative weights).
    if stock_value_pre > 1e-9:
        factor = target_stock / stock_value_pre
    else:
        factor = 0.0

    for t in shares:
        old_sh = shares[t]
        new_sh = old_sh * factor
        if new_sh > old_sh:
            # Buying more — update weighted-average cost basis.
            bought = new_sh - old_sh
            entry_prices[t] = (old_sh * entry_prices[t] + bought * px_today[t]) / new_sh
        # Selling (factor < 1) leaves entry/cost basis per share unchanged.
        shares[t] = new_sh

    cash_dollars = total - target_stock

    state["invested"] = inv
    state["cooldown"] = cooldown
    state["consec_vix_fall"] = consec_vix_fall
    state["consec_rvol_fall"] = consec_rvol_fall
    state["shares"] = shares
    state["entry_prices"] = entry_prices
    state["invested_dollars"] = target_stock
    state["cash_dollars"] = cash_dollars
    state["nav"] = total
    state["trading_cost"] = state.get("trading_cost", 0.0) + cost
    return state


def main():
    t0 = time.time()

    print("Downloading market + timing data...")
    gspc = download("^GSPC")
    vix = download("^VIX")
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    print(f"Downloading Live cohort stocks: {', '.join(LIVE_TICKERS)}")
    closes = {}
    for tkr in LIVE_TICKERS:
        df = download(tkr)
        closes[tkr] = df["Close"].squeeze()

    market_df = build_market_features(gspc, vix)

    prices = pd.DataFrame({t: closes[t] for t in LIVE_TICKERS})
    logret = np.log(prices / prices.shift(1))

    common_index = market_df.index
    for tkr in LIVE_TICKERS:
        common_index = common_index.intersection(logret[tkr].dropna().index)
    market_df = market_df.loc[common_index]
    logret = logret.loc[common_index]
    prices = prices.loc[common_index]      # align for positional per-stock lookup

    blended = logret.mean(axis=1)
    cash_daily = (tbill_raw.reindex(common_index).ffill().bfill() / 252)

    print(f"Common index: {common_index[0].date()} -> {common_index[-1].date()} "
          f"({len(common_index):,} trading days)")

    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)
        last_date = pd.Timestamp(state["last_date"])

        # ── One-time re-base migration to per-stock-v2 bookkeeping ──────────
        # Legacy state advanced the invested sleeve as a single blended dollar
        # bucket and never updated `shares` when the engine trimmed/reloaded,
        # so sum(shares*price) drifted above the true invested_dollars (the
        # trim proceeds were double-counted in cash). Scale shares once so they
        # match the engine's authoritative invested_dollars; carry NAV forward.
        if not state.get("per_stock_v2"):
            lp = state.get("last_prices", {})
            sh = state.get("shares", {})
            stock_val = sum(sh[t] * lp[t] for t in sh) if (sh and lp) else 0.0
            target = state.get("invested_dollars", stock_val)
            if stock_val > 1e-9:
                f_rebase = target / stock_val
                for t in sh:
                    sh[t] = sh[t] * f_rebase
                state["shares"] = sh
            state["per_stock_v2"] = True
            # Persist immediately — if there are no new trading days the engine
            # returns early below, and the re-base must survive that path.
            with open(STATE_PATH, "w") as f:
                json.dump(state, f, indent=2)
            print(f"  [migration] Re-based shares to match invested_dollars "
                  f"(scaled stock sleeve {stock_val:.2f} -> {target:.2f}); "
                  f"NAV carried forward at {state['nav']:.2f}")
    else:
        # Seed: start "live" as of the most recent trading day.
        seed_pos = len(common_index) - 1
        seed_date = common_index[seed_pos]
        inv0 = min(0.95, CFG["vol_target"] / market_df["rvol20"].iloc[seed_pos])
        seed_cost = START_NAV * inv0 * SLIPPAGE_FEE_RATE
        nav0 = START_NAV - seed_cost
        invested_dollars0 = nav0 * inv0
        per_ticker_dollars = invested_dollars0 / len(LIVE_TICKERS)
        # Entry prices reflect slippage: buys execute at close * (1 + fee rate)
        entry_prices = {t: float(prices[t].iloc[seed_pos]) * (1 + SLIPPAGE_FEE_RATE) for t in LIVE_TICKERS}
        shares = {t: per_ticker_dollars / entry_prices[t] for t in LIVE_TICKERS}
        state = dict(
            invested=inv0,
            cooldown=0,
            consec_vix_fall=0,
            consec_rvol_fall=0,
            invested_dollars=invested_dollars0,
            cash_dollars=nav0 * (1 - inv0),
            nav=nav0,
            trading_cost=seed_cost,
            last_date=str(seed_date.date()),
            entry_prices=entry_prices,
            shares=shares,
            last_prices=entry_prices.copy(),
            per_stock_v2=True,
        )
        rows = [{
            "date": seed_date.date().isoformat(),
            "nav": nav0,
            "invested_pct": inv0 * 100,
            "daily_log_ret": 0.0,
            "regime": "Defensive (CAPE frothy, 38.0)",
            "holdings": ", ".join(LIVE_TICKERS),
        }]
        pd.DataFrame(rows).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print(f"Seeded paper ledger at {seed_date.date()} (NAV={nav0:.2f}, invested={inv0*100:.1f}%, "
              f"trading cost so far={seed_cost:.2f})")
        print(f"\nRuntime: {time.time() - t0:.1f} seconds")
        return

    last_pos = common_index.get_indexer([last_date])[0]
    if last_pos < 0 or last_pos >= len(common_index) - 1:
        print("No new trading days since last update. Ledger unchanged.")
        print(f"\nRuntime: {time.time() - t0:.1f} seconds")
        return

    new_rows = []
    for i in range(last_pos + 1, len(common_index)):
        row, prev = market_df.iloc[i], market_df.iloc[i - 1]
        prev_nav = state["nav"]
        px_today = {t: float(prices[t].iloc[i]) for t in LIVE_TICKERS}
        state = _step(row, prev, state, CFG, blended.iloc[i], cash_daily.iloc[i],
                      px_today, float(cash_daily.iloc[i]))
        daily_log_ret = np.log(state["nav"] / prev_nav)
        date = common_index[i]
        new_rows.append({
            "date": date.date().isoformat(),
            "nav": state["nav"],
            "invested_pct": state["invested"] * 100,
            "daily_log_ret": daily_log_ret,
            "regime": "Defensive (CAPE frothy, 38.0)",
            "holdings": ", ".join(LIVE_TICKERS),
        })
        state["last_date"] = str(date.date())

    state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in LIVE_TICKERS}

    existing = pd.read_csv(LEDGER_PATH)
    updated = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated.to_csv(LEDGER_PATH, index=False)

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Appended {len(new_rows)} day(s). Latest NAV={state['nav']:.3f}, "
          f"invested={state['invested']*100:.1f}%, date={state['last_date']}")
    print(f"\nRuntime: {time.time() - t0:.1f} seconds")


if __name__ == "__main__":
    main()
