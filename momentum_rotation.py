"""
Momentum Rotation — Cross-Sectional / Dual Momentum Backtest (Strategy #1)
=========================================================================
The simplest, most-robust candidate from the strategy shortlist (Round 9):
rank a fixed, liquid, options-tradeable ETF universe by trailing momentum,
hold the top-N equal-weight, rebalance monthly. Optional *absolute* momentum
filter (dual momentum): a selected sleeve rotates to cash when its own trailing
return is negative — the classic drawdown-control leg.

Design choices (kept deliberately simple; see the plan, Round 9):
  * Universe  : fixed set of liquid ETFs (sectors + broad + intl + diversifiers).
                No survivorship bias — every ticker is still trading; the set is
                declared up front, not selected with hindsight.
  * Signal    : 12-1 momentum by default (total return over the past `lookback`
                months, skipping the most recent `skip` month to dodge the
                short-term reversal). Total return throughout (auto_adjust=True).
  * Rebalance : monthly, at month-end close. Signal at month-end t sets the
                weights *held during month t+1* — no look-ahead.
  * Costs     : turnover-based (bps per unit traded) charged at each rebalance.
  * Benchmark : SPY buy & hold over the identical window.

Also runs a lookback x top_n robustness sweep and an in-sample / out-of-sample
walk-forward split, so we can see whether any edge survives outside one lucky
parameter cell. A backtest is a hypothesis, not a promise.

Usage:
  py momentum_rotation.py
"""

import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import yfinance as yf

try:
    from curl_cffi import requests as cffi_requests
    SESSION = cffi_requests.Session(impersonate="chrome")
except Exception:
    SESSION = None

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


START = "2004-01-01"          # GLD (Nov 2004) is the binding constraint on the full set
RFR = 0.03                    # annual cash yield for the dual-momentum cash leg
COST_BPS = 10.0               # per unit of turnover, one-way, in basis points
TRADING_DAYS = 252

# ── Universe: liquid, long-lived, options-tradeable ETFs ─────────────────────
# Sectors (SPDR) + broad equity + international + diversifiers (bonds/gold).
# XLRE (2015) and XLC (2018) are deliberately excluded to keep a clean common
# window back to 2004; they can be added later once we shift to a rolling universe.
UNIVERSE = [
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB",  # S&P sectors
    "QQQ", "IWM", "EFA", "EEM",                                      # broad / style / intl
    "TLT", "GLD",                                                    # diversifiers
]
BENCHMARK = "SPY"


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

