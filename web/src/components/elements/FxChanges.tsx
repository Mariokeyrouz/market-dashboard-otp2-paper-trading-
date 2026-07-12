"use client";

import { useDerived } from "../DataContext";
import { DivergingBar, ItalicNote, MONO, PanelTitle, TILE } from "../ui";

export default function FxChanges() {
  const v = useDerived();
  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <PanelTitle>FX Changes</PanelTitle>
        <ItalicNote>Δ 1D · YTD %</ItalicNote>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {v.fx.map((f) => (
          <div
            key={f.pair}
            style={{
              display: "grid", gridTemplateColumns: "74px 1fr 54px 54px", gap: 10, alignItems: "center",
              padding: "6px 0", borderBottom: "1px solid rgba(0,0,0,.05)",
            }}
          >
            <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 500, color: "#2B2721" }}>{f.pair}</span>
            <DivergingBar barLeft={f.barLeft} barW={f.barW} color={f.barColor} height={8} track="rgba(0,0,0,.05)" />
            <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, textAlign: "right", color: f.d1Color }}>{f.d1}</span>
            <span style={{ fontFamily: MONO, fontSize: 12, textAlign: "right", color: f.ytdColor }}>{f.ytd}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
