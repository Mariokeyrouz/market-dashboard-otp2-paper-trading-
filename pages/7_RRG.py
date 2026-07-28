"""
RRG — Relative Rotation Graph (sectors -> stocks)
=================================================
Descriptive view of where every S&P 500 sector sits in relative-strength space
versus SPX, and where the constituents of the top-ranked sectors sit versus
their own sector ETF.

READS PRECOMPUTED FILES ONLY — no heavy compute, no scipy, no yfinance calls
at render time. Refresh the underlying numbers with:

    py rrg_null.py          # mechanical baseline (500 sims)
    py rrg_validate.py      # historical validation -> rrg_calibration.json
    py rrg_analysis.py      # current state -> the CSV/JSON this page reads

THE VALIDATION VERDICT IS SHOWN FIRST, DELIBERATELY. The RRG geometry did not
clear its pre-registered bar, so this page is a monitoring and communication
tool, not a signal generator. That framing is part of the product.
"""

import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="RRG — Relative Rotation", page_icon="🔄", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }

    /* Every box sets its own text colour explicitly — inheriting the theme
       default puts dark text on these dark backgrounds and it disappears. */
    .rrg-box, .verdict-fail, .verdict-pass {
        border-radius: 8px; padding: 20px 26px; margin-bottom: 20px;
        line-height: 1.7; font-size: 15px; color: #e9eef5;
    }
    .rrg-box      { background: #0d1b2a; border-left: 5px solid #4a9eff; }
    .verdict-fail { background: #2a1a00; border-left: 5px solid #ffa726; }
    .verdict-pass { background: #04231a; border-left: 5px solid #00c896; }

    .rrg-box b, .verdict-fail b, .verdict-pass b { color: #ffffff; }
    .rrg-box code, .verdict-fail code, .verdict-pass code {
        background: #ffffff14; color: #9ad8ff; padding: 2px 7px;
        border-radius: 4px; font-size: 13.5px;
    }
    .rrg-box h4 {
        margin: 0 0 14px 0; color: #ffffff; font-size: 12px;
        letter-spacing: 0.09em; text-transform: uppercase; font-weight: 700;
    }
    .rrg-box table { width: 100%; border-collapse: collapse; margin: 6px 0 16px 0; }
    .rrg-box th {
        text-align: left; padding: 7px 12px 7px 0; color: #8fa6bd;
        font-size: 11px; letter-spacing: 0.07em; text-transform: uppercase;
        font-weight: 600; border-bottom: 1px solid #ffffff1f;
    }
    .rrg-box td {
        padding: 9px 12px 9px 0; vertical-align: top;
        border-bottom: 1px solid #ffffff0f; font-size: 14.5px;
    }
    .rrg-box td:first-child { white-space: nowrap; color: #ffffff; font-weight: 600; }
    .rrg-box .note { color: #b9c7d6; font-size: 14px; margin: 0; }
    .rrg-box .keyline {
        color: #ffd479; font-weight: 600; display: block; margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

SECTOR_CSV = "rrg_sector_results.csv"
STOCK_CSV = "rrg_stock_results.csv"
CAND_CSV = "rrg_stock_candidates.csv"
CAL_JSON = "rrg_calibration.json"
TAILS_JSON = "rrg_tails.json"
VAL_CSV = "rrg_validation_results.csv"
PORT_CSV = "rrg_portfolio_results.csv"
STATE_PATH = "rrg_state.json"
LEDGER_PATH = "rrg_ledger.csv"
SELECT_JSON = "rrg_selection.json"

QUAD_COLOR = {"Leading": "#00c896", "Weakening": "#ffd166",
              "Lagging": "#ff4b4b", "Improving": "#4a9eff", "—": "#888888"}


@st.cache_data(ttl=300)
def fetch_live_prices(tickers):
    """Live prices for the paper book. NaN-hardened: a NaN close is still a
    float and would pass an `is not None` check, poisoning every total."""
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="5d", interval="1d")
            close = h["Close"].dropna() if not h.empty else pd.Series(dtype=float)
            if close.empty:
                raise ValueError("no data")
            out[t] = {
                "price": float(close.iloc[-1]),
                "prev_close": float(close.iloc[-2]) if len(close) > 1
                else float(close.iloc[-1]),
            }
        except Exception:
            out[t] = {"price": None, "prev_close": None}
    return out


@st.cache_data(ttl=900)
def load_all():
    out = {}
    for key, path in (("sectors", SECTOR_CSV), ("sizing", STOCK_CSV),
                      ("cands", CAND_CSV), ("val", VAL_CSV), ("port", PORT_CSV)):
        out[key] = pd.read_csv(path) if os.path.exists(path) else None
    for key, path in (("cal", CAL_JSON), ("tails", TAILS_JSON)):
        if os.path.exists(path):
            with open(path) as f:
                out[key] = json.load(f)
        else:
            out[key] = None
    return out


D = load_all()

st.title("🔄 RRG — Relative Rotation Graph")

if D["sectors"] is None or D["cal"] is None:
    st.warning("No RRG output found. Generate it with:\n\n"
               "```\npy rrg_null.py\npy rrg_validate.py\npy rrg_analysis.py\n```")
    st.stop()

cal = D["cal"]
tails = D["tails"] or {}
asof = tails.get("as_of", "—")
null_straight = float(tails.get("straightness_null", 0.769))
base = tails.get("baseline_hit", {})

col_r, _ = st.columns([1, 6])
with col_r:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()

# ── The verdict, first ───────────────────────────────────────────────────────
edge = bool(cal.get("edge_real"))
npass, nchk = cal.get("n_pass", 0), cal.get("n_checks", 0)
box = "verdict-pass" if edge else "verdict-fail"
headline = ("Edge cleared every pre-registered test — sizing is justified."
            if edge else
            "The RRG signal did NOT clear its pre-registered validation bar.")
st.markdown(f"""
<div class="{box}">
<b>Validation verdict — {npass}/{nchk} criteria passed.</b> {headline}<br>
<span style="color:#a0a0a0;font-size:0.92em;">
An RRG plots a rolling z-score against (approximately) its own derivative, and that
phase portrait rotates clockwise for <i>any</i> stationary series — including pure
noise. So rotation alone is not evidence. Every number here is measured against a
500-run simulation under zero true edge. Sizing multiplier applied:
<b>{cal.get('sizing_multiplier', 0):.2f}</b>.
</span></div>
""", unsafe_allow_html=True)

with st.expander("ℹ️ How every column is calculated — read me", expanded=False):
    st.markdown(f"""
Nothing on this page is a subjective judgement. The definitions:

| Column | Definition |
|---|---|
| **RS-Ratio / RS-Momentum** | JdK replication: `rs = 100·price/benchmark`; RS-Ratio = `SMA_S(100 + zscore_W(rs))`; RS-Momentum = `SMA_S(100 + zscore_W(100·RS-Ratio/RS-Ratio.shift(M)))`. Weekly, W={cal['spec']['W']}, S={cal['spec']['S']}, M={cal['spec']['M']}. |
| **Quadrant** | Leading = both > 100 · Weakening = ratio>100, mom<100 · Lagging = both < 100 · Improving = ratio<100, mom>100. |
| **Heading / Angle** | PCA principal direction of the last {cal['spec']['L']} points, signed by the chord, computed on **trailing-SD-standardized axes** (raw degrees are an artefact of the plot's aspect ratio). Near-stationary points are labelled *flat* rather than given a fake heading. |
| **Distance** | **Mahalanobis** distance from (100,100) using the trailing covariance — plain Euclidean is invalid because the two axes have different scales *and* are mechanically correlated. |
| **Δ Distance** | Change in that distance over the tail — the "is it expanding?" measure. |
| **Tail / straightness** | Net displacement ÷ path length. Compared against **{null_straight:.2f}**, the value pure noise produces under this same transform — *not* against the naive random-walk null of 0.33. Below 1.0× means less persistent than noise. |
| **RRG Score** | Walk-forward-fitted linear predictor of forward excess return (weights fit only on past data), percentile-ranked 0–100 across the cross-section. |
| **Hit rate** | Counted from history for the matching (quadrant × distance tercile) bucket, shrunk toward the pooled rate. Compare against the **measured baseline**, not 50% — stock excess returns versus a cap-weighted index are right-skewed with a negative median. |

**Baseline hit rates (measured):** 1M {100*base.get('1M', float('nan')):.1f}% · 3M {100*base.get('3M', float('nan')):.1f}%
""")

st.caption(f"As of {asof} (weekly close) · benchmark {cal['spec']['benchmark']} · "
           f"calibration generated {cal.get('generated','—')}")

# ── Decision-rule detail ─────────────────────────────────────────────────────
with st.expander(f"🔬 The {nchk} pre-registered decision rules", expanded=False):
    chk = pd.DataFrame(cal.get("checks", []))
    if len(chk):
        chk["result"] = np.where(chk["pass"], "✅ PASS", "❌ FAIL")
        st.dataframe(chk[["result", "name", "detail"]], width="stretch",
                     hide_index=True)
    st.caption("Thresholds were frozen and committed before the 2020–2026 holdout "
               "was opened. The deciding rule is the incremental IC over plain 12-1 "
               "relative momentum: the others can all pass on a repackaged "
               "momentum signal.")


# ── RRG chart ────────────────────────────────────────────────────────────────
def rrg_figure(tail_map, df, title, label_col="ticker", max_names=14):
    fig = go.Figure()
    xs = [v for t in tail_map.values() for v in t["x"]]
    ys = [v for t in tail_map.values() for v in t["y"]]
    if not xs:
        return None
    pad = 0.6
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    quads = [(100, x1, 100, y1, "rgba(0,200,150,0.07)", "Leading"),
             (100, x1, y0, 100, "rgba(255,209,102,0.07)", "Weakening"),
             (x0, 100, y0, 100, "rgba(255,75,75,0.07)", "Lagging"),
             (x0, 100, 100, y1, "rgba(74,158,255,0.07)", "Improving")]
    for qx0, qx1, qy0, qy1, col, name in quads:
        fig.add_shape(type="rect", x0=qx0, x1=qx1, y0=qy0, y1=qy1,
                      fillcolor=col, line=dict(width=0), layer="below")
        fig.add_annotation(x=(qx0 + qx1) / 2, y=qy1 if qy1 > 100 else qy0,
                           text=name, showarrow=False,
                           font=dict(size=10, color="#666"),
                           yanchor="top" if qy1 > 100 else "bottom")
    fig.add_hline(y=100, line=dict(color="#444", width=1))
    fig.add_vline(x=100, line=dict(color="#444", width=1))

    keep = list(df[label_col])[:max_names]
    for tk in keep:
        t = tail_map.get(str(tk))
        if not t:
            continue
        row = df[df[label_col] == tk]
        q = row["quadrant"].iloc[0] if len(row) else "—"
        col = QUAD_COLOR.get(q, "#888")
        fig.add_trace(go.Scatter(
            x=t["x"], y=t["y"], mode="lines", line=dict(color=col, width=1.5),
            opacity=0.55, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=[t["x"][-1]], y=[t["y"][-1]], mode="markers+text",
            marker=dict(size=11, color=col, line=dict(color="#fff", width=1)),
            text=[str(tk)], textposition="top center",
            textfont=dict(size=11, color="#e0e0e0"), name=str(tk),
            showlegend=False,
            hovertemplate=(f"<b>{tk}</b><br>RS-Ratio %{{x:.2f}}<br>"
                           f"RS-Momentum %{{y:.2f}}<br>{q}<extra></extra>")))
    fig.update_layout(
        title=title, height=560,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(title="RS-Ratio  (relative strength)", gridcolor="#2a2a3e",
                   range=[x0, x1], zeroline=False),
        yaxis=dict(title="RS-Momentum", gridcolor="#2a2a3e",
                   range=[y0, y1], zeroline=False))
    return fig


st.divider()
st.subheader("💼 Paper portfolio — live positions")

if not (os.path.exists(STATE_PATH) and os.path.exists(LEDGER_PATH)):
    st.info("No paper portfolio yet. Create one with "
            "`py rrg_portfolio_engine.py --seed`, then keep it current with "
            "`py rrg_portfolio_engine.py`.")
else:
    with open(STATE_PATH) as f:
        pstate = json.load(f)
    pledger = pd.read_csv(LEDGER_PATH)
    pledger["date"] = pd.to_datetime(pledger["date"])
    sel = {}
    if os.path.exists(SELECT_JSON):
        with open(SELECT_JSON) as f:
            sel = json.load(f).get("holdings", {})

    live = fetch_live_prices(tuple(sorted(pstate["shares"])))

    rows, tot_mv, tot_cost, tot_day = [], 0.0, 0.0, 0.0
    for t, n in pstate["shares"].items():
        entry = float(pstate["entry_prices"][t])
        lp = live.get(t, {})
        last = lp.get("price")
        if last is None or pd.isna(last):
            last = pstate.get("last_prices", {}).get(t)
        if last is None or pd.isna(last):
            last = entry
        prev = lp.get("prev_close")
        if prev is None or pd.isna(prev):
            prev = last
        mv, cost = n * last, n * entry
        tot_mv += mv
        tot_cost += cost
        tot_day += n * (last - prev)
        meta = sel.get(t, {})
        rows.append({
            "Ticker": t, "Sector": meta.get("sector", ""),
            "Setup": meta.get("setup", ""), "Shares": n,
            "Entry Price": entry, "Live Price": float(last),
            "Market Value": mv, "Unrealized $": mv - cost,
            "Unrealized %": (last / entry - 1.0) * 100.0,
            "Day $": n * (last - prev),
        })
    pos = pd.DataFrame(rows)
    denom = tot_mv if tot_mv > 0 else float("nan")
    pos["Weight %"] = pos["Market Value"] / denom * 100.0
    pos = pos.sort_values("Market Value", ascending=False)

    cash = float(pstate.get("cash_dollars", 0.0))
    nav = tot_mv + cash
    seed_nav = float(pledger["nav"].iloc[0]) if len(pledger) else nav
    peak = float(pstate.get("peak_nav", nav))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total portfolio value", f"${nav:,.2f}",
              f"{(nav/seed_nav - 1)*100:+.2f}% since seed")
    k2.metric("Unrealized P&L", f"${tot_mv - tot_cost:+,.2f}",
              f"{((tot_mv/tot_cost - 1)*100 if tot_cost else 0):+.2f}%")
    k3.metric("Today", f"${tot_day:+,.2f}",
              f"{(tot_day/(nav - tot_day)*100 if nav != tot_day else 0):+.2f}%")
    k4.metric("Cash", f"${cash:,.2f}",
              f"drawdown {(nav/peak - 1)*100:+.2f}%" if peak else "")

    st.dataframe(
        pos, width="stretch", hide_index=True,
        column_config={
            "Shares": st.column_config.NumberColumn(format="%.4f"),
            "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
            "Live Price": st.column_config.NumberColumn(format="$%.2f"),
            "Market Value": st.column_config.NumberColumn(format="$%,.2f"),
            "Unrealized $": st.column_config.NumberColumn(format="$%+,.2f"),
            "Unrealized %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Day $": st.column_config.NumberColumn(format="$%+,.2f"),
            "Weight %": st.column_config.NumberColumn(format="%.1f%%"),
        })
    st.caption(
        f"Seeded {pledger['date'].iloc[0].date()} with ${seed_nav:,.0f}, equal weight, "
        f"max {2} per sector · last engine update {pstate.get('last_date','—')} · "
        f"cumulative trading cost ${float(pstate.get('trading_cost',0)):,.2f} "
        f"(10 bps slippage on traded dollars) · prices refresh every 5 min."
    )

    if len(pledger) > 1:
        fign = go.Figure()
        fign.add_trace(go.Scatter(
            x=pledger["date"], y=pledger["nav"], mode="lines", name="NAV",
            line=dict(color="#4a9eff", width=2)))
        fign.add_trace(go.Scatter(
            x=[pledger["date"].iloc[-1]], y=[nav], mode="markers",
            name="live", marker=dict(color="#00c896", size=11, symbol="star")))
        fign.update_layout(
            height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
            yaxis=dict(title="NAV ($)", gridcolor="#2a2a3e", tickformat=","),
            xaxis=dict(gridcolor="#2a2a3e"))
        st.plotly_chart(fign, width="stretch")

    st.markdown(f"""
<div class="verdict-fail">
<b>This is a paper book, not a recommendation.</b> It holds the top {len(pos)} names by
RRG Score, equal-weighted, so the signal can be tracked forward out of sample — exactly
how the other strategies in this app are run. The validation says
<b>do not fund it</b>: the walk-forward backtest lost money with a 50% drawdown and the
sizing multiplier is {cal.get('sizing_multiplier', 0):.2f}. A failed backtest is a
statement about the past, so watching it forward is worthwhile — but the burden of proof
sits with the signal, and it has not met it.
</div>
""", unsafe_allow_html=True)

st.divider()
st.subheader("🧪 The portfolio backtest — does trading this actually work?")

port = D["port"]
if port is None or not len(port):
    st.info("No portfolio backtest found — run `py rrg_validate.py`.")
else:
    vals = {}
    if D["val"] is not None:
        v = D["val"]
        v = v[v["section"] == "portfolio"].copy()
        # `value` also carries string fields elsewhere in the file (data
        # fingerprints), so the column loads as object — coerce before formatting.
        v["value"] = pd.to_numeric(v["value"], errors="coerce")
        vals = dict(zip(v["metric"], v["value"]))

    def g(metric):
        try:
            return float(vals.get(metric, float("nan")))
        except (TypeError, ValueError):
            return float("nan")

    m1, m2, m3 = st.columns(3)
    m1.metric("In-sample fit (overfit)",
              f"IR {g('ir_1M_full-sample-fit (IS)'):+.2f}",
              f"t {g('t_1M_full-sample-fit (IS)'):+.2f} · "
              f"maxDD {100*g('maxdd_1M_full-sample-fit (IS)'):.0f}%")
    m2.metric("Walk-forward (honest)",
              f"IR {g('ir_1M_walk-forward'):+.2f}",
              f"t {g('t_1M_walk-forward'):+.2f} · "
              f"maxDD {100*g('maxdd_1M_walk-forward'):.0f}%")
    m3.metric("Walk-forward, 2020+ holdout",
              f"IR {g('ir_1M_walk-forward HOLDOUT'):+.2f}",
              f"t {g('t_1M_walk-forward HOLDOUT'):+.2f} · "
              f"maxDD {100*g('maxdd_1M_walk-forward HOLDOUT'):.0f}%")

    pf = port.copy()
    pf["date"] = pd.to_datetime(pf["date"])
    figp = go.Figure()
    for col, name, colr, dash in (
            ("in_sample", "Fit on the whole sample (look-ahead)", "#ffd166", "dash"),
            ("walk_forward", "Walk-forward (only past data)", "#ff4b4b", "solid"),
            ("equal_weight_sectors", "Equal-weight sectors vs SPY", "#4a9eff", "dot")):
        if col in pf.columns:
            figp.add_trace(go.Scatter(
                x=pf["date"], y=pf[col], name=name, mode="lines",
                line=dict(color=colr, width=2, dash=dash),
                hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.3f}<extra></extra>"))
    figp.add_hline(y=1.0, line=dict(color="#555", width=1, dash="dot"))
    figp.update_layout(
        height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=30, b=0),
        title="Growth of $1 — long top-3 / short bottom-3 sectors by RRG Score",
        yaxis=dict(title="Growth of $1 (active return)", gridcolor="#2a2a3e"),
        xaxis=dict(title="", gridcolor="#2a2a3e"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(figp, width="stretch")

    fin_is = float(pf["in_sample"].iloc[-1]) if "in_sample" in pf else float("nan")
    fin_wf = float(pf["walk_forward"].iloc[-1]) if "walk_forward" in pf else float("nan")
    fin_bh = float(pf["equal_weight_sectors"].iloc[-1]) \
        if "equal_weight_sectors" in pf else float("nan")
    st.markdown(f"""
<div class="rrg-box">
<h4>This is the test that matters</h4>
<p class="note">The signal is turned into an actual tradeable portfolio:
rebalance 1/H of capital each week and hold H weeks (Jegadeesh–Titman overlapping
tranches), long the top 3 sectors by RRG Score and short the bottom 3. Because each
period's return is a single non-overlapping observation, its t-statistic is honest —
unlike the IC tests, where sampling a 63-day return every week inflates naive t-stats
by up to 6.5×.</p>
<table>
<tr><th style="width:42%">Variant</th><th>Growth of $1</th><th>Verdict</th></tr>
<tr><td>Fit on the whole sample</td><td><b>${fin_is:.2f}</b></td>
    <td>Uses future data to pick its own weights. Not achievable.</td></tr>
<tr><td>Walk-forward (only past data)</td><td><b>${fin_wf:.2f}</b></td>
    <td><span class="keyline">The honest number — it loses money, with a
        {100*g('maxdd_1M_walk-forward'):.0f}% drawdown.</span></td></tr>
<tr><td>Equal-weight sectors vs SPY</td><td><b>${fin_bh:.2f}</b></td>
    <td>Doing nothing clever beat the signal.</td></tr>
</table>
<p class="note">The gap between the first and second rows <b>is</b> the overfitting.
Same data, same rules — the only difference is whether the model was allowed to see
the future when choosing its weights.</p>
</div>
""", unsafe_allow_html=True)

st.divider()
st.subheader("📊 Sector rotation vs SPX")
sec = D["sectors"]
fig = rrg_figure(tails.get("sectors", {}), sec,
                 f"All 11 S&P 500 sectors vs {cal['spec']['benchmark']} · "
                 f"{tails.get('tail_weeks', 14)}-week tails")
if fig:
    st.plotly_chart(fig, width="stretch")
st.caption("Tails run over the last "
           f"{tails.get('tail_weeks', 14)} weekly observations, so the full sequence "
           "of observations is shown, not just the latest point. Clockwise motion is "
           "the mechanical norm — it is not by itself informative.")

st.subheader("🏆 Sector ranking")
show_cols = ["rank", "ticker", "sector", "rrg_score", "quadrant", "heading",
             "angle_deg", "distance", "delta_distance", "straightness",
             "tail_vs_null", "hit_1M_pct", "hit_3M_pct", "n_1M"]
sec_disp = sec[[c for c in show_cols if c in sec.columns]].copy()
sec_disp = sec_disp.rename(columns={
    "rrg_score": "RRG Score", "angle_deg": "Angle°", "distance": "Distance",
    "delta_distance": "Δ Dist", "straightness": "Tail", "tail_vs_null": "Tail vs null",
    "hit_1M_pct": "1M hit %", "hit_3M_pct": "3M hit %", "n_1M": "n"})
st.dataframe(
    sec_disp, width="stretch", hide_index=True,
    column_config={
        "RRG Score": st.column_config.ProgressColumn(
            "RRG Score", min_value=0, max_value=100, format="%.0f"),
        "Angle°": st.column_config.NumberColumn(format="%.0f°"),
        "Distance": st.column_config.NumberColumn(format="%.2f"),
        "Δ Dist": st.column_config.NumberColumn(format="%+.2f"),
        "Tail": st.column_config.NumberColumn(format="%.2f"),
        "Tail vs null": st.column_config.NumberColumn(format="%.2fx"),
        "1M hit %": st.column_config.NumberColumn(format="%.1f%%"),
        "3M hit %": st.column_config.NumberColumn(format="%.1f%%"),
        "n": st.column_config.NumberColumn(format="%.0f"),
    })
b1 = 100 * base.get("1M", float("nan"))
st.caption(f"Hit rates are for the matching (quadrant × distance tercile) bucket. "
           f"Baseline is **{b1:.1f}%**, not 50% — a 51% hit rate is a real edge and "
           f"a 49% one may still be. 'Tail vs null' below 1.00× means the tail is "
           f"*less* persistent than pure noise under this transform.")

# ── Stock drill-down ─────────────────────────────────────────────────────────
st.divider()
st.subheader("🔎 Constituents vs their own sector ETF")
top_secs = tails.get("top_sectors", [])
stock_tails = tails.get("stocks", {})
cands = D["cands"]

if not top_secs or cands is None:
    st.info("No constituent output found — run `py rrg_analysis.py`.")
else:
    pick = st.selectbox("Sector", top_secs,
                        format_func=lambda s: f"{s} — "
                        f"{sec[sec['ticker']==s]['sector'].iloc[0] if (sec['ticker']==s).any() else s}")
    sub = cands[cands["sector_etf"] == pick].copy() if "sector_etf" in cands.columns \
        else pd.DataFrame()
    tm = stock_tails.get(pick, {})
    if len(sub) and tm:
        f2 = rrg_figure(tm, sub, f"{pick} constituents vs {pick}", max_names=12)
        if f2:
            st.plotly_chart(f2, width="stretch")
        cols2 = ["ticker", "rrg_score", "quadrant", "heading", "distance",
                 "delta_distance", "straightness", "setup", "hit_1M_pct",
                 "n_bucket", "R"]
        d2 = sub[[c for c in cols2 if c in sub.columns]].rename(columns={
            "rrg_score": "RRG Score", "distance": "Distance",
            "delta_distance": "Δ Dist", "straightness": "Tail",
            "setup": "Setup", "hit_1M_pct": "1M hit %", "n_bucket": "n"})
        st.dataframe(
            d2, width="stretch", hide_index=True,
            column_config={
                "RRG Score": st.column_config.ProgressColumn(
                    "RRG Score", min_value=0, max_value=100, format="%.0f"),
                "Distance": st.column_config.NumberColumn(format="%.2f"),
                "Δ Dist": st.column_config.NumberColumn(format="%+.2f"),
                "Tail": st.column_config.NumberColumn(format="%.2f"),
                "1M hit %": st.column_config.NumberColumn(format="%.1f%%"),
                "R": st.column_config.NumberColumn(format="%.2f"),
                "n": st.column_config.NumberColumn(format="%.0f"),
            })
        st.caption("**Setup** is rule-based, not an opinion: *Established leader* = "
                   f"Leading quadrant with straightness > {null_straight:.2f}; "
                   "*Improving → potential leader* = Improving with Δ Distance > 0; "
                   "*Deteriorating — avoid* = Weakening/Lagging with Δ Distance < 0.")
    else:
        st.info(f"{pick}: not enough constituent history for a stock-level RRG.")

# ── Sizing ───────────────────────────────────────────────────────────────────
st.divider()
st.subheader("💰 Position sizing — Kelly")
sz = D["sizing"]
if sz is None or not len(sz):
    st.info("No sizing output found.")
else:
    scols = ["ticker", "sector", "W_pct", "baseline_pct", "edge_pp", "R", "n",
             "exp_1M_pct", "kelly_binary_pct", "kelly_wealth_pct",
             "k_half_pct", "k_quarter_pct", "recommended_pct", "recommended_dollars"]
    d3 = sz[[c for c in scols if c in sz.columns]].rename(columns={
        "W_pct": "W %", "baseline_pct": "Baseline %", "edge_pp": "Edge pp",
        "exp_1M_pct": "Exp 1M %", "kelly_binary_pct": "Kelly % (as specified)",
        "kelly_wealth_pct": "Kelly % (of wealth)", "k_half_pct": "½ Kelly",
        "k_quarter_pct": "¼ Kelly", "recommended_pct": "Recommended %",
        "recommended_dollars": "Recommended $"})
    st.dataframe(
        d3, width="stretch", hide_index=True,
        column_config={
            "W %": st.column_config.NumberColumn(format="%.2f%%"),
            "Baseline %": st.column_config.NumberColumn(format="%.2f%%"),
            "Edge pp": st.column_config.NumberColumn(format="%+.2f"),
            "R": st.column_config.NumberColumn(format="%.2f"),
            "n": st.column_config.NumberColumn(format="%.0f"),
            "Exp 1M %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Kelly % (as specified)": st.column_config.NumberColumn(format="%.2f%%"),
            "Kelly % (of wealth)": st.column_config.NumberColumn(format="%.1f%%"),
            "½ Kelly": st.column_config.NumberColumn(format="%.2f%%"),
            "¼ Kelly": st.column_config.NumberColumn(format="%.2f%%"),
            "Recommended %": st.column_config.NumberColumn(format="%.2f%%"),
            "Recommended $": st.column_config.NumberColumn(format="$%,.0f"),
        })
    st.markdown(f"""
<div class="rrg-box">
<h4>Reading the columns</h4>
<table>
<tr><th style="width:30%">Column</th><th>What it means</th></tr>
<tr><td>Kelly&nbsp;% (as specified)</td>
    <td><code>W − (1−W)/R</code>, exactly as requested. Returns a fraction of a
        <i>bet unit whose loss is 1</i> — <b>not</b> a portfolio weight.</td></tr>
<tr><td>Kelly&nbsp;% (of wealth)</td>
    <td>The same figure divided by |mean loss|, which is the actual fraction of
        capital. Routinely exceeds 100%.
        <span class="keyline">That it does is itself the finding: full Kelly on
        1-month equity bets implies leverage nobody should run.</span></td></tr>
<tr><td>½ / ¼ Kelly</td>
    <td>Fractional Kelly after the correlation divisor, then clipped by the caps.</td></tr>
<tr><td>Recommended&nbsp;%</td>
    <td>¼ Kelly × the validation multiplier
        (<b>{cal.get('sizing_multiplier', 0):.2f}</b>), then capped.</td></tr>
</table>
<h4>Why ¼ Kelly, not ½</h4>
<table>
<tr><th style="width:30%">Reason</th><th>Evidence</th></tr>
<tr><td>Edge is unstable</td>
    <td>In-sample IR 0.60 → walk-forward 0.03. A 2× error in the estimate is
        entirely plausible.</td></tr>
<tr><td>Overbetting is ruin</td>
    <td>At 2× Kelly, log-growth is <b>exactly zero</b> — not merely worse.</td></tr>
<tr><td>¼ Kelly is cheap insurance</td>
    <td>Keeps <b>44%</b> of the growth for <b>6%</b> of the variance.</td></tr>
</table>
<p class="note">Caps bind long before Kelly does: ≤20% per position, ≤35% per
sector, leverage ≤1.0.</p>
</div>
""", unsafe_allow_html=True)

# ── Signals ──────────────────────────────────────────────────────────────────
st.divider()
st.subheader("🚦 Signals — what would change a position")
c1, c2, c3 = st.columns(3)
c1.markdown(f"""**⬆️ Increase** — all of:
- Quadrant enters **Leading**, or **Improving** with RS-Ratio rising
- **Δ Distance > 0** for 2+ consecutive weeks
- **Straightness > {null_straight:.2f}** (the simulated noise null)
- Distance **not** in the far deciles — measured forward excess peaked at the
  *low* end, so extra distance bought risk without return""")
c2.markdown(f"""**⬇️ Reduce** — any of:
- **Δ Distance** turns negative while distance sits in the top tercile
- **Straightness < {null_straight:.2f}** — the tail is less persistent than noise
- Quadrant rotates **Leading → Weakening**""")
c3.markdown("""**✖️ Exit** — any of:
- Quadrant reaches **Lagging**
- Heading persists **S / SW / SE** for 3+ weeks
- Bucket sample falls below **n = 200** — no basis left to size on""")

st.divider()
st.caption(
    "Research output, not investment advice. Sector ETFs carry no survivorship bias; "
    "the constituent panel is today's S&P 500 membership backfilled, so names that "
    "delisted out of the Lagging quadrant are absent — which flatters Lagging/Improving "
    "and inflates the win/loss ratio R, and therefore Kelly. Sources: rrg_core.py "
    "(transform), rrg_null.py (500-run baseline), rrg_validate.py (validation), "
    "rrg_analysis.py (current state)."
)
