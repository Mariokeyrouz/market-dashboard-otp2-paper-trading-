"""
Equity Analysis Dashboard
==========================
Read-only research tool: type a ticker, get a full single-stock view —
company overview, key stats, trailing returns, earnings history,
fundamentals deep-dive, and cash-flow trends.

No ledger, no daily-update wiring — purely additive, not part of the
paper-trading system (does not touch ENGINES/STRATS/PORTFOLIOS).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Equity Analysis", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
</style>
""", unsafe_allow_html=True)

GRID_COLOR = "#2a2a3e"
CF_COLORS = {
    "Operating CF": "#4a9eff",
    "Investing CF": "#c9a227",
    "Financing CF": "#8e5ac9",
    "Free Cash Flow": "#00c896",
}

# ── Helpers ──────────────────────────────────────────────────────────────────


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


def row(df, *names):
    """Fuzzy substring match against a statement DataFrame's index."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
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


def fmt(x, kind="num2"):
    """Centralized formatter — NaN/None always render as N/A."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    if kind == "pct":
        return f"{x * 100:.2f}%"
    if kind == "pct_signed":
        return f"{x * 100:+.2f}%"
    if kind == "usd":
        sign = "-" if x < 0 else ""
        ax = abs(x)
        if ax >= 1e12:
            return f"{sign}${ax / 1e12:.2f}T"
        if ax >= 1e9:
            return f"{sign}${ax / 1e9:.2f}B"
        if ax >= 1e6:
            return f"{sign}${ax / 1e6:.2f}M"
        if ax >= 1e3:
            return f"{sign}${ax / 1e3:.2f}K"
        return f"{sign}${ax:,.2f}"
    if kind == "num0":
        return f"{x:,.0f}"
    return f"{x:.2f}"  # num2


# ── Data fetch ───────────────────────────────────────────────────────────────


@st.cache_data(ttl=300)
def fetch_ticker_bundle(ticker: str) -> dict:
    """Single entry point for all data on one ticker. Never raises — every
    field defaults to an empty/None sentinel on failure."""
    out = {
        "ticker": ticker, "info": {}, "hist": pd.DataFrame(),
        "fin": pd.DataFrame(), "bal": pd.DataFrame(), "cf": pd.DataFrame(),
        "qcf": pd.DataFrame(), "earnings": None, "valid": False,
    }
    if not ticker:
        return out

    t = yf.Ticker(ticker)

    try:
        out["info"] = t.info or {}
    except Exception:
        out["info"] = {}

    try:
        hist = t.history(period="5y", interval="1d")
        if hist is None or hist.empty or len(hist) < 30:
            hist = t.history(period="max", interval="1d")
        out["hist"] = hist if hist is not None else pd.DataFrame()
    except Exception:
        out["hist"] = pd.DataFrame()

    try:
        out["fin"] = t.financials if t.financials is not None else pd.DataFrame()
    except Exception:
        out["fin"] = pd.DataFrame()

    try:
        out["bal"] = t.balance_sheet if t.balance_sheet is not None else pd.DataFrame()
    except Exception:
        out["bal"] = pd.DataFrame()

    try:
        out["cf"] = t.cashflow if t.cashflow is not None else pd.DataFrame()
    except Exception:
        out["cf"] = pd.DataFrame()

    try:
        out["qcf"] = t.quarterly_cashflow if t.quarterly_cashflow is not None else pd.DataFrame()
    except Exception:
        out["qcf"] = pd.DataFrame()

    try:
        ed = t.get_earnings_dates(limit=12)
        out["earnings"] = ed if ed is not None and not ed.empty else None
    except Exception:
        out["earnings"] = None

    out["valid"] = (
        (not out["hist"].empty)
        or bool(out["info"].get("longBusinessSummary"))
        or bool(out["info"].get("shortName"))
    )
    return out


