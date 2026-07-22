"""
Momentum Hardening — cost/slippage stress, config confirmation, bias discount
=============================================================================
Before committing single-stock momentum to paper trading, pressure-test it:

  1. COST SENSITIVITY — rerun the leading configs at 10 / 20 / 40 bps one-way
     turnover cost. High-turnover strategies die on costs; we need to see the
     edge survive a pessimistic assumption, not just the optimistic one.
  2. CONFIG CONFIRMATION — compare a small set of sensible configs (lookback,
     top-N, trend filter on/off) net of a realistic 20 bps cost, and pick one.
  3. SURVIVORSHIP DISCOUNT — at each cost level, report momentum minus the
     equal-weight hold of the SAME survivor universe. Both share the bias, so
     the *difference* is the honest, bias-controlled alpha estimate.

Reuses momentum_stocks.py (cached prices, backtest engine, metrics).

Usage:
  py momentum_harden.py
"""

import numpy as np
import pandas as pd

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

import momentum_stocks as ms


def _tab(rows, headers):
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("  ".join(headers))
        for r in rows:
            print("  ".join(str(v) for v in r))


def main():
    prices = ms.load_prices_cached()
    spy_m = prices[ms.BENCHMARK]
    stock_px = prices.drop(columns=[ms.BENCHMARK])
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= 26]
    print(f"Universe: {stock_px.shape[1]} survivor names, {len(prices)} months "
          f"({prices.index[0].date()} -> {prices.index[-1].date()})")

    # Candidate configs to confirm — (label, lookback, top_n, trend_filter).
    configs = [
        ("6m top10",            6, 10, False),
        ("6m top10 + trend",    6, 10, True),
        ("6m top20 + trend",    6, 20, True),
        ("12m top20 + trend",  12, 20, True),
        ("12m top30 + trend",  12, 30, True),
    ]
    cost_levels = [10.0, 20.0, 40.0]

    # ── 1+3. Cost sensitivity with bias-controlled alpha ─────────────────────
    print("\n" + "=" * 90)
    print("COST SENSITIVITY & SURVIVORSHIP-CONTROLLED ALPHA")
    print("  net CAGR / Sharpe / MaxDD  +  (alpha vs equal-weight-survivors, same cost)")
    print("=" * 90)

    # Reference baselines (cost-free holds).
    ew = ms.equal_weight_hold(stock_px, stock_px.index)
    for label, lb, n, tf in configs:
        row_out = [label]
        for cost in cost_levels:
            curve, _ = ms.backtest(stock_px, spy_m, top_n=n, lookback=lb, skip=1,
                                   trend_filter=tf, cost_bps=cost)
            m = ms.metrics(curve, label)
            ew_al = ms.metrics(ew.reindex(curve.index).dropna(), "ew")
            alpha = m["cagr_pct"] - ew_al["cagr_pct"]
            row_out.append(f"{m['cagr_pct']:.1f}/{m['sharpe']:.2f}/{m['max_dd_pct']:.0f}% "
                           f"(+{alpha:.1f})")
        _tab([row_out], ["config \\ cost"] + [f"{int(c)}bps" for c in cost_levels])

    spy_m_metrics = ms.metrics(ms.bh(prices, ms.BENCHMARK, stock_px.index[14:]), "SPY")
    ew_metrics = ms.metrics(ew.iloc[14:], "EW-survivors")
    print(f"\n  Reference (cost-free):  SPY  CAGR {spy_m_metrics['cagr_pct']:.1f}%  "
          f"Sharpe {spy_m_metrics['sharpe']:.2f}  MaxDD {spy_m_metrics['max_dd_pct']:.0f}%")
    print(f"                          EW   CAGR {ew_metrics['cagr_pct']:.1f}%  "
          f"Sharpe {ew_metrics['sharpe']:.2f}  MaxDD {ew_metrics['max_dd_pct']:.0f}%")

    # ── 2. Config confirmation at a realistic 20 bps, full metrics ───────────
    print("\n" + "=" * 90)
    print("CONFIG CONFIRMATION — net of 20 bps one-way cost")
    print("=" * 90)
    rows = []
    for label, lb, n, tf in configs:
        curve, log = ms.backtest(stock_px, spy_m, top_n=n, lookback=lb, skip=1,
                                 trend_filter=tf, cost_bps=20.0)
        m = ms.metrics(curve, label)
        avg_turn = float(np.mean([r["turnover"] for _, r in log.iterrows()])) if len(log) else 0.0
        rows.append([label, f"{m['cagr_pct']:.1f}%", f"{m['sharpe']:.2f}",
                     f"{m['sortino']:.2f}", f"{m['max_dd_pct']:.0f}%",
                     f"{m['worst_year_pct']:.0f}%", f"{avg_turn:.2f}"])
    _tab(rows, ["config", "CAGR", "Sharpe", "Sortino", "MaxDD", "WorstYr", "AvgTurn"])

    print("\nTurnover note: AvgTurn ~0.4 = ~40% of the book changes each month; at 20bps")
    print("that is ~1%/yr of drag (already included above). Real slippage on illiquid")
    print("names would add more — favors larger-cap, higher-N, liquid picks.")


if __name__ == "__main__":
    main()
