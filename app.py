import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 0.4rem; padding-bottom: 0rem; max-width: 100%; }
    [data-testid="stMetricDelta"] svg { display: none; }
    div[data-testid="metric-container"] { padding: 2px 0 4px 0; }
    .stRadio > div { gap: 2px; }
    .stRadio [data-testid="stMarkdownContainer"] p { font-size: 0.7rem; }
    h3 { margin-top: 0; margin-bottom: 2px; font-size: 0.78rem; color: #aaa;
         text-transform: uppercase; letter-spacing: 0.05em; }
    .section-lbl { font-size: 0.68rem; color: #888; font-weight: 700;
                   text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 4px; }
    .tag-green { background:#0d3d27; color:#00c896; border-radius:4px;
                 padding:1px 7px; font-size:0.72rem; font-weight:700; }
    .tag-red   { background:#3d0d0d; color:#ff4b4b; border-radius:4px;
                 padding:1px 7px; font-size:0.72rem; font-weight:700; }
    .tag-grey  { background:#2a2a3e; color:#aaa; border-radius:4px;
                 padding:1px 7px; font-size:0.72rem; }
    .cal-row   { font-size:0.75rem; padding:2px 0; border-bottom:1px solid #2a2a3e; }
    .cal-date  { color:#aaa; display:inline-block; width:72px; }
    .cal-event { color:#e0e0e0; }
</style>
""", unsafe_allow_html=True)

# ── Static macro constants (update manually each month) ───────────────────────
SHILLER_CAPE = 38.0
ISM_MFG = 49.0
FED_RATE = "4.25–4.50%"

FOMC_DATES = [
    ("Jul 28–29", "Hold expected"),
    ("Sep 15–16", "Cut priced in"),
    ("Oct 27–28", "—"),
    ("Dec 9–10",  "—"),
]
KEY_RELEASES = [
    ("NFP",         "Jul 2"),
    ("CPI",         "Jul 14"),
    ("FOMC mins.",  "Jul 8"),
    ("NFP",         "Aug 7"),
    ("CPI",         "Aug 18"),
]

# ── Tickers ───────────────────────────────────────────────────────────────────
STRIP_TICKERS = [
    ("S&P 500",    "^GSPC",    None),
    ("VIX",        "^VIX",     None),
    ("10Y Yield",  "^TNX",     "%"),
    ("DXY",        "DX-Y.NYB", None),
    ("Gold",       "GC=F",     None),
    ("Dr. Copper", "HG=F",     None),
]
CHART_TICKERS = [
    ("S&P 500",   "^GSPC"),
    ("Gold",      "GC=F"),
    ("Dr. Copper","HG=F"),
    ("Oil (WTI)", "CL=F"),
]
GLOBAL_TICKERS = [
    ("Nikkei 225",  "^N225"),
    ("DAX",         "^GDAXI"),
    ("FTSE 100",    "^FTSE"),
    ("Shanghai",    "000001.SS"),
    ("Hang Seng",   "^HSI"),
    ("Nifty 50",    "^NSEI"),
]
CHART_PERIODS = {"1D": "1d", "1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}

COT_MARKETS = {
    "S&P 500":  "S&P 500",
    "Gold":     "GOLD",
    "Copper":   "COPPER",
    "Crude Oil":"CRUDE OIL",
    "10Y TSY":  "10-YEAR T-NOTE",
    "EUR/USD":  "EURO FX",
}

# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_strip() -> list:
    rows = []
    for name, sym, suffix in STRIP_TICKERS:
        try:
            hist = yf.Ticker(sym).history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                raise ValueError("no data")
            p = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            pct = (p / prev - 1) * 100
            rows.append({"name": name, "price": p, "pct": pct, "suffix": suffix})
        except Exception:
            rows.append({"name": name, "price": None, "pct": None, "suffix": suffix})
    return rows


@st.cache_data(ttl=300)
def fetch_chart_data(symbol: str, period: str) -> pd.DataFrame:
    interval = "5m" if period == "1d" else "1d"
    try:
        return yf.Ticker(symbol).history(period=period, interval=interval)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_spot(symbol: str):
    try:
        h = yf.Ticker(symbol).history(period="2d", interval="1d")
        return float(h["Close"].iloc[-1]) if not h.empty else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_yield_curve() -> dict:
    try:
        import pandas_datareader.data as web
        series = ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"]
        end = datetime.today()
        start = end - timedelta(days=10)
        df = web.DataReader(series, "fred", start, end)
        latest = df.dropna(how="all").iloc[-1]
        return {s: (float(latest[s]) if pd.notna(latest[s]) else None) for s in series}
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def fetch_fred(series: str):
    try:
        import pandas_datareader.data as web
        end = datetime.today()
        start = end - timedelta(days=30)
        df = web.DataReader(series, "fred", start, end)
        val = df.dropna().iloc[-1, 0]
        return float(val)
    except Exception:
        return None


@st.cache_data(ttl=86400)
def fetch_cot() -> dict:
    results = {}
    try:
        url = "https://publicreporting.cftc.gov/resource/jun7-nznm.json"
        r = requests.get(url, params={"$limit": 500, "$order": "report_date_as_yyyy_mm_dd DESC"},
                         timeout=12)
        r.raise_for_status()
        data = r.json()
        seen = set()
        for row in data:
            mkt = row.get("market_and_exchange_names", "").upper()
            for label, pattern in COT_MARKETS.items():
                if pattern.upper() in mkt and label not in seen:
                    try:
                        longs = float(row.get("noncomm_positions_long_all", 0))
                        shorts = float(row.get("noncomm_positions_short_all", 0))
                        results[label] = {
                            "net": longs - shorts,
                            "longs": longs,
                            "shorts": shorts,
                            "date": str(row.get("report_date_as_yyyy_mm_dd", ""))[:10],
                        }
                        seen.add(label)
                    except Exception:
                        pass
    except Exception:
        pass
    return results


@st.cache_data(ttl=300)
def fetch_global() -> list:
    rows = []
    for name, sym in GLOBAL_TICKERS:
        try:
            hist = yf.Ticker(sym).history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                raise ValueError
            p = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            rows.append({"name": name, "price": p, "pct": (p / prev - 1) * 100})
        except Exception:
            rows.append({"name": name, "price": None, "pct": None})
    return rows


# ── Helpers ───────────────────────────────────────────────────────────────────
def _fmt(price, suffix=None) -> str:
    if price is None:
        return "—"
    if suffix == "%":
        return f"{price:.3f}%"
    if price > 10000:
        return f"{price:,.0f}"
    if price > 100:
        return f"{price:,.2f}"
    if price > 10:
        return f"{price:.3f}"
    return f"{price:.4f}"


def _pct_str(pct) -> str:
    if pct is None:
        return "—"
    arrow = "▲" if pct >= 0 else "▼"
    return f"{arrow} {abs(pct):.2f}%"


def _mini_chart(name: str, symbol: str, period: str, height: int = 155) -> None:
    df = fetch_chart_data(symbol, period)
    if df.empty:
        st.caption(f"No data for {name}")
        return
    close = df["Close"].squeeze()
    base = close.iloc[0]
    is_up = close.iloc[-1] >= base
    color = "#00c896" if is_up else "#ff4b4b"
    fill = "rgba(0,200,150,0.08)" if is_up else "rgba(255,75,75,0.08)"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=close.index, y=close.values, mode="lines",
        line=dict(color=color, width=1.5), fill="tozeroy", fillcolor=fill,
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=height,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="#1e1e2e", tickfont=dict(size=9), zeroline=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _gauge_bar(label: str, val: float | None, lo: float, hi: float,
               warn_lo=None, warn_hi=None,
               fmt: str = "{:.1f}", suffix: str = "") -> None:
    """Compact horizontal bar indicator."""
    if val is None:
        st.markdown(f"<div style='font-size:0.75rem;color:#888;padding:2px 0'>{label}: —</div>",
                    unsafe_allow_html=True)
        return
    frac = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    if warn_hi is not None and val >= warn_hi:
        bar_color = "#ff4b4b"
    elif warn_lo is not None and val <= warn_lo:
        bar_color = "#ff4b4b"
    else:
        bar_color = "#1565c0"
    val_str = fmt.format(val) + suffix
    st.markdown(f"""
<div style="margin-bottom:7px">
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#aaa;margin-bottom:2px">
    <span>{label}</span><span style="color:#e0e0e0;font-weight:600">{val_str}</span>
  </div>
  <div style="background:#1e1e2e;border-radius:3px;height:5px">
    <div style="background:{bar_color};width:{frac*100:.1f}%;height:5px;border-radius:3px"></div>
  </div>
</div>""", unsafe_allow_html=True)


# ── Clocks ────────────────────────────────────────────────────────────────────
def _clocks() -> str:
    try:
        from zoneinfo import ZoneInfo
        now_et = datetime.now(ZoneInfo("America/New_York"))
        now_local = datetime.now(ZoneInfo("Asia/Beirut"))  # local tz; adjust if needed
    except ImportError:
        now_et = datetime.utcnow() - timedelta(hours=4)
        now_local = datetime.utcnow() + timedelta(hours=3)
    # NYSE open 09:30–16:00 ET, Mon–Fri
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    h, m = now_et.hour, now_et.minute
    mins_et = h * 60 + m
    if weekday >= 5:
        status = "🔴 Closed (weekend)"
    elif mins_et < 9 * 60 + 30:
        td = 9 * 60 + 30 - mins_et
        status = f"🟡 Pre-market · opens in {td // 60}h {td % 60}m"
    elif mins_et <= 16 * 60:
        td = 16 * 60 - mins_et
        status = f"🟢 Open · closes in {td // 60}h {td % 60}m"
    else:
        status = "🔴 After-hours"
    nyse_str = now_et.strftime("%H:%M ET")
    local_str = now_local.strftime("%H:%M Local")
    return f"**{nyse_str}** · {local_str} · {status}"


# ═══════════════════════════════ LAYOUT ══════════════════════════════════════
# ── Header ────────────────────────────────────────────────────────────────────
hdr_l, hdr_m, hdr_r = st.columns([2, 3, 1])
with hdr_l:
    st.markdown("### 📈 Market Dashboard")
with hdr_m:
    st.markdown(_clocks())
with hdr_r:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── Ticker strip ──────────────────────────────────────────────────────────────
strip_data = fetch_strip()
strip_cols = st.columns(6)
for i, row in enumerate(strip_data):
    with strip_cols[i]:
        p = row["price"]
        pct = row["pct"]
        pct_color = "#00c896" if (pct or 0) >= 0 else "#ff4b4b"
        price_str = _fmt(p, row["suffix"])
        pct_str = _pct_str(pct)
        st.markdown(f"""
<div style="text-align:center;background:#1a1a2e;border-radius:6px;padding:6px 4px">
  <div style="font-size:0.65rem;color:#888;font-weight:700;text-transform:uppercase">{row['name']}</div>
  <div style="font-size:1.0rem;font-weight:700;color:#e0e0e0">{price_str}</div>
  <div style="font-size:0.72rem;color:{pct_color};font-weight:600">{pct_str}</div>
</div>""", unsafe_allow_html=True)

st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── Main row: charts | yield curve | risk panel ───────────────────────────────
col_charts, col_yield, col_risk = st.columns([2.4, 1.0, 1.0])

with col_charts:
    st.markdown('<div class="section-lbl">Price Charts</div>', unsafe_allow_html=True)
    # Period selector — one for all 4 charts
    period_key = st.radio(
        "period", list(CHART_PERIODS.keys()), index=0,
        horizontal=True, label_visibility="collapsed", key="chart_period"
    )
    period = CHART_PERIODS[period_key]
    row1 = st.columns(2)
    row2 = st.columns(2)
    grid = [row1[0], row1[1], row2[0], row2[1]]
    for i, (name, sym) in enumerate(CHART_TICKERS):
        with grid[i]:
            # Chart label with live price
            spot = next((r["price"] for r in strip_data if r["name"] == name), None)
            pct_val = next((r["pct"] for r in strip_data if r["name"] == name), None)
            price_disp = _fmt(spot)
            pct_disp = _pct_str(pct_val)
            pct_color = "#00c896" if (pct_val or 0) >= 0 else "#ff4b4b"
            st.markdown(
                f"<div style='font-size:0.72rem;font-weight:700;color:#ccc'>{name} "
                f"<span style='color:#aaa;font-weight:400'>{price_disp}</span> "
                f"<span style='color:{pct_color};font-size:0.68rem'>{pct_disp}</span></div>",
                unsafe_allow_html=True,
            )
            _mini_chart(name, sym, period, height=148)

with col_yield:
    st.markdown('<div class="section-lbl">Yield Curve</div>', unsafe_allow_html=True)
    yc = fetch_yield_curve()
    maturities = ["3M", "2Y", "5Y", "10Y", "30Y"]
    series_keys = ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30"]
    yc_vals = [yc.get(k) for k in series_keys]
    if any(v is not None for v in yc_vals):
        xs = [m for m, v in zip(maturities, yc_vals) if v is not None]
        ys = [v for v in yc_vals if v is not None]
        is_inverted = ys[0] > ys[-1] if len(ys) >= 2 else False
        yc_color = "#ff4b4b" if is_inverted else "#1565c0"
        fig_yc = go.Figure()
        fig_yc.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines+markers",
            line=dict(color=yc_color, width=2),
            marker=dict(size=5, color=yc_color),
        ))
        fig_yc.update_layout(
            height=175, margin=dict(l=0, r=0, t=4, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, tickfont=dict(size=9)),
            yaxis=dict(showgrid=True, gridcolor="#1e1e2e", tickfont=dict(size=9),
                       ticksuffix="%"),
            showlegend=False,
        )
        st.plotly_chart(fig_yc, use_container_width=True, config={"displayModeBar": False})
        # 2Y-10Y spread
        s2 = yc.get("DGS2")
        s10 = yc.get("DGS10")
        if s2 is not None and s10 is not None:
            spread = s10 - s2
            sprd_color = "#ff4b4b" if spread < 0 else "#00c896"
            inv_lbl = "INVERTED" if spread < 0 else "Normal"
            st.markdown(
                f"<div style='font-size:0.72rem;margin-bottom:4px'>"
                f"2Y–10Y spread: <span style='color:{sprd_color};font-weight:700'>"
                f"{spread:+.2f}% ({inv_lbl})</span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.warning("Yield curve data unavailable")

    # TIPS real yield + breakeven
    tips = fetch_fred("DFII10")
    bkev = fetch_fred("T10YIE")
    st.markdown('<div class="section-lbl" style="margin-top:6px">Real Rates</div>',
                unsafe_allow_html=True)
    _gauge_bar("TIPS 10Y Real Yield", tips, -2.0, 4.0,
               warn_lo=-0.5, fmt="{:.2f}", suffix="%")
    _gauge_bar("Breakeven Inflation", bkev, 0.5, 4.0,
               warn_hi=3.5, fmt="{:.2f}", suffix="%")

with col_risk:
    st.markdown('<div class="section-lbl">Risk & Valuation</div>', unsafe_allow_html=True)

    # VIX
    vix_val = next((r["price"] for r in strip_data if r["name"] == "VIX"), None)
    _gauge_bar("VIX", vix_val, 10, 50, warn_hi=25, fmt="{:.1f}")

    # Shiller CAPE
    _gauge_bar("Shiller CAPE", SHILLER_CAPE, 10, 50, warn_hi=30, fmt="{:.1f}")

    # Fed Funds
    st.markdown(
        f"<div style='margin-bottom:7px'><div style='font-size:0.72rem;color:#aaa'>Fed Funds Rate</div>"
        f"<div style='font-size:0.85rem;font-weight:700;color:#e0e0e0'>{FED_RATE}</div></div>",
        unsafe_allow_html=True,
    )

    # Cu/Au Ratio
    cu_price = next((r["price"] for r in strip_data if r["name"] == "Dr. Copper"), None)
    au_price = next((r["price"] for r in strip_data if r["name"] == "Gold"), None)
    cu_au = None
    if cu_price and au_price and au_price > 0:
        # Copper in $/lb (HG=F is $/lb, but quoted in cents on exchange), Gold in $/oz
        # HG=F Close is already in USD/lb on yfinance
        cu_au = cu_price / au_price * 1000  # express as ratio × 1000 for readability
    _gauge_bar("Cu/Au Ratio (×1000)", cu_au, 0.5, 2.5,
               warn_lo=0.8, warn_hi=2.2, fmt="{:.3f}")

    # ISM Manufacturing
    _gauge_bar("ISM Mfg PMI", ISM_MFG, 35, 65,
               warn_lo=45, fmt="{:.1f}")
    st.markdown(
        "<div style='font-size:0.65rem;color:#555;margin-top:-4px'>50 = neutral · "
        "<50 = contraction · >50 = expansion</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Bottom row: COT | Global markets | Calendar ───────────────────────────────
col_cot, col_global, col_cal = st.columns([1.4, 1.0, 1.0])

with col_cot:
    st.markdown('<div class="section-lbl">CFTC COT — Net Speculator Position</div>',
                unsafe_allow_html=True)
    cot = fetch_cot()
    if cot:
        labels = list(cot.keys())
        nets = [cot[k]["net"] for k in labels]
        colors = ["#00c896" if n >= 0 else "#ff4b4b" for n in nets]
        nets_k = [n / 1000 for n in nets]
        fig_cot = go.Figure(go.Bar(
            y=labels, x=nets_k,
            orientation="h",
            marker_color=colors,
            text=[f"{n:+.0f}K" for n in nets_k],
            textposition="outside",
            textfont=dict(size=9),
        ))
        fig_cot.update_layout(
            height=175, margin=dict(l=0, r=40, t=4, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=True, gridcolor="#1e1e2e", tickfont=dict(size=9),
                       ticksuffix="K", zeroline=True, zerolinecolor="#444"),
            yaxis=dict(tickfont=dict(size=9)),
            showlegend=False,
        )
        st.plotly_chart(fig_cot, use_container_width=True, config={"displayModeBar": False})
        dates = set(v["date"] for v in cot.values() if v["date"])
        if dates:
            st.caption(f"Latest COT report: {max(dates)}")
    else:
        st.info("COT data unavailable (CFTC API)")

with col_global:
    st.markdown('<div class="section-lbl">Global Markets</div>', unsafe_allow_html=True)
    global_data = fetch_global()
    for row in global_data:
        pct = row["pct"]
        pct_color = "#00c896" if (pct or 0) >= 0 else "#ff4b4b"
        price_str = _fmt(row["price"])
        pct_str = _pct_str(pct)
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:0.75rem;padding:2px 0;border-bottom:1px solid #1e1e2e'>"
            f"<span style='color:#ccc'>{row['name']}</span>"
            f"<span style='color:#888'>{price_str}</span>"
            f"<span style='color:{pct_color};font-weight:600'>{pct_str}</span></div>",
            unsafe_allow_html=True,
        )

with col_cal:
    st.markdown('<div class="section-lbl">Fed & Macro Calendar</div>', unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.68rem;color:#888;margin-bottom:3px'>FOMC 2026</div>",
                unsafe_allow_html=True)
    for date, note in FOMC_DATES:
        tag_cls = "tag-grey" if note == "—" else ("tag-red" if "Cut" in note else "tag-grey")
        st.markdown(
            f"<div class='cal-row'><span class='cal-date'>{date}</span>"
            f"<span class='tag-grey'>{note}</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='font-size:0.68rem;color:#888;margin:6px 0 3px'>Key Releases</div>",
                unsafe_allow_html=True)
    for event, date in KEY_RELEASES:
        st.markdown(
            f"<div class='cal-row'><span class='cal-date'>{date}</span>"
            f"<span class='cal-event'>{event}</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='font-size:0.68rem;color:#888;margin-top:4px'>"
                "COT reports: every Friday after 15:30 ET</div>",
                unsafe_allow_html=True)

st.markdown(
    "<div style='font-size:0.6rem;color:#444;margin-top:6px'>"
    "Data: Yahoo Finance (prices, delayed ~15min) · FRED (yields) · "
    "CFTC (COT, weekly) · For informational purposes only.</div>",
    unsafe_allow_html=True,
)
