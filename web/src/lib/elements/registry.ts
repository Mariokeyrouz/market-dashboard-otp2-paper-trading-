/**
 * Element registry — the single source of truth for the dashboard.
 * The grid renders from it, the default Z-pattern layout is derived from it,
 * and the Logic panel narrates from the same zRole/logic fields, so the
 * explainer can never drift from the actual layout.
 */
import type { ComponentType } from "react";

import CbCountdown from "@/components/elements/CbCountdown";
import Classification from "@/components/elements/Classification";
import Commodities from "@/components/elements/Commodities";
import CrossAssetHeatmap from "@/components/elements/CrossAssetHeatmap";
import EconSurprises from "@/components/elements/EconSurprises";
import FxChanges from "@/components/elements/FxChanges";
import Hinge from "@/components/elements/Hinge";
import KeyReleases from "@/components/elements/KeyReleases";
import LaborMarket from "@/components/elements/LaborMarket";
import MacroMatrix from "@/components/elements/MacroMatrix";
import Playbook from "@/components/elements/Playbook";
import Positioning from "@/components/elements/Positioning";
import RegimeStrip from "@/components/elements/RegimeStrip";
import Tripwires from "@/components/elements/Tripwires";
import YieldCurve from "@/components/elements/YieldCurve";

/** Where the element sits in the Z-pattern reading order. */
export type ZRole = "anchor" | "scan" | "pivot" | "terminal" | "support";

export const Z_ROLE_LABELS: Record<ZRole, string> = {
  anchor: "Z · entry (top-left)",
  scan: "Z · first sweep (top-right)",
  pivot: "Z · diagonal (centerpiece)",
  terminal: "Z · exit (bottom-right)",
  support: "supporting evidence",
};

export interface ElementDef {
  id: string;
  title: string;
  component: ComponentType;
  zRole: ZRole;
  /** One-sentence "why it's here" — rendered in the Logic panel. */
  logic: string;
  defaultLayout: { x: number; y: number; w: number; h: number; minW: number; minH: number };
  /**
   * Element reads every region rather than the one it's handed, so the
   * per-element POV pin doesn't apply and its control is hidden.
   */
  crossRegion?: boolean;
  /**
   * Not shown on a fresh dashboard. The default layout targets one screen
   * with no scrolling (~34 grid rows); these are the consult-on-demand tiles
   * that didn't make that cut. Re-addable from the Customize tray.
   */
  defaultHidden?: boolean;
}

