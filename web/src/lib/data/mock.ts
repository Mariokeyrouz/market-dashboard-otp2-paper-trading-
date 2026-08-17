/**
 * MOCK dataset — US region only (EU/CN/JP/GL removed along with Region
 * narrowing to "US" — see types.ts). ALL VALUES ARE PLACEHOLDER, NOT LIVE
 * MARKET LEVELS. Live data (`build-macro-data.ts`) is the primary source;
 * this module is now the equity-style bootstrap seed + per-bucket fallback
 * — same dual role as `mock-equity.ts`. `derive.ts` and every element
 * component stay unchanged; `deriveAllFrom` accepts either this mock or live
 * data, same shape.
 */
import type { CoreData, ExtraData, Region, RegionData } from "./types";

const DATA: Record<Region, CoreData> = {
  US: {
    exchange: "NYSE · ET", regimeLabel: "Stagflation", regimeColor: "var(--amber)", regimeDays: 47, regimeSince: "May 15",
    history: [
      { label: "Reflation", color: "var(--green)", w: 34 },
      { label: "Goldilocks", color: "#8FA05A", w: 26 },
      { label: "Soft landing", color: "#C9A24B", w: 40 },
      { label: "Stagflation", color: "var(--amber)", w: 52 },
    ],
    inflation: "3.1%", inflationSub: "core 3.3% · sticky", growth: 48.7, growthSub: "ISM mfg · slowing",
    policy: "4.25–4.50%", policySub: "Fed Funds · effective target range", cond: -0.15, condSub: "FCI · looser than avg",
    hingeDef: "10Y nominal = real yield + breakeven inflation",
    nom: [4.05, 4.08, 4.06, 4.11, 4.14, 4.17, 4.2], real: [1.92, 1.93, 1.92, 1.94, 1.93, 1.94, 1.95], be: [2.13, 2.15, 2.14, 2.17, 2.21, 2.23, 2.25],
    dNom: 0.15, dReal: 0.03, dBe: 0.12,
    classLabel: "Inflation Scare", classDesc: "Nominal up, led by the breakeven (inflation-expectations) leg.",
    classTags: ["duration-negative", "gold-positive", "risk-ambiguous"], classMover: "Breakeven leg",
    oilName: "Oil · WTI", oilVal: "70.94", oilChg: 2.47, oilSpark: [68, 67.5, 68.2, 69, 69.4, 70.1, 70.94],
    playbook: [
      { side: "SHORT", asset: "Long-duration USTs", note: "BE-led selloff", color: "var(--red)" },
      { side: "LONG", asset: "Gold / TIPS", note: "real-rate hedge", color: "var(--green)" },
      { side: "LONG", asset: "Energy / commods", note: "impulse tailwind", color: "var(--green)" },
      { side: "FADE", asset: "Long-duration tech", note: "rate-sensitive", color: "var(--amber)" },
    ],
    curve: [["3M", 4.55], ["1Y", 4.2], ["2Y", 3.86], ["5Y", 3.95], ["7Y", 4.05], ["10Y", 4.2], ["30Y", 4.45]],
    curveDate: "2026-08-12",
    curvePrev: [["3M", 4.58], ["1Y", 4.15], ["2Y", 3.80], ["5Y", 3.90], ["7Y", 4.00], ["10Y", 4.16], ["30Y", 4.40]],
    curvePrevDate: "2026-08-05",
    tripwires: [
      { label: "Credit · HY OAS", tag: "Leading tell for equity stress", val: "3.20%", chg: 0.1, unit: " pp", state: "", note: "Widening = rising stress.", tone: "var(--amber)" },
      { label: "Equity Vol · VIX", tag: "Risk-on / risk-off tripwire", val: "18.2", chg: null, state: "Contango", note: "Front below back month — calm / risk-on tilt.", tone: "var(--green)" },
      { label: "Dollar · DXY", tag: "Global liquidity valve", val: "104.8", chg: 0.3, state: "", note: "Stronger USD tightens conditions abroad.", tone: "var(--amber)" },
      { label: "Curve · 2s10s", tag: "Late-cycle / recession watch", val: "+0.34", chg: null, state: "Normal", note: "Upward-sloping — no curve-inversion warning.", tone: "var(--green)" },
    ],
    cross: [
      ["S&P 500", 0.4, 1.2, 3.1, 14.2], ["Nasdaq 100", 0.6, 1.8, 4.0, 19.5], ["UST 10Y", -0.3, -0.9, -1.4, -3.2],
      ["IG Credit", -0.1, 0.2, 0.9, 4.1], ["HY Credit", 0.2, 0.7, 1.6, 6.8], ["USD (DXY)", 0.3, 0.5, -0.8, 1.9],
      ["Gold", 0.9, 2.4, 5.2, 16.4], ["Brent", 1.1, 3.0, 4.8, -2.1], ["Copper", -0.4, 0.9, 2.2, 7.3],
    ],
    cb: { name: "FOMC · Federal Reserve", days: 29, date: "Jul 30" },
    releases: [["MON", "ISM Manufacturing", "48.5"], ["WED", "ADP Employment", "+150k"], ["THU", "Initial Jobless Claims", "232k"], ["FRI", "Nonfarm Payrolls", "+175k"], ["FRI", "Unemployment Rate", "4.1%"]],
  },
};

const EXTRA: Record<Region, ExtraData> = {
  US: {
    labor: [["Nonfarm Payrolls", "+175k", "prev +206k"], ["Unemployment", "4.1%", "+0.1 m/m"], ["Avg Hourly Earn", "3.9% y/y", "−0.1 pp"], ["Jobless Claims", "232k", "+8k w/w"], ["Participation", "62.6%", "flat"], ["JOLTS Openings", "8.10M", "−0.20M"]],
    fx: [["EUR/USD", -0.2, -1.4], ["USD/JPY", 0.3, 8.2], ["GBP/USD", -0.15, 0.9], ["USD/CNY", 0.15, 2.1], ["USD/CHF", 0.1, 3.4], ["AUD/USD", -0.25, -2.8]],
    commods: [["WTI Crude", "70.94", 2.47], ["Brent", "74.20", 1.8], ["Copper", "4.28", -0.9], ["Gold", "2412", 0.85], ["Nat Gas", "2.68", -1.2]],
  },
};

export function getRegionData(region: Region): RegionData {
  return { ...DATA[region], ...EXTRA[region] };
}