def trailing_returns(hist: pd.DataFrame) -> dict:
    """1d/5d/1m/6m/YTD/1y/5y returns (fractions, e.g. 0.05 = +5%), calendar-
    anchored so weekends/holidays don't skew the window. None where the
    ticker's history doesn't reach far enough back."""
    labels = ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y"]
    result = {l: None for l in labels}
    if hist is None or hist.empty:
        return result

    close = hist["Close"].dropna()
    if close.empty:
        return result
    if close.index.tz is not None:
        close = close.copy()
        close.index = close.index.tz_localize(None)

    last_date = close.index[-1]
    last_close = float(close.iloc[-1])
    first_date = close.index[0]

    def asof(target_date):
        idx = close.index[close.index <= target_date]
        if len(idx) == 0:
            return None
        return float(close.loc[idx[-1]])

    if len(close) > 1:
        prev = float(close.iloc[-2])
        if prev > 0:
            result["1D"] = last_close / prev - 1

    windows = {
        "5D": last_date - pd.Timedelta(days=7),
        "1M": last_date - pd.DateOffset(months=1),
        "6M": last_date - pd.DateOffset(months=6),
        "YTD": pd.Timestamp(year=last_date.year, month=1, day=1),
        "1Y": last_date - pd.DateOffset(years=1),
        "5Y": last_date - pd.DateOffset(years=5),
    }
    for label, target in windows.items():
        if target < first_date:
            continue
        anchor = asof(target)
        if anchor is not None and anchor > 0:
            result[label] = last_close / anchor - 1
    return result


def build_earnings_table(earnings: pd.DataFrame | None) -> pd.DataFrame:
    """Last 4 *reported* earnings (drops future/unconfirmed estimate rows)."""
    if earnings is None or earnings.empty:
        return pd.DataFrame()

    df = earnings.reset_index()
    df.columns = [str(c).strip() for c in df.columns]
    keep = [c for c in ["Earnings Date", "EPS Estimate", "Reported EPS", "Surprise(%)"] if c in df.columns]
    if "Earnings Date" not in keep or "Reported EPS" not in keep:
        return pd.DataFrame()

    df = df[keep].dropna(subset=["Reported EPS"])
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("Earnings Date", ascending=False).head(4).reset_index(drop=True)

    def flag(r):
        est, rep = r.get("EPS Estimate"), r.get("Reported EPS")
        if pd.isna(est) or pd.isna(rep):
            return "N/A"
        return "Beat" if rep >= est else "Miss"

    df["Beat/Miss"] = df.apply(flag, axis=1)
    df["Earnings Date"] = pd.to_datetime(df["Earnings Date"]).dt.strftime("%Y-%m-%d")
    for c in ["EPS Estimate", "Reported EPS", "Surprise(%)"]:
        if c in df.columns:
            df[c] = df[c].round(2)
    return df.rename(columns={"Surprise(%)": "Surprise (%)"})


def compute_fundamentals(info: dict, fin: pd.DataFrame, bal: pd.DataFrame) -> dict:
    """Valuation/short-interest/dividend fields come straight from `.info`
    (no reliable statement equivalent). Everything else is derived from the
    statements directly, since `.info`'s own ratio fields are inconsistent
    across tickers (see factor_screener.py / op2_screener.py precedent)."""
    f = {}

    f["trailing_pe"] = safe_get(info, "trailingPE")
    f["forward_pe"] = safe_get(info, "forwardPE")
    f["ps"] = safe_get(info, "priceToSalesTrailing12Months")
    f["pb"] = safe_get(info, "priceToBook")
    f["beta"] = safe_get(info, "beta")
    f["market_cap"] = safe_get(info, "marketCap")

    payout = safe_get(info, "payoutRatio")
    div_rate = info.get("dividendRate")
    f["has_dividend"] = div_rate is not None
    f["payout_ratio"] = payout
    f["retention_rate"] = (1 - payout) if not np.isnan(payout) else np.nan

    f["short_pct_float"] = safe_get(info, "shortPercentOfFloat")
    f["short_ratio"] = safe_get(info, "shortRatio")
    f["shares_short"] = safe_get(info, "sharesShort")

    rev_s = row(fin, "Total Revenue", "Revenue")
    op_s = row(fin, "Operating Income")
    net_s = row(fin, "Net Income")
    ebitda_s = row(fin, "EBITDA")
    ebit_s = row(fin, "EBIT", "Operating Income")
    dep_s = row(fin, "Reconciled Depreciation", "Depreciation")
    int_s = row(fin, "Interest Expense")

    cash_s = row(bal, "Cash And Cash Equivalents", "Cash")
    cur_a_s = row(bal, "Current Assets", "Total Current Assets")
    cur_l_s = row(bal, "Current Liabilities", "Total Current Liabilities")
    inv_s = row(bal, "Inventory")
    debt_s = row(bal, "Total Debt")
    equity_s = row(bal, "Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity")
    assets_s = row(bal, "Total Assets")

    revenue = v(rev_s)
    op_inc = v(op_s)
    net_inc = v(net_s)
    equity = v(equity_s)
    assets = v(assets_s)
    cur_assets = v(cur_a_s)
    cur_liab = v(cur_l_s)
    inventory = v(inv_s)
    if np.isnan(inventory):
        inventory = 0.0
    total_debt = v(debt_s)
    total_cash = v(cash_s)

    ebitda = v(ebitda_s)
    if np.isnan(ebitda):
        ebit, dep = v(ebit_s), v(dep_s)
        ebitda = ebit + dep if not (np.isnan(ebit) or np.isnan(dep)) else np.nan
    interest_exp = abs(v(int_s))

    f["revenue"] = revenue
    f["profit_margin"] = net_inc / revenue if revenue > 0 else np.nan
    f["operating_margin"] = op_inc / revenue if revenue > 0 else np.nan
    f["roe"] = net_inc / equity if equity > 0 else np.nan
    f["roa"] = net_inc / assets if assets > 0 else np.nan
    f["total_cash"] = total_cash
    f["total_debt"] = total_debt
    f["debt_to_equity"] = total_debt / equity if equity > 0 else np.nan
    f["current_ratio"] = cur_assets / cur_liab if cur_liab > 0 else np.nan
    f["quick_ratio"] = (cur_assets - inventory) / cur_liab if cur_liab > 0 else np.nan
    f["interest_coverage"] = ebitda / interest_exp if interest_exp > 0 else np.nan

    return f


