"""
Factor Strategy Engine — Aggressive Factor Portfolio
=====================================================
Daily advancement engine for the factor-score-weighted portfolio with
trailing stop risk management.

Strategy rules:
  - 15-20 stocks selected monthly by factor_screener.py
  - Weights proportional to composite factor score
  - Portfolio-level trailing stop: if NAV falls 9% from peak → scale to 50% invested
  - Re-entry: when 20-day realized vol drops below its 60-day SMA (sellers exhausted)
  - Cash earns T-bill rate
  - 10 bps slippage on all trades

Usage:
  python factor_strategy_engine.py
"""

import json
import os
import time
import numpy as np
import pandas as pd

from strategy_deep_test import download, download_tbill, build_market_features

LEDGER_PATH    = "factor_ledger.csv"
STATE_PATH     = "factor_state.json"
SELECTION_PATH = "factor_selection.json"
START_NAV      = 10_000.0
SLIPPAGE_RATE  = 0.001          # 10 bps round-trip
STOP_THRESHOLD = 0.09           # 9% trailing drawdown → trigger
TARGET_INVEST  = 1.0            # fully invested when not stopped
STOPPED_INVEST = 0.50           # scale to 50% when stopped
RVOL_SHORT     = 20             # rvol window for re-entry signal
RVOL_LONG_SMA  = 60             # rvol SMA for re-entry signal


def _load_selection():
    """Load the latest factor_selection.json output."""
    if not os.path.exists(SELECTION_PATH):
        raise FileNotFoundError(
            f"No {SELECTION_PATH} found. Run factor_screener.py first."
        )
    with open(SELECTION_PATH) as f:
        sel = json.load(f)
    return sel


def _build_rvol_sma(market_df):
    """Compute 60-day SMA of the 20-day realized vol column."""
    market_df = market_df.copy()
    market_df["rvol_sma60"] = market_df["rvol20"].rolling(RVOL_LONG_SMA).mean()
    return market_df


def _step(state, px_today, market_row, cash_ret_simple):
    """
    Advance state by one trading day.

    Trailing stop logic:
      - Update peak_nav each day
      - If NAV drops 9% from peak AND not already stopped → scale to 50% invested
      - If stopped AND rvol20 < rvol_sma60 → re-enter (scale back to 100%)

    Share bookkeeping mirrors paper_trading_engine.py exactly.
    """
    tickers      = list(state["shares"].keys())
    shares       = state["shares"]
    entry_prices = state["entry_prices"]

    # 1. Mark holdings to today's prices; apply cash return
    stock_value = sum(shares[t] * px_today[t] for t in tickers if t in px_today)
    cash_dollars = state["cash_dollars"] * (1.0 + cash_ret_simple)
    nav = stock_value + cash_dollars

    # 2. Update peak NAV
    peak_nav = max(state["peak_nav"], nav)

    # 3. Trailing stop check
    stopped_out = state["stopped_out"]
    drawdown_from_peak = (peak_nav - nav) / peak_nav if peak_nav > 0 else 0.0

    if not stopped_out and drawdown_from_peak >= STOP_THRESHOLD:
        stopped_out = True
        state["stop_date"] = str(pd.Timestamp.today().date())
        print(f"    *** TRAILING STOP TRIGGERED — drawdown {drawdown_from_peak*100:.2f}% from peak ***")

    # 4. Re-entry check (only when stopped)
    rvol20   = float(market_row.get("rvol20",  np.nan))
    rvol_sma = float(market_row.get("rvol_sma60", np.nan))
    if stopped_out and not np.isnan(rvol20) and not np.isnan(rvol_sma):
        if rvol20 < rvol_sma:
            stopped_out = False
            state["stop_date"] = None
            print(f"    *** RE-ENTRY SIGNAL — rvol20 {rvol20:.4f} < rvol_sma60 {rvol_sma:.4f} ***")

    # 5. Determine target invested fraction
    target_inv = STOPPED_INVEST if stopped_out else TARGET_INVEST

    # 6. Rebalance: scale shares to hit target_inv (preserve relative weights)
    target_stock = target_inv * nav
    traded_dollars = abs(target_stock - stock_value)
    cost = traded_dollars * SLIPPAGE_RATE
    nav_after = nav - cost
    target_stock = target_inv * nav_after

    if stock_value > 1e-9:
        factor = target_stock / stock_value
    else:
        factor = 0.0

    for t in tickers:
        if t not in px_today:
            continue
        old_sh = shares[t]
        new_sh = old_sh * factor
        if new_sh > old_sh:
            bought = new_sh - old_sh
            entry_prices[t] = (old_sh * entry_prices[t] + bought * px_today[t]) / new_sh
        shares[t] = new_sh

    cash_dollars = nav_after - target_stock

    state["nav"]            = nav_after
    state["peak_nav"]       = peak_nav
    state["invested"]       = target_inv
    state["stopped_out"]    = stopped_out
    state["shares"]         = shares
    state["entry_prices"]   = entry_prices
    state["invested_dollars"] = target_stock
    state["cash_dollars"]   = cash_dollars
    state["trading_cost"]   = state.get("trading_cost", 0.0) + cost
    return state


