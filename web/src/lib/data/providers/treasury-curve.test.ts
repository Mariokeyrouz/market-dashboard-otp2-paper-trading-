import { describe, expect, it } from "vitest";
import { parseTreasuryFeed } from "./treasury-curve";

function entryXml(date: string, values: Record<string, number>): string {
  const fields = Object.entries(values)
    .map(([field, v]) => `<d:${field} m:type="Edm.Double">${v}</d:${field}>`)
    .join("\n");
  return `<entry><content type="application/xml"><m:properties><d:NEW_DATE m:type="Edm.DateTime">${date}T00:00:00</d:NEW_DATE>${fields}</m:properties></content></entry>`;
}

const FULL_TENORS = {
  BC_1MONTH: 3.79, BC_3MONTH: 3.91, BC_6MONTH: 4.02, BC_1YEAR: 4.07,
  BC_2YEAR: 4.25, BC_5YEAR: 4.40, BC_10YEAR: 4.70, BC_30YEAR: 5.23,
};

describe("parseTreasuryFeed", () => {
  it("picks the entry with the latest NEW_DATE and maps all 8 tenors", () => {
    const xml = [
      "<feed>",
      entryXml("2026-08-03", { ...FULL_TENORS, BC_10YEAR: 4.6 }),
      entryXml("2026-08-12", FULL_TENORS),
      entryXml("2026-08-05", { ...FULL_TENORS, BC_10YEAR: 4.65 }),
      "</feed>",
    ].join("\n");
    const curve = parseTreasuryFeed(xml);
    expect(curve).toEqual([
      ["1M", 3.79], ["3M", 3.91], ["6M", 4.02], ["1Y", 4.07],
      ["2Y", 4.25], ["5Y", 4.40], ["10Y", 4.70], ["30Y", 5.23],
    ]);
  });

  it("throws when there are no entries", () => {
    expect(() => parseTreasuryFeed("<feed></feed>")).toThrow();
  });

  it("throws when a tenor field is missing from the latest entry", () => {
    const partial = { ...FULL_TENORS };
    delete (partial as Partial<typeof FULL_TENORS>).BC_30YEAR;
    const xml = `<feed>${entryXml("2026-08-12", partial)}</feed>`;
    expect(() => parseTreasuryFeed(xml)).toThrow();
  });
});
