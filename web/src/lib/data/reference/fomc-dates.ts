/**
 * FOMC 2026 meeting schedule — published by the Fed roughly a year ahead
 * (federalreserve.gov/monetarypolicy/fomccalendars.htm, verified 2026-08-13).
 * `date` is the second day of each two-day meeting — when the rate decision
 * and statement are released at 2:00pm ET. Single source of truth: both the
 * Equity calendar tile and the Macro "Next Policy Meeting" tile read from
 * this list rather than duplicating the dates.
 */
export const FOMC_MEETINGS: { date: string; label: string }[] = [
  { date: "2026-01-28", label: "Jan 27–28" },
  { date: "2026-03-18", label: "Mar 17–18" },
  { date: "2026-04-29", label: "Apr 28–29" },
  { date: "2026-06-17", label: "Jun 16–17" },
  { date: "2026-07-29", label: "Jul 28–29" },
  { date: "2026-09-16", label: "Sep 15–16" },
  { date: "2026-10-28", label: "Oct 27–28" },
  { date: "2026-12-09", label: "Dec 8–9" },
];

/** The soonest meeting on/after `now`, with days-until — or null once the schedule runs out (refresh the list above). */
export function nextFomcMeeting(now: Date): { date: string; daysFromNow: number } | null {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const MS_PER_DAY = 86400000;
  const upcoming = FOMC_MEETINGS.map((m) => ({
    date: m.date,
    daysFromNow: Math.round((new Date(`${m.date}T00:00:00`).getTime() - startOfToday) / MS_PER_DAY),
  })).filter((m) => m.daysFromNow >= 0);
  return upcoming.length > 0 ? upcoming[0] : null;
}
