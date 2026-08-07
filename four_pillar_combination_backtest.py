"""
Four-Pillar Combination — does combining weak/mediocre signals beat any one alone?
======================================================================================
Portfolio theory is explicit that this can work even when each piece looks
unremarkable alone: if N assets are sufficiently uncorrelated, the combined
Sharpe can exceed any single constituent's, because idiosyncratic risk
diversifies away while each piece's (even modest) expected return survives
the averaging. This script tests that directly on the four candidates this
session actually produced evidence for — not cherry-picked winners, the
four things that showed SOME real signal without being proven artifacts:

  1. Gold / real-yield timer      Sharpe 1.165 (dxy_gold_stopcheck.py) — the
                                   strongest, reconstructed here identically.
  2. Equal-weight sector premium  Sharpe 0.528 (sector_stockpick_diagnostic.py,
                                   arm E — REAL equal-weight sector ETFs,
                                   confirmed bias-free today).
  3. FMTS momentum+low-vol        Sharpe 0.473 (fmts_backtest.py, with-stop) —
                                   loses to SPY alone, but that doesn't rule
                                   out a diversification contribution.
  4. OTP2.0 base                  Sharpe 0.753 (otp2_ama_backtest.py, base
                                   arm, exact live cohort/config, 2009-2026).

NOT included: OTP2.0 AMA (proven statistically identical to OTP2.0 base —
would be redundant, not a 5th pillar), the backfilled sector+stockpick arms
(proven survivorship-bias artifacts today), RRG and BAB (failed validation).

METHOD
--------
Loads each pillar's DAILY (Gold, OTP2.0) or MONTHLY (sector-EW, FMTS is
daily but resampled to monthly for a consistent combination cadence) return
series, restated/reused from each pillar's own backtest exactly as already
validated — no new signal construction here, only combination. Aligns to
the common overlapping window (bounded by OTP2.0's ~2009 start — the latest
of the four). Reports:
  - the 4x4 correlation matrix (the actual answer to "how correlated are
    they")
  - equal-weight-of-4 as the PRIMARY, non-data-mined result
  - every non-empty subset (15 total: 4 singles, 6 pairs, 4 triples, 1 full)
    equal-weighted within itself, to directly answer "how many to combine" —
    reported as a full surface, not a cherry-picked best subset (picking the
    best of 15 after the fact is exactly the kind of thing CLAUDE.md's
    parameter-surface discipline exists to catch)
  - a walk-forward check on the equal-weight-of-4 result specifically

This is PAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real
money; nothing here is wired into the live paper-trading engines.

Usage:
  py four_pillar_combination_backtest.py
"""

import itertools
import sys
import time
import warnings

