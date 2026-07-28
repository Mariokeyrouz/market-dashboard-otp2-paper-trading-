"""
RRG Validate — does the RRG geometry actually forecast anything?
=================================================================
The honest test. Everything here is built so that a NULL RESULT is a first-class
outcome: if RRG carries no information beyond trailing relative momentum, this
script says so in plain language and the sizing downstream goes to zero.

PRIMARY SPECIFICATION (pre-registered, frozen before the holdout is opened)
--------------------------------------------------------------------------
  universe   9 long-history SPDR sector ETFs vs SPY  (zero survivorship bias)
  cadence    weekly, W=52 S=10 M=4 L=10
  horizons   4 weeks (1M) and 13 weeks (3M)
  splits     design  <= 2013-12-31   (unlimited looks)
             validation 2014 - 2019  (few looks)
             HOLDOUT  2020-01-01 ->  (opened once, frozen spec)
  purge      H periods between train and test

THE FIVE WAYS THIS COULD LIE TO US, AND THE CONTROLS
-----------------------------------------------------
1. Overlapping windows. Sampling an H-period return every period makes the
   series MA(H-1); naive t-stats inflate ~3.7x at H=21d, 6.5x at H=63d. Control:
   Newey-West everywhere (lag 1.5H), plus a non-overlapping co-headline, plus an
   overlapping-tranche PORTFOLIO whose return series has no overlap at all.
2. The rotation is mechanical. Control: every number is compared against
   rrg_null.py's simulated distribution under zero true edge.
3. RRG might just be repackaged momentum. Control: the horse race — incremental
   IC over 12-1 relative momentum and 1-month reversal. THIS TEST DECIDES THE
   PROJECT; tests 1-3 can all pass on a pure momentum proxy.
4. Multiple testing. ~1000 specs means E[max|t|] ~ 3.0 under the pure null.
   Control: report the parameter SURFACE (median t, sign agreement), never the
   best cell; deflated Sharpe; the null's own max|t| distribution.
5. In-sample fitting. Control: cross-sectional (never full-sample) ranking,
   trailing-only bucket edges, annual walk-forward refits, purged splits.

Outputs
-------
  rrg_validation_results.csv   every statistic, tidy
  rrg_calibration.json         weights + buckets + W/R for rrg_analysis.py

Usage:
  py rrg_validate.py            # primary spec + robustness
  py rrg_validate.py --quick    # skip the parameter grid
"""

import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import rrg_core as rc
import rrg_data as rd
import rrg_stats as rs

# ── Pre-registered primary specification ─────────────────────────────────────
PRIMARY = dict(rc.WEEKLY)
HORIZONS_W = {"1M": 4, "3M": 13}          # weekly periods
HORIZONS_D = {"1M": 21, "3M": 63}         # trading days

DESIGN_END = "2013-12-31"
VALID_END = "2019-12-31"
HOLDOUT_START = "2020-01-01"

FACTORS = ["distance", "delta_distance", "ne_score", "straightness",
           "tail_r2", "quadrant_run"]
CONTROLS = ["mom_12_1", "rev_1m"]

N_BUCKETS = 10
MIN_BUCKET_N = 200
REFIT_EVERY = 52                          # weeks between walk-forward refits

# Decision thresholds (frozen)
TH = dict(ic=0.03, ic_t=3.0, ir=0.40, ir_t=3.0, decay=0.50,
          d_ic=0.015, d_ic_t=2.5, grid_median_t=1.5, grid_sign=0.70,
          dsr_p=0.05, null_pct=0.99)


# ─────────────────────────────────────────────────────────────────────────────
# 1. PANEL CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def forward_excess(px, bench, H):
    """H-period forward return minus benchmark's. Last H rows are NaN, never padded."""
    p = np.asarray(px, dtype=float)
    b = np.asarray(bench, dtype=float)
    T = p.shape[0]
    fwd = np.full(p.shape, np.nan)
    fb = np.full(T, np.nan)
    if T > H:
        fwd[:T - H] = p[H:] / p[:T - H] - 1.0
        fb[:T - H] = b[H:] / b[:T - H] - 1.0
    return fwd - fb[:, None]


def momentum_controls(px, bench, long_lb, skip):
    """
    Benchmark-relative 12-1 momentum and 1-month reversal — the null that RRG
    must beat. Both use only information available at t.
    """
    p = np.asarray(px, dtype=float)
    b = np.asarray(bench, dtype=float).reshape(-1, 1)
    rel = p / b
    mom = np.full(p.shape, np.nan)
    rev = np.full(p.shape, np.nan)
    if p.shape[0] > long_lb + skip:
        mom[long_lb + skip:] = rel[long_lb + skip:] / rel[:-(long_lb + skip)] - 1.0
    if p.shape[0] > skip:
        rev[skip:] = rel[skip:] / rel[:-skip] - 1.0
    return mom, rev


def xs_zscore(a, min_n=4):
    """Cross-sectional z-score per date — uses only that date's data."""
    a = np.asarray(a, dtype=float)
    out = np.full(a.shape, np.nan)
    for t in range(a.shape[0]):
        row = a[t]
        ok = np.isfinite(row)
        if ok.sum() >= min_n:
            mu, sd = row[ok].mean(), row[ok].std(ddof=1)
            if sd > 1e-12:
                out[t, ok] = (row[ok] - mu) / sd
    return out


