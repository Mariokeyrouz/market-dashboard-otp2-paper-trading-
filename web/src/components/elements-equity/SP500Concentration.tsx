"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

/**
 * A plain left-anchored magnitude bar — deliberately not the shared
 * DivergingBar, which always draws a 50%-centerline for values that
 * straddle zero. Concentration weights are 0-100%, so that centerline
 * would read as a false "50 is neutral" marker.
 */
function WeightBar({ pct, color, height }: { pct: number; color: string; height: number }) {
  return (
    <div style={{ position: "relative", height, background: "var(--hairline)", borderRadius: 4 }}>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: `${pct}%`, background: color, borderRadius: 4 }} />
    </div>
  );
}

export default function SP500Concentration() {
  const v = useEquityDerived();
  const c = v.concentration;
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>S&amp;P 500 Concentration</PanelTitle>
        {!compact && <ItalicNote>top 10, % of index weight</ItalicNote>}
      </div>
      <div style={{ fontFamily: MONO, fontSize: compact ? 20 : 26, fontWeight: 600, marginBottom: compact ? 6 : 10 }}>
        {c.totalWeightPct}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 3 : 6, flex: 1, minHeight: 0, overflow: "hidden" }}>
        {c.rows.map((r) => (
          <div key={r.name} style={{ display: "grid", gridTemplateColumns: "56px 1fr 44px", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: compact ? 11 : 12.5, fontWeight: 600, color: "var(--ink)" }}>{r.name}</span>
            <WeightBar pct={parseFloat(r.barW)} color="var(--gold)" height={compact ? 6 : 8} />
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: "var(--muted)" }}>{r.weightPct}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
