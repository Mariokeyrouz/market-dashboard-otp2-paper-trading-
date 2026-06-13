"""
Strategy Deep Test
==================
Extends combined_backtest.py with three modules:
  1. Cash drag — flat 3% vs historical T-bill vs T-bill+50bp
  2. Regime / horizon analysis (named bear markets, rolling Sharpe)
  3. Hindsight-free rolling-cohort stock selection

All three share the same OT2.0 two-bucket engine.

Usage:
  python strategy_deep_test.py
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

try:
    import pandas_datareader.data as pdr
except ImportError:
    pdr = None


START = "1990-01-01"

OT2_CONFIG = dict(
    vix_l1=20, vix_l2=28, trim_l1_base=0.08, trim_l2_base=0.10,
    reload_size=0.04, floor=0.30, cooldown_days=3, vol_target=0.08,
    reload_min_days=2, rfr=0.03, ref_vol=0.15,
)

STOCKS7 = ["MSFT", "JNJ", "BRK-B", "AAPL", "MCD", "COST", "NKE"]

UNIVERSE30 = [
    "MSFT", "AAPL", "JNJ", "BRK-B", "MCD", "COST", "NKE", "PG", "KO", "PEP",
    "MMM", "ABT", "WMT", "GE", "XOM", "CVX", "IBM", "INTC", "CSCO", "AMGN",
    "MRK", "LLY", "UNH", "TGT", "HD", "LOW", "AXP", "JPM", "BAC", "GS",
]


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


def download_tbill():
    """3-month T-bill rate as a decimal (e.g. 0.03), daily, forward-filled."""
    if pdr is not None:
        try:
            tbill = pdr.get_data_fred("DTB3", start=START)
            tbill = tbill / 100.0
            tbill = tbill.resample("D").ffill()
            s = tbill["DTB3"].dropna()
            if len(s) > 252 * 5:
                return s, "FRED DTB3"
        except Exception as e:
            print(f"  [FRED DTB3 failed: {e}]")

    irx = download("^IRX")
    s = (irx["Close"].squeeze() / 100.0).dropna()
    return s, "^IRX (yfinance proxy)"


# ─────────────────────────────────────────────────────────────────────────────
# 2. FEATURE ENGINEERING (market timing layer)
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


# ─────────────────────────────────────────────────────────────────────────────
# 3. OT2.0 ENGINE — two-bucket, time-varying cash yield
# ─────────────────────────────────────────────────────────────────────────────

def ot2_engine(market_df, log_ret, cash_daily, label, cfg=None, rfr_for_sharpe=None):
    """
    market_df      : OT2.0 timing features, aligned to common index.
    log_ret        : daily log return of the invested bucket's contents.
    cash_daily     : daily simple return earned by the cash bucket
                      (e.g. tbill/252). Scalar or array-like, same length.
    rfr_for_sharpe : annualised RFR used in Sharpe/Sortino. Defaults to
                      cfg['rfr']; pass the mean cash yield for T-bill runs.
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
    consec_vix_fall  = 0
    consec_rvol_fall = 0

    if np.isscalar(cash_daily):
        cash_arr = np.full(n, cash_daily)
    else:
        cash_arr = np.asarray(cash_daily)

    invested_dollars = portfolio[0] * invested[0]
    cash_dollars     = portfolio[0] * (1 - invested[0])

    lr_arr = log_ret.values if hasattr(log_ret, "values") else np.asarray(log_ret)

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

    rfr = c["rfr"] if rfr_for_sharpe is None else rfr_for_sharpe
    return _compute_metrics(portfolio, invested, df.index, label, rfr)


def buy_and_hold(log_ret, index, label, rfr=0.03):
    portfolio = 100.0 * np.exp(np.cumsum(np.concatenate([[0.0], log_ret.values[1:]])))
    invested = np.ones(len(portfolio))
    return _compute_metrics(portfolio, invested, index, label, rfr)


