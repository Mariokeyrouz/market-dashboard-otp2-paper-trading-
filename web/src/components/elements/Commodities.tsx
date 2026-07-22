"use client";

import { useDerived } from "../DataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, Sparkline, TILE } from "../ui";

export default function Commodities() {
  const v = useDerived();
  // Compact trades the sparkline column and row air for showing every row.
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 1 : 7 }}>
        <PanelTitle>Commodities</PanelTitle>
        {!compact && <ItalicNote>price · Δ 1D · 7d</ItalicNote>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 0 : 2 }}>
        {v.commods.map((c) => (
          <div
            key={c.name}
            style={{
              display: "grid", gridTemplateColumns: compact ? "1fr auto 62px" : "1fr auto 62px 72px",
              gap: 12, alignItems: "center", lineHeight: compact ? 1.05 : undefined,
              padding: compact ? "0" : "4px 0", borderBottom: "1px solid var(--hairline)",
            }}
          >
            <span style={{ fontSize: compact ? 10.5 : 12.5, color: "var(--ink)" }}>{c.name}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 11 : 14, fontWeight: 600 }}>{c.price}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 12, fontWeight: 600, textAlign: "right", color: c.chgColor }}>{c.chg}</span>
            {!compact && <Sparkline d={c.spark} stroke={c.chgColor} w={70} h={24} />}
          </div>
        ))}
      </div>
    </div>
  );
}