def main():
    t0 = time.time()

    selection = _load_selection()
    tickers   = list(selection["holdings"].keys())
    weights   = {t: selection["holdings"][t]["target_weight"] for t in tickers}

    print(f"Factor selection ({selection['as_of']}): {', '.join(tickers)}")
    print(f"Downloading market data...")

    gspc = download("^GSPC")
    vix  = download("^VIX")
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    print(f"Downloading {len(tickers)} portfolio tickers...")
    closes = {}
    for tkr in tickers:
        try:
            df = download(tkr)
            closes[tkr] = df["Close"].squeeze()
        except Exception as e:
            print(f"  WARNING: failed to download {tkr}: {e}")

    # Remove any tickers that failed to download
    tickers = [t for t in tickers if t in closes]

    market_df = build_market_features(gspc, vix)
    market_df = _build_rvol_sma(market_df)

    prices = pd.DataFrame({t: closes[t] for t in tickers})

    # Align indices
    common_index = market_df.index
    for t in tickers:
        common_index = common_index.intersection(closes[t].dropna().index)
    market_df = market_df.loc[common_index]
    prices    = prices.loc[common_index]

    cash_daily = tbill_raw.reindex(common_index).ffill().bfill() / 252

    print(f"Common index: {common_index[0].date()} to {common_index[-1].date()} "
          f"({len(common_index):,} trading days)")

    # ── Load or seed state ────────────────────────────────────────────────────
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)

        # If tickers have changed (monthly rebalance), update holdings
        held_tickers = list(state["shares"].keys())
        if set(held_tickers) != set(tickers):
            print(f"  Portfolio rebalance: {held_tickers} → {tickers}")
            # Get last prices for old + new holdings
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
            per_ticker = target_stock / len(tickers)
            # Buy into new weights at today's prices
            entry_prices = {t: float(last_px[t]) * (1 + SLIPPAGE_RATE) for t in tickers}
            shares_new = {t: (per_ticker * weights[t] * len(tickers)) / entry_prices[t]
                         if weights[t] > 0 else 0.0 for t in tickers}
            state["shares"]         = shares_new
            state["entry_prices"]   = entry_prices
            state["invested_dollars"] = target_stock
            state["cash_dollars"]   = nav_now - target_stock
            state["nav"]            = nav_now
            state["trading_cost"]   = state.get("trading_cost", 0.0) + cost
            state["target_weights"] = weights

        last_date = pd.Timestamp(state["last_date"])

    else:
        # Seed: enter at last available trading day
        seed_idx   = len(common_index) - 1
        seed_date  = common_index[seed_idx]
        seed_cost  = START_NAV * TARGET_INVEST * SLIPPAGE_RATE
        nav0       = START_NAV - seed_cost
        target_stk = nav0 * TARGET_INVEST
        last_px    = {t: float(prices[t].iloc[seed_idx]) for t in tickers}
        entry_prices = {t: last_px[t] * (1 + SLIPPAGE_RATE) for t in tickers}
        # Allocate proportional to factor-score weights
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
            "date":         seed_date.date().isoformat(),
            "nav":          nav0,
            "invested_pct": TARGET_INVEST * 100,
            "daily_log_ret": 0.0,
            "stopped_out":  False,
            "peak_nav":     nav0,
            "holdings":     ", ".join(tickers),
        }]
        pd.DataFrame(row0).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print(f"Seeded factor ledger at {seed_date.date()} "
              f"(NAV={nav0:.2f}, invested={TARGET_INVEST*100:.0f}%, "
              f"tickers={len(tickers)}, seed_cost={seed_cost:.2f})")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── Advance from last date ────────────────────────────────────────────────
    last_pos = common_index.get_indexer([last_date])[0]
    if last_pos < 0 or last_pos >= len(common_index) - 1:
        print("No new trading days since last update. Ledger unchanged.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    new_rows = []
    for i in range(last_pos + 1, len(common_index)):
        date    = common_index[i]
        mrow    = market_df.iloc[i]
        px_today = {t: float(prices[t].iloc[i]) for t in tickers if t in prices.columns}
        prev_nav = state["nav"]

        state = _step(state, px_today, mrow, float(cash_daily.iloc[i]))

        daily_log_ret = np.log(state["nav"] / prev_nav) if prev_nav > 0 else 0.0
        new_rows.append({
            "date":         date.date().isoformat(),
            "nav":          state["nav"],
            "invested_pct": state["invested"] * 100,
            "daily_log_ret": daily_log_ret,
            "stopped_out":  state["stopped_out"],
            "peak_nav":     state["peak_nav"],
            "holdings":     ", ".join(tickers),
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
