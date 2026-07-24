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


@st.cache_data(ttl=21600)   # 6h — a year of daily correlation data barely moves intraday
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


def _corr_heatmap(tickers, color_hex, title, all_ret=None):
    if not tickers:
        st.info("No holdings data available.")
        return

    # Reuse a single batched download when provided (all holdings fetched once,
    # sliced per tab) instead of one download per strategy tab.
    if all_ret is not None:
        ret_df = all_ret
    else:
        with st.spinner(f"Fetching {len(tickers)} stocks ({CORR_PERIOD})…"):
            ret_df = fetch_stock_returns(tickers, CORR_PERIOD)

    # Keep only tickers that came back
    available = [t for t in tickers if t in ret_df.columns]
    if len(available) < 2:
        st.warning("Not enough price data to compute correlation.")
        return

    ret_df  = ret_df[available].dropna()
    corr    = ret_df.corr().round(2)

    # Diversification score: mean of the off-diagonal correlations (lower = the
    # book's names move more independently = better intra-portfolio diversification).
    _nh = len(corr)
    if _nh >= 2:
        _off = corr.values[np.triu_indices(_nh, k=1)]
        _avg = float(np.nanmean(_off)) if len(_off) else float("nan")
        _lab = ("well diversified" if _avg < 0.3 else
                "moderately correlated" if _avg < 0.6 else "highly correlated")
        st.caption(f"📊 Diversification score — avg pairwise correlation **{_avg:.2f}** "
                   f"({_lab}; lower = more diversified)")

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


# ── System-health helpers (operational monitoring across all strategies) ──────

def _load_all_states(portfolios=PORTFOLIOS):
    """Every strategy's state + (optional) selection JSON."""
    states, selections = {}, {}
    for name, cfg in portfolios.items():
        if os.path.exists(cfg["state"]):
            try:
                with open(cfg["state"]) as f:
                    states[name] = json.load(f)
            except Exception:
                pass
        sp = cfg.get("selection", "")
        if sp and os.path.exists(sp):
            try:
                with open(sp) as f:
                    selections[name] = json.load(f)
            except Exception:
                pass
    return states, selections


def _eff_shares(state):
    """Holdings as {ticker: shares}, folding Gold's gld_shares/in_position into
    the same shape as the equity strategies' `shares` dict."""
    sh = dict(state.get("shares") or {})
    if not sh and state.get("in_position") and state.get("gld_shares"):
        sh = {"GLD": state["gld_shares"]}
    return {t: q for t, q in sh.items() if q}


def _days_since(date_str):
    if not date_str:
        return None
    try:
        return (pd.Timestamp.today().normalize() - pd.Timestamp(date_str).normalize()).days
    except Exception:
        return None


def _diag_rows(states, selections, portfolios=PORTFOLIOS):
    rows = []
    for name, cfg in portfolios.items():
        s = states.get(name, {})
        led = _load_ledger(cfg["ledger"])
        last = s.get("last_date") or (str(led["date"].iloc[-1].date())
                                      if led is not None and len(led) else None)
        days = _days_since(last)
        dot = "🟢" if (days is not None and days <= 4) else \
              "🟡" if (days is not None and days <= 8) else "🔴"
        health = "current" if (days is not None and days <= 4) else \
                 "stale" if (days is not None and days <= 8) else "frozen"
        inv = s.get("invested", s.get("invested_pct"))
        if inv is not None and inv > 1.5:
            inv = inv / 100.0
        if s.get("stopped_out"):
            stance = "⚠ Stopped (50%)"
        elif s.get("risk_on") is False:
            stance = "Risk-off (cash)"
        elif "in_position" in s:
            stance = "Long GLD" if s.get("in_position") else "Cash (no signal)"
        elif inv is not None:
            stance = f"{inv*100:.0f}% invested"
        else:
            stance = "—"
        rows.append({
            "Strategy": f"{cfg['icon']} {name}", "Status": f"{dot} {health}",
            "Last update": last or "—", "Days ago": days if days is not None else "—",
            "Stance": stance, "Holdings": len(_eff_shares(s)),
            "Selection": selections.get(name, {}).get("as_of", "—"),
        })
    return rows


def _system_totals(states):
    total_nav = sum(float(s.get("nav", 0) or 0) for s in states.values())
    invested, riskoff = 0.0, 0
    for s in states.values():
        inv_d = s.get("invested_dollars")
        if inv_d is None:                                    # Gold has no invested_dollars
            inv_d = float(s.get("nav", 0) or 0) if s.get("in_position") else 0.0
        invested += float(inv_d or 0)
        if s.get("risk_on") is False or s.get("in_position") is False or \
           (s.get("invested") is not None and s.get("invested") < 0.05):
            riskoff += 1
    n = len(states)
    pnl = total_nav - 10000.0 * n
    return {"nav": total_nav, "invested": invested, "cash": total_nav - invested,
            "pct_inv": (invested / total_nav * 100) if total_nav else 0.0,
            "pnl": pnl, "pnl_pct": (pnl / (10000 * n) * 100) if n else 0.0,
            "n": n, "riskoff": riskoff}


