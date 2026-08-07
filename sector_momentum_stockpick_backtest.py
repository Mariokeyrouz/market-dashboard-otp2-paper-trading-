"""
Sector momentum + within-sector stock-picking — plain rules, long-only
==========================================================================
Top-down: rank the 9 core SPDR sector ETFs by 12-1 relative momentum vs SPY,
hold the top N_SECTORS. Bottom-up: within each winning sector, rank its
constituent stocks by the SAME plain 12-1 relative-momentum formula and hold
the top K_STOCKS. Monthly rebalance, long-only, no shorting.

WHY THIS IS A GENUINELY DIFFERENT TEST FROM RRG AND FROM sector_ls_backtest.py
----------------------------------------------------------------------------------
RRG (`rrg_validate.py`) ranked sectors AND stocks with a walk-forward-FITTED
linear score over quadrant/distance/straightness features, and failed its
own validation (1/9 criteria) — specifically because that score added
nothing over plain 12-1 relative momentum (`rrg_validate.py`'s own horse
race, `mom_12_1` control, incremental IC -0.004, t -0.26). This script tests
the thing RRG never actually validated on its own: does PLAIN momentum,
undressed by any fitted score, work as a deployable top-down strategy?
`sector_ls_backtest.py` also used RRG's quadrant/straightness machinery (for
a rule-gated long/short book) and failed (0/8). This script uses neither
RRG's fitted score nor its quadrant geometry — just `momentum_signal()`,
the identical formula already used (and shown NOT to beat) in
`cross_sectional_momentum_backtest.py` and as `rrg_validate.py`'s own
`mom_12_1` control block.

THE KEY QUESTION: does stock-picking beat just holding the sector ETF?
----------------------------------------------------------------------------
Four arms, same sector selection, to isolate exactly where any edge (or lack
of it) comes from:
  A. Full system      — top-3 sectors, top-K stocks within each (THE test object)
  B. Sector-ETF-only   — top-3 sectors, hold the ETFs directly (no stock-picking)
  C. Bottom-K stocks   — same sectors, but the WORST performers within them
                         (falsification check: if bottom-K does as well as
                         top-K, the within-sector selection isn't doing
                         anything real)
  D. SPY buy & hold
If A doesn't beat B, the stock-picking layer adds nothing over just buying
the sector ETF. If A doesn't beat C, "best performer" isn't a real signal
within these sectors.

SURVIVORSHIP BIAS
-------------------
The sector layer (9 core SPDRs) is clean — no survivorship bias. The stock
layer (`rrg_data.load_stock_panel()`, i.e. `momentum_daily_prices.csv`) is
today's S&P 500 backfilled, survivorship-biased — same caveat as every
stock-level backtest in this repo. At the time of this run that cache is
also sitting at a reduced ~396/504 tickers from an earlier rate-limit event
this session (see CLAUDE.md environment traps) — read results as resting on
that smaller universe.

COSTS (restated, not imported)
--------------------------------
  Commission + slippage : 10 bps one-way on turnover
  Stress cost            : 20 bps one-way, explicit robustness arm
  No borrow needed — long-only, no shorting.

Outputs: sector_stockpick_results.csv, sector_stockpick_surface.csv,
         sector_stockpick_curve.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py sector_momentum_stockpick_backtest.py
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

import rrg_data as rd
import rrg_stats as rs

LOOKBACK_M = 12
SKIP_M = 1
N_SECTORS = 3
K_STOCKS = 5
REBAL_MONTHS = 1

RFR = 0.03
COST_BPS = 10.0
COST_BPS_STRESS = 20.0

BASE_PARAMS = dict(n_sectors=N_SECTORS, k_stocks=K_STOCKS, lookback=LOOKBACK_M, skip=SKIP_M)

# Parameter sweep (report the surface, never the best cell)
N_SECTORS_GRID = (2, 3, 4)
K_STOCKS_GRID = (3, 5, 8)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA / SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def momentum_signal(px_m, spy_m, lookback=LOOKBACK_M, skip=SKIP_M):
    """Benchmark-relative momentum, identical formula to
    cross_sectional_momentum_backtest.momentum_signal() and
    rrg_validate.momentum_controls()'s mom_12_1 control:
    (asset return / SPY return) over the lookback, skipping the most recent
    `skip` periods."""
    rel = px_m.div(spy_m, axis=0)
    return rel.shift(skip) / rel.shift(lookback + skip) - 1.0


def load_data():
    px_sec = rd.load_sector_prices(verbose=False)
    sectors = rd.SECTOR_CORE   # 9 long-history SPDRs — zero survivorship bias, matches rrg_validate.py's primary sample
    spy_d = px_sec[rd.BENCHMARK]
    sec_d = px_sec[sectors]

    smap = rd.load_sector_map(verbose=False)
    stock_px = rd.load_stock_panel(verbose=False)
    print(f"Stock universe: {stock_px.shape[1]} tickers (today's S&P 500 backfilled)")

    sec_to_stocks = {etf: rd.stocks_in_sector(smap, etf, stock_px.columns) for etf in sectors}
    for etf, names in sec_to_stocks.items():
        print(f"  {etf} ({rd.SECTOR_NAMES.get(etf,'')}): {len(names)} constituents in the panel")

    return sec_d, spy_d, stock_px, sec_to_stocks


# ─────────────────────────────────────────────────────────────────────────────
# 2. PORTFOLIO CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                     n_sectors, k_stocks, pick="top", include_etf_arm=False, cost_bps=COST_BPS,
                     rebal_months=1, start=None):
    """
    pick='top'    -> Arm A (best-performer stock-picking) if include_etf_arm=False
    pick='bottom' -> Arm C (worst-performer falsification check)
    include_etf_arm=True -> Arm B (hold the winning sector ETFs directly, no stock-picking)
    """
    dates = sec_mom_m.index.intersection(stock_mom_m.index)   # stock panel starts later (~2004) than sectors (~1998)
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    eq = 100.0
    curve = {}
    w = pd.Series(dtype=float)
    k = 0

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        if k % rebal_months == 0:
            sm = sec_mom_m.loc[t].dropna()
            if len(sm) < n_sectors:
                tgt = pd.Series(dtype=float)
            elif include_etf_arm:
                top_sectors = sm.nlargest(n_sectors).index
                tgt = pd.Series(1.0 / len(top_sectors), index=top_sectors)
            else:
                top_sectors = sm.nlargest(n_sectors).index
                names = []
                for etf in top_sectors:
                    cand = [c for c in sec_to_stocks.get(etf, []) if c in stock_mom_m.columns]
                    if not cand:
                        continue
                    s = stock_mom_m.loc[t, cand].dropna()
                    if len(s) < 2:
                        continue
                    picked = s.nlargest(k_stocks) if pick == "top" else s.nsmallest(k_stocks)
                    names.extend(list(picked.index))
                tgt = pd.Series(1.0 / len(names), index=names) if names else pd.Series(dtype=float)

            all_idx = w.index.union(tgt.index)
            turn = float((tgt.reindex(all_idx).fillna(0.0) - w.reindex(all_idx).fillna(0.0)).abs().sum())
            eq *= (1.0 - turn * cost_bps / 1e4)
            w = tgt
        k += 1

        ret_src = ret_sec_m if include_etf_arm else ret_stock_m
        r = float((w * ret_src.loc[t1].reindex(w.index).fillna(0.0)).sum()) if len(w) else 0.0
        eq *= (1.0 + r)
        curve[t1] = eq

        if len(w):
            w = w * (1.0 + ret_src.loc[t1].reindex(w.index).fillna(0.0))
            wsum = w.sum()
            if wsum > 0:
                w = w / wsum

    return pd.Series(curve).sort_index()


def buy_hold(series, index):
    s = series.reindex(index).dropna()
    return 100.0 * s / s.iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# 3. STATS / REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    if len(curve) < 24:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan,
                "sortino": np.nan, "max_dd_pct": np.nan, "final": np.nan}
    n = len(curve)
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (12 / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() - rfr / 12) / r.std() * np.sqrt(12) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(12) if len(neg) > 1 else 0.0
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


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("SECTOR MOMENTUM + WITHIN-SECTOR STOCK-PICKING — plain rules, long-only")
    print("Top-3-of-9 sectors by 12-1 relative momentum; top-5 stocks within each by the SAME formula.")
    print("No RRG fitted score, no quadrant geometry — the plain baseline RRG's own validation")
    print("showed its complexity never beat (incremental IC -0.004, t -0.26).")
    print("PAPER-TESTING RESEARCH ONLY.")

    sec_d, spy_d, stock_px, sec_to_stocks = load_data()

    sec_m = sec_d.resample("ME").last()
    spy_m = spy_d.resample("ME").last()
    stock_m = stock_px.resample("ME").last()

    ret_sec_m = sec_m.pct_change()
    ret_stock_m = stock_m.pct_change()

    sec_mom_m = momentum_signal(sec_m, spy_m, LOOKBACK_M, SKIP_M)
    spy_m_aligned = spy_m.reindex(stock_m.index)
    stock_mom_m = momentum_signal(stock_m, spy_m_aligned, LOOKBACK_M, SKIP_M)

    print(f"\nMonthly window: {sec_mom_m.index[0].date()} -> {sec_mom_m.index[-1].date()} "
          f"({len(sec_mom_m)} months)")

    banner(f"BASE CONFIG — top {N_SECTORS} sectors, top {K_STOCKS} stocks/sector, monthly rebal")
    curve_a = build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                               N_SECTORS, K_STOCKS, pick="top", include_etf_arm=False, cost_bps=COST_BPS)
    curve_b = build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                               N_SECTORS, K_STOCKS, pick="top", include_etf_arm=True, cost_bps=COST_BPS)
    curve_c = build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                               N_SECTORS, K_STOCKS, pick="bottom", include_etf_arm=False, cost_bps=COST_BPS)
    spy_curve = buy_hold(spy_m, curve_a.index)

    results = [metrics(curve_a, "A: Full system (sector momentum + top-K stock-pick)"),
               metrics(curve_b, "B: Sector-ETF-only (no stock-picking)"),
               metrics(curve_c, "C: Bottom-K stocks (falsification check)"),
               metrics(spy_curve, "D: SPY buy & hold")]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"] for r in results],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $100"], [50, 8, 8, 8, 8, 8, 11])

    a_m, b_m, c_m, spy_m_metrics = results

    # ── significance vs SPY ─────────────────────────────────────────────────
    r_a = curve_a.pct_change().dropna()
    r_spy = spy_curve.pct_change().dropna()
    aligned = pd.concat([r_a.rename("a"), r_spy.rename("spy")], axis=1).dropna()
    excess = (aligned["a"] - aligned["spy"]).values
    t_naive = rs.naive_t(excess)
    _, t_nw, n_obs = rs.newey_west_t(excess, lag=1)
    print(f"\nMonths: {n_obs}   Excess-over-SPY (Arm A) naive t: {fmt(t_naive,2)}   "
          f"Newey-West (lag=1, sanity check): {fmt(t_nw,2)}")

    stress_curve = build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                                    N_SECTORS, K_STOCKS, pick="top", include_etf_arm=False, cost_bps=COST_BPS_STRESS)
    stress_m = metrics(stress_curve, "")
    print(f"Cost stress ({COST_BPS_STRESS:.0f}bps one-way): CAGR {fmt(stress_m['cagr_pct'],2,'%')} "
          f"(base {fmt(a_m['cagr_pct'],2,'%')})")

    banner("WALK-FORWARD — first half (IS) vs second half (OOS), base config")
    mid = sec_mom_m.index[len(sec_mom_m) // 2]
    is_curve = build_portfolio(sec_mom_m.loc[:mid], stock_mom_m.loc[:mid], sec_to_stocks, sec_d, stock_px,
                                ret_sec_m, ret_stock_m, N_SECTORS, K_STOCKS, pick="top", include_etf_arm=False)
    oos_curve = build_portfolio(sec_mom_m.loc[mid:], stock_mom_m.loc[mid:], sec_to_stocks, sec_d, stock_px,
                                 ret_sec_m, ret_stock_m, N_SECTORS, K_STOCKS, pick="top", include_etf_arm=False)
    is_m = metrics(is_curve, f"IS ({is_curve.index[0].date() if len(is_curve) else '?'}+)")
    oos_m = metrics(oos_curve, f"OOS ({oos_curve.index[0].date() if len(oos_curve) else '?'}+)")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")]
           for r in [is_m, oos_m]], ["Period", "CAGR", "Sharpe", "MaxDD"], [30, 8, 8, 8])

    banner(f"PARAMETER SURFACE ({len(N_SECTORS_GRID)*len(K_STOCKS_GRID)} cells) — "
           "median / sign agreement, never the best cell")
    surf_rows = []
    for ns in N_SECTORS_GRID:
        for ks in K_STOCKS_GRID:
            c = build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                                 ns, ks, pick="top", include_etf_arm=False)
            m = metrics(c, "")
            surf_rows.append({"n_sectors": ns, "k_stocks": ks, "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"]})
    surf = pd.DataFrame(surf_rows)
    surf.to_csv("sector_stockpick_surface.csv", index=False)
    sc = surf["cagr_pct"].dropna()
    print(f"CAGR%  — median {fmt(sc.median(),2)}  min {fmt(sc.min(),2)}  max {fmt(sc.max(),2)}  "
          f"sign+ {(sc>0).mean()*100:.0f}% of {len(sc)} cells")

    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=5/8 to pass)")
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (Arm A, full sample)",
         a_m["cagr_pct"] > 0, f"{a_m['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps cost stress (still net positive CAGR)",
         stress_m["cagr_pct"] > 0, f"{stress_m['cagr_pct']:+.2f}%"),
        (3, True, "Walk-forward OOS half still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "Beats the sector-ETF-only baseline (stock-picking adds value)",
         a_m["sharpe"] > b_m["sharpe"], f"A {fmt(a_m['sharpe'],3)} vs B(ETF-only) {fmt(b_m['sharpe'],3)}"),
        (5, False, "Top-K beats Bottom-K within the same sectors (selection criterion is real)",
         a_m["sharpe"] > c_m["sharpe"], f"top-K {fmt(a_m['sharpe'],3)} vs bottom-K {fmt(c_m['sharpe'],3)}"),
        (6, False, "Beats SPY on both CAGR and Sharpe",
         a_m["cagr_pct"] > spy_m_metrics["cagr_pct"] and a_m["sharpe"] > spy_m_metrics["sharpe"],
         f"A {fmt(a_m['cagr_pct'],2)}%/{fmt(a_m['sharpe'],3)} vs SPY {fmt(spy_m_metrics['cagr_pct'],2)}%/{fmt(spy_m_metrics['sharpe'],3)}"),
        (7, False, "Parameter-surface median CAGR > 0 and sign agreement >= 70%",
         sc.median() > 0 and (sc > 0).mean() >= 0.70, f"median {fmt(sc.median(),2)}%, {(sc>0).mean()*100:.0f}% positive"),
        (8, False, "Excess-over-SPY naive |t| >= 3",
         np.isfinite(t_naive) and abs(t_naive) >= 3, f"t={fmt(t_naive,2)}"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:56], det[:44]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 56, 44])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 5 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/8 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — survived its own pre-registered bar; still only PAPER-testing evidence, not a live-trading"
        " recommendation, and the stock-layer survivorship-bias caveat above still applies." if verdict == "PASS"
        else " — report the null and stop. This does not mean sector momentum or stock-picking never"
             " work, only that this specific plain-rule specification did not clear its own bar here."))
    print("=" * 100)

    pd.DataFrame(results).to_csv("sector_stockpick_results.csv", index=False)
    pd.DataFrame({"full_system": curve_a, "sector_etf_only": curve_b, "bottom_k": curve_c,
                  "spy": spy_curve}).to_csv("sector_stockpick_curve.csv")
    print(f"\nWrote sector_stockpick_results.csv, sector_stockpick_surface.csv, sector_stockpick_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
