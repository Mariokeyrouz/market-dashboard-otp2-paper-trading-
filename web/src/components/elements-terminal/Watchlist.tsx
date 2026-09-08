"use client";

import { useState } from "react";
import { useDashStore } from "@/lib/store";
import { useWatchlistQuotes } from "@/lib/useWatchlistQuotes";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TableHeadRow, TILE } from "../ui";

const WATCHLIST_COLS = "1fr 56px 56px 20px";

export default function Watchlist() {
  const watchlist = useDashStore((s) => s.watchlist);
  const addWatchlistTicker = useDashStore((s) => s.addWatchlistTicker);
  const removeWatchlistTicker = useDashStore((s) => s.removeWatchlistTicker);
  const compact = useCompact();
  const [input, setInput] = useState("");
  const { rows } = useWatchlistQuotes(watchlist, true);

  const submit = () => {
    const t = input.trim().toUpperCase();
    if (t) addWatchlistTicker(t);
    setInput("");
  };

  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>My Watchlist</PanelTitle>
        {!compact && <ItalicNote>{watchlist.length} tickers</ItalicNote>}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        style={{ display: "flex", gap: 6, marginBottom: compact ? 5 : 8 }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker…"
          aria-label="Add ticker to watchlist"
          style={{
            flex: 1, minWidth: 0, fontFamily: MONO, fontSize: 11.5, padding: "4px 8px", borderRadius: 6,
            border: "1px solid var(--control-border)", background: "var(--tile)", color: "var(--ink)",
          }}
        />
        <button
          type="submit"
          style={{
            fontFamily: MONO, fontSize: 10.5, fontWeight: 700, padding: "4px 10px", borderRadius: 6, cursor: "pointer",
            color: "var(--gold)", background: "color-mix(in srgb, var(--gold) 13%, transparent)",
            border: "1px solid color-mix(in srgb, var(--gold) 45%, transparent)",
          }}
        >
          Add
        </button>
      </form>
      <TableHeadRow labels={["Ticker", "Last", "Chg %"]} columns={WATCHLIST_COLS} />
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 5 : 8, flex: 1, minHeight: 0, overflow: "auto" }}>
        {watchlist.map((ticker) => {
          const q = rows.find((r) => r.ticker === ticker);
          return (
            <div key={ticker} style={{ display: "grid", gridTemplateColumns: WATCHLIST_COLS, gap: 8, alignItems: "center" }}>
              <span style={{ fontFamily: MONO, fontSize: compact ? 11 : 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {ticker}
              </span>
              <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: "var(--muted)" }}>{q?.price ?? "—"}</span>
              <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: q?.chgColor ?? "var(--muted)" }}>{q?.chgPct ?? "—"}</span>
              <button
                aria-label={`Remove ${ticker} from watchlist`}
                onClick={() => removeWatchlistTicker(ticker)}
                style={{
                  width: 18, height: 18, display: "flex", alignItems: "center", justifyContent: "center",
                  background: "transparent", border: "none", color: "var(--red)", fontSize: 13, lineHeight: 1, cursor: "pointer",
                }}
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
