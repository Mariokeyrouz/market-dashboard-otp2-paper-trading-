"use client";

import { useState } from "react";
import { DASHBOARD_TYPES } from "@/lib/dashboards";
import { REGION_LABELS, REGIONS } from "@/lib/data/types";
import { AMBER, GREEN } from "@/lib/derive";
import { selectActiveSavedViewId, selectHidden, selectSavedViews, useDashStore } from "@/lib/store";
import { useClock } from "@/lib/useClock";
import { useDashboardDef } from "@/lib/useDashboardDef";
import { RAIL_W, RAIL_W_COLLAPSED } from "@/lib/useShellMode";
import { useDerived } from "../DataContext";
import { MICRO, MONO, SERIF } from "../ui";
import DensityToggle from "./DensityToggle";
import HiddenElementButtons from "./HiddenElementButtons";
import ThemeToggle from "./ThemeToggle";

const divider = { height: 1, background: "var(--hairline)", margin: "7px 0 5px" };

/**
 * Persistent left rail: brand, the POV switcher, appearance, and the
 * customize controls, grouped into labeled sections.
 *
 * The region lens was a header dropdown, which hid the alternatives behind a
 * click. As a rail it becomes a list you can see and compare against — the
 * available points of view are the product's spine, so they get standing
 * chrome rather than a collapsed control.
 */
