// Reimplements OpenTerminal's server/src/routes/portfolio.ts + server/src/db.ts
// as a client-side module backed by `localStorage` instead of a server-side
// SQLite database (see the plan's "Known deliberate deviations" — portfolio
// data is per-browser and won't sync across devices). The average-cost
// `positions` aggregation math in `listPositions()` below is copied verbatim
// from the original route; everything else (schema, single default "Main"
// portfolio) mirrors it as closely as a synchronous, no-network module can.
"use client";

import { z } from "zod";

const STORAGE_KEY = "openterminal-portfolio-v1";

export type Portfolio = { id: number; name: string };
export type Side = "BUY" | "SELL";
export type Transaction = {
  id: number;
  portfolioId: number;
  symbol: string;
  side: Side;
  quantity: number;
  price: number;
  executed_at: string;
};
export type Position = { symbol: string; quantity: number; avgCost: number; realizedPnl: number };

type Store = { portfolios: Portfolio[]; transactions: Transaction[]; nextId: number };

const DEFAULT_STORE = (): Store => ({ portfolios: [{ id: 1, name: "Main" }], transactions: [], nextId: 1 });

function load(): Store {
  if (typeof window === "undefined") return DEFAULT_STORE();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const fresh = DEFAULT_STORE();
      save(fresh);
      return fresh;
    }
    const parsed = JSON.parse(raw) as Store;
    if (!Array.isArray(parsed.portfolios) || parsed.portfolios.length === 0) {
      const fresh = DEFAULT_STORE();
      save(fresh);
      return fresh;
    }
    return parsed;
  } catch {
    const fresh = DEFAULT_STORE();
    save(fresh);
    return fresh;
  }
}

function save(store: Store): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function listPortfolios(): Portfolio[] {
  return load().portfolios;
}

export function listTransactions(portfolioId: number): Transaction[] {
  return load()
    .transactions.filter((t) => t.portfolioId === portfolioId)
    .sort((a, b) => b.executed_at.localeCompare(a.executed_at) || b.id - a.id);
}

// Same shape/validation as the original server's `txSchema` (zod).
const txSchema = z.object({
  symbol: z.string().min(1).max(12).transform((s) => s.toUpperCase()),
  side: z.enum(["BUY", "SELL"]),
  quantity: z.number().positive(),
  price: z.number().nonnegative(),
  executed_at: z.string(),
});

export function addTransaction(
  portfolioId: number,
  input: { symbol: string; side: Side; quantity: number; price: number; executed_at: string }
): Transaction {
  const parsed = txSchema.parse(input);
  const store = load();
  const tx: Transaction = { id: store.nextId, portfolioId, ...parsed };
  store.transactions.push(tx);
  store.nextId += 1;
  save(store);
  return tx;
}

export function deleteTransaction(portfolioId: number, txId: number): void {
  const store = load();
  store.transactions = store.transactions.filter((t) => !(t.id === txId && t.portfolioId === portfolioId));
  save(store);
}

/**
 * Aggregated positions with average cost and realized PnL (FIFO-free,
 * average-cost method). Copied verbatim from the original route's algorithm.
 */
export function listPositions(portfolioId: number): Position[] {
  const txs = load()
    .transactions.filter((t) => t.portfolioId === portfolioId)
    .sort((a, b) => a.executed_at.localeCompare(b.executed_at) || a.id - b.id);

  const positions = new Map<string, { qty: number; avgCost: number; realizedPnl: number }>();
  for (const tx of txs) {
    let p = positions.get(tx.symbol);
    if (!p) {
      p = { qty: 0, avgCost: 0, realizedPnl: 0 };
      positions.set(tx.symbol, p);
    }
    if (tx.side === "BUY") {
      const totalCost = p.avgCost * p.qty + tx.price * tx.quantity;
      p.qty += tx.quantity;
      p.avgCost = p.qty > 0 ? totalCost / p.qty : 0;
    } else {
      const sold = Math.min(tx.quantity, p.qty);
      p.realizedPnl += (tx.price - p.avgCost) * sold;
      p.qty -= sold;
      if (p.qty === 0) p.avgCost = 0;
    }
  }
  return [...positions.entries()]
    .filter(([, p]) => p.qty > 0 || p.realizedPnl !== 0)
    .map(([symbol, p]) => ({ symbol, quantity: p.qty, avgCost: p.avgCost, realizedPnl: p.realizedPnl }));
}
