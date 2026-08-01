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
import OilPrice from "@/components/elements-equity/OilPrice";
import SP500Concentration from "@/components/elements-equity/SP500Concentration";

export const EQUITY_ELEMENTS: ElementDef[] = [
  {
    id: "eq-vix",
    title: "VIX & Term Structure",
    component: VixTermStructure,
    zRole: "anchor",
    logic:
      "The fastest single-glance risk-tone read entering the page: where VIX sits, and whether the term structure is pricing calm (contango) or near-term stress (backwardation). Plays the role the Regime Strip plays on the macro dashboard.",
    defaultLayout: { x: 0, y: 0, w: 7, h: 9, minW: 4, minH: 6 },
  },
  {
    id: "eq-concentration",
    title: "S&P 500 Concentration",
    component: SP500Concentration,
    zRole: "scan",
    logic:
      "The single most-debated actionable read in this market regime — is breadth dangerously narrow? Ends the first sweep on the sharpest signal, the equity-dashboard equivalent of Classification.",
    defaultLayout: { x: 7, y: 0, w: 5, h: 9, minW: 4, minH: 6 },
  },
  {
    id: "eq-indices",
    title: "Equity Indices",
    component: EquityIndices,
    zRole: "pivot",
    logic:
      "The chart this dashboard hangs on — the broadest, most information-dense read of how the major indices are actually performing. Gets the most area, the same role the Hinge plays on the macro dashboard.",
    defaultLayout: { x: 0, y: 9, w: 12, h: 11, minW: 6, minH: 8 },
  },
  {
    id: "eq-curve",
    title: "Yield Curve",
    component: EquityYieldCurve,
    zRole: "support",
    logic:
      "The rates backdrop for equity valuation and discount-rate context — consult-on-demand supporting evidence, the same role it plays on the macro dashboard.",
    defaultLayout: { x: 0, y: 20, w: 7, h: 9, minW: 4, minH: 6 },
  },
  {
    id: "eq-oil",
    title: "Oil",
    component: OilPrice,
    zRole: "terminal",
    logic:
      "A small exit-point tile — the real-economy inflation-impulse check, the last thing you glance at on the way out.",
    defaultLayout: { x: 7, y: 20, w: 5, h: 9, minW: 3, minH: 4 },
  },
];

export const EQUITY_DEFAULT_HIDDEN: string[] = EQUITY_ELEMENTS.filter((e) => e.defaultHidden).map((e) => e.id);
export const EQUITY_ELEMENT_MAP = new Map(EQUITY_ELEMENTS.map((e) => [e.id, e]));
