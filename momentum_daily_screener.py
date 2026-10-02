"""
Momentum Daily Screener — stock selection only, decoupled from timing
========================================================================
Identical stock-picking to momentum_screener.py — same universe, same
blended 6&12-month momentum signal, same top-20/equal-weight/40%-sector-cap
rules — with ONE deliberate difference: this screener does NOT bake a trend
gate into the selection. It always outputs the top 20 names, every month,
regardless of market regime.

Why: momentum_daily_strategy_engine.py (the "out-time" half of this pair)
applies its own DAILY SPY-vs-10-month-SMA exposure check, decoupled from the
monthly stock rotation — this is what momentum_trend_gate_control.py found
beats the existing (monthly-only) gate. If this screener also emptied its
holdings on a risk-off month, the two gates would double up and the engine
would have nothing to hold the moment the daily signal flips back risk-on
mid-month. Out-pace (which stocks) and out-time (are we in or out) are kept
fully separate here, matching exactly what was backtested.

Writes momentum_daily_selection.json — same schema as momentum_selection.json
minus the risk_on/trend_note fields (meaningless here — this file is never
"empty").

Usage:
  py momentum_daily_screener.py
"""

import io
import json
import time
import urllib.request
import warnings

import pandas as pd

warnings.filterwarnings("ignore")

import momentum_stocks as ms

N_HOLDINGS = 20
LOOKBACKS = (6, 12)          # blended momentum horizons (months)
SKIP = 1                     # skip most recent month (short-term reversal)
MAX_PER_SECTOR = 8           # cap any one GICS sector at 8/20 = 40% of the book
OUTPUT_PATH = "momentum_daily_selection.json"


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
    stock_px = prices.drop(columns=[ms.BENCHMARK])
    stock_px = stock_px.loc[:, stock_px.notna().sum() >= max(LOOKBACKS) + SKIP + 1]

    latest = stock_px.index[-1]
    print(f"Screening as of completed month: {latest.date()} "
          f"({stock_px.shape[1]} names) — UNCONDITIONAL (no trend gate on selection)")

    # ── Blended momentum score (percentile-averaged across horizons) ─────────
    mom = {}
    for lb in LOOKBACKS:
        mom[lb] = stock_px.shift(SKIP) / stock_px.shift(lb + SKIP) - 1.0
    raw6 = mom[6].loc[latest]
    raw12 = mom[12].loc[latest]
    blended_rank = (pct_rank(raw6) + pct_rank(raw12)) / 2
    blended_rank = blended_rank[raw6.notna() & raw12.notna()]

    sector_map = fetch_sector_map()

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

    holdings = {}
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
        "strategy": "single-stock momentum (blended 6&12m, top20), unconditional — "
                    "exposure timing handled daily by momentum_daily_strategy_engine.py",
        "n_holdings": len(holdings),
        "holdings": holdings,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(selection, f, indent=2)

    print(f"\n{'='*70}")
    print(f"TOP {N_HOLDINGS} MOMENTUM HOLDINGS  (as of {latest.date()})")
    print(f"{'='*70}")
    disp = pd.DataFrame([
        {"ticker": t, "score": h["score_composite"], "ret_6m%": h["ret_6m"],
         "ret_12m%": h["ret_12m"], "sector": h["sector"]}
        for t, h in holdings.items()
    ])
    print(disp.to_string(index=False))
    print(f"\nWritten: {OUTPUT_PATH}   ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
