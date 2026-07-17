"use client";

import { useDerived } from "../DataContext";
import { useCompact } from "../DensityContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

export default function CbCountdown() {
  const v = useDerived();
  const cb = v.cb;
  // Compact collapses the header to one line and drops the "Market-implied"
  // label row — countdown, bar, and priced probability all survive.
  const compact = useCompact();
  return (
    <div style={TILE}>
      {compact ? (
        <div style={{ fontFamily: SERIF, fontSize: 13.5, fontWeight: 600, marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {cb.name}
        </div>
      ) : (
        <>
          <Micro>Next Policy Meeting</Micro>
          <div style={{ fontFamily: SERIF, fontSize: 18, fontWeight: 600, margin: "6px 0 9px" }}>{cb.name}</div>
        </>
      )}
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 22 : 32, fontWeight: 600, lineHeight: 1 }}>{cb.days}</span>
        <span style={{ fontSize: compact ? 12 : 13, color: "var(--muted)" }}>days · {cb.date}</span>
        {compact && <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, marginLeft: "auto" }}>{cb.action}</span>}
      </div>
      <div style={{ marginTop: "auto", paddingTop: compact ? 5 : 9, borderTop: compact ? "none" : "1px solid var(--hairline)" }}>
        {!compact && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
            <span style={{ color: "var(--muted)" }}>Market-implied</span>
            <span style={{ fontFamily: MONO, fontWeight: 600 }}>{cb.action}</span>
          </div>
        )}
        <div style={{ height: 7, borderRadius: 4, background: "var(--hairline)", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${cb.prob}%`, background: v.classification.color }} />
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: compact ? 3 : 5 }}>
          <span style={{ fontFamily: MONO, color: "var(--ink)", fontWeight: 600 }}>{cb.prob}%</span> priced for {cb.move}
        </div>
      </div>
    </div>
  );
}
