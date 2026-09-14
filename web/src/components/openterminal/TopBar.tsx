// Ported from OpenTerminal's web/components/TopBar.tsx. apiGet path prefixed
// to /api/openterminal/status. Also adds the one deliberate seam into this
// app: a "← Dashboard" control that calls this app's own useDashStore, since
// the normal dashboard-type switcher (Header/LeftRail) is hidden while
// OpenTerminal's full-takeover shell is active.
"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useDashStore } from "@/lib/store";
import { apiGet } from "@/lib/openterminal/api";
import { useOpenTerminal } from "@/store/openterminal";

type Status = {
  ok: boolean;
  providers: Array<{ name: string; ok: number; failed: number; lastLatencyMs: number | null }>;
  ai: boolean;
};

function Clock({ tz, label }: { tz: string; label: string }) {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);
  if (!now) return null;
  return (
    <span className="dim">
      {label}{" "}
      <span className="text-[var(--text)]">
        {now.toLocaleTimeString("en-GB", { timeZone: tz, hour12: false })}
      </span>
    </span>
  );
}

function marketStateNY(): { label: string; open: boolean } {
  const ny = new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
  const day = ny.getDay();
  const mins = ny.getHours() * 60 + ny.getMinutes();
  const open = day >= 1 && day <= 5 && mins >= 570 && mins < 960; // 09:30–16:00
  return { label: open ? "NYSE OPEN" : "NYSE CLOSED", open };
}

export default function TopBar() {
  const setCommandOpen = useOpenTerminal((s) => s.setCommandOpen);
  const activeSymbol = useOpenTerminal((s) => s.activeSymbol);
  const setDashboardType = useDashStore((s) => s.setDashboardType);
  const { data: status } = useQuery({
    queryKey: ["status"],
    queryFn: () => apiGet<Status>("/api/openterminal/status"),
    refetchInterval: 30_000,
  });

  const market = marketStateNY();
  const healthy = status?.providers.filter((p) => p.ok > 0) ?? [];

  return (
    <header className="flex items-center gap-4 px-3 h-8 bg-[var(--panel-2)] border-b border-[var(--border)] text-[11px] shrink-0">
      <button
        className="term-btn dim hover:text-[var(--amber)]"
        onClick={() => setDashboardType("macro")}
        title="Back to the main dashboard"
      >
        ← Dashboard
      </button>
      <span className="amber font-bold tracking-widest">OPENTERMINAL</span>
      <span className={market.open ? "up" : "down"}>● {market.label}</span>
      <Clock tz="America/New_York" label="NY" />
      <Clock tz="Europe/Rome" label="MIL" />
      <Clock tz="Europe/London" label="LDN" />
      <Clock tz="Asia/Tokyo" label="TYO" />
      <button
        className="term-btn flex-1 max-w-md text-left dim"
        onClick={() => setCommandOpen(true)}
      >
        {activeSymbol} — search symbol… <span className="float-right">⌘K</span>
      </button>
      <span className="dim ml-auto">
        feeds:{" "}
        {healthy.length > 0
          ? healthy.map((p) => `${p.name} ${p.lastLatencyMs ?? "—"}ms`).join(" · ")
          : "connecting…"}
      </span>
      <span className={status?.ai ? "up" : "dim"}>AI {status?.ai ? "●" : "○"}</span>
    </header>
  );
}