def _aggregate_exposure(states, cur):
    """Total $ exposure per ticker across ALL strategies (surfaces cross-book
    concentration in names several strategies happen to share)."""
    agg = {}
    for name, s in states.items():
        lasts = s.get("last_prices") or {}
        entries = s.get("entry_prices") or {}
        for t, q in _eff_shares(s).items():
            px = cur.get(t) or lasts.get(t) or entries.get(t)
            if not px:
                continue
            e = agg.setdefault(t, {"value": 0.0, "strats": []})
            e["value"] += q * px
            e["strats"].append(name)
    return agg


def _strategy_return_frame(portfolios=PORTFOLIOS):
    rets = {}
    for name, cfg in portfolios.items():
        led = _load_ledger(cfg["ledger"])
        if led is not None and len(led) > 2 and "daily_log_ret" in led.columns:
            rets[name] = pd.to_numeric(led.set_index("date")["daily_log_ret"], errors="coerce")
    return pd.DataFrame(rets)


def _system_events(portfolios=PORTFOLIOS, limit=40):
    """Reverse-chronological activity feed reconstructed from ledger history —
    seeds, rebalances, stop triggers/re-entries, risk-on/off flips, big trims."""
    events = []
    for name, cfg in portfolios.items():
        led = _load_ledger(cfg["ledger"])
        if led is None or len(led) == 0:
            continue
        led = led.reset_index(drop=True)
        who = f"{cfg['icon']} {name}"
        events.append((led["date"].iloc[0], who, "seed", f"Seeded at ${led['nav'].iloc[0]:,.0f}"))
        cols = led.columns
        if "holdings" in cols:
            prev = None
            for i in range(len(led)):
                h = led["holdings"].iloc[i]
                if prev is not None and isinstance(h, str) and isinstance(prev, str) and h != prev:
                    events.append((led["date"].iloc[i], who, "rebalance", "Rebalanced holdings"))
                prev = h
        if "stopped_out" in cols:
            v = led["stopped_out"].astype(str).str.lower().isin(["true", "1"]).values
            for i in range(1, len(v)):
                if v[i] and not v[i-1]:
                    events.append((led["date"].iloc[i], who, "stop", "Trailing stop → scaled to 50%"))
                elif not v[i] and v[i-1]:
                    events.append((led["date"].iloc[i], who, "reentry", "Re-entered after stop"))
        if "risk_on" in cols:
            v = led["risk_on"].astype(str).str.lower().isin(["true", "1"]).values
            for i in range(1, len(v)):
                if not v[i] and v[i-1]:
                    events.append((led["date"].iloc[i], who, "risk-off", "Trend gate → risk-off (cash)"))
                elif v[i] and not v[i-1]:
                    events.append((led["date"].iloc[i], who, "risk-on", "Trend gate → risk-on"))
        if "invested_pct" in cols:
            iv = pd.to_numeric(led["invested_pct"], errors="coerce").values
            for i in range(1, len(iv)):
                if np.isfinite(iv[i]) and np.isfinite(iv[i-1]):
                    d = iv[i] - iv[i-1]
                    if d <= -8:
                        events.append((led["date"].iloc[i], who, "trim", f"Trimmed to {iv[i]:.0f}% invested"))
                    elif d >= 8:
                        events.append((led["date"].iloc[i], who, "reload", f"Reloaded to {iv[i]:.0f}% invested"))
    events.sort(key=lambda e: e[0], reverse=True)
    return events[:limit]


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

# ── Section 1c: System Health & Diagnostics ──────────────────────────────────

st.subheader("🩺 System Health & Diagnostics")

# The system view spans EVERY strategy, including Gold — which has its own page
# and is deliberately excluded from the equity-only sections above/below.
SYSTEM_PORTFOLIOS = {**PORTFOLIOS, "Gold": {
    "ledger": "gold_ledger.csv", "state": "gold_state.json", "selection": "",
    "icon": "🥇", "color": "#c9a227"}}
_hstates, _hsel = _load_all_states(SYSTEM_PORTFOLIOS)

# (a) Combined system totals
_tot = _system_totals(_hstates)
_hc = st.columns(5)
_hc[0].metric("Total System NAV", f"${_tot['nav']:,.0f}")
_hc[1].metric("Invested / Cash", f"{_tot['pct_inv']:.0f}% / {100 - _tot['pct_inv']:.0f}%")
_hc[2].metric("System P&L", f"${_tot['pnl']:+,.0f}", f"{_tot['pnl_pct']:+.2f}% since seed")
_hc[3].metric("Strategies", f"{_tot['n']}")
_hc[4].metric("In Cash / Risk-off", f"{_tot['riskoff']} / {_tot['n']}")

# (b) Per-strategy diagnostics + staleness heartbeat
st.markdown("**Strategy status** — operational state & data freshness")
_diagrows = _diag_rows(_hstates, _hsel, SYSTEM_PORTFOLIOS)
st.dataframe(pd.DataFrame(_diagrows), width='stretch', hide_index=True)
_frozen = [r["Strategy"] for r in _diagrows if "🔴" in r["Status"]]
if _frozen:
    st.warning(f"⚠ Stale/frozen ledgers: {', '.join(_frozen)} — the daily update job may not be running.")