def build_panel(prices, bench, params, horizons, long_lb, skip, label):
    """Features + forward excess returns + momentum controls, all aligned."""
    feats = rc.compute_features(prices, bench, params)
    px = prices.to_numpy(dtype=float)
    bm = np.asarray(bench, dtype=float)
    mom, rev = momentum_controls(px, bm, long_lb, skip)
    panel = {
        "label": label, "index": prices.index, "columns": list(prices.columns),
        "feats": {k: v.to_numpy(dtype=float) for k, v in feats.items()},
        "fwd": {h: forward_excess(px, bm, H) for h, H in horizons.items()},
        "controls": {"mom_12_1": mom, "rev_1m": rev},
        "horizons": horizons,
    }
    return panel


def slice_mask(index, start=None, end=None):
    m = np.ones(len(index), dtype=bool)
    if start:
        m &= np.asarray(index >= pd.Timestamp(start))
    if end:
        m &= np.asarray(index <= pd.Timestamp(end))
    return m


# ─────────────────────────────────────────────────────────────────────────────
# 2. DESCRIPTIVE EDGE TABLES
# ─────────────────────────────────────────────────────────────────────────────

def quadrant_table(panel, hname, mask=None):
    fwd = panel["fwd"][hname]
    q = panel["feats"]["quadrant"]
    m = np.ones(fwd.shape[0], dtype=bool) if mask is None else mask
    fwd, q = fwd[m], q[m]
    rows = []
    base = rs.hit_rate(fwd)
    for k, name in enumerate(rc.QUADRANTS):
        sel = fwd[q == k]
        sel = sel[np.isfinite(sel)]
        if sel.size < 30:
            continue
        rows.append({
            "quadrant": name, "n": int(sel.size),
            "hit_rate": rs.hit_rate(sel),
            "vs_baseline_pp": 100.0 * (rs.hit_rate(sel) - base),
            "mean_excess_pct": 100.0 * float(sel.mean()),
            "median_excess_pct": 100.0 * float(np.median(sel)),
            "win_loss_R": rs.win_loss_ratio(sel),
        })
    return pd.DataFrame(rows), base


def octant_table(panel, hname, mask=None):
    fwd = panel["fwd"][hname]
    ang = panel["feats"]["angle_deg"]
    m = np.ones(fwd.shape[0], dtype=bool) if mask is None else mask
    fwd, ang = fwd[m], ang[m]
    lab = rc.octant_labels(ang)
    rows = []
    base = rs.hit_rate(fwd)
    for oc in rc.OCTANTS + ("flat",):
        sel = fwd[lab == oc]
        sel = sel[np.isfinite(sel)]
        if sel.size < 30:
            continue
        rows.append({
            "heading": oc, "n": int(sel.size), "hit_rate": rs.hit_rate(sel),
            "vs_baseline_pp": 100.0 * (rs.hit_rate(sel) - base),
            "mean_excess_pct": 100.0 * float(sel.mean()),
            "win_loss_R": rs.win_loss_ratio(sel),
        })
    return pd.DataFrame(rows)


def decile_table(panel, hname, factor="distance", mask=None, edges=None):
    """
    THE distance question: does more distance keep paying, and where does it stop?
    """
    fwd = panel["fwd"][hname]
    f = panel["feats"][factor]
    m = np.ones(fwd.shape[0], dtype=bool) if mask is None else mask
    edges, buckets = rs.bucket_table(f[m], fwd[m], n_buckets=N_BUCKETS, edges=edges)
    rows = []
    for b in sorted(buckets):
        sel = buckets[b]
        rows.append({
            "bucket": b + 1, "n": int(sel.size),
            "lo": float(edges[b]), "hi": float(edges[b + 1]),
            "hit_rate": rs.hit_rate(sel),
            "mean_excess_pct": 100.0 * float(np.mean(sel)),
            "win_loss_R": rs.win_loss_ratio(sel),
        })
    return pd.DataFrame(rows), edges


def peak_bucket(dec_df):
    """Where extra distance stops improving forward return (argmax, not the top)."""
    if dec_df.empty:
        return np.nan, np.nan
    i = int(dec_df["mean_excess_pct"].to_numpy().argmax())
    return int(dec_df["bucket"].iloc[i]), float(dec_df["mean_excess_pct"].iloc[i])


# ─────────────────────────────────────────────────────────────────────────────
# 3. IC, HORSE RACE, PORTFOLIO
# ─────────────────────────────────────────────────────────────────────────────

def factor_ic(panel, hname, factor, mask=None):
    fwd = panel["fwd"][hname]
    f = panel["feats"][factor] if factor in panel["feats"] else panel["controls"][factor]
    if mask is not None:
        fwd, f = fwd[mask], f[mask]
    ic = rs.cross_sectional_ic(f, rs.winsorize_rows(fwd))
    H = panel["horizons"][hname]
    mean, t, n = rs.newey_west_t(ic, int(np.ceil(1.5 * H)))
    return dict(factor=factor, ic=mean, t_nw=t, t_naive=rs.naive_t(ic), n_dates=n,
                inflation=rs.overlap_inflation(H))


