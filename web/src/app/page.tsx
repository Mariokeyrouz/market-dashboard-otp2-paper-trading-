"use client";

import { useEffect, useMemo, useSyncExternalStore } from "react";
import Header from "@/components/chrome/Header";
import LeftRail from "@/components/chrome/LeftRail";
import LogicPanel from "@/components/chrome/LogicPanel";
import RightRail from "@/components/chrome/RightRail";
import DashboardGrid from "@/components/dashboard/DashboardGrid";
import { DataContext } from "@/components/DataContext";
import { MONO } from "@/components/ui";
import { deriveAll } from "@/lib/derive";
import { useDashStore } from "@/lib/store";
import { useShellMode } from "@/lib/useShellMode";

export default function Page() {
  const region = useDashStore((s) => s.region);
  const theme = useDashStore((s) => s.theme);
  const dockOpen = useDashStore((s) => s.dockOpen);
  const setDockOpen = useDashStore((s) => s.setDockOpen);
  const railCollapsed = useDashStore((s) => s.railCollapsed);
  const setRailCollapsed = useDashStore((s) => s.setRailCollapsed);
  const derived = useMemo(() => deriveAll(region), [region]);
  const mode = useShellMode();

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

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
    <DataContext.Provider value={derived}>
      {/* Rails + centred grid. The grid keeps its 1820 cap because the
          Z-pattern depends on a scannable sweep width — the reclaimed margin
          becomes standing chrome, not wider tiles. */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "8px 14px 14px" }}>
        {rails && (
          <LeftRail
            collapsed={collapsed}
            onToggleCollapse={mode === "wide" ? () => setRailCollapsed(!railCollapsed) : undefined}
          />
        )}
        <div style={{ flex: 1, minWidth: 0, maxWidth: 1820, margin: "0 auto" }}>
          {/* In wide/mid the rail owns brand + controls + clock, so there is no
              header band — the grid starts at the top. Narrow keeps the header. */}
          {!rails && <Header />}
          <DashboardGrid />
          <footer
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 16,
              flexWrap: "wrap", marginTop: 10,
            }}
          >
            <span
              style={{
                fontFamily: MONO, fontSize: 11, color: "var(--gold)",
                border: "1px solid rgba(160,123,29,.4)", borderRadius: 6, padding: "5px 11px",
              }}
            >
              ✎ MOCK DATA — placeholder values, not live levels
            </span>
            <span style={{ fontSize: 11, color: "var(--faint)" }}>
              Opinionated, style-dependent classification · directional reads, no validated hit-rates · layout is yours — see the Logic panel
            </span>
          </footer>
        </div>
        {docked && <RightRail open={dockOpen} onToggle={setDockOpen} />}
      </div>
      {/* Only one Logic surface at a time: docked when it fits, else the tab. */}
      {!docked && <LogicPanel />}
    </DataContext.Provider>
  );
}
