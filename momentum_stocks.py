"""
Single-Stock Cross-Sectional Momentum — Backtest (Strategy #1, rigorous test)
=============================================================================
The ETF rotation (momentum_rotation.py) showed simple ETF momentum is a
crash-protection tool, not a return engine. The documented momentum *alpha*
lives in the cross-section of individual stocks — so this tests that directly:
rank the S&P 500 by trailing 12-1 momentum each month, hold the top-N
equal-weight, rebalance monthly, benchmark against SPY.

  * Universe  : current S&P 500 constituents (Wikipedia), monthly total-return
                closes (auto_adjust=True), batch-downloaded.
  * Signal    : 12-1 momentum (past `lookback` months, skipping the most recent
                `skip` month). Rank -> top-N equal weight.
  * Rebalance : monthly at month-end; weights from month t held over month t+1
                (no look-ahead).
  * Costs     : turnover-based bps per rebalance.
  * Overlay   : optional SPY trend filter (hold only while SPY > its 10-month
                SMA, else cash) — the standard momentum + absolute-trend combo.
  * Benchmark : SPY buy & hold, same window.

*** SURVIVORSHIP BIAS — READ THIS ***
The universe is TODAY's S&P 500. Every name in it survived and was successful
enough to still be in the index; stocks that blew up and were delisted are
absent. That flatters ANY long-equity backtest, and momentum somewhat more
(it chases winners). Treat the absolute numbers here as an UPPER BOUND. A truly
clean test needs point-in-time constituents (CRSP / Norgate / paid PIT data) —
flagged as the upgrade path. The relative comparison (does momentum beat an
equal-weight hold of the SAME survivor universe?) is the more trustworthy read,
so that baseline is included.

Usage:
  py momentum_stocks.py
"""

import io
import time
import urllib.request
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


START = "2004-01-01"
RFR = 0.03
COST_BPS = 10.0
BENCHMARK = "SPY"
BATCH = 100


# ─────────────────────────────────────────────────────────────────────────────
# 1. UNIVERSE + DATA
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    df = pd.read_html(io.StringIO(html), header=0)[0]
    df.columns = [c.strip() for c in df.columns]
    tc = [c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()][0]
    tickers = df[tc].str.replace(".", "-", regex=False).str.strip().tolist()
    print(f"S&P 500 constituents fetched: {len(tickers)} tickers")
    return sorted(set(tickers))


PRICE_CACHE = "momentum_stocks_prices.csv"


def load_prices_cached(max_age_hours=18):
    """Monthly closes for the S&P 500 + SPY, cached to CSV so hardening reruns are cheap."""
    import os
    if os.path.exists(PRICE_CACHE):
        age_h = (time.time() - os.path.getmtime(PRICE_CACHE)) / 3600
        if age_h < max_age_hours:
            px = pd.read_csv(PRICE_CACHE, index_col=0, parse_dates=True)
            print(f"Loaded cached prices ({px.shape[1]} cols, {len(px)} months, {age_h:.1f}h old)")
            return px
    tickers = fetch_sp500()
    print(f"Downloading monthly closes for {len(tickers)} names + {BENCHMARK}...")
    px = batch_download_monthly(tickers + [BENCHMARK])
    px.to_csv(PRICE_CACHE)
    print(f"Cached -> {PRICE_CACHE}")
    return px


def batch_download_monthly(tickers):
    """Monthly total-return closes for a ticker list, as one aligned frame."""
    frames = []
    n_batches = (len(tickers) + BATCH - 1) // BATCH
    for b in range(n_batches):
        batch = tickers[b * BATCH:(b + 1) * BATCH]
        print(f"  batch {b+1}/{n_batches} ({len(batch)} tickers)...", flush=True)
        for attempt in range(3):
            try:
                kw = dict(start=START, interval="1mo", auto_adjust=True,
                          progress=False, threads=True)
                if SESSION is not None:
                    kw["session"] = SESSION
                raw = yf.download(batch, **kw)
                break
            except Exception as e:
                print(f"    retry ({e})", flush=True)
                time.sleep(10)
        else:
            continue
        if raw is None or raw.empty:
            continue
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if not isinstance(raw.columns, pd.MultiIndex):
            close.columns = batch[:1]
        frames.append(close)
    prices = pd.concat(frames, axis=1)
    prices = prices.loc[:, ~prices.columns.duplicated()]
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    # Drop the partial current month so momentum uses completed months only.
    prices = prices[prices.index <= pd.Timestamp.today().replace(day=1) - pd.Timedelta(days=1)]
    return prices.sort_index()


