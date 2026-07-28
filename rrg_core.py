"""
RRG Core — Relative Rotation Graph coordinates and measurable factors
=====================================================================
Numpy-only (no scipy / statsmodels / matplotlib) so that anything downstream,
including the deployed Streamlit page, imports cleanly on Streamlit Cloud where
only `requirements.txt` is installed.

WHAT THIS MODULE IS
-------------------
A JdK-style RRG transform plus the four "RRG factors" the analysis needs, each
defined as a *measurable* quantity rather than an eyeballed impression:

    heading / angle   -> PCA principal direction of the tail, on standardized axes
    distance          -> Mahalanobis distance from the (100, 100) centre
    delta distance    -> change in that distance over the tail
    tail persistence  -> straightness (net displacement / path length) + fit R^2

THE THING YOU MUST KNOW BEFORE TRUSTING ANY OF IT
-------------------------------------------------
`rs_ratio` is a rolling z-score. A rolling z-score is stationary and reverts to
100 *by construction*: if relative price jumps once and then sits perfectly
still, the trailing mean drifts up to meet it and the coordinate decays back to
100 on its own. An asset can therefore traverse Leading -> Weakening -> Lagging
with **zero change in relative price**.

`rs_momentum` is, to first order, the discrete derivative of `rs_ratio`. So an
RRG plots x against x-dot -- a phase portrait. The phase portrait of *any*
stationary series rotates clockwise: sine wave, AR(1), or pure noise. The famous
RRG rotation is therefore geometry, not evidence. Two consequences:

  1. `heading` is largely redundant with `quadrant` (clockwise motion implies
     heading ~ position-angle - 90 mechanically).
  2. The null hypothesis to beat is NOT "zero". It is "plain trailing relative
     momentum". See rrg_validate.py, which runs that horse race explicitly, and
     rrg_null.py, which prices the mechanical baseline of every metric here.

Nothing in this module decides whether RRG works. It only produces numbers.

Usage:
  py rrg_core.py          # runs the self-tests (synthetic sine + GBM)
"""

import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

# ── Default parameters ───────────────────────────────────────────────────────
# Weekly is the primary cadence: the signal is normalized over a year and lags
# price by ~S/2 + M/2 + S/2 periods, so daily sampling adds overlap, not
# information. Daily is kept as a robustness block.
WEEKLY = dict(W=52, S=10, M=4, L=10)      # burn-in (W+S-2) + M + (W-1) + (S-1) = 124 wks
DAILY = dict(W=252, S=10, M=20, L=10)     # burn-in 540 trading days (~2.15 yrs)

CENTER = 100.0
CHUNK = 128          # rows of output per rolling-window block (caps peak memory)
_EPS = 1e-12

QUADRANTS = ("Leading", "Weakening", "Lagging", "Improving")
OCTANTS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")


# ─────────────────────────────────────────────────────────────────────────────
# 1. ROLLING STATISTICS  (chunked -- see note)
# ─────────────────────────────────────────────────────────────────────────────
# sliding_window_view returns a *view*, but np.std/np.mean on that view allocate
# a temporary of the view's shape. On the daily stock panel that is
# 5423 x 504 x 252 x 8B = 5.5 GB. We therefore reduce in row-blocks. Never call
# np.ascontiguousarray on the view.
#
# NaN propagates through a window on purpose: it enforces min_periods == w
# strictly, so partial windows never leak into the output.

def _chunked_reduce(a, w, fn, chunk=CHUNK):
    """Apply `fn(window)` over trailing windows of length `w` along axis 0."""
    a = np.asarray(a, dtype=float)
    out = np.full(a.shape, np.nan)
    n_out = a.shape[0] - w + 1
    if n_out <= 0:
        return out
    for s in range(0, n_out, chunk):
        e = min(s + chunk, n_out)
        win = sliding_window_view(a[s:e + w - 1], w, axis=0)
        out[s + w - 1:e + w - 1] = fn(win)
    return out


def roll_mean(a, w):
    return _chunked_reduce(a, w, lambda x: x.mean(axis=-1))


def roll_std(a, w, ddof=1):
    return _chunked_reduce(a, w, lambda x: x.std(axis=-1, ddof=ddof))


