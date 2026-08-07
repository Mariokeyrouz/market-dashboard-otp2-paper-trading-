"""
OTP2.0 AMA — does the VIX-term-structure + dwell gate actually help?
=======================================================================
OTP2.0 AMA (`paper_trading_engine_AMA.py`) went live with two additions on
top of the base OTP2.0 engine (`paper_trading_engine.py`) — a VIX
term-structure filter (^VIX3M/^VIX ratio, 3-day MA, must be >= 1.0 to reload)
and a 20-day post-trim dwell timer — on an "AlphaMind recommendation," with
NO backtest of these two specific rules anywhere in the repo. This script is
that backtest.

METHOD — run the EXACT live code, not a proxy
------------------------------------------------
Unlike most backtests in this repo (which restate logic for standalone
auditability), this one imports `_step()` directly from both
`paper_trading_engine.py` and `paper_trading_engine_AMA.py`. The entire point
is to test the exact deployed code — a restated approximation would answer a
different question. Both engines are seeded identically (same NAV, same
7-stock cohort, same day) and stepped forward in lockstep over the same
historical index, so any divergence between the two NAV curves is
attributable ONLY to the two AMA gates.

THE KEY TEST IS THE PAIRED DIFFERENCE
----------------------------------------
Two nearly-identical engines sharing almost all the same trades produce
returns that are highly correlated except on the days the gates actually
bind. Comparing two independent Sharpe ratios throws that shared structure
away; the paired daily difference (AMA return - base return) isolates the
gates' effect directly and is a far more powerful test on a modest sample.

SAMPLE SIZE CAVEAT
---------------------
The common index is bounded by AVGO's post-spinoff trading history AND
^VIX3M's own inception — both push the earliest usable date to roughly
2010-2011, not OTP2.0's own 36-year backtest window. Treat this as a test of
the INCREMENTAL rules on a ~15-year sample, not a re-validation of the base
engine (which already has its own backtest lineage via
`combined_backtest.py` / `strategy_selection_v4`).

Outputs: otp2_ama_results.csv, otp2_ama_curve.csv, otp2_ama_annual.csv

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here changes the live engines or their state files.

Usage:
  py otp2_ama_backtest.py
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

from strategy_deep_test import download_many, download_tbill
from strategy_selection_v2 import DEFENSIVE_OT2_CONFIG
import paper_trading_engine as pte
import paper_trading_engine_AMA as pte_ama
import rrg_stats as rs

LIVE_TICKERS = ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"]
CFG = DEFENSIVE_OT2_CONFIG
START_NAV = 10_000.0
SLIPPAGE_FEE_RATE = pte.SLIPPAGE_FEE_RATE
RFR = 0.03


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    print(f"Downloading full history: ^GSPC, ^VIX, ^VIX3M, {', '.join(LIVE_TICKERS)}...")
    raw = download_many(["^GSPC", "^VIX", "^VIX3M"] + LIVE_TICKERS)
    gspc, vix, vix3m = raw["^GSPC"], raw["^VIX"], raw["^VIX3M"]
    tbill_raw, tbill_src = download_tbill()
    print(f"  T-bill source: {tbill_src}")

    closes = {t: raw[t]["Close"].squeeze() for t in LIVE_TICKERS}
    market_df = pte_ama.build_market_features_AMA(gspc, vix, vix3m)   # superset of base columns

    prices = pd.DataFrame({t: closes[t] for t in LIVE_TICKERS})
    logret = np.log(prices / prices.shift(1))

    common_index = market_df.index
    for t in LIVE_TICKERS:
        common_index = common_index.intersection(logret[t].dropna().index)
    market_df = market_df.loc[common_index]
    prices = prices.loc[common_index]
    logret = logret.loc[common_index]

    blended = logret.mean(axis=1)
    cash_daily = tbill_raw.reindex(common_index).ffill().bfill() / 252

    print(f"Common index: {common_index[0].date()} -> {common_index[-1].date()} "
          f"({len(common_index):,} trading days)")
    return market_df, prices, blended, cash_daily, common_index


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEED / RUN
# ─────────────────────────────────────────────────────────────────────────────

def seed_state(market_df, prices, tickers, cfg, seed_pos, start_nav):
    inv0 = min(0.95, cfg["vol_target"] / market_df["rvol20"].iloc[seed_pos])
    seed_cost = start_nav * inv0 * SLIPPAGE_FEE_RATE
    nav0 = start_nav - seed_cost
    invested_dollars0 = nav0 * inv0
    per_ticker = invested_dollars0 / len(tickers)
    entry_prices = {t: float(prices[t].iloc[seed_pos]) * (1 + SLIPPAGE_FEE_RATE) for t in tickers}
    shares = {t: per_ticker / entry_prices[t] for t in tickers}
    return dict(invested=inv0, cooldown=0, consec_vix_fall=0, consec_rvol_fall=0,
                invested_dollars=invested_dollars0, cash_dollars=nav0 * (1 - inv0),
                nav=nav0, trading_cost=seed_cost, entry_prices=entry_prices,
                shares=shares, trim_date=None)


def run_paired(market_df, prices, blended, cash_daily, common_index, cfg):
    state_base = seed_state(market_df, prices, LIVE_TICKERS, cfg, 0, START_NAV)
    state_ama = seed_state(market_df, prices, LIVE_TICKERS, cfg, 0, START_NAV)

    n = len(common_index)
    nav_base = np.full(n, np.nan); nav_base[0] = state_base["nav"]
    nav_ama = np.full(n, np.nan); nav_ama[0] = state_ama["nav"]
    dwell_blocked = np.zeros(n, dtype=bool)
    term_blocked = np.zeros(n, dtype=bool)

    for i in range(1, n):
        row, prev = market_df.iloc[i], market_df.iloc[i - 1]
        date = common_index[i]
        px_today = {t: float(prices[t].iloc[i]) for t in LIVE_TICKERS}

        trim_date_str = state_ama.get("trim_date")
        if trim_date_str:
            dwell_blocked[i] = (date - pd.Timestamp(trim_date_str)).days < pte_ama.DWELL_DAYS
        ratio_ma3 = float(row.get("vix3m_vix_ratio_ma3", np.nan))
        term_blocked[i] = not (np.isnan(ratio_ma3) or ratio_ma3 >= 1.0)

        state_base = pte._step(row, prev, state_base, cfg, blended.iloc[i], cash_daily.iloc[i],
                                px_today, float(cash_daily.iloc[i]))
        state_ama = pte_ama._step(row, prev, state_ama, cfg, blended.iloc[i], cash_daily.iloc[i],
                                   px_today, float(cash_daily.iloc[i]), today=date)
        nav_base[i] = state_base["nav"]
        nav_ama[i] = state_ama["nav"]

    curve_base = pd.Series(nav_base, index=common_index)
    curve_ama = pd.Series(nav_ama, index=common_index)
    gates = pd.DataFrame({"dwell_blocked": dwell_blocked, "term_blocked": term_blocked}, index=common_index)
    return curve_base, curve_ama, gates


# ─────────────────────────────────────────────────────────────────────────────
# 3. STATS / REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    if len(curve) < 252:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan,
                "sortino": np.nan, "max_dd_pct": np.nan, "final": np.nan}
    n = len(curve)
    cagr = (curve.iloc[-1] / curve.iloc[0]) ** (252 / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(252)
    sharpe = (r.mean() - rfr / 252) / r.std() * np.sqrt(252) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(252) if len(neg) > 1 else 0.0
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
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("OTP2.0 AMA — paired test of the VIX-term-structure + dwell gates vs base OTP2.0")
    print("Runs the EXACT live _step() code from both paper_trading_engine.py and")
    print("paper_trading_engine_AMA.py, seeded identically, over the same historical index.")
    print("PAPER-TESTING RESEARCH ONLY. These two AMA rules have never been backtested before.")

    market_df, prices, blended, cash_daily, common_index = load_data()
    curve_base, curve_ama, gates = run_paired(market_df, prices, blended, cash_daily, common_index, CFG)

    base_m = metrics(curve_base, "Base OTP2.0 (no AMA gates)")
    ama_m = metrics(curve_ama, "OTP2.0 AMA (VIX term-structure + dwell)")
    banner(f"BASE CONFIG — {common_index[0].date()} -> {common_index[-1].date()} "
           f"({len(common_index):,} trading days, ~{len(common_index)/252:.1f} years)")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["sortino"], 3), fmt(r["max_dd_pct"], 1, "%"), f"${r['final']:.0f}"]
          for r in [base_m, ama_m]],
          ["Arm", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Final $10k->"], [40, 8, 8, 8, 8, 8, 12])

    # ── paired difference ───────────────────────────────────────────────────
    ret_base = curve_base.pct_change().dropna()
    ret_ama = curve_ama.pct_change().dropna()
    diff = (ret_ama - ret_base).dropna()
    mean_diff_ann = diff.mean() * 252
    t_naive = rs.naive_t(diff.values)
    _, t_nw, n_obs = rs.newey_west_t(diff.values, lag=5)

    banner("PAIRED DIFFERENCE — daily (AMA return - base return)")
    print(f"  n={n_obs} trading days   Mean diff (annualized): {mean_diff_ann*100:+.3f}%")
    print(f"  Naive t: {fmt(t_naive,2)}   Newey-West (lag=5, sanity check): {fmt(t_nw,2)}")
    print(f"  Days AMA > base: {(diff>0).mean()*100:.1f}%   Days AMA < base: {(diff<0).mean()*100:.1f}%   "
          f"Days identical: {(diff==0).mean()*100:.1f}%")

    # ── gate activity ───────────────────────────────────────────────────────
    banner("GATE ACTIVITY — how often each AMA rule actually blocked a reload")
    n_days = len(gates)
    print(f"  Dwell-blocked days: {gates['dwell_blocked'].sum()} ({100*gates['dwell_blocked'].mean():.2f}% of days)")
    print(f"  Term-blocked days:  {gates['term_blocked'].sum()} ({100*gates['term_blocked'].mean():.2f}% of days)")
    print(f"  Either blocked:     {(gates['dwell_blocked']|gates['term_blocked']).sum()} "
          f"({100*(gates['dwell_blocked']|gates['term_blocked']).mean():.2f}% of days)")

    # ── annual concentration check ──────────────────────────────────────────
    banner("ANNUAL BREAKDOWN — is the effect concentrated in one or two years?")
    annual = diff.groupby(diff.index.year).sum() * 100
    ann_rows = [[str(yr), f"{v:+.3f}pp"] for yr, v in annual.items()]
    table(ann_rows, ["Year", "Sum of daily diffs (pp)"], [8, 24])
    cum_total = annual.sum()
    best_year_contrib = annual.max()
    concentrated = np.isfinite(cum_total) and cum_total != 0 and (
        (cum_total > 0 and best_year_contrib > cum_total) or
        (cum_total < 0 and annual.min() < cum_total))
    print(f"\n  Total cumulative diff: {cum_total:+.3f}pp   Best single year: {best_year_contrib:+.3f}pp")
    print(f"  Would removing the single best year flip the sign? {'YES — concentrated' if concentrated else 'No'}")

    # ── pre-registered criteria ─────────────────────────────────────────────
    banner("PRE-REGISTERED CRITERIA (written before reading results; 1,2,3 mandatory; >=4/6 to pass)")
    checks = [
        (1, True, "AMA CAGR > base CAGR",
         ama_m["cagr_pct"] > base_m["cagr_pct"], f"AMA {fmt(ama_m['cagr_pct'],2)}% vs base {fmt(base_m['cagr_pct'],2)}%"),
        (2, True, "Paired-difference mean > 0 (annualized)",
         mean_diff_ann > 0, f"{mean_diff_ann*100:+.3f}%/yr"),
        (3, True, "AMA MaxDD no worse than base MaxDD",
         ama_m["max_dd_pct"] >= base_m["max_dd_pct"], f"AMA {fmt(ama_m['max_dd_pct'],1)}% vs base {fmt(base_m['max_dd_pct'],1)}%"),
        (4, False, "Newey-West |t| on paired difference >= 3",
         np.isfinite(t_nw) and abs(t_nw) >= 3, f"t={fmt(t_nw,2)}"),
        (5, False, "Effect not concentrated in a single year",
         not concentrated, "concentrated" if concentrated else "distributed"),
        (6, False, "AMA Sharpe > base Sharpe",
         ama_m["sharpe"] > base_m["sharpe"], f"AMA {fmt(ama_m['sharpe'],3)} vs base {fmt(base_m['sharpe'],3)}"),
    ]
    rows = [[str(n), "YES" if mand else "", "PASS" if ok else "FAIL", desc[:52], det[:40]]
            for n, mand, desc, ok, det in checks]
    table(rows, ["#", "Mand", "Result", "Criterion", "Detail"], [3, 5, 7, 52, 40])

    passed = sum(1 for _, _, _, ok, _ in checks if ok)
    mand_ok = all(ok for _, mand, _, ok, _ in checks if mand)
    verdict = "PASS" if (passed >= 4 and mand_ok) else "FAIL"
    print()
    print(f"SCORE: {passed}/6 criteria passed. Mandatory (1,2,3): {'all passed' if mand_ok else 'NOT all passed'}.")
    print(f"VERDICT: {verdict}" + (
        " — the AMA gates earn their keep on this sample; still only a ~15-year paper-testing"
        " result, not a live-trading guarantee." if verdict == "PASS"
        else " — report the null and stop. The VIX-term-structure and dwell gates do not clear their"
             " own bar here; that does not prove they're worthless in all regimes, only that this"
             " sample does not support keeping them live over the base engine."))
    print("=" * 100)

    pd.DataFrame([base_m, ama_m]).to_csv("otp2_ama_results.csv", index=False)
    pd.DataFrame({"base": curve_base, "ama": curve_ama}).to_csv("otp2_ama_curve.csv")
    annual.to_csv("otp2_ama_annual.csv", header=["diff_sum_pp"])
    print(f"\nWrote otp2_ama_results.csv, otp2_ama_curve.csv, otp2_ama_annual.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
