"use client";

import { useDerived } from "../DataContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function LaborMarket() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 9 }}>
        <PanelTitle>Labor Market</PanelTitle>
        <ItalicNote>{v.region}</ItalicNote>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "7px 14px" }}>
        {v.labor.map((l) => (
          <div key={l.name} style={{ borderBottom: "1px solid var(--hairline)", paddingBottom: 6 }}>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>{l.name}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginTop: 2 }}>
              <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600 }}>{l.value}</span>
              <span style={{ fontSize: 10, color: "var(--faint)" }}>{l.delta}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
