"""
Momentum Daily Strategy Engine — paper-trade advancement
===========================================================
Live implementation of the finding in momentum_trend_gate_control.py /
momentum_walkforward_fix_verify.py: the existing (live) Momentum strategy's
SPY-10-month-SMA exposure check only runs once a month, at the same time as
the stock rotation. Checking the IDENTICAL rule every trading day instead —
instant on/off, no VIX, no smoothing, no gradual reload — backtested best of
everything tested in that research thread (full-sample Sharpe 1.419 vs the
live config's 0.841; beats a VIX-based trigger and several re-entry-filter
variants on every window tested).

Two components, deliberately kept separate (mirrors the backtest exactly):
  * Out-pace (WHICH stocks): momentum_daily_screener.py's monthly,
    unconditional top-20 blended-momentum selection.
  * Out-time (IN or OUT): this engine's own daily SPY vs 210-trading-day
    (~10-month) SMA check — same-day close vs same-day trailing SMA, binary,
    instant, re-evaluated every day regardless of the monthly rotation.

Explicit design choices (user-specified, deviates from every other engine
in this repo):
  * Cash is held as LITERAL cash — 0% return. Every other engine here earns
    the T-bill rate while in cash; this one deliberately does not, so its
    numbers aren't flattered by a risk-free carry the backtest didn't credit
    either. No download_tbill() call at all.
  * 10 bps slippage (SLIPPAGE_RATE, matches the repo-wide convention) is
    charged on BOTH kinds of trade this engine makes: the monthly stock
    rotation (as in every other engine) AND every daily exposure flip
    (entering or exiting the market) — a cost the monthly-only gate never
    has to pay as often, so this is the fair, cost-loaded comparison.

Ledger / state schema matches momentum_strategy_engine.py so
pages/11_Portfolio_Analytics.py reads it unchanged (same field names).

Usage:
  py momentum_daily_strategy_engine.py       # seeds on first run, else appends days
"""

import json
import os
import time

import numpy as np
import pandas as pd

from strategy_deep_test import download_many
from event_log import log_event
from blotter import record_fills

LEDGER_PATH    = "momentum_daily_ledger.csv"
STATE_PATH     = "momentum_daily_state.json"
SELECTION_PATH = "momentum_daily_selection.json"
BENCHMARK      = "SPY"
START_NAV      = 10_000.0
SLIPPAGE_RATE  = 0.001          # 10 bps on traded dollars
TREND_SMA_DAYS = 210            # ~10 trading months, daily-checked


def _load_selection():
    if not os.path.exists(SELECTION_PATH):
        raise FileNotFoundError(f"No {SELECTION_PATH}. Run momentum_daily_screener.py first.")
    with open(SELECTION_PATH) as f:
        return json.load(f)


def _download_prices(tickers):
    raw = download_many(tickers)
    return {t: raw[t]["Close"].squeeze() for t in tickers if t in raw}


def _buy_equal_weight(cash_available, tickers, weights, px):
    """Spend all of `cash_available` on `tickers` at equal (weight) allocation.
    Returns (shares, entry_prices, invested_dollars, cash_remaining, cost)."""
    cost = cash_available * SLIPPAGE_RATE
    to_invest = cash_available - cost
    shares, entry = {}, {}
    for t in tickers:
        alloc = to_invest * weights[t]
        entry[t] = px[t] * (1 + SLIPPAGE_RATE)
        shares[t] = alloc / entry[t] if entry[t] > 0 else 0.0
    return shares, entry, to_invest, cash_available - cost - to_invest, cost


def _sell_all(shares, px):
    """Liquidate every position at `px` (today's marks), net of slippage.
    Returns (proceeds, cost, realized_pnl) — realized_pnl needs entry_prices
    passed in by the caller since this helper only handles the cash math."""
    stock_val = sum(shares[t] * px.get(t, 0.0) for t in shares)
    cost = stock_val * SLIPPAGE_RATE
    return stock_val - cost, cost


