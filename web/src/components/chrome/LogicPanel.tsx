"use client";

import { useDashStore } from "@/lib/store";
import { SERIF } from "../ui";
import LogicContent from "./LogicContent";

/**
 * The Logic explainer as a floating tab + overlay drawer. Used when the
 * viewport can't afford the 320px right dock (see RightRail for the wide case).
 */
export default function LogicPanel() {
  const open = useDashStore((s) => s.logicOpen);
  const setOpen = useDashStore((s) => s.setLogicOpen);

  return (
    <>
      {/* Floating side tab */}
      <button
        onClick={() => setOpen(true)}
        aria-label="Open the layout logic explainer"
        style={{
          position: "fixed", right: 0, top: "42%", zIndex: 60,
          writingMode: "vertical-rl", letterSpacing: ".18em",
          fontSize: 11, fontWeight: 600, textTransform: "uppercase", color: "var(--gold)",
          background: "var(--tile)", border: "1px solid rgba(160,123,29,.5)", borderRight: "none",
          borderRadius: "8px 0 0 8px", padding: "14px 7px", cursor: "pointer",
          boxShadow: "-2px 2px 8px rgba(43,39,33,.08)",
        }}
      >
        ⓘ Logic
      </button>

      {/* Backdrop + drawer */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 70, background: "var(--scrim)" }}
        />
      )}
      <aside
        aria-hidden={!open}
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 80, width: 400, maxWidth: "92vw",
          background: "var(--tile)", borderLeft: "1px solid var(--tile-border)",
          boxShadow: "-8px 0 28px rgba(43,39,33,.16)",
          transform: open ? "translateX(0)" : "translateX(105%)",
          transition: "transform .25s ease", overflowY: "auto", padding: "18px 20px 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontFamily: SERIF, fontSize: 20, fontWeight: 600 }}>Why this layout</div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            style={{ background: "none", border: "1px solid var(--control-border)", borderRadius: 6, width: 26, height: 26, cursor: "pointer", color: "var(--muted)", fontSize: 14 }}
          >
            ×
          </button>
        </div>
        <LogicContent />
      </aside>
    </>
  );
}