def roll_cov_pair(a, b, w, chunk=CHUNK):
    """Trailing (var_a, cov_ab, var_b) over window `w`, mean-centred per window.

    Mean-centring inside the window (rather than the E[ab]-E[a]E[b] identity)
    avoids catastrophic cancellation when the inputs sit far from zero.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    saa = np.full(a.shape, np.nan)
    sab = np.full(a.shape, np.nan)
    sbb = np.full(a.shape, np.nan)
    n_out = a.shape[0] - w + 1
    if n_out <= 0:
        return saa, sab, sbb
    for s in range(0, n_out, chunk):
        e = min(s + chunk, n_out)
        wa = sliding_window_view(a[s:e + w - 1], w, axis=0)
        wb = sliding_window_view(b[s:e + w - 1], w, axis=0)
        ca = wa - wa.mean(axis=-1, keepdims=True)
        cb = wb - wb.mean(axis=-1, keepdims=True)
        lo, hi = s + w - 1, e + w - 1
        saa[lo:hi] = (ca * ca).sum(axis=-1) / (w - 1)
        sab[lo:hi] = (ca * cb).sum(axis=-1) / (w - 1)
        sbb[lo:hi] = (cb * cb).sum(axis=-1) / (w - 1)
    return saa, sab, sbb


def _guard_std(sd, mu):
    """Kill degenerate standard deviations -> NaN, never inf."""
    floor = np.maximum(1e-8, 1e-6 * np.abs(mu))
    return np.where(sd > floor, sd, np.nan)


def _shift(a, k):
    out = np.full(np.shape(a), np.nan)
    if k > 0:
        out[k:] = np.asarray(a)[:-k]
    elif k == 0:
        out[:] = a
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. RRG COORDINATES
# ─────────────────────────────────────────────────────────────────────────────

def rrg_coordinates(prices, benchmark, W, S, M):
    """
    JdK-style RS-Ratio / RS-Momentum.

        rs           = 100 * price / benchmark
        rs_ratio     = SMA_S( 100 + zscore_W(rs) )
        mom_raw      = 100 * rs_ratio / rs_ratio.shift(M)
        rs_momentum  = SMA_S( 100 + zscore_W(mom_raw) )

    prices    : (T, N) array of total-return prices
    benchmark : (T,)   array of benchmark total-return prices
    Returns (rs_ratio, rs_momentum), both (T, N), NaN through the burn-in.
    """
    prices = np.asarray(prices, dtype=float)
    benchmark = np.asarray(benchmark, dtype=float).reshape(-1, 1)

    with np.errstate(divide="ignore", invalid="ignore"):
        rs = CENTER * prices / benchmark
    rs = np.where(np.isfinite(rs), rs, np.nan)

    mu = roll_mean(rs, W)
    sd = _guard_std(roll_std(rs, W), mu)
    rs_ratio = roll_mean(CENTER + (rs - mu) / sd, S)

    prev = _shift(rs_ratio, M)
    with np.errstate(divide="ignore", invalid="ignore"):
        mom_raw = CENTER * rs_ratio / prev
    mom_raw = np.where(np.isfinite(mom_raw), mom_raw, np.nan)

    mu2 = roll_mean(mom_raw, W)
    sd2 = _guard_std(roll_std(mom_raw, W), mu2)
    rs_mom = roll_mean(CENTER + (mom_raw - mu2) / sd2, S)

    return rs_ratio, rs_mom


def burn_in(W, S, M):
    """First index that can hold a valid rs_momentum."""
    return (W + S - 2) + M + (W - 1) + (S - 1)


def quadrant_codes(rs_ratio, rs_mom):
    """0 Leading (NE), 1 Weakening (SE), 2 Lagging (SW), 3 Improving (NW). NaN -> -1."""
    r = np.asarray(rs_ratio, dtype=float)
    m = np.asarray(rs_mom, dtype=float)
    q = np.full(r.shape, -1, dtype=np.int8)
    ok = np.isfinite(r) & np.isfinite(m)
    hi_r, hi_m = r > CENTER, m > CENTER
    q[ok & hi_r & hi_m] = 0
    q[ok & hi_r & ~hi_m] = 1
    q[ok & ~hi_r & ~hi_m] = 2
    q[ok & ~hi_r & hi_m] = 3
    return q


def quadrant_run_length(q):
    """Consecutive periods (inclusive) the asset has sat in its current quadrant."""
    q = np.asarray(q)
    run = np.zeros(q.shape, dtype=float)
    run[0] = np.where(q[0] >= 0, 1.0, np.nan)
    for t in range(1, q.shape[0]):
        same = (q[t] == q[t - 1]) & (q[t] >= 0)
        run[t] = np.where(q[t] < 0, np.nan, np.where(same, run[t - 1] + 1.0, 1.0))
    return run


# ─────────────────────────────────────────────────────────────────────────────
# 3. THE FOUR FACTORS
# ─────────────────────────────────────────────────────────────────────────────

def mahalanobis_distance(rs_ratio, rs_mom, W):
    """
    Distance from the (100, 100) centre in trailing-covariance units.

    Euclidean sqrt(dr^2 + dm^2) is NOT valid here: the two axes have different
    unconditional scales (differencing amplifies noise, so sd(rs_mom) >
    sd(rs_ratio)) and they are mechanically correlated (rs_mom is approximately
    d/dt of rs_ratio). Mahalanobis fixes both in one step and makes the number
    comparable across assets, dates and parameter settings.
    """
    a = np.asarray(rs_ratio, dtype=float) - CENTER
    b = np.asarray(rs_mom, dtype=float) - CENTER
    saa, sab, sbb = roll_cov_pair(a, b, W)

    det = saa * sbb - sab * sab
    det = np.where(np.abs(det) > _EPS, det, np.nan)          # singular -> NaN
    # v' * inv(S) * v  for the 2x2 case, written out
    q = (sbb * a * a - 2.0 * sab * a * b + saa * b * b) / det
    q = np.where(q >= 0, q, np.nan)                          # numerical safety
    return np.sqrt(q)


def tail_geometry(rs_ratio, rs_mom, W, L, flat_frac=0.25, chunk=CHUNK):
    """
    Direction and consistency of travel over the trailing `L` observations.

    Axes are first standardized by their own trailing SD. Raw degrees on the raw
    axes are an artefact of the plot's aspect ratio -- "45 degrees = NE" is only
    meaningful once both axes are in comparable units.

    Direction is the PCA principal axis of the L points (total least squares),
    signed by the chord. That is more robust than a two-point chord and shares
    its definition with the R^2 persistence measure.

    Returns dict of (T, N) arrays:
        angle_deg    direction of travel, degrees (0 = E, 90 = N, 45 = NE)
        ne_score     cos(angle - 45), continuous "north-east-ness" in [-1, 1]
        straightness net displacement / path length, in [0, 1]
        tail_r2      share of tail variance on the principal axis
        chord_len    net displacement in standardized units
        path_len     total distance travelled
        is_flat      1.0 where displacement is too small for a defined heading
    """
    r = np.asarray(rs_ratio, dtype=float)
    m = np.asarray(rs_mom, dtype=float)

    sd_r = _guard_std(roll_std(r, W), np.ones_like(r))
    sd_m = _guard_std(roll_std(m, W), np.ones_like(m))
    x = (r - CENTER) / sd_r
    y = (m - CENTER) / sd_m

    shape = r.shape
    out = {k: np.full(shape, np.nan) for k in
           ("angle_deg", "ne_score", "straightness", "tail_r2", "chord_len", "path_len")}
    out["is_flat"] = np.full(shape, np.nan)

    n_out = shape[0] - L + 1
    if n_out <= 0:
        return out

    for s in range(0, n_out, chunk):
        e = min(s + chunk, n_out)
        wx = sliding_window_view(x[s:e + L - 1], L, axis=0)
        wy = sliding_window_view(y[s:e + L - 1], L, axis=0)
        lo, hi = s + L - 1, e + L - 1

        cx = wx[..., -1] - wx[..., 0]
        cy = wy[..., -1] - wy[..., 0]
        chord = np.hypot(cx, cy)

        dx = np.diff(wx, axis=-1)
        dy = np.diff(wy, axis=-1)
        step = np.hypot(dx, dy)
        path = step.sum(axis=-1)
        with warnings.catch_warnings():          # all-NaN windows in the burn-in
            warnings.simplefilter("ignore", RuntimeWarning)
            med_step = np.nanmedian(step, axis=-1)

        # straightness: 0/0 -> NaN, never 1.0
        with np.errstate(divide="ignore", invalid="ignore"):
            straight = np.where(path > _EPS, chord / path, np.nan)

        # PCA of the L points
        mx = wx.mean(axis=-1, keepdims=True)
        my = wy.mean(axis=-1, keepdims=True)
        ax_, ay_ = wx - mx, wy - my
        sxx = (ax_ * ax_).sum(axis=-1)
        sxy = (ax_ * ay_).sum(axis=-1)
        syy = (ay_ * ay_).sum(axis=-1)

        tr, dif = sxx + syy, sxx - syy
        root = np.sqrt(np.maximum(0.25 * dif * dif + sxy * sxy, 0.0))
        lam1, lam2 = 0.5 * tr + root, 0.5 * tr - root
        with np.errstate(divide="ignore", invalid="ignore"):
            r2 = np.where(tr > _EPS, lam1 / tr, np.nan)
        lam2 = np.maximum(lam2, 0.0)

        # principal eigenvector of [[sxx, sxy], [sxy, syy]]
        vx = np.where(np.abs(sxy) > _EPS, sxy, np.where(sxx >= syy, 1.0, 0.0))
        vy = np.where(np.abs(sxy) > _EPS, lam1 - sxx, np.where(sxx >= syy, 0.0, 1.0))
        vnorm = np.hypot(vx, vy)
        vx = np.where(vnorm > _EPS, vx / vnorm, np.nan)
        vy = np.where(vnorm > _EPS, vy / vnorm, np.nan)

        # sign the axis by the chord (PCA direction is sign-ambiguous)
        flip = (vx * cx + vy * cy) < 0
        vx = np.where(flip, -vx, vx)
        vy = np.where(flip, -vy, vy)

        # atan2(0, 0) silently returns 0.0 -- i.e. "due East" -- which would
        # manufacture a fake spike in the E octant exactly where observations are
        # densest (near the origin). Require real displacement or emit NaN.
        flat = ~(chord > flat_frac * np.where(np.isfinite(med_step), med_step, np.nan))
        ang = np.degrees(np.arctan2(vy, vx))
        ang = np.where(flat, np.nan, ang)

        out["angle_deg"][lo:hi] = ang
        out["ne_score"][lo:hi] = np.cos(np.radians(ang - 45.0))
        out["straightness"][lo:hi] = straight
        out["tail_r2"][lo:hi] = r2
        out["chord_len"][lo:hi] = chord
        out["path_len"][lo:hi] = path
        out["is_flat"][lo:hi] = flat.astype(float)

    return out


def straightness_null(L):
    """
    Expected straightness of an isotropic 2-D random walk over L points.

    E[net] = 1.253*sigma*sqrt(L-1), E[path] = 1.253*sigma*(L-1)  ->  ~1/sqrt(L-1).

    Matters because raw straightness is not interpretable on its own: 0.40 sounds
    "not very straight" but is ~1.8x the random-walk null at L=10. Note this is
    only the *random-walk* null -- the S-period smoothing in rrg_coordinates
    induces autocorrelation that pushes straightness far higher on its own, so
    the authoritative baseline is the simulated one in rrg_null.py.
    """
    return 1.0 / np.sqrt(max(L - 1, 1))


def octant_labels(angle_deg):
    """Map angle -> compass octant string; NaN (flat) -> 'flat'."""
    a = np.asarray(angle_deg, dtype=float)
    lab = np.full(a.shape, "flat", dtype=object)
    ok = np.isfinite(a)
    idx = np.floor(((a % 360.0) + 22.5) / 45.0).astype(int) % 8
    lab[ok] = np.array(OCTANTS, dtype=object)[idx[ok]]
    return lab


# ─────────────────────────────────────────────────────────────────────────────
# 4. ONE-CALL FEATURE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def compute_features(prices_df, benchmark, params, drop_burn_in=True):
    """
    Full RRG feature set for a price panel.

    prices_df : DataFrame (dates x tickers) of total-return prices
    benchmark : Series of benchmark prices, aligned to prices_df.index
    params    : dict with W, S, M, L (e.g. WEEKLY)

    Returns a dict of DataFrames sharing prices_df's index/columns.
    """
    W, S, M, L = params["W"], params["S"], params["M"], params["L"]
    px = prices_df.to_numpy(dtype=float)
    bm = np.asarray(benchmark, dtype=float)
    if bm.shape[0] != px.shape[0]:
        raise ValueError("benchmark and prices must share the same index length")

    rs_ratio, rs_mom = rrg_coordinates(px, bm, W, S, M)
    dist = mahalanobis_distance(rs_ratio, rs_mom, W)
    geo = tail_geometry(rs_ratio, rs_mom, W, L)
    q = quadrant_codes(rs_ratio, rs_mom)

    feats = {
        "rs_ratio": rs_ratio,
        "rs_momentum": rs_mom,
        "distance": dist,
        "delta_distance": dist - _shift(dist, L),
        "quadrant": q.astype(float),
        "quadrant_run": quadrant_run_length(q),
        **geo,
    }

    if drop_burn_in:
        b = burn_in(W, S, M)
        for k in feats:
            feats[k][:min(b, feats[k].shape[0])] = np.nan
        # quadrant is carried as float here so it can hold NaN; -1 means "undefined"

    return {k: pd.DataFrame(v, index=prices_df.index, columns=prices_df.columns)
            for k, v in feats.items()}


def to_weekly(prices_df, rule="W-FRI"):
    """Last observation of each week. Weekly is the primary cadence."""
    return prices_df.resample(rule).last().dropna(how="all")


# ─────────────────────────────────────────────────────────────────────────────
# 5. SELF-TESTS
# ─────────────────────────────────────────────────────────────────────────────

def _self_test():
    print("=" * 78)
    print("RRG CORE — SELF-TESTS")
    print("=" * 78)
    rng = np.random.default_rng(7)
    p = dict(WEEKLY)
    W, S, M, L = p["W"], p["S"], p["M"], p["L"]
    T = 900
    idx = pd.date_range("2005-01-07", periods=T, freq="W-FRI")

    # (a) Sine wave in relative strength -> clean clockwise rotation
    t = np.arange(T)
    bench = pd.Series(100.0 * np.exp(0.0008 * t), index=idx)
    rel = 1.0 + 0.15 * np.sin(2 * np.pi * t / 120.0)
    sine = pd.DataFrame({"SINE": bench.to_numpy() * rel}, index=idx)
    f = compute_features(sine, bench, p)
    rr, rm = f["rs_ratio"]["SINE"].dropna(), f["rs_momentum"]["SINE"].dropna()
    print(f"\n(a) sine wave: rs_ratio mean={rr.mean():7.3f}  rs_momentum mean={rm.mean():7.3f}"
          f"   (both should sit near {CENTER:.0f})")

    q = f["quadrant"]["SINE"].dropna().to_numpy()
    trans = q[1:][q[1:] != q[:-1]]
    prev = q[:-1][q[1:] != q[:-1]]
    cw = int(np.sum((prev - trans) % 4 == 3))   # Leading->Weakening->Lagging->Improving
    ccw = int(np.sum((trans - prev) % 4 == 3))
    print(f"    quadrant transitions: {cw} clockwise vs {ccw} counter-clockwise"
          f"   -> {100*cw/max(cw+ccw,1):.0f}% clockwise")
    print(f"    straightness={f['straightness']['SINE'].dropna().mean():.3f} "
          f"vs random-walk null {straightness_null(L):.3f}")

    # (b) Pure GBM, zero relative drift -> the mechanical baseline
    N = 40
    steps = rng.normal(0.0, 0.02, size=(T, N))
    gbm = pd.DataFrame(100.0 * np.exp(np.cumsum(steps, axis=0)),
                       index=idx, columns=[f"S{i:02d}" for i in range(N)])
    gb = pd.Series(gbm.mean(axis=1).to_numpy(), index=idx)
    fg = compute_features(gbm, gb, p)
    st_g = fg["straightness"].to_numpy()
    st_g = st_g[np.isfinite(st_g)]
    qg = fg["quadrant"].to_numpy()
    qg = qg[np.isfinite(qg)]
    qgi = qg.astype(int)
    print(f"\n(b) random walk (NO real signal — this is the artefact baseline):")
    print(f"    straightness mean={st_g.mean():.3f}  vs random-walk null "
          f"{straightness_null(L):.3f}  -> smoothing inflates it by "
          f"{st_g.mean()/straightness_null(L):.1f}x")
    share = [100 * np.mean(qgi == k) for k in range(4)]
    print("    quadrant occupancy: " +
          "  ".join(f"{QUADRANTS[k]} {share[k]:.0f}%" for k in range(4)))
    run = fg["quadrant_run"].to_numpy()
    print(f"    median quadrant run length = {np.nanmedian(run):.0f} periods "
          f"(pure noise — any real number must beat this)")

    # (c) Degeneracy guards
    print("\n(c) degeneracy guards:")
    flat = pd.DataFrame({"FLAT": bench.to_numpy()}, index=idx)   # identical to benchmark
    ff = compute_features(flat, bench, p)
    n_ang = int(ff["angle_deg"]["FLAT"].notna().sum())
    n_flat = int((ff["is_flat"]["FLAT"] == 1.0).sum())
    print(f"    constant relative strength -> defined angles: {n_ang}, "
          f"flagged flat: {n_flat}  (atan2(0,0) must NOT become 'East')")
    assert n_ang == 0, "flat series produced a heading — atan2(0,0) guard failed"

    zero = np.zeros((5, 2))
    assert np.all(np.isnan(_guard_std(roll_std(zero, 3), np.zeros((5, 2))))), "std guard failed"
    print("    zero-variance rolling std -> NaN (not inf): OK")

    d = mahalanobis_distance(np.full((5, 2), 100.0), np.full((5, 2), 100.0), 3)
    assert np.all(np.isnan(d)), "singular covariance should give NaN"
    print("    singular covariance -> NaN: OK")

    b = burn_in(W, S, M)
    assert f["rs_momentum"].iloc[:b].isna().all().all(), "burn-in leaked"
    print(f"    burn-in of {b} periods dropped: OK")

    print("\nAll self-tests passed.")
    print("=" * 78)


if __name__ == "__main__":
    _self_test()
