"""
Macro Signal Dashboard — three-layer signal hierarchy (FIRST PASS).

Layer 1 (Regime)   — slow, backward-looking macro context badge.
Layer 2 (The Hinge)— THE CENTERPIECE: 10Y nominal yield decomposed into real +
                     breakeven legs, classified as "Inflation Scare" vs.
                     "Growth/Tightening Shock". Daily-decision layer.
Layer 3 (Tripwires)— faster confirming signals: HY OAS, DXY, vol term structure.

Visuals match app.py's warm-paper theme. All data is MOCK (see macro_data.py);
the classification rules live in macro_logic.py. This page is intentionally a
"dumb" renderer of those two modules.
"""

import streamlit as st
import streamlit.components.v1 as components

import macro_data as mdata
import macro_logic as mlogic

st.set_page_config(
    page_title="Macro Dashboard",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  #MainMenu, header, footer { visibility: hidden; }
  .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
</style>
""", unsafe_allow_html=True)

# ── Pull mock data + run classifiers ──────────────────────────────────────────
hinge      = mdata.layer2_hinge()
fci        = mdata.financial_conditions()
regime_in  = mdata.layer1_regime()
trip       = mdata.layer3_tripwires()

hinge_cls  = mlogic.classify_hinge(hinge)
regime_cls = mlogic.classify_regime(regime_in)
vol_cls    = mlogic.vol_curve_state(trip["vix_term"]["front"], trip["vix_term"]["back"])

# Round 2 panels
growth     = mdata.growth_nowcast()
rcp        = mdata.rates_curve_policy()
commod     = mdata.commodities_impulse()
liqc       = mdata.liquidity_credit()
fx         = mdata.fx_panel()
xasset     = mdata.cross_asset()
goldreal   = mdata.gold_real_overlay()

curve_2s10s_cls = mlogic.curve_state(rcp["slope_2s10s"]["level"])
curve_3m10y_cls = mlogic.curve_state(rcp["slope_3m10y"]["level"])
cg_cls          = mlogic.copper_gold_signal(growth["copper_gold_ratio"]["series"])
liq_cls         = mlogic.liquidity_state(liqc["net_liquidity"]["trend"])
cmd_cls         = mlogic.commodity_impulse(commod["commodity_index"]["chg"])

# ── Small formatting helpers ──────────────────────────────────────────────────
def pp(v):           # percentage-point change, signed
    return f"{'+' if v >= 0 else '−'}{abs(v):.2f} pp"

def arrow(v):
    return "▲" if v >= 0 else "▼"

def sign_col(v, good_when_up=True):
    up = v >= 0
    pos, neg = "#2f8f5b", "#c14a32"
    return (pos if up else neg) if good_when_up else (neg if up else pos)


# ── Multi-series decomposition chart (static SVG, rendered server-side) ────────
def decomp_chart(series_list, W=640, H=250, pad_t=16, pad_b=26, pad_l=6, pad_r=58):
    """series_list: list of {'data':[...], 'color':str, 'label':str}."""
    all_vals = [v for s in series_list for v in s["data"]]
    mn, mx = min(all_vals), max(all_vals)
    rng = (mx - mn) or 1.0
    # pad the scale a touch so lines aren't glued to the frame
    mn -= rng * 0.12
    mx += rng * 0.12
    rng = mx - mn
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    def xy(i, n, v):
        x = pad_l + (i / (n - 1) * plot_w if n > 1 else 0)
        y = pad_t + (1 - (v - mn) / rng) * plot_h
        return x, y

    # horizontal gridlines (4 bands)
    grid = ""
    for g in range(5):
        gy = pad_t + g / 4 * plot_h
        gval = mx - g / 4 * rng
        grid += (f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + plot_w}" y2="{gy:.1f}" '
                 f'stroke="#efe8da" stroke-width="1"/>'
                 f'<text x="{pad_l + plot_w + 6}" y="{gy + 3:.1f}" font-size="9" '
                 f'fill="#a99f8c" font-family="IBM Plex Mono,monospace">{gval:.2f}</text>')

    paths = ""
    for s in series_list:
        data, color = s["data"], s["color"]
        n = len(data)
        coords = [xy(i, n, v) for i, v in enumerate(data)]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        lx, ly = coords[-1]
        paths += (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.1" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>'
                  f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.4" fill="{color}" '
                  f'stroke="#fff" stroke-width="1.5"/>'
                  f'<text x="{lx - 6:.1f}" y="{ly - 7:.1f}" font-size="10" font-weight="600" '
                  f'fill="{color}" text-anchor="end" '
                  f'font-family="IBM Plex Mono,monospace">{data[-1]:.2f}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" '
            f'preserveAspectRatio="none" style="overflow:visible;">{grid}{paths}</svg>')


# ── Shared small builders for the Round-2 panels ──────────────────────────────
def mini_spark(series, color, W=116, H=30, pad=4):
    """Tiny inline sparkline (no axes) for compact rows/tiles."""
    if not series or len(series) < 2:
        return ""
    mn, mx = min(series), max(series)
    rng = (mx - mn) or 1.0
    n = len(series)
    pts = [(pad + i / (n - 1) * (W - 2 * pad), pad + (1 - (v - mn) / rng) * (H - 2 * pad))
           for i, v in enumerate(series)]
    d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    lx, ly = pts[-1]
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" preserveAspectRatio="none" style="overflow:visible;">'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2" fill="{color}"/></svg>')


def chg_span(chg, suffix="", good_when_up=True, dp=2, size=10):
    """Signed, arrow-prefixed, color-coded change span."""
    return (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:{size}px;'
            f'color:{sign_col(chg, good_when_up)};">{arrow(chg)}{abs(chg):.{dp}f}{suffix}</span>')


def kpi_tile(label, value_html, sub_html=""):
    """Small label / big value / sub-line tile (warm-paper inset)."""
    return (f'<div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;'
            f'display:flex;flex-direction:column;gap:2px;min-width:0;">'
            f'<div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:16px;font-weight:600;color:#1d1a15;line-height:1.05;">{value_html}</div>'
            f'{sub_html}</div>')


def state_chip(cls):
    """Colored state pill from a {label,color} classifier dict."""
    return (f'<span style="background:{cls["color"]}1a;border:1px solid {cls["color"]}55;color:{cls["color"]};'
            f'font-size:10px;font-weight:600;border-radius:5px;padding:2px 8px;letter-spacing:0.02em;">{cls["label"]}</span>')


def section_label(title, subtitle=""):
    sub = (f'<span style="font-size:10.5px;color:#8a7f6a;font-style:italic;">{subtitle}</span>'
           if subtitle else "")
    return (f'<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px;flex-wrap:wrap;">'
            f'<span style="font-family:\'Spectral\',serif;font-size:15px;font-weight:600;color:#211d18;">{title}</span>{sub}</div>')


def asset_row(name, level, chg, level_fmt="{:.2f}", chg_suffix="", good_when_up=True, spark=None, spark_color="#8a7f6a"):
    """One compact name / level / change / spark row for the Commodities & FX panels."""
    spark_html = (f'<div style="width:80px;flex-shrink:0;">{mini_spark(spark, spark_color, W=80, H=22)}</div>'
                  if spark else '<div style="width:80px;flex-shrink:0;"></div>')
    return (f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #f3eddf;">'
            f'<span style="flex:1;font-size:11px;color:#4a443b;white-space:nowrap;">{name}</span>'
            f'{spark_html}'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;font-weight:600;color:#1d1a15;width:64px;text-align:right;">{level_fmt.format(level)}</span>'
            f'<span style="width:54px;text-align:right;">{chg_span(chg, chg_suffix, good_when_up)}</span>'
            f'</div>')


def heatmap_cell(val, dp=2, suffix="%"):
    """Cross-asset heatmap cell — green/red shaded by magnitude (cap ±5)."""
    cap = 5.0
    a = min(abs(val) / cap, 1.0) * 0.46 + 0.06
    bg = f"rgba(47,143,91,{a:.2f})" if val >= 0 else f"rgba(193,74,50,{a:.2f})"
    return (f'<td style="text-align:right;padding:6px 9px;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:11px;background:{bg};color:#1d1a15;white-space:nowrap;">'
            f'{"+" if val >= 0 else "−"}{abs(val):.{dp}f}{suffix}</td>')


# ── Mock-data banner (only while macro_data.MOCK is True) ──────────────────────
mock_banner = ""
if getattr(mdata, "MOCK", False):
    mock_banner = (
        '<div style="display:flex;align-items:center;gap:8px;background:#fbf1e3;'
        'border:1px solid #e7cfa6;border-radius:8px;padding:8px 13px;margin-bottom:14px;">'
        '<span style="font-size:12px;">🧪</span>'
        '<span style="font-size:11.5px;color:#9a7434;font-weight:600;letter-spacing:0.02em;">'
        'MOCK DATA — placeholder values for layout &amp; logic review. Not live market levels.</span>'
        '</div>'
    )

# ── Header ────────────────────────────────────────────────────────────────────
disclaimer = (
    "The Layer-2 signal hierarchy and Inflation-Scare vs. Growth-Shock "
    "classification are opinionated and style-dependent — calibrated to a "
    "macro-positional, stagflation-leaning book. A lens, not objective fact."
)
header = f'''
<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:14px;">
  <div style="display:flex;flex-direction:column;gap:3px;">
    <div style="display:flex;align-items:center;gap:10px;">
      <div style="width:26px;height:26px;border-radius:6px;background:#2b2620;display:flex;align-items:center;justify-content:center;color:#ece5d8;font-family:'Spectral',serif;font-weight:700;font-size:15px;">M</div>
      <div style="font-family:'Spectral',serif;font-weight:600;font-size:23px;letter-spacing:-0.01em;color:#211d18;">Macro Signal Dashboard</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:500;letter-spacing:0.08em;color:#8a7f5f;border:1px solid #d8cdb6;border-radius:4px;padding:2px 6px;background:#f4eedf;">OTP2.0</div>
      <span title="{disclaimer}" style="cursor:help;font-size:11px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;background:#f4eedf;">i</span>
    </div>
    <div style="font-size:11.5px;color:#7c7264;letter-spacing:0.01em;padding-left:36px;">Regime · The Hinge · Tripwires — a three-layer signal hierarchy, each on its own update clock</div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="display:flex;align-items:center;gap:8px;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:8px;padding:7px 12px;">
      <span id="nyse-dot" style="width:7px;height:7px;border-radius:50%;background:#a99f8c;display:inline-block;flex-shrink:0;"></span>
      <div style="display:flex;flex-direction:column;line-height:1.15;">
        <span style="font-size:9px;font-weight:600;letter-spacing:0.1em;color:#a99f8c;text-transform:uppercase;">NYSE · ET</span>
        <span id="et-time" style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500;color:#2b2620;">--:--:--</span>
      </div>
      <span id="nyse-status" style="font-size:10px;font-weight:600;color:#a99f8c;padding-left:2px;">--</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:8px;padding:7px 12px;">
      <div style="display:flex;flex-direction:column;line-height:1.15;">
        <span style="font-size:9px;font-weight:600;letter-spacing:0.1em;color:#a99f8c;text-transform:uppercase;">Local</span>
        <span id="local-time" style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500;color:#2b2620;">--:--:--</span>
      </div>
    </div>
  </div>
</div>
'''

# ── Layer 1 — Regime badge + Growth Nowcast (row) ─────────────────────────────
regime_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:13px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:10px;min-width:0;">
  <div style="display:flex;flex-direction:column;gap:2px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Layer 1 · Regime</span>
    <span style="font-size:9px;color:#b3a890;">Monthly clock · backward-looking context</span>
  </div>
  <div style="display:flex;align-items:center;gap:9px;background:{regime_cls['color']}1a;border:1px solid {regime_cls['color']}55;border-radius:7px;padding:8px 14px;">
    <span style="width:9px;height:9px;border-radius:50%;background:{regime_cls['color']};"></span>
    <span style="font-family:'Spectral',serif;font-size:18px;font-weight:600;color:{regime_cls['color']};">{regime_cls['label']}</span>
  </div>
  <span style="font-size:11px;color:#6b6256;line-height:1.4;">{regime_cls['note']}</span>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:6px 11px;text-align:center;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.06em;">CPI Headline</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#1d1a15;">{regime_in['cpi_headline']:.1f}%</div>
    </div>
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:6px 11px;text-align:center;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.06em;">CPI Core</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#1d1a15;">{regime_in['cpi_core']:.1f}%</div>
    </div>
  </div>
</div>
'''

# Growth Nowcast — flesh out the regime layer with activity reads
_citi = growth["citi_surprise"]
_ismm = growth["ism_mfg"]
_isms = growth["ism_services"]
_claims = growth["jobless_claims"]
_cg = growth["copper_gold_ratio"]
_ismm_col = "#c14a32" if _ismm["level"] < 50 else "#2f8f5b"
_isms_col = "#c14a32" if _isms["level"] < 50 else "#2f8f5b"
_claims_col = "#c14a32" if _claims["trend"] == "rising" else "#2f8f5b"
_citi_col = "#2f8f5b" if _citi >= 0 else "#c14a32"

growth_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:13px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:9px;min-width:0;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Growth Nowcast</span>
    <span style="font-size:9px;color:#b3a890;">activity &amp; inflation reads feeding the regime</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
    {kpi_tile("Citi Surprise", f'<span style="color:{_citi_col};">{_citi:+.0f}</span>', '<div style="font-size:9px;color:#a99f8c;">data vs. expectations</div>')}
    {kpi_tile("ISM Mfg", f'<span style="color:{_ismm_col};">{_ismm["level"]:.1f}</span>', f'<div style="font-size:9px;color:#a99f8c;">{chg_span(_ismm["chg"], dp=1, size=9)} · &lt;50 contracts</div>')}
    {kpi_tile("ISM Services", f'<span style="color:{_isms_col};">{_isms["level"]:.1f}</span>', f'<div style="font-size:9px;color:#a99f8c;">{chg_span(_isms["chg"], dp=1, size=9)}</div>')}
    {kpi_tile("Jobless Claims", f'{_claims["level"]}k', f'<div style="font-size:9px;color:{_claims_col};">{_claims["trend"]}</div>')}
    <div style="grid-column:span 2;background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;display:flex;align-items:center;justify-content:space-between;gap:8px;">
      <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
        <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">Copper / Gold ratio</div>
        <div style="display:flex;align-items:center;gap:7px;">{state_chip(cg_cls)}<span style="font-size:9px;color:#a99f8c;">growth-vs-fear tilt</span></div>
      </div>
      {mini_spark(_cg["series"], cg_cls["color"], W=90, H=26)}
    </div>
  </div>
</div>
'''

layer1_row = f'''
<div style="display:grid;grid-template-columns:1.05fr 2fr;gap:12px;align-items:stretch;margin-bottom:12px;">
  {regime_card}
  {growth_card}
</div>
'''

# ── Layer 2 — The Hinge (centerpiece) ─────────────────────────────────────────
chart_svg = decomp_chart([
    {"data": hinge["nominal_series"],   "color": "#2b2620", "label": "Nominal"},
    {"data": hinge["real_series"],      "color": "#3a6ea5", "label": "Real (TIPS)"},
    {"data": hinge["breakeven_series"], "color": "#c08a2d", "label": "Breakeven"},
])

def hinge_legend_item(color, label, level, chg):
    return (f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<span style="width:14px;height:3px;border-radius:2px;background:{color};"></span>'
            f'<span style="font-size:11px;color:#4a443b;">{label}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;font-weight:600;color:#1d1a15;">{level:.2f}%</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:{sign_col(chg)};">{arrow(chg)}{abs(chg):.2f}</span>'
            f'</div>')

legend = (
    hinge_legend_item("#2b2620", "Nominal 10Y", hinge["nominal"]["level"], hinge["nominal"]["chg"])
    + hinge_legend_item("#3a6ea5", "Real (TIPS)", hinge["real"]["level"], hinge["real"]["chg"])
    + hinge_legend_item("#c08a2d", "Breakeven", hinge["breakeven"]["level"], hinge["breakeven"]["chg"])
)

# implication tag chips
tag_chips = "".join(
    f'<span style="background:{hinge_cls["color"]}1a;border:1px solid {hinge_cls["color"]}55;color:{hinge_cls["color"]};'
    f'font-size:10px;font-weight:600;border-radius:5px;padding:3px 9px;letter-spacing:0.02em;">{t}</span>'
    for t in hinge_cls["tags"]
)

dom = hinge_cls.get("dominant")
dom_label = {"breakeven": "Breakeven leg", "real": "Real-yield leg", None: "No dominant leg"}[dom]

# FCI gauge — map NFCI roughly [-1.5 .. +1.5] to 0..100, center 50 = neutral
fci_level = fci["level"]
fci_pos = max(0, min(100, (fci_level + 1.5) / 3.0 * 100))
fci_looser = fci_level < 0
fci_col = "#2f8f5b" if fci_looser else "#c14a32"
fci_word = "Looser than avg" if fci_looser else "Tighter than avg"

classification_banner = f'''
<div style="background:{hinge_cls['color']}14;border:1px solid {hinge_cls['color']}55;border-left:4px solid {hinge_cls['color']};border-radius:9px;padding:14px 16px;display:flex;flex-direction:column;gap:9px;">
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:9.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Classification</span>
    <span title="{disclaimer}" style="cursor:help;font-size:9px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:14px;height:14px;display:inline-flex;align-items:center;justify-content:center;">i</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="width:11px;height:11px;border-radius:50%;background:{hinge_cls['color']};"></span>
    <span style="font-family:'Spectral',serif;font-size:25px;font-weight:700;color:{hinge_cls['color']};line-height:1.05;">{hinge_cls['label']}</span>
  </div>
  <div style="font-size:11.5px;color:#5a5247;line-height:1.45;">{hinge_cls['note']}</div>
  <div style="display:flex;gap:6px;flex-wrap:wrap;">{tag_chips}</div>
  <div style="font-size:10px;color:#a99f8c;border-top:1px solid #ece3d2;padding-top:7px;">
    Dominant mover: <span style="color:#6b6256;font-weight:600;">{dom_label}</span>
    · lookback {hinge['lookback_days']}d · v1 rule: larger absolute leg move
  </div>
</div>
'''

fci_card = f'''
<div style="display:flex;flex-direction:column;gap:8px;background:#faf6ee;border:1px solid #efe7d7;border-radius:9px;padding:13px 15px;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <span style="font-size:9.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Financial Conditions</span>
    <span style="font-size:9px;color:#b3a890;">daily · forward-looking</span>
  </div>
  <div style="display:flex;align-items:baseline;gap:8px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;font-weight:600;color:{fci_col};">{fci_level:+.2f}</span>
    <span style="font-size:11px;color:{fci_col};font-weight:600;">{fci_word}</span>
  </div>
  <div style="height:8px;background:#efe8da;border-radius:5px;position:relative;">
    <div style="position:absolute;left:50%;top:-2px;width:1px;height:12px;background:#c3b9a4;"></div>
    <div style="position:absolute;left:{min(fci_pos,50):.1f}%;width:{abs(fci_pos-50):.1f}%;height:100%;background:{fci_col};border-radius:5px;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:9px;color:#a99f8c;">
    <span>◄ looser</span><span>neutral</span><span>tighter ►</span>
  </div>
  <div style="font-size:10px;color:#a99f8c;">Change over window: {pp(fci['chg'])}</div>
</div>
'''

hinge_section = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:16px 17px;box-shadow:0 1px 3px rgba(70,55,25,0.05);margin-bottom:12px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:6px;">
    <div style="display:flex;align-items:baseline;gap:10px;">
      <span style="font-family:'Spectral',serif;font-size:17px;font-weight:600;color:#211d18;">Layer 2 · The Hinge</span>
      <span style="font-size:11px;color:#8a7f6a;font-style:italic;">10Y nominal = real yield + breakeven inflation</span>
    </div>
    <span style="font-size:9.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#2f8f5b;background:#edf7f1;border:1px solid #c3e6d1;border-radius:5px;padding:3px 9px;">Daily clock · checked daily</span>
  </div>
  <div style="display:grid;grid-template-columns:1.55fr 1fr;gap:16px;align-items:start;">
    <div style="min-width:0;">
      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px;">{legend}</div>
      {chart_svg}
    </div>
    <div style="display:flex;flex-direction:column;gap:11px;">
      {classification_banner}
      {fci_card}
    </div>
  </div>
</div>
'''

# ── Layer 3 — Tripwire row ────────────────────────────────────────────────────
def tripwire_tile(title, framing, big_html, state_html):
    return f'''
    <div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:7px;min-width:0;">
      <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">{title}</div>
      <div style="font-size:10.5px;color:#8a7f6a;font-style:italic;line-height:1.35;">{framing}</div>
      <div>{big_html}</div>
      <div style="margin-top:auto;">{state_html}</div>
    </div>
    '''

hy = trip["hy_oas"]
hy_big = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:26px;font-weight:600;color:#1d1a15;">{hy["level"]:.2f}%</span>'
          f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:{sign_col(hy["chg"], good_when_up=False)};margin-left:8px;">{arrow(hy["chg"])}{abs(hy["chg"]):.2f} pp</span>')
hy_state = ('<span style="font-size:10.5px;color:#6b6256;">Widening spreads = rising stress; '
            'a leading tell for equity risk.</span>')

dxy = trip["dxy"]
dxy_big = (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:26px;font-weight:600;color:#1d1a15;">{dxy["level"]:.1f}</span>'
           f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:12px;color:{sign_col(dxy["chg"], good_when_up=False)};margin-left:8px;">{arrow(dxy["chg"])}{abs(dxy["chg"]):.2f}</span>')
dxy_state = ('<span style="font-size:10.5px;color:#6b6256;">The global liquidity valve — '
             'a stronger dollar tightens conditions abroad.</span>')

vt = trip["vix_term"]
vol_big = (f'<span style="font-family:\'Spectral\',serif;font-size:22px;font-weight:700;color:{vol_cls["color"]};">{vol_cls["label"]}</span>'
           f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:#8a7f6a;margin-left:8px;">{vt["front"]:.1f} → {vt["back"]:.1f}</span>')
vol_state = f'<span style="font-size:10.5px;color:#6b6256;">{vol_cls["note"]}</span>'

tripwire_row = f'''
<div style="margin-bottom:6px;display:flex;align-items:baseline;gap:10px;">
  <span style="font-family:'Spectral',serif;font-size:15px;font-weight:600;color:#211d18;">Layer 3 · Tripwires</span>
  <span style="font-size:11px;color:#8a7f6a;font-style:italic;">faster confirming signals — directional, not mechanically precise</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px;">
  {tripwire_tile("Credit Spreads · HY OAS", "Leading indicator for equity stress", hy_big, hy_state)}
  {tripwire_tile("Dollar Index · DXY", "Global liquidity valve", dxy_big, dxy_state)}
  {tripwire_tile("Vol Term Structure", "Contango / backwardation tripwire", vol_big, vol_state)}
</div>
'''

# ── Layer-2 context row: Rates/Curve/Policy + Gold-vs-Real-Yield ──────────────
_fed = rcp["fed_funds"]
_cuts = rcp["implied_cuts"]
_move = rcp["move_index"]

rates_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:10px;min-width:0;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Rates, Curve &amp; Policy</span>
    <span style="font-size:10px;color:#8a7f6a;font-style:italic;">the policy force behind the real-yield leg</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;display:flex;flex-direction:column;gap:3px;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">2s10s slope</div>
      <div style="display:flex;align-items:baseline;gap:6px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#1d1a15;">{rcp['slope_2s10s']['level']:+.2f}</span>{state_chip(curve_2s10s_cls)}</div>
    </div>
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;display:flex;flex-direction:column;gap:3px;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">3m10y slope</div>
      <div style="display:flex;align-items:baseline;gap:6px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#1d1a15;">{rcp['slope_3m10y']['level']:+.2f}</span>{state_chip(curve_3m10y_cls)}</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;background:#f7f2e8;border:1px solid #ece2cf;border-radius:7px;padding:8px 11px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:10px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">Fed Funds</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;color:#2b2620;">{_fed['low']:.2f}–{_fed['high']:.2f}%</span>
    </div>
    <span style="font-size:11px;color:#6b6256;">Implied: <span style="font-weight:600;color:#2f8f5b;">{_cuts['count']} cuts (~{_cuts['bps']} bps)</span> {_cuts['horizon']}</span>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
    <div style="display:flex;flex-direction:column;">
      <span style="font-size:10px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">MOVE index</span>
      <span style="font-size:9px;color:#a99f8c;">the bond market's VIX (rate vol)</span>
    </div>
    <div style="display:flex;align-items:baseline;gap:7px;">
      <span style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:600;color:#1d1a15;">{_move['level']:.0f}</span>
      {chg_span(_move['chg'], good_when_up=False, dp=1, size=11)}
    </div>
  </div>
</div>
'''

goldreal_chart = decomp_chart([
    {"data": goldreal["gold_index"], "color": "#c08a2d", "label": "Gold"},
    {"data": goldreal["real_index"], "color": "#3a6ea5", "label": "Real yield"},
], H=170, pad_r=46)

goldreal_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:8px;min-width:0;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Gold vs Real Yield</span>
    <span style="font-size:10px;color:#8a7f6a;font-style:italic;">gold as a real-rate play</span>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:6px;"><span style="width:14px;height:3px;border-radius:2px;background:#c08a2d;"></span><span style="font-size:11px;color:#4a443b;">Gold</span><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#1d1a15;">${goldreal['gold_level']:,.0f}</span></div>
    <div style="display:flex;align-items:center;gap:6px;"><span style="width:14px;height:3px;border-radius:2px;background:#3a6ea5;"></span><span style="font-size:11px;color:#4a443b;">10Y Real</span><span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#1d1a15;">{goldreal['real_level']:.2f}%</span></div>
  </div>
  <div style="font-size:9px;color:#a99f8c;">indexed to 100 at window start</div>
  {goldreal_chart}
  <div style="font-size:10px;color:#6b6256;border-top:1px solid #ece3d2;padding-top:7px;">Typically <span style="font-weight:600;">{goldreal['relationship']}</span> — gold tends to rise when real yields fall. Directional only.</div>
</div>
'''

layer2_context_row = f'''
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:stretch;margin-bottom:14px;">
  {rates_card}
  {goldreal_card}
</div>
'''

# ── Layer-3 support row: Commodities · Liquidity & Credit · FX ─────────────────
commod_rows = (
    asset_row("Oil (WTI)",      commod["wti"]["level"],      commod["wti"]["chg"],      "{:.2f}", "%", spark=commod["wti"]["series"], spark_color="#c14a32")
    + asset_row("Brent",        commod["brent"]["level"],    commod["brent"]["chg"],    "{:.2f}", "%", spark=commod["brent"]["series"], spark_color="#c14a32")
    + asset_row("Gasoline",     commod["gasoline"]["level"], commod["gasoline"]["chg"], "{:.2f}", "%", spark=commod["gasoline"]["series"], spark_color="#c2703a")
    + asset_row("Copper",       commod["copper"]["level"],   commod["copper"]["chg"],   "{:.3f}", "%", spark=commod["copper"]["series"], spark_color="#c2703a")
    + asset_row("Gold",         commod["gold"]["level"],     commod["gold"]["chg"],     "{:,.0f}", "%", spark=commod["gold"]["series"], spark_color="#c08a2d")
    + asset_row("Commodity ix", commod["commodity_index"]["level"], commod["commodity_index"]["chg"], "{:.1f}", "%", spark=commod["commodity_index"]["series"], spark_color="#8a7f6a")
)
commod_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:7px;min-width:0;">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Commodities</span>
    {state_chip(cmd_cls)}
  </div>
  <div style="font-size:10.5px;color:#8a7f6a;font-style:italic;line-height:1.35;">Inflation impulse — the real-economy driver of breakevens</div>
  <div>{commod_rows}</div>
</div>
'''

_nl = liqc["net_liquidity"]
liq_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:9px;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Liquidity &amp; Credit</div>
  <div style="font-size:10.5px;color:#8a7f6a;font-style:italic;line-height:1.35;">the plumbing behind financial conditions</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
    {kpi_tile("HY OAS", f'{liqc["hy_oas"]["level"]:.2f}%', f'<div style="font-size:9px;color:#a99f8c;">{chg_span(liqc["hy_oas"]["chg"], " pp", good_when_up=False, size=9)}</div>')}
    {kpi_tile("IG OAS", f'{liqc["ig_oas"]["level"]:.2f}%', f'<div style="font-size:9px;color:#a99f8c;">{chg_span(liqc["ig_oas"]["chg"], " pp", good_when_up=False, size=9)}</div>')}
  </div>
  <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;display:flex;align-items:center;justify-content:space-between;gap:8px;">
    <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">Fed net liquidity</div>
      <div style="display:flex;align-items:baseline;gap:6px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:600;color:#1d1a15;">${_nl['level']:.2f}T</span>{state_chip(liq_cls)}</div>
      <div style="font-size:8.5px;color:#a99f8c;">balance sheet − RRP − TGA</div>
    </div>
    {mini_spark(_nl["series"], liq_cls["color"], W=84, H=30)}
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;font-size:11px;">
    <span style="color:#6b6256;">Bank reserves</span>
    <span style="font-family:'IBM Plex Mono',monospace;color:#1d1a15;font-weight:600;">${liqc['bank_reserves']['level']:.2f}T <span style="color:#a99f8c;font-weight:400;font-size:9px;">{liqc['bank_reserves']['trend']}</span></span>
  </div>
</div>
'''

fx_rows = (
    asset_row("DXY",     fx["dxy"]["level"],    fx["dxy"]["chg"],    "{:.2f}", "",  good_when_up=False)
    + asset_row("USD/JPY", fx["usdjpy"]["level"], fx["usdjpy"]["chg"], "{:.2f}", "",  good_when_up=False)
    + asset_row("EUR/USD", fx["eurusd"]["level"], fx["eurusd"]["chg"], "{:.4f}", "%", good_when_up=True)
    + asset_row("USD/CNH", fx["usdcnh"]["level"], fx["usdcnh"]["chg"], "{:.3f}", "",  good_when_up=False)
    + asset_row("EM FX",   fx["em_fx"]["level"],  fx["em_fx"]["chg"],  "{:.1f}", "%", good_when_up=True)
)
fx_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;gap:7px;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">FX</div>
  <div style="font-size:10.5px;color:#8a7f6a;font-style:italic;line-height:1.35;">global liquidity / carry lens</div>
  <div>{fx_rows}</div>
  <div style="font-size:9px;color:#a99f8c;">Green = supportive for risk (weaker USD / firmer EM). Directional.</div>
</div>
'''

layer3_support_row = f'''
<div style="display:grid;grid-template-columns:1.1fr 1fr 0.95fr;gap:12px;align-items:stretch;margin-bottom:16px;">
  {commod_card}
  {liq_card}
  {fx_card}
</div>
'''

# ── Cross-Asset Heatmap (full width) ──────────────────────────────────────────
def xasset_row_html(r):
    return (f'<tr>'
            f'<td style="text-align:left;padding:6px 10px;font-size:11.5px;color:#2b2620;white-space:nowrap;">{r["name"]}</td>'
            f'<td style="text-align:right;padding:6px 10px;font-family:\'IBM Plex Mono\',monospace;font-size:11.5px;color:#1d1a15;white-space:nowrap;">{r["level"]:,.2f}</td>'
            f'{heatmap_cell(r["d1"])}{heatmap_cell(r["d1w"])}{heatmap_cell(r["d1m"])}{heatmap_cell(r["ytd"])}'
            f'<td style="padding:4px 10px;width:90px;">{mini_spark(r["spark"], "#8a7f6a", W=90, H=22)}</td>'
            f'</tr>')

xasset_rows = "".join(xasset_row_html(r) for r in xasset)
cross_asset_section = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);margin-bottom:16px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:8px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Cross-Asset</span>
    <span style="font-size:10px;color:#8a7f6a;font-style:italic;">one-glance positioning · % change by horizon</span>
  </div>
  <table style="width:100%;border-collapse:collapse;">
    <thead><tr style="font-size:9px;color:#a99f8c;text-transform:uppercase;letter-spacing:0.06em;">
      <th style="text-align:left;padding:4px 10px;font-weight:600;">Asset</th>
      <th style="text-align:right;padding:4px 10px;font-weight:600;">Level</th>
      <th style="text-align:right;padding:4px 9px;font-weight:600;">1D</th>
      <th style="text-align:right;padding:4px 9px;font-weight:600;">1W</th>
      <th style="text-align:right;padding:4px 9px;font-weight:600;">1M</th>
      <th style="text-align:right;padding:4px 9px;font-weight:600;">YTD</th>
      <th style="text-align:left;padding:4px 10px;font-weight:600;">Trend</th>
    </tr></thead>
    <tbody>{xasset_rows}</tbody>
  </table>
  <div style="font-size:9px;color:#a99f8c;margin-top:6px;">Equities/commodities/FX shown as % change; 10Y UST shown as yield change (pp).</div>
</div>
'''

# ── Footer ────────────────────────────────────────────────────────────────────
footer = (
    '<div style="font-size:10px;color:#a99f8c;text-align:center;letter-spacing:0.03em;">'
    'All values are MOCK placeholders (macro_data.py) · '
    'classification logic is opinionated and style-dependent · '
    'lead/lag relationships are directional, no validated hit-rates implied'
    '</div>'
)

# ── Live-clock JS (plain string — no f-string, literal braces) ────────────────
clock_js = """
<script>
function isNYSEHoliday(d) {
  const y = d.getFullYear(), m = d.getMonth()+1, day = d.getDate(), dow = d.getDay();
  function nthDow(yr, mo, weekday, n){let count=0;for(let i=1;i<=31;i++){const dt=new Date(yr,mo-1,i);if(dt.getMonth()!==mo-1)break;if(dt.getDay()===weekday&&++count===n)return i;}}
  function lastMon(yr, mo){for(let i=31;i>=1;i--){const dt=new Date(yr,mo-1,i);if(dt.getMonth()!==mo-1)continue;if(dt.getDay()===1)return i;}}
  function goodFriday(yr){const a=yr%19,b=Math.floor(yr/100),c=yr%100,d2=Math.floor(b/4),e=b%4;const f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d2-g+15)%30;const i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7;const m2=Math.floor((a+11*h+22*l)/451);const mo2=Math.floor((h+l-7*m2+114)/31),dy=(h+l-7*m2+114)%31+1;const easter=new Date(yr,mo2-1,dy);easter.setDate(easter.getDate()-2);return{m:easter.getMonth()+1,d:easter.getDate()};}
  if(dow===0||dow===6)return true;
  function observed(mo2,dy2){const dt=new Date(y,mo2-1,dy2);const w=dt.getDay();if(w===6)return{m:mo2,d:dy2-1};if(w===0)return{m:mo2,d:dy2+1};return{m:mo2,d:dy2};}
  const gf=goodFriday(y);
  const holidays=[observed(1,1),{m:1,d:nthDow(y,1,1,3)},{m:2,d:nthDow(y,2,1,3)},gf,{m:5,d:lastMon(y,5)},observed(6,19),observed(7,4),{m:9,d:nthDow(y,9,1,1)},{m:11,d:nthDow(y,11,4,4)},observed(12,25)];
  return holidays.some(h2 => h2 && h2.m===m && h2.d===day);
}
function tick(){
  const now=new Date();
  document.getElementById('local-time').textContent=now.toLocaleTimeString('en-US',{hour12:false});
  const etOpts={timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false};
  document.getElementById('et-time').textContent=now.toLocaleTimeString('en-US',etOpts);
  const etDate=new Date(now.toLocaleString('en-US',{timeZone:'America/New_York'}));
  const dow=etDate.getDay(),h=etDate.getHours();
  const open=dow>=1&&dow<=5&&h>=9&&h<16&&!isNYSEHoliday(etDate);
  const dot=document.getElementById('nyse-dot'),lbl=document.getElementById('nyse-status');
  dot.style.background=open?'#2f8f5b':'#c14a32';
  dot.style.boxShadow=open?'0 0 0 3px rgba(47,143,91,0.2)':'0 0 0 3px rgba(193,74,50,0.2)';
  lbl.textContent=open?'OPEN':'CLOSED';
  lbl.style.color=open?'#2f8f5b':'#c14a32';
}
setInterval(tick,1000);tick();
</script>
"""

# ── Assemble full HTML ────────────────────────────────────────────────────────
html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;}}
</style>
</head>
<body style="background:#ece5d8;font-family:'IBM Plex Sans',sans-serif;color:#2b2620;padding:16px 18px 26px;min-height:100vh;">
<div style="max-width:1520px;margin:0 auto;">
  {header}
  {mock_banner}
  {layer1_row}
  {hinge_section}
  {layer2_context_row}
  {tripwire_row}
  {layer3_support_row}
  {cross_asset_section}
  {footer}
</div>
{clock_js}
</body>
</html>'''

components.html(html, height=1640, scrolling=True)