def _compute_metrics(portfolio, invested, index, label, rfr):
    port_s = pd.Series(portfolio, index=index)

    years   = len(portfolio) / 252
    cagr    = (portfolio[-1] / portfolio[0]) ** (1 / years) - 1
    vol_ann = port_s.pct_change().dropna().std() * np.sqrt(252)

    lr = np.diff(np.log(portfolio))

    # ── Fixed Sortino / Sharpe (Module 1 spec) ─────────────────────────────
    rfr_d  = np.log(1 + rfr) / 252
    sharpe = (lr.mean() - rfr_d) / lr.std() * np.sqrt(252) if lr.std() > 0 else 0.0

    neg = lr[lr < 0]
    downside_std = np.sqrt(np.mean(neg ** 2)) * np.sqrt(252) if len(neg) > 0 else 0.0
    excess_cagr = cagr - rfr
    sortino = excess_cagr / downside_std if downside_std > 0 else 0.0

    roll_max = port_s.cummax()
    max_dd   = ((port_s - roll_max) / roll_max).min()

    annual_r   = port_s.resample("A").last().pct_change().dropna()
    worst_year = annual_r.min() if len(annual_r) > 0 else np.nan

    avg_inv = np.mean(invested)

    return {
        "label":          label,
        "sharpe":         sharpe,
        "sortino":        sortino,
        "cagr_pct":       cagr * 100,
        "vol_pct":        vol_ann * 100,
        "max_dd_pct":     max_dd * 100,
        "worst_year_pct": worst_year * 100 if not np.isnan(worst_year) else np.nan,
        "avg_inv_pct":    avg_inv * 100,
    }


