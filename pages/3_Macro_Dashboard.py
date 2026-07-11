"""
Macro Signal Dashboard — ported from the Claude-design handoff (Round 6).

Source: "Macro-economics dashboard design.zip" → `Macro Signal Dashboard.dc.html`
(high-fidelity prototype) + README spec. Re-implemented per the handoff
instructions: the prototype runtime (support.js / DCLogic) is NOT reused — the
markup lives here as JS template literals and the logic class was ported to
plain JS functions.

Architecture: this file is a thin Streamlit shell; the dashboard itself is one
self-contained HTML/JS document rendered via components.html(). All data is the
design's own inline MOCK dataset (5 regions: US / EU / CN / JP / GL) — wiring to
real feeds (and/or macro_data.py) is a later, contained step: replace the JS
DATA/EXTRA maps, keep renderVals() and the templates unchanged.

Interactions: region <select> re-renders every panel and persists to
localStorage['macro_region']; a 1s clock patches only the clock elements.
"""

import streamlit as st

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

# NOTE: plain string (not an f-string) — the payload is a JS app full of braces;
# no Python interpolation is needed because all data lives in the JS below.
HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; }
  @keyframes mp-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.35;transform:scale(.82)} }
  .mp-select { -webkit-appearance:none; appearance:none; cursor:pointer; }
  .mp-select:focus { outline:2px solid rgba(160,123,29,.4); outline-offset:1px; }
</style>
</head>
<body>
<div style="min-height:100%; background:#E8DECB; padding:10px 18px 12px; font-family:'IBM Plex Sans',sans-serif; color:#2B2721;">
<div style="max-width:1820px; margin:0 auto;">

  <!-- ===== HEADER (static; region-dependent bits patched by JS) ===== -->
  <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:7px;">
    <div style="display:flex; align-items:center; gap:14px;">
      <div style="width:40px; height:40px; border-radius:9px; background:#2B2721; color:#E8DECB; display:flex; align-items:center; justify-content:center; font-family:'Newsreader',serif; font-size:24px; font-weight:600;">M</div>
      <div>
        <div style="display:flex; align-items:center; gap:10px;">
          <div style="font-family:'Newsreader',serif; font-size:22px; font-weight:600; letter-spacing:-.01em; line-height:1;">Macro Signal Dashboard</div>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; padding:3px 7px; border:1px solid rgba(0,0,0,.16); border-radius:5px; color:#8A8172;">OTP2.0</span>
        </div>
        <div style="display:flex; align-items:center; gap:10px; margin-top:9px;">
          <span style="font-size:10px; letter-spacing:.14em; color:#8A8172; text-transform:uppercase; font-weight:600;">Region</span>
          <div style="position:relative;">
            <select id="mp-region" class="mp-select" style="font-family:'IBM Plex Sans',sans-serif; font-size:13px; font-weight:600; color:#2B2721; background:#FBF8F1; border:1px solid rgba(0,0,0,.16); border-radius:7px; padding:6px 30px 6px 12px; line-height:1;">
              <option value="US">United States</option>
              <option value="EU">Euro Area</option>
              <option value="CN">China</option>
              <option value="JP">Japan</option>
              <option value="GL">Global (agg)</option>
            </select>
            <span style="position:absolute; right:11px; top:50%; transform:translateY(-50%); pointer-events:none; color:#8A8172; font-size:9px;">▼</span>
          </div>
        </div>
      </div>
    </div>
    <div style="display:flex; align-items:center; gap:14px; background:#FBF8F1; border:1px solid rgba(0,0,0,.1); border-radius:10px; padding:9px 15px;">
      <div style="text-align:right;">
        <div style="display:flex; align-items:center; gap:6px; justify-content:flex-end;">
          <span id="mp-dot" style="width:8px; height:8px; border-radius:50%; background:#5E7A3B; animation:mp-pulse 2s ease-in-out infinite;"></span>
          <span id="mp-exchange" style="font-size:10px; letter-spacing:.12em; color:#8A8172; text-transform:uppercase; font-weight:600;">NYSE · ET</span>
        </div>
        <div id="mp-clock" style="font-family:'IBM Plex Mono',monospace; font-size:20px; font-weight:500; letter-spacing:.02em; margin-top:2px;">--:--:--</div>
      </div>
      <div id="mp-state" style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; color:#5E7A3B; letter-spacing:.06em;">OPEN</div>
    </div>
  </div>

  <!-- ===== DASHBOARD BODY (fully re-rendered per region) ===== -->
  <div id="mp-main"></div>

  <!-- ===== FOOTER ===== -->
  <div style="display:flex; align-items:center; justify-content:center; gap:16px; flex-wrap:wrap;">
    <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#A07B1D; border:1px solid rgba(160,123,29,.4); border-radius:6px; padding:5px 11px;">✎ MOCK DATA — placeholder values, not live levels</span>
    <span style="font-size:11px; color:#B4A98F;">Opinionated, style-dependent classification · directional reads, no validated hit-rates · region-switchable via header</span>
  </div>

</div>
</div>

