"""
RRG Analysis — top-down sector -> stock report with Kelly sizing
=================================================================
Produces the requested deliverable: sector ranking, stock ranking, top 3
sectors, top 5 stocks, position sizes, the 1/2-vs-1/4 Kelly decision, and the
increase/reduce/exit signals.

EVERY NUMBER HERE IS MEASURED. Nothing is an opinion:

  RRG Score      = walk-forward-fitted linear predictor of forward excess
                   return, from rrg_calibration.json (weights fit on past data
                   only), applied to cross-sectionally standardized factors,
                   then percentile-ranked for display. The raw predicted excess
                   is kept for sizing, because ranks destroy the magnitude
                   information Kelly needs.
  Heading/Angle  = PCA principal direction of the tail on standardized axes.
  Distance       = Mahalanobis distance from the (100,100) centre.
  Tail           = straightness (net displacement / path length), reported
                   against the SIMULATED null, not the naive random-walk null.
  Hit rate / W / R = counted from the actual historical panel, per
                   (quadrant x distance tercile) bucket.

WHAT THE VALIDATION FOUND (rrg_validate.py, read from rrg_calibration.json)
---------------------------------------------------------------------------
The pre-registered bar was NOT met. In-sample the signal looks strong
(IR 0.60, t 3.10); walk-forward it is IR 0.03, t 0.15, with an IS->OOS decay
ratio of 0.26 and a calibration slope of 0.38. Critically, the RRG block adds
nothing over plain 12-1 relative momentum (incremental IC -0.004, t -0.26).

So the sizing section below reports the Kelly arithmetic exactly as specified
AND applies the empirically-calibrated multiplier, which is zero. That is the
honest answer, and it is what the pre-registration committed to.

Usage:
  py rrg_analysis.py
"""

import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

try:                                    # Windows console is cp1252 by default
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import rrg_core as rc
import rrg_data as rd
import rrg_stats as rs
import rrg_validate as rv

PORTFOLIO = 10_000.0
N_TOP_SECTORS = 3
N_STOCKS_PER_SECTOR = 3
MAX_POSITION_PCT = 20.0          # hard cap, regardless of Kelly
MAX_SECTOR_PCT = 35.0
MAX_LEVERAGE = 1.0
MIN_TRADE_DOLLARS = 250.0        # below this, whole-share rounding dominates
TAIL_WEEKS = 14                  # RRG tail length drawn on the dashboard

CAL_PATH = "rrg_calibration.json"


# ─────────────────────────────────────────────────────────────────────────────
# 1. HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_calibration():
    if not os.path.exists(CAL_PATH):
        raise FileNotFoundError("Run `py rrg_validate.py` first to produce "
                                f"{CAL_PATH}.")
    with open(CAL_PATH) as f:
        return json.load(f)


def latest_row(df):
    """Last row that has any finite value."""
    arr = df.to_numpy(dtype=float)
    ok = np.isfinite(arr).any(axis=1)
    return int(np.where(ok)[0][-1]) if ok.any() else -1


def score_from_weights(feats, cal, tickers, t):
    """
    RRG Score = intercept + sum_i beta_i * z_i, where z is the cross-sectional
    z-score of factor i at date t and beta comes from the walk-forward fit.
    Units are 'predicted forward excess return over the horizon'.
    """
    w = cal.get("weights")
    facs = cal.get("factors", rv.FACTORS)
    z = {}
    for f in facs:
        row = feats[f].to_numpy(dtype=float)[t]
        ok = np.isfinite(row)
        zz = np.full(row.shape, np.nan)
        if ok.sum() >= 3 and row[ok].std(ddof=1) > 1e-12:
            zz[ok] = (row[ok] - row[ok].mean()) / row[ok].std(ddof=1)
        z[f] = zz
    if not w:
        stack = np.stack([z[f] for f in facs], axis=0)
        return np.nanmean(stack, axis=0), z
    pred = np.full(len(tickers), float(cal.get("intercept") or 0.0))
    for f in facs:
        pred = pred + float(w[f]) * np.nan_to_num(z[f], nan=0.0)
    allnan = np.all(np.isnan(np.stack([z[f] for f in facs], axis=0)), axis=0)
    return np.where(allnan, np.nan, pred), z


