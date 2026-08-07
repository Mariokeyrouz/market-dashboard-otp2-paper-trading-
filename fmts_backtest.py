"""
FMTS — backtest of the price-only half (Momentum + Low-Vol) plus the trailing-stop overlay
==============================================================================================
FMTS (`factor_strategy_engine.py`, fed monthly by `factor_screener.py`) has
never been backtested. Its composite score averages FOUR factors —
Momentum, Quality, Value, Low-Vol (`factor_screener.score_universe()`) — but
Quality and Value need historical fundamentals (ROE, margins, leverage, P/E,
P/B, EV/EBITDA) this repo cannot get for history: `yfinance` only exposes
today's snapshot / last-3-years statements, the same wall documented for
Quality-minus-Junk and `eps_revision_backtest.py`. This script tests ONLY
what's honestly backtestable — Momentum + Low-Vol — and says so plainly
rather than substituting a proxy for Value/Quality and calling it FMTS.

FORMULAS — restated exactly from factor_screener.py::score_universe()
--------------------------------------------------------------------------
  rs_ratio    = (stock's 52-week return / SPX's 52-week return) * 100
  rs_momentum = (rs_ratio today / rs_ratio as of 4 weeks ago) * 100
  rvol_252    = annualized std of weekly returns (trailing window)
  score_momentum = avg(pct_rank(rs_ratio), pct_rank(rs_momentum))     [higher better]
  score_low_vol  = pct_rank(rvol_252, ascending=False)                [lower vol better]
  composite      = avg(score_momentum, score_low_vol)                [2-factor, not 4]
Selection: top N_HOLDINGS by composite, monthly rebalance, weight
proportional to composite score among the selected (matches
factor_screener.py's `target_weight` formula exactly).

TRAILING-STOP OVERLAY — restated from factor_strategy_engine.py::_step()
------------------------------------------------------------------------------
Portfolio NAV tracked daily; if drawdown from peak >= 9%, scale to 50%
invested; re-entry when the MARKET's (SPX) 20-day realized vol drops below
its own 60-day SMA (this is a market-vol signal, not portfolio-specific —
confirmed by reading factor_strategy_engine.py's `main()`, which builds
`rvol20`/`rvol_sma60` from `^GSPC`, not from the portfolio). Tested WITH and
WITHOUT this overlay on the identical underlying selection, to isolate
whether the stop mechanism itself adds value — the most directly
"unvalidated live mechanism" question for FMTS specifically.

SURVIVORSHIP BIAS + DATA CACHE CAVEAT
-----------------------------------------
Universe is `momentum_experiments_daily.load_daily()` — today's S&P 500
backfilled (survivorship-biased, same caveat as every stock-level backtest
here). At the time of this run the cache is sitting at a reduced ~396/504
tickers (see CLAUDE.md's environment traps) from an earlier yfinance
rate-limit event this session — read results as resting on that smaller
universe, not the full ~500.

Outputs: fmts_results.csv, fmts_surface.csv, fmts_curve.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here changes the live engine or its state files.

Usage:
  py fmts_backtest.py
"""

import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

import momentum_experiments_daily as med
from strategy_deep_test import download_many, download_tbill, build_market_features
import rrg_stats as rs

BENCHMARK = "SPY"

N_HOLDINGS = 18
STOP_THRESHOLD = 0.09
TARGET_INVEST = 1.0
STOPPED_INVEST = 0.50
RVOL_SMA_WINDOW = 60
RVOL_252_WEEKS = 78          # ~18mo, matches factor_screener's weekly download window
MOM_LOOKBACK_W = 52
MOM_SKIP_W = 4

RFR = 0.03
SLIPPAGE_RATE = 0.001
COST_STRESS_RATE = 0.002

BASE_PARAMS = dict(n_holdings=N_HOLDINGS, stop_threshold=STOP_THRESHOLD, use_stop=True)

