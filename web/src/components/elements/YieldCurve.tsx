"use client";

import { useDerived } from "../DataContext";
import { MONO, PanelTitle, SERIF, TILE } from "../ui";

export default function YieldCurve() {
  const v = useDerived();
  const c = v.curve;
  const spread = (label: string, val: string, color: string) => (
    <span style={{ fontSize: 11, color: "var(--muted)" }}>
      {label} <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600, color }}>{val}</span>
    </span>
  );
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 2 }}>
        <PanelTitle>Yield Curve</PanelTitle>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 14, height: 2.6, background: "var(--gold)", borderRadius: 2 }} />
            <span style={{ fontSize: 10, color: "var(--muted)" }}>now</span>
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 14, height: 0, borderTop: "2px dashed var(--faint)" }} />
            <span style={{ fontSize: 10, color: "var(--muted)" }}>1w ago</span>
          </span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, marginBottom: 8, alignItems: "center", flexWrap: "wrap" }}>
        {spread("2s10s", c.spread, c.spreadColor)}
        {spread("5s30s", c.spread3, c.spread3Color)}
        {spread("3m10s", c.spread2, c.spread2Color)}
        <span style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12, color: "var(--muted)", marginLeft: "auto" }}>{c.shape}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 7, marginBottom: 8 }}>
        {c.tenors.map((k) => (
          <div key={k.t} style={{ border: "1px solid var(--hairline)", borderRadius: 7, padding: "5px 9px" }}>
            <div style={{ fontSize: 9, letterSpacing: ".11em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>{k.t}</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 1 }}>
              <span style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600 }}>{k.v}</span>
              <span style={{ fontFamily: MONO, fontSize: 10, color: k.bpColor }}>{k.bp}</span>
            </div>
          </div>
        ))}
      </div>
      <svg viewBox="0 0 460 210" style={{ width: "100%", flex: 1, minHeight: 0, display: "block" }} preserveAspectRatio="none">
        {c.ticks.map((t, i) => (
          <g key={i}>
            <line x1={42} y1={t.y} x2={446} y2={t.y} stroke="var(--hairline)" strokeWidth={1} />
            <text x={37} y={t.ty} fontFamily="var(--font-plex-mono), monospace" fontSize={10} fill="var(--faint)" textAnchor="end">
              {t.label}
            </text>
          </g>
        ))}
        <line x1={42} y1={22} x2={42} y2={176} stroke="var(--strong-line)" strokeWidth={1} />
        <line x1={42} y1={176} x2={446} y2={176} stroke="var(--strong-line)" strokeWidth={1} />
        <path d={c.prevPath} fill="none" stroke="var(--faint)" strokeWidth={1.8} strokeDasharray="4 4" strokeLinejoin="round" strokeLinecap="round" />
        <path d={c.path} fill="none" stroke="var(--gold)" strokeWidth={2.6} strokeLinejoin="round" strokeLinecap="round" />
        {c.pts.map((p) => (
          <g key={p.t}>
            <circle cx={p.x} cy={p.y} r={3.2} fill="var(--gold)" />
            <text x={p.x} y={p.vy} fontFamily="var(--font-plex-mono), monospace" fontSize={9.5} fontWeight={600} fill="var(--gold-deep)" textAnchor="middle">
              {p.v}
            </text>
            <text x={p.x} y={190} fontFamily="var(--font-plex-mono), monospace" fontSize={10} fill="var(--muted)" textAnchor="middle">
              {p.t}
            </text>
          </g>
        ))}
        <text x={6} y={18} fontFamily="var(--font-plex-sans), sans-serif" fontSize={9} fill="var(--faint)">
          yield %
        </text>
        <text x={446} y={205} fontFamily="var(--font-plex-sans), sans-serif" fontSize={9} fill="var(--faint)" textAnchor="end">
          tenor
        </text>
      </svg>
    </div>
  );
}
