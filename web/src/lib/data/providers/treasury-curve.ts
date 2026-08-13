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

/** Pure parse, no network — unit-testable against a captured fixture. `tenors` selects and orders the output. */
export function parseTreasuryFeed(raw: string, tenors: string[] = EQUITY_TENORS): [string, number][] {
  const entries = raw.split("<entry>").slice(1); // first chunk is the feed header, not an entry
  if (entries.length === 0) throw new Error("Treasury feed: no entries");

  let latest: { date: string; xml: string } | null = null;
  for (const entry of entries) {
    const dateMatch = entry.match(/<d:NEW_DATE[^>]*>([^<]+)<\/d:NEW_DATE>/);
    if (!dateMatch) continue;
    if (!latest || dateMatch[1] > latest.date) latest = { date: dateMatch[1], xml: entry };
  }
  if (!latest) throw new Error("Treasury feed: no dated entries");

  const fieldByLabel = new Map(ALL_TENOR_FIELDS);
  const curve: [string, number][] = tenors.map((label) => {
    const field = fieldByLabel.get(label);
    if (!field) throw new Error(`Treasury feed: unknown tenor "${label}"`);
    const match = latest!.xml.match(new RegExp(`<d:${field}[^>]*>([^<]+)</d:${field}>`));
    const value = match ? Number(match[1]) : NaN;
    return [label, value];
  });
  if (curve.some(([, v]) => !Number.isFinite(v))) {
    throw new Error("Treasury feed: missing or non-numeric tenor field");
  }
  return curve;
}

async function fetchMonth(yyyymm: string): Promise<string> {
  const res = await fetch(feedUrl(yyyymm), {
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: 21600, tags: ["treasury-curve"] },
  });
  if (!res.ok) throw new Error(`Treasury feed: HTTP ${res.status}`);
  return res.text();
}

export async function fetchTreasuryCurve(tenors: string[] = EQUITY_TENORS): Promise<[string, number][]> {
  const now = new Date();
  const thisMonth = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}`;
  try {
    return parseTreasuryFeed(await fetchMonth(thisMonth), tenors);
  } catch {
    // Early in a month, this month's feed may have zero entries yet — fall back one month.
    const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const prevMonth = `${prev.getFullYear()}${String(prev.getMonth() + 1).padStart(2, "0")}`;
    return parseTreasuryFeed(await fetchMonth(prevMonth), tenors);
  }
}
