"use client";

import { useEffect, useRef, useState } from "react";
import { fmtQuote, type TerminalRowFmt } from "./derive-terminal";
import type { QuoteRow } from "./data/types-terminal";

const POLL_MS = 180_000; // same cadence as the main /api/terminal poll

/**
 * Fetches `/api/terminal/watchlist` for the given ticker list — decoupled
 * from the 180s main poll's request, because the ticker list is user-editable
 * client state with no server-side session to read. Polls on the same 180s
 * cadence, but also refetches immediately whenever the ticker list itself
 * changes (add/remove shouldn't wait up to 3 minutes to show a quote).
 */
export function useWatchlistQuotes(tickers: string[], enabled: boolean): { rows: TerminalRowFmt[]; loading: boolean } {
  const [rows, setRows] = useState<TerminalRowFmt[]>([]);
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  // Stable key so the effect only re-runs when the actual ticker set changes,
  // not on every render that happens to pass a new array identity.
  const key = tickers.join(",");
  const active = enabled && tickers.length > 0;
  // Derived rather than reset via a synchronous setState-in-effect (React
  // flags that as a cascading-render anti-pattern): filtering out any row
  // whose ticker isn't in the current list makes a removed ticker disappear
  // immediately, without waiting for the next poll to overwrite `rows`.
  const tickerSet = new Set(tickers);
  const visibleRows = active ? rows.filter((r) => r.ticker && tickerSet.has(r.ticker)) : [];

  useEffect(() => {
    if (!active) return;

    let cancelled = false;

    async function poll() {
      if (inFlight.current) return;
      inFlight.current = true;
      setLoading(true);
      try {
        const res = await fetch(`/api/terminal/watchlist?tickers=${encodeURIComponent(tickers.join(","))}`, { cache: "no-store" });
        if (!res.ok) return;
        const body = (await res.json()) as { quotes: QuoteRow[] };
        if (cancelled) return;
        setRows(body.quotes.map((q) => fmtQuote(q, 2)));
      } catch {
        // Silent no-op — keep whatever was already displayed.
      } finally {
        inFlight.current = false;
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` is the intentional dependency; `tickers` itself is a new array identity on every render.
  }, [active, key]);

  return { rows: visibleRows, loading };
}
