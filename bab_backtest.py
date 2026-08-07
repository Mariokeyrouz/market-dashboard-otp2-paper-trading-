"""
Betting-Against-Beta (BAB) — Frazzini-Pedersen rank-weighted, leverage-adjusted
=================================================================================
Long a rank-weighted low-beta portfolio, levered up to unit market beta; short
a rank-weighted high-beta portfolio, delevered down to unit market beta; both
funded/invested at the risk-free rate, so the combined book is (by
construction) beta-neutral and self-financing. Monthly rebalance, no forced
gate — this is a classical always-invested factor test, not the rule-gate
design used in sector_ls_backtest.py.

WHY THIS AND NOT QUALITY-MINUS-JUNK
-------------------------------------
QMJ needs a multi-decade panel of quality fundamentals (ROE, margins,
leverage) to backtest properly. This repo's fundamental-data pipeline
(op2_screener.py, factor_screener.py) only fetches TODAY's snapshot via
yfinance .info / last-3-years statements — the same "no historical
fundamentals" wall that sank eps_revision_backtest.py ("BI's Value and
Profitability sorts need 22 years of fundamentals, which are not obtainable
here"). BAB needs no fundamentals at all: beta is estimated purely from
trailing daily price history, so it is fully backtestable with the existing
momentum_experiments_daily price panel, full ~20-year history, right now.

WHY THIS IS A GENUINELY DIFFERENT TEST vs the two prior L/S failures
-----------------------------------------------------------------------
  cross_sectional_momentum_backtest.py: 12-1 momentum quintile spread,
    beta-neutral by a single scalar split. Sharpe -0.59.
  sector_ls_backtest.py: top-down sector-gated relative-strength rule.
    0/8 pre-registered criteria.
Both of those select on TREND (price having gone up or down). BAB selects on
BETA (sensitivity to the market), a structurally different characteristic —
its documented edge comes from leverage-constrained investors bidding up
high-beta names for the embedded leverage, not from momentum or reversion.

CONSTRUCTION (Frazzini & Pedersen 2014, JFE — "Betting Against Beta")
------------------------------------------------------------------------
At each rebalance date, for the cross-section of available betas b_i:
  rank_i = cross-sectional rank (1..n), z_i = rank_i - mean(rank)   [z sums to 0]
  S = sum(|z_i|) / 2                    (= sum of the positive z's)
  w_low_i  = max(-z_i, 0) / S           (nonzero, below-median beta only; sums to 1)
  w_high_i = max(+z_i, 0) / S           (nonzero, above-median beta only; sums to 1)
  beta_L = sum(w_low_i * b_i),  beta_H = sum(w_high_i * b_i)
  r_BAB  = (1/beta_L) * (r_low - rf) - (1/beta_H) * (r_high - rf)
where r_low, r_high are the (unlevered) portfolio raw returns of each leg.
This is the published formula exactly — each leg is levered/delevered to unit
beta, funded/invested at the risk-free rate, making the combined book
self-financing and (by construction) beta-neutral.

SIMPLIFICATIONS FROM THE PUBLISHED PAPER (stated explicitly)
-----------------------------------------------------------------
  - Beta shrinkage (Vasicek-style, beta_shrunk = shrink*beta_raw + (1-shrink)*1.0)
    uses a fixed shrink factor per run, swept in the parameter surface rather
    than estimated cross-sectionally per name.
  - Risk-free rate is the repo's existing flat 3%/yr convention (RFR, same as
    every other backtest here), not a daily T-bill series — this affects the
    ABSOLUTE return level only; the cross-sectional ranking and realized
    spread are driven by price changes, not the rf level, so this is a low-
    risk simplification.
  - Monthly rebalance (vs the paper's monthly-with-daily-rebalanced-weights);
    weights are held fixed between rebalances here, matching every other
    monthly-rebalanced script in this repo.

SURVIVORSHIP BIAS
------------------
Universe is momentum_daily_prices.csv (today's S&P 500 backfilled — see
cross_sectional_momentum_backtest.py's docstring for the full delisting-gap
argument). The channel here is weaker than for a pure "worst recent
performer" short leg — beta is a risk characteristic, not a performance
rank — but distressed companies often carry elevated beta shortly before
delisting, so the high-beta leg's return is still a plausible upper bound.

COSTS (restated, not imported, per repo convention)
------------------------------------------------------
  Commission + slippage : 10 bps one-way on turnover, applied to the EFFECTIVE
                           (levered) weights — a turnover of 1.0 in leveraged-
                           weight space costs the same bps regardless of the
                           leverage ratio, correctly pricing the larger
                           notional actually traded.
  Stress cost            : 20 bps one-way, explicit robustness arm
  Short-leg borrow       : 30 bps/year on the effective (levered) short
                            notional, accrued monthly

Outputs: bab_results.csv, bab_surface.csv, bab_curve.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py bab_backtest.py
"""

