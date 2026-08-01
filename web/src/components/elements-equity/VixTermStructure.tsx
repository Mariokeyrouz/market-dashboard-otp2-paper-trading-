"use client";

import { useEquityDerived } from "../EquityDataContext";
import { useCompact } from "../DensityContext";
import { MONO, PanelTitle, Sparkline, TILE } from "../ui";

export default function VixTermStructure() {
  const v = useEquityDerived();
  const x = v.vix;
  const compact = useCompact();
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
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: compact ? 8 : 14 }}>
        <span style={{ fontFamily: MONO, fontSize: compact ? 32 : 42, fontWeight: 600, color: x.levelColor, lineHeight: 1 }}>
          {x.level}
        </span>
        <Sparkline d={x.spark} stroke={x.levelColor} w={90} h={26} />
      </div>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: ".1em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
            vs VIX3M
          </div>
          <div style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: x.spreadVix3mColor }}>{x.spreadVix3m}</div>
        </div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: ".1em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600 }}>
            vs VIX9D
          </div>
          <div style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color: x.spreadVix9dColor }}>{x.spreadVix9d}</div>
        </div>
      </div>
      {!compact && (
        <div style={{ fontFamily: "var(--font-newsreader), serif", fontStyle: "italic", fontSize: 12.5, color: "var(--muted)", marginTop: "auto", paddingTop: 8 }}>
          {x.termLabel === "Backwardation"
            ? "Near-term VIX pricier than the 3-month — the market is paying up for near-dated protection."
            : "Normal calm-market shape — near-term vol priced below the 3-month."}
        </div>
      )}
    </div>
  );
}
