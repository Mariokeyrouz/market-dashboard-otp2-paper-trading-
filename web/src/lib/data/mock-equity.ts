/**
 * MOCK dataset — Equity Dashboard. ALL VALUES ARE PLACEHOLDER, NOT LIVE
 * MARKET LEVELS. Live data (`src/lib/data/build-equity-data.ts`) has since
 * replaced this as the primary source, but this module keeps two jobs:
 *  1. Bootstrap seed for `useEquityData`'s first render, before the initial
 *     `/api/equity` fetch resolves — so the page never renders blank/null.
 *  2. Per-bucket fallback inside `build-equity-data.ts`: if a live source
 *     fails, the matching slice of this mock fills the gap rather than
 *     leaving a hole in the tile.
 * `derive-equity.ts` and every equity element component are unchanged by any
 * of this — `deriveEquityFrom` accepts either this mock or live data, same shape.
 */
import type { EquityCoreData } from "./types-equity";

/**
 * Deterministic pseudo-walk (sine-based noise, no Math.random) — a fixed seed
 * means the same series renders on the server and the client, so there's no
 * SSR/hydration mismatch the way a truly random walk would cause.
 */
function walk(base: number, n: number, drift: number, vol: number, seed: number): number[] {
  const arr: number[] = [base];
  for (let i = 1; i < n; i++) {
    const wig = (Math.sin(i * 0.35 + seed) + Math.sin(i * 0.11 + seed * 1.9) * 0.6) * vol;
    arr.push(arr[i - 1] * (1 + drift) + wig);
  }
  return arr;
}

const INDEX_POINTS = 252; // ~1 trading year

