/**
 * Shared SVG chart-geometry primitives — pure functions of arrays and
 * pixel-space mapping, no dashboard-specific knowledge. Used by both the
 * macro dashboard's derive.ts and the equity dashboard's derive-equity.ts,
 * so every chart's line/tick math comes from one tested code path.
 */

export interface Tick { y: string; ty: string; label: string }
export interface XTick { x: string; label: string; anchor: "start" | "middle" | "end" }

const MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-08-12" (or with a time suffix) -> "Aug 12", matching this app's other short-date labels. */
export function shortDate(isoDate: string): string {
  const [, m, d] = isoDate.slice(0, 10).split("-").map(Number);
  return `${MONTH_ABBR[m - 1]} ${d}`;
}

/** SVG path `d` for a polyline through `arr`, mapped via `x`/`yfn`. */
export function buildPath(arr: number[], x: (i: number) => number, yfn: (v: number) => number): string {
  return arr.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + yfn(v).toFixed(1)).join(" ");
}

/** `count` evenly-spaced gridline ticks across [lo, hi], mapped through `yfn`. */
export function buildTicks(lo: number, hi: number, count: number, yfn: (v: number) => number): Tick[] {
  const ticks: Tick[] = [];
  for (let k = 0; k < count; k++) {
    const v = lo + ((hi - lo) * k) / (count - 1);
    const y = yfn(v);
    ticks.push({ y: y.toFixed(1), ty: (y + 3.5).toFixed(1), label: v.toFixed(2) });
  }
  return ticks;
}
