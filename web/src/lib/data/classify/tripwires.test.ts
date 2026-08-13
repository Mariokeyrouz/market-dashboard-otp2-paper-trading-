import { describe, expect, it } from "vitest";
import { curveState, volCurveState } from "./tripwires";

describe("volCurveState", () => {
  it("front below back -> Contango", () => {
    expect(volCurveState(18.2, 19.6).label).toBe("Contango");
  });
  it("front above back -> Backwardation", () => {
    expect(volCurveState(22.0, 19.6).label).toBe("Backwardation");
  });
  it("equal -> Flat", () => {
    expect(volCurveState(18.0, 18.0).label).toBe("Flat");
  });
});

describe("curveState", () => {
  it("negative slope beyond the flat band -> Inverted", () => {
    expect(curveState(-0.34).label).toBe("Inverted");
  });
  it("positive slope beyond the flat band -> Normal", () => {
    expect(curveState(0.34).label).toBe("Normal");
  });
  it("within the flat band -> Flat", () => {
    expect(curveState(0.02).label).toBe("Flat");
  });
});
