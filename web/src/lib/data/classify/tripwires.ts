/**
 * Direct TS ports of macro_logic.py's `vol_curve_state()` and `curve_state()`
 * — small, honest, directional-only flags. No hit-rate or correlation
 * number is asserted by either, matching the source's explicit intent.
 */
import { COL_NEUTRAL, COL_RISK_OFF, COL_RISK_ON } from "./colors";

export interface StateResult {
  label: string;
  color: string;
  note: string;
}

/** front < back -> Contango (typical, risk-on tilt); front > back -> Backwardation (stress tripwire). */
export function volCurveState(front: number, back: number): StateResult & { spread: number } {
  const spread = back - front;
  if (spread > 0) return { label: "Contango", color: COL_RISK_ON, note: "Front below back month — calm / risk-on tilt.", spread };
  if (spread < 0) return { label: "Backwardation", color: COL_RISK_OFF, note: "Front above back month — stress / risk-off tripwire.", spread };
  return { label: "Flat", color: COL_NEUTRAL, note: "Curve roughly flat.", spread: 0 };
}

/** Near-flat band (pp) for the curve before calling it inverted or normal. */
export const CURVE_FLAT_EPS = 0.05;

/** Negative slope = inverted (late-cycle warning, framed directionally — no recession probability asserted). */
export function curveState(slope: number): StateResult {
  if (slope < -CURVE_FLAT_EPS) return { label: "Inverted", color: COL_RISK_OFF, note: "Short rates above long — late-cycle / recession-watch signal." };
  if (slope > CURVE_FLAT_EPS) return { label: "Normal", color: COL_RISK_ON, note: "Upward-sloping — no curve-inversion warning." };
  return { label: "Flat", color: COL_NEUTRAL, note: "Curve near flat — transitional." };
}
