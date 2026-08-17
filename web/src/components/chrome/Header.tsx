"use client";

import { useState } from "react";
import { DASHBOARD_TYPES } from "@/lib/dashboards";
import { REGIONS, REGION_LABELS, type Region } from "@/lib/data/types";
import { AMBER, GREEN } from "@/lib/derive";
import { selectActiveSavedViewId, selectSavedViews, useDashStore } from "@/lib/store";
import { useClock } from "@/lib/useClock";
import { useDashboardDef } from "@/lib/useDashboardDef";
import { useDerived } from "../DataContext";
import { MONO, SERIF } from "../ui";
import DensityToggle from "./DensityToggle";
import ElementLibrary from "./ElementLibrary";
import ThemeToggle from "./ThemeToggle";

const selectStyle: React.CSSProperties = {
  fontFamily: "var(--font-plex-sans), sans-serif",
  fontSize: 13,
  fontWeight: 600,
  color: "var(--ink)",
  background: "var(--tile)",
  border: "1px solid var(--control-border)",
  borderRadius: 7,
  padding: "6px 30px 6px 12px",
  lineHeight: 1,
};

const btnStyle = (accent: string): React.CSSProperties => ({
  fontFamily: "var(--font-plex-sans), sans-serif",
  fontSize: 12.5,
  fontWeight: 600,
  color: accent,
  background: "var(--tile)",
  border: `1px solid ${accent}`,
  borderRadius: 7,
  padding: "7px 14px",
  cursor: "pointer",
});

