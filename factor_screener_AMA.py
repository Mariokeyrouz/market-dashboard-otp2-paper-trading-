"""
Factor Screener AMA — AlphaMind Adjusted
=========================================
Identical to factor_screener.py with one change recommended by AlphaMind:

  VALUE factor replaced by SUE (Standardized Unexpected Earnings)
  ---------------------------------------------------------------
  Value (P/E, P/B, EV/EBITDA) is redundant after the quality filter — the
  filter already screens out distressed cheap names, leaving medium-cheap
  quality stocks with weak factor returns. Worse, value and momentum are
  negatively correlated at regime turning points, producing incoherent
  composite scores.

  SUE = (latest_EPS - prior_EPS) / std(EPS over trailing quarters)
  It is orthogonal to momentum (analyst-driven, not price-driven), orthogonal
  to quality, and uncorrelated to low volatility. Positive earnings surprises
  are a persistent, independent alpha source.

  Data: yfinance quarterly_earnings (free, no new vendor required).
  Approximation note: prior EPS uses the immediately preceding quarter rather
  than the same quarter prior year (ideal). Validate alpha before upgrading
  to Polygon analyst consensus data.

New composite: (score_quality + score_momentum + score_low_vol + score_sue) / 4

Output: factor_selection_AMA.json

Usage:
  python factor_screener_AMA.py
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

# ── Constants (identical to factor_screener.py) ───────────────────────────────

N_HOLDINGS       = 18
EXCLUDED_SECTORS = {"Financial Services", "Real Estate"}
MIN_PRICE        = 10.0
MIN_ADV_USD      = 25_000_000
MIN_MKTCAP       = 2_000_000_000
MIN_YEARS_DATA   = 2
MIN_PROFIT_YEARS = 2
MIN_FCF_YEARS    = 2
MIN_CURRENT_RATIO  = 1.0
MIN_QUICK_RATIO    = 0.7
MIN_INT_COVERAGE   = 1.5
MAX_NET_DEBT_EBITDA = 5.0
VALID_EXCHANGES  = {"NYQ", "NMS", "NGM", "NCM", "NYSE", "NASDAQ", "NYS", "NAS"}

OUTPUT_PATH = "factor_selection_AMA.json"


# ── Universe (identical) ──────────────────────────────────────────────────────

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


# ── Utilities (identical) ─────────────────────────────────────────────────────

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
    idx = s.index
    if hasattr(idx, "tz") and idx.tz is not None:
        s = s.copy()
        s.index = idx.tz_localize(None)
    return s


def _extract(raw, ticker, field):
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            return _normalize_index(raw[field][ticker].dropna())
        except KeyError:
            return pd.Series(dtype=float)
    else:
        return _normalize_index(raw[field].dropna())


# ── Batch price download (identical) ─────────────────────────────────────────

def batch_download_prices(tickers, spx_hist, batch_size=30):
    spx       = _normalize_index(spx_hist)
    results   = {}
    n_batches = (len(tickers) + batch_size - 1) // batch_size

    for b in range(n_batches):
        batch = tickers[b * batch_size : (b + 1) * batch_size]
        print(f"  Batch {b+1}/{n_batches}  ({len(batch)} tickers)", flush=True)

        try:
            wk = yf.download(batch, period="18mo", interval="1wk",
                             auto_adjust=True, progress=False, threads=True)
        except Exception as e:
            print(f"    weekly download error: {e}")
            wk = pd.DataFrame()

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

                if not dy_close.empty and not dy_volume.empty:
                    dv_idx = dy_close.index.intersection(dy_volume.index)
                    adv_30 = float((dy_close.loc[dv_idx] * dy_volume.loc[dv_idx]).tail(30).mean())
                else:
                    wk_vol = _extract(wk, ticker, "Volume")
                    adv_30 = float((wk_close * wk_vol).tail(4).mean()) if not wk_vol.empty else 0.0

                rs_ratio = rs_momentum = np.nan
                common = wk_close.index.intersection(spx.index)
                if len(common) >= 52:
                    stk = wk_close.loc[common]
                    sx  = spx.loc[common]
                    stk_52w = float(stk.iloc[-1] / stk.iloc[-52])
                    spx_52w = float(sx.iloc[-1]  / sx.iloc[-52])
                    if spx_52w > 0:
                        rs_ratio = (stk_52w / spx_52w) * 100
                    if len(stk) >= 56:
                        stk_4w = float(stk.iloc[-5] / stk.iloc[-56])
                        spx_4w = float(sx.iloc[-5]  / sx.iloc[-56])
                        if spx_4w > 0 and not np.isnan(rs_ratio):
                            rs_ratio_4w = (stk_4w / spx_4w) * 100
                            if rs_ratio_4w > 0:
                                rs_momentum = (rs_ratio / rs_ratio_4w) * 100

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


# ── Fundamentals fetch — AMA version (SUE replaces value) ────────────────────

def _compute_sue(ticker_obj):
    """
    Approximate SUE from yfinance quarterly earnings.
    SUE = (latest_EPS - prior_EPS) / std(EPS series)
    Returns float or np.nan.
    """
    try:
        qe = ticker_obj.quarterly_earnings
        if qe is None or qe.empty:
            return np.nan
        eps_col = [c for c in qe.columns if "reported" in c.lower() or "eps" in c.lower()]
        if not eps_col:
            return np.nan
        eps = qe[eps_col[0]].dropna()
        if len(eps) < 3:
            return np.nan
        latest = float(eps.iloc[0])
        prior  = float(eps.iloc[1])
        std    = float(eps.std())
        if std < 1e-6:
            return 0.0
        return (latest - prior) / std
    except Exception:
        return np.nan


def fetch_ticker_fundamentals(ticker):
    """
    AMA version: drops pe/pb/ev_ebitda, adds sue (SUE score).
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

        profit_years = sum(1 for x in opinc_hist if not np.isnan(x) and x > 0)
        fcf_years    = sum(1 for x in fcf_hist   if not np.isnan(x) and x > 0)

        # ── AMA: SUE replaces Value ───────────────────────────────────────────
        sue = _compute_sue(t)

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
            # No pe / pb / ev_ebitda
            "sue":          sue,          # AMA: Standardized Unexpected Earnings
            "roe":          roe,
            "gross_margin": gross_margin,
            "op_margin":    op_margin,
            "de_ratio":     de_ratio,
            "fcf_quality":  fcf_quality,
        }
    except Exception:
        return None


