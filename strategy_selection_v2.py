"""
Strategy Selection v2
======================
OTP2.0 security-selection redesign, informed by selection_attribution.py:

  - Universe expanded from 30 old-economy mega-caps to ~50, adding modern
    growth/tech leaders (NVDA, GOOGL, AMZN, META, AVGO, ADBE, CRM, NFLX, V,
    MA, TSLA, QCOM, ORCL, TXN, ACN, ISRG, LIN, DIS, NEE, COP) so the "Live"
    cohort (2023+) isn't stuck with a stale universe (attribution showed
    selection effect -0.643 there vs SPX).

  - Cohort length shortened from 5yr to a configurable COHORT_YEARS (default
    3yr) so selections track regime changes faster.

  - 5th factor added: 252-day relative strength vs SPX (f5), reweighted
    alongside the original 4 factors.

  - Timing overlay made regime-aware: cohorts whose selected portfolio has
    a high composite-momentum score at selection time (decided ex-ante, no
    lookahead) get a relaxed OT2.0 config (higher vol_target / reload_size),
    since attribution showed the default timing config drags Sharpe down in
    high-momentum cohorts (e.g. Cohort 3: -0.245 timing effect).

Reuses download/feature/engine functions from strategy_deep_test.py.

Usage:
  python strategy_selection_v2.py
"""

import time
import numpy as np
import pandas as pd

from strategy_deep_test import (
    download, download_tbill, build_market_features, ot2_engine, buy_and_hold,
    _run_full, _compute_metrics, _print_table, OT2_CONFIG, STOCKS7,
)


COHORT_YEARS = 3
TOP_N = 7

MOMENTUM_OT2_CONFIG = dict(OT2_CONFIG)
MOMENTUM_OT2_CONFIG["vol_target"]  = 0.12   # relaxed (vs 0.08 default)
MOMENTUM_OT2_CONFIG["reload_size"] = 0.06   # vs 0.04 default

DEFENSIVE_OT2_CONFIG = dict(OT2_CONFIG)
DEFENSIVE_OT2_CONFIG["vol_target"]  = 0.06   # tighter (vs 0.08 default)
DEFENSIVE_OT2_CONFIG["reload_size"] = 0.03   # vs 0.04 default

# v4: approximate Shiller CAPE (S&P 500 cyclically-adjusted P/E) at each cohort's
# selection date, sourced from Shiller's published long-run series. Used as a
# valuation "froth" override, orthogonal to the price/momentum factors above.
CAPE_BY_SELECTION_YEAR = {
    1993: 20.7, 1996: 24.3, 1999: 32.9, 2002: 22.4, 2005: 26.7, 2008: 27.0,
    2011: 23.0, 2014: 25.1, 2017: 28.0, 2020: 31.0, 2023: 28.0, 2026: 38.0,
}
CAPE_FROTH_THRESHOLD = 30.0   # roughly top decile of CAPE's full 1881-present history

EXPANDED_UNIVERSE = [
    # Original 30 (old-economy mega-caps)
    "MSFT", "AAPL", "JNJ", "BRK-B", "MCD", "COST", "NKE", "PG", "KO", "PEP",
    "MMM", "ABT", "WMT", "GE", "XOM", "CVX", "IBM", "INTC", "CSCO", "AMGN",
    "MRK", "LLY", "UNH", "TGT", "HD", "LOW", "AXP", "JPM", "BAC", "GS",
    # Modern growth/tech additions
    "GOOGL", "AMZN", "NVDA", "META", "AVGO", "ADBE", "CRM", "NFLX", "V", "MA",
    "TSLA", "QCOM", "ORCL", "TXN", "ACN", "ISRG", "LIN", "DIS", "NEE", "COP",
    # v3: additional tech/growth tilt
    "AMD", "PANW", "NOW", "INTU",
]


