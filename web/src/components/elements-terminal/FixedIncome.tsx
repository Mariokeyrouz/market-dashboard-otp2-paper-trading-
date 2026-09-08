"use client";

import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { MICRO, PanelTitle, TableHeadRow, TableRow, TILE } from "../ui";

export default function FixedIncome() {
  const v = useTerminalDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <PanelTitle>Fixed Income</PanelTitle>
      <div style={{ display: "flex", gap: 16, marginTop: compact ? 4 : 8, flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 4 : 7, minWidth: 0 }}>
          <div style={MICRO}>Govt</div>
          <TableHeadRow labels={["ETF", "Last", "Chg %"]} />
          {v.fixedIncome.govt.map((r) => (
            <TableRow key={r.ticker} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
          ))}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 4 : 7, minWidth: 0 }}>
          <div style={MICRO}>Corp</div>
          <TableHeadRow labels={["ETF", "Last", "Chg %"]} />
          {v.fixedIncome.corp.map((r) => (
            <TableRow key={r.ticker} name={r.name} price={r.price} chgPct={r.chgPct} chgColor={r.chgColor} compact={compact} />
          ))}
        </div>
      </div>
    </div>
  );
}