# ── Filter stack (identical) ──────────────────────────────────────────────────

def apply_filters(df):
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


# ── Factor scoring — AMA version ─────────────────────────────────────────────

def pct_rank(s, ascending=True):
    r = s.rank(pct=True, ascending=ascending, na_option="keep") * 100
    return r.fillna(50.0)


def score_universe(df):
    # ── QUALITY (unchanged) ───────────────────────────────────────────────────
    df["score_quality"] = (
        pct_rank(df["roe"],          ascending=True) +
        pct_rank(df["gross_margin"], ascending=True) +
        pct_rank(df["op_margin"],    ascending=True) +
        pct_rank(df["de_ratio"],     ascending=False) +
        pct_rank(df["int_coverage"], ascending=True) +
        pct_rank(df["fcf_quality"],  ascending=True)
    ) / 6

    # ── RELATIVE MOMENTUM (unchanged) ────────────────────────────────────────
    df["score_momentum"] = (
        pct_rank(df["rs_ratio"],    ascending=True) +
        pct_rank(df["rs_momentum"], ascending=True)
    ) / 2

    # ── LOW VOLATILITY (unchanged) ────────────────────────────────────────────
    df["score_low_vol"] = pct_rank(df["rvol_252"], ascending=False)

    # ── SUE — replaces Value (AMA addition) ───────────────────────────────────
    # Higher positive earnings surprise = higher score
    df["score_sue"] = pct_rank(df["sue"], ascending=True)

    # ── COMPOSITE (equal weight, 4 factors) ───────────────────────────────────
    df["score_composite"] = (
        df["score_quality"] +
        df["score_momentum"] +
        df["score_low_vol"] +
        df["score_sue"]
    ) / 4

    return df.sort_values("score_composite", ascending=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()

    print("Downloading SPX weekly history for relative momentum...")
    spx_raw  = yf.Ticker("^GSPC").history(period="18mo", interval="1wk", auto_adjust=True)
    spx_hist = spx_raw["Close"] if not spx_raw.empty else pd.Series(dtype=float)
    if hasattr(spx_hist.index, "tz") and spx_hist.index.tz is not None:
        spx_hist.index = spx_hist.index.tz_localize(None)

    universe   = fetch_universe()
    tickers    = universe["ticker"].tolist()
    sector_map = dict(zip(universe["ticker"], universe["sector"]))

    print(f"\nPhase 1 — batch price download ({len(tickers)} tickers, 30/batch)...")
    price_data = batch_download_prices(tickers, spx_hist, batch_size=30)
    print(f"  Price data fetched: {len(price_data)} tickers  ({time.time()-t0:.0f}s)")

    pre_pass = [
        t for t, d in price_data.items()
        if d["price"] >= MIN_PRICE and d["adv_30"] >= MIN_ADV_USD
    ]
    print(f"  After price/ADV pre-filter: {len(pre_pass)} tickers")

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
        time.sleep(0.1)

    print(f"\nData fetch complete: {len(rows)} ok, {failed} failed  ({time.time()-t0:.0f}s)")

    raw      = pd.DataFrame(rows)
    filtered = apply_filters(raw)
    print(f"\n{len(filtered)} stocks passed all filters")

    if len(filtered) < 5:
        print("Too few stocks passed filters — check data quality.")
        return

    scored = score_universe(filtered)
    top    = scored.head(N_HOLDINGS).copy()
    top["target_weight"] = top["score_composite"] / top["score_composite"].sum()

    selection = {
        "as_of":      pd.Timestamp.today().strftime("%Y-%m-%d"),
        "variant":    "AMA",
        "n_holdings": len(top),
        "holdings": {
            row["ticker"]: {
                "target_weight":   round(float(row["target_weight"]), 6),
                "score_composite": round(float(row["score_composite"]), 1),
                "score_momentum":  round(float(row["score_momentum"]), 1),
                "score_quality":   round(float(row["score_quality"]), 1),
                "score_sue":       round(float(row["score_sue"]), 1),
                "score_low_vol":   round(float(row["score_low_vol"]), 1),
                "sector":          str(row["sector"]),
                "rs_ratio":        round(float(row["rs_ratio"]), 2) if not np.isnan(row["rs_ratio"]) else None,
                "rs_momentum":     round(float(row["rs_momentum"]), 2) if not np.isnan(row["rs_momentum"]) else None,
                "rvol_252":        round(float(row["rvol_252"]), 4) if not np.isnan(row["rvol_252"]) else None,
                "sue":             round(float(row["sue"]), 3) if not np.isnan(row["sue"]) else None,
            }
            for _, row in top.iterrows()
        }
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(selection, f, indent=2)

    print(f"\n{'='*80}")
    print(f"TOP {N_HOLDINGS} HOLDINGS — FMTS AMA Factor Portfolio Selection")
    print(f"{'='*80}")
    display = top[["ticker", "sector", "score_composite", "score_momentum",
                   "score_quality", "score_sue", "score_low_vol",
                   "rs_ratio", "rs_momentum", "target_weight"]].copy()
    for col in ["score_composite","score_momentum","score_quality","score_sue","score_low_vol"]:
        display[col] = display[col].round(1)
    display["rs_ratio"]      = display["rs_ratio"].round(1)
    display["rs_momentum"]   = display["rs_momentum"].round(1)
    display["target_weight"] = (display["target_weight"] * 100).round(2).astype(str) + "%"
    print(display.to_string(index=False))
    print(f"\nWeights sum: {top['target_weight'].sum():.6f} (should be 1.0)")
    print(f"Written: {OUTPUT_PATH}")
    print(f"Total runtime: {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
