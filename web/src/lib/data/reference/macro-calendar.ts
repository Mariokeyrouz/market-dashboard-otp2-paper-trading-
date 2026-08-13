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
  { date: "2026-09-16", label: "FOMC Rate Decision", detail: "Second day of the Sep 15–16 meeting" },
  { date: "2026-10-01", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-10-02", label: "Employment Situation (NFP)", detail: "BLS, September 2026 data" },
  { date: "2026-10-14", label: "CPI (Headline & Core)", detail: "BLS, September 2026 data" },
  { date: "2026-10-28", label: "FOMC Rate Decision", detail: "Second day of the Oct 27–28 meeting" },
  { date: "2026-11-02", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-11-06", label: "Employment Situation (NFP)", detail: "BLS, October 2026 data" },
  { date: "2026-11-10", label: "CPI (Headline & Core)", detail: "BLS, October 2026 data" },
  { date: "2026-12-01", label: "ISM Manufacturing PMI", detail: "ISM, prior month" },
  { date: "2026-12-04", label: "Employment Situation (NFP)", detail: "BLS, November 2026 data" },
  { date: "2026-12-09", label: "FOMC Rate Decision", detail: "Second day of the Dec 8–9 meeting" },
  { date: "2026-12-10", label: "CPI (Headline & Core)", detail: "BLS, November 2026 data" },
];

/** Pure + synchronous: converts the static list to daysFromNow-relative CalendarEvents, dropping anything already past. */
export function buildCalendarBucket(now: Date): CalendarEvent[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const MS_PER_DAY = 86400000;
  return MACRO_EVENTS.map((e) => {
    const eventDate = new Date(`${e.date}T00:00:00`);
    const daysFromNow = Math.round((eventDate.getTime() - startOfToday) / MS_PER_DAY);
    return { daysFromNow, kind: "macro" as const, label: e.label, detail: e.detail };
  }).filter((e) => e.daysFromNow >= 0);
}