<script>
// ============================================================================
// DATA MODEL — ported verbatim from the design prototype (ALL MOCK VALUES).
// Real-data wiring later = replace DATA/EXTRA, keep renderVals()/templates.
// ============================================================================
const DATA = {
  US: {
    exchange:'NYSE · ET', regimeLabel:'Stagflation', regimeColor:'#B08018', regimeDays:47, regimeSince:'May 15',
    history:[{label:'Reflation',color:'#5E7A3B',w:34},{label:'Goldilocks',color:'#8FA05A',w:26},{label:'Soft landing',color:'#C9A24B',w:40},{label:'Stagflation',color:'#B08018',w:52}],
    inflation:'3.1%', inflationSub:'core 3.3% · sticky', growth:48.7, growthSub:'ISM mfg · slowing', policy:'4.25–4.50%', policySub:'Fed · 2 cuts priced', cond:-0.15, condSub:'FCI · looser than avg',
    hingeDef:'10Y nominal = real yield + breakeven inflation',
    nom:[4.05,4.08,4.06,4.11,4.14,4.17,4.20], real:[1.92,1.93,1.92,1.94,1.93,1.94,1.95], be:[2.13,2.15,2.14,2.17,2.21,2.23,2.25],
    dNom:0.15, dReal:0.03, dBe:0.12,
    classLabel:'Inflation Scare', classDesc:'Nominal up, led by the breakeven (inflation-expectations) leg.', classTags:['duration-negative','gold-positive','risk-ambiguous'], classMover:'Breakeven leg',
    oilName:'Oil · WTI', oilVal:'70.94', oilChg:2.47, oilSpark:[68,67.5,68.2,69,69.4,70.1,70.94],
    playbook:[{side:'SHORT',asset:'Long-duration USTs',note:'BE-led selloff',color:'#B14A2E'},{side:'LONG',asset:'Gold / TIPS',note:'real-rate hedge',color:'#5E7A3B'},{side:'LONG',asset:'Energy / commods',note:'impulse tailwind',color:'#5E7A3B'},{side:'FADE',asset:'Long-duration tech',note:'rate-sensitive',color:'#B08018'}],
    curve:[['3M',4.55],['1Y',4.20],['2Y',3.86],['5Y',3.95],['7Y',4.05],['10Y',4.20],['30Y',4.45]],
    tripwires:[
      {label:'Credit · HY OAS',tag:'Leading tell for equity stress',val:'3.20%',chg:0.10,unit:' pp',state:'',note:'Widening = rising stress.',tone:'#B08018'},
      {label:'Equity Vol · VIX',tag:'Risk-on / risk-off tripwire',val:'18.2',chg:null,state:'Contango',note:'Front below back month — calm / risk-on tilt.',tone:'#5E7A3B'},
      {label:'Dollar · DXY',tag:'Global liquidity valve',val:'104.8',chg:0.30,state:'',note:'Stronger USD tightens conditions abroad.',tone:'#B08018'},
      {label:'Curve · 2s10s',tag:'Late-cycle / recession watch',val:'+0.34',chg:null,state:'Normal',note:'Upward-sloping — no curve-inversion warning.',tone:'#5E7A3B'} ],
    cross:[['S&P 500',0.4,1.2,3.1,14.2],['Nasdaq 100',0.6,1.8,4.0,19.5],['UST 10Y',-0.3,-0.9,-1.4,-3.2],['IG Credit',-0.1,0.2,0.9,4.1],['HY Credit',0.2,0.7,1.6,6.8],['USD (DXY)',0.3,0.5,-0.8,1.9],['Gold',0.9,2.4,5.2,16.4],['Brent',1.1,3.0,4.8,-2.1],['Copper',-0.4,0.9,2.2,7.3]],
    cb:{name:'FOMC · Federal Reserve',days:29,date:'Jul 30',action:'Hold',prob:78,move:'no change'},
    releases:[['MON','ISM Manufacturing','48.5'],['WED','ADP Employment','+150k'],['THU','Initial Jobless Claims','232k'],['FRI','Nonfarm Payrolls','+175k'],['FRI','Unemployment Rate','4.1%']],
    positioning:[['USTs',-1.4],['S&P 500',0.8],['USD',1.2],['Gold',1.9],['Crude',0.6],['EUR',-0.7]]
  },
  EU: {
    exchange:'Euronext · CET', regimeLabel:'Disinflation', regimeColor:'#5E7A3B', regimeDays:88, regimeSince:'Apr 4',
    history:[{label:'Stagnation',color:'#B08018',w:44},{label:'Reflation',color:'#8FA05A',w:24},{label:'Disinflation',color:'#5E7A3B',w:56},{label:'Disinflation',color:'#5E7A3B',w:28}],
    inflation:'2.2%', inflationSub:'core 2.4% · easing', growth:47.3, growthSub:'PMI comp · below 50', policy:'3.25%', policySub:'ECB · 1 cut priced', cond:0.22, condSub:'FCI · tighter than avg',
    hingeDef:'10Y Bund = real yield + breakeven inflation',
    nom:[2.58,2.55,2.52,2.50,2.48,2.46,2.44], real:[0.34,0.33,0.31,0.30,0.29,0.28,0.27], be:[2.24,2.22,2.21,2.20,2.19,2.18,2.17],
    dNom:-0.14, dReal:-0.07, dBe:-0.07,
    classLabel:'Easing Path', classDesc:'Nominal drifting lower, led by the real-yield leg as cuts get priced.', classTags:['duration-positive','euro-soft','risk-supportive'], classMover:'Real-yield leg',
    oilName:'Gas · TTF', oilVal:'32.10', oilChg:-1.80, oilSpark:[35,34.2,33.8,33.1,32.9,32.5,32.1],
    playbook:[{side:'LONG',asset:'Bund duration',note:'cuts ahead',color:'#5E7A3B'},{side:'LONG',asset:'EU periphery',note:'spread carry',color:'#5E7A3B'},{side:'FADE',asset:'EUR/USD rallies',note:'rate diff',color:'#B08018'},{side:'LONG',asset:'EU cyclicals',note:'easing beta',color:'#5E7A3B'}],
    curve:[['3M',3.40],['1Y',2.95],['2Y',2.55],['5Y',2.40],['7Y',2.48],['10Y',2.44],['30Y',2.72]],
    tripwires:[
      {label:'Credit · iTraxx XO',tag:'Leading tell for equity stress',val:'298',chg:-6,unit:'',state:'bp',note:'Tightening = risk appetite firm.',tone:'#5E7A3B'},
      {label:'Equity Vol · VSTOXX',tag:'Risk-on / risk-off tripwire',val:'16.4',chg:null,state:'Calm',note:'Subdued — supportive backdrop.',tone:'#5E7A3B'},
      {label:'EUR/USD',tag:'Global liquidity valve',val:'1.082',chg:-0.20,state:'',note:'Soft EUR eases financial conditions.',tone:'#5E7A3B'},
      {label:'Curve · 2s10s',tag:'Late-cycle / recession watch',val:'-0.11',chg:null,state:'Flat',note:'Mildly inverted — bull-steepening watch.',tone:'#B08018'} ],
    cross:[['Euro Stoxx 50',0.3,0.9,2.4,9.8],['DAX',0.5,1.1,2.8,11.2],['Bund 10Y',0.4,1.0,1.8,2.9],['IG Credit',0.1,0.4,1.2,4.6],['HY Credit',0.3,0.8,1.9,7.1],['EUR (index)',-0.2,-0.5,-1.1,-1.4],['Gold (EUR)',0.7,2.0,4.6,17.9],['Brent',1.1,3.0,4.8,-2.1],['Copper',-0.4,0.9,2.2,7.3]],
    cb:{name:'Governing Council · ECB',days:16,date:'Jul 17',action:'Cut 25bp',prob:64,move:'a 25bp cut'},
    releases:[['MON','HCOB Mfg PMI','45.8'],['TUE','Flash CPI (YoY)','2.2%'],['WED','PPI (MoM)','-0.1%'],['THU','ECB Minutes','—'],['FRI','Retail Sales','+0.3%']],
    positioning:[['Bunds',1.6],['Euro Stoxx',0.4],['EUR',-1.1],['Gold',1.7],['Brent',0.5],['GBP',0.2]]
  },
  CN: {
    exchange:'SSE · CST', regimeLabel:'Deflation Risk', regimeColor:'#B14A2E', regimeDays:132, regimeSince:'Feb 20',
    history:[{label:'Reopening',color:'#5E7A3B',w:30},{label:'Slowdown',color:'#C9A24B',w:38},{label:'Deflation risk',color:'#B14A2E',w:60},{label:'Deflation risk',color:'#B14A2E',w:24}],
    inflation:'0.3%', inflationSub:'core 0.6% · soft', growth:49.5, growthSub:'Caixin PMI · fragile', policy:'3.10%', policySub:'PBoC · easing bias', cond:0.05, condSub:'FCI · near neutral',
    hingeDef:'10Y CGB = real yield + breakeven inflation',
    nom:[2.28,2.24,2.20,2.16,2.12,2.10,2.08], real:[1.42,1.40,1.38,1.35,1.33,1.32,1.31], be:[0.86,0.84,0.82,0.81,0.79,0.78,0.77],
    dNom:-0.20, dReal:-0.11, dBe:-0.09,
    classLabel:'Deflation Watch', classDesc:'Nominal grinding lower with breakevens near zero — demand deficit signal.', classTags:['duration-positive','cny-weak','stimulus-sensitive'], classMover:'Breakeven leg',
    oilName:'Iron Ore', oilVal:'98.40', oilChg:-2.10, oilSpark:[106,104,102,101,100,99,98.4],
    playbook:[{side:'LONG',asset:'CGB duration',note:'deflation bid',color:'#5E7A3B'},{side:'FADE',asset:'CNY strength',note:'easing bias',color:'#B08018'},{side:'WATCH',asset:'Stimulus proxies',note:'policy optionality',color:'#B08018'},{side:'SHORT',asset:'Industrial metals',note:'demand deficit',color:'#B14A2E'}],
    curve:[['3M',1.75],['1Y',1.85],['2Y',1.98],['5Y',2.02],['7Y',2.05],['10Y',2.08],['30Y',2.28]],
    tripwires:[
      {label:'Credit · Property HY',tag:'Leading tell for equity stress',val:'21.4%',chg:0.60,unit:' pp',state:'',note:'Elevated — property stress lingers.',tone:'#B14A2E'},
      {label:'Equity Vol · CSI Vol',tag:'Risk-on / risk-off tripwire',val:'19.8',chg:null,state:'Uneasy',note:'Policy-headline sensitive.',tone:'#B08018'},
      {label:'USD/CNH',tag:'Global liquidity valve',val:'7.28',chg:0.15,state:'',note:'Weaker CNH signals easing pressure.',tone:'#B08018'},
      {label:'Curve · 2s10s',tag:'Late-cycle / recession watch',val:'+0.10',chg:null,state:'Flat',note:'Very flat — low growth expectations.',tone:'#B08018'} ],
    cross:[['CSI 300',-0.6,-1.4,-2.8,-4.5],['Hang Seng',0.4,1.1,2.0,12.6],['CGB 10Y',0.5,1.2,2.4,5.8],['Property HY',-1.2,-2.6,-4.0,-11.2],['CNY (index)',-0.2,-0.6,-1.2,-2.4],['Copper',-0.4,0.9,2.2,7.3],['Iron Ore',-1.5,-3.2,-6.1,-14.8],['Gold (CNY)',0.9,2.4,5.4,18.9],['Brent',1.1,3.0,4.8,-2.1]],
    cb:{name:'LPR Fixing · PBoC',days:20,date:'Jul 21',action:'Cut 10bp',prob:55,move:'a 10bp LPR cut'},
    releases:[['MON','Caixin Mfg PMI','49.5'],['WED','CPI (YoY)','0.3%'],['WED','PPI (YoY)','-1.6%'],['THU','Trade Balance','$78b'],['FRI','New Loans','¥1.9tn']],
    positioning:[['CGBs',1.8],['CSI 300',-0.9],['CNY',-1.4],['Copper',-0.6],['Iron Ore',-1.7],['Gold',1.6]]
  },
  JP: {
    exchange:'TSE · JST', regimeLabel:'Reflation', regimeColor:'#5E7A3B', regimeDays:210, regimeSince:'Dec 3',
    history:[{label:'Deflation',color:'#B14A2E',w:40},{label:'Exit',color:'#C9A24B',w:30},{label:'Reflation',color:'#5E7A3B',w:64},{label:'Reflation',color:'#5E7A3B',w:28}],
    inflation:'2.6%', inflationSub:'core 2.4% · firming', growth:50.9, growthSub:'PMI · expanding', policy:'0.25%', policySub:'BoJ · hikes ahead', cond:-0.08, condSub:'FCI · accommodative',
    hingeDef:'10Y JGB = real yield + breakeven inflation',
    nom:[1.00,1.02,1.04,1.05,1.06,1.05,1.06], real:[-0.52,-0.51,-0.50,-0.49,-0.49,-0.50,-0.49], be:[1.52,1.53,1.54,1.54,1.55,1.55,1.55],
    dNom:0.06, dReal:0.03, dBe:0.03,
    classLabel:'Normalization', classDesc:'Nominal rising as BoJ exits negative rates — breakevens anchoring above target.', classTags:['duration-negative','yen-supportive','equity-mixed'], classMover:'Real-yield leg',
    oilName:'Oil · JPY', oilVal:'11,240', oilChg:1.90, oilSpark:[10800,10900,11000,11050,11120,11180,11240],
    playbook:[{side:'SHORT',asset:'JGB duration',note:'normalization',color:'#B14A2E'},{side:'LONG',asset:'JPY vs USD',note:'carry unwind',color:'#5E7A3B'},{side:'LONG',asset:'JP banks',note:'steeper curve',color:'#5E7A3B'},{side:'FADE',asset:'Exporters',note:'stronger yen',color:'#B08018'}],
    curve:[['3M',0.10],['1Y',0.28],['2Y',0.44],['5Y',0.72],['7Y',0.88],['10Y',1.06],['30Y',2.10]],
    tripwires:[
      {label:'Credit · JP IG',tag:'Leading tell for equity stress',val:'62',chg:-1,unit:'',state:'bp',note:'Tight — corporate stress low.',tone:'#5E7A3B'},
      {label:'Equity Vol · N225 Vol',tag:'Risk-on / risk-off tripwire',val:'20.6',chg:null,state:'Elevated',note:'FX-driven volatility risk.',tone:'#B08018'},
      {label:'USD/JPY',tag:'Global liquidity valve',val:'156.2',chg:-0.40,state:'',note:'Intervention watch above 158.',tone:'#B08018'},
      {label:'Curve · 2s10s',tag:'Late-cycle / recession watch',val:'+0.62',chg:null,state:'Steep',note:'Bear-steepening as BoJ exits.',tone:'#5E7A3B'} ],
    cross:[['Nikkei 225',0.7,1.6,3.4,16.8],['TOPIX',0.5,1.3,2.9,14.1],['JGB 10Y',-0.4,-1.1,-2.0,-4.4],['JP IG',0.1,0.3,0.8,2.6],['JPY (index)',0.4,1.0,2.2,-6.8],['Gold (JPY)',0.6,2.1,5.0,24.2],['Brent',1.1,3.0,4.8,-2.1],['Copper',-0.4,0.9,2.2,7.3],['JP banks',0.9,2.4,5.1,22.4]],
    cb:{name:'Policy Meeting · BoJ',days:30,date:'Jul 31',action:'Hike 15bp',prob:48,move:'a 15bp hike'},
    releases:[['MON','Tankan Survey','+13'],['TUE','Jibun Mfg PMI','50.9'],['WED','Wages (YoY)','+2.8%'],['THU','Machine Orders','+1.2%'],['FRI','Tokyo CPI','2.5%']],
    positioning:[['JGBs',-1.3],['Nikkei',0.9],['JPY',0.7],['Gold',1.4],['JP banks',1.5],['Brent',0.5]]
  },
  GL: {
    exchange:'Global · UTC', regimeLabel:'Late Cycle', regimeColor:'#B08018', regimeDays:63, regimeSince:'Apr 29',
    history:[{label:'Recovery',color:'#5E7A3B',w:30},{label:'Mid cycle',color:'#8FA05A',w:34},{label:'Late cycle',color:'#B08018',w:56},{label:'Late cycle',color:'#B08018',w:28}],
    inflation:'3.4%', inflationSub:'DM core 3.0% · mixed', growth:49.8, growthSub:'Global PMI · flat', policy:'—', policySub:'DM · net easing bias', cond:0.03, condSub:'GFCI · near neutral',
    hingeDef:'DM 10Y agg = real yield + breakeven inflation',
    nom:[3.30,3.32,3.31,3.35,3.38,3.40,3.42], real:[1.10,1.10,1.09,1.11,1.12,1.12,1.13], be:[2.20,2.22,2.22,2.24,2.26,2.28,2.29],
    dNom:0.12, dReal:0.03, dBe:0.09,
    classLabel:'Late-Cycle Drift', classDesc:'Aggregate nominal firming, breakeven-led — global reflation micro-pulse.', classTags:['duration-negative','commodity-tilt','dispersion-high'], classMover:'Breakeven leg',
    oilName:'Brent · Global', oilVal:'74.20', oilChg:1.80, oilSpark:[71,71.5,72,72.8,73.3,73.8,74.2],
    playbook:[{side:'UW',asset:'DM duration',note:'reflation pulse',color:'#B14A2E'},{side:'OW',asset:'Real assets',note:'inflation hedge',color:'#5E7A3B'},{side:'OW',asset:'EM ex-China',note:'carry + easing',color:'#5E7A3B'},{side:'NEUTRAL',asset:'DM equities',note:'valuation-capped',color:'#B08018'}],
    curve:[['3M',4.10],['1Y',3.80],['2Y',3.55],['5Y',3.40],['7Y',3.44],['10Y',3.42],['30Y',3.70]],
    tripwires:[
      {label:'Credit · Global HY',tag:'Leading tell for equity stress',val:'3.60%',chg:0.08,unit:' pp',state:'',note:'Contained — no systemic widening.',tone:'#5E7A3B'},
      {label:'Equity Vol · VIX',tag:'Risk-on / risk-off tripwire',val:'17.4',chg:null,state:'Contango',note:'Calm cross-asset vol regime.',tone:'#5E7A3B'},
      {label:'Dollar · DXY',tag:'Global liquidity valve',val:'103.9',chg:-0.10,state:'',note:'Sideways USD — liquidity neutral.',tone:'#5E7A3B'},
      {label:'Curve · 2s10s',tag:'Late-cycle / recession watch',val:'-0.13',chg:null,state:'Flat',note:'Aggregate near flat — dispersion high.',tone:'#B08018'} ],
    cross:[['MSCI World',0.4,1.1,2.9,13.4],['MSCI EM',0.6,1.5,3.2,9.1],['Global Agg',-0.2,-0.6,-1.1,-2.0],['Global IG',-0.1,0.2,0.9,3.8],['Global HY',0.2,0.7,1.7,6.9],['USD (DXY)',-0.1,-0.3,-0.6,1.1],['Gold',0.8,2.2,5.0,17.1],['Brent',1.1,3.0,4.8,-1.2],['Copper',-0.4,0.9,2.2,7.3]],
    cb:{name:'Next up · FOMC',days:29,date:'Jul 30',action:'Hold',prob:74,move:'no change'},
    releases:[['MON','Global Mfg PMI','49.8'],['WED','US ISM Services','52.1'],['THU','EU Retail Sales','+0.3%'],['FRI','US Payrolls','+175k'],['FRI','CA Employment','+22k']],
    positioning:[['DM Bonds',-0.9],['Global Eq',0.7],['USD',0.3],['Gold',1.8],['Brent',0.9],['EM FX',0.5]]
  }
};

