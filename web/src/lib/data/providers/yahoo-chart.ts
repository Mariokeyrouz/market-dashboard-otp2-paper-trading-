/**
 * Yahoo Finance's unofficial chart endpoint (`v8/finance/chart`). Keyless,
 * no signup, confirmed working (verified by hand against ^GSPC, AAPL, GC=F
 * during planning) — but unofficial and undocumented, so every call here is
 * timeout-bounded and shape-validated by the caller. A browser-like
 * User-Agent avoids the default Node/undici UA getting rejected.
 */

const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const FETCH_TIMEOUT_MS = 8000;

export interface YahooChartSeries {
  /** Current/most-recent price straight from the quote meta block (freshest single value). */
  regularMarketPrice: number;
  /** Previous session's close, for a same-shape 1-day change calc. */
  previousClose: number;
  /** Daily closes, chronological, most-recent-last, nulls (non-trading gaps) dropped. */
  closes: number[];
  /** Unix seconds, 1:1 aligned with `closes` (same rows dropped) — lets callers find "the close nearest a given calendar date" (e.g. YTD). */
  timestamps: number[];
}

interface YahooChartPayload {
  chart?: {
    result?: {
      meta?: { regularMarketPrice?: number; chartPreviousClose?: number; previousClose?: number };
      timestamp?: number[];
      indicators?: { quote?: { close?: (number | null)[] }[] };
    }[];
    error?: unknown;
  };
}

/** Pure parse, no network — unit-testable against a captured fixture. */
export function parseYahooChartPayload(json: unknown): YahooChartSeries {
  const payload = json as YahooChartPayload;
  const result = payload.chart?.result?.[0];
  if (!result) throw new Error("Yahoo chart payload: no result");
  const meta = result.meta;
  const closesRaw = result.indicators?.quote?.[0]?.close;
  const timestampsRaw = result.timestamp;
  if (!meta || typeof meta.regularMarketPrice !== "number" || !Array.isArray(closesRaw)) {
    throw new Error("Yahoo chart payload: missing meta or closes");
  }
  const closes: number[] = [];
  const timestamps: number[] = [];
  closesRaw.forEach((c, i) => {
    if (typeof c === "number") {
      closes.push(c);
      timestamps.push(timestampsRaw?.[i] ?? NaN);
    }
  });
  if (closes.length === 0) throw new Error("Yahoo chart payload: no valid closes");
  const previousClose = meta.chartPreviousClose ?? meta.previousClose ?? closes[closes.length - 2] ?? closes[closes.length - 1];
  return { regularMarketPrice: meta.regularMarketPrice, previousClose, closes, timestamps };
}

export async function fetchYahooChart(symbol: string, range: string, interval: string, revalidateSeconds = 180): Promise<YahooChartSeries> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`;
  const res = await fetch(url, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: revalidateSeconds, tags: [`yahoo-chart-${symbol}`] },
  });
  if (!res.ok) throw new Error(`Yahoo chart ${symbol}: HTTP ${res.status}`);
  return parseYahooChartPayload(await res.json());
}

/** Index of the closes/timestamps entry nearest the start of `year` (first trading day on/after Jan 1) — for YTD-style change calcs. */
export function indexNearYearStart(timestamps: number[], year: number): number {
  const jan1 = Date.UTC(year, 0, 1) / 1000;
  const idx = timestamps.findIndex((t) => t >= jan1);
  return idx === -1 ? 0 : idx;
}