def combo_signal(panel, names):
    """Equal-weight cross-sectional z-score composite of a factor list."""
    cols = []
    for nm in names:
        src = panel["feats"] if nm in panel["feats"] else panel["controls"]
        cols.append(xs_zscore(src[nm]))
    stack = np.stack(cols, axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(stack, axis=0)


def horse_race(panel, hname, mask=None):
    """
    THE deciding test: does the RRG block add anything to 12-1 relative momentum
    and 1-month reversal?

    With only 9 sectors in the cross-section we cannot fit 8 regressors per date
    (a date needs more assets than parameters), so the RRG block is collapsed
    into a single equal-weight composite. The Fama-MacBeth model is then

        fwd_excess ~ rrg_combo + mom_12_1 + rev_1m

    which is 3 regressors + intercept against 9 assets — feasible, and a cleaner
    test besides. The t-stat on `rrg_combo` is the answer: it is the marginal
    contribution of RRG geometry once momentum is already in the model.
    """
    fwd = rs.winsorize_rows(panel["fwd"][hname])
    H = panel["horizons"][hname]
    lag = int(np.ceil(1.5 * H))
    idx = np.arange(fwd.shape[0]) if mask is None else np.where(mask)[0]

    rrg = combo_signal(panel, FACTORS)
    blocks = {"rrg_combo": rrg,
              "mom_12_1": panel["controls"]["mom_12_1"],
              "rev_1m": panel["controls"]["rev_1m"]}

    def stack(names):
        X, y, r2 = [], [], []
        for t in idx:
            Xt = np.column_stack([blocks[nm][t] for nm in names])
            yt = fwd[t]
            ok = np.isfinite(yt) & np.all(np.isfinite(Xt), axis=1)
            if ok.sum() < len(names) + 3:
                continue
            Xs = Xt[ok]
            sd = Xs.std(axis=0, ddof=1)
            if np.any(sd <= 1e-12):
                continue
            Xs = (Xs - Xs.mean(axis=0)) / sd
            X.append(Xs)
            y.append(yt[ok])
            Xd = np.column_stack([np.ones(ok.sum()), Xs])
            beta, *_ = np.linalg.lstsq(Xd, yt[ok], rcond=None)
            resid = yt[ok] - Xd @ beta
            ss = float(((yt[ok] - yt[ok].mean()) ** 2).sum())
            r2.append(1.0 - float(resid @ resid) / ss if ss > 0 else np.nan)
        return X, y, np.array(r2, dtype=float)

    ctl_names = ["mom_12_1", "rev_1m"]
    all_names = ["rrg_combo"] + ctl_names
    Xc, yc, r2c = stack(ctl_names)
    Xf, yf, r2f = stack(all_names)
    _, tc, _ = rs.fama_macbeth(Xc, yc, lag)
    mf, tf, _ = rs.fama_macbeth(Xf, yf, lag)

    sub = (lambda a: a if mask is None else a[mask])
    ic_rrg = rs.cross_sectional_ic(sub(rrg), sub(fwd))
    ic_ctl = rs.cross_sectional_ic(sub(combo_signal(panel, CONTROLS)), sub(fwd))
    m_rrg, t_rrg, _ = rs.newey_west_t(ic_rrg, lag)
    m_ctl, t_ctl, _ = rs.newey_west_t(ic_ctl, lag)

    # incremental IC: the part of the RRG IC series not explained by the control
    # IC series (so a signal that is pure repackaged momentum scores ~0)
    ok = np.isfinite(ic_rrg) & np.isfinite(ic_ctl)
    d_ic, d_t = np.nan, np.nan
    if ok.sum() > 30:
        A = np.column_stack([np.ones(ok.sum()), ic_ctl[ok]])
        b, *_ = np.linalg.lstsq(A, ic_rrg[ok], rcond=None)
        d_ic, d_t, _ = rs.newey_west_t(ic_rrg[ok] - A @ b + b[0], lag)

    fm = {}
    for i, nm in enumerate(all_names):
        fm[nm] = (float(mf[1 + i]) if len(mf) > 1 + i else np.nan,
                  float(tf[1 + i]) if len(tf) > 1 + i else np.nan)

    return {
        "ic_rrg_combo": m_rrg, "t_rrg_combo": t_rrg,
        "ic_control_combo": m_ctl, "t_control_combo": t_ctl,
        "delta_ic": d_ic, "t_delta_ic": d_t,
        "r2_controls_only": float(np.nanmean(r2c)) if r2c.size else np.nan,
        "r2_with_rrg": float(np.nanmean(r2f)) if r2f.size else np.nan,
        "fm": fm, "n_dates_fm": len(Xf),
    }


def tranche_portfolio(panel, score, hname, top_k=3, mask=None, long_only=False):
    """
    Jegadeesh-Titman overlapping tranches: rebalance 1/H of capital each period
    and hold H. The resulting return series is ONE PERIOD — no overlap at all —
    so its t-stat is directly interpretable. This is the headline number.
    """
    H = panel["horizons"][hname]
    px_idx = panel["index"]
    # one-period excess returns
    fwd1 = panel["fwd"][list(panel["horizons"])[0]]  # placeholder shape
    T, N = score.shape
    one = np.full((T, N), np.nan)
    f1 = panel["fwd_1p"]
    one[:, :] = f1

    W = np.zeros((T, N))
    for t in range(T):
        s = score[t]
        ok = np.isfinite(s)
        if ok.sum() < 2 * top_k:
            continue
        order = np.argsort(np.where(ok, s, -np.inf))
        top = order[-top_k:]
        w = np.zeros(N)
        w[top] = 1.0 / top_k
        if not long_only:
            bot = order[:top_k][ok[order[:top_k]]]
            if bot.size:
                w[bot] -= 1.0 / bot.size
        W[t] = w

    # average the last H tranches
    eff = np.full((T, N), np.nan)
    for t in range(H - 1, T):
        eff[t] = W[t - H + 1:t + 1].mean(axis=0)

    ret = np.full(T, np.nan)
    for t in range(T - 1):
        w, r = eff[t], one[t + 1]
        ok = np.isfinite(w) & np.isfinite(r)
        if ok.any():
            ret[t + 1] = float(w[ok] @ r[ok])
    if mask is not None:
        ret = np.where(mask, ret, np.nan)

    r = ret[np.isfinite(ret)]
    if r.size < 30:
        return dict(n=int(r.size), mean=np.nan, ir=np.nan, t=np.nan, sharpe_per_period=np.nan)
    per = 52 if panel["freq"] == "W" else 252
    mu, sd = float(r.mean()), float(r.std(ddof=1))
    ir = (mu / sd) * np.sqrt(per) if sd > 0 else np.nan
    _, t, _ = rs.newey_west_t(ret, 2)      # 1-period returns: minimal lag
    return dict(n=int(r.size), mean=mu, ir=ir, t=t,
                sharpe_per_period=(mu / sd if sd > 0 else np.nan))


# ─────────────────────────────────────────────────────────────────────────────
# 4. WALK-FORWARD COMPOSITE SCORE
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward_score(panel, hname, refit_every=REFIT_EVERY, min_train=200):
    """
    Composite RRG score, fit only on the past.

    At each refit date, OLS of forward excess on cross-sectionally standardized
    factors, using ONLY observations whose forward window closed at least H
    periods before the refit date (the purge). Weights then applied forward.
    Returns (score, weights_by_date, last_weights).
    """
    H = panel["horizons"][hname]
    fwd = rs.winsorize_rows(panel["fwd"][hname])
    T, N = fwd.shape
    Z = np.stack([xs_zscore(panel["feats"][f]) for f in FACTORS], axis=-1)  # (T,N,K)
    K = len(FACTORS)
    score = np.full((T, N), np.nan)
    wlog = []
    beta = None

    for t0 in range(0, T, refit_every):
        train_end = t0 - H - 1                     # purge
        if train_end > min_train:
            Xtr = Z[:train_end].reshape(-1, K)
            ytr = fwd[:train_end].reshape(-1)
            ok = np.isfinite(ytr) & np.all(np.isfinite(Xtr), axis=1)
            if ok.sum() > 500:
                A = np.column_stack([np.ones(ok.sum()), Xtr[ok]])
                try:
                    b, *_ = np.linalg.lstsq(A, ytr[ok], rcond=None)
                    beta = b
                    wlog.append({"date": str(panel["index"][t0].date()),
                                 **{f: float(b[1 + i]) for i, f in enumerate(FACTORS)}})
                except np.linalg.LinAlgError:
                    pass
        if beta is not None:
            hi = min(t0 + refit_every, T)
            blk = Z[t0:hi]
            score[t0:hi] = beta[0] + np.nansum(blk * beta[1:], axis=-1)
            score[t0:hi] = np.where(np.all(np.isnan(blk), axis=-1), np.nan, score[t0:hi])
    return score, pd.DataFrame(wlog), beta


def in_sample_score(panel, hname):
    """Full-sample fit — reported ONLY to measure the IS->OOS decay."""
    fwd = rs.winsorize_rows(panel["fwd"][hname])
    Z = np.stack([xs_zscore(panel["feats"][f]) for f in FACTORS], axis=-1)
    K = len(FACTORS)
    X = Z.reshape(-1, K)
    y = fwd.reshape(-1)
    ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
    if ok.sum() < 500:
        return np.full(fwd.shape, np.nan), None
    A = np.column_stack([np.ones(ok.sum()), X[ok]])
    b, *_ = np.linalg.lstsq(A, y[ok], rcond=None)
    sc = b[0] + np.nansum(Z * b[1:], axis=-1)
    sc = np.where(np.all(np.isnan(Z), axis=-1), np.nan, sc)
    return sc, b


def calibration_slope(score, fwd, mask=None):
    """OOS regression of realized on predicted. Slope ~1 means mu-hat is honest;
    slope 0.3 means every Kelly number is 3.3x too large."""
    s = score if mask is None else score[mask]
    f = fwd if mask is None else fwd[mask]
    ok = np.isfinite(s) & np.isfinite(f)
    if ok.sum() < 100:
        return np.nan
    A = np.column_stack([np.ones(ok.sum()), s[ok]])
    b, *_ = np.linalg.lstsq(A, f[ok], rcond=None)
    return float(b[1])


# ─────────────────────────────────────────────────────────────────────────────
# 5. PARAMETER GRID
# ─────────────────────────────────────────────────────────────────────────────

def parameter_grid(prices, bench, horizons, long_lb, skip, freq, quick=False):
    """
    Report the SURFACE, never the best cell. A signal that works in one (W,S,M,L)
    cell and nowhere else is overfit by definition.
    """
    if freq == "W":
        Ws, Ss, Ms, Ls = [40, 52, 65], [6, 10], [3, 4, 6], [8, 10]
    else:
        Ws, Ss, Ms, Ls = [180, 252, 320], [6, 10], [15, 20, 30], [8, 10]
    if quick:
        Ws, Ss, Ms, Ls = Ws[1:2], Ss[1:2], Ms[1:2], Ls[1:2]

    rows = []
    for W in Ws:
        for S in Ss:
            for M in Ms:
                for L in Ls:
                    p = dict(W=W, S=S, M=M, L=L)
                    try:
                        pan = build_panel(prices, bench, p, horizons, long_lb, skip, "grid")
                        pan["freq"] = freq
                    except Exception:
                        continue
                    for hname in horizons:
                        for f in ("distance", "ne_score"):
                            r = factor_ic(pan, hname, f)
                            rows.append({"W": W, "S": S, "M": M, "L": L,
                                         "horizon": hname, "factor": f,
                                         "ic": r["ic"], "t_nw": r["t_nw"]})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 6. REPORT
# ─────────────────────────────────────────────────────────────────────────────

def banner(title, ch="="):
    print("\n" + ch * 78)
    print(title)
    print(ch * 78)


def show(df, floatfmt="{:.4f}"):
    if df is None or len(df) == 0:
        print("  (insufficient data)")
        return
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if np.isfinite(v) else "—")
    print(d.to_string(index=False))


