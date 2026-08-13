/**
 * FRED's keyless CSV endpoint (`fred.stlouisfed.org/graph/fredgraph.csv`).
 * Verified by hand during planning against 16 series (DGS10, DFII10, T10YIE,
 * NFCI, CPIAUCSL, CPILFESL, BAMLH0A0HYM2, T10Y2Y, DFEDTARL/U, PAYEMS, UNRATE,
 * CES0500000003, ICSA, CIVPART, JTSJOL) — all keyless, no signup, no crumb.
 * Format: `observation_date,SERIES_ID` header, then `YYYY-MM-DD,value` rows;
 * a missing observation (holiday, not-yet-released month) is an EMPTY value
 * field, not FRED's older "." convention — every row must be checked, not
 * just the last line.
 */

const FETCH_TIMEOUT_MS = 8000;

export interface FredObservation {
  date: string; // YYYY-MM-DD
  value: number;
}

/** Pure parse, no network — unit-testable against a captured fixture. Drops empty/non-numeric rows, keeps chronological order. */
export function parseFredCsv(raw: string): FredObservation[] {
  const lines = raw.trim().split("\n").slice(1); // drop the header row
  const out: FredObservation[] = [];
  for (const line of lines) {
    const comma = line.indexOf(",");
    if (comma === -1) continue;
    const date = line.slice(0, comma).trim();
    const valueStr = line.slice(comma + 1).trim();
    const value = Number(valueStr);
    // Number("") is 0, not NaN — an empty field (holiday, not-yet-released month) must be checked explicitly.
    if (date && valueStr && Number.isFinite(value)) out.push({ date, value });
  }
  return out;
}

/**
 * Fetches a FRED series and returns its observations, most-recent-last.
 * `sinceYears` trims the request to a recent window server-side isn't
 * possible with this endpoint (it always returns full history), so trimming
 * happens client-side after parse — cheap relative to the fetch itself.
 */
export async function fetchFredSeries(seriesId: string, sinceYears?: number, revalidateSeconds = 3600): Promise<FredObservation[]> {
  const url = `https://fred.stlouisfed.org/graph/fredgraph.csv?id=${encodeURIComponent(seriesId)}`;
  const res = await fetch(url, {
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: revalidateSeconds, tags: [`fred-${seriesId}`] },
  });
  if (!res.ok) throw new Error(`FRED ${seriesId}: HTTP ${res.status}`);
  const obs = parseFredCsv(await res.text());
  if (obs.length === 0) throw new Error(`FRED ${seriesId}: no observations`);
  if (sinceYears === undefined) return obs;
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - sinceYears);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  const trimmed = obs.filter((o) => o.date >= cutoffStr);
  return trimmed.length > 0 ? trimmed : obs.slice(-10);
}

/** Convenience: the latest (most recent, non-empty) observation's value. */
export async function fetchFredLatest(seriesId: string, revalidateSeconds = 3600): Promise<number> {
  const obs = await fetchFredSeries(seriesId, undefined, revalidateSeconds);
  return obs[obs.length - 1].value;
}

/** Index of the first observation on/after Jan 1 of `year` — for YTD-style change calcs, mirrors yahoo-chart.ts's indexNearYearStart. */
export function indexNearYearStartFred(obs: FredObservation[], year: number): number {
  const idx = obs.findIndex((o) => o.date >= `${year}-01-01`);
  return idx === -1 ? 0 : idx;
}
