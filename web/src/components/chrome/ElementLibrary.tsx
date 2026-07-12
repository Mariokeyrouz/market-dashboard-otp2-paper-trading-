"use client";

import { ELEMENT_MAP } from "@/lib/elements/registry";
import { useDashStore } from "@/lib/store";
import { Micro } from "../ui";

/** Edit-mode tray: re-add hidden elements with one click. */
export default function ElementLibrary() {
  const hidden = useDashStore((s) => s.hidden);
  const showElement = useDashStore((s) => s.showElement);

  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        background: "rgba(251,248,241,.7)", border: "1px dashed rgba(160,123,29,.5)",
        borderRadius: 10, padding: "8px 13px",
      }}
    >
      <Micro>Customize</Micro>
      <span style={{ fontSize: 12, color: "#8A8172" }}>
        Drag any element to move it · drag the corner to resize · × to hide.
      </span>
      {hidden.length > 0 && (
        <span style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginLeft: "auto" }}>
          <span style={{ fontSize: 11, color: "#8A8172" }}>Hidden — click to re-add:</span>
          {hidden.map((id) => {
            const def = ELEMENT_MAP.get(id);
            if (!def) return null;
            return (
              <button
                key={id}
                onClick={() => showElement(id)}
                style={{
                  fontSize: 11.5, fontWeight: 600, color: "#5E7A3B", background: "rgba(94,122,59,.08)",
                  border: "1px solid rgba(94,122,59,.4)", borderRadius: 6, padding: "4px 10px", cursor: "pointer",
                }}
              >
                + {def.title}
              </button>
            );
          })}
        </span>
      )}
    </div>
  );
}
