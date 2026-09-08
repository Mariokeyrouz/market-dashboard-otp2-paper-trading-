"use client";

import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function TerminalSectors() {
  const v = useTerminalDerived();
  const rows = v.sectors;
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>US Equity Sectors</PanelTitle>
        {!compact && <ItalicNote>S&amp;P 500 GICS sectors, ranked 1D</ItalicNote>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: compact ? "1fr 46px 38px 38px 38px" : "1fr 58px 46px 46px 46px", gap: 8, marginBottom: 3 }}>
        <span />
        <span style={{ fontSize: 9.5, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--faint)", fontWeight: 600, textAlign: "right" }}>Price</span>
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
              gridTemplateColumns: compact ? "1fr 46px 38px 38px 38px" : "1fr 58px 46px 46px 46px",
              gap: 8,
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: compact ? 11 : 12.5, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.name}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: "var(--muted)" }}>{r.price}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1dColor }}>{r.chg1d}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1wColor }}>{r.chg1w}</span>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: r.chg1mColor }}>{r.chg1m}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
