"""
RRG Stats — the statistical toolkit, numpy-only
===============================================
Shared by rrg_null.py (synthetic baseline) and rrg_validate.py (real data) so
that every real-data number is produced by *exactly* the same code path as the
null it is compared against.

No scipy: statsmodels is broken in this environment (pandas-3 incompatibility)
and scipy is absent from requirements.txt, so anything that could end up in the
Streamlit page's import graph must be numpy + stdlib only.

Three things here exist to stop us fooling ourselves:

  newey_west_t   Sampling an H-day forward return every period makes the series
                 MA(H-1). Naive t-stats inflate by ~sqrt((2H^2+1)/(3H)):
                 3.7x at H=21, 6.5x at H=63. A headline "t = 3.5" on daily
                 63-day returns is an honest t = 0.54. This is by far the most
                 likely source of a false positive in this project.

  block_bootstrap_ci   Resamples whole DATES (keeping each date's entire
                 cross-section together) in blocks. Resampling (name, date)
                 pairs independently destroys both the cross-sectional and the
                 serial dependence and yields meaninglessly tight intervals --
                 the classic implementation bug in this class of test.

  deflated_sharpe   With ~1,000 specifications tried, E[max |t|] under the pure
                 null is ~3.0. |t| > 2 carries no information here.
"""

import math

import numpy as np

# ── Multiple-testing constants ───────────────────────────────────────────────
EULER_MASCHERONI = 0.5772156649015329


def norm_cdf(x):
    """Standard normal CDF via the stdlib error function (no scipy)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p):
    """Inverse standard normal CDF — Acklam's rational approximation (~1e-9)."""
    if not (0.0 < p < 1.0):
        return np.nan
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# ─────────────────────────────────────────────────────────────────────────────
# 1. RANKS AND CORRELATION
# ─────────────────────────────────────────────────────────────────────────────