# Parameter sweep (report the surface, never the best cell)
N_HOLDINGS_GRID = (12, 18, 25)
STOP_THRESHOLD_GRID = (0.06, 0.09, 0.12)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA / FACTOR CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def load_universe():
    px = med.load_daily()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    spy = px[BENCHMARK] if BENCHMARK in px.columns else None
    stocks = px.drop(columns=[BENCHMARK], errors="ignore")
    stocks = stocks.dropna(axis=1, how="all")
    print(f"Data source: momentum_experiments_daily.load_daily(). "
          f"Universe: {stocks.shape[1]} tickers, "
          f"{stocks.index.min().date()} -> {stocks.index.max().date()}")
    return stocks, spy


def compute_composite_weekly(stocks_d, spy_d):
    """Weekly rs_ratio / rs_momentum / rvol_252 -> score_momentum, score_low_vol,
    composite (2-factor). All vectorized with shifts — no look-ahead: every
    value at week t uses only prices at or before week t."""
    wk = stocks_d.resample("W-FRI").last()
    spy_wk = spy_d.resample("W-FRI").last()

    rel = wk.div(spy_wk, axis=0)
    rs_ratio = (rel / rel.shift(MOM_LOOKBACK_W)) * 100.0
    rs_ratio_lag = rs_ratio.shift(MOM_SKIP_W)
    rs_momentum = (rs_ratio / rs_ratio_lag) * 100.0

    ret_wk = wk.pct_change()
    rvol_252 = ret_wk.rolling(RVOL_252_WEEKS).std() * np.sqrt(52)

    def pct_rank_row(df, ascending=True):
        return df.rank(axis=1, pct=True, ascending=ascending, na_option="keep") * 100.0

    score_momentum = (pct_rank_row(rs_ratio, True) + pct_rank_row(rs_momentum, True)) / 2.0
    score_low_vol = pct_rank_row(rvol_252, ascending=False)
    composite = (score_momentum + score_low_vol) / 2.0
    return composite, wk.index


# ─────────────────────────────────────────────────────────────────────────────
# 2. PORTFOLIO CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def monthly_rebalance(state, new_holdings, px_today, slippage_rate):
    """Rotate holdings to `new_holdings` (dict ticker->weight, sums to 1),
    preserving the CURRENT invested fraction (matches
    factor_strategy_engine.py's rebalance branch — rebalancing does not
    reset the stop state)."""
    old_shares = state["shares"]
    stock_value = sum(old_shares.get(t, 0.0) * px_today.get(t, 0.0) for t in old_shares)
    cash = state["cash_dollars"]
    nav = stock_value + cash
    inv_frac = state["invested"]
    target_stock = inv_frac * nav
    cost = abs(target_stock) * slippage_rate * 0.5 + stock_value * slippage_rate * 0.5
    nav_after = nav - cost
    target_stock = inv_frac * nav_after

    entry_prices = {t: px_today[t] * (1 + slippage_rate) for t in new_holdings if t in px_today}
    shares = {t: (target_stock * w) / entry_prices[t] for t, w in new_holdings.items() if t in entry_prices}
    cash_dollars = nav_after - sum(shares[t] * px_today[t] for t in shares)

    state["shares"] = shares
    state["entry_prices"] = entry_prices
    state["cash_dollars"] = cash_dollars
    state["nav"] = cash_dollars + sum(shares[t] * px_today[t] for t in shares)
    state["trading_cost"] = state.get("trading_cost", 0.0) + cost
    return state