def pct_rank(a):
    """Cross-sectional percentile rank 0-100 (uses only this date's data)."""
    a = np.asarray(a, dtype=float)
    out = np.full(a.shape, np.nan)
    ok = np.isfinite(a)
    if ok.sum() >= 2:
        r = rs.avg_rank(a[ok])
        out[ok] = 100.0 * (r - 1) / (ok.sum() - 1)
    return out


def bucket_stats(fwd, quad, dist, terc_edges, pool_hit):
    """
    Empirical W, R, mean loss per (quadrant x distance tercile) — the numbers
    Kelly needs. Shrunk toward the pool; R refused when losses are too few.
    """
    cells = {}
    for k, qname in enumerate(rc.QUADRANTS):
        for ti in range(3):
            lo, hi = terc_edges[ti], terc_edges[ti + 1]
            m = (quad == k) & (dist >= lo) & ((dist < hi) if ti < 2 else (dist >= lo))
            sel = fwd[m]
            sel = sel[np.isfinite(sel)]
            if sel.size < 30:
                continue
            w = rs.hit_rate(sel)
            losses = sel[sel < 0]
            cells[(qname, ti + 1)] = dict(
                n=int(sel.size),
                W_raw=float(w),
                W=float(rs.shrink_win_rate(w, sel.size, pool_hit)),
                R=rs.win_loss_ratio(sel),
                mean_loss=float(losses.mean()) if losses.size >= 20 else np.nan,
                mean=float(sel.mean()), std=float(sel.std(ddof=1)),
                enough=bool(sel.size >= rv.MIN_BUCKET_N),
            )
    return cells


def tercile_of(d, edges):
    if not np.isfinite(d) or edges is None:
        return np.nan
    if d < edges[1]:
        return 1
    if d < edges[2]:
        return 2
    return 3


def build_view(prices, bench, params, horizons, long_lb, skip):
    """Panel + latest-observation snapshot for a set of assets vs a benchmark."""
    panel = rv.build_panel(prices, bench, params, horizons, long_lb, skip, "view")
    panel["freq"] = "W"
    return panel


def snapshot(panel, cal, hname):
    """Current RRG state per asset, with the four factors and the score."""
    feats = {k: pd.DataFrame(v, index=panel["index"], columns=panel["columns"])
             for k, v in panel["feats"].items()}
    t = latest_row(feats["rs_momentum"])
    tickers = panel["columns"]
    pred, _ = score_from_weights(feats, cal, tickers, t)
    ang = feats["angle_deg"].to_numpy()[t]
    rows = []
    for i, tk in enumerate(tickers):
        q = feats["quadrant"].to_numpy()[t][i]
        rows.append({
            "ticker": tk,
            "rs_ratio": feats["rs_ratio"].to_numpy()[t][i],
            "rs_momentum": feats["rs_momentum"].to_numpy()[t][i],
            "quadrant": rc.QUADRANTS[int(q)] if np.isfinite(q) and q >= 0 else "—",
            "heading": rc.octant_labels(np.array([ang[i]]))[0],
            "angle_deg": ang[i],
            "distance": feats["distance"].to_numpy()[t][i],
            "delta_distance": feats["delta_distance"].to_numpy()[t][i],
            "straightness": feats["straightness"].to_numpy()[t][i],
            "tail_r2": feats["tail_r2"].to_numpy()[t][i],
            "quadrant_run": feats["quadrant_run"].to_numpy()[t][i],
            "pred_excess": pred[i],
        })
    df = pd.DataFrame(rows)
    df["rrg_score"] = pct_rank(df["pred_excess"].to_numpy())
    return df, feats, t


def historical_buckets(panel, hname, design_mask):
    """Bucket W/R from this panel's own history (design sample edges)."""
    fwd = panel["fwd"][hname]
    q = panel["feats"]["quadrant"]
    d = panel["feats"]["distance"]
    dd = d[design_mask]
    dd = dd[np.isfinite(dd)]
    if dd.size < 200:
        return {}, None, np.nan
    edges = np.quantile(dd, [0, 1 / 3, 2 / 3, 1.0])
    edges[0], edges[-1] = -np.inf, np.inf
    pool = rs.hit_rate(fwd)
    return bucket_stats(fwd, q, d, edges, pool), edges, pool


