"use client";

import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, PanelTitle, TableGroupLabel, TableHeadRow, TableRow, TILE } from "../ui";

export default function GlobalMarkets() {
  const v = useTerminalDerived();
  const compact = useCompact();
  const developed = v.global.filter((r) => r.group === "Developed");
  const emerging = v.global.filter((r) => r.group === "Emerging");
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>Global Markets</PanelTitle>
        {!compact && <ItalicNote>Developed &amp; Emerging</ItalicNote>}
      </div>
      <TableHeadRow labels={["Index", "Last", "Chg %"]} />
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 4 : 7, flex: 1, minHeight: 0, overflow: "hidden" }}>
        <TableGroupLabel>Developed</TableGroupLabel>
        {developed.map((r) => (
          <TableRow key={r.ticker} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
        ))}
        <TableGroupLabel>Emerging</TableGroupLabel>
        {emerging.map((r) => (
          <TableRow key={r.ticker} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
        ))}
      </div>
    </div>
  );
}
