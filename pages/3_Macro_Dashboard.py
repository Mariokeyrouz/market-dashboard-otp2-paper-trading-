"""
Macro Signal Dashboard — three-layer signal hierarchy with a region lens.

Region dropdown (International / US / Europe; default International) re-frames the
*context* — regime/CPI, central bank, credit, equities, FX — while the US-anchored
hinge (real/breakeven decomposition, curve, MOVE, gold-vs-real, global commodities,
DXY, VIX) stays fixed, because US real yields are the global discount rate.

All data is MOCK (macro_data.py); classification rules live in macro_logic.py. The
page is a "dumb" renderer. Region switching is instant in-iframe via setRegion().
"""

import json

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

# ── Region config ─────────────────────────────────────────────────────────────
REGIONS = ["intl", "us", "eu"]
DEFAULT_REGION = "intl"
REGION_LABELS = {"intl": "🌐 International", "us": "🇺🇸 United States", "eu": "🇪🇺 Europe"}

# ── Pull data ─────────────────────────────────────────────────────────────────
# Fixed (US / global — render once)
hinge      = mdata.layer2_hinge()
hinge_cls  = mlogic.classify_hinge(hinge)
fci        = mdata.financial_conditions()
trip       = mdata.layer3_tripwires()
vol_cls    = mlogic.vol_curve_state(trip["vix_term"]["front"], trip["vix_term"]["back"])
rcp        = mdata.rates_curve_policy()
commod     = mdata.commodities_impulse()
cmd_cls    = mlogic.commodity_impulse(commod["commodity_index"]["chg"])
liqc       = mdata.liquidity_credit()
liq_cls    = mlogic.liquidity_state(liqc["net_liquidity"]["trend"])
goldreal   = mdata.gold_real_overlay()

# Region-dependent (one variant per region)
regime_by   = {r: mdata.layer1_regime(r) for r in REGIONS}
regimecls_by = {r: mlogic.classify_regime(regime_by[r]) for r in REGIONS}
growth_by   = {r: mdata.growth_nowcast(r) for r in REGIONS}
policy_by   = {r: mdata.central_bank_policy(r) for r in REGIONS}
credit_by   = {r: mdata.credit_spreads(r) for r in REGIONS}
fx_by       = {r: mdata.fx_panel(r) for r in REGIONS}
xasset_by   = {r: mdata.cross_asset(r) for r in REGIONS}
cg_cls_by   = {r: mlogic.copper_gold_signal(growth_by[r]["copper_gold_ratio"]["series"]) for r in REGIONS}

# ── Formatting helpers ────────────────────────────────────────────────────────
def pp(v):
    return f"{'+' if v >= 0 else '−'}{abs(v):.2f} pp"

def arrow(v):
    return "▲" if v >= 0 else "▼"

def sign_col(v, good_when_up=True):
    up = v >= 0
    pos, neg = "#2f8f5b", "#c14a32"
    return (pos if up else neg) if good_when_up else (neg if up else pos)

def chg_span(chg, suffix="", good_when_up=True, dp=2, size=10):
    return (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:{size}px;'
            f'color:{sign_col(chg, good_when_up)};">{arrow(chg)}{abs(chg):.{dp}f}{suffix}</span>')

CARD = ("background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:12px 14px;"
        "box-shadow:0 1px 2px rgba(70,55,25,0.04);box-sizing:border-box;")
LABEL = ("font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#a2987f;")


# ── Charts ────────────────────────────────────────────────────────────────────
def decomp_chart(series_list, W=640, H=210, pad_t=14, pad_b=22, pad_l=6, pad_r=52):
    all_vals = [v for s in series_list for v in s["data"]]
    mn, mx = min(all_vals), max(all_vals)
    rng = (mx - mn) or 1.0
    mn -= rng * 0.12; mx += rng * 0.12; rng = mx - mn
    plot_w = W - pad_l - pad_r; plot_h = H - pad_t - pad_b

    def xy(i, n, v):
        x = pad_l + (i / (n - 1) * plot_w if n > 1 else 0)
        y = pad_t + (1 - (v - mn) / rng) * plot_h
        return x, y

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
                  f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.2" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
                  f'<text x="{lx - 6:.1f}" y="{ly - 7:.1f}" font-size="10" font-weight="600" '
                  f'fill="{color}" text-anchor="end" font-family="IBM Plex Mono,monospace">{data[-1]:.2f}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" preserveAspectRatio="none" '
            f'style="overflow:visible;">{grid}{paths}</svg>')


