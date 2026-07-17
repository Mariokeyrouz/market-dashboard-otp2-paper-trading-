"use client";

import { REGION_LABELS } from "@/lib/data/types";
import { ELEMENT_MAP, Z_ROLE_LABELS, type ZRole } from "@/lib/elements/registry";
import { useDashStore } from "@/lib/store";
import { MONO, SERIF } from "../ui";

const ROLE_COLORS: Record<ZRole, string> = {
  anchor: "var(--gold)",
  scan: "var(--amber)",
  pivot: "var(--ink)",
  terminal: "var(--green)",
  support: "var(--muted)",
};

/** Small Z diagram showing the reading order. */
function ZDiagram() {
  const lbl = (x: number, y: number, t: string, anchor: "start" | "end" | "middle" = "start") => (
    <text x={x} y={y} fontSize={9.5} fill="var(--muted)" textAnchor={anchor} fontFamily="var(--font-plex-sans), sans-serif">
      {t}
    </text>
  );
  return (
    <svg viewBox="0 0 320 150" style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={8} y={8} width={304} height={134} rx={10} fill="var(--tile)" stroke="var(--tile-border)" />
      <path d="M40 36 L280 36 L40 114 L280 114" fill="none" stroke="var(--gold)" strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" strokeDasharray="1 6" />
      <circle cx={40} cy={36} r={5} fill="var(--gold)" />
      <circle cx={280} cy={36} r={5} fill="var(--amber)" />
      <circle cx={40} cy={114} r={5} fill="var(--ink)" />
      <circle cx={280} cy={114} r={5} fill="var(--green)" />
      {lbl(52, 30, "1 · Regime — where are we?")}
      {lbl(268, 30, "2 · Classification — the signal", "end")}
      {lbl(120, 72, "3 · The Hinge — why it's moving")}
      {lbl(52, 132, "4 · Tripwires — confirm / deny")}
      {lbl(268, 132, "5 · Calendar — what's next", "end")}
    </svg>
  );
}

/**
 * The explainer's body, with no drawer chrome of its own — so the same
 * narration can be docked in the right rail on a wide screen or shown in the
 * overlay drawer when there's no room to dock it.
 */
export default function LogicContent() {
  const layout = useDashStore((s) => s.layout);
  const hidden = useDashStore((s) => s.hidden);
  const pins = useDashStore((s) => s.pins);

  // Narrate elements in their *current* visual order (top-left → bottom-right).
  const ordered = [...layout]
    .filter((l) => !hidden.includes(l.i))
    .sort((a, b) => a.y - b.y || a.x - b.x)
    .map((l) => ELEMENT_MAP.get(l.i))
    .filter((d) => d !== undefined);

  return (
    <>
      <p style={{ fontSize: 13, lineHeight: 1.55, color: "var(--body)", margin: "0 0 12px" }}>
        The default arrangement follows a <strong>Z-pattern</strong> — the natural path a reader&apos;s eye takes across a
        page: enter top-left, sweep right, cut diagonally down, sweep right again.
        Each stop on that path answers the next question a macro investor asks.
      </p>
      <ZDiagram />
      <p style={{ fontSize: 13, lineHeight: 1.55, color: "var(--body)", margin: "12px 0 6px" }}>
        <strong>1 · Where are we?</strong> (regime, top-left) → <strong>2 · What&apos;s the signal?</strong> (classification,
        top-right) → <strong>3 · Why?</strong> (the Hinge decomposition on the diagonal) →{" "}
        <strong>4 · Is it confirmed?</strong> (tripwires, the bottom stroke) → <strong>5 · What&apos;s next?</strong>{" "}
        (calendar, bottom-right exit). Everything else is supporting evidence you consult on demand.
      </p>

      <div style={{ fontSize: 10, letterSpacing: ".13em", color: "var(--muted)", textTransform: "uppercase", fontWeight: 600, margin: "18px 0 8px" }}>
        Elements — in your current order
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {ordered.map((d) => (
          <div key={d.id} style={{ borderBottom: "1px solid var(--hairline)", paddingBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3, flexWrap: "wrap" }}>
              <span style={{ fontFamily: SERIF, fontSize: 14.5, fontWeight: 600 }}>{d.title}</span>
              <span
                style={{
                  fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: ".04em",
                  color: ROLE_COLORS[d.zRole],
                  border: `1px solid color-mix(in srgb, ${ROLE_COLORS[d.zRole]} 40%, transparent)`,
                  borderRadius: 4, padding: "1px 6px", whiteSpace: "nowrap",
                }}
              >
                {Z_ROLE_LABELS[d.zRole]}
              </span>
              {/* This panel claims to describe what's actually on screen, so a
                  pinned tile has to be called out or the narration is wrong. */}
              {pins[d.id] && !d.crossRegion && (
                <span
                  style={{
                    fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: ".04em",
                    color: "var(--gold)",
                    border: "1px solid color-mix(in srgb, var(--gold) 40%, transparent)",
                    borderRadius: 4, padding: "1px 6px", whiteSpace: "nowrap",
                  }}
                >
                  POV · {REGION_LABELS[pins[d.id]]}
                </span>
              )}
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.5, color: "var(--body)" }}>{d.logic}</div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 16, fontSize: 11.5, lineHeight: 1.5, color: "var(--muted)",
          border: "1px solid rgba(160,123,29,.35)", borderRadius: 8, padding: "9px 12px", background: "rgba(160,123,29,.06)",
        }}
      >
        This hierarchy is opinionated and style-dependent — calibrated to a macro-positional lens, not objective fact.
        Rearrange it: your layout is saved automatically, and <em>Reset layout</em> restores this default.
        In <em>Customize</em>, any tile can be pinned to its own region — pinned tiles ignore the header lens and
        carry a <span style={{ fontFamily: MONO, color: "var(--gold)" }}>POV</span> chip so you can tell at a glance.
      </div>
    </>
  );
}
