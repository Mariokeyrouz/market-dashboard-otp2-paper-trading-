import { fetchYahooSparkBatch } from "@/lib/data/providers/yahoo-spark-batch";
import type { QuoteRow } from "@/lib/data/types-terminal";

/**
 * Watchlist is user-editable client state with no server-side session to
 * read from, so it gets its own tiny route instead of a bucket inside
 * `build-terminal-data.ts` — the ticker list comes in on every request via
 * `?tickers=`, comma-separated. Never statically cached, same reasoning as
 * `api/terminal/route.ts`.
 */
export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const tickers = (searchParams.get("tickers") ?? "")
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);

  if (tickers.length === 0) {
    return Response.json({ quotes: [] }, { headers: { "Cache-Control": "no-store" } });
  }

  try {
    const { quotes } = await fetchYahooSparkBatch(tickers);
    const rows: QuoteRow[] = tickers
      .map((ticker) => {
        const q = quotes.get(ticker);
        if (!q) return null;
        return { name: q.name, ticker, price: q.price, chgPct: ((q.price - q.previousClose) / q.previousClose) * 100 };
      })
      .filter((r): r is QuoteRow => r !== null);
    return Response.json({ quotes: rows }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    // A ticker list with a typo'd/delisted symbol shouldn't 500 the whole
    // panel — an empty quote list just means every row falls back to "—".
    return Response.json({ quotes: [] }, { headers: { "Cache-Control": "no-store" } });
  }
}
