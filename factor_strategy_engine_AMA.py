"""
Factor Strategy Engine AMA — AlphaMind Adjusted
================================================
Identical to factor_strategy_engine.py except reads from factor_selection_AMA.json
and writes to factor_state_AMA.json + factor_ledger_AMA.csv.

The engine logic is unchanged — the AMA adjustment is in the screener (SUE replaces Value).

Usage:
  python factor_strategy_engine_AMA.py
"""

import json
import os
import time
import numpy as np
import pandas as pd

from strategy_deep_test import download_many, build_market_features
from event_log import log_event
from blotter import record_fills

LEDGER_PATH    = "factor_ledger_AMA.csv"
STATE_PATH     = "factor_state_AMA.json"
SELECTION_PATH = "factor_selection_AMA.json"
START_NAV      = 10_000.0
SLIPPAGE_RATE  = 0.001
STOP_THRESHOLD = 0.09
TARGET_INVEST  = 1.0
STOPPED_INVEST = 0.50
RVOL_SHORT     = 20
RVOL_LONG_SMA  = 60


def _load_selection():
    if not os.path.exists(SELECTION_PATH):
        raise FileNotFoundError(
            f"No {SELECTION_PATH} found. Run factor_screener_AMA.py first."
        )
    with open(SELECTION_PATH) as f:
        sel = json.load(f)
    return sel


def _build_rvol_sma(market_df):
    market_df = market_df.copy()
    market_df["rvol_sma60"] = market_df["rvol20"].rolling(RVOL_LONG_SMA).mean()
    return market_df


def _step(state, px_today, market_row, date_str=None):
    tickers      = list(state["shares"].keys())
    shares       = state["shares"]
    entry_prices = state["entry_prices"]

    # Cash earns nothing while stopped out
    stock_value  = sum(shares[t] * px_today[t] for t in tickers if t in px_today)
    cash_dollars = state["cash_dollars"]
    nav          = stock_value + cash_dollars

    peak_nav     = max(state["peak_nav"], nav)
    stopped_out  = state["stopped_out"]
    drawdown_from_peak = (peak_nav - nav) / peak_nav if peak_nav > 0 else 0.0

    if not stopped_out and drawdown_from_peak >= STOP_THRESHOLD:
        stopped_out = True
        state["stop_date"] = str(pd.Timestamp.today().date())
        print(f"    *** TRAILING STOP TRIGGERED — drawdown {drawdown_from_peak*100:.2f}% from peak ***")

    rvol20   = float(market_row.get("rvol20",     np.nan))
    rvol_sma = float(market_row.get("rvol_sma60", np.nan))
    if stopped_out and not np.isnan(rvol20) and not np.isnan(rvol_sma):
        if rvol20 < rvol_sma:
            stopped_out = False
            state["stop_date"] = None
            print(f"    *** RE-ENTRY SIGNAL — rvol20 {rvol20:.4f} < rvol_sma60 {rvol_sma:.4f} ***")

    target_inv   = STOPPED_INVEST if stopped_out else TARGET_INVEST
    target_stock = target_inv * nav
    traded_dollars = abs(target_stock - stock_value)
    cost         = traded_dollars * SLIPPAGE_RATE
    nav_after    = nav - cost
    target_stock = target_inv * nav_after

    factor = (target_stock / stock_value) if stock_value > 1e-9 else 0.0

    was_stopped = state["stopped_out"]
    prev_shares = dict(shares)
    prev_entry_prices = dict(entry_prices)

    for t in tickers:
        if t not in px_today:
            continue
        old_sh = shares[t]
        new_sh = old_sh * factor
        if new_sh > old_sh:
            bought = new_sh - old_sh
            entry_prices[t] = (old_sh * entry_prices[t] + bought * px_today[t]) / new_sh
        shares[t] = new_sh

    if not was_stopped and stopped_out:
        fill_reason = "stop"
    elif was_stopped and not stopped_out:
        fill_reason = "reentry"
    else:
        fill_reason = "vol-target"
    if date_str is not None:
        record_fills("FMTS AMA", date_str, prev_shares, shares, px_today,
                     prev_entry_prices, SLIPPAGE_RATE, reason=fill_reason)

    cash_dollars = nav_after - target_stock

    state["nav"]              = nav_after
    state["peak_nav"]         = peak_nav
    state["invested"]         = target_inv
    state["stopped_out"]      = stopped_out
    state["shares"]           = shares
    state["entry_prices"]     = entry_prices
    state["invested_dollars"] = target_stock
    state["cash_dollars"]     = cash_dollars
    state["trading_cost"]     = state.get("trading_cost", 0.0) + cost
    return state


