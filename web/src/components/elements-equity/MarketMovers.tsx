"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { MICRO, MONO, PanelTitle, TILE } from "../ui";
import type { MoverFmt } from "@/lib/derive-equity";

function MoverRow({ ticker, name, price, chgPct, chgColor, compact }: MoverFmt & { compact: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 6 }}>
      <div style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 11 : 12.5, fontWeight: 600 }}>{ticker}</span>
        <span style={{ fontSize: compact ? 9.5 : 10.5, color: "var(--muted)", marginLeft: 6 }}>{name}</span>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, color: "var(--muted)" }}>{price}</span>
        <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, color: chgColor, minWidth: 52, textAlign: "right" }}>{chgPct}</span>
      </div>
    </div>
  );
}

export default function MarketMovers() {
  const v = useEquityDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <PanelTitle>Market Movers</PanelTitle>
      <div style={{ display: "flex", gap: 16, marginTop: compact ? 4 : 8, flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 4 : 7, minWidth: 0 }}>
          <div style={{ ...MICRO, color: "var(--green)" }}>Gainers</div>
          {v.movers.gainers.map((r) => (
            <MoverRow key={r.ticker} {...r} compact={compact} />
          ))}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 4 : 7, minWidth: 0 }}>
          <div style={{ ...MICRO, color: "var(--red)" }}>Losers</div>
          {v.movers.losers.map((r) => (
            <MoverRow key={r.ticker} {...r} compact={compact} />
          ))}
        </div>
      </div>
    </div>
  );
}
