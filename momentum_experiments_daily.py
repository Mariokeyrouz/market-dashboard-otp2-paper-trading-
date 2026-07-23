"""
Momentum Experiments (daily) — portfolio stop + trim/reload overlays
====================================================================
Tests the risk overlays that need intra-month (daily) granularity, which the
monthly experiment cannot: a PORTFOLIO-LEVEL non-retreating trailing stop
(breach the drawdown line -> flat to cash until the next monthly rebalance), and
a graduated TRIM/RELOAD exposure manager (scale exposure down as drawdown from
the high-water mark deepens, back up as it recovers). Compared against the base
(binary monthly SPX-10mo trend gate, top-20 equal weight).

Same caveats: survivorship-inflated levels; read the RELATIVE differences.

Usage:  py momentum_experiments_daily.py
"""

import os
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import yfinance as yf

import momentum_stocks as ms

RFR = 0.03
TOPN = 20
TREND_SMA = 10
COST_BPS = 20
TRADING = 252
CACHE = "momentum_daily_prices.csv"
CASH_D = (1 + RFR) ** (1 / TRADING) - 1


def load_daily():
    if os.path.exists(CACHE) and (time.time() - os.path.getmtime(CACHE)) / 3600 < 24:
        px = pd.read_csv(CACHE, index_col=0, parse_dates=True)
        print(f"Loaded cached daily prices {px.shape}")
        return px
    tickers = ms.fetch_sp500() + [ms.BENCHMARK]
    print(f"Downloading DAILY closes for {len(tickers)} names (one-time)...")
    frames, B = [], 100
    for b in range((len(tickers) + B - 1) // B):
        batch = tickers[b * B:(b + 1) * B]
        print(f"  daily batch {b+1}/{(len(tickers)+B-1)//B}...", flush=True)
        raw = None
        for _ in range(3):
            try:
                kw = dict(start="2004-01-01", interval="1d", auto_adjust=True,
                          progress=False, threads=True)
                if ms.SESSION is not None:
                    kw["session"] = ms.SESSION
                raw = yf.download(batch, **kw)
                break
            except Exception as e:
                print(f"    retry ({e})"); time.sleep(10)
        if raw is None or raw.empty:
            continue
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if not isinstance(raw.columns, pd.MultiIndex):
            close.columns = batch[:1]
        frames.append(close)
    px = pd.concat(frames, axis=1)
    px = px.loc[:, ~px.columns.duplicated()]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px.sort_index()
    px.to_csv(CACHE)
    print(f"Cached -> {CACHE} {px.shape}")
    return px


def metrics(curve, label):
    c = curve.dropna(); p = c.values; yrs = len(p) / TRADING
    cagr = (p[-1] / p[0]) ** (1 / yrs) - 1
    r = c.pct_change().dropna()
    vol = r.std() * np.sqrt(TRADING)
    sharpe = (r.mean() - RFR / TRADING) / r.std() * np.sqrt(TRADING) if r.std() > 0 else 0.0
    neg = r[r < 0]
    dd_std = neg.std() * np.sqrt(TRADING) if len(neg) else 0.0
    sortino = (cagr - RFR) / dd_std if dd_std > 0 else 0.0
    mdd = ((c - c.cummax()) / c.cummax()).min()
    return dict(label=label, cagr=cagr * 100, vol=vol * 100, sharpe=sharpe,
                sortino=sortino, mdd=mdd * 100, final=p[-1])


def main():
    px = load_daily()
    spy_d = px[ms.BENCHMARK].dropna()
    stock_d = px.drop(columns=[ms.BENCHMARK])
    stock_d = stock_d.loc[:, stock_d.notna().sum() >= 500]
    daily_ret = stock_d.pct_change()

    px_m = stock_d.resample("ME").last()
    spy_m = spy_d.resample("ME").last()
    spy_sma = spy_m.rolling(TREND_SMA).mean()
    r6 = px_m.shift(1) / px_m.shift(7) - 1
    r12 = px_m.shift(1) / px_m.shift(13) - 1
    rank_blend = ((r6.rank(axis=1, pct=True) + r12.rank(axis=1, pct=True)) / 2).where(
        r6.notna() & r12.notna())
    months = px_m.index

    weights = {}
    for i in range(13, len(months) - 1):
        t = months[i]
        w = pd.Series(0.0, index=stock_d.columns)
        if spy_m.loc[t] > spy_sma.loc[t]:
            s = rank_blend.loc[t].dropna().sort_values(ascending=False).head(TOPN)
            w[s.index] = 1.0 / len(s)
        weights[t] = w

    idx = stock_d.index

    # Precompute each holding month's block once: its trading days, the daily
    # return of that month's (normalized) basket, its risk-on fraction, and the
    # rebalance cost. Overlays then just scale a precomputed daily return — no
    # repeated 500-column dot products.
    blocks = []
    prev_w = pd.Series(0.0, index=stock_d.columns)
    for i in range(13, len(months) - 1):
        t, t1 = months[i], months[i + 1]
        w = weights[t]
        cost = float((w - prev_w).abs().sum() * COST_BPS / 1e4)
        prev_w = w
        base_frac = float(w.sum())
        days = idx[(idx > t) & (idx <= t1)]
        if len(days) == 0:
            continue
        if base_frac > 0:
            hr = (daily_ret.loc[days] * (w / base_frac)).sum(axis=1).values
        else:
            hr = np.zeros(len(days))
        blocks.append((days, hr, base_frac, cost))

    def simulate(mode="base", stop=0.15, floor=0.25, k=2.5, reset_hwm=False):
        equity = 100.0; hwm = 100.0
        dates, vals = [], []
        for days, hr, base_frac, cost in blocks:
            equity *= (1.0 - cost)
            if reset_hwm:                                     # peak resets each rebalance
                hwm = equity
            stopped = False                                   # non-retreating within month
            for j in range(len(days)):
                hwm = max(hwm, equity)
                dd = equity / hwm - 1.0                        # <= 0
                if base_frac == 0.0:
                    frac = 0.0
                elif mode == "base":
                    frac = 1.0
                elif mode == "stop":
                    if dd <= -stop:
                        stopped = True
                    frac = 0.0 if stopped else 1.0
                else:                                          # trim/reload (graduated)
                    frac = min(1.0, max(floor, 1.0 + k * dd))
                equity *= (1.0 + frac * hr[j] + (1.0 - frac) * CASH_D)
                dates.append(days[j]); vals.append(equity)
        return pd.Series(vals, index=pd.DatetimeIndex(dates))

    base = simulate("base")
    spy = 100.0 * spy_d.reindex(base.index).dropna() / spy_d.reindex(base.index).dropna().iloc[0]

    print("\n" + "!" * 74)
    print("Daily S&P 500 data. Levels are survivorship-inflated UPPER BOUNDS —")
    print("read the RELATIVE differences between overlays.")
    print("!" * 74)
    print(f"\nWindow: {base.index[0].date()} -> {base.index[-1].date()}  "
          f"({len(base)} days)\n")

    rows = [metrics(base, "BASE (monthly trend gate)")]
    for s in (0.10, 0.15, 0.20):
        rows.append(metrics(simulate("stop", stop=s), f"+ stop {int(s*100)}% (all-time peak)"))
    rows.append(metrics(simulate("stop", stop=0.15, reset_hwm=True), "+ stop 15% (reset monthly)"))
    rows.append(metrics(simulate("trim"), "+ trim/reload (all-time peak)"))
    rows.append(metrics(simulate("trim", reset_hwm=True), "+ trim/reload (reset monthly)"))
    rows.append(metrics(spy, "SPY buy & hold"))

    hdr = f"{'Overlay':32s} {'CAGR':>7} {'Vol':>7} {'Sharpe':>7} {'Sortino':>8} {'MaxDD':>7}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['label']:32s} {r['cagr']:6.1f}% {r['vol']:6.1f}% {r['sharpe']:7.2f} "
              f"{r['sortino']:8.2f} {r['mdd']:6.1f}%")

    b = rows[0]
    print("\nvs BASE:")
    for r in rows[1:-1]:
        print(f"  {r['label']:32s} CAGR {r['cagr']-b['cagr']:+5.1f}pp  "
              f"Sharpe {r['sharpe']-b['sharpe']:+.2f}  MaxDD {r['mdd']-b['mdd']:+5.1f}pp")


if __name__ == "__main__":
    main()
