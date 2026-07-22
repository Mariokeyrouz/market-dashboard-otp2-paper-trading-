"use client";

import { useDerived } from "../DataContext";
import { useCompact } from "../DensityContext";
import { MONO, SERIF } from "../ui";

export default function Tripwires() {
  const v = useDerived();
  // Compact drops the taglines and notes; a tripwire that shows its label and
  // level has done its job — a tripwire that crops its level has not.
  const compact = useCompact();
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", boxSizing: "border-box" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: compact ? 4 : 6 }}>
        <div style={{ fontFamily: SERIF, fontSize: compact ? 17 : 20, fontWeight: 600 }}>Risk Tripwires</div>
        {!compact && (
          <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 13, color: "var(--muted)" }}>
            faster confirming signals — directional, not mechanically precise
          </div>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, flex: 1, minHeight: 0 }}>
        {v.tripwires.map((t) => (
          <div
            key={t.label}
            style={{
              background: "var(--tile)", border: "1px solid var(--tile-border)", borderTop: `3px solid ${t.tone}`,
              borderRadius: 11, padding: compact ? "5px 10px" : "9px 12px", overflow: "hidden",
              // Spread label→value→note across the card height so tall cards fill
              // instead of stranding content at the top.
              display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 2,
            }}
          >
            <div>
              <div style={{ fontSize: 10, letterSpacing: ".11em", textTransform: "uppercase", fontWeight: 600, color: "var(--muted)" }}>
                {t.label}
              </div>
              {!compact && (
                <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12.5, color: "var(--muted)", marginTop: 4 }}>{t.tag}</div>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontFamily: MONO, fontSize: compact ? 19 : 22, fontWeight: 600 }}>{t.val}</span>
              <span style={{ fontFamily: MONO, fontSize: 12, color: t.chgColor }}>{t.chg}</span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>{t.state}</span>
            </div>
            {/* The note always shows: it's a third element that lets the card
                fill its height via space-between instead of stranding a big gap. */}
            <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.25 }}>{t.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
