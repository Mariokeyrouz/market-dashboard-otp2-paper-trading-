"use client";

import { Fragment } from "react";
import { useTerminalDerived } from "../TerminalDataContext";
import { useCompact } from "../DensityContext";
import { ItalicNote, MICRO, MONO, PanelTitle, TILE } from "../ui";

// Matches STYLE_FACTOR_ETFS's row-major order (reference/style-factors.ts):
// size (rows) x style (cols), one coherent Vanguard ETF family.
const SIZES = ["Large", "Mid", "Small"];
const STYLES = ["Value", "Blend", "Growth"];

export default function EquityFactors() {
  const v = useTerminalDerived();
  const compact = useCompact();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: compact ? 4 : 8 }}>
        <PanelTitle>US Equity Factors</PanelTitle>
        {!compact && <ItalicNote>size x style, 1D %</ItalicNote>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: `36px repeat(${STYLES.length}, 1fr)`, gap: 4, flex: 1, minHeight: 0 }}>
        <span />
        {STYLES.map((s) => (
          <div key={s} style={{ ...MICRO, textAlign: "center" }}>{s}</div>
        ))}
        {SIZES.map((size, r) => (
          <Fragment key={size}>
            <div style={{ ...MICRO, display: "flex", alignItems: "center" }}>{size}</div>
            {STYLES.map((_, c) => {
              const cell = v.factors[r * STYLES.length + c];
              if (!cell) return <div key={c} />;
              return (
                <div
                  key={cell.ticker}
                  title={cell.name}
                  style={{
                    background: cell.bg, borderRadius: 6, display: "flex", flexDirection: "column",
                    alignItems: "center", justifyContent: "center", padding: compact ? "4px 2px" : "8px 4px", minWidth: 0,
                  }}
                >
                  <span style={{ fontFamily: MONO, fontSize: compact ? 9.5 : 10.5, color: "var(--muted)" }}>{cell.ticker}</span>
                  <span style={{ fontFamily: MONO, fontSize: compact ? 11.5 : 13.5, fontWeight: 600 }}>{cell.chgPct}</span>
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
