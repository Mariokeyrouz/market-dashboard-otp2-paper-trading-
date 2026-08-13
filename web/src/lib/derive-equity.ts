/**
 * Pure derive selectors for the Equity Dashboard — mirrors derive.ts's shape
 * and conventions exactly, but for a flat (no per-region) dataset. No React,
 * no side effects: unit-testable and swappable to real data.
 */
import { buildPath, buildTicks } from "./chart-geometry";
import type { Tick, XTick } from "./chart-geometry";
import { AMBER, GREEN, RED, bpSign, curveShapeWord, makeSpark, sign, sparkPath, toneUpDown } from "./derive";
import type { LegendEntry } from "./derive";
import { getEquityData } from "./data/mock-equity";
import type { EquityCoreData, MoverRow } from "./data/types-equity";

export type IndicesTimeframe = "1M" | "3M" | "1Y";

export interface IndicesSeries { name: string; color: string; d: string; ys: number[]; values: number[] }
export interface IndicesTF {
  legend: LegendEntry[];
  ticks: Tick[];
  xTicks: XTick[];
  windowLabel: string;
  /** Per-point x pixel position, shared across all series in this timeframe. */
  xs: number[];
  /** Per-point hover label ("N sessions ago" / "Today"), parallel to `xs`. */
  dates: string[];
  series: IndicesSeries[];
}

export interface MoverFmt { ticker: string; name: string; price: string; chgPct: string; chgColor: string }

export interface EquityDerived {
  indices: Record<IndicesTimeframe, IndicesTF>;
  vix: {
    level: string; levelColor: string;
    termLabel: string; termColor: string;
    spreadVix3m: string; spreadVix3mColor: string;
    spreadVix9d: string; spreadVix9dColor: string;
    historyPath: string; refLine18: string; refLine25: string; historyStartLabel: string;
  };
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
  commods: { name: string; price: string; chg: string; chgColor: string; spark: string }[];
  concentration: { totalWeightPct: string; rows: { name: string; weightPct: string; barW: string }[] };
  sectors: {
    name: string;
    chg1d: string; chg1dColor: string;
    chg1w: string; chg1wColor: string;
    chg1m: string; chg1mColor: string;
    barLeft: string; barW: string;
  }[];
  movers: { gainers: MoverFmt[]; losers: MoverFmt[] };
  events: { dateLabel: string; kind: "earnings" | "macro"; kindLabel: string; kindColor: string; label: string; detail: string }[];
}

const TIMEFRAMES: { key: IndicesTimeframe; points: number; label: string; axisLabels: [string, string, string] }[] = [
  { key: "1M", points: 22, label: "1-month, rebased to 100", axisLabels: ["3wk ago", "1wk ago", "Today"] },
  { key: "3M", points: 64, label: "3-month, rebased to 100", axisLabels: ["12wk ago", "6wk ago", "Today"] },
  { key: "1Y", points: 252, label: "1-year, rebased to 100", axisLabels: ["11mo ago", "5mo ago", "Today"] },
];

