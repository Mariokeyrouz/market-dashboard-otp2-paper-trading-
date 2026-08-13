import { describe, expect, it } from "vitest";
import { buildCalendarBucket } from "./macro-calendar";

describe("buildCalendarBucket", () => {
  it("drops events already in the past and keeps today/future ones, kind always macro", () => {
    const events = buildCalendarBucket(new Date("2026-08-13T12:00:00"));
    expect(events.length).toBeGreaterThan(0);
    events.forEach((e) => {
      expect(e.daysFromNow).toBeGreaterThanOrEqual(0);
      expect(e.kind).toBe("macro");
    });
  });

  it("is sorted-agnostic but every daysFromNow is computed relative to the given date", () => {
    const early = buildCalendarBucket(new Date("2026-08-13T12:00:00"));
    const later = buildCalendarBucket(new Date("2026-09-05T12:00:00"));
    expect(later.length).toBeLessThan(early.length);
  });

  it("returns an empty list once every reference date is in the past", () => {
    expect(buildCalendarBucket(new Date("2099-01-01"))).toEqual([]);
  });
});
