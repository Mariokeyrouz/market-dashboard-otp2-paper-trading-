"""
RRG Data — sector ETF prices, stock panel, and the GICS -> SPDR map
===================================================================
One place for every data dependency of the RRG study, so the caveats travel
with the data rather than getting lost.

DATA CAVEATS THAT MUST REACH THE OUTPUT
---------------------------------------
1. **Sector ETFs are clean.** All 11 SPDRs still trade, so there is no
   survivorship bias. This is why the 9 long-history sectors are the PRIMARY
   sample for the validation.

2. **The stock panel is NOT clean.** `momentum_daily_prices.csv` is TODAY's
   S&P 500 membership projected back to 2004. Every name that was deep in the
   Lagging quadrant in 2008 and then went to zero — Lehman, WaMu, Bear,
   Countrywide — is simply absent. The bias is therefore *concentrated in the
   signal dimension we are studying*: the Lagging and Improving quadrants are a
   curated set of survivors. Its second-order effect is worse than the first:
   truncating the loss tail understates |mean loss|, which inflates
   R = mean(win)/|mean(loss)|, which inflates Kelly.

3. **The GICS map has look-ahead.** Sector labels are today's. The 2018-09-24
   Communication Services creation (GOOGL/META/NFLX/DIS moved out of Tech and
   Discretionary) and the 2023-03-17 reshuffle (V/MA/PYPL Tech -> Financials)
   mean historical observations get their end-state sector. Those same dates are
   structural breaks *inside* the ETFs being z-scored, so a rolling window
   spanning them manufactures a large fake rotation. Flagged in RECLASS_DATES.

4. **yfinance restates adjusted closes.** The file hash and mtime are recorded
   with every result set so a run can be reproduced.
"""

import hashlib
import os
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

PRICE_CACHE = "rrg_prices.csv"          # gitignored
STOCK_PANEL = "momentum_daily_prices.csv"
BENCHMARK = "SPY"
START = "1998-12-01"

# ── The 11 SPDR sector ETFs ──────────────────────────────────────────────────
# The 9 "core" ones start 1998-12-22. XLRE (2015-10-08) and XLC (2018-06-18)
# are late arrivals: with a 52-week normalization plus smoothing, XLC's first
# valid weekly RRG point is ~2020. They are therefore a separate robustness
# block, never mixed into the headline sample.
SECTOR_CORE = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB"]
SECTOR_LATE = ["XLRE", "XLC"]
SECTOR_ETFS = SECTOR_CORE + SECTOR_LATE

SECTOR_NAMES = {
    "XLK": "Information Technology", "XLF": "Financials", "XLE": "Energy",
    "XLV": "Health Care", "XLI": "Industrials", "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples", "XLU": "Utilities", "XLB": "Materials",
    "XLRE": "Real Estate", "XLC": "Communication Services",
}

# GICS label (Wikipedia) -> SPDR ETF
GICS_TO_ETF = {
    "Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE",
    "Health Care": "XLV", "Industrials": "XLI", "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP", "Utilities": "XLU", "Materials": "XLB",
    "Real Estate": "XLRE", "Communication Services": "XLC",
}

# GICS reclassifications = structural breaks inside the z-score windows
RECLASS_DATES = ["2016-09-16", "2018-09-24", "2023-03-17"]


def file_fingerprint(path):
    """(mtime, sha256[:16]) so a result set can be tied to its exact input."""
    if not os.path.exists(path):
        return ("missing", "missing")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    mt = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(path)))
    return (mt, h.hexdigest()[:16])


