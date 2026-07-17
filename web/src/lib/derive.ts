/**
 * Pure derive selectors — every computed value and chart geometry for the
 * dashboard, ported from the validated design handoff's renderVals().
 * No React, no side effects: unit-testable and swappable to real data.
 */
import { getRegionData } from "./data/mock";
import { REGION_LABELS, REGIONS } from "./data/types";
import type { PlaybookRow, Region, RegimeSeg } from "./data/types";

// ---------- formatting / color helpers ----------
export const GREEN = "var(--green)";
export const RED = "var(--red)";
export const AMBER = "var(--amber)";

export function sign(v: number, dp = 2, pct = false): string {
  return (v >= 0 ? "+" : "") + v.toFixed(dp) + (pct ? "%" : "");
}
export function toneUpDown(v: number): string {
  return v >= 0 ? GREEN : RED;
}
export function bpSign(v: number): string {
  return (v >= 0 ? "+" : "") + Math.round(v) + " bp";
}
export function heatColor(v: number): { bg: string; fg: string } {
  const cap = 8;
  const a = Math.min(Math.abs(v) / cap, 1);
  const alpha = (0.1 + a * 0.32).toFixed(3);
  return v >= 0
    ? { bg: `rgba(94,122,59,${alpha})`, fg: "var(--ink)" }
    : { bg: `rgba(177,74,46,${alpha})`, fg: "var(--ink)" };
}
export function makeSpark(last: number, chgPct: number): number[] {
  const start = last / (1 + chgPct / 100);
  const arr: number[] = [];
  for (let i = 0; i < 7; i++) {
    const base = start + (last - start) * (i / 6);
    const wig = Math.sin(i * 1.7 + (last % 3)) * (last - start) * 0.16;
    arr.push(base + wig);
  }
  arr[6] = last;
  return arr;
}
export function sparkPath(arr: number[], w: number, h: number, pad = 2): string {
  const lo = Math.min(...arr);
  const hi = Math.max(...arr);
  const r = hi - lo || 1;
  return arr
    .map(
      (v, i) =>
        (i ? "L" : "M") +
        (((i / (arr.length - 1)) * (w - 2 * pad)) + pad).toFixed(1) +
        " " +
        (h - pad - ((v - lo) / r) * (h - 2 * pad)).toFixed(1),
    )
    .join(" ");
}
function buildPath(arr: number[], x: (i: number) => number, yfn: (v: number) => number): string {
  return arr.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + yfn(v).toFixed(1)).join(" ");
}

// ---------- derived shapes ----------
export interface Tick { y: string; ty: string; label: string }
export interface XTick { x: string; label: string; anchor: "start" | "middle" | "end" }
export interface LegendEntry { name: string; color: string; val: string; delta: string; dColor: string }
export interface MidLabel { x: string; y: string; v: string }
export interface EndDot { x: string; y: string; lx: string; ly: string; v: string; color: string }
export interface BarRow { name: string; val: string; color: string; barLeft: string; barW: string }

export interface Derived {
  region: Region;
  exchange: string;
  regime: { label: string; color: string; days: number; since: string; history: RegimeSeg[] };
  metrics: {
    inflation: string; inflationSub: string;
    growth: string; growthSub: string; growthColor: string;
    policy: string; policySub: string;
    cond: string; condSub: string; condColor: string;
  };
  hinge: {
    def: string;
    legend: LegendEntry[];
    ticks: Tick[];
    xTicks: XTick[];
    nomPath: string;
    realPath: string;
    realArea: string;
    beArea: string;
    beMid: MidLabel;
    realMid: MidLabel;
    end: EndDot;
    impulse: { name: string; val: string; chg: string; color: string; spark: string };
  };
  classification: { label: string; desc: string; tags: string[]; mover: string; color: string };
  playbook: PlaybookRow[];
  tripwires: { label: string; tag: string; val: string; chg: string; chgColor: string; state: string; note: string; tone: string }[];
  heatmap: { cols: string[]; rows: { name: string; cells: { txt: string; bg: string; fg: string }[] }[] };
  curve: {
    path: string; prevPath: string;
    pts: { x: string; y: string; t: string; v: string; vy: string }[];
    ticks: Tick[];
    tenors: { t: string; v: string; bp: string; bpColor: string }[];
    spread: string; spreadColor: string;
    spread2: string; spread2Color: string;
    spread3: string; spread3Color: string;
    shape: string;
  };
  surprises: { headline: string; color: string; spark: string; rows: BarRow[] };
  labor: { name: string; value: string; delta: string }[];
  fx: { pair: string; d1: string; d1Color: string; ytd: string; ytdColor: string; barLeft: string; barW: string; barColor: string }[];
  commods: { name: string; price: string; chg: string; chgColor: string; spark: string }[];
  cb: { name: string; days: string; date: string; action: string; prob: number; move: string };
  releases: { day: string; name: string; cons: string; dayColor: string }[];
  positioning: BarRow[];
}

