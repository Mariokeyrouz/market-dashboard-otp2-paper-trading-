/**
 * MOCK dataset — Equity Dashboard, ported by hand for the v1 element set.
 * ALL VALUES ARE PLACEHOLDER, NOT LIVE MARKET LEVELS.
 * Real-data wiring (phase 2) replaces this module with API-backed data of the
 * same shape; derive-equity.ts and every equity element component stay
 * unchanged. Mirrors the macro dashboard's src/lib/data/mock.ts convention.
 */
import type { EquityCoreData } from "./types-equity";

const EQUITY_DATA: EquityCoreData = {
  indices: [
    { name: "S&P 500", color: "var(--ink)",
      prices: [5780, 5795, 5760, 5810, 5840, 5825, 5860, 5890, 5870, 5905, 5920, 5900, 5935, 5955, 5940] },
    { name: "Nasdaq 100", color: "var(--gold)",
      prices: [20100, 20220, 20050, 20280, 20390, 20310, 20480, 20620, 20540, 20710, 20790, 20680, 20850, 20940, 20870] },
    { name: "Dow Jones", color: "#3A6B9E",
      prices: [42300, 42410, 42180, 42500, 42610, 42540, 42690, 42800, 42720, 42910, 42980, 42870, 43040, 43150, 43080] },
    { name: "Russell 2000", color: "var(--green)",
      prices: [2260, 2245, 2210, 2255, 2280, 2265, 2295, 2310, 2290, 2320, 2335, 2305, 2340, 2360, 2345] },
  ],
  vix: { spot: 18.2, vix3m: 20.4, vix9d: 16.8, spark: [21.5, 20.1, 19.4, 20.8, 19.6, 18.9, 18.2] },
  curve: [["1M", 4.32], ["3M", 4.28], ["6M", 4.15], ["1Y", 3.98], ["2Y", 3.86], ["5Y", 3.94], ["10Y", 4.20], ["30Y", 4.45]],
  oilName: "WTI Crude", oilVal: "70.94", oilChg: 2.47,
  oilSpark: [68, 67.5, 68.2, 69, 69.4, 70.1, 70.94],
  concentration: [
    { name: "AAPL", weightPct: 7.1 }, { name: "MSFT", weightPct: 6.8 }, { name: "NVDA", weightPct: 6.4 },
    { name: "AMZN", weightPct: 3.9 }, { name: "META", weightPct: 2.6 }, { name: "GOOGL", weightPct: 2.1 },
    { name: "GOOG", weightPct: 1.8 }, { name: "AVGO", weightPct: 1.7 }, { name: "TSLA", weightPct: 1.6 },
    { name: "BRK.B", weightPct: 1.5 },
  ],
};

export function getEquityData(): EquityCoreData {
  return EQUITY_DATA;
}
