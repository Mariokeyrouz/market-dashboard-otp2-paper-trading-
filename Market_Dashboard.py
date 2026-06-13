import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 16px;
        margin: 4px;
    }
    .positive { color: #00c896; }
    .negative { color: #ff4b4b; }
    [data-testid="stMetricDelta"] svg { display: none; }
</style>
""", unsafe_allow_html=True)

TICKERS = {
    "S&P 500":        "^GSPC",
    "Nasdaq":         "^IXIC",
    "Dow Jones":      "^DJI",
    "Russell 2000":   "^RUT",
    "VIX":            "^VIX",
    "10Y Treasury":   "^TNX",
    "DXY (Dollar)":   "DX-Y.NYB",
    "Gold":           "GC=F",
    "Oil (WTI)":      "CL=F",
    "Silver":         "SI=F",
}

PERIODS = {"1D": "1d", "5D": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "YTD": "ytd"}

@st.cache_data(ttl=300)
def fetch_snapshots(tickers: dict) -> pd.DataFrame:
    rows = []
    for name, symbol in tickers.items():
        try:
            hist = yf.Ticker(symbol).history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                raise ValueError("insufficient data")
            price = float(hist["Close"].iloc[-1])
            prev  = float(hist["Close"].iloc[-2])
            chg   = price - prev
            pct   = (chg / prev) * 100 if prev else 0
            rows.append({"Name": name, "Symbol": symbol, "Price": price, "Change": chg, "Pct": pct})
        except Exception:
            rows.append({"Name": name, "Symbol": symbol, "Price": None, "Change": None, "Pct": None})
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def fetch_history(symbol: str, period: str) -> pd.DataFrame:
    interval = "5m" if period == "1d" else "1d"
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    return df

def fmt_price(name: str, price: float) -> str:
    if price is None:
        return "N/A"
    if name in ("10Y Treasury",):
        return f"{price:.3f}%"
    if name == "VIX":
        return f"{price:.2f}"
    if price > 1000:
        return f"{price:,.2f}"
    return f"{price:.4f}" if price < 10 else f"{price:.2f}"

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📈 Market Dashboard")
st.caption(f"Macro Overview · Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

col_refresh, col_period = st.columns([1, 6])
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
with col_period:
    period_label = st.radio("Chart period", list(PERIODS.keys()), index=0, horizontal=True, label_visibility="collapsed")
period = PERIODS[period_label]

st.divider()

# ── Snapshot cards ─────────────────────────────────────────────────────────────
with st.spinner("Loading market data…"):
    df = fetch_snapshots(TICKERS)

cols = st.columns(5)
for i, row in df.iterrows():
    col = cols[i % 5]
    with col:
        price_str = fmt_price(row["Name"], row["Price"])
        pct = row["Pct"]
        chg = row["Change"]
        if pct is not None:
            arrow = "▲" if pct >= 0 else "▼"
            color = "positive" if pct >= 0 else "negative"
            delta_str = f"{arrow} {abs(chg):.2f}  ({abs(pct):.2f}%)"
        else:
            color = ""
            delta_str = "N/A"
        st.metric(
            label=row["Name"],
            value=price_str,
            delta=delta_str,
        )

st.divider()

# ── Charts ─────────────────────────────────────────────────────────────────────
st.subheader("Price Charts")

chart_cols = st.columns(2)
for i, row in df.iterrows():
    col = chart_cols[i % 2]
    with col:
        hist = fetch_history(row["Symbol"], period)
        if hist.empty:
            st.warning(f"No data for {row['Name']}")
            continue

        close = hist["Close"].squeeze()
        base  = close.iloc[0]
        is_up = close.iloc[-1] >= base
        color = "#00c896" if is_up else "#ff4b4b"
        fillcolor = "rgba(0,200,150,0.08)" if is_up else "rgba(255,75,75,0.08)"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=close.index,
            y=close.values,
            mode="lines",
            line=dict(color=color, width=1.8),
            fill="tozeroy",
            fillcolor=fillcolor,
            name=row["Name"],
        ))
        fig.update_layout(
            title=dict(text=row["Name"], font=dict(size=14)),
            margin=dict(l=0, r=0, t=32, b=0),
            height=220,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, showticklabels=True, tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="#2a2a3e", tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.caption("Data via Yahoo Finance · Prices delayed ~15 min · For informational purposes only.")
