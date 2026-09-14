// Ported from OpenTerminal's web/components/widgets/WatchlistWidget.tsx.
// apiGet path prefixed to /api/openterminal/...
"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, fmt, fmtBig, pctClass, type Quote } from "@/lib/openterminal/api";
import { useOpenTerminal } from "@/store/openterminal";
import Flash from "@/components/openterminal/Flash";

export default function WatchlistWidget() {
  const watchlist = useOpenTerminal((s) => s.watchlist);
  const addToWatchlist = useOpenTerminal((s) => s.addToWatchlist);
  const removeFromWatchlist = useOpenTerminal((s) => s.removeFromWatchlist);
  const setActiveSymbol = useOpenTerminal((s) => s.setActiveSymbol);
  const [input, setInput] = useState("");

  const { data = [] } = useQuery({
    queryKey: ["watchlist", watchlist.join(",")],
    queryFn: () => apiGet<Quote[]>(`/api/openterminal/quotes?symbols=${watchlist.join(",")}`),
    enabled: watchlist.length > 0,
    refetchInterval: 1_000,
  });

  return (
    <div>
      <form
        className="flex gap-1 p-1"
        onSubmit={(e) => {
          e.preventDefault();
          if (input.trim()) {
            addToWatchlist(input.trim());
            setInput("");
          }
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Add ticker…"
          className="flex-1"
        />
        <button className="term-btn" type="submit">+</button>
      </form>
      <table className="data-table">
        <thead>
          <tr><th>Sym</th><th>Last</th><th>Chg%</th><th>Vol</th><th></th></tr>
        </thead>
        <tbody>
          {watchlist.map((sym) => {
            const q = data.find((d) => d.symbol === sym);
            return (
              <tr key={sym} onClick={() => setActiveSymbol(sym)}>
                <td className="font-bold">{sym}</td>
                <td><Flash value={q?.price}>{fmt(q?.price)}</Flash></td>
                <td className={pctClass(q?.changePercent)}>
                  <Flash value={q?.changePercent}>{fmt(q?.changePercent)}%</Flash>
                </td>
                <td>{fmtBig(q?.volume)}</td>
                <td>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFromWatchlist(sym);
                    }}
                    className="dim hover:text-[var(--down)]"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
