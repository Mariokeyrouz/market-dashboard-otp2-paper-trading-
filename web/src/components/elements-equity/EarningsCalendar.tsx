"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";
import type { EquityDerived } from "@/lib/derive-equity";

function EventRow({ e, compact }: { e: EquityDerived["events"][number]; compact: boolean }) {
  const near = e.dateLabel === "Today" || e.dateLabel === "Tomorrow";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "52px 68px 1fr", gap: 10, alignItems: "baseline" }}>
      <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, fontWeight: near ? 700 : 400, color: near ? "var(--gold)" : "var(--muted)" }}>
        {e.dateLabel}
      </span>
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
        <div style={{ fontSize: compact ? 10 : 11, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.detail}</div>
      </div>
    </div>
  );
}

export default function EarningsCalendar() {
  const v = useEquityDerived();
  const compact = useCompact();
  const half = Math.ceil(v.events.length / 2);
  const left = v.events.slice(0, half);
  const right = v.events.slice(half);
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>Earnings &amp; FOMC Calendar</PanelTitle>
        {!compact && <ItalicNote>next scheduled catalysts</ItalicNote>}
      </div>
      <div style={{ display: "flex", gap: 24, flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 5 : 9, minWidth: 0, overflow: "hidden" }}>
          {left.map((e, i) => (
            <EventRow key={i} e={e} compact={compact} />
          ))}
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: compact ? 5 : 9, minWidth: 0, overflow: "hidden" }}>
          {right.map((e, i) => (
            <EventRow key={i} e={e} compact={compact} />
          ))}
        </div>
      </div>
    </div>
  );
}