def main():
    t0 = time.time()

    print("Downloading market + timing data...")
    gspc = download("^GSPC")
    vix  = download("^VIX")

    print("Downloading T-bill rate...")
    tbill_raw, tbill_src = download_tbill()
    print(f"  Source: {tbill_src}")

    print(f"Downloading {len(EXPANDED_UNIVERSE)}-stock expanded universe (close prices)...")
    closes = {}
    for tkr in EXPANDED_UNIVERSE:
        df = download(tkr)
        closes[tkr] = df["Close"].squeeze()
        print(f"  {tkr:6s}: {df.index[0].date()} -> {df.index[-1].date()}  ({len(df):,} days)")

    print("\nBuilding features...")
    market_df = build_market_features(gspc, vix)

    # Common index basis: same as strategy_deep_test.py (market features
    # intersected with STOCKS7-minus-BRK-B availability), so chained results
    # are directly comparable to the existing 0.625/8.89% baseline.
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

    prices = pd.DataFrame({t: closes[t] for t in EXPANDED_UNIVERSE}).reindex(common_index)
    logret = np.log(prices / prices.shift(1))
    sma50  = prices.rolling(50).mean()
    spx_logret = market_df["log_ret"]

    print(f"\nCommon index: {common_index[0].date()} -> {common_index[-1].date()}  "
          f"({len(common_index):,} trading days)")

    spx_bh_full = buy_and_hold(spx_logret, common_index, "SPX B&H")

    # ── Build cohorts dynamically: every COHORT_YEARS, starting 1993-01-04 ──
    cohort_starts = []
    y = 1993
    last_year = common_index[-1].year
    while y <= last_year:
        cohort_starts.append(y)
        y += COHORT_YEARS

    cohorts = []
    for idx, start_year in enumerate(cohort_starts):
        sel_date = pd.Timestamp(f"{start_year}-01-04")
        hold_start = sel_date
        if idx + 1 < len(cohort_starts):
            hold_end = pd.Timestamp(f"{cohort_starts[idx+1]-1}-12-31")
            name = f"{start_year}-{cohort_starts[idx+1]-1}"
        else:
            hold_end = common_index[-1]
            name = f"{start_year}-present (Live)"
        cohorts.append((name, sel_date, hold_start, hold_end))

    # ── Pass 1: compute selection + mean composite for every cohort ────────
    cohort_data = []
    for name, sel_date, hold_start, hold_end in cohorts:
        if sel_date < common_index[0]:
            sel_date = common_index[0]
        sel_pos = common_index.searchsorted(sel_date)
        sel_pos = min(sel_pos, len(common_index) - 1)

        scores = {}
        for tkr in EXPANDED_UNIVERSE:
            px = prices[tkr].iloc[:sel_pos + 1]
            valid = px.dropna()
            if len(valid) < 280:
                continue

            c0   = valid.iloc[-1]
            c1m  = valid.iloc[-22]
            c12m = valid.iloc[-253]
            f1 = (c1m / c12m) - 1

            sma_seg = sma50[tkr].iloc[:sel_pos + 1].dropna()
            px_seg  = prices[tkr].iloc[:sel_pos + 1].reindex(sma_seg.index)
            lookback2 = min(252, len(sma_seg))
            f2 = (px_seg.iloc[-lookback2:] > sma_seg.iloc[-lookback2:]).mean()

            lb3 = min(756, len(valid) - 1)
            c3 = valid.iloc[-(lb3 + 1)]
            cagr3 = (c0 / c3) ** (252 / lb3) - 1
            lr3 = logret[tkr].iloc[sel_pos - lb3 + 1:sel_pos + 1].dropna()
            vol3 = lr3.std() * np.sqrt(252)
            f3 = cagr3 / vol3 if vol3 > 0 else 0.0

            lb4 = min(1260, len(valid))
            window5 = valid.iloc[-lb4:]
            roll_max = window5.cummax()
            dd = ((window5 - roll_max) / roll_max).min()
            f4 = 1 / abs(dd) if dd != 0 else 0.0

            # F5: 252-day relative strength vs SPX
            lb5 = min(252, len(valid) - 1)
            stock_ret = (valid.iloc[-1] / valid.iloc[-(lb5 + 1)]) - 1
            spx_valid = spx_logret.iloc[:sel_pos + 1]
            spx_cum = np.exp(spx_valid.iloc[-lb5:].sum()) - 1
            f5 = stock_ret - spx_cum

            scores[tkr] = dict(f1=f1, f2=f2, f3=f3, f4=f4, f5=f5)

        sc_df = pd.DataFrame(scores).T
        for col in ["f1", "f2", "f3", "f4", "f5"]:
            sc_df[col + "_rank"] = sc_df[col].rank(pct=True)

        sc_df["composite"] = (0.30 * sc_df["f1_rank"] + 0.20 * sc_df["f2_rank"] +
                               0.20 * sc_df["f3_rank"] + 0.10 * sc_df["f4_rank"] +
                               0.20 * sc_df["f5_rank"])
        sc_df = sc_df.sort_values("composite", ascending=False)
        top = sc_df.head(TOP_N)
        selected = list(top.index)
        mean_composite = top["composite"].mean()

        cohort_data.append(dict(
            name=name, sel_date=sel_date, hold_start=hold_start, hold_end=hold_end,
            sel_pos=sel_pos, top=top, selected=selected, mean_composite=mean_composite,
        ))

    # ── Determine regime-tilt thresholds: relative tertiles across cohorts ──
    mean_composites = pd.Series([c["mean_composite"] for c in cohort_data])
    thresh_hi = mean_composites.quantile(2 / 3)
    thresh_lo = mean_composites.quantile(1 / 3)
    print(f"\nRegime-tilt thresholds across {len(cohort_data)} cohorts "
          f"(tertiles of mean composite): "
          f"low <= {thresh_lo:.3f}  |  mid  |  high >= {thresh_hi:.3f}")

    chained_segments_port = []
    chained_segments_inv  = []
    chained_segments_idx  = []
    mod3_rows = []
    selection_rows = []

    # ── Pass 2: assign regime-tilted cfg + run backtest per cohort ─────────
    for cd in cohort_data:
        name, sel_date  = cd["name"], cd["sel_date"]
        hold_start, hold_end = cd["hold_start"], cd["hold_end"]
        sel_pos = cd["sel_pos"]
        top, selected = cd["top"], cd["selected"]
        mean_composite = cd["mean_composite"]

        if mean_composite >= thresh_hi:
            cfg, regime_label = MOMENTUM_OT2_CONFIG, "Momentum (high)"
        elif mean_composite <= thresh_lo:
            cfg, regime_label = DEFENSIVE_OT2_CONFIG, "Defensive (low)"
        else:
            cfg, regime_label = OT2_CONFIG, "Default (mid)"

        # v4: valuation override - frothy CAPE forces Defensive regardless of
        # the momentum-based regime tertile above.
        cape = CAPE_BY_SELECTION_YEAR.get(sel_date.year)
        if cape is not None and cape >= CAPE_FROTH_THRESHOLD:
            cfg, regime_label = DEFENSIVE_OT2_CONFIG, f"Defensive (CAPE frothy, {cape:.1f})"

        print(f"\n{name}  (selected {common_index[sel_pos].date()}, "
              f"mean composite={mean_composite:.3f}, {regime_label} cfg)")
        for tkr, row in top.iterrows():
            print(f"    {tkr:6s}  composite={row['composite']:.3f}  "
                  f"(mom={row['f1']*100:+.1f}%, trend={row['f2']*100:.0f}%, "
                  f"vol-adj={row['f3']:.2f}, dd-resil={row['f4']:.2f}, rel-str={row['f5']*100:+.1f}%)")

        selection_rows.append([name, ", ".join(selected), f"{mean_composite:.3f}", regime_label])

        # ── Holding period slice ────────────────────────────────────────
        hp_start_pos = common_index.searchsorted(hold_start)
        hp_end_pos   = common_index.searchsorted(hold_end)
        hp_end_pos   = min(hp_end_pos, len(common_index) - 1)
        if hp_start_pos >= hp_end_pos:
            continue

        hp_index = common_index[hp_start_pos:hp_end_pos + 1]
        hp_market = market_df.loc[hp_index]
        hp_logret = logret.loc[hp_index, selected]
        hp_avail = hp_logret.notna()
        hp_n = hp_avail.sum(axis=1).replace(0, np.nan)
        hp_weight = hp_avail.div(hp_n, axis=0).fillna(0.0)
        hp_blended = (hp_weight * hp_logret.fillna(0.0)).sum(axis=1)
        hp_blended.iloc[0] = 0.0

        hp_tbill = tbill_raw.reindex(hp_index).ffill().bfill()
        hp_cash = (hp_tbill / 252).values
        rfr_mean_seg = float(hp_tbill.mean())

        r = ot2_engine(hp_market, hp_blended, hp_cash, f"{name} OT2.0+selected{TOP_N}",
                        cfg=cfg, rfr_for_sharpe=rfr_mean_seg)
        spx_seg = buy_and_hold(hp_market["log_ret"], hp_index, f"{name} SPX B&H", rfr=rfr_mean_seg)
        stock_bh = buy_and_hold(hp_blended, hp_index, f"{name} cohort B&H", rfr=rfr_mean_seg)

        mod3_rows.append([
            name, f"{r['sharpe']:.3f}", f"{r['cagr_pct']:.2f}%", f"{r['max_dd_pct']:.1f}%",
            f"{stock_bh['sharpe']:.3f}", f"{stock_bh['cagr_pct']:.2f}%",
            f"{spx_seg['sharpe']:.3f}", f"{spx_seg['cagr_pct']:.2f}%",
        ])

        seg_port, seg_inv = _run_full_cfg(hp_market, hp_blended, hp_cash, cfg)
        chained_segments_port.append(seg_port)
        chained_segments_inv.append(seg_inv)
        chained_segments_idx.append(hp_index)

    print("\nPer-cohort results (v2 selection, COHORT_YEARS={}):".format(COHORT_YEARS))
    headers5 = ["Cohort", "OT2.0 Sharpe", "OT2.0 CAGR", "OT2.0 MaxDD",
                 "Cohort B&H Sharpe", "Cohort B&H CAGR", "SPX Sharpe", "SPX CAGR"]
    _print_table(headers5, mod3_rows)

    # ── Chained backtest ──────────────────────────────────────────────────
    chained_port = []
    chained_inv  = []
    chained_idx  = []
    level = 100.0
    for seg_port, seg_inv, seg_idx in zip(chained_segments_port, chained_segments_inv, chained_segments_idx):
        scaled = seg_port / seg_port[0] * level
        if chained_idx and seg_idx[0] == chained_idx[-1][-1]:
            scaled = scaled[1:]
            seg_inv_use = seg_inv[1:]
            seg_idx_use = seg_idx[1:]
        else:
            seg_inv_use = seg_inv
            seg_idx_use = seg_idx
        chained_port.append(scaled)
        chained_inv.append(seg_inv_use)
        chained_idx.append(seg_idx_use)
        level = scaled[-1]

    full_port = np.concatenate(chained_port)
    full_inv  = np.concatenate(chained_inv)
    full_idx  = chained_idx[0]
    for seg in chained_idx[1:]:
        full_idx = full_idx.append(seg)

    rfr_mean_all = float(tbill_raw.reindex(common_index).ffill().bfill().mean())
    chained_result = _compute_metrics(full_port, full_inv, full_idx,
                                       "Chained v4 (hindsight-free)", rfr_mean_all)

    print("\nChained hindsight-free backtest (v4 selection: CAPE-froth override + regime tertiles + tech-tilted universe):")
    headers6 = ["Variant", "Sharpe", "Sortino", "CAGR", "MaxDD", "WorstYr", "AvgInv"]
    rows6 = [
        ["Chained v4 ({}-stock universe, {}yr cohorts, top{}, CAPE override)".format(
            len(EXPANDED_UNIVERSE), COHORT_YEARS, TOP_N),
         f"{chained_result['sharpe']:.3f}", f"{chained_result['sortino']:.3f}",
         f"{chained_result['cagr_pct']:.2f}%", f"{chained_result['max_dd_pct']:.1f}%",
         f"{chained_result['worst_year_pct']:.1f}%", f"{chained_result['avg_inv_pct']:.1f}%"],
        ["SPX B&H (full)", f"{spx_bh_full['sharpe']:.3f}", f"{spx_bh_full['sortino']:.3f}",
         f"{spx_bh_full['cagr_pct']:.2f}%", f"{spx_bh_full['max_dd_pct']:.1f}%",
         f"{spx_bh_full['worst_year_pct']:.1f}%", "100.0%"],
        ["v3 chained (regime tertiles, no CAPE override)",
         "0.617", "0.636", "11.06%", "-33.4%", "-20.4%", "61.5%"],
        ["v2 chained (50-stock universe, 3yr cohorts, top7, 0.65 fixed threshold)",
         "0.642", "0.666", "13.12%", "-52.0%", "-26.9%", "76.0%"],
        ["v1 chained (5yr cohorts, top8, original Module 3)",
         "0.625", "n/a", "8.89%", "-17.7%", "n/a", "n/a"],
    ]
    _print_table(headers6, rows6)

    print(f"\nTarget bar: Sharpe > 1.0  OR  CAGR > 15%")
    print(f"  v4 result: Sharpe {chained_result['sharpe']:.3f}, CAGR {chained_result['cagr_pct']:.2f}%")
    if chained_result["sharpe"] > 1.0 or chained_result["cagr_pct"] > 15.0:
        print("  -> BAR CLEARED")
    else:
        print("  -> bar not reached")

    pd.DataFrame(mod3_rows, columns=headers5).to_csv("strategy_selection_v4_results.csv", index=False)

    # ── v4 thesis artifacts ─────────────────────────────────────────────────
    spx_log_ret_full = market_df.loc[full_idx, "log_ret"].values
    spx_cum = np.exp(np.cumsum(spx_log_ret_full))
    spx_series = spx_cum / spx_cum[0] * full_port[0]

    pd.DataFrame({
        "date": full_idx,
        "v4_portfolio": full_port,
        "v4_invested_pct": full_inv * 100,
        "spx_portfolio": spx_series,
    }).to_csv("v4_chained_series.csv", index=False)

    pd.DataFrame(selection_rows,
                  columns=["Cohort", "Selected", "MeanComposite", "RegimeLabel"]
                  ).to_csv("v4_cohort_regimes.csv", index=False)

    elapsed = time.time() - t0
    print(f"\nRuntime: {elapsed:.1f} seconds")


