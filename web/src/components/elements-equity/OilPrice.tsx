"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { MONO, PanelTitle, Sparkline, TILE } from "../ui";

export default function OilPrice() {
  const v = useEquityDerived();
  const o = v.oil;
  const compact = useCompact();
  return (
    <div style={TILE}>
      <PanelTitle>{o.name}</PanelTitle>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: compact ? 6 : 12 }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 26 : 34, fontWeight: 600 }}>${o.val}</span>
        <span style={{ fontFamily: MONO, fontSize: compact ? 12 : 15, fontWeight: 600, color: o.chgColor }}>{o.chg}</span>
      </div>
      {!compact && (
        <div style={{ marginTop: "auto", paddingTop: 10 }}>
          <Sparkline d={o.spark} stroke={o.chgColor} w={110} h={30} />
        </div>
      )}
    </div>
  );
}