def mini_spark(series, color, W=116, H=30, pad=4):
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


def state_chip(cls, size=10):
    return (f'<span style="background:{cls["color"]}1a;border:1px solid {cls["color"]}55;color:{cls["color"]};'
            f'font-size:{size}px;font-weight:600;border-radius:5px;padding:2px 8px;letter-spacing:0.02em;white-space:nowrap;">{cls["label"]}</span>')


def kpi_tile(label, value_html, sub_html=""):
    return (f'<div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:7px 9px;'
            f'display:flex;flex-direction:column;gap:2px;min-width:0;">'
            f'<div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:15px;font-weight:600;color:#1d1a15;line-height:1.05;">{value_html}</div>'
            f'{sub_html}</div>')


def asset_row(name, level, chg, level_fmt="{:.2f}", chg_suffix="", good_when_up=True, spark=None, spark_color="#8a7f6a"):
    spark_html = (f'<div style="width:66px;flex-shrink:0;">{mini_spark(spark, spark_color, W=66, H=20)}</div>'
                  if spark else "")
    return (f'<div style="display:flex;align-items:center;gap:7px;padding:4px 0;border-bottom:1px solid #f3eddf;">'
            f'<span style="flex:1;font-size:10.5px;color:#4a443b;white-space:nowrap;">{name}</span>'
            f'{spark_html}'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11.5px;font-weight:600;color:#1d1a15;width:60px;text-align:right;">{level_fmt.format(level)}</span>'
            f'<span style="width:50px;text-align:right;">{chg_span(chg, chg_suffix, good_when_up)}</span>'
            f'</div>')


def heatmap_cell(val, dp=2, suffix="%"):
    cap = 5.0
    a = min(abs(val) / cap, 1.0) * 0.46 + 0.06
    bg = f"rgba(47,143,91,{a:.2f})" if val >= 0 else f"rgba(193,74,50,{a:.2f})"
    return (f'<td style="text-align:right;padding:5px 8px;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:10.5px;background:{bg};color:#1d1a15;white-space:nowrap;">'
            f'{"+" if val >= 0 else "−"}{abs(val):.{dp}f}{suffix}</td>')


def region_slot(htmls, fill=True):
    """Wrap the three region variants as toggled panes (default region visible)."""
    h = "height:100%;" if fill else ""
    return "".join(
        f'<div class="region-pane" data-region="{r}" style="{h}{"" if r == DEFAULT_REGION else "display:none;"}">{htmls[r]}</div>'
        for r in REGIONS)


# ══════════════════════════════════════════════════════════════════════════════
# REGION-DEPENDENT CARD BUILDERS (rendered once per region)
# ══════════════════════════════════════════════════════════════════════════════
def build_regime(rg, rcls):
    return f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:8px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;">
    <span style="{LABEL}">Layer 1 · Regime</span>
    <span style="font-size:9px;color:#b3a890;">{rg['region_label']}</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;background:{rcls['color']}1a;border:1px solid {rcls['color']}55;border-radius:7px;padding:7px 12px;">
    <span style="width:8px;height:8px;border-radius:50%;background:{rcls['color']};"></span>
    <span style="font-family:'Spectral',serif;font-size:17px;font-weight:600;color:{rcls['color']};">{rcls['label']}</span>
  </div>
  <span style="font-size:10.5px;color:#6b6256;line-height:1.35;">{rcls['note']}</span>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:auto;">
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:5px 9px;text-align:center;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">{rg['price_label']} Headline</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{rg['cpi_headline']:.1f}%</div>
    </div>
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:5px 9px;text-align:center;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">{rg['price_label']} Core</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{rg['cpi_core']:.1f}%</div>
    </div>
  </div>
