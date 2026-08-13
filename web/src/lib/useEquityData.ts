"use client";

import { useEffect, useRef, useState } from "react";
import { deriveEquity, deriveEquityFrom, type EquityDerived } from "./derive-equity";
import type { EquityFetchMeta } from "./data/build-equity-data";
import type { EquityCoreData } from "./data/types-equity";

export type EquityDataStatus = "bootstrap" | "live" | "partial" | "degraded";

export interface EquityDataState {
  /** Never null — bootstrap mock until the first live fetch resolves, then live/fallback data thereafter. */
  derived: EquityDerived;
  meta: EquityFetchMeta | null;
  status: EquityDataStatus;
}

const POLL_MS = 180_000; // matches the fastest server-side bucket revalidate window
const REFOCUS_MIN_GAP_MS = 60_000;

function statusFor(meta: EquityFetchMeta): EquityDataStatus {
  if (meta.degraded) return "degraded";
  if (Object.values(meta.stale).some(Boolean)) return "partial";
  return "live";
}

/** Fetches /api/equity while `enabled`, polling and refetching on focus/visibility regain. Never throws past this hook — a failed poll just keeps whatever was last displayed. */
export function useEquityData(enabled: boolean): EquityDataState {
  const [state, setState] = useState<EquityDataState>(() => ({
    derived: deriveEquity(),
    meta: null,
    status: "bootstrap",
  }));
  const lastFetchAt = useRef(0);
  const inFlight = useRef(false);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    async function poll() {
      if (inFlight.current) return;
      inFlight.current = true;
      try {
        const res = await fetch("/api/equity", { cache: "no-store" });
        if (!res.ok) return;
        const body = (await res.json()) as { data: EquityCoreData; meta: EquityFetchMeta };
        if (cancelled) return;
        lastFetchAt.current = Date.now();
        setState({ derived: deriveEquityFrom(body.data), meta: body.meta, status: statusFor(body.meta) });
      } catch {
        // Silent no-op — keep whatever was already displayed (bootstrap mock or last live snapshot).
      } finally {
        inFlight.current = false;
      }
    }

    poll();
    const interval = setInterval(poll, POLL_MS);

    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastFetchAt.current < REFOCUS_MIN_GAP_MS) return;
      poll();
    }
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);

    return () => {
      cancelled = true;
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [enabled]);

  return state;
}