export const ELEMENTS: ElementDef[] = [
  {
    id: "regime",
    title: "Regime Strip",
    component: RegimeStrip,
    zRole: "anchor",
    logic:
      "The eye enters a page top-left, so the first thing you see is cycle context: which regime we're in, for how long, and the four state variables (inflation, growth, policy, conditions) that define it. Every other read on the page is conditioned on this.",
    defaultLayout: { x: 0, y: 0, w: 8, h: 5, minW: 5, minH: 4 },
  },
  {
    id: "classification",
    title: "Classification",
    component: Classification,
    zRole: "scan",
    logic:
      "The first horizontal sweep ends top-right on the single actionable read: what today's yield move means (which leg is driving) and its portfolio implications. Context on the left, signal on the right.",
    defaultLayout: { x: 8, y: 0, w: 4, h: 6, minW: 3, minH: 5 },
  },
  {
    id: "hinge",
    title: "The Hinge",
    component: Hinge,
    zRole: "pivot",
    logic:
      "The Z's diagonal lands on the centerpiece: the 10Y nominal yield decomposed into its real-yield and breakeven legs. Which leg drives a move determines the regime classification and the playbook — this is the chart the whole dashboard hangs on, so it gets the most area.",
    defaultLayout: { x: 0, y: 5, w: 8, h: 8, minW: 6, minH: 8 },
  },
  {
    id: "playbook",
    title: "Regime Playbook",
    component: Playbook,
    zRole: "pivot",
    logic:
      "Sits directly beside the hinge because it translates the decomposition into positioning tilts — the bridge from 'what's moving' to 'what to do about it'.",
    defaultLayout: { x: 8, y: 6, w: 4, h: 4, minW: 3, minH: 4 },
  },
  {
    id: "tripwires",
    title: "Risk Tripwires",
    component: Tripwires,
    zRole: "scan",
    logic:
      "The Z's bottom stroke: a fast left-to-right confirm/deny scan. Credit, equity vol, the dollar and the curve either corroborate the hinge read or warn you off it. Directional signals, deliberately not precise.",
    defaultLayout: { x: 0, y: 14, w: 12, h: 4, minW: 8, minH: 4 },
  },
  {
    id: "matrix",
    title: "Macro Matrix",
    component: MacroMatrix,
    zRole: "support",
    crossRegion: true,
    logic:
      "Everything above reads one economy at a time; this reads all of them at once. A regime call only means something relative to the alternatives — US stagflation implies a different book if Europe is disinflating than if it's stuck too. Sits directly under the tripwires because it answers the question they provoke: 'is this local or global?' Click a row to move the lens to that region.",
    defaultLayout: { x: 0, y: 18, w: 12, h: 8, minW: 8, minH: 5 },
  },
  {
    id: "heatmap",
    title: "Cross-Asset Heatmap",
    component: CrossAssetHeatmap,
    zRole: "support",
    logic:
      "The tape's verdict: cross-asset returns over four horizons. If the regime read is right, it should be visible here — and disagreements are information.",
    defaultLayout: { x: 0, y: 26, w: 4, h: 8, minW: 3, minH: 7 },
  },
  {
    id: "surprises",
    title: "Economic Surprises",
    component: EconSurprises,
    zRole: "support",
    defaultHidden: true,
    logic:
      "Data versus expectations — the pulse of whether the macro narrative is beating or missing. Feeds the growth leg of the regime read.",
    defaultLayout: { x: 0, y: 34, w: 4, h: 7, minW: 3, minH: 6 },
  },
  {
    id: "cb",
    title: "Next Policy Meeting",
    component: CbCountdown,
    zRole: "terminal",
    logic:
      "Part of the natural exit point of the page: after reading state and signals, the last question is 'what's next?' — the countdown to the central bank and what's priced.",
    defaultLayout: { x: 8, y: 10, w: 4, h: 4, minW: 3, minH: 4 },
  },
  {
    id: "curve",
    title: "Yield Curve",
    component: YieldCurve,
    zRole: "support",
    logic:
      "The full term structure behind the hinge's single point: slope, shape word, and week-over-week shift. Where the cycle expresses itself in rates space.",
    defaultLayout: { x: 4, y: 26, w: 4, h: 8, minW: 3, minH: 8 },
  },
  {
    id: "releases",
    title: "Key Releases",
    component: KeyReleases,
    zRole: "terminal",
    defaultHidden: true,
    logic:
      "The other half of the exit point: this week's known catalysts and their consensus, so the last thing you carry away is the calendar of what could change the read.",
    defaultLayout: { x: 4, y: 34, w: 4, h: 6, minW: 3, minH: 5 },
  },
  {
    id: "positioning",
    title: "Positioning & Flows",
    component: Positioning,
    zRole: "support",
    defaultHidden: true,
    logic:
      "Crowding context: z-scores of net spec positioning. A signal that everyone already owns is a weaker signal — this panel tempers conviction.",
    defaultLayout: { x: 8, y: 34, w: 4, h: 6, minW: 3, minH: 5 },
  },
  {
    id: "commods",
    title: "Commodities",
    component: Commodities,
    zRole: "support",
    logic:
      "The real-economy inflation impulse in detail — the complex that feeds the breakeven leg of the hinge.",
    defaultLayout: { x: 8, y: 26, w: 4, h: 4, minW: 3, minH: 4 },
  },
  {
    id: "fx",
    title: "FX Changes",
    component: FxChanges,
    zRole: "support",
    logic:
      "The currency channel: how the region's exchange rates are moving and what that does to financial conditions.",
    defaultLayout: { x: 8, y: 30, w: 4, h: 4, minW: 3, minH: 4 },
  },
  {
    id: "labor",
    title: "Labor Market",
    component: LaborMarket,
    zRole: "support",
    defaultHidden: true,
    logic:
      "The slowest, stickiest input to the regime: employment. It confirms or eventually forces a regime change.",
    defaultLayout: { x: 0, y: 34, w: 4, h: 6, minW: 3, minH: 5 },
  },
];

/** Ids hidden on a fresh dashboard — see ElementDef.defaultHidden. */
export const DEFAULT_HIDDEN: string[] = ELEMENTS.filter((e) => e.defaultHidden).map((e) => e.id);

export const ELEMENT_MAP = new Map(ELEMENTS.map((e) => [e.id, e]));