function buildIndicesTF(d: EquityCoreData, points: number, windowLabel: string, axisLabels: [string, string, string]): IndicesTF {
  const IL = 44, IR = 20, IT = 18, IB = 26, IW = 700, IH = 220;
  const priceSlices = d.indices.map((s) => s.prices.slice(-points));
  const n = priceSlices[0]?.length ?? 0;
  const rebased = priceSlices.map((prices) => prices.map((p) => (p / prices[0]) * 100));
  let ilo = Math.min(...rebased.flat());
  let ihi = Math.max(...rebased.flat());
  const ipad = (ihi - ilo) * 0.1 || 0.2;
  ilo -= ipad * 0.4;
  ihi += ipad;
  const ix = (i: number) => IL + (i / (n - 1)) * (IW - IL - IR);
  const iy = (v: number) => IT + ((ihi - v) / (ihi - ilo)) * (IH - IT - IB);
  const iTicks = buildTicks(ilo, ihi, 5, iy);
  const xs = Array.from({ length: n }, (_, i) => ix(i));
  const dates = Array.from({ length: n }, (_, i) => (i === n - 1 ? "Today" : `${n - 1 - i} session${n - 1 - i === 1 ? "" : "s"} ago`));
  const xTicks: XTick[] = [
    { x: ix(0).toFixed(1), label: axisLabels[0], anchor: "start" },
    { x: ix(Math.floor((n - 1) / 2)).toFixed(1), label: axisLabels[1], anchor: "middle" },
    { x: ix(n - 1).toFixed(1), label: axisLabels[2], anchor: "end" },
  ];
  const series: IndicesSeries[] = d.indices.map((s, k) => ({
    name: s.name, color: s.color,
    d: buildPath(rebased[k], ix, iy),
    ys: rebased[k].map((v) => iy(v)),
    values: rebased[k],
  }));
  const legend: LegendEntry[] = d.indices.map((s, k) => {
    const prices = priceSlices[k];
    const chgPct = (prices[prices.length - 1] / prices[0] - 1) * 100;
    return {
      name: s.name, color: s.color,
      val: prices[prices.length - 1].toLocaleString("en-US", { maximumFractionDigits: 0 }),
      delta: sign(chgPct, 1, true), dColor: toneUpDown(chgPct),
    };
  });
  return { legend, ticks: iTicks, xTicks, windowLabel, xs, dates, series };
}

export function deriveEquity(): EquityDerived {
  return deriveEquityFrom(getEquityData());
}