import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")   # Windows console is cp1252

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

import momentum_experiments_daily as med   # load_daily() — existing loader, reused as-is
import rrg_stats as rs                     # newey_west_t, naive_t

BENCHMARK = "SPY"

BETA_LOOKBACK = 252              # trading days, rolling beta vs SPY
SHRINK = 0.6                     # Vasicek-style: beta_shrunk = SHRINK*raw + (1-SHRINK)*1.0
REBAL_MONTHS = 1
MIN_NAMES = 20                   # minimum cross-section to form legs this month

RFR = 0.03
COST_BPS = 10.0
COST_BPS_STRESS = 20.0
BORROW_BPS_ANNUAL = 30.0
VOL_MATCH_WINDOW = 6
VOL_SCALE_CAP = 3.0

BASE_PARAMS = dict(lookback=BETA_LOOKBACK, shrink=SHRINK, rebal_months=REBAL_MONTHS,
                    cost_bps=COST_BPS, borrow_bps_annual=BORROW_BPS_ANNUAL)

# Parameter sweep (report the surface, never the best cell)
LOOKBACKS = (126, 252, 500)
SHRINKS = (0.4, 0.6, 0.8)
REBAL_GRID = (1, 3)


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_universe():
    px = med.load_daily()
    px.index = pd.to_datetime(px.index).tz_localize(None)
    spy = px[BENCHMARK] if BENCHMARK in px.columns else None
    stocks = px.drop(columns=[BENCHMARK], errors="ignore")
    stocks = stocks.dropna(axis=1, how="all")
    print(f"Data source: momentum_experiments_daily.load_daily() (yfinance, auto_adjust=True). "
          f"Universe: {stocks.shape[1]} tickers (today's S&P 500), "
          f"{stocks.index.min().date()} -> {stocks.index.max().date()}")
    return stocks, spy


def rolling_beta_panel(daily_ret, spy_daily_ret, window):
    """Closed-form rolling OLS beta per column vs SPY: Cov(stock,spy)_t / Var(spy)_t."""
    cov = daily_ret.rolling(window).cov(spy_daily_ret)
    var = spy_daily_ret.rolling(window).var()
    return cov.div(var, axis=0)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SIGNAL / PORTFOLIO CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def rank_weighted_legs(beta_row, min_names=MIN_NAMES):
    """Frazzini-Pedersen rank weights: w_low/w_high each sum to 1, nonzero only
    below/above the cross-sectional median beta respectively."""
    b = beta_row.dropna()
    if len(b) < min_names:
        return pd.Series(dtype=float), pd.Series(dtype=float), np.nan, np.nan
    ranks = b.rank(method="average")
    z = ranks - ranks.mean()
    S = z.abs().sum() / 2.0
    if S <= 0:
        return pd.Series(dtype=float), pd.Series(dtype=float), np.nan, np.nan
    w_low = (-z).clip(lower=0) / S
    w_high = z.clip(lower=0) / S
    beta_L = float((w_low * b).sum())
    beta_H = float((w_high * b).sum())
    return w_low, w_high, beta_L, beta_H