def _download(tickers, retries=5, wait=15):
    last = None
    for attempt in range(1, retries + 1):
        try:
            kw = dict(start=START, interval="1d", auto_adjust=True,
                      progress=False, threads=True)
            if SESSION is not None:
                kw["session"] = SESSION
            raw = yf.download(tickers, **kw)
            if raw is not None and len(raw) > 0:
                close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
                if not isinstance(raw.columns, pd.MultiIndex):
                    close.columns = tickers[:1]
                return close
            last = "empty result"
        except Exception as e:
            last = e
        if attempt < retries:
            print(f"    attempt {attempt} failed ({last}), retry in {wait}s ...", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Failed to download sector ETFs: {last}")


def load_sector_prices(max_age_hours=18, verbose=True):
    """Daily total-return closes for the 11 SPDRs + SPY, cached to rrg_prices.csv."""
    if os.path.exists(PRICE_CACHE):
        age = (time.time() - os.path.getmtime(PRICE_CACHE)) / 3600
        if age < max_age_hours:
            px = pd.read_csv(PRICE_CACHE, index_col=0, parse_dates=True)
            if verbose:
                print(f"Loaded cached sector prices {px.shape} ({age:.1f}h old)")
            return px
    if verbose:
        print(f"Downloading {len(SECTOR_ETFS)+1} sector ETFs + benchmark ...")
    px = _download(SECTOR_ETFS + [BENCHMARK])
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px.sort_index()
    px = px[[c for c in SECTOR_ETFS + [BENCHMARK] if c in px.columns]]
    px.to_csv(PRICE_CACHE)
    if verbose:
        print(f"Cached -> {PRICE_CACHE} {px.shape}")
        for c in px.columns:
            s = px[c].dropna()
            print(f"  {c:5s}: {s.index[0].date()} -> {s.index[-1].date()}  ({len(s):,} days)")
    return px


def load_stock_panel(verbose=True):
    """
    Daily adjusted closes for ~503 S&P 500 names + SPY (2004 -> today).
    See caveat 2 in the module docstring: this panel is survivorship-biased.
    """
    if not os.path.exists(STOCK_PANEL):
        raise FileNotFoundError(
            f"{STOCK_PANEL} not found. Regenerate with: "
            f"py -c \"import momentum_experiments_daily as m; m.load_daily()\"")
    px = pd.read_csv(STOCK_PANEL, index_col=0, parse_dates=True)
    if verbose:
        mt, sha = file_fingerprint(STOCK_PANEL)
        print(f"Loaded stock panel {px.shape}  (mtime {mt}, sha256 {sha})")
        print("  NOTE: current S&P 500 membership backfilled -> survivorship bias.")
    return px


def load_sector_map(verbose=True):
    """ticker -> GICS sector (today's labels; see caveat 3)."""
    try:
        from momentum_screener import fetch_sector_map
        m = fetch_sector_map()
        if m:
            if verbose:
                print(f"Sector map: {len(m)} tickers")
            return m
    except Exception as e:
        print(f"  [sector map failed: {e}]")
    return {}


def stocks_in_sector(sector_map, etf, available):
    """Tickers whose GICS sector maps to `etf` and that exist in the price panel."""
    want = {t for t, s in sector_map.items() if GICS_TO_ETF.get(str(s)) == etf}
    return sorted(want & set(available))


def spans_reclassification(dates, window):
    """
    Boolean mask: True where the trailing `window` observations span a GICS
    reclassification date, so the z-score is contaminated by a constituent
    change rather than a market move.
    """
    dates = pd.DatetimeIndex(dates)
    mask = np.zeros(len(dates), dtype=bool)
    for d in pd.to_datetime(RECLASS_DATES):
        pos = dates.searchsorted(d)
        lo, hi = pos, min(pos + window, len(dates))
        if lo < len(dates):
            mask[lo:hi] = True
    return mask


if __name__ == "__main__":
    print("=" * 78)
    print("RRG DATA — availability check")
    print("=" * 78)
    px = load_sector_prices()
    print("\nCommon start if ALL 11 sectors required:",
          px[SECTOR_ETFS].dropna().index[0].date())
    print("Common start for the 9 core sectors:    ",
          px[SECTOR_CORE + [BENCHMARK]].dropna().index[0].date())
