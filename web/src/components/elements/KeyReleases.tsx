"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, TILE } from "../ui";

export default function KeyReleases() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <Micro style={{ marginBottom: 9 }}>Key Releases · This Week</Micro>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {v.releases.map((r, i) => (
          <div
            key={`${r.day}-${r.name}-${i}`}
            style={{
              display: "grid", gridTemplateColumns: "34px 1fr auto auto", gap: 10, alignItems: "baseline",
              padding: "5px 0", borderBottom: "1px solid var(--hairline)",
            }}
          >
            <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: r.dayColor }}>{r.day}</span>
            <span style={{ fontSize: 12.5, color: "var(--ink)" }}>{r.name}</span>
            <span style={{ fontSize: 11, color: "var(--muted)" }}>cons</span>
            <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 600 }}>{r.cons}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