</div>'''


def build_growth(g, cg_cls):
    mfg, srv = g["mfg"], g["services"]
    mfg_col = "#c14a32" if mfg["level"] < 50 else "#2f8f5b"
    srv_col = "#c14a32" if srv["level"] < 50 else "#2f8f5b"
    citi_col = "#2f8f5b" if g["surprise"] >= 0 else "#c14a32"
    cl = g["claims"]
    if cl.get("is_text"):
        cl_val = str(cl["level"])
    else:
        cl_val = f'{cl["level"]}{cl.get("unit", "")}'
    cl_col = "#c14a32" if cl["trend"] == "rising" else ("#2f8f5b" if cl["trend"] in ("falling", "steady") else "#6b6256")
    return f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:8px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;flex-wrap:wrap;">
    <span style="{LABEL}">Growth Nowcast</span>
    <span style="font-size:9px;color:#b3a890;">activity reads feeding the regime</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:7px;">
    {kpi_tile(g["surprise_label"].split("(")[0].strip(), f'<span style="color:{citi_col};">{g["surprise"]:+.0f}</span>', '<div style="font-size:8px;color:#a99f8c;">data vs exp.</div>')}
    {kpi_tile(f'{g["pmi_name"]} Mfg', f'<span style="color:{mfg_col};">{mfg["level"]:.1f}</span>', f'<div style="font-size:8px;color:#a99f8c;">{chg_span(mfg["chg"], dp=1, size=8)}</div>')}
    {kpi_tile(f'{g["pmi_name"]} Svc', f'<span style="color:{srv_col};">{srv["level"]:.1f}</span>', f'<div style="font-size:8px;color:#a99f8c;">{chg_span(srv["chg"], dp=1, size=8)}</div>')}
    {kpi_tile(g["claims_label"], cl_val, f'<div style="font-size:8px;color:{cl_col};">{cl["trend"]}</div>')}
  </div>
  <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:6px 9px;display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:auto;">
    <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">Copper / Gold ratio</div>
      <div style="display:flex;align-items:center;gap:6px;">{state_chip(cg_cls, 9)}<span style="font-size:8.5px;color:#a99f8c;">growth-vs-fear</span></div>
    </div>
    {mini_spark(g["copper_gold_ratio"]["series"], cg_cls["color"], W=84, H=24)}
  </div>
</div>'''


def build_policy(p):
    rng = (f"{p['low']:.2f}–{p['high']:.2f}%" if p["low"] != p["high"] else f"{p['low']:.2f}%")
    return f'''
<div style="background:#f7f2e8;border:1px solid #ece2cf;border-radius:8px;padding:9px 11px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
  <div style="display:flex;flex-direction:column;gap:1px;">
    <span style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.06em;">{p['bank']} · {p['rate_label']}</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#2b2620;">{rng}</span>
  </div>
  <span style="font-size:10px;color:#6b6256;text-align:right;">Implied <span style="font-weight:600;color:#2f8f5b;">{p['implied_count']} cut{'s' if p['implied_count'] != 1 else ''} · ~{p['implied_bps']}bps</span><br>{p['horizon']}</span>
</div>'''


def build_credit(c):
    return f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:7px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;">
    <span style="{LABEL}">Credit Spreads</span>
    <span style="font-size:9px;color:#b3a890;">{c['label']}</span>
  </div>
  <div style="font-size:10px;color:#8a7f6a;font-style:italic;line-height:1.3;">leading tell for equity stress</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:auto;">
    {kpi_tile("HY OAS", f'{c["hy"]["level"]:.2f}%', f'<div style="font-size:8px;color:#a99f8c;">{chg_span(c["hy"]["chg"], " pp", good_when_up=False, size=8)}</div>')}
    {kpi_tile("IG OAS", f'{c["ig"]["level"]:.2f}%', f'<div style="font-size:8px;color:#a99f8c;">{chg_span(c["ig"]["chg"], " pp", good_when_up=False, size=8)}</div>')}
  </div>
