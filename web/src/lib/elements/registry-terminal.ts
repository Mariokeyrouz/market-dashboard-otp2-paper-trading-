/**
 * Terminal Dashboard's element registry — same shape as registry-equity.ts,
 * so the grid, default layout, and Logic panel all work unchanged. Ids are
 * prefixed `tm-`. Unlike Macro/Equity, this dashboard is allowed to scroll —
 * density over fit-to-viewport is the point of a terminal — so
 * `defaultLayout` isn't tuned to fit one screen.
 */
import type { ElementDef } from "./registry";

import Currencies from "@/components/elements-terminal/Currencies";
import EquityFactors from "@/components/elements-terminal/EquityFactors";
import EquityMarkets from "@/components/elements-terminal/EquityMarkets";
import FixedIncome from "@/components/elements-terminal/FixedIncome";
import GlobalMarkets from "@/components/elements-terminal/GlobalMarkets";
import TerminalCalendar from "@/components/elements-terminal/TerminalCalendar";
import TerminalCommodities from "@/components/elements-terminal/TerminalCommodities";
import TerminalMovers from "@/components/elements-terminal/TerminalMovers";
import TerminalPerformance from "@/components/elements-terminal/TerminalPerformance";
import TerminalSectors from "@/components/elements-terminal/TerminalSectors";
import Watchlist from "@/components/elements-terminal/Watchlist";

export const TERMINAL_ELEMENTS: ElementDef[] = [
  {
    id: "tm-markets",
    title: "US Equity Markets",
    component: EquityMarkets,
    zRole: "anchor",
    logic:
      "The tape, first — Nasdaq 100, S&P 500, Dow Jones, Russell 2000, and the Volatility Index as a fifth row (Koyfin's own layout), so risk tone and the headline indices are read together.",
    defaultLayout: { x: 0, y: 0, w: 4, h: 9, minW: 3, minH: 6 },
  },
  {
    id: "tm-sectors",
    title: "US Equity Sectors",
    component: TerminalSectors,
    zRole: "scan",
    logic:
      "Where the tape's move is coming from — the 11 GICS sectors ranked by today's move, price alongside 1D/1W/1M to tell a one-day pop from a real rotation.",
    defaultLayout: { x: 4, y: 0, w: 4, h: 11, minW: 3, minH: 6 },
  },
  {
    id: "tm-watchlist",
    title: "My Watchlist",
    component: Watchlist,
    zRole: "terminal",
    logic:
      "Your own names, always visible — a scan surface has no fixed reading order, so the tickers you actually care about get a permanent panel rather than a search you re-run every time.",
    defaultLayout: { x: 8, y: 0, w: 4, h: 20, minW: 3, minH: 10 },
  },
  {
    id: "tm-performance",
    title: "Normalized Performance",
    component: TerminalPerformance,
    zRole: "pivot",
    logic:
      "How the major indices are actually performing, rebased to 100 — toggle 1M/3M/1Y or hover for a crosshair readout, the same chart Equity's Indices tile hangs on.",
    defaultLayout: { x: 0, y: 9, w: 8, h: 11, minW: 6, minH: 8 },
  },
  {
    id: "tm-currencies",
    title: "Currencies",
    component: Currencies,
    zRole: "scan",
    logic: "The cross-asset read: 7 major FX pairs, the channel through which rate and risk moves show up first.",
    defaultLayout: { x: 0, y: 20, w: 4, h: 8, minW: 3, minH: 5 },
  },
  {
    id: "tm-global",
    title: "Global Markets",
    component: GlobalMarkets,
    zRole: "scan",
    logic:
      "Is the US move a global move? Developed and Emerging index performance side by side with the US tape above.",
    defaultLayout: { x: 4, y: 11, w: 4, h: 12, minW: 3, minH: 6 },
  },
  {
    id: "tm-fixed-income",
    title: "Fixed Income",
    component: FixedIncome,
    zRole: "support",
    logic: "The rates/credit backdrop — government and corporate credit ETFs side by side, consult-on-demand positioning context.",
    defaultLayout: { x: 0, y: 28, w: 4, h: 8, minW: 4, minH: 5 },
  },
  {
    id: "tm-factors",
    title: "US Equity Factors",
    component: EquityFactors,
    zRole: "support",
    logic: "Size x style rotation in one glance — the Vanguard style-box 3x3, magnitude-shaded, not just a threshold color.",
    defaultLayout: { x: 4, y: 23, w: 4, h: 7, minW: 3, minH: 5 },
  },
  {
    id: "tm-commods",
    title: "Commodities",
    component: TerminalCommodities,
    zRole: "support",
    logic: "The real-economy inflation impulse — oil, gold, copper, nat gas — a small exit-point tile, same role it plays on Equity.",
    defaultLayout: { x: 8, y: 20, w: 4, h: 8, minW: 3, minH: 4 },
  },
  {
    id: "tm-movers",
    title: "Market Movers",
    component: TerminalMovers,
    zRole: "support",
    logic: "The single-name extremes underneath the index-level read — today's biggest S&P 500 gainers and losers, side by side.",
    defaultLayout: { x: 0, y: 36, w: 8, h: 9, minW: 6, minH: 6 },
  },
  {
    id: "tm-calendar",
    title: "Macro Calendar",
    component: TerminalCalendar,
    zRole: "support",
    logic: "What's next — the upcoming macro events (FOMC, CPI, payrolls, ISM) most likely to move the tape.",
    defaultLayout: { x: 0, y: 45, w: 8, h: 9, minW: 6, minH: 5 },
  },
];

export const TERMINAL_DEFAULT_HIDDEN: string[] = TERMINAL_ELEMENTS.filter((e) => e.defaultHidden).map((e) => e.id);
export const TERMINAL_ELEMENT_MAP = new Map(TERMINAL_ELEMENTS.map((e) => [e.id, e]));