def build_bab(px_m, ret_m, beta_panel_m, cost_bps, borrow_bps_annual, rf_m,
              rebal_months=1, min_names=MIN_NAMES, start=None):
    dates = beta_panel_m.index
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    eq_bab, eq_low, eq_high = 100.0, 100.0, 100.0
    curve_bab, curve_low, curve_high = {}, {}, {}
    w_low_raw, w_high_raw = pd.Series(dtype=float), pd.Series(dtype=float)      # unlevered, sum to 1
    w_low_eff, w_high_eff = pd.Series(dtype=float), pd.Series(dtype=float)      # levered, actual traded notional
    beta_L, beta_H = np.nan, np.nan
    log, k = [], 0
    borrow_m = borrow_bps_annual / 1e4 / 12.0

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        if k % rebal_months == 0:
            w_low_raw, w_high_raw, beta_L, beta_H = rank_weighted_legs(beta_panel_m.loc[t], min_names)
            tgt_low_eff = (w_low_raw / beta_L) if (len(w_low_raw) and beta_L and beta_L > 0) else pd.Series(dtype=float)
            tgt_high_eff = (w_high_raw / beta_H) if (len(w_high_raw) and beta_H and beta_H > 0) else pd.Series(dtype=float)

            all_l = w_low_eff.index.union(tgt_low_eff.index)
            turn_l = float((tgt_low_eff.reindex(all_l).fillna(0.0) - w_low_eff.reindex(all_l).fillna(0.0)).abs().sum())
            all_h = w_high_eff.index.union(tgt_high_eff.index)
            turn_h = float((tgt_high_eff.reindex(all_h).fillna(0.0) - w_high_eff.reindex(all_h).fillna(0.0)).abs().sum())
            eq_bab *= (1.0 - (turn_l + turn_h) * cost_bps / 1e4)
            w_low_eff, w_high_eff = tgt_low_eff, tgt_high_eff
            log.append({"date": t, "n": len(w_low_raw) + len(w_high_raw), "beta_L": beta_L, "beta_H": beta_H,
                        "n_low": len(w_low_raw), "n_high": len(w_high_raw),
                        "gross_low_eff": float(w_low_eff.sum()) if len(w_low_eff) else 0.0,
                        "gross_high_eff": float(w_high_eff.sum()) if len(w_high_eff) else 0.0,
                        "turnover_low": turn_l, "turnover_high": turn_h})
        k += 1

        r_low = float((w_low_raw * ret_m.loc[t1].reindex(w_low_raw.index).fillna(0.0)).sum()) if len(w_low_raw) else 0.0
        r_high = float((w_high_raw * ret_m.loc[t1].reindex(w_high_raw.index).fillna(0.0)).sum()) if len(w_high_raw) else 0.0
        short_gross_eff = float(w_high_eff.sum()) if len(w_high_eff) else 0.0

        r_bab = 0.0
        if len(w_low_eff):
            r_bab += (1.0 / beta_L) * (r_low - rf_m)
        if len(w_high_eff):
            r_bab -= (1.0 / beta_H) * (r_high - rf_m)

        eq_low *= (1.0 + r_low)      # informational: raw, unlevered low-beta leg
        eq_high *= (1.0 + r_high)    # informational: raw, unlevered high-beta leg
        eq_bab *= (1.0 + r_bab - short_gross_eff * borrow_m)

        curve_low[t1], curve_high[t1], curve_bab[t1] = eq_low, eq_high, eq_bab

    return (pd.Series(curve_bab).sort_index(), pd.Series(curve_low).sort_index(),
            pd.Series(curve_high).sort_index(), pd.DataFrame(log))


def matched_vol_long_only(long_curve, ls_curve, window=VOL_MATCH_WINDOW, cap=VOL_SCALE_CAP):
    """Scales the raw low-beta leg's own trailing vol to match the BAB book's,
    for an apples-to-apples Sharpe comparison — same construction as
    cross_sectional_momentum_backtest.matched_vol_long_only()."""
    r_long = long_curve.pct_change()
    r_ls = ls_curve.pct_change()
    target_vol = r_ls.rolling(window).std() * np.sqrt(12)
    long_vol = r_long.rolling(window).std() * np.sqrt(12)
    scale = (target_vol / long_vol).clip(upper=cap).shift(1).fillna(1.0)
    vr = r_long * scale
    return 100.0 * (1.0 + vr.fillna(0.0)).cumprod()


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


def beta_corr_vs_spy(strat_ret_m, spy_ret_m):
    aligned = pd.concat([strat_ret_m.rename("strat"), spy_ret_m.rename("spy")], axis=1).dropna()
    if len(aligned) < 12:
        return np.nan, np.nan
    var = aligned["spy"].var()
    beta = aligned["strat"].cov(aligned["spy"]) / var if var > 0 else np.nan
    return float(beta), float(aligned["strat"].corr(aligned["spy"]))


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
# 4. WALK-FORWARD / PARAMETER SURFACE
# ─────────────────────────────────────────────────────────────────────────────

def run_full(px_m, ret_m, beta_panel_m, params, rf_m, start=None):
    return build_bab(px_m, ret_m, beta_panel_m, params["cost_bps"], params["borrow_bps_annual"],
                      rf_m, rebal_months=params["rebal_months"], start=start)


