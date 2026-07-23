"""
Momentum Experiments — candidate improvements to the locked config
==================================================================
Tests improvement ideas on the cached monthly S&P 500 data (2005-2026), holding
the rest of the config fixed (blended 6&12m momentum, top 20, SPY 10-month trend
gate, 20 bps costs). Monthly granularity — so this covers rebalance FREQUENCY
(hold N months), WEIGHTING (equal vs inverse-vol), and VOLATILITY TARGETING.
Intra-month trailing stops and weekly/daily rebalancing need daily data and are
a separate run.

Reminder: absolute CAGRs are survivorship-inflated upper bounds; read the
RELATIVE differences between variants, not the levels.

Usage:  py momentum_experiments.py
"""

import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import momentum_stocks as ms

RFR = 0.03
TOPN = 20
TREND_SMA = 10
COST_BPS = 20
CASH_M = (1 + RFR) ** (1 / 12) - 1


def main():
    prices = ms.load_prices_cached()
    spy_m = prices[ms.BENCHMARK]
    stock_px = prices.drop(columns=[ms.BENCHMARK])
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= 26]

    ret_m = stock_px.pct_change()
    vol6 = ret_m.rolling(6).std()
    spy_sma = spy_m.rolling(TREND_SMA).mean()

    # Blended 6&12-month momentum, cross-sectional percentile rank (matches the
    # live screener), skipping the most recent month.
    r6 = stock_px.shift(1) / stock_px.shift(7) - 1
    r12 = stock_px.shift(1) / stock_px.shift(13) - 1
    rank_blend = ((r6.rank(axis=1, pct=True) + r12.rank(axis=1, pct=True)) / 2)
    rank_blend = rank_blend.where(r6.notna() & r12.notna())

    months = stock_px.index

    def run(hold_months=1, weight="equal", cost_bps=COST_BPS):
        equity = 100.0
        curve = pd.Series(index=months, dtype=float)
        w = pd.Series(0.0, index=stock_px.columns)
        turnovers = []
        for i in range(13, len(months) - 1):
            t, t1 = months[i], months[i + 1]
            if (i - 13) % hold_months == 0:                      # rebalance month
                neww = pd.Series(0.0, index=stock_px.columns)
                if spy_m.loc[t] > spy_sma.loc[t]:                # risk-on
                    s = rank_blend.loc[t].dropna().sort_values(ascending=False).head(TOPN)
                    if weight == "equal":
                        neww[s.index] = 1.0 / len(s)
                    else:                                        # inverse-vol
                        iv = 1.0 / vol6.loc[t, s.index].replace(0, np.nan)
                        iv = iv.fillna(iv.mean())
                        neww[s.index] = iv / iv.sum()
                turnovers.append((neww - w).abs().sum())
                equity *= (1.0 - (neww - w).abs().sum() * cost_bps / 1e4)
                w = neww
            port_r = float((w * ret_m.loc[t1].fillna(0.0)).sum()) + (1.0 - w.sum()) * CASH_M
            equity *= (1.0 + port_r)
            curve.loc[t1] = equity
        return curve.dropna(), float(np.mean(turnovers)) if turnovers else 0.0

    def vol_target(curve, target=0.15):
        """Volatility-managed overlay (Moreira-Muir / Barroso-Santa-Clara): scale
        next month's exposure by target / trailing realized vol, rest to cash."""
        r = curve.pct_change()
        tv = r.rolling(6).std() * np.sqrt(12)
        scale = (target / tv).clip(upper=1.5).shift(1).fillna(1.0)
        vr = r * scale + (1.0 - scale) * CASH_M
        return 100.0 * (1.0 + vr.fillna(0.0)).cumprod()

    base, base_turn = run(1, "equal")
    two, two_turn = run(2, "equal")
    qtr, qtr_turn = run(3, "equal")
    ivw, ivw_turn = run(1, "invvol")
    spy = ms.bh(prices, ms.BENCHMARK, base.index)

    print("!" * 74)
    print("Monthly S&P 500 data. Absolute CAGRs are survivorship-inflated UPPER")
    print("BOUNDS — compare the RELATIVE differences between rows.")
    print("!" * 74)
    print(f"\nWindow: {base.index[0].date()} -> {base.index[-1].date()}  "
          f"({len(base)} months)\n")

    rows = [
        ms.metrics(base, "BASE: monthly, equal-wt"),
        ms.metrics(two, "Rebalance every 2 months"),
        ms.metrics(qtr, "Rebalance quarterly"),
        ms.metrics(ivw, "Inverse-vol weighting"),
        ms.metrics(vol_target(base, 0.15), "Base + 15% vol target"),
        ms.metrics(vol_target(base, 0.20), "Base + 20% vol target"),
        ms.metrics(spy, "SPY buy & hold"),
    ]
    ms.print_metrics(rows)

    print(f"\nAvg monthly turnover — base {base_turn:.2f} | 2-month {two_turn:.2f} | "
          f"quarterly {qtr_turn:.2f} | inverse-vol {ivw_turn:.2f}")
    b = rows[0]
    print("\nvs BASE (monthly equal-wt):")
    for r in rows[1:-1]:
        print(f"  {r['label']:26s}  CAGR {r['cagr_pct']-b['cagr_pct']:+5.1f}pp   "
              f"Sharpe {r['sharpe']-b['sharpe']:+.2f}   MaxDD {r['max_dd_pct']-b['max_dd_pct']:+5.1f}pp")


if __name__ == "__main__":
    main()
