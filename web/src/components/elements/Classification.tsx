"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

export default function Classification() {
  const v = useDerived();
  const c = v.classification;
  return (
    <div style={{ ...TILE, borderLeft: `4px solid ${c.color}` }}>
      <Micro style={{ letterSpacing: ".14em" }}>Classification</Micro>
      <div style={{ display: "flex", alignItems: "center", gap: 9, margin: "9px 0 8px" }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: c.color }} />
        <span style={{ fontFamily: SERIF, fontSize: 21, fontWeight: 600, color: c.color }}>{c.label}</span>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5, color: "#4A443B" }}>{c.desc}</div>
      <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginTop: 12 }}>
        {c.tags.map((tag) => (
          <span
            key={tag}
            style={{
              fontFamily: MONO, fontSize: 11, color: "#A07B1D",
              border: "1px solid rgba(160,123,29,.4)", borderRadius: 5, padding: "3px 8px",
            }}
          >
            {tag}
          </span>
        ))}
      </div>
      <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid rgba(0,0,0,.08)", fontSize: 11, color: "#8A8172" }}>
        Dominant mover: <span style={{ color: "#2B2721", fontWeight: 600 }}>{c.mover}</span> · lookback 5d
      </div>
    </div>
  );
}
