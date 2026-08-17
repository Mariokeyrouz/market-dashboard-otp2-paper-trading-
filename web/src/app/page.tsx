"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import ElementLibraryDock from "@/components/chrome/ElementLibraryDock";
import ElementLibraryPanel from "@/components/chrome/ElementLibraryPanel";
import Header from "@/components/chrome/Header";
import LeftRail from "@/components/chrome/LeftRail";
import LogicPanel from "@/components/chrome/LogicPanel";
import RightRail from "@/components/chrome/RightRail";
import DashboardGrid from "@/components/dashboard/DashboardGrid";
import { DataContext } from "@/components/DataContext";
import { MONO } from "@/components/ui";
import { AMBER, GREEN } from "@/lib/derive";
import { useDashStore } from "@/lib/store";
import { useDashboardDef } from "@/lib/useDashboardDef";
import { useEquityData } from "@/lib/useEquityData";
import { useMacroData } from "@/lib/useMacroData";
import { useShellMode } from "@/lib/useShellMode";

function timeAgoLabel(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins === 1) return "1m ago";
  return `${mins}m ago`;
}

/** Shared LIVE/PARTIAL/DEGRADED footer badge — same status shape for both the Equity and Macro live-data hooks. */
function LiveStatusBadge({
  status, fetchedAt, staleBuckets,
}: {
  status: "bootstrap" | "live" | "partial" | "degraded";
  fetchedAt?: string;
  staleBuckets?: Record<string, boolean>;
}) {
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  if (status === "bootstrap") return null; // near-instant; avoid an alarming flash before the first fetch resolves

  const color = status === "live" ? GREEN : AMBER;
  const label =
    status === "live"
      ? `● LIVE — updated ${timeAgoLabel(fetchedAt!)}`
      : status === "partial"
        ? `⚠ PARTIAL LIVE DATA — fallback for: ${Object.entries(staleBuckets ?? {}).filter(([, s]) => s).map(([b]) => b).join(", ")}`
        : "⚠ LIVE DATA UNAVAILABLE — showing reference values";

  return (
    <span
      style={{
        fontFamily: MONO, fontSize: 11, color,
        border: `1px solid ${color}`, borderRadius: 6, padding: "5px 11px", opacity: 0.85,
      }}
    >
      {label}
    </span>
  );
}

export default function Page() {
  const theme = useDashStore((s) => s.theme);
  const dockOpen = useDashStore((s) => s.dockOpen);
  const setDockOpen = useDashStore((s) => s.setDockOpen);
  const railCollapsed = useDashStore((s) => s.railCollapsed);
  const setRailCollapsed = useDashStore((s) => s.setRailCollapsed);
  const mode = useShellMode();
  const dashDef = useDashboardDef();
  const isEquity = dashDef.id === "equity";
  const equity = useEquityData(isEquity);
  // Not gated by the active tab — LeftRail/Header read the outer DataContext
  // (macro.derived, below) unconditionally for chrome like the tripwire-flag
  // count, regardless of which dashboard is on screen.
  const macro = useMacroData();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    document.title = dashDef.label;
  }, [dashDef]);

  // Render after hydration so persisted state (region/layout) never mismatches SSR.
  const ready = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  if (!ready) return <div style={{ minHeight: "100vh" }} />;

  const rails = mode !== "narrow";
  const docked = mode === "wide";
  // The rail auto-collapses in `mid` (it's forced, not a choice); in `wide`
  // it respects the user's manual override instead.
  const collapsed = mode === "mid" || railCollapsed;

  return (
    <DataContext.Provider value={macro.derived}>
      {/* Rails + centred grid. The grid keeps its 1820 cap because the
          Z-pattern depends on a scannable sweep width — the reclaimed margin
          becomes standing chrome, not wider tiles. */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 14px 14px" }}>
        {rails && (
          <LeftRail
            collapsed={collapsed}
            onToggleCollapse={mode === "wide" ? () => setRailCollapsed(!railCollapsed) : undefined}
            libraryDocked={docked}
          />
        )}
        {docked && <ElementLibraryDock />}
        <div style={{ flex: 1, minWidth: 0, maxWidth: 1820, margin: "0 auto" }}>
          {/* In wide/mid the rail owns brand + controls + clock, so there is no
              header band — the grid starts at the top. Narrow keeps the header. */}
          {!rails && <Header />}
          <DashboardGrid equityData={isEquity ? equity.derived : null} macroData={!isEquity ? macro.derived : null} />
          <footer
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 16,
              flexWrap: "wrap", marginTop: 10,
            }}
          >
            {isEquity ? (
              <LiveStatusBadge status={equity.status} fetchedAt={equity.meta?.fetchedAt} staleBuckets={equity.meta?.stale} />
            ) : (
              <LiveStatusBadge status={macro.status} fetchedAt={macro.meta?.fetchedAt} staleBuckets={macro.meta?.stale} />
            )}
            <span style={{ fontSize: 11, color: "var(--faint)" }}>
              Opinionated, style-dependent classification · directional reads, no validated hit-rates · layout is yours — see the Logic panel
            </span>
          </footer>
        </div>
        {docked && <RightRail open={dockOpen} onToggle={setDockOpen} />}
      </div>
      {/* Only one Logic surface at a time: docked when it fits, else the tab. */}
      {!docked && <LogicPanel />}
      {/* Element Library drawer — its trigger lives in LeftRail (mid) or
          Header (narrow); this just renders the backdrop + panel. */}
      {!docked && <ElementLibraryPanel />}
    </DataContext.Provider>
  );
}