import numpy as np
import pandas as pd
import requests
import yfinance as yf

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
PILLAR_NAMES = ["Gold", "SectorEW", "FMTS", "OTP2.0"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. PILLAR RECONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def fetch_yf(ticker):
    df = yf.download(ticker, start="1990-01-01", progress=False, auto_adjust=False)
    return df["Close"].squeeze()


def fetch_fred(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    df = pd.read_csv(url, index_col=0, parse_dates=True)
    return pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()


def build_gold_pillar():
    """Restated identically from dxy_gold_stopcheck.py: R-dir+DXY signal +
    5% trailing stop, Sharpe 1.165 in that script's own validation."""
    print("  Rebuilding Gold pillar (R-dir+DXY + 5% stop, from dxy_gold_stopcheck.py)...")
    gold = fetch_yf("GC=F")
    dxy = fetch_yf("DX-Y.NYB")
    tbill = fetch_fred("DGS3MO")
    tips = fetch_fred("DFII10")

    gold_log = np.log(gold / gold.shift(1)).dropna()
    cash_d = np.log(1 + tbill / 100) / 252
    dxy_sma = dxy.rolling(150).mean()
    dxy_scalar = pd.Series(np.where(dxy < dxy_sma, 1.0, 0.5), index=dxy.index).shift(1)

    idx = gold_log.index
    for s in [cash_d, dxy_scalar, tips]:
        idx = idx.intersection(s.dropna().index)
    gold_log = gold_log.reindex(idx)
    cash_d = cash_d.reindex(idx).ffill()
    dxy_scalar = dxy_scalar.reindex(idx).ffill()
    gold_price = gold.reindex(idx, method="ffill")
    tips_a = tips.reindex(idx, method="ffill")
    tips_fall = (tips_a < tips_a.rolling(60).mean()).astype(float)

    sig, px, sc = tips_fall.values, gold_price.values, dxy_scalar.values
    n = len(sig)
    pos = np.zeros(n)
    hwm = np.nan
    stop_active = False
    for i in range(1, n):
        s_prev, s_curr, p = sig[i - 1], sig[i], px[i]
        base = s_prev * sc[i - 1]
        if stop_active:
            if s_curr < 0.01:
                stop_active = False
                hwm = np.nan
            pos[i] = 0.0
            continue
        if base < 0.01:
            hwm = np.nan
            pos[i] = 0.0
        else:
            hwm = p if np.isnan(hwm) else max(hwm, p)
            if p < hwm * 0.95:
                pos[i] = 0.0
                hwm = np.nan
                stop_active = True
            else:
                pos[i] = base
    pos = pd.Series(pos, index=idx)
    ret_log = pos * gold_log + (1 - pos) * cash_d
    return np.expm1(ret_log).rename("Gold")   # log -> simple return, consistent with the other 3 pillars


def load_csv_pillar(path, col, label):
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    curve = df[col].dropna()
    ret = curve.pct_change().dropna()
    print(f"  Loaded {label} pillar from {path}::{col} — "
          f"{ret.index[0].date()} -> {ret.index[-1].date()} ({len(ret)} periods)")
    return ret.rename(label)


# ─────────────────────────────────────────────────────────────────────────────
# 2. COMBINATION
# ─────────────────────────────────────────────────────────────────────────────

def to_monthly(ret_daily_or_monthly, is_monthly):
    if is_monthly:
        return ret_daily_or_monthly
    eq = (1 + ret_daily_or_monthly).cumprod()
    return eq.resample("ME").last().pct_change().dropna()


def metrics(ret_m, label, rfr=RFR):
    ret_m = ret_m.dropna()
    if len(ret_m) < 12:
        return {"label": label, "cagr_pct": np.nan, "vol_pct": np.nan, "sharpe": np.nan, "max_dd_pct": np.nan, "n": len(ret_m)}
    eq = (1 + ret_m).cumprod()
    n = len(ret_m)
    cagr = eq.iloc[-1] ** (12 / n) - 1
    vol = ret_m.std() * np.sqrt(12)
    sharpe = (ret_m.mean() - rfr / 12) / ret_m.std() * np.sqrt(12) if ret_m.std() > 0 else 0.0
    roll = eq.cummax()
    dd = (eq - roll) / roll
    return {"label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100, "sharpe": sharpe,
            "max_dd_pct": dd.min() * 100, "n": n}


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
# 3. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    banner("FOUR-PILLAR COMBINATION — Gold, Equal-Weight Sector, FMTS, OTP2.0")
    print("Testing whether combining four individually-mediocre-or-better signals beats any one")
    print("alone, via diversification. No new signal construction — pure portfolio combination.")
    print("PAPER-TESTING RESEARCH ONLY.\n")

    gold_ret_d = build_gold_pillar()
    otp2_ret_d = load_csv_pillar("otp2_ama_curve.csv", "base", "OTP2.0")
    fmts_ret_d = load_csv_pillar("fmts_curve.csv", "with_stop", "FMTS")
    sectorew_ret_m = load_csv_pillar("sector_stockpick_diagnostic_curve.csv", "equal_weight_etf", "SectorEW")

    gold_m = to_monthly(gold_ret_d, is_monthly=False).rename("Gold")
    otp2_m = to_monthly(otp2_ret_d, is_monthly=False).rename("OTP2.0")
    fmts_m = to_monthly(fmts_ret_d, is_monthly=False).rename("FMTS")
    sectorew_m = sectorew_ret_m.rename("SectorEW")

    panel = pd.concat([gold_m, sectorew_m, fmts_m, otp2_m], axis=1).dropna()
    print(f"\nCommon monthly window: {panel.index[0].date()} -> {panel.index[-1].date()} "
          f"({len(panel)} months) — bounded by OTP2.0's ~2009 start (AVGO's post-IPO history).")

    banner("CORRELATION MATRIX (monthly returns, common window)")
    corr = panel.corr()
    table([[idx] + [fmt(v, 2) for v in row] for idx, row in zip(corr.index, corr.values)],
          [""] + list(corr.columns), [10, 8, 8, 8, 8])

    banner("EACH PILLAR ALONE (common window)")
    single_results = [metrics(panel[c], c) for c in panel.columns]
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["vol_pct"], 2, "%"), fmt(r["sharpe"], 3),
            fmt(r["max_dd_pct"], 1, "%")] for r in single_results],
          ["Pillar", "CAGR", "Vol", "Sharpe", "MaxDD"], [12, 8, 8, 8, 8])

    banner("PRIMARY RESULT — equal-weight of all 4 (non-data-mined default)")
    eq4 = panel.mean(axis=1)
    eq4_m = metrics(eq4, "Equal-weight of 4")
    print(f"  CAGR {fmt(eq4_m['cagr_pct'],2,'%')}   Vol {fmt(eq4_m['vol_pct'],2,'%')}   "
          f"Sharpe {fmt(eq4_m['sharpe'],3)}   MaxDD {fmt(eq4_m['max_dd_pct'],1,'%')}")
    best_single = max(single_results, key=lambda r: r["sharpe"] if np.isfinite(r["sharpe"]) else -99)
    print(f"  Best single pillar alone: {best_single['label']} Sharpe {fmt(best_single['sharpe'],3)}")
    print(f"  Equal-weight-4 {'BEATS' if eq4_m['sharpe'] > best_single['sharpe'] else 'does NOT beat'} "
          f"the best single pillar on Sharpe.")

    banner("SUBSET SURFACE — every combination, equal-weighted within itself (report all, pick none)")
    cols = list(panel.columns)
    subset_rows = []
    for size in range(1, 5):
        for combo in itertools.combinations(cols, size):
            r = panel[list(combo)].mean(axis=1)
            m = metrics(r, "+".join(combo))
            subset_rows.append({"size": size, "combo": "+".join(combo), "cagr_pct": m["cagr_pct"],
                                 "sharpe": m["sharpe"], "max_dd_pct": m["max_dd_pct"]})
    surf = pd.DataFrame(subset_rows)
    surf.to_csv("four_pillar_surface.csv", index=False)
    for size in range(1, 5):
        g = surf[surf["size"] == size]
        print(f"\n  Size {size} ({len(g)} combos): Sharpe median {fmt(g['sharpe'].median(),3)}  "
              f"min {fmt(g['sharpe'].min(),3)}  max {fmt(g['sharpe'].max(),3)}")
        table([[row["combo"], fmt(row["cagr_pct"], 2, "%"), fmt(row["sharpe"], 3), fmt(row["max_dd_pct"], 1, "%")]
               for _, row in g.iterrows()], ["Combo", "CAGR", "Sharpe", "MaxDD"], [24, 8, 8, 8])

    banner("WALK-FORWARD — equal-weight-of-4, first half vs second half")
    mid = panel.index[len(panel) // 2]
    is_eq4 = panel.loc[:mid].mean(axis=1)
    oos_eq4 = panel.loc[mid:].mean(axis=1)
    is_m = metrics(is_eq4, f"IS ({panel.index[0].date()} - {mid.date()})")
    oos_m = metrics(oos_eq4, f"OOS ({mid.date()} - {panel.index[-1].date()})")
    table([[r["label"], fmt(r["cagr_pct"], 2, "%"), fmt(r["sharpe"], 3), fmt(r["max_dd_pct"], 1, "%")]
           for r in [is_m, oos_m]], ["Period", "CAGR", "Sharpe", "MaxDD"], [40, 8, 8, 8])

    _, t_nw, n_obs = rs.newey_west_t(eq4.values, lag=1)
    t_naive = rs.naive_t(eq4.values)
    print(f"\nEqual-weight-4 monthly returns: naive t (n={n_obs}) = {fmt(t_naive,2)}   "
          f"Newey-West (lag=1) = {fmt(t_nw,2)}")

    banner("BOTTOM LINE")
    if eq4_m["sharpe"] > best_single["sharpe"] and is_m["sharpe"] > 0 and oos_m["sharpe"] > 0:
        print("  Equal-weight-of-4 beats every single pillar and holds up in both halves of the")
        print("  sample — the diversification argument holds here. Still only 4 assets over a")
        print(f"  {len(panel)}-month common window; treat as suggestive, not proven, and note the")
        print("  FMTS/SectorEW pillars individually still trail SPY on a standalone basis.")
    else:
        print("  The combination does not clearly beat the best single pillar, or breaks down in")
        print("  one half of the sample. Report that plainly — diversification requires genuinely")
        print("  low correlation AND positive expected return in each piece; check the correlation")
        print("  matrix and per-pillar Sharpes above for which condition is failing.")
    print("=" * 100)

    panel.to_csv("four_pillar_monthly_returns.csv")
    print(f"\nWrote four_pillar_surface.csv, four_pillar_monthly_returns.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")
    print("\nPAPER-TESTING RESEARCH ONLY. Not a recommendation to trade real money.")


if __name__ == "__main__":
    main()
