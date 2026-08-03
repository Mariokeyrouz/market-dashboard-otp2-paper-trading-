"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { DivergingBar, ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function SectorPerformance() {
  const v = useEquityDerived();
  const rows = v.sectors;
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>Sector Performance</PanelTitle>
        {!compact && <ItalicNote>S&amp;P 500 GICS sectors, ranked 1D</ItalicNote>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr 60px 40px 40px 40px" : "1fr 84px 46px 46px 46px", gap: 8, marginBottom: 3 }}>
        <span />
        <span />
        <span style={{ fontSize: 9.5, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--faint)", fontWeight: 600, textAlign: "right" }}>1D</span>
        <span style={{ fontSize: 9.5, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--faint)", fontWeight: 600, textAlign: "right" }}>1W</span>
        <span style={{ fontSize: 9.5, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--faint)", fontWeight: 600, textAlign: "right" }}>1M</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 3 : 5, flex: 1, minHeight: 0, overflow: "hidden" }}>
        {rows.map((r) => (
          <div
            key={r.name}
            style={{
              display: "grid",
              gridTemplateColumns: compact ? "1fr 60px 40px 40px 40px" : "1fr 84px 46px 46px 46px",
              gap: 8,
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: compact ? 11 : 12.5, color: "var(--ink)" }}>{r.name}</span>
            <DivergingBar barLeft={r.barLeft} barW={r.barW} color={r.chg1dColor} height={compact ? 6 : 8} />
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1dColor }}>{r.chg1d}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1wColor }}>{r.chg1w}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1mColor }}>{r.chg1m}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
