"""
Portfolio Analytics
===================
Performance metrics and intra-portfolio stock correlation heatmaps
for all four active equity strategies.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Portfolio Analytics",
    page_icon="📐",
    layout="wide",
)

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .section-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #888;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ── Config ────────────────────────────────────────────────────────────────────

PORTFOLIOS = {
    "OTP2.0": {
        "ledger":    "paper_ledger.csv",
        "state":     "paper_state.json",
        "tickers":   ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"],
        "color":     "#1565c0",
        "icon":      "📊",
    },
    "OTP2.0 AMA": {
        "ledger":    "paper_ledger_AMA.csv",
        "state":     "paper_state_AMA.json",
        "tickers":   ["GE", "GS", "GOOGL", "AVGO", "IBM", "JPM", "JNJ"],
        "color":     "#0288d1",
        "icon":      "🧠",
    },
    "FMTS": {
        "ledger":    "factor_ledger.csv",
        "state":     "factor_state.json",
        "selection": "factor_selection.json",
        "color":     "#e65100",
        "icon":      "🎯",
    },
    "FMTS AMA": {
        "ledger":    "factor_ledger_AMA.csv",
        "state":     "factor_state_AMA.json",
        "selection": "factor_selection_AMA.json",
        "color":     "#f57c00",
        "icon":      "🔬",
    },
}

CORR_PERIOD = "1y"   # yfinance period for stock correlation data


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tickers_for(name, cfg):
    if "tickers" in cfg:
        return cfg["tickers"]
    sel_path = cfg.get("selection", "")
    if os.path.exists(sel_path):
        with open(sel_path) as f:
            sel = json.load(f)
        return list(sel.get("holdings", {}).keys())
    return []


def _load_ledger(path):
    if not os.path.exists(path):
        return None
    return pd.read_csv(path, parse_dates=["date"]).sort_values("date")


def _compute_metrics(ledger):
    if ledger is None or len(ledger) < 2:
        return {}

    nav   = ledger["nav"]
    rets  = ledger["daily_log_ret"].iloc[1:].dropna()
    dates = ledger["date"]

    total_ret   = (nav.iloc[-1] / nav.iloc[0] - 1) * 100
    # Days live = calendar days since inception up to TODAY (not the last ledger
    # date, which lags whenever the daily update hasn't run yet).
    n_days      = (pd.Timestamp.today().normalize() - dates.iloc[0].normalize()).days
    ann_factor  = 252 / max(len(rets), 1)
    ann_ret     = rets.mean() * 252 * 100
    ann_vol     = rets.std() * np.sqrt(252) * 100
    sharpe      = ann_ret / ann_vol if ann_vol > 0 else float("nan")

    # Sortino (downside vol only)
    neg = rets[rets < 0]
    down_vol = neg.std() * np.sqrt(252) * 100
    sortino = ann_ret / down_vol if down_vol > 0 else float("nan")

    # Max drawdown
    running_max = nav.cummax()
    dd          = (nav - running_max) / running_max * 100
    max_dd      = dd.min()

    # Win rate
    win_rate = (rets > 0).mean() * 100

    # Best / worst day
    best_day  = rets.max() * 100
    worst_day = rets.min() * 100

    # Calmar
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else float("nan")

    return {
        "NAV":          nav.iloc[-1],
        "Total Return": total_ret,
        "Ann. Return":  ann_ret,
        "Ann. Vol":     ann_vol,
        "Sharpe":       sharpe,
        "Sortino":      sortino,
        "Calmar":       calmar,
        "Max Drawdown": max_dd,
        "Win Rate":     win_rate,
        "Best Day":     best_day,
        "Worst Day":    worst_day,
        "Days Live":    n_days,
        "N Obs":        len(rets),
    }


@st.cache_data(ttl=3600)
def fetch_stock_returns(tickers, period="1y"):
    if not tickers:
        return pd.DataFrame()
    try:
        raw = yf.download(tickers, period=period, interval="1d",
                          auto_adjust=True, progress=False)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]] if len(tickers) == 1 else raw
        closes.columns = [str(c) for c in closes.columns]
        tz = closes.index
        if hasattr(tz, "tz") and tz.tz is not None:
            closes.index = closes.index.tz_localize(None)
        return closes.pct_change().dropna(how="all")
    except Exception:
        return pd.DataFrame()


def _corr_heatmap(tickers, color_hex, title):
    if not tickers:
        st.info("No holdings data available.")
        return

    with st.spinner(f"Fetching {len(tickers)} stocks ({CORR_PERIOD})…"):
        ret_df = fetch_stock_returns(tickers, CORR_PERIOD)

    # Keep only tickers that came back
    available = [t for t in tickers if t in ret_df.columns]
    if len(available) < 2:
        st.warning("Not enough price data to compute correlation.")
        return

    ret_df  = ret_df[available].dropna()
    corr    = ret_df.corr().round(2)
    labels  = list(corr.columns)
    z       = corr.values.tolist()
    n       = len(labels)

    # Build annotation text
    text = [[f"{corr.iloc[i,j]:.2f}" for j in range(n)] for i in range(n)]

    # Colour scale: white at 0, colour at 1, lighter at -1
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)
    colorscale = [
        [0.0,  f"rgb(180,210,255)"],
        [0.5,  "rgb(250,250,250)"],
        [1.0,  f"rgb({r},{g},{b})"],
    ]

    fig = ff.create_annotated_heatmap(
        z=z,
        x=labels,
        y=labels,
        annotation_text=text,
        colorscale=colorscale,
        zmin=-1, zmax=1,
        showscale=True,
    )
    fig.update_layout(
        height=max(320, 40 * n + 100),
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11),
        xaxis=dict(side="bottom"),
    )
    fig.update_traces(
        hovertemplate="<b>%{y} vs %{x}</b><br>Correlation: %{z:.3f}<extra></extra>"
    )

    st.plotly_chart(fig, width='stretch')
    st.caption(f"{len(available)} holdings · {CORR_PERIOD} daily returns · {len(ret_df)} observations")


# ── Page ──────────────────────────────────────────────────────────────────────

st.title("📐 Portfolio Analytics")
st.caption("Performance metrics and intra-portfolio stock correlations across all active equity strategies.")

col_refresh, _ = st.columns([1, 8])
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── Section 1: Performance metrics comparison ─────────────────────────────────

st.subheader("📊 Performance Metrics")

metric_rows = []
for name, cfg in PORTFOLIOS.items():
    ledger = _load_ledger(cfg["ledger"])
    m = _compute_metrics(ledger)
    if m:
        state = {}
        if os.path.exists(cfg["state"]):
            with open(cfg["state"]) as f:
                state = json.load(f)
        m["Strategy"]  = f"{cfg['icon']} {name}"
        m["Invested %"] = state.get("invested", float("nan")) * 100
        metric_rows.append(m)

if metric_rows:
    cols_order = [
        "Strategy", "NAV", "Total Return", "Ann. Return", "Ann. Vol",
        "Sharpe", "Sortino", "Calmar", "Max Drawdown",
        "Win Rate", "Best Day", "Worst Day", "Invested %", "Days Live",
    ]
    df_metrics = pd.DataFrame(metric_rows)[cols_order]

    def _fmt(col, val):
        if pd.isna(val):
            return "—"
        pct_cols = {"Total Return", "Ann. Return", "Ann. Vol", "Max Drawdown",
                    "Win Rate", "Best Day", "Worst Day", "Invested %"}
        ratio_cols = {"Sharpe", "Sortino", "Calmar"}
        if col == "NAV":
            return f"${val:,.2f}"
        if col in pct_cols:
            return f"{val:+.2f}%" if col != "Win Rate" and col != "Invested %" else f"{val:.1f}%"
        if col in ratio_cols:
            return f"{val:.2f}"
        if col == "Days Live":
            return f"{int(val)}d"
        return str(val)

    # Style: colour-code return/risk columns
    def _style(df):
        styled = df.style
        for col in ["Total Return", "Ann. Return", "Max Drawdown", "Best Day", "Worst Day"]:
            if col in df.columns:
                styled = styled.map(
                    lambda v: f"color: {'#00c896' if isinstance(v, float) and v > 0 else '#ff4b4b' if isinstance(v, float) and v < 0 else ''}; font-weight: 600",
                    subset=[col]
                )
        for col in ["Sharpe", "Sortino", "Calmar"]:
            if col in df.columns:
                styled = styled.map(
                    lambda v: f"color: {'#00c896' if isinstance(v, float) and v > 1 else '#ff4b4b' if isinstance(v, float) and v < 0 else '#e8a020' if isinstance(v, float) and 0 <= v <= 1 else ''}; font-weight: 600",
                    subset=[col]
                )
        return styled

    fmt_dict = {col: (lambda v, c=col: _fmt(c, v)) for col in cols_order if col != "Strategy"}
    display_df = df_metrics.copy()
    for col in cols_order[1:]:
        display_df[col] = display_df[col].apply(lambda v, c=col: _fmt(c, v))

    st.dataframe(
        _style(df_metrics).format(fmt_dict, na_rep="—"),
        width='stretch',
        hide_index=True,
    )
else:
    st.info("No ledger data found. Run the strategy engines to generate data.")

st.divider()

# ── Section 2: NAV comparison chart ───────────────────────────────────────────

st.subheader("📈 NAV Comparison (indexed to 10,000)")

fig_nav = go.Figure()
for name, cfg in PORTFOLIOS.items():
    ledger = _load_ledger(cfg["ledger"])
    if ledger is None or len(ledger) < 2:
        continue
    fig_nav.add_trace(go.Scatter(
        x=ledger["date"],
        y=ledger["nav"],
        mode="lines",
        name=f"{cfg['icon']} {name}",
        line=dict(color=cfg["color"], width=2),
    ))

fig_nav.update_layout(
    height=340,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    yaxis=dict(title="NAV ($)", gridcolor="#2a2a3e", tickformat="$,.0f"),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
)
st.plotly_chart(fig_nav, width='stretch')

st.divider()

# ── Section 3: Drawdown comparison ────────────────────────────────────────────

st.subheader("📉 Drawdown Comparison")

fig_dd = go.Figure()
for name, cfg in PORTFOLIOS.items():
    ledger = _load_ledger(cfg["ledger"])
    if ledger is None or len(ledger) < 2:
        continue
    running_max = ledger["nav"].cummax()
    dd = (ledger["nav"] - running_max) / running_max * 100
    fig_dd.add_trace(go.Scatter(
        x=ledger["date"],
        y=dd,
        mode="lines",
        name=f"{cfg['icon']} {name}",
        line=dict(color=cfg["color"], width=2),
    ))

fig_dd.add_hline(y=-9.0, line_dash="dot", line_color="#ff8800",
                  annotation_text="9% stop threshold", annotation_position="bottom right")
fig_dd.update_layout(
    height=280,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    yaxis=dict(title="Drawdown (%)", gridcolor="#2a2a3e"),
    xaxis=dict(title="Date"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
)
st.plotly_chart(fig_dd, width='stretch')

st.divider()

# ── Section 4: Intra-portfolio stock correlations ─────────────────────────────

st.subheader("🔗 Intra-Portfolio Stock Correlations")
st.caption("Pairwise correlations of individual holdings within each strategy — 1-year daily returns.")

tabs = st.tabs([f"{cfg['icon']} {name}" for name, cfg in PORTFOLIOS.items()])

for tab, (name, cfg) in zip(tabs, PORTFOLIOS.items()):
    with tab:
        tickers = _tickers_for(name, cfg)
        if not tickers:
            st.info("No holdings data available — run the screener first.")
            continue

        st.markdown(f"**{len(tickers)} holdings:** {', '.join(tickers)}")
        _corr_heatmap(tickers, cfg["color"], name)

st.divider()

st.caption(
    "All returns are daily log-returns. Sharpe and Sortino use 252-day annualisation. "
    "Calmar = annualised return / |max drawdown|. "
    "Stock correlations use 1-year daily price-return data from Yahoo Finance."
)