def walk_forward(px_m, ret_m, beta_panel_m, params, rf_m):
    me = beta_panel_m.index
    mid = me[len(me) // 2]
    is_bab, is_low, _, _ = run_full(px_m.loc[:mid], ret_m.loc[:mid], beta_panel_m.loc[:mid], params, rf_m)
    oos_bab, oos_low, _, _ = run_full(px_m.loc[mid:], ret_m.loc[mid:], beta_panel_m.loc[mid:], params, rf_m)
    return {"is": metrics(is_bab, f"IS  ({is_bab.index[0].date() if len(is_bab) else '?'}+)"),
            "oos": metrics(oos_bab, f"OOS ({oos_bab.index[0].date() if len(oos_bab) else '?'}+)")}


def parameter_sweep(px, spy, ret_m_cache, px_m, rf_m):
    rows = []
    daily_ret_full = px.pct_change()
    spy_daily_ret = spy.pct_change()
    for lb in LOOKBACKS:
        beta_panel = rolling_beta_panel(daily_ret_full, spy_daily_ret, lb)
        for shr in SHRINKS:
            beta_shrunk = shr * beta_panel + (1 - shr) * 1.0
            beta_panel_m = beta_shrunk.reindex(px_m.index, method="ffill")
            for rb in REBAL_GRID:
                p = dict(BASE_PARAMS, rebal_months=rb)
                bab, _, _, _ = run_full(px_m, ret_m_cache, beta_panel_m, p, rf_m)
                m = metrics(bab, "")
                r = bab.pct_change().dropna().values
                _, t_nw, _ = rs.newey_west_t(r, lag=1)
                rows.append({"lookback": lb, "shrink": shr, "rebal_months": rb,
                             "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"],
                             "max_dd_pct": m["max_dd_pct"], "t_nw": t_nw})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("BETTING-AGAINST-BETA — rank-weighted, leverage-adjusted to unit beta each leg")
    print("Frazzini-Pedersen (2014) construction. Purely price-based (no fundamentals needed) —")
    print("sidesteps the historical-fundamentals gap that blocked a Quality-minus-Junk backtest.")
    print("PAPER-TESTING RESEARCH ONLY. Two prior long/short attempts here both failed:")
    print("  cross_sectional_momentum_backtest.py: Sharpe -0.59")
    print("  sector_ls_backtest.py: 0/8 pre-registered criteria")
    print("!" * 74)
    print("SURVIVORSHIP-BIASED universe (today's S&P 500 backfilled) — read RELATIVE differences.")
    print("!" * 74)

    px, spy = load_universe()
    if spy is None:
        raise RuntimeError("SPY not found in the price panel — cannot benchmark.")

    px_m = px.resample("ME").last()
    spy_m = spy.resample("ME").last()
    ret_m = px_m.pct_change()
    spy_ret_m = spy_m.pct_change()
    rf_m = RFR / 12.0

    daily_ret = px.pct_change()
    spy_daily_ret = spy.pct_change()
    print(f"\nComputing rolling {BETA_LOOKBACK}d beta vs SPY for {px.shape[1]} names...", flush=True)
    beta_panel = rolling_beta_panel(daily_ret, spy_daily_ret, BETA_LOOKBACK)
    beta_shrunk = SHRINK * beta_panel + (1 - SHRINK) * 1.0
    beta_panel_m = beta_shrunk.reindex(px_m.index, method="ffill")

    print(f"Monthly window: {px_m.index[0].date()} -> {px_m.index[-1].date()} ({len(px_m)} months)")

    banner(f"BASE CONFIG — lookback={BETA_LOOKBACK}d, shrink={SHRINK}, monthly rebal, "
           f"min {MIN_NAMES} names/side")
    bab, low_c, high_c, log = run_full(px_m, ret_m, beta_panel_m, BASE_PARAMS, rf_m)
    matched_vol = matched_vol_long_only(low_c, bab)
    spy_curve = buy_hold(spy_m, bab.index)

    results = [metrics(bab, "BAB (beta-neutral, self-financing)"),
               metrics(low_c, "Low-beta leg (raw, unlevered, informational)"),
               metrics(high_c, "High-beta leg (raw, unlevered, informational)"),
               metrics(matched_vol, "Low-beta leg, vol-matched to BAB"),
               metrics(spy_curve, "SPY buy & hold")]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"] for r in results],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $100"],
          [45, 8, 8, 8, 8, 8, 11])

    avg_beta_L = log["beta_L"].mean()
    avg_beta_H = log["beta_H"].mean()
    avg_n = log["n"].mean()
    avg_turn = (log["turnover_low"].mean() + log["turnover_high"].mean()) / 2.0
    beta_ex_post, corr = beta_corr_vs_spy(bab.pct_change().dropna(), spy_ret_m)
    _, t_nw, n_obs = rs.newey_west_t(bab.pct_change().dropna().values, lag=1)
    t_naive = rs.naive_t(bab.pct_change().dropna().values)

    print(f"\nMonths: {n_obs}   Avg beta_L={fmt(avg_beta_L,2)}  beta_H={fmt(avg_beta_H,2)}  "
          f"avg cross-section n={avg_n:.0f}   Avg turnover/leg/rebal: {avg_turn:.2f}")
    print(f"Ex-post beta vs SPY: {fmt(beta_ex_post,3)} (should be near 0 if the leverage "
          f"adjustment is doing its job)   Correlation vs SPY: {fmt(corr,3)}")
    print(f"Significance — monthly BAB returns, naive t (n={n_obs}): t={fmt(t_naive,2)}   "
          f"| Newey-West (lag=1, sanity check): t={fmt(t_nw,2)}")
    print("(Monthly rebalancing already samples one non-overlapping observation per period, so the")
    print(" naive t-stat is the legitimate headline per CLAUDE.md; NW lag=1 checks for mild month-end drift.)")

    stress_params = dict(BASE_PARAMS, cost_bps=COST_BPS_STRESS)
    stress_bab, _, _, _ = run_full(px_m, ret_m, beta_panel_m, stress_params, rf_m)
    stress_cagr = metrics(stress_bab, "")["cagr_pct"]
    print(f"\nCost stress ({COST_BPS_STRESS:.0f}bps one-way): CAGR {stress_cagr:+.2f}% "
          f"(base {results[0]['cagr_pct']:+.2f}%)")

    banner("WALK-FORWARD — first half (IS) vs second half (OOS), base config")
    wf = walk_forward(px_m, ret_m, beta_panel_m, BASE_PARAMS, rf_m)
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%"),
            f"${r['final']:.0f}"] for r in [wf["is"], wf["oos"]]],
          ["Period", "CAGR", "Sharpe", "MaxDD", "Final $100"], [30, 8, 8, 8, 11])

    print(f"\nRunning parameter surface ({len(LOOKBACKS)*len(SHRINKS)*len(REBAL_GRID)} cells: "
          f"lookback x shrink x rebal_months)...", flush=True)
    surf = parameter_sweep(px, spy, ret_m, px_m, rf_m)
    surf.to_csv("bab_surface.csv", index=False)
    sc = surf["cagr_pct"].dropna()
    tc = surf["t_nw"].dropna()
    banner("PARAMETER SURFACE — median / range / sign agreement, never the best cell")
    print(f"CAGR%  — median {fmt(sc.median(),2)}  mean {fmt(sc.mean(),2)}  "
          f"min {fmt(sc.min(),2)}  max {fmt(sc.max(),2)}  sign+ {(sc>0).mean()*100:.0f}% of {len(sc)} cells")
    print(f"t_nw   — median {fmt(tc.median(),2)}  sign agreement {max((tc>0).mean(),(tc<0).mean())*100:.0f}%")

    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=5/7 to pass)")
    base_m = results[0]
    mv_m = results[3]
    oos_m = wf["oos"]
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (base config, full sample)",
         base_m["cagr_pct"] > 0, f"{base_m['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps stress cost (still net positive CAGR)",
         stress_cagr > 0, f"{stress_cagr:+.2f}%"),
        (3, True, "Walk-forward OOS half still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "BAB Sharpe beats the vol-matched low-beta-only baseline",
         (not np.isnan(base_m["sharpe"])) and (not np.isnan(mv_m["sharpe"])) and base_m["sharpe"] > mv_m["sharpe"],
         f"BAB {fmt(base_m['sharpe'],3)} vs vol-matched low-beta {fmt(mv_m['sharpe'],3)}"),
        (5, False, "Parameter-surface median cell CAGR > 0",
         sc.median() > 0, f"median {sc.median():+.2f}%"),
        (6, False, "Parameter-surface sign agreement >= 70% of cells positive",
         (sc > 0).mean() >= 0.70, f"{(sc > 0).mean() * 100:.0f}% of {len(sc)} cells"),
        (7, False, "Naive t-stat on monthly BAB returns |t| >= 3",
         (not np.isnan(t_naive)) and abs(t_naive) >= 3, f"t={fmt(t_naive, 2)}"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:56], det[:44]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 56, 44])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 5 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/7 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — survived its own pre-registered bar; still only PAPER-testing evidence, not a live-trading"
        " recommendation, and the short-leg survivorship-bias caveat above still applies." if verdict == "PASS"
        else " — report the null and stop. This does not mean BAB never works, only that this specific"
             " specification did not clear its own bar over this survivorship-biased sample."))
    print("=" * 100)

    pd.DataFrame(results).to_csv("bab_results.csv", index=False)
    curves = pd.DataFrame({"bab": bab, "low_beta_raw": low_c, "high_beta_raw": high_c,
                            "matched_vol": matched_vol, "spy": spy_curve})
    curves.to_csv("bab_curve.csv")
    print(f"\nWrote bab_results.csv, bab_surface.csv, bab_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
