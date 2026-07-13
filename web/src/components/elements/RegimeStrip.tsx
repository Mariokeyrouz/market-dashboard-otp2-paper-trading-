"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

export default function RegimeStrip() {
  const v = useDerived();
  const m = v.metrics;
  const metric = (label: string, value: React.ReactNode, sub: string, color?: string) => (
    <div>
      <Micro>{label}</Micro>
      <div style={{ fontFamily: MONO, fontSize: 19, fontWeight: 500, marginTop: 3, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{sub}</div>
    </div>
  );
  return (
    <div style={{ ...TILE, padding: "8px 12px", flexDirection: "row", alignItems: "stretch", gap: 20 }}>
      <div style={{ minWidth: 220 }}>
        <Micro style={{ letterSpacing: ".14em" }}>Regime · {v.region}</Micro>
        <div
          style={{
            display: "flex", alignItems: "center", gap: 9, margin: "7px 0 8px", padding: "7px 13px",
            border: `1px solid ${v.regime.color}`, borderRadius: 9, width: "fit-content",
          }}
        >
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: v.regime.color }} />
          <span style={{ fontFamily: SERIF, fontSize: 20, fontWeight: 600, color: v.regime.color }}>{v.regime.label}</span>
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>
          In regime <span style={{ fontFamily: MONO, color: "var(--ink)", fontWeight: 600 }}>{v.regime.days}d</span> · since {v.regime.since}
        </div>
        <div style={{ display: "flex", gap: 3, marginTop: 9, height: 22, alignItems: "flex-end" }}>
          {v.regime.history.map((seg, i) => (
            <div key={i} title={seg.label} style={{ width: seg.w, height: 18, borderRadius: 2, background: seg.color }} />
          ))}
        </div>
      </div>
      <div style={{ width: 1, background: "var(--tile-border)" }} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 18, flex: 1, alignContent: "center" }}>
        {metric("Inflation", m.inflation, m.inflationSub)}
        {metric("Growth", m.growth, m.growthSub, m.growthColor)}
        {metric("Policy", m.policy, m.policySub)}
        {metric("Conditions", m.cond, m.condSub, m.condColor)}
      </div>
    </div>
  );
}
