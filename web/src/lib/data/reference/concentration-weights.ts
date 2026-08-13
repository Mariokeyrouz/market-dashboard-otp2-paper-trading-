/**
 * S&P 500 top-10 constituent weights, as static reference data.
 *
 * This is NOT live-fetched: computing a true float-adjusted index weight
 * live would require shares-outstanding for every constituent plus S&P's
 * proprietary divisor, none of which is free/keyless. Yahoo's keyless
 * endpoints (chart, spark) don't expose market cap either — every quote
 * endpoint that does (`v7/finance/quote`, `v10/finance/quoteSummary`) now
 * requires a crumb/cookie handshake, which we ruled out along with every
 * other signup-gated source. Index weights also move slowly day to day, so
 * a periodically-refreshed snapshot is a reasonable stand-in.
 *
 * Snapshot basis: NVDA/AAPL/MSFT weights corroborated by public reporting as
 * of 2026-03-30 (7.0% / 6.3% / 4.6%); the remaining rows are directionally
 * ordered estimates. Refresh from slickcharts.com/sp500 (or an equivalent
 * public index-weight source) periodically — this is the least "live" bucket
 * in the equity dashboard by nature, not by oversight.
 */
export const CONCENTRATION_WEIGHTS: { name: string; weightPct: number }[] = [
  { name: "NVDA", weightPct: 7.0 },
  { name: "AAPL", weightPct: 6.3 },
  { name: "MSFT", weightPct: 4.6 },
  { name: "AMZN", weightPct: 3.8 },
  { name: "META", weightPct: 2.7 },
  { name: "AVGO", weightPct: 2.5 },
  { name: "GOOGL", weightPct: 2.2 },
  { name: "GOOG", weightPct: 1.8 },
  { name: "TSLA", weightPct: 1.6 },
  { name: "BRK-B", weightPct: 1.5 },
];
