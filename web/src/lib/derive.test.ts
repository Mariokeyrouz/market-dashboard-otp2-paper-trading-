import { describe, expect, it } from "vitest";
import { getRegionData } from "./data/mock";
import { REGIONS } from "./data/types";
import {
  curveShapeWord, deriveAll, deriveMatrix, heatColor, makeSpark, sign, toneUpDown,
} from "./derive";

describe("mock data integrity", () => {
  it("hinge identity holds: real + breakeven == nominal (±0.011) for every region/point", () => {
    for (const r of REGIONS) {
      const d = getRegionData(r);
      expect(d.nom.length).toBe(d.real.length);
      expect(d.nom.length).toBe(d.be.length);
      d.nom.forEach((nom, i) => {
        expect(Math.abs(d.real[i] + d.be[i] - nom)).toBeLessThanOrEqual(0.011);
      });
    }
  });

  it("every region derives without throwing and keeps its identity fields", () => {
    for (const r of REGIONS) {
      const v = deriveAll(r);
      expect(v.region).toBe(r);
      expect(v.tripwires).toHaveLength(4);
      expect(v.heatmap.rows).toHaveLength(9);
      expect(v.hinge.legend).toHaveLength(3);
    }
  });
});

describe("macro matrix", () => {
  it("has one row per region, in REGIONS order, with Global flagged as the aggregate", () => {
    const m = deriveMatrix();
    expect(m.rows.map((r) => r.region)).toEqual(REGIONS);
    expect(m.rows.filter((r) => r.isAgg).map((r) => r.region)).toEqual(["GL"]);
    for (const r of m.rows) expect(r.cells.map((c) => c.key)).toEqual(m.cols.map((c) => c.key));
  });

  it("hinge identity holds on the 10Y / Real / BE it reports", () => {
    for (const r of deriveMatrix().rows) {
      const num = (k: string) => parseFloat(r.cells.find((c) => c.key === k)!.txt);
      expect(Math.abs(num("real") + num("be") - num("y10"))).toBeLessThanOrEqual(0.011);
    }
  });

  it("2s10s matches the region's own curve", () => {
    for (const r of deriveMatrix().rows) {
      const d = getRegionData(r.region);
      const at = (t: string) => d.curve.find((p) => p[0] === t)![1];
      expect(r.cells.find((c) => c.key === "s2s10")!.txt).toBe(sign(at("10Y") - at("2Y"), 2));
    }
  });

  // The point of the matrix is that it can't contradict the tile showing the
  // same number — so pin every shared cell to deriveAll's own output.
  it("never disagrees with deriveAll for the same region", () => {
    for (const r of deriveMatrix().rows) {
      const v = deriveAll(r.region);
      const cell = (k: string) => r.cells.find((c) => c.key === k)!;
      const legend = (n: string) => v.hinge.legend.find((l) => l.name.startsWith(n))!;

      expect(r.regime.label).toBe(v.regime.label);
      expect(r.regime.color).toBe(v.regime.color);
      expect(cell("cpi").txt).toBe(v.metrics.inflation);
      expect(cell("growth").txt).toBe(v.metrics.growth);
      expect(cell("growth").color).toBe(v.metrics.growthColor);
      expect(cell("policy").txt).toBe(v.metrics.policy);
      expect(cell("fci").txt).toBe(v.metrics.cond);
      expect(cell("fci").color).toBe(v.metrics.condColor);
      expect(cell("y10").txt).toBe(legend("Nominal").val);
      expect(cell("real").txt).toBe(legend("Real").val);
      expect(cell("be").txt).toBe(legend("Breakeven").val);
      expect(cell("s2s10").txt).toBe(v.curve.spread);
      expect(cell("s2s10").color).toBe(v.curve.spreadColor);
      expect(cell("esi").txt).toBe(v.surprises.headline);
      expect(cell("esi").color).toBe(v.surprises.color);
    }
  });
});

describe("curve shape word (design thresholds)", () => {
  it("classifies by 2s10s spread", () => {
    expect(curveShapeWord(-0.11)).toBe("inverted");
    expect(curveShapeWord(0.0)).toBe("flat");
    expect(curveShapeWord(0.34)).toBe("upward-sloping");
    expect(curveShapeWord(0.62)).toBe("steep");
  });

  it("matches per-region mock curves", () => {
    expect(deriveAll("US").curve.shape).toBe("upward-sloping");
    expect(deriveAll("EU").curve.shape).toBe("inverted");
    expect(deriveAll("JP").curve.shape).toBe("steep");
  });
});

describe("helpers", () => {
  it("sign formats with explicit +/-", () => {
    expect(sign(0.15)).toBe("+0.15");
    expect(sign(-1.4, 1, true)).toBe("-1.4%");
  });

  it("toneUpDown maps sign to green/red theme variables", () => {
    expect(toneUpDown(0.1)).toBe("var(--green)");
    expect(toneUpDown(-0.1)).toBe("var(--red)");
  });

  it("heatColor alpha caps at |v| = 8", () => {
    expect(heatColor(8).bg).toBe(heatColor(80).bg);
    expect(heatColor(-8).bg).toBe(heatColor(-80).bg);
    expect(heatColor(4).bg).toContain("rgba(94,122,59,");
    expect(heatColor(-4).bg).toContain("rgba(177,74,46,");
  });

  it("makeSpark produces 7 points ending exactly at last", () => {
    const s = makeSpark(70.94, 2.47);
    expect(s).toHaveLength(7);
    expect(s[6]).toBe(70.94);
  });
});

describe("diverging bars clamp", () => {
  it("positioning z-scores clamp to ±3 (barW ≤ 50)", () => {
    for (const r of REGIONS) {
      for (const p of deriveAll(r).positioning) {
        expect(parseFloat(p.barW)).toBeLessThanOrEqual(50);
        expect(parseFloat(p.barLeft)).toBeGreaterThanOrEqual(0);
      }
    }
  });
});