export default function Header() {
  const v = useDerived();
  const { clock, open } = useClock();
  const dashDef = useDashboardDef();
  const dashboardType = useDashStore((s) => s.dashboardType);
  const setDashboardType = useDashStore((s) => s.setDashboardType);
  const region = useDashStore((s) => s.region);
  const setRegion = useDashStore((s) => s.setRegion);
  const edit = useDashStore((s) => s.editMode);
  const setEditMode = useDashStore((s) => s.setEditMode);
  const resetLayout = useDashStore((s) => s.resetLayout);
  const libraryOpen = useDashStore((s) => s.libraryOpen);
  const setLibraryOpen = useDashStore((s) => s.setLibraryOpen);
  const savedViews = useDashStore(selectSavedViews);
  const activeSavedViewId = useDashStore(selectActiveSavedViewId);
  const saveView = useDashStore((s) => s.saveView);
  const restoreView = useDashStore((s) => s.restoreView);
  const [savingView, setSavingView] = useState(false);
  const [newViewName, setNewViewName] = useState("");
  const mktColor = open ? "var(--green)" : "var(--red)";
  const flagged = v.tripwires.filter((t) => t.tone !== GREEN).length;
  const exchangeLabel = dashDef.hasRegionLens ? v.exchange : "NYSE · ET";

  const clockBox = (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 14, background: "var(--tile)",
        border: "1px solid var(--tile-border)", borderRadius: 10, padding: "9px 15px",
      }}
    >
      {dashDef.hasRegionLens && (
        <div
          style={{ display: "flex", alignItems: "center", gap: 5 }}
          title={`${flagged} tripwire${flagged === 1 ? "" : "s"} flagged · Regime: ${v.regime.label} (${v.regime.days}d, since ${v.regime.since})`}
        >
          <span
            style={{
              width: 7, height: 7, borderRadius: "50%",
              background: flagged > 0 ? AMBER : GREEN,
              animation: flagged > 0 ? "mp-pulse 2s ease-in-out infinite" : undefined,
            }}
          />
          <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, color: flagged > 0 ? AMBER : "var(--muted)" }}>
            {flagged}
          </span>
        </div>
      )}
      <div style={{ textAlign: "right" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: mktColor, animation: "mp-pulse 2s ease-in-out infinite" }} />
          <span style={{ fontSize: 10, letterSpacing: ".12em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
            {exchangeLabel}
          </span>
        </div>
        <div style={{ fontFamily: MONO, fontSize: 20, fontWeight: 500, letterSpacing: ".02em", marginTop: 2 }}>{clock}</div>
      </div>
      <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: mktColor, letterSpacing: ".06em" }}>
        {open ? "OPEN" : "CLOSED"}
      </div>
    </div>
  );

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, marginBottom: 7 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 40, height: 40, borderRadius: 9, background: "var(--ink)", color: "var(--canvas)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: SERIF, fontSize: 24, fontWeight: 600,
            }}
          >
            M
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{ position: "relative" }}>
                <select
                  className="mws-select"
                  aria-label="Dashboard type"
                  value={dashboardType}
                  onChange={(e) => setDashboardType(e.target.value as typeof dashboardType)}
                  style={{ ...selectStyle, fontFamily: SERIF, fontSize: 22, padding: "4px 30px 4px 4px" }}
                >
                  {DASHBOARD_TYPES.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <span
                style={{
                  fontFamily: MONO, fontSize: 11, padding: "3px 7px",
                  border: "1px solid var(--control-border)", borderRadius: 5, color: "var(--muted)",
                }}
              >
                OTP2.0
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 6, flexWrap: "wrap" }}>
              {dashDef.hasRegionLens && REGIONS.length > 1 && (
                <>
                  <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    Region
                  </span>
                  <div style={{ position: "relative" }}>
                    <select
                      className="mws-select"
                      value={region}
                      onChange={(e) => setRegion(e.target.value as Region)}
                      style={selectStyle}
                    >
                      {REGIONS.map((r) => (
                        <option key={r} value={r}>
                          {REGION_LABELS[r]}
                        </option>
                      ))}
                    </select>
                    <span style={{ position: "absolute", right: 11, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)", fontSize: 9 }}>
                      ▼
                    </span>
                  </div>
                </>
              )}
              {dashDef.hasRegionLens && REGIONS.length === 1 && (
                <>
                  <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                    Region
                  </span>
                  <span style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: "var(--gold)" }}>{REGIONS[0]}</span>
                </>
              )}
              <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Theme
              </span>
              <div style={{ width: 108 }}>
                <ThemeToggle />
              </div>
              <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Density
              </span>
              <div style={{ width: 168 }}>
                <DensityToggle />
              </div>
              <span style={{ fontSize: 10, letterSpacing: ".14em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
                Views
              </span>
              {savedViews.length > 0 && (
                <div style={{ position: "relative" }}>
                  <select
                    className="mws-select"
                    value={activeSavedViewId ?? ""}
                    onChange={(e) => e.target.value && restoreView(e.target.value)}
                    style={selectStyle}
                  >
                    <option value="" disabled>
                      Restore…
                    </option>
                    {savedViews.map((sv) => (
                      <option key={sv.id} value={sv.id}>
                        {sv.name}
                      </option>
                    ))}
                  </select>
                  <span style={{ position: "absolute", right: 11, top: "50%", transform: "translateY(-50%)", pointerEvents: "none", color: "var(--muted)", fontSize: 9 }}>
                    ▼
                  </span>
                </div>
              )}
              {savingView ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const trimmed = newViewName.trim();
                    if (trimmed) saveView(trimmed);
                    setNewViewName("");
                    setSavingView(false);
                  }}
                >
                  <input
                    autoFocus
                    value={newViewName}
                    onChange={(e) => setNewViewName(e.target.value)}
                    onBlur={() => { setSavingView(false); setNewViewName(""); }}
                    placeholder="View name…"
                    aria-label="New saved view name"
                    style={{ fontSize: 12.5, padding: "6px 9px", border: "1px solid var(--control-border)", borderRadius: 7, background: "var(--tile)", color: "var(--ink)", width: 130 }}
                  />
                </form>
              ) : (
                <button style={btnStyle("var(--gold)")} onClick={() => setSavingView(true)}>
                  + Save view
                </button>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {edit ? (
            <>
              <button style={btnStyle("var(--muted)")} onClick={resetLayout}>
                Reset layout
              </button>
              <button style={{ ...btnStyle("var(--green)"), background: "rgba(94,122,59,.1)" }} onClick={() => setEditMode(false)}>
                ✓ Done
              </button>
            </>
          ) : (
            <button style={btnStyle("var(--gold)")} onClick={() => setEditMode(true)}>
              ✎ Customize
            </button>
          )}
          <button
            style={{
              ...btnStyle(libraryOpen ? "var(--gold)" : "var(--muted)"),
              background: libraryOpen ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "var(--tile)",
            }}
            aria-expanded={libraryOpen}
            onClick={() => setLibraryOpen(!libraryOpen)}
          >
            ▦ Elements
          </button>
          {clockBox}
        </div>
      </div>
      {edit && <ElementLibrary />}
    </div>
  );
}