def build_cashflow_frame(cf: pd.DataFrame, quarterly: bool, n_periods: int) -> pd.DataFrame:
    if cf is None or cf.empty:
        return pd.DataFrame()

    ocf = row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
    icf = row(cf, "Investing Cash Flow", "Total Cashflows From Investing Activities")
    fin_cf = row(cf, "Financing Cash Flow", "Total Cash From Financing Activities")
    capex = row(cf, "Capital Expenditure", "Capital Expenditures")
    fcf = ocf - capex.abs()

    cols = list(reversed(list(cf.columns[:n_periods])))  # oldest -> newest

    def label(c):
        ts = pd.Timestamp(c)
        if quarterly:
            return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
        return str(ts.year)

    def series_vals(s):
        return [float(s.loc[c]) if c in s.index and pd.notna(s.loc[c]) else np.nan for c in cols]

    return pd.DataFrame({
        "Period": [label(c) for c in cols],
        "Operating CF": series_vals(ocf),
        "Investing CF": series_vals(icf),
        "Financing CF": series_vals(fin_cf),
        "Free Cash Flow": series_vals(fcf),
    })


def cashflow_chart(df: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    for col, color in CF_COLORS.items():
        fig.add_trace(go.Bar(name=col, x=df["Period"], y=df[col], marker_color=color))
    fig.update_layout(
        barmode="group",
        title=title,
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=40, b=0),
        yaxis=dict(gridcolor=GRID_COLOR, tickformat="$,.0f"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


# ── Page ─────────────────────────────────────────────────────────────────────

st.title("🔍 Equity Analysis Dashboard")
st.caption("Look up any ticker for a full view: overview, fundamentals, and cash-flow trends. Research tool only — not investment advice.")

if "eq_ticker" not in st.session_state:
    st.session_state["eq_ticker"] = "AAPL"

ticker_input = st.text_input("Ticker", value=st.session_state["eq_ticker"]).strip().upper()
if ticker_input:
    st.session_state["eq_ticker"] = ticker_input
ticker = st.session_state["eq_ticker"]

if not ticker:
    st.info("Enter a ticker to begin.")
    st.stop()

bundle = fetch_ticker_bundle(ticker)

if not bundle["valid"]:
    st.error(f"No data found for '{ticker}'. Check the symbol and try again.")
    st.stop()

info, hist = bundle["info"], bundle["hist"]
fin, bal, cf, qcf = bundle["fin"], bundle["bal"], bundle["cf"], bundle["qcf"]
fnd = compute_fundamentals(info, fin, bal)

tab_overview, tab_fundamentals, tab_cashflow = st.tabs(["📋 Overview", "📊 Fundamentals", "💵 Cash Flow"])

# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab_overview:
    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector") or "N/A"
    industry = info.get("industry") or "N/A"
    st.subheader(f"{name} ({ticker})")
    st.caption(f"{sector} · {industry}")

    summary = info.get("longBusinessSummary")
    if summary:
        if len(summary) > 500:
            st.write(summary[:500].rsplit(" ", 1)[0] + "…")
            with st.expander("Read full description"):
                st.write(summary)
        else:
            st.write(summary)
    else:
        st.info("No company description available.")

    st.markdown("**Key Stats**")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Trailing P/E", fmt(fnd["trailing_pe"]))
    c2.metric("Forward P/E", fmt(fnd["forward_pe"]))
    c3.metric("Market Cap", fmt(fnd["market_cap"], "usd"))
    c4.metric("Beta", fmt(fnd["beta"]))
    c5.metric("Industry", industry)

    st.markdown("**Trailing Returns**")
    rets = trailing_returns(hist)
    cols = st.columns(7)
    for col, label in zip(cols, ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y"]):
        col.metric(label, fmt(rets.get(label), "pct_signed"))

    st.markdown("**Last 4 Earnings**")
    eq_table = build_earnings_table(bundle["earnings"])
    if eq_table.empty:
        st.info("No earnings history available for this ticker.")
    else:
        st.dataframe(eq_table, width="stretch", height=38 + 35 * len(eq_table) + 10, hide_index=True)

# ── Tab 2: Fundamentals ────────────────────────────────────────────────────────
with tab_fundamentals:
    if fin.empty and bal.empty:
        st.info("Fundamentals data unavailable for this ticker.")
    else:
        sub_val, sub_prof, sub_liq, sub_div, sub_short = st.tabs(
            ["Valuation", "Profitability", "Liquidity & Solvency", "Dividends", "Short Interest"]
        )

        with sub_val:
            c1, c2 = st.columns(2)
            c1.metric("P/S", fmt(fnd["ps"]))
            c2.metric("P/B", fmt(fnd["pb"]))

        with sub_prof:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Revenue", fmt(fnd["revenue"], "usd"))
            c2.metric("Profit Margin", fmt(fnd["profit_margin"], "pct"))
            c3.metric("Operating Margin", fmt(fnd["operating_margin"], "pct"))
            c4.metric("Return on Equity", fmt(fnd["roe"], "pct"))
            c5.metric("Return on Assets", fmt(fnd["roa"], "pct"))

        with sub_liq:
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total Cash", fmt(fnd["total_cash"], "usd"))
            c2.metric("Total Debt", fmt(fnd["total_debt"], "usd"))
            c3.metric("Debt/Equity", fmt(fnd["debt_to_equity"]))
            c4.metric("Current Ratio", fmt(fnd["current_ratio"]))
            c5.metric("Quick Ratio", fmt(fnd["quick_ratio"]))
            c6.metric("Interest Coverage (DSR proxy)", fmt(fnd["interest_coverage"]))
            st.caption(
                "yfinance doesn't expose a principal-repayment schedule, so a textbook "
                "Debt Service Ratio isn't derivable. Interest Coverage (EBITDA / Interest "
                "Expense) is shown instead as the closest available proxy for debt-service capacity."
            )

        with sub_div:
            if fnd["has_dividend"]:
                c1, c2 = st.columns(2)
                c1.metric("Dividend Payout Ratio", fmt(fnd["payout_ratio"], "pct"))
                c2.metric("Retention Rate", fmt(fnd["retention_rate"], "pct"))
            else:
                st.info("No dividend.")

        with sub_short:
            c1, c2, c3 = st.columns(3)
            c1.metric("Short % of Float", fmt(fnd["short_pct_float"], "pct"))
            c2.metric("Short Ratio (days to cover)", fmt(fnd["short_ratio"]))
            c3.metric("Shares Short", fmt(fnd["shares_short"], "num0"))

# ── Tab 3: Cash Flow ───────────────────────────────────────────────────────────
with tab_cashflow:
    st.markdown("**Annual**")
    annual_cf = build_cashflow_frame(cf, quarterly=False, n_periods=4)
    if annual_cf.empty:
        st.info("Annual cash flow data unavailable for this ticker.")
    else:
        st.plotly_chart(cashflow_chart(annual_cf, "Annual Cash Flow Trend"), width="stretch")
        st.dataframe(annual_cf.set_index("Period"), width="stretch")

    st.markdown("**Quarterly**")
    quarterly_cf = build_cashflow_frame(qcf, quarterly=True, n_periods=5)
    if quarterly_cf.empty:
        st.info("Quarterly cash flow data unavailable for this ticker.")
    else:
        st.plotly_chart(cashflow_chart(quarterly_cf, "Quarterly Cash Flow Trend"), width="stretch")
        st.dataframe(quarterly_cf.set_index("Period"), width="stretch")
