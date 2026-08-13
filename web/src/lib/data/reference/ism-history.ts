/**
 * ISM Manufacturing PMI — trailing monthly prints. ISM restricts free
 * redistribution of its data (not on FRED, no free API), so unlike every
 * other series in this app this is genuinely static reference data, sourced
 * once from ISM's own published reports and business press coverage,
 * refreshed periodically. This is a real number from a real release, not a
 * placeholder — the honesty bar is "sourced and dated," same as the FOMC
 * calendar, not "continuously live."
 *
 * 50.0 is expansion/contraction breakeven by ISM's own definition (not a
 * threshold we invented) — see classify/regime.ts's growthTrendFromIsm.
 *
 * Sourced 2026-08-13 from ISM's monthly PMI reports (ismworld.org) and
 * business-press coverage of each release. Refresh monthly after the first
 * business day (new print) by appending one row — see fomc-dates.ts for the
 * release-date convention used elsewhere in this app.
 */
export const ISM_MANUFACTURING_PMI: { month: string; value: number }[] = [
  { month: "2025-08", value: 48.0 },
  { month: "2025-09", value: 48.7 },
  { month: "2025-10", value: 49.1 },
  { month: "2025-11", value: 48.2 },
  { month: "2025-12", value: 47.9 },
  { month: "2026-01", value: 52.6 },
  { month: "2026-02", value: 52.4 },
  { month: "2026-03", value: 52.7 },
  { month: "2026-04", value: 52.7 },
  { month: "2026-05", value: 54.0 },
  { month: "2026-06", value: 53.3 },
  { month: "2026-07", value: 55.6 },
];

/** The latest print and the one before it — what growthTrendFromIsm() needs. */
export function latestIsmPair(): { latest: number; prior: number; month: string } {
  const n = ISM_MANUFACTURING_PMI.length;
  return {
    latest: ISM_MANUFACTURING_PMI[n - 1].value,
    prior: ISM_MANUFACTURING_PMI[n - 2].value,
    month: ISM_MANUFACTURING_PMI[n - 1].month,
  };
}
