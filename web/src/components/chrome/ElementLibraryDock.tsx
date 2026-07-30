"use client";

import { useDashStore } from "@/lib/store";
import { DOCK_W } from "@/lib/useShellMode";
import { SERIF } from "../ui";
import HiddenElementButtons from "./HiddenElementButtons";

/**
 * The Element Library, docked — wide-screen counterpart to
 * ElementLibraryPanel's mid/narrow drawer. Toggled from the button in
 * LeftRail, same dock chrome as RightRail's Logic panel.
 */
export default function ElementLibraryDock() {
  const open = useDashStore((s) => s.libraryDockOpen);
  const setOpen = useDashStore((s) => s.setLibraryDockOpen);

  if (!open) return null;

  return (
    <aside
      aria-label="Element library"
      style={{
        alignSelf: "stretch",
        width: DOCK_W, flexShrink: 0,
        overflowY: "auto",
        background: "var(--tile)", border: "1px solid var(--tile-border)",
        borderRadius: 10, padding: "12px 14px 16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
        <div style={{ fontFamily: SERIF, fontSize: 18, fontWeight: 600 }}>Element Library</div>
        <button
          onClick={() => setOpen(false)}
          aria-label="Close the element library"
          style={{
            flexShrink: 0, background: "none", border: "1px solid var(--control-border)",
            borderRadius: 6, width: 24, height: 24, cursor: "pointer",
            color: "var(--muted)", fontSize: 13, lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>
        Elements currently hidden from the dashboard — click one to add it back.
      </div>
      <HiddenElementButtons orientation="vertical" emptyLabel="Everything is already on the dashboard." />
    </aside>
  );
}
