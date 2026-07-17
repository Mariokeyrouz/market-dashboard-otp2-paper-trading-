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
              borderRadius: 11, padding: compact ? "6px 11px" : "9px 12px", overflow: "hidden",
            }}
          >
            <div style={{ fontSize: 10, letterSpacing: ".11em", textTransform: "uppercase", fontWeight: 600, color: "var(--muted)" }}>
              {t.label}
            </div>
            {!compact && (
              <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12.5, color: "var(--muted)", margin: "4px 0 7px" }}>{t.tag}</div>
            )}
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: compact ? 4 : 0 }}>
              <span style={{ fontFamily: MONO, fontSize: compact ? 19 : 22, fontWeight: 600 }}>{t.val}</span>
              <span style={{ fontFamily: MONO, fontSize: 12, color: t.chgColor }}>{t.chg}</span>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>{t.state}</span>
            </div>
            {!compact && (
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 7, lineHeight: 1.4 }}>{t.note}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