</div>'''


def build_fx(fxd):
    rows = "".join(
        asset_row(r["name"], r["level"], r["chg"], r["fmt"], "%", good_when_up=r["good_up"])
        for r in fxd["rows"])
    return f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:5px;">
  <div style="{LABEL}">FX</div>
  <div style="font-size:10px;color:#8a7f6a;font-style:italic;line-height:1.3;">global liquidity / carry lens</div>
  <div>{rows}</div>
</div>'''


def build_xasset(rows):
    body = ""
    for r in rows:
        body += (f'<tr>'
                 f'<td style="text-align:left;padding:5px 9px;font-size:10.5px;color:#2b2620;white-space:nowrap;">{r["name"]}</td>'
                 f'<td style="text-align:right;padding:5px 9px;font-family:\'IBM Plex Mono\',monospace;font-size:10.5px;color:#1d1a15;white-space:nowrap;">{r["level"]:,.2f}</td>'
                 f'{heatmap_cell(r["d1"])}{heatmap_cell(r["d1w"])}{heatmap_cell(r["d1m"])}{heatmap_cell(r["ytd"])}'
                 f'<td style="padding:3px 9px;width:74px;">{mini_spark(r["spark"], "#8a7f6a", W=74, H=18)}</td>'
                 f'</tr>')
    return f'''
<div style="{CARD}">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;margin-bottom:6px;flex-wrap:wrap;">
    <span style="{LABEL}">Cross-Asset</span>
    <span style="font-size:9px;color:#8a7f6a;font-style:italic;">one-glance positioning · % change by horizon</span>
  </div>
  <table style="width:100%;border-collapse:collapse;">
    <thead><tr style="font-size:8.5px;color:#a99f8c;text-transform:uppercase;letter-spacing:0.05em;">
      <th style="text-align:left;padding:3px 9px;font-weight:600;">Asset</th>
      <th style="text-align:right;padding:3px 9px;font-weight:600;">Level</th>
      <th style="text-align:right;padding:3px 8px;font-weight:600;">1D</th>
      <th style="text-align:right;padding:3px 8px;font-weight:600;">1W</th>
      <th style="text-align:right;padding:3px 8px;font-weight:600;">1M</th>
      <th style="text-align:right;padding:3px 8px;font-weight:600;">YTD</th>
      <th style="text-align:left;padding:3px 9px;font-weight:600;">Trend</th>
    </tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>'''


# Pre-render region variants
regime_html = {r: build_regime(regime_by[r], regimecls_by[r]) for r in REGIONS}
growth_html = {r: build_growth(growth_by[r], cg_cls_by[r]) for r in REGIONS}
policy_html = {r: build_policy(policy_by[r]) for r in REGIONS}
credit_html = {r: build_credit(credit_by[r]) for r in REGIONS}
fx_html     = {r: build_fx(fx_by[r]) for r in REGIONS}
xasset_html = {r: build_xasset(xasset_by[r]) for r in REGIONS}

disclaimer = (
    "The Inflation-Scare vs. Growth-Shock classification is opinionated and "
    "style-dependent — calibrated to a macro-positional, stagflation-leaning book. "
    "A lens, not objective fact. The region toggle does not alter this US-anchored hinge."
)

# ── Header (with region dropdown) ─────────────────────────────────────────────
region_options = "".join(
    f'<option value="{r}"{" selected" if r == DEFAULT_REGION else ""}>{REGION_LABELS[r]}</option>'
    for r in REGIONS)

