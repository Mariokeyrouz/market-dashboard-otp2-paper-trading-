"""
RRG Null — the mechanical baseline for every RRG metric
=======================================================
Runs synthetic price panels with **zero relative drift** — pure random walks,
no signal of any kind — through the *entire* rrg_core pipeline, and records the
distribution of every metric the real study will report.

WHY THIS EXISTS
---------------
An RRG plots a rolling z-score against (approximately) its own derivative. That
phase portrait rotates clockwise for any stationary series, and the S-period
smoothing manufactures long, straight-looking tails on its own. rrg_core's
self-test already shows pure noise producing ~0.77 straightness against a
random-walk null of 0.33.

So "sector X has a long persistent north-east tail" is not evidence until we
know what a *coin flip* produces under the same transform. This module supplies
that number. Every real-data statistic in rrg_validate.py is reported next to
its percentile in this null distribution.

It also prices the search itself: the distribution of max |t| across factors
tells us the critical value that a "significant" result must clear once we
account for having looked at several factors.

Outputs
-------
  rrg_null_results.csv   metric | mean | p50 | p90 | p95 | p99 | n_sims

Usage:
  py rrg_null.py                 # 500 sims (default)
  py rrg_null.py 100             # quick pass
"""

import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import rrg_core as rc
import rrg_stats as rs

# ── Simulation design ────────────────────────────────────────────────────────
# Shaped to mirror the primary real sample: 9 sector-like assets, weekly, from
# roughly 1999 -> 2026 after burn-in.
N_SIMS = 500
N_ASSETS = 9
N_PERIODS = 1400              # weekly observations
MKT_VOL = 0.021               # weekly market factor vol (~15% annualized)
IDIO_VOL = 0.018              # weekly idiosyncratic vol
BETA_LO, BETA_HI = 0.75, 1.25
HORIZONS = {"1M": 4, "3M": 13}       # weekly periods
SEED = 20260728

FACTORS = ["distance", "delta_distance", "ne_score", "straightness",
           "tail_r2", "quadrant_run"]


def simulate_panel(rng):
    """
    A market factor plus betas plus idiosyncratic noise. No asset has any drift
    relative to the benchmark, so the true forward excess return is zero by
    construction and every measured "edge" is mechanical.
    """
    mkt = rng.normal(0.0, MKT_VOL, size=N_PERIODS)
    betas = rng.uniform(BETA_LO, BETA_HI, size=N_ASSETS)
    idio = rng.normal(0.0, IDIO_VOL, size=(N_PERIODS, N_ASSETS))
    rets = mkt[:, None] * betas[None, :] + idio
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    bench = prices.mean(axis=1)          # equal-weight benchmark of the panel
    return prices, bench


def forward_excess(prices, bench, H):
    """Asset H-period forward return minus the benchmark's. NaN in the last H."""
    T = prices.shape[0]
    fwd = np.full(prices.shape, np.nan)
    fb = np.full(T, np.nan)
    fwd[:T - H] = prices[H:] / prices[:T - H] - 1.0
    fb[:T - H] = bench[H:] / bench[:T - H] - 1.0
    return fwd - fb[:, None]


def run_once(rng, params):
    """One synthetic panel -> a dict of metrics."""
    prices, bench = simulate_panel(rng)
    idx = pd.date_range("2000-01-07", periods=N_PERIODS, freq="W-FRI")
    px = pd.DataFrame(prices, index=idx,
                      columns=[f"A{i}" for i in range(N_ASSETS)])
    feats = rc.compute_features(px, pd.Series(bench, index=idx), params)

    out = {}
    fin = lambda a: a[np.isfinite(a)]

    st = fin(feats["straightness"].to_numpy())
    out["straightness_mean"] = st.mean() if st.size else np.nan
    run = fin(feats["quadrant_run"].to_numpy())
    out["quadrant_run_median"] = np.median(run) if run.size else np.nan
    out["quadrant_run_p90"] = np.quantile(run, 0.90) if run.size else np.nan

    q = fin(feats["quadrant"].to_numpy()).astype(int)
    for k, name in enumerate(rc.QUADRANTS):
        out[f"occupancy_{name}"] = float(np.mean(q == k)) if q.size else np.nan

    ne = fin(feats["ne_score"].to_numpy())
    out["ne_score_mean"] = ne.mean() if ne.size else np.nan
    flat = fin(feats["is_flat"].to_numpy())
    out["flat_share"] = flat.mean() if flat.size else np.nan

    for hname, H in HORIZONS.items():
        fexc = forward_excess(prices, bench, H)
        lag = int(np.ceil(1.5 * H))

        # unconditional baseline hit rate — never assume 50%
        out[f"baseline_hit_{hname}"] = rs.hit_rate(fexc)

        ts = []
        for f in FACTORS:
            ic = rs.cross_sectional_ic(feats[f].to_numpy(), fexc)
            m, t, _ = rs.newey_west_t(ic, lag)
            out[f"ic_{f}_{hname}"] = m
            out[f"t_{f}_{hname}"] = t
            if np.isfinite(t):
                ts.append(abs(t))
        # the critical value the search must clear
        out[f"max_abs_t_{hname}"] = max(ts) if ts else np.nan

        # hit rate by quadrant, and the Leading-minus-Lagging spread
        qq = feats["quadrant"].to_numpy()
        hits = {}
        for k, name in enumerate(rc.QUADRANTS):
            sel = fexc[qq == k]
            hits[name] = rs.hit_rate(sel)
            out[f"hit_{name}_{hname}"] = hits[name]
        if np.isfinite(hits["Leading"]) and np.isfinite(hits["Lagging"]):
            out[f"hit_spread_Lead_minus_Lag_{hname}"] = hits["Leading"] - hits["Lagging"]

        # distance decile spread: top minus bottom
        _, buckets = rs.bucket_table(feats["distance"].to_numpy(), fexc, n_buckets=10)
        if len(buckets) >= 10:
            out[f"dist_decile_spread_{hname}"] = (
                float(np.mean(buckets[9])) - float(np.mean(buckets[0])))
    return out


