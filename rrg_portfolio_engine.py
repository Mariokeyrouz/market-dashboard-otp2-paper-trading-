"""
RRG Paper-Trading Engine
========================
Instantiates the RRG selection as an actual portfolio so it can be watched
position by position: shares, entry price, live price, market value, unrealized
P&L, weight and total NAV — the same treatment every other strategy in this
repo gets.

READ THIS BEFORE FUNDING ANYTHING
---------------------------------
The RRG signal FAILED its own pre-registered validation (1 of 9 criteria; see
rrg_validate.py). The walk-forward backtest turned $1 into $0.98 with a 50%
drawdown while an equal-weight sector basket made $1.12. `rrg_calibration.json`
therefore carries `sizing_multiplier: 0`, and the analysis recommends $0 of real
capital.

This engine exists anyway, for the reason every other paper book here exists:
to track forward, out of sample, whether the signal does anything. A failed
backtest is a hypothesis about the future, not a proof — but the burden of
evidence sits with the signal, and right now it has not met it. Nothing here
places a real order; it is a simulated ledger.

DIVERSIFICATION (changed 2026-08-07)
-------------------------------------
The book originally held N_HOLDINGS=5 names capped at 2 per sector, drawn from
a candidate pool of only the top 3 sectors (rrg_analysis.py's N_TOP_SECTORS).
Because those top sectors tend to be correlated with each other, that meant up
to 40% of the book sitting in a single sector on 5 names total — concentrated
enough that single-name and single-sector noise, not the RRG signal, was
driving most of the forward P&L swing. That's a bad way to test whether a
signal has edge, independent of whatever the signal's own merits are.

Now: 12 names, still capped at 2 per sector, drawn from a wider pool of the
top 6 sectors (rrg_analysis.py's N_CANDIDATE_SECTORS) — exactly 2 picks from
each of the 6 best-ranked sectors, ~8.3% each. Max single-sector exposure
drops from ~40% to ~16.7%. This does NOT change the validation verdict above;
it only makes the forward paper-P&L a cleaner read on the RRG signal itself
rather than on which 1-2 stocks happened to get picked.

State/ledger schema deliberately mirrors momentum_strategy_engine.py so the
existing tooling (Portfolio Analytics, Activity Log, run_daily_update.py) can
pick it up unchanged.

Usage:
  py rrg_portfolio_engine.py --seed        # create the book (once)
  py rrg_portfolio_engine.py               # mark to market / rebalance on schedule
  py rrg_portfolio_engine.py --rebalance   # force a rebalance today, regardless of
                                            # the 28-day schedule (e.g. after a
                                            # strategy-parameter change like this one)
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import yfinance as yf

try:
    from curl_cffi import requests as cffi_requests
    SESSION = cffi_requests.Session(impersonate="chrome")
except Exception:
    SESSION = None

LEDGER_PATH = "rrg_ledger.csv"
STATE_PATH = "rrg_state.json"
SELECTION_PATH = "rrg_selection.json"
CANDIDATES = "rrg_stock_candidates.csv"
SECTORS = "rrg_sector_results.csv"
CAL = "rrg_calibration.json"

START_NAV = 10_000.0
N_HOLDINGS = 12               # 2 per sector x rrg_analysis.py's N_CANDIDATE_SECTORS (6)
MAX_PER_SECTOR = 2            # stop one sector taking the whole book
SLIPPAGE_RATE = 0.001         # 10 bps on traded dollars, same as the other engines
REBALANCE_DAYS = 28           # monthly-ish, matching the weekly signal's horizon


def log(msg):
    print(f"[rrg] {msg}", flush=True)


def fetch_prices(tickers):
    """Live prices, NaN-hardened (a NaN close is a float and passes `is not None`)."""
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d", interval="1d")
            close = h["Close"].dropna() if not h.empty else pd.Series(dtype=float)
            if close.empty:
                raise ValueError("no data")
            out[t] = float(close.iloc[-1])
        except Exception:
            out[t] = None
    return out


def pick_holdings():
    """
    Top N by RRG Score from the current analysis, capped per sector.
    Falls back to the sector ETFs themselves if no constituent file exists.
    """
    if os.path.exists(CANDIDATES):
        df = pd.read_csv(CANDIDATES)
        df = df[df["rrg_score"].notna()].sort_values("rrg_score", ascending=False)
        picks, per_sector = [], {}
        for _, r in df.iterrows():
            sec = str(r.get("sector_etf", "?"))
            if per_sector.get(sec, 0) >= MAX_PER_SECTOR:
                continue
            picks.append({"ticker": str(r["ticker"]), "sector": str(r.get("sector", "")),
                          "sector_etf": sec, "rrg_score": float(r["rrg_score"]),
                          "quadrant": str(r.get("quadrant", "")),
                          "setup": str(r.get("setup", ""))})
            per_sector[sec] = per_sector.get(sec, 0) + 1
            if len(picks) >= N_HOLDINGS:
                break
        if picks:
            return picks
    sec = pd.read_csv(SECTORS).sort_values("rrg_score", ascending=False).head(3)
    return [{"ticker": str(r["ticker"]), "sector": str(r["sector"]),
             "sector_etf": str(r["ticker"]), "rrg_score": float(r["rrg_score"]),
             "quadrant": str(r["quadrant"]), "setup": "sector sleeve"}
            for _, r in sec.iterrows()]


def build_positions(picks, nav, prices):
    """Equal-weight the book across names that returned a usable price."""
    live = [p for p in picks if prices.get(p["ticker"])]
    if not live:
        raise RuntimeError("no live prices for any candidate")
    w = 1.0 / len(live)
    shares, entry, target = {}, {}, {}
    invested, cost = 0.0, 0.0
    for p in live:
        t = p["ticker"]
        px = prices[t] * (1.0 + SLIPPAGE_RATE)      # pay the spread on entry
        dollars = nav * w
        n = dollars / px
        shares[t] = n
        entry[t] = px
        target[t] = w
        invested += n * px
        cost += dollars * SLIPPAGE_RATE
    return shares, entry, target, invested, cost, live


def seed():
    if os.path.exists(STATE_PATH):
        log(f"{STATE_PATH} already exists — refusing to overwrite. "
            f"Delete it first if you really want to re-seed.")
        return
    picks = pick_holdings()
    tickers = [p["ticker"] for p in picks]
    log(f"Seeding with {len(tickers)} names: {', '.join(tickers)}")
    prices = fetch_prices(tickers)
    shares, entry, target, invested, cost, live = build_positions(
        picks, START_NAV, prices)
    today = time.strftime("%Y-%m-%d")

    state = {
        "nav": START_NAV, "peak_nav": START_NAV, "invested": 1.0,
        "cash_dollars": START_NAV - invested, "invested_dollars": invested,
        "shares": shares, "entry_prices": entry, "target_weights": target,
        "last_prices": {t: entry[t] for t in entry},
        "last_date": today, "last_selection_asof": today,
        "trading_cost": cost, "last_rebalance_date": today,
        "sizing_multiplier": _sizing_multiplier(),
    }
    _write_state(state)
    _append_ledger(today, START_NAV, 100.0, 0.0, START_NAV, list(shares))
    with open(SELECTION_PATH, "w") as f:
        json.dump({"as_of": today, "n_holdings": len(live),
                   "strategy": "RRG top-N by score, equal weight, sector-capped",
                   "holdings": {p["ticker"]: p for p in live}}, f, indent=2)
    log(f"Seeded ${START_NAV:,.0f} across {len(live)} names "
        f"(cost ${cost:,.2f}). -> {STATE_PATH}, {LEDGER_PATH}")


def _sizing_multiplier():
    try:
        with open(CAL) as f:
            return float(json.load(f).get("sizing_multiplier", 0.0))
    except Exception:
        return 0.0


def _write_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _append_ledger(date, nav, invested_pct, daily_log_ret, peak_nav, holdings):
    row = pd.DataFrame([{
        "date": date, "nav": round(nav, 2), "invested_pct": round(invested_pct, 2),
        "daily_log_ret": round(daily_log_ret, 8), "risk_on": True,
        "peak_nav": round(peak_nav, 2), "holdings": ", ".join(holdings),
    }])
    if os.path.exists(LEDGER_PATH):
        old = pd.read_csv(LEDGER_PATH)
        old = old[old["date"] != date]
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(LEDGER_PATH, index=False)


def update(force_rebalance=False):
    if not os.path.exists(STATE_PATH):
        log("No state — run with --seed first.")
        return
    with open(STATE_PATH) as f:
        state = json.load(f)
    today = time.strftime("%Y-%m-%d")
    if state.get("last_date") == today and not force_rebalance:
        log(f"Already updated for {today}.")
        return

    tickers = list(state["shares"])
    prices = fetch_prices(tickers)
    prev_nav = float(state["nav"])

    mv = 0.0
    for t, n in state["shares"].items():
        px = prices.get(t)
        if px is None or not np.isfinite(px):
            px = state["last_prices"].get(t, state["entry_prices"][t])
        state["last_prices"][t] = float(px)
        mv += n * px
    nav = mv + float(state.get("cash_dollars", 0.0))

    due = force_rebalance or (pd.Timestamp(today) -
           pd.Timestamp(state.get("last_rebalance_date", today))).days >= REBALANCE_DAYS
    if due:
        picks = pick_holdings()
        new_t = [p["ticker"] for p in picks]
        if set(new_t) != set(tickers):
            log(f"Rebalance: {', '.join(sorted(set(tickers)-set(new_t))) or '—'} out / "
                f"{', '.join(sorted(set(new_t)-set(tickers))) or '—'} in")
            npx = fetch_prices(new_t)
            shares, entry, target, invested, cost, live = build_positions(
                picks, nav, npx)
            turnover_cost = cost + nav * SLIPPAGE_RATE   # exit + entry
            nav -= turnover_cost
            shares, entry, target, invested, cost, live = build_positions(
                picks, nav, npx)
            state.update({"shares": shares, "entry_prices": entry,
                          "target_weights": target,
                          "last_prices": {t: entry[t] for t in entry},
                          "cash_dollars": nav - invested,
                          "invested_dollars": invested,
                          "trading_cost": float(state.get("trading_cost", 0)) + turnover_cost,
                          "last_rebalance_date": today,
                          "last_selection_asof": today})
            with open(SELECTION_PATH, "w") as f:
                json.dump({"as_of": today, "n_holdings": len(live),
                           "strategy": "RRG top-N by score, equal weight, sector-capped",
                           "holdings": {p["ticker"]: p for p in live}}, f, indent=2)
            try:
                from event_log import log_event
                log_event("RRG", "rebalance", date=today,
                          detail=f"rotated to {', '.join(new_t)}", tickers=new_t)
            except Exception:
                pass
        else:
            state["last_rebalance_date"] = today

    state["nav"] = nav
    state["peak_nav"] = max(float(state.get("peak_nav", nav)), nav)
    state["invested_dollars"] = sum(
        state["shares"][t] * state["last_prices"][t] for t in state["shares"])
    state["invested"] = (state["invested_dollars"] / nav) if nav > 0 else 0.0
    state["last_date"] = today
    state["sizing_multiplier"] = _sizing_multiplier()
    _write_state(state)

    lr = float(np.log(nav / prev_nav)) if prev_nav > 0 and nav > 0 else 0.0
    _append_ledger(today, nav, 100.0 * state["invested"], lr,
                   state["peak_nav"], list(state["shares"]))
    log(f"{today}  NAV ${nav:,.2f}  ({100*(nav/START_NAV-1):+.2f}% since seed)")


def main():
    if "--seed" in sys.argv:
        seed()
    else:
        update(force_rebalance="--rebalance" in sys.argv)


if __name__ == "__main__":
    main()
