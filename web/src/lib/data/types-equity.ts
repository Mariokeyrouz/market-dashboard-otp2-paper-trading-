/** Equity Dashboard's core dataset shape — flat, no per-region variants (US-focused only, v1). */

export interface EquityIndexSeries {
  name: string;
  color: string;
  /** Raw index levels, most recent last. ~1Y of daily levels — timeframe toggles slice from this. */
  prices: number[];
}

export interface SectorRow {
  name: string;
  chg1d: number;
  chg1w: number;
  chg1m: number;
}

export interface MoverRow {
  ticker: string;
  name: string;
  price: number;
  chgPct: number;
}

export interface CalendarEvent {
  /** 0 = today, 1 = tomorrow, etc. — relative so no real Date object is ever needed. */
  daysFromNow: number;
  kind: "earnings" | "macro";
  label: string;
  detail: string;
}

export interface EquityCoreData {
  indices: EquityIndexSeries[];
  vix: { spot: number; vix3m: number; vix9d: number; history: number[] };
  /** Same [tenor, yield%] tuple shape as the macro dashboard's yield curve. */
  curve: [string, number][];
  oilName: string;
  oilVal: string;
  oilChg: number;
  oilSpark: number[];
  /** Top-10 S&P 500 constituents by index weight, descending. */
  concentration: { name: string; weightPct: number }[];
  /** 11 GICS sectors. */
  sectors: SectorRow[];
  movers: { gainers: MoverRow[]; losers: MoverRow[] };
  events: CalendarEvent[];
}
