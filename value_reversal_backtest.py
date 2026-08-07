"""
Value proxy via long-term reversal — 60-12 formation, monthly rebalance
==========================================================================
True value (book-to-market, earnings yield) needs decades of historical
fundamentals this repo does not have — the same wall documented in
eps_revision_backtest.py and in bab_backtest.py's docstring (yfinance only
exposes today's snapshot / last-3-years statements, no historical panel).

This uses a PRICE-ONLY PROXY instead: long-term price reversal (De Bondt &
Thaler 1985) — rank stocks by their trailing 60-month return, EXCLUDING the
most recent 12 months, and go long the biggest past LOSERS / short the
biggest past WINNERS. Long-horizon losers tend to be statistically cheap
(price has fallen relative to a slowly-adjusting fundamental value), which is
the closest a price-only signal can get to "value" — but it is a proxy, not a
replication, and that distinction matters for what a positive or negative
result here would actually mean.

WHY THE 12-MONTH SKIP
------------------------
cross_sectional_momentum_backtest.py already tested 12-1 momentum (formation
11-12mo, most recent month excluded) and it failed (Sharpe -0.59). Long-term
reversal is formed over 36-60 months; excluding the most recent 12 months is
the standard construction (not a tuning choice) and it also reduces mechanical
overlap with that already-tested medium-term momentum signal. This script
explicitly measures the correlation between the two signals' long-short
returns (criterion 8 below) — if this "value" proxy turns out to just be
inverted momentum wearing a different name, that is itself the finding.

CONSTRUCTION — identical machinery to cross_sectional_momentum_backtest.py
------------------------------------------------------------------------------
Same beta-neutral long/short construction, same cost model, same pre-
registered-criteria pattern. Restated (not imported) per repo convention, with
the score definition and lookback/skip windows changed to a value orientation:

  score = -(price return over the trailing LOOKBACK_M months, ending SKIP_M
            months ago)

Long the top quintile of `score` (biggest past losers), short the bottom
quintile (biggest past winners). Each leg equal-weighted; gross split between
legs by inverse average trailing beta (beta-neutral, gross exposure constant
at 1.0) — same as the momentum script.

SURVIVORSHIP BIAS — universe is TODAY's S&P 500 backfilled, same caveat as
cross_sectional_momentum_backtest.py: absolute return levels are an upper
bound, read RELATIVE differences. The delisting gap is, if anything, WORSE
for a long-term-loser strategy than for a 12-1 momentum strategy: a genuine
multi-year loser is more likely to have been delisted/acquired/gone bankrupt
before its 60-month formation window would even complete, so real historical
"biggest losers" are the names most systematically absent from this panel —
worse than the equivalent bias already documented for the short leg of the
momentum test.

COSTS (restated, not imported)
--------------------------------
  Commission + slippage : 10 bps one-way on turnover
  Stress cost            : 20 bps one-way, explicit robustness arm
  Short-leg borrow       : 30 bps/year, accrued monthly on short notional

Outputs: value_reversal_results.csv, value_reversal_surface.csv,
         value_reversal_curve.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py value_reversal_backtest.py
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
MOMENTUM_CURVE_CACHE = "cross_sectional_momentum_curve.csv"   # for the distinctiveness check

LOOKBACK_M = 60
SKIP_M = 12
GROUP_FRAC = 0.20
REBAL_MONTHS = 1

RFR = 0.03
COST_BPS = 10.0
COST_BPS_STRESS = 20.0
BORROW_BPS_ANNUAL = 30.0
BETA_LOOKBACK = 252
BETA_SCALE_CLAMP = (0.2, 5.0)
VOL_MATCH_WINDOW = 6
VOL_SCALE_CAP = 3.0

BASE_PARAMS = dict(lookback=LOOKBACK_M, skip=SKIP_M, group_frac=GROUP_FRAC,
                    rebal_months=REBAL_MONTHS, cost_bps=COST_BPS,
                    borrow_bps_annual=BORROW_BPS_ANNUAL, beta_neutral=True)

# Parameter sweep (report the surface, never the best cell)
LOOKBACKS = (36, 48, 60)
SKIPS = (6, 12)
GROUP_FRACS = (0.10, 0.20)


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


# ─────────────────────────────────────────────────────────────────────────────
# 2. SIGNAL
# ─────────────────────────────────────────────────────────────────────────────

def value_signal(px_m, lookback=LOOKBACK_M, skip=SKIP_M):
    """Long-term reversal score: NEGATIVE of the `lookback`-month return ending
    `skip` months ago. High score = biggest past loser = value candidate."""
    return -(px_m.shift(skip) / px_m.shift(lookback + skip) - 1.0)


def rolling_beta_panel(daily_ret, spy_daily_ret, window=BETA_LOOKBACK):
    cov = daily_ret.rolling(window).cov(spy_daily_ret)
    var = spy_daily_ret.rolling(window).var()
    return cov.div(var, axis=0)


def rank_groups(s, group_frac):
    s = s.dropna()
    if len(s) < 20:
        return [], []
    k = max(1, int(round(len(s) * group_frac)))
    return list(s.nlargest(k).index), list(s.nsmallest(k).index)


# ─────────────────────────────────────────────────────────────────────────────
# 3. PORTFOLIO CONSTRUCTION — identical to cross_sectional_momentum_backtest.py
# ─────────────────────────────────────────────────────────────────────────────

def build_long_short(px_m, ret_m, scores, group_frac, cost_bps, borrow_bps_annual,
                      beta_neutral=True, beta_panel_m=None, rebal_months=1, start=None):
    dates = scores.index
    if start is not None:
        dates = dates[dates >= pd.Timestamp(start)]
    eq_ls, eq_long, eq_short = 100.0, 100.0, 100.0
    curve_ls, curve_long, curve_short = {}, {}, {}
    w_long, w_short = pd.Series(dtype=float), pd.Series(dtype=float)
    log, k = [], 0
    borrow_m = borrow_bps_annual / 1e4 / 12.0

    for i in range(len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        if k % rebal_months == 0:
            s = scores.loc[t].dropna()
            longs, shorts = rank_groups(s, group_frac)
            tgt_l = pd.Series(1.0 / len(longs), index=longs) if longs else pd.Series(dtype=float)
            tgt_s = pd.Series(1.0 / len(shorts), index=shorts) if shorts else pd.Series(dtype=float)

            long_frac, short_frac, scale = 0.5, 0.5, np.nan
            if beta_neutral and beta_panel_m is not None and len(tgt_l) and len(tgt_s):
                bl = beta_panel_m.loc[t, tgt_l.index].mean()
                bs = beta_panel_m.loc[t, tgt_s.index].mean()
                if pd.notna(bl) and pd.notna(bs) and bs != 0:
                    scale = float(np.clip(bl / bs, *BETA_SCALE_CLAMP))
                    long_frac, short_frac = 1.0 / (1.0 + scale), scale / (1.0 + scale)

            all_l = w_long.index.union(tgt_l.index)
            turn_l = float((tgt_l.reindex(all_l).fillna(0.0) - w_long.reindex(all_l).fillna(0.0)).abs().sum())
            all_s = w_short.index.union(tgt_s.index)
            turn_s = float((tgt_s.reindex(all_s).fillna(0.0) - w_short.reindex(all_s).fillna(0.0)).abs().sum())
            eq_long *= (1.0 - turn_l * cost_bps / 1e4)
            eq_short *= (1.0 - turn_s * cost_bps / 1e4)
            w_long, w_short = tgt_l, tgt_s
            log.append({"date": t, "n_long": len(tgt_l), "n_short": len(tgt_s),
                        "long_frac": long_frac, "short_frac": short_frac,
                        "beta_scale": scale, "turnover_long": turn_l, "turnover_short": turn_s})
        else:
            long_frac, short_frac = log[-1]["long_frac"], log[-1]["short_frac"]
        k += 1

        r_long = float((w_long * ret_m.loc[t1].reindex(w_long.index).fillna(0.0)).sum()) if len(w_long) else 0.0
        r_short = float((w_short * ret_m.loc[t1].reindex(w_short.index).fillna(0.0)).sum()) if len(w_short) else 0.0

        eq_long *= (1.0 + r_long)
        eq_short *= (1.0 + r_short - borrow_m)
        eq_ls *= (1.0 + long_frac * r_long - short_frac * r_short - short_frac * borrow_m)

        curve_long[t1], curve_short[t1], curve_ls[t1] = eq_long, eq_short, eq_ls

        if len(w_long):
            w_long = w_long * (1.0 + ret_m.loc[t1].reindex(w_long.index).fillna(0.0))
            w_long = w_long / w_long.sum()
        if len(w_short):
            w_short = w_short * (1.0 + ret_m.loc[t1].reindex(w_short.index).fillna(0.0))
            w_short = w_short / w_short.sum()

    return (pd.Series(curve_ls).sort_index(), pd.Series(curve_long).sort_index(),
            pd.Series(curve_short).sort_index(), pd.DataFrame(log))


def matched_vol_long_only(long_curve, ls_curve, window=VOL_MATCH_WINDOW, cap=VOL_SCALE_CAP):
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
# 4. STATS / REPORTING
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
# 5. WALK-FORWARD / PARAMETER SURFACE
# ─────────────────────────────────────────────────────────────────────────────

def run_full(px_m, ret_m, beta_panel_m, params, start=None):
    scores = value_signal(px_m, params["lookback"], params["skip"])
    return build_long_short(px_m, ret_m, scores, params["group_frac"], params["cost_bps"],
                             params["borrow_bps_annual"], beta_neutral=params["beta_neutral"],
                             beta_panel_m=beta_panel_m, rebal_months=params["rebal_months"], start=start)


def walk_forward(px_m, ret_m, beta_panel_m, params):
    me = px_m.index
    mid = me[len(me) // 2]
    is_ls, _, _, _ = run_full(px_m.loc[:mid], ret_m.loc[:mid], beta_panel_m, params)
    oos_ls, _, _, _ = run_full(px_m.loc[mid:], ret_m.loc[mid:], beta_panel_m, params)
    return {"is": metrics(is_ls, f"IS  ({is_ls.index[0].date() if len(is_ls) else '?'}+)"),
            "oos": metrics(oos_ls, f"OOS ({oos_ls.index[0].date() if len(oos_ls) else '?'}+)")}


def parameter_sweep(px_m, ret_m, beta_panel_m):
    rows = []
    for gf in GROUP_FRACS:
        for lb in LOOKBACKS:
            for sk in SKIPS:
                p = dict(BASE_PARAMS, group_frac=gf, lookback=lb, skip=sk)
                ls, _, _, _ = run_full(px_m, ret_m, beta_panel_m, p)
                m = metrics(ls, "")
                r = ls.pct_change().dropna().values
                _, t_nw, _ = rs.newey_west_t(r, lag=1)
                rows.append({"group_frac": gf, "lookback": lb, "skip": sk,
                             "cagr_pct": m["cagr_pct"], "sharpe": m["sharpe"],
                             "max_dd_pct": m["max_dd_pct"], "t_nw": t_nw})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# 6. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("VALUE PROXY (LONG-TERM REVERSAL) — 60-12 formation, monthly rebalance, beta-neutral")
    print("PRICE-ONLY proxy for value (true book-to-market unavailable — see docstring).")
    print("PAPER-TESTING RESEARCH ONLY. Prior long/short attempts here:")
    print("  cross_sectional_momentum_backtest.py: Sharpe -0.59")
    print("  sector_ls_backtest.py: 0/8 pre-registered criteria")
    print("  bab_backtest.py: 0/7 pre-registered criteria (beta sign-flipped in this sample)")
    print("!" * 74)
    print("SURVIVORSHIP-BIASED universe (today's S&P 500 backfilled) — read RELATIVE differences.")
    print("Delisting gap likely WORSE here than for 12-1 momentum: real multi-year losers are the")
    print("names most likely to have been delisted before a 60-month window could even complete.")
    print("!" * 74)

    px, spy = load_universe()
    if spy is None:
        raise RuntimeError("SPY not found in the price panel — cannot benchmark.")

    px_m = px.resample("ME").last()
    spy_m = spy.resample("ME").last()
    ret_m = px_m.pct_change()

    daily_ret = px.pct_change()
    spy_daily_ret = spy.pct_change()
    print(f"\nComputing rolling {BETA_LOOKBACK}d beta vs SPY for {px.shape[1]} names...", flush=True)
    beta_panel = rolling_beta_panel(daily_ret, spy_daily_ret, BETA_LOOKBACK)
    beta_panel_m = beta_panel.reindex(px_m.index, method="ffill")

    print(f"\nMonthly window: {px_m.index[0].date()} -> {px_m.index[-1].date()} ({len(px_m)} months)")

    banner(f"BASE CONFIG — lookback={LOOKBACK_M}-{SKIP_M}, quintile ({GROUP_FRAC:.0%}), monthly rebal, beta-neutral")
    ls, long_c, short_c, log = run_full(px_m, ret_m, beta_panel_m, BASE_PARAMS)
    matched_vol = matched_vol_long_only(long_c, ls)
    spy_curve = buy_hold(spy_m, ls.index)

    results = [metrics(ls, "Long-short (beta-neutral, value proxy)"), metrics(long_c, "Long leg (losers) only"),
               metrics(short_c, "Short leg (winners) only"), metrics(matched_vol, "Long-only, vol-matched to LS"),
               metrics(spy_curve, "SPY buy & hold")]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"] for r in results],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $100"],
          [40, 8, 8, 8, 8, 8, 11])

    rstat_r = ls.pct_change().dropna()
    avg_turn = (log["turnover_long"].mean() + log["turnover_short"].mean()) / 2.0
    avg_n_long, avg_n_short = log["n_long"].mean(), log["n_short"].mean()
    _, t_nw, n_obs = rs.newey_west_t(rstat_r.values, lag=1)
    t_naive = rs.naive_t(rstat_r.values)

    print(f"\nMonths: {len(rstat_r)}   Universe/rebal: {avg_n_long:.0f} long / {avg_n_short:.0f} short   "
          f"Avg turnover/leg/rebal: {avg_turn:.2f}")
    print(f"Naive t (n={n_obs}): {fmt(t_naive,2)}   | Newey-West (lag=1, sanity check): {fmt(t_nw,2)}")

    # ── distinctiveness vs the already-tested momentum spread ──────────────
    banner("DISTINCTIVENESS CHECK — is this just inverted 12-1 momentum wearing a different name?")
    corr_mom = np.nan
    try:
        mom_curve = pd.read_csv(MOMENTUM_CURVE_CACHE, index_col=0, parse_dates=True).iloc[:, 0]
        mom_ret = mom_curve.pct_change().dropna()
        aligned = pd.concat([rstat_r.rename("value_proxy"), mom_ret.rename("momentum")], axis=1).dropna()
        if len(aligned) >= 24:
            corr_mom = float(aligned["value_proxy"].corr(aligned["momentum"]))
            print(f"  Correlation of monthly L/S returns vs cross_sectional_momentum_backtest.py's "
                  f"12-1 spread: {corr_mom:+.3f}  (n={len(aligned)} overlapping months)")
        else:
            print(f"  Only {len(aligned)} overlapping months — too few to say anything.")
    except FileNotFoundError:
        print(f"  {MOMENTUM_CURVE_CACHE} not found — run cross_sectional_momentum_backtest.py first "
              f"for this check. Proceeding without it.")

    stress_params = dict(BASE_PARAMS, cost_bps=COST_BPS_STRESS)
    stress_ls, _, _, _ = run_full(px_m, ret_m, beta_panel_m, stress_params)
    stress_cagr = metrics(stress_ls, "")["cagr_pct"]
    base_m = results[0]
    print(f"\nCost stress ({COST_BPS_STRESS:.0f}bps one-way): CAGR {fmt(stress_cagr,2,'%')} "
          f"(base {fmt(base_m['cagr_pct'],2,'%')})")

    banner("WALK-FORWARD — first half (IS) vs second half (OOS), base config")
    wf = walk_forward(px_m, ret_m, beta_panel_m, BASE_PARAMS)
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%"),
            f"${r['final']:.0f}"] for r in [wf["is"], wf["oos"]]],
          ["Period", "CAGR", "Sharpe", "MaxDD", "Final $100"], [30, 8, 8, 8, 11])

    print(f"\nRunning parameter surface ({len(GROUP_FRACS)*len(LOOKBACKS)*len(SKIPS)} cells)...", flush=True)
    surf = parameter_sweep(px_m, ret_m, beta_panel_m)
    surf.to_csv("value_reversal_surface.csv", index=False)
    sc = surf["cagr_pct"].dropna()
    tc = surf["t_nw"].dropna()
    banner("PARAMETER SURFACE — median / range / sign agreement, never the best cell")
    print(f"CAGR%  — median {fmt(sc.median(),2)}  mean {fmt(sc.mean(),2)}  "
          f"min {fmt(sc.min(),2)}  max {fmt(sc.max(),2)}  sign+ {(sc>0).mean()*100:.0f}% of {len(sc)} cells")

    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=5/8 to pass)")
    oos_m = wf["oos"]
    mv_m = results[3]
    checks = [
        (1, True, "Net-of-cost CAGR > 0 (base config, full sample)",
         base_m["cagr_pct"] > 0, f"{base_m['cagr_pct']:+.2f}%"),
        (2, True, "Survives 20bps stress cost (still net positive CAGR)",
         stress_cagr > 0, f"{stress_cagr:+.2f}%"),
        (3, True, "Walk-forward OOS half still net positive CAGR",
         oos_m["cagr_pct"] > 0, f"{oos_m['cagr_pct']:+.2f}%"),
        (4, False, "Long-short Sharpe beats the matched-vol long-only baseline",
         (not np.isnan(base_m["sharpe"])) and (not np.isnan(mv_m["sharpe"])) and base_m["sharpe"] > mv_m["sharpe"],
         f"LS {fmt(base_m['sharpe'],3)} vs matched-vol long-only {fmt(mv_m['sharpe'],3)}"),
        (5, False, "Parameter-surface median cell CAGR > 0",
         sc.median() > 0, f"median {sc.median():+.2f}%"),
        (6, False, "Parameter-surface sign agreement >= 70% of cells positive",
         (sc > 0).mean() >= 0.70, f"{(sc > 0).mean() * 100:.0f}% of {len(sc)} cells"),
        (7, False, "Naive t-stat on monthly LS returns |t| >= 3",
         (not np.isnan(t_naive)) and abs(t_naive) >= 3, f"t={fmt(t_naive, 2)}"),
        (8, False, "Distinct from the already-tested 12-1 momentum spread (|corr| < 0.5)",
         np.isfinite(corr_mom) and abs(corr_mom) < 0.5,
         f"corr={fmt(corr_mom,3)}" if np.isfinite(corr_mom) else "momentum curve unavailable"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:56], det[:44]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 56, 44])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 5 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/8 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — survived its own pre-registered bar; still only PAPER-testing evidence, not a live-trading"
        " recommendation, and the delisting-gap caveat above still applies (likely understated)." if verdict == "PASS"
        else " — report the null and stop. This does not mean value/long-term reversal never works, only"
             " that this price-only proxy did not clear its own bar over this survivorship-biased sample."))
    print("=" * 100)

    pd.DataFrame(results).to_csv("value_reversal_results.csv", index=False)
    ls.to_csv("value_reversal_curve.csv", header=["equity"])
    print(f"\nWrote value_reversal_results.csv, value_reversal_surface.csv, value_reversal_curve.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
