import { describe, expect, it } from "vitest";
import { classifyHinge, classMoverLabel } from "./hinge";

describe("classifyHinge", () => {
  it("nominal up, breakeven dominant -> Inflation Scare", () => {
    const r = classifyHinge({ nominalChg: 0.15, realChg: 0.03, breakevenChg: 0.12 });
    expect(r.label).toBe("Inflation Scare");
    expect(r.dominant).toBe("breakeven");
    expect(r.tags).toContain("gold-positive");
  });

  it("nominal up, real dominant -> Growth / Tightening Shock", () => {
    const r = classifyHinge({ nominalChg: 0.15, realChg: 0.12, breakevenChg: 0.03 });
    expect(r.label).toBe("Growth / Tightening Shock");
    expect(r.dominant).toBe("real");
  });

  it("nominal not clearly rising -> Mixed / Neutral", () => {
    const r = classifyHinge({ nominalChg: 0.01, realChg: 0.2, breakevenChg: -0.19 });
    expect(r.label).toBe("Mixed / Neutral");
    expect(r.dominant).toBeNull();
  });

  it("legs too close to separate -> Mixed / Neutral even with nominal rising", () => {
    const r = classifyHinge({ nominalChg: 0.1, realChg: 0.05, breakevenChg: 0.051 });
    expect(r.label).toBe("Mixed / Neutral");
  });
});

describe("classMoverLabel", () => {
  it("maps dominant leg to the mock's existing label convention", () => {
    expect(classMoverLabel("breakeven")).toBe("Breakeven leg");
    expect(classMoverLabel("real")).toBe("Real-yield leg");
    expect(classMoverLabel(null)).toBe("No dominant leg");
  });
});
