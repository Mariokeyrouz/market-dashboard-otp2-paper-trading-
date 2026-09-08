/**
 * Pure derive selectors for the Terminal Dashboard — mirrors derive-equity.ts's
 * shape and conventions exactly: formatted table rows using `sign()`/
 * `toneUpDown()` from `derive.ts`, and the Performance chart's geometry via
 * the same `buildIndicesTF`/`TIMEFRAMES` Equity's indices chart uses. No
 * React, no side effects: unit-testable and swappable to real data.
 */
import { buildIndicesTF, TIMEFRAMES, type IndicesTF, type IndicesTimeframe } from "./derive-equity";
import { makeSpark, sign, sparkPath, toneUpDown } from "./derive";
import { getTerminalData } from "./data/mock-terminal";
import type { GroupedQuoteRow, QuoteRow, TerminalCoreData } from "./data/types-terminal";
import type { MoverRow } from "./data/types-equity";

export interface TerminalRowFmt { name: string; ticker?: string; price: string; chgPct: string; chgColor: string }
export interface TerminalGroupedRowFmt extends TerminalRowFmt { group: string }
export interface FactorCellFmt { name: string; ticker: string; chgPct: string; bg: string }
export interface MoverFmt { ticker: string; name: string; price: string; chgPct: string; chgColor: string }

export interface TerminalDerived {
  markets: TerminalRowFmt[];
  sectors: { name: string; price: string; chg1d: string; chg1dColor: string; chg1w: string; chg1wColor: string; chg1m: string; chg1mColor: string }[];
  performance: Record<IndicesTimeframe, IndicesTF>;
  currencies: TerminalRowFmt[];
  global: TerminalGroupedRowFmt[];
  fixedIncome: { govt: TerminalRowFmt[]; corp: TerminalRowFmt[] };
  factors: FactorCellFmt[];
  commods: { name: string; price: string; chg: string; chgColor: string; spark: string }[];
  movers: { gainers: MoverFmt[]; losers: MoverFmt[] };
  events: { dateLabel: string; kind: "earnings" | "macro"; kindLabel: string; kindColor: string; label: string; detail: string }[];
}

/**
 * Magnitude-scaled heatmap cell background — the 3x3 style-box grid needs a
 * gradient read (how strong, not just which side), unlike every other table
 * in this app where a threshold-only up/down color is enough.
 */
export function factorCellColor(pct: number): string {
  const cap = 3; // %, style-box ETFs rarely move further than this in a day
  const mag = Math.min(Math.abs(pct) / cap, 1);
  const strength = Math.round(12 + mag * 58); // 12%..70% mix against the tile background
  const base = pct >= 0 ? "var(--green)" : "var(--red)";
  return `color-mix(in srgb, ${base} ${strength}%, var(--tile))`;
}

export function fmtQuote(r: QuoteRow, dp = 2): TerminalRowFmt {
  return {
    name: r.name,
    ticker: r.ticker,
    price: r.price.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp }),
    chgPct: sign(r.chgPct, 2, true),
    chgColor: toneUpDown(r.chgPct),
  };
}

function fmtGroupedQuote(r: GroupedQuoteRow, dp = 0): TerminalGroupedRowFmt {
  return { ...fmtQuote(r, dp), group: r.group };
}

export function deriveTerminal(): TerminalDerived {
  return deriveTerminalFrom(getTerminalData());
}

export function deriveTerminalFrom(d: TerminalCoreData): TerminalDerived {
  // ----- US Equity Markets: 4 indices + a VIX row, Koyfin's own layout -----
  const markets: TerminalRowFmt[] = d.indices.map((s) => {
    const prices = s.prices;
    const last = prices[prices.length - 1];
    const prev = prices[prices.length - 2];
    const chgPct = ((last - prev) / prev) * 100;
    return {
      name: s.name,
      price: last.toLocaleString("en-US", { maximumFractionDigits: last >= 1000 ? 0 : 2 }),
      chgPct: sign(chgPct, 2, true),
      chgColor: toneUpDown(chgPct),
    };
  });
  const vixHist = d.vix.history;
  const vixPrev = vixHist[vixHist.length - 2] ?? d.vix.spot;
  const vixChgPct = ((d.vix.spot - vixPrev) / vixPrev) * 100;
  markets.push({
    name: "Volatility Index · CBOE VIX",
    price: d.vix.spot.toFixed(2),
    chgPct: sign(vixChgPct, 2, true),
    chgColor: toneUpDown(vixChgPct),
  });

  // ----- US Equity Sectors, ranked by today's move (same as Equity's Sector Performance) -----
  const sectors = [...d.sectors]
    .sort((a, b) => b.chg1d - a.chg1d)
    .map((s) => ({
      name: s.name,
      price: s.price != null ? s.price.toFixed(2) : "—",
      chg1d: sign(s.chg1d, 2, true), chg1dColor: toneUpDown(s.chg1d),
      chg1w: sign(s.chg1w, 2, true), chg1wColor: toneUpDown(s.chg1w),
      chg1m: sign(s.chg1m, 2, true), chg1mColor: toneUpDown(s.chg1m),
    }));

  // ----- Normalized Performance chart: exact same geometry as Equity's indices chart -----
  const performance = Object.fromEntries(
    TIMEFRAMES.map((tf) => [tf.key, buildIndicesTF(d, tf.points, tf.label, tf.axisLabels)]),
  ) as Record<IndicesTimeframe, IndicesTF>;

  const currencies = d.fx.map((r) => fmtQuote(r, 4));
  const global = d.global.map((r) => fmtGroupedQuote(r, 0));
  const fixedIncome = { govt: d.fixedIncome.govt.map((r) => fmtQuote(r, 2)), corp: d.fixedIncome.corp.map((r) => fmtQuote(r, 2)) };
  const factors: FactorCellFmt[] = d.factors.map((f) => ({
    name: f.name, ticker: f.ticker, chgPct: sign(f.chgPct, 2, true), bg: factorCellColor(f.chgPct),
  }));

  const commods = d.commods.map(([name, priceStr, chg]) => {
    const price = parseFloat(priceStr.replace(/,/g, ""));
    return { name, price: priceStr, chg: sign(chg, 2, true), chgColor: toneUpDown(chg), spark: sparkPath(makeSpark(price, chg), 70, 24) };
  });

  const fmtMover = (r: MoverRow): MoverFmt => ({
    ticker: r.ticker, name: r.name, price: r.price.toFixed(2),
    chgPct: sign(r.chgPct, 2, true), chgColor: toneUpDown(r.chgPct),
  });
  const movers = { gainers: d.movers.gainers.map(fmtMover), losers: d.movers.losers.map(fmtMover) };

  const dateLabel = (n: number) => (n === 0 ? "Today" : n === 1 ? "Tomorrow" : `in ${n}d`);
  const events = [...d.events]
    .sort((a, b) => a.daysFromNow - b.daysFromNow)
    .map((e) => ({
      dateLabel: dateLabel(e.daysFromNow),
      kind: e.kind,
      kindLabel: e.kind === "earnings" ? "Earnings" : "Macro",
      kindColor: e.kind === "earnings" ? "var(--gold)" : "var(--blue-deep)",
      label: e.label, detail: e.detail,
    }));

  return { markets, sectors, performance, currencies, global, fixedIncome, factors, commods, movers, events };
}