def main():
    t0 = time.time()
    selection = _load_selection()
    tickers = list(selection["holdings"].keys())
    weights = {t: selection["holdings"][t]["target_weight"] for t in tickers}
    as_of = selection["as_of"]

    print(f"Momentum Daily selection ({as_of}): {len(tickers)} names "
          f"(unconditional — exposure decided daily, not by the screener)")

    dl = _download_prices(tickers + [BENCHMARK])
    spy_full = dl[BENCHMARK]
    spy_sma_full = spy_full.rolling(TREND_SMA_DAYS).mean()
    tickers = [t for t in tickers if t in dl]

    common_index = spy_full.dropna().index
    for t in tickers:
        common_index = common_index.intersection(dl[t].dropna().index)
    common_index = common_index.intersection(spy_sma_full.dropna().index)
    spy = spy_full.reindex(common_index)
    spy_sma = spy_sma_full.reindex(common_index)
    prices = pd.DataFrame({t: dl[t] for t in tickers}).reindex(common_index) if tickers else pd.DataFrame(index=common_index)

    print(f"Common index: {common_index[0].date()} -> {common_index[-1].date()} "
          f"({len(common_index):,} days). Cash is held as literal cash (0% return), not T-bill.")

    # ── Seed on first run ────────────────────────────────────────────────────
    if not os.path.exists(STATE_PATH):
        seed_idx = len(common_index) - 1
        seed_date = common_index[seed_idx]
        risk_on = bool(spy.iloc[seed_idx] > spy_sma.iloc[seed_idx])
        px0 = {t: float(prices[t].iloc[seed_idx]) for t in tickers}

        if risk_on:
            shares, entry, inv_dollars, cash_dollars, cost = _buy_equal_weight(
                START_NAV, tickers, weights, px0)
        else:
            shares, entry, inv_dollars, cash_dollars, cost = {}, {}, 0.0, START_NAV, 0.0
        nav0 = START_NAV - cost

        state = dict(
            nav=nav0, peak_nav=nav0, invested=1.0 if risk_on else 0.0,
            risk_on=risk_on, cash_dollars=cash_dollars, invested_dollars=inv_dollars,
            shares=shares, entry_prices=entry, target_weights=weights,
            last_prices=px0, last_date=str(seed_date.date()),
            last_selection_asof=as_of, trading_cost=cost,
            last_rebalance_date=str(seed_date.date()),
        )
        pd.DataFrame([{
            "date": seed_date.date().isoformat(), "nav": nav0,
            "invested_pct": (1.0 if risk_on else 0.0) * 100, "daily_log_ret": 0.0,
            "risk_on": risk_on, "peak_nav": nav0,
            "holdings": ", ".join(tickers) if risk_on else "(cash)",
        }]).to_csv(LEDGER_PATH, index=False)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        record_fills("Momentum Daily", str(seed_date.date()), {}, shares, entry,
                     {}, SLIPPAGE_RATE, reason="seed")
        print(f"Seeded momentum-daily ledger at {seed_date.date()} "
              f"(NAV={nav0:.2f}, {'invested' if risk_on else 'cash'}, "
              f"{len(tickers) if risk_on else 0} names, cost={cost:.2f})")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── Load state ────────────────────────────────────────────────────────────
    with open(STATE_PATH) as f:
        state = json.load(f)

    # Monthly stock rotation: fires once, using the latest available prices,
    # same simplification the existing Momentum engine uses for a multi-day
    # catch-up gap. Only actually trades if currently invested — if in cash,
    # this just updates target_weights for whenever exposure next flips on.
    if state.get("last_selection_asof") != as_of:
        print(f"  Stock rotation: selection {state.get('last_selection_asof')} -> {as_of}")
        last_px = {t: float(prices[t].iloc[-1]) for t in tickers}
        if state["risk_on"] and state["shares"]:
            old = state["shares"]
            old_entry = state.get("entry_prices", {}) or {}
            old_px = state.get("last_prices", {})
            _exit_prices = {t: old_px.get(t, last_px.get(t, 0.0)) for t in old}
            proceeds, sell_cost = _sell_all(old, _exit_prices)
            realized = sum(old[t] * (_exit_prices[t] - old_entry.get(t, _exit_prices[t])) for t in old) - sell_cost
            cash_after_sell = state["cash_dollars"] + proceeds
            shares, entry, inv_dollars, cash_dollars, buy_cost = _buy_equal_weight(
                cash_after_sell, tickers, weights, last_px)
            state.update(
                shares=shares, entry_prices=entry, invested_dollars=inv_dollars,
                cash_dollars=cash_dollars,
                trading_cost=state.get("trading_cost", 0.0) + sell_cost + buy_cost,
            )
            log_event("Momentum Daily", "rebalance",
                      f"Stock rotation while invested ({as_of})",
                      date=str(common_index[-1].date()), realized_pnl=realized,
                      tickers=[t for t in tickers if t not in old] or list(tickers))
            record_fills("Momentum Daily", str(common_index[-1].date()), old, shares,
                         {**_exit_prices, **entry}, old_entry, SLIPPAGE_RATE, reason="rebalance")
        state["target_weights"] = weights
        state["last_selection_asof"] = as_of
        state["last_rebalance_date"] = str(common_index[-1].date())

    last_date = pd.Timestamp(state["last_date"])
    last_pos = common_index.searchsorted(last_date, side="right") - 1
    if last_pos < 0:
        print(f"  [WARN] last recorded date {last_date.date()} predates the entire aligned "
              f"trading-day index (earliest available: {common_index[0].date()}). Skipping this "
              f"run — investigate if this persists.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return
    if last_pos >= len(common_index) - 1:
        state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in tickers}
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print("No new trading days since last update. Ledger unchanged.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return
    if common_index[last_pos] != last_date:
        print(f"  [note] {last_date.date()} is absent from today's aligned trading-day index "
              f"(a source likely lacked that single day) — resuming from "
              f"{common_index[last_pos].date()} instead.")

    # ── Advance day by day, checking the exposure gate EVERY day ─────────────
    new_rows = []
    n_flips = 0
    for i in range(last_pos + 1, len(common_index)):
        date = common_index[i]
        prev_nav = state["nav"]
        px_today = {t: float(prices[t].iloc[i]) for t in tickers}
        risk_on_today = bool(spy.iloc[i] > spy_sma.iloc[i])

        if risk_on_today and not state["risk_on"]:
            # Flip 0 -> 1: enter the market with today's target basket.
            shares, entry, inv_dollars, cash_dollars, cost = _buy_equal_weight(
                state["cash_dollars"], tickers, state["target_weights"], px_today)
            state.update(shares=shares, entry_prices=entry, invested_dollars=inv_dollars,
                        cash_dollars=cash_dollars, risk_on=True, invested=1.0,
                        trading_cost=state.get("trading_cost", 0.0) + cost)
            log_event("Momentum Daily", "risk-on",
                      f"SPY crossed above its {TREND_SMA_DAYS}-day SMA — entering",
                      date=str(date.date()))
            record_fills("Momentum Daily", str(date.date()), {}, shares, entry,
                         {}, SLIPPAGE_RATE, reason="risk-on")
            n_flips += 1
        elif (not risk_on_today) and state["risk_on"]:
            # Flip 1 -> 0: exit to cash with today's marks.
            old = state["shares"]
            old_entry = state.get("entry_prices", {}) or {}
            proceeds, cost = _sell_all(old, px_today)
            realized = sum(old[t] * (px_today.get(t, 0.0) - old_entry.get(t, px_today.get(t, 0.0))) for t in old) - cost
            state.update(shares={}, entry_prices={}, invested_dollars=0.0,
                        cash_dollars=state["cash_dollars"] + proceeds,
                        risk_on=False, invested=0.0,
                        trading_cost=state.get("trading_cost", 0.0) + cost)
            log_event("Momentum Daily", "risk-off",
                      f"SPY crossed below its {TREND_SMA_DAYS}-day SMA — exiting to cash",
                      date=str(date.date()), realized_pnl=realized, tickers=list(old))
            record_fills("Momentum Daily", str(date.date()), old, {},
                         px_today, old_entry, SLIPPAGE_RATE, reason="risk-off")
            n_flips += 1

        stock_val = sum(state["shares"].get(t, 0.0) * px_today.get(t, 0.0) for t in state["shares"])
        nav = stock_val + state["cash_dollars"]              # cash: literal, no accrual
        state["nav"] = nav
        state["invested_dollars"] = stock_val
        state["peak_nav"] = max(state["peak_nav"], nav)
        daily_log_ret = np.log(nav / prev_nav) if prev_nav > 0 else 0.0
        new_rows.append({
            "date": date.date().isoformat(), "nav": nav,
            "invested_pct": (stock_val / nav * 100) if nav > 0 else 0.0,
            "daily_log_ret": daily_log_ret, "risk_on": state["risk_on"],
            "peak_nav": state["peak_nav"],
            "holdings": ", ".join(state["shares"].keys()) if state["shares"] else "(cash)",
        })
        state["last_date"] = str(date.date())

    state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in tickers}
    existing = pd.read_csv(LEDGER_PATH)
    pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True).to_csv(LEDGER_PATH, index=False)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Appended {len(new_rows)} day(s), {n_flips} exposure flip(s). NAV={state['nav']:.2f}, "
          f"{'invested' if state['risk_on'] else 'cash'}, "
          f"peak={state['peak_nav']:.2f}, date={state['last_date']}")
    print(f"Runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
