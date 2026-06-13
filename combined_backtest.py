"""
Combined Backtest — OT2.0 Timing on a 7-Stock Outpacing Portfolio
==================================================================
Tests whether RRG and OBV filters on individual stock weights, layered
under OT2.0 market-timing (the reconciled engine from ot2_volume_test.py),
add value versus an equal-weight baseline.

Usage:
  python combined_backtest.py
"""

import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import yfinance as yf

try:
    from curl_cffi import requests as cffi_requests
    SESSION = cffi_requests.Session(impersonate="chrome")
except Exception:
    SESSION = None

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


START = "1990-01-01"

OT2_CONFIG = dict(
    vix_l1=20, vix_l2=28, trim_l1_base=0.08, trim_l2_base=0.10,
    reload_size=0.04, floor=0.30, cooldown_days=3, vol_target=0.08,
    reload_min_days=2, rfr=0.03, ref_vol=0.15,
)

STOCKS = ["MSFT", "JNJ", "BRK-B", "AAPL", "MCD", "COST", "NKE"]


# ─────────────────────────────────────────────────────────────────────────────
# 1. DATA DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

def download(ticker, retries=5, wait=20):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            kw = dict(start=START, auto_adjust=True, progress=False)
            if SESSION is not None:
                kw["session"] = SESSION
            df = yf.download(ticker, **kw)
            if df is not None and len(df) > 0:
                return df
            last_err = "empty result"
        except Exception as e:
            last_err = e
        if attempt < retries:
            print(f"\n    [{ticker}] attempt {attempt} failed ({last_err}), retrying in {wait}s ...",
                  end=" ", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {ticker}: {last_err}")


def download_all():
    data = {}
    print("Downloading market + timing data...")
    for tkr in ["^GSPC", "^VIX"]:
        df = download(tkr)
        data[tkr] = df
        print(f"  {tkr:6s}: {df.index[0].date()} -> {df.index[-1].date()}  ({len(df):,} days)")

    print("\nDownloading stock data...")
    for tkr in STOCKS:
        df = download(tkr)
        data[tkr] = df
        print(f"  {tkr:6s}: {df.index[0].date()} -> {df.index[-1].date()}  ({len(df):,} days)")

    return data


# ─────────────────────────────────────────────────────────────────────────────
# 2. FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────

def build_market_features(gspc, vix):
    df = pd.DataFrame({
        "close": gspc["Close"].squeeze(),
        "vix":   vix["Close"].squeeze(),
    }).dropna()

    df["returns"]  = df["close"].pct_change()
    df["sma50"]    = df["close"].rolling(50).mean()
    df["sma100"]   = df["close"].rolling(100).mean()
    df["sma200"]   = df["close"].rolling(200).mean()
    df["momentum"] = df["close"].pct_change(20)

    df["rvol20"]  = df["returns"].rolling(20).std()  * np.sqrt(252)
    df["rvol252"] = df["returns"].rolling(252).std() * np.sqrt(252)

    df["vix_ma5"]  = df["vix"].rolling(5).mean()
    df["vix_ma20"] = df["vix"].rolling(20).mean()

    # ── Breadth composite score (exact formula from ot2_volume_test.py) ─────
    above50  = df["close"] > df["sma50"]
    above100 = df["close"] > df["sma100"]
    above200 = df["close"] > df["sma200"]
    above_cnt = above50.astype(int) + above100.astype(int) + above200.astype(int)

    score = pd.Series(0, index=df.index, dtype=float)
    score = score.where(above_cnt != 0, score - 2)
    score = score.where(above_cnt != 1, score - 1)
    score = score.where(above_cnt != 3, score + 1)

    score = score - (df["sma50"] < df["sma100"]).astype(int)

    gap = (df["close"] - df["sma200"]) / df["sma200"]
    gap_fell = (gap.shift(10) - gap) > 0.015
    score = score - gap_fell.astype(int)

    sign_sum = np.sign(df["returns"]).rolling(20).sum()
    score = score - (sign_sum < -5).astype(int)
    score = score + (sign_sum > 5).astype(int)

    df["breadth_score"] = score

    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))

    return df.dropna(subset=[
        "close", "vix", "returns", "sma200", "momentum",
        "rvol20", "rvol252", "vix_ma5", "vix_ma20", "breadth_score", "log_ret",
    ])


