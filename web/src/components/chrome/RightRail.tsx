"use client";

import { DOCK_RAIL_W, DOCK_W } from "@/lib/useShellMode";
import { SERIF } from "../ui";
import LogicContent from "./LogicContent";

/**
 * The Logic explainer, docked — collapsed to an icon strip by default.
 *
 * The strip is always on screen so the panel stays discoverable and the grid
 * doesn't reflow between two unrelated affordances; opening it expands the
 * dock beside it rather than covering the dashboard, which is the whole reason
 * to dock it at all. Same shape as Koyfin's right-hand icon rail.
 */
export default function RightRail({ open, onToggle }: { open: boolean; onToggle: (b: boolean) => void }) {
  return (
    <>
      {open && (
        <aside
          aria-label="Why this layout"
          style={{
            alignSelf: "stretch",
            width: DOCK_W, flexShrink: 0,
            overflowY: "auto",
            background: "var(--tile)", border: "1px solid var(--tile-border)",
            borderRadius: 10, padding: "12px 14px 16px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
            <div style={{ fontFamily: SERIF, fontSize: 18, fontWeight: 600 }}>Why this layout</div>
            <button
              onClick={() => onToggle(false)}
              aria-label="Collapse the layout logic panel"
              style={{
                flexShrink: 0, background: "none", border: "1px solid var(--control-border)",
                borderRadius: 6, width: 24, height: 24, cursor: "pointer",
                color: "var(--muted)", fontSize: 13, lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>
          <LogicContent />
        </aside>
      )}

      <nav
        aria-label="Panels"
        style={{
          alignSelf: "stretch",
          width: DOCK_RAIL_W, flexShrink: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
          background: "var(--tile)", border: "1px solid var(--tile-border)",
          borderRadius: 10, padding: "7px 0",
        }}
      >
        <div style={{ position: "sticky", top: 8, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
          <button
            onClick={() => onToggle(!open)}
            aria-label={open ? "Collapse the layout logic panel" : "Expand the layout logic panel"}
            aria-expanded={open}
            title={open ? "Hide “Why this layout”" : "Show “Why this layout”"}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 26, height: 26, cursor: "pointer", fontSize: 13, lineHeight: 1,
              color: open ? "var(--gold)" : "var(--muted)",
              background: open ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
              border: `1px solid ${open ? "color-mix(in srgb, var(--gold) 45%, transparent)" : "var(--control-border)"}`,
              borderRadius: 7,
            }}
          >
            ⓘ
          </button>
          <span
            aria-hidden
            style={{
              writingMode: "vertical-rl", letterSpacing: ".16em", fontSize: 9.5, fontWeight: 600,
              textTransform: "uppercase", color: open ? "var(--gold)" : "var(--faint)", marginTop: 2,
            }}
          >
            Logic
          </span>
        </div>
      </nav>
    </>
  );
}
