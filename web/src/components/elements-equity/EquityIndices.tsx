"use client";

import { useRef, useState, type MouseEvent } from "react";
import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";
import type { IndicesTimeframe } from "@/lib/derive-equity";

const TIMEFRAMES: IndicesTimeframe[] = ["1M", "3M", "1Y"];

export default function EquityIndices() {
  const v = useEquityDerived();
  const compact = useCompact();
  const [tf, setTf] = useState<IndicesTimeframe>("1M");
  const [hoverI, setHoverI] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const idx = v.indices[tf];

  const handleMove = (e: MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) return;
    const relX = ((e.clientX - rect.left) / rect.width) * 700;
    let nearest = 0;
    let best = Infinity;
    idx.xs.forEach((x, i) => {
      const dist = Math.abs(x - relX);
      if (dist < best) {
        best = dist;
        nearest = i;
      }
    });
    setHoverI(nearest);
  };

  return (
    <div style={{ ...TILE, padding: "8px 12px" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
        <PanelTitle>Equity Indices</PanelTitle>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          {!compact && <ItalicNote>{idx.windowLabel}</ItalicNote>}
          <div role="group" aria-label="Chart timeframe" style={{ display: "flex", gap: 3 }}>
            {TIMEFRAMES.map((t) => {
              const active = t === tf;
              return (
                <button
                  key={t}
                  onClick={() => {
                    setTf(t);
                    setHoverI(null);
                  }}
                  aria-current={active}
                  style={{
                    fontFamily: MONO, fontSize: 9.5, fontWeight: 700, cursor: "pointer",
                    padding: "3px 7px", borderRadius: 6,
                    color: active ? "var(--gold)" : "var(--body)",
                    background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
                    border: `1px solid ${active ? "color-mix(in srgb, var(--gold) 45%, transparent)" : "var(--control-border)"}`,
                  }}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", gap: 18, margin: "6px 0 2px", flexWrap: "wrap" }}>
        {idx.legend.map((s, i) => (
          <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <span style={{ width: 18, height: 3, borderRadius: 2, background: s.color, display: "inline-block" }} />
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{s.name}</span>
            <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600 }}>
              {hoverI !== null ? idx.series[i].values[hoverI].toFixed(1) : s.val}
            </span>
            {hoverI === null && <span style={{ fontFamily: MONO, fontSize: 11, color: s.dColor }}>{s.delta}</span>}
          </div>
        ))}
      </div>
      <svg
        ref={svgRef}
        viewBox="0 0 700 220"
        style={{ width: "100%", flex: 1, minHeight: 0, display: "block", cursor: "crosshair" }}
        preserveAspectRatio="none"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverI(null)}
      >
        {idx.ticks.map((t, i) => (
          <g key={i}>
            <line x1={44} y1={t.y} x2={680} y2={t.y} stroke="var(--hairline)" strokeWidth={1} />
            <text x={696} y={t.ty} fontFamily="var(--font-plex-mono), monospace" fontSize={9.5} fill="var(--faint)" textAnchor="end">
              {t.label}
            </text>
          </g>
        ))}
        {idx.series.map((s) => (
          <path key={s.name} d={s.d} fill="none" stroke={s.color} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {hoverI !== null && (
          <>
            <line x1={idx.xs[hoverI]} y1={18} x2={idx.xs[hoverI]} y2={194} stroke="var(--muted)" strokeWidth={1} strokeDasharray="2 3" />
            {idx.series.map((s) => (
              <circle key={s.name} cx={idx.xs[hoverI]} cy={s.ys[hoverI]} r={3.2} fill={s.color} stroke="var(--tile)" strokeWidth={1.2} />
            ))}
          </>
        )}
        {idx.xTicks.map((x, i) => (
          <text key={i} x={x.x} y={214} fontFamily="var(--font-plex-mono), monospace" fontSize={10} fill="var(--faint)" textAnchor={x.anchor}>
            {x.label}
          </text>
        ))}
      </svg>
      <div style={{ fontFamily: MONO, fontSize: 10.5, color: "var(--muted)", textAlign: "right", marginTop: 2, height: 14 }}>
        {hoverI !== null ? idx.dates[hoverI] : ""}
      </div>
    </div>
  );
}
