"use client";

import { useDerived } from "../DataContext";
import { MONO, Micro, SERIF, Sparkline, TILE } from "../ui";

export default function Hinge() {
  const v = useDerived();
  const h = v.hinge;
  return (
    <div style={{ ...TILE, padding: "9px 13px" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <div style={{ fontFamily: SERIF, fontSize: 22, fontWeight: 600 }}>The Hinge</div>
          <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 14, color: "#8A8172" }}>{h.def}</div>
        </div>
        <span
          style={{
            fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase", fontWeight: 600, color: "#5E7A3B",
            background: "rgba(94,122,59,.1)", border: "1px solid rgba(94,122,59,.3)", borderRadius: 5, padding: "4px 9px",
            whiteSpace: "nowrap",
          }}
        >
          Daily clock · checked daily
        </span>
      </div>
      <div style={{ display: "flex", gap: 24, margin: "8px 0 2px", flexWrap: "wrap" }}>
        {h.legend.map((s) => (
          <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 18, height: 3, borderRadius: 2, background: s.color, display: "inline-block" }} />
            <span style={{ fontSize: 12, color: "#8A8172" }}>{s.name}</span>
            <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600 }}>{s.val}</span>
            <span style={{ fontFamily: MONO, fontSize: 11, color: s.dColor }}>{s.delta}</span>
          </div>
        ))}
      </div>
      <svg viewBox="0 0 700 250" style={{ width: "100%", flex: 1, minHeight: 0, display: "block" }} preserveAspectRatio="none">
        {h.ticks.map((t, i) => (
          <g key={i}>
            <line x1={44} y1={t.y} x2={636} y2={t.y} stroke="rgba(0,0,0,.06)" strokeWidth={1} />
            <text x={644} y={t.ty} fontFamily="var(--font-plex-mono), monospace" fontSize={11} fill="#B4A98F">
              {t.label}
            </text>
          </g>
        ))}
        <path d={h.realArea} fill="rgba(58,107,158,.20)" stroke="none" />
        <path d={h.beArea} fill="rgba(160,123,29,.22)" stroke="none" />
        <path d={h.realPath} fill="none" stroke="#3A6B9E" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <path d={h.nomPath} fill="none" stroke="#2B2721" strokeWidth={2.6} strokeLinejoin="round" strokeLinecap="round" />
        <text x={h.beMid.x} y={h.beMid.y} fontFamily="var(--font-plex-mono), monospace" fontSize={12} fontWeight={600} fill="#8A6A16" textAnchor="end">
          BE {h.beMid.v}
        </text>
        <text x={h.realMid.x} y={h.realMid.y} fontFamily="var(--font-plex-mono), monospace" fontSize={12} fontWeight={600} fill="#2C5480" textAnchor="end">
          real {h.realMid.v}
        </text>
        <circle cx={h.end.x} cy={h.end.y} r={4} fill={h.end.color} />
        <text x={h.end.lx} y={h.end.ly} fontFamily="var(--font-plex-mono), monospace" fontSize={13} fontWeight={600} fill={h.end.color} textAnchor="end">
          {h.end.v}
        </text>
        {h.xTicks.map((x, i) => (
          <text key={i} x={x.x} y={244} fontFamily="var(--font-plex-mono), monospace" fontSize={11} fill="#B4A98F" textAnchor={x.anchor}>
            {x.label}
          </text>
        ))}
      </svg>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8, paddingTop: 9, borderTop: "1px solid rgba(0,0,0,.08)" }}>
        <Micro>Inflation Impulse</Micro>
        <span style={{ fontSize: 12, color: "#8A8172" }}>{h.impulse.name}</span>
        <span style={{ fontFamily: MONO, fontSize: 18, fontWeight: 600 }}>{h.impulse.val}</span>
        <span style={{ fontFamily: MONO, fontSize: 12, color: h.impulse.color }}>{h.impulse.chg}</span>
        <Sparkline d={h.impulse.spark} stroke="#A07B1D" w={120} h={30} />
        <span style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 13, color: "#8A8172" }}>feeds the breakeven leg</span>
      </div>
    </div>
  );
}
