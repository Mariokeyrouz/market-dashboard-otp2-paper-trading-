"""
Factor Screener — Aggressive Factor Strategy
=============================================
Monthly stock selection for the factor portfolio. Scores S&P 500 + Russell 1000
on four factors: Relative Momentum (RRG-inspired vs SPX), Quality, Value,
and Low Volatility.

Outputs factor_selection.json with the top 15-20 holdings and target weights.

Usage:
  python factor_screener.py
"""

import io
import json
import sys
import time
import urllib.request
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

# ── Constants ─────────────────────────────────────────────────────────────────

N_HOLDINGS      = 18          # target portfolio size (15-20)
EXCLUDED_SECTORS = {"Financial Services", "Real Estate"}
MIN_PRICE       = 10.0
MIN_ADV_USD     = 25_000_000
MIN_MKTCAP      = 2_000_000_000   # $2B market cap
MIN_YEARS_DATA  = 2
MIN_PROFIT_YEARS = 2
MIN_FCF_YEARS   = 2
MIN_CURRENT_RATIO = 1.0
MIN_QUICK_RATIO = 0.7
MIN_INT_COVERAGE = 1.5
MAX_NET_DEBT_EBITDA = 5.0
VALID_EXCHANGES = {"NYQ", "NMS", "NGM", "NCM", "NYSE", "NASDAQ", "NYS", "NAS"}

OUTPUT_PATH = "factor_selection.json"

# ── Universe ──────────────────────────────────────────────────────────────────

