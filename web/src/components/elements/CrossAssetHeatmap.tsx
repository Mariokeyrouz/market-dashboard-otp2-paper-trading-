"use client";

import { Fragment } from "react";
import { useDerived } from "../DataContext";
import { ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function CrossAssetHeatmap() {
  const v = useDerived();
  const h = v.heatmap;
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
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
              color: "#8A8172", textAlign: "center", paddingBottom: 4,
            }}
          >
            {c}
          </div>
        ))}
        {h.rows.map((r) => (
          <Fragment key={r.name}>
            <div style={{ fontSize: 12, color: "#2B2721", display: "flex", alignItems: "center", padding: "0 2px", whiteSpace: "nowrap" }}>
              {r.name}
            </div>
            {r.cells.map((cell, i) => (
              <div
                key={i}
                style={{
                  fontFamily: MONO, fontSize: 12.5, fontWeight: 500, textAlign: "center",
                  padding: "4px 4px", borderRadius: 5, background: cell.bg, color: cell.fg,
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
