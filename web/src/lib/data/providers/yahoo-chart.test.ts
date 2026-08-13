import { describe, expect, it } from "vitest";
import { parseYahooChartPayload } from "./yahoo-chart";

function fixture(overrides: Partial<{ price: number; prevClose: number; closes: (number | null)[] }> = {}) {
  const { price = 100, prevClose = 98, closes = [95, 96, null, 98, 100] } = overrides;
  return {
    chart: {
      result: [
        {
          meta: { regularMarketPrice: price, chartPreviousClose: prevClose },
          indicators: { quote: [{ close: closes }] },
        },
      ],
    },
  };
}

describe("parseYahooChartPayload", () => {
  it("extracts price, previous close, and drops null closes", () => {
    const out = parseYahooChartPayload(fixture());
    expect(out.regularMarketPrice).toBe(100);
    expect(out.previousClose).toBe(98);
    expect(out.closes).toEqual([95, 96, 98, 100]);
  });

  it("throws on a missing result", () => {
    expect(() => parseYahooChartPayload({ chart: { result: [] } })).toThrow();
  });

  it("throws when meta is missing regularMarketPrice", () => {
    const bad = { chart: { result: [{ meta: {}, indicators: { quote: [{ close: [1, 2] }] } }] } };
    expect(() => parseYahooChartPayload(bad)).toThrow();
  });

  it("throws when every close is null", () => {
    expect(() => parseYahooChartPayload(fixture({ closes: [null, null] }))).toThrow();
  });

  it("falls back to the second-to-last close when chartPreviousClose is absent", () => {
    const payload = fixture({ closes: [10, 20, 30] });
    delete (payload.chart.result[0].meta as { chartPreviousClose?: number }).chartPreviousClose;
    const out = parseYahooChartPayload(payload);
    expect(out.previousClose).toBe(20);
  });
});