def _read_html_wiki(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")
    return pd.read_html(io.StringIO(html), header=0)


def fetch_universe():
    print("Fetching S&P 500 constituents...")
    sp500 = _read_html_wiki("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    sp500["idx"] = "SP500"

    print("Fetching Russell 1000 proxy via S&P 400 MidCap...")
    sp400 = _read_html_wiki("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")[0]
    sp400["idx"] = "SP400"

    def norm(df):
        df.columns = [c.strip() for c in df.columns]
        tc = [c for c in df.columns if "ticker" in c.lower() or "symbol" in c.lower()][0]
        sc = [c for c in df.columns if "sector" in c.lower() or "gics" in c.lower()][0]
        df = df.rename(columns={tc: "ticker", sc: "sector"})
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False).str.strip()
        return df[["ticker", "sector", "idx"]]

    combined = pd.concat([norm(sp500), norm(sp400)], ignore_index=True)
    combined = combined.drop_duplicates("ticker")
    print(f"  Combined universe: {len(combined)} tickers")
    return combined


# ── Data fetch ────────────────────────────────────────────────────────────────

def safe_get(d, *keys, default=np.nan):
    v = d
    for k in keys:
        try:
            v = v[k]
        except (KeyError, TypeError, IndexError):
            return default
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _normalize_index(s):
    """Strip timezone from a Series/DataFrame index."""
    idx = s.index
    if hasattr(idx, "tz") and idx.tz is not None:
        s = s.copy()
        s.index = idx.tz_localize(None)
    return s


def _extract(raw, ticker, field):
    """Pull a column from a yf.download result (handles single- and multi-ticker)."""
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            return _normalize_index(raw[field][ticker].dropna())
        except KeyError:
            return pd.Series(dtype=float)
    else:
        return _normalize_index(raw[field].dropna())


def batch_download_prices(tickers, spx_hist, batch_size=60):
    """
    Two-pass batch download — keeps data volumes small:

    Pass A  interval=1wk, period=18mo  (60 tickers / batch)
            → price, rvol_252 (annualised from weekly returns),
              RS-Ratio, RS-Momentum (weekly bars, 52 weeks lookback)

    Pass B  interval=1d,  period=35d   (60 tickers / batch)
            → 30-day avg dollar volume (ADV) for the liquidity gate

    Weekly bars are ~75 rows per ticker vs ~375 for daily/2y — ~5× less data,
    so each batch downloads and processes much faster.
    """
    spx = _normalize_index(spx_hist)          # weekly SPX close (already weekly from caller)

    results   = {}
    n_batches = (len(tickers) + batch_size - 1) // batch_size

    for b in range(n_batches):
        batch = tickers[b * batch_size : (b + 1) * batch_size]
        print(f"  Batch {b+1}/{n_batches}  ({len(batch)} tickers)", flush=True)

        # ── Pass A: weekly bars for momentum + vol ────────────────────────────
        try:
            wk = yf.download(batch, period="18mo", interval="1wk",
                             auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            print(f"    weekly download error: {e}")
            wk = pd.DataFrame()

        # ── Pass B: daily bars (35d) for ADV ─────────────────────────────────
        try:
            dy = yf.download(batch, period="35d", interval="1d",
                             auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            print(f"    daily download error: {e}")
            dy = pd.DataFrame()

        for ticker in batch:
            try:
                wk_close  = _extract(wk, ticker, "Close")
                dy_close  = _extract(dy, ticker, "Close")
                dy_volume = _extract(dy, ticker, "Volume")

                if wk_close.empty or len(wk_close) < 30:
                    continue

                price = float(wk_close.iloc[-1])

                # ADV from daily data (fall back to weekly if daily failed)
                if not dy_close.empty and not dy_volume.empty:
                    dv_idx = dy_close.index.intersection(dy_volume.index)
                    adv_30 = float((dy_close.loc[dv_idx] * dy_volume.loc[dv_idx]).tail(30).mean())
                else:
                    # rough fallback: weekly close × volume
                    wk_vol = _extract(wk, ticker, "Volume")
                    adv_30 = float((wk_close * wk_vol).tail(4).mean()) if not wk_vol.empty else 0.0

                # ── RS-Ratio & RS-Momentum (weekly, 52-week lookback) ─────────
                rs_ratio = rs_momentum = np.nan
                common = wk_close.index.intersection(spx.index)
                if len(common) >= 52:
                    stk = wk_close.loc[common]
                    sx  = spx.loc[common]
                    stk_52w = float(stk.iloc[-1] / stk.iloc[-52])
                    spx_52w = float(sx.iloc[-1]  / sx.iloc[-52])
                    if spx_52w > 0:
                        rs_ratio = (stk_52w / spx_52w) * 100
                    if len(stk) >= 56:            # 52 + 4-week lag
                        stk_4w = float(stk.iloc[-5] / stk.iloc[-56])
                        spx_4w = float(sx.iloc[-5]  / sx.iloc[-56])
                        if spx_4w > 0 and not np.isnan(rs_ratio):
                            rs_ratio_4w = (stk_4w / spx_4w) * 100
                            if rs_ratio_4w > 0:
                                rs_momentum = (rs_ratio / rs_ratio_4w) * 100

                # ── Annualised vol from weekly returns (×√52) ─────────────────
                rvol_252 = float(wk_close.pct_change().std() * np.sqrt(52))

                results[ticker] = {
                    "price":       price,
                    "adv_30":      adv_30,
                    "rs_ratio":    rs_ratio,
                    "rs_momentum": rs_momentum,
                    "rvol_252":    rvol_252,
                }
            except Exception:
                continue

    return results


def fetch_ticker_fundamentals(ticker):
    """
    Fetch fundamentals (info + financials/balance_sheet/cashflow) for a single
    ticker that already passed price-based pre-filters.
    Returns partial dict (no price/rvol fields) or None on failure.
    """
    try:
        t   = yf.Ticker(ticker)
        inf = t.info or {}

        exchange = str(inf.get("exchange", "")).upper()
        mktcap   = inf.get("marketCap", 0) or 0
        if mktcap < MIN_MKTCAP:
            return None

        fin = t.financials
        bal = t.balance_sheet
        cf  = t.cashflow

        if fin is None or fin.empty or bal is None or bal.empty or cf is None or cf.empty:
            return None

        fin = fin.iloc[:, :3]
        bal = bal.iloc[:, :3]
        cf  = cf.iloc[:, :3]
        n_periods = min(fin.shape[1], bal.shape[1], cf.shape[1])
        if n_periods < MIN_YEARS_DATA:
            return None

        def row(df, *names):
            for name in names:
                matches = [i for i in df.index if name.lower() in str(i).lower()]
                if matches:
                    return df.loc[matches[0]]
            return pd.Series([np.nan] * df.shape[1], index=df.columns)

        def v(s, i=0):
            try:
                return float(s.iloc[i])
            except Exception:
                return np.nan

        rev_s     = row(fin, "Total Revenue", "Revenue")
        opinc_s   = row(fin, "Operating Income", "Ebit")
        ebit_s    = row(fin, "EBIT", "Operating Income")
        net_s     = row(fin, "Net Income")
        int_exp_s = row(fin, "Interest Expense")
        gross_s   = row(fin, "Gross Profit")
        cur_a_s   = row(bal, "Current Assets", "Total Current Assets")
        cur_l_s   = row(bal, "Current Liabilities", "Total Current Liabilities")
        inv_s     = row(bal, "Inventory")
        cash_s    = row(bal, "Cash And Cash Equivalents", "Cash")
        tot_d_s   = row(bal, "Total Debt", "Long Term Debt And Capital Lease Obligation")
        equity_s  = row(bal, "Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity")
        opcf_s    = row(cf,  "Operating Cash Flow", "Total Cash From Operating Activities")
        capex_s   = row(cf,  "Capital Expenditure", "Capital Expenditures")

        revenue      = v(rev_s)
        op_inc       = v(opinc_s)
        ebit         = v(ebit_s) if not np.isnan(v(ebit_s)) else op_inc
        net_inc      = v(net_s)
        int_exp      = abs(v(int_exp_s)) if not np.isnan(v(int_exp_s)) else 0.0
        gross_profit = v(gross_s)
        cur_assets   = v(cur_a_s)
        cur_liab     = v(cur_l_s)
        inventory    = v(inv_s) if not np.isnan(v(inv_s)) else 0.0
        cash_val     = v(cash_s)
        tot_debt     = v(tot_d_s) if not np.isnan(v(tot_d_s)) else 0.0
        equity       = v(equity_s)
        op_cf        = v(opcf_s)
        capex        = abs(v(capex_s)) if not np.isnan(v(capex_s)) else 0.0
        fcf          = op_cf - capex if not np.isnan(op_cf) else np.nan

        opinc_hist = [v(opinc_s, i) for i in range(n_periods)]
        opcf_hist  = [v(opcf_s,  i) for i in range(n_periods)]
        capex_hist = [abs(v(capex_s, i)) if not np.isnan(v(capex_s, i)) else 0.0 for i in range(n_periods)]
        fcf_hist   = [o - c for o, c in zip(opcf_hist, capex_hist)]

        net_debt     = max(tot_debt - cash_val, 0.0) if not np.isnan(tot_debt) and not np.isnan(cash_val) else np.nan
        ebit_da      = ebit + safe_get(inf, "depreciation", default=0)
        int_coverage = (ebit / int_exp) if int_exp > 0 else 999.0
        net_d_ebitda = (net_debt / ebit_da) if (not np.isnan(net_debt) and ebit_da > 0) else 0.0
        cur_ratio    = (cur_assets / cur_liab) if (not np.isnan(cur_assets) and cur_liab > 0) else np.nan
        quick_ratio  = ((cur_assets - inventory) / cur_liab) if (not np.isnan(cur_assets) and cur_liab > 0) else np.nan
        de_ratio     = (tot_debt / equity) if (not np.isnan(equity) and equity > 0) else np.nan
        roe          = (net_inc / equity) if (not np.isnan(equity) and equity > 0) else np.nan
        gross_margin = (gross_profit / revenue) if (not np.isnan(revenue) and revenue > 0) else np.nan
        op_margin    = (op_inc / revenue) if (not np.isnan(revenue) and revenue > 0) else np.nan
        fcf_quality  = (fcf / net_inc) if (not np.isnan(net_inc) and net_inc != 0) else np.nan
        cf_quality   = (op_cf / net_inc) if (not np.isnan(net_inc) and net_inc != 0) else np.nan

        profit_years = sum(1 for x in opinc_hist if not np.isnan(x) and x > 0)
        fcf_years    = sum(1 for x in fcf_hist   if not np.isnan(x) and x > 0)

        return {
            "exchange":     exchange,
            "mktcap":       safe_get(inf, "marketCap"),
            "sector":       str(inf.get("sector", "")),
            "n_periods":    n_periods,
            "profit_years": profit_years,
            "fcf_years":    fcf_years,
            "cur_ratio":    cur_ratio,
            "quick_ratio":  quick_ratio,
            "int_coverage": int_coverage,
            "net_d_ebitda": net_d_ebitda,
            "pe":           safe_get(inf, "trailingPE"),
            "pb":           safe_get(inf, "priceToBook"),
            "ev_ebitda":    safe_get(inf, "enterpriseToEbitda"),
            "roe":          roe,
            "gross_margin": gross_margin,
            "op_margin":    op_margin,
            "de_ratio":     de_ratio,
            "fcf_quality":  fcf_quality,
            "cf_quality":   cf_quality,
        }
    except Exception:
        return None


# ── Filter stack ──────────────────────────────────────────────────────────────

def apply_filters(df):
    """
    Fundamentals filter gates. Price >= $5 and ADV >= $10M are already applied
    in Phase 1 (batch price pre-filter), so they are omitted here.
    """
    n0 = len(df)
    stages = []

    def gate(mask, label):
        nonlocal df
        df = df[mask].copy()
        stages.append((label, len(df)))

    gate(~df["sector"].isin(EXCLUDED_SECTORS),                              "Sector exclusion")
    gate(df["exchange"].str[:3].isin({"NYQ", "NMS", "NGM", "NCM", "NYS", "NAS"}) |
         df["exchange"].isin(VALID_EXCHANGES),                               "Exchange (NYSE/NASDAQ)")
    gate(df["n_periods"] >= MIN_YEARS_DATA,                                  "Data completeness (2yr)")
    gate(df["profit_years"] >= MIN_PROFIT_YEARS,                             "Profitability gate")
    gate(df["fcf_years"] >= MIN_FCF_YEARS,                                   "FCF gate")
    gate((df["cur_ratio"] >= MIN_CURRENT_RATIO) &
         (df["quick_ratio"] >= MIN_QUICK_RATIO),                             "Short-term solvency")
    gate((df["int_coverage"] >= MIN_INT_COVERAGE) &
         (df["net_d_ebitda"].fillna(0) <= MAX_NET_DEBT_EBITDA),              "Long-term solvency")

    print(f"\nFilter funnel ({n0} starting, price/ADV pre-filtered in Phase 1):")
    for label, n in stages:
        print(f"  {label:<35} -> {n:>4} remaining")
    return df


# ── Factor scoring ────────────────────────────────────────────────────────────

def pct_rank(s, ascending=True):
    """Percentile rank 0-100. NaNs get 50 (neutral)."""
    r = s.rank(pct=True, ascending=ascending, na_option="keep") * 100
    return r.fillna(50.0)


def score_universe(df):
    # ── VALUE (lower = better) ────────────────────────────────────────────────
    df["score_value"] = (
        pct_rank(df["pe"],       ascending=False) +
        pct_rank(df["pb"],       ascending=False) +
        pct_rank(df["ev_ebitda"],ascending=False)
    ) / 3

    # ── QUALITY (higher = better) ─────────────────────────────────────────────
    df["score_quality"] = (
        pct_rank(df["roe"],          ascending=True) +
        pct_rank(df["gross_margin"], ascending=True) +
        pct_rank(df["op_margin"],    ascending=True) +
        pct_rank(df["de_ratio"],     ascending=False) +   # lower debt = better
        pct_rank(df["int_coverage"], ascending=True) +
        pct_rank(df["fcf_quality"],  ascending=True)
    ) / 6

    # ── RELATIVE MOMENTUM (RRG-inspired, vs SPX) ──────────────────────────────
    # Equal weight RS-Ratio and RS-Momentum; both normalized to same 0-100 scale
    rs_ratio_score = pct_rank(df["rs_ratio"],    ascending=True)
    rs_mom_score   = pct_rank(df["rs_momentum"], ascending=True)
    df["score_momentum"] = (rs_ratio_score + rs_mom_score) / 2

    # ── LOW VOLATILITY (lower rvol = better) ──────────────────────────────────
    df["score_low_vol"] = pct_rank(df["rvol_252"], ascending=False)

    # ── COMPOSITE (equal factor weights) ─────────────────────────────────────
    df["score_composite"] = (
        df["score_value"] +
        df["score_quality"] +
        df["score_momentum"] +
        df["score_low_vol"]
    ) / 4

    return df.sort_values("score_composite", ascending=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()

    # ── SPX weekly history for relative momentum ──────────────────────────────
    print("Downloading SPX weekly history for relative momentum...")
    spx_raw  = yf.Ticker("^GSPC").history(period="18mo", interval="1wk", auto_adjust=True)
    spx_hist = spx_raw["Close"] if not spx_raw.empty else pd.Series(dtype=float)
    # Strip timezone so index aligns with batch download output
    if hasattr(spx_hist.index, "tz") and spx_hist.index.tz is not None:
        spx_hist.index = spx_hist.index.tz_localize(None)

    universe   = fetch_universe()
    tickers    = universe["ticker"].tolist()
    sector_map = dict(zip(universe["ticker"], universe["sector"]))

    # ── Phase 1: batch OHLCV (60 at a time) ──────────────────────────────────
    print(f"\nPhase 1 — batch price download ({len(tickers)} tickers, 30/batch)...")
    price_data = batch_download_prices(tickers, spx_hist, batch_size=30)
    print(f"  Price data fetched: {len(price_data)} tickers  ({time.time()-t0:.0f}s)")

    # Pre-filter on price, ADV, and market cap before touching fundamentals
    # Market cap estimated from price × shares; we use ADV as a proxy when mktcap unavailable
    pre_pass = [
        t for t, d in price_data.items()
        if d["price"] >= MIN_PRICE and d["adv_30"] >= MIN_ADV_USD
    ]
    print(f"  After price/ADV pre-filter: {len(pre_pass)} tickers")

    # ── Phase 2: fundamentals (per ticker, only survivors) ────────────────────
    print(f"\nPhase 2 — fundamentals fetch ({len(pre_pass)} tickers)...")
    rows, failed = [], 0
    for i, ticker in enumerate(pre_pass):
        fund = fetch_ticker_fundamentals(ticker)
        elapsed = time.time() - t0
        if fund is None:
            failed += 1
            print(f"  [{i+1}/{len(pre_pass)}]  {ticker:<6}  SKIP  "
                  f"ok={len(rows)}  failed={failed}  elapsed={elapsed:.0f}s")
        else:
            rec = {"ticker": ticker, **price_data[ticker], **fund}
            if not rec.get("sector") or rec["sector"] == "nan":
                rec["sector"] = sector_map.get(ticker, "")
            rows.append(rec)
            print(f"  [{i+1}/{len(pre_pass)}]  {ticker:<6}  ok    "
                  f"ok={len(rows)}  failed={failed}  elapsed={elapsed:.0f}s")
        time.sleep(0.1)  # small pause to avoid rate-limit kills

    print(f"\nData fetch complete: {len(rows)} ok, {failed} failed  ({time.time()-t0:.0f}s)")

    raw      = pd.DataFrame(rows)
    filtered = apply_filters(raw)
    print(f"\n{len(filtered)} stocks passed all filters")

    if len(filtered) < 5:
        print("Too few stocks passed filters — check data quality.")
        return

    scored = score_universe(filtered)
    top    = scored.head(N_HOLDINGS).copy()

    # Factor-score-weighted target allocation
    top["target_weight"] = top["score_composite"] / top["score_composite"].sum()

    # Build output
    selection = {
        "as_of": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "n_holdings": len(top),
        "holdings": {
            row["ticker"]: {
                "target_weight":   round(float(row["target_weight"]), 6),
                "score_composite": round(float(row["score_composite"]), 1),
                "score_momentum":  round(float(row["score_momentum"]), 1),
                "score_quality":   round(float(row["score_quality"]), 1),
                "score_value":     round(float(row["score_value"]), 1),
                "score_low_vol":   round(float(row["score_low_vol"]), 1),
                "sector":          str(row["sector"]),
                "rs_ratio":        round(float(row["rs_ratio"]), 2) if not np.isnan(row["rs_ratio"]) else None,
                "rs_momentum":     round(float(row["rs_momentum"]), 2) if not np.isnan(row["rs_momentum"]) else None,
                "rvol_252":        round(float(row["rvol_252"]), 4) if not np.isnan(row["rvol_252"]) else None,
            }
            for _, row in top.iterrows()
        }
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(selection, f, indent=2)

    print(f"\n{'='*80}")
    print(f"TOP {N_HOLDINGS} HOLDINGS — Factor Portfolio Selection")
    print(f"{'='*80}")
    display = top[["ticker", "sector", "score_composite", "score_momentum",
                   "score_quality", "score_value", "score_low_vol",
                   "rs_ratio", "rs_momentum", "target_weight"]].copy()
    for col in ["score_composite","score_momentum","score_quality","score_value","score_low_vol"]:
        display[col] = display[col].round(1)
    display["rs_ratio"]     = display["rs_ratio"].round(1)
    display["rs_momentum"]  = display["rs_momentum"].round(1)
    display["target_weight"] = (display["target_weight"] * 100).round(2).astype(str) + "%"
    print(display.to_string(index=False))
    print(f"\nWeights sum: {top['target_weight'].sum():.6f} (should be 1.0)")
    print(f"Written: {OUTPUT_PATH}")
    print(f"Total runtime: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
