"use client";

import { useDerived } from "../DataContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function LaborMarket() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
        <PanelTitle>Labor Market</PanelTitle>
        <ItalicNote>{v.region}</ItalicNote>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "9px 16px" }}>
        {v.labor.map((l) => (
          <div key={l.name} style={{ borderBottom: "1px solid rgba(0,0,0,.05)", paddingBottom: 8 }}>
            <div style={{ fontSize: 11, color: "#8A8172" }}>{l.name}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 7, marginTop: 2 }}>
              <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600 }}>{l.value}</span>
              <span style={{ fontSize: 10, color: "#B4A98F" }}>{l.delta}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
