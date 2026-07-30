"use client";

import { useDashStore } from "@/lib/store";
import { SERIF } from "../ui";
import HiddenElementButtons from "./HiddenElementButtons";

/**
 * The Element Library as an overlay drawer, for mid/narrow screens where the
 * dock doesn't fit (see ElementLibraryDock for the wide case). Unlike
 * LogicPanel, this has no floating tab of its own — the trigger is the
 * existing button in LeftRail (mid) or Header (narrow), so there's no
 * second affordance competing with the Logic tab for the same screen edge.
 */
export default function ElementLibraryPanel() {
  const open = useDashStore((s) => s.libraryOpen);
  const setOpen = useDashStore((s) => s.setLibraryOpen);

  return (
    <>
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 70, background: "var(--scrim)" }}
        />
      )}
      <aside
        aria-hidden={!open}
        aria-label="Element library"
        style={{
          position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 80, width: 340, maxWidth: "92vw",
          background: "var(--tile)", borderRight: "1px solid var(--tile-border)",
          boxShadow: "8px 0 28px rgba(43,39,33,.16)",
          transform: open ? "translateX(0)" : "translateX(-105%)",
          transition: "transform .25s ease", overflowY: "auto", padding: "18px 20px 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontFamily: SERIF, fontSize: 20, fontWeight: 600 }}>Element Library</div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            style={{ background: "none", border: "1px solid var(--control-border)", borderRadius: 6, width: 26, height: 26, cursor: "pointer", color: "var(--muted)", fontSize: 14 }}
          >
            ×
          </button>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 12 }}>
          Elements currently hidden from the dashboard — tap one to add it back.
        </div>
        <HiddenElementButtons orientation="vertical" emptyLabel="Everything is already on the dashboard." />
      </aside>
    </>
  );
}
