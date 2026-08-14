import streamlit as st
import yfinance as yf
import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, date

st.set_page_config(
    page_title="Institutional Market Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  #MainMenu, header, footer { visibility: hidden; }
  .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
</style>
""", unsafe_allow_html=True)

# ── Portfolio correlation ─────────────────────────────────────────────────────

PORTFOLIO_LEDGERS = {
    "OTP2.0":      "paper_ledger.csv",
    "OTP2.0 AMA":  "paper_ledger_AMA.csv",
    "FMTS":        "factor_ledger.csv",
    "FMTS AMA":    "factor_ledger_AMA.csv",
    "Momentum":    "momentum_ledger.csv",
    "Gold":        "gold_ledger.csv",
    "Four-Pillar": "four_pillar_ledger.csv",
    "RRG":         "rrg_ledger.csv",
}

# RRG is a research book, not a funded strategy — see pages/10_Portfolio_Analytics.py.
# It is still included here so the homepage reflects the whole system, not just the
# funded subset.
RESEARCH_ONLY_LEDGERS = {"RRG"}

def _build_corr_card():
    rets  = {}
    stats = {}
    for name, path in PORTFOLIO_LEDGERS.items():
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
            s  = pd.to_numeric(df.set_index("date")["daily_log_ret"], errors="coerce").dropna()
            if len(s) < 2:
                continue
            rets[name] = s
            ann_ret = s.mean() * 252 * 100
            ann_vol = s.std() * np.sqrt(252) * 100
            sharpe  = ann_ret / ann_vol if ann_vol > 0 else float("nan")
            stats[name] = dict(ret=ann_ret, vol=ann_vol, sharpe=sharpe,
                               n=len(s), start=str(s.index[0].date()),
                               end=str(s.index[-1].date()))
        except Exception:
            continue

    names = list(rets.keys())
    n = len(names)

    if n < 2:
        return ""   # not enough portfolios seeded yet

    # Align by date, not by row position — strategies seeded on different days
    # (e.g. Four-Pillar, added later) have shorter/offset histories. Pairwise
    # correlation over each pair's actual shared dates avoids truncating every
    # strategy down to the newest one's tiny window. min_periods=8 blanks out
    # pairs without enough overlap yet.
    ret_df  = pd.DataFrame(rets)
    corr_df = ret_df.corr(min_periods=8)
    corr    = corr_df.reindex(index=names, columns=names).values

    overlap = ret_df.notna()
    pair_obs = [int((overlap[names[i]] & overlap[names[j]]).sum())
                for i in range(n) for j in range(n) if i < j]
    obs = min(pair_obs) if pair_obs else 0

    # Color helper: 1.0=deep red, 0.0=neutral grey, -1.0=deep blue
    def corr_hex(v):
        # clamp to [-1, 1] just in case
        v = max(-1.0, min(1.0, v))
        if v >= 0:
            # 0 → warm parchment; 1 → deep red
            r2 = int(0xf3 + v * (0xc1 - 0xf3))
            g2 = int(0xee + v * (0x4a - 0xee))
            b2 = int(0xe2 + v * (0x32 - 0xe2))
        else:
            # 0 → warm parchment; -1 → deep blue
            av = abs(v)
            r2 = int(0xf3 + av * (0x1a - 0xf3))
            g2 = int(0xee + av * (0x4a - 0xee))
            b2 = int(0xe2 + av * (0x8c - 0xe2))
        bg  = f"#{r2:02x}{g2:02x}{b2:02x}"
        lum = 0.299 * r2 + 0.587 * g2 + 0.114 * b2
        return bg, lum

    def cell_color(v, is_diag):
        if is_diag:
            return "#2b2620", "#f3eee2"   # bg, text
        if np.isnan(v):
            return "#f5f0e8", "#a99f8c"
        bg, lum = corr_hex(v)
        txt = "#f3eee2" if lum < 140 else "#2b2620"
        return bg, txt

    def val_txt(v, is_diag):
        if is_diag:
            return "1.00"
        return f"{v:.2f}" if not np.isnan(v) else "—"

    # Header row
    th_cells = '<th style="padding:0;"></th>' + "".join(
        f'<th style="font-size:10px;font-weight:600;letter-spacing:0.05em;color:#6b6256;padding:4px 10px 6px;text-align:center;white-space:nowrap;">'
        f'{nm}{" ⚠️" if nm in RESEARCH_ONLY_LEDGERS else ""}</th>'
        for nm in names
    )

    # Data rows
    data_rows = ""
    for i, rname in enumerate(names):
        cells = f'<td style="font-size:10px;font-weight:600;color:#6b6256;padding:5px 10px;white-space:nowrap;border-right:1px solid #ece3d2;">{rname}</td>'
        for j in range(n):
            is_diag = (i == j)
            v = corr[i, j]
            bg, txt = cell_color(v, is_diag)
            vt = val_txt(v, is_diag)
            cells += (f'<td style="background:{bg};color:{txt};font-family:\'IBM Plex Mono\',monospace;'
                      f'font-size:12px;font-weight:500;text-align:center;padding:7px 14px;'
                      f'border-radius:5px;white-space:nowrap;">{vt}</td>')
        data_rows += f"<tr>{cells}</tr>"

    # Per-portfolio stats row
    stat_cells = '<td style="font-size:10px;font-weight:600;color:#a99f8c;padding:8px 10px;border-top:1px solid #ece3d2;border-right:1px solid #ece3d2;white-space:nowrap;">Stats (ann.)</td>'
    for nm in names:
        s = stats.get(nm, {})
        ret_col = "#2f8f5b" if s.get("ret", 0) >= 0 else "#c14a32"
        sh_col  = "#2f8f5b" if s.get("sharpe", 0) >= 0 else "#c14a32"
        stat_cells += (
            f'<td style="text-align:center;padding:8px 6px;border-top:1px solid #ece3d2;vertical-align:top;">'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:{ret_col};font-weight:600;">'
            f'{s.get("ret", float("nan")):+.1f}%</div>'
            f'<div style="font-size:9px;color:#a99f8c;">{s.get("vol", float("nan")):.1f}% vol</div>'
            f'<div style="font-size:9px;color:{sh_col};">SR {s.get("sharpe", float("nan")):.2f}</div>'
            f'</td>'
        )

    obs_note = f"min {obs} shared day{'s' if obs != 1 else ''}"
    date_range = ""
    if stats:
        starts = [s["start"] for s in stats.values()]
        ends   = [s["end"] for s in stats.values()]
        date_range = f" · {min(starts)} → {max(ends)}"

    card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 16px 12px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:inline-block;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">Portfolio Correlation</div>
    <div style="font-size:9.5px;color:#a99f8c;font-family:'IBM Plex Mono',monospace;">{obs_note}{date_range}</div>
  </div>
  <div style="overflow-x:auto;">
    <table style="border-collapse:separate;border-spacing:3px;font-family:'IBM Plex Sans',sans-serif;">
      <thead><tr>{th_cells}</tr></thead>
      <tbody>
        {data_rows}
        <tr>{stat_cells}</tr>
      </tbody>
    </table>
  </div>
  <div style="font-size:9px;color:#a99f8c;margin-top:8px;">
    Daily log-return correlations across all active strategies · Stats are annualised · SR = Sharpe ratio
    {' · ⚠️ RRG is a research book, not funded' if 'RRG' in names else ''}
    {'· <span style="color:#c89b53;font-weight:500;">⚠ Low observation count — values will stabilise after 60+ trading days</span>' if obs < 60 else ''}
  </div>
</div>'''

    return card

corr_card_html = _build_corr_card()

# ── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_all():
    symbols = {
        'sp500':    '^GSPC',
        'nasdaq':   '^IXIC',
        'dow':      '^DJI',
        'russell':  '^RUT',
        'vix':      '^VIX',
        'gold':     'GC=F',
        'silver':   'SI=F',
        'oil':      'CL=F',
        'copper':   'HG=F',
        'dxy':      'DX-Y.NYB',
        'tnx':      '^TNX',
        'fvx':      '^FVX',
        'tyx':      '^TYX',
        'irx':      '^IRX',
        'nikkei':   '^N225',
        'dax':      '^GDAXI',
        'ftse':     '^FTSE',
        'shanghai': '000001.SS',
        'hangseng': '^HSI',
        'nifty':    '^NSEI',
    }
    data = {}
    for k, sym in symbols.items():
        try:
            h = yf.Ticker(sym).history(period='1y', interval='1d')
            if h.empty:
                raise ValueError('empty')
            c = [float(x) for x in h['Close']]
            pr, pv = c[-1], (c[-2] if len(c) > 1 else c[-1])
            data[k] = dict(price=pr, prev=pv, chg=pr - pv, pct=(pr - pv) / pv * 100, closes=c)
        except Exception:
            data[k] = dict(price=None, prev=None, chg=None, pct=None, closes=[])

    # Intraday for the 4 chart cards
    for k, sym in [('sp500', '^GSPC'), ('gold', 'GC=F'), ('copper', 'HG=F'), ('oil', 'CL=F')]:
        try:
            h = yf.Ticker(sym).history(period='1d', interval='5m')
            data[k]['intraday'] = [] if h.empty else [float(x) for x in h['Close']]
        except Exception:
            data[k]['intraday'] = []

    return data

SECTOR_ETFS = [
    ('XLK',  'Technology'),
    ('XLF',  'Financials'),
    ('XLV',  'Health Care'),
    ('XLY',  'Cons. Discretionary'),
    ('XLP',  'Cons. Staples'),
    ('XLE',  'Energy'),
    ('XLI',  'Industrials'),
    ('XLB',  'Materials'),
    ('XLU',  'Utilities'),
    ('XLRE', 'Real Estate'),
    ('XLC',  'Comm. Services'),
]

@st.cache_data(ttl=300)
def fetch_sectors():
    out = {}
    for sym, _ in SECTOR_ETFS:
        try:
            h = yf.Ticker(sym).history(period='2mo', interval='1d')
            c = [float(x) for x in h['Close'].dropna()]
            if len(c) < 2:
                raise ValueError('empty')
            d1  = (c[-1] - c[-2]) / c[-2] * 100
            d1m = (c[-1] - c[-21]) / c[-21] * 100 if len(c) >= 21 else None
            out[sym] = dict(price=c[-1], d1=d1, d1m=d1m)
        except Exception:
            out[sym] = dict(price=None, d1=None, d1m=None)
    return out

if st.button('🔄 Refresh Data'):
    st.cache_data.clear()
    st.rerun()

data = fetch_all()
sector_data = fetch_sectors()

# ── Helpers ────────────────────────────────────────────────────────────────────

def gv(key):
    return data.get(key, {})

def price(key):
    return gv(key).get('price')

def pct(key):
    return gv(key).get('pct')

def closes(key):
    return gv(key).get('closes', [])

def fmt_val(v, key=''):
    if v is None:
        return 'N/A'
    if key in ('tnx', 'fvx', 'tyx', 'irx'):
        return f'{v:.3f}%'
    if key == 'vix':
        return f'{v:.2f}'
    if v >= 10000:
        return f'{v:,.0f}'
    if v >= 1000:
        return f'{v:,.2f}'
    if v >= 10:
        return f'{v:.2f}'
    return f'{v:.4f}'

def chg_str(key):
    pc = pct(key)
    if pc is None:
        return '—', '#a99f8c'
    arrow = '▲' if pc >= 0 else '▼'
    col = '#2f8f5b' if pc >= 0 else '#c14a32'
    return f'{arrow} {abs(pc):.2f}%', col

def svg_chart(prices, color, W=320, H=96, pad=8, ref=None):
    if not prices or len(prices) < 2:
        return '<text x="50%" y="50%" fill="#a99f8c" font-size="11" text-anchor="middle">No data</text>'
    vals = prices + [ref] if ref is not None else prices
    mn, mx = min(vals), max(vals)
    rng = mx - mn or 1
    n = len(prices)
    coords = [(i / (n - 1) * W, pad + (1 - (p - mn) / rng) * (H - 2 * pad)) for i, p in enumerate(prices)]
    line_d = 'M ' + ' L '.join(f'{x:.1f},{y:.1f}' for x, y in coords)
    area_d = line_d + f' L{W},{H} L0,{H} Z'
    gid = f'g{abs(hash(str(prices[-1]) + color)) % 99999}'
    lx, ly = coords[-1]
    ref_line = ''
    if ref is not None:
        ry = pad + (1 - (ref - mn) / rng) * (H - 2 * pad)
        ref_line = f'<line x1="0" y1="{ry:.1f}" x2="{W}" y2="{ry:.1f}" stroke="#c9bfa8" stroke-width="1" stroke-dasharray="3,3"/>'
    return f'''<defs>
  <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{color}" stop-opacity="0.20"/>
    <stop offset="60%" stop-color="{color}" stop-opacity="0.04"/>
    <stop offset="100%" stop-color="{color}" stop-opacity="0"/>
  </linearGradient>
</defs>
<line x1="0" y1="{H//3}" x2="{W}" y2="{H//3}" stroke="#f1ece1" stroke-width="1"/>
<line x1="0" y1="{H*2//3}" x2="{W}" y2="{H*2//3}" stroke="#f1ece1" stroke-width="1"/>
<path d="{area_d}" fill="url(#{gid})"/>
{ref_line}
<path d="{line_d}" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" fill="{color}" stroke="white" stroke-width="1.5"/>'''

# ── Build series data for JS chart switching ──────────────────────────────────

CHART_CARDS = [
    ('sp500',  'S&P 500',      'equity index', '#2f8f5b'),
    ('gold',   'Gold (XAU)',   'commodities',  '#c08a2d'),
    ('copper', 'Dr. Copper',   'growth proxy', '#c2703a'),
    ('oil',    'Oil (WTI)',    'energy',       '#c14a32'),
]

chart_series = {}
for key, *_ in CHART_CARDS:
    cl = closes(key)
    ind = gv(key).get('intraday', [])
    ytd_n = 0
    today = date.today()
    h = yf.Ticker({'sp500':'^GSPC','gold':'GC=F','copper':'HG=F','oil':'CL=F'}.get(key,''))
    # Approximate YTD from closes (trading days from ~Jan)
    ytd_n = min(len(cl), max(1, int(len(cl) * (today.timetuple().tm_yday / 365.0))))
    chart_series[key] = {
        '1D':  ind if ind else cl[-20:],
        '1W':  cl[-5:]  if len(cl) >= 5  else cl,
        '1M':  cl[-21:] if len(cl) >= 21 else cl,
        '3M':  cl[-63:] if len(cl) >= 63 else cl,
        '1Y':  cl,
        'YTD': cl[-ytd_n:] if ytd_n else cl,
    }

series_json = json.dumps(chart_series)
colors_json = json.dumps({key: color for key, _, __, color in CHART_CARDS})

# ── Ticker strip ───────────────────────────────────────────────────────────────

TICKER_ITEMS = [
    ('sp500',   'S&P 500'),
    ('nasdaq',  'Nasdaq'),
    ('dow',     'Dow Jones'),
    ('russell', 'Russell 2K'),
    ('vix',     'VIX'),
    ('gold',    'Gold'),
    ('silver',  'Silver'),
    ('oil',     'Oil WTI'),
    ('copper',  'Copper'),
    ('dxy',     'DXY'),
    ('tnx',     '10Y UST'),
]

def ticker_item(key, label):
    pr = price(key)
    pc = pct(key)
    val = fmt_val(pr, key) if pr is not None else 'N/A'
    if pc is None:
        chg_html = '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:#a99f8c;">—</span>'
    else:
        col = '#2f8f5b' if pc >= 0 else '#c14a32'
        arrow = '▲' if pc >= 0 else '▼'
        chg_html = f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:{col};">{arrow}{abs(pc):.2f}%</span>'
    return f'''<div style="display:flex;align-items:baseline;gap:7px;padding:0 18px;border-right:1px solid #ece3d2;white-space:nowrap;">
  <span style="font-size:11px;font-weight:600;color:#6b6256;letter-spacing:0.03em;">{label}</span>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;color:#2b2620;">{val}</span>
  {chg_html}
</div>'''

ticker_html = ''.join(ticker_item(k, l) for k, l in TICKER_ITEMS)
ticker_2x = ticker_html + ticker_html

# ── Price chart cards ──────────────────────────────────────────────────────────

def chart_card(key, name, tag, color):
    pr = price(key)
    val = fmt_val(pr, key) if pr is not None else 'N/A'
    chg_s, chg_col = chg_str(key)
    init = chart_series.get(key, {}).get('1M', [])
    chart_svg = svg_chart(init, color) if init else ''
    pills = ['1D', '1W', '1M', '3M', '1Y', 'YTD']
    pills_html = ''.join(
        f'''<button onclick="switchTf('{key}','{tf}',this)"
  style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:500;border:none;border-radius:5px;padding:3px 7px;cursor:pointer;
  background:{'#2b2620' if tf == '1M' else '#f3eee2'};color:{'#f3eee2' if tf == '1M' else '#8a7f6a'};">{tf}</button>'''
        for tf in pills
    )
    return f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:12px 13px 11px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="display:flex;align-items:baseline;gap:6px;">
    <span style="font-size:13.5px;font-weight:600;color:#211d18;">{name}</span>
    <span style="font-size:9.5px;font-style:italic;color:#a99f8c;">{tag}</span>
  </div>
  <div style="display:flex;align-items:baseline;gap:7px;margin-top:2px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:19px;font-weight:500;color:#1d1a15;letter-spacing:-0.01em;">{val}</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;color:{chg_col};white-space:nowrap;">{chg_s}</span>
  </div>
  <div style="display:flex;gap:3px;margin-top:9px;flex-wrap:wrap;" id="pills-{key}">{pills_html}</div>
  <div style="position:relative;margin-top:8px;">
    <svg viewBox="0 0 320 96" width="100%" height="96" preserveAspectRatio="none" id="chart-{key}" style="overflow:visible;">{chart_svg}</svg>
  </div>
</div>'''

cards_html = ''.join(chart_card(k, n, t, c) for k, n, t, c in CHART_CARDS)

# ── Yield curve card ───────────────────────────────────────────────────────────

TENORS = [('irx', '3M'), (None, '2Y'), ('fvx', '5Y'), ('tnx', '10Y'), ('tyx', '30Y')]

def tenor_val(key):
    if key is None:
        return 'N/A'
    pr = price(key)
    return f'{pr:.2f}%' if pr is not None else 'N/A'

tenors_html = ''.join(f'''<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">
  <span style="font-size:10px;color:#9a917e;">{label}</span>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:13px;color:#2b2620;">{tenor_val(key)}</span>
</div>''' for key, label in TENORS)

yc_vals = [(i, price(k)) for i, (k, _) in enumerate(TENORS) if k is not None and price(k) is not None]
if len(yc_vals) >= 2:
    ys = [v for _, v in yc_vals]
    mn_y, mx_y = min(ys), max(ys)
    rng_y = mx_y - mn_y or 0.5
    W_yc, H_yc = 280, 46
    coords_yc = [(i / (len(TENORS) - 1) * W_yc, 4 + (1 - (v - mn_y) / rng_y) * (H_yc - 8)) for i, v in yc_vals]
    line_yc = 'M ' + ' L '.join(f'{x:.1f},{y:.1f}' for x, y in coords_yc)
    area_yc = line_yc + f' L{coords_yc[-1][0]:.1f},{H_yc} L{coords_yc[0][0]:.1f},{H_yc} Z'
    nodes_yc = ''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="#3a6ea5" stroke="white" stroke-width="1.5"/>' for x, y in coords_yc)
    yield_svg = f'''<svg viewBox="0 0 280 46" width="100%" height="46" preserveAspectRatio="none">
  <defs><linearGradient id="gcyc" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#3a6ea5" stop-opacity="0.16"/>
    <stop offset="100%" stop-color="#3a6ea5" stop-opacity="0"/>
  </linearGradient></defs>
  <path d="{area_yc}" fill="url(#gcyc)"/>
  <path d="{line_yc}" fill="none" stroke="#3a6ea5" stroke-width="2"/>
  {nodes_yc}
</svg>'''
else:
    yield_svg = '<svg viewBox="0 0 280 46" width="100%" height="46"><text x="50%" y="30" fill="#a99f8c" font-size="11" text-anchor="middle">No data</text></svg>'

v10 = price('tnx')
spread_chip = ''
if v10:
    spread_chip = f'''<div style="display:flex;align-items:center;gap:8px;margin-top:10px;background:#f7f2e8;border:1px solid #ece2cf;border-radius:6px;padding:8px 10px;">
  <span style="font-size:10px;color:#9a917e;letter-spacing:0.06em;text-transform:uppercase;">10Y Yield</span>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:18px;font-weight:600;color:#2b2620;">{v10:.3f}%</span>
</div>'''

yield_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:10px;">Yield Curve</div>
  <div style="display:flex;justify-content:space-between;margin-bottom:10px;">{tenors_html}</div>
  {yield_svg}
  {spread_chip}
  <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px;">
    <div style="display:flex;justify-content:space-between;font-size:11px;">
      <span style="color:#6b6256;">5Y Treasury</span>
      <span style="font-family:'IBM Plex Mono',monospace;color:#2b2620;">{tenor_val('fvx')}</span>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:11px;">
      <span style="color:#6b6256;">30Y Treasury</span>
      <span style="font-family:'IBM Plex Mono',monospace;color:#2b2620;">{tenor_val('tyx')}</span>
    </div>
  </div>
</div>'''

# ── 10Y–3M spread (recession-model input) — fills the empty space below the
# yield curve card with the single-number version of the same curve: is it
# inverted right now, and for how long has it been.
_tnx_c, _irx_c = closes('tnx'), closes('irx')
_n_sp = min(len(_tnx_c), len(_irx_c))
spread_series = [_tnx_c[-_n_sp + i] - _irx_c[-_n_sp + i] for i in range(_n_sp)] if _n_sp >= 2 else []
last_spread = spread_series[-1] if spread_series else None

if last_spread is not None:
    _inverted = last_spread < 0
    spread_col  = '#c14a32' if _inverted else '#2f8f5b'
    spread_stat = 'Inverted' if _inverted else 'Normal'
    spread_bg   = '#fbe9e4' if _inverted else '#e7f5ec'
    spread_svg  = svg_chart(spread_series[-180:], spread_col, 280, 46, 5, ref=0.0)
    spread_txt  = f'{last_spread:+.2f}%'
else:
    spread_col, spread_stat, spread_bg, spread_txt = '#a99f8c', '—', '#f5f0e8', 'N/A'
    spread_svg = svg_chart([], spread_col)

yield_spread_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:8px;">10Y–3M Spread</div>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:{spread_col};">{spread_txt}</span>
    <span style="font-size:9.5px;font-weight:600;background:{spread_bg};color:{spread_col};border-radius:4px;padding:2px 7px;">{spread_stat}</span>
  </div>
  <svg viewBox="0 0 280 46" width="100%" height="46" preserveAspectRatio="none">{spread_svg}</svg>
  <div style="font-size:9.5px;color:#6b6256;margin-top:8px;line-height:1.4;">NY Fed recession-model input · negative spreads have preceded every US recession since 1970, lead time varies (~6–18mo).</div>
</div>'''

# ── Dr. Copper card ────────────────────────────────────────────────────────────

cu_p = price('copper')
cu_val = fmt_val(cu_p, 'copper') if cu_p is not None else 'N/A'
cu_chg_s, cu_chg_col = chg_str('copper')
cu_series = closes('copper')[-63:] if closes('copper') else []
cu_svg = svg_chart(cu_series, '#c2703a', 280, 58, 6) if cu_series else ''
ism_val = 48.7  # latest available; FRED data not wired yet

copper_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:8px;">Dr. Copper Signal</div>
  <div style="display:flex;align-items:baseline;gap:7px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:27px;font-weight:600;color:#c2703a;">{cu_val}</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:{cu_chg_col};">{cu_chg_s}</span>
  </div>
  <p style="font-size:11.5px;color:#6b6256;margin:8px 0 6px;line-height:1.45;">Copper — a leading economic indicator. Rising prices signal growth optimism; falling signals slowdown risk.</p>
  <svg viewBox="0 0 280 58" width="100%" height="58" preserveAspectRatio="none">{cu_svg}</svg>
  <div style="margin-top:10px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
      <span style="font-size:10px;color:#6b6256;">ISM Manufacturing</span>
      <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:{'#c14a32' if ism_val < 50 else '#2f8f5b'};">{ism_val}</span>
    </div>
    <div style="height:6px;background:#efe8da;border-radius:5px;position:relative;">
      <div style="height:100%;width:{ism_val}%;background:#c89b53;border-radius:5px;max-width:100%;"></div>
      <div style="position:absolute;left:50%;top:-2px;width:1px;height:10px;background:#a99f8c;"></div>
    </div>
    <div style="font-size:9px;color:#a99f8c;margin-top:2px;">Below 50 = contraction</div>
  </div>
</div>'''

# ── Copper/Gold ratio (risk-appetite proxy) — the growth-vs-safety complement
# to the Dr. Copper signal above it; scaled x1000 (desk convention) so the
# ~0.0015 raw ratio reads as a legible number.
_cu_c, _au_c = closes('copper'), closes('gold')
_n_cg = min(len(_cu_c), len(_au_c))
cg_series = [(_cu_c[-_n_cg + i] / _au_c[-_n_cg + i]) * 1000 for i in range(_n_cg)] if _n_cg >= 2 else []
last_cg = cg_series[-1] if cg_series else None
cg_chg = ((cg_series[-1] / cg_series[-22] - 1) * 100) if len(cg_series) >= 22 else None

if last_cg is not None:
    cg_col  = '#2f8f5b' if (cg_chg or 0) >= 0 else '#c14a32'
    cg_svg  = svg_chart(cg_series[-180:], '#7a8c5c', 280, 46, 5)
    cg_txt  = f'{last_cg:.3f}'
    cg_chgtxt = f'{cg_chg:+.1f}% · 1M' if cg_chg is not None else '—'
else:
    cg_col, cg_txt, cg_chgtxt = '#a99f8c', 'N/A', '—'
    cg_svg = svg_chart([], '#7a8c5c')

copper_gold_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:8px;">Copper/Gold Ratio</div>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:#2b2620;">{cg_txt}</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:{cg_col};">{cg_chgtxt}</span>
  </div>
  <svg viewBox="0 0 280 46" width="100%" height="46" preserveAspectRatio="none">{cg_svg}</svg>
  <div style="font-size:9.5px;color:#6b6256;margin-top:8px;line-height:1.4;">Rising = growth/risk-on demand outpacing the gold safe-haven bid; falling = risk-off. Tracks 10Y yields closely.</div>
</div>'''

# ── Risk & Rates card ──────────────────────────────────────────────────────────

vix_p = price('vix')
vix_val = fmt_val(vix_p, 'vix') if vix_p is not None else 'N/A'
vix_fill = min(vix_p / 80 * 100, 100) if vix_p else 0
vix_col = '#c14a32' if vix_p and vix_p > 20 else ('#2f8f5b' if vix_p else '#a99f8c')
tnx_p = price('tnx')
dxy_p = price('dxy')

def gauge(label, val_str, fill_pct, fill_color, scale, val_color='#2b2620'):
    return f'''<div style="margin-bottom:11px;">
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px;">
    <span style="font-size:11.5px;color:#4a443b;">{label}</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:500;color:{val_color};">{val_str}</span>
  </div>
  <div style="height:6px;background:#efe8da;border-radius:5px;">
    <div style="height:100%;width:{min(fill_pct, 100):.0f}%;background:{fill_color};border-radius:5px;"></div>
  </div>
  <div style="font-size:9px;color:#a99f8c;margin-top:2px;">{scale}</div>
</div>'''

risk_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:10px;">Risk &amp; Rates</div>
  {gauge('VIX (Fear Index)', vix_val, vix_fill, '#3a6ea5', '0 = calm  ·  80 = extreme fear', vix_col)}
  {gauge('10Y Treasury', f"{tnx_p:.3f}%" if tnx_p else 'N/A', (tnx_p / 8 * 100) if tnx_p else 0, '#c79a4e', '0% → 8%', '#c08a2d')}
  {gauge('DXY (Dollar Index)', f"{dxy_p:.2f}" if dxy_p else 'N/A', ((dxy_p - 80) / 50 * 100) if dxy_p else 0, '#9a6db5', '80 → 130')}
  {gauge('ISM Manufacturing', f'{ism_val}', ism_val, '#c89b53', '0 → 100  ·  50 = expansion threshold', '#c14a32' if ism_val < 50 else '#2f8f5b')}
</div>'''

# ── Vol risk premium: VIX vs 20d realized — the professional-desk complement
# to the raw VIX gauge above (options are priced on the spread between implied
# and realized, not on VIX's level alone). Realized vol is computed from the
# same S&P 500 closes already fetched for the price-chart cards.
_sp_c, _vix_c = closes('sp500'), closes('vix')
if len(_sp_c) >= 22 and len(_vix_c) >= 2:
    _log_rets = np.diff(np.log(_sp_c))
    rv_series = [float(np.std(_log_rets[i - 20:i], ddof=1) * np.sqrt(252) * 100)
                 for i in range(20, len(_log_rets) + 1)]
    _n_vrp = min(len(rv_series), len(_vix_c))
    rv_aligned  = rv_series[-_n_vrp:]
    vix_aligned = _vix_c[-_n_vrp:]
    vrp_series = [v - r for v, r in zip(vix_aligned, rv_aligned)]
else:
    vrp_series, rv_aligned = [], []

last_vrp = vrp_series[-1] if vrp_series else None
last_rv  = rv_aligned[-1] if rv_aligned else None

if last_vrp is not None:
    vrp_col = '#2f8f5b' if last_vrp >= 0 else '#c14a32'
    vrp_txt = f'{last_vrp:+.1f} pts'
    rv_txt  = f'{last_rv:.1f}%'
    vrp_svg = svg_chart(vrp_series[-180:], vrp_col, 280, 46, 5, ref=0.0)
else:
    vrp_col, vrp_txt, rv_txt = '#a99f8c', 'N/A', 'N/A'
    vrp_svg = svg_chart([], vrp_col)

vol_premium_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:8px;">Vol Risk Premium</div>
  <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:600;color:{vrp_col};">{vrp_txt}</span>
  </div>
  <div style="font-size:10px;color:#a99f8c;margin-bottom:6px;">VIX {vix_val} − 20d realized {rv_txt}</div>
  <svg viewBox="0 0 280 46" width="100%" height="46" preserveAspectRatio="none">{vrp_svg}</svg>
  <div style="font-size:9.5px;color:#6b6256;margin-top:8px;line-height:1.4;">Positive = implied vol priced above realized, the normal state; compression toward zero has preceded vol spikes.</div>
</div>'''

# ── CFTC COT card (illustrative) ───────────────────────────────────────────────

COT_ROWS = [
    ('S&P 500',   68,   '#2f8f5b'),
    ('Gold',      186,  '#2f8f5b'),
    ('Copper',    28,   '#2f8f5b'),
    ('Oil (WTI)', -44,  '#c14a32'),
    ('10Y TSY',   -312, '#c14a32'),
    ('EUR/USD',   14,   '#2f8f5b'),
]
max_abs_cot = max(abs(v) for _, v, _ in COT_ROWS)

def cot_row(label, val, color):
    pct_fill = abs(val) / max_abs_cot * 50
    if val >= 0:
        bar = f'<div style="position:absolute;left:50%;width:{pct_fill:.1f}%;height:100%;background:{color};border-radius:0 3px 3px 0;"></div>'
    else:
        bar = f'<div style="position:absolute;right:50%;width:{pct_fill:.1f}%;height:100%;background:{color};border-radius:3px 0 0 3px;"></div>'
    sign = '+' if val >= 0 else ''
    return f'''<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
  <span style="font-size:10.5px;color:#4a443b;width:64px;flex-shrink:0;white-space:nowrap;">{label}</span>
  <div style="flex:1;height:13px;background:#f5efe3;border-radius:5px;position:relative;">
    <div style="position:absolute;left:50%;top:0;width:1px;height:100%;background:#d5cec0;"></div>
    {bar}
  </div>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:{color};width:40px;text-align:right;flex-shrink:0;">{sign}{val}K</span>
</div>'''

cot_rows_html = ''.join(cot_row(l, v, c) for l, v, c in COT_ROWS)

cot_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:4px;">CFTC COT Positioning</div>
  <div style="display:flex;justify-content:space-between;font-size:9px;color:#a99f8c;margin-bottom:8px;letter-spacing:0.05em;">
    <span>◄ NET SHORT</span><span>NET LONG ►</span>
  </div>
  {cot_rows_html}
  <div style="font-size:9px;color:#a99f8c;margin-top:4px;">Illustrative · Latest CFTC COT release</div>
</div>'''

# ── Global Markets card ────────────────────────────────────────────────────────

GLOBAL = [
    ('nikkei',   'Nikkei 225',  'JP'),
    ('dax',      'DAX',         'DE'),
    ('ftse',     'FTSE 100',    'UK'),
    ('shanghai', 'Shanghai',    'CN'),
    ('hangseng', 'Hang Seng',   'HK'),
    ('nifty',    'Nifty 50',    'IN'),
]

def global_row(key, name, country, last=False):
    pr = price(key)
    pc = pct(key)
    val = fmt_val(pr, key) if pr is not None else 'N/A'
    if pc is None:
        pct_html = '<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:#a99f8c;">—</span>'
    else:
        col = '#2f8f5b' if pc >= 0 else '#c14a32'
        arrow = '▲' if pc >= 0 else '▼'
        pct_html = f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;color:{col};">{arrow}{abs(pc):.2f}%</span>'
    border = '' if last else 'border-bottom:1px solid #f3eddf;'
    return f'''<div style="display:flex;align-items:center;gap:8px;padding:7px 0;{border}">
  <span style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;font-weight:500;background:#f4eedf;padding:2px 5px;border-radius:3px;color:#6b6256;">{country}</span>
  <span style="flex:1;font-size:11.5px;color:#2b2620;">{name}</span>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#1d1a15;">{val}</span>
  {pct_html}
</div>'''

global_rows_html = ''.join(global_row(k, n, c, i == len(GLOBAL) - 1) for i, (k, n, c) in enumerate(GLOBAL))

global_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:6px;">Global Markets</div>
  {global_rows_html}
</div>'''

# ── Sector Performance card (1M rotation, ranked) ──────────────────────────────
# Sits beside the correlation matrix — a domestic-equity breadth/rotation read
# that complements the cross-asset macro cards without repeating them.

_sector_ranked = sorted(
    ((sym, name, sector_data[sym]) for sym, name in SECTOR_ETFS if sector_data[sym]['d1m'] is not None),
    key=lambda r: r[2]['d1m'], reverse=True,
)
_sector_max_abs = max((abs(r[2]['d1m']) for r in _sector_ranked), default=1) or 1

def sector_row(sym, name, s, last=False):
    d1, d1m = s['d1'], s['d1m']
    col = '#2f8f5b' if d1m >= 0 else '#c14a32'
    fill = abs(d1m) / _sector_max_abs * 50
    bar = (f'<div style="position:absolute;left:50%;width:{fill:.1f}%;height:100%;background:{col};border-radius:0 3px 3px 0;"></div>' if d1m >= 0
           else f'<div style="position:absolute;right:50%;width:{fill:.1f}%;height:100%;background:{col};border-radius:3px 0 0 3px;"></div>')
    d1_col = '#2f8f5b' if d1 is not None and d1 >= 0 else '#c14a32'
    d1_txt = f'{d1:+.1f}%' if d1 is not None else '—'
    border = '' if last else 'border-bottom:1px solid #f3eddf;'
    return f'''<div style="display:flex;align-items:center;gap:7px;padding:6px 0;{border}">
  <span style="font-family:'IBM Plex Mono',monospace;font-size:8.5px;font-weight:500;background:#f4eedf;padding:2px 5px;border-radius:3px;color:#6b6256;width:30px;text-align:center;flex-shrink:0;">{sym}</span>
  <span style="flex:1;font-size:11px;color:#2b2620;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{name}</span>
  <div style="width:90px;height:12px;background:#f5efe3;border-radius:5px;position:relative;flex-shrink:0;">
    <div style="position:absolute;left:50%;top:0;width:1px;height:100%;background:#d5cec0;"></div>
    {bar}
  </div>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:10.5px;font-weight:600;color:{col};width:44px;text-align:right;flex-shrink:0;">{d1m:+.1f}%</span>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:{d1_col};width:38px;text-align:right;flex-shrink:0;">{d1_txt}</span>
</div>'''

sector_rows_html = ''.join(sector_row(sym, name, s, i == len(_sector_ranked) - 1) for i, (sym, name, s) in enumerate(_sector_ranked))
if not sector_rows_html:
    sector_rows_html = '<div style="font-size:10px;color:#a99f8c;padding:8px 0;">No sector data available.</div>'

sector_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 16px 12px;box-shadow:0 1px 2px rgba(70,55,25,0.04);flex:1;min-width:280px;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;">
    <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;">S&amp;P Sector Rotation</div>
    <div style="display:flex;gap:10px;font-size:8.5px;color:#a99f8c;letter-spacing:0.04em;text-transform:uppercase;padding-right:1px;">
      <span style="width:44px;text-align:right;">1M</span><span style="width:38px;text-align:right;">1D</span>
    </div>
  </div>
  <div style="font-size:9px;color:#a99f8c;margin-bottom:6px;">Ranked by 1-month return · SPDR sector ETFs</div>
  {sector_rows_html}
</div>'''

# ── Extended Macro card ────────────────────────────────────────────────────────

MACRO_TILES = [
    ('tnx',     '10Y Treasury', 'tnx'),
    ('tyx',     '30Y Treasury', 'tyx'),
    ('irx',     '3M T-Bill',    'irx'),
    ('silver',  'Silver',       'silver'),
    ('dxy',     'Dollar (DXY)', 'dxy'),
    ('russell', 'Russell 2000', 'russell'),
]

def macro_tile(key, label, fk):
    pr = price(key)
    pc = pct(key)
    val = fmt_val(pr, fk) if pr is not None else 'N/A'
    if pc is None:
        sub = '<span style="font-size:10px;color:#a99f8c;">—</span>'
    else:
        col = '#2f8f5b' if pc >= 0 else '#c14a32'
        arrow = '▲' if pc >= 0 else '▼'
        sub = f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;color:{col};">{arrow}{abs(pc):.2f}%</span>'
    return f'''<div style="background:#faf6ee;border:1px solid #efe7d7;border-radius:7px;padding:8px 10px;">
  <div style="font-size:10px;color:#6b6256;margin-bottom:3px;">{label}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:15px;font-weight:600;color:#1d1a15;">{val}</div>
  {sub}
</div>'''

macro_tiles_html = ''.join(macro_tile(k, l, fk) for k, l, fk in MACRO_TILES)

macro_card = f'''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:10px;">Extended Macro</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">{macro_tiles_html}</div>
</div>'''

# ── Fed & Policy Calendar card ─────────────────────────────────────────────────

fed_card = '''<div style="background:#ffffff;border:1px solid #e8e0d2;border-radius:9px;padding:14px 15px;box-shadow:0 1px 2px rgba(70,55,25,0.04);display:flex;flex-direction:column;min-width:0;">
  <div style="font-size:10.5px;font-weight:600;letter-spacing:0.09em;text-transform:uppercase;color:#a2987f;margin-bottom:10px;">Fed &amp; Policy Calendar</div>
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
    <span style="font-size:11px;color:#6b6256;">Fed Funds Target</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;background:#f4eedf;border:1px solid #e3d9c6;border-radius:4px;padding:2px 8px;color:#2b2620;">4.25–4.50%</span>
  </div>
  <div style="font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#a99f8c;margin-bottom:6px;">Next FOMC</div>
  <div style="display:flex;flex-direction:column;gap:5px;margin-bottom:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span style="font-size:11.5px;color:#2b2620;">Jul 29–30, 2026</span>
      <span style="background:#f4eedf;border:1px solid #e3d9c6;border-radius:3px;padding:1px 6px;font-size:9.5px;color:#8a7f5f;">Hold expected</span>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <span style="font-size:11.5px;color:#2b2620;">Sep 16–17, 2026</span>
      <span style="background:#edf7f1;border:1px solid #c3e6d1;border-radius:3px;padding:1px 6px;font-size:9.5px;color:#2f8f5b;">Cut priced in</span>
    </div>
  </div>
  <div style="font-size:10px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#a99f8c;margin-bottom:6px;">Next Data Releases</div>
  <div style="display:flex;flex-direction:column;gap:5px;">
    <div style="display:flex;justify-content:space-between;font-size:11.5px;">
      <span style="color:#2b2620;">CPI (May)</span>
      <span style="font-family:'IBM Plex Mono',monospace;color:#6b6256;">Jul 11, 2026</span>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:11.5px;">
      <span style="color:#2b2620;">NFP (Jun)</span>
      <span style="font-family:'IBM Plex Mono',monospace;color:#6b6256;">Jul 3, 2026</span>
    </div>
    <div style="display:flex;justify-content:space-between;font-size:11.5px;">
      <span style="color:#2b2620;">PCE (May)</span>
      <span style="font-family:'IBM Plex Mono',monospace;color:#6b6256;">Jun 27, 2026</span>
    </div>
  </div>
</div>'''

# ── Assemble full HTML ─────────────────────────────────────────────────────────

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
@keyframes mkd-scroll{{from{{transform:translateX(0);}}to{{transform:translateX(-50%);}}}}
@keyframes mkd-spin{{from{{transform:rotate(0deg);}}to{{transform:rotate(360deg);}}}}
button{{cursor:pointer;transition:filter 0.1s;}}
button:hover{{filter:brightness(0.94);}}
</style>
</head>
<body style="background:#ece5d8;font-family:'IBM Plex Sans',sans-serif;color:#2b2620;padding:16px 18px 26px;min-height:100vh;">
<div style="max-width:1520px;margin:0 auto;">

  <!-- HEADER -->
  <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:18px;flex-wrap:wrap;margin-bottom:14px;">
    <div style="display:flex;flex-direction:column;gap:3px;">
      <div style="display:flex;align-items:center;gap:10px;">
        <div style="width:26px;height:26px;border-radius:6px;background:#2b2620;display:flex;align-items:center;justify-content:center;color:#ece5d8;font-family:'Spectral',serif;font-weight:700;font-size:15px;">M</div>
        <div style="font-family:'Spectral',serif;font-weight:600;font-size:23px;letter-spacing:-0.01em;color:#211d18;">Institutional Market Dashboard</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:500;letter-spacing:0.08em;color:#8a7f5f;border:1px solid #d8cdb6;border-radius:4px;padding:2px 6px;background:#f4eedf;">OTP2.0</div>
      </div>
      <div style="font-size:11.5px;color:#7c7264;letter-spacing:0.01em;padding-left:36px;">Macro · Positioning · Commodities · Rates · Prices delayed ~15 min</div>
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
      <button id="refresh-btn" onclick="doRefresh()" style="display:flex;align-items:center;gap:7px;background:#2b2620;color:#f3eee2;border:none;border-radius:8px;padding:9px 15px;font-family:'IBM Plex Sans',sans-serif;font-size:12.5px;font-weight:500;">
        <span id="refresh-icon" style="font-size:13px;">↻</span>
        <span id="refresh-label">Refresh</span>
      </button>
    </div>
  </div>

  <!-- TICKER STRIP -->
  <div style="overflow:hidden;background:#fbf8f1;border:1px solid #e3d9c6;border-radius:8px;padding:8px 0;margin-bottom:14px;-webkit-mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);">
    <div style="display:flex;width:max-content;animation:mkd-scroll 48s linear infinite;">
      {ticker_2x}
    </div>
  </div>

  <!-- PORTFOLIO CORRELATION | SECTOR ROTATION -->
  <div style="display:flex;gap:14px;align-items:stretch;flex-wrap:wrap;margin-bottom:12px;">
    {corr_card_html}
    {sector_card}
  </div>

  <!-- ROW 1: price charts | yield curve | dr copper | risk & rates -->
  <!-- Explicit 2-row grid (not per-column flex stacks) so every card in the
  top row shares one height and every card in the bottom row shares another —
  grid auto-placement fills row 1 (yield/copper/risk) then row 2 (their
  sub-cards) around the price-chart block, which spans both via grid-row. -->
  <div style="display:grid;grid-template-columns:1.95fr 1.12fr 1.12fr 1.02fr;grid-template-rows:auto auto;gap:12px;margin-bottom:12px;">
    <div style="grid-row:1 / span 2;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:12px;min-width:0;">
      {cards_html}
    </div>
    {yield_card}
    {copper_card}
    {risk_card}
    {yield_spread_card}
    {copper_gold_card}
    {vol_premium_card}
  </div>

  <!-- ROW 2: cot | global | macro | fed -->
  <div style="display:grid;grid-template-columns:1.28fr 1fr 1.05fr 1fr;gap:12px;align-items:stretch;margin-bottom:16px;">
    {cot_card}
    {global_card}
    {macro_card}
    {fed_card}
  </div>

  <!-- FOOTER -->
  <div style="font-size:10px;color:#a99f8c;text-align:center;letter-spacing:0.03em;">
    Data via Yahoo Finance · Prices delayed ~15 min · For informational purposes only · COT positioning is illustrative
  </div>
</div>

<script>
const SERIES = {series_json};
const COLORS = {colors_json};

// NYSE market holidays (fixed + computed)
function isNYSEHoliday(d) {{
  const y = d.getFullYear(), m = d.getMonth()+1, day = d.getDate(), dow = d.getDay();
  // Helper: nth weekday of month (dow: 0=Sun,1=Mon,...; n: 1-based)
  function nthDow(yr, mo, weekday, n) {{
    let count=0;
    for (let i=1;i<=31;i++) {{
      const dt = new Date(yr,mo-1,i);
      if (dt.getMonth()!==mo-1) break;
      if (dt.getDay()===weekday && ++count===n) return i;
    }}
  }}
  // Last Monday of month
  function lastMon(yr, mo) {{
    for (let i=31;i>=1;i--) {{
      const dt = new Date(yr,mo-1,i);
      if (dt.getMonth()!==mo-1) continue;
      if (dt.getDay()===1) return i;
    }}
  }}
  // Good Friday (2 days before Easter)
  function goodFriday(yr) {{
    const a=yr%19,b=Math.floor(yr/100),c=yr%100,d2=Math.floor(b/4),e=b%4;
    const f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d2-g+15)%30;
    const i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7;
    const m2=Math.floor((a+11*h+22*l)/451);
    const mo2=Math.floor((h+l-7*m2+114)/31),dy=(h+l-7*m2+114)%31+1;
    const easter=new Date(yr,mo2-1,dy);
    easter.setDate(easter.getDate()-2);
    return {{m:easter.getMonth()+1,d:easter.getDate()}};
  }}
  // Saturday/Sunday always closed
  if (dow===0||dow===6) return true;
  // Observed holiday: if Jul 4/Dec 25/Jan 1 falls on Sat → Fri; Sun → Mon
  function observed(mo2,dy2) {{
    const dt=new Date(y,mo2-1,dy2);
    const w=dt.getDay();
    if (w===6) return {{m:mo2,d:dy2-1}};
    if (w===0) return {{m:mo2,d:dy2+1}};
    return {{m:mo2,d:dy2}};
  }}
  const gf = goodFriday(y);
  const holidays = [
    observed(1,1),          // New Year's Day
    {{m:1,d:nthDow(y,1,1,3)}},  // MLK Day (3rd Mon Jan)
    {{m:2,d:nthDow(y,2,1,3)}},  // Presidents' Day (3rd Mon Feb)
    gf,                     // Good Friday
    {{m:5,d:lastMon(y,5)}},     // Memorial Day (last Mon May)
    observed(6,19),         // Juneteenth
    observed(7,4),          // Independence Day
    {{m:9,d:nthDow(y,9,1,1)}},  // Labor Day (1st Mon Sep)
    {{m:11,d:nthDow(y,11,4,4)}},// Thanksgiving (4th Thu Nov)
    observed(12,25),        // Christmas
  ];
  return holidays.some(h2 => h2 && h2.m===m && h2.d===day);
}}

// Live clocks
function tick() {{
  const now = new Date();
  document.getElementById('local-time').textContent = now.toLocaleTimeString('en-US', {{hour12:false}});
  const etOpts = {{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}};
  document.getElementById('et-time').textContent = now.toLocaleTimeString('en-US', etOpts);
  const etDate = new Date(now.toLocaleString('en-US', {{timeZone:'America/New_York'}}));
  const dow = etDate.getDay(), h = etDate.getHours();
  const open = dow >= 1 && dow <= 5 && h >= 9 && h < 16 && !isNYSEHoliday(etDate);
  const dot = document.getElementById('nyse-dot');
  const lbl = document.getElementById('nyse-status');
  dot.style.background = open ? '#2f8f5b' : '#c14a32';
  dot.style.boxShadow = open ? '0 0 0 3px rgba(47,143,91,0.2)' : '0 0 0 3px rgba(193,74,50,0.2)';
  lbl.textContent = open ? 'OPEN' : 'CLOSED';
  lbl.style.color = open ? '#2f8f5b' : '#c14a32';
}}
setInterval(tick, 1000); tick();

// Chart rendering
function renderChart(key, prices) {{
  const svg = document.getElementById('chart-'+key);
  if (!svg || !prices || prices.length < 2) return;
  const color = COLORS[key] || '#2b2620';
  const W=320, H=96, pad=8;
  const mn = Math.min(...prices), mx = Math.max(...prices);
  const rng = mx - mn || 1;
  const n = prices.length;
  const coords = prices.map((p,i) => [i/(n-1)*W, pad+(1-(p-mn)/rng)*(H-2*pad)]);
  const lineD = coords.map((c,i)=>(i===0?'M':'L')+c[0].toFixed(1)+','+c[1].toFixed(1)).join(' ');
  const areaD = lineD+' L'+W+','+H+' L0,'+H+' Z';
  const gid = 'g'+key;
  const [lx,ly] = coords[n-1];
  svg.innerHTML = `
    <defs><linearGradient id="${{gid}}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${{color}}" stop-opacity="0.20"/>
      <stop offset="60%" stop-color="${{color}}" stop-opacity="0.04"/>
      <stop offset="100%" stop-color="${{color}}" stop-opacity="0"/>
    </linearGradient></defs>
    <line x1="0" y1="32" x2="${{W}}" y2="32" stroke="#f1ece1" stroke-width="1"/>
    <line x1="0" y1="64" x2="${{W}}" y2="64" stroke="#f1ece1" stroke-width="1"/>
    <path d="${{areaD}}" fill="url(#${{gid}})"/>
    <path d="${{lineD}}" fill="none" stroke="${{color}}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    <circle cx="${{lx.toFixed(1)}}" cy="${{ly.toFixed(1)}}" r="3.5" fill="${{color}}" stroke="white" stroke-width="1.5"/>
  `;
}}

function switchTf(key, tf, btn) {{
  const s = SERIES[key];
  if (!s || !s[tf]) return;
  const container = document.getElementById('pills-'+key);
  if (container) container.querySelectorAll('button').forEach(b => {{
    b.style.background = '#f3eee2'; b.style.color = '#8a7f6a';
  }});
  btn.style.background = '#2b2620'; btn.style.color = '#f3eee2';
  renderChart(key, s[tf]);
}}

// Init charts
Object.keys(SERIES).forEach(k => {{ if (SERIES[k]['1M']) renderChart(k, SERIES[k]['1M']); }});

// Refresh button (visual spin; actual refresh happens via Streamlit)
function doRefresh() {{
  const icon = document.getElementById('refresh-icon');
  const lbl = document.getElementById('refresh-label');
  icon.style.animation = 'mkd-spin 0.8s linear infinite';
  lbl.textContent = 'Refreshing…';
  setTimeout(() => {{ icon.style.animation=''; lbl.textContent='Refresh'; }}, 1500);
}}
</script>
</body>
</html>'''

st.iframe(html, height=1160)
