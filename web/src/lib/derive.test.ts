import { describe, expect, it } from "vitest";
import { getRegionData } from "./data/mock";
import { REGIONS } from "./data/types";
import { curveShapeWord, deriveAll, heatColor, makeSpark, sign, toneUpDown } from "./derive";

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
