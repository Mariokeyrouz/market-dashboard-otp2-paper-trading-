import { describe, expect, it } from "vitest";
import { parseYahooSparkPayload } from "./yahoo-spark-batch";

describe("parseYahooSparkPayload", () => {
  it("extracts price, previous close, and name per symbol", () => {
    const payload = {
      spark: {
        result: [
          { symbol: "AAPL", response: [{ meta: { regularMarketPrice: 300, chartPreviousClose: 295, longName: "Apple Inc." } }] },
          { symbol: "MSFT", response: [{ meta: { regularMarketPrice: 500, previousClose: 490, shortName: "Microsoft" } }] },
        ],
      },
    };
    const out = parseYahooSparkPayload(payload);
    expect(out.get("AAPL")).toEqual({ price: 300, previousClose: 295, name: "Apple Inc." });
    expect(out.get("MSFT")).toEqual({ price: 500, previousClose: 490, name: "Microsoft" });
  });

  it("falls back to the symbol when no name is present", () => {
    const payload = { spark: { result: [{ symbol: "XYZ", response: [{ meta: { regularMarketPrice: 1, chartPreviousClose: 1 } }] }] } };
    expect(parseYahooSparkPayload(payload).get("XYZ")?.name).toBe("XYZ");
  });

  it("skips entries missing price or previous close", () => {
    const payload = {
      spark: {
        result: [
          { symbol: "A", response: [{ meta: {} }] },
          { symbol: "B", response: [{ meta: { regularMarketPrice: 5 } }] },
        ],
      },
    };
    const out = parseYahooSparkPayload(payload);
    expect(out.size).toBe(0);
  });

  it("returns an empty map for an empty result set", () => {
    expect(parseYahooSparkPayload({ spark: { result: [] } }).size).toBe(0);
    expect(parseYahooSparkPayload({}).size).toBe(0);
  });
});