export default function LeftRail({
  collapsed,
  onToggleCollapse,
  libraryDocked,
}: {
  collapsed: boolean;
  /** Manual collapse override, available only in `wide` mode. Undefined in
   *  `mid`, where the rail is force-collapsed and a toggle would be a no-op. */
  onToggleCollapse?: () => void;
  /** `wide`: the Element Library button opens the left dock. `mid`: it opens
   *  the overlay drawer instead (the dock doesn't fit). */
  libraryDocked: boolean;
}) {
  const dashDef = useDashboardDef();
  const dashboardType = useDashStore((s) => s.dashboardType);
  const setDashboardType = useDashStore((s) => s.setDashboardType);
  const region = useDashStore((s) => s.region);
  const setRegion = useDashStore((s) => s.setRegion);
  const edit = useDashStore((s) => s.editMode);
  const setEditMode = useDashStore((s) => s.setEditMode);
  const resetLayout = useDashStore((s) => s.resetLayout);
  const hidden = useDashStore(selectHidden);
  const libraryDockOpen = useDashStore((s) => s.libraryDockOpen);
  const setLibraryDockOpen = useDashStore((s) => s.setLibraryDockOpen);
  const libraryOpen = useDashStore((s) => s.libraryOpen);
  const setLibraryOpen = useDashStore((s) => s.setLibraryOpen);
  const savedViews = useDashStore(selectSavedViews);
  const activeSavedViewId = useDashStore(selectActiveSavedViewId);
  const saveView = useDashStore((s) => s.saveView);
  const restoreView = useDashStore((s) => s.restoreView);
  const deleteView = useDashStore((s) => s.deleteView);
  const [savingView, setSavingView] = useState(false);
  const [newViewName, setNewViewName] = useState("");
  const { clock, open } = useClock();
  const v = useDerived();
  const mktColor = open ? "var(--green)" : "var(--red)";
  const flagged = v.tripwires.filter((t) => t.tone !== GREEN).length;
  // The region-scoped exchange label only means something on a dashboard
  // with a region lens — a stale "Euronext" while Equity (US-only) is
  // active would be actively misleading.
  const exchangeLabel = dashDef.hasRegionLens ? v.exchange : "NYSE · ET";

  return (
    <aside
      aria-label="Point of view and layout controls"
      style={{
        alignSelf: "stretch",
        width: collapsed ? RAIL_W_COLLAPSED : RAIL_W, flexShrink: 0,
        overflowY: "auto",
        display: "flex", flexDirection: "column", gap: 5,
        background: "var(--tile)", border: "1px solid var(--tile-border)",
        borderRadius: 10, padding: collapsed ? "9px 7px" : "10px 10px 12px",
      }}
    >
      <div style={{ position: "sticky", top: 8, display: "flex", flexDirection: "column", gap: 5 }}>
        {/* Brand */}
        <div
          style={{
            display: "flex",
            flexDirection: collapsed ? "column" : "row",
            alignItems: collapsed ? "center" : "flex-start",
            justifyContent: collapsed ? "flex-start" : "space-between",
            gap: collapsed ? 6 : 8,
          }}
        >
          <div
            style={{
              width: 32, height: 32, borderRadius: 8, background: "var(--ink)", color: "var(--canvas)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: SERIF, fontSize: 18, fontWeight: 600, flexShrink: 0,
            }}
          >
            M
          </div>
          {!collapsed && (
            <span
              style={{
                display: "inline-block",
                fontFamily: MONO, fontSize: 10, padding: "2px 6px",
                border: "1px solid var(--control-border)", borderRadius: 5, color: "var(--muted)",
              }}
            >
              OTP2.0
            </span>
          )}
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              aria-label={collapsed ? "Expand the rail" : "Collapse the rail"}
              title={collapsed ? "Expand" : "Collapse"}
              style={{
                flexShrink: 0, cursor: "pointer", fontSize: 12, fontWeight: 700,
                color: "var(--muted)", background: "transparent",
                border: "1px solid var(--control-border)", borderRadius: 6,
                width: collapsed ? "100%" : 22, height: 22,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              {collapsed ? "»" : "«"}
            </button>
          )}
        </div>

        {!collapsed && (
          <>
            <div style={divider} />
            <div style={{ ...MICRO, marginBottom: 2 }}>Dashboard</div>
            <div
              role="tablist"
              aria-label="Dashboard type"
              style={{
                display: "flex", flexDirection: "column", gap: 2,
                border: "1px solid var(--control-border)", borderRadius: 8, padding: 3,
              }}
            >
              {DASHBOARD_TYPES.map((d) => {
                const active = d.id === dashboardType;
                return (
                  <button
                    key={d.id}
                    role="tab"
                    aria-selected={active}
                    onClick={() => setDashboardType(d.id)}
                    style={{
                      display: "flex", alignItems: "center", gap: 8,
                      width: "100%", textAlign: "left", cursor: "pointer",
                      border: "1px solid transparent", borderRadius: 6, padding: "7px 9px",
                      background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: active ? "var(--gold)" : "var(--control-border)", flexShrink: 0 }} />
                    <span style={{ fontFamily: SERIF, fontSize: 14, fontWeight: 600, color: active ? "var(--ink)" : "var(--muted)" }}>
                      {d.shortLabel}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}

        {dashDef.hasRegionLens && REGIONS.length > 1 && (
          <>
            <div style={divider} />

            {/* Point of view */}
            {!collapsed && <div style={{ ...MICRO, marginBottom: 2 }}>Point of view</div>}

            {REGIONS.map((r) => {
              const active = r === region;
              return (
                <button
                  key={r}
                  onClick={() => setRegion(r)}
                  aria-current={active}
                  // Collapsed, the only visible text is the "US"/"EU" code, so the
                  // full name has to come from the label rather than the content.
                  aria-label={`Set the region lens to ${REGION_LABELS[r]}`}
                  title={collapsed ? REGION_LABELS[r] : undefined}
                  style={{
                    display: "flex", alignItems: "center", gap: 8,
                    justifyContent: collapsed ? "center" : "flex-start",
                    width: "100%", textAlign: "left", cursor: "pointer",
                    background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
                    border: "1px solid transparent",
                    boxShadow: active ? "inset 3px 0 0 var(--gold)" : undefined,
                    borderRadius: 7, padding: collapsed ? "6px 0" : "6px 8px",
                    color: active ? "var(--ink)" : "var(--body)",
                  }}
                >
                  <span style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: active ? "var(--gold)" : "var(--faint)" }}>
                    {r}
                  </span>
                  {!collapsed && (
                    <span style={{ fontSize: 12.5, fontWeight: active ? 600 : 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {REGION_LABELS[r]}
                    </span>
                  )}
                </button>
              );
            })}
          </>
        )}
        {dashDef.hasRegionLens && REGIONS.length === 1 && !collapsed && (
          <>
            <div style={divider} />
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={MICRO}>Point of view</div>
              <span style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: "var(--gold)" }}>{REGIONS[0]}</span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>EU · CN · JP awaiting a live source</div>
          </>
        )}
      </div>

      {/* Market clock + session status — relocated from the old header band.
          Content is top-aligned (empty space falls at the bottom, matching the
          right rail) rather than bottom-anchored, which stranded a big mid-rail gap. */}
      <div
        style={{
          display: "flex", alignItems: "center",
          justifyContent: collapsed ? "center" : "flex-start",
          gap: 8, padding: collapsed ? "6px 0" : "8px 4px",
          borderTop: "1px solid var(--hairline)", borderBottom: "1px solid var(--hairline)",
        }}
        title={`${exchangeLabel} · ${open ? "OPEN" : "CLOSED"}`}
      >
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: mktColor, animation: "mp-pulse 2s ease-in-out infinite", flexShrink: 0 }} />
        {collapsed ? (
          <span style={{ fontFamily: MONO, fontSize: 8.5, fontWeight: 600, color: "var(--muted)", writingMode: "vertical-rl", letterSpacing: ".1em" }}>
            {open ? "OPEN" : "CLOSED"}
          </span>
        ) : (
          <>
            <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
              <span style={{ ...MICRO, marginBottom: 1 }}>{exchangeLabel}</span>
              <span style={{ fontFamily: MONO, fontSize: 15, fontWeight: 500, letterSpacing: ".02em", color: "var(--ink)" }}>{clock}</span>
            </div>
            <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: ".06em", color: mktColor }}>
              {open ? "OPEN" : "CLOSED"}
            </span>
          </>
        )}
      </div>

      {/* Status pulse — tripwire flag count + current regime, glanceable
          without opening either tile. Passive display only. Macro-only —
          no equity equivalent in v1. */}
      {dashDef.hasRegionLens && (
        <div
          style={{
            display: "flex", alignItems: "center", gap: collapsed ? 4 : 9,
            justifyContent: collapsed ? "center" : "flex-start",
            padding: collapsed ? "3px 0" : "5px 4px",
          }}
          title={`${flagged} tripwire${flagged === 1 ? "" : "s"} flagged · Regime: ${v.regime.label} (${v.regime.days}d, since ${v.regime.since})`}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
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
          </span>
          {!collapsed && (
            <span
              style={{
                fontSize: 11.5, fontWeight: 600, color: v.regime.color,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}
            >
              {v.regime.label}
            </span>
          )}
        </div>
      )}

      <div style={divider} />

      {/* Appearance */}
      {!collapsed && <div style={{ ...MICRO, marginBottom: 2 }}>Appearance</div>}
      <ThemeToggle collapsed={collapsed} />
      <DensityToggle collapsed={collapsed} />

      <div style={divider} />

      {/* Layout */}
      {!collapsed && <div style={{ ...MICRO, marginBottom: 2 }}>Layout</div>}

      <button
        onClick={() => setEditMode(!edit)}
        aria-label={edit ? "Done customizing" : "Customize layout"}
        title={collapsed ? (edit ? "Done customizing" : "Customize layout") : undefined}
        style={{
          display: "flex", alignItems: "center", gap: 7,
          justifyContent: collapsed ? "center" : "flex-start",
          fontSize: 12, fontWeight: 600, cursor: "pointer",
          color: edit ? "var(--green)" : "var(--gold)",
          background: edit ? "rgba(94,122,59,.1)" : "transparent",
          border: `1px solid ${edit ? "var(--green)" : "var(--gold)"}`,
          borderRadius: 7, padding: collapsed ? "6px 0" : "7px 9px",
        }}
      >
        <span>{edit ? "✓" : "✎"}</span>
        {!collapsed && <span>{edit ? "Done" : "Customize"}</span>}
      </button>

      <button
        onClick={() => (libraryDocked ? setLibraryDockOpen(!libraryDockOpen) : setLibraryOpen(!libraryOpen))}
        aria-label={(libraryDocked ? libraryDockOpen : libraryOpen) ? "Close the element library" : "Browse the element library"}
        aria-expanded={libraryDocked ? libraryDockOpen : libraryOpen}
        title={collapsed ? "Element library" : undefined}
        style={{
          display: "flex", alignItems: "center", gap: 7,
          justifyContent: collapsed ? "center" : "flex-start",
          fontSize: 12, fontWeight: 600, cursor: "pointer",
          color: (libraryDocked ? libraryDockOpen : libraryOpen) ? "var(--gold)" : "var(--muted)",
          background: (libraryDocked ? libraryDockOpen : libraryOpen)
            ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
          border: `1px solid ${(libraryDocked ? libraryDockOpen : libraryOpen)
            ? "color-mix(in srgb, var(--gold) 45%, transparent)" : "var(--control-border)"}`,
          borderRadius: 7, padding: collapsed ? "6px 0" : "7px 9px",
        }}
      >
        <span>▦</span>
        {!collapsed && <span>Element library</span>}
      </button>

      {edit && (
        <button
          onClick={resetLayout}
          aria-label="Reset layout to the default arrangement"
          title={collapsed ? "Reset layout" : undefined}
          style={{
            display: "flex", alignItems: "center", gap: 7,
            justifyContent: collapsed ? "center" : "flex-start",
            fontSize: 12, fontWeight: 600, color: "var(--muted)", cursor: "pointer",
            background: "transparent", border: "1px solid var(--control-border)",
            borderRadius: 7, padding: collapsed ? "6px 0" : "7px 9px",
          }}
        >
          <span>⟳</span>
          {!collapsed && <span>Reset layout</span>}
        </button>
      )}

      {/* Hidden-element tray. Only useful with labels, so the collapsed rail
          shows a count and defers to the expanded state. */}
      {edit && hidden.length > 0 && (
        <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 5 }}>
          {!collapsed && <div style={MICRO}>Hidden — click to re-add</div>}
          {collapsed ? (
            <div
              title={`${hidden.length} hidden element(s) — widen the window to re-add`}
              style={{
                textAlign: "center", fontFamily: MONO, fontSize: 10, fontWeight: 700,
                color: "var(--green)", border: "1px solid rgba(94,122,59,.4)",
                borderRadius: 6, padding: "4px 0",
              }}
            >
              +{hidden.length}
            </div>
          ) : (
            <HiddenElementButtons orientation="vertical" />
          )}
        </div>
      )}

      {edit && !collapsed && (
        <div style={{ fontSize: 10.5, lineHeight: 1.45, color: "var(--muted)", marginTop: 7 }}>
          Drag to move · corner to resize · × to hide
          {dashDef.hasRegionLens && " · set each tile's POV from its own dropdown"}.
        </div>
      )}

      <div style={divider} />

      {/* Saved views — named snapshots of region + layout + hidden. Fills the
          remaining rail height, so it's last and unbounded (no slot cap). */}
      {!collapsed && <div style={{ ...MICRO, marginBottom: 2 }}>Saved views</div>}

      {collapsed ? (
        savedViews.length > 0 && (
          <div
            title={savedViews.map((sv) => sv.name).join(", ")}
            style={{
              textAlign: "center", fontFamily: MONO, fontSize: 10, fontWeight: 700,
              color: "var(--gold)", border: "1px solid color-mix(in srgb, var(--gold) 45%, transparent)",
              borderRadius: 6, padding: "4px 0",
            }}
          >
            ★{savedViews.length}
          </div>
        )
      ) : (
        <>
          {savedViews.map((sv) => {
            const active = sv.id === activeSavedViewId;
            return (
              <div key={sv.id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <button
                  onClick={() => restoreView(sv.id)}
                  aria-current={active}
                  title={sv.name}
                  style={{
                    flex: 1, minWidth: 0, textAlign: "left", cursor: "pointer", fontSize: 12.5,
                    fontWeight: active ? 600 : 400,
                    color: active ? "var(--ink)" : "var(--body)",
                    background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
                    border: "1px solid transparent", borderRadius: 7, padding: "6px 8px",
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  }}
                >
                  {sv.name}
                </button>
                <button
                  onClick={() => deleteView(sv.id)}
                  aria-label={`Delete saved view "${sv.name}"`}
                  style={{
                    flexShrink: 0, background: "none", border: "1px solid var(--control-border)",
                    borderRadius: 6, width: 20, height: 20, cursor: "pointer",
                    color: "var(--muted)", fontSize: 11, lineHeight: 1,
                  }}
                >
                  ×
                </button>
              </div>
            );
          })}

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
                style={{
                  width: "100%", fontSize: 12, padding: "5px 7px",
                  border: "1px solid var(--control-border)", borderRadius: 6,
                  background: "var(--canvas)", color: "var(--ink)",
                }}
              />
            </form>
          ) : (
            <button
              onClick={() => setSavingView(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6, cursor: "pointer",
                fontSize: 12, fontWeight: 600, color: "var(--gold)", background: "transparent",
                border: "1px dashed color-mix(in srgb, var(--gold) 45%, transparent)",
                borderRadius: 7, padding: "6px 8px",
              }}
            >
              <span>+</span><span>Save current view</span>
            </button>
          )}
        </>
      )}
    </aside>
  );
}
