import { buildMacroData } from "@/lib/data/build-macro-data";

// Never statically cached at the route level — freshness is controlled per
// upstream fetch inside buildMacroData() via each call's own `revalidate`.
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { data, meta } = await buildMacroData();
    return Response.json({ data, meta }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    // Structurally unreachable — buildMacroData() never throws (every
    // bucket is individually caught) — but a route handler must never let
    // an unexpected error escape as an unhandled 500 with no body.
    return Response.json({ error: "macro data unavailable" }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
