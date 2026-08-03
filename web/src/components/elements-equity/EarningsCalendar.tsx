"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function EarningsCalendar() {
  const v = useEquityDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>Earnings &amp; FOMC Calendar</PanelTitle>
        {!compact && <ItalicNote>next scheduled catalysts</ItalicNote>}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 4 : 7, flex: 1, minHeight: 0, overflow: "hidden" }}>
        {v.events.map((e, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "52px 68px 1fr", gap: 10, alignItems: "baseline" }}>
            <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, color: "var(--muted)" }}>{e.dateLabel}</span>
            <span
              style={{
                fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: ".04em", textAlign: "center",
                color: e.kindColor, border: `1px solid color-mix(in srgb, ${e.kindColor} 40%, transparent)`,
                borderRadius: 4, padding: "1px 6px", whiteSpace: "nowrap", justifySelf: "start",
              }}
            >
              {e.kindLabel}
            </span>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: compact ? 11.5 : 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {e.label}
              </div>
              {!compact && <div style={{ fontSize: 11, color: "var(--muted)" }}>{e.detail}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
