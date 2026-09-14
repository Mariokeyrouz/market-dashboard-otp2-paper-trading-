// Reimplemented from OpenTerminal's web/components/widgets/PortfolioWidget.tsx.
// The original hit a server route (server/src/routes/portfolio.ts) backed by
// SQLite; this calls the client-side @/lib/openterminal/portfolio module
// (localStorage) directly instead of apiGet/apiPost/apiDelete. Quotes still
// come from the live /api/openterminal/quotes route — only the
// portfolio/transaction bookkeeping itself moved client-side.
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiGet, fmt, pctClass, type Quote } from "@/lib/openterminal/api";
import {
  addTransaction,
  deleteTransaction,
  listPortfolios,
  listPositions,
  listTransactions,
  type Side,
} from "@/lib/openterminal/portfolio";

export default function PortfolioWidget() {
  const qc = useQueryClient();
  const [portfolioId, setPortfolioId] = useState<number | null>(null);
  const [showTx, setShowTx] = useState(false);
  const [form, setForm] = useState({ symbol: "", side: "BUY" as Side, quantity: "", price: "" });
  const [formError, setFormError] = useState<string | null>(null);

  const { data: portfolios = [] } = useQuery({
    queryKey: ["ot-portfolios"],
    queryFn: () => listPortfolios(),
  });
  const pid = portfolioId ?? portfolios[0]?.id;

  const { data: positions = [] } = useQuery({
    queryKey: ["ot-positions", pid],
    queryFn: () => listPositions(pid!),
    enabled: !!pid,
  });

  const { data: txs = [] } = useQuery({
    queryKey: ["ot-transactions", pid],
    queryFn: () => listTransactions(pid!),
    enabled: !!pid && showTx,
  });

  const symbols = positions.map((p) => p.symbol);
  const { data: quotes = [] } = useQuery({
    queryKey: ["pf-quotes", symbols.join(",")],
    queryFn: () => apiGet<Quote[]>(`/api/openterminal/quotes?symbols=${symbols.join(",")}`),
    enabled: symbols.length > 0,
    refetchInterval: 30_000,
  });

  const addTx = useMutation({
    mutationFn: async () =>
      addTransaction(pid!, {
        symbol: form.symbol,
        side: form.side,
        quantity: Number(form.quantity),
        price: Number(form.price),
        executed_at: new Date().toISOString(),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ot-positions", pid] });
      qc.invalidateQueries({ queryKey: ["ot-transactions", pid] });
      setForm({ symbol: "", side: "BUY", quantity: "", price: "" });
      setFormError(null);
    },
    onError: (err) => setFormError(err instanceof Error ? err.message : String(err)),
  });

  const totals = positions.reduce(
    (acc, p) => {
      const q = quotes.find((x) => x.symbol === p.symbol);
      const mv = (q?.price ?? p.avgCost) * p.quantity;
      acc.marketValue += mv;
      acc.cost += p.avgCost * p.quantity;
      acc.realized += p.realizedPnl;
      return acc;
    },
    { marketValue: 0, cost: 0, realized: 0 }
  );
  const unrealized = totals.marketValue - totals.cost;

  return (
    <div>
      <div className="flex gap-2 p-1 items-center flex-wrap">
        <select value={pid ?? ""} onChange={(e) => setPortfolioId(Number(e.target.value))}>
          {portfolios.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <button className={`term-btn ${showTx ? "active" : ""}`} onClick={() => setShowTx(!showTx)}>
          TRANSACTIONS
        </button>
        <span className="ml-auto">
          MV <span className="amber">{fmt(totals.marketValue)}</span>{" "}
          <span className="dim">Unrl</span> <span className={pctClass(unrealized)}>{fmt(unrealized)}</span>{" "}
          <span className="dim">Rlzd</span> <span className={pctClass(totals.realized)}>{fmt(totals.realized)}</span>
        </span>
      </div>

      <form
        className="flex gap-1 p-1 border-b border-[var(--border)]"
        onSubmit={(e) => {
          e.preventDefault();
          if (form.symbol && form.quantity && form.price) addTx.mutate();
        }}
      >
        <input className="w-20" placeholder="Ticker" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} />
        <select value={form.side} onChange={(e) => setForm({ ...form, side: e.target.value as Side })}>
          <option>BUY</option><option>SELL</option>
        </select>
        <input className="w-20" placeholder="Qty" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        <input className="w-24" placeholder="Price" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
        <button className="term-btn" type="submit">ADD</button>
        {formError && <span className="down">{formError}</span>}
      </form>

      {!showTx ? (
        <table className="data-table">
          <thead>
            <tr><th>Sym</th><th>Qty</th><th>Avg Cost</th><th>Last</th><th>Mkt Val</th><th>Unrl PnL</th><th>Rlzd PnL</th></tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const q = quotes.find((x) => x.symbol === p.symbol);
              const last = q?.price ?? null;
              const mv = last !== null ? last * p.quantity : null;
              const upnl = last !== null ? (last - p.avgCost) * p.quantity : null;
              return (
                <tr key={p.symbol}>
                  <td className="font-bold">{p.symbol}</td>
                  <td>{fmt(p.quantity, 4)}</td>
                  <td>{fmt(p.avgCost)}</td>
                  <td>{fmt(last)}</td>
                  <td>{fmt(mv)}</td>
                  <td className={pctClass(upnl)}>{fmt(upnl)}</td>
                  <td className={pctClass(p.realizedPnl)}>{fmt(p.realizedPnl)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Date</th><th>Sym</th><th>Side</th><th>Qty</th><th>Price</th><th></th></tr>
          </thead>
          <tbody>
            {txs.map((t) => (
              <tr key={t.id}>
                <td className="!text-left dim">{new Date(t.executed_at).toLocaleDateString()}</td>
                <td className="font-bold">{t.symbol}</td>
                <td className={t.side === "BUY" ? "up" : "down"}>{t.side}</td>
                <td>{fmt(t.quantity, 4)}</td>
                <td>{fmt(t.price)}</td>
                <td>
                  <button
                    className="dim hover:text-[var(--down)]"
                    onClick={() => {
                      deleteTransaction(pid!, t.id);
                      qc.invalidateQueries({ queryKey: ["ot-positions", pid] });
                      qc.invalidateQueries({ queryKey: ["ot-transactions", pid] });
                    }}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
