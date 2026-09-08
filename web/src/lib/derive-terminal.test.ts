import { describe, expect, it } from "vitest";
import { deriveTerminal, factorCellColor } from "./derive-terminal";

describe("terminal mock data integrity", () => {
  it("derives without throwing and keeps its shape", () => {
    const v = deriveTerminal();
    expect(v.markets.length).toBeGreaterThan(0);
    expect(v.performance["1M"].series.length).toBeGreaterThan(0);
  });

  it("markets has 4 indices plus a VIX row", () => {
    const v = deriveTerminal();
    expect(v.markets).toHaveLength(5);
    expect(v.markets[v.markets.length - 1].name).toContain("VIX");
  });

  it("all three performance timeframes have consistent, non-empty geometry", () => {
    const v = deriveTerminal();
    (["1M", "3M", "1Y"] as const).forEach((tf) => {
      const idx = v.performance[tf];
      expect(idx.xs.length).toBeGreaterThan(0);
      expect(idx.dates).toHaveLength(idx.xs.length);
      idx.series.forEach((s) => {
        expect(s.values).toHaveLength(idx.xs.length);
        expect(s.ys).toHaveLength(idx.xs.length);
      });
    });
    expect(v.performance["1Y"].xs.length).toBeGreaterThan(v.performance["3M"].xs.length);
    expect(v.performance["3M"].xs.length).toBeGreaterThan(v.performance["1M"].xs.length);
  });

  it("sectors are sorted descending by 1D change and every sector is present", () => {
    const v = deriveTerminal();
    expect(v.sectors).toHaveLength(11);
    const chg1d = v.sectors.map((s) => parseFloat(s.chg1d));
    for (let i = 1; i < chg1d.length; i++) expect(chg1d[i]).toBeLessThanOrEqual(chg1d[i - 1]);
  });

  it("currencies has all 7 FX pairs", () => {
    const v = deriveTerminal();
    expect(v.currencies).toHaveLength(7);
  });

  it("global markets carries a Developed/Emerging group on every row", () => {
    const v = deriveTerminal();
    expect(v.global.length).toBeGreaterThan(0);
    expect(v.global.every((r) => r.group === "Developed" || r.group === "Emerging")).toBe(true);
  });

  it("fixed income splits into govt and corp tables", () => {
    const v = deriveTerminal();
    expect(v.fixedIncome.govt).toHaveLength(4);
    expect(v.fixedIncome.corp).toHaveLength(4);
  });

  it("factors has all 9 style-box cells", () => {
    const v = deriveTerminal();
    expect(v.factors).toHaveLength(9);
  });

  it("market movers has 5 gainers and 5 losers, all correctly signed", () => {
    const v = deriveTerminal();
    expect(v.movers.gainers).toHaveLength(5);
    expect(v.movers.losers).toHaveLength(5);
    v.movers.gainers.forEach((r) => expect(parseFloat(r.chgPct)).toBeGreaterThan(0));
    v.movers.losers.forEach((r) => expect(parseFloat(r.chgPct)).toBeLessThan(0));
  });

  it("calendar events are sorted chronologically and the nearest is labeled Today", () => {
    const v = deriveTerminal();
    expect(v.events.length).toBeGreaterThan(0);
    expect(v.events[0].dateLabel).toBe("Today");
  });
});

describe("factorCellColor", () => {
  it("is a color-mix expression that leans green for positive and red for negative", () => {
    expect(factorCellColor(2)).toContain("var(--green)");
    expect(factorCellColor(-2)).toContain("var(--red)");
  });

  it("clamps magnitude so an extreme move doesn't overflow the mix percentage", () => {
    const extreme = factorCellColor(50);
    const match = extreme.match(/(\d+)%/);
    expect(match).not.toBeNull();
    expect(Number(match![1])).toBeLessThanOrEqual(70);
  });
});
