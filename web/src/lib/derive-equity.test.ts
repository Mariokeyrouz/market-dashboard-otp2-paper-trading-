import { describe, expect, it } from "vitest";
import { deriveEquity } from "./derive-equity";

describe("equity mock data integrity", () => {
  it("derives without throwing and keeps its shape", () => {
    const v = deriveEquity();
    expect(v.indices.legend.length).toBeGreaterThan(0);
    expect(v.indices.paths.length).toBe(v.indices.legend.length);
    expect(v.concentration.rows).toHaveLength(10);
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

  it("curve has the tenors the spread math depends on", () => {
    const v = deriveEquity();
    const tenorLabels = v.curve.tenors.map((t) => t.t);
    expect(tenorLabels).toEqual(expect.arrayContaining(["2Y", "10Y", "30Y"]));
    expect(v.curve.shape).toBeTruthy();
  });

  it("index legend value/delta count matches the paths drawn", () => {
    const v = deriveEquity();
    expect(v.indices.legend).toHaveLength(v.indices.paths.length);
    expect(v.indices.ticks.length).toBeGreaterThan(0);
    expect(v.indices.xTicks).toHaveLength(3);
  });
});
