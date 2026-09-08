"use client";

import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, PanelTitle, TableHeadRow, TableRow, TILE } from "../ui";

export default function Currencies() {
  const v = useTerminalDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>Currencies</PanelTitle>
        {!compact && <ItalicNote>7 major FX pairs</ItalicNote>}
      </div>
      <TableHeadRow labels={["Pair", "Last", "Chg %"]} />
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 5 : 8, flex: 1, minHeight: 0, overflow: "hidden" }}>
        {v.currencies.map((r) => (
          <TableRow key={r.ticker} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
        ))}
      </div>
    </div>
  );
}
