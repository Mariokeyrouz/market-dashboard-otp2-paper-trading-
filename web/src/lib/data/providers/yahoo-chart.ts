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
}

interface YahooChartPayload {
  chart?: {
    result?: {
      meta?: { regularMarketPrice?: number; chartPreviousClose?: number; previousClose?: number };
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
  if (!meta || typeof meta.regularMarketPrice !== "number" || !Array.isArray(closesRaw)) {
    throw new Error("Yahoo chart payload: missing meta or closes");
  }
  const closes = closesRaw.filter((c): c is number => typeof c === "number");
  if (closes.length === 0) throw new Error("Yahoo chart payload: no valid closes");
  const previousClose = meta.chartPreviousClose ?? meta.previousClose ?? closes[closes.length - 2] ?? closes[closes.length - 1];
  return { regularMarketPrice: meta.regularMarketPrice, previousClose, closes };
}

export async function fetchYahooChart(symbol: string, range: string, interval: string): Promise<YahooChartSeries> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=${interval}`;
  const res = await fetch(url, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: 180, tags: [`yahoo-chart-${symbol}`] },
  });
  if (!res.ok) throw new Error(`Yahoo chart ${symbol}: HTTP ${res.status}`);
  return parseYahooChartPayload(await res.json());
}
