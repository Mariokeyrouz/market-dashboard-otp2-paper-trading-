"use client";

import { selectHidden, useDashStore } from "@/lib/store";
import { Micro } from "../ui";
import HiddenElementButtons from "./HiddenElementButtons";

/** Edit-mode tray: re-add hidden elements with one click. */
export default function ElementLibrary() {
  const hidden = useDashStore(selectHidden);

  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        background: "color-mix(in srgb, var(--tile) 72%, transparent)",
        border: "1px dashed color-mix(in srgb, var(--gold) 50%, transparent)",
        borderRadius: 10, padding: "8px 13px",
      }}
    >
      <Micro>Customize</Micro>
      <span style={{ fontSize: 12, color: "var(--muted)" }}>
        Drag any element to move it · drag the corner to resize · × to hide.
      </span>
      {hidden.length > 0 && (
        <span style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginLeft: "auto" }}>
          <span style={{ fontSize: 11, color: "var(--muted)" }}>Hidden — click to re-add:</span>
          <HiddenElementButtons orientation="horizontal" />
        </span>
      )}
    </div>
  );
}
