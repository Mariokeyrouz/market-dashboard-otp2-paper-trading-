/** Equity Dashboard's core dataset shape — flat, no per-region variants (US-focused only, v1). */

export interface EquityIndexSeries {
  name: string;
  color: string;
  /** Raw index levels, most recent last. All series share the same length/window. */
  prices: number[];
}

export interface EquityCoreData {
  indices: EquityIndexSeries[];
  vix: { spot: number; vix3m: number; vix9d: number; spark: number[] };
  /** Same [tenor, yield%] tuple shape as the macro dashboard's yield curve. */
  curve: [string, number][];
  oilName: string;
  oilVal: string;
  oilChg: number;
  oilSpark: number[];
  /** Top-10 S&P 500 constituents by index weight, descending. */
  concentration: { name: string; weightPct: number }[];
}
