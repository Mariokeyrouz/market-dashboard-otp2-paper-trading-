import { describe, expect, it } from "vitest";
import { nextFomcMeeting } from "./fomc-dates";

describe("nextFomcMeeting", () => {
  it("finds the soonest meeting on/after the given date", () => {
    const m = nextFomcMeeting(new Date("2026-08-13T12:00:00"));
    expect(m?.date).toBe("2026-09-16");
    expect(m?.daysFromNow).toBeGreaterThan(0);
  });

  it("returns null once every meeting is in the past", () => {
    expect(nextFomcMeeting(new Date("2099-01-01"))).toBeNull();
  });
});
