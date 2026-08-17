"use client";

import { useEffect, useRef, useState } from "react";
import { deriveAll, deriveAllFrom, type Derived } from "./derive";
import type { MacroFetchMeta } from "./data/build-macro-data";
import type { CoreData, ExtraData } from "./data/types";

export type MacroDataStatus = "bootstrap" | "live" | "partial" | "degraded";

export interface MacroDataState {
  /** Never null — bootstrap mock until the first live fetch resolves, then live/fallback data thereafter. */
  derived: Derived;
  meta: MacroFetchMeta | null;
  status: MacroDataStatus;
}

const POLL_MS = 180_000;
const REFOCUS_MIN_GAP_MS = 60_000;

function statusFor(meta: MacroFetchMeta): MacroDataStatus {
  if (meta.degraded) return "degraded";
  if (Object.values(meta.stale).some(Boolean)) return "partial";
  return "live";
}

export function useMacroData(enabled = true): MacroDataState {
  const [state, setState] = useState<MacroDataState>(() => ({
    derived: deriveAll("US"),
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
        const res = await fetch("/api/macro", { cache: "no-store" });
        if (!res.ok) return;
        const body = (await res.json()) as { data: CoreData & ExtraData; meta: MacroFetchMeta };
        if (cancelled) return;
        lastFetchAt.current = Date.now();
        setState({ derived: deriveAllFrom("US", body.data), meta: body.meta, status: statusFor(body.meta) });
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