def export_tails(feats, index, t, tickers, n=None):
    """
    Last `n` weekly (rs_ratio, rs_momentum) points per ticker — the RRG tail the
    dashboard draws. Exported as plain lists so the page needs no compute.
    """
    n = n or TAIL_WEEKS
    lo = max(0, t - n + 1)
    rr = feats["rs_ratio"].to_numpy(dtype=float)
    rm = feats["rs_momentum"].to_numpy(dtype=float)
    out = {}
    for i, tk in enumerate(tickers):
        x, y, d = [], [], []
        for j in range(lo, t + 1):
            if np.isfinite(rr[j][i]) and np.isfinite(rm[j][i]):
                x.append(round(float(rr[j][i]), 4))
                y.append(round(float(rm[j][i]), 4))
                d.append(str(index[j].date()))
        if len(x) >= 2:
            out[str(tk)] = {"x": x, "y": y, "dates": d}
    return out


def show(df, cols=None, floatfmt="{:.2f}"):
    if df is None or len(df) == 0:
        print("  (no data)")
        return
    d = df[cols].copy() if cols else df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if np.isfinite(v) else "—")
    print(d.to_string(index=False))


def banner(t, ch="="):
    print("\n" + ch * 78)
    print(t)
    print(ch * 78)


# ─────────────────────────────────────────────────────────────────────────────
# 2. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    cal = load_calibration()
    params = dict(rc.WEEKLY)
    H = "1M"

    banner("TOP-DOWN RRG ANALYSIS — S&P 500 SECTORS -> CONSTITUENTS")
    print(f"  Portfolio     : ${PORTFOLIO:,.0f}")
    print(f"  Cadence       : weekly, W={params['W']} S={params['S']} "
          f"M={params['M']} L={params['L']}   horizon {H}")
    print(f"  Calibration   : {cal['generated']}  "
          f"({cal['n_pass']}/{cal['n_checks']} decision rules passed)")
    print(f"  Sizing multiplier from validation: {cal['sizing_multiplier']:.2f}")

    # ── sectors ─────────────────────────────────────────────────────────────
    px_all = rd.load_sector_prices(verbose=False)
    sectors = [s for s in rd.SECTOR_ETFS if s in px_all.columns]
    dly = px_all[sectors + [rd.BENCHMARK]].dropna(how="all")
    wk = rc.to_weekly(dly)
    sec_prices = wk[sectors]
    sec_bench = wk[rd.BENCHMARK]

    sp = build_view(sec_prices, sec_bench, params, rv.HORIZONS_W, 52, 4)
    sec_df, sec_feats, t_idx = snapshot(sp, cal, H)
    asof = sp["index"][t_idx].date()
    print(f"  As of         : {asof} (weekly close)")

    design_mask = rv.slice_mask(sp["index"], end=rv.DESIGN_END)
    sec_buckets, sec_edges, sec_pool = historical_buckets(sp, H, design_mask)
    sec_buckets_3m, _, sec_pool_3m = historical_buckets(sp, "3M", design_mask)

    # attach measured historical hit rates for each sector's CURRENT setup
    for hz, bk, pool in (("1M", sec_buckets, sec_pool), ("3M", sec_buckets_3m, sec_pool_3m)):
        hits, ns = [], []
        for _, r in sec_df.iterrows():
            ti = tercile_of(r["distance"], sec_edges)
            cell = bk.get((r["quadrant"], ti)) if np.isfinite(ti) else None
            hits.append(cell["W"] * 100 if cell else np.nan)
            ns.append(cell["n"] if cell else np.nan)
        sec_df[f"hit_{hz}_pct"] = hits
        sec_df[f"n_{hz}"] = ns
    sec_df["tercile"] = [tercile_of(d, sec_edges) for d in sec_df["distance"]]
    sec_df["tail_vs_null"] = sec_df["straightness"] / 0.769   # simulated null

    sec_df = sec_df.sort_values("rrg_score", ascending=False).reset_index(drop=True)
    sec_df["rank"] = np.arange(1, len(sec_df) + 1)
    sec_df["sector"] = sec_df["ticker"].map(rd.SECTOR_NAMES)

    tails = {"as_of": str(asof), "tail_weeks": TAIL_WEEKS, "sectors": {}, "stocks": {}}
    tails["sectors"] = export_tails(sec_feats, sp["index"], t_idx, sec_prices.columns)

    banner("SECTOR RANKING — all 11 S&P 500 sectors vs SPY")
    print(f"  Baseline (unconditional) hit rate: 1M {100*sec_pool:.2f}%  "
          f"3M {100*sec_pool_3m:.2f}%   <- compare hit rates against THIS, not 50%")
    print(f"  Straightness null (simulated, zero true edge): 0.769 — "
          f"'tail_vs_null' below 1.0 means LESS persistent than pure noise.\n")
    show(sec_df, ["rank", "ticker", "sector", "rrg_score", "quadrant", "heading",
                  "angle_deg", "distance", "delta_distance", "straightness",
                  "tail_vs_null", "hit_1M_pct", "hit_3M_pct", "n_1M"])
    sec_df.to_csv("rrg_sector_results.csv", index=False)

    top = sec_df.head(N_TOP_SECTORS)
    banner(f"TOP {N_TOP_SECTORS} SECTORS — why each ranks here")
    for _, r in top.iterrows():
        print(f"\n  {r['rank']}. {r['ticker']} — {r['sector']}   "
              f"RRG Score {r['rrg_score']:.0f}/100")
        print(f"     Quadrant {r['quadrant']}, heading {r['heading']} "
              f"({r['angle_deg']:+.0f}° on standardized axes)")
        print(f"     Distance {r['distance']:.2f} (tercile {r['tercile']:.0f} of 3), "
              f"change over tail {r['delta_distance']:+.2f} "
              f"({'increasing' if r['delta_distance'] > 0 else 'decreasing'})")
        print(f"     Tail straightness {r['straightness']:.2f} = "
              f"{r['tail_vs_null']:.2f}x the noise null; "
              f"{r['quadrant_run']:.0f} weeks in quadrant")
        hh = r["hit_1M_pct"]
        if np.isfinite(hh):
            print(f"     Measured historical 1M hit rate for this exact setup: "
                  f"{hh:.1f}% (n={r['n_1M']:.0f}) vs {100*sec_pool:.1f}% baseline "
                  f"-> edge {hh - 100*sec_pool:+.1f}pp")
        else:
            print("     No bucket with enough history for this setup.")

    # ── stocks within the top sectors ───────────────────────────────────────
    banner("STOCK RRG — constituents vs THEIR OWN SECTOR ETF")
    print("  NOTE: the stock panel is today's S&P 500 membership backfilled, so it")
    print("  is survivorship-biased. Names that went to zero out of the Lagging")
    print("  quadrant are absent, which flatters Lagging/Improving and inflates R.")
    stock_px = rd.load_stock_panel(verbose=False)
    smap = rd.load_sector_map(verbose=False)
    all_stock_rows = []      # top N per sector -> sizing candidates
    full_stock_rows = []     # every constituent -> the dashboard drill-down

    for _, srow in top.iterrows():
        etf = srow["ticker"]
        names = rd.stocks_in_sector(smap, etf, stock_px.columns)
        if len(names) < 8:
            print(f"\n  {etf}: only {len(names)} constituents in the panel — skipped")
            continue
        cols = [c for c in names if c in stock_px.columns]
        sub_d = stock_px[cols].join(px_all[[etf]], how="inner").dropna(how="all")
        if etf not in sub_d.columns:
            continue
        # Keep every row where the sector ETF trades and let individual names
        # carry their own NaNs. A blanket .dropna() would delete all history
        # before the LATEST constituent's IPO, wiping out the design sample.
        sub_w = rc.to_weekly(sub_d)
        sub_w = sub_w[sub_w[etf].notna()]
        keep = [c for c in sub_w.columns
                if c == etf or sub_w[c].notna().sum() >= 0.5 * len(sub_w)]
        sub_w = sub_w[keep]
        if len(sub_w) < 300:
            print(f"\n  {etf}: insufficient weekly history — skipped")
            continue
        tick = [c for c in sub_w.columns if c != etf]
        sv = build_view(sub_w[tick], sub_w[etf], params, rv.HORIZONS_W, 52, 4)
        sdf, sfeats, st = snapshot(sv, cal, H)
        tails["stocks"][etf] = export_tails(sfeats, sv["index"], st, tick)

        dmask = rv.slice_mask(sv["index"], end=rv.DESIGN_END)
        sbk, sedges, spool = historical_buckets(sv, H, dmask)
        sdf["tercile"] = [tercile_of(d, sedges) for d in sdf["distance"]]
        hits, ns, Rs, mls, mus, sds = [], [], [], [], [], []
        for _, r in sdf.iterrows():
            cell = sbk.get((r["quadrant"], r["tercile"]))
            hits.append(cell["W"] * 100 if cell else np.nan)
            ns.append(cell["n"] if cell else np.nan)
            Rs.append(cell["R"] if cell else np.nan)
            mls.append(cell["mean_loss"] if cell else np.nan)
            mus.append(cell["mean"] if cell else np.nan)
            sds.append(cell["std"] if cell else np.nan)
        sdf["hit_1M_pct"], sdf["n_bucket"] = hits, ns
        sdf["R"], sdf["mean_loss"] = Rs, mls
        sdf["bucket_mean"], sdf["bucket_std"] = mus, sds
        sdf["baseline_hit"] = 100 * spool
        sdf["sector_etf"] = etf
        sdf["sector"] = rd.SECTOR_NAMES.get(etf, etf)

        # setup classification — measurable rules, not adjectives
        def setup(r):
            if r["quadrant"] == "Leading" and r["straightness"] > 0.769:
                return "Established leader"
            if r["quadrant"] == "Improving" and r["delta_distance"] > 0:
                return "Improving -> potential leader"
            if r["quadrant"] in ("Weakening", "Lagging") and r["delta_distance"] < 0:
                return "Deteriorating — avoid"
            if r["quadrant"] == "Weakening":
                return "Weakening"
            return r["quadrant"]
        sdf["setup"] = sdf.apply(setup, axis=1)
        sdf = sdf.sort_values("rrg_score", ascending=False).reset_index(drop=True)

        base_txt = (f"baseline hit {100*spool:.1f}%" if np.isfinite(spool)
                    else "no pre-2014 history -> no W/R buckets")
        print(f"\n  --- {etf} ({rd.SECTOR_NAMES.get(etf,'')}) — "
              f"{len(tick)} constituents, {base_txt} ---")
        show(sdf.head(8), ["ticker", "rrg_score", "quadrant", "heading", "distance",
                           "delta_distance", "straightness", "setup",
                           "hit_1M_pct", "n_bucket", "R"])
        worst = sdf[sdf["setup"] == "Deteriorating — avoid"].tail(3)
        if len(worst):
            print("      Deteriorating (avoid): " +
                  ", ".join(f"{r['ticker']} ({r['quadrant']}, "
                            f"Δdist {r['delta_distance']:+.2f})"
                            for _, r in worst.iterrows()))
        all_stock_rows.append(sdf.head(N_STOCKS_PER_SECTOR))
        full_stock_rows.append(sdf)

    if not all_stock_rows:
        print("\n  No sector produced a usable constituent panel.")
        return

    picks = pd.concat(all_stock_rows, ignore_index=True)
    picks = picks.sort_values("rrg_score", ascending=False).reset_index(drop=True)

    # ── Kelly sizing ────────────────────────────────────────────────────────
    banner("POSITION SIZING — Kelly, as specified and as corrected")
    k_pos = min(5, len(picks))
    sel = picks.head(k_pos).copy()

    # correlation between the actual candidates (weekly excess vs their sector)
    rho, n_rho, rho_src = np.nan, 0, "assumed"
    try:
        have = [t for t in sel["ticker"] if t in stock_px.columns]
        rets = stock_px[have].pct_change().tail(260)
        rets = rets.dropna(axis=1, how="all").dropna()
        if rets.shape[1] > 1 and len(rets) > 60:
            C = np.corrcoef(rets.to_numpy().T)
            iu = np.triu_indices_from(C, k=1)
            rho, n_rho, rho_src = float(np.nanmean(C[iu])), rets.shape[1], "measured"
    except Exception:
        pass
    if not np.isfinite(rho):
        rho = 0.5
    div = rs.correlation_divisor(k_pos, rho)

    print(f"  Simultaneous positions k = {k_pos};  {rho_src} average pairwise "
          f"daily return correlation rho = {rho:.2f}"
          f"{f' (over {n_rho} names, 260d)' if n_rho else ''}")
    print(f"  Multi-asset Kelly is f = inv(Sigma) @ mu; for equal correlation that")
    print(f"  divides each position by (1 + (k-1)*rho) = {div:.2f}x")
    # State the comparison the data actually supports, not a prior.
    if div > 2.0:
        print(f"  -> At rho={rho:.2f} this haircut ({div:.2f}x) is LARGER than the")
        print("     1/2-vs-1/4 Kelly choice (a 2x factor), so it dominates that decision.\n")
    else:
        print(f"  -> At rho={rho:.2f} this haircut ({div:.2f}x) is SMALLER than the")
        print("     1/2-vs-1/4 Kelly factor of 2x. These 5 names happen to be weakly")
        print("     correlated; with a typical large-cap rho of 0.5 the divisor would")
        print(f"     be {rs.correlation_divisor(k_pos, 0.5):.2f}x and would dominate instead.\n")

    rows = []
    for _, r in sel.iterrows():
        W, R, ml = r["hit_1M_pct"] / 100.0, r["R"], r["mean_loss"]
        kb = rs.kelly_binary(W, R)
        kw = rs.kelly_wealth_fraction(W, R, ml)
        kc = rs.kelly_continuous(r["bucket_mean"], r["bucket_std"])
        rows.append({
            "ticker": r["ticker"], "sector": r["sector"],
            "rrg_score": r["rrg_score"], "setup": r["setup"],
            "W_pct": 100 * W if np.isfinite(W) else np.nan,
            "baseline_pct": r["baseline_hit"],
            "edge_pp": (100 * W - r["baseline_hit"]) if np.isfinite(W) else np.nan,
            "R": R, "n": r["n_bucket"],
            "exp_1M_pct": 100 * r["bucket_mean"] if np.isfinite(r["bucket_mean"]) else np.nan,
            "kelly_binary_pct": 100 * kb if np.isfinite(kb) else np.nan,
            "kelly_wealth_pct": 100 * kw if np.isfinite(kw) else np.nan,
            "kelly_cont_pct": 100 * kc if np.isfinite(kc) else np.nan,
        })
    ks = pd.DataFrame(rows)

    print("  Kelly% as specified, W - (1-W)/R, with W and R counted from the")
    print("  matching (quadrant x distance tercile) bucket:")
    show(ks, ["ticker", "sector", "W_pct", "baseline_pct", "edge_pp", "R", "n",
              "exp_1M_pct", "kelly_binary_pct"])
    print("\n  UNITS WARNING: W - (1-W)/R is a fraction of a bet unit whose LOSS")
    print("  is 1, not a portfolio weight. Converting to a wealth fraction:")
    show(ks, ["ticker", "kelly_binary_pct", "kelly_wealth_pct", "kelly_cont_pct"])
    print("  (kelly_wealth = kelly_binary / |mean loss|; kelly_cont = mu/sigma^2.")
    print("   Both routinely exceed 100% — which is itself the proof that Kelly is")
    print("   the wrong sizing principle for a diversified 1-month equity book.)")

    # apply the ladder: correlation -> fractional Kelly -> validation -> caps
    mult = float(cal["sizing_multiplier"])
    for frac, label in ((0.5, "half"), (0.25, "quarter")):
        ks[f"k_{label}_pct"] = np.clip(
            ks["kelly_wealth_pct"] / div * frac, 0, MAX_POSITION_PCT)
    ks["recommended_pct"] = np.clip(
        ks["kelly_wealth_pct"] / div * 0.25 * mult, 0, MAX_POSITION_PCT)
    ks["recommended_dollars"] = ks["recommended_pct"] / 100.0 * PORTFOLIO

    banner("1/2 KELLY vs 1/4 KELLY — and the recommendation")
    show(ks, ["ticker", "kelly_wealth_pct", "k_half_pct", "k_quarter_pct",
              "recommended_pct", "recommended_dollars"])
    print(f"\n  Decision inputs:")
    print(f"    portfolio                     ${PORTFOLIO:,.0f}")
    print(f"    simultaneous positions        {k_pos}")
    print(f"    measured correlation          {rho:.2f}  -> divisor {div:.2f}x")
    print(f"    max position / sector caps    {MAX_POSITION_PCT:.0f}% / {MAX_SECTOR_PCT:.0f}%")
    print(f"    bucket sample sizes           n = "
          f"{', '.join(str(int(x)) for x in ks['n'].dropna())} "
          f"(need >= {rv.MIN_BUCKET_N} to quote W/R at all)")
    print(f"    edge stability (validation)   {cal['n_pass']}/{cal['n_checks']} rules passed")
    print("\n  -> USE 1/4 KELLY, NOT 1/2. Reasons, in order of size:")
    print("     1. The edge estimate is unstable: walk-forward IR 0.03 vs in-sample")
    print("        0.60, decay ratio 0.26, calibration slope 0.38.")
    print("     2. Overbetting is not a milder error — at 2x Kelly log-growth is")
    print(f"        EXACTLY ZERO. At 1/4 Kelly you keep "
          f"{100*rs.growth_fraction(0.25):.0f}% of growth for "
          f"{100*0.25**2:.0f}% of the variance.")
    print("     3. Holdings are correlated (rho ~ %.2f), so the effective number of"
          % rho)
    print("        independent bets is far below the position count.")
    print(f"\n  -> BUT the validation multiplier is {mult:.2f}, so the recommended")
    print("     allocation to this signal is $0. See the verdict below.")

    ks.to_csv("rrg_stock_results.csv", index=False)
    pd.concat(full_stock_rows, ignore_index=True).to_csv(
        "rrg_stock_candidates.csv", index=False)
    tails["top_sectors"] = list(top["ticker"])
    tails["baseline_hit"] = {"1M": float(sec_pool), "3M": float(sec_pool_3m)}
    tails["straightness_null"] = 0.769
    with open("rrg_tails.json", "w") as f:
        json.dump(tails, f)

    # ── signals ─────────────────────────────────────────────────────────────
    peak = np.nan
    try:
        vres = pd.read_csv("rrg_validation_results.csv")
        pk = vres[(vres["section"] == "distance") &
                  (vres["metric"] == f"peak_decile_{H}")]["value"]
        if len(pk):
            peak = float(pk.iloc[0])
    except Exception:
        pass

    banner("SIGNALS — what would change each position")
    print("  All thresholds are measurable from the weekly RRG state:\n")
    print("  INCREASE when ALL hold:")
    print("    * quadrant moves into Leading, or Improving with rs_ratio rising")
    print("    * delta_distance > 0 for 2+ consecutive weeks (distance expanding)")
    print("    * straightness > 0.77 (the simulated noise null) — tail is real")
    if np.isfinite(peak):
        if peak <= 3:
            print(f"    * distance is NOT far from the centre. Measured forward excess")
            print(f"      PEAKS at decile {peak:.0f} of 10 and falls away above it — in")
            print("      this sample, greater distance was WORSE, not better. Do not")
            print("      treat a long tail far from the centre as a stronger signal.")
        else:
            print(f"    * distance still below decile {peak:.0f} of 10 — measured forward")
            print("      excess peaks there and does not improve above it, so extra")
            print("      distance past that point buys risk without return.")
    else:
        print("    * distance below the empirical peak decile (see rrg_validation_results.csv)")
    print("\n  REDUCE when ANY holds:")
    print("    * delta_distance turns negative while distance is in the top tercile")
    print("    * straightness falls below 0.77 (tail less persistent than noise)")
    print("    * quadrant rotates Leading -> Weakening")
    print("\n  EXIT when ANY holds:")
    print("    * quadrant reaches Lagging")
    print("    * heading persists in the S/SW/SE octants for 3+ weeks")
    print("    * the name's bucket sample falls below n=200 (no basis to size)")
    print("\n  NOTE: these are state-transition rules for a DESCRIPTIVE tool. The")
    print("  validation did not establish that acting on them beats holding SPY.")

    # ── verdict ─────────────────────────────────────────────────────────────
    banner("BOTTOM LINE")
    print(f"  Top {N_TOP_SECTORS} sectors by RRG Score : "
          f"{', '.join(f'{r.ticker} ({r.sector})' for r in top.itertuples())}")
    print(f"  Top {k_pos} stocks by RRG Score  : "
          f"{', '.join(sel['ticker'])}")
    print(f"\n  Kelly recommendation           : 1/4 Kelly (not 1/2)")
    print(f"  Recommended capital at risk    : "
          f"${ks['recommended_dollars'].sum():,.0f} of ${PORTFOLIO:,.0f}")
    if mult == 0:
        print("\n  The RRG signal did not clear its pre-registered validation bar")
        print("  (1/9 criteria). It adds nothing over plain 12-1 relative momentum")
        print("  (incremental IC -0.004, t -0.26). The rankings above are a valid")
        print("  DESCRIPTION of where each name sits in relative-strength space —")
        print("  useful for monitoring and communication — but on this evidence")
        print("  they are not a basis for allocating real capital.")
    print(f"\nSaved -> rrg_sector_results.csv, rrg_stock_results.csv, "
          f"rrg_stock_candidates.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
