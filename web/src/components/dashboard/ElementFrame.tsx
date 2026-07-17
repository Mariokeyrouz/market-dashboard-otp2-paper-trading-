"use client";

import { REGION_LABELS, REGIONS, type Region } from "@/lib/data/types";
import type { ElementDef } from "@/lib/elements/registry";
import { MONO } from "../ui";

/**
 * Wraps an element in the grid. Outside edit mode it's invisible chrome except
 * for the POV chip; in edit mode it overlays a full-tile drag surface (the RGL
 * drag handle), a title chip, a POV selector, and a hide button.
 */
export default function ElementFrame({
  def,
  edit,
  pin,
  onPin,
  onHide,
  children,
}: {
  def: ElementDef;
  edit: boolean;
  /** Region this element is pinned to; undefined = follows the global lens. */
  pin?: Region;
  onPin: (r: Region | null) => void;
  onHide: () => void;
  children: React.ReactNode;
}) {
  return (
    <div style={{ position: "relative", height: "100%" }}>
      {children}

      {/* A pinned tile shows a region that disagrees with the header. Saying so
          is not optional — an unlabelled tile quietly displaying Japan while the
          header reads US is a data-integrity trap. Rides the tile's top border,
          where no element's own content can collide with it. */}
      {pin && !edit && (
        <span
          title={`Pinned to ${REGION_LABELS[pin]} — this tile ignores the global region lens`}
          style={{
            position: "absolute", top: -1, right: 12, transform: "translateY(-50%)",
            zIndex: 6, pointerEvents: "none",
            fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: ".06em",
            color: "var(--gold)", background: "var(--tile)",
            border: "1px solid color-mix(in srgb, var(--gold) 45%, transparent)",
            borderRadius: 4, padding: "1px 6px", lineHeight: 1.5, whiteSpace: "nowrap",
          }}
        >
          POV · {pin}
        </span>
      )}

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
              border: "1.5px dashed color-mix(in srgb, var(--gold) 60%, transparent)",
              background: "color-mix(in srgb, var(--canvas) 8%, transparent)",
            }}
          />
          <span
            style={{
              position: "absolute", top: 6, left: 8, zIndex: 20, pointerEvents: "none",
              fontSize: 10, fontWeight: 600, letterSpacing: ".08em", textTransform: "uppercase",
              color: "var(--gold)", background: "var(--tile)", border: "1px solid color-mix(in srgb, var(--gold) 40%, transparent)",
              borderRadius: 5, padding: "2px 7px",
            }}
          >
            {def.title}
          </span>
          {/* Cross-region elements read every region, so a POV pin would be a
              control that does nothing — omit it rather than lie. */}
          {!def.crossRegion && (
            <select
              className="mws-select"
              aria-label={`Point of view for ${def.title}`}
              value={pin ?? ""}
              // The drag surface sits above the tile at zIndex 10 and swallows
              // pointer events; stop propagation so the select stays usable.
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
              onChange={(e) => onPin(e.target.value ? (e.target.value as Region) : null)}
              style={{
                position: "absolute", bottom: 6, left: 8, zIndex: 30,
                fontFamily: MONO, fontSize: 10, fontWeight: 600,
                color: pin ? "var(--gold)" : "var(--muted)",
                background: "var(--tile)",
                border: `1px solid ${pin ? "color-mix(in srgb, var(--gold) 50%, transparent)" : "var(--control-border)"}`,
                borderRadius: 5, padding: "3px 6px", lineHeight: 1.4, cursor: "pointer",
              }}
            >
              <option value="">POV · follow global</option>
              {REGIONS.map((r) => (
                <option key={r} value={r}>
                  POV · {REGION_LABELS[r]}
                </option>
              ))}
            </select>
          )}
          <button
            aria-label={`Hide ${def.title}`}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={onHide}
            style={{
              position: "absolute", top: 5, right: 5, zIndex: 30, width: 22, height: 22,
              display: "flex", alignItems: "center", justifyContent: "center",
              background: "var(--tile)", border: "1px solid rgba(177,74,46,.5)", borderRadius: 6,
              color: "var(--red)", fontSize: 14, lineHeight: 1, cursor: "pointer",
            }}
          >
            ×
          </button>
        </>
      )}
    </div>
  );
}