def main():
    t0 = time.time()

    selection = _load_selection()
    tickers   = list(selection["holdings"].keys())
    weights   = {t: selection["holdings"][t]["target_weight"] for t in tickers}

    print(f"Factor AMA selection ({selection['as_of']}): {', '.join(tickers)}")
    print(f"Downloading market data...")

    print(f"Downloading {len(tickers)} portfolio tickers...")
    raw  = download_many(["^GSPC", "^VIX"] + tickers)
    gspc = raw["^GSPC"]
    vix  = raw["^VIX"]

    closes = {t: raw[t]["Close"].squeeze() for t in tickers if t in raw}

    tickers = [t for t in tickers if t in closes]

    market_df = build_market_features(gspc, vix)
    market_df = _build_rvol_sma(market_df)

    prices = pd.DataFrame({t: closes[t] for t in tickers})

    common_index = market_df.index
    for t in tickers:
        common_index = common_index.intersection(closes[t].dropna().index)
    market_df = market_df.loc[common_index]
    prices    = prices.loc[common_index]

    print(f"Common index: {common_index[0].date()} to {common_index[-1].date()} "
          f"({len(common_index):,} trading days)")

    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)

        held_tickers = list(state["shares"].keys())
        if set(held_tickers) != set(tickers):
            print(f"  Portfolio rebalance: {held_tickers} to {tickers}")
            last_px = {t: float(prices[t].iloc[-1]) for t in tickers if t in prices.columns}
            stock_val = sum(state["shares"].get(t, 0) * state.get("last_prices", {}).get(t, last_px.get(t, 0))
                            for t in held_tickers)
            cash_val  = state["cash_dollars"]
            nav_now   = stock_val + cash_val
            inv_frac  = state["invested"]
            target_stock = inv_frac * nav_now
            cost = abs(target_stock - stock_val) * SLIPPAGE_RATE
            nav_now -= cost
            target_stock = inv_frac * nav_now
            entry_prices = {t: float(last_px[t]) * (1 + SLIPPAGE_RATE) for t in tickers}
            shares_new = {t: (target_stock * weights[t]) / entry_prices[t]
                         if weights[t] > 0 else 0.0 for t in tickers}
            # Realized P&L of the outgoing book (sale proceeds vs cost basis, net of slippage).
            _osh = state["shares"]; _oep = state.get("entry_prices", {}) or {}
            _olp = state.get("last_prices", {}) or {}
            _realized = sum(_osh.get(t, 0) * (_olp.get(t, last_px.get(t, 0.0))
                            - _oep.get(t, _olp.get(t, last_px.get(t, 0.0)))) for t in held_tickers) - cost
            _dropped = [t for t in held_tickers if t not in tickers]
            _added = [t for t in tickers if t not in held_tickers]
            state["shares"]           = shares_new
            state["entry_prices"]     = entry_prices
            state["invested_dollars"] = target_stock
            state["cash_dollars"]     = nav_now - target_stock
            state["nav"]              = nav_now
            state["trading_cost"]     = state.get("trading_cost", 0.0) + cost
            state["target_weights"]   = weights
            log_event("FMTS AMA", "rebalance",
                      f"Rotated {len(_dropped)} out / {len(_added)} in ({selection['as_of']})",
                      date=str(common_index[-1].date()), realized_pnl=_realized, tickers=_added)
            _exit_prices = {t: _olp.get(t, last_px.get(t, 0.0)) for t in held_tickers}
            record_fills("FMTS AMA", str(common_index[-1].date()), _osh, shares_new,
                         {**_exit_prices, **entry_prices}, _oep, SLIPPAGE_RATE, reason="rebalance")

        last_date = pd.Timestamp(state["last_date"])

    else:
        seed_idx   = len(common_index) - 1
        seed_date  = common_index[seed_idx]
        seed_cost  = START_NAV * TARGET_INVEST * SLIPPAGE_RATE
        nav0       = START_NAV - seed_cost
        target_stk = nav0 * TARGET_INVEST
        last_px    = {t: float(prices[t].iloc[seed_idx]) for t in tickers}
        entry_prices = {t: last_px[t] * (1 + SLIPPAGE_RATE) for t in tickers}
        shares = {t: (target_stk * weights[t]) / entry_prices[t] for t in tickers}

        state = dict(
            nav=nav0,
            peak_nav=nav0,
            invested=TARGET_INVEST,
            stopped_out=False,
            stop_date=None,
            cash_dollars=nav0 * (1 - TARGET_INVEST),
            invested_dollars=target_stk,
            shares=shares,
            entry_prices=entry_prices,
            target_weights=weights,
            last_prices=last_px,
            last_date=str(seed_date.date()),
            trading_cost=seed_cost,
            last_rebalance_date=str(seed_date.date()),
        )

        row0 = [{
            "date":          seed_date.date().isoformat(),
            "nav":           nav0,
            "invested_pct":  TARGET_INVEST * 100,
            "daily_log_ret": 0.0,
            "stopped_out":   False,
            "peak_nav":      nav0,
            "holdings":      ", ".join(tickers),
        }]
        pd.DataFrame(row0).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        record_fills("FMTS AMA", str(seed_date.date()), {}, shares, entry_prices,
                     {}, SLIPPAGE_RATE, reason="seed")
        print(f"Seeded FMTS AMA ledger at {seed_date.date()} "
              f"(NAV={nav0:.2f}, invested={TARGET_INVEST*100:.0f}%, "
              f"tickers={len(tickers)}, seed_cost={seed_cost:.2f})")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # searchsorted (not get_indexer) so a single day missing from the aligned index — e.g.
    # one ticker permanently lacking that date upstream — doesn't stall the engine forever:
    # we resume from the last available date <= last_date instead of requiring an exact match.
    last_pos = common_index.searchsorted(last_date, side="right") - 1
    if last_pos < 0:
        print(f"  [WARN] last recorded date {last_date.date()} predates the entire aligned "
              f"trading-day index (earliest available: {common_index[0].date()}). Skipping this "
              f"run — investigate if this persists.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return
    if last_pos >= len(common_index) - 1:
        print("No new trading days since last update. Ledger unchanged.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return
    if common_index[last_pos] != last_date:
        print(f"  [note] {last_date.date()} is absent from today's aligned trading-day index "
              f"(a source likely lacked that single day) — resuming from "
              f"{common_index[last_pos].date()} instead.")

    new_rows = []
    for i in range(last_pos + 1, len(common_index)):
        date     = common_index[i]
        mrow     = market_df.iloc[i]
        px_today = {t: float(prices[t].iloc[i]) for t in tickers if t in prices.columns}
        prev_nav = state["nav"]

        state = _step(state, px_today, mrow, date.date().isoformat())

        daily_log_ret = np.log(state["nav"] / prev_nav) if prev_nav > 0 else 0.0
        new_rows.append({
            "date":          date.date().isoformat(),
            "nav":           state["nav"],
            "invested_pct":  state["invested"] * 100,
            "daily_log_ret": daily_log_ret,
            "stopped_out":   state["stopped_out"],
            "peak_nav":      state["peak_nav"],
            "holdings":      ", ".join(tickers),
        })
        state["last_date"] = str(date.date())

    state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in tickers if t in prices.columns}

    existing = pd.read_csv(LEDGER_PATH)
    updated  = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True)
    updated.to_csv(LEDGER_PATH, index=False)

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    stop_str = " [STOPPED 50%]" if state["stopped_out"] else ""
    print(f"Appended {len(new_rows)} day(s). NAV={state['nav']:.2f}, "
          f"invested={state['invested']*100:.0f}%{stop_str}, "
          f"peak_nav={state['peak_nav']:.2f}, date={state['last_date']}")
    print(f"Runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
