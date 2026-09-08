/**
 * Terminal Dashboard's core dataset shape — a Koyfin-style "scan surface" of
 * many small panels rather than a narrative sweep. Reuses `CalendarEvent` and
 * `MoverRow` from `types-equity.ts` instead of redefining them (same shape,
 * same source buckets for the panels this dashboard shares with Equity).
 */
import type { CalendarEvent, EquityIndexSeries, MoverRow, SectorRow } from "./types-equity";

export interface QuoteRow {
  name: string;
  ticker: string;
  price: number;
  chgPct: number;
}

/** Global Markets rows carry a Developed/Emerging sub-group label for the table's group headers. */
export interface GroupedQuoteRow extends QuoteRow {
  group: string;
}

export interface TerminalCoreData {
  indices: EquityIndexSeries[];
  vix: { spot: number; vix3m: number; vix9d: number; history: number[] };
  sectors: SectorRow[];
  commods: [string, string, number][];
  movers: { gainers: MoverRow[]; losers: MoverRow[] };
  fx: QuoteRow[];
  global: GroupedQuoteRow[];
  fixedIncome: { govt: QuoteRow[]; corp: QuoteRow[] };
  /** 1-Day % only, keyed by ticker — the 3x3 style-box heatmap doesn't need a full row shape. */
  factors: { name: string; ticker: string; chgPct: number }[];
  events: CalendarEvent[];
}
