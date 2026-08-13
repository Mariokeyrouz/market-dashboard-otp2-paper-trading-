import { describe, expect, it } from "vitest";
import { classifyRegime, cpiTrendFromYoy, growthTrendFromIsm } from "./regime";

describe("classifyRegime", () => {
  it("sticky/rising inflation + weak growth -> Stagflation", () => {
    expect(classifyRegime("sticky", "slowing").label).toBe("Stagflation");
    expect(classifyRegime("rising", "contracting").label).toBe("Stagflation");
  });
  it("cooling inflation + expanding/slowing growth -> Soft Landing", () => {
    expect(classifyRegime("cooling", "expanding").label).toBe("Soft Landing");
    expect(classifyRegime("cooling", "slowing").label).toBe("Soft Landing");
  });
  it("cooling inflation + contracting growth -> Disinflation", () => {
    expect(classifyRegime("cooling", "contracting").label).toBe("Disinflation");
  });
});

describe("cpiTrendFromYoy", () => {
  it("rising when YoY accelerates beyond the epsilon", () => {
    expect(cpiTrendFromYoy(3.5, 3.0)).toBe("rising");
  });
  it("cooling when YoY decelerates beyond the epsilon", () => {
    expect(cpiTrendFromYoy(2.5, 3.0)).toBe("cooling");
  });
  it("sticky when within the epsilon band", () => {
    expect(cpiTrendFromYoy(3.05, 3.0)).toBe("sticky");
  });
});

describe("growthTrendFromIsm", () => {
  it("below 50 is always contracting regardless of direction", () => {
    expect(growthTrendFromIsm(48.0, 47.0)).toBe("contracting");
  });
  it("at/above 50 but decelerating is slowing", () => {
    expect(growthTrendFromIsm(51.0, 53.0)).toBe("slowing");
  });
  it("at/above 50 and flat-or-rising is expanding", () => {
    expect(growthTrendFromIsm(53.0, 51.0)).toBe("expanding");
    expect(growthTrendFromIsm(52.0, 52.0)).toBe("expanding");
  });
});
