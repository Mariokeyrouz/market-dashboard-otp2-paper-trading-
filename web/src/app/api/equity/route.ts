import { buildEquityData } from "@/lib/data/build-equity-data";

// Never statically cached at the route level — freshness is controlled per
// upstream fetch inside buildEquityData() via each call's own `revalidate`.
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { data, meta } = await buildEquityData();
    return Response.json({ data, meta }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    // Structurally unreachable — buildEquityData() never throws (every
    // bucket is individually caught) — but a route handler must never let
    // an unexpected error escape as an unhandled 500 with no body.
    return Response.json({ error: "equity data unavailable" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
