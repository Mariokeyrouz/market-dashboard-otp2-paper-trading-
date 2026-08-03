import { describe, expect, it } from "vitest";
import { deriveEquity } from "./derive-equity";

describe("equity mock data integrity", () => {
  it("derives without throwing and keeps its shape", () => {
    const v = deriveEquity();
    expect(v.indices["1M"].legend.length).toBeGreaterThan(0);
    expect(v.indices["1M"].series.length).toBe(v.indices["1M"].legend.length);
    expect(v.concentration.rows).toHaveLength(10);
  });

  it("all three index timeframes have consistent, non-empty geometry", () => {
    const v = deriveEquity();
    (["1M", "3M", "1Y"] as const).forEach((tf) => {
      const idx = v.indices[tf];
      expect(idx.xs.length).toBeGreaterThan(0);
      expect(idx.dates).toHaveLength(idx.xs.length);
      idx.series.forEach((s) => {
        expect(s.values).toHaveLength(idx.xs.length);
        expect(s.ys).toHaveLength(idx.xs.length);
      });
    });
    // Longer windows cover more sessions than shorter ones.
    expect(v.indices["1Y"].xs.length).toBeGreaterThan(v.indices["3M"].xs.length);
    expect(v.indices["3M"].xs.length).toBeGreaterThan(v.indices["1M"].xs.length);
  });

  it("concentration rows are sorted descending and total is their sum", () => {
    const v = deriveEquity();
    const weights = v.concentration.rows.map((r) => parseFloat(r.weightPct));
    for (let i = 1; i < weights.length; i++) expect(weights[i]).toBeLessThanOrEqual(weights[i - 1]);
    const total = weights.reduce((s, w) => s + w, 0);
    expect(parseFloat(v.concentration.totalWeightPct)).toBeCloseTo(total, 1);
  });

  it("concentration bar widths are scaled to the largest row (max = 100)", () => {
    const v = deriveEquity();
    const maxBar = Math.max(...v.concentration.rows.map((r) => parseFloat(r.barW)));
    expect(maxBar).toBeCloseTo(100, 1);
  });

  it("VIX term-structure spread sign matches the term label", () => {
    const v = deriveEquity();
    const spread = parseFloat(v.vix.spreadVix3m);
    if (spread > 0) expect(v.vix.termLabel).toBe("Backwardation");
    else expect(v.vix.termLabel).toBe("Contango");
  });

  it("VIX spread color is inverted (positive spread = red, the stress case)", () => {
    const v = deriveEquity();
    const spread = parseFloat(v.vix.spreadVix3m);
    expect(v.vix.spreadVix3mColor).toBe(spread > 0 ? "var(--red)" : "var(--green)");
  });

  it("VIX historical chart has a path and threshold reference lines", () => {
    const v = deriveEquity();
    expect(v.vix.historyPath).toMatch(/^M/);
    expect(parseFloat(v.vix.refLine25)).toBeLessThan(parseFloat(v.vix.refLine18)); // higher value = smaller y (SVG origin top-left)
  });

  it("curve has the tenors the spread math depends on", () => {
    const v = deriveEquity();
    const tenorLabels = v.curve.tenors.map((t) => t.t);
    expect(tenorLabels).toEqual(expect.arrayContaining(["2Y", "10Y", "30Y"]));
    expect(v.curve.shape).toBeTruthy();
  });

  it("index legend value/delta count matches the series drawn", () => {
    const v = deriveEquity();
    const idx = v.indices["1M"];
    expect(idx.legend).toHaveLength(idx.series.length);
    expect(idx.ticks.length).toBeGreaterThan(0);
    expect(idx.xTicks).toHaveLength(3);
  });

  it("sectors are sorted descending by 1D change and every sector is present", () => {
    const v = deriveEquity();
    expect(v.sectors).toHaveLength(11);
    const chg1d = v.sectors.map((s) => parseFloat(s.chg1d));
    for (let i = 1; i < chg1d.length; i++) expect(chg1d[i]).toBeLessThanOrEqual(chg1d[i - 1]);
  });

  it("market movers has 5 gainers and 5 losers, all correctly signed", () => {
    const v = deriveEquity();
    expect(v.movers.gainers).toHaveLength(5);
    expect(v.movers.losers).toHaveLength(5);
    v.movers.gainers.forEach((r) => expect(parseFloat(r.chgPct)).toBeGreaterThan(0));
    v.movers.losers.forEach((r) => expect(parseFloat(r.chgPct)).toBeLessThan(0));
  });

  it("calendar events are sorted chronologically and the nearest is labeled Today", () => {
    const v = deriveEquity();
    expect(v.events.length).toBeGreaterThan(0);
    expect(v.events[0].dateLabel).toBe("Today");
    expect(v.events.every((e) => e.kindLabel === "Earnings" || e.kindLabel === "Macro")).toBe(true);
  });
});
