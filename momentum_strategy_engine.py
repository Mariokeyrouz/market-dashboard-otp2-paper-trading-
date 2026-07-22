"""
Momentum Strategy Engine — paper-trade advancement
==================================================
Daily NAV advancement for the single-stock momentum portfolio selected by
momentum_screener.py. Deliberately simpler than factor_strategy_engine.py:
the monthly SPY-trend decision is already baked into the selection (empty
holdings == risk-off == cash), so the engine has no separate daily stop — it
just holds the month's equal-weight picks and marks them to market, with cash
earning the T-bill rate. Rebalances whenever the screener writes a new
selection (new `as_of`).

  * Equal weight across the top-20 momentum names (5% each) when risk-on.
  * 100% cash (T-bill) when the selection is empty (risk-off).
  * 10 bps slippage on traded dollars at each rebalance.
  * Ledger / state schema matches factor_strategy_engine.py so
    pages/7_Portfolio_Analytics.py reads it unchanged.

Usage:
  py momentum_strategy_engine.py       # seeds on first run, else appends days
"""

import json
import os
import time

import numpy as np
import pandas as pd

from strategy_deep_test import download, download_tbill

LEDGER_PATH    = "momentum_ledger.csv"
STATE_PATH     = "momentum_state.json"
SELECTION_PATH = "momentum_selection.json"
BENCHMARK      = "SPY"
START_NAV      = 10_000.0
SLIPPAGE_RATE  = 0.001          # 10 bps on traded dollars


def _load_selection():
    if not os.path.exists(SELECTION_PATH):
        raise FileNotFoundError(f"No {SELECTION_PATH}. Run momentum_screener.py first.")
    with open(SELECTION_PATH) as f:
        return json.load(f)


def _download_prices(tickers):
    closes = {}
    for tkr in tickers:
        try:
            closes[tkr] = download(tkr)["Close"].squeeze()
        except Exception as e:
            print(f"  WARNING: failed to download {tkr}: {e}")
    return closes


def _buy_equal_weight(nav, tickers, weights, px):
    """Spend `nav`*invested on the tickers at equal (weight) allocation; return
    (shares, entry_prices, invested_dollars, cash_dollars, cost)."""
    invested_frac = sum(weights.values())               # 1.0 risk-on, 0.0 risk-off
    target_stock = invested_frac * nav
    cost = target_stock * SLIPPAGE_RATE                 # buying from all-cash
    nav_after = nav - cost
    target_stock = invested_frac * nav_after
    shares, entry = {}, {}
    for t in tickers:
        alloc = target_stock * (weights[t] / invested_frac) if invested_frac > 0 else 0.0
        entry[t] = px[t] * (1 + SLIPPAGE_RATE)
        shares[t] = alloc / entry[t] if entry[t] > 0 else 0.0
    return shares, entry, target_stock, nav_after - target_stock, cost