# ─────────────────────────────────────────────────────────────────────────────
# 2. BACKTEST (monthly frequency)
# ─────────────────────────────────────────────────────────────────────────────

def momentum_score(prices_m, lookback, skip):
    return prices_m.shift(skip) / prices_m.shift(lookback + skip) - 1.0


def backtest(prices_m, spy_m, top_n=30, lookback=12, skip=1,
             trend_filter=False, cost_bps=COST_BPS, rfr=RFR):
    """
    Returns (equity_series base 100, rebalance log). Weights chosen at month t
    are held through month t+1. `trend_filter` gates the whole book to cash when
    SPY is below its 10-month SMA at the signal date.
    """
    scores = momentum_score(prices_m, lookback, skip)
    ret_m = prices_m.pct_change()
    months = prices_m.index
    cash_m = (1.0 + rfr) ** (1.0 / 12) - 1.0

    spy_sma10 = spy_m.rolling(10).mean()

    equity = 100.0
    curve = pd.Series(index=months, dtype=float)
    prev_w = pd.Series(0.0, index=prices_m.columns)
    log = []

    first_i = lookback + skip
    for i in range(first_i, len(months) - 1):
        t, t1 = months[i], months[i + 1]
        s = scores.loc[t].dropna()
        s = s[s > -0.99]                         # guard against broken/delisted rows
        risk_on = (not trend_filter) or (spy_m.loc[t] > spy_sma10.loc[t])

        w = pd.Series(0.0, index=prices_m.columns)
        if risk_on and len(s) >= top_n:
            picks = s.sort_values(ascending=False).head(top_n)
            w[picks.index] = 1.0 / top_n

        turnover = (w - prev_w).abs().sum()
        equity *= (1.0 - turnover * cost_bps / 1e4)
        prev_w = w

        held = ret_m.loc[t1, w[w > 0].index].fillna(0.0)
        port_r = float((held * (1.0 / len(held) if len(held) else 0)).sum()) if len(held) else 0.0
        equity *= (1.0 + (port_r if w.sum() > 0 else cash_m))
        curve.loc[t1] = equity

        log.append({"date": t1.date(), "n": int((w > 0).sum()),
                    "turnover": round(turnover, 2),
                    "top5": ", ".join(s.sort_values(ascending=False).head(5).index)})

    return curve.dropna(), pd.DataFrame(log)


def equal_weight_hold(prices_m, index):
    """Equal-weight buy & hold of the SAME survivor universe — the fair momentum baseline."""
    ret = prices_m.pct_change()
    ew = ret.mean(axis=1)                        # each month, mean of available names
    curve = 100.0 * (1.0 + ew.reindex(index).fillna(0.0)).cumprod()
    return curve


def bh(prices_m, ticker, index):
    s = prices_m[ticker].reindex(index).dropna()
    return 100.0 * s / s.iloc[0]


# ─────────────────────────────────────────────────────────────────────────────
# 3. METRICS (monthly)
# ─────────────────────────────────────────────────────────────────────────────

def metrics(curve, label, rfr=RFR):
    curve = curve.dropna()
    port = curve.values
    n = len(port)
    cagr = (port[-1] / port[0]) ** (12 / n) - 1
    r = curve.pct_change().dropna()
    vol = r.std() * np.sqrt(12)
    sharpe = (r.mean() - rfr / 12) / r.std() * np.sqrt(12) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(12) if len(neg) else 0.0
    sortino = (cagr - rfr) / dd_std if dd_std > 0 else 0.0
    roll = curve.cummax()
    max_dd = ((curve - roll) / roll).min()
    annual = curve.resample("YE").last().pct_change().dropna()
    return {"label": label, "cagr_pct": cagr * 100, "vol_pct": vol * 100,
            "sharpe": sharpe, "sortino": sortino, "max_dd_pct": max_dd * 100,
            "worst_year_pct": annual.min() * 100 if len(annual) else np.nan,
            "final": port[-1]}


def print_metrics(rows):
    headers = ["Strategy", "CAGR", "Vol", "Sharpe", "Sortino", "MaxDD", "Worst Yr", "Final $100"]
    table = [[r["label"], f"{r['cagr_pct']:.2f}%", f"{r['vol_pct']:.2f}%", f"{r['sharpe']:.3f}",
              f"{r['sortino']:.3f}", f"{r['max_dd_pct']:.1f}%", f"{r['worst_year_pct']:.1f}%",
              f"${r['final']:.0f}"] for r in rows]
    print()
    if HAS_TABULATE:
        print(tabulate(table, headers=headers, tablefmt="simple"))
    else:
        w = [30, 8, 8, 8, 8, 8, 9, 10]
        line = "  ".join(h.ljust(w[i]) for i, h in enumerate(headers))
        print(line); print("-" * len(line))
        for row in table:
            print("  ".join(str(v).ljust(w[i]) for i, v in enumerate(row)))


