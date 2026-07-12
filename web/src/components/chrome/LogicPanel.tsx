"use client";

import { ELEMENT_MAP, Z_ROLE_LABELS, type ZRole } from "@/lib/elements/registry";
import { useDashStore } from "@/lib/store";
import { MONO, SERIF } from "../ui";

const ROLE_COLORS: Record<ZRole, string> = {
  anchor: "#A07B1D",
  scan: "#B08018",
  pivot: "#2B2721",
  terminal: "#5E7A3B",
  support: "#8A8172",
};

/** Small Z diagram showing the reading order. */
function ZDiagram() {
  const lbl = (x: number, y: number, t: string, anchor: "start" | "end" | "middle" = "start") => (
    <text x={x} y={y} fontSize={9.5} fill="#8A8172" textAnchor={anchor} fontFamily="var(--font-plex-sans), sans-serif">
      {t}
    </text>
  );
  return (
    <svg viewBox="0 0 320 150" style={{ width: "100%", height: "auto", display: "block" }}>
      <rect x={8} y={8} width={304} height={134} rx={10} fill="#FBF8F1" stroke="rgba(0,0,0,.09)" />
      <path d="M40 36 L280 36 L40 114 L280 114" fill="none" stroke="#A07B1D" strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" strokeDasharray="1 6" />
      <circle cx={40} cy={36} r={5} fill="#A07B1D" />
      <circle cx={280} cy={36} r={5} fill="#B08018" />
      <circle cx={40} cy={114} r={5} fill="#2B2721" />
      <circle cx={280} cy={114} r={5} fill="#5E7A3B" />
      {lbl(52, 30, "1 · Regime — where are we?")}
      {lbl(268, 30, "2 · Classification — the signal", "end")}
      {lbl(120, 72, "3 · The Hinge — why it's moving")}
      {lbl(52, 132, "4 · Tripwires — confirm / deny")}
      {lbl(268, 132, "5 · Calendar — what's next", "end")}
    </svg>
  );
}

export default function LogicPanel() {
  const open = useDashStore((s) => s.logicOpen);
  const setOpen = useDashStore((s) => s.setLogicOpen);
  const layout = useDashStore((s) => s.layout);
  const hidden = useDashStore((s) => s.hidden);

  // Narrate elements in their *current* visual order (top-left → bottom-right).
  const ordered = [...layout]
    .filter((l) => !hidden.includes(l.i))
    .sort((a, b) => a.y - b.y || a.x - b.x)
    .map((l) => ELEMENT_MAP.get(l.i))
    .filter((d) => d !== undefined);

  return (
    <>
      {/* Floating side tab */}
      <button
        onClick={() => setOpen(true)}
        aria-label="Open the layout logic explainer"
        style={{
          position: "fixed", right: 0, top: "42%", zIndex: 60,
          writingMode: "vertical-rl", letterSpacing: ".18em",
          fontSize: 11, fontWeight: 600, textTransform: "uppercase", color: "#A07B1D",
          background: "#FBF8F1", border: "1px solid rgba(160,123,29,.5)", borderRight: "none",
          borderRadius: "8px 0 0 8px", padding: "14px 7px", cursor: "pointer",
          boxShadow: "-2px 2px 8px rgba(43,39,33,.08)",
        }}
      >
        ⓘ Logic
      </button>

      {/* Backdrop + drawer */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 70, background: "rgba(43,39,33,.28)" }}
        />
      )}
      <aside
        aria-hidden={!open}
        style={{
          position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 80, width: 400, maxWidth: "92vw",
          background: "#FBF8F1", borderLeft: "1px solid rgba(0,0,0,.12)",
          boxShadow: "-8px 0 28px rgba(43,39,33,.16)",
          transform: open ? "translateX(0)" : "translateX(105%)",
          transition: "transform .25s ease", overflowY: "auto", padding: "18px 20px 24px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontFamily: SERIF, fontSize: 20, fontWeight: 600 }}>Why this layout</div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            style={{ background: "none", border: "1px solid rgba(0,0,0,.16)", borderRadius: 6, width: 26, height: 26, cursor: "pointer", color: "#8A8172", fontSize: 14 }}
          >
            ×
          </button>
        </div>

        <p style={{ fontSize: 13, lineHeight: 1.55, color: "#4A443B", margin: "0 0 12px" }}>
          The default arrangement follows a <strong>Z-pattern</strong> — the natural path a reader&apos;s eye takes across a
          page: enter top-left, sweep right, cut diagonally down, sweep right again.
          Each stop on that path answers the next question a macro investor asks.
        </p>
        <ZDiagram />
        <p style={{ fontSize: 13, lineHeight: 1.55, color: "#4A443B", margin: "12px 0 6px" }}>
          <strong>1 · Where are we?</strong> (regime, top-left) → <strong>2 · What&apos;s the signal?</strong> (classification,
          top-right) → <strong>3 · Why?</strong> (the Hinge decomposition on the diagonal) →{" "}
          <strong>4 · Is it confirmed?</strong> (tripwires, the bottom stroke) → <strong>5 · What&apos;s next?</strong>{" "}
          (calendar, bottom-right exit). Everything else is supporting evidence you consult on demand.
        </p>

        <div style={{ fontSize: 10, letterSpacing: ".13em", color: "#8A8172", textTransform: "uppercase", fontWeight: 600, margin: "18px 0 8px" }}>
          Elements — in your current order
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {ordered.map((d) => (
            <div key={d.id} style={{ borderBottom: "1px solid rgba(0,0,0,.06)", paddingBottom: 10 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 3 }}>
                <span style={{ fontFamily: SERIF, fontSize: 14.5, fontWeight: 600 }}>{d.title}</span>
                <span
                  style={{
                    fontFamily: MONO, fontSize: 9.5, fontWeight: 600, letterSpacing: ".04em",
                    color: ROLE_COLORS[d.zRole], border: `1px solid ${ROLE_COLORS[d.zRole]}55`,
                    borderRadius: 4, padding: "1px 6px", whiteSpace: "nowrap",
                  }}
                >
                  {Z_ROLE_LABELS[d.zRole]}
                </span>
              </div>
              <div style={{ fontSize: 12.5, lineHeight: 1.5, color: "#4A443B" }}>{d.logic}</div>
            </div>
          ))}
        </div>

        <div
          style={{
            marginTop: 16, fontSize: 11.5, lineHeight: 1.5, color: "#8A8172",
            border: "1px solid rgba(160,123,29,.35)", borderRadius: 8, padding: "9px 12px", background: "rgba(160,123,29,.06)",
          }}
        >
          This hierarchy is opinionated and style-dependent — calibrated to a macro-positional lens, not objective fact.
          Rearrange it: your layout is saved automatically, and <em>Reset layout</em> restores this default.
        </div>
      </aside>
    </>
  );
}
