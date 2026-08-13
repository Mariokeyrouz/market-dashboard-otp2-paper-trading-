import { describe, expect, it } from "vitest";
import { indexNearYearStartFred, parseFredCsv } from "./fred";

describe("parseFredCsv", () => {
  it("parses observations and drops the header row", () => {
    const csv = "observation_date,DGS10\n2026-08-10,4.72\n2026-08-11,4.70\n";
    expect(parseFredCsv(csv)).toEqual([
      { date: "2026-08-10", value: 4.72 },
      { date: "2026-08-11", value: 4.70 },
    ]);
  });

  it("drops rows with an empty value (holiday / no observation)", () => {
    const csv = "observation_date,DGS10\n2026-07-03,\n2026-07-06,4.48\n";
    expect(parseFredCsv(csv)).toEqual([{ date: "2026-07-06", value: 4.48 }]);
  });

  it("drops rows with a non-numeric value", () => {
    const csv = "observation_date,DGS10\n2026-07-03,.\n2026-07-06,4.48\n";
    expect(parseFredCsv(csv)).toEqual([{ date: "2026-07-06", value: 4.48 }]);
  });

  it("returns an empty array for a header-only CSV", () => {
    expect(parseFredCsv("observation_date,DGS10\n")).toEqual([]);
  });
});

describe("indexNearYearStartFred", () => {
  const obs = [
    { date: "2025-12-30", value: 1 },
    { date: "2026-01-02", value: 2 },
    { date: "2026-01-05", value: 3 },
  ];
  it("finds the first observation on/after Jan 1 of the given year", () => {
    expect(indexNearYearStartFred(obs, 2026)).toBe(1);
  });
  it("falls back to 0 if every observation is before Jan 1", () => {
    expect(indexNearYearStartFred(obs, 2027)).toBe(0);
  });
});