# ─────────────────────────────────────────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    prices = load_prices_cached()
    spy_m = prices[BENCHMARK]
    stock_px = prices.drop(columns=[BENCHMARK])
    # Keep names with a reasonable history; require >= lookback+skip+12 months.
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= 26]
    print(f"  usable stock series: {stock_px.shape[1]}   months: {len(prices)} "
          f"({prices.index[0].date()} -> {prices.index[-1].date()})")

    print("\n" + "!" * 78)
    print("SURVIVORSHIP BIAS: universe is TODAY's S&P 500 — delisted losers are absent.")
    print("Absolute returns are an UPPER BOUND. The trustworthy read is momentum vs the")
    print("equal-weight hold of the SAME survivor universe (both share the bias).")
    print("!" * 78)

    # ── Base: 12-1 momentum, top 30, monthly ────────────────────────────────
    print("\n" + "=" * 78)
    print("BASE — 12-1 momentum, top 30, monthly, no trend filter")
    print("=" * 78)
    curve, log = backtest(stock_px, spy_m, top_n=30, lookback=12, skip=1, trend_filter=False)
    curve_tf, _ = backtest(stock_px, spy_m, top_n=30, lookback=12, skip=1, trend_filter=True)
    ew = equal_weight_hold(stock_px, curve.index)
    spy = bh(prices, BENCHMARK, curve.index)

    rows = [
        metrics(curve, "Momentum top30 (12-1)"),
        metrics(curve_tf, "Momentum top30 + SPY trend"),
        metrics(ew, "Equal-wt hold (survivors)"),
        metrics(spy, "SPY buy & hold"),
    ]
    print_metrics(rows)
    m, e, s = rows[0], rows[2], rows[3]
    print(f"\n  Momentum vs EW-survivors:  CAGR {m['cagr_pct']-e['cagr_pct']:+.2f}pp   "
          f"Sharpe {m['sharpe']-e['sharpe']:+.3f}   (this is the bias-controlled read)")
    print(f"  Momentum vs SPY:           CAGR {m['cagr_pct']-s['cagr_pct']:+.2f}pp   "
          f"Sharpe {m['sharpe']-s['sharpe']:+.3f}")

    print("\nLast 5 rebalances (top 5 momentum names):")
    print(log.tail(5).to_string(index=False))

    # ── Sweep: lookback x top_n ──────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("ROBUSTNESS SWEEP — no trend filter; each cell = Sharpe (CAGR%)")
    print("=" * 78)
    lookbacks, tns = [3, 6, 9, 12], [10, 20, 30, 50]
    grid = []
    for lb in lookbacks:
        row = [f"{lb}m"]
        for n in tns:
            c, _ = backtest(stock_px, spy_m, top_n=n, lookback=lb, skip=1, trend_filter=False)
            mm = metrics(c, "")
            row.append(f"{mm['sharpe']:.2f} ({mm['cagr_pct']:.1f})")
        grid.append(row)
    hdr = ["lookback \\ topN"] + [f"top{n}" for n in tns]
    print(tabulate(grid, headers=hdr, tablefmt="simple") if HAS_TABULATE
          else "\n".join("  ".join(map(str, r)) for r in [hdr] + grid))

    # ── Walk-forward IS/OOS ──────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("WALK-FORWARD — base config, first half (IS) vs second half (OOS)")
    print("=" * 78)
    mid = prices.index[len(prices) // 2]
    is_c, _ = backtest(stock_px.loc[:mid], spy_m.loc[:mid], top_n=30, lookback=12, skip=1)
    oos_c, _ = backtest(stock_px.loc[mid:], spy_m.loc[mid:], top_n=30, lookback=12, skip=1)
    print_metrics([
        metrics(is_c, f"IS  Momentum ({is_c.index[0].date()}+)"),
        metrics(bh(prices, BENCHMARK, is_c.index), "IS  SPY"),
        metrics(oos_c, f"OOS Momentum ({oos_c.index[0].date()}+)"),
        metrics(bh(prices, BENCHMARK, oos_c.index), "OOS SPY"),
    ])

    curve.to_csv("momentum_stocks_curve.csv", header=["equity"])
    pd.DataFrame(rows).to_csv("momentum_stocks_results.csv", index=False)
    print(f"\nSaved -> momentum_stocks_curve.csv, momentum_stocks_results.csv")
    print(f"Runtime: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