const EXTRA = {
  US: {
    labor:[['Nonfarm Payrolls','+175k','prev +206k'],['Unemployment','4.1%','+0.1 m/m'],['Avg Hourly Earn','3.9% y/y','−0.1 pp'],['Jobless Claims','232k','+8k w/w'],['Participation','62.6%','flat'],['JOLTS Openings','8.10M','−0.20M']],
    fx:[['EUR/USD',-0.20,-1.4],['USD/JPY',0.30,8.2],['GBP/USD',-0.15,0.9],['USD/CNH',0.15,2.1],['USD/CHF',0.10,3.4],['AUD/USD',-0.25,-2.8]],
    commods:[['WTI Crude','70.94',2.47],['Brent','74.20',1.80],['Copper','4.28',-0.90],['Gold','2412',0.85],['Nat Gas','2.68',-1.20]],
    esi:12, esiTrend:[-9,-12,-8,-4,1,6,9,12],
    surprises:[['ISM Mfg',-0.6],['ADP',0.4],['Jobless Claims',-0.3],['Nonfarm Payrolls',-0.8],['CPI',0.9],['Retail Sales',0.5]] },
  EU: {
    labor:[['Unemployment','6.4%','flat'],['Employment q/q','+0.3%','+0.1 pp'],['Neg. Wages','4.7% y/y','−0.2 pp'],['Youth Unemp','14.2%','−0.1 pp'],['Participation','65.8%','+0.1'],['Vacancy Rate','2.9%','−0.1']],
    fx:[['EUR/USD',-0.20,-1.4],['EUR/GBP',0.10,-0.6],['EUR/JPY',0.25,6.8],['EUR/CHF',0.08,1.2],['GBP/USD',-0.15,0.9],['USD/SEK',0.30,4.1]],
    commods:[['Brent','74.20',1.80],['TTF Gas','32.10',-1.80],['Copper','4.28',-0.90],['Gold (EUR)','2228',0.70],['Carbon EUA','68.40',1.10]],
    esi:-4, esiTrend:[6,3,-1,-4,-6,-3,-5,-4],
    surprises:[['HCOB PMI',-0.5],['Flash CPI',-0.2],['PPI',-0.4],['ZEW',0.6],['Ifo',-0.3],['Retail Sales',0.2]] },
  CN: {
    labor:[['Surveyed Unemp','5.1%','+0.1 pp'],['Youth Unemp','14.9%','+0.3 pp'],['Urban Jobs YTD','6.8M','on track'],['Avg Wage g','4.2% y/y','−0.3 pp'],['Mfg Employment','48.1','−0.4'],['Svc Employment','49.6','−0.2']],
    fx:[['USD/CNH',0.15,2.1],['USD/CNY',0.12,1.9],['CNH/JPY',-0.10,5.4],['EUR/CNH',-0.08,0.6],['AUD/CNH',-0.20,-1.1],['CNH/HKD',0.05,0.3]],
    commods:[['Iron Ore','98.40',-2.10],['Copper','4.28',-0.90],['Brent','74.20',1.80],['Thermal Coal','118.5',-1.40],['Gold (CNY)','560.2',0.80]],
    esi:-11, esiTrend:[-4,-7,-10,-12,-11,-9,-12,-11],
    surprises:[['Caixin PMI',-0.4],['CPI',-0.7],['PPI',-0.9],['Exports',0.5],['Retail Sales',-0.3],['New Loans',-0.6]] },
  JP: {
    labor:[['Unemployment','2.5%','flat'],['Jobs/Applicants','1.26','+0.01'],['Wages nominal','+2.8% y/y','+0.2 pp'],['Real Wages','−0.4% y/y','+0.3 pp'],['Participation','63.1%','+0.1'],['Shunto Wage','5.1%','—']],
    fx:[['USD/JPY',-0.40,8.2],['EUR/JPY',-0.20,6.8],['GBP/JPY',-0.15,7.1],['AUD/JPY',-0.30,4.6],['CNH/JPY',-0.10,5.4],['CHF/JPY',-0.05,9.0]],
    commods:[['WTI (JPY)','11,240',1.90],['Brent','74.20',1.80],['Copper','4.28',-0.90],['Gold (JPY)','12,050',0.90],['LNG (JKM)','12.40',-1.60]],
    esi:8, esiTrend:[-2,1,3,5,6,8,7,8],
    surprises:[['Tankan',0.7],['Jibun PMI',0.3],['Wages',0.6],['Machine Orders',0.4],['Tokyo CPI',0.5],['Exports',0.2]] },
  GL: {
    labor:[['DM Unemp (agg)','4.6%','flat'],['US Payrolls','+175k','prev +206k'],['EU Unemp','6.4%','flat'],['JP Unemp','2.5%','flat'],['DM Wage g','4.1% y/y','−0.1 pp'],['Global PMI Emp','49.6','−0.2']],
    fx:[['DXY',0.10,1.1],['EUR/USD',-0.20,-1.4],['USD/JPY',0.30,8.2],['GBP/USD',-0.15,0.9],['USD/CNH',0.15,2.1],['EM FX idx',-0.30,-0.4]],
    commods:[['Brent','74.20',1.80],['WTI','70.94',2.47],['Copper','4.28',-0.90],['Gold','2412',0.85],['BBG Cmdty','98.6',0.60]],
    esi:2, esiTrend:[-6,-4,-2,0,1,3,2,2],
    surprises:[['Global PMI',-0.2],['US CPI',0.9],['EU CPI',-0.2],['China PPI',-0.9],['US Payrolls',-0.8],['Global Retail',0.3]] }
};

