"""
Selection Attribution
=====================
Step 1 of the OTP2.0 security-selection redesign: decompose the existing
Module 3 chained result (Sharpe 0.625, CAGR 8.89%) per-cohort into:

  (a) Selection effect  = cohort-stocks B&H Sharpe  - SPX B&H Sharpe
  (b) Timing effect     = OT2.0-overlay Sharpe      - cohort-stocks B&H Sharpe

This tells us, per 5-year cohort, whether weak results are driven by bad
stock picks (selection effect <= 0) or by a hard market regime that even
good picks + timing couldn't escape (selection effect > 0 but absolute
Sharpe still low, e.g. dot-com 1998-2002).

Reuses strategy_deep_test.py's download/feature/engine functions and the
exact same cohort definitions + 4-factor selection logic, so results are
directly comparable to the existing strategy_deep_test_results.csv.

Usage:
  python selection_attribution.py
"""

import time
import numpy as np
import pandas as pd

from strategy_deep_test import (
    download, download_tbill, build_market_features, ot2_engine, buy_and_hold,
    _print_table, UNIVERSE30, STOCKS7, OT2_CONFIG, START,
)


def main():
    t0 = time.time()

    print("Downloading market + timing data...")
    gspc = download("^GSPC")
    vix  = download("^VIX")

    print("Downloading T-bill rate...")
    tbill_raw, tbill_src = download_tbill()
    print(f"  Source: {tbill_src}")

    print("Downloading 30-stock universe (close prices)...")
    closes = {}
    for tkr in UNIVERSE30:
        df = download(tkr)
        closes[tkr] = df["Close"].squeeze()
        print(f"  {tkr:6s}: {df.index[0].date()} -> {df.index[-1].date()}  ({len(df):,} days)")

    print("\nBuilding features...")
    market_df = build_market_features(gspc, vix)

    # Same common_index basis as strategy_deep_test.py (market features
    # intersected with STOCKS7-minus-BRK-B availability)
    log_ret7 = {}
    for tkr in STOCKS7:
        s = closes[tkr]
        log_ret7[tkr] = np.log(s / s.shift(1))

    common_index = market_df.index
    for tkr in STOCKS7:
        if tkr == "BRK-B":
            continue
        common_index = common_index.intersection(log_ret7[tkr].dropna().index)
    market_df = market_df.loc[common_index]

    prices30 = pd.DataFrame({t: closes[t] for t in UNIVERSE30}).reindex(common_index)
    logret30 = np.log(prices30 / prices30.shift(1))
    sma50_30 = prices30.rolling(50).mean()

    print(f"\nCommon index: {common_index[0].date()} -> {common_index[-1].date()}  "
          f"({len(common_index):,} trading days)")

    cohorts = [
        ("Cohort 1", "1993-01-04", "1993-01-04", "1997-12-31"),
        ("Cohort 2", "1998-01-02", "1998-01-02", "2002-12-31"),
        ("Cohort 3", "2003-01-02", "2003-01-02", "2007-12-31"),
        ("Cohort 4", "2008-01-02", "2008-01-02", "2012-12-31"),
        ("Cohort 5", "2013-01-02", "2013-01-02", "2017-12-31"),
        ("Cohort 6", "2018-01-02", "2018-01-02", "2022-12-31"),
        ("Live",     "2023-01-03", "2023-01-03", str(common_index[-1].date())),
    ]

    rows = []
    for name, sel_str, hold_start_str, hold_end_str in cohorts:
        sel_date = pd.Timestamp(sel_str)
        hold_start = pd.Timestamp(hold_start_str)
        hold_end   = pd.Timestamp(hold_end_str)

        if sel_date < common_index[0]:
            sel_date = common_index[0]
        sel_pos = common_index.searchsorted(sel_date)
        sel_pos = min(sel_pos, len(common_index) - 1)

        # ── Identical 4-factor selection logic to strategy_deep_test.py ────
        scores = {}
        for tkr in UNIVERSE30:
            px = prices30[tkr].iloc[:sel_pos + 1]
            valid = px.dropna()
            if len(valid) < 280:
                continue

            c0   = valid.iloc[-1]
            c1m  = valid.iloc[-22]
            c12m = valid.iloc[-253]
            f1 = (c1m / c12m) - 1

            sma_seg = sma50_30[tkr].iloc[:sel_pos + 1].dropna()
            px_seg  = prices30[tkr].iloc[:sel_pos + 1].reindex(sma_seg.index)
            lookback2 = min(252, len(sma_seg))
            f2 = (px_seg.iloc[-lookback2:] > sma_seg.iloc[-lookback2:]).mean()

            lb3 = min(756, len(valid) - 1)
            c3 = valid.iloc[-(lb3 + 1)]
            cagr3 = (c0 / c3) ** (252 / lb3) - 1
            lr3 = logret30[tkr].iloc[sel_pos - lb3 + 1:sel_pos + 1].dropna()
            vol3 = lr3.std() * np.sqrt(252)
            f3 = cagr3 / vol3 if vol3 > 0 else 0.0

            lb4 = min(1260, len(valid))
            window5 = valid.iloc[-lb4:]
            roll_max = window5.cummax()
            dd = ((window5 - roll_max) / roll_max).min()
            f4 = 1 / abs(dd) if dd != 0 else 0.0

            scores[tkr] = dict(f1=f1, f2=f2, f3=f3, f4=f4)

        sc_df = pd.DataFrame(scores).T
        for col in ["f1", "f2", "f3", "f4"]:
            sc_df[col + "_rank"] = sc_df[col].rank(pct=True)

        sc_df["composite"] = (0.35 * sc_df["f1_rank"] + 0.25 * sc_df["f2_rank"] +
                               0.25 * sc_df["f3_rank"] + 0.15 * sc_df["f4_rank"])
        sc_df = sc_df.sort_values("composite", ascending=False)
        selected = list(sc_df.head(8).index)

        # ── Holding period slice ────────────────────────────────────────
        hp_start_pos = common_index.searchsorted(hold_start)
        hp_end_pos   = common_index.searchsorted(hold_end)
        hp_end_pos   = min(hp_end_pos, len(common_index) - 1)
        if hp_start_pos >= hp_end_pos:
            continue

        hp_index = common_index[hp_start_pos:hp_end_pos + 1]
        hp_market = market_df.loc[hp_index]
        hp_logret = logret30.loc[hp_index, selected]
        hp_avail = hp_logret.notna()
        hp_n = hp_avail.sum(axis=1).replace(0, np.nan)
        hp_weight = hp_avail.div(hp_n, axis=0).fillna(0.0)
        hp_blended = (hp_weight * hp_logret.fillna(0.0)).sum(axis=1)
        hp_blended.iloc[0] = 0.0

        hp_tbill = tbill_raw.reindex(hp_index).ffill().bfill()
        hp_cash = (hp_tbill / 252).values
        rfr_mean_seg = float(hp_tbill.mean())

        # (a) Selection effect: cohort-stocks B&H vs SPX B&H, same window
        spx_seg   = buy_and_hold(hp_market["log_ret"], hp_index, f"{name} SPX B&H", rfr=rfr_mean_seg)
        stock_bh  = buy_and_hold(hp_blended, hp_index, f"{name} cohort B&H", rfr=rfr_mean_seg)

        # (b) Timing effect: OT2.0 overlay on the same cohort stocks vs their B&H
        strat = ot2_engine(hp_market, hp_blended, hp_cash, f"{name} OT2.0+selected8",
                            rfr_for_sharpe=rfr_mean_seg)

        selection_effect = stock_bh["sharpe"] - spx_seg["sharpe"]
        timing_effect    = strat["sharpe"]    - stock_bh["sharpe"]

        rows.append([
            name,
            f"{spx_seg['sharpe']:.3f}", f"{spx_seg['cagr_pct']:.2f}%",
            f"{stock_bh['sharpe']:.3f}", f"{stock_bh['cagr_pct']:.2f}%",
            f"{strat['sharpe']:.3f}", f"{strat['cagr_pct']:.2f}%",
            f"{selection_effect:+.3f}", f"{timing_effect:+.3f}",
        ])

    headers = [
        "Cohort",
        "SPX B&H Sharpe", "SPX CAGR",
        "Cohort B&H Sharpe", "Cohort CAGR",
        "OT2.0 Sharpe", "OT2.0 CAGR",
        "Selection Effect", "Timing Effect",
    ]

    print("\n" + "=" * 70)
    print("PER-COHORT ATTRIBUTION: SELECTION EFFECT vs TIMING EFFECT")
    print("(Selection = Cohort B&H Sharpe - SPX B&H Sharpe)")
    print("(Timing    = OT2.0 Sharpe - Cohort B&H Sharpe)")
    print("=" * 70)
    _print_table(headers, rows)

    elapsed = time.time() - t0
    print(f"\nRuntime: {elapsed:.1f} seconds")


if __name__ == "__main__":
    main()
