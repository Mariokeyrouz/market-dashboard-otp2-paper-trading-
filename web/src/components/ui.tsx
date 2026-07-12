/** Shared design tokens as style objects (ported from the design handoff). */
import type { CSSProperties } from "react";

export const SERIF = "var(--font-newsreader), serif";
export const SANS = "var(--font-plex-sans), sans-serif";
export const MONO = "var(--font-plex-mono), monospace";

export const MICRO: CSSProperties = {
  fontSize: 10,
  letterSpacing: ".13em",
  color: "#8A8172",
  textTransform: "uppercase",
  fontWeight: 600,
};

/** Standard tile chrome; fills its grid cell. */
export const TILE: CSSProperties = {
  background: "#FBF8F1",
  border: "1px solid rgba(0,0,0,.09)",
  borderRadius: 10,
  padding: "9px 12px",
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
    <div style={{ fontFamily: SERIF, fontStyle: "italic", fontSize: 12, color: "#8A8172", ...style }}>
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
  track = "rgba(0,0,0,.06)",
}: {
  barLeft: string;
  barW: string;
  color: string;
  height?: number;
  track?: string;
}) {
  return (
    <div style={{ position: "relative", height, background: track, borderRadius: 4 }}>
      <div style={{ position: "absolute", top: 0, bottom: 0, left: "50%", width: 1, background: "rgba(0,0,0,.2)" }} />
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
