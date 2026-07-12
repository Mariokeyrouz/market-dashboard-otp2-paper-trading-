"use client";

import { useDerived } from "../DataContext";
import { MONO, SERIF } from "../ui";

export default function Tripwires() {
  const v = useDerived();
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", boxSizing: "border-box" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8 }}>
        <div style={{ fontFamily: SERIF, fontSize: 20, fontWeight: 600 }}>Risk Tripwires</div>
        <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 13, color: "#8A8172" }}>
          faster confirming signals — directional, not mechanically precise
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, flex: 1, minHeight: 0 }}>
        {v.tripwires.map((t) => (
          <div
            key={t.label}
            style={{
              background: "#FBF8F1", border: "1px solid rgba(0,0,0,.09)", borderTop: `3px solid ${t.tone}`,
              borderRadius: 11, padding: "11px 14px", overflow: "hidden",
            }}
          >
            <div style={{ fontSize: 10, letterSpacing: ".11em", textTransform: "uppercase", fontWeight: 600, color: "#8A8172" }}>
              {t.label}
            </div>
            <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12.5, color: "#8A8172", margin: "4px 0 7px" }}>{t.tag}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontFamily: MONO, fontSize: 22, fontWeight: 600 }}>{t.val}</span>
              <span style={{ fontFamily: MONO, fontSize: 12, color: t.chgColor }}>{t.chg}</span>
              <span style={{ fontSize: 11, color: "#8A8172" }}>{t.state}</span>
            </div>
            <div style={{ fontSize: 11.5, color: "#8A8172", marginTop: 7, lineHeight: 1.4 }}>{t.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
