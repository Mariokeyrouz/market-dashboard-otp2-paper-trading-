"use client";

import type { ElementDef } from "@/lib/elements/registry";

/**
 * Wraps an element in the grid. Outside edit mode it's invisible chrome; in
 * edit mode it overlays a full-tile drag surface (the RGL drag handle), a
 * title chip, and a hide button.
 */
export default function ElementFrame({
  def,
  edit,
  onHide,
  children,
}: {
  def: ElementDef;
  edit: boolean;
  onHide: () => void;
  children: React.ReactNode;
}) {
  return (
    <div style={{ position: "relative", height: "100%" }}>
      {children}
      {edit && (
        <>
          <div
            className="mws-drag"
            title={`Drag to move · ${def.title}`}
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 10,
              cursor: "grab",
              borderRadius: 10,
              border: "1.5px dashed rgba(160,123,29,.6)",
              background: "rgba(232,222,203,.06)",
            }}
          />
          <span
            style={{
              position: "absolute", top: 6, left: 8, zIndex: 20, pointerEvents: "none",
              fontSize: 10, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase",
              color: "#A07B1D", background: "rgba(251,248,241,.92)", border: "1px solid rgba(160,123,29,.4)",
              borderRadius: 5, padding: "2px 7px",
            }}
          >
            {def.title}
          </span>
          <button
            aria-label={`Hide ${def.title}`}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={onHide}
            style={{
              position: "absolute", top: 5, right: 5, zIndex: 30, width: 22, height: 22,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "#FBF8F1", border: "1px solid rgba(177,74,46,.5)", borderRadius: 6,
              color: "#B14A2E", fontSize: 14, lineHeight: 1, cursor: "pointer",
            }}
          >
            ×
          </button>
        </>
      )}
    </div>
  );
}