// ============================================================================
// HELPERS — ported from the prototype logic class.
// ============================================================================
function sign(v, dp, pct) { dp = (dp===undefined)?2:dp; return (v>=0?'+':'') + v.toFixed(dp) + (pct?'%':''); }
function toneUpDown(v) { return v>=0 ? '#5E7A3B' : '#B14A2E'; }
function bpSign(v) { return (v>=0?'+':'') + Math.round(v) + ' bp'; }
function buildPath(arr, x, yfn) { return arr.map((v,i)=> (i?'L':'M')+x(i).toFixed(1)+' '+yfn(v).toFixed(1)).join(' '); }
function heatColor(v) {
  const cap = 8; const a = Math.min(Math.abs(v)/cap, 1);
  if (v >= 0) return { bg:`rgba(94,122,59,${(0.10+a*0.32).toFixed(3)})`, fg:'#2B2721' };
  return { bg:`rgba(177,74,46,${(0.10+a*0.32).toFixed(3)})`, fg:'#2B2721' };
}
function makeSpark(last, chgPct) {
  const start = last / (1 + chgPct/100); const arr=[];
  for (let i=0;i<7;i++){ const base=start+(last-start)*(i/6); const wig=Math.sin(i*1.7+(last%3))*(last-start)*0.16; arr.push(base+wig); }
  arr[6]=last; return arr;
}
function sparkPath(arr, w, h, pad) {
  pad = (pad===undefined)?2:pad;
  const lo=Math.min(...arr), hi=Math.max(...arr), r=(hi-lo)||1;
  return arr.map((v,i)=>(i?'L':'M')+((i/(arr.length-1))*(w-2*pad)+pad).toFixed(1)+' '+(h-pad-(v-lo)/r*(h-2*pad)).toFixed(1)).join(' ');
}