def _log_ret_array(portfolio):
    return np.diff(np.log(portfolio))


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    all_results = []

    # ── Download ────────────────────────────────────────────────────────────
    print("Downloading market + timing data...")
    gspc = download("^GSPC")
    vix  = download("^VIX")
    print(f"  ^GSPC : {gspc.index[0].date()} -> {gspc.index[-1].date()}  ({len(gspc):,} days)")
    print(f"  ^VIX  : {vix.index[0].date()} -> {vix.index[-1].date()}  ({len(vix):,} days)")

    print("\nDownloading T-bill rate...")
    tbill_raw, tbill_src = download_tbill()
    print(f"  Source: {tbill_src}  ({tbill_raw.index[0].date()} -> {tbill_raw.index[-1].date()})")

    print("\nDownloading 30-stock universe (close prices)...")
    closes = {}
    for tkr in UNIVERSE30:
        df = download(tkr)
        closes[tkr] = df["Close"].squeeze()
        print(f"  {tkr:6s}: {df.index[0].date()} -> {df.index[-1].date()}  ({len(df):,} days)")

    # ── Build market features + common index ─────────────────────────────
    print("\nBuilding features...")
    market_df = build_market_features(gspc, vix)

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

    log_ret7_df = pd.DataFrame({t: log_ret7[t] for t in STOCKS7}).reindex(common_index)
    available7 = log_ret7_df.notna()
    n_avail7 = available7.sum(axis=1)
    eq_weight7 = available7.div(n_avail7, axis=0).fillna(0.0)
    blended7 = (eq_weight7 * log_ret7_df.fillna(0.0)).sum(axis=1)
    blended7.iloc[0] = 0.0

    spx_log_ret = market_df["log_ret"]

    print(f"\nCommon index: {common_index[0].date()} -> {common_index[-1].date()}  "
          f"({len(common_index):,} trading days)")

    # Hindsight 7-stock reference results (flat 3% cash, for Module 3 comparison)
    flat3_daily = 0.03 / 252
    hindsight_baseline = ot2_engine(market_df, blended7, flat3_daily,
                                     "OT2.0 + 7-stock (hindsight, flat 3%)")
    spx_bh_full = buy_and_hold(spx_log_ret, common_index, "SPX B&H (full)")
    seven_bh_full = buy_and_hold(blended7, common_index, "7-stock B&H (hindsight, full)")

    # ── T-bill series aligned to common_index ──────────────────────────────
    tbill = tbill_raw.reindex(common_index).ffill().bfill()
    tbill_daily       = (tbill / 252).values
    tbill50_daily     = ((tbill + 0.005) / 252).values

    # =========================================================================
    # MODULE 1 — CASH DRAG
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODULE 1 — CASH DRAG: FLAT 3% vs T-BILL vs T-BILL+50BP")
    print("=" * 70)

    years_total = len(common_index) / 252

    scenarios = {
        "Flat 3% (current)":  (np.full(len(common_index), flat3_daily), 0.03),
        "T-bill (historical)": (tbill_daily, float(tbill.mean())),
        "T-bill + 50bp":      (tbill50_daily, float(tbill.mean()) + 0.005),
    }

    mod1_rows = []
    mod1_results = []
    for name, (cash_arr, avg_yield) in scenarios.items():
        r = ot2_engine(market_df, blended7, cash_arr,
                        f"OT2.0 + Baseline ({name})", rfr_for_sharpe=avg_yield)
        avg_cash_weight = 1 - r["avg_inv_pct"] / 100
        cash_contribution_pct = avg_cash_weight * avg_yield * years_total * 100 / years_total
        # cash_contribution expressed as annualised CAGR contribution (pp)
        cash_contrib_pp = avg_cash_weight * avg_yield * 100

        mod1_rows.append([
            name, f"{r['sharpe']:.3f}", f"{r['sortino']:.3f}", f"{r['cagr_pct']:.2f}%",
            f"{r['vol_pct']:.2f}%", f"{r['max_dd_pct']:.1f}%",
            f"{avg_yield*100:.2f}%", f"{cash_contrib_pp:.2f}pp",
        ])
        r["scenario"] = name
        r["avg_cash_yield_pct"] = avg_yield * 100
        r["cash_contribution_pp"] = cash_contrib_pp
        mod1_results.append(r)
        all_results.append(r)

    headers1 = ["Scenario", "Sharpe", "Sortino", "CAGR", "Vol", "MaxDD",
                 "Avg Cash Yield", "Cash CAGR Contrib"]
    print()
    _print_table(headers1, mod1_rows)

    flat_cagr = mod1_results[0]["cagr_pct"]
    tbill_cagr = mod1_results[1]["cagr_pct"]
    print(f"\nCAGR improvement, T-bill vs flat 3%: {tbill_cagr - flat_cagr:+.2f}pp "
          f"(of which ~{mod1_results[1]['cash_contribution_pp'] - mod1_results[0]['cash_contribution_pp']:+.2f}pp "
          f"attributable to higher cash yield, remainder to timing/sequencing)")

    cash_drag_reduction = tbill_cagr - flat_cagr

    # =========================================================================
    # MODULE 2 — REGIME AND HORIZON ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODULE 2 — REGIME AND HORIZON ANALYSIS  (T-bill cash)")
    print("=" * 70)

    strat_tbill = ot2_engine(market_df, blended7, tbill_daily,
                              "OT2.0 + Baseline (T-bill)", rfr_for_sharpe=float(tbill.mean()))
    all_results.append(strat_tbill)

    # Re-run engine to get full portfolio/invested arrays for regime slicing
    strat_port, strat_inv = _run_full(market_df, blended7, tbill_daily)
    spx_port = 100.0 * np.exp(np.cumsum(np.concatenate([[0.0], spx_log_ret.values[1:]])))
    seven_port = 100.0 * np.exp(np.cumsum(np.concatenate([[0.0], blended7.values[1:]])))

    rfr_mean = float(tbill.mean())

    # ── Regime definitions ──────────────────────────────────────────────────
    above200 = market_df["close"] > market_df["sma200"]
    vix_s = market_df["vix"]
    bull_low  = above200 & (vix_s < 18)
    bull_high = above200 & (vix_s >= 18)
    bear_low  = (~above200) & (vix_s < 28)
    bear_high = (~above200) & (vix_s >= 28)

    tbill_annual = tbill_raw.resample("A").last()
    tbill_yoy = tbill_annual.diff()
    shock_years = set(tbill_yoy[tbill_yoy > 0.015].index.year)
    rate_shock = pd.Series(common_index.year, index=common_index).isin(shock_years)

    regimes = {
        "Bull low-vol":  bull_low,
        "Bull high-vol": bull_high,
        "Bear low-vol":  bear_low,
        "Bear high-vol": bear_high,
        "Rate shock (>150bp YoY)": rate_shock,
    }

    print("\nRegime breakdown:")
    headers2 = ["Regime", "Days", "Strat Sharpe", "Strat CAGR", "Strat MaxDD", "Strat AvgInv",
                 "SPX Sharpe", "SPX CAGR", "7stk Sharpe", "7stk CAGR"]
    rows2 = []
    for name, mask in regimes.items():
        mask_arr = mask.values
        n_days = int(mask_arr.sum())
        if n_days < 10:
            rows2.append([name, n_days] + ["-"] * 8)
            continue

        sm = _subset_metrics(strat_port, strat_inv, mask_arr, rfr_mean)
        spm = _subset_metrics(spx_port, None, mask_arr, rfr_mean)
        s7m = _subset_metrics(seven_port, None, mask_arr, rfr_mean)

        rows2.append([
            name, n_days,
            f"{sm['sharpe']:.3f}", f"{sm['cagr_pct']:.2f}%", f"{sm['max_dd_pct']:.1f}%", f"{sm['avg_inv_pct']:.1f}%",
            f"{spm['sharpe']:.3f}", f"{spm['cagr_pct']:.2f}%",
            f"{s7m['sharpe']:.3f}", f"{s7m['cagr_pct']:.2f}%",
        ])
        sm["regime"] = name
        all_results.append({**sm, "label": f"Regime: {name} (strategy)"})

    _print_table(headers2, rows2)

    # ── Named bear market periods ───────────────────────────────────────────
    print("\nNamed bear-market periods:")
    bear_periods = {
        "Dot-com":        ("2000-03-01", "2002-10-09"),
        "GFC":            ("2007-10-09", "2009-03-09"),
        "COVID crash":    ("2020-02-19", "2020-03-23"),
        "COVID recovery": ("2020-03-23", "2020-08-18"),
        "2022 bear":      ("2022-01-03", "2022-10-12"),
    }

    headers3 = ["Period", "Strat Ret", "SPX Ret", "7stk Ret", "Strat MaxDD",
                 "Days to New High (Strat)"]
    rows3 = []
    for name, (start, end) in bear_periods.items():
        sd, ed = pd.Timestamp(start), pd.Timestamp(end)
        if sd < common_index[0] or sd > common_index[-1]:
            rows3.append([name, "n/a (out of range)", "-", "-", "-", "-"])
            continue
        idx_start = common_index.searchsorted(sd)
        idx_end   = common_index.searchsorted(ed)
        idx_start = min(idx_start, len(common_index) - 1)
        idx_end   = min(idx_end, len(common_index) - 1)

        strat_ret = strat_port[idx_end] / strat_port[idx_start] - 1
        spx_ret   = spx_port[idx_end] / spx_port[idx_start] - 1
        seven_ret = seven_port[idx_end] / seven_port[idx_start] - 1

        window = strat_port[idx_start:idx_end + 1]
        roll_max = np.maximum.accumulate(window)
        max_dd = ((window - roll_max) / roll_max).min()

        pre_peak = strat_port[:idx_start + 1].max()
        days_to_high = "not yet"
        for j in range(idx_end, len(strat_port)):
            if strat_port[j] >= pre_peak:
                days_to_high = j - idx_end
                break

        rows3.append([
            name, f"{strat_ret*100:+.1f}%", f"{spx_ret*100:+.1f}%", f"{seven_ret*100:+.1f}%",
            f"{max_dd*100:.1f}%", str(days_to_high),
        ])

    _print_table(headers3, rows3)

    # ── Rolling window analysis ──────────────────────────────────────────────
    print("\nRolling window analysis:")
    strat_lr = _log_ret_array(strat_port)
    spx_lr   = _log_ret_array(spx_port)
    seven_lr = _log_ret_array(seven_port)
    dates_lr = common_index[1:]

    rfr_d_mean = np.log(1 + rfr_mean) / 252

    def rolling_sharpe_cagr(lr, window):
        n = len(lr)
        sharpes = np.full(n - window + 1, np.nan)
        cagrs   = np.full(n - window + 1, np.nan)
        for k in range(window, n + 1):
            w = lr[k - window:k]
            std = w.std()
            sharpes[k - window] = (w.mean() - rfr_d_mean) / std * np.sqrt(252) if std > 0 else 0.0
            cagrs[k - window]   = np.exp(w.mean() * 252) - 1
        return sharpes, cagrs

    headers4 = ["Window", "Median Sharpe", "P10 Sharpe", "P90 Sharpe",
                 "% Beat SPX (Sharpe)", "% Beat SPX (CAGR)", "Worst Sharpe", "Worst Window"]
    rows4 = []
    for label, window in [("1yr", 252), ("3yr", 756), ("5yr", 1260), ("10yr", 2520)]:
        if window >= len(strat_lr):
            rows4.append([label, "insufficient data"] + ["-"] * 6)
            continue
        s_sh, s_cg = rolling_sharpe_cagr(strat_lr, window)
        x_sh, x_cg = rolling_sharpe_cagr(spx_lr, window)

        beat_sharpe = np.mean(s_sh > x_sh) * 100
        beat_cagr   = np.mean(s_cg > x_cg) * 100

        worst_idx = np.argmin(s_sh)
        worst_start = dates_lr[worst_idx]
        worst_end   = dates_lr[worst_idx + window - 1]

        rows4.append([
            label,
            f"{np.median(s_sh):.3f}", f"{np.percentile(s_sh, 10):.3f}", f"{np.percentile(s_sh, 90):.3f}",
            f"{beat_sharpe:.0f}%", f"{beat_cagr:.0f}%",
            f"{s_sh[worst_idx]:.3f}", f"{worst_start.date()} -> {worst_end.date()}",
        ])

    _print_table(headers4, rows4)

    # =========================================================================
    # MODULE 3 — HINDSIGHT-FREE STOCK SELECTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODULE 3 — HINDSIGHT-FREE ROLLING-COHORT STOCK SELECTION")
    print("=" * 70)

    prices30 = pd.DataFrame({t: closes[t] for t in UNIVERSE30}).reindex(common_index)
    logret30 = np.log(prices30 / prices30.shift(1))
    sma50_30 = prices30.rolling(50).mean()

    cohorts = [
        ("Cohort 1", "1993-01-04", "1993-01-04", "1997-12-31"),
        ("Cohort 2", "1998-01-02", "1998-01-02", "2002-12-31"),
        ("Cohort 3", "2003-01-02", "2003-01-02", "2007-12-31"),
        ("Cohort 4", "2008-01-02", "2008-01-02", "2012-12-31"),
        ("Cohort 5", "2013-01-02", "2013-01-02", "2017-12-31"),
        ("Cohort 6", "2018-01-02", "2018-01-02", "2022-12-31"),
        ("Live",     "2023-01-03", "2023-01-03", str(common_index[-1].date())),
    ]

    chained_segments_port = []
    chained_segments_inv  = []
    chained_segments_idx  = []
    mod3_rows = []

    for name, sel_str, hold_start_str, hold_end_str in cohorts:
        sel_date = pd.Timestamp(sel_str)
        hold_start = pd.Timestamp(hold_start_str)
        hold_end   = pd.Timestamp(hold_end_str)

        if sel_date < common_index[0]:
            sel_date = common_index[0]
        sel_pos = common_index.searchsorted(sel_date)
        sel_pos = min(sel_pos, len(common_index) - 1)
        sel_date_actual = common_index[sel_pos]

        scores = {}
        for tkr in UNIVERSE30:
            px = prices30[tkr].iloc[:sel_pos + 1]
            valid = px.dropna()
            if len(valid) < 280:   # need at least ~12m + 1m history
                continue

            # F1: 12m-1m momentum
            c0   = valid.iloc[-1]
            c1m  = valid.iloc[-22]
            c12m = valid.iloc[-253]
            f1 = (c1m / c12m) - 1

            # F2: % of last 252 days above SMA50
            sma_seg = sma50_30[tkr].iloc[:sel_pos + 1].dropna()
            px_seg  = prices30[tkr].iloc[:sel_pos + 1].reindex(sma_seg.index)
            lookback2 = min(252, len(sma_seg))
            f2 = (px_seg.iloc[-lookback2:] > sma_seg.iloc[-lookback2:]).mean()

            # F3: 3yr (or available) CAGR / vol
            lb3 = min(756, len(valid) - 1)
            c3 = valid.iloc[-(lb3 + 1)]
            cagr3 = (c0 / c3) ** (252 / lb3) - 1
            lr3 = logret30[tkr].iloc[sel_pos - lb3 + 1:sel_pos + 1].dropna()
            vol3 = lr3.std() * np.sqrt(252)
            f3 = cagr3 / vol3 if vol3 > 0 else 0.0

            # F4: drawdown resilience over prior 5yr (or available)
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
        top8 = sc_df.head(8)

        print(f"\n{name}  (selected {sel_date_actual.date()}, hold {hold_start.date()}->{hold_end.date()})")
        for tkr, row in top8.iterrows():
            print(f"    {tkr:6s}  composite={row['composite']:.3f}  "
                  f"(mom={row['f1']*100:+.1f}%, trend={row['f2']*100:.0f}%, "
                  f"vol-adj={row['f3']:.2f}, dd-resil={row['f4']:.2f})")

        selected = list(top8.index)

        # ── Holding period slice ────────────────────────────────────────────
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

        r = ot2_engine(hp_market, hp_blended, hp_cash, f"{name} OT2.0+selected8",
                        rfr_for_sharpe=float(hp_tbill.mean()))
        spx_seg = buy_and_hold(hp_market["log_ret"], hp_index, f"{name} SPX B&H")

        mod3_rows.append([
            name, f"{r['sharpe']:.3f}", f"{r['cagr_pct']:.2f}%", f"{r['max_dd_pct']:.1f}%",
            f"{r['worst_year_pct']:.1f}%", f"{spx_seg['sharpe']:.3f}", f"{spx_seg['cagr_pct']:.2f}%",
        ])
        r["cohort"] = name
        all_results.append(r)

        # store portfolio segment for chained backtest
        seg_port, seg_inv = _run_full(hp_market, hp_blended, hp_cash)
        chained_segments_port.append(seg_port)
        chained_segments_inv.append(seg_inv)
        chained_segments_idx.append(hp_index)

    print("\nPer-cohort results (5-year holding period each):")
    headers5 = ["Cohort", "Strat Sharpe", "Strat CAGR", "Strat MaxDD", "Strat WorstYr",
                 "SPX Sharpe", "SPX CAGR"]
    _print_table(headers5, mod3_rows)

    # ── Chained backtest ──────────────────────────────────────────────────
    chained_port = []
    chained_inv  = []
    chained_idx  = []
    level = 100.0
    for seg_port, seg_inv, seg_idx in zip(chained_segments_port, chained_segments_inv, chained_segments_idx):
        scaled = seg_port / seg_port[0] * level
        if chained_idx and seg_idx[0] == chained_idx[-1][-1]:
            # avoid duplicate boundary date
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

    chained_result = _compute_metrics(full_port, full_inv, full_idx,
                                       "Chained hindsight-free cohorts", rfr_mean)
    all_results.append(chained_result)

    print("\nChained hindsight-free backtest (1993 -> present, reconstituted every 5yrs):")
    headers6 = ["Variant", "Sharpe", "Sortino", "CAGR", "MaxDD", "WorstYr", "AvgInv"]
    rows6 = [
        ["Chained cohorts (hindsight-free)", f"{chained_result['sharpe']:.3f}",
         f"{chained_result['sortino']:.3f}", f"{chained_result['cagr_pct']:.2f}%",
         f"{chained_result['max_dd_pct']:.1f}%", f"{chained_result['worst_year_pct']:.1f}%",
         f"{chained_result['avg_inv_pct']:.1f}%"],
        ["Hindsight portfolio (7 known winners)", f"{hindsight_baseline['sharpe']:.3f}",
         f"{hindsight_baseline['sortino']:.3f}", f"{hindsight_baseline['cagr_pct']:.2f}%",
         f"{hindsight_baseline['max_dd_pct']:.1f}%", f"{hindsight_baseline['worst_year_pct']:.1f}%",
         f"{hindsight_baseline['avg_inv_pct']:.1f}%"],
        ["SPX B&H", f"{spx_bh_full['sharpe']:.3f}", f"{spx_bh_full['sortino']:.3f}",
         f"{spx_bh_full['cagr_pct']:.2f}%", f"{spx_bh_full['max_dd_pct']:.1f}%",
         f"{spx_bh_full['worst_year_pct']:.1f}%", "100.0%"],
        ["7-stock B&H (hindsight)", f"{seven_bh_full['sharpe']:.3f}", f"{seven_bh_full['sortino']:.3f}",
         f"{seven_bh_full['cagr_pct']:.2f}%", f"{seven_bh_full['max_dd_pct']:.1f}%",
         f"{seven_bh_full['worst_year_pct']:.1f}%", "100.0%"],
    ]
    _print_table(headers6, rows6)

    # ── Save + summary ───────────────────────────────────────────────────
    pd.DataFrame(all_results).to_csv("strategy_deep_test_results.csv", index=False)

    elapsed = time.time() - t0

    sharpe_gap_vs_hindsight = chained_result["sharpe"] - hindsight_baseline["sharpe"]
    sharpe_vs_spx = chained_result["sharpe"] - spx_bh_full["sharpe"]

    print("\n" + "=" * 54)
    print(" STRATEGY SUMMARY — HINDSIGHT-FREE, T-BILL CASH")
    print("=" * 54)
    print(f" Chained cohort Sharpe:      {chained_result['sharpe']:.3f}")
    print(f" Chained cohort CAGR:        {chained_result['cagr_pct']:.2f}%")
    print(f" Chained cohort MaxDD:       {chained_result['max_dd_pct']:.1f}%")
    print(f" vs SPX B&H Sharpe:          {sharpe_vs_spx:+.3f}")
    print(f" vs Hindsight portfolio:     {sharpe_gap_vs_hindsight:+.3f}")
    print(f" Cash drag reduction (T-bill vs flat 3%): {cash_drag_reduction:+.2f}pp CAGR")
    print("=" * 54)

    print(f"\nResults saved -> strategy_deep_test_results.csv")
    print(f"Runtime: {elapsed:.1f} seconds")


