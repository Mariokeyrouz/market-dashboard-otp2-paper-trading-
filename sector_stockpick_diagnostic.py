"""
Diagnostic: why did sector_momentum_stockpick_backtest.py's "edge" survive
its own numbers but fail its falsification check?
==============================================================================
sector_momentum_stockpick_backtest.py found Arm A (top-5 momentum stocks per
winning sector) beating SPY and the real sector ETF — but Arm C (bottom-5,
i.e. the WORST performers in the same sectors) did just as well. That means
the edge isn't coming from WHICH stocks get picked. This script isolates
WHERE it's actually coming from, using three real, historically-accurate
Invesco equal-weight sector ETFs (RSPT, RSPF, RSPG, ...) as a survivorship-
bias-free, point-in-time-accurate reference:

  B  Cap-weight sector ETF (XLK, XLF, ...)      — real fund, real weighting
  E  Equal-weight sector ETF (RSPT, RSPF, ...)  — real fund, equal weight
  F  Equal-weight ALL sector constituents        — momentum_daily_prices.csv,
     from momentum_daily_prices.csv               survivorship-biased panel
  A  Top-5 momentum stocks (from the prior script) — subset of F
  C  Bottom-5 momentum stocks (from the prior script) — subset of F

Same monthly top-3-sector selection (12-1 relative momentum vs SPY) drives
which sectors are held in every arm — only the INSTRUMENT held within those
sectors differs. If E ~ F (real equal-weight ETF tracks our backfilled
equal-weight basket closely), the A/C edge over SPY is a genuine equal-weight
premium. If F >> E, that gap is the survivorship-bias/point-in-time artifact.

This is PAPER-TESTING RESEARCH ONLY.

Usage:
  py sector_stockpick_diagnostic.py
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
from strategy_deep_test import download_many
import sector_momentum_stockpick_backtest as base

# Invesco S&P 500 Equal Weight Sector ETFs — real funds, no survivorship bias,
# no point-in-time sector-labeling issue (each ETF's own historical holdings).
EW_TICKERS = {
    "XLK": "RSPT", "XLF": "RSPF", "XLE": "RSPG", "XLV": "RSPH", "XLI": "RSPN",
    "XLY": "RSPD", "XLP": "RSPS", "XLU": "RSPU", "XLB": "RSPM",
}

N_SECTORS = base.N_SECTORS
K_STOCKS = base.K_STOCKS
COST_BPS = base.COST_BPS


def load_ew_etfs():
    tickers = list(EW_TICKERS.values())
    print(f"Downloading equal-weight sector ETFs: {', '.join(tickers)}...")
    raw = download_many(tickers)
    ok = {t: raw[t]["Close"].squeeze() for t in tickers if t in raw and len(raw[t]) > 500}
    missing = [t for t in tickers if t not in ok]
    if missing:
        print(f"  [WARN] failed or too little history: {missing} — those sectors will be "
              f"excluded from the equal-weight-ETF arm when selected.")
    px = pd.DataFrame(ok)
    px.index = pd.to_datetime(px.index).tz_localize(None)
    return px


def build_instrument_arm(sec_mom_m, price_m, ret_m, sector_to_col, n_sectors, cost_bps, start=None):
    """Arm B / E: hold the chosen INSTRUMENT (cap-weight or equal-weight ETF)
    for each of the top n_sectors sectors, equal dollar-weighted across the
    3 sectors, monthly rebalance."""
    dates = sec_mom_m.index.intersection(ret_m.index)
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    eq = 100.0
    curve = {}
    w = pd.Series(dtype=float)

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        sm = sec_mom_m.loc[t].dropna()
        top_sectors = [s for s in sm.nlargest(n_sectors * 2).index if sector_to_col.get(s) in ret_m.columns]
        top_sectors = top_sectors[:n_sectors]
        cols = [sector_to_col[s] for s in top_sectors]
        tgt = pd.Series(1.0 / len(cols), index=cols) if cols else pd.Series(dtype=float)

        all_idx = w.index.union(tgt.index)
        turn = float((tgt.reindex(all_idx).fillna(0.0) - w.reindex(all_idx).fillna(0.0)).abs().sum())
        eq *= (1.0 - turn * cost_bps / 1e4)
        w = tgt

        r = float((w * ret_m.loc[t1].reindex(w.index).fillna(0.0)).sum()) if len(w) else 0.0
        eq *= (1.0 + r)
        curve[t1] = eq

        if len(w):
            w = w * (1.0 + ret_m.loc[t1].reindex(w.index).fillna(0.0))
            wsum = w.sum()
            if wsum > 0:
                w = w / wsum

    return pd.Series(curve).sort_index()


def build_equal_weight_all(sec_mom_m, stock_mom_m, sec_to_stocks, ret_stock_m, n_sectors, cost_bps, start=None):
    """Arm F: equal-weight ALL constituents (not just top/bottom-K) in the
    winning sectors, from the backfilled stock panel."""
    dates = sec_mom_m.index.intersection(stock_mom_m.index)
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    eq = 100.0
    curve = {}
    w = pd.Series(dtype=float)

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        sm = sec_mom_m.loc[t].dropna()
        top_sectors = sm.nlargest(n_sectors).index
        names = []
        for etf in top_sectors:
            cand = [c for c in sec_to_stocks.get(etf, []) if c in stock_mom_m.columns]
            avail = stock_mom_m.loc[t, cand].dropna().index if cand else []
            names.extend(list(avail))
        tgt = pd.Series(1.0 / len(names), index=names) if names else pd.Series(dtype=float)

        all_idx = w.index.union(tgt.index)
        turn = float((tgt.reindex(all_idx).fillna(0.0) - w.reindex(all_idx).fillna(0.0)).abs().sum())
        eq *= (1.0 - turn * cost_bps / 1e4)
        w = tgt

        r = float((w * ret_stock_m.loc[t1].reindex(w.index).fillna(0.0)).sum()) if len(w) else 0.0
        eq *= (1.0 + r)
        curve[t1] = eq

        if len(w):
            w = w * (1.0 + ret_stock_m.loc[t1].reindex(w.index).fillna(0.0))
            wsum = w.sum()
            if wsum > 0:
                w = w / wsum

    return pd.Series(curve).sort_index()


def main():
    t0 = time.time()
    base.banner("DIAGNOSTIC — is the sector+stockpick edge real, or survivorship bias?")
    print("Compares: cap-weight sector ETF vs REAL equal-weight sector ETF vs backfilled-panel")
    print("equal-weight-all vs top-K vs bottom-K. Same monthly sector selection drives all arms.")

    sec_d, spy_d, stock_px, sec_to_stocks = base.load_data()
    ew_px = load_ew_etfs()

    sec_m = sec_d.resample("ME").last()
    spy_m = spy_d.resample("ME").last()
    stock_m = stock_px.resample("ME").last()
    ew_m = ew_px.resample("ME").last()

    ret_sec_m = sec_m.pct_change()
    ret_stock_m = stock_m.pct_change()
    ret_ew_m = ew_m.pct_change()

    sec_mom_m = base.momentum_signal(sec_m, spy_m, base.LOOKBACK_M, base.SKIP_M)
    spy_m_aligned = spy_m.reindex(stock_m.index)
    stock_mom_m = base.momentum_signal(stock_m, spy_m_aligned, base.LOOKBACK_M, base.SKIP_M)

    identity_map = {s: s for s in rd.SECTOR_CORE}
    curve_b = build_instrument_arm(sec_mom_m, sec_m, ret_sec_m, identity_map, N_SECTORS, COST_BPS)
    curve_e = build_instrument_arm(sec_mom_m, ew_m, ret_ew_m, EW_TICKERS, N_SECTORS, COST_BPS)
    curve_f = build_equal_weight_all(sec_mom_m, stock_mom_m, sec_to_stocks, ret_stock_m, N_SECTORS, COST_BPS)
    curve_a = base.build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                                    N_SECTORS, K_STOCKS, pick="top", include_etf_arm=False, cost_bps=COST_BPS)
    curve_c = base.build_portfolio(sec_mom_m, stock_mom_m, sec_to_stocks, sec_d, stock_px, ret_sec_m, ret_stock_m,
                                    N_SECTORS, K_STOCKS, pick="bottom", include_etf_arm=False, cost_bps=COST_BPS)
    spy_curve = base.buy_hold(spy_m, curve_a.index)

    results = [
        base.metrics(curve_b, "B: Cap-weight sector ETF (XLK, XLF, ... — real fund)"),
        base.metrics(curve_e, "E: Equal-weight sector ETF (RSPT, RSPF, ... — real fund)"),
        base.metrics(curve_f, "F: Equal-weight ALL constituents (backfilled panel)"),
        base.metrics(curve_a, "A: Top-5 momentum stocks (backfilled panel)"),
        base.metrics(curve_c, "C: Bottom-5 momentum stocks (backfilled panel)"),
        base.metrics(spy_curve, "SPY buy & hold"),
    ]
    base.table([[r["label"], base.fmt(r["cagr_pct"], 2, "%"), base.fmt(r["vol_pct"], 2, "%"),
                 base.fmt(r["sharpe"], 3), base.fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"]
                for r in results],
               ["Arm", "CAGR", "Vol", "Sharpe", "MaxDD", "Final $100"], [55, 8, 8, 8, 8, 11])

    b_m, e_m, f_m, a_m, c_m, spy_m_metrics = results

    base.banner("THE DECISIVE COMPARISON")
    gap_ew = f_m["cagr_pct"] - e_m["cagr_pct"]
    gap_sharpe = f_m["sharpe"] - e_m["sharpe"]
    print(f"  Backfilled equal-weight-all (F) vs REAL equal-weight ETF (E):")
    print(f"    CAGR gap:   {gap_ew:+.2f}pp   ({base.fmt(f_m['cagr_pct'],2)}% vs {base.fmt(e_m['cagr_pct'],2)}%)")
    print(f"    Sharpe gap: {gap_sharpe:+.3f}   ({base.fmt(f_m['sharpe'],3)} vs {base.fmt(e_m['sharpe'],3)})")
    if abs(gap_sharpe) < 0.15:
        print("\n  -> F and E are CLOSE. The A/C edge over SPY looks like a genuine equal-weight")
        print("     premium (real, but not survivorship bias) — the backfilled panel isn't lying.")
    else:
        print("\n  -> F clearly beats E despite both being 'equal-weight within winning sectors.'")
        print("     Since E is a real historical fund (no survivorship bias) and F uses the")
        print("     backfilled panel, this gap IS the survivorship-bias / point-in-time artifact —")
        print("     not stock-picking skill, not even a real equal-weight premium.")

    print(f"\n  For reference: E vs cap-weight ETF (B) — the genuine equal-weight-premium question:")
    print(f"    CAGR: {base.fmt(e_m['cagr_pct'],2)}% vs {base.fmt(b_m['cagr_pct'],2)}%   "
          f"Sharpe: {base.fmt(e_m['sharpe'],3)} vs {base.fmt(b_m['sharpe'],3)}")

    pd.DataFrame(results).to_csv("sector_stockpick_diagnostic_results.csv", index=False)
    pd.DataFrame({"cap_weight_etf": curve_b, "equal_weight_etf": curve_e, "equal_weight_all_backfilled": curve_f,
                  "top5_backfilled": curve_a, "bottom5_backfilled": curve_c, "spy": spy_curve}
                 ).to_csv("sector_stockpick_diagnostic_curve.csv")
    print(f"\nWrote sector_stockpick_diagnostic_results.csv, sector_stockpick_diagnostic_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
