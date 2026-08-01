"use client";

import { selectHidden, useDashStore } from "@/lib/store";
import { useDashboardDef } from "@/lib/useDashboardDef";

/**
 * The re-add-a-hidden-element button list, shared by every place that offers
 * it: Header's edit-mode tray, the left rail's edit-mode tray, and the
 * always-available Element Library dock/drawer. One list, three renderers.
 */
export default function HiddenElementButtons({
  orientation = "horizontal",
  emptyLabel,
}: {
  orientation?: "horizontal" | "vertical";
  /** Shown in place of the (otherwise empty) list when nothing is hidden. */
  emptyLabel?: string;
}) {
  const dashDef = useDashboardDef();
  const hidden = useDashStore(selectHidden);
  const showElement = useDashStore((s) => s.showElement);

  if (hidden.length === 0) {
    return emptyLabel ? <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{emptyLabel}</span> : null;
  }

  return (
    <span
      style={{
        display: "flex", flexWrap: "wrap",
        flexDirection: orientation === "vertical" ? "column" : "row",
        alignItems: orientation === "vertical" ? "stretch" : "center",
        gap: orientation === "vertical" ? 5 : 7,
      }}
    >
      {hidden.map((id) => {
        const def = dashDef.elementMap.get(id);
        if (!def) return null;
        return (
          <button
            key={id}
            onClick={() => showElement(id)}
            style={{
              textAlign: "left", fontSize: 11.5, fontWeight: 600, color: "var(--green)",
              background: "rgba(94,122,59,.08)", border: "1px solid rgba(94,122,59,.4)",
              borderRadius: 6, padding: orientation === "vertical" ? "4px 8px" : "4px 10px",
              cursor: "pointer",
            }}
          >
            + {def.title}
          </button>
        );
      })}
    </span>
  );
}
