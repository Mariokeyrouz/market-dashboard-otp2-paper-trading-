import { describe, expect, it } from "vitest";
import { computeRegimeHistory, type MonthlyValue } from "./regime-history";
import type { FredObservation } from "../providers/fred";

/** Builds a monthly CPI index series (chronologically compounded) that yields a chosen YoY% for each month from 2025-01 to 2026-07. */
function buildCpiSeries(yoyByMonth: Record<string, number>): FredObservation[] {
  const months: string[] = [];
  for (let y = 2024; y <= 2026; y++) {
    for (let m = 1; m <= 12; m++) {
      if (y === 2026 && m > 7) break;
      months.push(`${y}-${String(m).padStart(2, "0")}`);
    }
  }
  const values = new Map<string, number>();
  months.filter((m) => m.startsWith("2024")).forEach((m) => values.set(m, 300)); // flat base year
  months
    .filter((m) => !m.startsWith("2024"))
    .forEach((m) => {
      const [y, mm] = m.split("-").map(Number);
      const priorYearMonth = `${y - 1}-${String(mm).padStart(2, "0")}`;
      const yoy = yoyByMonth[m] ?? 3.0;
      values.set(m, values.get(priorYearMonth)! * (1 + yoy / 100));
    });
  return months.map((m) => ({ date: `${m}-01`, value: values.get(m)! }));
}

describe("computeRegimeHistory", () => {
  it("classifies the latest month and reports a since-date at a run boundary", () => {
    // Cooling CPI (YoY drifting down) + expanding ISM (all >= 50, flat-to-rising) every month -> Soft Landing throughout.
    const yoyByMonth: Record<string, number> = {};
    let yoy = 4.0;
    for (let y = 2025; y <= 2026; y++) {
      for (let m = 1; m <= 12; m++) {
        if (y === 2026 && m > 7) break;
        yoy -= 0.1;
        yoyByMonth[`${y}-${String(m).padStart(2, "0")}`] = yoy;
      }
    }
    const cpi = buildCpiSeries(yoyByMonth);
    const ism: MonthlyValue[] = [];
    for (let i = 0; i < 12; i++) {
      const month = i < 5 ? `2025-${String(8 + i).padStart(2, "0")}` : `2026-${String(i - 4).padStart(2, "0")}`;
      ism.push({ month, value: 52 + i * 0.1 });
    }

    const result = computeRegimeHistory(cpi, ism, new Date("2026-08-13"));
    expect(result.label).toBe("Soft Landing");
    expect(result.regimeDays).toBeGreaterThanOrEqual(0);
    expect(result.history.length).toBeGreaterThan(0);
    expect(result.history[result.history.length - 1].label).toBe("Soft Landing");
  });

  it("throws if no month has both a CPI trend and a growth trend available", () => {
    expect(() => computeRegimeHistory([], [{ month: "2026-07", value: 52 }], new Date("2026-08-13"))).toThrow();
  });
});