header = f'''
<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:12px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:26px;height:26px;border-radius:6px;background:#2b2620;display:flex;align-items:center;justify-content:center;color:#ece5d8;font-family:'Spectral',serif;font-weight:700;font-size:15px;">M</div>
    <div style="font-family:'Spectral',serif;font-weight:600;font-size:22px;letter-spacing:-0.01em;color:#211d18;">Macro Signal Dashboard</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:500;letter-spacing:0.08em;color:#8a7f5f;border:1px solid #d8cdb6;border-radius:4px;padding:2px 6px;background:#f4eedf;">OTP2.0</div>
    <span title="{disclaimer}" style="cursor:help;font-size:11px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;background:#f4eedf;">i</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="display:flex;align-items:center;gap:7px;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:8px;padding:5px 10px;">
      <span style="font-size:9px;font-weight:600;letter-spacing:0.1em;color:#a99f8c;text-transform:uppercase;">Region</span>
      <select id="region-select" onchange="setRegion(this.value)" style="font-family:'IBM Plex Sans',sans-serif;font-size:12.5px;font-weight:600;color:#2b2620;background:transparent;border:none;outline:none;cursor:pointer;">
        {region_options}
      </select>
    </div>
    <div style="display:flex;align-items:center;gap:8px;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:8px;padding:5px 11px;">
      <span id="nyse-dot" style="width:7px;height:7px;border-radius:50%;background:#a99f8c;display:inline-block;flex-shrink:0;"></span>
      <div style="display:flex;flex-direction:column;line-height:1.1;">
        <span style="font-size:8.5px;font-weight:600;letter-spacing:0.1em;color:#a99f8c;text-transform:uppercase;">NYSE · ET</span>
        <span id="et-time" style="font-family:'IBM Plex Mono',monospace;font-size:12.5px;font-weight:500;color:#2b2620;">--:--:--</span>
      </div>
      <span id="nyse-status" style="font-size:9.5px;font-weight:600;color:#a99f8c;">--</span>
    </div>
  </div>
</div>'''

mock_chip = ""
if getattr(mdata, "MOCK", False):
    mock_chip = ('<span style="font-size:10px;color:#9a7434;font-weight:600;background:#fbf1e3;'
                 'border:1px solid #e7cfa6;border-radius:6px;padding:3px 9px;">🧪 MOCK DATA — placeholder values, not live levels</span>')

# ── Layer 1 context strip: Regime | Growth | (FCI + Policy) ───────────────────
fci_level = fci["level"]
fci_pos = max(0, min(100, (fci_level + 1.5) / 3.0 * 100))
fci_looser = fci_level < 0
fci_col = "#2f8f5b" if fci_looser else "#c14a32"
fci_word = "Looser than avg" if fci_looser else "Tighter than avg"
fci_card = f'''
<div style="{CARD}display:flex;flex-direction:column;gap:6px;">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <span style="{LABEL}">Financial Conditions</span>
    <span style="font-size:9px;color:#b3a890;">daily · forward-looking</span>
  </div>
  <div style="display:flex;align-items:baseline;gap:8px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:{fci_col};">{fci_level:+.2f}</span>
    <span style="font-size:10.5px;color:{fci_col};font-weight:600;">{fci_word}</span>
  </div>
  <div style="height:7px;background:#efe8da;border-radius:5px;position:relative;">
    <div style="position:absolute;left:50%;top:-2px;width:1px;height:11px;background:#c3b9a4;"></div>
    <div style="position:absolute;left:{min(fci_pos,50):.1f}%;width:{abs(fci_pos-50):.1f}%;height:100%;background:{fci_col};border-radius:5px;"></div>
  </div>
  <div style="display:flex;justify-content:space-between;font-size:8.5px;color:#a99f8c;"><span>◄ looser</span><span>tighter ►</span></div>
</div>'''

context_strip = f'''
<div style="display:grid;grid-template-columns:1.05fr 1.7fr 1.15fr;gap:12px;align-items:stretch;margin-bottom:12px;">
  <div style="min-width:0;display:flex;">{region_slot(regime_html)}</div>
  <div style="min-width:0;display:flex;">{region_slot(growth_html)}</div>
  <div style="min-width:0;display:flex;flex-direction:column;gap:10px;">
    {fci_card}
    {region_slot(policy_html, fill=False)}
  </div>
</div>'''

# ── Layer 2 centerpiece: Hinge | (Rates&Curve + Vol + Gold/Real) ──────────────
chart_svg = decomp_chart([
    {"data": hinge["nominal_series"],   "color": "#2b2620"},
    {"data": hinge["real_series"],      "color": "#3a6ea5"},
    {"data": hinge["breakeven_series"], "color": "#c08a2d"},
])

