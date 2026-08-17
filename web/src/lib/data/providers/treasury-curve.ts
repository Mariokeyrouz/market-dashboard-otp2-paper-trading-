/**
 * US Treasury's official daily par-yield-curve feed. Free, keyless, and the
 * least fragile source in this project (a federal data feed, not an
 * unofficial API) — verified by hand during planning to expose exactly the
 * 8 tenors this app needs. The feed returns one entry per trading day for a
 * given month; we take the entry with the latest NEW_DATE.
 *
 * The XML shape is simple and repetitive enough that a small regex parser
 * avoids pulling in an XML parsing dependency for one feed. Every expected
 * field is validated as present and numeric before returning — a format
 * change here should fail loudly (and fall back), not silently return
 * garbage into the yield curve tile.
 */

const FETCH_TIMEOUT_MS = 8000;

/** Every tenor the feed exposes that this app might want, [label, field suffix]. Callers pick a subset. */
const ALL_TENOR_FIELDS: [string, string][] = [
  ["1M", "BC_1MONTH"],
  ["3M", "BC_3MONTH"],
  ["6M", "BC_6MONTH"],
  ["1Y", "BC_1YEAR"],
  ["2Y", "BC_2YEAR"],
  ["5Y", "BC_5YEAR"],
  ["7Y", "BC_7YEAR"],
  ["10Y", "BC_10YEAR"],
  ["30Y", "BC_30YEAR"],
];

/** The Equity dashboard's curve tenor set, in its expected order (unchanged from the original 8-tenor build). */
export const EQUITY_TENORS = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"];
/** The Macro dashboard's curve tenor set (mirrors macro_data.py's mock, adds 7Y, drops 1M/6M). */
export const MACRO_TENORS = ["3M", "1Y", "2Y", "5Y", "7Y", "10Y", "30Y"];

function feedUrl(yyyymm: string): string {
  return `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=${yyyymm}`;
}

export interface CurveSnapshot {
  /** Raw `NEW_DATE` value from the feed, e.g. "2026-08-12T00:00:00". */
  date: string;
  curve: [string, number][];
}

function extractCurve(xml: string, tenors: string[]): [string, number][] | null {
  const fieldByLabel = new Map(ALL_TENOR_FIELDS);
  const curve: [string, number][] = [];
  for (const label of tenors) {
    const field = fieldByLabel.get(label);
    if (!field) throw new Error(`Treasury feed: unknown tenor "${label}"`);
    const match = xml.match(new RegExp(`<d:${field}[^>]*>([^<]+)</d:${field}>`));
    const value = match ? Number(match[1]) : NaN;
    if (!Number.isFinite(value)) return null;
    curve.push([label, value]);
  }
  return curve;
}

/**
 * Every dated entry in the feed with a complete `tenors` set, newest first —
 * a full month of trading days, so callers can pick a real historical
 * snapshot (e.g. ~1 week back) instead of "latest only".
 */
export function parseTreasuryFeedHistory(raw: string, tenors: string[] = EQUITY_TENORS): CurveSnapshot[] {
  const entries = raw.split("<entry>").slice(1); // first chunk is the feed header, not an entry
  if (entries.length === 0) throw new Error("Treasury feed: no entries");

  const snapshots: CurveSnapshot[] = [];
  for (const entry of entries) {
    const dateMatch = entry.match(/<d:NEW_DATE[^>]*>([^<]+)<\/d:NEW_DATE>/);
    if (!dateMatch) continue;
    const curve = extractCurve(entry, tenors);
    if (curve) snapshots.push({ date: dateMatch[1], curve });
  }
  if (snapshots.length === 0) throw new Error("Treasury feed: no dated entries with a complete tenor set");
  snapshots.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  return snapshots;
}

/** Pure parse, no network — unit-testable against a captured fixture. `tenors` selects and orders the output. */
export function parseTreasuryFeed(raw: string, tenors: string[] = EQUITY_TENORS): [string, number][] {
  return parseTreasuryFeedHistory(raw, tenors)[0].curve;
}

async function fetchMonth(yyyymm: string): Promise<string> {
  const res = await fetch(feedUrl(yyyymm), {
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: 21600, tags: ["treasury-curve"] },
  });
  if (!res.ok) throw new Error(`Treasury feed: HTTP ${res.status}`);
  return res.text();
}

function monthKey(d: Date): string {
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * The current curve plus a real historical snapshot ~`tradingDaysBack`
 * trading days earlier (default 5 ≈ 1 week) — used to replace a fabricated
 * "1 week ago" offset with an actual past reading and its real date.
 * Early in a month there may not be enough entries yet, so this pulls in
 * the previous month's feed too when needed.
 */
export async function fetchTreasuryCurveWithHistory(
  tenors: string[] = EQUITY_TENORS,
  tradingDaysBack = 5,
): Promise<{ now: CurveSnapshot; prev: CurveSnapshot }> {
  const today = new Date();
  const prevMonthDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);

  let snapshots: CurveSnapshot[] = [];
  try {
    snapshots = parseTreasuryFeedHistory(await fetchMonth(monthKey(today)), tenors);
  } catch {
    // This month's feed may be empty (start of month) or unreachable —
    // the previous-month fallback below still has a shot at a full history.
  }
  if (snapshots.length <= tradingDaysBack) {
    try {
      const older = parseTreasuryFeedHistory(await fetchMonth(monthKey(prevMonthDate)), tenors);
      const seen = new Set(snapshots.map((s) => s.date));
      snapshots = [...snapshots, ...older.filter((s) => !seen.has(s.date))]
        .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    } catch {
      // Fine as long as the current-month fetch above produced something.
    }
  }
  if (snapshots.length === 0) throw new Error("Treasury feed: no usable snapshots");
  return { now: snapshots[0], prev: snapshots[Math.min(tradingDaysBack, snapshots.length - 1)] };
}
