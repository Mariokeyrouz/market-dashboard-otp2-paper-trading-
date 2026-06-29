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

# ── Layer 1 — Regime badge ────────────────────────────────────────────────────
regime_card = f'''
<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:13px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:12px;">
  <div style="display:flex;flex-direction:column;gap:3px;">
    <span style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Layer 1 · Regime</span>
    <span style="font-size:9px;color:#b3a890;">Monthly clock · backward-looking context</span>
  </div>
  <div style="display:flex;align-items:center;gap:9px;background:{regime_cls['color']}1a;border:1px solid {regime_cls['color']}55;border-radius:7px;padding:7px 14px;">
    <span style="width:8px;height:8px;border-radius:50%;background:{regime_cls['color']};"></span>
    <span style="font-family:'Spectral',serif;font-size:16px;font-weight:600;color:{regime_cls['color']};">{regime_cls['label']}</span>
  </div>
  <span style="font-size:11.5px;color:#6b6256;flex:1;min-width:160px;">{regime_cls['note']}</span>
  <div style="display:flex;gap:8px;">
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:6px 11px;text-align:center;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.06em;">CPI Headline</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{regime_in['cpi_headline']:.1f}%</div>
    </div>
    <div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:6px;padding:6px 11px;text-align:center;">
      <div style="font-size:9px;color:#9a917e;text-transform:uppercase;letter-spacing:0.06em;">CPI Core</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{regime_in['cpi_core']:.1f}%</div>
    </div>
  </div>
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

# ── Footer ────────────────────────────────────────────────────────────────────
footer = (
    '<div style="font-size:10px;color:#a99f8c;text-align:center;letter-spacing:0.03em;">'
    'First-pass layout · all values are MOCK placeholders (macro_data.py) · '
    'classification logic is opinionated and style-dependent · '
    'Layer-3 relationships are directional, no validated hit-rates implied'
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
  {regime_card}
  {hinge_section}
  {tripwire_row}
  {footer}
</div>
{clock_js}
</body>
</html>'''

components.html(html, height=900, scrolling=True)