export function deriveEquityFrom(d: EquityCoreData): EquityDerived {
  // ----- equity indices, precomputed for every timeframe up front -----
  const indices = Object.fromEntries(
    TIMEFRAMES.map((tf) => [tf.key, buildIndicesTF(d, tf.points, tf.label, tf.axisLabels)]),
  ) as Record<IndicesTimeframe, IndicesTF>;

  // ----- VIX term structure + historical chart -----
  const spreadVix3m = d.vix.spot - d.vix.vix3m;
  const spreadVix9d = d.vix.spot - d.vix.vix9d;
  const backwardation = spreadVix3m > 0; // spot pricier than 3m = near-term stress premium

  const VW = 300, VH = 100, VL = 6, VR = 6, VT = 10, VB = 20;
  const hist = d.vix.history;
  const vn = hist.length;
  let vlo = Math.min(...hist, 15);
  let vhi = Math.max(...hist, 25);
  const vpad = (vhi - vlo) * 0.12 || 1;
  vlo -= vpad;
  vhi += vpad;
  const vx = (i: number) => VL + (i / (vn - 1)) * (VW - VL - VR);
  const vy = (v: number) => VT + ((vhi - v) / (vhi - vlo)) * (VH - VT - VB);

  // ----- yield curve (same construction as the macro dashboard's) -----
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
  const cticks = buildTicks(clo, chi, 4, cy);
  const at = (t: string) => cv.find((p) => p[0] === t)![1];
  const y3m = at("3M"), y2 = at("2Y"), y5 = at("5Y"), y10 = at("10Y"), y30 = at("30Y");
  const spread = y10 - y2, spread2 = y10 - y3m, spread3 = y30 - y5;
  const idxT = (t: string) => cv.findIndex((p) => p[0] === t);
  const tenors = ([["2Y", y2], ["10Y", y10], ["30Y", y30]] as [string, number][]).map(([t, v]) => {
    const bp = (v - prev[idxT(t)]) * 100;
    return { t, v: v.toFixed(2), bp: bpSign(bp), bpColor: toneUpDown(bp) };
  });

  // ----- sector performance (zero-centered, same bar formula as the macro dashboard's positioning) -----
  const SECTOR_CAP = 3;
  const sectors = [...d.sectors]
    .sort((a, b) => b.chg1d - a.chg1d)
    .map((s) => {
      const clamped = Math.max(-SECTOR_CAP, Math.min(SECTOR_CAP, s.chg1d));
      const half = (clamped / SECTOR_CAP) * 50;
      return {
        name: s.name,
        chg1d: sign(s.chg1d, 2, true), chg1dColor: toneUpDown(s.chg1d),
        chg1w: sign(s.chg1w, 2, true), chg1wColor: toneUpDown(s.chg1w),
        chg1m: sign(s.chg1m, 2, true), chg1mColor: toneUpDown(s.chg1m),
        barLeft: (s.chg1d >= 0 ? 50 : 50 + half).toFixed(1),
        barW: Math.abs(half).toFixed(1),
      };
    });

  // ----- market movers -----
  const fmtMover = (r: MoverRow): MoverFmt => ({
    ticker: r.ticker, name: r.name,
    price: r.price.toFixed(2),
    chgPct: sign(r.chgPct, 2, true), chgColor: toneUpDown(r.chgPct),
  });
  const movers = { gainers: d.movers.gainers.map(fmtMover), losers: d.movers.losers.map(fmtMover) };

  // ----- earnings & FOMC calendar -----
  const dateLabel = (n: number) => (n === 0 ? "Today" : n === 1 ? "Tomorrow" : `in ${n}d`);
  const events = [...d.events]
    .sort((a, b) => a.daysFromNow - b.daysFromNow)
    .map((e) => ({
      dateLabel: dateLabel(e.daysFromNow),
      kind: e.kind,
      kindLabel: e.kind === "earnings" ? "Earnings" : "Macro",
      kindColor: e.kind === "earnings" ? "var(--gold)" : "var(--blue-deep)",
      label: e.label, detail: e.detail,
    }));

  return {
    indices,
    vix: {
      level: d.vix.spot.toFixed(1),
      levelColor: d.vix.spot >= 25 ? RED : d.vix.spot >= 18 ? AMBER : GREEN,
      termLabel: backwardation ? "Backwardation" : "Contango", termColor: backwardation ? RED : GREEN,
      // Inverted tone on purpose: a positive spread (spot pricier than the
      // forward date) is the stress case, unlike every other signed metric
      // in this app where positive = green.
      spreadVix3m: sign(spreadVix3m, 2), spreadVix3mColor: spreadVix3m > 0 ? RED : GREEN,
      spreadVix9d: sign(spreadVix9d, 2), spreadVix9dColor: spreadVix9d > 0 ? RED : GREEN,
      historyPath: buildPath(hist, vx, vy),
      refLine18: vy(18).toFixed(1), refLine25: vy(25).toFixed(1),
      historyStartLabel: `${vn - 1}d ago`,
    },
    curve: {
      path: buildPath(cv.map((p) => p[1]), cx, cy),
      prevPath: buildPath(prev, cx, cy),
      pts: curvePts, ticks: cticks, tenors,
      spread: sign(spread, 2), spreadColor: toneUpDown(spread),
      spread2: sign(spread2, 2), spread2Color: toneUpDown(spread2),
      spread3: sign(spread3, 2), spread3Color: toneUpDown(spread3),
      shape: curveShapeWord(spread),
    },
    commods: d.commods.map(([name, priceStr, chg]) => {
      const price = parseFloat(priceStr.replace(/,/g, ""));
      return { name, price: priceStr, chg: sign(chg, 2, true), chgColor: toneUpDown(chg), spark: sparkPath(makeSpark(price, chg), 70, 24) };
    }),
    concentration: (() => {
      const sorted = [...d.concentration].sort((a, b) => b.weightPct - a.weightPct);
      const maxW = Math.max(...sorted.map((r) => r.weightPct));
      const totalWeightPct = sorted.reduce((s, r) => s + r.weightPct, 0);
      return {
        totalWeightPct: totalWeightPct.toFixed(1) + "%",
        rows: sorted.map((r) => ({
          name: r.name, weightPct: r.weightPct.toFixed(1) + "%",
          barW: ((r.weightPct / maxW) * 100).toFixed(1),
        })),
      };
    })(),
    sectors,
    movers,
    events,
  };
}