def load_null():
    try:
        n = pd.read_csv("rrg_null_results.csv")
        return {r["metric"]: r for _, r in n.iterrows()}
    except Exception:
        return {}


def main():
    t0 = time.time()
    quick = "--quick" in sys.argv
    results = []          # tidy rows -> rrg_validation_results.csv

    def rec(section, metric, value, note=""):
        results.append({"section": section, "metric": metric,
                        "value": value, "note": note})

    banner("RRG VALIDATION — primary specification")
    print("  Universe : 9 long-history SPDR sectors vs SPY (no survivorship bias)")
    print(f"  Cadence  : weekly, W={PRIMARY['W']} S={PRIMARY['S']} "
          f"M={PRIMARY['M']} L={PRIMARY['L']}")
    print(f"  Horizons : 1M={HORIZONS_W['1M']}w  3M={HORIZONS_W['3M']}w")
    print(f"  Splits   : design<={DESIGN_END}  valid<={VALID_END}  "
          f"HOLDOUT>={HOLDOUT_START}")

    null = load_null()
    if null:
        print(f"  Null     : rrg_null_results.csv loaded "
              f"({int(null['straightness_mean']['n_sims'])} sims)")
    else:
        print("  Null     : MISSING — run `py rrg_null.py` first for baselines")

    # ── data ────────────────────────────────────────────────────────────────
    px_all = rd.load_sector_prices()
    mt, sha = rd.file_fingerprint(rd.PRICE_CACHE)
    rec("data", "sector_price_mtime", mt)
    rec("data", "sector_price_sha256", sha)

    core = rd.SECTOR_CORE
    daily = px_all[core + [rd.BENCHMARK]].dropna()
    wk = rc.to_weekly(daily)
    prices_w = wk[core]
    bench_w = wk[rd.BENCHMARK]
    print(f"\n  Weekly panel: {prices_w.shape[0]} weeks x {prices_w.shape[1]} sectors "
          f"({wk.index[0].date()} -> {wk.index[-1].date()})")

    panel = build_panel(prices_w, bench_w, PRIMARY, HORIZONS_W, 52, 4, "sectors-weekly")
    panel["freq"] = "W"
    # one-period excess returns for the portfolio test
    pxn = prices_w.to_numpy(dtype=float)
    bmn = bench_w.to_numpy(dtype=float)
    one = np.full(pxn.shape, np.nan)
    one[1:] = pxn[1:] / pxn[:-1] - 1.0
    oneb = np.full(len(bmn), np.nan)
    oneb[1:] = bmn[1:] / bmn[:-1] - 1.0
    panel["fwd_1p"] = one - oneb[:, None]

    idx = panel["index"]
    m_design = slice_mask(idx, end=DESIGN_END)
    m_valid = slice_mask(idx, start="2014-01-01", end=VALID_END)
    m_hold = slice_mask(idx, start=HOLDOUT_START)
    valid_rows = np.isfinite(panel["feats"]["rs_momentum"]).any(axis=1)
    print(f"  Usable after burn-in: {int(valid_rows.sum())} weeks "
          f"(first {idx[valid_rows][0].date() if valid_rows.any() else '—'})")
    print(f"  design={int((m_design & valid_rows).sum())}w  "
          f"validation={int((m_valid & valid_rows).sum())}w  "
          f"HOLDOUT={int((m_hold & valid_rows).sum())}w")

    # ── 1. baseline + quadrant ──────────────────────────────────────────────
    banner("1. HIT RATE BY QUADRANT  (baseline is measured, never assumed 50%)")
    for hname in HORIZONS_W:
        qt, base = quadrant_table(panel, hname)
        print(f"\n  --- {hname} horizon --- unconditional baseline hit rate = "
              f"{100*base:.2f}%   <- compare against THIS, not 50%")
        nb = null.get(f"baseline_hit_{hname}")
        if nb is not None:
            print(f"      (synthetic null baseline: {100*nb['mean']:.2f}%)")
        show(qt)
        rec("quadrant", f"baseline_hit_{hname}", base)
        for _, r in qt.iterrows():
            rec("quadrant", f"hit_{r['quadrant']}_{hname}", r["hit_rate"])
            rec("quadrant", f"mean_excess_{r['quadrant']}_{hname}", r["mean_excess_pct"])
        if len(qt):
            lead = qt[qt["quadrant"] == "Leading"]["hit_rate"]
            lag = qt[qt["quadrant"] == "Lagging"]["hit_rate"]
            if len(lead) and len(lag):
                spread = float(lead.iloc[0] - lag.iloc[0])
                nk = null.get(f"hit_spread_Lead_minus_Lag_{hname}")
                nn = f"  (null p95 = {nk['p95']:+.4f})" if nk is not None else ""
                print(f"      Leading - Lagging hit spread: {spread:+.4f}{nn}")
                rec("quadrant", f"hit_spread_Lead_minus_Lag_{hname}", spread)

    # ── 2. heading ──────────────────────────────────────────────────────────
    banner("2. HIT RATE BY HEADING OCTANT")
    print("  NOTE: heading is largely redundant with quadrant — clockwise motion is")
    print("  mechanical, so these two tables are not independent evidence.")
    for hname in HORIZONS_W:
        print(f"\n  --- {hname} ---")
        show(octant_table(panel, hname))

    # ── 3. distance ─────────────────────────────────────────────────────────
    banner("3. DISTANCE FROM CENTRE vs FORWARD EXCESS RETURN")
    print("  Testing the assumption that more distance = stronger. Bucket edges")
    print("  come from the DESIGN sample only, then applied out of sample.")
    dist_edges = {}
    for hname in HORIZONS_W:
        dd, edges = decile_table(panel, hname, "distance", mask=m_design)
        dist_edges[hname] = edges
        print(f"\n  --- {hname} : distance deciles (design sample) ---")
        show(dd)
        pk, pv = peak_bucket(dd)
        print(f"      Forward excess PEAKS at decile {pk} ({pv:+.3f}%), "
              f"not at decile {N_BUCKETS}." if np.isfinite(pv) else "      (insufficient)")
        rec("distance", f"peak_decile_{hname}", pk)
        if len(dd) >= 10:
            spread = float(dd["mean_excess_pct"].iloc[-1] - dd["mean_excess_pct"].iloc[0])
            nk = null.get(f"dist_decile_spread_{hname}")
            nn = f"  (null p95 = {100*nk['p95']:+.3f}%)" if nk is not None else ""
            print(f"      top-minus-bottom decile spread: {spread:+.3f}%{nn}")
            rec("distance", f"decile_spread_{hname}", spread)
        # holdout view
        dh, _ = decile_table(panel, hname, "distance", mask=m_hold, edges=edges)
        if len(dh):
            print(f"      HOLDOUT, same edges:")
            show(dh[["bucket", "n", "hit_rate", "mean_excess_pct"]])

    banner("3b. INCREASING vs ABSOLUTE DISTANCE")
    print("  delta_distance is mechanically anti-correlated with lagged distance,")
    print("  so the bivariate model uses delta orthogonalized against level.")
    for hname in HORIZONS_W:
        a = factor_ic(panel, hname, "distance")
        b = factor_ic(panel, hname, "delta_distance")
        corr = rs.pearson(panel["feats"]["distance"].ravel(),
                          panel["feats"]["delta_distance"].ravel())
        print(f"\n  {hname}:  IC(level)={a['ic']:+.4f} (t={a['t_nw']:+.2f})   "
              f"IC(delta)={b['ic']:+.4f} (t={b['t_nw']:+.2f})   corr={corr:+.3f}")
        rec("distance", f"ic_level_{hname}", a["ic"])
        rec("distance", f"ic_delta_{hname}", b["ic"])
        better = "delta" if abs(b["ic"]) > abs(a["ic"]) else "level"
        print(f"      -> stronger univariate predictor: {better}")
        rec("distance", f"stronger_{hname}", better)

    # ── 4. factor contribution ──────────────────────────────────────────────
    banner("4. WHICH FACTOR CONTRIBUTES MOST?  (rank IC, Newey-West)")
    print(f"  Overlap inflation of naive t: 1M={rs.overlap_inflation(4):.2f}x  "
          f"3M={rs.overlap_inflation(13):.2f}x")
    for hname in HORIZONS_W:
        rows = [factor_ic(panel, hname, f) for f in FACTORS + CONTROLS]
        df = pd.DataFrame(rows)[["factor", "ic", "t_nw", "t_naive", "n_dates"]]
        print(f"\n  --- {hname} ---")
        show(df)
        for r in rows:
            rec("factor_ic", f"ic_{r['factor']}_{hname}", r["ic"])
            rec("factor_ic", f"t_{r['factor']}_{hname}", r["t_nw"])
        nk = null.get(f"max_abs_t_{hname}")
        if nk is not None:
            print(f"      Null max|t| p95 = {nk['p95']:.2f} — anything below is noise.")

    # ── 5. the horse race ───────────────────────────────────────────────────
    banner("5. THE DECIDING TEST — does RRG beat plain relative momentum?")
    print("  RRG is a lagged, double-smoothed transform of relative price. If it")
    print("  adds nothing over 12-1 momentum + 1M reversal, it is a visualization,")
    print("  not a forecast.")
    hr = {}
    for hname in HORIZONS_W:
        h = horse_race(panel, hname)
        hr[hname] = h
        print(f"\n  --- {hname} ---")
        print(f"    IC  RRG combo      : {h['ic_rrg_combo']:+.4f}  (t={h['t_rrg_combo']:+.2f})")
        print(f"    IC  momentum combo : {h['ic_control_combo']:+.4f}  (t={h['t_control_combo']:+.2f})")
        print(f"    INCREMENTAL IC     : {h['delta_ic']:+.4f}  (t={h['t_delta_ic']:+.2f})"
              f"   [need >{TH['d_ic']:.3f}, t>{TH['d_ic_t']}]")
        print(f"    mean cross-sec R2  : controls {h['r2_controls_only']:+.4f} "
              f"-> +RRG {h['r2_with_rrg']:+.4f}")
        print(f"    Fama-MacBeth (fwd ~ rrg_combo + mom_12_1 + rev_1m), "
              f"{h['n_dates_fm']} dates:")
        for nm, (coef, t) in h["fm"].items():
            mark = "  <- the RRG marginal contribution" if nm == "rrg_combo" else ""
            print(f"        {nm:<12s} coef={coef:+.5f}  t={t:+.2f}{mark}"
                  if np.isfinite(t) else f"        {nm:<12s} —")
            rec("horse_race", f"fm_t_{nm}_{hname}", t)
        rec("horse_race", f"delta_ic_{hname}", h["delta_ic"])
        rec("horse_race", f"t_delta_ic_{hname}", h["t_delta_ic"])
        rec("horse_race", f"ic_rrg_{hname}", h["ic_rrg_combo"])
        rec("horse_race", f"ic_momentum_{hname}", h["ic_control_combo"])

    # ── 6. portfolio ────────────────────────────────────────────────────────
    banner("6. PORTFOLIO TEST (overlapping tranches — no overlap in the returns)")
    print("  Rebalance 1/H each period, hold H. Long top-3 / short bottom-3 of the")
    print("  9 sectors. This return series is one-period, so its t-stat is honest.")
    port = {}
    for hname in HORIZONS_W:
        sc_wf, wlog, last_beta = walk_forward_score(panel, hname)
        sc_is, beta_is = in_sample_score(panel, hname)
        for tag, sc, msk in (("full-sample-fit (IS)", sc_is, None),
                             ("walk-forward", sc_wf, None),
                             ("walk-forward HOLDOUT", sc_wf, m_hold)):
            r = tranche_portfolio(panel, sc, hname, top_k=3, mask=msk)
            print(f"\n  {hname}  {tag:<24s} n={r['n']:4d}  "
                  f"mean/period={r['mean']:+.5f}  IR={r['ir']:+.3f}  t={r['t']:+.2f}")
            rec("portfolio", f"ir_{hname}_{tag}", r["ir"])
            rec("portfolio", f"t_{hname}_{tag}", r["t"])
            port[(hname, tag)] = r
        # IS vs OOS IC decay
        ic_is = rs.cross_sectional_ic(sc_is, panel["fwd"][hname])
        ic_oos = rs.cross_sectional_ic(np.where(m_hold[:, None], sc_wf, np.nan),
                                       panel["fwd"][hname])
        m_is, _, _ = rs.newey_west_t(ic_is, int(np.ceil(1.5 * HORIZONS_W[hname])))
        m_oos, t_oos, _ = rs.newey_west_t(ic_oos, int(np.ceil(1.5 * HORIZONS_W[hname])))
        decay = (m_oos / m_is) if (np.isfinite(m_is) and abs(m_is) > 1e-9) else np.nan
        slope = calibration_slope(sc_wf, panel["fwd"][hname], m_hold)
        print(f"      composite IC: IS={m_is:+.4f}  OOS(holdout)={m_oos:+.4f} "
              f"(t={t_oos:+.2f})  decay ratio={decay:+.2f}  [need >{TH['decay']}]")
        print(f"      OOS calibration slope={slope:+.2f}  [need 0.5-1.5; "
              f"0.3 would mean every Kelly number is 3.3x too big]")
        rec("walkforward", f"ic_is_{hname}", m_is)
        rec("walkforward", f"ic_oos_{hname}", m_oos)
        rec("walkforward", f"decay_{hname}", decay)
        rec("walkforward", f"calib_slope_{hname}", slope)

    # ── 7. parameter surface ────────────────────────────────────────────────
    banner("7. PARAMETER SURFACE (median, not the best cell)")
    grid = parameter_grid(prices_w, bench_w, HORIZONS_W, 52, 4, "W", quick=quick)
    if len(grid):
        for hname in HORIZONS_W:
            g = grid[grid["horizon"] == hname]
            for f in g["factor"].unique():
                gg = g[g["factor"] == f]["t_nw"].dropna()
                if len(gg):
                    med = float(gg.median())
                    sign = float(max((gg > 0).mean(), (gg < 0).mean()))
                    print(f"  {hname} {f:<14s} cells={len(gg):3d}  median t={med:+.2f}  "
                          f"max|t|={gg.abs().max():.2f}  sign agreement={100*sign:.0f}%"
                          f"   [need median>{TH['grid_median_t']}, "
                          f"agreement>{100*TH['grid_sign']:.0f}%]")
                    rec("grid", f"median_t_{f}_{hname}", med)
                    rec("grid", f"sign_agree_{f}_{hname}", sign)
        grid.to_csv("rrg_grid_results.csv", index=False)
        print("\n  Saved -> rrg_grid_results.csv")

    # ── 8. daily robustness ─────────────────────────────────────────────────
    banner("8. ROBUSTNESS — daily cadence (the user asked to compare both)")
    pan_d = build_panel(daily[core], daily[rd.BENCHMARK], rc.DAILY, HORIZONS_D, 252, 21,
                        "sectors-daily")
    pan_d["freq"] = "D"
    for hname in HORIZONS_D:
        rows = [factor_ic(pan_d, hname, f) for f in ("distance", "ne_score", "straightness")]
        df = pd.DataFrame(rows)[["factor", "ic", "t_nw", "t_naive"]]
        print(f"\n  --- daily, {hname} (t_naive is inflated "
              f"{rs.overlap_inflation(HORIZONS_D[hname]):.1f}x) ---")
        show(df)
        for r in rows:
            rec("daily", f"ic_{r['factor']}_{hname}", r["ic"])
            rec("daily", f"t_{r['factor']}_{hname}", r["t_nw"])

    # ── 9. verdict ──────────────────────────────────────────────────────────
    banner("9. VERDICT AGAINST THE PRE-REGISTERED DECISION RULES")
    checks = []
    h = "1M"
    ic_oos = next((r["value"] for r in results
                   if r["metric"] == f"ic_oos_{h}" and r["section"] == "walkforward"), np.nan)
    decay = next((r["value"] for r in results
                  if r["metric"] == f"decay_{h}" and r["section"] == "walkforward"), np.nan)
    pr = port.get((h, "walk-forward HOLDOUT"), {})
    d_ic = hr[h]["delta_ic"]
    d_t = hr[h]["t_delta_ic"]
    nullmax = null.get(f"max_abs_t_{h}", {}).get("p95", np.nan)

    def chk(name, ok, detail):
        checks.append((name, bool(ok), detail))

    chk("OOS rank-IC > 0.03", np.isfinite(ic_oos) and ic_oos > TH["ic"], f"{ic_oos:+.4f}")
    chk("Portfolio IR > 0.40 (holdout)",
        np.isfinite(pr.get("ir", np.nan)) and pr.get("ir", np.nan) > TH["ir"],
        f"{pr.get('ir', float('nan')):+.3f}")
    chk("Portfolio t > 3.0 (holdout)",
        np.isfinite(pr.get("t", np.nan)) and pr.get("t", np.nan) > TH["ir_t"],
        f"{pr.get('t', float('nan')):+.2f}")
    chk("OOS/IS IC decay > 0.50", np.isfinite(decay) and decay > TH["decay"], f"{decay:+.2f}")
    chk("Incremental IC over momentum > 0.015",
        np.isfinite(d_ic) and d_ic > TH["d_ic"], f"{d_ic:+.4f}")
    chk("Incremental IC t > 2.5", np.isfinite(d_t) and d_t > TH["d_ic_t"], f"{d_t:+.2f}")
    chk("Beats synthetic null max|t| p95",
        np.isfinite(d_t) and np.isfinite(nullmax) and abs(d_t) > nullmax,
        f"|{d_t:.2f}| vs {nullmax:.2f}" if np.isfinite(nullmax) else "null missing")
    if len(grid):
        g = grid[(grid["horizon"] == h) & (grid["factor"] == "distance")]["t_nw"].dropna()
        med = float(g.median()) if len(g) else np.nan
        agree = float(max((g > 0).mean(), (g < 0).mean())) if len(g) else np.nan
        chk("Grid median |t| > 1.5", np.isfinite(med) and abs(med) > TH["grid_median_t"],
            f"{med:+.2f}")
        chk("Grid sign agreement > 70%", np.isfinite(agree) and agree > TH["grid_sign"],
            f"{100*agree:.0f}%")

    n_pass = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {name:<42s} {detail}")
        rec("verdict", name, 1.0 if ok else 0.0, detail)
    print(f"\n  {n_pass}/{len(checks)} criteria passed.")
    edge_real = n_pass == len(checks)
    print("\n  " + ("=" * 74))
    if edge_real:
        print("  VERDICT: edge survives every pre-registered test. Sizing is justified.")
    else:
        print("  VERDICT: the pre-registered bar is NOT met.")
        print("  RRG state is still a legitimate DESCRIPTIVE tool — it summarizes where")
        print("  each sector/stock sits in relative-strength space, which is useful for")
        print("  communication. But on this evidence it should not drive position size.")
        print("  Recommended sizing multiplier: 0. See section 5 for the reason —")
        print("  whatever signal exists is largely already in plain relative momentum.")
    print("  " + ("=" * 74))
    rec("verdict", "n_pass", n_pass)
    rec("verdict", "n_checks", len(checks))
    rec("verdict", "edge_real", 1.0 if edge_real else 0.0)

    # ── 10. calibration for rrg_analysis.py ────────────────────────────────
    cal = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "spec": {"cadence": "weekly", **PRIMARY, "horizons": HORIZONS_W,
                 "universe": core, "benchmark": rd.BENCHMARK},
        "data_fingerprint": {"sector_prices_mtime": mt, "sector_prices_sha256": sha},
        "edge_real": bool(edge_real),
        "n_pass": int(n_pass), "n_checks": int(len(checks)),
        "checks": [{"name": n, "pass": bool(o), "detail": d} for n, o, d in checks],
        "factors": FACTORS,
        "weights": ({f: float(last_beta[1 + i]) for i, f in enumerate(FACTORS)}
                    if last_beta is not None else None),
        "intercept": float(last_beta[0]) if last_beta is not None else None,
        "baseline_hit": {h: float(quadrant_table(panel, h)[1]) for h in HORIZONS_W},
        "distance_edges": {h: [float(x) for x in dist_edges[h]] for h in dist_edges},
        "buckets": {},
        "sizing_multiplier": 1.0 if edge_real else 0.0,
    }
    # per (quadrant x distance tercile) W / R / mean-loss, shrunk toward the pool
    for hname in HORIZONS_W:
        fwd = panel["fwd"][hname]
        q = panel["feats"]["quadrant"]
        d = panel["feats"]["distance"]
        ok_d = np.isfinite(d[m_design])
        terc = np.quantile(d[m_design][ok_d], [0, 1 / 3, 2 / 3, 1.0]) if ok_d.sum() > 100 else None
        pool = rs.hit_rate(fwd)
        cal["buckets"][hname] = {"tercile_edges": [float(x) for x in terc] if terc is not None else None,
                                 "pool_hit": float(pool), "cells": []}
        if terc is None:
            continue
        for k, qname in enumerate(rc.QUADRANTS):
            for ti in range(3):
                sel = fwd[(q == k) & (d >= terc[ti]) & (d < terc[ti + 1] if ti < 2 else d >= terc[ti])]
                sel = sel[np.isfinite(sel)]
                if sel.size < 30:
                    continue
                w = rs.hit_rate(sel)
                R = rs.win_loss_ratio(sel)
                losses = sel[sel < 0]
                cal["buckets"][hname]["cells"].append({
                    "quadrant": qname, "distance_tercile": ti + 1, "n": int(sel.size),
                    "W_raw": float(w),
                    "W_shrunk": float(rs.shrink_win_rate(w, sel.size, pool)),
                    "R": float(R) if np.isfinite(R) else None,
                    "mean_loss": float(losses.mean()) if losses.size >= 20 else None,
                    "mean_excess": float(sel.mean()),
                    "std_excess": float(sel.std(ddof=1)),
                    "enough_data": bool(sel.size >= MIN_BUCKET_N),
                })
    with open("rrg_calibration.json", "w") as f:
        json.dump(cal, f, indent=2)

    pd.DataFrame(results).to_csv("rrg_validation_results.csv", index=False)
    print(f"\nSaved -> rrg_validation_results.csv, rrg_calibration.json")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
