"use client";

import { useMemo, useSyncExternalStore } from "react";
import Header from "@/components/chrome/Header";
import LogicPanel from "@/components/chrome/LogicPanel";
import DashboardGrid from "@/components/dashboard/DashboardGrid";
import { DataContext } from "@/components/DataContext";
import { MONO } from "@/components/ui";
import { deriveAll } from "@/lib/derive";
import { useDashStore } from "@/lib/store";

export default function Page() {
  const region = useDashStore((s) => s.region);
  const derived = useMemo(() => deriveAll(region), [region]);

  // Render after hydration so persisted state (region/layout) never mismatches SSR.
  const ready = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  if (!ready) return <div style={{ minHeight: "100vh" }} />;

  return (
    <DataContext.Provider value={derived}>
      <div style={{ maxWidth: 1820, margin: "0 auto", padding: "10px 18px 16px" }}>
        <Header />
        <DashboardGrid />
        <footer
          style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 16,
            flexWrap: "wrap", marginTop: 14,
          }}
        >
          <span
            style={{
              fontFamily: MONO, fontSize: 11, color: "#A07B1D",
              border: "1px solid rgba(160,123,29,.4)", borderRadius: 6, padding: "5px 11px",
            }}
          >
            ✎ MOCK DATA — placeholder values, not live levels
          </span>
          <span style={{ fontSize: 11, color: "#B4A98F" }}>
            Opinionated, style-dependent classification · directional reads, no validated hit-rates · layout is yours — see the Logic tab
          </span>
        </footer>
      </div>
      <LogicPanel />
    </DataContext.Provider>
  );
}
