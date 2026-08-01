"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function EquityIndices() {
  const v = useEquityDerived();
  const idx = v.indices;
  // Compact drops the in-chart axis labels — the legend row above already
  // carries every level/delta — same tradeoff Hinge/YieldCurve make.
  const compact = useCompact();
  return (
    <div style={{ ...TILE, padding: "8px 12px" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <PanelTitle>Equity Indices</PanelTitle>
        {!compact && <ItalicNote>{idx.windowLabel}</ItalicNote>}
      </div>
      <div style={{ display: "flex", gap: 18, margin: "6px 0 2px", flexWrap: "wrap" }}>
        {idx.legend.map((s) => (
          <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 18, height: 3, borderRadius: 2, background: s.color, display: "inline-block" }} />
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{s.name}</span>
            <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600 }}>{s.val}</span>
            <span style={{ fontFamily: MONO, fontSize: 11, color: s.dColor }}>{s.delta}</span>
          </div>
        ))}
      </div>
      <svg viewBox="0 0 700 220" style={{ width: "100%", flex: 1, minHeight: 0, display: "block" }} preserveAspectRatio="none">
        {idx.ticks.map((t, i) => (
          <g key={i}>
            <line x1={44} y1={t.y} x2={680} y2={t.y} stroke="var(--hairline)" strokeWidth={1} />
            {!compact && (
              <text x={688} y={t.ty} fontFamily="var(--font-plex-mono), monospace" fontSize={10} fill="var(--faint)">
                {t.label}
              </text>
            )}
          </g>
        ))}
        {idx.paths.map((p) => (
          <path key={p.name} d={p.d} fill="none" stroke={p.color} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {!compact &&
          idx.xTicks.map((x, i) => (
            <text key={i} x={x.x} y={214} fontFamily="var(--font-plex-mono), monospace" fontSize={10.5} fill="var(--faint)" textAnchor={x.anchor}>
              {x.label}
            </text>
          ))}
      </svg>
    </div>
  );
}