// ============================================================================
// renderVals(region) — every derived value + all chart geometry (ported).
// ============================================================================
function renderVals(region) {
  const d = Object.assign({}, DATA[region] || DATA.US, EXTRA[region] || EXTRA.US);

  // ----- hinge chart geometry (stacked decomposition: real + breakeven = nominal) -----
  const HL=44,HR=64,HT=18,HB=30,HW=700,HH=250;
  const n=d.nom.length;
  let lo=Math.min(0,...d.real), hi=Math.max(...d.nom); const pad=(hi-lo)*0.08||0.2; lo-=pad*0.4; hi+=pad;
  const hx=i=> HL + i/(n-1)*(HW-HL-HR);
  const hy=v=> HT + (hi-v)/(hi-lo)*(HH-HT-HB);
  const ticks=[]; for(let k=0;k<5;k++){ const v=lo+(hi-lo)*k/4; const y=hy(v); ticks.push({y:y.toFixed(1),ty:(y+3.5).toFixed(1),label:v.toFixed(2)}); }
  const dates=['Jun 23','Jun 27','Jul 1'];
  const hingeXTicks=[{x:hx(0).toFixed(1),label:dates[0],anchor:'start'},{x:hx(Math.floor((n-1)/2)).toFixed(1),label:dates[1],anchor:'middle'},{x:hx(n-1).toFixed(1),label:dates[2],anchor:'end'}];
  const mkEnd=(arr,color)=>{ const x=hx(n-1),y=hy(arr[n-1]); return {x:x.toFixed(1),y:y.toFixed(1),lx:(x-9).toFixed(1),ly:(y-8).toFixed(1),v:arr[n-1].toFixed(2),color}; };
  const areaBetween=(top,base)=>{
    let p='M'+hx(0).toFixed(1)+' '+hy(top[0]).toFixed(1);
    for(let i=1;i<n;i++) p+=' L'+hx(i).toFixed(1)+' '+hy(top[i]).toFixed(1);
    for(let i=n-1;i>=0;i--) p+=' L'+hx(i).toFixed(1)+' '+hy(base[i]).toFixed(1);
    return p+' Z';
  };
  const zeros=d.real.map(()=>0);
  const hingeRealArea=areaBetween(d.real, zeros);
  const hingeBeArea=areaBetween(d.nom, d.real);
  const hingeMidVal=((d.real[n-1]+d.nom[n-1])/2);
  const hingeBeMid={x:(hx(n-1)-6).toFixed(1), y:(hy(hingeMidVal)+4).toFixed(1), v:d.be[n-1].toFixed(2)};
  const hingeRealMid={x:(hx(n-1)-6).toFixed(1), y:(hy(d.real[n-1]/2)+4).toFixed(1), v:d.real[n-1].toFixed(2)};

  // ----- oil sparkline -----
  const os=d.oilSpark; const oLo=Math.min(...os),oHi=Math.max(...os); const orng=(oHi-oLo)||1;
  const oilSpark=os.map((v,i)=>(i?'L':'M')+(i/(os.length-1)*116+2).toFixed(1)+' '+(26-(v-oLo)/orng*22).toFixed(1)).join(' ');

  // ----- yield curve -----
  const CW=460,CH=210,CL=42,CR=14,CT=22,CBm=34;
  const cv=d.curve; const cn=cv.length;
  const prev=cv.map((p,i)=>p[1] - (0.06 - 0.05*(i/(cn-1)-0.5)*2));
  const cyv=[...cv.map(p=>p[1]),...prev];
  let clo=Math.min(...cyv),chi=Math.max(...cyv); const cpad=(chi-clo)*0.18||0.2; clo-=cpad; chi+=cpad;
  const cx=i=> CL + i/(cn-1)*(CW-CL-CR);
  const cy=v=> CT + (chi-v)/(chi-clo)*(CH-CT-CBm);
  const curvePath=cv.map((p,i)=>(i?'L':'M')+cx(i).toFixed(1)+' '+cy(p[1]).toFixed(1)).join(' ');
  const curvePrevPath=prev.map((v,i)=>(i?'L':'M')+cx(i).toFixed(1)+' '+cy(v).toFixed(1)).join(' ');
  const curvePts=cv.map((p,i)=>{ const py=cy(p[1]); return {x:cx(i).toFixed(1),y:py.toFixed(1),t:p[0],v:p[1].toFixed(2),vy:(py>CT+16?py-8:py+16).toFixed(1)}; });
  const cticks=[]; for(let k=0;k<4;k++){ const v=clo+(chi-clo)*k/3; const y=cy(v); cticks.push({y:y.toFixed(1),ty:(y+3.5).toFixed(1),label:v.toFixed(2)}); }
  const y3m=cv.find(p=>p[0]==='3M')[1], y2=cv.find(p=>p[0]==='2Y')[1], y5=cv.find(p=>p[0]==='5Y')[1], y10=cv.find(p=>p[0]==='10Y')[1], y30=cv.find(p=>p[0]==='30Y')[1];
  const spread=y10-y2, spread2=y10-y3m, spread3=y30-y5;
  const curveShape = spread<-0.05 ? 'inverted' : (spread<0.1 ? 'flat' : (spread>0.5 ? 'steep' : 'upward-sloping'));
  const idxT=t=>cv.findIndex(p=>p[0]===t);
  const tenorReadout=[['2Y',y2],['10Y',y10],['30Y',y30]].map(([t,v])=>{ const i=idxT(t); const bp=(v-prev[i])*100; return {t,v:v.toFixed(2),bp:bpSign(bp),bpColor:toneUpDown(bp)}; });

  // ----- heatmap -----
  const crossRows=d.cross.map(r=>({name:r[0],cells:r.slice(1).map(v=>{const c=heatColor(v);return {txt:sign(v,1),bg:c.bg,fg:c.fg};})}));

  // ----- positioning -----
  const positioning=d.positioning.map(p=>{ const z=p[1]; const clamped=Math.max(-3,Math.min(3,z)); const half=clamped/3*50; const color=toneUpDown(z); return { name:p[0], z:sign(z,1), color, barLeft:(z>=0?50:50+half).toFixed(1), barW:Math.abs(half).toFixed(1) }; });

  // ----- labor / fx / commods / surprises -----
  const labor=d.labor.map(l=>({name:l[0],value:l[1],delta:l[2]}));
  const fx=d.fx.map(f=>{ const d1=f[1],ytd=f[2]; const c=Math.max(-1,Math.min(1,d1)); const half=c/1*50; return { pair:f[0], d1:sign(d1,2,true), d1Color:toneUpDown(d1), ytd:sign(ytd,1,true), ytdColor:toneUpDown(ytd), barLeft:(d1>=0?50:50+half).toFixed(1), barW:Math.abs(half).toFixed(1), barColor:toneUpDown(d1) }; });
  const commods=d.commods.map(c=>{ const price=parseFloat((''+c[1]).replace(/,/g,'')); const sp=makeSpark(price,c[2]); return { name:c[0], price:c[1], chg:sign(c[2],2,true), chgColor:toneUpDown(c[2]), spark:sparkPath(sp,70,24) }; });
  const surprises=d.surprises.map(s=>{ const v=s[1]; const c=Math.max(-1.5,Math.min(1.5,v)); const half=c/1.5*50; return { name:s[0], val:sign(v,1), color:toneUpDown(v), barLeft:(v>=0?50:50+half).toFixed(1), barW:Math.abs(half).toFixed(1) }; });
  const esiSpark=sparkPath(d.esiTrend,56,20);

  // ----- releases -----
  const dayColors={MON:'#8A8172',TUE:'#8A8172',WED:'#8A8172',THU:'#8A8172',FRI:'#B08018'};
  const releases=d.releases.map(r=>({day:r[0],name:r[1],cons:r[2],dayColor:dayColors[r[0]]||'#8A8172'}));

  // ----- tripwires -----
  const tripwires=d.tripwires.map(t=>({ label:t.label, tag:t.tag, val:t.val, state:t.state, note:t.note, tone:t.tone,
    chg: t.chg==null?'':(sign(t.chg,2)+(t.unit||'')), chgColor: t.chg==null?'#8A8172':toneUpDown(t.chg) }));

  const dArrow=v=> (v>=0?'▲':'▼')+Math.abs(v).toFixed(2);

  return {
    region, exchange:d.exchange,
    regimeLabel:d.regimeLabel, regimeColor:d.regimeColor, regimeDays:d.regimeDays, regimeSince:d.regimeSince,
    regimeHistory:d.history,
    mInflation:d.inflation, mInflationSub:d.inflationSub,
    mGrowth:(''+d.growth), mGrowthSub:d.growthSub, mGrowthColor:(d.growth<50?'#B14A2E':'#5E7A3B'),
    mPolicy:d.policy, mPolicySub:d.policySub,
    mCond:sign(d.cond,2), mCondSub:d.condSub, mCondColor:toneUpDown(-d.cond),
    hingeDef:d.hingeDef,
    hingeLegend:[
      {name:'Nominal 10Y',color:'#2B2721',val:d.nom[n-1].toFixed(2)+'%',delta:dArrow(d.dNom),dColor:toneUpDown(d.dNom)},
      {name:'Real (TIPS)',color:'#3A6B9E',val:d.real[n-1].toFixed(2)+'%',delta:dArrow(d.dReal),dColor:toneUpDown(d.dReal)},
      {name:'Breakeven',color:'#A07B1D',val:d.be[n-1].toFixed(2)+'%',delta:dArrow(d.dBe),dColor:toneUpDown(d.dBe)} ],
    hingeTicks:ticks, hingeXTicks,
    hingeNomPath:buildPath(d.nom,hx,hy), hingeRealPath:buildPath(d.real,hx,hy),
    hingeRealArea, hingeBeArea, hingeBeMid, hingeRealMid,
    hingeEnds:[mkEnd(d.nom,'#2B2721')],
    classLabel:d.classLabel, classDesc:d.classDesc, classTags:d.classTags, classMover:d.classMover,
    oilName:d.oilName, oilVal:d.oilVal, oilChg:sign(d.oilChg,2,true), oilColor:toneUpDown(d.oilChg), oilSpark,
    playbook:d.playbook,
    crossCols:['1D','1W','1M','YTD'], crossRows,
    curvePath, curvePrevPath, curvePts, curveTicks:cticks, tenorReadout,
    curveSpread:sign(spread,2), curveSpreadColor:toneUpDown(spread),
    curveSpread2:sign(spread2,2), curveSpread2Color:toneUpDown(spread2),
    curveSpread3:sign(spread3,2), curveSpread3Color:toneUpDown(spread3), curveShape,
    labor, fx, commods, surprises, esiSpark,
    esiHeadline:sign(d.esi,0), esiColor:toneUpDown(d.esi),
    tripwires,
    cbName:d.cb.name, cbDays:(''+d.cb.days), cbDate:d.cb.date, cbAction:d.cb.action, cbProb:(''+d.cb.prob), cbMove:d.cb.move,
    releases, positioning
  };
}

// ============================================================================
// TEMPLATES — the prototype markup as JS template literals.
// ============================================================================
const MICRO = "font-size:10px; letter-spacing:.13em; color:#8A8172; text-transform:uppercase; font-weight:600;";
const TILE  = "background:#FBF8F1; border:1px solid rgba(0,0,0,.09); border-radius:10px; padding:9px 12px;";

