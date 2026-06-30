"""
Macro Signal Dashboard — lean, US-focused.

Three clean zones, ruthless hierarchy:
  1. Header (title, disclaimer, clock)
  2. Context band — regime badge + inline macro stats (inflation, growth, policy, conditions)
  3. The Hinge (hero) — 10Y nominal = real + breakeven, with the Inflation-Scare /
     Growth-Shock classification. The visual centerpiece.
  4. Tripwire row — four uniform tiles: Credit · VIX · DXY · Curve.

All data is MOCK (macro_data.py); classification rules live in macro_logic.py.
Secondary panels (commodities, liquidity, FX, cross-asset, gold-vs-real, regions)
were intentionally removed from this view to keep it focused; their data functions
remain in macro_data.py for later.
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

# ── Data (US) ─────────────────────────────────────────────────────────────────
hinge      = mdata.layer2_hinge()
hinge_cls  = mlogic.classify_hinge(hinge)
regime_in  = mdata.layer1_regime("us")
regime_cls = mlogic.classify_regime(regime_in)
growth     = mdata.growth_nowcast("us")
policy     = mdata.central_bank_policy("us")
credit     = mdata.credit_spreads("us")
fci        = mdata.financial_conditions()
trip       = mdata.layer3_tripwires()
vol_cls    = mlogic.vol_curve_state(trip["vix_term"]["front"], trip["vix_term"]["back"])
rcp        = mdata.rates_curve_policy()
curve_cls  = mlogic.curve_state(rcp["slope_2s10s"]["level"])

# ── Helpers ───────────────────────────────────────────────────────────────────
def arrow(v):
    return "▲" if v >= 0 else "▼"

def sign_col(v, good_when_up=True):
    up = v >= 0
    pos, neg = "#2f8f5b", "#c14a32"
    return (pos if up else neg) if good_when_up else (neg if up else pos)

def chg_span(chg, suffix="", good_when_up=True, dp=2, size=11):
    return (f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:{size}px;'
            f'color:{sign_col(chg, good_when_up)};">{arrow(chg)}{abs(chg):.{dp}f}{suffix}</span>')

MONO = "'IBM Plex Mono',monospace"
SERIF = "'Spectral',serif"
CARD = ("background:#ffffff;border:1px solid #e8e0d2;border-radius:11px;"
        "box-shadow:0 1px 3px rgba(70,55,25,0.05);box-sizing:border-box;")
LABEL = "font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;color:#a2987f;"

disclaimer = (
    "The Inflation-Scare vs. Growth-Shock classification is opinionated and style-dependent — "
    "calibrated to a macro-positional, stagflation-leaning book. A lens, not objective fact."
)


# ── Decomposition chart (the hero visual) ─────────────────────────────────────
def decomp_chart(series_list, W=620, H=260, pad_t=18, pad_b=24, pad_l=8, pad_r=54):
    all_vals = [v for s in series_list for v in s["data"]]
    mn, mx = min(all_vals), max(all_vals)
    rng = (mx - mn) or 1.0
    mn -= rng * 0.14; mx += rng * 0.14; rng = mx - mn
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
                 f'stroke="#f1ece1" stroke-width="1"/>'
                 f'<text x="{pad_l + plot_w + 7}" y="{gy + 3:.1f}" font-size="9.5" '
                 f'fill="#b3a890" font-family="{MONO}">{gval:.2f}</text>')
    paths = ""
    for s in series_list:
        data, color = s["data"], s["color"]
        n = len(data)
        coords = [xy(i, n, v) for i, v in enumerate(data)]
        d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
        lx, ly = coords[-1]
        paths += (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.4" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>'
                  f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.6" fill="{color}" stroke="#fff" stroke-width="1.6"/>'
                  f'<text x="{lx - 7:.1f}" y="{ly - 8:.1f}" font-size="10.5" font-weight="600" '
                  f'fill="{color}" text-anchor="end" font-family="{MONO}">{data[-1]:.2f}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" preserveAspectRatio="none" '
            f'style="overflow:visible;">{grid}{paths}</svg>')


# ── Header ────────────────────────────────────────────────────────────────────
header = f'''
<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:11px;">
    <div style="width:28px;height:28px;border-radius:7px;background:#2b2620;display:flex;align-items:center;justify-content:center;color:#ece5d8;font-family:{SERIF};font-weight:700;font-size:16px;">M</div>
    <div style="font-family:{SERIF};font-weight:600;font-size:23px;letter-spacing:-0.01em;color:#211d18;">Macro Signal Dashboard</div>
    <div style="font-family:{MONO};font-size:9.5px;font-weight:500;letter-spacing:0.08em;color:#8a7f5f;border:1px solid #d8cdb6;border-radius:4px;padding:2px 6px;background:#f4eedf;">OTP2.0</div>
    <span title="{disclaimer}" style="cursor:help;font-size:11px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;background:#f4eedf;">i</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:9px;padding:6px 12px;">
    <span id="nyse-dot" style="width:7px;height:7px;border-radius:50%;background:#a99f8c;display:inline-block;flex-shrink:0;"></span>
    <div style="display:flex;flex-direction:column;line-height:1.15;">
      <span style="font-size:8.5px;font-weight:600;letter-spacing:0.1em;color:#a99f8c;text-transform:uppercase;">NYSE · ET</span>
      <span id="et-time" style="font-family:{MONO};font-size:13px;font-weight:500;color:#2b2620;">--:--:--</span>
    </div>
    <span id="nyse-status" style="font-size:10px;font-weight:600;color:#a99f8c;">--</span>
  </div>
</div>'''

# ── Context band: regime badge + inline macro stats ───────────────────────────
def stat_block(label, value_html, sub_html, first=False):
    border = "" if first else "border-left:1px solid #ece3d2;"
    return (f'<div style="{border}padding:0 16px;display:flex;flex-direction:column;gap:3px;min-width:0;">'
            f'<div style="font-size:9px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#a2987f;">{label}</div>'
            f'<div style="font-family:{MONO};font-size:17px;font-weight:600;color:#1d1a15;line-height:1;">{value_html}</div>'
            f'<div style="font-size:9.5px;color:#9a917e;">{sub_html}</div></div>')

ism = growth["mfg"]
ism_col = "#c14a32" if ism["level"] < 50 else "#2f8f5b"
fci_looser = fci["level"] < 0
fci_col = "#2f8f5b" if fci_looser else "#c14a32"
growth_word = regime_in["growth"].capitalize()

context_band = f'''
<div style="{CARD}padding:15px 18px;display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:16px;">
  <div style="display:flex;flex-direction:column;gap:5px;padding-right:18px;border-right:1px solid #ece3d2;">
    <span style="{LABEL}">Regime · US</span>
    <div style="display:flex;align-items:center;gap:9px;background:{regime_cls['color']}1a;border:1px solid {regime_cls['color']}55;border-radius:8px;padding:7px 14px;">
      <span style="width:9px;height:9px;border-radius:50%;background:{regime_cls['color']};"></span>
      <span style="font-family:{SERIF};font-size:18px;font-weight:600;color:{regime_cls['color']};">{regime_cls['label']}</span>
    </div>
  </div>
  <div style="display:flex;align-items:center;flex:1;flex-wrap:wrap;gap:8px 0;">
    {stat_block("Inflation", f"{regime_in['cpi_headline']:.1f}%", f"core {regime_in['cpi_core']:.1f}% · {regime_in['cpi_trend']}", first=True)}
    {stat_block("Growth", f'<span style="color:{ism_col};">{ism["level"]:.1f}</span>', f"ISM mfg · {growth_word}")}
    {stat_block("Policy", f"{policy['low']:.2f}–{policy['high']:.2f}%", f"{policy['bank']} · {policy['implied_count']} cut{'s' if policy['implied_count']!=1 else ''} priced")}
    {stat_block("Conditions", f'<span style="color:{fci_col};">{fci["level"]:+.2f}</span>', f"FCI · {'looser' if fci_looser else 'tighter'} than avg")}
  </div>
</div>'''

# ── The Hinge (hero) ──────────────────────────────────────────────────────────
chart_svg = decomp_chart([
    {"data": hinge["nominal_series"],   "color": "#2b2620"},
    {"data": hinge["real_series"],      "color": "#3a6ea5"},
    {"data": hinge["breakeven_series"], "color": "#c08a2d"},
])

def legend_item(color, label, level, chg):
    return (f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<span style="width:15px;height:3px;border-radius:2px;background:{color};"></span>'
            f'<span style="font-size:11.5px;color:#4a443b;">{label}</span>'
            f'<span style="font-family:{MONO};font-size:12.5px;font-weight:600;color:#1d1a15;">{level:.2f}%</span>'
            f'<span style="font-family:{MONO};font-size:10px;color:{sign_col(chg)};">{arrow(chg)}{abs(chg):.2f}</span></div>')

legend = (legend_item("#2b2620", "Nominal 10Y", hinge["nominal"]["level"], hinge["nominal"]["chg"])
          + legend_item("#3a6ea5", "Real (TIPS)", hinge["real"]["level"], hinge["real"]["chg"])
          + legend_item("#c08a2d", "Breakeven", hinge["breakeven"]["level"], hinge["breakeven"]["chg"]))

tag_chips = "".join(
    f'<span style="background:{hinge_cls["color"]}1a;border:1px solid {hinge_cls["color"]}55;color:{hinge_cls["color"]};'
    f'font-size:10px;font-weight:600;border-radius:5px;padding:3px 9px;letter-spacing:0.02em;">{t}</span>'
    for t in hinge_cls["tags"])
dom = hinge_cls.get("dominant")
dom_label = {"breakeven": "Breakeven leg", "real": "Real-yield leg", None: "No dominant leg"}[dom]

hinge_hero = f'''
<div style="{CARD}padding:18px 20px;margin-bottom:16px;">
  <div style="display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
    <div style="display:flex;align-items:baseline;gap:11px;">
      <span style="font-family:{SERIF};font-size:19px;font-weight:600;color:#211d18;">The Hinge</span>
      <span style="font-size:12px;color:#8a7f6a;font-style:italic;">10Y nominal = real yield + breakeven inflation</span>
    </div>
    <span style="font-size:9.5px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#2f8f5b;background:#edf7f1;border:1px solid #c3e6d1;border-radius:6px;padding:3px 10px;">Daily clock · checked daily</span>
  </div>
  <div style="display:grid;grid-template-columns:1.62fr 1fr;gap:22px;align-items:stretch;">
    <div style="min-width:0;display:flex;flex-direction:column;">
      <div style="display:flex;gap:18px;flex-wrap:wrap;margin-bottom:10px;">{legend}</div>
      {chart_svg}
    </div>
    <div style="background:{hinge_cls['color']}12;border:1px solid {hinge_cls['color']}50;border-left:5px solid {hinge_cls['color']};border-radius:11px;padding:16px 18px;display:flex;flex-direction:column;gap:11px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="{LABEL}">Classification</span>
        <span title="{disclaimer}" style="cursor:help;font-size:9px;color:#a2987f;border:1px solid #d8cdb6;border-radius:50%;width:14px;height:14px;display:inline-flex;align-items:center;justify-content:center;">i</span>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="width:12px;height:12px;border-radius:50%;background:{hinge_cls['color']};"></span>
        <span style="font-family:{SERIF};font-size:27px;font-weight:700;color:{hinge_cls['color']};line-height:1.02;">{hinge_cls['label']}</span>
      </div>
      <div style="font-size:12px;color:#5a5247;line-height:1.5;">{hinge_cls['note']}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">{tag_chips}</div>
      <div style="font-size:10px;color:#a99f8c;border-top:1px solid #ece3d2;padding-top:9px;margin-top:auto;">
        Dominant mover: <span style="color:#6b6256;font-weight:600;">{dom_label}</span> · lookback {hinge['lookback_days']}d
      </div>
    </div>
  </div>
</div>'''

# ── Tripwire row: four uniform tiles ──────────────────────────────────────────
def tripwire_tile(label, framing, big_html, state_html):
    return f'''
<div style="{CARD}padding:15px 16px;display:flex;flex-direction:column;gap:8px;min-width:0;height:100%;">
  <div style="{LABEL}">{label}</div>
  <div style="font-size:10.5px;color:#8a7f6a;font-style:italic;line-height:1.35;">{framing}</div>
  <div style="margin-top:4px;">{big_html}</div>
  <div style="margin-top:auto;">{state_html}</div>
</div>'''

def big_val(value, chg_html):
    return (f'<span style="font-family:{MONO};font-size:27px;font-weight:600;color:#1d1a15;">{value}</span>'
            f'<span style="margin-left:9px;">{chg_html}</span>')

hy = credit["hy"]
vt = trip["vix_term"]
dxy = trip["dxy"]
s2s10s = rcp["slope_2s10s"]

credit_tile = tripwire_tile(
    "Credit · HY OAS", "Leading tell for equity stress",
    big_val(f'{hy["level"]:.2f}%', chg_span(hy["chg"], " pp", good_when_up=False, dp=2)),
    '<span style="font-size:10.5px;color:#6b6256;">Widening = rising stress.</span>')

vix_tile = tripwire_tile(
    "Equity Vol · VIX", "Risk-on / risk-off tripwire",
    f'<span style="font-family:{MONO};font-size:27px;font-weight:600;color:#1d1a15;">{vt["front"]:.1f}</span>'
    f'<span style="margin-left:9px;font-size:11px;color:{vol_cls["color"]};font-weight:600;">{vol_cls["label"]}</span>',
    f'<span style="font-size:10.5px;color:#6b6256;">{vol_cls["note"]}</span>')

dxy_tile = tripwire_tile(
    "Dollar · DXY", "Global liquidity valve",
    big_val(f'{dxy["level"]:.1f}', chg_span(dxy["chg"], "", good_when_up=False, dp=2)),
    '<span style="font-size:10.5px;color:#6b6256;">Stronger USD tightens conditions abroad.</span>')

curve_tile = tripwire_tile(
    "Curve · 2s10s", "Late-cycle / recession watch",
    f'<span style="font-family:{MONO};font-size:27px;font-weight:600;color:#1d1a15;">{s2s10s["level"]:+.2f}</span>'
    f'<span style="margin-left:9px;font-size:11px;color:{curve_cls["color"]};font-weight:600;">{curve_cls["label"]}</span>',
    f'<span style="font-size:10.5px;color:#6b6256;">{curve_cls["note"]}</span>')

tripwire_row = f'''
<div style="margin-bottom:8px;display:flex;align-items:baseline;gap:10px;">
  <span style="font-family:{SERIF};font-size:15px;font-weight:600;color:#211d18;">Risk Tripwires</span>
  <span style="font-size:11px;color:#8a7f6a;font-style:italic;">faster confirming signals — directional, not mechanically precise</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:14px;align-items:stretch;margin-bottom:16px;">
  {credit_tile}{vix_tile}{dxy_tile}{curve_tile}
</div>'''

mock_chip = ""
if getattr(mdata, "MOCK", False):
    mock_chip = ('<span style="font-size:10px;color:#9a7434;font-weight:600;background:#fbf1e3;'
                 'border:1px solid #e7cfa6;border-radius:6px;padding:3px 10px;">🧪 MOCK DATA — placeholder values, not live levels</span>')

footer = (
    '<div style="display:flex;align-items:center;justify-content:center;gap:12px;flex-wrap:wrap;font-size:10px;color:#a99f8c;text-align:center;letter-spacing:0.02em;">'
    f'{mock_chip}<span>Opinionated, style-dependent classification · directional reads, no validated hit-rates · all values via macro_data.py</span>'
    '</div>'
)

# ── Clock JS ──────────────────────────────────────────────────────────────────
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
</style>
</head>
<body style="background:#ece5d8;font-family:'IBM Plex Sans',sans-serif;color:#2b2620;padding:20px 22px 18px;min-height:100vh;">
<div style="max-width:1320px;margin:0 auto;">
  {header}
  {context_band}
  {hinge_hero}
  {tripwire_row}
  {footer}
</div>
{clock_js}
</body>
</html>'''

components.html(html, height=820, scrolling=True)
