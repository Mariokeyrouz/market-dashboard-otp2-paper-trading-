"use client";

import { REGION_LABELS, REGIONS } from "@/lib/data/types";
import { ELEMENT_MAP } from "@/lib/elements/registry";
import { useDashStore } from "@/lib/store";
import { useClock } from "@/lib/useClock";
import { RAIL_W, RAIL_W_COLLAPSED } from "@/lib/useShellMode";
import { useDerived } from "../DataContext";
import { MICRO, MONO, SERIF } from "../ui";
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
}: {
  collapsed: boolean;
  /** Manual collapse override, available only in `wide` mode. Undefined in
   *  `mid`, where the rail is force-collapsed and a toggle would be a no-op. */
  onToggleCollapse?: () => void;
}) {
  const region = useDashStore((s) => s.region);
  const setRegion = useDashStore((s) => s.setRegion);
  const edit = useDashStore((s) => s.editMode);
  const setEditMode = useDashStore((s) => s.setEditMode);
  const resetLayout = useDashStore((s) => s.resetLayout);
  const hidden = useDashStore((s) => s.hidden);
  const showElement = useDashStore((s) => s.showElement);
  const { clock, open } = useClock();
  const v = useDerived();
  const mktColor = open ? "var(--green)" : "var(--red)";

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
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: SERIF, fontSize: 15, fontWeight: 600, letterSpacing: "-.01em", lineHeight: 1.2 }}>
                Macro Signal Dashboard
              </div>
              <span
                style={{
                  display: "inline-block", marginTop: 4,
                  fontFamily: MONO, fontSize: 10, padding: "2px 6px",
                  border: "1px solid var(--control-border)", borderRadius: 5, color: "var(--muted)",
                }}
              >
                OTP2.0
              </span>
            </div>
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
        title={`${v.exchange} · ${open ? "OPEN" : "CLOSED"}`}
      >
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: mktColor, animation: "mp-pulse 2s ease-in-out infinite", flexShrink: 0 }} />
        {collapsed ? (
          <span style={{ fontFamily: MONO, fontSize: 8.5, fontWeight: 600, color: "var(--muted)", writingMode: "vertical-rl", letterSpacing: ".1em" }}>
            {open ? "OPEN" : "CLOSED"}
          </span>
        ) : (
          <>
            <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.15 }}>
              <span style={{ ...MICRO, marginBottom: 1 }}>{v.exchange}</span>
              <span style={{ fontFamily: MONO, fontSize: 15, fontWeight: 500, letterSpacing: ".02em", color: "var(--ink)" }}>{clock}</span>
            </div>
            <span style={{ marginLeft: "auto", fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: ".06em", color: mktColor }}>
              {open ? "OPEN" : "CLOSED"}
            </span>
          </>
        )}
      </div>

      <div style={divider} />

      {/* Appearance */}
      {!collapsed && <div style={{ ...MICRO, marginBottom: 2 }}>Appearance</div>}
      <ThemeToggle collapsed={collapsed} />

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
            hidden.map((id) => {
              const def = ELEMENT_MAP.get(id);
              if (!def) return null;
              return (
                <button
                  key={id}
                  onClick={() => showElement(id)}
                  style={{
                    textAlign: "left", fontSize: 11.5, fontWeight: 600, color: "var(--green)",
                    background: "rgba(94,122,59,.08)", border: "1px solid rgba(94,122,59,.4)",
                    borderRadius: 6, padding: "4px 8px", cursor: "pointer",
                  }}
                >
                  + {def.title}
                </button>
              );
            })
          )}
        </div>
      )}

      {edit && !collapsed && (
        <div style={{ fontSize: 10.5, lineHeight: 1.45, color: "var(--muted)", marginTop: 7 }}>
          Drag to move · corner to resize · × to hide · set each tile&apos;s POV from its own dropdown.
        </div>
      )}
    </aside>
  );
}
