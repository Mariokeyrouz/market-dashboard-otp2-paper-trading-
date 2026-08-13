/**
 * Direct TS port of `macro_logic.py`'s `classify_regime()` (repo root) — the
 * same rule, same labels, same colors, kept in sync deliberately. That
 * module's docstring: "these rules are OPINIONATED and STYLE-DEPENDENT... a
 * lens, not objective fact." This port carries the same caveat forward.
 */
import { COL_NEUTRAL, COL_RISK_ON, COL_STAG } from "./colors";

export type CpiTrend = "cooling" | "sticky" | "rising";
export type GrowthTrend = "expanding" | "slowing" | "contracting";

export interface RegimeResult {
  label: string;
  color: string;
  note: string;
}

export function classifyRegime(cpiTrend: CpiTrend, growth: GrowthTrend): RegimeResult {
  const hotInflation = cpiTrend === "sticky" || cpiTrend === "rising";
  const weakGrowth = growth === "slowing" || growth === "contracting";

  if (hotInflation && weakGrowth) {
    return { label: "Stagflation", color: COL_STAG, note: "Sticky/rising inflation alongside slowing growth." };
  }
  if (cpiTrend === "cooling" && (growth === "expanding" || growth === "slowing")) {
    return { label: "Soft Landing", color: COL_RISK_ON, note: "Inflation cooling while growth holds up." };
  }
  if (cpiTrend === "cooling" && growth === "contracting") {
    return { label: "Disinflation", color: COL_NEUTRAL, note: "Inflation cooling as growth rolls over." };
  }
  return { label: "Mixed / Transitional", color: COL_NEUTRAL, note: "No clean regime read on current inputs." };
}

/** Not in macro_logic.py — new, small, and documented like its neighbors: this repo's own thresholding for turning raw CPI YoY history into a trend label. */
const CPI_TREND_EPS_PP = 0.2;

export function cpiTrendFromYoy(latestYoy: number, priorYoy: number): CpiTrend {
  const delta = latestYoy - priorYoy;
  if (delta > CPI_TREND_EPS_PP) return "rising";
  if (delta < -CPI_TREND_EPS_PP) return "cooling";
  return "sticky";
}

/** ISM's own convention: 50 is the expand/contract breakeven, not an arbitrary threshold. */
const GROWTH_TREND_EPS = 0.2;

export function growthTrendFromIsm(latestIsm: number, priorIsm: number): GrowthTrend {
  if (latestIsm < 50) return "contracting";
  if (latestIsm < priorIsm - GROWTH_TREND_EPS) return "slowing";
  return "expanding";
}
