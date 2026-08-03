/**
 * Single source of truth for "what dashboard types exist." Every place that
 * used to hardcode the macro ELEMENTS/ELEMENT_MAP (the store, DashboardGrid,
 * LeftRail, Header, LogicContent, the element-library trays) reads through
 * here instead, so adding a third dashboard type later means adding one
 * registry file + one entry below — nothing else.
 */
import type { ElementDef } from "./elements/registry";
import { DEFAULT_HIDDEN, ELEMENTS, ELEMENT_MAP } from "./elements/registry";
import { EQUITY_DEFAULT_HIDDEN, EQUITY_ELEMENTS, EQUITY_ELEMENT_MAP } from "./elements/registry-equity";

export type DashboardType = "macro" | "equity";

export interface DashboardTypeDef {
  id: DashboardType;
  label: string;
  shortLabel: string;
  elements: ElementDef[];
  defaultHidden: string[];
  elementMap: Map<string, ElementDef>;
  /** Whether this dashboard has the US/EU/CN/JP/GL point-of-view lens. */
  hasRegionLens: boolean;
  logicIntro: {
    /** The "how to read this" paragraph, dashboard-specific. */
    blurb: string;
    /** Exactly 5 short labels for the Z-diagram's fixed 5 positions. */
    zSteps: string[];
    /** Trailing footer note — only dashboards with a region lens need one. */
    pinFooter?: string;
  };
}

export const DASHBOARD_TYPES: DashboardTypeDef[] = [
  {
    id: "macro",
    label: "Macro Signal Dashboard",
    shortLabel: "Macro",
    elements: ELEMENTS,
    defaultHidden: DEFAULT_HIDDEN,
    elementMap: ELEMENT_MAP,
    hasRegionLens: true,
    logicIntro: {
      blurb:
        "1 · Where are we? (regime, top-left) → 2 · What's the signal? (classification, top-right) → " +
        "3 · Why? (the Hinge decomposition on the diagonal) → 4 · Is it confirmed? (tripwires, the bottom stroke) → " +
        "5 · What's next? (calendar, bottom-right exit). Everything else is supporting evidence you consult on demand.",
      zSteps: [
        "1 · Regime — where are we?",
        "2 · Classification — the signal",
        "3 · The Hinge — why it's moving",
        "4 · Tripwires — confirm / deny",
        "5 · Calendar — what's next",
      ],
      pinFooter:
        "In Customize, any tile can be pinned to its own region — pinned tiles ignore the header lens and " +
        "carry a POV chip so you can tell at a glance.",
    },
  },
  {
    id: "equity",
    label: "Equity Dashboard",
    shortLabel: "Equity",
    elements: EQUITY_ELEMENTS,
    defaultHidden: EQUITY_DEFAULT_HIDDEN,
    elementMap: EQUITY_ELEMENT_MAP,
    hasRegionLens: false,
    logicIntro: {
      blurb:
        "1 · What's the risk tone? (VIX & term structure, top-left) → 2 · Is breadth narrow, and where's the move coming from? " +
        "(S&P 500 concentration, sector performance, and market movers, top-right) → 3 · How are indices actually performing? " +
        "(the indices chart on the diagonal, toggle 1M/3M/1Y or hover for a crosshair) → 4 · What's the rates backdrop? (yield curve) → " +
        "5 · What's next? (commodities for the inflation impulse, and the earnings/FOMC calendar for upcoming catalysts).",
      zSteps: [
        "1 · VIX — risk tone",
        "2 · Concentration & rotation — the signal",
        "3 · Indices — how it's moving",
        "4 · Yield Curve — confirm / deny",
        "5 · Commodities & Calendar — what's next",
      ],
    },
  },
];

export const DASHBOARD_TYPE_MAP = new Map(DASHBOARD_TYPES.map((d) => [d.id, d]));
export const DEFAULT_DASHBOARD_TYPE: DashboardType = "macro";

export function getDashboardDef(type: DashboardType): DashboardTypeDef {
  return DASHBOARD_TYPE_MAP.get(type)!;
}
