"""
Momentum Screener — Single-Stock Cross-Sectional Momentum (paper-trade)
=======================================================================
Monthly stock selection for the momentum strategy validated in
momentum_stocks.py / momentum_harden.py. Locked config:

  * Universe   : current S&P 500 constituents.
  * Signal     : blended 6-month + 12-month momentum, each skipping the most
                 recent month (12-1 style), combined by percentile rank so we
                 aren't overfit to a single lookback.
  * Selection  : top 20 by blended momentum, equal weight (5% each).
  * Trend gate : SPY vs its 10-month SMA. If SPY is below (risk-off), the
                 selection is EMPTY — the engine sits in cash. This overlay is
                 what cut the backtest max drawdown from ~-56% to ~-24%.

Writes momentum_selection.json in the same schema factor_screener.py uses
(so pages/7_Portfolio_Analytics.py reads it unchanged), plus a `risk_on` flag
and the blended-momentum context for attribution.

Usage:
  py momentum_screener.py
"""

import io
import json
import time
import urllib.request
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import momentum_stocks as ms

N_HOLDINGS = 20
LOOKBACKS = (6, 12)          # blended momentum horizons (months)
SKIP = 1                     # skip most recent month (short-term reversal)
TREND_SMA_MONTHS = 10        # SPY 10-month SMA trend gate (~200 trading days)
MAX_PER_SECTOR = 8           # cap any one GICS sector at 8/20 = 40% of the book
OUTPUT_PATH = "momentum_selection.json"


def fetch_sector_map():
    """GICS sector per ticker from the S&P 500 Wikipedia table (for attribution)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8")
        df = pd.read_html(io.StringIO(html), header=0)[0]
        df.columns = [c.strip() for c in df.columns]
        tc = [c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()][0]
        sc = [c for c in df.columns if "sector" in c.lower() or "gics" in c.lower()][0]
        df[tc] = df[tc].str.replace(".", "-", regex=False).str.strip()
        return dict(zip(df[tc], df[sc]))
    except Exception as e:
        print(f"  [sector map failed: {e}]")
        return {}


def pct_rank(s):
    """Percentile rank 0-100; NaNs neutral at 50."""
    return (s.rank(pct=True) * 100).fillna(50.0)


def main():
    t0 = time.time()
    prices = ms.load_prices_cached()
    spy_m = prices[ms.BENCHMARK]
    stock_px = prices.drop(columns=[ms.BENCHMARK])
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= max(LOOKBACKS) + SKIP + 1]

    latest = stock_px.index[-1]
    print(f"Screening as of completed month: {latest.date()} "
          f"({stock_px.shape[1]} names)")

    # ── Blended momentum score (percentile-averaged across horizons) ─────────
    mom = {}
    for lb in LOOKBACKS:
        mom[lb] = stock_px.shift(SKIP) / stock_px.shift(lb + SKIP) - 1.0
    raw6 = mom[6].loc[latest]
    raw12 = mom[12].loc[latest]
    blended_rank = (pct_rank(raw6) + pct_rank(raw12)) / 2
    blended_rank = blended_rank[raw6.notna() & raw12.notna()]

    # ── Trend gate: SPY vs 10-month SMA ──────────────────────────────────────
    spy_sma = spy_m.rolling(TREND_SMA_MONTHS).mean()
    risk_on = bool(spy_m.loc[latest] > spy_sma.loc[latest])
    print(f"Trend gate: SPY {spy_m.loc[latest]:.2f} vs {TREND_SMA_MONTHS}mo SMA "
          f"{spy_sma.loc[latest]:.2f}  ->  {'RISK-ON' if risk_on else 'RISK-OFF (cash)'}")

    sector_map = fetch_sector_map()

    holdings = {}
    if risk_on:
        # Greedy fill: descend the momentum ranking, adding a name only while its
        # sector is under the cap — so a single hot theme can't take the whole book.
        ranked = blended_rank.sort_values(ascending=False)
        sector_count, picks = {}, []
        for tkr in ranked.index:
            sec = str(sector_map.get(tkr, "Unknown"))
            if sector_count.get(sec, 0) >= MAX_PER_SECTOR:
                continue
            picks.append(tkr)
            sector_count[sec] = sector_count.get(sec, 0) + 1
            if len(picks) >= N_HOLDINGS:
                break
        top = ranked.loc[picks]
        print(f"Sector cap {MAX_PER_SECTOR}/{N_HOLDINGS}: {sector_count}")
        w = round(1.0 / len(top), 6)
        for tkr in top.index:
            holdings[tkr] = {
                "target_weight":   w,
                "score_composite": round(float(top[tkr]), 1),
                "score_momentum":  round(float(top[tkr]), 1),
                "ret_6m":          round(float(raw6[tkr]) * 100, 2),
                "ret_12m":         round(float(raw12[tkr]) * 100, 2),
                "sector":          str(sector_map.get(tkr, "")),
            }

    selection = {
        "as_of": latest.strftime("%Y-%m-%d"),
        "strategy": "single-stock momentum (blended 6&12m, top20, SPY trend gate)",
        "risk_on": risk_on,
        "trend_note": f"SPY {'above' if risk_on else 'below'} {TREND_SMA_MONTHS}mo SMA",
        "n_holdings": len(holdings),
        "holdings": holdings,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(selection, f, indent=2)

    print(f"\n{'='*70}")
    if risk_on:
        print(f"TOP {N_HOLDINGS} MOMENTUM HOLDINGS  (as of {latest.date()})")
        print(f"{'='*70}")
        disp = pd.DataFrame([
            {"ticker": t, "score": h["score_composite"], "ret_6m%": h["ret_6m"],
             "ret_12m%": h["ret_12m"], "sector": h["sector"]}
            for t, h in holdings.items()
        ])
        print(disp.to_string(index=False))
    else:
        print("RISK-OFF — selection is empty (portfolio holds cash this month).")
    print(f"\nWritten: {OUTPUT_PATH}   ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