function regimeStrip(v) {
  return `
  <div style="background:#FBF8F1; border:1px solid rgba(0,0,0,.09); border-radius:10px; padding:9px 13px; display:flex; align-items:stretch; gap:26px; margin-bottom:7px;">
    <div style="min-width:220px;">
      <div style="font-size:10px; letter-spacing:.14em; color:#8A8172; text-transform:uppercase; font-weight:600;">Regime · ${v.region}</div>
      <div style="display:flex; align-items:center; gap:9px; margin:9px 0 10px; padding:9px 14px; border:1px solid ${v.regimeColor}; border-radius:9px; width:fit-content;">
        <span style="width:9px; height:9px; border-radius:50%; background:${v.regimeColor};"></span>
        <span style="font-family:'Newsreader',serif; font-size:20px; font-weight:600; color:${v.regimeColor};">${v.regimeLabel}</span>
      </div>
      <div style="font-size:11px; color:#8A8172;">In regime <span style="font-family:'IBM Plex Mono',monospace; color:#2B2721; font-weight:600;">${v.regimeDays}d</span> · since ${v.regimeSince}</div>
      <div style="display:flex; gap:3px; margin-top:9px; height:22px; align-items:flex-end;">
        ${v.regimeHistory.map(seg=>`<div title="${seg.label}" style="width:${seg.w}px; height:18px; border-radius:2px; background:${seg.color};"></div>`).join('')}
      </div>
    </div>
    <div style="width:1px; background:rgba(0,0,0,.1);"></div>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:22px; flex:1; align-content:center;">
      <div>
        <div style="${MICRO}">Inflation</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:19px; font-weight:500; margin-top:3px;">${v.mInflation}</div>
        <div style="font-size:11px; color:#8A8172; margin-top:2px;">${v.mInflationSub}</div>
      </div>
      <div>
        <div style="${MICRO}">Growth</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:19px; font-weight:500; margin-top:3px; color:${v.mGrowthColor};">${v.mGrowth}</div>
        <div style="font-size:11px; color:#8A8172; margin-top:2px;">${v.mGrowthSub}</div>
      </div>
      <div>
        <div style="${MICRO}">Policy</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:19px; font-weight:500; margin-top:3px;">${v.mPolicy}</div>
        <div style="font-size:11px; color:#8A8172; margin-top:2px;">${v.mPolicySub}</div>
      </div>
      <div>
        <div style="${MICRO}">Conditions</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:19px; font-weight:500; margin-top:3px; color:${v.mCondColor};">${v.mCond}</div>
        <div style="font-size:11px; color:#8A8172; margin-top:2px;">${v.mCondSub}</div>
      </div>
    </div>
  </div>`;
}

