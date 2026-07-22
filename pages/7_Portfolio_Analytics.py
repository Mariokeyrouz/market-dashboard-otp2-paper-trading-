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
    "Momentum": {
        "ledger":    "momentum_ledger.csv",
        "state":     "momentum_state.json",
        "selection": "momentum_selection.json",
        "color":     "#6a1b9a",
        "icon":      "🚀",
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
    # A freshly-seeded strategy has a single ledger row (no return history yet).
    # Still surface it as a row — NAV / Total Return / Days Live are meaningful;
    # the return-based stats (Sharpe, vol, drawdown…) stay NaN and render as "—"
    # until the daily engine appends more days.
    if ledger is None or len(ledger) < 1:
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


@st.cache_data(ttl=3600)
def fetch_benchmark(ticker="SPY", period="6mo"):
    """Benchmark daily total-return closes (auto_adjust folds in dividends)."""
    try:
        raw = yf.download(ticker, period=period, interval="1d",
                          auto_adjust=True, progress=False)
        if raw.empty:
            return pd.Series(dtype=float)
        closes = raw["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        if getattr(closes.index, "tz", None) is not None:
            closes.index = closes.index.tz_localize(None)
        return closes.dropna()
    except Exception:
        return pd.Series(dtype=float)


def _benchmark_return(spy, start, end):
    """Total return (%) of the benchmark over each portfolio's own live window."""
    if spy is None or spy.empty:
        return float("nan")
    s = spy[(spy.index >= start) & (spy.index <= end)]
    if len(s) < 2:
        return float("nan")
    return (s.iloc[-1] / s.iloc[0] - 1) * 100


@st.cache_data(ttl=900)
def fetch_current_prices(tickers):
    """Latest close per ticker (one download). Missing symbols fall back to the
    state file's stored last_prices at the call site."""
    tickers = sorted(set(t for t in tickers if t))
    if not tickers:
        return {}
    try:
        raw = yf.download(tickers, period="5d", interval="1d",
                          auto_adjust=True, progress=False)
        if raw.empty:
            return {}
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
        if len(tickers) == 1 and "Close" in closes:
            return {tickers[0]: float(closes["Close"].dropna().iloc[-1])}
        out = {}
        for t in tickers:
            if t in closes.columns:
                col = closes[t].dropna()
                if len(col):
                    out[t] = float(col.iloc[-1])
        return out
    except Exception:
        return {}


def _position_rows(name, cfg, state, current_prices, selection):
    """One attribution row per held position, from the strategy's state file."""
    shares  = state.get("shares", {}) or {}
    entries = state.get("entry_prices", {}) or {}
    lasts   = state.get("last_prices", {}) or {}
    invested = state.get("invested_dollars", 0.0) or 0.0
    holdings = selection.get("holdings", {}) if selection else {}

    rows = []
    for t, sh in shares.items():
        entry = entries.get(t)
        if not entry or sh in (None, 0):
            continue
        cur = current_prices.get(t, lasts.get(t))   # fresh quote, else last stored
        if not cur:
            continue
        ret   = (cur / entry - 1) * 100
        mv    = sh * cur
        pnl   = sh * (cur - entry)
        wfrac = (mv / invested) if invested else float("nan")
        contrib = (wfrac * ret) if pd.notna(wfrac) else float("nan")  # % of invested return
        row = {
            "Ticker": t, "Strategy": name,
            "Return %": ret, "Contribution %": contrib,
            "P&L $": pnl, "Weight %": wfrac * 100 if pd.notna(wfrac) else float("nan"),
            "Entry": entry, "Now": cur,
        }
        h = holdings.get(t, {})   # factor context (FMTS strategies only)
        if h:
            row["Sector"]   = h.get("sector", "—")
            row["Momentum"] = h.get("score_momentum")
            row["Quality"]  = h.get("score_quality")
            row["Value"]    = h.get("score_value")
            row["LowVol"]   = h.get("score_low_vol")
        rows.append(row)
    return rows


def _ret_color(v):
    if isinstance(v, (int, float)) and pd.notna(v):
        if v > 0:
            return "color:#00c896; font-weight:600"
        if v < 0:
            return "color:#ff4b4b; font-weight:600"
    return ""


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

spy = fetch_benchmark("SPY")   # total-return benchmark

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
        # Benchmark over THIS portfolio's live window (apples-to-apples)
        spy_ret = _benchmark_return(spy, ledger["date"].iloc[0], ledger["date"].iloc[-1])
        m["SPY %"]  = spy_ret
        m["vs SPY"] = (m["Total Return"] - spy_ret) if pd.notna(spy_ret) else float("nan")
        metric_rows.append(m)

if metric_rows:
    cols_order = [
        "Strategy", "NAV", "Total Return", "SPY %", "vs SPY", "Ann. Return", "Ann. Vol",
        "Sharpe", "Sortino", "Calmar", "Max Drawdown",
        "Win Rate", "Best Day", "Worst Day", "Invested %", "Days Live",
    ]
    df_metrics = pd.DataFrame(metric_rows)[cols_order]

    def _fmt(col, val):
        if pd.isna(val):
            return "—"
        pct_cols = {"Total Return", "SPY %", "vs SPY", "Ann. Return", "Ann. Vol",
                    "Max Drawdown", "Win Rate", "Best Day", "Worst Day", "Invested %"}
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

    # Per-cell colour derived from the NUMERIC frame (green/red/amber by sign/threshold).
    _GREEN, _RED, _AMBER = ("color: #00c896; font-weight: 600",
                            "color: #ff4b4b; font-weight: 600",
                            "color: #e8a020; font-weight: 600")

    def _cell_color(col, v):
        if not isinstance(v, (int, float)) or pd.isna(v):
            return ""
        if col in {"Total Return", "SPY %", "vs SPY", "Ann. Return", "Max Drawdown", "Best Day", "Worst Day"}:
            return _GREEN if v > 0 else _RED if v < 0 else ""
        if col in {"Sharpe", "Sortino", "Calmar"}:
            if v > 1:        return _GREEN
            if v < 0:        return _RED
            if 0 <= v <= 1:  return _AMBER
        return ""

    # Streamlit renders a Styler's NaN cells as "None" regardless of na_rep, so we
    # hand it a fully pre-formatted STRING table ("—" for NaN via _fmt) and attach
    # the colours as a same-shaped CSS matrix computed from the numeric values.
    display_df = df_metrics.copy()
    color_df = pd.DataFrame("", index=df_metrics.index, columns=cols_order)
    for col in cols_order[1:]:
        color_df[col] = df_metrics[col].map(lambda v, c=col: _cell_color(c, v))
        display_df[col] = display_df[col].apply(lambda v, c=col: _fmt(c, v))

    st.dataframe(
        display_df.style.apply(lambda _: color_df, axis=None),
        width='stretch',
        hide_index=True,
    )
else:
    st.info("No ledger data found. Run the strategy engines to generate data.")

st.divider()

# ── Section 1b: Position Attribution ──────────────────────────────────────────

st.subheader("🎯 Position Attribution")
st.caption(
    "Per-position return since entry, dollar P&L, and contribution to each strategy's "
    "invested return. Positions reflect current holdings as of each strategy's last "
    "rebalance. A few weeks is far too short to separate skill from noise — read this as "
    "descriptive, not predictive."
)

# Load every strategy's state + (factor) selection once; price all held tickers together.
_states, _selections, _all_tickers = {}, {}, set()
for name, cfg in PORTFOLIOS.items():
    if os.path.exists(cfg["state"]):
        with open(cfg["state"]) as f:
            _states[name] = json.load(f)
        _all_tickers |= set((_states[name].get("shares") or {}).keys())
    sel_path = cfg.get("selection", "")
    if sel_path and os.path.exists(sel_path):
        with open(sel_path) as f:
            _selections[name] = json.load(f)

with st.spinner(f"Pricing {len(_all_tickers)} positions…"):
    _cur = fetch_current_prices(tuple(sorted(_all_tickers)))

_all_rows = []
for name, cfg in PORTFOLIOS.items():
    if name in _states:
        _all_rows += _position_rows(name, cfg, _states[name], _cur, _selections.get(name))

if not _all_rows:
    st.info("No open positions found in the strategy state files.")
else:
    df_pos = pd.DataFrame(_all_rows)
    _priced = sum(1 for r in _all_rows if r["Ticker"] in _cur)
    if _priced < len(_all_rows):
        st.caption(f"⚠ {len(_all_rows) - _priced} of {len(_all_rows)} positions used the last "
                   "stored price (Yahoo returned no fresh quote).")

    _pnl_fmt = {"Return %": "{:+.2f}%", "Contribution %": "{:+.2f}%",
                "P&L $": "${:+,.0f}", "Weight %": "{:.1f}%"}

    # (a) Combined best & worst across all portfolios
    st.markdown("**Best & worst positions — across all portfolios**")
    combined = df_pos.sort_values("Contribution %", ascending=False, na_position="last")
    cc = combined.dropna(subset=["Contribution %"])
    if len(cc):
        b, w = cc.iloc[0], cc.iloc[-1]
        st.markdown(
            f"Top contributor: **{b['Ticker']}** ({b['Strategy']}) {b['Return %']:+.1f}%  ·  "
            f"Biggest drag: **{w['Ticker']}** ({w['Strategy']}) {w['Return %']:+.1f}%"
        )
    st.dataframe(
        combined[["Ticker", "Strategy", "Return %", "Contribution %", "P&L $", "Weight %"]]
            .style.map(_ret_color, subset=["Return %", "Contribution %", "P&L $"])
            .format(_pnl_fmt, na_rep="—"),
        width='stretch', hide_index=True,
    )

    # (b) Per-strategy, with factor context where available (FMTS strategies)
    st.markdown("**By strategy**")
    ptabs = st.tabs([f"{cfg['icon']} {name}" for name, cfg in PORTFOLIOS.items()])
    for tab, (name, cfg) in zip(ptabs, PORTFOLIOS.items()):
        with tab:
            sub = df_pos[df_pos["Strategy"] == name].sort_values(
                "Contribution %", ascending=False, na_position="last")
            if sub.empty:
                st.info("No open positions.")
                continue
            has_factors = "Momentum" in sub.columns and sub["Momentum"].notna().any()
            cols = ["Ticker", "Return %", "Contribution %", "P&L $", "Weight %"]
            fmt = dict(_pnl_fmt)
            if has_factors:
                cols += ["Sector", "Momentum", "Quality", "Value", "LowVol"]
                fmt.update({k: "{:.0f}" for k in ["Momentum", "Quality", "Value", "LowVol"]})
            st.dataframe(
                sub[cols].style
                    .map(_ret_color, subset=["Return %", "Contribution %", "P&L $"])
                    .format(fmt, na_rep="—"),
                width='stretch', hide_index=True,
            )
            cw = sub.dropna(subset=["Contribution %"])
            if len(cw):
                t, d = cw.iloc[0], cw.iloc[-1]
                note = (f"Top: **{t['Ticker']}** ({t['Contribution %']:+.2f}% contrib) · "
                        f"Drag: **{d['Ticker']}** ({d['Contribution %']:+.2f}% contrib)")
                if has_factors:
                    note += "  ·  factor scores shown are as of the last rebalance"
                st.caption(note)

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

# Benchmark overlay: SPY rebased to 10,000 at the earliest inception shown.
_starts = [l["date"].iloc[0] for cfg in PORTFOLIOS.values()
           if (l := _load_ledger(cfg["ledger"])) is not None and len(l) >= 2]
if _starts and not spy.empty:
    _s = spy[spy.index >= min(_starts)]
    if len(_s) >= 2:
        fig_nav.add_trace(go.Scatter(
            x=_s.index, y=10000 * _s / _s.iloc[0], mode="lines",
            name="⚑ S&P 500 (SPY)",
            line=dict(color="#9aa0a6", width=2, dash="dash"),
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
