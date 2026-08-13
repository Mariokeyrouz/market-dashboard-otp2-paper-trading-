/**
 * Direct TS port of macro_logic.py's `classify_hinge()` — same rule, same
 * tunable constants, same tags/notes. Classifies *why* the 10Y nominal yield
 * is moving: which leg (real yield vs. breakeven inflation) dominates the
 * move over the lookback window.
 */
import { COL_GROWTH, COL_INFLATION, COL_NEUTRAL } from "./colors";

/** Minimum nominal-yield move (pp) over the lookback to count as "rising". */
export const NOMINAL_RISE_EPS = 0.02;
/** If the two legs' absolute moves are within this band (pp), no dominant leg — Mixed/Neutral. */
export const LEG_DOMINANCE_EPS = 0.02;

export interface HingeInput {
  nominalChg: number;
  realChg: number;
  breakevenChg: number;
}

export interface HingeResult {
  label: string;
  color: string;
  dominant: "real" | "breakeven" | null;
  tags: string[];
  note: string;
  nominalDir: "rising" | "falling" | "flat";
}

export function classifyHinge({ nominalChg, realChg, breakevenChg }: HingeInput): HingeResult {
  const nominalRising = nominalChg > NOMINAL_RISE_EPS;
  const realAbs = Math.abs(realChg);
  const beAbs = Math.abs(breakevenChg);
  const gap = Math.abs(beAbs - realAbs);
  const nominalDir = nominalRising ? "rising" : nominalChg < -NOMINAL_RISE_EPS ? "falling" : "flat";

  if (!nominalRising || gap <= LEG_DOMINANCE_EPS) {
    const reason = !nominalRising ? "nominal not clearly rising" : "real and breakeven moved by similar amounts";
    return { label: "Mixed / Neutral", color: COL_NEUTRAL, dominant: null, tags: ["no dominant leg"], note: `No clean read — ${reason}.`, nominalDir };
  }

  if (beAbs > realAbs) {
    return {
      label: "Inflation Scare", color: COL_INFLATION, dominant: "breakeven",
      tags: ["duration-negative", "gold-positive", "risk-ambiguous"],
      note: "Nominal up, led by the breakeven (inflation-expectations) leg.", nominalDir,
    };
  }

  return {
    label: "Growth / Tightening Shock", color: COL_GROWTH, dominant: "real",
    tags: ["equities-negative", "credit-negative", "growth-factor-negative"],
    note: "Nominal up, led by the real-yield (growth/policy-tightening) leg.", nominalDir,
  };
}

/** classDesc/classMover formatting matches mock.ts's existing convention ("Breakeven leg" / "Real-yield leg"). */
export function classMoverLabel(dominant: HingeResult["dominant"]): string {
  if (dominant === "breakeven") return "Breakeven leg";
  if (dominant === "real") return "Real-yield leg";
  return "No dominant leg";
}