function hingeSection(v) {
  return `
  <div style="display:grid; grid-template-columns:1.72fr 1fr; gap:10px; margin-bottom:7px;">
    <div style="${TILE} padding:9px 13px;">
      <div style="display:flex; align-items:baseline; justify-content:space-between;">
        <div style="display:flex; align-items:baseline; gap:12px;">
          <div style="font-family:'Newsreader',serif; font-size:22px; font-weight:600;">The Hinge</div>
          <div style="font-family:'Newsreader',serif; font-style:italic; font-size:14px; color:#8A8172;">${v.hingeDef}</div>
        </div>
        <span style="font-size:10px; letter-spacing:.1em; text-transform:uppercase; font-weight:600; color:#5E7A3B; background:rgba(94,122,59,.1); border:1px solid rgba(94,122,59,.3); border-radius:5px; padding:4px 9px;">Daily clock · checked daily</span>
      </div>
      <div style="display:flex; gap:24px; margin:8px 0 2px; flex-wrap:wrap;">
        ${v.hingeLegend.map(s=>`
        <div style="display:flex; align-items:center; gap:7px;">
          <span style="width:18px; height:3px; border-radius:2px; background:${s.color}; display:inline-block;"></span>
          <span style="font-size:12px; color:#8A8172;">${s.name}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600;">${s.val}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:${s.dColor};">${s.delta}</span>
        </div>`).join('')}
      </div>
      <svg viewBox="0 0 700 250" style="width:100%; height:auto; max-height:172px; display:block;">
        ${v.hingeTicks.map(t=>`
        <line x1="44" y1="${t.y}" x2="636" y2="${t.y}" stroke="rgba(0,0,0,.06)" stroke-width="1"></line>
        <text x="644" y="${t.ty}" font-family="IBM Plex Mono, monospace" font-size="11" fill="#B4A98F">${t.label}</text>`).join('')}
        <path d="${v.hingeRealArea}" fill="rgba(58,107,158,.20)" stroke="none"></path>
        <path d="${v.hingeBeArea}" fill="rgba(160,123,29,.22)" stroke="none"></path>
        <path d="${v.hingeRealPath}" fill="none" stroke="#3A6B9E" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"></path>
        <path d="${v.hingeNomPath}" fill="none" stroke="#2B2721" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"></path>
        <text x="${v.hingeBeMid.x}" y="${v.hingeBeMid.y}" font-family="IBM Plex Mono, monospace" font-size="12" font-weight="600" fill="#8A6A16" text-anchor="end">BE ${v.hingeBeMid.v}</text>
        <text x="${v.hingeRealMid.x}" y="${v.hingeRealMid.y}" font-family="IBM Plex Mono, monospace" font-size="12" font-weight="600" fill="#2C5480" text-anchor="end">real ${v.hingeRealMid.v}</text>
        ${v.hingeEnds.map(e=>`
        <circle cx="${e.x}" cy="${e.y}" r="4" fill="${e.color}"></circle>
        <text x="${e.lx}" y="${e.ly}" font-family="IBM Plex Mono, monospace" font-size="13" font-weight="600" fill="${e.color}" text-anchor="end">${e.v}</text>`).join('')}
        ${v.hingeXTicks.map(x=>`
        <text x="${x.x}" y="244" font-family="IBM Plex Mono, monospace" font-size="11" fill="#B4A98F" text-anchor="${x.anchor}">${x.label}</text>`).join('')}
      </svg>
      <div style="display:flex; align-items:center; gap:12px; margin-top:8px; padding-top:9px; border-top:1px solid rgba(0,0,0,.08);">
        <span style="${MICRO}">Inflation Impulse</span>
        <span style="font-size:12px; color:#8A8172;">${v.oilName}</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:600;">${v.oilVal}</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; color:${v.oilColor};">${v.oilChg}</span>
        <svg viewBox="0 0 120 30" style="width:120px; height:30px;"><path d="${v.oilSpark}" fill="none" stroke="#A07B1D" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
        <span style="font-family:'Newsreader',serif; font-style:italic; font-size:13px; color:#8A8172;">feeds the breakeven leg</span>
      </div>
    </div>
    <div style="display:flex; flex-direction:column; gap:8px;">
      <div style="background:#FBF8F1; border:1px solid rgba(0,0,0,.09); border-left:4px solid ${v.regimeColor}; border-radius:10px; padding:9px 12px;">
        <div style="font-size:10px; letter-spacing:.14em; color:#8A8172; text-transform:uppercase; font-weight:600;">Classification</div>
        <div style="display:flex; align-items:center; gap:9px; margin:9px 0 8px;">
          <span style="width:10px; height:10px; border-radius:50%; background:${v.regimeColor};"></span>
          <span style="font-family:'Newsreader',serif; font-size:21px; font-weight:600; color:${v.regimeColor};">${v.classLabel}</span>
        </div>
        <div style="font-size:13px; line-height:1.5; color:#4A443B;">${v.classDesc}</div>
        <div style="display:flex; gap:7px; flex-wrap:wrap; margin-top:12px;">
          ${v.classTags.map(tag=>`<span style="font-family:'IBM Plex Mono',monospace; font-size:11px; color:#A07B1D; border:1px solid rgba(160,123,29,.4); border-radius:5px; padding:3px 8px;">${tag}</span>`).join('')}
        </div>
        <div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(0,0,0,.08); font-size:11px; color:#8A8172;">Dominant mover: <span style="color:#2B2721; font-weight:600;">${v.classMover}</span> · lookback 5d</div>
      </div>
      <div style="${TILE} flex:1;">
        <div style="font-size:10px; letter-spacing:.14em; color:#8A8172; text-transform:uppercase; font-weight:600; margin-bottom:12px;">Regime Playbook</div>
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${v.playbook.map(p=>`
          <div style="display:flex; align-items:center; gap:11px;">
            <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; font-weight:600; letter-spacing:.05em; color:${p.color}; border:1px solid ${p.color}; border-radius:4px; padding:3px 6px; min-width:44px; text-align:center;">${p.side}</span>
            <span style="font-size:13px; color:#2B2721;">${p.asset}</span>
            <span style="font-size:12px; color:#8A8172; margin-left:auto;">${p.note}</span>
          </div>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

function tripwiresSection(v) {
  return `
  <div style="margin-bottom:7px;">
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:8px;">
      <div style="font-family:'Newsreader',serif; font-size:20px; font-weight:600;">Risk Tripwires</div>
      <div style="font-family:'Newsreader',serif; font-style:italic; font-size:13px; color:#8A8172;">faster confirming signals — directional, not mechanically precise</div>
    </div>
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:8px;">
      ${v.tripwires.map(t=>`
      <div style="background:#FBF8F1; border:1px solid rgba(0,0,0,.09); border-top:3px solid ${t.tone}; border-radius:11px; padding:11px 14px;">
        <div style="font-size:10px; letter-spacing:.11em; text-transform:uppercase; font-weight:600; color:#8A8172;">${t.label}</div>
        <div style="font-family:'Newsreader',serif; font-style:italic; font-size:12.5px; color:#8A8172; margin:4px 0 7px;">${t.tag}</div>
        <div style="display:flex; align-items:baseline; gap:8px;">
          <span style="font-family:'IBM Plex Mono',monospace; font-size:22px; font-weight:600;">${t.val}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; color:${t.chgColor};">${t.chg}</span>
          <span style="font-size:11px; color:#8A8172;">${t.state}</span>
        </div>
        <div style="font-size:11.5px; color:#8A8172; margin-top:7px; line-height:1.4;">${t.note}</div>
      </div>`).join('')}
    </div>
  </div>`;
}

// ----- secondary tiles -----
function tileHeatmap(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:14px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600;">Cross-Asset Heatmap</div>
      <div style="font-family:'Newsreader',serif; font-style:italic; font-size:12px; color:#8A8172;">total return, %</div>
    </div>
    <div style="display:grid; grid-template-columns:1.4fr repeat(4,1fr); gap:4px;">
      <div></div>
      ${v.crossCols.map(c=>`<div style="font-size:10px; letter-spacing:.08em; text-transform:uppercase; font-weight:600; color:#8A8172; text-align:center; padding-bottom:4px;">${c}</div>`).join('')}
      ${v.crossRows.map(r=>`
      <div style="font-size:12px; color:#2B2721; display:flex; align-items:center; padding:0 2px; white-space:nowrap;">${r.name}</div>
      ${r.cells.map(cell=>`<div style="font-family:'IBM Plex Mono',monospace; font-size:12.5px; font-weight:500; text-align:center; padding:4px 4px; border-radius:5px; background:${cell.bg}; color:${cell.fg};">${cell.txt}</div>`).join('')}`).join('')}
    </div>
  </div>`;
}

function tilePositioning(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px;">
      <span style="${MICRO}">Positioning & Flows</span>
      <span style="font-family:'Newsreader',serif; font-style:italic; font-size:11px; color:#8A8172;">net spec · z-score</span>
    </div>
    <div style="display:flex; flex-direction:column; gap:11px;">
      ${v.positioning.map(p=>`
      <div style="display:grid; grid-template-columns:78px 1fr 42px; gap:10px; align-items:center;">
        <span style="font-size:12.5px; color:#2B2721;">${p.name}</span>
        <div style="position:relative; height:8px; background:rgba(0,0,0,.06); border-radius:4px;">
          <div style="position:absolute; top:0; bottom:0; left:50%; width:1px; background:rgba(0,0,0,.2);"></div>
          <div style="position:absolute; top:0; bottom:0; left:${p.barLeft}%; width:${p.barW}%; background:${p.color}; border-radius:4px;"></div>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; text-align:right; color:${p.color};">${p.z}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

function tileCB(v) {
  return `
  <div style="${TILE}">
    <div style="${MICRO}">Next Policy Meeting</div>
    <div style="font-family:'Newsreader',serif; font-size:18px; font-weight:600; margin:8px 0 12px;">${v.cbName}</div>
    <div style="display:flex; align-items:baseline; gap:8px;">
      <span style="font-family:'IBM Plex Mono',monospace; font-size:32px; font-weight:600; line-height:1;">${v.cbDays}</span>
      <span style="font-size:13px; color:#8A8172;">days · ${v.cbDate}</span>
    </div>
    <div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(0,0,0,.08);">
      <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px;"><span style="color:#8A8172;">Market-implied</span><span style="font-family:'IBM Plex Mono',monospace; font-weight:600;">${v.cbAction}</span></div>
      <div style="height:7px; border-radius:4px; background:rgba(0,0,0,.08); overflow:hidden;"><div style="height:100%; width:${v.cbProb}%; background:${v.regimeColor};"></div></div>
      <div style="font-size:11px; color:#8A8172; margin-top:5px;"><span style="font-family:'IBM Plex Mono',monospace; color:#2B2721; font-weight:600;">${v.cbProb}%</span> priced for ${v.cbMove}</div>
    </div>
  </div>`;
}

function tileCurve(v) {
  return `
  <div style="${TILE} display:flex; flex-direction:column;">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:2px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600;">Yield Curve</div>
      <div style="display:flex; align-items:center; gap:14px;">
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:2.6px; background:#A07B1D; border-radius:2px;"></span><span style="font-size:10px; color:#8A8172;">now</span></span>
        <span style="display:flex; align-items:center; gap:5px;"><span style="width:14px; height:0; border-top:2px dashed #C0B49A;"></span><span style="font-size:10px; color:#8A8172;">1w ago</span></span>
      </div>
    </div>
    <div style="display:flex; gap:14px; margin-bottom:8px; align-items:center; flex-wrap:wrap;">
      <span style="font-size:11px; color:#8A8172;">2s10s <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; color:${v.curveSpreadColor};">${v.curveSpread}</span></span>
      <span style="font-size:11px; color:#8A8172;">5s30s <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; color:${v.curveSpread3Color};">${v.curveSpread3}</span></span>
      <span style="font-size:11px; color:#8A8172;">3m10s <span style="font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; color:${v.curveSpread2Color};">${v.curveSpread2}</span></span>
      <span style="font-family:'Newsreader',serif; font-style:italic; font-size:12px; color:#8A8172; margin-left:auto;">${v.curveShape}</span>
    </div>
    <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:7px; margin-bottom:8px;">
      ${v.tenorReadout.map(k=>`
      <div style="border:1px solid rgba(0,0,0,.08); border-radius:7px; padding:5px 9px;">
        <div style="font-size:9px; letter-spacing:.11em; color:#8A8172; text-transform:uppercase; font-weight:600;">${k.t}</div>
        <div style="display:flex; align-items:baseline; gap:6px; margin-top:1px;">
          <span style="font-family:'IBM Plex Mono',monospace; font-size:16px; font-weight:600;">${k.v}</span>
          <span style="font-family:'IBM Plex Mono',monospace; font-size:10px; color:${k.bpColor};">${k.bp}</span>
        </div>
      </div>`).join('')}
    </div>
    <svg viewBox="0 0 460 210" style="width:100%; height:auto; max-height:158px; display:block;">
      ${v.curveTicks.map(t=>`
      <line x1="42" y1="${t.y}" x2="446" y2="${t.y}" stroke="rgba(0,0,0,.06)" stroke-width="1"></line>
      <text x="37" y="${t.ty}" font-family="IBM Plex Mono, monospace" font-size="10" fill="#B4A98F" text-anchor="end">${t.label}</text>`).join('')}
      <line x1="42" y1="22" x2="42" y2="176" stroke="rgba(0,0,0,.22)" stroke-width="1"></line>
      <line x1="42" y1="176" x2="446" y2="176" stroke="rgba(0,0,0,.22)" stroke-width="1"></line>
      <path d="${v.curvePrevPath}" fill="none" stroke="#C0B49A" stroke-width="1.8" stroke-dasharray="4 4" stroke-linejoin="round" stroke-linecap="round"></path>
      <path d="${v.curvePath}" fill="none" stroke="#A07B1D" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"></path>
      ${v.curvePts.map(p=>`
      <circle cx="${p.x}" cy="${p.y}" r="3.2" fill="#A07B1D"></circle>
      <text x="${p.x}" y="${p.vy}" font-family="IBM Plex Mono, monospace" font-size="9.5" font-weight="600" fill="#7A6A45" text-anchor="middle">${p.v}</text>
      <text x="${p.x}" y="190" font-family="IBM Plex Mono, monospace" font-size="10" fill="#8A8172" text-anchor="middle">${p.t}</text>`).join('')}
      <text x="6" y="18" font-family="IBM Plex Sans, sans-serif" font-size="9" fill="#B4A98F">yield %</text>
      <text x="446" y="205" font-family="IBM Plex Sans, sans-serif" font-size="9" fill="#B4A98F" text-anchor="end">tenor</text>
    </svg>
  </div>`;
}

function tileSurprises(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600; white-space:nowrap;">Economic Surprises</div>
      <div style="display:flex; align-items:baseline; gap:5px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:16px; font-weight:600; color:${v.esiColor};">${v.esiHeadline}</span>
        <svg viewBox="0 0 56 20" style="width:56px; height:20px;"><path d="${v.esiSpark}" fill="none" stroke="${v.esiColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      </div>
    </div>
    <div style="display:flex; flex-direction:column; gap:8px;">
      ${v.surprises.map(s=>`
      <div style="display:grid; grid-template-columns:104px 1fr 34px; gap:10px; align-items:center;">
        <span style="font-size:12px; color:#2B2721;">${s.name}</span>
        <div style="position:relative; height:11px;">
          <div style="position:absolute; top:0; bottom:0; left:50%; width:1px; background:rgba(0,0,0,.2);"></div>
          <div style="position:absolute; top:1px; bottom:1px; left:${s.barLeft}%; width:${s.barW}%; background:${s.color}; border-radius:3px;"></div>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; text-align:right; color:${s.color};">${s.val}</span>
      </div>`).join('')}
    </div>
    <div style="font-size:10px; color:#B4A98F; margin-top:9px;">bars = actual vs consensus, σ · beats right / misses left</div>
  </div>`;
}

function tileReleases(v) {
  return `
  <div style="${TILE}">
    <div style="${MICRO} margin-bottom:12px;">Key Releases · This Week</div>
    <div style="display:flex; flex-direction:column; gap:1px;">
      ${v.releases.map(r=>`
      <div style="display:grid; grid-template-columns:34px 1fr auto auto; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px solid rgba(0,0,0,.05);">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:11px; font-weight:600; color:${r.dayColor};">${r.day}</span>
        <span style="font-size:12.5px; color:#2B2721;">${r.name}</span>
        <span style="font-size:11px; color:#8A8172;">cons</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12.5px; font-weight:600;">${r.cons}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

function tileCommods(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:10px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600;">Commodities</div>
      <div style="font-family:'Newsreader',serif; font-style:italic; font-size:12px; color:#8A8172;">price · Δ 1D · 7d</div>
    </div>
    <div style="display:flex; flex-direction:column; gap:2px;">
      ${v.commods.map(c=>`
      <div style="display:grid; grid-template-columns:1fr auto 62px 72px; gap:12px; align-items:center; padding:6px 0; border-bottom:1px solid rgba(0,0,0,.05);">
        <span style="font-size:12.5px; color:#2B2721;">${c.name}</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:14px; font-weight:600;">${c.price}</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; text-align:right; color:${c.chgColor};">${c.chg}</span>
        <svg viewBox="0 0 70 24" style="width:70px; height:24px;"><path d="${c.spark}" fill="none" stroke="${c.chgColor}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      </div>`).join('')}
    </div>
  </div>`;
}

function tileFX(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:10px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600;">FX Changes</div>
      <div style="font-family:'Newsreader',serif; font-style:italic; font-size:12px; color:#8A8172;">Δ 1D · YTD %</div>
    </div>
    <div style="display:flex; flex-direction:column; gap:2px;">
      ${v.fx.map(f=>`
      <div style="display:grid; grid-template-columns:74px 1fr 54px 54px; gap:10px; align-items:center; padding:6px 0; border-bottom:1px solid rgba(0,0,0,.05);">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12.5px; font-weight:500; color:#2B2721;">${f.pair}</span>
        <div style="position:relative; height:8px; background:rgba(0,0,0,.05); border-radius:4px;">
          <div style="position:absolute; top:0; bottom:0; left:50%; width:1px; background:rgba(0,0,0,.18);"></div>
          <div style="position:absolute; top:0; bottom:0; left:${f.barLeft}%; width:${f.barW}%; background:${f.barColor}; border-radius:4px;"></div>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; font-weight:600; text-align:right; color:${f.d1Color};">${f.d1}</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:12px; text-align:right; color:${f.ytdColor};">${f.ytd}</span>
      </div>`).join('')}
    </div>
  </div>`;
}

function tileLabor(v) {
  return `
  <div style="${TILE}">
    <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px;">
      <div style="font-family:'Newsreader',serif; font-size:17px; font-weight:600;">Labor Market</div>
      <div style="font-family:'Newsreader',serif; font-style:italic; font-size:12px; color:#8A8172;">${v.region}</div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:9px 16px;">
      ${v.labor.map(l=>`
      <div style="border-bottom:1px solid rgba(0,0,0,.05); padding-bottom:8px;">
        <div style="font-size:11px; color:#8A8172;">${l.name}</div>
        <div style="display:flex; align-items:baseline; gap:7px; margin-top:2px;">
          <span style="font-family:'IBM Plex Mono',monospace; font-size:16px; font-weight:600;">${l.value}</span>
          <span style="font-size:10px; color:#B4A98F;">${l.delta}</span>
        </div>
      </div>`).join('')}
    </div>
  </div>`;
}

function secondarySection() {
  // Placeholder grid — tiles are packed by layoutTiles() (README-recommended
  // "assign next tile to the currently-shortest column" balancer), with an
  // adaptive column count so wide screens get 4 columns instead of 3.
  return `<div id="mp-tiles" style="display:grid; gap:8px; align-items:start; margin-bottom:7px;"></div>`;
}

function layoutTiles(v) {
  const host = document.getElementById('mp-tiles');
  host.innerHTML = '';
  const w = host.clientWidth || 1200;
  const ncols = w >= 1480 ? 4 : (w >= 1050 ? 3 : 2);
  host.style.gridTemplateColumns = `repeat(${ncols},1fr)`;
  const cols = [];
  for (let i=0;i<ncols;i++) {
    const c = document.createElement('div');
    c.style.cssText = 'display:flex; flex-direction:column; gap:8px; min-width:0;';
    host.appendChild(c); cols.push(c);
  }
  const tiles = [tileHeatmap(v), tileCurve(v), tileSurprises(v), tileCommods(v),
                 tileFX(v), tileLabor(v), tilePositioning(v), tileReleases(v), tileCB(v)];
  // Measure each tile at real column width, pack tallest-first into the
  // currently-shortest column, then refine (moves/swaps out of the tallest
  // column) so the columns bottom out as evenly as the tile sizes allow.
  const nodes = tiles.map((html, idx) => {
    const dv = document.createElement('div'); dv.innerHTML = html;
    const n = dv.firstElementChild;
    cols[0].appendChild(n); const h = n.offsetHeight; cols[0].removeChild(n);
    return { n, h, idx };
  });
  nodes.sort((a,b)=>b.h-a.h);
  const bins = []; for (let i=0;i<ncols;i++) bins.push([]);
  const bh = i => bins[i].reduce((s,t)=>s+t.h+8, 0);
  nodes.forEach(t => {
    let mi = 0;
    for (let i=1;i<ncols;i++) if (bh(i) < bh(mi)) mi = i;
    bins[mi].push(t);
  });
  for (let iter=0; iter<30; iter++) {
    const hs = bins.map((_,i)=>bh(i));
    const M = hs.indexOf(Math.max.apply(null, hs));
    const curMax = hs[M];
    let best = null;
    const othersMax = (a,b) => Math.max.apply(null, hs.map((h,i)=>(i===a||i===b)?-1:h));
    bins[M].forEach((t,ti)=>{
      for (let c=0;c<ncols;c++){ if (c===M) continue;
        const mvMax = Math.max(hs[M]-t.h-8, hs[c]+t.h+8, othersMax(M,c));
        if (mvMax < curMax-1 && (!best || mvMax < best.max)) best={max:mvMax,type:'move',ti,c};
        bins[c].forEach((u,ui)=>{
          const swMax = Math.max(hs[M]-t.h+u.h, hs[c]+t.h-u.h, othersMax(M,c));
          if (swMax < curMax-1 && (!best || swMax < best.max)) best={max:swMax,type:'swap',ti,c,ui};
        });
      }
    });
    if (!best) break;
    if (best.type==='move') { bins[best.c].push(bins[M].splice(best.ti,1)[0]); }
    else { const t=bins[M][best.ti]; bins[M][best.ti]=bins[best.c][best.ui]; bins[best.c][best.ui]=t; }
  }
  // keep the design's importance order top-to-bottom within each column
  bins.forEach(list => list.sort((a,b)=>a.idx-b.idx));
  bins.forEach((list,i)=> list.forEach(t=> cols[i].appendChild(t.n)));
}

// ============================================================================
// RENDER + INTERACTIONS
// ============================================================================
let currentRegion = 'US';

function renderAll(region) {
  currentRegion = region;
  const v = renderVals(region);
  document.getElementById('mp-main').innerHTML =
    regimeStrip(v) + hingeSection(v) + tripwiresSection(v) + secondarySection();
  layoutTiles(v);
  document.getElementById('mp-exchange').textContent = v.exchange;
  const sel = document.getElementById('mp-region');
  if (sel.value !== region) sel.value = region;
}

// Re-pack the tile columns when the viewport width changes (debounced).
let _rsz = null;
window.addEventListener('resize', function(){
  clearTimeout(_rsz);
  _rsz = setTimeout(function(){ layoutTiles(renderVals(currentRegion)); }, 150);
});

function tick() {
  const now = new Date();
  // prototype behavior: local time labeled as the regional exchange
  const fmt = now.toLocaleTimeString('en-US', { hour12:false });
  const h = now.getHours(), day = now.getDay();
  const open = day>=1 && day<=5 && h>=9 && h<16;
  const color = open ? '#5E7A3B' : '#B14A2E';
  document.getElementById('mp-clock').textContent = fmt;
  const st = document.getElementById('mp-state');
  st.textContent = open ? 'OPEN' : 'CLOSED';
  st.style.color = color;
  document.getElementById('mp-dot').style.background = color;
}

let region = 'US';
try { const r = localStorage.getItem('macro_region'); if (r && DATA[r]) region = r; } catch(e){}
document.getElementById('mp-region').addEventListener('change', function(e){
  const r = e.target.value;
  try { localStorage.setItem('macro_region', r); } catch(err){}
  renderAll(r);
});
renderAll(region);
tick();
setInterval(tick, 1000);
</script>
</body>
</html>"""

st.iframe(HTML, height=1355)