const EQUITY_DATA: EquityCoreData = {
  indices: [
    { name: "S&P 500", color: "var(--ink)", prices: walk(5400, INDEX_POINTS, 0.00038, 16, 1.3) },
    { name: "Nasdaq 100", color: "var(--gold)", prices: walk(18800, INDEX_POINTS, 0.00048, 70, 2.7) },
    { name: "Dow Jones", color: "#3A6B9E", prices: walk(40200, INDEX_POINTS, 0.00033, 90, 4.1) },
    { name: "Russell 2000", color: "var(--green)", prices: walk(2150, INDEX_POINTS, 0.0003, 10, 5.9) },
  ],
  vix: {
    spot: 18.2,
    vix3m: 20.4,
    vix9d: 16.8,
    // 45 sessions of history ending at spot, deterministic wave with an
    // occasional spike above the 25 stress threshold.
    history: (() => {
      const n = 45;
      const arr = Array.from({ length: n }, (_, i) => Math.max(11, 17 + Math.sin(i * 0.22 + 0.6) * 3.4 + Math.sin(i * 0.05 + 1.1) * 5.2));
      arr[n - 1] = 18.2;
      return arr;
    })(),
  },
  curve: [["1M", 4.32], ["3M", 4.28], ["6M", 4.15], ["1Y", 3.98], ["2Y", 3.86], ["5Y", 3.94], ["10Y", 4.20], ["30Y", 4.45]],
  curveDate: "2026-08-12",
  curvePrev: [["1M", 4.35], ["3M", 4.30], ["6M", 4.10], ["1Y", 3.93], ["2Y", 3.80], ["5Y", 3.89], ["10Y", 4.16], ["30Y", 4.40]],
  curvePrevDate: "2026-08-05",
  commods: [
    ["WTI Crude", "70.94", 2.47],
    ["Brent", "74.20", 1.80],
    ["Gold", "2,412", 0.85],
    ["Copper", "4.28", -0.90],
    ["Nat Gas", "2.68", -1.20],
  ],
  concentration: [
    { name: "AAPL", weightPct: 7.1 }, { name: "MSFT", weightPct: 6.8 }, { name: "NVDA", weightPct: 6.4 },
    { name: "AMZN", weightPct: 3.9 }, { name: "META", weightPct: 2.6 }, { name: "GOOGL", weightPct: 2.1 },
    { name: "GOOG", weightPct: 1.8 }, { name: "AVGO", weightPct: 1.7 }, { name: "TSLA", weightPct: 1.6 },
    { name: "BRK.B", weightPct: 1.5 },
  ],
  sectors: [
    { name: "Technology", chg1d: 1.42, chg1w: 3.85, chg1m: 7.20 },
    { name: "Communication Services", chg1d: 0.95, chg1w: 2.40, chg1m: 5.10 },
    { name: "Financials", chg1d: 0.58, chg1w: 1.10, chg1m: 2.35 },
    { name: "Industrials", chg1d: 0.31, chg1w: 0.80, chg1m: 1.95 },
    { name: "Consumer Discretionary", chg1d: 0.74, chg1w: 1.65, chg1m: 3.40 },
    { name: "Materials", chg1d: 0.18, chg1w: 0.35, chg1m: 0.85 },
    { name: "Health Care", chg1d: -0.12, chg1w: -0.45, chg1m: 0.60 },
    { name: "Consumer Staples", chg1d: -0.28, chg1w: -0.90, chg1m: -1.10 },
    { name: "Utilities", chg1d: -0.42, chg1w: -1.15, chg1m: -0.35 },
    { name: "Real Estate", chg1d: -0.65, chg1w: -1.60, chg1m: -2.20 },
    { name: "Energy", chg1d: -1.35, chg1w: -2.80, chg1m: -4.65 },
  ],
  movers: {
    gainers: [
      { ticker: "SMCI", name: "Super Micro Computer", price: 42.18, chgPct: 8.92 },
      { ticker: "PLTR", name: "Palantir Technologies", price: 78.34, chgPct: 6.71 },
      { ticker: "CRWD", name: "CrowdStrike Holdings", price: 356.20, chgPct: 5.44 },
      { ticker: "MRNA", name: "Moderna", price: 41.05, chgPct: 4.98 },
      { ticker: "ENPH", name: "Enphase Energy", price: 68.72, chgPct: 4.60 },
    ],
    losers: [
      { ticker: "INTC", name: "Intel", price: 21.36, chgPct: -6.15 },
      { ticker: "DXCM", name: "DexCom", price: 61.90, chgPct: -5.20 },
      { ticker: "APA", name: "APA Corporation", price: 22.44, chgPct: -4.35 },
      { ticker: "BA", name: "Boeing", price: 154.10, chgPct: -3.80 },
      { ticker: "PARA", name: "Paramount Global", price: 11.28, chgPct: -3.42 },
    ],
  },
  events: [
    { daysFromNow: 0, kind: "macro", label: "ISM Manufacturing PMI", detail: "Consensus 48.9, prior 48.4" },
    { daysFromNow: 1, kind: "earnings", label: "AAPL — Apple", detail: "EPS est. $1.62 · after market close" },
    { daysFromNow: 2, kind: "earnings", label: "AMZN — Amazon", detail: "EPS est. $1.14 · after market close" },
    { daysFromNow: 3, kind: "macro", label: "FOMC Rate Decision", detail: "No change expected, ~30% odds priced for a 25bp cut" },
    { daysFromNow: 4, kind: "earnings", label: "GOOGL — Alphabet", detail: "EPS est. $2.02 · after market close" },
    { daysFromNow: 6, kind: "macro", label: "Nonfarm Payrolls", detail: "Consensus +170k, prior +206k" },
    { daysFromNow: 8, kind: "earnings", label: "NVDA — Nvidia", detail: "EPS est. $0.89 · after market close" },
    { daysFromNow: 10, kind: "macro", label: "CPI (Headline & Core)", detail: "Consensus +0.2% m/m core" },
    { daysFromNow: 12, kind: "macro", label: "Retail Sales", detail: "Consensus +0.3% m/m" },
    { daysFromNow: 14, kind: "earnings", label: "META — Meta Platforms", detail: "EPS est. $5.25 · after market close" },
  ],
};

export function getEquityData(): EquityCoreData {
  return EQUITY_DATA;
}
