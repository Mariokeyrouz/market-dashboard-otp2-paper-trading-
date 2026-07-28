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

st.set_page_config(page_title="RRG — Relative Rotation", page_icon="🔄", layout="wide")

st.markdown("""
<style>
    [data-testid="stMetricDelta"] svg { display: none; }
    .rrg-box { background: #0d1b2a; border-left: 5px solid #4a9eff;
               padding: 14px 18px; border-radius: 6px; margin-bottom: 14px; }
    .verdict-fail { background: #2a1a00; border-left: 5px solid #ffa726;
                    padding: 14px 18px; border-radius: 6px; margin-bottom: 14px; }
    .verdict-pass { background: #04231a; border-left: 5px solid #00c896;
                    padding: 14px 18px; border-radius: 6px; margin-bottom: 14px; }
</style>
""", unsafe_allow_html=True)

SECTOR_CSV = "rrg_sector_results.csv"
STOCK_CSV = "rrg_stock_results.csv"
CAND_CSV = "rrg_stock_candidates.csv"
CAL_JSON = "rrg_calibration.json"
TAILS_JSON = "rrg_tails.json"
VAL_CSV = "rrg_validation_results.csv"

QUAD_COLOR = {"Leading": "#00c896", "Weakening": "#ffd166",
              "Lagging": "#ff4b4b", "Improving": "#4a9eff", "—": "#888888"}


@st.cache_data(ttl=900)
def load_all():
    out = {}
    for key, path in (("sectors", SECTOR_CSV), ("sizing", STOCK_CSV),
                      ("cands", CAND_CSV), ("val", VAL_CSV)):
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
<b>Reading the two Kelly columns.</b> <code>Kelly % (as specified)</code> is
<code>W − (1−W)/R</code> exactly as requested. That expression returns a fraction of a
<i>bet unit whose loss is 1</i>, not a portfolio weight — dividing by |mean loss| gives
<code>Kelly % (of wealth)</code>, which routinely exceeds 100%. That it does is itself the
finding: full Kelly on 1-month equity bets implies leverage no one should run, which is
why the caps (≤20% per position, ≤35% per sector, leverage ≤1.0) and the fractional
multiplier bind long before Kelly does.<br><br>
<b>¼ Kelly, not ½.</b> At 2× Kelly log-growth is <i>exactly zero</i>; ¼ Kelly keeps 44% of
the growth for 6% of the variance and survives a 2× error in the edge estimate — and the
estimate here is unstable (in-sample IR 0.60 → walk-forward 0.03). The recommended column
additionally applies the validation multiplier of
<b>{cal.get('sizing_multiplier', 0):.2f}</b>.
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