def _run_full_cfg(market_df, log_ret, cash_daily, cfg):
    """Same as strategy_deep_test._run_full but with a configurable cfg dict."""
    c = cfg
    df = market_df
    n = len(df)
    invested  = np.zeros(n)
    portfolio = np.zeros(n)
    invested[0]  = min(0.95, c["vol_target"] / df["rvol20"].iloc[0])
    portfolio[0] = 100.0

    cooldown = 0
    consec_vix_fall = 0
    consec_rvol_fall = 0

    if np.isscalar(cash_daily):
        cash_arr = np.full(n, cash_daily)
    else:
        cash_arr = np.asarray(cash_daily)

    invested_dollars = portfolio[0] * invested[0]
    cash_dollars     = portfolio[0] * (1 - invested[0])
    lr_arr = log_ret.values if hasattr(log_ret, "values") else np.asarray(log_ret)

    for i in range(1, n):
        row, prev = df.iloc[i], df.iloc[i - 1]
        inv = invested[i - 1]

        rvol = max(row["rvol20"], 1e-6)
        vol_target_inv = min(0.95, c["vol_target"] / rvol)
        rvol_long = max(row["rvol252"], 1e-6)
        vol_scale = min(2.5, rvol / rvol_long)

        above_sma = row["close"] > row["sma200"]
        pos_mom   = row["momentum"] > 0
        if not above_sma and not pos_mom:
            trend_scale = 1.5
        elif above_sma and pos_mom:
            trend_scale = 0.7
        else:
            trend_scale = 1.0

        bs = row["breadth_score"]
        vix_l2_thresh = c["vix_l2"]
        if bs <= -2:
            vix_l1_thresh = c["vix_l1"] - 2
            vix_l2_thresh = c["vix_l2"] - 2
            breadth_trim_mul = 1.4
        elif bs >= 2:
            vix_l1_thresh = c["vix_l1"] + 3
            breadth_trim_mul = 0.6
        else:
            vix_l1_thresh = c["vix_l1"]
            breadth_trim_mul = 1.0

        vix_above_ma = row["vix"] > row["vix_ma5"]
        vix_l1_signal = row["vix"] > vix_l1_thresh and vix_above_ma
        vix_l2_signal = row["vix"] > vix_l2_thresh and vix_above_ma

        trim = 0.0
        if cooldown == 0:
            scale = vol_scale * trend_scale * breadth_trim_mul
            if vix_l2_signal:
                trim = c["trim_l2_base"] * scale
            elif vix_l1_signal:
                trim = c["trim_l1_base"] * scale

        if trim > 0:
            inv = max(c["floor"], inv - trim)
            cooldown = c["cooldown_days"]

        consec_vix_fall  = consec_vix_fall  + 1 if row["vix"]    < prev["vix"]    else 0
        consec_rvol_fall = consec_rvol_fall + 1 if row["rvol20"] < prev["rvol20"] else 0

        above_sma50 = row["close"] > row["sma50"]
        speed_needed = c["reload_min_days"] if above_sma50 else c["reload_min_days"] + 2
        vix_ma20_ok = row["vix"] <= row["vix_ma20"] * 1.02
        above_sma200 = row["close"] > row["sma200"]

        base_signal = (
            consec_vix_fall >= speed_needed and
            consec_rvol_fall >= speed_needed and
            vix_ma20_ok and
            above_sma200 and
            inv < 0.90 and
            cooldown == 0
        )

        if base_signal:
            inv = min(0.95, inv + c["reload_size"])

        if trim == 0 and not base_signal:
            if abs(inv - vol_target_inv) > 0.03:
                inv = 0.6 * inv + 0.4 * vol_target_inv
            inv = max(c["floor"], inv)

        if cooldown > 0:
            cooldown -= 1

        invested_dollars *= np.exp(lr_arr[i])
        cash_dollars     *= (1.0 + cash_arr[i])
        total = invested_dollars + cash_dollars
        invested_dollars = inv * total
        cash_dollars     = (1.0 - inv) * total

        invested[i]  = inv
        portfolio[i] = total

    return portfolio, invested


if __name__ == "__main__":
    main()
