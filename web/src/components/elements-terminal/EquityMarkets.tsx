"use client";

import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, PanelTitle, TableHeadRow, TableRow, TILE } from "../ui";

export default function EquityMarkets() {
  const v = useTerminalDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>US Equity Markets</PanelTitle>
        {!compact && <ItalicNote>major indices + VIX</ItalicNote>}
      </div>
      <TableHeadRow labels={["Index", "Last", "Chg %"]} />
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 5 : 8, flex: 1, minHeight: 0, overflow: "hidden" }}>
        {v.markets.map((r) => (
          <TableRow key={r.name} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
        ))}
      </div>
    </div>
  );
}