def build_stock_features(stock_df, gspc_close):
    df = pd.DataFrame({
        "close":  stock_df["Close"].squeeze(),
        "volume": stock_df["Volume"].squeeze(),
    }).dropna()

    df["returns"] = df["close"].pct_change()
    df["log_ret"] = np.log(df["close"] / df["close"].shift(1))

    df["obv"]       = (np.sign(df["returns"]) * df["volume"]).cumsum()
    df["obv_slope"] = df["obv"] - df["obv"].shift(63)

    gspc_aligned = gspc_close.reindex(df.index)
    rs_relative  = df["close"] / gspc_aligned

    rs_ratio    = (rs_relative / rs_relative.rolling(260).mean()) * 100
    rs_momentum = (rs_ratio / rs_ratio.rolling(20).mean()) * 100

    df["rs_ratio"]    = rs_ratio
    df["rs_momentum"] = rs_momentum

    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. OT2.0 ENGINE  (reconciled, from ot2_volume_test.py)
# ─────────────────────────────────────────────────────────────────────────────

def ot2_engine(market_df, log_ret, label, cfg=None):
    """
    market_df : DataFrame aligned to common index, with OT2.0 timing
                features (close, sma50/100/200, momentum, rvol20/252,
                vix, vix_ma5/20, breadth_score).
    log_ret   : Series aligned to common index — the daily log return of
                whatever is INSIDE the invested bucket (GSPC for
                "OT2.0 on SPX", or the blended stock-portfolio log
                return for the 4 stock-portfolio variants).
    """
    if cfg is None:
        cfg = OT2_CONFIG
    c = cfg

    df = market_df
    n = len(df)
    invested  = np.zeros(n)
    portfolio = np.zeros(n)

    invested[0]  = min(0.95, c["vol_target"] / df["rvol20"].iloc[0])
    portfolio[0] = 100.0

    cooldown         = 0
    reload_count     = 0
    reloads_blocked  = 0
    consec_vix_fall  = 0
    consec_rvol_fall = 0
    rfr_daily = c["rfr"] / 252

    invested_dollars = portfolio[0] * invested[0]
    cash_dollars     = portfolio[0] * (1 - invested[0])

    lr_arr = log_ret.values

    for i in range(1, n):
        row  = df.iloc[i]
        prev = df.iloc[i - 1]
        inv  = invested[i - 1]

        rvol = max(row["rvol20"], 1e-6)
        vol_target_inv = min(0.95, c["vol_target"] / rvol)

        rvol_long = max(row["rvol252"], 1e-6)
        vol_scale = min(2.5, rvol / rvol_long)

        above_sma = row["close"]    > row["sma200"]
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
            vix_l1_thresh    = c["vix_l1"] - 2
            vix_l2_thresh    = c["vix_l2"] - 2
            breadth_trim_mul = 1.4
        elif bs >= 2:
            vix_l1_thresh    = c["vix_l1"] + 3
            breadth_trim_mul = 0.6
        else:
            vix_l1_thresh    = c["vix_l1"]
            breadth_trim_mul = 1.0

        vix_above_ma  = row["vix"] > row["vix_ma5"]
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
            inv      = max(c["floor"], inv - trim)
            cooldown = c["cooldown_days"]

        consec_vix_fall  = consec_vix_fall  + 1 if row["vix"]    < prev["vix"]    else 0
        consec_rvol_fall = consec_rvol_fall + 1 if row["rvol20"] < prev["rvol20"] else 0

        above_sma50  = row["close"] > row["sma50"]
        speed_needed = c["reload_min_days"] if above_sma50 else c["reload_min_days"] + 2
        vix_ma20_ok  = row["vix"] <= row["vix_ma20"] * 1.02
        above_sma200 = row["close"] > row["sma200"]

        base_signal = (
            consec_vix_fall  >= speed_needed and
            consec_rvol_fall >= speed_needed and
            vix_ma20_ok and
            above_sma200 and
            inv < 0.90 and
            cooldown == 0
        )

        if base_signal:
            inv = min(0.95, inv + c["reload_size"])
            reload_count += 1

        if trim == 0 and not base_signal:
            if abs(inv - vol_target_inv) > 0.03:
                inv = 0.6 * inv + 0.4 * vol_target_inv
            inv = max(c["floor"], inv)

        if cooldown > 0:
            cooldown -= 1

        invested_dollars *= np.exp(lr_arr[i])
        cash_dollars     *= (1.0 + rfr_daily)
        total = invested_dollars + cash_dollars

        invested_dollars = inv * total
        cash_dollars     = (1.0 - inv) * total

        invested[i]  = inv
        portfolio[i] = total

    return _compute_metrics(portfolio, invested, df.index, label, c,
                             reload_count, reloads_blocked)