def _run_full(market_df, log_ret, cash_daily):
    """Same loop as ot2_engine but returns raw portfolio/invested arrays."""
    c = OT2_CONFIG
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


def _subset_metrics(portfolio, invested, mask, rfr):
    """Approximate metrics on a (possibly non-contiguous) boolean subset of days."""
    sub = portfolio[mask]
    if len(sub) < 10:
        return dict(sharpe=np.nan, cagr_pct=np.nan, max_dd_pct=np.nan, avg_inv_pct=np.nan)

    lr = np.diff(np.log(sub))
    rfr_d = np.log(1 + rfr) / 252
    sharpe = (lr.mean() - rfr_d) / lr.std() * np.sqrt(252) if lr.std() > 0 else 0.0
    cagr = np.exp(lr.mean() * 252) - 1

    roll_max = np.maximum.accumulate(sub)
    max_dd = ((sub - roll_max) / roll_max).min()

    avg_inv = np.mean(invested[mask]) * 100 if invested is not None else 100.0

    return dict(sharpe=sharpe, cagr_pct=cagr * 100, max_dd_pct=max_dd * 100, avg_inv_pct=avg_inv)


def _print_table(headers, rows):
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) + 2
                  for i, h in enumerate(headers)]
        print("  ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
        print("-" * (sum(widths) + 2 * len(widths)))
        for row in rows:
            print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))


if __name__ == "__main__":
    main()