def download(ticker, retries=5, wait=15):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            kw = dict(start=START, auto_adjust=True, progress=False)
            if SESSION is not None:
                kw["session"] = SESSION
            df = yf.download(ticker, **kw)
            if df is not None and len(df) > 0:
                return df["Close"].squeeze()
            last_err = "empty result"
        except Exception as e:
            last_err = e
        if attempt < retries:
            print(f"    [{ticker}] attempt {attempt} failed ({last_err}), retry in {wait}s ...",
                  flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")


def load_prices():
    """Daily total-return closes for the universe + benchmark, as one aligned frame."""
    print(f"Downloading {len(UNIVERSE) + 1} ETFs (total-return closes)...")
    cols = {}
    for tkr in UNIVERSE + [BENCHMARK]:
        s = download(tkr)
        cols[tkr] = s
        print(f"  {tkr:5s}: {s.index[0].date()} -> {s.index[-1].date()}  ({len(s):,} days)")
    prices = pd.DataFrame(cols).sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices


# ─────────────────────────────────────────────────────────────────────────────
# 2. BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def momentum_score(prices_m, lookback, skip):
    """`lookback`-month total return ending `skip` months ago (12-1 by default)."""
    return prices_m.shift(skip) / prices_m.shift(lookback + skip) - 1.0


def backtest(prices_d, universe, top_n=3, lookback=12, skip=1,
             abs_filter=True, cost_bps=COST_BPS, rfr=RFR, start_after=None):
    """
    Monthly momentum rotation. Returns a daily equity Series (base 100) plus a
    per-rebalance log (dates, holdings, turnover).

    Weights chosen at month-end t are held over month t+1 (no look-ahead). With
    `abs_filter`, a selected sleeve whose own momentum <= 0 goes to cash instead.
    """
    px = prices_d[universe].dropna(how="all")
    prices_m = px.resample("ME").last()
    scores = momentum_score(prices_m, lookback, skip)

    month_ends = prices_m.index
    daily_ret = px.pct_change().fillna(0.0)
    cash_daily = (1.0 + rfr) ** (1.0 / TRADING_DAYS) - 1.0

    equity = 100.0
    curve = pd.Series(index=px.index, dtype=float)
    prev_w = pd.Series(0.0, index=universe)
    log = []

    # First rebalance only once the longest lookback has history.
    first_i = lookback + skip
    if start_after is not None:
        first_i = max(first_i, month_ends.searchsorted(pd.Timestamp(start_after)))

    for i in range(first_i, len(month_ends) - 1):
        sig_date = month_ends[i]
        s = scores.loc[sig_date].dropna()
        if s.empty:
            continue

        picks = s.sort_values(ascending=False).head(top_n)
        w = pd.Series(0.0, index=universe)
        if len(picks) > 0:
            each = 1.0 / top_n                 # equal weight; remainder is cash
            for tkr, mom in picks.items():
                if abs_filter and mom <= 0:
                    continue                    # dual momentum: this sleeve -> cash
                w[tkr] = each

        # Turnover cost charged at the rebalance instant.
        turnover = (w - prev_w).abs().sum()
        equity *= (1.0 - turnover * cost_bps / 1e4)
        prev_w = w

        cash_w = 1.0 - w.sum()
        hold_days = px.loc[(px.index > sig_date) & (px.index <= month_ends[i + 1])].index
        for d in hold_days:
            r = float((daily_ret.loc[d, universe] * w).sum() + cash_w * cash_daily)
            equity *= (1.0 + r)
            curve.loc[d] = equity

        log.append({
            "date": sig_date, "holdings": ", ".join(picks.index) or "(cash)",
            "cash_w": round(cash_w, 3), "turnover": round(turnover, 3),
        })

    return curve.dropna(), pd.DataFrame(log)


def buy_and_hold(prices_d, ticker, index):
    """SPY (or any ticker) buy & hold, base 100, aligned to a strategy curve index."""
    s = prices_d[ticker].reindex(index).dropna()
    return 100.0 * s / s.iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# 3. METRICS  (definitions mirror combined_backtest._compute_metrics)
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    port = curve.values
    years = len(port) / TRADING_DAYS
    cagr = (port[-1] / port[0]) ** (1 / years) - 1
    daily = curve.pct_change().dropna()
    vol = daily.std() * np.sqrt(TRADING_DAYS)

    lr = np.diff(np.log(port))
    rfr_d = np.log(1 + rfr) / TRADING_DAYS
    sharpe = (lr.mean() - rfr_d) / lr.std() * np.sqrt(TRADING_DAYS) if lr.std() > 0 else 0.0

    neg = lr[lr < 0]
    dd_std = np.sqrt((neg ** 2).mean()) * np.sqrt(TRADING_DAYS) if len(neg) else 0.0
    sortino = (cagr - rfr) / dd_std if dd_std > 0 else 0.0

    roll_max = curve.cummax()
    max_dd = ((curve - roll_max) / roll_max).min()

    annual = curve.resample("YE").last().pct_change().dropna()
    return {
        "label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100,
        "sharpe": sharpe, "sortino": sortino, "max_dd_pct": max_dd * 100,
        "worst_year_pct": annual.min() * 100 if len(annual) else np.nan,
        "best_year_pct": annual.max() * 100 if len(annual) else np.nan,
        "final": port[-1],
    }


def print_metrics(rows):
    headers = ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Worst Yr", "Final $100"]
    table = [[
        r["label"], f"{r['cagr_pct']:.2f}%", f"{r['vol_pct']:.2f}%", f"{r['sharpe']:.3f}",
        f"{r['sortino']:.3f}", f"{r['max_dd_pct']:.1f}%", f"{r['worst_year_pct']:.1f}%",
        f"${r['final']:.0f}",
    ] for r in rows]
    print()
    if HAS_TABULATE:
        print(tabulate(table, headers=headers, tablefmt="simple"))
    else:
        w = [26, 8, 8, 8, 8, 8, 9, 10]
        line = "  ".join(h.ljust(w[i]) for i, h in enumerate(headers))
        print(line); print("-" * len(line))
        for row in table:
            print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(row)))


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    prices = load_prices()

    # Common window: every universe ETF has data (GLD from Nov-2004 binds).
    valid_from = prices[UNIVERSE].dropna().index[0]
    prices = prices.loc[valid_from:]
    print(f"\nCommon window: {prices.index[0].date()} -> {prices.index[-1].date()} "
          f"({len(prices):,} days, {len(prices)/TRADING_DAYS:.1f}y)")

    # ── Base configuration: 12-1 momentum, top 3, dual-momentum cash filter ──
    print("\n" + "=" * 78)
    print("BASE STRATEGY — 12-1 momentum, top 3, dual-momentum cash filter, monthly")
    print("=" * 78)
    curve, log = backtest(prices, UNIVERSE, top_n=3, lookback=12, skip=1, abs_filter=True)
    spy = buy_and_hold(prices, BENCHMARK, curve.index)

    results = [metrics(curve, "Momentum (12-1, top3, dual)"), metrics(spy, "SPY buy & hold")]
    # Long-only variant (no cash filter) to isolate what the dual leg contributes.
    curve_lo, _ = backtest(prices, UNIVERSE, top_n=3, lookback=12, skip=1, abs_filter=False)
    results.insert(1, metrics(curve_lo, "Momentum (12-1, top3, no cash)"))
    print_metrics(results)

    base = results[0]
    print(f"\n  vs SPY:  CAGR {base['cagr_pct'] - results[-1]['cagr_pct']:+.2f}pp   "
          f"Sharpe {base['sharpe'] - results[-1]['sharpe']:+.3f}   "
          f"MaxDD {base['max_dd_pct'] - results[-1]['max_dd_pct']:+.1f}pp")

    print("\nLast 6 rebalances (base strategy):")
    print(log.tail(6).to_string(index=False))

    # ── Robustness sweep: lookback x top_n (Sharpe / CAGR grid) ──────────────
    print("\n" + "=" * 78)
    print("ROBUSTNESS SWEEP — dual momentum; each cell = Sharpe (CAGR%)")
    print("=" * 78)
    lookbacks = [3, 6, 9, 12]
    top_ns = [1, 2, 3, 4]
    grid = []
    for lb in lookbacks:
        row = [f"{lb}m"]
        for n in top_ns:
            c, _ = backtest(prices, UNIVERSE, top_n=n, lookback=lb, skip=1, abs_filter=True)
            m = metrics(c, "")
            row.append(f"{m['sharpe']:.2f} ({m['cagr_pct']:.1f})")
        grid.append(row)
    hdr = ["lookback \\ topN"] + [f"top{n}" for n in top_ns]
    if HAS_TABULATE:
        print(tabulate(grid, headers=hdr, tablefmt="simple"))
    else:
        print("  ".join(hdr))
        for r in grid:
            print("  ".join(str(v) for v in r))

    # ── Walk-forward: first half (IS) vs second half (OOS), base config ──────
    print("\n" + "=" * 78)
    print("WALK-FORWARD — base config on first half (IS) vs second half (OOS)")
    print("=" * 78)
    mid = prices.index[len(prices) // 2]
    is_c, _ = backtest(prices.loc[:mid], UNIVERSE, top_n=3, lookback=12, skip=1, abs_filter=True)
    oos_c, _ = backtest(prices.loc[mid:], UNIVERSE, top_n=3, lookback=12, skip=1, abs_filter=True)
    is_spy = buy_and_hold(prices, BENCHMARK, is_c.index)
    oos_spy = buy_and_hold(prices, BENCHMARK, oos_c.index)
    print_metrics([
        metrics(is_c, f"IS  Momentum ({is_c.index[0].date()}+)"),
        metrics(is_spy, "IS  SPY"),
        metrics(oos_c, f"OOS Momentum ({oos_c.index[0].date()}+)"),
        metrics(oos_spy, "OOS SPY"),
    ])

    curve.to_csv("momentum_rotation_curve.csv", header=["equity"])
    pd.DataFrame(results).to_csv("momentum_rotation_results.csv", index=False)
    print(f"\nSaved -> momentum_rotation_curve.csv, momentum_rotation_results.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