def _compute_metrics(portfolio, invested, index, label, c,
                      reload_count=0, reloads_blocked=0,
                      n_active=None, hhi=None):
    port_s = pd.Series(portfolio, index=index)

    years   = len(portfolio) / 252
    cagr    = (portfolio[-1] / portfolio[0]) ** (1 / years) - 1
    vol_ann = port_s.pct_change().dropna().std() * np.sqrt(252)

    lr     = np.diff(np.log(portfolio))
    rfr_d  = np.log(1 + c["rfr"]) / 252
    sharpe = (lr.mean() - rfr_d) / lr.std() * np.sqrt(252)

    neg    = lr[lr < 0]
    dd_std = np.sqrt((neg ** 2).mean()) * np.sqrt(252) * 100
    sortino = (cagr - c["rfr"] * 100) / dd_std if dd_std > 0 else 0.0

    roll_max = port_s.cummax()
    max_dd   = ((port_s - roll_max) / roll_max).min()

    annual_r   = port_s.resample("A").last().pct_change().dropna()
    worst_year = annual_r.min()

    avg_inv = np.mean(invested)

    return {
        "label":           label,
        "sharpe":          sharpe,
        "sortino":         sortino,
        "cagr_pct":        cagr * 100,
        "vol_pct":         vol_ann * 100,
        "max_dd_pct":      max_dd * 100,
        "worst_year_pct":  worst_year * 100,
        "avg_inv_pct":     avg_inv * 100,
        "avg_active":      np.nan if n_active is None else np.mean(n_active),
        "avg_hhi":         np.nan if hhi is None else np.mean(hhi),
        "reload_count":    reload_count,
        "reloads_blocked": reloads_blocked,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. BUY & HOLD HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def buy_and_hold(log_ret, index, label, c=OT2_CONFIG, n_active=None, hhi=None):
    portfolio = 100.0 * np.exp(np.cumsum(np.concatenate([[0.0], log_ret.values[1:]])))
    invested = np.ones(len(portfolio))
    return _compute_metrics(portfolio, invested, index, label, c,
                             n_active=n_active, hhi=hhi)


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()

    data = download_all()

    print("\nBuilding features...")
    market_df = build_market_features(data["^GSPC"], data["^VIX"])
    gspc_close = data["^GSPC"]["Close"].squeeze()

    stock_feats = {}
    for tkr in STOCKS:
        stock_feats[tkr] = build_stock_features(data[tkr], gspc_close)

    # ── Common index: market features ∩ feature-valid range of the 6
    #    non-BRK-B stocks. BRK-B is reindexed onto this and will be NaN
    #    before its own history starts (1996).
    common_index = market_df.index
    for tkr in STOCKS:
        if tkr == "BRK-B":
            continue
        valid = stock_feats[tkr].dropna(subset=["log_ret", "obv_slope", "rs_ratio", "rs_momentum"]).index
        common_index = common_index.intersection(valid)

    market_df = market_df.loc[common_index]

    aligned = {}
    for tkr in STOCKS:
        aligned[tkr] = stock_feats[tkr].reindex(common_index)

    print(f"\nCommon index: {common_index[0].date()} -> {common_index[-1].date()}  "
          f"({len(common_index):,} trading days)")
    brk_start = aligned["BRK-B"]["log_ret"].first_valid_index()
    print(f"  BRK-B included from: {brk_start.date()}  "
          f"(6-stock portfolio before, 7-stock from then on)")

    # ── Stack stock-level series into DataFrames (rows=dates, cols=stocks)
    log_ret_df    = pd.DataFrame({t: aligned[t]["log_ret"]    for t in STOCKS}, index=common_index)
    obv_slope_df  = pd.DataFrame({t: aligned[t]["obv_slope"]  for t in STOCKS}, index=common_index)
    rs_ratio_df   = pd.DataFrame({t: aligned[t]["rs_ratio"]   for t in STOCKS}, index=common_index)
    rs_mom_df     = pd.DataFrame({t: aligned[t]["rs_momentum"]for t in STOCKS}, index=common_index)

    available = log_ret_df.notna()
    n_avail = available.sum(axis=1)
    equal_weight = available.div(n_avail, axis=0).fillna(0.0)

    # ── RRG classification ────────────────────────────────────────────────
    leading    = (rs_ratio_df > 100) & (rs_mom_df > 100)
    improving  = (rs_ratio_df < 100) & (rs_mom_df > 100)
    weakening  = (rs_ratio_df > 100) & (rs_mom_df < 100)
    lagging    = (rs_ratio_df < 100) & (rs_mom_df < 100)
    rrg_valid  = rs_ratio_df.notna() & rs_mom_df.notna()

    rrg_factor = pd.DataFrame(1.0, index=common_index, columns=STOCKS)
    rrg_factor[leading]   = 1.0
    rrg_factor[improving] = 1.0
    rrg_factor[weakening] = 0.5
    rrg_factor[lagging]   = 0.0
    rrg_factor = rrg_factor.where(rrg_valid, 1.0)   # no RS history yet -> neutral

    # ── OBV factor ───────────────────────────────────────────────────────
    obv_factor = pd.DataFrame(1.0, index=common_index, columns=STOCKS)
    obv_factor = obv_factor.where(obv_slope_df.isna() | (obv_slope_df > 0), 0.5)

    # Lag both filters by one day: today's weight must be set using only
    # information known at yesterday's close, to avoid using the same
    # day's price move both to classify the stock and to weight its return.
    rrg_factor = rrg_factor.shift(1).fillna(1.0)
    obv_factor = obv_factor.shift(1).fillna(1.0)

    # ── Weight schemes ───────────────────────────────────────────────────
    def normalise(w):
        s = w.sum(axis=1)
        out = w.div(s, axis=0)
        # fallback to equal weight where everything zeroed out
        zero_rows = (s == 0)
        out.loc[zero_rows] = equal_weight.loc[zero_rows]
        return out.fillna(0.0)

    weights = {}
    weights["Baseline"] = equal_weight

    w_rrg = equal_weight * rrg_factor
    weights["+RRG"] = normalise(w_rrg)

    w_obv = equal_weight * obv_factor
    weights["+OBV"] = normalise(w_obv)

    w_combo = equal_weight * rrg_factor * obv_factor
    weights["+RRG+OBV"] = normalise(w_combo)

    # ── Blended log returns per variant ─────────────────────────────────
    blended_log_ret = {}
    for name, w in weights.items():
        blended_log_ret[name] = (w * log_ret_df.fillna(0.0)).sum(axis=1)
        blended_log_ret[name].iloc[0] = 0.0

    # ── Stats: avg stocks active, avg HHI ────────────────────────────────
    stats = {}
    for name, w in weights.items():
        active = (w > 0).sum(axis=1)
        hhi = (w ** 2).sum(axis=1)
        stats[name] = (active.values, hhi.values)

    # ── Run everything ────────────────────────────────────────────────────
    print("\nRunning backtests...")
    results = []

    spx_log_ret = market_df["log_ret"]

    r = buy_and_hold(spx_log_ret, common_index, "SPX B&H",
                      n_active=np.ones(len(common_index)), hhi=np.ones(len(common_index)))
    print(f"  SPX B&H ... Sharpe {r['sharpe']:.3f}")
    results.append(r)

    seven_active, seven_hhi = stats["Baseline"]
    r = buy_and_hold(blended_log_ret["Baseline"], common_index, "7-stock B&H",
                      n_active=seven_active, hhi=seven_hhi)
    print(f"  7-stock B&H ... Sharpe {r['sharpe']:.3f}")
    results.append(r)

    r = ot2_engine(market_df, spx_log_ret, "OT2.0 on SPX")
    r["avg_active"] = 1.0
    r["avg_hhi"] = 1.0
    print(f"  OT2.0 on SPX ... Sharpe {r['sharpe']:.3f}")
    results.append(r)

    variant_labels = {
        "Baseline":  "OT2.0 + Baseline (equal-wt)",
        "+RRG":      "OT2.0 + RRG filter",
        "+OBV":      "OT2.0 + OBV filter",
        "+RRG+OBV":  "OT2.0 + RRG + OBV",
    }
    for key, label in variant_labels.items():
        r = ot2_engine(market_df, blended_log_ret[key], label)
        active, hhi = stats[key]
        r["avg_active"] = np.mean(active)
        r["avg_hhi"] = np.mean(hhi)
        print(f"  {label} ... Sharpe {r['sharpe']:.3f}")
        results.append(r)

    # ── Reporting ────────────────────────────────────────────────────────
    print_results(results)

    pd.DataFrame(results).to_csv("combined_backtest_results.csv", index=False)
    print("\nResults saved -> combined_backtest_results.csv")

    # ── Sanity checks ────────────────────────────────────────────────────
    print("\nSANITY CHECKS")
    print("-" * 60)

    ot2_spx_sharpe = results[2]["sharpe"]
    ok1 = abs(ot2_spx_sharpe - 0.497) <= 0.03
    print(f"1. OT2.0 on SPX Sharpe = {ot2_spx_sharpe:.3f} "
          f"(target 0.497 +/- 0.03) -> {'PASS' if ok1 else 'FAIL'}")

    spx_cagr = results[0]["cagr_pct"]
    seven_cagr = results[1]["cagr_pct"]
    ok2 = seven_cagr > spx_cagr
    print(f"2. 7-stock B&H CAGR = {seven_cagr:.2f}%  vs  SPX B&H CAGR = {spx_cagr:.2f}% "
          f"-> {'PASS' if ok2 else 'FAIL'}")

    baseline_sharpe = results[3]["sharpe"]
    ok3 = baseline_sharpe > ot2_spx_sharpe
    print(f"3. Baseline Sharpe = {baseline_sharpe:.3f}  vs  OT2.0 on SPX Sharpe = {ot2_spx_sharpe:.3f} "
          f"-> {'PASS' if ok3 else 'FAIL'}")

    print("\n4. +RRG classification breakdown (% of stock-days, over valid RS history):")
    total_valid = rrg_valid.sum().sum()
    for name, mask in [("Leading", leading), ("Improving", improving),
                        ("Weakening", weakening), ("Lagging", lagging)]:
        cnt = (mask & rrg_valid).sum().sum()
        pct = cnt / total_valid * 100 if total_valid > 0 else 0.0
        print(f"     {name:10s}: {pct:5.1f}%")

    elapsed = time.time() - t0
    print(f"\nRuntime: {elapsed:.1f} seconds")


def print_results(results):
    headers = ["Variant", "Sharpe", "Sortino", "CAGR", "Vol", "MaxDD",
               "Worst Yr", "Avg Inv", "Avg Active", "Avg HHI"]
    rows = []
    for r in results:
        rows.append([
            r["label"],
            f"{r['sharpe']:.3f}",
            f"{r['sortino']:.3f}",
            f"{r['cagr_pct']:.2f}%",
            f"{r['vol_pct']:.2f}%",
            f"{r['max_dd_pct']:.1f}%",
            f"{r['worst_year_pct']:.1f}%",
            f"{r['avg_inv_pct']:.1f}%",
            f"{r['avg_active']:.2f}",
            f"{r['avg_hhi']:.3f}",
        ])

    print()
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        w = [30, 8, 8, 7, 7, 7, 9, 8, 10, 8]
        header_line = "  ".join(h.ljust(w[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-" * len(header_line))
        for row in rows:
            print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(row)))

    baseline = results[3]
    print()
    print("DELTA vs BASELINE (OT2.0 + Baseline equal-weight)")
    print("-" * 60)
    for r in results:
        if r is baseline:
            continue
        ds = r["sharpe"]     - baseline["sharpe"]
        dt = r["sortino"]    - baseline["sortino"]
        dc = r["cagr_pct"]   - baseline["cagr_pct"]
        dd = r["max_dd_pct"] - baseline["max_dd_pct"]
        print(f"  {r['label']:30s}  Sharpe {ds:+.3f}   Sortino {dt:+.3f}   "
              f"CAGR {dc:+.2f}%   MaxDD {dd:+.1f}pp")


if __name__ == "__main__":
    main()
