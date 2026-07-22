"use client";

import { useDerived } from "../DataContext";
import { useCompact } from "../DensityContext";
import { MONO, Micro, TILE } from "../ui";

export default function Playbook() {
  const v = useDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <Micro style={{ letterSpacing: ".14em", marginBottom: compact ? 3 : 9 }}>Regime Playbook</Micro>
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 3 : 7 }}>
        {v.playbook.map((p) => (
          // Grid so the columns align down the rows and the note sits right after
          // the asset (filling the middle) instead of being flung to the far right.
          <div key={p.asset} style={{ display: "grid", gridTemplateColumns: "44px auto 1fr", alignItems: "center", gap: 11 }}>
            <span
              style={{
                fontFamily: MONO, fontSize: compact ? 9 : 10, fontWeight: 600, letterSpacing: ".05em", color: p.color,
                border: `1px solid ${p.color}`, borderRadius: 4, padding: compact ? "1px 5px" : "3px 6px", textAlign: "center",
              }}
            >
              {p.side}
            </span>
            <span style={{ fontSize: compact ? 12 : 13, color: "var(--ink)", whiteSpace: "nowrap" }}>{p.asset}</span>
            <span style={{ fontSize: compact ? 11 : 12, color: "var(--muted)" }}>{p.note}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