def main():
    t0 = time.time()
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else N_SIMS
    params = dict(rc.WEEKLY)

    print("=" * 78)
    print("RRG SYNTHETIC NULL — mechanical baseline under ZERO true edge")
    print("=" * 78)
    print(f"  sims={n_sims}  assets={N_ASSETS}  periods={N_PERIODS} (weekly)")
    print(f"  params W={params['W']} S={params['S']} M={params['M']} L={params['L']}"
          f"   burn-in={rc.burn_in(params['W'], params['S'], params['M'])}")
    print("  Every asset has ZERO drift relative to the benchmark. Any structure")
    print("  below is produced by the transform itself, not by a market effect.\n")

    rng = np.random.default_rng(SEED)
    rows = []
    for i in range(n_sims):
        rows.append(run_once(rng, params))
        if (i + 1) % max(1, n_sims // 10) == 0:
            print(f"    {i+1}/{n_sims} sims  ({time.time()-t0:.0f}s)", flush=True)

    df = pd.DataFrame(rows)
    summary = pd.DataFrame({
        "metric": df.columns,
        "mean": df.mean().to_numpy(),
        "p50": df.quantile(0.50).to_numpy(),
        "p90": df.quantile(0.90).to_numpy(),
        "p95": df.quantile(0.95).to_numpy(),
        "p99": df.quantile(0.99).to_numpy(),
        "n_sims": n_sims,
    })
    summary.to_csv("rrg_null_results.csv", index=False)

    def show(title, keys, fmt="{:.4f}"):
        print("\n" + "-" * 78)
        print(title)
        print("-" * 78)
        sub = summary[summary["metric"].isin(keys)]
        if sub.empty:
            print("  (none)")
            return
        disp = sub.copy()
        for c in ("mean", "p50", "p90", "p95", "p99"):
            disp[c] = disp[c].map(lambda v: fmt.format(v) if np.isfinite(v) else "—")
        print(disp[["metric", "mean", "p50", "p95", "p99"]].to_string(index=False))

    show("GEOMETRY — what pure noise looks like on an RRG",
         ["straightness_mean", "quadrant_run_median", "quadrant_run_p90",
          "ne_score_mean", "flat_share"] +
         [f"occupancy_{q}" for q in rc.QUADRANTS])

    print(f"\n  Random-walk straightness null is {rc.straightness_null(params['L']):.3f}; "
          f"the transform alone lifts it to {summary.loc[summary['metric']=='straightness_mean','mean'].iloc[0]:.3f}.")
    print("  => A 'persistent tail' on real data must beat the SIMULATED number, not 0.33.")

    show("BASELINE HIT RATES — the honest comparison point (NOT 50%)",
         [f"baseline_hit_{h}" for h in HORIZONS])

    show("HIT RATE BY QUADRANT under zero true edge",
         [f"hit_{q}_{h}" for h in HORIZONS for q in rc.QUADRANTS] +
         [f"hit_spread_Lead_minus_Lag_{h}" for h in HORIZONS])

    show("FACTOR IC under zero true edge (p95/p99 are the critical values)",
         [f"ic_{f}_{h}" for h in HORIZONS for f in FACTORS])

    show("t-STATS under zero true edge — note max_abs_t: the search-adjusted bar",
         [f"t_{f}_{h}" for h in HORIZONS for f in FACTORS] +
         [f"max_abs_t_{h}" for h in HORIZONS], fmt="{:+.2f}")

    show("DISTANCE DECILE SPREAD (top minus bottom) under zero true edge",
         [f"dist_decile_spread_{h}" for h in HORIZONS])

    print("\n" + "=" * 78)
    print("HOW TO USE THIS FILE")
    print("=" * 78)
    print("  A real-data metric counts as evidence only if it exceeds the p95/p99")
    print("  column above. Anything inside the null band is the transform talking.")
    for h in HORIZONS:
        row = summary[summary["metric"] == f"max_abs_t_{h}"]
        if not row.empty and np.isfinite(row["p95"].iloc[0]):
            print(f"  {h}: searching {len(FACTORS)} factors gives max|t| p95 = "
                  f"{row['p95'].iloc[0]:.2f} under the pure null "
                  f"-> |t| below that is noise.")
    print(f"\nSaved -> rrg_null_results.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
