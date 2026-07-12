"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, TILE } from "../ui";

export default function KeyReleases() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <Micro style={{ marginBottom: 12 }}>Key Releases · This Week</Micro>
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {v.releases.map((r, i) => (
          <div
            key={`${r.day}-${r.name}-${i}`}
            style={{
              display: "grid", gridTemplateColumns: "34px 1fr auto auto", gap: 10, alignItems: "baseline",
              padding: "7px 0", borderBottom: "1px solid rgba(0,0,0,.05)",
            }}
          >
            <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: r.dayColor }}>{r.day}</span>
            <span style={{ fontSize: 12.5, color: "#2B2721" }}>{r.name}</span>
            <span style={{ fontSize: 11, color: "#8A8172" }}>cons</span>
            <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 600 }}>{r.cons}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
