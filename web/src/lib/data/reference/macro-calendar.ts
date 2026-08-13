/**
 * Macro release calendar — FOMC / CPI / Employment Situation (NFP) / ISM
 * Manufacturing PMI. These dates are published by the Fed/BLS/ISM many
 * months ahead, so a hardcoded list is legitimate reference data (not mock)
 * — no live source is needed or exists for "when is the next CPI print."
 * Consensus/prior figures are deliberately omitted: those genuinely do
 * change and aren't obtainable free & live, so we show the date and metric
 * only rather than fabricate a number.
 *
 * Sources (verified 2026-08-13): federalreserve.gov/monetarypolicy/fomccalendars.htm,
 * bls.gov/schedule/, ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/
 * Refresh when this list runs low — the Fed/BLS/ISM publish roughly a year ahead.
 */
import type { CalendarEvent } from "../types-equity";
import { FOMC_MEETINGS } from "./fomc-dates";

interface MacroEvent {
  date: string; // YYYY-MM-DD
  label: string;
  detail: string;
}

const MACRO_EVENTS: MacroEvent[] = [
  { date: "2026-08-13", label: "Retail Sales", detail: "US Census Bureau, prior month" },
  { date: "2026-09-01", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-09-04", label: "Employment Situation (NFP)", detail: "BLS, August 2026 data" },
  { date: "2026-09-11", label: "CPI (Headline & Core)", detail: "BLS, August 2026 data" },
  { date: "2026-10-01", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-10-02", label: "Employment Situation (NFP)", detail: "BLS, September 2026 data" },
  { date: "2026-10-14", label: "CPI (Headline & Core)", detail: "BLS, September 2026 data" },
  { date: "2026-11-02", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-11-06", label: "Employment Situation (NFP)", detail: "BLS, October 2026 data" },
  { date: "2026-11-10", label: "CPI (Headline & Core)", detail: "BLS, October 2026 data" },
  { date: "2026-12-01", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-12-04", label: "Employment Situation (NFP)", detail: "BLS, November 2026 data" },
  { date: "2026-12-10", label: "CPI (Headline & Core)", detail: "BLS, November 2026 data" },
  // FOMC dates come from the shared fomc-dates.ts list rather than being duplicated here.
  ...FOMC_MEETINGS.map((m) => ({ date: m.date, label: "FOMC Rate Decision", detail: `Second day of the ${m.label} meeting` })),
];

function upcoming(now: Date): { date: string; label: string; detail: string; daysFromNow: number }[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const MS_PER_DAY = 86400000;
  return MACRO_EVENTS.map((e) => ({
    ...e,
    daysFromNow: Math.round((new Date(`${e.date}T00:00:00`).getTime() - startOfToday) / MS_PER_DAY),
  }))
    .filter((e) => e.daysFromNow >= 0)
    .sort((a, b) => a.daysFromNow - b.daysFromNow);
}

/** Pure + synchronous: converts the static list to daysFromNow-relative CalendarEvents, dropping anything already past. */
export function buildCalendarBucket(now: Date): CalendarEvent[] {
  return upcoming(now).map((e) => ({ daysFromNow: e.daysFromNow, kind: "macro" as const, label: e.label, detail: e.detail }));
}

const WEEKDAY_CODES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

/**
 * Macro dashboard's Key Releases tile shape: [weekday, name, value][]. No
 * consensus figure — that genuinely isn't free/live, so the honest choice is
 * "—" rather than a fabricated forecast. Real dates and names only.
 */
export function buildReleasesList(now: Date, limit = 5): [string, string, string][] {
  return upcoming(now)
    .slice(0, limit)
    .map((e) => [WEEKDAY_CODES[new Date(`${e.date}T00:00:00`).getDay()], e.label, "—"]);
}
