/**
 * Equity Dashboard's element registry — same shape as registry.ts's macro
 * ELEMENTS, so the grid, default layout, and Logic panel all work unchanged.
 * Ids are prefixed `eq-` to stay unambiguous even though per-dashboard-type
 * storage would tolerate a collision with a macro id.
 */
import type { ElementDef } from "./registry";

import EquityIndices from "@/components/elements-equity/EquityIndices";
import VixTermStructure from "@/components/elements-equity/VixTermStructure";
import EquityYieldCurve from "@/components/elements-equity/EquityYieldCurve";
import Commodities from "@/components/elements-equity/Commodities";
import SP500Concentration from "@/components/elements-equity/SP500Concentration";
import SectorPerformance from "@/components/elements-equity/SectorPerformance";
import MarketMovers from "@/components/elements-equity/MarketMovers";
import EarningsCalendar from "@/components/elements-equity/EarningsCalendar";

export const EQUITY_ELEMENTS: ElementDef[] = [
  {
    id: "eq-vix",
    title: "VIX & Term Structure",
    component: VixTermStructure,
    zRole: "anchor",
    logic:
      "The fastest single-glance risk-tone read entering the page: where VIX sits, and whether the term structure is pricing calm (contango) or near-term stress (backwardation). Plays the role the Regime Strip plays on the macro dashboard.",
    defaultLayout: { x: 0, y: 0, w: 7, h: 8, minW: 4, minH: 6 },
  },
  {
    id: "eq-concentration",
    title: "S&P 500 Concentration",
    component: SP500Concentration,
    zRole: "scan",
    logic:
      "The single most-debated actionable read in this market regime — is breadth dangerously narrow? Ends the first sweep on the sharpest signal, the equity-dashboard equivalent of Classification.",
    // Ranks all 10 top-weight names — shorter than this crops rows, so
    // unlike the shorter tiles around it, this one keeps its original height.
    defaultLayout: { x: 7, y: 0, w: 5, h: 11, minW: 4, minH: 6 },
  },
  {
    id: "eq-sectors",
    title: "Sector Performance",
    component: SectorPerformance,
    zRole: "scan",
    logic:
      "Where the move is actually coming from — the 11 GICS sectors ranked by today's move, with 1W/1M alongside to tell a one-day pop from a real rotation.",
    // All 11 GICS sectors — same reasoning as Concentration above.
    defaultLayout: { x: 0, y: 11, w: 5, h: 11, minW: 4, minH: 6 },
  },
  {
    id: "eq-movers",
    title: "Market Movers",
    component: MarketMovers,
    zRole: "scan",
    logic:
      "The single-name extremes underneath the index-level read — today's biggest S&P 500 gainers and losers, side by side.",
    // 5 rows each side — h:7 crops the 5th mid-row.
    defaultLayout: { x: 5, y: 11, w: 7, h: 8, minW: 4, minH: 6 },
  },
  {
    id: "eq-indices",
    title: "Equity Indices",
    component: EquityIndices,
    zRole: "pivot",
    logic:
      "The chart this dashboard hangs on — the broadest, most information-dense read of how the major indices are actually performing. Gets the most area, the same role the Hinge plays on the macro dashboard. Toggle 1M/3M/1Y or hover for a crosshair readout.",
    defaultLayout: { x: 0, y: 22, w: 12, h: 9, minW: 6, minH: 8 },
  },
  {
    id: "eq-curve",
    title: "Yield Curve",
    component: EquityYieldCurve,
    zRole: "support",
    logic:
      "The rates backdrop for equity valuation and discount-rate context — consult-on-demand supporting evidence, the same role it plays on the macro dashboard.",
    defaultLayout: { x: 0, y: 31, w: 7, h: 7, minW: 4, minH: 6 },
  },
  {
    id: "eq-oil",
    title: "Commodities",
    component: Commodities,
    zRole: "terminal",
    logic:
      "A small exit-point tile — the real-economy inflation-impulse check (oil, gold, copper, nat gas) you glance at on the way out, the same role Commodities plays on the macro dashboard.",
    defaultLayout: { x: 7, y: 31, w: 5, h: 7, minW: 3, minH: 4 },
  },
  {
    id: "eq-calendar",
    title: "Macro Calendar",
    component: EarningsCalendar,
    zRole: "support",
    logic:
      "What's next — the upcoming macro events (FOMC, CPI, payrolls, ISM) most likely to move the tape, a reference footer you consult on demand.",
    // 6 events per column — shorter than this crops the last one mid-row.
    defaultLayout: { x: 0, y: 38, w: 12, h: 10, minW: 6, minH: 5 },
  },
];

export const EQUITY_DEFAULT_HIDDEN: string[] = EQUITY_ELEMENTS.filter((e) => e.defaultHidden).map((e) => e.id);
export const EQUITY_ELEMENT_MAP = new Map(EQUITY_ELEMENTS.map((e) => [e.id, e]));
