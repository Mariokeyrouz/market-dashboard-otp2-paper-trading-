/**
 * MOCK dataset — Terminal Dashboard. ALL VALUES ARE PLACEHOLDER, NOT LIVE
 * MARKET LEVELS. Same two jobs as `mock-equity.ts`: bootstrap seed for
 * `useTerminalData`'s first render, and per-bucket fallback inside
 * `build-terminal-data.ts` when a live source fails.
 *
 * Reuses `getEquityData()`'s indices/vix/sectors/commods/movers slices rather
 * than re-authoring fake data that already exists — fresh mock is authored
 * only for the four buckets that are new to Terminal (fx/global/fixedIncome/
 * factors).
 */
import { getEquityData } from "./mock-equity";
import { CORP_CREDIT_ETFS, GOVT_CREDIT_ETFS } from "./reference/credit-etfs";
import { FX_PAIRS } from "./reference/fx-pairs";
import { GLOBAL_INDICES } from "./reference/global-indices";
import { STYLE_FACTOR_ETFS } from "./reference/style-factors";
import type { TerminalCoreData } from "./types-terminal";

/** Deterministic pseudo-noise (sine-based, no Math.random) — same reasoning as `mock-equity.ts`'s `walk()`: no SSR/hydration mismatch. */
function pctFrom(seed: number): number {
  return Math.sin(seed * 12.9898) * 3.5;
}

const equity = getEquityData();

const TERMINAL_DATA: TerminalCoreData = {
  indices: equity.indices,
  vix: equity.vix,
  sectors: equity.sectors.map((s, i) => ({ ...s, price: [228, 84, 46, 137, 202, 91, 152, 78, 68, 41, 88][i] ?? 100 })),
  commods: equity.commods,
  movers: equity.movers,
  fx: FX_PAIRS.map((p, i) => {
    const base = [1.085, 1.27, 148.4, 0.885, 1.365, 0.652, 7.18][i] ?? 1;
    const chgPct = pctFrom(i + 1) * 0.3;
    return { name: p.name, ticker: p.ticker, price: base, chgPct };
  }),
  global: GLOBAL_INDICES.map((idx, i) => {
    const base = [38500, 18900, 7650, 8250, 8100, 2650, 18200, 81500, 68, 55800, 129000][i] ?? 10000;
    return { name: idx.name, ticker: idx.ticker, group: idx.group, price: base, chgPct: pctFrom(i + 11) };
  }),
  fixedIncome: {
    govt: GOVT_CREDIT_ETFS.map((e, i) => ({ name: e.name, ticker: e.ticker, price: [82.4, 95.1, 88.6, 22.8][i] ?? 90, chgPct: pctFrom(i + 21) * 0.4 })),
    corp: CORP_CREDIT_ETFS.map((e, i) => ({ name: e.name, ticker: e.ticker, price: [108.2, 79.4, 78.9, 91.3][i] ?? 90, chgPct: pctFrom(i + 31) * 0.5 })),
  },
  factors: STYLE_FACTOR_ETFS.map((f, i) => ({ name: f.name, ticker: f.ticker, chgPct: pctFrom(i + 41) })),
  events: equity.events,
};

export function getTerminalData(): TerminalCoreData {
  return TERMINAL_DATA;
}
