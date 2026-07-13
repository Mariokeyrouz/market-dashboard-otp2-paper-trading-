"use client";

import { useDerived } from "../DataContext";
import { DivergingBar, MONO, PanelTitle, Sparkline, TILE } from "../ui";

export default function EconSurprises() {
  const v = useDerived();
  const s = v.surprises;
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
        <div style={{ whiteSpace: "nowrap" }}>
          <PanelTitle>Economic Surprises</PanelTitle>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 5 }}>
          <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: s.color }}>{s.headline}</span>
          <Sparkline d={s.spark} stroke={s.color} w={56} h={20} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {s.rows.map((r) => (
          <div key={r.name} style={{ display: "grid", gridTemplateColumns: "104px 1fr 34px", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--ink)" }}>{r.name}</span>
            <DivergingBar barLeft={r.barLeft} barW={r.barW} color={r.color} height={11} track="transparent" />
            <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, textAlign: "right", color: r.color }}>{r.val}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 10, color: "var(--faint)", marginTop: 7 }}>bars = actual vs consensus, σ · beats right / misses left</div>
    </div>
  );
}