def daily_step(state, px_today, rvol20, rvol_sma60, cash_ret_simple, use_stop, stop_threshold, slippage_rate):
    """Mirrors factor_strategy_engine.py::_step() exactly, with a `use_stop`
    toggle: when False, target_inv is always 1.0 (the stop check still runs
    for reporting but never changes exposure)."""
    tickers = list(state["shares"].keys())
    shares = state["shares"]

    stock_value = sum(shares[t] * px_today[t] for t in tickers if t in px_today)
    cash_dollars = state["cash_dollars"] * (1.0 + cash_ret_simple)
    nav = stock_value + cash_dollars

    peak_nav = max(state["peak_nav"], nav)
    stopped_out = state["stopped_out"]
    drawdown = (peak_nav - nav) / peak_nav if peak_nav > 0 else 0.0

    if use_stop and not stopped_out and drawdown >= stop_threshold:
        stopped_out = True
    if use_stop and stopped_out and np.isfinite(rvol20) and np.isfinite(rvol_sma60) and rvol20 < rvol_sma60:
        stopped_out = False
    if not use_stop:
        stopped_out = False

    target_inv = STOPPED_INVEST if stopped_out else TARGET_INVEST
    target_stock = target_inv * nav
    traded_dollars = abs(target_stock - stock_value)
    cost = traded_dollars * slippage_rate
    nav_after = nav - cost
    target_stock = target_inv * nav_after

    factor = target_stock / stock_value if stock_value > 1e-9 else 0.0
    for t in tickers:
        shares[t] = shares[t] * factor
    cash_dollars = nav_after - target_stock

    state.update(nav=nav_after, peak_nav=peak_nav, invested=target_inv, stopped_out=stopped_out,
                 shares=shares, cash_dollars=cash_dollars,
                 trading_cost=state.get("trading_cost", 0.0) + cost)
    return state


def run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, params, start=None, end=None):
    idx = stocks_d.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end)]

    month_key = idx.to_series().dt.to_period("M")
    rebal_dates = set(idx[month_key.ne(month_key.shift(1)).to_numpy() & (np.arange(len(idx)) > 0)])
    first_valid_week = composite.dropna(how="all").index.min()

    state = None
    nav_series = {}
    n_holdings = params["n_holdings"]

    for date in idx:
        if date < first_valid_week + pd.Timedelta(weeks=1):
            continue
        px_today = stocks_d.loc[date].dropna().to_dict()   # one row lookup/day, not cell-by-cell
        cash_ret = float(market_df["cash_daily"].asof(date)) if "cash_daily" in market_df.columns else 0.0

        is_rebal = state is None or date in rebal_dates
        if is_rebal:
            wk_asof = composite.index[composite.index <= date]
            if len(wk_asof) == 0:
                continue
            row = composite.loc[wk_asof[-1]].dropna()
            row = row[row.index.isin(px_today.keys())]
            if len(row) < n_holdings:
                continue
            top = row.nlargest(n_holdings)
            new_holdings = (top / top.sum()).to_dict()

            if state is None:
                entry_prices = {t: px_today[t] * (1 + SLIPPAGE_RATE) for t in new_holdings}
                shares = {t: (10_000.0 * TARGET_INVEST * w) / entry_prices[t] for t, w in new_holdings.items()}
                seed_cost = 10_000.0 * TARGET_INVEST * SLIPPAGE_RATE
                state = dict(nav=10_000.0 - seed_cost, peak_nav=10_000.0 - seed_cost, invested=TARGET_INVEST,
                             stopped_out=False, shares=shares, cash_dollars=(10_000.0 - seed_cost) * (1 - TARGET_INVEST),
                             trading_cost=seed_cost)
            else:
                state = monthly_rebalance(state, new_holdings, px_today, SLIPPAGE_RATE)

        rvol20 = float(market_df["rvol20"].asof(date))
        rvol_sma60 = float(market_df["rvol_sma60"].asof(date))
        state = daily_step(state, px_today, rvol20, rvol_sma60, cash_ret, params["use_stop"],
                            params["stop_threshold"], SLIPPAGE_RATE)
        nav_series[date] = state["nav"]

    return pd.Series(nav_series).sort_index()


