"""
Four-Pillar Combination — drift-band (rule-based) rebalancing, not calendar-based
======================================================================================
four_pillar_combination_backtest.py's equal-weight-of-4 result (Sharpe 1.139,
MaxDD -9.1% over 2009-2026) implicitly rebalanced back to 25/25/25/25 every
single month regardless of how far weights had actually drifted — and never
modeled a cost for doing so. This script fixes both: weights drift freely
between checks and a REBALANCE ONLY FIRES WHEN A PILLAR BREACHES A BAND
around its 25% target (standard band/threshold rebalancing, not a fixed
calendar), with an explicit top-level trading cost applied whenever a
rebalance actually happens.

Pillars (identical to four_pillar_combination_backtest.py, reused from its
saved output — no new signal construction): Gold, SectorEW, FMTS, OTP2.0,
each already validated / diagnosed on its own in this session.

RULE
------
Check monthly (matches each pillar's own native rebalance cadence). If any
pillar's weight has drifted more than `band` away from 25%, reset ALL FOUR
back to 25/25/25/25 and pay a turnover cost; otherwise let weights drift for
free. `band=0` reduces to "always rebalance" and should reproduce
four_pillar_combination_backtest.py's original result almost exactly — used
here as a correctness check on the mechanics, not a headline result.

Outputs: four_pillar_band_surface.csv, four_pillar_band_curve.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py four_pillar_band_rebalance_backtest.py
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

import rrg_stats as rs

RFR = 0.03
COST_BPS = 10.0          # top-level rebalancing cost, one-way, on $ traded
COST_BPS_STRESS = 20.0
TARGET_W = 0.25          # 4 pillars, equal target

BAND_GRID = (0.0, 0.03, 0.05, 0.08, 0.12)   # 0.0 = "always rebalance" sanity check
BASE_BAND = 0.05


# ─────────────────────────────────────────────────────────────────────────────
# 1. BAND-REBALANCED PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

def run_band_portfolio(panel, band, cost_bps, start=None, end=None):
    """panel: DataFrame of monthly simple returns, columns = pillars."""
    idx = panel.index
    if start is not None:
        idx = idx[idx >= pd.Timestamp(start)]
    if end is not None:
        idx = idx[idx <= pd.Timestamp(end)]
    cols = list(panel.columns)
    n_assets = len(cols)
    target = np.full(n_assets, 1.0 / n_assets)

    w = target.copy()
    eq = 100.0
    curve = {}
    n_rebals = 0
    turnover_total = 0.0

    for i in range(len(idx) - 1):
        t, t1 = idx[i], idx[i + 1]
        drift = np.max(np.abs(w - target))
        if drift > band or band == 0.0:
            turn = float(np.abs(target - w).sum())
            eq *= (1.0 - turn * cost_bps / 1e4)
            w = target.copy()
            n_rebals += 1
            turnover_total += turn

        r = panel.loc[t1, cols].to_numpy(dtype=float)
        r = np.nan_to_num(r, nan=0.0)
        port_r = float((w * r).sum())
        eq *= (1.0 + port_r)
        curve[t1] = eq

        w = w * (1.0 + r)
        wsum = w.sum()
        if wsum > 0:
            w = w / wsum

    return pd.Series(curve).sort_index(), n_rebals, turnover_total


def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    if len(curve) < 12:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan, "max_dd_pct": np.nan}
    n = len(curve)
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (12 / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() - rfr / 12) / r.std() * np.sqrt(12) if r.std() > 0 else 0.0
    roll = curve.cummax()
    dd = (curve - roll) / roll
    return {"label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100, "sharpe": sharpe, "max_dd_pct": dd.min() * 100}


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
# 2. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("FOUR-PILLAR COMBINATION — drift-band rebalancing (rule-based, not calendar)")
    print("Rebalance to 25/25/25/25 only when a pillar drifts beyond `band` of its target,")
    print("not automatically every month. Top-level trading cost now explicitly modeled.")
    print("PAPER-TESTING RESEARCH ONLY.\n")

    panel = pd.read_csv("four_pillar_monthly_returns.csv", index_col=0, parse_dates=True)
    print(f"Loaded four_pillar_monthly_returns.csv: {panel.index[0].date()} -> {panel.index[-1].date()} "
          f"({len(panel)} months), pillars: {', '.join(panel.columns)}")

    # sanity check: band=0 should reproduce the original always-rebalance result
    curve0, n0, turn0 = run_band_portfolio(panel, 0.0, COST_BPS)
    m0 = metrics(curve0, "band=0 (always rebalance, +10bps cost)")
    print(f"\nSanity check — band=0 vs original (no top-level cost modeled there): "
          f"Sharpe {fmt(m0['sharpe'],3)} here vs 1.139 original (small gap expected: cost now included).")

    banner(f"BASE CONFIG — band=±{BASE_BAND:.0%}")
    curve_base, n_base, turn_base = run_band_portfolio(panel, BASE_BAND, COST_BPS)
    m_base = metrics(curve_base, f"Band ±{BASE_BAND:.0%}")
    print(f"  Rebalances triggered: {n_base} of {len(panel)-1} possible months "
          f"({100*n_base/(len(panel)-1):.1f}%)   Total turnover: {turn_base:.2f}")
    print(f"  CAGR {fmt(m_base['cagr_pct'],2,'%')}   Sharpe {fmt(m_base['sharpe'],3)}   "
          f"MaxDD {fmt(m_base['max_dd_pct'],1,'%')}")

    banner(f"BAND SURFACE ({len(BAND_GRID)} widths) — turnover vs performance tradeoff")
    rows = []
    for band in BAND_GRID:
        c, n_reb, turn = run_band_portfolio(panel, band, COST_BPS)
        m = metrics(c, f"band={band:.0%}")
        rows.append({"band_pct": band * 100, "n_rebals": n_reb, "turnover": turn,
                     "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"], "max_dd_pct": m["max_dd_pct"]})
    surf = pd.DataFrame(rows)
    surf.to_csv("four_pillar_band_surface.csv", index=False)
    table([[f"{r['band_pct']:.0f}%", r["n_rebals"], f"{r['turnover']:.2f}", fmt(r["cagr_pct"], 2, "%"),
            fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")] for r in rows],
          ["Band", "#Rebals", "Turnover", "CAGR", "Sharpe", "MaxDD"], [8, 9, 10, 8, 8, 8])

    best_row = surf.loc[surf["sharpe"].idxmax()]
    print(f"\n  Best Sharpe in the surface: band={best_row['band_pct']:.0f}% "
          f"(Sharpe {best_row['sharpe']:.3f}) — reported for transparency, not as a recommendation;")
    print(f"  see CLAUDE.md's parameter-surface discipline before treating any single cell as the answer.")

    # ── cost stress ──────────────────────────────────────────────────────────
    curve_stress, _, _ = run_band_portfolio(panel, BASE_BAND, COST_BPS_STRESS)
    m_stress = metrics(curve_stress, "")
    print(f"\nCost stress ({COST_BPS_STRESS:.0f}bps one-way, band=±{BASE_BAND:.0%}): "
          f"CAGR {fmt(m_stress['cagr_pct'],2,'%')} (base {fmt(m_base['cagr_pct'],2,'%')})")

    # ── walk-forward ─────────────────────────────────────────────────────────
    banner("WALK-FORWARD — first half (IS) vs second half (OOS), band=±5%")
    mid = panel.index[len(panel) // 2]
    is_curve, _, _ = run_band_portfolio(panel, BASE_BAND, COST_BPS, end=mid)
    oos_curve, _, _ = run_band_portfolio(panel, BASE_BAND, COST_BPS, start=mid)
    is_m = metrics(is_curve, f"IS ({panel.index[0].date()} - {mid.date()})")
    oos_m = metrics(oos_curve, f"OOS ({mid.date()} - {panel.index[-1].date()})")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")]
           for r in [is_m, oos_m]], ["Period", "CAGR", "Sharpe", "MaxDD"], [40, 8, 8, 8])

    ret_base = curve_base.pct_change().dropna()
    t_naive = rs.naive_t(ret_base.values)
    _, t_nw, n_obs = rs.newey_west_t(ret_base.values, lag=1)
    print(f"\nBase-band monthly returns: naive t (n={n_obs}) = {fmt(t_naive,2)}   "
          f"Newey-West (lag=1) = {fmt(t_nw,2)}")

    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=4/6 to pass)")
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (band=±5%, base config)",
         m_base["cagr_pct"] > 0, f"{m_base['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps cost stress (still net positive CAGR)",
         m_stress["cagr_pct"] > 0, f"{m_stress['cagr_pct']:+.2f}%"),
        (3, True, "Walk-forward OOS half still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "Band rebalancing beats always-rebalance (band=0) net of costs",
         m_base["sharpe"] > m0["sharpe"], f"band=5% {fmt(m_base['sharpe'],3)} vs always {fmt(m0['sharpe'],3)}"),
        (5, False, "Reduces turnover materially vs always-rebalance (>=30% fewer trades)",
         n_base <= 0.7 * n0, f"{n_base} vs {n0} rebalances ({100*n_base/max(n0,1):.0f}% of always-rebalance)"),
        (6, False, "Newey-West |t| on band-config monthly returns >= 3",
         np.isfinite(t_nw) and abs(t_nw) >= 3, f"t={fmt(t_nw,2)}"),
    ]
    rows2 = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:56], det[:44]]
             for n, mand, desc, ok, det in checks]
    table(rows2, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 56, 44])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 4 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/6 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}")
    print("=" * 100)

    curves = pd.DataFrame({f"band_{int(b*100)}pct": run_band_portfolio(panel, b, COST_BPS)[0] for b in BAND_GRID})
    curves.to_csv("four_pillar_band_curve.csv")
    print(f"\nWrote four_pillar_band_surface.csv, four_pillar_band_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
