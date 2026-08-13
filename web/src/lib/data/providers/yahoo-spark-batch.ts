/**
 * Yahoo Finance's unofficial batched "spark" endpoint (`v7/finance/spark`).
 * Keyless, no signup — but caps at 20 symbols per request (confirmed by
 * hand: 21+ symbols returns HTTP 400 "Number of symbols needs to be less
 * than or equal to 20"). Used instead of `v7/finance/quote` /
 * `v10/finance/quoteSummary`, both of which now require a crumb/cookie
 * handshake ("Invalid Crumb" / "Unauthorized" when called plain) — those are
 * effectively a signup-adjacent auth step, which this project explicitly
 * ruled out. Only price + previous close are needed here (no market cap
 * available through any keyless endpoint — see concentration-weights.ts).
 */
import { chunk } from "../chunk";

const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36";
const FETCH_TIMEOUT_MS = 8000;
const BATCH_SIZE = 20;

export interface SparkQuote {
  price: number;
  previousClose: number;
  name: string;
}

interface YahooSparkPayload {
  spark?: {
    result?: {
      symbol?: string;
      response?: {
        meta?: {
          regularMarketPrice?: number;
          chartPreviousClose?: number;
          previousClose?: number;
          longName?: string;
          shortName?: string;
        };
      }[];
    }[];
    error?: unknown;
  };
}

/** Pure parse, no network — unit-testable against a captured fixture. */
export function parseYahooSparkPayload(json: unknown): Map<string, SparkQuote> {
  const payload = json as YahooSparkPayload;
  const out = new Map<string, SparkQuote>();
  for (const entry of payload.spark?.result ?? []) {
    const meta = entry.response?.[0]?.meta;
    if (!entry.symbol || !meta || typeof meta.regularMarketPrice !== "number") continue;
    const previousClose = meta.chartPreviousClose ?? meta.previousClose;
    if (typeof previousClose !== "number") continue;
    out.set(entry.symbol, {
      price: meta.regularMarketPrice,
      previousClose,
      name: meta.longName ?? meta.shortName ?? entry.symbol,
    });
  }
  return out;
}

async function fetchOneBatch(symbols: string[]): Promise<Map<string, SparkQuote>> {
  const url = `https://query1.finance.yahoo.com/v7/finance/spark?symbols=${symbols.map(encodeURIComponent).join(",")}&range=1d&interval=1d`;
  const res = await fetch(url, {
    headers: { "User-Agent": USER_AGENT },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    next: { revalidate: 180, tags: ["yahoo-spark"] },
  });
  if (!res.ok) throw new Error(`Yahoo spark batch: HTTP ${res.status}`);
  return parseYahooSparkPayload(await res.json());
}

/**
 * Fetches quotes for an arbitrary-length symbol list, chunked to respect the
 * 20-per-request cap, all chunks issued in parallel. Returns a map of
 * whatever resolved successfully plus the count of chunks that failed, so
 * callers can apply their own "trust the result only if enough came back"
 * threshold (see build-equity-data.ts's movers bucket).
 */
export async function fetchYahooSparkBatch(symbols: string[]): Promise<{ quotes: Map<string, SparkQuote>; failedChunks: number; totalChunks: number }> {
  const chunks = chunk(symbols, BATCH_SIZE);
  const settled = await Promise.allSettled(chunks.map(fetchOneBatch));
  const quotes = new Map<string, SparkQuote>();
  let failedChunks = 0;
  for (const result of settled) {
    if (result.status === "fulfilled") {
      for (const [symbol, quote] of result.value) quotes.set(symbol, quote);
    } else {
      failedChunks++;
    }
  }
  return { quotes, failedChunks, totalChunks: chunks.length };
}