# ─────────────────────────────────────────────────────────────────────────────
# 3. STATS / REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR, periods_per_year=252.0):
    curve = curve.dropna()
    if len(curve) < periods_per_year:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan,
                "sortino": np.nan, "max_dd_pct": np.nan, "final": np.nan}
    n = len(curve)
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (periods_per_year / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(periods_per_year)
    sharpe = (r.mean() - rfr / periods_per_year) / r.std() * np.sqrt(periods_per_year) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(periods_per_year) if len(neg) > 1 else 0.0
    sortino = (cagr - rfr) / dd_std if dd_std > 0 else 0.0
    roll = curve.cummax()
    dd = (curve - roll) / roll
    return {"label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100, "sharpe": sharpe,
            "sortino": sortino, "max_dd_pct": dd.min() * 100, "final": curve.iloc[-1]}


def fmt(v, d=2, suffix=""):
    return "n/a" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v:.{d}f}{suffix}"


def table(rows, headers, widths):
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
        return
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line); print("-" * len(line))
    for row in rows:
        print("  ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))


def banner(title, ch="="):
    print("\n" + ch * 100)
    print(title)
    print(ch * 100)


def buy_hold(series, index):
    s = series.reindex(index).dropna()
    return 10_000.0 * s / s.iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("FMTS — Momentum + Low-Vol (2-factor, price-only) with/without the 9% trailing stop")
    print("Value + Quality are NOT tested — no historical fundamentals pipeline exists (same wall")
    print("as Quality-minus-Junk / eps_revision_backtest.py). This is the backtestable HALF of FMTS.")
    print("PAPER-TESTING RESEARCH ONLY. FMTS has never been backtested before this script.")

    stocks_d, spy_d = load_universe()
    print("\nDownloading ^GSPC/^VIX for the market-vol re-entry signal (matches factor_strategy_engine.py)...")
    raw = download_many(["^GSPC", "^VIX"])
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")
    market_df = build_market_features(raw["^GSPC"], raw["^VIX"])
    market_df["rvol_sma60"] = market_df["rvol20"].rolling(RVOL_SMA_WINDOW).mean()
    market_df["cash_daily"] = tbill_raw.reindex(market_df.index).ffill().bfill() / 252

    print("\nComputing weekly Momentum + Low-Vol composite (no look-ahead)...", flush=True)
    composite, weekly_index = compute_composite_weekly(stocks_d, spy_d)

    banner(f"BASE CONFIG — top {N_HOLDINGS} by composite, monthly rebal, {STOP_THRESHOLD:.0%} trailing stop")
    curve_stop = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, BASE_PARAMS)
    curve_nostop = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df,
                                 dict(BASE_PARAMS, use_stop=False))
    spy_curve = buy_hold(spy_d, curve_stop.index)

    results = [metrics(curve_stop, "FMTS 2-factor WITH 9% trailing stop"),
               metrics(curve_nostop, "FMTS 2-factor WITHOUT stop (always 100% invested)"),
               metrics(spy_curve, "SPY buy & hold")]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"] for r in results],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $10k->"], [42, 8, 8, 8, 8, 8, 12])

    # ── significance vs SPY (monthly excess return) ─────────────────────────
    m_stop = curve_stop.resample("ME").last().pct_change().dropna()
    m_spy = spy_curve.resample("ME").last().pct_change().dropna()
    aligned = pd.concat([m_stop.rename("strat"), m_spy.rename("spy")], axis=1).dropna()
    excess = (aligned["strat"] - aligned["spy"]).values
    t_naive = rs.naive_t(excess)
    _, t_nw, n_obs = rs.newey_west_t(excess, lag=1)
    print(f"\nMonths: {n_obs}   Excess-over-SPY naive t: {fmt(t_naive,2)}   "
          f"Newey-West (lag=1, sanity check): {fmt(t_nw,2)}")

    stress_curve = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, BASE_PARAMS)
    # cost-stress arm: same run but with SLIPPAGE_RATE doubled via module-level override
    global SLIPPAGE_RATE
    _orig = SLIPPAGE_RATE
    SLIPPAGE_RATE = COST_STRESS_RATE
    stress_curve = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, BASE_PARAMS)
    SLIPPAGE_RATE = _orig
    stress_m = metrics(stress_curve, "")
    base_m = results[0]
    print(f"Cost stress (20bps one-way): CAGR {fmt(stress_m['cagr_pct'],2,'%')} "
          f"(base {fmt(base_m['cagr_pct'],2,'%')})")

    banner("WALK-FORWARD — first half (IS) vs second half (OOS), base config")
    mid = curve_stop.index[len(curve_stop) // 2]
    is_curve = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, BASE_PARAMS, end=mid)
    oos_curve = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, BASE_PARAMS, start=mid)
    is_m = metrics(is_curve, f"IS ({is_curve.index[0].date() if len(is_curve) else '?'}+)")
    oos_m = metrics(oos_curve, f"OOS ({oos_curve.index[0].date() if len(oos_curve) else '?'}+)")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")]
           for r in [is_m, oos_m]], ["Period", "CAGR", "Sharpe", "MaxDD"], [30, 8, 8, 8])

    banner(f"PARAMETER SURFACE ({len(N_HOLDINGS_GRID)*len(STOP_THRESHOLD_GRID)} cells) — "
           "median / sign agreement, never the best cell")
    surf_rows = []
    for nh in N_HOLDINGS_GRID:
        for st in STOP_THRESHOLD_GRID:
            p = dict(n_holdings=nh, stop_threshold=st, use_stop=True)
            c = run_backtest(stocks_d, spy_d, composite, weekly_index, market_df, p)
            m = metrics(c, "")
            surf_rows.append({"n_holdings": nh, "stop_threshold": st, "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"]})
    surf = pd.DataFrame(surf_rows)
    surf.to_csv("fmts_surface.csv", index=False)
    sc = surf["cagr_pct"].dropna()
    print(f"CAGR%  — median {fmt(sc.median(),2)}  min {fmt(sc.min(),2)}  max {fmt(sc.max(),2)}  "
          f"sign+ {(sc>0).mean()*100:.0f}% of {len(sc)} cells")

    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=5/7 to pass)")
    nostop_m = results[1]
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (with-stop base config, full sample)",
         base_m["cagr_pct"] > 0, f"{base_m['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps cost stress (still net positive CAGR)",
         stress_m["cagr_pct"] > 0, f"{stress_m['cagr_pct']:+.2f}%"),
        (3, True, "Walk-forward OOS half still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "With-stop Sharpe beats without-stop Sharpe (isolates the stop's value)",
         base_m["sharpe"] > nostop_m["sharpe"], f"with-stop {fmt(base_m['sharpe'],3)} vs no-stop {fmt(nostop_m['sharpe'],3)}"),
        (5, False, "With-stop MaxDD better than without-stop MaxDD",
         base_m["max_dd_pct"] > nostop_m["max_dd_pct"], f"with-stop {fmt(base_m['max_dd_pct'],1)}% vs no-stop {fmt(nostop_m['max_dd_pct'],1)}%"),
        (6, False, "Parameter-surface median CAGR > 0 and sign agreement >= 70%",
         sc.median() > 0 and (sc > 0).mean() >= 0.70, f"median {fmt(sc.median(),2)}%, {(sc>0).mean()*100:.0f}% positive"),
        (7, False, "Excess-over-SPY naive |t| >= 3",
         np.isfinite(t_naive) and abs(t_naive) >= 3, f"t={fmt(t_naive,2)}"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:58], det[:38]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 58, 38])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 5 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/7 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — the backtestable half of FMTS clears its own bar; Value/Quality remain untested," if verdict == "PASS"
        else " — report the null and stop. This does not mean FMTS's full 4-factor composite fails —"
             " Value/Quality are simply untested — only that the Momentum+Low-Vol half, plus the"
             " trailing stop, do not clear their own bar here."))
    print("=" * 100)

    pd.DataFrame(results).to_csv("fmts_results.csv", index=False)
    pd.DataFrame({"with_stop": curve_stop, "without_stop": curve_nostop, "spy": spy_curve}).to_csv("fmts_curve.csv")
    print(f"\nWrote fmts_results.csv, fmts_surface.csv, fmts_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
