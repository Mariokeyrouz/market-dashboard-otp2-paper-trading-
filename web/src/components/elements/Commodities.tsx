"use client";

import { useDerived } from "../DataContext";
import { ItalicNote, MONO, PanelTitle, Sparkline, TILE } from "../ui";

export default function Commodities() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 7 }}>
        <PanelTitle>Commodities</PanelTitle>
        <ItalicNote>price · Δ 1D · 7d</ItalicNote>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {v.commods.map((c) => (
          <div
            key={c.name}
            style={{
              display: "grid", gridTemplateColumns: "1fr auto 62px 72px", gap: 12, alignItems: "center",
              padding: "4px 0", borderBottom: "1px solid var(--hairline)",
            }}
          >
            <span style={{ fontSize: 12.5, color: "var(--ink)" }}>{c.name}</span>
            <span style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600 }}>{c.price}</span>
            <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, textAlign: "right", color: c.chgColor }}>{c.chg}</span>
            <Sparkline d={c.spark} stroke={c.chgColor} w={70} h={24} />
          </div>
        ))}
      </div>
    </div>
  );
}
