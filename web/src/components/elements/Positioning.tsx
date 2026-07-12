"use client";

import { useDerived } from "../DataContext";
import { DivergingBar, ItalicNote, MONO, Micro, TILE } from "../ui";

export default function Positioning() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
        <Micro>Positioning &amp; Flows</Micro>
        <ItalicNote style={{ fontSize: 11 }}>net spec · z-score</ItalicNote>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
        {v.positioning.map((p) => (
          <div key={p.name} style={{ display: "grid", gridTemplateColumns: "78px 1fr 42px", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: 12.5, color: "#2B2721" }}>{p.name}</span>
            <DivergingBar barLeft={p.barLeft} barW={p.barW} color={p.color} height={8} />
            <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, textAlign: "right", color: p.color }}>{p.val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
