/**
 * Aggregates every live-data bucket into one EquityCoreData, the same shape
 * `getEquityData()` (the mock) has always returned — so `deriveEquityFrom`
 * and every equity element component need no changes at all.
 *
 * Each bucket is independently fetched and independently allowed to fail:
 * `Promise.allSettled` means one flaky upstream never blocks the others, and
 * a failed bucket falls back to the matching slice of the bundled mock
 * (still a complete, correctly-shaped, just-not-live dataset) rather than
 * leaving a hole in the page. `meta.stale` records which buckets actually
 * fell back, and `page.tsx` turns that into the footer's status badge.
 *
 * Concentration and the calendar aren't fetched at all (see their reference
 * data files for why) — they're never "stale" because they were never meant
 * to be live in the first place, just periodically-refreshed reference data.
 */
import { getEquityData } from "./mock-equity";
import { fetchYahooChart } from "./providers/yahoo-chart";
import { fetchYahooSparkBatch } from "./providers/yahoo-spark-batch";
import { fetchTreasuryCurve } from "./providers/treasury-curve";
import { CONCENTRATION_WEIGHTS } from "./reference/concentration-weights";
import { SECTOR_ETFS } from "./reference/sector-etfs";
import { SP500_CONSTITUENTS } from "./reference/sp500-constituents";
import { buildCalendarBucket } from "./reference/macro-calendar";
import type { EquityCoreData, MoverRow, SectorRow } from "./types-equity";

export type StaleBucket = "indices" | "vix" | "curve" | "commods" | "sectors" | "movers";

export interface EquityFetchMeta {
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

const INDEX_TICKERS: { symbol: string; name: string; color: string }[] = [
  { symbol: "^GSPC", name: "S&P 500", color: "var(--ink)" },
  { symbol: "^NDX", name: "Nasdaq 100", color: "var(--gold)" },
  { symbol: "^DJI", name: "Dow Jones", color: "#3A6B9E" },
  { symbol: "^RUT", name: "Russell 2000", color: "var(--green)" },
];

async function fetchIndicesBucket(): Promise<EquityCoreData["indices"]> {
  const series = await Promise.all(
    INDEX_TICKERS.map(async (t) => {
      const s = await fetchYahooChart(t.symbol, "1y", "1d");
      return { name: t.name, color: t.color, prices: s.closes };
    }),
  );
  if (series.some((s) => s.prices.length < 30)) throw new Error("indices: too few points");
  return series;
}

async function fetchVixBucket(): Promise<EquityCoreData["vix"]> {
  const [vix, vix3m, vix9d] = await Promise.all([
    fetchYahooChart("^VIX", "3mo", "1d"),
    fetchYahooChart("^VIX3M", "5d", "1d"),
    fetchYahooChart("^VIX9D", "5d", "1d"),
  ]);
  if (vix.closes.length < 10) throw new Error("vix: too few points");
  return {
    spot: vix.regularMarketPrice,
    vix3m: vix3m.regularMarketPrice,
    vix9d: vix9d.regularMarketPrice,
    history: vix.closes.slice(-45),
  };
}

const COMMOD_TICKERS: [string, string][] = [
  ["CL=F", "WTI Crude"],
  ["BZ=F", "Brent"],
  ["GC=F", "Gold"],
  ["HG=F", "Copper"],
  ["NG=F", "Nat Gas"],
];

async function fetchCommodsBucket(): Promise<EquityCoreData["commods"]> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(COMMOD_TICKERS.map(([sym]) => sym));
  if (failedChunks === totalChunks) throw new Error("commods: batch fetch failed");
  const rows = COMMOD_TICKERS.map(([symbol, name]) => {
    const q = quotes.get(symbol);
    if (!q) throw new Error(`commods: missing ${symbol}`);
    const chgPct = ((q.price - q.previousClose) / q.previousClose) * 100;
    const priceStr = q.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return [name, priceStr, chgPct] as [string, string, number];
  });
  return rows;
}

async function fetchSectorsBucket(): Promise<SectorRow[]> {
  const rows = await Promise.all(
    SECTOR_ETFS.map(async ({ name, ticker }) => {
      const s = await fetchYahooChart(ticker, "3mo", "1d");
      const c = s.closes;
      if (c.length < 23) throw new Error(`sectors: ${ticker} too few points`);
      const last = c[c.length - 1];
      const pct = (from: number) => ((last - from) / from) * 100;
      return { name, chg1d: pct(c[c.length - 2]), chg1w: pct(c[c.length - 6]), chg1m: pct(c[c.length - 22]) };
    }),
  );
  return rows;
}

const MOVERS_MIN_SUCCESS_RATIO = 0.9;

async function fetchMoversBucket(): Promise<EquityCoreData["movers"]> {
  const { quotes, failedChunks, totalChunks } = await fetchYahooSparkBatch(SP500_CONSTITUENTS);
  if (failedChunks / totalChunks > 1 - MOVERS_MIN_SUCCESS_RATIO) {
    throw new Error(`movers: too many failed chunks (${failedChunks}/${totalChunks})`);
  }
  const ranked: (MoverRow & { chgRaw: number })[] = [];
  for (const [ticker, q] of quotes) {
    const chgRaw = ((q.price - q.previousClose) / q.previousClose) * 100;
    ranked.push({ ticker, name: q.name, price: q.price, chgPct: chgRaw, chgRaw });
  }
  ranked.sort((a, b) => b.chgRaw - a.chgRaw);
  const strip = (r: MoverRow & { chgRaw: number }): MoverRow => ({ ticker: r.ticker, name: r.name, price: r.price, chgPct: r.chgPct });
  return {
    gainers: ranked.slice(0, 5).map(strip),
    losers: ranked.slice(-5).reverse().map(strip),
  };
}

export async function buildEquityData(): Promise<{ data: EquityCoreData; meta: EquityFetchMeta }> {
  const mock = getEquityData();

  const [indices, vix, curve, commods, sectors, movers] = await Promise.all([
    settle(fetchIndicesBucket),
    settle(fetchVixBucket),
    settle(fetchTreasuryCurve),
    settle(fetchCommodsBucket),
    settle(fetchSectorsBucket),
    settle(fetchMoversBucket),
  ]);

  const stale: Record<StaleBucket, boolean> = {
    indices: !indices.ok,
    vix: !vix.ok,
    curve: !curve.ok,
    commods: !commods.ok,
    sectors: !sectors.ok,
    movers: !movers.ok,
  };

  const data: EquityCoreData = {
    indices: indices.ok ? indices.value : mock.indices,
    vix: vix.ok ? vix.value : mock.vix,
    curve: curve.ok ? curve.value : mock.curve,
    commods: commods.ok ? commods.value : mock.commods,
    concentration: CONCENTRATION_WEIGHTS,
    sectors: sectors.ok ? sectors.value : mock.sectors,
    movers: movers.ok ? movers.value : mock.movers,
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
