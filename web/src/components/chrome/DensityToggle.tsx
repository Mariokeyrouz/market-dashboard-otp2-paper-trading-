"use client";

import { useDashStore, type DensityOverride } from "@/lib/store";
import { MONO } from "../ui";

const OPTIONS: DensityOverride[] = ["auto", "compact", "comfortable"];
const LABELS: Record<DensityOverride, string> = { auto: "Auto", compact: "Compact", comfortable: "Comfortable" };
const GLYPHS: Record<DensityOverride, string> = { auto: "◧", compact: "▤", comfortable: "▥" };

/**
 * Shared density control, same shape as ThemeToggle: expanded is a
 * three-segment switch, collapsed (rail only) is a single icon that cycles
 * auto → compact → comfortable → auto.
 */
export default function DensityToggle({ collapsed = false }: { collapsed?: boolean }) {
  const density = useDashStore((s) => s.densityOverride);
  const setDensity = useDashStore((s) => s.setDensityOverride);

  if (collapsed) {
    const next = OPTIONS[(OPTIONS.indexOf(density) + 1) % OPTIONS.length];
    return (
      <button
        onClick={() => setDensity(next)}
        aria-label={`Tile density: ${LABELS[density]} — click for ${LABELS[next]}`}
        title={`Tile density: ${LABELS[density]} — click for ${LABELS[next]}`}
        style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          width: "100%", cursor: "pointer", fontSize: 13,
          color: "var(--gold)", background: "transparent",
          border: "1px solid var(--control-border)", borderRadius: 7,
          padding: "6px 0",
        }}
      >
        {GLYPHS[density]}
      </button>
    );
  }

  return (
    <div role="group" aria-label="Tile density" style={{ display: "flex", gap: 4 }}>
      {OPTIONS.map((d) => {
        const active = d === density;
        return (
          <button
            key={d}
            onClick={() => setDensity(d)}
            aria-current={active}
            title={LABELS[d]}
            style={{
              flex: 1, textAlign: "center", cursor: "pointer",
              fontFamily: MONO, fontSize: 9.5, fontWeight: 700,
              color: active ? "var(--gold)" : "var(--body)",
              background: active ? "color-mix(in srgb, var(--gold) 13%, transparent)" : "transparent",
              border: `1px solid ${active ? "color-mix(in srgb, var(--gold) 45%, transparent)" : "var(--control-border)"}`,
              borderRadius: 7, padding: "6px 2px",
            }}
          >
            {LABELS[d]}
          </button>
        );
      })}
    </div>
  );
}
