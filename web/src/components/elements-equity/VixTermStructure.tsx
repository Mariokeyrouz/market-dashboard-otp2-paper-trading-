"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { MONO, PanelTitle, TILE } from "../ui";

export default function VixTermStructure() {
  const v = useEquityDerived();
  const x = v.vix;
  const compact = useCompact();
  const y18 = Number(x.refLine18);
  const y25 = Number(x.refLine25);
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 4 }}>
        <PanelTitle>VIX &amp; Term Structure</PanelTitle>
        <span
          style={{
            fontSize: 10, letterSpacing: ".1em", textTransform: "uppercase", fontWeight: 600, color: x.termColor,
            border: `1px solid color-mix(in srgb, ${x.termColor} 45%, transparent)`, borderRadius: 5, padding: "3px 8px",
            whiteSpace: "nowrap",
          }}
        >
          {x.termLabel}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 20, flexWrap: "wrap", marginBottom: compact ? 6 : 10 }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 32 : 40, fontWeight: 600, color: x.levelColor, lineHeight: 1 }}>
          {x.level}
        </span>
        <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 10, letterSpacing: ".1em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
              vs VIX3M
            </div>
            <div style={{ fontFamily: MONO, fontSize: 15, fontWeight: 600, color: x.spreadVix3mColor }}>{x.spreadVix3m}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, letterSpacing: ".1em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
              vs VIX9D
            </div>
            <div style={{ fontFamily: MONO, fontSize: 15, fontWeight: 600, color: x.spreadVix9dColor }}>{x.spreadVix9d}</div>
          </div>
        </div>
      </div>
      <svg viewBox="0 0 300 100" style={{ width: "100%", flex: 1, minHeight: 0, display: "block" }} preserveAspectRatio="none">
        <line x1={6} y1={y25} x2={294} y2={y25} stroke="var(--red)" strokeWidth={1} strokeDasharray="2 3" opacity={0.55} />
        <line x1={6} y1={y18} x2={294} y2={y18} stroke="var(--amber)" strokeWidth={1} strokeDasharray="2 3" opacity={0.55} />
        <text x={296} y={y25 - 2} fontFamily="var(--font-plex-mono), monospace" fontSize={8} fill="var(--red)" textAnchor="end">25</text>
        <text x={296} y={y18 - 2} fontFamily="var(--font-plex-mono), monospace" fontSize={8} fill="var(--amber)" textAnchor="end">18</text>
        <path d={x.historyPath} fill="none" stroke={x.levelColor} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontFamily: MONO, fontSize: 9.5, color: "var(--faint)", marginTop: 2 }}>
        <span>{x.historyStartLabel}</span>
        <span>Today</span>
      </div>
      {!compact && (
        <div style={{ fontFamily: "var(--font-newsreader), serif", fontStyle: "italic", fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
          {x.termLabel === "Backwardation"
            ? "Near-term VIX pricier than the 3-month — the market is paying up for near-dated protection."
            : "Normal calm-market shape — near-term vol priced below the 3-month."}
        </div>
      )}
    </div>
  );
}