else:
    st.caption("🟢 all ledgers current · 🟡 5–8 days behind · 🔴 frozen (>8 days) — the freshness heartbeat.")

# (c) Aggregate exposure & overlap
st.markdown("**Aggregate exposure & overlap** — total system exposure per name, across every strategy")
_htk = set()
for _s in _hstates.values():
    _htk |= set(_eff_shares(_s).keys())
_hcur = fetch_current_prices(tuple(sorted(t for t in _htk if t)))
_exp = _aggregate_exposure(_hstates, _hcur)
if _exp:
    _tinv = sum(e["value"] for e in _exp.values()) or 1.0
    _erows = [{"Ticker": t, "Total $": e["value"], "% of System": e["value"] / _tinv * 100,
               "# Strategies": len(e["strats"]), "Held by": ", ".join(e["strats"])}
              for t, e in sorted(_exp.items(), key=lambda kv: -kv[1]["value"])]
    _edf = pd.DataFrame(_erows)
    _ov = _edf[_edf["# Strategies"] > 1]
    if len(_ov):
        _t0 = _ov.iloc[0]
        st.caption(f"⚠ {len(_ov)} names are held by 2+ strategies (hidden concentration). Largest shared "
                   f"exposure: **{_t0['Ticker']}** = {_t0['% of System']:.1f}% of the whole system across "
                   f"{int(_t0['# Strategies'])} strategies.")
    st.dataframe(
        _edf.head(20).style.format({"Total $": "${:,.0f}", "% of System": "{:.1f}%"}).apply(
            lambda row: ["background-color: rgba(255,180,0,0.13)" if row["# Strategies"] > 1 else ""
                         for _ in row], axis=1),
        width='stretch', hide_index=True,
    )
else:
    st.info("No open positions to aggregate (all strategies in cash).")

# (d) Cross-strategy correlation
st.markdown("**Cross-strategy correlation** — are the strategies actually diversifying each other?")
_ccorr = _strategy_return_frame(SYSTEM_PORTFOLIOS).corr(min_periods=8)
if _ccorr.notna().values.sum() > len(_ccorr):
    _cl = list(_ccorr.columns)
    _cz = _ccorr.values
    _figc = go.Figure(data=go.Heatmap(
        z=_cz, x=_cl, y=_cl, zmin=-1, zmax=1, colorscale="RdBu_r",
        text=np.where(np.isnan(_cz), "", np.round(_cz, 2).astype(str)),
        texttemplate="%{text}", hoverongaps=False, colorbar=dict(title="ρ")))
    _figc.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(_figc, width='stretch')
    st.caption("Blank cells = not enough shared history yet (e.g. Momentum, seeded recently). "
               "Near-1 = redundant (the OTP2.0 and FMTS variant pairs); low/negative = genuine "
               "diversification (the two families vs each other, and Gold ≈ 0 with everything).")
else:
    st.info("Not enough overlapping history yet to compute cross-strategy correlations.")

# (e) Event log / backlog
st.markdown("**Event log** — rebalances, stop triggers, risk-flips & seeds across the whole system")
_ev = _system_events(SYSTEM_PORTFOLIOS)
if _ev:
    _evdf = pd.DataFrame([{"Date": d.date().isoformat(), "Strategy": who, "Event": ty, "Detail": msg}
                          for d, who, ty, msg in _ev])
    st.dataframe(_evdf, width='stretch', hide_index=True,
                 height=min(380, 45 + 35 * len(_evdf)))
else:
    st.info("No events recorded yet.")

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

# Loaded on demand — this is the page's heaviest fetch (a year of daily prices
# for every holding). Off by default keeps the rest of the page fast; when on,
# all holdings are pulled in ONE batched download and sliced per tab (instead of
# a separate download per strategy).
if st.checkbox("📈 Load correlation heatmaps (fetches 1-year price history)", value=False):
    _all_ctk = sorted({t for name, cfg in PORTFOLIOS.items() for t in _tickers_for(name, cfg)})
    with st.spinner(f"Fetching 1-year returns for {len(_all_ctk)} holdings…"):
        _all_ret = fetch_stock_returns(_all_ctk, CORR_PERIOD)
    tabs = st.tabs([f"{cfg['icon']} {name}" for name, cfg in PORTFOLIOS.items()])
    for tab, (name, cfg) in zip(tabs, PORTFOLIOS.items()):
        with tab:
            tickers = _tickers_for(name, cfg)
            if not tickers:
                st.info("No holdings data available — run the screener first.")
                continue
            st.markdown(f"**{len(tickers)} holdings:** {', '.join(tickers)}")
            _corr_heatmap(tickers, cfg["color"], name, all_ret=_all_ret)
else:
    st.caption("↑ Tick the box to load the heatmaps on demand (keeps the page fast otherwise).")

st.divider()

st.caption(
    "All returns are daily log-returns. Sharpe and Sortino use 252-day annualisation. "
    "Calmar = annualised return / |max drawdown|. "
    "Stock correlations use 1-year daily price-return data from Yahoo Finance."
)
