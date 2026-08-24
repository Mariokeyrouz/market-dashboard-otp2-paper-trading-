"""
Equity Analysis Dashboard (EAD)
==========================
Read-only research tool: type a ticker, get a full single-stock view —
company overview, key stats, trailing returns, earnings history,
fundamentals deep-dive, institutional ownership, and cash-flow trends —
laid out as one dense scrollable page of card panels (no tabs).

No ledger, no daily-update wiring — purely additive, not part of the
paper-trading system (does not touch ENGINES/STRATS/PORTFOLIOS).
"""

import html as _html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Equity Analysis Dashboard", page_icon="🔍", layout="wide")

GRID_COLOR = "#2a2a3e"
POS_COLOR = "#00c896"
NEG_COLOR = "#ff4b4b"
CF_COLORS = {
    "Operating CF": "#4a9eff",
    "Investing CF": "#c9a227",
    "Financing CF": "#8e5ac9",
    "Free Cash Flow": "#00c896",
}

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    [data-testid="stVerticalBlock"] { gap: 0.4rem; }

    .ead-title { font-size: 19px; font-weight: 700; color: #e6e6e6; margin: 0; }
    .ead-subtitle { font-size: 11.5px; color: #8080a0; margin: 0 0 8px 0; }
    .ead-company { font-size: 15px; font-weight: 700; color: #e6e6e6; margin: 0; }
    .ead-sector { font-size: 11.5px; color: #9090a8; margin: 0 0 4px 0; }

    .ead-nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 10px 0; }
    .ead-nav a {
        font-size: 10.5px; color: #a0b8ff; text-decoration: none;
        padding: 3px 10px; background: #1e1e2e; border-radius: 12px;
        border: 1px solid #2a2a3e;
    }
    .ead-nav a:hover { border-color: #4a9eff; }
    .ead-section-label {
        font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
        color: #6a6a88; text-transform: uppercase; margin: 6px 0 4px 0;
        scroll-margin-top: 10px;
    }
    div[data-testid="stButton"] button {
        font-size: 11px !important; padding: 2px 4px !important; min-height: 0 !important;
    }
    .ead-desc { font-size: 12px; line-height: 1.45; color: #c0c0d0; margin: 0 0 8px 0; }

    [data-testid="stExpander"] summary { font-size: 11.5px !important; }
    [data-testid="stExpander"] p { font-size: 12px !important; }
    .stTextInput label { font-size: 12px !important; }
    .stTextInput input { font-size: 12px !important; padding: 4px 8px !important; }
    .stCaption, [data-testid="stCaptionContainer"] { font-size: 10.5px !important; }

    .ead-card {
        background: #1e1e2e;
        border-radius: 8px;
        padding: 8px 10px;
        margin-bottom: 8px;
    }
    .ead-card h4 {
        color: #e6e6e6;
        margin: 0 0 4px 0;
        font-size: 12px;
        border-bottom: 1px solid #2a2a3e;
        padding-bottom: 4px;
    }
    table.ead-table { width: 100%; border-collapse: collapse; font-size: 11px; }
    table.ead-table th {
        text-align: left; color: #9090a8; font-weight: 500;
        border-bottom: 1px solid #2a2a3e; padding: 2px 4px;
    }
    table.ead-table td { padding: 2px 4px; color: #d0d0e0; line-height: 1.5; }
    table.ead-table td.label { color: #9090a8; }
    table.ead-table td.value { text-align: right; font-weight: 600; color: #e6e6e6; white-space: nowrap; }
    table.ead-table tr:nth-child(even) { background: rgba(255,255,255,0.03); }
    table.ead-table td.num { text-align: right; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

CHART_FONT = dict(size=10, color="#c0c0d0")

# ── Helpers ──────────────────────────────────────────────────────────────────


def esc(x) -> str:
    return _html.escape(str(x)) if x is not None else ""


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
    if kind == "usd2":
        return f"${x:,.2f}"
    if kind == "num0":
        return f"{x:,.0f}"
    return f"{x:.2f}"  # num2


def render_kv_card(title: str, rows_: list):
    """rows_: list of (label, value_str, color_or_None)."""
    parts = [f'<div class="ead-card"><h4>{esc(title)}</h4><table class="ead-table">']
    for label, value, color in rows_:
        style = f' style="color:{color};"' if color else ""
        parts.append(f'<tr><td class="label">{esc(label)}</td><td class="value"{style}>{esc(value)}</td></tr>')
    parts.append("</table></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ── Data fetch ───────────────────────────────────────────────────────────────


@st.cache_data(ttl=300)
def fetch_ticker_bundle(ticker: str) -> dict:
    """Single entry point for all data on one ticker. Never raises — every
    field defaults to an empty/None sentinel on failure."""
    out = {
        "ticker": ticker, "info": {}, "hist": pd.DataFrame(),
        "fin": pd.DataFrame(), "bal": pd.DataFrame(), "cf": pd.DataFrame(),
        "qcf": pd.DataFrame(), "earnings": None, "holders": pd.DataFrame(),
        "valid": False,
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

    try:
        ih = t.institutional_holders
        out["holders"] = ih if ih is not None and not ih.empty else pd.DataFrame()
    except Exception:
        out["holders"] = pd.DataFrame()

    out["valid"] = (
        (not out["hist"].empty)
        or bool(out["info"].get("longBusinessSummary"))
        or bool(out["info"].get("shortName"))
    )
    return out


def _denorm_tz(close: pd.Series) -> pd.Series:
    if close.index.tz is not None:
        close = close.copy()
        close.index = close.index.tz_localize(None)
    return close


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
    close = _denorm_tz(close)

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


def render_earnings_card(df: pd.DataFrame):
    if df.empty:
        st.markdown('<div class="ead-card"><h4>Last 4 Earnings</h4>', unsafe_allow_html=True)
        st.info("No earnings history available for this ticker.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    parts = [
        '<div class="ead-card"><h4>Last 4 Earnings</h4><table class="ead-table"><tr>'
        "<th>Date</th><th>EPS Est.</th><th>Reported EPS</th><th>Surprise</th><th>Result</th></tr>"
    ]
    for _, r in df.iterrows():
        surprise = r.get("Surprise (%)")
        surprise_str = f"{surprise:+.2f}%" if pd.notna(surprise) else "N/A"
        surprise_color = POS_COLOR if pd.notna(surprise) and surprise >= 0 else (NEG_COLOR if pd.notna(surprise) else None)
        bm = r["Beat/Miss"]
        bm_color = POS_COLOR if bm == "Beat" else (NEG_COLOR if bm == "Miss" else None)
        est_str = f'{r["EPS Estimate"]:.2f}' if pd.notna(r["EPS Estimate"]) else "N/A"
        rep_str = f'{r["Reported EPS"]:.2f}' if pd.notna(r["Reported EPS"]) else "N/A"
        parts.append(
            f'<tr><td>{esc(r["Earnings Date"])}</td>'
            f'<td class="num">{esc(est_str)}</td>'
            f'<td class="num">{esc(rep_str)}</td>'
            f'<td class="num" style="color:{surprise_color or "#d0d0e0"};">{esc(surprise_str)}</td>'
            f'<td class="num" style="color:{bm_color or "#d0d0e0"};font-weight:600;">{esc(bm)}</td></tr>'
        )
    parts.append("</table></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def build_holders_table(holders: pd.DataFrame) -> pd.DataFrame:
    if holders is None or holders.empty:
        return pd.DataFrame()
    keep = [c for c in ["Holder", "pctHeld"] if c in holders.columns]
    if "Holder" not in keep or "pctHeld" not in keep:
        return pd.DataFrame()
    return holders[keep].head(8).reset_index(drop=True)


def render_holders_card(df: pd.DataFrame):
    if df.empty:
        st.markdown('<div class="ead-card"><h4>Top Institutional Holders</h4>', unsafe_allow_html=True)
        st.info("No institutional holder data available for this ticker.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    parts = ['<div class="ead-card"><h4>Top Institutional Holders</h4><table class="ead-table"><tr><th>Holder</th><th>% Out</th></tr>']
    for _, r in df.iterrows():
        pct = r["pctHeld"]
        pct_str = fmt(float(pct), "pct") if pd.notna(pct) else "N/A"
        parts.append(f'<tr><td>{esc(r["Holder"])}</td><td class="num">{esc(pct_str)}</td></tr>')
    parts.append("</table></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


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
    f["current_price"] = safe_get(info, "currentPrice")

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
        title=dict(text=title, font=dict(size=12, color="#e6e6e6")),
        height=230,
        font=CHART_FONT,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        yaxis=dict(gridcolor=GRID_COLOR, tickformat="$,.0f", tickfont=dict(size=9)),
        xaxis=dict(tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=9)),
    )
    return fig


def price_by_year(hist: pd.DataFrame, years: list) -> list:
    """Last available close in each calendar year (NaN if the ticker didn't trade that year)."""
    if hist is None or hist.empty:
        return [np.nan] * len(years)
    close = _denorm_tz(hist["Close"].dropna())
    out = []
    for y in years:
        try:
            yi = int(y)
        except (TypeError, ValueError):
            out.append(np.nan)
            continue
        mask = close.index.year == yi
        out.append(float(close[mask].iloc[-1]) if mask.any() else np.nan)
    return out


def cashflow_vs_price_chart(annual_cf: pd.DataFrame, hist: pd.DataFrame, ticker: str) -> go.Figure:
    years = annual_cf["Period"].tolist()
    prices = price_by_year(hist, years)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Free Cash Flow", x=years, y=annual_cf["Free Cash Flow"], marker_color=CF_COLORS["Free Cash Flow"], yaxis="y"))
    fig.add_trace(go.Scatter(name="Stock Price", x=years, y=prices, mode="lines+markers", line=dict(color="#4a9eff", width=2), yaxis="y2"))
    fig.update_layout(
        title=dict(text=f"{ticker} — Free Cash Flow vs. Stock Price", font=dict(size=12, color="#e6e6e6")),
        height=260,
        font=CHART_FONT,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(title=dict(text="Year", font=dict(size=9)), tickfont=dict(size=9)),
        yaxis=dict(title=dict(text="Free Cash Flow ($)", font=dict(size=9)), gridcolor=GRID_COLOR, tickformat="$,.0f", tickfont=dict(size=9)),
        yaxis2=dict(title=dict(text="Stock Price ($)", font=dict(size=9)), overlaying="y", side="right", showgrid=False, tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(size=9)),
    )
    return fig


# ── Page ─────────────────────────────────────────────────────────────────────

st.markdown('<div class="ead-title">🔍 Equity Analysis Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="ead-subtitle">Look up any ticker for a full view: overview, fundamentals, '
    'ownership, and cash-flow trends. Research tool only — not investment advice.</div>',
    unsafe_allow_html=True,
)

QUICK_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "SPY"]

# Query-param <-> session_state sync: lets the ticker survive a refresh, browser
# back/forward, or a pasted link (?ticker=MSFT), while local typing/clicks still win.
qp_ticker = (st.query_params.get("ticker") or "").strip().upper()
if "eq_ticker" not in st.session_state:
    st.session_state["eq_ticker"] = qp_ticker or "AAPL"
elif qp_ticker and qp_ticker != st.session_state["eq_ticker"]:
    st.session_state["eq_ticker"] = qp_ticker

search_col, btn_col = st.columns([1, 3], gap="small")
with search_col:
    ticker_input = st.text_input(
        "Ticker", value=st.session_state["eq_ticker"], help="Type a symbol and press Enter",
    ).strip().upper()
    if ticker_input:
        st.session_state["eq_ticker"] = ticker_input

with btn_col:
    qcols = st.columns(len(QUICK_TICKERS), gap="small")
    for qc, qt in zip(qcols, QUICK_TICKERS):
        with qc:
            if st.button(qt, key=f"quick_{qt}", width="stretch"):
                st.session_state["eq_ticker"] = qt
                st.rerun()

ticker = st.session_state["eq_ticker"]

if not ticker:
    st.info("Enter a ticker to begin.")
    st.stop()

if st.query_params.get("ticker") != ticker:
    st.query_params["ticker"] = ticker

st.markdown(
    '<div class="ead-nav">'
    '<a href="#ead-overview">Overview</a>'
    '<a href="#ead-returns">Returns &amp; Ownership</a>'
    '<a href="#ead-earnings">Earnings</a>'
    '<a href="#ead-cashflow">Cash Flow</a>'
    "</div>",
    unsafe_allow_html=True,
)

with st.spinner(f"Loading {ticker}…"):
    bundle = fetch_ticker_bundle(ticker)

if not bundle["valid"]:
    st.error(f"No data found for '{ticker}'. Check the symbol and try again.")
    st.stop()

info, hist = bundle["info"], bundle["hist"]
fin, bal, cf, qcf = bundle["fin"], bundle["bal"], bundle["cf"], bundle["qcf"]
fnd = compute_fundamentals(info, fin, bal)

# ── Header: name / sector / description ─────────────────────────────────────
name = info.get("shortName") or info.get("longName") or ticker
sector = info.get("sector") or "N/A"
industry = info.get("industry") or "N/A"
st.markdown(f'<div id="ead-overview" class="ead-company">{esc(name)} ({esc(ticker)})</div>', unsafe_allow_html=True)
st.markdown(f'<div class="ead-sector">{esc(sector)} · {esc(industry)}</div>', unsafe_allow_html=True)

summary = info.get("longBusinessSummary")
if summary:
    if len(summary) > 320:
        st.markdown(f'<div class="ead-desc">{esc(summary[:320].rsplit(" ", 1)[0])}…</div>', unsafe_allow_html=True)
        with st.expander("Read full description"):
            st.markdown(f'<div class="ead-desc">{esc(summary)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ead-desc">{esc(summary)}</div>', unsafe_allow_html=True)
else:
    st.info("No company description available.")

st.markdown('<div class="ead-section-label">Fundamentals</div>', unsafe_allow_html=True)

# ── Row 1: General Info | Valuation & Profitability | Liquidity, Solvency & Dividends
r1c1, r1c2, r1c3 = st.columns(3, gap="small")

with r1c1:
    render_kv_card("General Information", [
        ("Current Price", fmt(fnd["current_price"], "usd2"), None),
        ("Market Cap", fmt(fnd["market_cap"], "usd"), None),
        ("Trailing P/E", fmt(fnd["trailing_pe"]), None),
        ("Forward P/E", fmt(fnd["forward_pe"]), None),
        ("Beta", fmt(fnd["beta"]), None),
        ("Sector", sector, None),
        ("Industry", industry, None),
    ])

with r1c2:
    render_kv_card("Valuation & Profitability", [
        ("P/S Ratio", fmt(fnd["ps"]), None),
        ("P/B Ratio", fmt(fnd["pb"]), None),
        ("Revenue", fmt(fnd["revenue"], "usd"), None),
        ("Profit Margin", fmt(fnd["profit_margin"], "pct"), None),
        ("Operating Margin", fmt(fnd["operating_margin"], "pct"), None),
        ("Return on Equity", fmt(fnd["roe"], "pct"), None),
        ("Return on Assets", fmt(fnd["roa"], "pct"), None),
    ])

with r1c3:
    div_rows = (
        [("Dividend Payout Ratio", fmt(fnd["payout_ratio"], "pct"), None),
         ("Retention Rate", fmt(fnd["retention_rate"], "pct"), None)]
        if fnd["has_dividend"] else [("Dividend", "No dividend", None)]
    )
    render_kv_card("Liquidity, Solvency & Dividends", [
        ("Total Cash", fmt(fnd["total_cash"], "usd"), None),
        ("Total Debt", fmt(fnd["total_debt"], "usd"), None),
        ("Debt/Equity", fmt(fnd["debt_to_equity"]), None),
        ("Current Ratio", fmt(fnd["current_ratio"]), None),
        ("Quick Ratio", fmt(fnd["quick_ratio"]), None),
        ("Interest Coverage (DSR proxy)", fmt(fnd["interest_coverage"]), None),
        *div_rows,
    ])
    st.caption(
        "yfinance doesn't expose a principal-repayment schedule, so a textbook Debt "
        "Service Ratio isn't derivable — Interest Coverage (EBITDA / Interest Expense) "
        "is shown instead as the closest available proxy."
    )

st.markdown('<div id="ead-returns" class="ead-section-label">Returns &amp; Ownership</div>', unsafe_allow_html=True)

# ── Row 2: Short Interest | Stock Returns | Top Institutional Holders ───────
r2c1, r2c2, r2c3 = st.columns(3, gap="small")

with r2c1:
    render_kv_card("Short Interest", [
        ("Short % of Float", fmt(fnd["short_pct_float"], "pct"), None),
        ("Short Ratio (days to cover)", fmt(fnd["short_ratio"]), None),
        ("Shares Short", fmt(fnd["shares_short"], "num0"), None),
    ])

with r2c2:
    rets = trailing_returns(hist)
    ret_rows = []
    for label in ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y"]:
        val = rets.get(label)
        color = None if val is None else (POS_COLOR if val >= 0 else NEG_COLOR)
        ret_rows.append((label, fmt(val, "pct_signed"), color))
    render_kv_card("Stock Returns", ret_rows)

with r2c3:
    holders_df = build_holders_table(bundle["holders"])
    render_holders_card(holders_df)

# ── Row 3: Last 4 Earnings (full width) ──────────────────────────────────────
st.markdown('<div id="ead-earnings" class="ead-section-label">Earnings</div>', unsafe_allow_html=True)
eq_table = build_earnings_table(bundle["earnings"])
render_earnings_card(eq_table)

# ── Row 4: Cash Flow vs Stock Price ──────────────────────────────────────────
st.markdown('<div id="ead-cashflow" class="ead-section-label">Cash Flow</div>', unsafe_allow_html=True)
annual_cf = build_cashflow_frame(cf, quarterly=False, n_periods=4)
if annual_cf.empty:
    st.info("Annual cash flow data unavailable for this ticker.")
else:
    st.plotly_chart(cashflow_vs_price_chart(annual_cf, hist, ticker), width="stretch")

# ── Row 5: Annual + Quarterly Cash Flow Breakdown ────────────────────────────
r5c1, r5c2 = st.columns(2, gap="small")
with r5c1:
    if annual_cf.empty:
        st.info("Annual cash flow breakdown unavailable for this ticker.")
    else:
        st.plotly_chart(cashflow_chart(annual_cf, "Annual Cash Flow Breakdown"), width="stretch")

with r5c2:
    quarterly_cf = build_cashflow_frame(qcf, quarterly=True, n_periods=5)
    if quarterly_cf.empty:
        st.info("Quarterly cash flow breakdown unavailable for this ticker.")
    else:
        st.plotly_chart(cashflow_chart(quarterly_cf, "Quarterly Cash Flow Breakdown"), width="stretch")
