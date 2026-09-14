import { getSectors } from "@/lib/openterminal/market";

export const dynamic = "force-dynamic";

// getSectors() already swallows its own errors and resolves to [] (matching
// the original Express route, which never surfaces a 502 for this endpoint).
export async function GET() {
  const data = await getSectors();
  return Response.json(data);
}
