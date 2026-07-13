"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

export default function Classification() {
  const v = useDerived();
  const c = v.classification;
  return (
    <div style={{ ...TILE, borderLeft: `4px solid ${c.color}` }}>
      <Micro style={{ letterSpacing: ".14em" }}>Classification</Micro>
      <div style={{ display: "flex", alignItems: "center", gap: 9, margin: "7px 0 6px" }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: c.color }} />
        <span style={{ fontFamily: SERIF, fontSize: 21, fontWeight: 600, color: c.color }}>{c.label}</span>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--body)" }}>{c.desc}</div>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginTop: 9 }}>
        {c.tags.map((tag) => (
          <span
            key={tag}
            style={{
              fontFamily: MONO, fontSize: 11, color: "var(--gold)",
              border: "1px solid rgba(160,123,29,.4)", borderRadius: 5, padding: "3px 8px",
            }}
          >
            {tag}
          </span>
        ))}
      </div>
      <div style={{ marginTop: "auto", paddingTop: 9, borderTop: "1px solid var(--hairline)", fontSize: 11, color: "var(--muted)" }}>
        Dominant mover: <span style={{ color: "var(--ink)", fontWeight: 600 }}>{c.mover}</span> · lookback 5d
      </div>
    </div>
  );
}