def main():
    t0 = time.time()
    selection = _load_selection()
    tickers = list(selection["holdings"].keys())
    weights = {t: selection["holdings"][t]["target_weight"] for t in tickers}
    risk_on = selection.get("risk_on", len(tickers) > 0)
    as_of = selection["as_of"]

    print(f"Momentum selection ({as_of}): "
          f"{'RISK-ON, ' + str(len(tickers)) + ' names' if risk_on else 'RISK-OFF (cash)'}")

    # Always need SPY for the trading calendar + cash accrual timing.
    dl = _download_prices(tickers + [BENCHMARK])
    spy = dl[BENCHMARK]
    tickers = [t for t in tickers if t in dl]
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    prices = pd.DataFrame({t: dl[t] for t in tickers}) if tickers else pd.DataFrame(index=spy.index)
    common_index = spy.dropna().index
    for t in tickers:
        common_index = common_index.intersection(dl[t].dropna().index)
    spy = spy.reindex(common_index)
    if tickers:
        prices = prices.reindex(common_index)
    cash_daily = tbill_raw.reindex(common_index).ffill().bfill() / 252

    print(f"Calendar: {common_index[0].date()} -> {common_index[-1].date()} "
          f"({len(common_index):,} days)")

    # ── Seed on first run ────────────────────────────────────────────────────
    if not os.path.exists(STATE_PATH):
        seed_idx = len(common_index) - 1
        seed_date = common_index[seed_idx]
        px0 = {t: float(prices[t].iloc[seed_idx]) for t in tickers}
        shares, entry, inv_dollars, cash_dollars, cost = _buy_equal_weight(
            START_NAV, tickers, weights, px0)
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
        print(f"Seeded momentum ledger at {seed_date.date()} "
              f"(NAV={nav0:.2f}, {'invested' if risk_on else 'cash'}, "
              f"{len(tickers)} names, cost={cost:.2f})")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── Load state, rebalance if the screener produced a new selection ───────
    with open(STATE_PATH) as f:
        state = json.load(f)

    if state.get("last_selection_asof") != as_of:
        print(f"  Rebalance: selection {state.get('last_selection_asof')} -> {as_of}")
        last_px = {t: float(prices[t].iloc[-1]) for t in tickers}
        old = state["shares"]
        old_px = state.get("last_prices", {})
        stock_val = sum(old[t] * old_px.get(t, last_px.get(t, 0)) for t in old)
        nav_now = stock_val + state["cash_dollars"]
        sell_cost = stock_val * SLIPPAGE_RATE            # liquidate to cash first
        nav_now -= sell_cost
        shares, entry, inv_dollars, cash_dollars, buy_cost = _buy_equal_weight(
            nav_now, tickers, weights, last_px)
        state.update(
            shares=shares, entry_prices=entry, invested_dollars=inv_dollars,
            cash_dollars=cash_dollars, nav=nav_now - buy_cost,
            invested=1.0 if risk_on else 0.0, risk_on=risk_on,
            target_weights=weights, last_selection_asof=as_of,
            last_rebalance_date=str(common_index[-1].date()),
            trading_cost=state.get("trading_cost", 0.0) + sell_cost + buy_cost,
        )

    last_date = pd.Timestamp(state["last_date"])
    last_pos = common_index.get_indexer([last_date])[0]
    if last_pos < 0 or last_pos >= len(common_index) - 1:
        state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in tickers}
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
        print("No new trading days since last update. Ledger unchanged.")
        print(f"Runtime: {time.time()-t0:.1f}s")
        return

    # ── Advance day by day (buy & hold the month's picks; cash accrues) ──────
    new_rows = []
    for i in range(last_pos + 1, len(common_index)):
        date = common_index[i]
        prev_nav = state["nav"]
        stock_val = sum(state["shares"][t] * float(prices[t].iloc[i]) for t in tickers)
        state["cash_dollars"] *= (1.0 + float(cash_daily.iloc[i]))
        nav = stock_val + state["cash_dollars"]
        state["nav"] = nav
        state["invested_dollars"] = stock_val
        state["peak_nav"] = max(state["peak_nav"], nav)
        daily_log_ret = np.log(nav / prev_nav) if prev_nav > 0 else 0.0
        new_rows.append({
            "date": date.date().isoformat(), "nav": nav,
            "invested_pct": (stock_val / nav * 100) if nav > 0 else 0.0,
            "daily_log_ret": daily_log_ret, "risk_on": state["risk_on"],
            "peak_nav": state["peak_nav"],
            "holdings": ", ".join(tickers) if tickers else "(cash)",
        })
        state["last_date"] = str(date.date())

    state["last_prices"] = {t: float(prices[t].iloc[-1]) for t in tickers}
    existing = pd.read_csv(LEDGER_PATH)
    pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True).to_csv(LEDGER_PATH, index=False)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Appended {len(new_rows)} day(s). NAV={state['nav']:.2f}, "
          f"{'invested' if state['risk_on'] else 'cash'}, "
          f"peak={state['peak_nav']:.2f}, date={state['last_date']}")
    print(f"Runtime: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
