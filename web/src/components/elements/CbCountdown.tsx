"use client";

import { useDerived } from "../DataContext";
import { useCompact } from "../DensityContext";
import { MONO, Micro, SERIF, TILE } from "../ui";

/**
 * The market-implied rate-path bar (probability + "priced for a cut") was
 * dropped — that's CME FedWatch-style data with no free live source. Shows
 * the actual live Fed Funds target range instead (v.metrics.policy), which
 * is real and obtainable (FRED DFEDTARL/DFEDTARU).
 */
export default function CbCountdown() {
  const v = useDerived();
  const cb = v.cb;
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
        {compact && <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, marginLeft: "auto" }}>{v.metrics.policy}</span>}
      </div>
      <div style={{ marginTop: "auto", paddingTop: compact ? 5 : 9, borderTop: compact ? "none" : "1px solid var(--hairline)" }}>
        {!compact && (
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span style={{ color: "var(--muted)" }}>Current target range</span>
            <span style={{ fontFamily: MONO, fontWeight: 600 }}>{v.metrics.policy}</span>
          </div>
        )}
        {!compact && (
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>{v.metrics.policySub}</div>
        )}
      </div>
    </div>
  );
}
