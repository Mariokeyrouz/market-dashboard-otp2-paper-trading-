/**
 * Pure derive selectors for the Equity Dashboard — mirrors derive.ts's shape
 * and conventions exactly, but for a flat (no per-region) dataset. No React,
 * no side effects: unit-testable and swappable to real data.
 */
import { buildPath, buildTicks } from "./chart-geometry";
import type { Tick, XTick } from "./chart-geometry";
import { AMBER, GREEN, RED, bpSign, curveShapeWord, sign, sparkPath, toneUpDown } from "./derive";
import type { LegendEntry } from "./derive";
import { getEquityData } from "./data/mock-equity";

export interface EquityDerived {
  indices: {
    legend: LegendEntry[];
    paths: { name: string; color: string; d: string }[];
    ticks: Tick[];
    xTicks: XTick[];
    windowLabel: string;
  };
  vix: {
    level: string; levelColor: string;
    termLabel: string; termColor: string;
    spreadVix3m: string; spreadVix3mColor: string;
    spreadVix9d: string; spreadVix9dColor: string;
    spark: string;
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
  oil: { name: string; val: string; chg: string; chgColor: string; spark: string };
  concentration: { totalWeightPct: string; rows: { name: string; weightPct: string; barW: string }[] };
}

export function deriveEquity(): EquityDerived {
  const d = getEquityData();

  // ----- equity indices (rebased to 100 so differently-scaled indices compare) -----
  const IL = 44, IR = 20, IT = 18, IB = 26, IW = 700, IH = 220;
  const n = d.indices[0]?.prices.length ?? 0;
  const rebased = d.indices.map((s) => s.prices.map((p) => (p / s.prices[0]) * 100));
  let ilo = Math.min(...rebased.flat());
  let ihi = Math.max(...rebased.flat());
  const ipad = (ihi - ilo) * 0.1 || 0.2;
  ilo -= ipad * 0.4;
  ihi += ipad;
  const ix = (i: number) => IL + (i / (n - 1)) * (IW - IL - IR);
  const iy = (v: number) => IT + ((ihi - v) / (ihi - ilo)) * (IH - IT - IB);
  const iTicks = buildTicks(ilo, ihi, 5, iy);
  const windowLabels = ["3wk ago", "1wk ago", "Today"];
  const ixTicks: XTick[] = [
    { x: ix(0).toFixed(1), label: windowLabels[0], anchor: "start" },
    { x: ix(Math.floor((n - 1) / 2)).toFixed(1), label: windowLabels[1], anchor: "middle" },
    { x: ix(n - 1).toFixed(1), label: windowLabels[2], anchor: "end" },
  ];
  const paths = d.indices.map((s, k) => ({ name: s.name, color: s.color, d: buildPath(rebased[k], ix, iy) }));
  const legend: LegendEntry[] = d.indices.map((s) => {
    const chgPct = (s.prices[s.prices.length - 1] / s.prices[0] - 1) * 100;
    return {
      name: s.name, color: s.color,
      val: s.prices[s.prices.length - 1].toLocaleString("en-US", { maximumFractionDigits: 0 }),
      delta: sign(chgPct, 1, true), dColor: toneUpDown(chgPct),
    };
  });

  // ----- VIX term structure -----
  const spreadVix3m = d.vix.spot - d.vix.vix3m;
  const spreadVix9d = d.vix.spot - d.vix.vix9d;
  const backwardation = spreadVix3m > 0;   // spot pricier than 3m = near-term stress premium

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

  return {
    indices: { legend, paths, ticks: iTicks, xTicks: ixTicks, windowLabel: "1-month, rebased to 100" },
    vix: {
      level: d.vix.spot.toFixed(1),
      levelColor: d.vix.spot >= 25 ? RED : d.vix.spot >= 18 ? AMBER : GREEN,
      termLabel: backwardation ? "Backwardation" : "Contango", termColor: backwardation ? RED : GREEN,
      // Inverted tone on purpose: a positive spread (spot pricier than the
      // forward date) is the stress case, unlike every other signed metric
      // in this app where positive = green.
      spreadVix3m: sign(spreadVix3m, 2), spreadVix3mColor: spreadVix3m > 0 ? RED : GREEN,
      spreadVix9d: sign(spreadVix9d, 2), spreadVix9dColor: spreadVix9d > 0 ? RED : GREEN,
      spark: sparkPath(d.vix.spark, 90, 26),
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
    oil: {
      name: d.oilName, val: d.oilVal, chg: sign(d.oilChg, 2, true), chgColor: toneUpDown(d.oilChg),
      spark: sparkPath(d.oilSpark, 70, 24),
    },
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
  };
}
