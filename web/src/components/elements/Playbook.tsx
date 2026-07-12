"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, TILE } from "../ui";

export default function Playbook() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <Micro style={{ letterSpacing: ".14em", marginBottom: 12 }}>Regime Playbook</Micro>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {v.playbook.map((p) => (
          <div key={p.asset} style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <span
              style={{
                fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: ".05em", color: p.color,
                border: `1px solid ${p.color}`, borderRadius: 4, padding: "3px 6px", minWidth: 44, textAlign: "center",
              }}
            >
              {p.side}
            </span>
            <span style={{ fontSize: 13, color: "#2B2721" }}>{p.asset}</span>
            <span style={{ fontSize: 12, color: "#8A8172", marginLeft: "auto" }}>{p.note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
