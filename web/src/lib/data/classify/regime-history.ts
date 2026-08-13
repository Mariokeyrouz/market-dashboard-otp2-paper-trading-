/**
 * Not a port from macro_logic.py — this repo's own logic for turning
 * `classifyRegime`'s single-point-in-time call into the regimeDays/
 * regimeSince/history the RegimeStrip tile needs. Monthly granularity only
 * (CPI is monthly, ISM is monthly) — this can't know the exact day a regime
 * flipped, only the month, so `regimeSince` is the 1st of that month. That's
 * an honest limitation of monthly inputs, not an approximation dressed up as
 * precision.
 */
import type { FredObservation } from "../providers/fred";
import type { RegimeSeg } from "../types";
import { classifyRegime, cpiTrendFromYoy, growthTrendFromIsm } from "./regime";

export interface MonthlyValue {
  month: string; // "YYYY-MM"
  value: number;
}

export interface RegimeHistoryResult {
  label: string;
  color: string;
  regimeDays: number;
  regimeSince: string; // e.g. "Jan 1, 2026"
  history: RegimeSeg[];
}

function monthIndex(month: string): number {
  const [y, m] = month.split("-").map(Number);
  return y * 12 + (m - 1);
}

function monthKeyAt(idx: number): string {
  const y = Math.floor(idx / 12);
  const m = (idx % 12) + 1;
  return `${y}-${String(m).padStart(2, "0")}`;
}

function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

/** Collapses monthly CPIAUCSL observations to one (most recent) value per calendar month. */
function monthlyIndexFromObservations(obs: FredObservation[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const o of obs) map.set(o.date.slice(0, 7), o.value);
  return map;
}

export function computeRegimeHistory(cpiObservations: FredObservation[], ismHistory: MonthlyValue[], now: Date): RegimeHistoryResult {
  const cpiByMonth = monthlyIndexFromObservations(cpiObservations);

  const yoyByMonth = new Map<string, number>();
  for (const [month, value] of cpiByMonth) {
    const priorMonth = monthKeyAt(monthIndex(month) - 12);
    const priorValue = cpiByMonth.get(priorMonth);
    if (priorValue !== undefined) yoyByMonth.set(month, (value / priorValue - 1) * 100);
  }

  const timeline: { month: string; label: string; color: string }[] = [];
  for (let j = 1; j < ismHistory.length; j++) {
    const { month, value } = ismHistory[j];
    const growthTrend = growthTrendFromIsm(value, ismHistory[j - 1].value);

    const yoyNow = yoyByMonth.get(month);
    const yoyPriorMonth = monthKeyAt(monthIndex(month) - 3);
    const yoyPrior = yoyByMonth.get(yoyPriorMonth);
    if (yoyNow === undefined || yoyPrior === undefined) continue;

    const cpiTrend = cpiTrendFromYoy(yoyNow, yoyPrior);
    const { label, color } = classifyRegime(cpiTrend, growthTrend);
    timeline.push({ month, label, color });
  }

  if (timeline.length === 0) {
    // Should be unreachable given a 12-month ISM table and 3y of CPI history, but never leave the caller with nothing.
    throw new Error("computeRegimeHistory: no month has both CPI trend and growth trend available");
  }

  const current = timeline[timeline.length - 1];

  // Runs of consecutive equal labels, oldest first — also the `history` strip's segments.
  const runs: { label: string; color: string; months: number; startMonth: string }[] = [];
  for (const point of timeline) {
    const last = runs[runs.length - 1];
    if (last && last.label === point.label) last.months += 1;
    else runs.push({ label: point.label, color: point.color, months: 1, startMonth: point.month });
  }
  const currentRun = runs[runs.length - 1];

  const sinceIdx = monthIndex(currentRun.startMonth);
  const sinceDate = new Date(Math.floor(sinceIdx / 12), sinceIdx % 12, 1);
  const regimeDays = Math.max(0, Math.round((now.getTime() - sinceDate.getTime()) / 86400000));

  return {
    label: current.label,
    color: current.color,
    regimeDays,
    regimeSince: monthLabel(currentRun.startMonth),
    history: runs.map((r) => ({ label: r.label, color: r.color, w: r.months * 10 })),
  };
}