def hinge_legend_item(color, label, level, chg):
    return (f'<div style="display:flex;align-items:center;gap:5px;">'
            f'<span style="width:13px;height:3px;border-radius:2px;background:{color};"></span>'
            f'<span style="font-size:10.5px;color:#4a443b;">{label}</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11.5px;font-weight:600;color:#1d1a15;">{level:.2f}%</span>'
            f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:9.5px;color:{sign_col(chg)};">{arrow(chg)}{abs(chg):.2f}</span></div>')

legend = (hinge_legend_item("#2b2620", "Nominal 10Y", hinge["nominal"]["level"], hinge["nominal"]["chg"])
          + hinge_legend_item("#3a6ea5", "Real (TIPS)", hinge["real"]["level"], hinge["real"]["chg"])
          + hinge_legend_item("#c08a2d", "Breakeven", hinge["breakeven"]["level"], hinge["breakeven"]["chg"]))

tag_chips = "".join(
    f'<span style="background:{hinge_cls["color"]}1a;border:1px solid {hinge_cls["color"]}55;color:{hinge_cls["color"]};'
    f'font-size:9.5px;font-weight:600;border-radius:5px;padding:2px 8px;letter-spacing:0.02em;">{t}</span>'
    for t in hinge_cls["tags"])
dom = hinge_cls.get("dominant")
dom_label = {"breakeven": "Breakeven leg", "real": "Real-yield leg", None: "No dominant leg"}[dom]

hinge_card = f'''
<div style="{CARD}">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:6px;">
    <div style="display:flex;align-items:baseline;gap:8px;">
      <span style="font-family:'Spectral',serif;font-size:16px;font-weight:600;color:#211d18;">Layer 2 · The Hinge</span>
      <span style="font-size:10px;color:#8a7f6a;font-style:italic;">10Y nominal = real + breakeven · US-anchored</span>
    </div>
    <span style="font-size:9px;font-weight:600;letter-spacing:0.07em;text-transform:uppercase;color:#2f8f5b;background:#edf7f1;border:1px solid #c3e6d1;border-radius:5px;padding:2px 8px;">Daily clock</span>
  </div>
  <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:14px;align-items:start;">
    <div style="min-width:0;">
      <div style="display:flex;gap:13px;flex-wrap:wrap;margin-bottom:6px;">{legend}</div>
      {chart_svg}
    </div>
    <div style="background:{hinge_cls['color']}14;border:1px solid {hinge_cls['color']}55;border-left:4px solid {hinge_cls['color']};border-radius:9px;padding:11px 13px;display:flex;flex-direction:column;gap:7px;">
      <div style="display:flex;align-items:center;gap:7px;">
        <span style="{LABEL}">Classification</span>
        <span title="{disclaimer}" style="cursor:help;font-size:8.5px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:13px;height:13px;display:inline-flex;align-items:center;justify-content:center;">i</span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="width:10px;height:10px;border-radius:50%;background:{hinge_cls['color']};"></span>
        <span style="font-family:'Spectral',serif;font-size:21px;font-weight:700;color:{hinge_cls['color']};line-height:1.05;">{hinge_cls['label']}</span>
      </div>
      <div style="font-size:10.5px;color:#5a5247;line-height:1.4;">{hinge_cls['note']}</div>
      <div style="display:flex;gap:5px;flex-wrap:wrap;">{tag_chips}</div>
      <div style="font-size:9px;color:#a99f8c;border-top:1px solid #ece3d2;padding-top:6px;">Dominant mover: <span style="color:#6b6256;font-weight:600;">{dom_label}</span> · lookback {hinge['lookback_days']}d</div>
    </div>
  </div>
</div>'''

# Right column: Rates & Curve, Volatility, Gold vs Real (all fixed/US)
curve_2s10s_cls = mlogic.curve_state(rcp["slope_2s10s"]["level"])
curve_3m10y_cls = mlogic.curve_state(rcp["slope_3m10y"]["level"])
_move = rcp["move_index"]
vt = trip["vix_term"]
rates_vol_card = f'''
<div style="{CARD}display:flex;flex-direction:column;gap:8px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;">
    <span style="{LABEL}">US Rates · Curve · Vol</span>
    <span style="font-size:9px;color:#b3a890;">stays US</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;">
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:6px 9px;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">2s10s</div>
      <div style="display:flex;align-items:baseline;gap:5px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;color:#1d1a15;">{rcp['slope_2s10s']['level']:+.2f}</span>{state_chip(curve_2s10s_cls, 8.5)}</div>
    </div>
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:6px 9px;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">3m10y</div>
      <div style="display:flex;align-items:baseline;gap:5px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;color:#1d1a15;">{rcp['slope_3m10y']['level']:+.2f}</span>{state_chip(curve_3m10y_cls, 8.5)}</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
    <div style="display:flex;flex-direction:column;"><span style="font-size:9px;color:#6b6256;">MOVE <span style="color:#a99f8c;">(bond vol)</span></span></div>
    <div style="display:flex;align-items:baseline;gap:6px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{_move['level']:.0f}</span>{chg_span(_move['chg'], good_when_up=False, dp=1, size=10)}</div>
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;border-top:1px solid #ece3d2;padding-top:7px;">
    <span style="font-size:9px;color:#6b6256;">Vol term structure</span>
    <div style="display:flex;align-items:center;gap:6px;">{state_chip(vol_cls, 9.5)}<span style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;color:#8a7f6a;">{vt['front']:.1f}→{vt['back']:.1f}</span></div>
  </div>
</div>'''

goldreal_chart = decomp_chart([
    {"data": goldreal["gold_index"], "color": "#c08a2d"},
    {"data": goldreal["real_index"], "color": "#3a6ea5"},
], H=96, pad_t=8, pad_b=12, pad_r=40)
goldreal_card = f'''
<div style="{CARD}display:flex;flex-direction:column;gap:5px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;">
    <span style="{LABEL}">Gold vs Real Yield</span>
    <span style="font-size:9px;color:#b3a890;">real-rate play</span>
  </div>
  <div style="display:flex;gap:12px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:5px;"><span style="width:12px;height:3px;border-radius:2px;background:#c08a2d;"></span><span style="font-size:10px;color:#4a443b;">Gold ${goldreal['gold_level']:,.0f}</span></div>
    <div style="display:flex;align-items:center;gap:5px;"><span style="width:12px;height:3px;border-radius:2px;background:#3a6ea5;"></span><span style="font-size:10px;color:#4a443b;">10Y Real {goldreal['real_level']:.2f}%</span></div>
  </div>
  {goldreal_chart}
  <div style="font-size:9px;color:#a99f8c;">Indexed to 100 · typically <span style="font-weight:600;">{goldreal['relationship']}</span> — directional only.</div>
</div>'''

centerpiece = f'''
<div style="display:grid;grid-template-columns:1.75fr 1fr;gap:12px;align-items:stretch;margin-bottom:12px;">
  {hinge_card}
  <div style="display:flex;flex-direction:column;gap:12px;">
    {rates_vol_card}
    {goldreal_card}
  </div>
</div>'''

# ── Layer 3 secondary row: Credit | Commodities | Liquidity | FX ──────────────
commod_rows = (
    asset_row("Oil (WTI)", commod["wti"]["level"], commod["wti"]["chg"], "{:.2f}", "%", spark=commod["wti"]["series"], spark_color="#c14a32")
    + asset_row("Brent", commod["brent"]["level"], commod["brent"]["chg"], "{:.2f}", "%", spark=commod["brent"]["series"], spark_color="#c14a32")
    + asset_row("Copper", commod["copper"]["level"], commod["copper"]["chg"], "{:.3f}", "%", spark=commod["copper"]["series"], spark_color="#c2703a")
    + asset_row("Gold", commod["gold"]["level"], commod["gold"]["chg"], "{:,.0f}", "%", spark=commod["gold"]["series"], spark_color="#c08a2d")
    + asset_row("Commodity ix", commod["commodity_index"]["level"], commod["commodity_index"]["chg"], "{:.1f}", "%", spark=commod["commodity_index"]["series"], spark_color="#8a7f6a")
)
commod_card = f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:6px;">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
    <span style="{LABEL}">Commodities</span>{state_chip(cmd_cls, 9.5)}
  </div>
  <div style="font-size:10px;color:#8a7f6a;font-style:italic;line-height:1.3;">inflation impulse → breakevens</div>
  <div>{commod_rows}</div>
</div>'''

_nl = liqc["net_liquidity"]
liq_card = f'''
<div style="{CARD}height:100%;display:flex;flex-direction:column;gap:7px;">
  <span style="{LABEL}">Liquidity</span>
  <div style="font-size:10px;color:#8a7f6a;font-style:italic;line-height:1.3;">US/global plumbing</div>
  <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:7px 9px;display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:auto;">
    <div style="display:flex;flex-direction:column;gap:2px;min-width:0;">
      <div style="font-size:8.5px;color:#9a917e;text-transform:uppercase;letter-spacing:0.05em;">Fed net liquidity</div>
      <div style="display:flex;align-items:baseline;gap:5px;"><span style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">${_nl['level']:.2f}T</span>{state_chip(liq_cls, 8.5)}</div>
      <div style="font-size:8px;color:#a99f8c;">bal. sheet − RRP − TGA</div>
    </div>
    {mini_spark(_nl["series"], liq_cls["color"], W=72, H=28)}
  </div>
  <div style="display:flex;align-items:center;justify-content:space-between;font-size:10.5px;">
    <span style="color:#6b6256;">Bank reserves</span>
    <span style="font-family:'IBM Plex Mono',monospace;color:#1d1a15;font-weight:600;">${liqc['bank_reserves']['level']:.2f}T <span style="color:#a99f8c;font-weight:400;font-size:8.5px;">{liqc['bank_reserves']['trend']}</span></span>
  </div>
</div>'''

secondary_row = f'''
<div style="display:grid;grid-template-columns:1fr 1.15fr 1fr 1fr;gap:12px;align-items:stretch;margin-bottom:12px;">
  <div style="min-width:0;display:flex;">{region_slot(credit_html)}</div>
  {commod_card}
  {liq_card}
  <div style="min-width:0;display:flex;">{region_slot(fx_html)}</div>
</div>'''

# ── Cross-asset (region) ──────────────────────────────────────────────────────
xasset_section = f'''
<div style="margin-bottom:14px;">{region_slot(xasset_html, fill=False)}</div>'''

footer = (
    '<div style="font-size:10px;color:#a99f8c;text-align:center;letter-spacing:0.03em;">'
    'Region lens re-frames context; the real-yield hinge stays US-anchored · '
    'all values MOCK (macro_data.py) · classification is opinionated · directional reads, no validated hit-rates'
    '</div>'
)

# ── JS: clocks + region toggle ────────────────────────────────────────────────
region_js = """
<script>
var REGION_LABELS = __LABELS__;
function setRegion(r){
  document.querySelectorAll('.region-pane').forEach(function(el){
    el.style.display = (el.getAttribute('data-region')===r) ? '' : 'none';
  });
  var sel=document.getElementById('region-select'); if(sel && sel.value!==r) sel.value=r;
}
</script>
""".replace("__LABELS__", json.dumps(REGION_LABELS))

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

# ── Assemble ──────────────────────────────────────────────────────────────────
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
select#region-select{{appearance:auto;}}
</style>
</head>
<body style="background:#ece5d8;font-family:'IBM Plex Sans',sans-serif;color:#2b2620;padding:14px 16px 20px;min-height:100vh;">
<div style="max-width:1560px;margin:0 auto;">
  {header}
  <div style="margin-bottom:10px;">{mock_chip}</div>
  {context_strip}
  {centerpiece}
  {secondary_row}
  {xasset_section}
  {footer}
</div>
{region_js}
{clock_js}
</body>
</html>'''

components.html(html, height=1240, scrolling=True)