/** Curve shape word from the 2s10s spread (design thresholds). */
export function curveShapeWord(spread: number): string {
  return spread < -0.05 ? "inverted" : spread < 0.1 ? "flat" : spread > 0.5 ? "steep" : "upward-sloping";
}

// ---------- cross-region comparison matrix ----------
export interface MatrixCell { key: string; txt: string; color: string }
export interface MatrixRow {
  region: Region;
  label: string;
  /** Global is an aggregate, not a peer of the single economies — rendered apart. */
  isAgg: boolean;
  regime: { label: string; color: string };
  cells: MatrixCell[];
}
export interface MatrixDerived {
  cols: { key: string; label: string }[];
  rows: MatrixRow[];
}

export const MATRIX_COLS: { key: string; label: string }[] = [
  { key: "cpi", label: "CPI" },
  { key: "growth", label: "Growth" },
  { key: "policy", label: "Policy" },
  { key: "fci", label: "FCI" },
  { key: "y10", label: "10Y" },
  { key: "real", label: "Real" },
  { key: "be", label: "BE" },
  { key: "d10", label: "Δ10Y" },
  { key: "s2s10", label: "2s10s" },
  { key: "esi", label: "ESI" },
];

/**
 * Every region on one row, so they can be read against each other instead of
 * one at a time behind the global lens.
 *
 * Colors reuse deriveAll's rules verbatim (growth < 50 = red, looser FCI =
 * green, direction elsewhere) so a matrix cell can never disagree with the
 * tile showing the same number. Deliberately no background heat-shading: the
 * columns are on incompatible scales (a diffusion index, a z-score, a spread
 * in pp), so a shared color ramp across them would imply a comparison that
 * isn't there.
 */
export function deriveMatrix(): MatrixDerived {
  const rows: MatrixRow[] = REGIONS.map((region) => {
    const d = getRegionData(region);
    const last = d.nom.length - 1;
    const at = (t: string) => d.curve.find((p) => p[0] === t)![1];
    const s2s10 = at("10Y") - at("2Y");
    return {
      region,
      label: REGION_LABELS[region],
      isAgg: region === "GL",
      regime: { label: d.regimeLabel, color: d.regimeColor },
      cells: [
        { key: "cpi", txt: d.inflation, color: "var(--ink)" },
        { key: "growth", txt: String(d.growth), color: d.growth < 50 ? RED : GREEN },
        { key: "policy", txt: d.policy, color: "var(--ink)" },
        { key: "fci", txt: sign(d.cond, 2), color: toneUpDown(-d.cond) },
        { key: "y10", txt: d.nom[last].toFixed(2) + "%", color: "var(--ink)" },
        { key: "real", txt: d.real[last].toFixed(2) + "%", color: "var(--ink)" },
        { key: "be", txt: d.be[last].toFixed(2) + "%", color: "var(--ink)" },
        { key: "d10", txt: bpSign(d.dNom * 100), color: toneUpDown(d.dNom) },
        { key: "s2s10", txt: sign(s2s10, 2), color: toneUpDown(s2s10) },
        { key: "esi", txt: sign(d.esi, 0), color: toneUpDown(d.esi) },
      ],
    };
  });
  return { cols: MATRIX_COLS, rows };
}

