"use client";

import { useMemo } from "react";
import { deriveMatrix } from "@/lib/derive";
import { useDashStore } from "@/lib/store";
import { ItalicNote, MICRO, MONO, PanelTitle, TILE } from "../ui";

/**
 * Cross-region comparison matrix. Unlike every other element this one reads
 * *all* regions rather than the one it's handed, so it deliberately ignores
 * both the global lens and any POV pin (see `crossRegion` in the registry).
 * The lens only decides which row is highlighted; clicking a row moves it.
 */
export default function MacroMatrix() {
  const m = useMemo(() => deriveMatrix(), []);
  const region = useDashStore((s) => s.region);
  const setRegion = useDashStore((s) => s.setRegion);

  const cols = `minmax(104px,1.15fr) minmax(92px,auto) repeat(${m.cols.length}, minmax(46px,1fr))`;

  return (
    <div style={TILE}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 7 }}>
        <PanelTitle>Macro Matrix</PanelTitle>
        <ItalicNote>every region at once · click a row to move the lens</ItalicNote>
      </div>

      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ minWidth: 720 }}>
          {/* header row */}
          <div
            style={{
              display: "grid", gridTemplateColumns: cols, gap: 8, alignItems: "end",
              padding: "0 7px 3px", borderBottom: "1px solid var(--hairline)",
            }}
          >
            <span style={MICRO}>Region</span>
            <span style={MICRO}>Regime</span>
            {m.cols.map((c) => (
              <span key={c.key} style={{ ...MICRO, textAlign: "right" }}>
                {c.label}
              </span>
            ))}
          </div>

          {m.rows.map((r) => {
            const active = r.region === region;
            return (
              <button
                key={r.region}
                onClick={() => setRegion(r.region)}
                aria-label={`Switch the region lens to ${r.label}`}
                aria-current={active}
                style={{
                  display: "grid", gridTemplateColumns: cols, gap: 8, alignItems: "center",
                  width: "100%", textAlign: "left", cursor: "pointer",
                  font: "inherit", padding: "3px 7px",
                  background: active ? "color-mix(in srgb, var(--gold) 11%, transparent)" : "transparent",
                  border: "none",
                  borderBottom: "1px solid var(--hairline)",
                  // Global is an aggregate — visually detached from the peer economies above.
                  borderTop: r.isAgg ? "1px solid var(--control-border)" : undefined,
                  boxShadow: active ? "inset 2px 0 0 var(--gold)" : undefined,
                }}
              >
                <span style={{ fontSize: 11.5, color: "var(--ink)", fontWeight: active ? 600 : 400 }}>
                  {r.label}
                </span>
                <span
                  style={{
                    justifySelf: "start", fontFamily: MONO, fontSize: 9.5, fontWeight: 600,
                    color: r.regime.color, letterSpacing: ".03em",
                    border: `1px solid color-mix(in srgb, ${r.regime.color} 45%, transparent)`,
                    borderRadius: 4, padding: "0 6px", whiteSpace: "nowrap",
                  }}
                >
                  {r.regime.label}
                </span>
                {r.cells.map((c) => (
                  <span
                    key={c.key}
                    style={{
                      fontFamily: MONO, fontSize: 11, fontWeight: 600,
                      textAlign: "right", color: c.color, whiteSpace: "nowrap",
                    }}
                  >
                    {c.txt}
                  </span>
                ))}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