def avg_rank(x):
    """
    Average ranks of the finite entries of a 1-D array; NaN stays NaN.

    argsort(argsort(x)) gives ORDINAL ranks and is wrong under ties. Prices
    rarely tie, but halted or flat names do, and the tie handling changes the
    correlation.
    """
    x = np.asarray(x, dtype=float)
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    v = x[ok]
    n = v.size
    if n == 0:
        return out
    order = np.argsort(v, kind="mergesort")
    sv = v[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sv[j + 1] == sv[i]:
            j += 1
        ranks[i:j + 1] = 0.5 * (i + j) + 1.0
        i = j + 1
    r = np.empty(n, dtype=float)
    r[order] = ranks
    out[ok] = r
    return out


def pearson(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return np.nan
    x, y = a[ok] - a[ok].mean(), b[ok] - b[ok].mean()
    d = math.sqrt(float(x @ x) * float(y @ y))
    return float(x @ y) / d if d > 0 else np.nan


def spearman(a, b):
    """Rank correlation with proper average-rank tie handling."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return np.nan
    return pearson(avg_rank(a[ok]), avg_rank(b[ok]))


def cross_sectional_ic(factor, fwd):
    """
    Rank IC per date. `factor` and `fwd` are (T, N) arrays aligned on dates.
    Returns a (T,) array of per-date Spearman correlations (NaN where n < 5).
    """
    factor = np.asarray(factor, dtype=float)
    fwd = np.asarray(fwd, dtype=float)
    T = factor.shape[0]
    out = np.full(T, np.nan)
    for t in range(T):
        ok = np.isfinite(factor[t]) & np.isfinite(fwd[t])
        if ok.sum() >= 5:
            out[t] = spearman(factor[t][ok], fwd[t][ok])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. STANDARD ERRORS THAT SURVIVE OVERLAPPING WINDOWS
# ─────────────────────────────────────────────────────────────────────────────

def newey_west_t(x, lag):
    """
    Mean, Newey-West t-stat and n for a (possibly autocorrelated) series.
    Bartlett kernel. Use lag = ceil(1.5 * H) for H-period overlapping returns.
    Returns (mean, t_stat, n_obs).
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = x.size
    if n < 5:
        return (np.nan, np.nan, n)
    mu = float(x.mean())
    e = x - mu
    lag = int(max(0, min(lag, n - 2)))
    s = float(e @ e) / n
    for l in range(1, lag + 1):
        g = float(e[l:] @ e[:-l]) / n
        s += 2.0 * (1.0 - l / (lag + 1.0)) * g
    if s <= 0:
        return (mu, np.nan, n)
    se = math.sqrt(s / n)
    return (mu, mu / se if se > 0 else np.nan, n)


def naive_t(x):
    """iid t-stat — reported only to show how large the overlap inflation is."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5 or x.std(ddof=1) == 0:
        return np.nan
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(x.size)))


def overlap_inflation(H):
    """Theoretical t inflation from sampling H-period returns every period."""
    return math.sqrt((2.0 * H * H + 1.0) / (3.0 * H))


def fama_macbeth(X_by_date, y_by_date, lag):
    """
    Fama-MacBeth: cross-sectional OLS per date, then Newey-West on the
    coefficient time series.

    X_by_date : list of (n_t, k) design matrices (WITHOUT intercept)
    y_by_date : list of (n_t,) targets
    Returns (coef_means, t_stats, coef_series) — each of length k (+1 intercept
    first).
    """
    rows = []
    for X, y in zip(X_by_date, y_by_date):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        ok = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        if ok.sum() < X.shape[1] + 3:
            continue
        Xd = np.column_stack([np.ones(ok.sum()), X[ok]])
        try:
            beta, *_ = np.linalg.lstsq(Xd, y[ok], rcond=None)
        except np.linalg.LinAlgError:
            continue
        rows.append(beta)
    if not rows:
        return np.array([]), np.array([]), np.empty((0, 0))
    coefs = np.vstack(rows)
    means = np.full(coefs.shape[1], np.nan)
    tstats = np.full(coefs.shape[1], np.nan)
    for j in range(coefs.shape[1]):
        m, t, _ = newey_west_t(coefs[:, j], lag)
        means[j], tstats[j] = m, t
    return means, tstats, coefs


def block_bootstrap_ci(date_values, block_len, n_boot=1000, alpha=0.05, seed=0):
    """
    Circular block bootstrap over DATES for the mean of a per-date statistic.

    `date_values` is a (T,) array of one number per date (e.g. that date's mean
    excess return or IC) — the whole cross-section must already be collapsed
    into it, so that resampling a date carries its cross-section intact.
    Block length should be >= 2H.
    """
    x = np.asarray(date_values, dtype=float)
    x = x[np.isfinite(x)]
    T = x.size
    if T < 10:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    b = int(max(1, min(block_len, T)))
    n_blocks = int(math.ceil(T / b))
    starts = rng.integers(0, T, size=(n_boot, n_blocks))
    offs = np.arange(b)
    idx = (starts[:, :, None] + offs[None, None, :]).reshape(n_boot, -1) % T
    means = x[idx[:, :T]].mean(axis=1)
    return (float(np.quantile(means, alpha / 2)),
            float(np.quantile(means, 1 - alpha / 2)))


def deflated_sharpe(sr, n_obs, n_trials, skew=0.0, kurt=3.0):
    """
    Bailey & Lopez de Prado deflated Sharpe ratio p-value.

    `sr` is the per-period Sharpe of the best configuration found; `n_trials`
    the number of specifications searched. Returns P(true SR > 0).
    """
    if not np.isfinite(sr) or n_obs < 10 or n_trials < 1:
        return np.nan
    e = 1.0 - EULER_MASCHERONI
    z1 = norm_ppf(1.0 - 1.0 / max(n_trials, 2))
    z2 = norm_ppf(1.0 - 1.0 / (max(n_trials, 2) * math.e))
    sr0 = (1.0 / math.sqrt(max(n_obs - 1, 1))) * (e * z1 + EULER_MASCHERONI * z2)
    denom = 1.0 - skew * sr + 0.25 * (kurt - 1.0) * sr * sr
    if denom <= 0:
        return np.nan
    return norm_cdf(((sr - sr0) * math.sqrt(max(n_obs - 1, 1))) / math.sqrt(denom))


def expected_max_t(n_trials):
    """E[max |t|] under the pure null over n_trials independent tries."""
    if n_trials < 2:
        return np.nan
    e = 1.0 - EULER_MASCHERONI
    return e * norm_ppf(1 - 1.0 / n_trials) + EULER_MASCHERONI * norm_ppf(1 - 1.0 / (n_trials * math.e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. EDGE DESCRIPTIVES
# ─────────────────────────────────────────────────────────────────────────────

def hit_rate(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.mean(x > 0)) if x.size else np.nan


def win_loss_ratio(x, min_losses=20):
    """
    R = mean(win) / |mean(loss)|.

    Returns NaN when there are too few losses. Without this guard R -> inf,
    Kelly = W - (1-W)/R -> W ~ 1.0, and the sizing code cheerfully recommends a
    100% position on a handful of observations.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    w, l = x[x > 0], x[x < 0]
    if l.size < min_losses or w.size < 5:
        return np.nan
    ml = abs(float(l.mean()))
    return float(w.mean()) / ml if ml > 0 else np.nan


def bucket_table(factor, fwd, n_buckets=10, edges=None, min_n=1):
    """
    Mean forward return by factor bucket — the "does more distance keep paying?"
    test. Pass trailing `edges` to avoid look-ahead; None uses in-sample
    quantiles (exploratory only).
    Returns (edges, dict of arrays keyed by bucket index).
    """
    f = np.asarray(factor, dtype=float).ravel()
    y = np.asarray(fwd, dtype=float).ravel()
    ok = np.isfinite(f) & np.isfinite(y)
    f, y = f[ok], y[ok]
    if f.size < n_buckets * min_n:
        return (edges, {})
    if edges is None:
        edges = np.quantile(f, np.linspace(0, 1, n_buckets + 1))
        edges[0], edges[-1] = -np.inf, np.inf
    idx = np.clip(np.searchsorted(edges, f, side="right") - 1, 0, len(edges) - 2)
    out = {}
    for b in range(len(edges) - 1):
        sel = y[idx == b]
        if sel.size:
            out[b] = sel
    return (edges, out)


def winsorize_rows(a, lo=0.01, hi=0.99):
    """Clip each row (date) at its own quantiles — one +150% name in 2020 will
    otherwise drive a whole coefficient. Keep the raw series for sizing."""
    a = np.asarray(a, dtype=float).copy()
    for t in range(a.shape[0]):
        row = a[t]
        ok = np.isfinite(row)
        if ok.sum() >= 10:
            ql, qh = np.quantile(row[ok], [lo, hi])
            a[t] = np.clip(row, ql, qh)
    return a


# ─────────────────────────────────────────────────────────────────────────────
# 4. SIZING
# ─────────────────────────────────────────────────────────────────────────────

def kelly_binary(W, R):
    """
    The formula as specified: Kelly% = W - (1-W)/R.

    NOTE ON UNITS: this returns a fraction of a bet unit whose LOSS is 1, not a
    portfolio weight. Divide by |mean loss| to get a wealth fraction — see
    kelly_wealth_fraction. Used directly as a weight it is off by a factor of
    1/|mean loss| (often 20-25x).
    """
    if not (np.isfinite(W) and np.isfinite(R)) or R <= 0:
        return np.nan
    return W - (1.0 - W) / R


def kelly_wealth_fraction(W, R, mean_loss):
    """Convert the binary Kelly output into an actual fraction of wealth."""
    k = kelly_binary(W, R)
    if not np.isfinite(k) or not np.isfinite(mean_loss) or abs(mean_loss) < 1e-9:
        return np.nan
    return k / abs(mean_loss)


def kelly_empirical(returns, f_max=5.0, n_grid=501):
    """
    Exact Kelly for the empirical return distribution: the f maximizing
    E[log(1 + f*r)]. Handles fat tails, always well-defined, and needs no
    normality or binary-outcome assumption.
    """
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 30:
        return np.nan
    worst = r.min()
    cap = f_max if worst >= 0 else min(f_max, 0.999 / abs(worst))
    if cap <= 0:
        return 0.0
    grid = np.linspace(0.0, cap, n_grid)
    g = np.array([np.mean(np.log1p(f * r)) for f in grid])
    g = np.where(np.isfinite(g), g, -np.inf)
    return float(grid[int(np.argmax(g))])


def kelly_continuous(mu, sigma):
    """f* = mu / sigma^2 for continuous returns."""
    if not (np.isfinite(mu) and np.isfinite(sigma)) or sigma <= 0:
        return np.nan
    return mu / (sigma * sigma)


def correlation_divisor(k, rho):
    """
    Multi-asset Kelly is f = inv(Sigma) @ mu. For k equal-correlation bets that
    collapses to dividing the single-asset Kelly by (1 + (k-1)*rho).

    k=5, rho=0.5 -> 3.0x reduction. k=10, rho=0.7 -> 7.3x. This is a far bigger
    adjustment than the 1/2-vs-1/4 Kelly decision, and omitting it is the single
    largest sizing error available.
    """
    if not np.isfinite(rho) or k < 1:
        return np.nan
    return max(1.0 + (k - 1) * rho, 1e-6)


def shrink_win_rate(w_bucket, n_bucket, w_pool, n0=100.0):
    """Shrink a noisy bucket win-rate toward the pooled estimate."""
    if not np.isfinite(w_bucket):
        return w_pool
    return (n_bucket * w_bucket + n0 * w_pool) / (n_bucket + n0)


def growth_fraction(f_over_fstar):
    """
    Share of maximum log-growth retained at f/f*:  2x - x^2.
    x=0.5 -> 0.75 of growth at 0.25 of the variance.
    x=0.25 -> 0.44 of growth at 0.0625 of the variance.
    x=2.0 -> EXACTLY ZERO growth. Overbetting is not a milder version of
    betting; it is ruin.
    """
    x = float(f_over_fstar)
    return 2.0 * x - x * x
