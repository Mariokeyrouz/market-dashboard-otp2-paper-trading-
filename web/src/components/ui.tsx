/** Shared design tokens as style objects (ported from the design handoff). */
import type { CSSProperties } from "react";

export const SERIF = "var(--font-newsreader), serif";
export const SANS = "var(--font-plex-sans), sans-serif";
export const MONO = "var(--font-plex-mono), monospace";

export const MICRO: CSSProperties = {
  fontSize: 10,
  letterSpacing: ".13em",
  color: "var(--muted)",
  textTransform: "uppercase",
  fontWeight: 600,
};

/** Standard tile chrome; fills its grid cell. */
export const TILE: CSSProperties = {
  background: "var(--tile)",
  border: "1px solid var(--tile-border)",
  borderRadius: 10,
  padding: "8px 11px",
  boxSizing: "border-box",
  height: "100%",
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
};

export function Micro({ children, style }: { children: React.ReactNode; style?: CSSProperties }) {
  return <div style={{ ...MICRO, ...style }}>{children}</div>;
}

export function PanelTitle({ children }: { children: React.ReactNode }) {
  return <div style={{ fontFamily: SERIF, fontSize: 17, fontWeight: 600 }}>{children}</div>;
}

export function ItalicNote({ children, style }: { children: React.ReactNode; style?: CSSProperties }) {
  return (
    <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12, color: "var(--muted)", ...style }}>
      {children}
    </div>
  );
}

/** Centered diverging bar (positioning z, FX 1D, surprises σ). */
export function DivergingBar({
  barLeft,
  barW,
  color,
  height = 8,
  track = "var(--hairline)",
}: {
  barLeft: string;
  barW: string;
  color: string;
  height?: number;
  track?: string;
}) {
  return (
    <div style={{ position: "relative", height, background: track, borderRadius: 4 }}>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: 1, background: "var(--centerline)" }} />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: `${barLeft}%`,
          width: `${barW}%`,
          background: color,
          borderRadius: 4,
        }}
      />
    </div>
  );
}

/**
 * Dense-table primitives shared across the Terminal dashboard's many
 * small panels (Markets, Sectors, Currencies, Global, Fixed Income x2,
 * Watchlist) — generic enough for a future 4th dashboard type, not
 * Terminal-specific, so they live alongside DivergingBar/Sparkline rather
 * than inside `elements-terminal/`.
 */
const TABLE_COLS_DEFAULT = "1fr 64px 60px";

export function TableHeadRow({
  labels,
  columns = TABLE_COLS_DEFAULT,
}: {
  /** First label is left-aligned (the name column); the rest are right-aligned (numeric columns). */
  labels: string[];
  columns?: string;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: columns, gap: 8, marginBottom: 3 }}>
      {labels.map((l, i) => (
        <span
          key={l}
          style={{
            fontSize: 9.5, letterSpacing: ".08em", textTransform: "uppercase",
            color: "var(--faint)", fontWeight: 600, textAlign: i === 0 ? "left" : "right",
          }}
        >
          {l}
        </span>
      ))}
    </div>
  );
}

export function TableRow({
  name,
  ticker,
  price,
  chgPct,
  chgColor,
  compact = false,
  columns = TABLE_COLS_DEFAULT,
}: {
  name: string;
  /** When present, rendered bold+mono ahead of `name` (Watchlist/Movers style); omitted, `name` alone carries the row. */
  ticker?: string;
  price: string;
  chgPct: string;
  chgColor: string;
  compact?: boolean;
  columns?: string;
}) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: columns, gap: 8, alignItems: "baseline" }}>
      <div style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {ticker && <span style={{ fontFamily: MONO, fontSize: compact ? 11 : 12.5, fontWeight: 600 }}>{ticker}</span>}
        <span style={{ fontSize: compact ? (ticker ? 9.5 : 11) : ticker ? 10.5 : 12.5, color: ticker ? "var(--muted)" : "var(--ink)", marginLeft: ticker ? 6 : 0 }}>
          {name}
        </span>
      </div>
      <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: "var(--muted)" }}>{price}</span>
      <span style={{ fontFamily: MONO, fontSize: compact ? 10.5 : 11.5, textAlign: "right", color: chgColor }}>{chgPct}</span>
    </div>
  );
}

/** Sub-header row inside a dense table (e.g. "Developed" / "Emerging" in Global Markets). */
export function TableGroupLabel({ children }: { children: React.ReactNode }) {
  return <div style={{ ...MICRO, marginTop: 6, marginBottom: 1 }}>{children}</div>;
}

/** Tiny inline sparkline from a precomputed SVG path. */
export function Sparkline({
  d,
  stroke,
  w,
  h,
}: {
  d: string;
  stroke: string;
  w: number;
  h: number;
}) {
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: w, height: h, flexShrink: 0 }}>
      <path d={d} fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