export function deriveAll(region: Region): Derived {
  const d = getRegionData(region);

  // ----- hinge chart geometry (stacked: real base band + breakeven band = nominal) -----
  const HL = 44, HR = 64, HT = 18, HB = 30, HW = 700, HH = 250;
  const n = d.nom.length;
  let lo = Math.min(0, ...d.real);
  let hi = Math.max(...d.nom);
  const pad = (hi - lo) * 0.08 || 0.2;
  lo -= pad * 0.4;
  hi += pad;
  const hx = (i: number) => HL + (i / (n - 1)) * (HW - HL - HR);
  const hy = (v: number) => HT + ((hi - v) / (hi - lo)) * (HH - HT - HB);
  const ticks: Tick[] = [];
  for (let k = 0; k < 5; k++) {
    const v = lo + ((hi - lo) * k) / 4;
    const y = hy(v);
    ticks.push({ y: y.toFixed(1), ty: (y + 3.5).toFixed(1), label: v.toFixed(2) });
  }
  const dates = ["Jun 23", "Jun 27", "Jul 1"]; // mock window labels (real index later)
  const xTicks: XTick[] = [
    { x: hx(0).toFixed(1), label: dates[0], anchor: "start" },
    { x: hx(Math.floor((n - 1) / 2)).toFixed(1), label: dates[1], anchor: "middle" },
    { x: hx(n - 1).toFixed(1), label: dates[2], anchor: "end" },
  ];
  const areaBetween = (top: number[], base: number[]): string => {
    let p = "M" + hx(0).toFixed(1) + " " + hy(top[0]).toFixed(1);
    for (let i = 1; i < n; i++) p += " L" + hx(i).toFixed(1) + " " + hy(top[i]).toFixed(1);
    for (let i = n - 1; i >= 0; i--) p += " L" + hx(i).toFixed(1) + " " + hy(base[i]).toFixed(1);
    return p + " Z";
  };
  const zeros = d.real.map(() => 0);
  const endX = hx(n - 1);
  const endY = hy(d.nom[n - 1]);
  const hingeMidVal = (d.real[n - 1] + d.nom[n - 1]) / 2;
  const dArrow = (v: number) => (v >= 0 ? "▲" : "▼") + Math.abs(v).toFixed(2);

  // ----- oil sparkline -----
  const os = d.oilSpark;
  const oLo = Math.min(...os);
  const oHi = Math.max(...os);
  const orng = oHi - oLo || 1;
  const oilSparkPath = os
    .map((v, i) => (i ? "L" : "M") + ((i / (os.length - 1)) * 116 + 2).toFixed(1) + " " + (26 - ((v - oLo) / orng) * 22).toFixed(1))
    .join(" ");

  // ----- yield curve -----
  const CW = 460, CH = 210, CL = 42, CR = 14, CT = 22, CB = 34;
  const cv = d.curve;
  const cn = cv.length;
  const prev = cv.map((p, i) => p[1] - (0.06 - 0.05 * ((i / (cn - 1) - 0.5) * 2)));
  const cyv = [...cv.map((p) => p[1]), ...prev];
  let clo = Math.min(...cyv);
  let chi = Math.max(...cyv);
  const cpad = (chi - clo) * 0.18 || 0.2;
  clo -= cpad;
  chi += cpad;
  const cx = (i: number) => CL + (i / (cn - 1)) * (CW - CL - CR);
  const cy = (v: number) => CT + ((chi - v) / (chi - clo)) * (CH - CT - CB);
  const curvePts = cv.map((p, i) => {
    const py = cy(p[1]);
    return { x: cx(i).toFixed(1), y: py.toFixed(1), t: p[0], v: p[1].toFixed(2), vy: (py > CT + 16 ? py - 8 : py + 16).toFixed(1) };
  });
  const cticks: Tick[] = [];
  for (let k = 0; k < 4; k++) {
    const v = clo + ((chi - clo) * k) / 3;
    const y = cy(v);
    cticks.push({ y: y.toFixed(1), ty: (y + 3.5).toFixed(1), label: v.toFixed(2) });
  }
  const at = (t: string) => cv.find((p) => p[0] === t)![1];
  const y3m = at("3M"), y2 = at("2Y"), y5 = at("5Y"), y10 = at("10Y"), y30 = at("30Y");
  const spread = y10 - y2, spread2 = y10 - y3m, spread3 = y30 - y5;
  const idxT = (t: string) => cv.findIndex((p) => p[0] === t);
  const tenors = ([["2Y", y2], ["10Y", y10], ["30Y", y30]] as [string, number][]).map(([t, v]) => {
    const bp = (v - prev[idxT(t)]) * 100;
    return { t, v: v.toFixed(2), bp: bpSign(bp), bpColor: toneUpDown(bp) };
  });

  // ----- diverging bars -----
  const positioning: BarRow[] = d.positioning.map(([name, z]) => {
    const clamped = Math.max(-3, Math.min(3, z));
    const half = (clamped / 3) * 50;
    return { name, val: sign(z, 1), color: toneUpDown(z), barLeft: (z >= 0 ? 50 : 50 + half).toFixed(1), barW: Math.abs(half).toFixed(1) };
  });
  const surpriseRows: BarRow[] = d.surprises.map(([name, v]) => {
    const c = Math.max(-1.5, Math.min(1.5, v));
    const half = (c / 1.5) * 50;
    return { name, val: sign(v, 1), color: toneUpDown(v), barLeft: (v >= 0 ? 50 : 50 + half).toFixed(1), barW: Math.abs(half).toFixed(1) };
  });
  const fx = d.fx.map(([pair, d1, ytd]) => {
    const c = Math.max(-1, Math.min(1, d1));
    const half = c * 50;
    return {
      pair, d1: sign(d1, 2, true), d1Color: toneUpDown(d1), ytd: sign(ytd, 1, true), ytdColor: toneUpDown(ytd),
      barLeft: (d1 >= 0 ? 50 : 50 + half).toFixed(1), barW: Math.abs(half).toFixed(1), barColor: toneUpDown(d1),
    };
  });
  const commods = d.commods.map(([name, priceStr, chg]) => {
    const price = parseFloat(String(priceStr).replace(/,/g, ""));
    return { name, price: priceStr, chg: sign(chg, 2, true), chgColor: toneUpDown(chg), spark: sparkPath(makeSpark(price, chg), 70, 24) };
  });

  const dayColors: Record<string, string> = { MON: "var(--muted)", TUE: "var(--muted)", WED: "var(--muted)", THU: "var(--muted)", FRI: AMBER };

  return {
    region,
    exchange: d.exchange,
    regime: { label: d.regimeLabel, color: d.regimeColor, days: d.regimeDays, since: d.regimeSince, history: d.history },
    metrics: {
      inflation: d.inflation, inflationSub: d.inflationSub,
      growth: String(d.growth), growthSub: d.growthSub, growthColor: d.growth < 50 ? RED : GREEN,
      policy: d.policy, policySub: d.policySub,
      cond: sign(d.cond, 2), condSub: d.condSub, condColor: toneUpDown(-d.cond),
    },
    hinge: {
      def: d.hingeDef,
      legend: [
        { name: "Nominal 10Y", color: "var(--ink)", val: d.nom[n - 1].toFixed(2) + "%", delta: dArrow(d.dNom), dColor: toneUpDown(d.dNom) },
        { name: "Real (TIPS)", color: "#3A6B9E", val: d.real[n - 1].toFixed(2) + "%", delta: dArrow(d.dReal), dColor: toneUpDown(d.dReal) },
        { name: "Breakeven", color: "var(--gold)", val: d.be[n - 1].toFixed(2) + "%", delta: dArrow(d.dBe), dColor: toneUpDown(d.dBe) },
      ],
      ticks, xTicks,
      nomPath: buildPath(d.nom, hx, hy),
      realPath: buildPath(d.real, hx, hy),
      realArea: areaBetween(d.real, zeros),
      beArea: areaBetween(d.nom, d.real),
      beMid: { x: (endX - 6).toFixed(1), y: (hy(hingeMidVal) + 4).toFixed(1), v: d.be[n - 1].toFixed(2) },
      realMid: { x: (endX - 6).toFixed(1), y: (hy(d.real[n - 1] / 2) + 4).toFixed(1), v: d.real[n - 1].toFixed(2) },
      end: { x: endX.toFixed(1), y: endY.toFixed(1), lx: (endX - 9).toFixed(1), ly: (endY - 8).toFixed(1), v: d.nom[n - 1].toFixed(2), color: "var(--ink)" },
      impulse: { name: d.oilName, val: d.oilVal, chg: sign(d.oilChg, 2, true), color: toneUpDown(d.oilChg), spark: oilSparkPath },
    },
    classification: { label: d.classLabel, desc: d.classDesc, tags: d.classTags, mover: d.classMover, color: d.regimeColor },
    playbook: d.playbook,
    tripwires: d.tripwires.map((t) => ({
      label: t.label, tag: t.tag, val: t.val, state: t.state, note: t.note, tone: t.tone,
      chg: t.chg == null ? "" : sign(t.chg, 2) + (t.unit || ""),
      chgColor: t.chg == null ? "var(--muted)" : toneUpDown(t.chg),
    })),
    heatmap: {
      cols: ["1D", "1W", "1M", "YTD"],
      rows: d.cross.map((r) => ({
        name: r[0],
        cells: (r.slice(1) as number[]).map((v) => {
          const c = heatColor(v);
          return { txt: sign(v, 1), bg: c.bg, fg: c.fg };
        }),
      })),
    },
    curve: {
      path: cv.map((p, i) => (i ? "L" : "M") + cx(i).toFixed(1) + " " + cy(p[1]).toFixed(1)).join(" "),
      prevPath: prev.map((v, i) => (i ? "L" : "M") + cx(i).toFixed(1) + " " + cy(v).toFixed(1)).join(" "),
      pts: curvePts, ticks: cticks, tenors,
      spread: sign(spread, 2), spreadColor: toneUpDown(spread),
      spread2: sign(spread2, 2), spread2Color: toneUpDown(spread2),
      spread3: sign(spread3, 2), spread3Color: toneUpDown(spread3),
      shape: curveShapeWord(spread),
    },
    surprises: { headline: sign(d.esi, 0), color: toneUpDown(d.esi), spark: sparkPath(d.esiTrend, 56, 20), rows: surpriseRows },
    labor: d.labor.map(([name, value, delta]) => ({ name, value, delta })),
    fx, commods,
    cb: { name: d.cb.name, days: String(d.cb.days), date: d.cb.date, action: d.cb.action, prob: d.cb.prob, move: d.cb.move },
    releases: d.releases.map(([day, name, cons]) => ({ day, name, cons, dayColor: dayColors[day] || "var(--muted)" })),
    positioning,
  };
}
