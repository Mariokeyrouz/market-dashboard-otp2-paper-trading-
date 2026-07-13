"use client";

import { Fragment } from "react";
import { useDerived } from "../DataContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function CrossAssetHeatmap() {
  const v = useDerived();
  const h = v.heatmap;
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 9 }}>
        <PanelTitle>Cross-Asset Heatmap</PanelTitle>
        <ItalicNote>total return, %</ItalicNote>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr repeat(4,1fr)", gap: 4 }}>
        <div />
        {h.cols.map((c) => (
          <div
            key={c}
            style={{
              fontSize: 10, letterSpacing: ".08em", textTransform: "uppercase", fontWeight: 600,
              color: "var(--muted)", textAlign: "center", paddingBottom: 4,
            }}
          >
            {c}
          </div>
        ))}
        {h.rows.map((r) => (
          <Fragment key={r.name}>
            <div style={{ fontSize: 12, color: "var(--ink)", display: "flex", alignItems: "center", padding: "0 2px", whiteSpace: "nowrap" }}>
              {r.name}
            </div>
            {r.cells.map((cell, i) => (
              <div
                key={i}
                style={{
                  fontFamily: MONO, fontSize: 12.5, fontWeight: 500, textAlign: "center",
                  padding: "3px 4px", borderRadius: 5, background: cell.bg, color: cell.fg,
                }}
              >
                {cell.txt}
              </div>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
