/**
 * Aggregates every live-data bucket into one TerminalCoreData, the same shape
 * `getTerminalData()` (the mock) returns — mirrors `build-equity-data.ts`'s
 * `settle()` + `Promise.all` + per-bucket-mock-fallback shape exactly.
 *
 * Five buckets (indices, vix, sectors, commods, movers) are the same live
 * fetches Equity already makes, just imported and reused verbatim — one
 * flaky upstream never blocks the others, and a failed bucket falls back to
 * the matching slice of the bundled mock rather than leaving a hole in the
 * tile. `events` isn't stale-tracked, matching Equity's own calendar bucket
 * (it's periodically-refreshed reference data, never meant to be live).
 */
import { fetchCommodsBucket, fetchIndicesBucket, fetchMoversBucket, fetchSectorsBucket, fetchVixBucket } from "./build-equity-data";
import { getTerminalData } from "./mock-terminal";
import { fetchYahooSparkBatch, type SparkQuote } from "./providers/yahoo-spark-batch";
import { CORP_CREDIT_ETFS, GOVT_CREDIT_ETFS } from "./reference/credit-etfs";
import { FX_PAIRS } from "./reference/fx-pairs";
import { GLOBAL_INDICES } from "./reference/global-indices";
import { buildCalendarBucket } from "./reference/macro-calendar";
import { STYLE_FACTOR_ETFS } from "./reference/style-factors";
import type { GroupedQuoteRow, QuoteRow, TerminalCoreData } from "./types-terminal";

export type StaleBucket = "indices" | "vix" | "sectors" | "commods" | "movers" | "fx" | "global" | "fixedIncome" | "factors";

export interface TerminalFetchMeta {
  fetchedAt: string;
  stale: Record<StaleBucket, boolean>;
  degraded: boolean;
}

type BucketResult<T> = { ok: true; value: T } | { ok: false };

async function settle<T>(fn: () => Promise<T>): Promise<BucketResult<T>> {
  try {
    return { ok: true, value: await fn() };
  } catch {
    return { ok: false };
  }
}

function toRow(name: string, ticker: string, q: SparkQuote | undefined): QuoteRow {
  if (!q) throw new Error(`terminal: missing quote for ${ticker}`);
  return { name, ticker, price: q.price, chgPct: ((q.price - q.previousClose) / q.previousClose) * 100 };
}

async function fetchFxBucket(): Promise<QuoteRow[]> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(FX_PAIRS.map((p) => p.ticker));
  if (failedChunks === totalChunks) throw new Error("fx: batch fetch failed");
  return FX_PAIRS.map((p) => toRow(p.name, p.ticker, quotes.get(p.ticker)));
}

async function fetchGlobalBucket(): Promise<GroupedQuoteRow[]> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(GLOBAL_INDICES.map((idx) => idx.ticker));
  if (failedChunks === totalChunks) throw new Error("global: batch fetch failed");
  return GLOBAL_INDICES.map((idx) => ({ ...toRow(idx.name, idx.ticker, quotes.get(idx.ticker)), group: idx.group }));
}

async function fetchFixedIncomeBucket(): Promise<TerminalCoreData["fixedIncome"]> {
  const tickers = [...GOVT_CREDIT_ETFS, ...CORP_CREDIT_ETFS].map((e) => e.ticker);
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(tickers);
  if (failedChunks === totalChunks) throw new Error("fixedIncome: batch fetch failed");
  return {
    govt: GOVT_CREDIT_ETFS.map((e) => toRow(e.name, e.ticker, quotes.get(e.ticker))),
    corp: CORP_CREDIT_ETFS.map((e) => toRow(e.name, e.ticker, quotes.get(e.ticker))),
  };
}

async function fetchFactorsBucket(): Promise<TerminalCoreData["factors"]> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(STYLE_FACTOR_ETFS.map((f) => f.ticker));
  if (failedChunks === totalChunks) throw new Error("factors: batch fetch failed");
  return STYLE_FACTOR_ETFS.map((f) => {
    const row = toRow(f.name, f.ticker, quotes.get(f.ticker));
    return { name: f.name, ticker: f.ticker, chgPct: row.chgPct };
  });
}

export async function buildTerminalData(): Promise<{ data: TerminalCoreData; meta: TerminalFetchMeta }> {
  const mock = getTerminalData();

  const [indices, vix, sectors, commods, movers, fx, global, fixedIncome, factors] = await Promise.all([
    settle(fetchIndicesBucket),
    settle(fetchVixBucket),
    settle(fetchSectorsBucket),
    settle(fetchCommodsBucket),
    settle(fetchMoversBucket),
    settle(fetchFxBucket),
    settle(fetchGlobalBucket),
    settle(fetchFixedIncomeBucket),
    settle(fetchFactorsBucket),
  ]);

  const stale: Record<StaleBucket, boolean> = {
    indices: !indices.ok,
    vix: !vix.ok,
    sectors: !sectors.ok,
    commods: !commods.ok,
    movers: !movers.ok,
    fx: !fx.ok,
    global: !global.ok,
    fixedIncome: !fixedIncome.ok,
    factors: !factors.ok,
  };

  const data: TerminalCoreData = {
    indices: indices.ok ? indices.value : mock.indices,
    vix: vix.ok ? vix.value : mock.vix,
    sectors: sectors.ok ? sectors.value : mock.sectors,
    commods: commods.ok ? commods.value : mock.commods,
    movers: movers.ok ? movers.value : mock.movers,
    fx: fx.ok ? fx.value : mock.fx,
    global: global.ok ? global.value : mock.global,
    fixedIncome: fixedIncome.ok ? fixedIncome.value : mock.fixedIncome,
    factors: factors.ok ? factors.value : mock.factors,
    events: buildCalendarBucket(new Date()),
  };

  return {
    data,
    meta: {
      fetchedAt: new Date().toISOString(),
      stale,
      degraded: Object.values(stale).every(Boolean),
    },
  };
}
