"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

export default function CbCountdown() {
  const v = useDerived();
  const cb = v.cb;
  return (
    <div style={TILE}>
      <Micro>Next Policy Meeting</Micro>
      <div style={{ fontFamily: SERIF, fontSize: 18, fontWeight: 600, margin: "8px 0 12px" }}>{cb.name}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontFamily: MONO, fontSize: 32, fontWeight: 600, lineHeight: 1 }}>{cb.days}</span>
        <span style={{ fontSize: 13, color: "#8A8172" }}>days · {cb.date}</span>
      </div>
      <div style={{ marginTop: "auto", paddingTop: 12, borderTop: "1px solid rgba(0,0,0,.08)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
          <span style={{ color: "#8A8172" }}>Market-implied</span>
          <span style={{ fontFamily: MONO, fontWeight: 600 }}>{cb.action}</span>
        </div>
        <div style={{ height: 7, borderRadius: 4, background: "rgba(0,0,0,.08)", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${cb.prob}%`, background: v.classification.color }} />
        </div>
        <div style={{ fontSize: 11, color: "#8A8172", marginTop: 5 }}>
          <span style={{ fontFamily: MONO, color: "#2B2721", fontWeight: 600 }}>{cb.prob}%</span> priced for {cb.move}
        </div>
      </div>
    </div>
  );
}
